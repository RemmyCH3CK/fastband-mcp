"""
Fastband AI Hub - API Routes.

REST API endpoints for session management, chat, and conversations.
Includes SSE streaming for real-time chat responses.
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from fastband.hub.analyzer import PlatformAnalyzer
from fastband.hub.chat import ChatManager
from fastband.hub.models import (
    Conversation,
    HubSession,
    SessionConfig,
    SubscriptionTier,
)
from fastband.hub.session import SessionManager

logger = logging.getLogger(__name__)

# Dev mode - return mock responses when no chat manager
# Auto-detect: explicit env var OR no AI provider keys configured
_explicit_dev = os.environ.get("FASTBAND_DEV_MODE", "").lower() in ("1", "true", "yes")
_no_ai_keys = not any([
    os.environ.get("ANTHROPIC_API_KEY"),
    os.environ.get("OPENAI_API_KEY"),
    os.environ.get("GOOGLE_API_KEY"),
    os.environ.get("OLLAMA_HOST"),
])
DEV_MODE = _explicit_dev or _no_ai_keys


def _utc_now() -> datetime:
    """Get current UTC time with timezone info."""
    return datetime.now(timezone.utc)


router = APIRouter(tags=["hub"])


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================


class CreateSessionRequest(BaseModel):
    """Request to create a new session."""

    user_id: str = Field(..., description="User identifier")
    tier: str = Field(default="free", description="Subscription tier")
    project_path: str | None = Field(None, description="Project path")
    model: str = Field(default="claude-sonnet-4-20250514", description="AI model")
    temperature: float = Field(default=0.7, ge=0, le=2)
    tools_enabled: list[str] = Field(default_factory=list)


class SessionResponse(BaseModel):
    """Session response."""

    session_id: str
    user_id: str
    status: str
    tier: str
    created_at: str
    current_conversation_id: str | None = None


class ChatRequest(BaseModel):
    """Chat message request."""

    session_id: str = Field(..., description="Session identifier")
    content: str = Field(..., min_length=1, max_length=32000)
    conversation_id: str | None = Field(None, description="Conversation ID")
    stream: bool = Field(default=False, description="Stream response via SSE")


class ChatResponse(BaseModel):
    """Chat message response."""

    message_id: str
    role: str
    content: str
    tokens_used: int
    conversation_id: str
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)


class ConversationResponse(BaseModel):
    """Conversation response."""

    conversation_id: str
    session_id: str
    title: str
    status: str
    message_count: int
    created_at: str
    updated_at: str


class UsageResponse(BaseModel):
    """Usage statistics response."""

    user_id: str
    tier: str
    messages_today: int
    messages_this_minute: int
    tokens_used_today: int
    memory_entries: int


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    version: str
    active_sessions: int
    uptime_seconds: float


class AnalyzeRequest(BaseModel):
    """Request to analyze a codebase."""

    path: str | None = Field(None, description="Local path to analyze")
    github_url: str | None = Field(None, description="GitHub repository URL")
    github_token: str | None = Field(None, description="GitHub access token for private repos")


class AnalyzeResponse(BaseModel):
    """Analysis response."""

    report_id: str
    project_name: str
    connection_type: str
    phase: str
    summary: str
    confidence: float
    warnings: list[str]
    tech_stack: dict[str, Any] | None = None
    workflow: dict[str, Any] | None = None
    recommendations: list[dict[str, Any]] = Field(default_factory=list)
    file_stats: dict[str, Any] | None = None


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def _parse_tier(tier_str: str) -> SubscriptionTier:
    """Parse tier string to SubscriptionTier enum, defaulting to FREE."""
    try:
        return SubscriptionTier(tier_str.lower())
    except ValueError:
        return SubscriptionTier.FREE


def _session_to_response(session: HubSession) -> SessionResponse:
    """Convert Session model to SessionResponse."""
    return SessionResponse(
        session_id=session.session_id,
        user_id=session.config.user_id,
        status=session.status.value,
        tier=session.config.tier.value,
        created_at=session.created_at.isoformat(),
        current_conversation_id=session.current_conversation_id,
    )


def _conversation_to_response(conv: Conversation) -> ConversationResponse:
    """Convert Conversation model to ConversationResponse."""
    return ConversationResponse(
        conversation_id=conv.conversation_id,
        session_id=conv.session_id,
        title=conv.title,
        status=conv.status.value,
        message_count=len(conv.messages),
        created_at=conv.created_at.isoformat(),
        updated_at=conv.updated_at.isoformat(),
    )


# =============================================================================
# DEPENDENCIES
# =============================================================================


async def get_session_manager(request: Request) -> SessionManager:
    """Get session manager from app state."""
    manager = getattr(request.app.state, "session_manager", None)
    if not manager:
        raise HTTPException(status_code=503, detail="Service not initialized")
    return manager


async def get_chat_manager(request: Request) -> ChatManager | None:
    """Get chat manager from app state. Returns None in dev mode."""
    manager = getattr(request.app.state, "chat_manager", None)
    if not manager and not DEV_MODE:
        raise HTTPException(status_code=503, detail="AI service not available")
    return manager


# =============================================================================
# SESSION ENDPOINTS
# =============================================================================


@router.post("/sessions", response_model=SessionResponse)
async def create_session(
    request: CreateSessionRequest,
    manager: SessionManager = Depends(get_session_manager),
):
    """Create a new hub session.

    Creates a session for a user with the specified configuration.
    Sessions are automatically cleaned up after 30 minutes of inactivity.
    """
    config = SessionConfig(
        user_id=request.user_id,
        tier=_parse_tier(request.tier),
        project_path=request.project_path,
        model=request.model,
        temperature=request.temperature,
        tools_enabled=request.tools_enabled,
    )

    session = await manager.create_session(config)
    return _session_to_response(session)


@router.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: str,
    manager: SessionManager = Depends(get_session_manager),
):
    """Get session details.

    Returns the current status and configuration of a session.
    """
    session = manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return _session_to_response(session)


@router.delete("/sessions/{session_id}")
async def terminate_session(
    session_id: str,
    manager: SessionManager = Depends(get_session_manager),
):
    """Terminate a session.

    Ends the session and cleans up associated resources.
    """
    success = await manager.terminate_session(session_id)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")

    return {"status": "terminated", "session_id": session_id}


@router.get("/sessions/{session_id}/usage", response_model=UsageResponse)
async def get_session_usage(
    session_id: str,
    manager: SessionManager = Depends(get_session_manager),
):
    """Get usage statistics for a session.

    Returns current usage against tier limits.
    """
    session = manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    stats = manager.get_usage_stats(session.config.user_id)
    if not stats:
        raise HTTPException(status_code=404, detail="Usage stats not found")

    return UsageResponse(
        user_id=stats.user_id,
        tier=stats.tier.value,
        messages_today=stats.messages_today,
        messages_this_minute=stats.messages_this_minute,
        tokens_used_today=stats.tokens_used_today,
        memory_entries=stats.memory_entries,
    )


# =============================================================================
# CHAT ENDPOINTS
# =============================================================================


@router.post("/chat", response_model=ChatResponse)
async def send_message(
    request: ChatRequest,
    chat: ChatManager | None = Depends(get_chat_manager),
):
    """Send a chat message.

    Sends a message and receives the AI response.
    For streaming responses, use stream=true or the /chat/stream endpoint.
    """
    if request.stream:
        raise HTTPException(
            status_code=400,
            detail="Use /chat/stream endpoint for streaming responses",
        )

    # Dev mode mock response
    if DEV_MODE and not chat:
        import uuid

        return ChatResponse(
            message_id=str(uuid.uuid4()),
            role="assistant",
            content=f'🔧 Dev Mode: Received "{request.content}". Configure API keys for real responses.',
            tokens_used=50,
            conversation_id=request.conversation_id or "dev-conv-1",
            tool_calls=[],
        )

    try:
        response = await chat.send_message(
            session_id=request.session_id,
            content=request.content,
            conversation_id=request.conversation_id,
            stream=False,
        )

        # Get conversation ID
        session_mgr = chat.get_session_manager()
        session = session_mgr.get_session(request.session_id)
        conv_id = session.current_conversation_id if session else None

        return ChatResponse(
            message_id=response.message_id,
            role=response.role.value,
            content=response.content,
            tokens_used=response.tokens_used,
            conversation_id=conv_id or "",
            tool_calls=[
                {
                    "tool_id": tc.tool_id,
                    "tool_name": tc.tool_name,
                    "result": tc.result,
                }
                for tc in response.tool_calls
            ],
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/chat/stream")
async def stream_message(
    request: ChatRequest,
    chat: ChatManager | None = Depends(get_chat_manager),
):
    """Stream a chat response via SSE.

    Sends a message and streams the AI response in real-time
    using Server-Sent Events (SSE).

    Event types:
    - content: Response text chunk
    - tool: Tool execution notification
    - done: Stream complete
    - error: Error occurred
    """

    async def generate_dev_response():
        """Generate mock streaming response for dev mode."""
        import uuid

        # Mock AI response chunks
        mock_response = (
            "🔧 **Dev Mode Response**\n\n"
            f'I received your message: *"{request.content}"*\n\n'
            "This is a mock response because the AI backend is running in development mode. "
            "To enable real AI responses, set up your API keys:\n\n"
            "```bash\n"
            "export ANTHROPIC_API_KEY=your-key-here\n"
            "export OPENAI_API_KEY=your-key-here  # For embeddings\n"
            "```\n\n"
            "Then restart without `FASTBAND_DEV_MODE=1`."
        )

        # Stream chunks with delay for realistic effect
        words = mock_response.split(" ")
        for i in range(0, len(words), 3):
            chunk = " ".join(words[i : i + 3]) + " "
            data = json.dumps({"type": "content", "content": chunk})
            yield f"data: {data}\n\n"
            await asyncio.sleep(0.05)

        # Send done event
        data = json.dumps(
            {
                "type": "done",
                "message_id": str(uuid.uuid4()),
                "tokens_used": len(mock_response) // 4,
            }
        )
        yield f"data: {data}\n\n"

    async def generate():
        try:
            async for chunk in await chat.send_message(
                session_id=request.session_id,
                content=request.content,
                conversation_id=request.conversation_id,
                stream=True,
            ):
                if isinstance(chunk, str):
                    # Text content chunk
                    data = json.dumps({"type": "content", "content": chunk})
                    yield f"data: {data}\n\n"
                else:
                    # Final message
                    data = json.dumps(
                        {
                            "type": "done",
                            "message_id": chunk.message_id,
                            "tokens_used": chunk.tokens_used,
                        }
                    )
                    yield f"data: {data}\n\n"

        except ValueError as e:
            data = json.dumps({"type": "error", "error": str(e)})
            yield f"data: {data}\n\n"

        except Exception as e:
            logger.error(f"Streaming error: {e}")
            data = json.dumps({"type": "error", "error": "Internal error"})
            yield f"data: {data}\n\n"

    # Use mock response generator in dev mode when no chat manager
    generator = generate_dev_response() if (DEV_MODE and not chat) else generate()

    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# =============================================================================
# CONVERSATION ENDPOINTS
# =============================================================================


# Mock conversations for dev mode
_DEV_CONVERSATIONS = [
    ConversationResponse(
        conversation_id="conv-1",
        session_id="dev-session-123",
        title="Debug Python async issue",
        status="active",
        message_count=5,
        created_at=_utc_now().isoformat(),
        updated_at=_utc_now().isoformat(),
    ),
    ConversationResponse(
        conversation_id="conv-2",
        session_id="dev-session-123",
        title="Refactor authentication flow",
        status="active",
        message_count=12,
        created_at=_utc_now().isoformat(),
        updated_at=_utc_now().isoformat(),
    ),
    ConversationResponse(
        conversation_id="conv-3",
        session_id="dev-session-123",
        title="Add API rate limiting",
        status="active",
        message_count=8,
        created_at=_utc_now().isoformat(),
        updated_at=_utc_now().isoformat(),
    ),
]


@router.get("/conversations", response_model=list[ConversationResponse])
async def list_conversations(
    session_id: str,
    manager: SessionManager = Depends(get_session_manager),
):
    """List conversations for a session.

    Returns all conversations associated with the session.
    """
    # Dev mode mock response
    if DEV_MODE:
        return _DEV_CONVERSATIONS

    session = manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    conversations = manager.get_conversations(session_id)
    return [_conversation_to_response(conv) for conv in conversations]


@router.post("/conversations")
async def create_conversation(
    session_id: str,
    title: str | None = None,
    manager: SessionManager = Depends(get_session_manager),
):
    """Create a new conversation.

    Creates a new conversation thread in the session.
    """
    # Dev mode mock response
    if DEV_MODE:
        import uuid

        return ConversationResponse(
            conversation_id=str(uuid.uuid4()),
            session_id=session_id,
            title=title or "New Chat",
            status="active",
            message_count=0,
            created_at=_utc_now().isoformat(),
            updated_at=_utc_now().isoformat(),
        )

    session = manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    conversation = manager.create_conversation(session_id, title)
    if not conversation:
        raise HTTPException(status_code=400, detail="Could not create conversation")

    return _conversation_to_response(conversation)


@router.get("/conversations/{conversation_id}")
async def get_conversation(
    session_id: str,
    conversation_id: str,
    manager: SessionManager = Depends(get_session_manager),
):
    """Get conversation details with messages.

    Returns the conversation including all messages.
    """
    # Dev mode mock response
    if DEV_MODE:
        conv = next((c for c in _DEV_CONVERSATIONS if c.conversation_id == conversation_id), None)
        if conv:
            return {
                "conversation_id": conv.conversation_id,
                "session_id": conv.session_id,
                "title": conv.title,
                "status": conv.status,
                "created_at": conv.created_at,
                "updated_at": conv.updated_at,
                "messages": [],  # Empty messages for dev mode
            }
        raise HTTPException(status_code=404, detail="Conversation not found")
    conversation = manager.get_conversation(session_id, conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return {
        "conversation_id": conversation.conversation_id,
        "session_id": conversation.session_id,
        "title": conversation.title,
        "status": conversation.status.value,
        "created_at": conversation.created_at.isoformat(),
        "updated_at": conversation.updated_at.isoformat(),
        "messages": [
            {
                "message_id": msg.message_id,
                "role": msg.role.value,
                "content": msg.content,
                "created_at": msg.created_at.isoformat(),
                "tokens_used": msg.tokens_used,
                "tool_calls": [
                    {
                        "tool_id": tc.tool_id,
                        "tool_name": tc.tool_name,
                        "result": tc.result,
                    }
                    for tc in msg.tool_calls
                ],
            }
            for msg in conversation.messages
        ],
    }


# =============================================================================
# UTILITY ENDPOINTS
# =============================================================================


# Track start time for uptime
_start_time = _utc_now()


@router.get("/usage", response_model=UsageResponse)
async def get_usage(
    session_id: str,
    manager: SessionManager = Depends(get_session_manager),
):
    """Get usage statistics by session ID (query param version).

    Alternative to /sessions/{session_id}/usage that accepts session_id as query param.
    """
    # Dev mode mock response
    if DEV_MODE:
        return UsageResponse(
            user_id="dev-user-123",
            tier="pro",
            messages_today=5,
            messages_this_minute=1,
            tokens_used_today=1250,
            memory_entries=10,
        )

    session = manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    stats = manager.get_usage_stats(session.config.user_id)
    if not stats:
        raise HTTPException(status_code=404, detail="Usage stats not found")

    return UsageResponse(
        user_id=stats.user_id,
        tier=stats.tier.value,
        messages_today=stats.messages_today,
        messages_this_minute=stats.messages_this_minute,
        tokens_used_today=stats.tokens_used_today,
        memory_entries=stats.memory_entries,
    )


@router.get("/health", response_model=HealthResponse)
async def health_check(
    manager: SessionManager = Depends(get_session_manager),
):
    """Health check endpoint.

    Returns service health status and basic statistics.
    """
    from fastband import __version__

    uptime = (_utc_now() - _start_time).total_seconds()

    return HealthResponse(
        status="healthy",
        version=__version__,
        active_sessions=manager.get_active_session_count(),
        uptime_seconds=uptime,
    )


@router.get("/stats")
async def get_stats(
    manager: SessionManager = Depends(get_session_manager),
):
    """Get service statistics.

    Returns detailed statistics about sessions and usage.
    """
    return manager.get_stats()


# =============================================================================
# ANALYZER ENDPOINTS
# =============================================================================


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_codebase(request: AnalyzeRequest):
    """Analyze a codebase for MCP tool recommendations.

    Analyzes either a local directory or GitHub repository to detect:
    - Programming languages and frameworks
    - CI/CD pipelines
    - Testing frameworks
    - Database usage
    - Team workflow patterns

    Then generates MCP tool configuration recommendations.
    """
    from pathlib import Path

    analyzer = PlatformAnalyzer()

    if request.path:
        # Local directory analysis
        path = Path(request.path)
        if not path.exists():
            raise HTTPException(status_code=400, detail=f"Path does not exist: {request.path}")
        if not path.is_dir():
            raise HTTPException(status_code=400, detail=f"Path is not a directory: {request.path}")

        report = await analyzer.analyze_local(path)

    elif request.github_url:
        # GitHub repository analysis
        report = await analyzer.analyze_github(
            repo_url=request.github_url,
            access_token=request.github_token,
        )
    else:
        raise HTTPException(
            status_code=400,
            detail="Either 'path' or 'github_url' must be provided",
        )

    # Convert report to response
    return AnalyzeResponse(
        report_id=report.report_id,
        project_name=report.project_name,
        connection_type=report.connection_type.value,
        phase=report.phase.value,
        summary=report.summary,
        confidence=report.confidence,
        warnings=report.warnings,
        tech_stack={
            "primary_language": report.tech_stack.primary_language,
            "languages": report.tech_stack.languages,
            "frameworks": report.tech_stack.frameworks,
            "databases": report.tech_stack.databases,
            "ci_cd": report.tech_stack.ci_cd,
            "testing": report.tech_stack.testing,
            "package_managers": report.tech_stack.package_managers,
        }
        if report.tech_stack
        else None,
        workflow={
            "has_git": report.workflow.has_git,
            "default_branch": report.workflow.default_branch,
            "has_ci": report.workflow.has_ci,
            "has_tests": report.workflow.has_tests,
            "has_docs": report.workflow.has_docs,
            "has_docker": report.workflow.has_docker,
            "has_kubernetes": report.workflow.has_kubernetes,
        }
        if report.workflow
        else None,
        recommendations=[
            {
                "tool_category": rec.tool_category,
                "tools": rec.tools,
                "priority": rec.priority,
                "rationale": rec.rationale,
                "configuration": rec.configuration,
            }
            for rec in report.recommendations
        ],
        file_stats={
            "total_files": report.file_stats.total_files,
            "total_lines": report.file_stats.total_lines,
            "by_extension": report.file_stats.by_extension,
            "by_directory": report.file_stats.by_directory,
        }
        if report.file_stats
        else None,
    )


# =============================================================================
# AI PROVIDER CONFIGURATION ENDPOINTS
# =============================================================================


class ProviderConfigRequest(BaseModel):
    """Request to configure an AI provider."""

    provider: str
    api_key: str


class ProviderStatusResponse(BaseModel):
    """Status of configured AI providers."""

    anthropic: dict | None = None
    openai: dict | None = None


@router.get("/providers/status", response_model=ProviderStatusResponse)
async def get_provider_status():
    """Get the configuration status of AI providers.

    Returns which providers are configured and whether their keys are valid.
    """
    import os

    result = {
        "anthropic": {
            "configured": bool(os.environ.get("ANTHROPIC_API_KEY")),
            "valid": None,  # We don't validate on status check to avoid rate limits
        },
        "openai": {
            "configured": bool(os.environ.get("OPENAI_API_KEY")),
            "valid": None,
        },
    }

    return ProviderStatusResponse(**result)


@router.post("/providers/configure")
async def configure_provider(request: ProviderConfigRequest):
    """Configure an AI provider with an API key.

    Validates the key and stores it for the current session.
    Note: For persistence, set environment variables or use .env file.
    """
    import os

    provider = request.provider.lower()
    api_key = request.api_key.strip()

    if provider not in ("anthropic", "openai"):
        raise HTTPException(
            status_code=400,
            detail=f"Unknown provider: {provider}. Supported: anthropic, openai",
        )

    # Validate key format
    if provider == "anthropic" and not api_key.startswith("sk-ant-"):
        raise HTTPException(
            status_code=400,
            detail="Invalid Anthropic API key format. Should start with 'sk-ant-'",
        )

    if provider == "openai" and not api_key.startswith("sk-"):
        raise HTTPException(
            status_code=400,
            detail="Invalid OpenAI API key format. Should start with 'sk-'",
        )

    # Set the environment variable for the current process
    env_var = "ANTHROPIC_API_KEY" if provider == "anthropic" else "OPENAI_API_KEY"
    os.environ[env_var] = api_key

    # Try to validate the key by making a simple API call
    valid = await _validate_provider_key(provider, api_key)

    return {
        "provider": provider,
        "configured": True,
        "valid": valid,
        "message": "API key configured successfully"
        if valid
        else "Key saved but validation failed",
    }


async def _validate_provider_key(provider: str, api_key: str) -> bool:
    """Validate an API key by making a test request."""
    try:
        if provider == "anthropic":
            try:
                import anthropic

                client = anthropic.Anthropic(api_key=api_key)
                # Make a minimal request to validate
                client.messages.create(
                    model="claude-3-haiku-20240307",
                    max_tokens=1,
                    messages=[{"role": "user", "content": "hi"}],
                )
                return True
            except anthropic.AuthenticationError:
                return False
            except Exception:
                # Other errors might be rate limits, etc. - key might still be valid
                return True

        elif provider == "openai":
            try:
                import openai

                client = openai.OpenAI(api_key=api_key)
                # Make a minimal request to validate
                client.models.list()
                return True
            except openai.AuthenticationError:
                return False
            except Exception:
                return True

    except ImportError:
        # Provider library not installed, assume key is valid
        return True
    except Exception:
        return False


# =============================================================================
# BACKUP ENDPOINTS
# =============================================================================


class BackupCreateRequest(BaseModel):
    """Request to create a backup."""

    description: str = ""
    backup_type: str = "manual"


class BackupResponse(BaseModel):
    """Response with backup information."""

    id: str
    backup_type: str
    created_at: str
    size_bytes: int
    size_human: str
    files_count: int
    description: str


class SchedulerStatusResponse(BaseModel):
    """Response with scheduler status."""

    running: bool
    pid: int | None
    started_at: str | None
    last_backup_at: str | None
    next_backup_at: str | None
    backups_created: int
    errors: int


@router.get("/backups")
async def list_backups() -> list[BackupResponse]:
    """List all backups."""
    from pathlib import Path

    from fastband.backup.manager import BackupManager
    from fastband.core.config import get_config

    config = get_config()
    manager = BackupManager(Path.cwd(), config.backup)

    backups = manager.list_backups()
    return [
        BackupResponse(
            id=b.id,
            backup_type=b.backup_type.value,
            created_at=b.created_at.isoformat(),
            size_bytes=b.size_bytes,
            size_human=b.size_human,
            files_count=b.files_count,
            description=b.description,
        )
        for b in backups
    ]


@router.post("/backups")
async def create_backup(request: BackupCreateRequest) -> BackupResponse:
    """Create a new backup."""
    from pathlib import Path

    from fastband.backup.manager import BackupManager, BackupType
    from fastband.core.config import get_config

    config = get_config()
    manager = BackupManager(Path.cwd(), config.backup)

    # Map string to BackupType
    backup_type_map = {
        "full": BackupType.FULL,
        "incremental": BackupType.INCREMENTAL,
        "manual": BackupType.MANUAL,
    }
    backup_type = backup_type_map.get(request.backup_type, BackupType.MANUAL)

    backup = manager.create_backup(
        backup_type=backup_type,
        description=request.description,
    )

    return BackupResponse(
        id=backup.id,
        backup_type=backup.backup_type.value,
        created_at=backup.created_at.isoformat(),
        size_bytes=backup.size_bytes,
        size_human=backup.size_human,
        files_count=backup.files_count,
        description=backup.description,
    )


@router.get("/backups/{backup_id}")
async def get_backup(backup_id: str) -> BackupResponse:
    """Get a specific backup."""
    from pathlib import Path

    from fastapi import HTTPException

    from fastband.backup.manager import BackupManager
    from fastband.core.config import get_config

    config = get_config()
    manager = BackupManager(Path.cwd(), config.backup)

    backup = manager.get_backup(backup_id)
    if not backup:
        raise HTTPException(status_code=404, detail="Backup not found")

    return BackupResponse(
        id=backup.id,
        backup_type=backup.backup_type.value,
        created_at=backup.created_at.isoformat(),
        size_bytes=backup.size_bytes,
        size_human=backup.size_human,
        files_count=backup.files_count,
        description=backup.description,
    )


@router.delete("/backups/{backup_id}")
async def delete_backup(backup_id: str) -> dict:
    """Delete a backup."""
    from pathlib import Path

    from fastapi import HTTPException

    from fastband.backup.manager import BackupManager
    from fastband.core.config import get_config

    config = get_config()
    manager = BackupManager(Path.cwd(), config.backup)

    success = manager.delete_backup(backup_id)
    if not success:
        raise HTTPException(status_code=404, detail="Backup not found")

    return {"deleted": True, "id": backup_id}


@router.post("/backups/{backup_id}/restore")
async def restore_backup(backup_id: str) -> dict:
    """Restore a backup."""
    from pathlib import Path

    from fastapi import HTTPException

    from fastband.backup.manager import BackupManager
    from fastband.core.config import get_config

    config = get_config()
    manager = BackupManager(Path.cwd(), config.backup)

    backup = manager.get_backup(backup_id)
    if not backup:
        raise HTTPException(status_code=404, detail="Backup not found")

    success = manager.restore_backup(backup_id)
    if not success:
        raise HTTPException(status_code=500, detail="Restore failed")

    return {"restored": True, "id": backup_id}


@router.get("/backups/scheduler/status")
async def get_scheduler_status() -> SchedulerStatusResponse:
    """Get backup scheduler status."""
    from pathlib import Path

    from fastband.backup.scheduler import BackupScheduler
    from fastband.core.config import get_config

    config = get_config()
    scheduler = BackupScheduler(Path.cwd(), config.backup)

    status = scheduler.get_status()
    state = status.get("state", {})
    return SchedulerStatusResponse(
        running=status.get("running", False),
        pid=status.get("pid"),
        started_at=state.get("started_at"),
        last_backup_at=state.get("last_backup_at"),
        next_backup_at=state.get("next_backup_at"),
        backups_created=state.get("backups_created", 0),
        errors=state.get("errors", 0),
    )


@router.post("/backups/scheduler/start")
async def start_scheduler() -> dict:
    """Start the backup scheduler."""
    from pathlib import Path

    from fastband.backup.scheduler import BackupScheduler
    from fastband.core.config import get_config

    config = get_config()
    scheduler = BackupScheduler(Path.cwd(), config.backup)

    success = scheduler.start_daemon()
    return {"started": success}


@router.post("/backups/scheduler/stop")
async def stop_scheduler() -> dict:
    """Stop the backup scheduler."""
    from pathlib import Path

    from fastband.backup.scheduler import BackupScheduler
    from fastband.core.config import get_config

    config = get_config()
    scheduler = BackupScheduler(Path.cwd(), config.backup)

    success = scheduler.stop_daemon()
    return {"stopped": success}


# =============================================================================
# TICKET ENDPOINTS
# =============================================================================


class TicketCreateRequest(BaseModel):
    """Request to create a ticket."""

    title: str
    description: str = ""
    ticket_type: str = "task"
    priority: str = "medium"
    labels: list[str] = []
    requirements: list[str] = []


class TicketUpdateRequest(BaseModel):
    """Request to update a ticket."""

    title: str | None = None
    description: str | None = None
    ticket_type: str | None = None
    priority: str | None = None
    status: str | None = None
    labels: list[str] | None = None
    assigned_to: str | None = None
    notes: str | None = None
    resolution: str | None = None


class TicketResponse(BaseModel):
    """Response with ticket information."""

    id: str
    ticket_number: str | None
    title: str
    description: str
    ticket_type: str
    priority: str
    status: str
    assigned_to: str | None
    created_by: str
    created_at: str
    updated_at: str
    labels: list[str]
    requirements: list[str]
    notes: str
    resolution: str


@router.get("/tickets")
async def list_tickets(
    status: str | None = None,
    priority: str | None = None,
    ticket_type: str | None = None,
    assigned_to: str | None = None,
) -> list[TicketResponse]:
    """List all tickets with optional filters."""
    from pathlib import Path

    from fastband.tickets.storage import StorageFactory

    store = StorageFactory.get_default(Path.cwd())

    tickets = store.list()

    # Apply filters
    if status:
        tickets = [t for t in tickets if t.status.value == status]
    if priority:
        tickets = [t for t in tickets if t.priority.value == priority]
    if ticket_type:
        tickets = [t for t in tickets if t.ticket_type.value == ticket_type]
    if assigned_to:
        tickets = [t for t in tickets if t.assigned_to == assigned_to]

    return [
        TicketResponse(
            id=t.id,
            ticket_number=t.ticket_number,
            title=t.title,
            description=t.description,
            ticket_type=t.ticket_type.value,
            priority=t.priority.value,
            status=t.status.value,
            assigned_to=t.assigned_to,
            created_by=t.created_by,
            created_at=t.created_at.isoformat(),
            updated_at=t.updated_at.isoformat(),
            labels=t.labels,
            requirements=t.requirements,
            notes=t.notes,
            resolution=t.resolution,
        )
        for t in tickets
    ]


@router.post("/tickets")
async def create_ticket(request: TicketCreateRequest) -> TicketResponse:
    """Create a new ticket."""
    from pathlib import Path

    from fastband.tickets.models import Ticket, TicketPriority, TicketType
    from fastband.tickets.storage import StorageFactory

    store = StorageFactory.get_default(Path.cwd())

    ticket = Ticket(
        title=request.title,
        description=request.description,
        ticket_type=TicketType.from_string(request.ticket_type),
        priority=TicketPriority.from_string(request.priority),
        labels=request.labels,
        requirements=request.requirements,
        created_by="dashboard",
    )

    store.create(ticket)

    return TicketResponse(
        id=ticket.id,
        ticket_number=ticket.ticket_number,
        title=ticket.title,
        description=ticket.description,
        ticket_type=ticket.ticket_type.value,
        priority=ticket.priority.value,
        status=ticket.status.value,
        assigned_to=ticket.assigned_to,
        created_by=ticket.created_by,
        created_at=ticket.created_at.isoformat(),
        updated_at=ticket.updated_at.isoformat(),
        labels=ticket.labels,
        requirements=ticket.requirements,
        notes=ticket.notes,
        resolution=ticket.resolution,
    )


@router.get("/tickets/{ticket_id}")
async def get_ticket(ticket_id: str) -> TicketResponse:
    """Get a specific ticket."""
    from pathlib import Path

    from fastapi import HTTPException

    from fastband.tickets.storage import StorageFactory

    store = StorageFactory.get_default(Path.cwd())

    ticket = store.get(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    return TicketResponse(
        id=ticket.id,
        ticket_number=ticket.ticket_number,
        title=ticket.title,
        description=ticket.description,
        ticket_type=ticket.ticket_type.value,
        priority=ticket.priority.value,
        status=ticket.status.value,
        assigned_to=ticket.assigned_to,
        created_by=ticket.created_by,
        created_at=ticket.created_at.isoformat(),
        updated_at=ticket.updated_at.isoformat(),
        labels=ticket.labels,
        requirements=ticket.requirements,
        notes=ticket.notes,
        resolution=ticket.resolution,
    )


@router.put("/tickets/{ticket_id}")
async def update_ticket(ticket_id: str, request: TicketUpdateRequest) -> TicketResponse:
    """Update a ticket."""
    from datetime import datetime
    from pathlib import Path

    from fastapi import HTTPException

    from fastband.tickets.models import TicketPriority, TicketStatus, TicketType
    from fastband.tickets.storage import StorageFactory

    store = StorageFactory.get_default(Path.cwd())

    ticket = store.get(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    # Update fields
    if request.title is not None:
        ticket.title = request.title
    if request.description is not None:
        ticket.description = request.description
    if request.ticket_type is not None:
        ticket.ticket_type = TicketType.from_string(request.ticket_type)
    if request.priority is not None:
        ticket.priority = TicketPriority.from_string(request.priority)
    if request.status is not None:
        ticket.status = TicketStatus.from_string(request.status)
    if request.labels is not None:
        ticket.labels = request.labels
    if request.assigned_to is not None:
        ticket.assigned_to = request.assigned_to
    if request.notes is not None:
        ticket.notes = request.notes
    if request.resolution is not None:
        ticket.resolution = request.resolution

    ticket.updated_at = datetime.now()
    store.update(ticket)

    return TicketResponse(
        id=ticket.id,
        ticket_number=ticket.ticket_number,
        title=ticket.title,
        description=ticket.description,
        ticket_type=ticket.ticket_type.value,
        priority=ticket.priority.value,
        status=ticket.status.value,
        assigned_to=ticket.assigned_to,
        created_by=ticket.created_by,
        created_at=ticket.created_at.isoformat(),
        updated_at=ticket.updated_at.isoformat(),
        labels=ticket.labels,
        requirements=ticket.requirements,
        notes=ticket.notes,
        resolution=ticket.resolution,
    )


@router.delete("/tickets/{ticket_id}")
async def delete_ticket(ticket_id: str) -> dict:
    """Delete a ticket."""
    from pathlib import Path

    from fastapi import HTTPException

    from fastband.tickets.storage import StorageFactory

    store = StorageFactory.get_default(Path.cwd())

    ticket = store.get(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    store.delete(ticket_id)
    return {"deleted": True, "id": ticket_id}


@router.post("/tickets/{ticket_id}/claim")
async def claim_ticket(ticket_id: str, agent_name: str = "dashboard") -> TicketResponse:
    """Claim a ticket for an agent."""
    from datetime import datetime
    from pathlib import Path

    from fastapi import HTTPException

    from fastband.tickets.models import TicketStatus
    from fastband.tickets.storage import StorageFactory

    store = StorageFactory.get_default(Path.cwd())

    ticket = store.get(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    if ticket.status != TicketStatus.OPEN:
        raise HTTPException(status_code=400, detail="Ticket is not open")

    ticket.assigned_to = agent_name
    ticket.status = TicketStatus.IN_PROGRESS
    ticket.started_at = datetime.now()
    ticket.updated_at = datetime.now()
    store.update(ticket)

    return TicketResponse(
        id=ticket.id,
        ticket_number=ticket.ticket_number,
        title=ticket.title,
        description=ticket.description,
        ticket_type=ticket.ticket_type.value,
        priority=ticket.priority.value,
        status=ticket.status.value,
        assigned_to=ticket.assigned_to,
        created_by=ticket.created_by,
        created_at=ticket.created_at.isoformat(),
        updated_at=ticket.updated_at.isoformat(),
        labels=ticket.labels,
        requirements=ticket.requirements,
        notes=ticket.notes,
        resolution=ticket.resolution,
    )


@router.get("/tickets/stats/summary")
async def get_ticket_stats() -> dict:
    """Get ticket statistics."""
    from pathlib import Path

    from fastband.tickets.models import TicketStatus
    from fastband.tickets.storage import StorageFactory

    store = StorageFactory.get_default(Path.cwd())

    tickets = store.list()

    stats = {
        "total": len(tickets),
        "by_status": {},
        "by_priority": {},
        "by_type": {},
    }

    for ticket in tickets:
        status = ticket.status.value
        priority = ticket.priority.value
        ticket_type = ticket.ticket_type.value

        stats["by_status"][status] = stats["by_status"].get(status, 0) + 1
        stats["by_priority"][priority] = stats["by_priority"].get(priority, 0) + 1
        stats["by_type"][ticket_type] = stats["by_type"].get(ticket_type, 0) + 1

    return stats


# =============================================================================
# ONBOARDING & SYSTEM ENDPOINTS
# =============================================================================


class OnboardingDataRequest(BaseModel):
    """Onboarding configuration data."""

    projectPath: str = ""
    githubUrl: str = ""
    operationMode: str = "manual"
    backupEnabled: bool = True
    ticketsEnabled: bool = True
    providers: dict = Field(default_factory=dict)
    analysisComplete: bool = False
    bibleGenerated: bool = False
    techStack: list[str] = Field(default_factory=list)
    selectedTools: list[str] = Field(default_factory=list)
    maxRecommendedTools: int = 60


class SystemCapabilitiesResponse(BaseModel):
    """System capabilities for performance meter."""

    platform: str
    cpuCores: int
    totalRamGB: float
    availableRamGB: float
    diskFreeGB: float
    pythonVersion: str
    aiProvider: str | None
    aiModel: str | None
    contextWindow: int
    maxRecommendedTools: int
    hasPsutil: bool


@router.get("/system/capabilities")
async def get_system_capabilities() -> SystemCapabilitiesResponse:
    """Get system resource info for performance meter."""
    from fastband.core.system_capabilities import get_system_capabilities

    caps = get_system_capabilities()
    data = caps.to_dict()

    return SystemCapabilitiesResponse(
        platform=data["platform"],
        cpuCores=data["cpuCores"],
        totalRamGB=data["totalRamGB"],
        availableRamGB=data["availableRamGB"],
        diskFreeGB=data["diskFreeGB"],
        pythonVersion=data["pythonVersion"],
        aiProvider=data["aiProvider"],
        aiModel=data["aiModel"],
        contextWindow=data["contextWindow"],
        maxRecommendedTools=data["maxRecommendedTools"],
        hasPsutil=data["hasPsutil"],
    )


@router.get("/onboarding/status")
async def get_onboarding_status() -> dict:
    """Check if onboarding is complete."""
    from pathlib import Path

    # Check if fastband.yaml exists with onboarding flag
    config_path = Path.cwd() / ".fastband" / "config.yaml"
    if config_path.exists():
        try:
            import yaml

            with open(config_path) as f:
                config = yaml.safe_load(f) or {}
                return {
                    "completed": config.get("onboarding_completed", False),
                    "operationMode": config.get("operation_mode", "manual"),
                }
        except Exception:
            pass

    return {"completed": False, "operationMode": "manual"}


@router.post("/onboarding/complete")
async def complete_onboarding(data: OnboardingDataRequest) -> dict:
    """Mark onboarding complete and save configuration."""
    from pathlib import Path

    import yaml

    # Ensure .fastband directory exists
    fastband_dir = Path.cwd() / ".fastband"
    fastband_dir.mkdir(parents=True, exist_ok=True)

    # Load or create config
    config_path = fastband_dir / "config.yaml"
    config = {}
    if config_path.exists():
        try:
            with open(config_path) as f:
                config = yaml.safe_load(f) or {}
        except Exception:
            pass

    # Update config with onboarding data
    config["onboarding_completed"] = True
    config["operation_mode"] = data.operationMode
    config["backup_enabled"] = data.backupEnabled
    config["tickets_enabled"] = data.ticketsEnabled
    config["github_url"] = data.githubUrl
    config["project_path"] = data.projectPath
    config["tech_stack"] = data.techStack
    config["selected_tools"] = data.selectedTools

    # Save provider keys to environment (don't store in config file)
    # The keys should be stored securely in .env or environment

    # Save config
    with open(config_path, "w") as f:
        yaml.safe_dump(config, f, default_flow_style=False)

    return {"success": True, "message": "Onboarding complete"}


@router.get("/bible")
async def get_bible() -> dict:
    """Get current AGENT_BIBLE.md content."""
    from pathlib import Path

    bible_path = Path.cwd() / "AGENT_BIBLE.md"
    if not bible_path.exists():
        return {"exists": False, "content": ""}

    content = bible_path.read_text()
    return {"exists": True, "content": content}


@router.put("/bible")
async def update_bible(content: str = "") -> dict:
    """Update AGENT_BIBLE.md content."""
    from pathlib import Path

    bible_path = Path.cwd() / "AGENT_BIBLE.md"
    bible_path.write_text(content)

    return {"success": True, "message": "Bible updated"}


class BibleRuleRequest(BaseModel):
    """Structured rule for Agent Bible."""

    category: str = "custom"
    severity: str = "SHOULD"
    description: str


@router.post("/bible/rules")
async def add_bible_rule(rule: BibleRuleRequest) -> dict:
    """Add structured rule to Bible."""
    from pathlib import Path
    import re

    bible_path = Path.cwd() / "AGENT_BIBLE.md"

    # Read existing content
    content = ""
    if bible_path.exists():
        content = bible_path.read_text()

    # Check if structured rules section exists
    rules_start = "<!-- BEGIN_STRUCTURED_RULES -->"
    rules_end = "<!-- END_STRUCTURED_RULES -->"

    if rules_start not in content:
        # Add structured rules section
        rules_section = f"""
## Agent Laws

{rules_start}
| Severity | Category | Rule |
|----------|----------|------|
| {rule.severity} | {rule.category} | {rule.description} |
{rules_end}
"""
        content = content + "\n" + rules_section
    else:
        # Insert new rule into existing table
        new_row = f"| {rule.severity} | {rule.category} | {rule.description} |"
        content = content.replace(
            rules_end,
            f"{new_row}\n{rules_end}"
        )

    bible_path.write_text(content)
    return {"success": True, "message": "Rule added"}


@router.post("/analyze/generate-bible")
async def generate_bible(
    projectPath: str = "",
    operationMode: str = "manual",
    techStack: list[str] = [],
    regenerate: bool = False,
) -> dict:
    """Generate AGENT_BIBLE.md using AI."""
    from pathlib import Path

    # Default Bible content if AI generation fails
    mode_rules = (
        "## Automation Level: YOLO\nAgents have full autonomy within these guardrails."
        if operationMode == "yolo"
        else "## Automation Level: Manual\nAgents must confirm all actions before execution."
    )

    tech_list = "\n".join([f"- {t}" for t in techStack]) if techStack else "- Auto-detected"

    content = f"""# Agent Bible

{mode_rules}

## Core Laws

<!-- BEGIN_STRUCTURED_RULES -->
| Severity | Category | Rule |
|----------|----------|------|
| MUST | security | Never commit secrets or API keys |
| MUST | workflow | Always create feature branches for changes |
| SHOULD | testing | Write tests for new features |
| SHOULD | code_style | Follow existing code conventions |
| MUST_NOT | workflow | Never force push to main branch |
| MUST_NOT | security | Never disable security features |
<!-- END_STRUCTURED_RULES -->

## Tech Stack
{tech_list}

## Guidelines
- Keep changes focused and atomic
- Write clear commit messages
- Document significant changes
- Respect existing architecture patterns
- Ask for clarification when requirements are unclear
"""

    # Try to use AI to generate a better Bible (if available)
    try:
        # Check if we have Anthropic key
        import os
        if os.environ.get("ANTHROPIC_API_KEY") and not DEV_MODE:
            from anthropic import Anthropic

            client = Anthropic()

            prompt = f"""Generate an AGENT_BIBLE.md file for a software project with:
- Tech stack: {', '.join(techStack) if techStack else 'unknown'}
- Operation mode: {operationMode}

The bible should include:
1. Automation level header based on mode
2. Core laws table with MUST/SHOULD/MUST_NOT rules
3. Guidelines specific to the tech stack

Keep it concise but comprehensive. Use markdown format."""

            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}],
            )
            content = response.content[0].text
    except Exception as e:
        logger.warning(f"AI Bible generation failed, using default: {e}")

    # Save if regenerating or if file doesn't exist
    project_path = Path(projectPath) if projectPath else Path.cwd()
    bible_path = project_path / "AGENT_BIBLE.md"

    if regenerate or not bible_path.exists():
        bible_path.write_text(content)

    return {"success": True, "content": content}


@router.post("/analyze/tech-stack")
async def detect_tech_stack(projectPath: str = "") -> dict:
    """Detect tech stack from project files."""
    from pathlib import Path

    project = Path(projectPath) if projectPath else Path.cwd()
    stack = []

    # Check for common tech markers
    markers = {
        "package.json": ["Node.js", "JavaScript"],
        "tsconfig.json": ["TypeScript"],
        "pyproject.toml": ["Python"],
        "requirements.txt": ["Python"],
        "Cargo.toml": ["Rust"],
        "go.mod": ["Go"],
        "pom.xml": ["Java", "Maven"],
        "build.gradle": ["Java", "Gradle"],
        "Gemfile": ["Ruby"],
        "composer.json": ["PHP"],
        ".next": ["Next.js"],
        "vite.config.ts": ["Vite"],
        "tailwind.config.js": ["Tailwind CSS"],
        "docker-compose.yml": ["Docker"],
        "Dockerfile": ["Docker"],
    }

    for file, techs in markers.items():
        if (project / file).exists():
            stack.extend(techs)

    # Check for framework-specific files
    if (project / "src" / "App.tsx").exists() or (project / "src" / "App.jsx").exists():
        stack.append("React")
    if (project / "angular.json").exists():
        stack.append("Angular")
    if (project / "vue.config.js").exists():
        stack.append("Vue.js")
    if (project / "fastapi").exists() or any(project.glob("**/fastapi*.py")):
        stack.append("FastAPI")
    if (project / "flask").exists() or any(project.glob("**/flask*.py")):
        stack.append("Flask")

    # Deduplicate and return
    stack = list(dict.fromkeys(stack))

    return {"stack": stack}

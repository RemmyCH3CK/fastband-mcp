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
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from fastband.core.logging import AuditEventType, audit_log
from fastapi.responses import PlainTextResponse, StreamingResponse
from pydantic import BaseModel, Field

# Load .env file BEFORE checking for API keys
# This ensures DEV_MODE is correctly set based on configured keys
def _load_env_early():
    """Load .env from .fastband directory at module import time."""
    # Try multiple locations for .env file
    possible_paths = [
        Path.cwd() / ".fastband" / ".env",
        Path(__file__).parent.parent.parent.parent / ".fastband" / ".env",  # Project root
        Path.home() / ".fastband" / ".env",  # User home
    ]

    for env_path in possible_paths:
        if env_path.exists():
            try:
                with open(env_path) as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            key, value = line.split("=", 1)
                            if key not in os.environ:
                                os.environ[key] = value
                break  # Found and loaded, stop searching
            except Exception:
                pass

_load_env_early()

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
# PAGINATION MODELS (Enterprise)
# =============================================================================


class PaginationMeta(BaseModel):
    """Pagination metadata for list responses."""

    total: int = Field(..., description="Total number of items")
    page: int = Field(..., description="Current page number (1-indexed)")
    page_size: int = Field(..., description="Number of items per page")
    total_pages: int = Field(..., description="Total number of pages")
    has_next: bool = Field(..., description="Whether there is a next page")
    has_prev: bool = Field(..., description="Whether there is a previous page")


class PaginatedTicketsResponse(BaseModel):
    """Paginated tickets response."""

    items: list["TicketResponse"] = Field(default_factory=list)
    pagination: PaginationMeta


class PaginatedConversationsResponse(BaseModel):
    """Paginated conversations response."""

    items: list[ConversationResponse] = Field(default_factory=list)
    pagination: PaginationMeta


class PaginatedBackupsResponse(BaseModel):
    """Paginated backups response."""

    items: list["BackupResponse"] = Field(default_factory=list)
    pagination: PaginationMeta


def paginate(items: list, page: int = 1, page_size: int = 20) -> tuple[list, PaginationMeta]:
    """
    Paginate a list of items.

    Args:
        items: Full list of items
        page: Page number (1-indexed)
        page_size: Items per page

    Returns:
        Tuple of (paginated items, pagination metadata)
    """
    # Ensure valid bounds
    page = max(1, page)
    page_size = min(max(1, page_size), 100)  # Max 100 items per page

    total = len(items)
    total_pages = max(1, (total + page_size - 1) // page_size)

    # Clamp page to valid range
    page = min(page, total_pages)

    start = (page - 1) * page_size
    end = start + page_size
    paginated_items = items[start:end]

    meta = PaginationMeta(
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_prev=page > 1,
    )

    return paginated_items, meta


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

    import uuid

    # Mock response when no chat manager available (dev mode or missing API keys)
    if not chat:
        return ChatResponse(
            message_id=str(uuid.uuid4()),
            role="assistant",
            content=f'🔧 No AI provider configured. Received: "{request.content}". Configure API keys in Settings to enable chat.',
            tokens_used=50,
            conversation_id=request.conversation_id or "dev-conv-1",
            tool_calls=[],
        )

    # Check if this is a generated session ID without a real session
    # If so, create a session first or return mock response
    session_mgr = chat.get_session_manager()
    session = session_mgr.get_session(request.session_id)

    if not session:
        # Session doesn't exist - for dev/generated sessions, create one
        if request.session_id.startswith(("dev-", "chat-")):
            try:
                session = await session_mgr.create_session(
                    config=SessionConfig(
                        user_id=f"hub-user-{request.session_id[:8]}",
                        tier=SubscriptionTier.PRO,
                    ),
                )
                # Update session_id to match
                request.session_id = session.session_id
            except Exception as e:
                logger.warning(f"Could not create session: {e}")
                # Return mock response if session creation fails
                return ChatResponse(
                    message_id=str(uuid.uuid4()),
                    role="assistant",
                    content=f'🔧 Session error. Received: "{request.content}". Please refresh the page.',
                    tokens_used=50,
                    conversation_id=request.conversation_id or "dev-conv-1",
                    tool_calls=[],
                )
        else:
            raise HTTPException(status_code=400, detail=f"Session not found: {request.session_id}")

    try:
        response = await chat.send_message(
            session_id=request.session_id,
            content=request.content,
            conversation_id=request.conversation_id,
            stream=False,
        )

        # Get conversation ID
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
        # Handle session/conversation not found errors gracefully
        error_msg = str(e)
        if "not found" in error_msg.lower():
            return ChatResponse(
                message_id=str(uuid.uuid4()),
                role="assistant",
                content="🔧 Session expired. Please refresh the page to start a new session.",
                tokens_used=50,
                conversation_id=request.conversation_id or "dev-conv-1",
                tool_calls=[],
            )
        logger.warning(f"Chat request validation error: {e}")
        raise HTTPException(status_code=400, detail="Invalid request")


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
    import uuid as uuid_module

    async def generate_dev_response():
        """Generate mock streaming response for dev mode."""
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
                "message_id": str(uuid_module.uuid4()),
                "tokens_used": len(mock_response) // 4,
            }
        )
        yield f"data: {data}\n\n"

    async def generate(session_id: str):
        try:
            async for chunk in await chat.send_message(
                session_id=session_id,
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
            error_msg = str(e)
            if "not found" in error_msg.lower():
                # Session or conversation not found - return friendly message
                data = json.dumps({
                    "type": "content",
                    "content": f"🔧 {error_msg}. Please refresh the page to start a new session."
                })
                yield f"data: {data}\n\n"
                data = json.dumps({
                    "type": "done",
                    "message_id": str(uuid_module.uuid4()),
                    "tokens_used": 50,
                })
                yield f"data: {data}\n\n"
            else:
                data = json.dumps({"type": "error", "error": error_msg})
                yield f"data: {data}\n\n"

        except Exception as e:
            logger.error(f"Streaming error: {e}")
            data = json.dumps({"type": "error", "error": "Internal error"})
            yield f"data: {data}\n\n"

    # Use mock response generator when no chat manager is available
    # This can happen in dev mode OR when API keys are not configured properly
    if not chat:
        generator = generate_dev_response()
    else:
        # Check if session exists, create if needed for generated session IDs
        session_mgr = chat.get_session_manager()
        session = session_mgr.get_session(request.session_id)
        session_id = request.session_id

        if not session:
            # Session doesn't exist - for dev/generated sessions, create one
            if request.session_id.startswith(("dev-", "chat-")) or len(request.session_id) == 36:
                try:
                    session = await session_mgr.create_session(
                        config=SessionConfig(
                            user_id=f"hub-user-{request.session_id[:8]}",
                            tier=SubscriptionTier.PRO,
                        ),
                    )
                    session_id = session.session_id
                except Exception as e:
                    logger.warning(f"Could not create session for stream: {e}")
                    generator = generate_dev_response()
                    return StreamingResponse(
                        generator,
                        media_type="text/event-stream",
                        headers={
                            "Cache-Control": "no-cache",
                            "Connection": "keep-alive",
                            "X-Accel-Buffering": "no",
                        },
                    )

        generator = generate(session_id)

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


@router.get("/conversations", response_model=PaginatedConversationsResponse)
async def list_conversations(
    session_id: str,
    page: int = 1,
    page_size: int = 20,
    manager: SessionManager = Depends(get_session_manager),
):
    """List conversations for a session with pagination.

    Args:
        session_id: Session identifier
        page: Page number (1-indexed, default: 1)
        page_size: Items per page (1-100, default: 20)

    Returns:
        Paginated list of conversations with metadata.
    """
    # Dev mode or generated session ID - return mock data
    if DEV_MODE or session_id.startswith("dev-") or session_id.startswith("chat-"):
        items, pagination = paginate(_DEV_CONVERSATIONS, page, page_size)
        return PaginatedConversationsResponse(items=items, pagination=pagination)

    session = manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    conversations = manager.get_conversations(session_id)
    all_responses = [_conversation_to_response(conv) for conv in conversations]
    items, pagination = paginate(all_responses, page, page_size)
    return PaginatedConversationsResponse(items=items, pagination=pagination)


@router.post("/conversations")
async def create_conversation(
    session_id: str,
    title: str | None = None,
    manager: SessionManager = Depends(get_session_manager),
):
    """Create a new conversation.

    Creates a new conversation thread in the session.
    """
    # Dev mode or generated session ID - return mock response
    if DEV_MODE or session_id.startswith("dev-") or session_id.startswith("chat-"):
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
    # Dev mode or generated session ID - return mock response
    if DEV_MODE or session_id.startswith("dev-") or session_id.startswith("chat-"):
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
    # Dev mode mock response - also handle frontend dev sessions gracefully
    if DEV_MODE or session_id.startswith("dev-"):
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
        # Return mock data instead of 404 for better UX
        return UsageResponse(
            user_id="unknown",
            tier="free",
            messages_today=0,
            messages_this_minute=0,
            tokens_used_today=0,
            memory_entries=0,
        )

    stats = manager.get_usage_stats(session.config.user_id)
    if not stats:
        return UsageResponse(
            user_id=session.config.user_id,
            tier=session.config.tier.value,
            messages_today=0,
            messages_this_minute=0,
            tokens_used_today=0,
            memory_entries=0,
        )

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


# =============================================================================
# KUBERNETES HEALTH PROBES (Enterprise)
# =============================================================================


class LivenessResponse(BaseModel):
    """Liveness probe response."""

    status: str = Field(..., description="alive or dead")
    timestamp: str


class ReadinessResponse(BaseModel):
    """Readiness probe response with component status."""

    status: str = Field(..., description="ready or not_ready")
    timestamp: str
    checks: dict[str, bool] = Field(default_factory=dict, description="Component health checks")


@router.get("/health/live", response_model=LivenessResponse)
async def liveness_probe():
    """Kubernetes liveness probe.

    Returns 200 if the process is alive and responding.
    Use this for container restart decisions.

    Note: This endpoint skips most middleware for reliability.
    """
    return LivenessResponse(
        status="alive",
        timestamp=_utc_now().isoformat(),
    )


@router.get("/health/ready", response_model=ReadinessResponse)
async def readiness_probe(request: Request):
    """Kubernetes readiness probe.

    Checks if all dependencies are ready to serve traffic:
    - Session manager initialized
    - Database accessible (if configured)
    - AI provider available (if configured)
    - WebSocket manager running

    Returns 503 if any critical dependency is unhealthy.
    Use this for load balancer traffic routing.
    """
    checks = {}
    all_ready = True

    # Check session manager
    try:
        from fastband.hub.session import get_session_manager

        sm = get_session_manager()
        checks["session_manager"] = sm is not None
        if not checks["session_manager"]:
            all_ready = False
    except Exception:
        checks["session_manager"] = False
        all_ready = False

    # Check WebSocket manager
    try:
        from fastband.hub.websockets.manager import get_websocket_manager

        ws_manager = get_websocket_manager()
        checks["websocket_manager"] = ws_manager is not None
    except Exception:
        checks["websocket_manager"] = False
        # WebSocket manager is non-critical, don't affect readiness

    # Check AI provider availability (optional)
    try:
        app_state = getattr(request, "app", None)
        if app_state:
            chat_manager = getattr(app_state.state, "chat_manager", None)
            checks["ai_provider"] = chat_manager is not None
        else:
            checks["ai_provider"] = None  # Unknown
    except Exception:
        checks["ai_provider"] = None  # Unknown, not critical

    # Check control plane service
    try:
        app_state = getattr(request, "app", None)
        if app_state:
            control_plane = getattr(app_state.state, "control_plane_service", None)
            checks["control_plane"] = control_plane is not None
        else:
            checks["control_plane"] = None
    except Exception:
        checks["control_plane"] = None

    if not all_ready:
        raise HTTPException(
            status_code=503,
            detail="Service not ready",
        )

    return ReadinessResponse(
        status="ready",
        timestamp=_utc_now().isoformat(),
        checks=checks,
    )


@router.get("/stats")
async def get_stats(
    manager: SessionManager = Depends(get_session_manager),
):
    """Get service statistics.

    Returns detailed statistics about sessions and usage.
    """
    return manager.get_stats()


@router.get("/metrics", response_class=PlainTextResponse)
async def prometheus_metrics(
    request: Request,
    manager: SessionManager = Depends(get_session_manager),
):
    """Prometheus-compatible metrics endpoint.

    Returns metrics in Prometheus text format for monitoring and alerting.
    Enterprise feature for observability.
    """
    from fastband import __version__
    from fastband.hub.websockets.manager import get_websocket_manager

    uptime = (_utc_now() - _start_time).total_seconds()
    ws_manager = get_websocket_manager()
    ws_stats = ws_manager.get_connection_stats()
    session_stats = manager.get_stats()

    # Build Prometheus text format metrics
    lines = [
        "# HELP fastband_info Fastband Hub information",
        "# TYPE fastband_info gauge",
        f'fastband_info{{version="{__version__}"}} 1',
        "",
        "# HELP fastband_uptime_seconds Hub uptime in seconds",
        "# TYPE fastband_uptime_seconds counter",
        f"fastband_uptime_seconds {uptime:.2f}",
        "",
        "# HELP fastband_sessions_active Number of active sessions",
        "# TYPE fastband_sessions_active gauge",
        f"fastband_sessions_active {session_stats.get('active_sessions', 0)}",
        "",
        "# HELP fastband_sessions_total Total sessions created",
        "# TYPE fastband_sessions_total counter",
        f"fastband_sessions_total {session_stats.get('total_sessions', 0)}",
        "",
        "# HELP fastband_websocket_connections Active WebSocket connections",
        "# TYPE fastband_websocket_connections gauge",
        f"fastband_websocket_connections {ws_stats.get('total_connections', 0)}",
        "",
        "# HELP fastband_websocket_max Maximum WebSocket connections allowed",
        "# TYPE fastband_websocket_max gauge",
        f"fastband_websocket_max {ws_stats.get('max_connections', 1000)}",
        "",
        "# HELP fastband_websocket_capacity_percent WebSocket capacity utilization",
        "# TYPE fastband_websocket_capacity_percent gauge",
        f"fastband_websocket_capacity_percent {ws_stats.get('capacity_percent', 0):.2f}",
        "",
        "# HELP fastband_websocket_unique_ips Unique IPs connected via WebSocket",
        "# TYPE fastband_websocket_unique_ips gauge",
        f"fastband_websocket_unique_ips {ws_stats.get('unique_ips', 0)}",
        "",
    ]

    # Add subscription metrics
    subscriptions = ws_stats.get("subscriptions", {})
    lines.append("# HELP fastband_websocket_subscriptions Connections per subscription type")
    lines.append("# TYPE fastband_websocket_subscriptions gauge")
    for sub_type, count in subscriptions.items():
        lines.append(f'fastband_websocket_subscriptions{{type="{sub_type}"}} {count}')
    lines.append("")

    # Add memory metrics if available
    try:
        from fastband.memory.budget import get_budget_manager
        budget_manager = get_budget_manager()
        budget_stats = budget_manager.get_total_usage()

        lines.extend([
            "# HELP fastband_memory_sessions Active memory sessions",
            "# TYPE fastband_memory_sessions gauge",
            f"fastband_memory_sessions {budget_stats.get('active_sessions', 0)}",
            "",
            "# HELP fastband_memory_tokens_allocated Total tokens allocated",
            "# TYPE fastband_memory_tokens_allocated gauge",
            f"fastband_memory_tokens_allocated {budget_stats.get('total_allocated', 0)}",
            "",
            "# HELP fastband_memory_tokens_used Total tokens used",
            "# TYPE fastband_memory_tokens_used gauge",
            f"fastband_memory_tokens_used {budget_stats.get('total_used', 0)}",
            "",
            "# HELP fastband_memory_budget_utilization Budget utilization percentage",
            "# TYPE fastband_memory_budget_utilization gauge",
            f"fastband_memory_budget_utilization {budget_stats.get('budget_utilization', 0):.2f}",
            "",
        ])
    except Exception:
        pass  # Memory module not available

    return "\n".join(lines)


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
            raise HTTPException(status_code=400, detail="Path does not exist")
        if not path.is_dir():
            raise HTTPException(status_code=400, detail="Path is not a directory")

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

    Validates the key and stores it persistently in .env file.
    """
    import os

    provider = request.provider.lower()
    api_key = request.api_key.strip()

    if provider not in ("anthropic", "openai", "gemini"):
        raise HTTPException(
            status_code=400,
            detail=f"Unknown provider: {provider}. Supported: anthropic, openai, gemini",
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
    env_var_map = {
        "anthropic": "ANTHROPIC_API_KEY",
        "openai": "OPENAI_API_KEY",
        "gemini": "GOOGLE_API_KEY",
    }
    env_var = env_var_map[provider]
    os.environ[env_var] = api_key

    # Persist to .env file
    fastband_dir = Path.cwd() / ".fastband"
    fastband_dir.mkdir(exist_ok=True)
    env_path = fastband_dir / ".env"

    # Read existing .env if it exists
    existing_env = {}
    if env_path.exists():
        try:
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, val = line.split("=", 1)
                        existing_env[key] = val
        except Exception:
            pass

    # Update with new key
    existing_env[env_var] = api_key

    # Write .env file
    with open(env_path, "w") as f:
        f.write("# Fastband API Keys\n")
        for key, val in existing_env.items():
            f.write(f"{key}={val}\n")

    # Try to validate the key by making a simple API call
    valid, validation_msg = await _validate_provider_key(provider, api_key)

    # Audit log the API key configuration (never log the actual key!)
    audit_log(
        event_type=AuditEventType.API_KEY,
        action="configure",
        resource=f"{provider}_api_key",
        success=valid,
        details={"provider": provider, "validation_result": validation_msg},
    )

    return {
        "provider": provider,
        "configured": True,
        "valid": valid,
        "message": validation_msg if valid else f"Key saved but validation failed: {validation_msg}",
    }


class ProviderValidateRequest(BaseModel):
    """Request to validate a provider API key."""

    provider: str
    key: str | None = None
    host: str | None = None


@router.post("/providers/validate")
async def validate_provider(request: ProviderValidateRequest):
    """Validate an AI provider API key without saving it.

    Returns whether the key is valid.
    """
    provider = request.provider.lower()
    value = request.key or request.host or ""

    if not value:
        return {"valid": False, "message": "No key or host provided"}

    # For Ollama, just check if host is reachable
    if provider == "ollama":
        try:
            import httpx

            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{value}/api/tags")
                return {"valid": response.status_code == 200}
        except Exception:
            return {"valid": False, "message": "Could not connect to Ollama"}

    # For other providers, validate the key
    if provider in ("anthropic", "openai", "gemini"):
        try:
            valid, message = await _validate_provider_key(provider, value)
            return {"valid": valid, "message": message}
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            print(f"Validation error for {provider}: {tb}")
            return {"valid": False, "message": f"Validation error: {type(e).__name__}: {e}"}

    return {"valid": False, "message": f"Unknown provider: {provider}"}


async def _validate_provider_key(provider: str, api_key: str) -> tuple[bool, str]:
    """Validate an API key by making a test request.

    Returns (valid, message) tuple.
    """
    # Basic format checks
    api_key = api_key.strip()
    if not api_key:
        return False, "API key is empty"

    if " " in api_key:
        return False, "API key contains spaces - please remove them"

    if provider == "anthropic":
        if not api_key.startswith("sk-ant-"):
            return False, "Anthropic keys should start with 'sk-ant-'"
        try:
            import anthropic

            client = anthropic.Anthropic(api_key=api_key)
            client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=1,
                messages=[{"role": "user", "content": "hi"}],
            )
            return True, "Valid"
        except ImportError:
            return True, "Key accepted (anthropic library not installed)"
        except Exception as e:
            err_name = type(e).__name__
            if "AuthenticationError" in err_name:
                return False, "Invalid API key - authentication failed"
            elif "RateLimitError" in err_name:
                return True, "Valid (rate limited but key accepted)"
            else:
                # Other errors - key format might be valid
                return True, f"Key accepted ({err_name})"

    elif provider == "openai":
        if not api_key.startswith("sk-"):
            return False, "OpenAI keys should start with 'sk-'"
        try:
            import openai

            client = openai.OpenAI(api_key=api_key)
            client.models.list()
            return True, "Valid"
        except ImportError:
            return True, "Key accepted (openai library not installed)"
        except Exception as e:
            err_name = type(e).__name__
            if "AuthenticationError" in err_name:
                return False, "Invalid API key - authentication failed"
            elif "RateLimitError" in err_name:
                return True, "Valid (rate limited but key accepted)"
            else:
                return True, f"Key accepted ({err_name})"

    elif provider == "gemini":
        if not api_key.startswith("AIza"):
            return False, "Gemini keys should start with 'AIza'"
        return True, "Key format valid"

    return False, "Unknown provider"


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


class BackupConfigResponse(BaseModel):
    """Response with backup configuration."""

    backup_path: str
    retention_days: int
    interval_hours: int
    max_backups: int
    enabled: bool
    scheduler_enabled: bool


class BackupConfigUpdateRequest(BaseModel):
    """Request to update backup configuration."""

    backup_path: str | None = None
    retention_days: int | None = None
    interval_hours: int | None = None
    max_backups: int | None = None


class DirectoryEntry(BaseModel):
    """A directory entry for browsing."""

    name: str
    path: str
    is_dir: bool


class DirectoryListResponse(BaseModel):
    """Response with directory contents."""

    current_path: str
    parent_path: str | None
    entries: list[DirectoryEntry]


@router.post("/filesystem/pick-folder")
async def pick_folder_native() -> dict:
    """Open native folder picker dialog (macOS Finder)."""
    import platform
    import subprocess

    if platform.system() != "Darwin":
        raise HTTPException(status_code=501, detail="Native folder picker only available on macOS")

    try:
        # Use osascript to open native Finder folder picker
        script = '''
        tell application "Finder"
            activate
        end tell
        set selectedFolder to choose folder with prompt "Select Backup Folder"
        return POSIX path of selectedFolder
        '''
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=120,  # 2 minute timeout for user to select
        )

        if result.returncode != 0:
            # User cancelled
            raise HTTPException(status_code=400, detail="Folder selection cancelled")

        folder_path = result.stdout.strip()
        return {"path": folder_path}

    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=408, detail="Folder selection timed out")
    except Exception as e:
        logger.error(f"Native folder picker failed: {e}")
        raise HTTPException(status_code=500, detail="Folder selection failed")


@router.get("/filesystem/browse")
async def browse_filesystem(path: str = "~") -> DirectoryListResponse:
    """Browse filesystem directories for folder selection.

    Security: Only allows browsing within home directory, cwd, or /Volumes.
    """
    from pathlib import Path

    # Expand ~ to home directory
    if path == "~" or path.startswith("~/"):
        browse_path = Path(path).expanduser()
    else:
        browse_path = Path(path)

    # Resolve to absolute path
    try:
        browse_path = browse_path.resolve()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid path")

    # SECURITY: Restrict browsing to allowed roots only
    allowed_roots = [
        Path.home().resolve(),
        Path.cwd().resolve(),
        Path("/Volumes").resolve() if Path("/Volumes").exists() else None,
    ]
    allowed_roots = [r for r in allowed_roots if r is not None]

    is_allowed = any(
        browse_path == root or browse_path.is_relative_to(root)
        for root in allowed_roots
    )
    if not is_allowed:
        raise HTTPException(
            status_code=403,
            detail="Access to this directory is not allowed"
        )

    if not browse_path.exists():
        raise HTTPException(status_code=404, detail="Path not found")

    if not browse_path.is_dir():
        raise HTTPException(status_code=400, detail="Not a directory")

    # Get parent path
    parent_path = str(browse_path.parent) if browse_path.parent != browse_path else None

    # List directory contents (directories only for folder picker)
    entries = []
    try:
        for item in sorted(browse_path.iterdir(), key=lambda x: x.name.lower()):
            # Skip hidden files and common non-browsable dirs
            if item.name.startswith("."):
                continue
            if item.is_dir():
                entries.append(DirectoryEntry(
                    name=item.name,
                    path=str(item),
                    is_dir=True,
                ))
    except PermissionError:
        raise HTTPException(status_code=403, detail="Permission denied")

    return DirectoryListResponse(
        current_path=str(browse_path),
        parent_path=parent_path,
        entries=entries,
    )


@router.get("/backups/config")
async def get_backup_config() -> BackupConfigResponse:
    """Get backup configuration."""
    from fastband.core.config import get_config

    config = get_config()
    return BackupConfigResponse(
        backup_path=config.backup.backup_path,
        retention_days=config.backup.retention_days,
        interval_hours=config.backup.interval_hours,
        max_backups=config.backup.max_backups,
        enabled=config.backup.enabled,
        scheduler_enabled=config.backup.scheduler_enabled,
    )


@router.put("/backups/config")
async def update_backup_config(request: BackupConfigUpdateRequest) -> BackupConfigResponse:
    """Update backup configuration."""
    from pathlib import Path

    import yaml

    from fastband.core.config import get_config

    config = get_config()
    project_path = Path.cwd()
    config_path = project_path / ".fastband" / "config.yaml"

    # Load existing config file or create empty dict
    if config_path.exists():
        with open(config_path) as f:
            file_data = yaml.safe_load(f) or {}
    else:
        file_data = {}

    # Ensure fastband.backup structure exists
    if "fastband" not in file_data:
        file_data["fastband"] = {}
    if "backup" not in file_data["fastband"]:
        file_data["fastband"]["backup"] = {}

    backup_config = file_data["fastband"]["backup"]

    # Update fields if provided
    if request.backup_path is not None:
        backup_config["backup_path"] = request.backup_path
        config.backup.backup_path = request.backup_path
    if request.retention_days is not None:
        backup_config["retention_days"] = request.retention_days
        config.backup.retention_days = request.retention_days
    if request.interval_hours is not None:
        backup_config["interval_hours"] = request.interval_hours
        config.backup.interval_hours = request.interval_hours
    if request.max_backups is not None:
        backup_config["max_backups"] = request.max_backups
        config.backup.max_backups = request.max_backups

    # Save updated config
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, "w") as f:
        yaml.dump(file_data, f, default_flow_style=False)

    return BackupConfigResponse(
        backup_path=config.backup.backup_path,
        retention_days=config.backup.retention_days,
        interval_hours=config.backup.interval_hours,
        max_backups=config.backup.max_backups,
        enabled=config.backup.enabled,
        scheduler_enabled=config.backup.scheduler_enabled,
    )


@router.get("/backups")
async def list_backups(
    page: int = 1,
    page_size: int = 20,
) -> PaginatedBackupsResponse:
    """List all backups with pagination.

    Args:
        page: Page number (1-indexed, default: 1)
        page_size: Items per page (1-100, default: 20)

    Returns:
        Paginated list of backups with metadata.
    """
    from pathlib import Path

    from fastband.backup.manager import BackupManager
    from fastband.core.config import get_config

    config = get_config()
    manager = BackupManager(Path.cwd(), config.backup)

    backups = manager.list_backups()
    all_responses = [
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

    items, pagination = paginate(all_responses, page, page_size)
    return PaginatedBackupsResponse(items=items, pagination=pagination)


@router.post("/backups")
async def create_backup(request: BackupCreateRequest) -> BackupResponse:
    """Create a new backup."""
    from pathlib import Path

    from fastband.backup.manager import BackupManager, BackupType
    from fastband.core.config import get_config

    try:
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

        # Audit log backup creation
        audit_log(
            event_type=AuditEventType.BACKUP,
            action="create",
            resource=backup.id,
            details={
                "type": backup.backup_type.value,
                "size_bytes": backup.size_bytes,
                "files_count": backup.files_count,
            },
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
    except Exception as e:
        logger.error(f"Backup creation failed: {e}")
        raise HTTPException(status_code=500, detail="Backup creation failed")


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
    import subprocess
    import sys
    from pathlib import Path

    from fastband.backup.scheduler import BackupScheduler
    from fastband.core.config import get_config

    try:
        config = get_config()
        scheduler = BackupScheduler(Path.cwd(), config.backup)

        # Check if already running
        if scheduler.is_running():
            return {"started": True, "message": "Scheduler already running"}

        # Check if scheduler is enabled
        if not config.backup.enabled or not config.backup.scheduler_enabled:
            return {"started": False, "message": "Scheduler is disabled in config"}

        # Use subprocess to start scheduler instead of fork (safer in async context)
        try:
            proc = subprocess.Popen(
                [sys.executable, "-m", "fastband.backup.scheduler", "--start"],
                cwd=str(Path.cwd()),
                start_new_session=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            # Wait briefly for it to start
            import time
            time.sleep(0.5)

            # Check if it started successfully
            if scheduler.is_running():
                return {"started": True}
            else:
                return {"started": False, "message": "Scheduler process started but not running"}
        except Exception as e:
            logger.error(f"Failed to start scheduler subprocess: {e}")
            return {"started": False, "message": "Failed to start scheduler process"}

    except Exception as e:
        logger.error(f"Scheduler start failed: {e}")
        raise HTTPException(status_code=500, detail="Scheduler start failed")


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
    page: int = 1,
    page_size: int = 20,
) -> PaginatedTicketsResponse:
    """List all tickets with optional filters and pagination.

    Args:
        status: Filter by ticket status
        priority: Filter by priority level
        ticket_type: Filter by ticket type
        assigned_to: Filter by assignee
        page: Page number (1-indexed, default: 1)
        page_size: Items per page (1-100, default: 20)

    Returns:
        Paginated list of tickets with metadata.
    """
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

    all_responses = [
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

    items, pagination = paginate(all_responses, page, page_size)
    return PaginatedTicketsResponse(items=items, pagination=pagination)


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

    ticket.updated_at = datetime.now(timezone.utc)
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
    ticket.started_at = datetime.now(timezone.utc)
    ticket.updated_at = datetime.now(timezone.utc)
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
async def complete_onboarding(data: OnboardingDataRequest, request: Request) -> dict:
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

    # Save provider keys to .env file and set in environment
    env_path = fastband_dir / ".env"
    env_lines = []

    # Read existing .env if it exists
    existing_env = {}
    if env_path.exists():
        try:
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, val = line.split("=", 1)
                        existing_env[key] = val
        except Exception:
            pass

    # Update with new provider keys
    if data.providers:
        if data.providers.get("anthropic", {}).get("key"):
            key = data.providers["anthropic"]["key"]
            existing_env["ANTHROPIC_API_KEY"] = key
            os.environ["ANTHROPIC_API_KEY"] = key
        if data.providers.get("openai", {}).get("key"):
            key = data.providers["openai"]["key"]
            existing_env["OPENAI_API_KEY"] = key
            os.environ["OPENAI_API_KEY"] = key
        if data.providers.get("gemini", {}).get("key"):
            key = data.providers["gemini"]["key"]
            existing_env["GOOGLE_API_KEY"] = key
            os.environ["GOOGLE_API_KEY"] = key
        if data.providers.get("ollama", {}).get("host"):
            host = data.providers["ollama"]["host"]
            existing_env["OLLAMA_HOST"] = host
            os.environ["OLLAMA_HOST"] = host

    # Write .env file
    with open(env_path, "w") as f:
        f.write("# Fastband API Keys - Generated by onboarding\n")
        for key, val in existing_env.items():
            f.write(f"{key}={val}\n")

    # Save config
    with open(config_path, "w") as f:
        yaml.safe_dump(config, f, default_flow_style=False)

    # Attempt to sync onboarding data to Supabase profile (optional)
    supabase_synced = False
    try:
        supabase_url = os.environ.get("SUPABASE_URL", "")
        supabase_key = os.environ.get("SUPABASE_KEY", "")

        if supabase_url and supabase_key:
            # Get user token from Authorization header if available
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                access_token = auth_header.split(" ", 1)[1]

                # Import supabase client
                try:
                    from supabase import create_client

                    client = create_client(supabase_url, supabase_key)

                    # Get user from token
                    user_response = client.auth.get_user(access_token)
                    if user_response and user_response.user:
                        user_id = user_response.user.id

                        # Update profiles table
                        profile_data = {
                            "id": user_id,
                            "onboarding_completed": True,
                            "operation_mode": data.operationMode,
                            "onboarding_data": {
                                "projectPath": data.projectPath,
                                "githubUrl": data.githubUrl,
                                "backupEnabled": data.backupEnabled,
                                "ticketsEnabled": data.ticketsEnabled,
                                "techStack": data.techStack,
                                "selectedTools": data.selectedTools,
                                "maxRecommendedTools": data.maxRecommendedTools,
                            },
                            "updated_at": datetime.now(timezone.utc).isoformat(),
                        }

                        # Upsert profile
                        client.table("profiles").upsert(profile_data).execute()
                        supabase_synced = True
                        logger.info(f"Synced onboarding data to Supabase for user {user_id}")
                except ImportError:
                    logger.debug("supabase-py not installed - skipping cloud sync")
                except Exception as e:
                    logger.warning(f"Failed to sync to Supabase: {e}")
    except Exception as e:
        logger.warning(f"Supabase sync error: {e}")

    # Reinitialize chat manager with new API keys (no server restart needed)
    chat_reinitialized = False
    try:
        from fastband.hub.api.app import reinitialize_chat_manager

        chat_reinitialized = await reinitialize_chat_manager(request.app)
    except Exception as e:
        logger.warning(f"Could not reinitialize chat: {e}")

    return {
        "success": True,
        "message": "Onboarding complete",
        "cloudSynced": supabase_synced,
        "chatReady": chat_reinitialized,
    }


# Rate limiting for server restart (simple in-memory)
_last_restart_time: float = 0
_restart_cooldown_seconds: float = 60.0  # Minimum 60s between restarts

# Valid restart tokens (populated from config or generated)
_valid_restart_tokens: set[str] = set()


def _get_or_create_restart_token() -> str:
    """Get or create a restart token from environment or generate one."""
    import secrets
    token = os.environ.get("FASTBAND_RESTART_TOKEN")
    if not token:
        # Generate a secure token and store it
        token = secrets.token_urlsafe(32)
        os.environ["FASTBAND_RESTART_TOKEN"] = token
    _valid_restart_tokens.add(token)
    return token


def _validate_restart_token(token: str) -> bool:
    """Validate a restart token."""
    if not token:
        return False
    # Ensure we have a valid token to compare against
    _get_or_create_restart_token()
    return token in _valid_restart_tokens


@router.post("/server/restart")
async def restart_server(request: Request) -> dict:
    """Restart the Fastband Hub server to apply new configuration.

    This schedules a graceful server restart that will:
    1. Complete any pending requests
    2. Reload configuration from .fastband/config.yaml
    3. Apply new provider settings

    Security:
    - Requires valid Bearer token (FASTBAND_RESTART_TOKEN env var) OR localhost
    - Rate limited to once per 60 seconds
    - Localhost requests are allowed for local development
    """
    import signal
    import threading
    import time as time_module

    global _last_restart_time

    # Rate limiting check
    current_time = time_module.time()
    if current_time - _last_restart_time < _restart_cooldown_seconds:
        remaining = int(_restart_cooldown_seconds - (current_time - _last_restart_time))
        raise HTTPException(
            status_code=429,
            detail=f"Rate limited. Try again in {remaining} seconds."
        )

    # SECURITY: Proper authorization check with token validation
    auth_header = request.headers.get("Authorization", "")
    client_host = request.client.host if request.client else "unknown"

    # Check if localhost (allowed for local development)
    is_localhost = client_host in ("127.0.0.1", "localhost", "::1")

    # Validate Bearer token if provided
    is_authenticated = False
    if auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()  # Extract token after "Bearer "
        is_authenticated = _validate_restart_token(token)
        if not is_authenticated:
            logger.warning(f"Invalid restart token from {client_host}")

    # Require either localhost OR valid authentication
    if not (is_localhost or is_authenticated):
        logger.warning(f"Unauthorized restart attempt from {client_host}")
        raise HTTPException(
            status_code=401,
            detail="Authentication required for server restart. Use Bearer token or connect from localhost."
        )

    # Update rate limit timestamp
    _last_restart_time = current_time

    # Audit log the restart request
    audit_log(
        event_type=AuditEventType.SERVER,
        action="restart",
        ip_address=client_host,
        details={"authenticated": is_authenticated, "localhost": is_localhost},
    )

    # Log the restart request
    logger.info(f"Server restart requested by {client_host} (auth: {is_authenticated})")

    def delayed_restart():
        """Perform restart after a short delay to allow response to be sent."""
        time_module.sleep(1)  # Wait for response to be sent
        try:
            # Send SIGTERM for graceful shutdown
            # Requires process manager (systemd, docker, supervisor) to restart
            logger.info("Server restart initiated - graceful shutdown...")
            os.kill(os.getpid(), signal.SIGTERM)
        except Exception as e:
            logger.error(f"Failed to restart server: {e}")

    # Schedule restart in background thread
    restart_thread = threading.Thread(target=delayed_restart, daemon=True)
    restart_thread.start()

    return {
        "success": True,
        "message": "Server restart scheduled. Please wait a few seconds and refresh.",
    }


@router.get("/server/status")
async def server_status() -> dict:
    """Check if server is running and ready."""
    return {
        "status": "running",
        "ready": True,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


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


class GenerateBibleRequest(BaseModel):
    """Request to generate AGENT_BIBLE.md."""

    projectPath: str = ""
    operationMode: str = "manual"
    techStack: list[str] = Field(default_factory=list)
    regenerate: bool = False


@router.post("/analyze/generate-bible")
async def generate_bible(request: GenerateBibleRequest) -> dict:
    """Generate AGENT_BIBLE.md using AI with comprehensive template."""
    from pathlib import Path
    from datetime import datetime
    import importlib.resources
    import re

    projectPath = request.projectPath
    operationMode = request.operationMode
    techStack = request.techStack
    regenerate = request.regenerate

    # Security: Validate and sanitize project path to prevent path traversal
    if projectPath:
        try:
            project_path = Path(projectPath).resolve()
            allowed_base = Path.cwd().resolve()
            # Ensure path is within current working directory
            if not str(project_path).startswith(str(allowed_base)):
                raise HTTPException(
                    status_code=400,
                    detail="Invalid project path: must be within project directory"
                )
        except Exception as e:
            logger.warning(f"Invalid project path rejected: {projectPath} - {e}")
            raise HTTPException(status_code=400, detail="Invalid project path")
    else:
        project_path = Path.cwd()

    # Security: Sanitize techStack to prevent prompt injection
    ALLOWED_TECH_PATTERN = re.compile(r'^[a-zA-Z0-9\s\.\-\+\#\/]+$')
    sanitized_tech_stack = []
    for tech in techStack:
        # Only allow alphanumeric, spaces, dots, dashes, plus, hash, slash
        if ALLOWED_TECH_PATTERN.match(tech) and len(tech) < 50:
            sanitized_tech_stack.append(tech.strip())
        else:
            logger.warning(f"Rejected suspicious tech stack entry: {tech[:50]}")
    techStack = sanitized_tech_stack

    # Security: Validate operation mode
    if operationMode not in ("manual", "yolo"):
        operationMode = "manual"

    # Load the template as a reference
    template_content = ""
    try:
        template_path = Path(__file__).parent.parent.parent / "templates" / "AGENT_BIBLE_TEMPLATE.md"
        if template_path.exists():
            template_content = template_path.read_text()
    except Exception as e:
        logger.warning(f"Could not load template: {e}")

    # Operation mode descriptions
    if operationMode == "yolo":
        mode_header = "Automation Level: YOLO (Full Autonomy)"
        mode_description = """Agents have FULL AUTONOMY to:
- Claim and work on tickets without confirmation
- Push code changes to development branches
- Merge approved pull requests
- Deploy to staging environments
- Make architectural decisions within established patterns

Agents MUST still:
- Follow all security rules
- Stay within the guardrails defined in this Bible
- Report significant decisions to the ops log
- Never bypass review requirements for production"""
    else:
        mode_header = "Automation Level: Manual (Confirmation Required)"
        mode_description = """Agents MUST confirm with user before:
- Making code changes
- Pushing to any branch
- Merging pull requests
- Deploying to any environment
- Making architectural decisions

Agents CAN autonomously:
- Read and analyze code
- Run tests and linters
- Prepare changes for review
- Generate reports and documentation"""

    # Build tech-specific rules
    tech_rules = []
    tech_commands = []
    tech_patterns = []

    for tech in techStack:
        tech_lower = tech.lower()
        if "python" in tech_lower:
            tech_rules.extend([
                "| MUST | code_style | Use type hints for function parameters and returns |",
                "| SHOULD | code_style | Follow PEP 8 style guidelines |",
                "| MUST | testing | Run pytest before committing |",
            ])
            tech_commands.append("- `pytest` - Run tests")
            tech_commands.append("- `ruff check .` - Lint code")
        if "typescript" in tech_lower or "javascript" in tech_lower:
            tech_rules.extend([
                "| MUST | code_style | Use TypeScript strict mode |",
                "| SHOULD | code_style | Prefer const over let |",
                "| MUST | testing | Run npm test before committing |",
            ])
            tech_commands.append("- `npm test` - Run tests")
            tech_commands.append("- `npm run lint` - Lint code")
        if "react" in tech_lower:
            tech_rules.extend([
                "| SHOULD | code_style | Use functional components with hooks |",
                "| MUST | code_style | Follow component naming conventions (PascalCase) |",
            ])
        if "docker" in tech_lower:
            tech_rules.extend([
                "| MUST | workflow | Rebuild containers after dependency changes |",
                "| SHOULD | security | Use multi-stage builds for production |",
            ])
            tech_commands.append("- `docker-compose build` - Rebuild containers")
            tech_commands.append("- `docker-compose up -d` - Start services")
        if "fastapi" in tech_lower or "flask" in tech_lower:
            tech_rules.extend([
                "| MUST | security | Validate all user input with Pydantic models |",
                "| SHOULD | code_style | Use async endpoints where appropriate |",
            ])
        if "next" in tech_lower:
            tech_rules.extend([
                "| SHOULD | code_style | Use App Router patterns |",
                "| MUST | code_style | Server components by default, client only when needed |",
            ])
            tech_commands.append("- `npm run dev` - Start development server")
            tech_commands.append("- `npm run build` - Build for production")

    # Generate tech stack section
    tech_list = "\n".join([f"- {t}" for t in techStack]) if techStack else "- To be detected"
    tech_rules_str = "\n".join(tech_rules) if tech_rules else ""
    tech_commands_str = "\n".join(tech_commands) if tech_commands else "- See package.json or pyproject.toml for available commands"

    # Default fallback content
    today = datetime.now().strftime("%Y-%m-%d")
    content = f"""# THE AGENT BIBLE

**Version:** 1.0.0
**Last Updated:** {today}
**Status:** AUTHORITATIVE - THIS IS THE ONLY AGENT DOCUMENTATION

---

## Table of Contents

1. [The Hierarchy of Authority](#1-the-hierarchy-of-authority)
2. [The Core Laws](#2-the-core-laws)
3. [Project Overview](#3-project-overview)
4. [Workflow Guidelines](#4-workflow-guidelines)
5. [Code Standards](#5-code-standards)
6. [Testing Requirements](#6-testing-requirements)
7. [Security Rules](#7-security-rules)
8. [Quick Reference](#8-quick-reference)

---

## 1. THE HIERARCHY OF AUTHORITY

```
┌─────────────────────────────────────────────────────┐
│                USER ("The Boss")                    │
│         Final authority on all decisions            │
│       Can override any rule when necessary          │
└─────────────────────────┬───────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────┐
│           AGENT_BIBLE.md ("The Law")                │
│     Single authoritative documentation source       │
│        Defines all rules and constraints            │
└─────────────────────────┬───────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────┐
│              AGENTS ("The Crew")                    │
│      Follow the law, serve the user's goals         │
│            without exception                        │
└─────────────────────────────────────────────────────┘
```

**Key Principle:** When in doubt, escalate UP the hierarchy.

---

## 2. THE CORE LAWS

These laws are absolute. Violation is unacceptable.

<!-- BEGIN_STRUCTURED_RULES -->
| Severity | Category | Rule |
|----------|----------|------|
| MUST | security | Never commit secrets, API keys, or credentials to version control |
| MUST | workflow | Always create feature branches for changes |
| MUST | workflow | Write clear, descriptive commit messages |
| MUST | code_style | Follow existing codebase conventions and patterns |
| MUST | testing | Verify changes work before marking complete |
| SHOULD | testing | Write tests for new features |
| SHOULD | documentation | Document significant changes and decisions |
| SHOULD | code_style | Keep functions focused and single-purpose |
| MUST_NOT | workflow | Never force push to main/master branch |
| MUST_NOT | security | Never disable security features or linters |
| MUST_NOT | workflow | Never merge without proper review |
{tech_rules_str}
<!-- END_STRUCTURED_RULES -->

---

## 3. PROJECT OVERVIEW

### Tech Stack

{tech_list}

---

## 4. WORKFLOW GUIDELINES

### {mode_header}

{mode_description}

### Standard Workflow

1. **Understand the Task** - Read requirements, identify affected files
2. **Create Feature Branch** - Branch from main/development
3. **Implement Changes** - Follow code standards, make atomic commits
4. **Verify Changes** - Run tests, manually verify functionality
5. **Submit for Review** - Create PR with clear description

---

## 5. CODE STANDARDS

### General Principles

- **Readability First**: Code should be self-documenting
- **Consistency**: Match existing patterns in the codebase
- **Simplicity**: Prefer simple solutions over clever ones
- **DRY**: Don't Repeat Yourself, but don't over-abstract

---

## 6. TESTING REQUIREMENTS

### Before Completing Any Task

- [ ] Code compiles/runs without errors
- [ ] Existing tests pass
- [ ] New functionality has been manually verified
- [ ] No console errors or warnings introduced
- [ ] Edge cases considered

---

## 7. SECURITY RULES

### Never Do

- Commit secrets, API keys, or credentials
- Store sensitive data in plain text
- Disable security features
- Ignore security warnings
- Use hardcoded passwords

### Always Do

- Use environment variables for secrets
- Validate and sanitize user input
- Follow principle of least privilege
- Keep dependencies updated

---

## 8. QUICK REFERENCE

### Essential Commands

{tech_commands_str}

### When Stuck

1. Re-read this Bible and relevant documentation
2. Search codebase for similar implementations
3. Try at least 2 different approaches
4. Document what you tried and why it failed
5. Escalate to human with clear problem description

---

**END OF AGENT BIBLE**

*This document is the single source of truth for agent behavior in this project.*
"""

    # Try to use AI to generate an enhanced Bible using template as reference
    try:
        import os
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if api_key and not DEV_MODE:
            from anthropic import Anthropic

            client = Anthropic()

            prompt = f"""You are generating a comprehensive AGENT_BIBLE.md for a software project.

## Project Context
- Tech stack: {', '.join(techStack) if techStack else 'To be detected'}
- Operation mode: {operationMode} ({'Full autonomy within guardrails' if operationMode == 'yolo' else 'Confirmation required for actions'})

## Reference Template
Use this template structure as your model. Your output should follow this format but be customized for the specific tech stack:

{template_content[:3000] if template_content else 'Standard Agent Bible format'}

## Requirements
1. Use the EXACT same section structure as the template
2. Include the hierarchy of authority ASCII diagram
3. Include a structured rules table with <!-- BEGIN_STRUCTURED_RULES --> markers
4. Add tech-stack-specific rules (e.g., for React: component patterns, for Python: type hints)
5. Set automation level based on operation mode: {operationMode}
6. Include practical commands specific to the tech stack
7. Keep it comprehensive but actionable

## Tech-Specific Rules to Include
For {', '.join(techStack) if techStack else 'general projects'}:
- Language-specific style guidelines
- Testing requirements
- Build/deployment commands
- Security considerations

Generate a complete AGENT_BIBLE.md that agents can follow immediately. Use markdown format.
Today's date: {today}"""

            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4000,
                messages=[{"role": "user", "content": prompt}],
            )
            content = response.content[0].text
    except Exception as e:
        logger.warning(f"AI Bible generation failed, using default: {e}")

    # Save if regenerating or if file doesn't exist
    # Note: project_path is already validated and sanitized at the start of this function
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


# ============================================
# DIRECTORY BROWSER ENDPOINTS
# ============================================


class DirectoryListRequest(BaseModel):
    """Request to list directory contents."""

    path: str = Field(default="~", description="Directory path to list")


class DirectoryEntry(BaseModel):
    """A directory entry."""

    name: str
    path: str
    is_dir: bool
    is_hidden: bool


class DirectoryListResponse(BaseModel):
    """Response with directory listing."""

    current_path: str
    parent_path: str | None
    entries: list[DirectoryEntry]


@router.post("/browse/directories", response_model=DirectoryListResponse)
async def browse_directories(request: DirectoryListRequest):
    """Browse directories on the local filesystem.

    Used by the onboarding wizard for project path selection.
    Only returns directories, not files.

    Security: Only allows browsing within home directory, cwd, or /Volumes.
    """
    from pathlib import Path

    # Expand ~ and resolve path
    try:
        path = Path(request.path).expanduser().resolve()
    except Exception:
        path = Path.home()

    # SECURITY: Restrict browsing to allowed roots only
    allowed_roots = [
        Path.home().resolve(),
        Path.cwd().resolve(),
        Path("/Volumes").resolve() if Path("/Volumes").exists() else None,
    ]
    allowed_roots = [r for r in allowed_roots if r is not None]

    is_allowed = any(
        path == root or path.is_relative_to(root)
        for root in allowed_roots
    )
    if not is_allowed:
        # Fall back to home directory if path not allowed
        path = Path.home()

    # If path doesn't exist or isn't a directory, fall back to home
    if not path.exists() or not path.is_dir():
        path = Path.home()

    # Get parent path (None if at root)
    parent = path.parent if path != path.parent else None

    entries: list[DirectoryEntry] = []

    try:
        for item in sorted(path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
            # Only include directories
            if not item.is_dir():
                continue

            # Skip system directories on macOS/Linux
            if item.name in ('.Trash', 'Library', '$RECYCLE.BIN', 'System Volume Information'):
                continue

            try:
                # Check if we can access this directory
                list(item.iterdir())
                entries.append(DirectoryEntry(
                    name=item.name,
                    path=str(item),
                    is_dir=True,
                    is_hidden=item.name.startswith('.'),
                ))
            except PermissionError:
                # Skip directories we can't access
                continue
    except PermissionError:
        # Can't read this directory, return empty list
        pass

    return DirectoryListResponse(
        current_path=str(path),
        parent_path=str(parent) if parent else None,
        entries=entries,
    )


@router.get("/browse/home")
async def get_home_directory():
    """Get the user's home directory path."""
    from pathlib import Path

    home = Path.home()
    return {"path": str(home)}

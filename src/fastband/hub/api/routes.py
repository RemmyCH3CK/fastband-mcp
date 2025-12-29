"""
Fastband AI Hub - API Routes.

REST API endpoints for session management, chat, and conversations.
Includes SSE streaming for real-time chat responses.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from fastband.hub.models import (
    SessionConfig,
    SessionStatus,
    SubscriptionTier,
    MessageRole,
)
from fastband.hub.session import SessionManager
from fastband.hub.chat import ChatManager

logger = logging.getLogger(__name__)

router = APIRouter(tags=["hub"])


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================


class CreateSessionRequest(BaseModel):
    """Request to create a new session."""

    user_id: str = Field(..., description="User identifier")
    tier: str = Field(default="free", description="Subscription tier")
    project_path: Optional[str] = Field(None, description="Project path")
    model: str = Field(default="claude-sonnet-4-20250514", description="AI model")
    temperature: float = Field(default=0.7, ge=0, le=2)
    tools_enabled: List[str] = Field(default_factory=list)


class SessionResponse(BaseModel):
    """Session response."""

    session_id: str
    user_id: str
    status: str
    tier: str
    created_at: str
    current_conversation_id: Optional[str] = None


class ChatRequest(BaseModel):
    """Chat message request."""

    session_id: str = Field(..., description="Session identifier")
    content: str = Field(..., min_length=1, max_length=32000)
    conversation_id: Optional[str] = Field(None, description="Conversation ID")
    stream: bool = Field(default=False, description="Stream response via SSE")


class ChatResponse(BaseModel):
    """Chat message response."""

    message_id: str
    role: str
    content: str
    tokens_used: int
    conversation_id: str
    tool_calls: List[Dict[str, Any]] = Field(default_factory=list)


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


# =============================================================================
# DEPENDENCIES
# =============================================================================


async def get_session_manager(request: Request) -> SessionManager:
    """Get session manager from app state."""
    manager = getattr(request.app.state, "session_manager", None)
    if not manager:
        raise HTTPException(status_code=503, detail="Service not initialized")
    return manager


async def get_chat_manager(request: Request) -> ChatManager:
    """Get chat manager from app state."""
    manager = getattr(request.app.state, "chat_manager", None)
    if not manager:
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
    try:
        tier = SubscriptionTier(request.tier.lower())
    except ValueError:
        tier = SubscriptionTier.FREE

    config = SessionConfig(
        user_id=request.user_id,
        tier=tier,
        project_path=request.project_path,
        model=request.model,
        temperature=request.temperature,
        tools_enabled=request.tools_enabled,
    )

    session = await manager.create_session(config)

    return SessionResponse(
        session_id=session.session_id,
        user_id=session.config.user_id,
        status=session.status.value,
        tier=session.config.tier.value,
        created_at=session.created_at.isoformat(),
        current_conversation_id=session.current_conversation_id,
    )


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

    return SessionResponse(
        session_id=session.session_id,
        user_id=session.config.user_id,
        status=session.status.value,
        tier=session.config.tier.value,
        created_at=session.created_at.isoformat(),
        current_conversation_id=session.current_conversation_id,
    )


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
    chat: ChatManager = Depends(get_chat_manager),
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
    chat: ChatManager = Depends(get_chat_manager),
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
                    data = json.dumps({
                        "type": "done",
                        "message_id": chunk.message_id,
                        "tokens_used": chunk.tokens_used,
                    })
                    yield f"data: {data}\n\n"

        except ValueError as e:
            data = json.dumps({"type": "error", "error": str(e)})
            yield f"data: {data}\n\n"

        except Exception as e:
            logger.error(f"Streaming error: {e}")
            data = json.dumps({"type": "error", "error": "Internal error"})
            yield f"data: {data}\n\n"

    return StreamingResponse(
        generate(),
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


@router.get("/conversations", response_model=List[ConversationResponse])
async def list_conversations(
    session_id: str,
    manager: SessionManager = Depends(get_session_manager),
):
    """List conversations for a session.

    Returns all conversations associated with the session.
    """
    session = manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    conversations = manager.get_conversations(session_id)

    return [
        ConversationResponse(
            conversation_id=conv.conversation_id,
            session_id=conv.session_id,
            title=conv.title,
            status=conv.status.value,
            message_count=len(conv.messages),
            created_at=conv.created_at.isoformat(),
            updated_at=conv.updated_at.isoformat(),
        )
        for conv in conversations
    ]


@router.post("/conversations")
async def create_conversation(
    session_id: str,
    title: Optional[str] = None,
    manager: SessionManager = Depends(get_session_manager),
):
    """Create a new conversation.

    Creates a new conversation thread in the session.
    """
    session = manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    conversation = manager.create_conversation(session_id, title)
    if not conversation:
        raise HTTPException(status_code=400, detail="Could not create conversation")

    return ConversationResponse(
        conversation_id=conversation.conversation_id,
        session_id=conversation.session_id,
        title=conversation.title,
        status=conversation.status.value,
        message_count=0,
        created_at=conversation.created_at.isoformat(),
        updated_at=conversation.updated_at.isoformat(),
    )


@router.get("/conversations/{conversation_id}")
async def get_conversation(
    session_id: str,
    conversation_id: str,
    manager: SessionManager = Depends(get_session_manager),
):
    """Get conversation details with messages.

    Returns the conversation including all messages.
    """
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
_start_time = datetime.utcnow()


@router.get("/health", response_model=HealthResponse)
async def health_check(
    manager: SessionManager = Depends(get_session_manager),
):
    """Health check endpoint.

    Returns service health status and basic statistics.
    """
    from fastband import __version__

    uptime = (datetime.utcnow() - _start_time).total_seconds()

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

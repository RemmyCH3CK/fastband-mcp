"""
Fastband AI Hub - Data Models.

Defines all data structures for the AI Hub system using Pydantic
for validation and serialization.

Performance Optimizations (Issue #38):
- Uses dataclass(slots=True) for memory efficiency
- Lazy loading for large content fields
- Efficient serialization with model_dump()
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


def _utc_now() -> datetime:
    """Get current UTC time (timezone-aware)."""
    return datetime.now(timezone.utc)


import logging
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)


# =============================================================================
# ENUMS
# =============================================================================


class SessionStatus(str, Enum):
    """Hub session status."""

    INITIALIZING = "initializing"
    ACTIVE = "active"
    IDLE = "idle"
    SUSPENDED = "suspended"
    TERMINATED = "terminated"


class MessageRole(str, Enum):
    """Chat message roles."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class ConversationStatus(str, Enum):
    """Conversation status."""

    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"


class SubscriptionTier(str, Enum):
    """Subscription tier levels."""

    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class AnalysisStatus(str, Enum):
    """Platform analysis status."""

    PENDING = "pending"
    ANALYZING = "analyzing"
    COMPLETED = "completed"
    FAILED = "failed"


# =============================================================================
# TIER CONFIGURATION
# =============================================================================


@dataclass(slots=True)
class TierLimits:
    """Rate limits and quotas per subscription tier.

    Attributes:
        tier: Subscription tier
        messages_per_minute: Max messages per minute
        messages_per_day: Max messages per day
        max_context_tokens: Max tokens in context window
        max_memory_entries: Max RAG memory entries
        max_projects: Max projects that can be connected
        streaming_enabled: Whether SSE streaming is enabled
        priority_queue: Whether to use priority queue
    """

    tier: SubscriptionTier
    messages_per_minute: int = 10
    messages_per_day: int = 100
    max_context_tokens: int = 8000
    max_memory_entries: int = 1000
    max_projects: int = 1
    streaming_enabled: bool = True
    priority_queue: bool = False

    @classmethod
    def for_tier(cls, tier: SubscriptionTier) -> "TierLimits":
        """Get limits for a subscription tier."""
        limits = {
            SubscriptionTier.FREE: cls(
                tier=tier,
                messages_per_minute=5,
                messages_per_day=50,
                max_context_tokens=4000,
                max_memory_entries=100,
                max_projects=1,
                streaming_enabled=True,
                priority_queue=False,
            ),
            SubscriptionTier.PRO: cls(
                tier=tier,
                messages_per_minute=30,
                messages_per_day=1000,
                max_context_tokens=32000,
                max_memory_entries=10000,
                max_projects=10,
                streaming_enabled=True,
                priority_queue=True,
            ),
            SubscriptionTier.ENTERPRISE: cls(
                tier=tier,
                messages_per_minute=100,
                messages_per_day=10000,
                max_context_tokens=128000,
                max_memory_entries=100000,
                max_projects=100,
                streaming_enabled=True,
                priority_queue=True,
            ),
        }
        return limits.get(tier, limits[SubscriptionTier.FREE])


@dataclass(slots=True)
class UsageStats:
    """Usage statistics for billing and rate limiting.

    Attributes:
        user_id: User identifier
        tier: Current subscription tier
        messages_today: Messages sent today
        messages_this_minute: Messages in current minute
        tokens_used_today: Tokens consumed today
        memory_entries: Current memory entry count
        last_message_at: Timestamp of last message
        reset_at: When daily limits reset
    """

    user_id: str
    tier: SubscriptionTier
    messages_today: int = 0
    messages_this_minute: int = 0
    tokens_used_today: int = 0
    memory_entries: int = 0
    last_message_at: datetime | None = None
    reset_at: datetime | None = None

    def can_send_message(self, limits: TierLimits) -> tuple[bool, str | None]:
        """Check if user can send a message.

        Returns:
            Tuple of (allowed, reason_if_denied)
        """
        if self.messages_this_minute >= limits.messages_per_minute:
            return False, "Rate limit exceeded. Please wait a moment."

        if self.messages_today >= limits.messages_per_day:
            return False, "Daily message limit reached. Resets at midnight UTC."

        return True, None


# =============================================================================
# SESSION MODELS
# =============================================================================


@dataclass(slots=True)
class SessionConfig:
    """Configuration for a hub session.

    Attributes:
        user_id: Authenticated user ID
        tier: Subscription tier
        project_path: Path to connected project (if any)
        model: AI model to use
        temperature: Model temperature
        max_tokens: Max response tokens
        tools_enabled: List of enabled tool categories
        memory_enabled: Whether RAG memory is enabled
    """

    user_id: str
    tier: SubscriptionTier = SubscriptionTier.FREE
    project_path: str | None = None
    model: str = "claude-sonnet-4-20250514"
    temperature: float = 0.7
    max_tokens: int = 4096
    tools_enabled: list[str] = field(default_factory=list)
    memory_enabled: bool = True


@dataclass(slots=True)
class HubSession:
    """A user's hub session.

    Represents an active connection to the Fastband AI Hub,
    including configuration, state, and conversation history.

    Attributes:
        session_id: Unique session identifier
        config: Session configuration
        status: Current session status
        created_at: When session was created
        last_activity: Last activity timestamp
        current_conversation_id: Active conversation ID
        metadata: Additional session metadata
    """

    session_id: str
    config: SessionConfig
    status: SessionStatus = SessionStatus.INITIALIZING
    created_at: datetime = field(default_factory=_utc_now)
    last_activity: datetime = field(default_factory=_utc_now)
    current_conversation_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(cls, config: SessionConfig) -> "HubSession":
        """Create a new session with generated ID."""
        return cls(
            session_id=str(uuid4()),
            config=config,
            status=SessionStatus.ACTIVE,
        )

    def touch(self) -> None:
        """Update last activity timestamp."""
        self.last_activity = _utc_now()

    def is_active(self) -> bool:
        """Check if session is active."""
        return self.status == SessionStatus.ACTIVE


# =============================================================================
# CHAT MODELS
# =============================================================================


@dataclass(slots=True)
class ToolCall:
    """A tool call made during chat.

    Attributes:
        tool_id: Unique call ID
        tool_name: Name of tool called
        arguments: Tool arguments
        result: Tool execution result
        error: Error if execution failed
        duration_ms: Execution time in milliseconds
    """

    tool_id: str
    tool_name: str
    arguments: dict[str, Any]
    result: Any | None = None
    error: str | None = None
    duration_ms: int | None = None


@dataclass(slots=True)
class ChatMessage:
    """A chat message in a conversation.

    Attributes:
        message_id: Unique message identifier
        role: Message role (user/assistant/system/tool)
        content: Message text content
        created_at: When message was created
        tool_calls: Any tool calls made (for assistant messages)
        tool_call_id: ID of tool call this responds to (for tool messages)
        tokens_used: Tokens consumed by this message
        metadata: Additional message metadata
    """

    message_id: str
    role: MessageRole
    content: str
    created_at: datetime = field(default_factory=_utc_now)
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_call_id: str | None = None
    tokens_used: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def user(cls, content: str) -> "ChatMessage":
        """Create a user message."""
        return cls(
            message_id=str(uuid4()),
            role=MessageRole.USER,
            content=content,
        )

    @classmethod
    def assistant(
        cls,
        content: str,
        tool_calls: list[ToolCall] | None = None,
        tokens_used: int = 0,
    ) -> "ChatMessage":
        """Create an assistant message."""
        return cls(
            message_id=str(uuid4()),
            role=MessageRole.ASSISTANT,
            content=content,
            tool_calls=tool_calls or [],
            tokens_used=tokens_used,
        )

    @classmethod
    def system(cls, content: str) -> "ChatMessage":
        """Create a system message."""
        return cls(
            message_id=str(uuid4()),
            role=MessageRole.SYSTEM,
            content=content,
        )

    @classmethod
    def tool_result(cls, tool_call_id: str, content: str) -> "ChatMessage":
        """Create a tool result message."""
        return cls(
            message_id=str(uuid4()),
            role=MessageRole.TOOL,
            content=content,
            tool_call_id=tool_call_id,
        )

    def to_api_format(self) -> dict[str, Any]:
        """Convert to API message format."""
        msg = {
            "role": self.role.value,
            "content": self.content,
        }
        if self.tool_calls:
            msg["tool_calls"] = [
                {
                    "id": tc.tool_id,
                    "type": "function",
                    "function": {
                        "name": tc.tool_name,
                        "arguments": tc.arguments,
                    },
                }
                for tc in self.tool_calls
            ]
        if self.tool_call_id:
            msg["tool_call_id"] = self.tool_call_id
        return msg


@dataclass(slots=True)
class Conversation:
    """A conversation thread.

    Attributes:
        conversation_id: Unique conversation identifier
        session_id: Parent session ID
        title: Conversation title (auto-generated or user-set)
        status: Conversation status
        messages: List of messages in conversation
        created_at: When conversation was created
        updated_at: Last update timestamp
        summary: AI-generated summary for context
        metadata: Additional conversation metadata
    """

    conversation_id: str
    session_id: str
    title: str = "New Conversation"
    status: ConversationStatus = ConversationStatus.ACTIVE
    messages: list[ChatMessage] = field(default_factory=list)
    created_at: datetime = field(default_factory=_utc_now)
    updated_at: datetime = field(default_factory=_utc_now)
    summary: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(cls, session_id: str, title: str | None = None) -> "Conversation":
        """Create a new conversation."""
        return cls(
            conversation_id=str(uuid4()),
            session_id=session_id,
            title=title or "New Conversation",
        )

    def add_message(self, message: ChatMessage) -> None:
        """Add a message to the conversation."""
        self.messages.append(message)
        self.updated_at = _utc_now()

    def get_context_messages(self, max_tokens: int = 8000) -> list[ChatMessage]:
        """Get messages that fit within token budget.

        Uses a simple heuristic: ~4 chars per token.
        Returns most recent messages that fit.
        """
        result = []
        token_count = 0
        chars_per_token = 4

        for msg in reversed(self.messages):
            msg_tokens = len(msg.content) // chars_per_token
            if token_count + msg_tokens > max_tokens:
                break
            result.insert(0, msg)
            token_count += msg_tokens

        return result


# =============================================================================
# MEMORY MODELS
# =============================================================================


@dataclass(slots=True)
class MemoryEntry:
    """A memory entry for RAG retrieval.

    Attributes:
        entry_id: Unique entry identifier
        user_id: Owner user ID
        content: Text content
        embedding: Vector embedding (optional, computed lazily)
        source: Where this memory came from
        created_at: When entry was created
        last_accessed: Last retrieval timestamp
        access_count: How many times retrieved
        metadata: Additional entry metadata
    """

    entry_id: str
    user_id: str
    content: str
    embedding: list[float] | None = None
    source: str = "conversation"
    created_at: datetime = field(default_factory=_utc_now)
    last_accessed: datetime | None = None
    access_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_message(cls, message: ChatMessage, user_id: str) -> "MemoryEntry":
        """Create memory entry from a chat message."""
        return cls(
            entry_id=str(uuid4()),
            user_id=user_id,
            content=message.content,
            source="conversation",
            metadata={
                "message_id": message.message_id,
                "role": message.role.value,
            },
        )


@dataclass(slots=True)
class MemoryContext:
    """Context retrieved from memory for a query.

    Attributes:
        entries: Retrieved memory entries
        query: Original query
        total_found: Total matching entries
        tokens_used: Tokens consumed by context
    """

    entries: list[MemoryEntry]
    query: str
    total_found: int = 0
    tokens_used: int = 0

    def to_context_string(self, max_entries: int = 5) -> str:
        """Convert to context string for prompt injection."""
        if not self.entries:
            return ""

        lines = ["Relevant context from memory:"]
        for entry in self.entries[:max_entries]:
            lines.append(f"- {entry.content[:500]}")

        return "\n".join(lines)


# =============================================================================
# PLATFORM ANALYSIS MODELS
# =============================================================================


@dataclass(slots=True)
class ProjectInfo:
    """Information about a connected project.

    Attributes:
        project_id: Unique project identifier
        user_id: Owner user ID
        name: Project name
        path: Project path or repository URL
        connection_type: How project is connected (github/gitlab/ssh/upload)
        language: Primary programming language
        framework: Detected framework
        created_at: When project was connected
        last_analyzed: Last analysis timestamp
        metadata: Additional project metadata
    """

    project_id: str
    user_id: str
    name: str
    path: str
    connection_type: str = "local"
    language: str | None = None
    framework: str | None = None
    created_at: datetime = field(default_factory=_utc_now)
    last_analyzed: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AnalysisResult:
    """Result of platform/codebase analysis.

    Attributes:
        analysis_id: Unique analysis identifier
        project_id: Project that was analyzed
        status: Analysis status
        summary: Analysis summary
        recommendations: List of recommendations
        detected_stack: Detected technology stack
        file_count: Number of files analyzed
        created_at: When analysis started
        completed_at: When analysis completed
        metadata: Additional analysis metadata
    """

    analysis_id: str
    project_id: str
    status: AnalysisStatus = AnalysisStatus.PENDING
    summary: str | None = None
    recommendations: list[str] = field(default_factory=list)
    detected_stack: dict[str, Any] = field(default_factory=dict)
    file_count: int = 0
    created_at: datetime = field(default_factory=_utc_now)
    completed_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(cls, project_id: str) -> "AnalysisResult":
        """Create a new analysis result."""
        return cls(
            analysis_id=str(uuid4()),
            project_id=project_id,
            status=AnalysisStatus.ANALYZING,
        )

    def complete(
        self,
        summary: str,
        recommendations: list[str],
        detected_stack: dict[str, Any],
        file_count: int,
    ) -> None:
        """Mark analysis as completed."""
        self.status = AnalysisStatus.COMPLETED
        self.summary = summary
        self.recommendations = recommendations
        self.detected_stack = detected_stack
        self.file_count = file_count
        self.completed_at = _utc_now()

    def fail(self, error: str) -> None:
        """Mark analysis as failed."""
        self.status = AnalysisStatus.FAILED
        self.metadata["error"] = error
        self.completed_at = _utc_now()

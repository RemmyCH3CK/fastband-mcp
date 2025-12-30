"""Tests for Fastband Hub models."""

from datetime import datetime

from fastband.hub.models import (
    AnalysisResult,
    AnalysisStatus,
    ChatMessage,
    Conversation,
    ConversationStatus,
    HubSession,
    MemoryContext,
    MemoryEntry,
    MessageRole,
    SessionConfig,
    SessionStatus,
    SubscriptionTier,
    TierLimits,
    UsageStats,
)


class TestEnums:
    """Test enum definitions."""

    def test_session_status_values(self):
        """Test SessionStatus enum values."""
        assert SessionStatus.ACTIVE.value == "active"
        assert SessionStatus.IDLE.value == "idle"
        assert SessionStatus.TERMINATED.value == "terminated"
        assert SessionStatus.INITIALIZING.value == "initializing"

    def test_message_role_values(self):
        """Test MessageRole enum values."""
        assert MessageRole.USER.value == "user"
        assert MessageRole.ASSISTANT.value == "assistant"
        assert MessageRole.SYSTEM.value == "system"
        assert MessageRole.TOOL.value == "tool"

    def test_subscription_tier_values(self):
        """Test SubscriptionTier enum values."""
        assert SubscriptionTier.FREE.value == "free"
        assert SubscriptionTier.PRO.value == "pro"
        assert SubscriptionTier.ENTERPRISE.value == "enterprise"


class TestSessionConfig:
    """Test SessionConfig dataclass."""

    def test_default_values(self):
        """Test default configuration values."""
        config = SessionConfig(user_id="user123")

        assert config.user_id == "user123"
        assert config.tier == SubscriptionTier.FREE
        assert config.project_path is None
        assert config.model == "claude-sonnet-4-20250514"
        assert config.temperature == 0.7
        assert config.max_tokens == 4096
        assert config.tools_enabled == []
        assert config.memory_enabled is True

    def test_custom_values(self):
        """Test custom configuration values."""
        config = SessionConfig(
            user_id="user456",
            tier=SubscriptionTier.PRO,
            project_path="/path/to/project",
            model="claude-opus-4-20250514",
            temperature=0.5,
            max_tokens=8192,
            tools_enabled=["read_file", "write_file"],
            memory_enabled=False,
        )

        assert config.user_id == "user456"
        assert config.tier == SubscriptionTier.PRO
        assert config.project_path == "/path/to/project"
        assert config.model == "claude-opus-4-20250514"
        assert config.temperature == 0.5
        assert config.max_tokens == 8192
        assert config.tools_enabled == ["read_file", "write_file"]
        assert config.memory_enabled is False


class TestHubSession:
    """Test HubSession dataclass."""

    def test_session_creation(self):
        """Test creating a session."""
        config = SessionConfig(user_id="user123")
        session = HubSession(
            session_id="sess_123",
            config=config,
            status=SessionStatus.ACTIVE,
        )

        assert session.session_id == "sess_123"
        assert session.config == config
        assert session.status == SessionStatus.ACTIVE
        assert session.current_conversation_id is None
        assert isinstance(session.created_at, datetime)
        assert isinstance(session.last_activity, datetime)

    def test_session_create_classmethod(self):
        """Test creating a session via classmethod."""
        config = SessionConfig(user_id="user123")
        session = HubSession.create(config)

        # Session ID is a UUID, just check it's not empty
        assert session.session_id is not None
        assert len(session.session_id) > 0
        assert session.config == config
        assert session.status == SessionStatus.ACTIVE

    def test_session_touch(self):
        """Test touching a session updates last_activity."""
        config = SessionConfig(user_id="user123")
        session = HubSession(
            session_id="sess_123",
            config=config,
            status=SessionStatus.ACTIVE,
        )

        old_activity = session.last_activity
        # Small delay to ensure time difference
        import time

        time.sleep(0.01)
        session.touch()

        assert session.last_activity > old_activity

    def test_session_is_active(self):
        """Test is_active method."""
        config = SessionConfig(user_id="user123")
        session = HubSession(
            session_id="sess_123",
            config=config,
            status=SessionStatus.ACTIVE,
        )

        assert session.is_active() is True

        # IDLE is not ACTIVE - is_active only returns True for ACTIVE
        session.status = SessionStatus.IDLE
        assert session.is_active() is False

        session.status = SessionStatus.TERMINATED
        assert session.is_active() is False


class TestChatMessage:
    """Test ChatMessage dataclass."""

    def test_message_creation(self):
        """Test creating a chat message."""
        msg = ChatMessage(
            message_id="msg_123",
            role=MessageRole.USER,
            content="Hello, world!",
        )

        assert msg.message_id == "msg_123"
        assert msg.role == MessageRole.USER
        assert msg.content == "Hello, world!"
        assert msg.tool_calls == []  # Default is empty list
        assert msg.tool_call_id is None
        assert isinstance(msg.created_at, datetime)

    def test_user_message_classmethod(self):
        """Test creating user message via classmethod."""
        msg = ChatMessage.user("Hello!")
        assert msg.role == MessageRole.USER
        assert msg.content == "Hello!"
        assert msg.message_id is not None

    def test_assistant_message_classmethod(self):
        """Test creating assistant message via classmethod."""
        msg = ChatMessage.assistant("Hi there!", tokens_used=50)
        assert msg.role == MessageRole.ASSISTANT
        assert msg.content == "Hi there!"
        assert msg.tokens_used == 50

    def test_tool_result_message(self):
        """Test tool result message."""
        msg = ChatMessage.tool_result("call_1", '{"result": "file contents"}')

        assert msg.role == MessageRole.TOOL
        assert msg.tool_call_id == "call_1"


class TestConversation:
    """Test Conversation dataclass."""

    def test_conversation_creation(self):
        """Test creating a conversation."""
        conv = Conversation(
            conversation_id="conv_123",
            session_id="sess_123",
        )

        assert conv.conversation_id == "conv_123"
        assert conv.session_id == "sess_123"
        assert conv.title == "New Conversation"
        assert conv.status == ConversationStatus.ACTIVE
        assert conv.messages == []
        assert isinstance(conv.created_at, datetime)
        assert isinstance(conv.updated_at, datetime)

    def test_conversation_create_classmethod(self):
        """Test creating conversation via classmethod."""
        conv = Conversation.create("sess_123", "My Conversation")

        # conversation_id is a UUID
        assert conv.conversation_id is not None
        assert len(conv.conversation_id) > 0
        assert conv.session_id == "sess_123"
        assert conv.title == "My Conversation"

    def test_add_message(self):
        """Test adding a message to conversation."""
        conv = Conversation(
            conversation_id="conv_123",
            session_id="sess_123",
        )

        msg = ChatMessage(
            message_id="msg_1",
            role=MessageRole.USER,
            content="Hello!",
        )

        old_updated = conv.updated_at
        import time

        time.sleep(0.01)
        conv.add_message(msg)

        assert len(conv.messages) == 1
        assert conv.messages[0] == msg
        assert conv.updated_at > old_updated


class TestTierLimits:
    """Test TierLimits dataclass."""

    def test_free_tier(self):
        """Test free tier limits."""
        limits = TierLimits.for_tier(SubscriptionTier.FREE)

        assert limits.messages_per_day == 50
        assert limits.messages_per_minute == 5
        assert limits.max_context_tokens == 4000
        assert limits.max_memory_entries == 100
        assert limits.max_projects == 1
        assert limits.streaming_enabled is True

    def test_pro_tier(self):
        """Test pro tier limits."""
        limits = TierLimits.for_tier(SubscriptionTier.PRO)

        assert limits.messages_per_day == 1000
        assert limits.messages_per_minute == 30
        assert limits.max_context_tokens == 32000
        assert limits.max_memory_entries == 10000
        assert limits.priority_queue is True

    def test_enterprise_tier(self):
        """Test enterprise tier limits."""
        limits = TierLimits.for_tier(SubscriptionTier.ENTERPRISE)

        assert limits.messages_per_day == 10000
        assert limits.messages_per_minute == 100


class TestUsageStats:
    """Test UsageStats dataclass."""

    def test_default_stats(self):
        """Test default usage stats."""
        stats = UsageStats(user_id="user123", tier=SubscriptionTier.FREE)

        assert stats.user_id == "user123"
        assert stats.tier == SubscriptionTier.FREE
        assert stats.messages_today == 0
        assert stats.messages_this_minute == 0
        assert stats.tokens_used_today == 0
        assert stats.memory_entries == 0
        assert stats.last_message_at is None
        assert stats.reset_at is None

    def test_can_send_message_within_limits(self):
        """Test limit checking."""
        stats = UsageStats(
            user_id="user123",
            tier=SubscriptionTier.FREE,
            messages_today=25,
            messages_this_minute=2,
        )
        limits = TierLimits.for_tier(SubscriptionTier.FREE)

        allowed, reason = stats.can_send_message(limits)
        assert allowed is True
        assert reason is None

    def test_daily_limit_exceeded(self):
        """Test daily limit exceeded."""
        stats = UsageStats(
            user_id="user123",
            tier=SubscriptionTier.FREE,
            messages_today=51,  # Exceeds FREE tier limit of 50
            messages_this_minute=2,
        )
        limits = TierLimits.for_tier(SubscriptionTier.FREE)

        allowed, reason = stats.can_send_message(limits)
        assert allowed is False
        assert reason is not None

    def test_minute_limit_exceeded(self):
        """Test minute limit checking."""
        stats = UsageStats(
            user_id="user123",
            tier=SubscriptionTier.FREE,
            messages_today=25,
            messages_this_minute=6,  # Exceeds FREE tier limit of 5
        )
        limits = TierLimits.for_tier(SubscriptionTier.FREE)

        allowed, reason = stats.can_send_message(limits)
        assert allowed is False


class TestMemoryEntry:
    """Test MemoryEntry dataclass."""

    def test_memory_entry_creation(self):
        """Test creating a memory entry."""
        entry = MemoryEntry(
            entry_id="mem_123",
            user_id="user_123",
            content="Important information",
            source="conversation",
        )

        assert entry.entry_id == "mem_123"
        assert entry.user_id == "user_123"
        assert entry.content == "Important information"
        assert entry.source == "conversation"
        assert entry.embedding is None
        assert entry.access_count == 0


class TestMemoryContext:
    """Test MemoryContext dataclass."""

    def test_memory_context_creation(self):
        """Test creating memory context."""
        entries = [
            MemoryEntry(
                entry_id="mem_1",
                user_id="user_123",
                content="Entry 1",
                source="conversation",
            ),
            MemoryEntry(
                entry_id="mem_2",
                user_id="user_123",
                content="Entry 2",
                source="file",
            ),
        ]

        context = MemoryContext(
            entries=entries,
            query="test query",
            total_found=2,
        )

        assert len(context.entries) == 2
        assert context.query == "test query"
        assert context.total_found == 2

    def test_to_context_string(self):
        """Test converting memory context to string."""
        entries = [
            MemoryEntry(
                entry_id="mem_1",
                user_id="user_123",
                content="Important fact",
                source="conversation",
            ),
        ]

        context = MemoryContext(entries=entries, query="query", total_found=1)
        context_str = context.to_context_string()

        assert "Relevant context from memory" in context_str
        assert "Important fact" in context_str


class TestAnalysisResult:
    """Test AnalysisResult dataclass."""

    def test_analysis_result_creation(self):
        """Test creating analysis result."""
        result = AnalysisResult(
            analysis_id="analysis_123",
            project_id="project_123",
        )

        assert result.analysis_id == "analysis_123"
        assert result.project_id == "project_123"
        assert result.status == AnalysisStatus.PENDING
        assert result.recommendations == []
        assert result.detected_stack == {}

    def test_analysis_result_create_classmethod(self):
        """Test creating analysis via classmethod."""
        result = AnalysisResult.create("project_123")

        assert result.analysis_id is not None
        assert result.project_id == "project_123"
        assert result.status == AnalysisStatus.ANALYZING

    def test_complete_analysis(self):
        """Test completing an analysis."""
        result = AnalysisResult.create("project_123")

        result.complete(
            summary="Analysis complete",
            recommendations=["Use TypeScript"],
            detected_stack={"language": "Python"},
            file_count=100,
        )

        assert result.status == AnalysisStatus.COMPLETED
        assert result.summary == "Analysis complete"
        assert result.file_count == 100

"""Tests for Fastband Hub session management."""

from datetime import datetime, timedelta, timezone

import pytest

from fastband.hub.models import (
    ConversationStatus,
    SessionConfig,
    SessionStatus,
    SubscriptionTier,
)
from fastband.hub.session import SessionManager, get_session_manager, reset_session_manager


class TestSessionManager:
    """Test SessionManager class."""

    @pytest.fixture
    def manager(self):
        """Create a fresh session manager for each test."""
        return SessionManager(max_sessions=10, idle_timeout_minutes=5)

    @pytest.mark.asyncio
    async def test_create_session(self, manager):
        """Test creating a new session."""
        config = SessionConfig(user_id="user123")
        session = await manager.create_session(config)

        assert session is not None
        # Session ID is a UUID, just verify it's not empty
        assert session.session_id is not None
        assert len(session.session_id) > 0
        assert session.config == config
        assert session.status == SessionStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_create_session_with_pro_tier(self, manager):
        """Test creating a session with Pro tier."""
        config = SessionConfig(user_id="user123", tier=SubscriptionTier.PRO)
        session = await manager.create_session(config)

        assert session.config.tier == SubscriptionTier.PRO

    @pytest.mark.asyncio
    async def test_get_session(self, manager):
        """Test retrieving a session."""
        config = SessionConfig(user_id="user123")
        created = await manager.create_session(config)

        retrieved = manager.get_session(created.session_id)

        assert retrieved is not None
        assert retrieved.session_id == created.session_id

    @pytest.mark.asyncio
    async def test_get_nonexistent_session(self, manager):
        """Test retrieving a non-existent session."""
        result = manager.get_session("nonexistent_id")
        assert result is None

    @pytest.mark.asyncio
    async def test_terminate_session(self, manager):
        """Test terminating a session."""
        config = SessionConfig(user_id="user123")
        session = await manager.create_session(config)
        session_id = session.session_id

        result = await manager.terminate_session(session_id)

        assert result is True
        assert manager.get_session(session_id) is None

    @pytest.mark.asyncio
    async def test_terminate_nonexistent_session(self, manager):
        """Test terminating a non-existent session."""
        result = await manager.terminate_session("nonexistent_id")
        assert result is False

    @pytest.mark.asyncio
    async def test_max_sessions_limit_with_idle_eviction(self, manager):
        """Test that max sessions limit evicts idle sessions."""
        # Create max sessions, setting some to IDLE
        sessions = []
        for i in range(10):
            config = SessionConfig(user_id=f"user{i}")
            session = await manager.create_session(config)
            sessions.append(session)

        # Set first session to IDLE for eviction
        sessions[0].status = SessionStatus.IDLE

        # Create another session - should succeed by evicting idle
        config = SessionConfig(user_id="user_overflow")
        session = await manager.create_session(config)

        # Should succeed by evicting an idle session
        assert session is not None

    @pytest.mark.asyncio
    async def test_rate_limit_check(self, manager):
        """Test rate limit checking."""
        config = SessionConfig(user_id="user123", tier=SubscriptionTier.FREE)
        await manager.create_session(config)

        # Check rate limit for new session
        allowed, message = manager.check_rate_limit("user123")
        assert allowed is True
        assert message is None

    @pytest.mark.asyncio
    async def test_rate_limit_exceeded(self, manager):
        """Test rate limit exceeded scenario."""
        config = SessionConfig(user_id="user123", tier=SubscriptionTier.FREE)
        await manager.create_session(config)

        # Manually set usage to exceed limits
        if "user123" in manager._usage_stats:
            manager._usage_stats["user123"].messages_this_minute = 100
            manager._usage_stats["user123"].last_message_at = datetime.now(timezone.utc)

        allowed, message = manager.check_rate_limit("user123")
        assert allowed is False
        assert message is not None
        assert "rate limit" in message.lower() or "limit" in message.lower()


class TestSessionManagerConversations:
    """Test SessionManager conversation handling."""

    @pytest.fixture
    def manager(self):
        """Create a fresh session manager."""
        return SessionManager(max_sessions=10, idle_timeout_minutes=5)

    @pytest.mark.asyncio
    async def test_create_conversation(self, manager):
        """Test creating a conversation."""
        config = SessionConfig(user_id="user123")
        session = await manager.create_session(config)

        conv = manager.create_conversation(session.session_id, "Test Conversation")

        assert conv is not None
        # Conversation ID is a UUID
        assert conv.conversation_id is not None
        assert len(conv.conversation_id) > 0
        assert conv.session_id == session.session_id
        assert conv.title == "Test Conversation"
        assert conv.status == ConversationStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_create_conversation_invalid_session(self, manager):
        """Test creating conversation for invalid session."""
        conv = manager.create_conversation("invalid_session", "Test")
        assert conv is None

    @pytest.mark.asyncio
    async def test_get_conversation(self, manager):
        """Test retrieving a conversation."""
        config = SessionConfig(user_id="user123")
        session = await manager.create_session(config)
        created = manager.create_conversation(session.session_id, "Test")

        retrieved = manager.get_conversation(session.session_id, created.conversation_id)

        assert retrieved is not None
        assert retrieved.conversation_id == created.conversation_id

    @pytest.mark.asyncio
    async def test_get_conversations(self, manager):
        """Test getting all conversations for a session."""
        config = SessionConfig(user_id="user123")
        session = await manager.create_session(config)

        # Create multiple conversations
        manager.create_conversation(session.session_id, "Conv 1")
        manager.create_conversation(session.session_id, "Conv 2")
        manager.create_conversation(session.session_id, "Conv 3")

        convs = manager.get_conversations(session.session_id)

        assert len(convs) == 3


class TestSessionManagerCallbacks:
    """Test SessionManager callback functionality."""

    @pytest.fixture
    def manager(self):
        """Create a fresh session manager."""
        return SessionManager(max_sessions=10, idle_timeout_minutes=5)

    @pytest.mark.asyncio
    async def test_on_session_created_callback(self, manager):
        """Test on_session_created callback."""
        callback_called = []

        def callback(session):
            callback_called.append(session.session_id)

        manager.on_session_created(callback)

        config = SessionConfig(user_id="user123")
        session = await manager.create_session(config)

        assert len(callback_called) == 1
        assert callback_called[0] == session.session_id

    @pytest.mark.asyncio
    async def test_on_session_terminated_callback(self, manager):
        """Test on_session_terminated callback."""
        callback_called = []

        # The callback receives the session object, not just the ID
        def callback(session):
            callback_called.append(session.session_id)

        manager.on_session_terminated(callback)

        config = SessionConfig(user_id="user123")
        session = await manager.create_session(config)
        session_id = session.session_id

        await manager.terminate_session(session_id)

        assert len(callback_called) == 1
        assert callback_called[0] == session_id


class TestCleanupIdleSessions:
    """Test idle session cleanup."""

    @pytest.fixture
    def manager(self):
        """Create a session manager with short timeout."""
        return SessionManager(max_sessions=10, idle_timeout_minutes=0)

    @pytest.mark.asyncio
    async def test_cleanup_idle_sessions(self, manager):
        """Test that idle sessions are cleaned up."""
        config = SessionConfig(user_id="user123")
        session = await manager.create_session(config)
        session_id = session.session_id

        # Force session to be old
        session.last_activity = datetime.now(timezone.utc) - timedelta(hours=1)

        # Run cleanup
        count = await manager.cleanup_idle_sessions()

        assert count >= 1
        assert manager.get_session(session_id) is None


class TestGetSessionManager:
    """Test global session manager singleton."""

    def test_get_session_manager_returns_instance(self):
        """Test that get_session_manager returns an instance."""
        # Reset the global state
        reset_session_manager()

        manager = get_session_manager()

        assert manager is not None
        assert isinstance(manager, SessionManager)

    def test_get_session_manager_returns_same_instance(self):
        """Test that get_session_manager returns the same instance."""
        reset_session_manager()

        manager1 = get_session_manager()
        manager2 = get_session_manager()

        assert manager1 is manager2

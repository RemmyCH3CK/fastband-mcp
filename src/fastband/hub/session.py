"""
Fastband AI Hub - Session Management.

Manages hub sessions, including creation, lifecycle, and cleanup.

Performance Optimizations (Issue #38):
- Session pooling with LRU eviction
- Lazy initialization of heavy resources
- Background cleanup of idle sessions
- Thread-safe session access
"""

import asyncio
import logging
import threading
from collections import OrderedDict
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import Any

from fastband.hub.models import (
    Conversation,
    HubSession,
    SessionConfig,
    SessionStatus,
    TierLimits,
    UsageStats,
)

logger = logging.getLogger(__name__)


class SessionManager:
    """
    Manages hub sessions with pooling and lifecycle management.

    Features:
    - Session creation and retrieval
    - Automatic idle session cleanup
    - Usage tracking and rate limiting
    - Thread-safe operations

    Example:
        manager = SessionManager(max_sessions=1000)

        # Create session
        session = await manager.create_session(config)

        # Get existing session
        session = manager.get_session(session_id)

        # Clean up idle sessions
        await manager.cleanup_idle_sessions()
    """

    def __init__(
        self,
        max_sessions: int = 1000,
        idle_timeout_minutes: int = 30,
        cleanup_interval_seconds: int = 60,
    ):
        """Initialize session manager.

        Args:
            max_sessions: Maximum concurrent sessions
            idle_timeout_minutes: Minutes before idle session cleanup
            cleanup_interval_seconds: Seconds between cleanup runs
        """
        self._sessions: OrderedDict[str, HubSession] = OrderedDict()
        self._conversations: dict[str, dict[str, Conversation]] = {}
        self._usage_stats: dict[str, UsageStats] = {}
        self._max_sessions = max_sessions
        self._idle_timeout = timedelta(minutes=idle_timeout_minutes)
        self._cleanup_interval = cleanup_interval_seconds
        self._lock = threading.RLock()
        self._cleanup_task: asyncio.Task | None = None
        self._on_session_created: Callable[[HubSession], None] | None = None
        self._on_session_terminated: Callable[[HubSession], None] | None = None

    async def start(self) -> None:
        """Start the session manager background tasks."""
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            logger.info("Session manager started")

    async def stop(self) -> None:
        """Stop the session manager and cleanup."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
        logger.info("Session manager stopped")

    async def create_session(self, config: SessionConfig) -> HubSession:
        """Create a new hub session.

        Args:
            config: Session configuration

        Returns:
            Created HubSession

        Raises:
            ValueError: If max sessions reached
        """
        with self._lock:
            # Check capacity
            if len(self._sessions) >= self._max_sessions:
                # Try to evict oldest idle session
                evicted = self._evict_oldest_idle()
                if not evicted:
                    raise ValueError(f"Maximum sessions ({self._max_sessions}) reached")

            # Create session
            session = HubSession.create(config)
            self._sessions[session.session_id] = session
            self._conversations[session.session_id] = {}

            # Initialize usage stats
            self._usage_stats[config.user_id] = UsageStats(
                user_id=config.user_id,
                tier=config.tier,
                reset_at=self._get_next_reset_time(),
            )

            logger.info(f"Created session {session.session_id} for user {config.user_id}")

            if self._on_session_created:
                self._on_session_created(session)

            return session

    def get_session(self, session_id: str) -> HubSession | None:
        """Get a session by ID.

        Args:
            session_id: Session identifier

        Returns:
            HubSession if found and active, None otherwise
        """
        with self._lock:
            session = self._sessions.get(session_id)
            if session and session.is_active():
                session.touch()
                # Move to end for LRU
                self._sessions.move_to_end(session_id)
                return session
            return None

    def get_session_by_user(self, user_id: str) -> HubSession | None:
        """Get active session for a user.

        Args:
            user_id: User identifier

        Returns:
            Most recent active session for user, or None
        """
        with self._lock:
            for session in reversed(self._sessions.values()):
                if session.config.user_id == user_id and session.is_active():
                    return session
            return None

    async def terminate_session(self, session_id: str) -> bool:
        """Terminate a session.

        Args:
            session_id: Session to terminate

        Returns:
            True if session was terminated
        """
        with self._lock:
            session = self._sessions.get(session_id)
            if session:
                session.status = SessionStatus.TERMINATED
                del self._sessions[session_id]
                del self._conversations[session_id]

                logger.info(f"Terminated session {session_id}")

                if self._on_session_terminated:
                    self._on_session_terminated(session)

                return True
            return False

    def get_conversation(
        self,
        session_id: str,
        conversation_id: str,
    ) -> Conversation | None:
        """Get a conversation from a session.

        Args:
            session_id: Session identifier
            conversation_id: Conversation identifier

        Returns:
            Conversation if found
        """
        with self._lock:
            session_convs = self._conversations.get(session_id, {})
            return session_convs.get(conversation_id)

    def create_conversation(
        self,
        session_id: str,
        title: str | None = None,
    ) -> Conversation | None:
        """Create a new conversation in a session.

        Args:
            session_id: Session identifier
            title: Optional conversation title

        Returns:
            Created Conversation or None if session not found
        """
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return None

            conv = Conversation.create(session_id, title)
            self._conversations[session_id][conv.conversation_id] = conv
            session.current_conversation_id = conv.conversation_id
            session.touch()

            logger.debug(f"Created conversation {conv.conversation_id} in session {session_id}")

            return conv

    def get_conversations(self, session_id: str) -> list[Conversation]:
        """Get all conversations for a session.

        Args:
            session_id: Session identifier

        Returns:
            List of conversations
        """
        with self._lock:
            session_convs = self._conversations.get(session_id, {})
            return list(session_convs.values())

    def check_rate_limit(
        self,
        user_id: str,
    ) -> tuple[bool, str | None]:
        """Check if user can send a message.

        Args:
            user_id: User identifier

        Returns:
            Tuple of (allowed, reason_if_denied)
        """
        with self._lock:
            stats = self._usage_stats.get(user_id)
            if not stats:
                return True, None

            limits = TierLimits.for_tier(stats.tier)
            return stats.can_send_message(limits)

    def record_message(
        self,
        user_id: str,
        tokens_used: int = 0,
    ) -> None:
        """Record a message for rate limiting.

        Args:
            user_id: User identifier
            tokens_used: Tokens consumed
        """
        with self._lock:
            stats = self._usage_stats.get(user_id)
            if stats:
                now = datetime.now(timezone.utc)

                # Reset minute counter if new minute
                if stats.last_message_at:
                    if (now - stats.last_message_at).total_seconds() >= 60:
                        stats.messages_this_minute = 0

                # Reset daily counter if new day
                if stats.reset_at and now >= stats.reset_at:
                    stats.messages_today = 0
                    stats.tokens_used_today = 0
                    stats.reset_at = self._get_next_reset_time()

                stats.messages_today += 1
                stats.messages_this_minute += 1
                stats.tokens_used_today += tokens_used
                stats.last_message_at = now

    def get_usage_stats(self, user_id: str) -> UsageStats | None:
        """Get usage stats for a user.

        Args:
            user_id: User identifier

        Returns:
            UsageStats if found
        """
        with self._lock:
            return self._usage_stats.get(user_id)

    def get_active_session_count(self) -> int:
        """Get count of active sessions."""
        with self._lock:
            return sum(1 for s in self._sessions.values() if s.is_active())

    def get_stats(self) -> dict[str, Any]:
        """Get session manager statistics."""
        with self._lock:
            active = sum(1 for s in self._sessions.values() if s.is_active())
            return {
                "total_sessions": len(self._sessions),
                "active_sessions": active,
                "max_sessions": self._max_sessions,
                "total_conversations": sum(len(convs) for convs in self._conversations.values()),
                "tracked_users": len(self._usage_stats),
            }

    # =========================================================================
    # LIFECYCLE CALLBACKS
    # =========================================================================

    def on_session_created(
        self,
        callback: Callable[[HubSession], None],
    ) -> None:
        """Register callback for session creation."""
        self._on_session_created = callback

    def on_session_terminated(
        self,
        callback: Callable[[HubSession], None],
    ) -> None:
        """Register callback for session termination."""
        self._on_session_terminated = callback

    # =========================================================================
    # PRIVATE METHODS
    # =========================================================================

    def _evict_oldest_idle(self) -> bool:
        """Evict oldest idle session to make room.

        Returns:
            True if a session was evicted
        """
        # Use list() to avoid RuntimeError from dictionary modification during iteration
        for session_id in list(self._sessions.keys()):
            session = self._sessions.get(session_id)
            if session and session.status == SessionStatus.IDLE:
                session.status = SessionStatus.TERMINATED
                del self._sessions[session_id]
                self._conversations.pop(session_id, None)
                logger.info(f"Evicted idle session {session_id}")
                return True
        return False

    def _get_next_reset_time(self) -> datetime:
        """Get next daily reset time (midnight UTC)."""
        now = datetime.now(timezone.utc)
        tomorrow = now + timedelta(days=1)
        return tomorrow.replace(hour=0, minute=0, second=0, microsecond=0)

    async def _cleanup_loop(self) -> None:
        """Background loop to cleanup idle sessions."""
        while True:
            try:
                await asyncio.sleep(self._cleanup_interval)
                await self.cleanup_idle_sessions()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Session cleanup error: {e}")

    async def cleanup_idle_sessions(self) -> int:
        """Clean up idle sessions that have timed out.

        Returns:
            Number of sessions cleaned up
        """
        now = datetime.now(timezone.utc)
        to_terminate = []

        with self._lock:
            # Use list() to create snapshot, avoiding RuntimeError during iteration
            for session_id, session in list(self._sessions.items()):
                if session.is_active():
                    idle_time = now - session.last_activity
                    if idle_time > self._idle_timeout:
                        to_terminate.append(session_id)

        count = 0
        for session_id in to_terminate:
            if await self.terminate_session(session_id):
                count += 1

        if count > 0:
            logger.info(f"Cleaned up {count} idle sessions")

        return count


# =============================================================================
# GLOBAL SINGLETON
# =============================================================================

_session_manager: SessionManager | None = None
_manager_lock = threading.Lock()


def get_session_manager(
    max_sessions: int = 1000,
    idle_timeout_minutes: int = 30,
) -> SessionManager:
    """Get or create the global session manager.

    Args:
        max_sessions: Maximum concurrent sessions
        idle_timeout_minutes: Idle timeout

    Returns:
        Global SessionManager instance
    """
    global _session_manager

    with _manager_lock:
        if _session_manager is None:
            _session_manager = SessionManager(
                max_sessions=max_sessions,
                idle_timeout_minutes=idle_timeout_minutes,
            )
        return _session_manager


def reset_session_manager() -> None:
    """Reset the global session manager (for testing)."""
    global _session_manager

    with _manager_lock:
        _session_manager = None

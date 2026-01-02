"""
Fastband AI Hub - Redis Session Store.

Redis-backed session management for horizontal scaling and persistence.

Features:
- Session sharing across Hub instances
- Automatic session expiration via Redis TTL
- JSON serialization with Pydantic
- Connection pooling
- Async Redis operations

Configuration via environment variables:
- FASTBAND_SESSION_STORE=redis (enable Redis sessions)
- FASTBAND_REDIS_URL=redis://localhost:6379/0
- FASTBAND_REDIS_PASSWORD=password (optional)
- FASTBAND_REDIS_SSL=true (for production)
- FASTBAND_REDIS_PREFIX=fastband:session (key prefix)
- FASTBAND_SESSION_TTL=1800 (30 min default)
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any

from fastband.hub.models import (
    Conversation,
    HubSession,
    SessionConfig,
    SessionStatus,
    UsageStats,
)

logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================


class RedisSessionConfig:
    """Redis session store configuration."""

    def __init__(
        self,
        redis_url: str | None = None,
        password: str | None = None,
        use_ssl: bool = False,
        key_prefix: str = "fastband:session",
        session_ttl: int = 1800,  # 30 minutes
        connection_pool_size: int = 10,
    ):
        """Initialize Redis config.

        Args:
            redis_url: Redis connection URL
            password: Redis password
            use_ssl: Enable SSL/TLS
            key_prefix: Key prefix for all session keys
            session_ttl: Session TTL in seconds
            connection_pool_size: Connection pool size
        """
        self.redis_url = redis_url or os.getenv(
            "FASTBAND_REDIS_URL", "redis://localhost:6379/0"
        )
        self.password = password or os.getenv("FASTBAND_REDIS_PASSWORD")
        self.use_ssl = use_ssl or os.getenv("FASTBAND_REDIS_SSL", "").lower() in (
            "true",
            "1",
            "yes",
        )
        self.key_prefix = key_prefix or os.getenv(
            "FASTBAND_REDIS_PREFIX", "fastband:session"
        )
        self.session_ttl = session_ttl or int(
            os.getenv("FASTBAND_SESSION_TTL", "1800")
        )
        self.connection_pool_size = connection_pool_size

    @classmethod
    def from_env(cls) -> "RedisSessionConfig":
        """Create config from environment variables."""
        return cls()


# =============================================================================
# REDIS SESSION MANAGER
# =============================================================================


class RedisSessionManager:
    """
    Redis-backed session manager for horizontal scaling.

    Implements the same interface as SessionManager but uses Redis
    for storage, enabling session sharing across multiple Hub instances.

    Example:
        config = RedisSessionConfig(redis_url="redis://localhost:6379")
        manager = RedisSessionManager(config)
        await manager.initialize()

        session = await manager.create_session(session_config)
        session = await manager.get_session(session_id)
    """

    def __init__(self, config: RedisSessionConfig | None = None):
        """Initialize Redis session manager.

        Args:
            config: Redis configuration
        """
        self.config = config or RedisSessionConfig.from_env()
        self._redis = None
        self._initialized = False

    async def initialize(self) -> bool:
        """Initialize Redis connection.

        Returns:
            True if initialization successful
        """
        if self._initialized:
            return True

        try:
            import redis.asyncio as aioredis

            # Parse URL and apply settings
            self._redis = aioredis.from_url(
                self.config.redis_url,
                password=self.config.password,
                ssl=self.config.use_ssl,
                max_connections=self.config.connection_pool_size,
                decode_responses=True,
            )

            # Test connection
            await self._redis.ping()

            self._initialized = True
            logger.info(f"Redis session store initialized: {self._sanitize_url()}")
            return True

        except ImportError:
            logger.error("redis package not installed. Run: pip install redis")
            return False
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            return False

    def _sanitize_url(self) -> str:
        """Sanitize Redis URL for logging (hide password)."""
        url = self.config.redis_url
        if "@" in url:
            parts = url.split("@")
            return f"redis://***@{parts[-1]}"
        return url

    async def close(self) -> None:
        """Close Redis connection."""
        if self._redis:
            await self._redis.close()
            self._initialized = False
            logger.info("Redis session store closed")

    # =========================================================================
    # KEY HELPERS
    # =========================================================================

    def _session_key(self, session_id: str) -> str:
        """Get Redis key for session."""
        return f"{self.config.key_prefix}:{session_id}"

    def _conversations_key(self, session_id: str) -> str:
        """Get Redis key for session conversations."""
        return f"{self.config.key_prefix}:{session_id}:conversations"

    def _usage_key(self, user_id: str) -> str:
        """Get Redis key for user usage stats."""
        return f"{self.config.key_prefix}:usage:{user_id}"

    def _user_sessions_key(self, user_id: str) -> str:
        """Get Redis key for user's session list."""
        return f"{self.config.key_prefix}:user:{user_id}:sessions"

    # =========================================================================
    # SESSION OPERATIONS
    # =========================================================================

    async def create_session(self, config: SessionConfig) -> HubSession:
        """Create a new session.

        Args:
            config: Session configuration

        Returns:
            Created HubSession
        """
        if not self._initialized:
            raise RuntimeError("Redis session manager not initialized")

        # Create session
        session = HubSession.create(config)

        # Serialize and store
        session_data = session.model_dump_json()
        await self._redis.setex(
            self._session_key(session.session_id),
            self.config.session_ttl,
            session_data,
        )

        # Track user's sessions
        await self._redis.sadd(
            self._user_sessions_key(config.user_id),
            session.session_id,
        )

        # Initialize usage stats if not exists
        usage_key = self._usage_key(config.user_id)
        if not await self._redis.exists(usage_key):
            usage = UsageStats(
                user_id=config.user_id,
                tier=config.tier,
                reset_at=self._get_next_reset_time(),
            )
            await self._redis.set(usage_key, usage.model_dump_json())

        logger.info(f"Created Redis session {session.session_id} for {config.user_id}")
        return session

    async def get_session(self, session_id: str) -> HubSession | None:
        """Get a session by ID.

        Args:
            session_id: Session identifier

        Returns:
            HubSession if found, None otherwise
        """
        if not self._initialized:
            return None

        data = await self._redis.get(self._session_key(session_id))
        if not data:
            return None

        try:
            session = HubSession.model_validate_json(data)

            # Update last activity and extend TTL
            session.touch()
            await self._redis.setex(
                self._session_key(session_id),
                self.config.session_ttl,
                session.model_dump_json(),
            )

            return session
        except Exception as e:
            logger.error(f"Failed to deserialize session {session_id}: {e}")
            return None

    async def get_session_by_user(self, user_id: str) -> HubSession | None:
        """Get most recent active session for a user.

        Args:
            user_id: User identifier

        Returns:
            Most recent active session, or None
        """
        if not self._initialized:
            return None

        # Get user's session IDs
        session_ids = await self._redis.smembers(self._user_sessions_key(user_id))

        # Find active session (most recent)
        for session_id in session_ids:
            session = await self.get_session(session_id)
            if session and session.is_active():
                return session

        return None

    async def update_session(self, session: HubSession) -> None:
        """Update a session.

        Args:
            session: Session to update
        """
        if not self._initialized:
            raise RuntimeError("Redis session manager not initialized")

        session.touch()
        await self._redis.setex(
            self._session_key(session.session_id),
            self.config.session_ttl,
            session.model_dump_json(),
        )

    async def terminate_session(self, session_id: str) -> None:
        """Terminate a session.

        Args:
            session_id: Session to terminate
        """
        if not self._initialized:
            return

        # Get session to find user
        session = await self.get_session(session_id)
        if session:
            session.status = SessionStatus.TERMINATED

            # Update with terminated status (short TTL for cleanup)
            await self._redis.setex(
                self._session_key(session_id),
                60,  # Keep for 1 minute for cleanup
                session.model_dump_json(),
            )

            # Remove from user's sessions
            await self._redis.srem(
                self._user_sessions_key(session.user_id),
                session_id,
            )

            # Delete conversations
            await self._redis.delete(self._conversations_key(session_id))

            logger.info(f"Terminated Redis session {session_id}")

    # =========================================================================
    # CONVERSATION OPERATIONS
    # =========================================================================

    async def add_conversation(
        self, session_id: str, conversation: Conversation
    ) -> None:
        """Add a conversation to a session.

        Args:
            session_id: Session ID
            conversation: Conversation to add
        """
        if not self._initialized:
            raise RuntimeError("Redis session manager not initialized")

        await self._redis.hset(
            self._conversations_key(session_id),
            conversation.conversation_id,
            conversation.model_dump_json(),
        )

        # Extend session TTL
        await self._redis.expire(
            self._session_key(session_id), self.config.session_ttl
        )

    async def get_conversation(
        self, session_id: str, conversation_id: str
    ) -> Conversation | None:
        """Get a conversation.

        Args:
            session_id: Session ID
            conversation_id: Conversation ID

        Returns:
            Conversation if found, None otherwise
        """
        if not self._initialized:
            return None

        data = await self._redis.hget(
            self._conversations_key(session_id),
            conversation_id,
        )
        if not data:
            return None

        try:
            return Conversation.model_validate_json(data)
        except Exception as e:
            logger.error(f"Failed to deserialize conversation: {e}")
            return None

    async def update_conversation(
        self, session_id: str, conversation: Conversation
    ) -> None:
        """Update a conversation.

        Args:
            session_id: Session ID
            conversation: Updated conversation
        """
        await self.add_conversation(session_id, conversation)

    async def get_all_conversations(
        self, session_id: str
    ) -> list[Conversation]:
        """Get all conversations for a session.

        Args:
            session_id: Session ID

        Returns:
            List of conversations
        """
        if not self._initialized:
            return []

        data = await self._redis.hgetall(self._conversations_key(session_id))

        conversations = []
        for conv_data in data.values():
            try:
                conversations.append(Conversation.model_validate_json(conv_data))
            except Exception as e:
                logger.error(f"Failed to deserialize conversation: {e}")

        return sorted(conversations, key=lambda c: c.created_at, reverse=True)

    # =========================================================================
    # USAGE OPERATIONS
    # =========================================================================

    async def get_usage(self, user_id: str) -> UsageStats | None:
        """Get usage stats for a user.

        Args:
            user_id: User identifier

        Returns:
            UsageStats if found, None otherwise
        """
        if not self._initialized:
            return None

        data = await self._redis.get(self._usage_key(user_id))
        if not data:
            return None

        try:
            return UsageStats.model_validate_json(data)
        except Exception as e:
            logger.error(f"Failed to deserialize usage: {e}")
            return None

    async def update_usage(self, usage: UsageStats) -> None:
        """Update usage stats.

        Args:
            usage: Usage stats to update
        """
        if not self._initialized:
            raise RuntimeError("Redis session manager not initialized")

        await self._redis.set(
            self._usage_key(usage.user_id),
            usage.model_dump_json(),
        )

    async def increment_usage(
        self,
        user_id: str,
        messages: int = 0,
        tokens: int = 0,
    ) -> UsageStats | None:
        """Atomically increment usage counters.

        Args:
            user_id: User identifier
            messages: Messages to add
            tokens: Tokens to add

        Returns:
            Updated UsageStats
        """
        usage = await self.get_usage(user_id)
        if usage:
            usage.messages_used += messages
            usage.tokens_used += tokens
            await self.update_usage(usage)
        return usage

    # =========================================================================
    # STATS & CLEANUP
    # =========================================================================

    async def get_stats(self) -> dict[str, Any]:
        """Get session store statistics.

        Returns:
            Stats dictionary
        """
        if not self._initialized:
            return {"error": "Not initialized"}

        # Count sessions using SCAN
        cursor = 0
        session_count = 0
        pattern = f"{self.config.key_prefix}:*"

        while True:
            cursor, keys = await self._redis.scan(
                cursor, match=pattern, count=100
            )
            # Only count session keys (not conversations or usage)
            session_count += sum(
                1
                for k in keys
                if ":conversations" not in k and ":usage" not in k and ":user:" not in k
            )
            if cursor == 0:
                break

        return {
            "store": "redis",
            "url": self._sanitize_url(),
            "active_sessions": session_count,
            "key_prefix": self.config.key_prefix,
            "session_ttl": self.config.session_ttl,
            "connected": self._initialized,
        }

    async def cleanup_expired_user_sessions(self, user_id: str) -> int:
        """Clean up expired session references for a user.

        Args:
            user_id: User identifier

        Returns:
            Number of cleaned up sessions
        """
        if not self._initialized:
            return 0

        cleaned = 0
        user_sessions_key = self._user_sessions_key(user_id)
        session_ids = await self._redis.smembers(user_sessions_key)

        for session_id in session_ids:
            # Check if session still exists
            if not await self._redis.exists(self._session_key(session_id)):
                await self._redis.srem(user_sessions_key, session_id)
                cleaned += 1

        return cleaned

    # =========================================================================
    # HELPERS
    # =========================================================================

    def _get_next_reset_time(self) -> datetime:
        """Get next usage reset time (start of next month)."""
        now = datetime.now(timezone.utc)
        if now.month == 12:
            return datetime(now.year + 1, 1, 1, tzinfo=timezone.utc)
        return datetime(now.year, now.month + 1, 1, tzinfo=timezone.utc)


# =============================================================================
# FACTORY FUNCTION
# =============================================================================


_redis_session_manager: RedisSessionManager | None = None


async def get_redis_session_manager(
    config: RedisSessionConfig | None = None,
) -> RedisSessionManager:
    """Get or create the global Redis session manager.

    Args:
        config: Optional Redis configuration

    Returns:
        Initialized RedisSessionManager
    """
    global _redis_session_manager

    if _redis_session_manager is None:
        _redis_session_manager = RedisSessionManager(config)
        await _redis_session_manager.initialize()

    return _redis_session_manager


def should_use_redis_sessions() -> bool:
    """Check if Redis sessions are configured.

    Returns:
        True if FASTBAND_SESSION_STORE=redis
    """
    return os.getenv("FASTBAND_SESSION_STORE", "").lower() == "redis"

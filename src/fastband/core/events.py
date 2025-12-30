"""
Fastband Event Bus - Lightweight pub/sub for extensibility.

Provides in-process event broadcasting that integrates with existing
OpsLog EventType system. Designed for easy swap to cloud-based
backends (Redis, AWS EventBridge, etc.) for Option C.

Performance Optimizations:
- Async handler execution with concurrent gathering
- Handler isolation (one failure doesn't crash others)
- Minimal overhead for emit path
- Thread-safe subscription management
"""

import asyncio
import logging
import threading
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastband.agents.ops_log import EventType

logger = logging.getLogger(__name__)

# Type aliases
EventHandler = Callable[[dict[str, Any]], None]
AsyncEventHandler = Callable[[dict[str, Any]], Any]  # Returns Coroutine


@dataclass(slots=True)
class EventData:
    """Structured event data for pub/sub."""

    event_type: EventType
    data: dict[str, Any]
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    source: str = "system"
    correlation_id: str = field(default_factory=lambda: str(uuid4())[:8])

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "event_type": self.event_type.value
            if isinstance(self.event_type, EventType)
            else self.event_type,
            "data": self.data,
            "timestamp": self.timestamp.isoformat() + "Z",
            "source": self.source,
            "correlation_id": self.correlation_id,
        }


class EventBus:
    """
    In-process async event bus for Fastband extensibility.

    Supports:
    - Async and sync handlers
    - Wildcard subscriptions (subscribe to all events)
    - Handler isolation (failures don't propagate)
    - Decorator-based subscription syntax

    Example:
        bus = get_event_bus()

        # Decorator syntax
        @bus.on(EventType.TICKET_CLAIMED)
        async def on_ticket_claimed(data):
            print(f"Ticket {data['ticket_id']} claimed!")

        # Manual subscription
        bus.subscribe(EventType.AGENT_STARTED, my_handler)

        # Emit events
        await bus.emit(EventType.TICKET_CLAIMED, {
            "ticket_id": "123",
            "agent": "agent-1"
        })
    """

    __slots__ = ("_handlers", "_wildcard_handlers", "_sync_lock", "_started")

    def __init__(self):
        self._handlers: dict[EventType, list[tuple]] = defaultdict(list)
        self._wildcard_handlers: list[tuple] = []
        self._sync_lock = threading.Lock()  # Thread-safe for subscribe/unsubscribe
        self._started = False

    async def start(self) -> None:
        """Initialize the event bus (for lifecycle management)."""
        if self._started:
            return
        self._started = True
        logger.info("EventBus started")

    async def stop(self) -> None:
        """Shutdown the event bus."""
        self._started = False
        logger.info("EventBus stopped")

    def subscribe(
        self,
        event_type: EventType | str,
        handler: EventHandler | AsyncEventHandler,
        *,
        priority: int = 0,
    ) -> str:
        """
        Subscribe a handler to an event type (thread-safe).

        Args:
            event_type: Event type to subscribe to, or "*" for all events
            handler: Sync or async function to call when event fires
            priority: Higher priority handlers run first (default: 0)

        Returns:
            Subscription ID for unsubscribing
        """
        subscription_id = str(uuid4())[:8]
        entry = (priority, subscription_id, handler)

        with self._sync_lock:  # Thread-safe subscription
            if event_type == "*":
                self._wildcard_handlers.append(entry)
                self._wildcard_handlers.sort(key=lambda x: -x[0])  # Sort by priority desc
            else:
                # Convert string to EventType if needed
                if isinstance(event_type, str):
                    try:
                        event_type = EventType(event_type)
                    except ValueError:
                        logger.warning(f"Unknown event type: {event_type}")
                        return subscription_id

                self._handlers[event_type].append(entry)
                self._handlers[event_type].sort(key=lambda x: -x[0])

        logger.debug(f"Subscribed to {event_type}: {subscription_id}")
        return subscription_id

    def unsubscribe(self, subscription_id: str) -> bool:
        """
        Unsubscribe a handler by ID (thread-safe).

        Args:
            subscription_id: ID from subscribe()

        Returns:
            True if handler was found and removed
        """
        with self._sync_lock:  # Thread-safe unsubscription
            # Check wildcard handlers (iterate in reverse for safe removal)
            for i in range(len(self._wildcard_handlers) - 1, -1, -1):
                if self._wildcard_handlers[i][1] == subscription_id:
                    self._wildcard_handlers.pop(i)
                    logger.debug(f"Unsubscribed: {subscription_id}")
                    return True

            # Check specific event handlers
            for event_type, handlers in self._handlers.items():
                for i in range(len(handlers) - 1, -1, -1):
                    if handlers[i][1] == subscription_id:
                        handlers.pop(i)
                        logger.debug(f"Unsubscribed from {event_type}: {subscription_id}")
                        return True

        return False

    def on(self, event_type: EventType | str, *, priority: int = 0):
        """
        Decorator for subscribing to events.

        Example:
            @bus.on(EventType.TICKET_COMPLETED)
            async def handle_completion(data):
                print(f"Ticket completed: {data}")
        """

        def decorator(func: EventHandler | AsyncEventHandler):
            self.subscribe(event_type, func, priority=priority)
            return func

        return decorator

    async def emit(
        self,
        event_type: EventType,
        data: dict[str, Any],
        *,
        source: str = "system",
    ) -> EventData:
        """
        Emit an event to all subscribers.

        Args:
            event_type: Type of event to emit
            data: Event payload
            source: Source identifier (agent name, service, etc.)

        Returns:
            EventData object with correlation ID
        """
        event = EventData(
            event_type=event_type,
            data=data,
            source=source,
        )

        # Collect all handlers
        handlers_to_call = []

        # Add specific event handlers
        for _, _, handler in self._handlers.get(event_type, []):
            handlers_to_call.append(handler)

        # Add wildcard handlers
        for _, _, handler in self._wildcard_handlers:
            handlers_to_call.append(handler)

        if not handlers_to_call:
            return event

        # Execute all handlers concurrently
        tasks = []
        for handler in handlers_to_call:
            tasks.append(self._safe_invoke(handler, event.to_dict()))

        await asyncio.gather(*tasks, return_exceptions=True)

        return event

    def emit_sync(
        self,
        event_type: EventType,
        data: dict[str, Any],
        *,
        source: str = "system",
    ) -> None:
        """
        Emit an event synchronously (for non-async contexts).

        Note: This creates a new event loop if needed. Prefer emit()
        in async contexts.
        """
        try:
            asyncio.get_running_loop()
            # Already in async context - schedule as task
            asyncio.create_task(self.emit(event_type, data, source=source))
        except RuntimeError:
            # No event loop - run synchronously
            asyncio.run(self.emit(event_type, data, source=source))

    async def _safe_invoke(
        self,
        handler: EventHandler | AsyncEventHandler,
        data: dict[str, Any],
    ) -> None:
        """Safely invoke a handler with error isolation."""
        try:
            if asyncio.iscoroutinefunction(handler):
                await handler(data)
            else:
                # Run sync handler in thread pool to avoid blocking
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, handler, data)
        except Exception as e:
            logger.error(f"Error in event handler: {e}", exc_info=True)

    def get_subscriber_count(self, event_type: EventType | None = None) -> int:
        """Get number of subscribers for an event type (or all if None)."""
        if event_type is None:
            total = len(self._wildcard_handlers)
            for handlers in self._handlers.values():
                total += len(handlers)
            return total
        return len(self._handlers.get(event_type, [])) + len(self._wildcard_handlers)


# =============================================================================
# Global Instance Management
# =============================================================================

_event_bus: EventBus | None = None
_bus_lock = threading.Lock()  # Thread-safe singleton creation


def get_event_bus() -> EventBus:
    """
    Get the global EventBus instance (thread-safe).

    Creates the instance on first call (lazy initialization).
    Uses double-checked locking for thread safety.
    """
    global _event_bus

    if _event_bus is None:
        with _bus_lock:
            if _event_bus is None:  # Double-check after acquiring lock
                _event_bus = EventBus()

    return _event_bus


def reset_event_bus() -> None:
    """Reset the global event bus (for testing)."""
    global _event_bus
    with _bus_lock:
        _event_bus = None


# =============================================================================
# Extended Event Types for Hub/Plugin System
# =============================================================================

# These are additional event types beyond what ops_log defines.
# We could add these to EventType enum, but keeping them separate
# allows gradual integration.


class HubEventType:
    """Additional event types for Hub and plugin system."""

    # Hub lifecycle
    HUB_STARTED = "hub_started"
    HUB_STOPPED = "hub_stopped"

    # Plugin lifecycle
    PLUGIN_LOADED = "plugin_loaded"
    PLUGIN_UNLOADED = "plugin_unloaded"
    PLUGIN_ERROR = "plugin_error"

    # WebSocket
    WS_CLIENT_CONNECTED = "ws_client_connected"
    WS_CLIENT_DISCONNECTED = "ws_client_disconnected"

    # Dashboard
    DASHBOARD_REFRESH = "dashboard_refresh"

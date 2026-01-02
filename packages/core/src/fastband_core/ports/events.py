"""
Event publishing port interfaces.

Defines abstractions for event-driven communication between components.
Supports publish/subscribe patterns and event sourcing concepts.

These are pure interfaces - no message broker imports allowed.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Awaitable, Callable, Generic, Protocol, TypeVar, runtime_checkable
from uuid import uuid4


def _utc_now() -> datetime:
    """Get current UTC time (timezone-aware)."""
    return datetime.now(timezone.utc)


class EventPriority(Enum):
    """Priority levels for events."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class EventMetadata:
    """Metadata attached to every event."""

    event_id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = field(default_factory=_utc_now)
    source: str = ""  # Origin of the event
    correlation_id: str | None = None  # For request tracing
    causation_id: str | None = None  # ID of event that caused this one
    version: int = 1  # Schema version
    priority: EventPriority = EventPriority.NORMAL
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass
class Event:
    """
    Base event structure.

    All domain events should follow this structure.
    """

    type: str  # e.g., "ticket.created", "user.updated"
    data: dict[str, Any]
    metadata: EventMetadata = field(default_factory=EventMetadata)

    @property
    def aggregate_type(self) -> str:
        """Extract aggregate type from event type (e.g., 'ticket' from 'ticket.created')."""
        return self.type.split(".")[0] if "." in self.type else self.type

    @property
    def action(self) -> str:
        """Extract action from event type (e.g., 'created' from 'ticket.created')."""
        parts = self.type.split(".")
        return parts[1] if len(parts) > 1 else ""


# Type variable for event payload
T = TypeVar("T")


@dataclass
class TypedEvent(Generic[T]):
    """
    Typed event with structured payload.

    Use when you want strong typing on event data.
    """

    type: str
    data: T
    metadata: EventMetadata = field(default_factory=EventMetadata)


# Handler type aliases
EventHandler = Callable[[Event], Awaitable[None]]
TypedEventHandler = Callable[[TypedEvent[T]], Awaitable[None]]


@dataclass
class Subscription:
    """Represents an event subscription."""

    id: str
    topic: str  # Topic pattern (may include wildcards)
    handler_name: str
    created_at: datetime = field(default_factory=_utc_now)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DeliveryResult:
    """Result of event delivery attempt."""

    success: bool
    event_id: str
    subscription_id: str | None = None
    error: str | None = None
    retry_count: int = 0
    delivered_at: datetime | None = None


class EventPublisher(ABC):
    """
    Abstract base for publishing events.

    Publishes events to subscribers asynchronously.
    """

    @abstractmethod
    async def publish(self, event: Event) -> str:
        """
        Publish an event.

        Args:
            event: The event to publish.

        Returns:
            The event ID.
        """
        ...

    @abstractmethod
    async def publish_many(self, events: list[Event]) -> list[str]:
        """
        Publish multiple events atomically.

        Args:
            events: Events to publish.

        Returns:
            List of event IDs.
        """
        ...

    @abstractmethod
    async def publish_delayed(
        self,
        event: Event,
        delay_seconds: int,
    ) -> str:
        """
        Publish an event with a delay.

        Args:
            event: The event to publish.
            delay_seconds: Seconds to wait before publishing.

        Returns:
            The event ID.
        """
        ...


@runtime_checkable
class EventSubscriber(Protocol):
    """
    Protocol for subscribing to events.

    Registers handlers for event topics.
    """

    async def subscribe(
        self,
        topic: str,
        handler: EventHandler,
        handler_name: str | None = None,
    ) -> Subscription:
        """
        Subscribe to events matching a topic.

        Args:
            topic: Topic pattern (e.g., "ticket.*", "user.created").
            handler: Async function to handle events.
            handler_name: Optional name for the handler.

        Returns:
            Subscription details.
        """
        ...

    async def unsubscribe(self, subscription_id: str) -> bool:
        """
        Unsubscribe from events.

        Args:
            subscription_id: The subscription to cancel.

        Returns:
            True if unsubscribed, False if not found.
        """
        ...

    async def list_subscriptions(self, topic: str | None = None) -> list[Subscription]:
        """
        List active subscriptions.

        Args:
            topic: Optional topic filter.

        Returns:
            List of subscriptions.
        """
        ...


class EventBus(ABC):
    """
    Abstract base for in-process event bus.

    Combines publishing and subscribing for local events.
    """

    @abstractmethod
    async def publish(self, event: Event) -> list[DeliveryResult]:
        """
        Publish an event to all local subscribers.

        Args:
            event: The event to publish.

        Returns:
            Results of delivery to each subscriber.
        """
        ...

    @abstractmethod
    async def subscribe(
        self,
        topic: str,
        handler: EventHandler,
    ) -> Subscription:
        """
        Subscribe to events matching a topic.

        Args:
            topic: Topic pattern.
            handler: Event handler function.

        Returns:
            Subscription details.
        """
        ...

    @abstractmethod
    async def unsubscribe(self, subscription_id: str) -> bool:
        """Unsubscribe from events."""
        ...


@dataclass
class StreamPosition:
    """Position in an event stream."""

    stream_id: str
    position: int
    timestamp: datetime | None = None


@dataclass
class StreamEvent:
    """An event in a stream with position."""

    event: Event
    position: int
    stream_id: str


class EventStore(ABC):
    """
    Abstract base for event sourcing.

    Stores and retrieves events by stream.
    """

    @abstractmethod
    async def append(
        self,
        stream_id: str,
        events: list[Event],
        expected_version: int | None = None,
    ) -> int:
        """
        Append events to a stream.

        Args:
            stream_id: The stream to append to.
            events: Events to append.
            expected_version: Expected current version (for optimistic concurrency).

        Returns:
            New stream version.

        Raises:
            ConflictError: If expected_version doesn't match.
        """
        ...

    @abstractmethod
    async def read(
        self,
        stream_id: str,
        from_position: int = 0,
        max_count: int = 100,
    ) -> list[StreamEvent]:
        """
        Read events from a stream.

        Args:
            stream_id: The stream to read.
            from_position: Starting position.
            max_count: Maximum events to return.

        Returns:
            List of stream events.
        """
        ...

    @abstractmethod
    async def read_all(
        self,
        from_position: int = 0,
        max_count: int = 100,
        event_types: list[str] | None = None,
    ) -> list[StreamEvent]:
        """
        Read events across all streams.

        Args:
            from_position: Global starting position.
            max_count: Maximum events to return.
            event_types: Optional filter by event types.

        Returns:
            List of stream events.
        """
        ...

    @abstractmethod
    async def get_stream_version(self, stream_id: str) -> int | None:
        """
        Get the current version of a stream.

        Args:
            stream_id: The stream to check.

        Returns:
            Current version, or None if stream doesn't exist.
        """
        ...


class OutboxEntry:
    """Entry in the transactional outbox."""

    id: str
    event: Event
    created_at: datetime
    published_at: datetime | None = None
    attempts: int = 0
    last_error: str | None = None


class TransactionalOutbox(ABC):
    """
    Abstract base for transactional outbox pattern.

    Ensures events are published reliably with database transactions.
    """

    @abstractmethod
    async def store(self, events: list[Event]) -> list[str]:
        """
        Store events in the outbox (within a transaction).

        Args:
            events: Events to store.

        Returns:
            Outbox entry IDs.
        """
        ...

    @abstractmethod
    async def get_pending(self, limit: int = 100) -> list[OutboxEntry]:
        """
        Get unpublished outbox entries.

        Args:
            limit: Maximum entries to return.

        Returns:
            Pending outbox entries.
        """
        ...

    @abstractmethod
    async def mark_published(self, entry_ids: list[str]) -> int:
        """
        Mark entries as successfully published.

        Args:
            entry_ids: IDs of published entries.

        Returns:
            Number of entries marked.
        """
        ...

    @abstractmethod
    async def mark_failed(
        self,
        entry_id: str,
        error: str,
    ) -> None:
        """
        Mark an entry as failed.

        Args:
            entry_id: The failed entry.
            error: Error message.
        """
        ...


class DeadLetterQueue(ABC):
    """
    Abstract base for dead letter queue.

    Stores events that failed to process after max retries.
    """

    @abstractmethod
    async def store(
        self,
        event: Event,
        error: str,
        subscription_id: str | None = None,
    ) -> str:
        """
        Store a failed event.

        Args:
            event: The failed event.
            error: Error that caused the failure.
            subscription_id: Optional subscription that failed.

        Returns:
            Dead letter entry ID.
        """
        ...

    @abstractmethod
    async def get(self, limit: int = 100) -> list[tuple[str, Event, str]]:
        """
        Get dead letter entries.

        Args:
            limit: Maximum entries to return.

        Returns:
            List of (entry_id, event, error) tuples.
        """
        ...

    @abstractmethod
    async def retry(self, entry_id: str) -> bool:
        """
        Retry a dead letter event.

        Args:
            entry_id: Entry to retry.

        Returns:
            True if requeued, False if not found.
        """
        ...

    @abstractmethod
    async def delete(self, entry_id: str) -> bool:
        """
        Delete a dead letter entry.

        Args:
            entry_id: Entry to delete.

        Returns:
            True if deleted, False if not found.
        """
        ...

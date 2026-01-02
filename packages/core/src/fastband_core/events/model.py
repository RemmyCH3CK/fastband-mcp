"""
Core event domain models.

Pure domain types for event-driven communication. These models are
protocol-agnostic and have NO side effects on import.

Architecture Rules:
- No framework imports (FastAPI, Flask)
- No database driver imports
- No logging initialization
- No file I/O on import
- No environment variable reading on import
- Only stdlib + typing allowed
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Generic, TypeVar
from uuid import uuid4


def _utc_now() -> datetime:
    """Get current UTC time (timezone-aware)."""
    return datetime.now(timezone.utc)


def _generate_id() -> str:
    """Generate a unique identifier."""
    return str(uuid4())


def _short_id() -> str:
    """Generate a short identifier (8 chars)."""
    return str(uuid4())[:8]


class EventPriority(Enum):
    """Priority levels for events."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class EventCategory(Enum):
    """High-level event categories."""

    SYSTEM = "system"  # Infrastructure events
    DOMAIN = "domain"  # Business domain events
    INTEGRATION = "integration"  # External system events
    SECURITY = "security"  # Security-related events
    AUDIT = "audit"  # Audit trail events


@dataclass(frozen=True, slots=True)
class EventMetadata:
    """
    Immutable metadata attached to every event.

    Frozen to ensure metadata cannot be modified after creation,
    which is important for event sourcing and audit trails.
    """

    event_id: str = field(default_factory=_generate_id)
    timestamp: datetime = field(default_factory=_utc_now)
    source: str = ""  # Origin of the event (service, component)
    correlation_id: str | None = None  # For request tracing across services
    causation_id: str | None = None  # ID of event that caused this one
    version: int = 1  # Schema version for evolution
    priority: EventPriority = EventPriority.NORMAL
    category: EventCategory = EventCategory.DOMAIN
    tenant_id: str | None = None  # Multi-tenancy support
    attributes: tuple[tuple[str, Any], ...] = ()  # Extra immutable attributes

    def with_correlation(self, correlation_id: str) -> "EventMetadata":
        """Create a copy with correlation ID set."""
        return EventMetadata(
            event_id=self.event_id,
            timestamp=self.timestamp,
            source=self.source,
            correlation_id=correlation_id,
            causation_id=self.causation_id,
            version=self.version,
            priority=self.priority,
            category=self.category,
            tenant_id=self.tenant_id,
            attributes=self.attributes,
        )

    def with_causation(self, causation_id: str) -> "EventMetadata":
        """Create a copy with causation ID set."""
        return EventMetadata(
            event_id=self.event_id,
            timestamp=self.timestamp,
            source=self.source,
            correlation_id=self.correlation_id,
            causation_id=causation_id,
            version=self.version,
            priority=self.priority,
            category=self.category,
            tenant_id=self.tenant_id,
            attributes=self.attributes,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        result: dict[str, Any] = {
            "event_id": self.event_id,
            "timestamp": self.timestamp.isoformat(),
            "version": self.version,
            "priority": self.priority.value,
            "category": self.category.value,
        }
        if self.source:
            result["source"] = self.source
        if self.correlation_id:
            result["correlation_id"] = self.correlation_id
        if self.causation_id:
            result["causation_id"] = self.causation_id
        if self.tenant_id:
            result["tenant_id"] = self.tenant_id
        if self.attributes:
            result["attributes"] = dict(self.attributes)
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EventMetadata":
        """Create from dictionary."""
        attrs = data.get("attributes", {})
        if isinstance(attrs, dict):
            attrs = tuple(attrs.items())

        return cls(
            event_id=data.get("event_id", _generate_id()),
            timestamp=datetime.fromisoformat(data["timestamp"])
            if isinstance(data.get("timestamp"), str)
            else data.get("timestamp", _utc_now()),
            source=data.get("source", ""),
            correlation_id=data.get("correlation_id"),
            causation_id=data.get("causation_id"),
            version=data.get("version", 1),
            priority=EventPriority(data.get("priority", "normal")),
            category=EventCategory(data.get("category", "domain")),
            tenant_id=data.get("tenant_id"),
            attributes=attrs,
        )


@dataclass(frozen=True, slots=True)
class DomainEvent:
    """
    Base domain event structure.

    Immutable to ensure events cannot be modified after creation.
    All domain events should follow this structure.

    Example:
        event = DomainEvent(
            type="ticket.created",
            data={"ticket_id": "123", "title": "Fix bug"},
            metadata=EventMetadata(source="ticket-service"),
        )
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

    @property
    def event_id(self) -> str:
        """Convenience accessor for event ID."""
        return self.metadata.event_id

    @property
    def timestamp(self) -> datetime:
        """Convenience accessor for timestamp."""
        return self.metadata.timestamp

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "type": self.type,
            "data": self.data,
            "metadata": self.metadata.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DomainEvent":
        """Create from dictionary."""
        metadata = data.get("metadata", {})
        if isinstance(metadata, dict):
            metadata = EventMetadata.from_dict(metadata)
        return cls(
            type=data["type"],
            data=data.get("data", {}),
            metadata=metadata,
        )

    def caused_by(self, parent_event: "DomainEvent") -> "DomainEvent":
        """Create a new event with causation chain from parent."""
        new_metadata = EventMetadata(
            source=self.metadata.source,
            correlation_id=parent_event.metadata.correlation_id
            or parent_event.event_id,
            causation_id=parent_event.event_id,
            priority=self.metadata.priority,
            category=self.metadata.category,
            tenant_id=self.metadata.tenant_id,
            attributes=self.metadata.attributes,
        )
        return DomainEvent(
            type=self.type,
            data=self.data,
            metadata=new_metadata,
        )


# Type variable for typed event payloads
T = TypeVar("T")


@dataclass(frozen=True)
class TypedEvent(Generic[T]):
    """
    Typed event with structured payload.

    Use when you want strong typing on event data.

    Example:
        @dataclass
        class TicketCreatedPayload:
            ticket_id: str
            title: str

        event: TypedEvent[TicketCreatedPayload] = TypedEvent(
            type="ticket.created",
            data=TicketCreatedPayload(ticket_id="123", title="Fix bug"),
        )
    """

    type: str
    data: T
    metadata: EventMetadata = field(default_factory=EventMetadata)

    @property
    def event_id(self) -> str:
        """Convenience accessor for event ID."""
        return self.metadata.event_id

    def to_domain_event(self) -> DomainEvent:
        """Convert to untyped DomainEvent."""
        data_dict = (
            self.data
            if isinstance(self.data, dict)
            else getattr(self.data, "__dict__", {})
        )
        return DomainEvent(
            type=self.type,
            data=data_dict,
            metadata=self.metadata,
        )


@dataclass(frozen=True, slots=True)
class EventEnvelope:
    """
    Envelope wrapping an event for transport/storage.

    Includes routing and delivery metadata separate from the event itself.
    """

    event: DomainEvent
    topic: str  # Routing topic
    partition_key: str | None = None  # For ordered processing
    sequence_number: int | None = None  # Position in stream
    delivered_at: datetime | None = None  # Delivery timestamp

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        result = {
            "event": self.event.to_dict(),
            "topic": self.topic,
        }
        if self.partition_key:
            result["partition_key"] = self.partition_key
        if self.sequence_number is not None:
            result["sequence_number"] = self.sequence_number
        if self.delivered_at:
            result["delivered_at"] = self.delivered_at.isoformat()
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EventEnvelope":
        """Create from dictionary."""
        delivered = data.get("delivered_at")
        if isinstance(delivered, str):
            delivered = datetime.fromisoformat(delivered)
        return cls(
            event=DomainEvent.from_dict(data["event"]),
            topic=data["topic"],
            partition_key=data.get("partition_key"),
            sequence_number=data.get("sequence_number"),
            delivered_at=delivered,
        )


# Common event type constants (protocol-agnostic)
class CommonEventTypes:
    """Common event type patterns."""

    # Lifecycle patterns
    CREATED = "created"
    UPDATED = "updated"
    DELETED = "deleted"

    # State patterns
    STARTED = "started"
    STOPPED = "stopped"
    PAUSED = "paused"
    RESUMED = "resumed"

    # Completion patterns
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"

    @staticmethod
    def for_aggregate(aggregate: str, action: str) -> str:
        """Build event type string."""
        return f"{aggregate}.{action}"

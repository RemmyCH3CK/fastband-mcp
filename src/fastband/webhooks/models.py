"""
Webhook data models.

Provides:
- WebhookSubscription: Webhook registration configuration
- WebhookEvent: Event types that can trigger webhooks
- WebhookDelivery: Delivery attempt tracking
- DeliveryStatus: Delivery outcome status
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4


class WebhookEvent(str, Enum):
    """Events that can trigger webhooks."""

    # Ticket lifecycle
    TICKET_CREATED = "ticket.created"
    TICKET_CLAIMED = "ticket.claimed"
    TICKET_UPDATED = "ticket.updated"
    TICKET_COMPLETED = "ticket.completed"
    TICKET_APPROVED = "ticket.approved"
    TICKET_REJECTED = "ticket.rejected"
    TICKET_CLOSED = "ticket.closed"
    TICKET_COMMENT_ADDED = "ticket.comment_added"

    # Agent events
    AGENT_STARTED = "agent.started"
    AGENT_STOPPED = "agent.stopped"
    AGENT_ERROR = "agent.error"

    # Code review
    CODE_REVIEW_STARTED = "code_review.started"
    CODE_REVIEW_PASSED = "code_review.passed"
    CODE_REVIEW_FAILED = "code_review.failed"

    # Build/Deploy
    BUILD_STARTED = "build.started"
    BUILD_COMPLETED = "build.completed"
    BUILD_FAILED = "build.failed"

    # Wildcard
    ALL = "*"

    @classmethod
    def from_ops_log_event(cls, event_type: str) -> "WebhookEvent | None":
        """Map ops_log EventType to WebhookEvent."""
        mapping = {
            "ticket_claimed": cls.TICKET_CLAIMED,
            "ticket_completed": cls.TICKET_COMPLETED,
            "agent_started": cls.AGENT_STARTED,
            "agent_stopped": cls.AGENT_STOPPED,
            "error": cls.AGENT_ERROR,
            "rebuild_requested": cls.BUILD_STARTED,
            "rebuild_complete": cls.BUILD_COMPLETED,
        }
        return mapping.get(event_type)


class DeliveryStatus(str, Enum):
    """Status of a webhook delivery attempt."""

    PENDING = "pending"
    DELIVERED = "delivered"
    FAILED = "failed"
    RETRYING = "retrying"


@dataclass
class WebhookSubscription:
    """
    Webhook subscription configuration.

    Stores URL, secret, and event filters for a webhook endpoint.
    """

    id: str
    url: str
    events: list[WebhookEvent]
    secret: str
    name: str | None
    description: str | None
    active: bool
    created_at: datetime
    updated_at: datetime
    metadata: dict[str, Any] = field(default_factory=dict)

    # Stats
    total_deliveries: int = 0
    successful_deliveries: int = 0
    failed_deliveries: int = 0
    last_delivery_at: datetime | None = None
    last_error: str | None = None

    @classmethod
    def create(
        cls,
        url: str,
        events: list[str | WebhookEvent],
        secret: str,
        name: str | None = None,
        description: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> "WebhookSubscription":
        """Create a new webhook subscription."""
        now = datetime.now(timezone.utc)

        # Convert string events to WebhookEvent
        parsed_events = []
        for event in events:
            if isinstance(event, WebhookEvent):
                parsed_events.append(event)
            else:
                try:
                    parsed_events.append(WebhookEvent(event))
                except ValueError:
                    # Try without prefix
                    for we in WebhookEvent:
                        if we.value.endswith(event) or event == we.name.lower():
                            parsed_events.append(we)
                            break

        return cls(
            id=str(uuid4()),
            url=url,
            events=parsed_events if parsed_events else [WebhookEvent.ALL],
            secret=secret,
            name=name or f"Webhook {url[:30]}",
            description=description,
            active=True,
            created_at=now,
            updated_at=now,
            metadata=metadata or {},
        )

    def should_deliver(self, event: WebhookEvent) -> bool:
        """Check if this subscription should receive an event."""
        if not self.active:
            return False
        if WebhookEvent.ALL in self.events:
            return True
        return event in self.events

    def record_delivery(self, success: bool, error: str | None = None) -> None:
        """Record a delivery attempt."""
        self.total_deliveries += 1
        self.last_delivery_at = datetime.now(timezone.utc)
        self.updated_at = self.last_delivery_at

        if success:
            self.successful_deliveries += 1
            self.last_error = None
        else:
            self.failed_deliveries += 1
            self.last_error = error

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "url": self.url,
            "events": [e.value for e in self.events],
            "secret": self.secret,
            "name": self.name,
            "description": self.description,
            "active": self.active,
            "created_at": self.created_at.isoformat() + "Z",
            "updated_at": self.updated_at.isoformat() + "Z",
            "metadata": self.metadata,
            "stats": {
                "total_deliveries": self.total_deliveries,
                "successful_deliveries": self.successful_deliveries,
                "failed_deliveries": self.failed_deliveries,
                "success_rate": (
                    self.successful_deliveries / self.total_deliveries
                    if self.total_deliveries > 0
                    else 0.0
                ),
                "last_delivery_at": (
                    self.last_delivery_at.isoformat() + "Z"
                    if self.last_delivery_at
                    else None
                ),
                "last_error": self.last_error,
            },
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WebhookSubscription":
        """Create from dictionary."""
        stats = data.get("stats", {})
        return cls(
            id=data["id"],
            url=data["url"],
            events=[WebhookEvent(e) for e in data["events"]],
            secret=data["secret"],
            name=data.get("name"),
            description=data.get("description"),
            active=data.get("active", True),
            created_at=datetime.fromisoformat(data["created_at"].rstrip("Z")),
            updated_at=datetime.fromisoformat(data["updated_at"].rstrip("Z")),
            metadata=data.get("metadata", {}),
            total_deliveries=stats.get("total_deliveries", 0),
            successful_deliveries=stats.get("successful_deliveries", 0),
            failed_deliveries=stats.get("failed_deliveries", 0),
            last_delivery_at=(
                datetime.fromisoformat(stats["last_delivery_at"].rstrip("Z"))
                if stats.get("last_delivery_at")
                else None
            ),
            last_error=stats.get("last_error"),
        )


@dataclass
class WebhookDelivery:
    """
    Record of a webhook delivery attempt.

    Tracks request/response details for debugging and auditing.
    """

    id: str
    subscription_id: str
    event: WebhookEvent
    status: DeliveryStatus
    attempt: int
    max_attempts: int
    payload: dict[str, Any]
    created_at: datetime
    delivered_at: datetime | None
    next_retry_at: datetime | None

    # Response details
    response_status: int | None = None
    response_body: str | None = None
    response_time_ms: int | None = None
    error_message: str | None = None

    @classmethod
    def create(
        cls,
        subscription_id: str,
        event: WebhookEvent,
        payload: dict[str, Any],
        max_attempts: int = 3,
    ) -> "WebhookDelivery":
        """Create a new delivery record."""
        return cls(
            id=str(uuid4()),
            subscription_id=subscription_id,
            event=event,
            status=DeliveryStatus.PENDING,
            attempt=1,
            max_attempts=max_attempts,
            payload=payload,
            created_at=datetime.now(timezone.utc),
            delivered_at=None,
            next_retry_at=None,
        )

    def mark_delivered(
        self,
        status_code: int,
        body: str | None = None,
        response_time_ms: int | None = None,
    ) -> None:
        """Mark delivery as successful."""
        self.status = DeliveryStatus.DELIVERED
        self.delivered_at = datetime.now(timezone.utc)
        self.response_status = status_code
        self.response_body = body[:500] if body else None  # Truncate
        self.response_time_ms = response_time_ms
        self.error_message = None

    def mark_failed(
        self,
        error: str,
        status_code: int | None = None,
        body: str | None = None,
    ) -> None:
        """Mark delivery as failed."""
        self.error_message = error
        self.response_status = status_code
        self.response_body = body[:500] if body else None

        if self.attempt >= self.max_attempts:
            self.status = DeliveryStatus.FAILED
        else:
            self.status = DeliveryStatus.RETRYING
            self.attempt += 1
            # Exponential backoff: 10s, 60s, 300s
            backoff_seconds = [10, 60, 300][min(self.attempt - 1, 2)]
            from datetime import timedelta

            self.next_retry_at = datetime.now(timezone.utc) + timedelta(
                seconds=backoff_seconds
            )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "subscription_id": self.subscription_id,
            "event": self.event.value,
            "status": self.status.value,
            "attempt": self.attempt,
            "max_attempts": self.max_attempts,
            "payload": self.payload,
            "created_at": self.created_at.isoformat() + "Z",
            "delivered_at": (
                self.delivered_at.isoformat() + "Z" if self.delivered_at else None
            ),
            "next_retry_at": (
                self.next_retry_at.isoformat() + "Z" if self.next_retry_at else None
            ),
            "response": {
                "status": self.response_status,
                "body": self.response_body,
                "time_ms": self.response_time_ms,
            },
            "error_message": self.error_message,
        }

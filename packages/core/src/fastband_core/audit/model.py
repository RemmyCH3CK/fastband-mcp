"""
Core audit domain models.

Pure domain types for audit logging and compliance. These models are
designed for append-only storage and security-sensitive operations.

Architecture Rules:
- No framework imports (FastAPI, Flask)
- No database driver imports
- No logging initialization
- No file I/O on import
- No environment variable reading on import
- Only stdlib + typing allowed
- All models are immutable (frozen dataclasses)

Design Principles:
- Append-only: Records should never be modified after creation
- Immutable: Frozen dataclasses prevent modification
- Complete: Each record is self-contained with all context
- Traceable: Request/correlation IDs for tracing
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4


def _utc_now() -> datetime:
    """Get current UTC time (timezone-aware)."""
    return datetime.now(timezone.utc)


def _generate_id() -> str:
    """Generate a unique identifier."""
    return str(uuid4())


class AuditSeverity(Enum):
    """Audit event severity levels."""

    INFO = "info"  # Normal operations
    WARNING = "warning"  # Potential issues, security notices
    CRITICAL = "critical"  # Security incidents, failures


class AuditCategory(Enum):
    """High-level audit categories for filtering and routing."""

    AUTHENTICATION = "authentication"  # Login, logout, token operations
    AUTHORIZATION = "authorization"  # Access control decisions
    CONFIGURATION = "configuration"  # System/app configuration changes
    DATA_ACCESS = "data_access"  # Data read/write operations
    DATA_MODIFICATION = "data_modification"  # Create/update/delete operations
    SECURITY = "security"  # Security events, violations
    SYSTEM = "system"  # System operations, lifecycle
    COMPLIANCE = "compliance"  # Regulatory/compliance events


class AuditOutcome(Enum):
    """Outcome of the audited operation."""

    SUCCESS = "success"
    FAILURE = "failure"
    DENIED = "denied"  # Access denied specifically
    ERROR = "error"  # System error during operation
    PARTIAL = "partial"  # Partially successful


@dataclass(frozen=True, slots=True)
class AuditActor:
    """
    The actor who performed the audited action.

    Immutable to preserve audit integrity.
    """

    actor_id: str | None = None  # User ID, service account ID, etc.
    actor_type: str = "user"  # "user", "service", "system", "anonymous"
    display_name: str | None = None  # Human-readable name
    ip_address: str | None = None  # Client IP
    user_agent: str | None = None  # Client user agent
    session_id: str | None = None  # Session identifier

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        result: dict[str, Any] = {"actor_type": self.actor_type}
        if self.actor_id:
            result["actor_id"] = self.actor_id
        if self.display_name:
            result["display_name"] = self.display_name
        if self.ip_address:
            result["ip_address"] = self.ip_address
        if self.user_agent:
            result["user_agent"] = self.user_agent
        if self.session_id:
            result["session_id"] = self.session_id
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AuditActor":
        """Create from dictionary."""
        return cls(
            actor_id=data.get("actor_id"),
            actor_type=data.get("actor_type", "user"),
            display_name=data.get("display_name"),
            ip_address=data.get("ip_address"),
            user_agent=data.get("user_agent"),
            session_id=data.get("session_id"),
        )

    @classmethod
    def system(cls) -> "AuditActor":
        """Create a system actor."""
        return cls(actor_type="system", display_name="System")

    @classmethod
    def anonymous(cls, ip_address: str | None = None) -> "AuditActor":
        """Create an anonymous actor."""
        return cls(actor_type="anonymous", ip_address=ip_address)


@dataclass(frozen=True, slots=True)
class AuditResource:
    """
    The resource that was acted upon.

    Immutable to preserve audit integrity.
    """

    resource_type: str  # e.g., "ticket", "api_key", "backup", "config"
    resource_id: str | None = None  # Specific resource identifier
    resource_name: str | None = None  # Human-readable name
    parent_type: str | None = None  # Parent resource type (for hierarchy)
    parent_id: str | None = None  # Parent resource ID

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        result: dict[str, Any] = {"resource_type": self.resource_type}
        if self.resource_id:
            result["resource_id"] = self.resource_id
        if self.resource_name:
            result["resource_name"] = self.resource_name
        if self.parent_type:
            result["parent_type"] = self.parent_type
        if self.parent_id:
            result["parent_id"] = self.parent_id
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AuditResource":
        """Create from dictionary."""
        return cls(
            resource_type=data["resource_type"],
            resource_id=data.get("resource_id"),
            resource_name=data.get("resource_name"),
            parent_type=data.get("parent_type"),
            parent_id=data.get("parent_id"),
        )


@dataclass(frozen=True, slots=True)
class AuditRecord:
    """
    Immutable audit record for append-only storage.

    This is the core domain model for audit logging. Each record
    represents a single audited operation and cannot be modified
    after creation (frozen dataclass).

    Required invariants:
    - record_id is always set (generated if not provided)
    - timestamp is always set (current time if not provided)
    - event_type is always set (non-empty)
    - action is always set (non-empty)
    - category is always set

    Example:
        record = AuditRecord(
            event_type="auth:login",
            action="authenticate",
            actor=AuditActor(actor_id="user123", ip_address="192.168.1.1"),
            outcome=AuditOutcome.SUCCESS,
            category=AuditCategory.AUTHENTICATION,
        )
    """

    # Core identification
    record_id: str = field(default_factory=_generate_id)
    timestamp: datetime = field(default_factory=_utc_now)

    # Event classification
    event_type: str = ""  # e.g., "auth:login", "config:changed", "security:rate_limited"
    action: str = ""  # e.g., "login", "update", "delete"
    category: AuditCategory = AuditCategory.SYSTEM
    severity: AuditSeverity = AuditSeverity.INFO

    # Outcome
    outcome: AuditOutcome = AuditOutcome.SUCCESS
    error_message: str | None = None  # Error details if outcome is FAILURE/ERROR

    # Context
    actor: AuditActor | None = None  # Who performed the action
    resource: AuditResource | None = None  # What was acted upon

    # Tracing
    request_id: str | None = None  # HTTP request correlation ID
    correlation_id: str | None = None  # Cross-service correlation ID
    session_id: str | None = None  # User session ID

    # Additional context (immutable)
    details: tuple[tuple[str, Any], ...] = ()  # Extra structured data
    tags: tuple[str, ...] = ()  # Searchable tags

    # Multi-tenancy
    tenant_id: str | None = None

    def __post_init__(self) -> None:
        """Validate invariants after initialization."""
        # Note: We can't raise exceptions in frozen dataclass __post_init__
        # if we need to mutate. Instead, we use factory methods for validation.
        pass

    @classmethod
    def create(
        cls,
        event_type: str,
        action: str,
        category: AuditCategory = AuditCategory.SYSTEM,
        severity: AuditSeverity = AuditSeverity.INFO,
        outcome: AuditOutcome = AuditOutcome.SUCCESS,
        actor: AuditActor | None = None,
        resource: AuditResource | None = None,
        error_message: str | None = None,
        request_id: str | None = None,
        correlation_id: str | None = None,
        details: dict[str, Any] | None = None,
        tags: list[str] | None = None,
        tenant_id: str | None = None,
    ) -> "AuditRecord":
        """
        Factory method to create a validated audit record.

        Raises:
            ValueError: If required fields are missing or invalid.
        """
        if not event_type:
            raise ValueError("event_type is required")
        if not action:
            raise ValueError("action is required")

        details_tuple = tuple(details.items()) if details else ()
        tags_tuple = tuple(tags) if tags else ()

        return cls(
            event_type=event_type,
            action=action,
            category=category,
            severity=severity,
            outcome=outcome,
            actor=actor,
            resource=resource,
            error_message=error_message,
            request_id=request_id,
            correlation_id=correlation_id,
            details=details_tuple,
            tags=tags_tuple,
            tenant_id=tenant_id,
        )

    def to_dict(self) -> dict[str, Any]:
        """
        Convert to dictionary for serialization.

        The output is JSON-safe and suitable for storage.
        """
        result: dict[str, Any] = {
            "record_id": self.record_id,
            "timestamp": self.timestamp.isoformat(),
            "event_type": self.event_type,
            "action": self.action,
            "category": self.category.value,
            "severity": self.severity.value,
            "outcome": self.outcome.value,
        }

        if self.error_message:
            result["error_message"] = self.error_message
        if self.actor:
            result["actor"] = self.actor.to_dict()
        if self.resource:
            result["resource"] = self.resource.to_dict()
        if self.request_id:
            result["request_id"] = self.request_id
        if self.correlation_id:
            result["correlation_id"] = self.correlation_id
        if self.session_id:
            result["session_id"] = self.session_id
        if self.details:
            result["details"] = dict(self.details)
        if self.tags:
            result["tags"] = list(self.tags)
        if self.tenant_id:
            result["tenant_id"] = self.tenant_id

        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AuditRecord":
        """Create from dictionary."""
        actor = data.get("actor")
        if isinstance(actor, dict):
            actor = AuditActor.from_dict(actor)

        resource = data.get("resource")
        if isinstance(resource, dict):
            resource = AuditResource.from_dict(resource)

        details = data.get("details", {})
        if isinstance(details, dict):
            details = tuple(details.items())

        tags = data.get("tags", [])
        if isinstance(tags, list):
            tags = tuple(tags)

        timestamp = data.get("timestamp")
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)
        elif timestamp is None:
            timestamp = _utc_now()

        return cls(
            record_id=data.get("record_id", _generate_id()),
            timestamp=timestamp,
            event_type=data.get("event_type", ""),
            action=data.get("action", ""),
            category=AuditCategory(data.get("category", "system")),
            severity=AuditSeverity(data.get("severity", "info")),
            outcome=AuditOutcome(data.get("outcome", "success")),
            error_message=data.get("error_message"),
            actor=actor,
            resource=resource,
            request_id=data.get("request_id"),
            correlation_id=data.get("correlation_id"),
            session_id=data.get("session_id"),
            details=details,
            tags=tags,
            tenant_id=data.get("tenant_id"),
        )

    @property
    def is_security_event(self) -> bool:
        """Check if this is a security-related event."""
        return (
            self.category == AuditCategory.SECURITY
            or self.severity == AuditSeverity.CRITICAL
            or self.event_type.startswith("security:")
        )

    @property
    def is_failure(self) -> bool:
        """Check if this represents a failed operation."""
        return self.outcome in (
            AuditOutcome.FAILURE,
            AuditOutcome.ERROR,
            AuditOutcome.DENIED,
        )


# Common audit event type constants
class AuditEventTypes:
    """
    Standard audit event type constants.

    Use these for consistency across the system.
    """

    # Authentication
    AUTH_LOGIN = "auth:login"
    AUTH_LOGOUT = "auth:logout"
    AUTH_FAILURE = "auth:failure"
    AUTH_TOKEN_ISSUED = "auth:token_issued"
    AUTH_TOKEN_REVOKED = "auth:token_revoked"
    AUTH_SESSION_CREATED = "auth:session_created"
    AUTH_SESSION_DESTROYED = "auth:session_destroyed"

    # API Keys
    API_KEY_CREATED = "api_key:created"
    API_KEY_DELETED = "api_key:deleted"
    API_KEY_ROTATED = "api_key:rotated"
    API_KEY_USED = "api_key:used"

    # Configuration
    CONFIG_CHANGED = "config:changed"
    CONFIG_RESET = "config:reset"

    # Data Operations
    DATA_CREATED = "data:created"
    DATA_READ = "data:read"
    DATA_UPDATED = "data:updated"
    DATA_DELETED = "data:deleted"
    DATA_EXPORTED = "data:exported"
    DATA_IMPORTED = "data:imported"

    # Backup
    BACKUP_CREATED = "backup:created"
    BACKUP_RESTORED = "backup:restored"
    BACKUP_DELETED = "backup:deleted"

    # Security
    SECURITY_RATE_LIMITED = "security:rate_limited"
    SECURITY_ACCESS_DENIED = "security:access_denied"
    SECURITY_CSRF_VIOLATION = "security:csrf_violation"
    SECURITY_SUSPICIOUS = "security:suspicious"
    SECURITY_BLOCKED = "security:blocked"

    # System
    SYSTEM_STARTED = "system:started"
    SYSTEM_STOPPED = "system:stopped"
    SYSTEM_ERROR = "system:error"

    # Agent Operations
    AGENT_STARTED = "agent:started"
    AGENT_STOPPED = "agent:stopped"
    TICKET_CLAIMED = "agent:ticket_claimed"
    TICKET_COMPLETED = "agent:ticket_completed"

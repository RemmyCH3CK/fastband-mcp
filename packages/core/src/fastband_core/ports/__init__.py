"""
Fastband Core Ports - Interface definitions for adapters.

This module exports all port (interface) definitions that adapters must
implement. Ports define contracts without implementations.

Usage:
    from fastband_core.ports import KeyValueStore, Authenticator, EventPublisher

Architecture:
    - Ports are abstract interfaces (ABCs or Protocols)
    - Adapters provide concrete implementations
    - Core depends only on ports, never on adapters
"""

# Storage Ports
from fastband_core.ports.storage import (
    ConflictError,
    DocumentStore,
    KeyValueStore,
    MigrationInfo,
    MigrationRunner,
    NotFoundError,
    QueryFilter,
    QueryOrder,
    QueryResult,
    StorageError,
    TransactionManager,
)

# Auth Ports
from fastband_core.ports.auth import (
    AccessDecision,
    AccessRequest,
    AuthenticationError,
    AuthError,
    AuthorizationError,
    Authenticator,
    Authorizer,
    Credential,
    CredentialStore,
    Permission,
    Principal,
    Resource,
    Session,
    TokenExpiredError,
    TokenInvalidError,
    TokenPair,
    TokenProvider,
)

# Policy Ports
from fastband_core.ports.policy import (
    FeatureFlag,
    FeatureFlagContext,
    FeatureFlagProvider,
    Policy,
    PolicyContext,
    PolicyDecision,
    PolicyError,
    PolicyEvaluator,
    PolicyResult,
    PolicyStore,
    PolicyViolation,
    QuotaConfig,
    QuotaManager,
    QuotaStatus,
    RateLimitConfig,
    RateLimitExceeded,
    RateLimiter,
    RateLimitStatus,
)

# Telemetry Ports
from fastband_core.ports.telemetry import (
    Counter,
    Gauge,
    Histogram,
    Logger,
    LoggerFactory,
    LogLevel,
    LogRecord,
    MetricLabels,
    MetricsRegistry,
    MetricType,
    Span,
    SpanContext,
    SpanEvent,
    SpanStatus,
    TelemetryProvider,
    Tracer,
)

# Event Ports
from fastband_core.ports.events import (
    DeadLetterQueue,
    DeliveryResult,
    Event,
    EventBus,
    EventHandler,
    EventMetadata,
    EventPriority,
    EventPublisher,
    EventStore,
    EventSubscriber,
    StreamEvent,
    StreamPosition,
    Subscription,
    TransactionalOutbox,
    TypedEvent,
    TypedEventHandler,
)

__all__ = [
    # Storage
    "StorageError",
    "NotFoundError",
    "ConflictError",
    "KeyValueStore",
    "QueryFilter",
    "QueryOrder",
    "QueryResult",
    "DocumentStore",
    "TransactionManager",
    "MigrationInfo",
    "MigrationRunner",
    # Auth
    "AuthError",
    "AuthenticationError",
    "AuthorizationError",
    "TokenExpiredError",
    "TokenInvalidError",
    "Principal",
    "Credential",
    "Session",
    "TokenPair",
    "Authenticator",
    "TokenProvider",
    "Permission",
    "Resource",
    "AccessRequest",
    "AccessDecision",
    "Authorizer",
    "CredentialStore",
    # Policy
    "PolicyError",
    "PolicyViolation",
    "RateLimitExceeded",
    "PolicyDecision",
    "PolicyContext",
    "PolicyResult",
    "Policy",
    "PolicyEvaluator",
    "PolicyStore",
    "FeatureFlag",
    "FeatureFlagContext",
    "FeatureFlagProvider",
    "RateLimitConfig",
    "RateLimitStatus",
    "RateLimiter",
    "QuotaConfig",
    "QuotaStatus",
    "QuotaManager",
    # Telemetry
    "LogLevel",
    "MetricType",
    "LogRecord",
    "Logger",
    "LoggerFactory",
    "MetricLabels",
    "Counter",
    "Gauge",
    "Histogram",
    "MetricsRegistry",
    "SpanContext",
    "SpanStatus",
    "SpanEvent",
    "Span",
    "Tracer",
    "TelemetryProvider",
    # Events
    "EventPriority",
    "EventMetadata",
    "Event",
    "TypedEvent",
    "EventHandler",
    "TypedEventHandler",
    "Subscription",
    "DeliveryResult",
    "EventPublisher",
    "EventSubscriber",
    "EventBus",
    "StreamPosition",
    "StreamEvent",
    "EventStore",
    "TransactionalOutbox",
    "DeadLetterQueue",
]

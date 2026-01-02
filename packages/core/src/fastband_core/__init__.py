"""
Fastband Core - Shared foundations for Fastband products.

This package contains the shared core components used by both
Fastband Dev and Fastband Enterprise. It must not import from
either product package.

Architecture Rules:
- Core must not import fastband_dev or fastband_enterprise
- Core provides foundational abstractions only
- No product-specific conveniences or features
- No framework imports (FastAPI, Flask)
- No database driver imports
- No environment file loading

Modules:
- ports: Interface definitions for adapters to implement
"""

__version__ = "0.0.1"

# Re-export commonly used ports at package level
from fastband_core.ports import (
    # Storage
    KeyValueStore,
    DocumentStore,
    TransactionManager,
    # Auth
    Principal,
    Session,
    Authenticator,
    Authorizer,
    TokenProvider,
    # Policy
    PolicyEvaluator,
    RateLimiter,
    FeatureFlagProvider,
    # Telemetry
    Logger,
    Tracer,
    MetricsRegistry,
    TelemetryProvider,
    # Events
    Event,
    EventPublisher,
    EventSubscriber,
    EventBus,
)

__all__ = [
    # Storage
    "KeyValueStore",
    "DocumentStore",
    "TransactionManager",
    # Auth
    "Principal",
    "Session",
    "Authenticator",
    "Authorizer",
    "TokenProvider",
    # Policy
    "PolicyEvaluator",
    "RateLimiter",
    "FeatureFlagProvider",
    # Telemetry
    "Logger",
    "Tracer",
    "MetricsRegistry",
    "TelemetryProvider",
    # Events
    "Event",
    "EventPublisher",
    "EventSubscriber",
    "EventBus",
]

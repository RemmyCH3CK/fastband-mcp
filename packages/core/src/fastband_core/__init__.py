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
- No side effects on import

Modules:
- ports: Interface definitions for adapters to implement
- runtime: Engine lifecycle and context management
- tools: Tool abstraction and registry
- events: Domain event models
- audit: Audit domain models
- providers: AI provider abstraction layer
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
    # Events (ports)
    Event,
    EventPublisher,
    EventSubscriber,
    EventBus,
)

# Re-export commonly used runtime components
from fastband_core.runtime import (
    # Engine
    EngineBase,
    EngineConfig,
    EngineState,
    EngineInfo,
    # Context
    RuntimeContext,
    RuntimeConfig,
    RequestContext,
    ServiceRegistry,
    # Registry
    ComponentRegistry,
)

# Re-export commonly used tool components
from fastband_core.tools import (
    # Base types
    ToolCategory,
    ProjectType,
    ToolParameter,
    ToolMetadata,
    ToolDefinition,
    ToolResult,
    ToolBase,
    Tool,
    tool,
    # Registry types
    ToolLoadStatus,
    ToolRegistry,
)

# Re-export domain event models
# Note: EventMetadata and EventPriority also exist in ports - use qualified imports
# (fastband_core.events.EventMetadata) if you need the domain model version
from fastband_core.events import (
    DomainEvent,
    EventEnvelope,
    EventCategory,
    TypedEvent,
    CommonEventTypes,
)

# Re-export audit models
from fastband_core.audit import (
    AuditRecord,
    AuditActor,
    AuditResource,
    AuditSeverity,
    AuditCategory,
    AuditOutcome,
    AuditEventTypes,
)

# Re-export provider abstractions
# Note: Full provider types available via fastband_core.providers
from fastband_core.providers import (
    # Capabilities
    Capability,
    CapabilitySet,
    ModelInfo,
    # Provider ports
    CompletionProvider,
    EmbeddingProvider,
    # Domain models
    ProviderConfig,
    CompletionResponse,
    EmbeddingConfig,
    EmbeddingResult,
    ProviderHealth,
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
    # Events (ports)
    "Event",
    "EventPublisher",
    "EventSubscriber",
    "EventBus",
    # Runtime - Engine
    "EngineBase",
    "EngineConfig",
    "EngineState",
    "EngineInfo",
    # Runtime - Context
    "RuntimeContext",
    "RuntimeConfig",
    "RequestContext",
    "ServiceRegistry",
    # Runtime - Registry
    "ComponentRegistry",
    # Tools - Base
    "ToolCategory",
    "ProjectType",
    "ToolParameter",
    "ToolMetadata",
    "ToolDefinition",
    "ToolResult",
    "ToolBase",
    "Tool",
    "tool",
    # Tools - Registry
    "ToolLoadStatus",
    "ToolRegistry",
    # Events - Domain models
    "DomainEvent",
    "EventEnvelope",
    "EventCategory",
    "TypedEvent",
    "CommonEventTypes",
    # Audit - Domain models
    "AuditRecord",
    "AuditActor",
    "AuditResource",
    "AuditSeverity",
    "AuditCategory",
    "AuditOutcome",
    "AuditEventTypes",
    # Providers - Capabilities
    "Capability",
    "CapabilitySet",
    "ModelInfo",
    # Providers - Ports
    "CompletionProvider",
    "EmbeddingProvider",
    # Providers - Domain models
    "ProviderConfig",
    "CompletionResponse",
    "EmbeddingConfig",
    "EmbeddingResult",
    "ProviderHealth",
]

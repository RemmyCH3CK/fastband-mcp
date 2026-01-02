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
- runtime: Engine lifecycle and context management
- tools: Tool abstraction and registry
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
]

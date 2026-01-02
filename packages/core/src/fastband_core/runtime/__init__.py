"""
Fastband Core Runtime - Engine and lifecycle management.

This module provides abstract base classes and utilities for building
runtime engines. Concrete implementations (e.g., MCP engine) extend
these abstractions.

Usage:
    from fastband_core.runtime import EngineBase, RuntimeContext

    class MyEngine(EngineBase):
        async def _do_start(self) -> None:
            ...

Architecture:
    - EngineBase: Abstract engine lifecycle
    - RuntimeContext: Dependency injection and request scoping
    - ComponentRegistry: Tool/service registration
"""

# Engine
from fastband_core.runtime.engine import (
    EngineBase,
    EngineConfig,
    EngineError,
    EngineInfo,
    EngineStartError,
    EngineState,
    EngineStopError,
    LifecycleHook,
    LifecycleManager,
    ToolExecutor,
    ToolProvider,
)

# Context
from fastband_core.runtime.context import (
    RequestContext,
    RequestContextManager,
    RuntimeConfig,
    RuntimeContext,
    ServiceRegistry,
    get_runtime_context,
    reset_runtime_context,
    set_runtime_context,
)

# Registry
from fastband_core.runtime.registry import (
    ComponentInfo,
    ComponentRegistry,
    ComponentState,
    SimpleRegistry,
    ToolDefinition,
    ToolRegistryBase,
)

__all__ = [
    # Engine
    "EngineState",
    "EngineConfig",
    "EngineInfo",
    "EngineError",
    "EngineStartError",
    "EngineStopError",
    "ToolExecutor",
    "ToolProvider",
    "EngineBase",
    "LifecycleHook",
    "LifecycleManager",
    # Context
    "RequestContext",
    "RuntimeConfig",
    "ServiceRegistry",
    "RuntimeContext",
    "RequestContextManager",
    "get_runtime_context",
    "set_runtime_context",
    "reset_runtime_context",
    # Registry
    "ComponentState",
    "ComponentInfo",
    "ComponentRegistry",
    "SimpleRegistry",
    "ToolDefinition",
    "ToolRegistryBase",
]

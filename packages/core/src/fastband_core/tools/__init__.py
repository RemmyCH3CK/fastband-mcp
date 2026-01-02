"""
Fastband Core Tools - Tool abstraction and registry.

This module provides the shared tool system used by both
Fastband Dev and Fastband Enterprise.

Architecture Rules:
- No framework-specific imports (FastAPI, Flask)
- No database driver imports
- No environment file loading
- Protocol-agnostic definitions

Modules:
- base: Tool base classes and definitions
- registry: Tool registration and lifecycle
"""

# Base types
from fastband_core.tools.base import (
    ProjectType,
    Tool,
    ToolBase,
    ToolCategory,
    ToolDefinition,
    ToolMetadata,
    ToolParameter,
    ToolResult,
    tool,
)

# Registry types
from fastband_core.tools.registry import (
    LazyToolSpec,
    PerformanceReport,
    ToolExecutionStats,
    ToolLoadStatus,
    ToolRegistry,
    ToolRegistryBase,
)

__all__ = [
    # Base types
    "ToolCategory",
    "ProjectType",
    "ToolParameter",
    "ToolMetadata",
    "ToolDefinition",
    "ToolResult",
    "ToolBase",
    "Tool",  # Alias for ToolBase
    "tool",  # Decorator
    # Registry types
    "ToolLoadStatus",
    "LazyToolSpec",
    "PerformanceReport",
    "ToolExecutionStats",
    "ToolRegistryBase",
    "ToolRegistry",  # Alias for ToolRegistryBase
]

"""
Tool base classes and definitions.

All Fastband tools inherit from the Tool base class and define
their parameters and execution logic.

This module re-exports from fastband_core.tools for backwards compatibility.
"""

# Re-export everything from Core
from fastband_core.tools import (
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

__all__ = [
    "ToolCategory",
    "ProjectType",
    "ToolParameter",
    "ToolMetadata",
    "ToolDefinition",
    "ToolResult",
    "Tool",
    "ToolBase",
    "tool",
]

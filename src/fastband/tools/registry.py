"""
Tool Registry - Manages the Tool Garage.

Handles tool registration, loading, unloading, and performance monitoring.

Performance Optimizations (Issue #38):
- Lazy loading: Tools are only imported when first accessed
- Tool class registration: Register class paths, instantiate on demand
- Efficient lookup: O(1) dictionary access for tool retrieval
- Memory efficiency: Unloaded tools don't consume memory

This module re-exports from fastband_core.tools for backwards compatibility
and provides global registry singleton management.
"""

import logging

# Re-export from Core
from fastband_core.tools import (
    LazyToolSpec,
    PerformanceReport,
    ToolExecutionStats,
    ToolLoadStatus,
    ToolRegistry as ToolRegistryBase,
)
from fastband_core.tools import Tool, ToolCategory, ToolResult

logger = logging.getLogger(__name__)


class ToolRegistry(ToolRegistryBase):
    """
    Fastband Tool Registry - manages the Tool Garage.

    Extends ToolRegistryBase with Fastband-specific logging and CLI integration.

    Features:
    - Tool registration and discovery
    - Dynamic loading/unloading
    - Performance monitoring
    - Category-based organization
    - Lazy loading for improved startup performance (Issue #38)

    Example:
        registry = ToolRegistry()
        registry.register(HealthCheckTool())
        registry.load("health_check")

        tool = registry.get("health_check")
        result = await tool.safe_execute()

    Lazy Loading Example:
        registry.register_lazy(
            "my_tool",
            "fastband.tools.custom",
            "MyCustomTool",
            ToolCategory.CORE
        )
        # Tool is only imported/instantiated when first accessed
        tool = registry.get("my_tool")
    """

    def register(self, tool: Tool) -> None:
        """Register a tool with INFO-level logging."""
        super().register(tool)
        logger.info(f"Registered tool: {tool.name} ({tool.category.value})")

    def load(self, name: str) -> ToolLoadStatus:
        """Load a tool with INFO-level logging."""
        status = super().load(name)
        if status.loaded and status.error != "Already loaded":
            logger.info(f"Loaded tool: {name} ({status.load_time_ms:.2f}ms)")
        return status

    def unload(self, name: str, force: bool = False) -> bool:
        """Unload a tool with INFO-level logging."""
        result = super().unload(name, force)
        if result:
            logger.info(f"Unloaded tool: {name}")
        return result

    def unload_category(self, category: ToolCategory) -> int:
        """Unload category with INFO-level logging."""
        count = super().unload_category(category)
        if count:
            logger.info(f"Unloaded {count} tools from {category.value}")
        return count

    def unregister(self, name: str) -> bool:
        """Unregister a tool with INFO-level logging."""
        result = super().unregister(name)
        if result:
            logger.info(f"Unregistered tool: {name}")
        return result

    def _get_performance_recommendation(self) -> str | None:
        """Get Fastband-specific performance recommendation."""
        count = len(self._active)
        if count < 20:
            return None
        if count < 40:
            return "Consider reviewing unused tools with 'fastband tools audit'"
        if count < self._max_active:
            return "Tool count is high. Run 'fastband tools optimize' to unload unused tools"
        return "WARNING: Tool count exceeds recommended limit. Performance may be degraded."


# Global registry instance
_registry: ToolRegistry | None = None


def get_registry() -> ToolRegistry:
    """Get the global tool registry."""
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
    return _registry


def reset_registry() -> None:
    """Reset the global registry (for testing)."""
    global _registry
    _registry = None


__all__ = [
    # Re-exported from Core
    "LazyToolSpec",
    "PerformanceReport",
    "ToolExecutionStats",
    "ToolLoadStatus",
    "Tool",
    "ToolCategory",
    "ToolResult",
    # Fastband-specific
    "ToolRegistry",
    "get_registry",
    "reset_registry",
]

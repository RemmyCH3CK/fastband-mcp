"""
Tool Registry - Manages the Tool Garage.

Handles tool registration, loading, unloading, and performance monitoring.
"""

from typing import Dict, List, Optional, Type, Set
from dataclasses import dataclass
import time
import logging

from fastband.tools.base import Tool, ToolCategory, ToolResult

logger = logging.getLogger(__name__)


@dataclass
class ToolLoadStatus:
    """Status of a loaded tool."""
    name: str
    loaded: bool
    category: ToolCategory
    load_time_ms: float
    error: Optional[str] = None


@dataclass
class PerformanceReport:
    """Performance report for the tool registry."""
    active_tools: int
    available_tools: int
    max_recommended: int
    status: str  # "optimal", "moderate", "heavy", "overloaded"
    categories: Dict[str, int]
    recommendation: Optional[str]
    total_executions: int
    average_execution_time_ms: float


class ToolRegistry:
    """
    Registry for managing the Tool Garage.

    Features:
    - Tool registration and discovery
    - Dynamic loading/unloading
    - Performance monitoring
    - Category-based organization

    Example:
        registry = ToolRegistry()
        registry.register(HealthCheckTool())
        registry.load("health_check")

        tool = registry.get("health_check")
        result = await tool.safe_execute()
    """

    def __init__(self, max_active_tools: int = 60):
        self._available: Dict[str, Tool] = {}      # All registered tools
        self._active: Dict[str, Tool] = {}         # Currently loaded tools
        self._max_active = max_active_tools
        self._load_history: List[ToolLoadStatus] = []
        self._execution_stats: Dict[str, List[float]] = {}  # Tool -> execution times

    # =========================================================================
    # REGISTRATION
    # =========================================================================

    def register(self, tool: Tool) -> None:
        """
        Register a tool (make it available in the garage).

        Args:
            tool: Tool instance to register
        """
        name = tool.name
        if name in self._available:
            logger.warning(f"Tool {name} already registered, replacing")

        self._available[name] = tool
        logger.info(f"Registered tool: {name} ({tool.category.value})")

    def register_class(self, tool_class: Type[Tool]) -> None:
        """
        Register a tool class (instantiates it).

        Args:
            tool_class: Tool class to instantiate and register
        """
        tool = tool_class()
        self.register(tool)

    def unregister(self, name: str) -> bool:
        """
        Unregister a tool (remove from garage).

        Args:
            name: Tool name to unregister

        Returns:
            True if tool was unregistered
        """
        if name in self._active:
            self.unload(name)

        if name in self._available:
            del self._available[name]
            logger.info(f"Unregistered tool: {name}")
            return True

        return False

    # =========================================================================
    # LOADING / UNLOADING
    # =========================================================================

    def load(self, name: str) -> ToolLoadStatus:
        """
        Load a tool from garage into active set.

        Args:
            name: Tool name to load

        Returns:
            ToolLoadStatus with result
        """
        start = time.perf_counter()

        if name not in self._available:
            status = ToolLoadStatus(
                name=name,
                loaded=False,
                category=ToolCategory.CORE,
                load_time_ms=0,
                error=f"Tool not found: {name}",
            )
            self._load_history.append(status)
            return status

        if name in self._active:
            return ToolLoadStatus(
                name=name,
                loaded=True,
                category=self._active[name].category,
                load_time_ms=0,
                error="Already loaded",
            )

        # Check max tools limit (soft limit with warning)
        if len(self._active) >= self._max_active:
            logger.warning(
                f"Tool count ({len(self._active)}) at limit ({self._max_active}). "
                "Performance may be impacted."
            )

        tool = self._available[name]
        self._active[name] = tool

        elapsed = (time.perf_counter() - start) * 1000
        status = ToolLoadStatus(
            name=name,
            loaded=True,
            category=tool.category,
            load_time_ms=elapsed,
        )
        self._load_history.append(status)

        logger.info(f"Loaded tool: {name} ({elapsed:.2f}ms)")
        return status

    def load_category(self, category: ToolCategory) -> List[ToolLoadStatus]:
        """
        Load all tools in a category.

        Args:
            category: Category to load

        Returns:
            List of ToolLoadStatus for each tool
        """
        results = []
        for name, tool in self._available.items():
            if tool.category == category and name not in self._active:
                results.append(self.load(name))
        return results

    def load_core(self) -> List[ToolLoadStatus]:
        """Load all core tools."""
        return self.load_category(ToolCategory.CORE)

    def unload(self, name: str) -> bool:
        """
        Unload a tool from active set.

        Args:
            name: Tool name to unload

        Returns:
            True if tool was unloaded
        """
        if name not in self._active:
            return False

        # Don't unload core tools by default
        tool = self._active[name]
        if tool.category == ToolCategory.CORE:
            logger.warning(f"Cannot unload core tool: {name}")
            return False

        del self._active[name]
        logger.info(f"Unloaded tool: {name}")
        return True

    def unload_category(self, category: ToolCategory) -> int:
        """
        Unload all tools in a category.

        Args:
            category: Category to unload

        Returns:
            Number of tools unloaded
        """
        if category == ToolCategory.CORE:
            logger.warning("Cannot unload core tools")
            return 0

        to_unload = [
            name for name, tool in self._active.items()
            if tool.category == category
        ]

        for name in to_unload:
            del self._active[name]

        logger.info(f"Unloaded {len(to_unload)} tools from {category.value}")
        return len(to_unload)

    # =========================================================================
    # ACCESS
    # =========================================================================

    def get(self, name: str) -> Optional[Tool]:
        """
        Get an active tool by name.

        Args:
            name: Tool name

        Returns:
            Tool instance or None if not loaded
        """
        return self._active.get(name)

    def get_available(self, name: str) -> Optional[Tool]:
        """
        Get a tool from garage (may not be loaded).

        Args:
            name: Tool name

        Returns:
            Tool instance or None if not registered
        """
        return self._available.get(name)

    def get_active_tools(self) -> List[Tool]:
        """Get all currently active tools."""
        return list(self._active.values())

    def get_available_tools(self) -> List[Tool]:
        """Get all available tools in garage."""
        return list(self._available.values())

    def get_tools_by_category(self, category: ToolCategory) -> List[Tool]:
        """Get all tools in a specific category."""
        return [
            tool for tool in self._available.values()
            if tool.category == category
        ]

    def is_loaded(self, name: str) -> bool:
        """Check if a tool is currently loaded."""
        return name in self._active

    def is_registered(self, name: str) -> bool:
        """Check if a tool is registered in the garage."""
        return name in self._available

    # =========================================================================
    # MCP INTEGRATION
    # =========================================================================

    def get_mcp_tools(self) -> List[Dict]:
        """Get MCP tool schemas for all active tools."""
        return [tool.definition.to_mcp_schema() for tool in self._active.values()]

    def get_openai_tools(self) -> List[Dict]:
        """Get OpenAI function schemas for all active tools."""
        return [tool.definition.to_openai_schema() for tool in self._active.values()]

    async def execute(self, name: str, **kwargs) -> ToolResult:
        """
        Execute a tool by name.

        Args:
            name: Tool name
            **kwargs: Tool parameters

        Returns:
            ToolResult from execution
        """
        tool = self.get(name)
        if not tool:
            return ToolResult(
                success=False,
                error=f"Tool not loaded: {name}",
            )

        result = await tool.safe_execute(**kwargs)

        # Track execution stats
        if name not in self._execution_stats:
            self._execution_stats[name] = []
        self._execution_stats[name].append(result.execution_time_ms)

        # Keep only last 100 executions per tool
        if len(self._execution_stats[name]) > 100:
            self._execution_stats[name] = self._execution_stats[name][-100:]

        return result

    # =========================================================================
    # PERFORMANCE MONITORING
    # =========================================================================

    def get_performance_report(self) -> PerformanceReport:
        """Get tool loading performance report."""
        active_count = len(self._active)
        available_count = len(self._available)

        status = "optimal"
        if active_count > 40:
            status = "moderate"
        if active_count > 50:
            status = "heavy"
        if active_count > self._max_active:
            status = "overloaded"

        recommendation = self._get_performance_recommendation()

        # Calculate execution stats
        total_executions = sum(len(times) for times in self._execution_stats.values())
        all_times = [t for times in self._execution_stats.values() for t in times]
        avg_time = sum(all_times) / len(all_times) if all_times else 0

        return PerformanceReport(
            active_tools=active_count,
            available_tools=available_count,
            max_recommended=self._max_active,
            status=status,
            categories=self._count_by_category(),
            recommendation=recommendation,
            total_executions=total_executions,
            average_execution_time_ms=avg_time,
        )

    def _count_by_category(self) -> Dict[str, int]:
        """Count active tools by category."""
        counts: Dict[str, int] = {}
        for tool in self._active.values():
            cat = tool.category.value
            counts[cat] = counts.get(cat, 0) + 1
        return counts

    def _get_performance_recommendation(self) -> Optional[str]:
        """Get performance optimization recommendation."""
        count = len(self._active)
        if count < 20:
            return None
        if count < 40:
            return "Consider reviewing unused tools with 'fastband tools audit'"
        if count < self._max_active:
            return "Tool count is high. Run 'fastband tools optimize' to unload unused tools"
        return "WARNING: Tool count exceeds recommended limit. Performance may be degraded."

    def get_tool_stats(self, name: str) -> Optional[Dict]:
        """Get execution statistics for a specific tool."""
        if name not in self._execution_stats:
            return None

        times = self._execution_stats[name]
        return {
            "name": name,
            "total_executions": len(times),
            "average_time_ms": sum(times) / len(times) if times else 0,
            "min_time_ms": min(times) if times else 0,
            "max_time_ms": max(times) if times else 0,
        }


# Global registry instance
_registry: Optional[ToolRegistry] = None


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

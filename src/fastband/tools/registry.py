"""
Tool Registry - Manages the Tool Garage.

Handles tool registration, loading, unloading, and performance monitoring.

Performance Optimizations (Issue #38):
- Lazy loading: Tools are only imported when first accessed
- Tool class registration: Register class paths, instantiate on demand
- Efficient lookup: O(1) dictionary access for tool retrieval
- Memory efficiency: Unloaded tools don't consume memory
"""

import importlib
import logging
import time
from dataclasses import dataclass

from fastband.tools.base import Tool, ToolCategory, ToolResult

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ToolLoadStatus:
    """Status of a loaded tool."""

    name: str
    loaded: bool
    category: ToolCategory
    load_time_ms: float
    error: str | None = None


@dataclass(slots=True)
class LazyToolSpec:
    """
    Specification for a lazily-loaded tool.

    Instead of importing the tool class immediately, we store the module
    path and class name. The tool is only instantiated when first accessed.

    Performance benefit: Avoids importing heavy tool modules until needed.
    """

    module_path: str
    class_name: str
    category: ToolCategory
    _instance: Tool | None = None

    def get_instance(self) -> Tool:
        """
        Get or create the tool instance.

        This is where lazy loading happens - the module is only
        imported when this method is first called.
        """
        if self._instance is None:
            module = importlib.import_module(self.module_path)
            tool_class = getattr(module, self.class_name)
            self._instance = tool_class()
        return self._instance

    @property
    def is_loaded(self) -> bool:
        """Check if the tool has been instantiated."""
        return self._instance is not None


@dataclass
class PerformanceReport:
    """Performance report for the tool registry."""

    __slots__ = (
        "active_tools",
        "available_tools",
        "max_recommended",
        "status",
        "categories",
        "recommendation",
        "total_executions",
        "average_execution_time_ms",
    )

    active_tools: int
    available_tools: int
    max_recommended: int
    status: str  # "optimal", "moderate", "heavy", "overloaded"
    categories: dict[str, int]
    recommendation: str | None
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
    - Lazy loading for improved startup performance (Issue #38)

    Example:
        registry = ToolRegistry()
        registry.register(HealthCheckTool())
        registry.load("health_check")

        tool = registry.get("health_check")
        result = await tool.safe_execute()

    Lazy Loading Example:
        # Register a tool class path instead of an instance
        registry.register_lazy(
            "my_tool",
            "fastband.tools.custom",
            "MyCustomTool",
            ToolCategory.CORE
        )
        # Tool is only imported/instantiated when first accessed
        tool = registry.get("my_tool")
    """

    __slots__ = (
        "_available",
        "_active",
        "_lazy_specs",
        "_max_active",
        "_load_history",
        "_execution_stats",
        "_category_cache",
    )

    def __init__(self, max_active_tools: int = 60):
        self._available: dict[str, Tool] = {}  # All registered (instantiated) tools
        self._active: dict[str, Tool] = {}  # Currently loaded tools
        self._lazy_specs: dict[str, LazyToolSpec] = {}  # Lazy-loaded tool specs
        self._max_active = max_active_tools
        self._load_history: list[ToolLoadStatus] = []
        self._execution_stats: dict[str, list[float]] = {}  # Tool -> execution times
        self._category_cache: dict[str, int] | None = None  # Cached category counts

    # =========================================================================
    # REGISTRATION
    # =========================================================================

    def register(self, tool: Tool) -> None:
        """
        Register a tool instance (make it available in the garage).

        Args:
            tool: Tool instance to register

        Note: For better startup performance, consider using register_lazy()
        to defer tool instantiation until first use.
        """
        name = tool.name
        if name in self._available or name in self._lazy_specs:
            logger.warning(f"Tool {name} already registered, replacing")
            # Remove from lazy specs if present
            self._lazy_specs.pop(name, None)

        self._available[name] = tool
        self._invalidate_cache()
        logger.info(f"Registered tool: {name} ({tool.category.value})")

    def register_lazy(
        self,
        name: str,
        module_path: str,
        class_name: str,
        category: ToolCategory,
    ) -> None:
        """
        Register a tool for lazy loading.

        The tool class will only be imported and instantiated when first accessed.
        This significantly improves startup time when many tools are registered.

        Args:
            name: Tool name for lookup
            module_path: Full module path (e.g., "fastband.tools.git")
            class_name: Class name within the module (e.g., "GitStatusTool")
            category: Tool category for organization

        Example:
            registry.register_lazy(
                "git_status",
                "fastband.tools.git",
                "GitStatusTool",
                ToolCategory.GIT
            )
        """
        if name in self._available:
            logger.warning(
                f"Tool {name} already registered as instance, skipping lazy registration"
            )
            return

        if name in self._lazy_specs:
            logger.warning(f"Tool {name} already registered for lazy loading, replacing")

        self._lazy_specs[name] = LazyToolSpec(
            module_path=module_path,
            class_name=class_name,
            category=category,
        )
        self._invalidate_cache()
        logger.debug(f"Registered lazy tool: {name} ({category.value})")

    def register_class(self, tool_class: type[Tool]) -> None:
        """
        Register a tool class (instantiates it immediately).

        Args:
            tool_class: Tool class to instantiate and register

        Note: For better startup performance, consider using register_lazy().
        """
        tool = tool_class()
        self.register(tool)

    def _invalidate_cache(self) -> None:
        """Invalidate cached data when registry changes."""
        self._category_cache = None

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

        removed = False
        if name in self._available:
            del self._available[name]
            removed = True

        if name in self._lazy_specs:
            del self._lazy_specs[name]
            removed = True

        if removed:
            self._invalidate_cache()
            logger.info(f"Unregistered tool: {name}")

        return removed

    # =========================================================================
    # LOADING / UNLOADING
    # =========================================================================

    def _resolve_tool(self, name: str) -> Tool | None:
        """
        Resolve a tool by name, handling lazy loading if needed.

        This is the core lazy loading mechanism. If a tool is registered
        lazily, it will be instantiated on first access.

        Args:
            name: Tool name to resolve

        Returns:
            Tool instance or None if not found
        """
        # Check already-instantiated tools first (fast path)
        if name in self._available:
            return self._available[name]

        # Check lazy specs and instantiate if found
        if name in self._lazy_specs:
            spec = self._lazy_specs[name]
            try:
                tool = spec.get_instance()
                # Move to available once instantiated
                self._available[name] = tool
                logger.debug(f"Lazy-loaded tool: {name}")
                return tool
            except Exception as e:
                logger.error(f"Failed to lazy-load tool {name}: {e}")
                return None

        return None

    def load(self, name: str) -> ToolLoadStatus:
        """
        Load a tool from garage into active set.

        Supports both eagerly-registered and lazily-registered tools.
        Lazy tools are instantiated on first load.

        Args:
            name: Tool name to load

        Returns:
            ToolLoadStatus with result
        """
        start = time.perf_counter()

        # Already active?
        if name in self._active:
            return ToolLoadStatus(
                name=name,
                loaded=True,
                category=self._active[name].category,
                load_time_ms=0,
                error="Already loaded",
            )

        # Try to resolve the tool (handles lazy loading)
        tool = self._resolve_tool(name)

        if tool is None:
            # Check if it's a lazy spec that failed to load
            category = ToolCategory.CORE
            if name in self._lazy_specs:
                category = self._lazy_specs[name].category

            status = ToolLoadStatus(
                name=name,
                loaded=False,
                category=category,
                load_time_ms=(time.perf_counter() - start) * 1000,
                error=f"Tool not found: {name}",
            )
            self._load_history.append(status)
            return status

        # Check max tools limit (soft limit with warning)
        if len(self._active) >= self._max_active:
            logger.warning(
                f"Tool count ({len(self._active)}) at limit ({self._max_active}). "
                "Performance may be impacted."
            )

        self._active[name] = tool
        self._invalidate_cache()

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

    def load_category(self, category: ToolCategory) -> list[ToolLoadStatus]:
        """
        Load all tools in a category.

        Includes both eagerly-registered and lazily-registered tools.

        Args:
            category: Category to load

        Returns:
            List of ToolLoadStatus for each tool
        """
        results = []

        # Load from available (already instantiated)
        for name, tool in self._available.items():
            if tool.category == category and name not in self._active:
                results.append(self.load(name))

        # Load from lazy specs
        for name, spec in self._lazy_specs.items():
            if spec.category == category and name not in self._active:
                results.append(self.load(name))

        return results

    def load_core(self) -> list[ToolLoadStatus]:
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
        self._invalidate_cache()
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

        to_unload = [name for name, tool in self._active.items() if tool.category == category]

        for name in to_unload:
            del self._active[name]

        if to_unload:
            self._invalidate_cache()

        logger.info(f"Unloaded {len(to_unload)} tools from {category.value}")
        return len(to_unload)

    # =========================================================================
    # ACCESS
    # =========================================================================

    def get(self, name: str) -> Tool | None:
        """
        Get an active tool by name.

        Args:
            name: Tool name

        Returns:
            Tool instance or None if not loaded
        """
        return self._active.get(name)

    def get_available(self, name: str) -> Tool | None:
        """
        Get a tool from garage (may not be loaded).

        Supports lazy loading - if the tool is registered lazily,
        it will be instantiated on first access.

        Args:
            name: Tool name

        Returns:
            Tool instance or None if not registered
        """
        return self._resolve_tool(name)

    def get_active_tools(self) -> list[Tool]:
        """Get all currently active tools."""
        return list(self._active.values())

    def get_available_tools(self) -> list[Tool]:
        """
        Get all available tools in garage.

        Note: This instantiates any lazy-loaded tools. For checking
        available tools without instantiation, use get_available_names().
        """
        # Resolve all lazy specs first
        for name in list(self._lazy_specs.keys()):
            self._resolve_tool(name)
        return list(self._available.values())

    def get_available_names(self) -> list[str]:
        """
        Get names of all available tools without instantiating lazy ones.

        This is more efficient than get_available_tools() when you only
        need to check what tools are available.
        """
        names = set(self._available.keys())
        names.update(self._lazy_specs.keys())
        return list(names)

    def get_lazy_tool_names(self) -> list[str]:
        """
        Get names of all lazily registered tools.

        These are tools that have been registered but not yet instantiated.
        Useful for loading all available tools at once.
        """
        return list(self._lazy_specs.keys())

    def get_tools_by_category(self, category: ToolCategory) -> list[Tool]:
        """
        Get all tools in a specific category.

        Note: This may instantiate lazy-loaded tools in that category.
        """
        tools = []

        # From available (already instantiated)
        for tool in self._available.values():
            if tool.category == category:
                tools.append(tool)

        # From lazy specs (will instantiate)
        for name, spec in list(self._lazy_specs.items()):
            if spec.category == category and name not in self._available:
                tool = self._resolve_tool(name)
                if tool:
                    tools.append(tool)

        return tools

    def is_loaded(self, name: str) -> bool:
        """Check if a tool is currently loaded (active)."""
        return name in self._active

    def is_registered(self, name: str) -> bool:
        """Check if a tool is registered in the garage (eager or lazy)."""
        return name in self._available or name in self._lazy_specs

    def is_lazy(self, name: str) -> bool:
        """Check if a tool is registered for lazy loading."""
        return name in self._lazy_specs and name not in self._available

    # =========================================================================
    # MCP INTEGRATION
    # =========================================================================

    def get_mcp_tools(self) -> list[dict]:
        """Get MCP tool schemas for all active tools."""
        return [tool.definition.to_mcp_schema() for tool in self._active.values()]

    def get_openai_tools(self) -> list[dict]:
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
        # Include both instantiated and lazy tools
        available_count = len(self._available) + len(self._lazy_specs)

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

    def _count_by_category(self) -> dict[str, int]:
        """
        Count active tools by category.

        Uses caching to avoid recounting on every call.
        Cache is invalidated when tools are loaded/unloaded.
        """
        if self._category_cache is not None:
            return self._category_cache

        counts: dict[str, int] = {}
        for tool in self._active.values():
            cat = tool.category.value
            counts[cat] = counts.get(cat, 0) + 1

        self._category_cache = counts
        return counts

    def _get_performance_recommendation(self) -> str | None:
        """Get performance optimization recommendation."""
        count = len(self._active)
        if count < 20:
            return None
        if count < 40:
            return "Consider reviewing unused tools with 'fastband tools audit'"
        if count < self._max_active:
            return "Tool count is high. Run 'fastband tools optimize' to unload unused tools"
        return "WARNING: Tool count exceeds recommended limit. Performance may be degraded."

    def get_tool_stats(self, name: str) -> dict | None:
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

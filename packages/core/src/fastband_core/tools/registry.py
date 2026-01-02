"""
Core Tool Registry - Manages tool registration and execution.

Provides:
- Tool registration (eager and lazy loading)
- Tool loading/unloading lifecycle
- Performance monitoring
- Category-based organization

Architecture Rules:
- No framework-specific imports (FastAPI, Flask)
- No database driver imports
- No environment file loading
- Protocol-agnostic execution
"""

import importlib
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, TypeVar

from fastband_core.tools.base import ToolBase, ToolCategory, ToolResult

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=ToolBase)


@dataclass(slots=True)
class ToolLoadStatus:
    """Status of a tool load operation."""

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
    _instance: ToolBase | None = None

    def get_instance(self) -> ToolBase:
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


@dataclass
class ToolExecutionStats:
    """Execution statistics for a tool."""

    name: str
    total_executions: int = 0
    total_time_ms: float = 0.0
    min_time_ms: float = float("inf")
    max_time_ms: float = 0.0
    last_execution: datetime | None = None
    error_count: int = 0

    @property
    def average_time_ms(self) -> float:
        """Calculate average execution time."""
        if self.total_executions == 0:
            return 0.0
        return self.total_time_ms / self.total_executions

    def record(self, execution_time_ms: float, success: bool = True) -> None:
        """Record an execution."""
        self.total_executions += 1
        self.total_time_ms += execution_time_ms
        self.min_time_ms = min(self.min_time_ms, execution_time_ms)
        self.max_time_ms = max(self.max_time_ms, execution_time_ms)
        self.last_execution = datetime.now(timezone.utc)
        if not success:
            self.error_count += 1


class ToolRegistryBase:
    """
    Base registry for managing tools.

    Features:
    - Tool registration and discovery
    - Dynamic loading/unloading
    - Performance monitoring
    - Category-based organization
    - Lazy loading for improved startup performance

    Example:
        registry = ToolRegistryBase()
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
        self._available: dict[str, ToolBase] = {}  # All registered (instantiated) tools
        self._active: dict[str, ToolBase] = {}  # Currently loaded tools
        self._lazy_specs: dict[str, LazyToolSpec] = {}  # Lazy-loaded tool specs
        self._max_active = max_active_tools
        self._load_history: list[ToolLoadStatus] = []
        self._execution_stats: dict[str, ToolExecutionStats] = {}
        self._category_cache: dict[str, int] | None = None

    # =========================================================================
    # REGISTRATION
    # =========================================================================

    def register(self, tool: ToolBase) -> None:
        """
        Register a tool instance (make it available).

        Args:
            tool: Tool instance to register

        Note: For better startup performance, consider using register_lazy()
        to defer tool instantiation until first use.
        """
        name = tool.name
        if name in self._available or name in self._lazy_specs:
            logger.warning(f"Tool {name} already registered, replacing")
            self._lazy_specs.pop(name, None)

        self._available[name] = tool
        self._invalidate_cache()
        logger.debug(f"Registered tool: {name} ({tool.category.value})")

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

    def register_class(self, tool_class: type[ToolBase]) -> None:
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
        Unregister a tool.

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
            logger.debug(f"Unregistered tool: {name}")

        return removed

    # =========================================================================
    # LOADING / UNLOADING
    # =========================================================================

    def _resolve_tool(self, name: str) -> ToolBase | None:
        """
        Resolve a tool by name, handling lazy loading if needed.

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
                self._available[name] = tool
                logger.debug(f"Lazy-loaded tool: {name}")
                return tool
            except Exception as e:
                logger.error(f"Failed to lazy-load tool {name}: {e}")
                return None

        return None

    def load(self, name: str) -> ToolLoadStatus:
        """
        Load a tool into active set.

        Supports both eagerly-registered and lazily-registered tools.

        Args:
            name: Tool name to load

        Returns:
            ToolLoadStatus with result
        """
        start = time.perf_counter()

        if name in self._active:
            return ToolLoadStatus(
                name=name,
                loaded=True,
                category=self._active[name].category,
                load_time_ms=0,
                error="Already loaded",
            )

        tool = self._resolve_tool(name)

        if tool is None:
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

        logger.debug(f"Loaded tool: {name} ({elapsed:.2f}ms)")
        return status

    def load_category(self, category: ToolCategory) -> list[ToolLoadStatus]:
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

        for name, spec in self._lazy_specs.items():
            if spec.category == category and name not in self._active:
                results.append(self.load(name))

        return results

    def load_core(self) -> list[ToolLoadStatus]:
        """Load all core tools."""
        return self.load_category(ToolCategory.CORE)

    def unload(self, name: str, force: bool = False) -> bool:
        """
        Unload a tool from active set.

        Args:
            name: Tool name to unload
            force: If True, unload even core tools

        Returns:
            True if tool was unloaded
        """
        if name not in self._active:
            return False

        tool = self._active[name]
        if tool.category == ToolCategory.CORE and not force:
            logger.warning(f"Cannot unload core tool: {name}")
            return False

        del self._active[name]
        self._invalidate_cache()
        logger.debug(f"Unloaded tool: {name}")
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
            name for name, tool in self._active.items() if tool.category == category
        ]

        for name in to_unload:
            del self._active[name]

        if to_unload:
            self._invalidate_cache()

        logger.debug(f"Unloaded {len(to_unload)} tools from {category.value}")
        return len(to_unload)

    # =========================================================================
    # ACCESS
    # =========================================================================

    def get(self, name: str) -> ToolBase | None:
        """
        Get an active tool by name.

        Args:
            name: Tool name

        Returns:
            Tool instance or None if not loaded
        """
        return self._active.get(name)

    def get_available(self, name: str) -> ToolBase | None:
        """
        Get a tool (may not be loaded).

        Supports lazy loading - if the tool is registered lazily,
        it will be instantiated on first access.

        Args:
            name: Tool name

        Returns:
            Tool instance or None if not registered
        """
        return self._resolve_tool(name)

    def get_active_tools(self) -> list[ToolBase]:
        """Get all currently active tools."""
        return list(self._active.values())

    def get_available_tools(self) -> list[ToolBase]:
        """
        Get all available tools.

        Note: This instantiates any lazy-loaded tools.
        """
        for name in list(self._lazy_specs.keys()):
            self._resolve_tool(name)
        return list(self._available.values())

    def get_available_names(self) -> list[str]:
        """
        Get names of all available tools without instantiating lazy ones.
        """
        names = set(self._available.keys())
        names.update(self._lazy_specs.keys())
        return list(names)

    def get_lazy_tool_names(self) -> list[str]:
        """Get names of all lazily registered tools."""
        return list(self._lazy_specs.keys())

    def get_tools_by_category(self, category: ToolCategory) -> list[ToolBase]:
        """
        Get all tools in a specific category.

        Note: This may instantiate lazy-loaded tools in that category.
        """
        tools = []

        for tool in self._available.values():
            if tool.category == category:
                tools.append(tool)

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
        """Check if a tool is registered (eager or lazy)."""
        return name in self._available or name in self._lazy_specs

    def is_lazy(self, name: str) -> bool:
        """Check if a tool is registered for lazy loading."""
        return name in self._lazy_specs and name not in self._available

    # =========================================================================
    # SCHEMA GENERATION
    # =========================================================================

    def get_schemas(self) -> list[dict[str, Any]]:
        """Get standard schemas for all active tools."""
        return [tool.definition.to_schema() for tool in self._active.values()]

    def get_mcp_tools(self) -> list[dict[str, Any]]:
        """Get MCP tool schemas for all active tools."""
        return [tool.definition.to_mcp_schema() for tool in self._active.values()]

    def get_openai_tools(self) -> list[dict[str, Any]]:
        """Get OpenAI function schemas for all active tools."""
        return [tool.definition.to_openai_schema() for tool in self._active.values()]

    # =========================================================================
    # EXECUTION
    # =========================================================================

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
            self._execution_stats[name] = ToolExecutionStats(name=name)
        self._execution_stats[name].record(result.execution_time_ms, result.success)

        return result

    # =========================================================================
    # PERFORMANCE MONITORING
    # =========================================================================

    def get_performance_report(self) -> PerformanceReport:
        """Get tool loading performance report."""
        active_count = len(self._active)
        available_count = len(self._available) + len(self._lazy_specs)

        status = "optimal"
        if active_count > 40:
            status = "moderate"
        if active_count > 50:
            status = "heavy"
        if active_count > self._max_active:
            status = "overloaded"

        recommendation = self._get_performance_recommendation()

        total_executions = sum(
            stats.total_executions for stats in self._execution_stats.values()
        )
        total_time = sum(stats.total_time_ms for stats in self._execution_stats.values())
        avg_time = total_time / total_executions if total_executions > 0 else 0

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
        """Count active tools by category with caching."""
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
            return "Consider reviewing unused tools"
        if count < self._max_active:
            return "Tool count is high. Consider unloading unused tools"
        return "WARNING: Tool count exceeds recommended limit. Performance may be degraded."

    def get_tool_stats(self, name: str) -> dict[str, Any] | None:
        """Get execution statistics for a specific tool."""
        stats = self._execution_stats.get(name)
        if not stats:
            return None

        return {
            "name": stats.name,
            "total_executions": stats.total_executions,
            "average_time_ms": stats.average_time_ms,
            "min_time_ms": stats.min_time_ms if stats.min_time_ms != float("inf") else 0,
            "max_time_ms": stats.max_time_ms,
            "error_count": stats.error_count,
            "last_execution": stats.last_execution.isoformat()
            if stats.last_execution
            else None,
        }

    def get_load_history(self) -> list[ToolLoadStatus]:
        """Get tool load history."""
        return list(self._load_history)

    def clear_stats(self) -> None:
        """Clear execution statistics."""
        self._execution_stats.clear()
        self._load_history.clear()


# Backwards compatibility alias
ToolRegistry = ToolRegistryBase

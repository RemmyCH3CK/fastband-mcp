"""
Fastband Plugin System - Extensibility via Python entry points.

Plugins can extend Fastband with:
- Additional tools (via ToolRegistry)
- Event handlers (via EventBus)
- API routes (via FastAPI routers)
- CLI commands (via Typer apps)

Uses standard Python entry points (setuptools) for discovery,
making it easy to package and distribute plugins.

Example plugin pyproject.toml:
    [project.entry-points."fastband.plugins"]
    my_plugin = "my_plugin:MyPlugin"

Performance Optimizations:
- Lazy plugin loading (only when needed)
- Cached discovery results
- Async lifecycle hooks
"""

import asyncio
import logging
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass
from importlib.metadata import entry_points
from typing import Any

from fastband.core.events import EventBus, HubEventType, get_event_bus

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class PluginMetadata:
    """Metadata about a discovered plugin."""

    name: str
    entry_point: str
    module: str
    version: str = "0.1.0"
    description: str = ""
    author: str = ""
    enabled: bool = True

    # Capability flags
    provides_tools: bool = False
    provides_routes: bool = False
    provides_cli: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "enabled": self.enabled,
            "provides_tools": self.provides_tools,
            "provides_routes": self.provides_routes,
            "provides_cli": self.provides_cli,
        }


class Plugin(ABC):
    """
    Abstract base class for Fastband plugins.

    Plugins follow a lifecycle:
    1. Discovery - Found via entry points
    2. Load - __init__ called, metadata read
    3. Initialize - on_load() called with EventBus
    4. Active - Plugin is running, can handle events
    5. Cleanup - on_unload() called before shutdown

    Example:
        class MyPlugin(Plugin):
            name = "my-plugin"
            version = "1.0.0"
            description = "Does something useful"

            async def on_load(self, bus: EventBus) -> None:
                # Subscribe to events
                @bus.on(EventType.TICKET_COMPLETED)
                async def handle_completion(data):
                    self.notify_slack(data)

            def get_tools(self) -> List[Tool]:
                return [MyCustomTool()]
    """

    # Required class attributes
    name: str = "unnamed-plugin"
    version: str = "0.1.0"
    description: str = ""
    author: str = ""

    # Capability flags (override in subclass)
    provides_tools: bool = False
    provides_routes: bool = False
    provides_cli: bool = False

    @abstractmethod
    async def on_load(self, bus: EventBus) -> None:
        """
        Called when the plugin is loaded.

        Use this to:
        - Subscribe to events
        - Initialize resources
        - Validate configuration

        Args:
            bus: The global EventBus for subscribing to events
        """
        pass

    async def on_unload(self) -> None:
        """
        Called when the plugin is unloaded.

        Use this to:
        - Clean up resources
        - Close connections
        - Unsubscribe from external services
        """
        pass

    def get_tools(self) -> list[Any]:
        """
        Return tools provided by this plugin.

        Override this to add custom tools to the ToolRegistry.

        Returns:
            List of Tool instances
        """
        return []

    def get_api_router(self) -> Any | None:
        """
        Return a FastAPI APIRouter for plugin routes.

        Override this to add API endpoints.

        Returns:
            FastAPI APIRouter or None
        """
        return None

    def get_cli_app(self) -> Any | None:
        """
        Return a Typer app for plugin CLI commands.

        Override this to add CLI commands.

        Returns:
            Typer app or None
        """
        return None

    def get_metadata(self) -> PluginMetadata:
        """Get plugin metadata."""
        return PluginMetadata(
            name=self.name,
            entry_point=f"{self.__class__.__module__}:{self.__class__.__name__}",
            module=self.__class__.__module__,
            version=self.version,
            description=self.description,
            author=self.author,
            provides_tools=self.provides_tools,
            provides_routes=self.provides_routes,
            provides_cli=self.provides_cli,
        )


class PluginManager:
    """
    Central manager for discovering, loading, and managing plugins.

    Plugins are discovered via Python entry points under the group
    "fastband.plugins". This allows plugins to be installed as
    separate packages and automatically discovered.

    Example:
        manager = get_plugin_manager()

        # Discover available plugins
        plugins = manager.discover()
        print(f"Found {len(plugins)} plugins")

        # Load a specific plugin
        await manager.load("my-plugin")

        # Get all loaded plugins
        for name, plugin in manager.loaded.items():
            print(f"  - {name} v{plugin.version}")
    """

    ENTRY_POINT_GROUP = "fastband.plugins"

    __slots__ = ("_event_bus", "_discovered", "_loaded", "_active", "_async_lock", "_sync_lock")

    def __init__(self, event_bus: EventBus | None = None):
        self._event_bus = event_bus or get_event_bus()
        self._discovered: dict[str, type[Plugin]] = {}
        self._loaded: dict[str, Plugin] = {}
        self._active: dict[str, Plugin] = {}
        self._async_lock: asyncio.Lock | None = None  # Lazy init for async operations
        self._sync_lock = threading.Lock()  # Thread-safe for discovery

    def _get_async_lock(self) -> asyncio.Lock:
        """Get or create the async lock (lazy initialization)."""
        if self._async_lock is None:
            self._async_lock = asyncio.Lock()
        return self._async_lock

    @property
    def loaded(self) -> dict[str, Plugin]:
        """Get all loaded plugins."""
        return self._loaded.copy()

    @property
    def active(self) -> dict[str, Plugin]:
        """Get all active plugins."""
        return self._active.copy()

    def discover(self) -> list[PluginMetadata]:
        """
        Discover available plugins via entry points.

        Returns:
            List of plugin metadata for all discovered plugins
        """
        plugins: list[PluginMetadata] = []
        self._discovered.clear()

        try:
            # Python 3.10+ entry_points() returns SelectableGroups
            eps = entry_points()

            # Handle both old and new API
            if hasattr(eps, "select"):
                group = eps.select(group=self.ENTRY_POINT_GROUP)
            else:
                group = eps.get(self.ENTRY_POINT_GROUP, [])

            for ep in group:
                try:
                    # Load the plugin class
                    plugin_class = ep.load()

                    # Validate it's a Plugin subclass
                    if not (isinstance(plugin_class, type) and issubclass(plugin_class, Plugin)):
                        logger.warning(f"Entry point {ep.name} is not a Plugin subclass")
                        continue

                    # Store for later loading
                    self._discovered[ep.name] = plugin_class

                    # Create temporary instance for metadata
                    temp_instance = plugin_class()
                    metadata = temp_instance.get_metadata()
                    metadata.name = ep.name  # Use entry point name

                    plugins.append(metadata)
                    logger.debug(f"Discovered plugin: {ep.name}")

                except Exception as e:
                    logger.error(f"Failed to load entry point {ep.name}: {e}")

        except Exception as e:
            logger.error(f"Error discovering plugins: {e}")

        logger.info(f"Discovered {len(plugins)} plugins")
        return plugins

    async def load(self, name: str, config: dict[str, Any] | None = None) -> bool:
        """
        Load a plugin by name.

        Args:
            name: Plugin name (from entry point)
            config: Optional plugin-specific configuration

        Returns:
            True if plugin was loaded successfully
        """
        async with self._get_async_lock():
            # Check if already loaded
            if name in self._loaded:
                logger.warning(f"Plugin {name} already loaded")
                return True

            # Find plugin class
            plugin_class = self._discovered.get(name)
            if plugin_class is None:
                # Try to discover if not already done
                self.discover()
                plugin_class = self._discovered.get(name)

            if plugin_class is None:
                logger.error(f"Plugin not found: {name}")
                return False

            try:
                # Instantiate plugin
                plugin = plugin_class()

                # Call on_load lifecycle hook
                await plugin.on_load(self._event_bus)

                # Store as loaded
                self._loaded[name] = plugin
                self._active[name] = plugin

                # Emit plugin loaded event
                await self._event_bus.emit(
                    HubEventType.PLUGIN_LOADED,
                    {"plugin_name": name, "version": plugin.version},
                    source="plugin_manager",
                )

                logger.info(f"Loaded plugin: {name} v{plugin.version}")
                return True

            except Exception as e:
                logger.error(f"Failed to load plugin {name}: {e}", exc_info=True)
                return False

    async def unload(self, name: str) -> bool:
        """
        Unload a plugin.

        Args:
            name: Plugin name to unload

        Returns:
            True if plugin was unloaded successfully
        """
        async with self._get_async_lock():
            plugin = self._loaded.get(name)
            if plugin is None:
                logger.warning(f"Plugin {name} not loaded")
                return False

            try:
                # Call on_unload lifecycle hook
                await plugin.on_unload()

                # Remove from active and loaded
                self._active.pop(name, None)
                self._loaded.pop(name, None)

                # Emit plugin unloaded event
                await self._event_bus.emit(
                    HubEventType.PLUGIN_UNLOADED,
                    {"plugin_name": name},
                    source="plugin_manager",
                )

                logger.info(f"Unloaded plugin: {name}")
                return True

            except Exception as e:
                logger.error(f"Error unloading plugin {name}: {e}", exc_info=True)
                return False

    async def load_all(self) -> int:
        """
        Load all discovered plugins.

        Returns:
            Number of plugins successfully loaded
        """
        if not self._discovered:
            self.discover()

        loaded_count = 0
        for name in self._discovered:
            if await self.load(name):
                loaded_count += 1

        return loaded_count

    async def unload_all(self) -> None:
        """Unload all loaded plugins."""
        for name in list(self._loaded.keys()):
            await self.unload(name)

    def get_all_tools(self) -> list[Any]:
        """
        Collect tools from all active plugins.

        Returns:
            List of all Tool instances from plugins
        """
        tools = []
        for plugin in self._active.values():
            if plugin.provides_tools:
                tools.extend(plugin.get_tools())
        return tools

    def get_all_routers(self) -> list[tuple]:
        """
        Collect API routers from all active plugins.

        Returns:
            List of (plugin_name, router) tuples
        """
        routers = []
        for name, plugin in self._active.items():
            if plugin.provides_routes:
                router = plugin.get_api_router()
                if router:
                    routers.append((name, router))
        return routers

    def get_all_cli_apps(self) -> list[tuple]:
        """
        Collect CLI apps from all active plugins.

        Returns:
            List of (plugin_name, typer_app) tuples
        """
        apps = []
        for name, plugin in self._active.items():
            if plugin.provides_cli:
                cli_app = plugin.get_cli_app()
                if cli_app:
                    apps.append((name, cli_app))
        return apps

    def get_plugin(self, name: str) -> Plugin | None:
        """Get a loaded plugin by name."""
        return self._loaded.get(name)

    def is_loaded(self, name: str) -> bool:
        """Check if a plugin is loaded."""
        return name in self._loaded

    def is_discovered(self, name: str) -> bool:
        """Check if a plugin has been discovered."""
        return name in self._discovered

    def has_discovered(self) -> bool:
        """Check if any plugins have been discovered."""
        return bool(self._discovered)

    def ensure_discovered(self) -> list[PluginMetadata]:
        """Ensure plugins have been discovered, running discovery if needed."""
        if not self._discovered:
            return self.discover()
        # Return metadata for already-discovered plugins
        plugins = []
        for name, plugin_class in self._discovered.items():
            temp = plugin_class()
            metadata = temp.get_metadata()
            metadata.name = name
            plugins.append(metadata)
        return plugins

    def get_plugin_metadata(self, name: str) -> PluginMetadata | None:
        """
        Get metadata for a discovered plugin by name.

        Args:
            name: Plugin name to get metadata for

        Returns:
            PluginMetadata or None if not found
        """
        plugin_class = self._discovered.get(name)
        if plugin_class is None:
            return None
        temp = plugin_class()
        metadata = temp.get_metadata()
        metadata.name = name
        return metadata

    def get_plugin_instance(self, name: str) -> Plugin | None:
        """
        Get a fresh instance of a discovered plugin (not loaded into manager).

        Useful for inspecting plugin capabilities without loading it.

        Args:
            name: Plugin name

        Returns:
            Plugin instance or None if not found
        """
        plugin_class = self._discovered.get(name)
        if plugin_class is None:
            return None
        return plugin_class()


# =============================================================================
# Global Instance Management
# =============================================================================

_plugin_manager: PluginManager | None = None
_manager_lock = threading.Lock()  # Thread-safe singleton creation


def get_plugin_manager() -> PluginManager:
    """
    Get the global PluginManager instance (thread-safe).

    Creates the instance on first call (lazy initialization).
    Uses double-checked locking for thread safety.
    """
    global _plugin_manager

    if _plugin_manager is None:
        with _manager_lock:
            if _plugin_manager is None:  # Double-check after acquiring lock
                _plugin_manager = PluginManager()

    return _plugin_manager


def reset_plugin_manager() -> None:
    """Reset the global plugin manager (for testing)."""
    global _plugin_manager
    with _manager_lock:
        _plugin_manager = None

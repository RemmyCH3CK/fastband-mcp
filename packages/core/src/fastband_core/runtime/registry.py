"""
Component registry for runtime services.

Provides registration and discovery of runtime components like tools,
handlers, and plugins.

This module contains NO framework-specific imports.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Generic, TypeVar


class ComponentState(Enum):
    """Component lifecycle states."""

    REGISTERED = "registered"
    LOADING = "loading"
    ACTIVE = "active"
    DISABLED = "disabled"
    ERROR = "error"


@dataclass
class ComponentInfo:
    """Metadata about a registered component."""

    name: str
    type: str  # "tool", "handler", "plugin", etc.
    description: str = ""
    version: str = "0.0.0"
    state: ComponentState = ComponentState.REGISTERED
    registered_at: datetime = field(default_factory=datetime.utcnow)
    loaded_at: datetime | None = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


T = TypeVar("T")


class ComponentRegistry(ABC, Generic[T]):
    """
    Abstract base for component registries.

    Manages registration, loading, and lifecycle of components.
    Subclasses provide type-specific behavior.

    Example:
        class ToolRegistry(ComponentRegistry[Tool]):
            def _do_load(self, name: str) -> Tool:
                return self._registered[name]()
    """

    def __init__(self) -> None:
        self._registered: dict[str, T | Callable[[], T]] = {}
        self._active: dict[str, T] = {}
        self._info: dict[str, ComponentInfo] = {}
        self._lazy: dict[str, Callable[[], T]] = {}

    def register(
        self,
        name: str,
        component: T | Callable[[], T],
        info: ComponentInfo | None = None,
    ) -> None:
        """
        Register a component.

        Args:
            name: Component name.
            component: Component instance or factory.
            info: Optional metadata.
        """
        self._registered[name] = component
        self._info[name] = info or ComponentInfo(
            name=name,
            type=self._get_component_type(),
        )
        self._info[name].state = ComponentState.REGISTERED

    def register_lazy(
        self,
        name: str,
        factory: Callable[[], T],
        info: ComponentInfo | None = None,
    ) -> None:
        """
        Register a lazily-loaded component.

        Args:
            name: Component name.
            factory: Factory function to create component.
            info: Optional metadata.
        """
        self._lazy[name] = factory
        self._info[name] = info or ComponentInfo(
            name=name,
            type=self._get_component_type(),
        )
        self._info[name].state = ComponentState.REGISTERED

    def load(self, name: str) -> T:
        """
        Load and activate a component.

        Args:
            name: Component name to load.

        Returns:
            The loaded component.

        Raises:
            KeyError: If component is not registered.
        """
        if name in self._active:
            return self._active[name]

        if name not in self._registered and name not in self._lazy:
            raise KeyError(f"Component not registered: {name}")

        self._info[name].state = ComponentState.LOADING

        try:
            if name in self._lazy:
                component = self._lazy[name]()
            elif callable(self._registered[name]) and not isinstance(
                self._registered[name], type
            ):
                # It's a factory function
                component = self._registered[name]()  # type: ignore
            else:
                component = self._registered[name]  # type: ignore

            component = self._do_load(name, component)
            self._active[name] = component
            self._info[name].state = ComponentState.ACTIVE
            self._info[name].loaded_at = datetime.utcnow()
            return component

        except Exception as e:
            self._info[name].state = ComponentState.ERROR
            self._info[name].error = str(e)
            raise

    def unload(self, name: str) -> bool:
        """
        Unload a component.

        Args:
            name: Component name to unload.

        Returns:
            True if component was unloaded.
        """
        if name not in self._active:
            return False

        try:
            self._do_unload(name, self._active[name])
        except Exception:
            pass

        del self._active[name]
        self._info[name].state = ComponentState.DISABLED
        return True

    def get(self, name: str) -> T | None:
        """Get an active component by name."""
        return self._active.get(name)

    def require(self, name: str) -> T:
        """
        Get a required component.

        Loads if not already active.
        """
        if name in self._active:
            return self._active[name]
        return self.load(name)

    def get_active(self) -> list[T]:
        """Get all active components."""
        return list(self._active.values())

    def get_active_names(self) -> list[str]:
        """Get names of all active components."""
        return list(self._active.keys())

    def get_registered_names(self) -> list[str]:
        """Get names of all registered components."""
        return list(set(self._registered.keys()) | set(self._lazy.keys()))

    def get_lazy_names(self) -> list[str]:
        """Get names of lazily-registered components."""
        return list(self._lazy.keys())

    def get_info(self, name: str) -> ComponentInfo | None:
        """Get component metadata."""
        return self._info.get(name)

    def list_info(self) -> list[ComponentInfo]:
        """Get metadata for all components."""
        return list(self._info.values())

    def is_registered(self, name: str) -> bool:
        """Check if a component is registered."""
        return name in self._registered or name in self._lazy

    def is_active(self, name: str) -> bool:
        """Check if a component is active."""
        return name in self._active

    def clear(self) -> None:
        """Unload and clear all components."""
        for name in list(self._active.keys()):
            self.unload(name)
        self._registered.clear()
        self._lazy.clear()
        self._info.clear()

    @abstractmethod
    def _get_component_type(self) -> str:
        """Return the component type name."""
        ...

    def _do_load(self, name: str, component: T) -> T:
        """
        Perform component-specific loading.

        Override for custom load behavior.
        """
        return component

    def _do_unload(self, name: str, component: T) -> None:
        """
        Perform component-specific unloading.

        Override for custom unload behavior.
        """
        pass


class SimpleRegistry(ComponentRegistry[T]):
    """Simple registry with no special loading behavior."""

    def __init__(self, component_type: str = "component") -> None:
        super().__init__()
        self._component_type = component_type

    def _get_component_type(self) -> str:
        return self._component_type


@dataclass
class ToolDefinition:
    """
    Abstract tool definition.

    Contains metadata about a tool without implementation details.
    """

    name: str
    description: str
    parameters: dict[str, Any] = field(default_factory=dict)
    returns: str = ""
    examples: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    deprecated: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


class ToolRegistryBase(ComponentRegistry[Any]):
    """
    Base registry for tools.

    Extends ComponentRegistry with tool-specific functionality.
    """

    def __init__(self) -> None:
        super().__init__()
        self._definitions: dict[str, ToolDefinition] = {}

    def _get_component_type(self) -> str:
        return "tool"

    def register_with_definition(
        self,
        name: str,
        component: Any,
        definition: ToolDefinition,
    ) -> None:
        """Register a tool with its definition."""
        self._definitions[name] = definition
        info = ComponentInfo(
            name=name,
            type="tool",
            description=definition.description,
            metadata={"tags": definition.tags},
        )
        self.register(name, component, info)

    def get_definition(self, name: str) -> ToolDefinition | None:
        """Get a tool's definition."""
        return self._definitions.get(name)

    def list_definitions(self) -> list[ToolDefinition]:
        """Get all tool definitions."""
        return list(self._definitions.values())

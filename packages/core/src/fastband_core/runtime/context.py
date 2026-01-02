"""
Runtime context and dependency injection.

Provides a context object for passing dependencies through the runtime.
Implements a simple service locator pattern for component access.

This module contains NO framework-specific imports.
"""

from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Generic, TypeVar, cast
from uuid import uuid4


T = TypeVar("T")


@dataclass
class RequestContext:
    """
    Context for a single request/operation.

    Carries request-scoped data like correlation IDs and timing.
    """

    request_id: str = field(default_factory=lambda: str(uuid4()))
    correlation_id: str | None = None
    started_at: datetime = field(default_factory=datetime.utcnow)
    attributes: dict[str, Any] = field(default_factory=dict)
    parent_id: str | None = None

    def child(self) -> "RequestContext":
        """Create a child context for nested operations."""
        return RequestContext(
            correlation_id=self.correlation_id or self.request_id,
            parent_id=self.request_id,
        )

    @property
    def elapsed_ms(self) -> float:
        """Milliseconds since request started."""
        return (datetime.utcnow() - self.started_at).total_seconds() * 1000


@dataclass
class RuntimeConfig:
    """
    Runtime configuration.

    Contains settings that affect runtime behavior.
    """

    project_path: Path = field(default_factory=Path.cwd)
    debug: bool = False
    environment: str = "development"
    instance_id: str = field(default_factory=lambda: str(uuid4())[:8])
    metadata: dict[str, Any] = field(default_factory=dict)


class ServiceRegistry:
    """
    Simple service registry for dependency injection.

    Stores and retrieves services by type or name.

    Example:
        registry = ServiceRegistry()
        registry.register(Logger, my_logger)
        logger = registry.get(Logger)
    """

    def __init__(self) -> None:
        self._services: dict[str, Any] = {}
        self._factories: dict[str, tuple[type, Any]] = {}

    def register(
        self,
        service_type: type[T],
        instance: T,
        name: str | None = None,
    ) -> None:
        """
        Register a service instance.

        Args:
            service_type: The service type/interface.
            instance: The service instance.
            name: Optional name for named services.
        """
        key = self._make_key(service_type, name)
        self._services[key] = instance

    def register_factory(
        self,
        service_type: type[T],
        factory: type[T],
        name: str | None = None,
    ) -> None:
        """
        Register a factory for lazy instantiation.

        Args:
            service_type: The service type/interface.
            factory: Factory class to instantiate.
            name: Optional name for named services.
        """
        key = self._make_key(service_type, name)
        self._factories[key] = (service_type, factory)

    def get(
        self,
        service_type: type[T],
        name: str | None = None,
        default: T | None = None,
    ) -> T | None:
        """
        Get a service by type.

        Args:
            service_type: The service type to retrieve.
            name: Optional name for named services.
            default: Default if not found.

        Returns:
            The service instance or default.
        """
        key = self._make_key(service_type, name)

        # Check for registered instance
        if key in self._services:
            return cast(T, self._services[key])

        # Check for factory
        if key in self._factories:
            _, factory = self._factories[key]
            instance = factory()
            self._services[key] = instance
            return cast(T, instance)

        return default

    def require(
        self,
        service_type: type[T],
        name: str | None = None,
    ) -> T:
        """
        Get a required service.

        Args:
            service_type: The service type to retrieve.
            name: Optional name for named services.

        Returns:
            The service instance.

        Raises:
            KeyError: If service is not registered.
        """
        result = self.get(service_type, name)
        if result is None:
            key = self._make_key(service_type, name)
            raise KeyError(f"Service not found: {key}")
        return result

    def has(
        self,
        service_type: type[T],
        name: str | None = None,
    ) -> bool:
        """Check if a service is registered."""
        key = self._make_key(service_type, name)
        return key in self._services or key in self._factories

    def unregister(
        self,
        service_type: type[T],
        name: str | None = None,
    ) -> bool:
        """
        Unregister a service.

        Returns:
            True if service was removed.
        """
        key = self._make_key(service_type, name)
        removed = False
        if key in self._services:
            del self._services[key]
            removed = True
        if key in self._factories:
            del self._factories[key]
            removed = True
        return removed

    def clear(self) -> None:
        """Clear all registered services."""
        self._services.clear()
        self._factories.clear()

    @staticmethod
    def _make_key(service_type: type, name: str | None) -> str:
        """Create a unique key for a service type/name combo."""
        type_name = f"{service_type.__module__}.{service_type.__qualname__}"
        if name:
            return f"{type_name}:{name}"
        return type_name


class RuntimeContext:
    """
    Main runtime context.

    Provides access to configuration, services, and request context.
    Thread-safe through context variables.

    Example:
        ctx = RuntimeContext(config)
        ctx.services.register(Logger, my_logger)

        with ctx.request() as req:
            logger = ctx.services.require(Logger)
            logger.info("Processing", request_id=req.request_id)
    """

    def __init__(
        self,
        config: RuntimeConfig | None = None,
    ) -> None:
        self._config = config or RuntimeConfig()
        self._services = ServiceRegistry()
        self._request_var: ContextVar[RequestContext | None] = ContextVar(
            "request_context", default=None
        )

    @property
    def config(self) -> RuntimeConfig:
        """Get runtime configuration."""
        return self._config

    @property
    def services(self) -> ServiceRegistry:
        """Get service registry."""
        return self._services

    @property
    def current_request(self) -> RequestContext | None:
        """Get current request context (if any)."""
        return self._request_var.get()

    def request(self) -> "RequestContextManager":
        """
        Create a new request context.

        Usage:
            with ctx.request() as req:
                # req.request_id available
                ...
        """
        return RequestContextManager(self)

    def set_request(self, request: RequestContext) -> None:
        """Set the current request context."""
        self._request_var.set(request)

    def clear_request(self) -> None:
        """Clear the current request context."""
        self._request_var.set(None)


class RequestContextManager:
    """Context manager for request scopes."""

    def __init__(self, runtime: RuntimeContext) -> None:
        self._runtime = runtime
        self._request: RequestContext | None = None
        self._token: Any = None

    def __enter__(self) -> RequestContext:
        self._request = RequestContext()
        self._token = self._runtime._request_var.set(self._request)
        return self._request

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> bool:
        self._runtime._request_var.reset(self._token)
        return False

    async def __aenter__(self) -> RequestContext:
        return self.__enter__()

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> bool:
        return self.__exit__(exc_type, exc_val, exc_tb)


# Global runtime context (optional singleton pattern)
_global_context: RuntimeContext | None = None


def get_runtime_context() -> RuntimeContext:
    """
    Get the global runtime context.

    Creates one if not already initialized.
    """
    global _global_context
    if _global_context is None:
        _global_context = RuntimeContext()
    return _global_context


def set_runtime_context(ctx: RuntimeContext) -> None:
    """Set the global runtime context."""
    global _global_context
    _global_context = ctx


def reset_runtime_context() -> None:
    """Reset the global runtime context."""
    global _global_context
    _global_context = None

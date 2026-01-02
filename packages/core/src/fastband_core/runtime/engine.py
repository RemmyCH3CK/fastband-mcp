"""
Abstract Engine base class.

Defines the lifecycle and core behavior contract for runtime engines.
Concrete implementations provide protocol-specific details (MCP, REST, etc.).

This module contains NO framework-specific imports.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Generic, Protocol, TypeVar, runtime_checkable


class EngineState(Enum):
    """Engine lifecycle states."""

    CREATED = "created"
    INITIALIZING = "initializing"
    READY = "ready"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class EngineConfig:
    """
    Base configuration for engines.

    Concrete implementations extend this with protocol-specific options.
    """

    name: str = "fastband-engine"
    version: str = "0.0.0"
    project_path: Path = field(default_factory=Path.cwd)
    debug: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class EngineInfo:
    """Runtime information about the engine."""

    name: str
    version: str
    state: EngineState
    started_at: datetime | None = None
    uptime_seconds: float = 0.0
    active_tools: int = 0
    total_executions: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


class EngineError(Exception):
    """Base exception for engine errors."""

    def __init__(self, message: str, state: EngineState | None = None):
        super().__init__(message)
        self.message = message
        self.state = state


class EngineStartError(EngineError):
    """Raised when engine fails to start."""

    pass


class EngineStopError(EngineError):
    """Raised when engine fails to stop cleanly."""

    pass


# Type variable for tool result
T = TypeVar("T")


@runtime_checkable
class ToolExecutor(Protocol[T]):
    """
    Protocol for tool execution.

    Defines the contract for executing named operations with parameters.
    """

    async def execute(self, name: str, **kwargs: Any) -> T:
        """
        Execute a tool/operation by name.

        Args:
            name: The tool/operation name.
            **kwargs: Tool parameters.

        Returns:
            The tool result.
        """
        ...

    def list_tools(self) -> list[str]:
        """List available tool names."""
        ...

    def has_tool(self, name: str) -> bool:
        """Check if a tool is available."""
        ...


@runtime_checkable
class ToolProvider(Protocol):
    """
    Protocol for providing tool definitions.

    Used to register tools with an engine.
    """

    @property
    def name(self) -> str:
        """Tool name."""
        ...

    @property
    def description(self) -> str:
        """Tool description."""
        ...

    async def __call__(self, **kwargs: Any) -> Any:
        """Execute the tool."""
        ...


class EngineBase(ABC):
    """
    Abstract base class for runtime engines.

    Provides lifecycle management and common functionality.
    Concrete implementations handle protocol-specific details.

    Lifecycle:
        CREATED -> INITIALIZING -> READY -> RUNNING -> STOPPING -> STOPPED
                                     |                    ^
                                     +--------------------+

    Example:
        class MyEngine(EngineBase):
            async def _do_start(self) -> None:
                # Protocol-specific startup
                ...

            async def _do_stop(self) -> None:
                # Protocol-specific shutdown
                ...
    """

    def __init__(self, config: EngineConfig | None = None):
        self._config = config or EngineConfig()
        self._state = EngineState.CREATED
        self._started_at: datetime | None = None
        self._execution_count = 0
        self._error: Exception | None = None

    @property
    def config(self) -> EngineConfig:
        """Get engine configuration."""
        return self._config

    @property
    def state(self) -> EngineState:
        """Get current engine state."""
        return self._state

    @property
    def is_running(self) -> bool:
        """Check if engine is running."""
        return self._state == EngineState.RUNNING

    @property
    def is_ready(self) -> bool:
        """Check if engine is ready (initialized but not yet running)."""
        return self._state == EngineState.READY

    def get_info(self) -> EngineInfo:
        """Get runtime information about the engine."""
        uptime = 0.0
        if self._started_at:
            uptime = (datetime.utcnow() - self._started_at).total_seconds()

        return EngineInfo(
            name=self._config.name,
            version=self._config.version,
            state=self._state,
            started_at=self._started_at,
            uptime_seconds=uptime,
            active_tools=self._get_active_tool_count(),
            total_executions=self._execution_count,
        )

    def _get_active_tool_count(self) -> int:
        """Override in subclass to return active tool count."""
        return 0

    async def initialize(self) -> None:
        """
        Initialize the engine.

        Called before start() to set up resources.
        """
        if self._state != EngineState.CREATED:
            raise EngineError(
                f"Cannot initialize from state {self._state}",
                self._state,
            )

        self._state = EngineState.INITIALIZING
        try:
            await self._do_initialize()
            self._state = EngineState.READY
        except Exception as e:
            self._state = EngineState.ERROR
            self._error = e
            raise EngineStartError(f"Initialization failed: {e}", self._state) from e

    async def start(self) -> None:
        """
        Start the engine.

        Initializes if needed, then starts the main loop.
        """
        if self._state == EngineState.CREATED:
            await self.initialize()

        if self._state != EngineState.READY:
            raise EngineStartError(
                f"Cannot start from state {self._state}",
                self._state,
            )

        self._started_at = datetime.utcnow()
        self._state = EngineState.RUNNING

        try:
            await self._do_start()
        except Exception as e:
            self._state = EngineState.ERROR
            self._error = e
            raise EngineStartError(f"Start failed: {e}", self._state) from e

    async def stop(self) -> None:
        """
        Stop the engine.

        Gracefully shuts down resources.
        """
        if self._state not in (EngineState.RUNNING, EngineState.READY):
            return  # Already stopped or never started

        self._state = EngineState.STOPPING

        try:
            await self._do_stop()
            self._state = EngineState.STOPPED
        except Exception as e:
            self._state = EngineState.ERROR
            self._error = e
            raise EngineStopError(f"Stop failed: {e}", self._state) from e

    def record_execution(self) -> None:
        """Record a tool execution for metrics."""
        self._execution_count += 1

    @abstractmethod
    async def _do_initialize(self) -> None:
        """
        Perform initialization.

        Override to set up protocol-specific resources.
        """
        ...

    @abstractmethod
    async def _do_start(self) -> None:
        """
        Perform startup.

        Override to start the protocol-specific server/loop.
        """
        ...

    @abstractmethod
    async def _do_stop(self) -> None:
        """
        Perform shutdown.

        Override to clean up protocol-specific resources.
        """
        ...

    async def __aenter__(self) -> "EngineBase":
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> bool:
        """Async context manager exit."""
        await self.stop()
        return False


# Lifecycle hooks
LifecycleHook = Callable[["EngineBase"], Any]


class LifecycleManager:
    """
    Manages lifecycle hooks for engines.

    Allows registering callbacks for lifecycle events.
    """

    def __init__(self) -> None:
        self._on_initialize: list[LifecycleHook] = []
        self._on_start: list[LifecycleHook] = []
        self._on_stop: list[LifecycleHook] = []
        self._on_error: list[Callable[["EngineBase", Exception], Any]] = []

    def on_initialize(self, hook: LifecycleHook) -> LifecycleHook:
        """Register initialization hook (decorator)."""
        self._on_initialize.append(hook)
        return hook

    def on_start(self, hook: LifecycleHook) -> LifecycleHook:
        """Register start hook (decorator)."""
        self._on_start.append(hook)
        return hook

    def on_stop(self, hook: LifecycleHook) -> LifecycleHook:
        """Register stop hook (decorator)."""
        self._on_stop.append(hook)
        return hook

    def on_error(
        self, hook: Callable[["EngineBase", Exception], Any]
    ) -> Callable[["EngineBase", Exception], Any]:
        """Register error hook (decorator)."""
        self._on_error.append(hook)
        return hook

    async def run_initialize_hooks(self, engine: "EngineBase") -> None:
        """Run all initialization hooks."""
        for hook in self._on_initialize:
            await self._run_hook(hook, engine)

    async def run_start_hooks(self, engine: "EngineBase") -> None:
        """Run all start hooks."""
        for hook in self._on_start:
            await self._run_hook(hook, engine)

    async def run_stop_hooks(self, engine: "EngineBase") -> None:
        """Run all stop hooks."""
        for hook in self._on_stop:
            await self._run_hook(hook, engine)

    async def run_error_hooks(self, engine: "EngineBase", error: Exception) -> None:
        """Run all error hooks."""
        for hook in self._on_error:
            try:
                result = hook(engine, error)
                if hasattr(result, "__await__"):
                    await result
            except Exception:
                pass  # Don't let error hooks cause more errors

    @staticmethod
    async def _run_hook(hook: LifecycleHook, engine: "EngineBase") -> None:
        """Run a single hook, handling async/sync."""
        result = hook(engine)
        if hasattr(result, "__await__"):
            await result

"""
Fastband - Circuit Breaker for AI Providers.

Implements the circuit breaker pattern to prevent cascading failures
when AI providers are unavailable or experiencing issues.

Features:
- Three states: CLOSED (normal), OPEN (failing), HALF_OPEN (testing)
- Configurable failure thresholds and recovery timeouts
- Per-provider circuit tracking
- Async support for provider calls
- Fallback mechanism support
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps
from typing import Any, Callable, TypeVar

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


# =============================================================================
# CIRCUIT STATES
# =============================================================================


class CircuitState(str, Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation, requests allowed
    OPEN = "open"  # Failing, requests blocked
    HALF_OPEN = "half_open"  # Testing if service recovered


# =============================================================================
# CONFIGURATION
# =============================================================================


@dataclass(slots=True)
class CircuitBreakerConfig:
    """Circuit breaker configuration.

    Attributes:
        failure_threshold: Number of failures before opening circuit
        success_threshold: Successes needed to close circuit from half-open
        timeout: Seconds to wait before trying half-open
        half_open_max_calls: Max concurrent calls in half-open state
        excluded_exceptions: Exceptions that don't count as failures
        name: Circuit breaker name for logging
    """

    failure_threshold: int = 5
    success_threshold: int = 2
    timeout: float = 60.0  # seconds
    half_open_max_calls: int = 3
    excluded_exceptions: tuple[type[Exception], ...] = ()
    name: str = "circuit"


# =============================================================================
# CIRCUIT BREAKER
# =============================================================================


class CircuitBreakerError(Exception):
    """Raised when circuit breaker is open."""

    def __init__(self, circuit_name: str, remaining_time: float):
        self.circuit_name = circuit_name
        self.remaining_time = remaining_time
        super().__init__(
            f"Circuit breaker '{circuit_name}' is open. "
            f"Retry after {remaining_time:.1f} seconds."
        )


@dataclass
class CircuitBreakerState:
    """Circuit breaker state tracking."""

    state: CircuitState = CircuitState.CLOSED
    failures: int = 0
    successes: int = 0
    last_failure_time: float = 0.0
    half_open_calls: int = 0


class CircuitBreaker:
    """Circuit breaker for resilient AI provider calls.

    Example:
        breaker = CircuitBreaker(config=CircuitBreakerConfig(
            failure_threshold=3,
            timeout=30.0,
            name="claude"
        ))

        @breaker
        async def call_claude(prompt: str):
            return await claude_provider.complete(prompt)

        # With fallback
        @breaker.with_fallback(lambda: "Fallback response")
        async def call_claude_safe(prompt: str):
            return await claude_provider.complete(prompt)
    """

    def __init__(self, config: CircuitBreakerConfig | None = None):
        """Initialize circuit breaker.

        Args:
            config: Circuit breaker configuration
        """
        self.config = config or CircuitBreakerConfig()
        self._state = CircuitBreakerState()
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        """Get current circuit state."""
        return self._state.state

    @property
    def is_open(self) -> bool:
        """Check if circuit is open (blocking requests)."""
        return self._state.state == CircuitState.OPEN

    @property
    def is_closed(self) -> bool:
        """Check if circuit is closed (normal operation)."""
        return self._state.state == CircuitState.CLOSED

    def get_remaining_timeout(self) -> float:
        """Get remaining time until circuit can try half-open."""
        if self._state.state != CircuitState.OPEN:
            return 0.0
        elapsed = time.monotonic() - self._state.last_failure_time
        remaining = self.config.timeout - elapsed
        return max(0.0, remaining)

    async def _should_allow_request(self) -> bool:
        """Check if request should be allowed."""
        async with self._lock:
            if self._state.state == CircuitState.CLOSED:
                return True

            if self._state.state == CircuitState.OPEN:
                # Check if timeout has passed
                elapsed = time.monotonic() - self._state.last_failure_time
                if elapsed >= self.config.timeout:
                    logger.info(
                        f"Circuit '{self.config.name}' transitioning to half-open"
                    )
                    self._state.state = CircuitState.HALF_OPEN
                    self._state.half_open_calls = 0
                    self._state.successes = 0
                    return True
                return False

            if self._state.state == CircuitState.HALF_OPEN:
                # Allow limited calls in half-open
                if self._state.half_open_calls < self.config.half_open_max_calls:
                    self._state.half_open_calls += 1
                    return True
                return False

            return False

    async def _record_success(self) -> None:
        """Record a successful call."""
        async with self._lock:
            if self._state.state == CircuitState.HALF_OPEN:
                self._state.successes += 1
                if self._state.successes >= self.config.success_threshold:
                    logger.info(
                        f"Circuit '{self.config.name}' closing after "
                        f"{self._state.successes} successes"
                    )
                    self._state.state = CircuitState.CLOSED
                    self._state.failures = 0
                    self._state.successes = 0
            elif self._state.state == CircuitState.CLOSED:
                # Reset failure count on success
                self._state.failures = 0

    async def _record_failure(self, exception: Exception) -> None:
        """Record a failed call."""
        # Check if exception is excluded
        if isinstance(exception, self.config.excluded_exceptions):
            return

        async with self._lock:
            self._state.failures += 1
            self._state.last_failure_time = time.monotonic()

            if self._state.state == CircuitState.HALF_OPEN:
                # Any failure in half-open reopens the circuit
                logger.warning(
                    f"Circuit '{self.config.name}' reopening due to failure: {exception}"
                )
                self._state.state = CircuitState.OPEN
            elif self._state.state == CircuitState.CLOSED:
                if self._state.failures >= self.config.failure_threshold:
                    logger.warning(
                        f"Circuit '{self.config.name}' opening after "
                        f"{self._state.failures} failures"
                    )
                    self._state.state = CircuitState.OPEN

    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute a function through the circuit breaker.

        Args:
            func: Function to call
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Function result

        Raises:
            CircuitBreakerError: If circuit is open
        """
        if not await self._should_allow_request():
            raise CircuitBreakerError(
                self.config.name,
                self.get_remaining_timeout()
            )

        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            await self._record_success()
            return result
        except Exception as e:
            await self._record_failure(e)
            raise

    def __call__(self, func: F) -> F:
        """Decorator to wrap a function with circuit breaker.

        Example:
            @circuit_breaker
            async def call_provider():
                pass
        """

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            return await self.call(func, *args, **kwargs)

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            import asyncio

            if asyncio.get_event_loop().is_running():
                raise RuntimeError("Use async version in async context")
            return asyncio.run(self.call(func, *args, **kwargs))

        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        return sync_wrapper  # type: ignore

    def with_fallback(
        self, fallback: Callable[..., Any]
    ) -> Callable[[F], F]:
        """Decorator with fallback when circuit is open.

        Args:
            fallback: Fallback function to call

        Example:
            @circuit_breaker.with_fallback(lambda: "fallback")
            async def call_provider():
                pass
        """

        def decorator(func: F) -> F:
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                try:
                    return await self.call(func, *args, **kwargs)
                except CircuitBreakerError:
                    logger.warning(
                        f"Circuit '{self.config.name}' open, using fallback"
                    )
                    if asyncio.iscoroutinefunction(fallback):
                        return await fallback(*args, **kwargs)
                    return fallback(*args, **kwargs)

            return async_wrapper  # type: ignore

        return decorator

    def reset(self) -> None:
        """Reset circuit breaker to closed state."""
        self._state = CircuitBreakerState()
        logger.info(f"Circuit '{self.config.name}' reset to closed")

    def force_open(self) -> None:
        """Force circuit to open state (for testing/maintenance)."""
        self._state.state = CircuitState.OPEN
        self._state.last_failure_time = time.monotonic()
        logger.info(f"Circuit '{self.config.name}' forced open")

    def get_stats(self) -> dict[str, Any]:
        """Get circuit breaker statistics."""
        return {
            "name": self.config.name,
            "state": self._state.state.value,
            "failures": self._state.failures,
            "successes": self._state.successes,
            "half_open_calls": self._state.half_open_calls,
            "remaining_timeout": self.get_remaining_timeout(),
            "config": {
                "failure_threshold": self.config.failure_threshold,
                "success_threshold": self.config.success_threshold,
                "timeout": self.config.timeout,
            },
        }


# =============================================================================
# CIRCUIT BREAKER REGISTRY
# =============================================================================


class CircuitBreakerRegistry:
    """Registry for managing multiple circuit breakers.

    Example:
        registry = CircuitBreakerRegistry()

        # Get or create circuit breaker for provider
        breaker = registry.get("claude")

        @breaker
        async def call_claude():
            pass
    """

    def __init__(self, default_config: CircuitBreakerConfig | None = None):
        """Initialize registry.

        Args:
            default_config: Default config for new circuit breakers
        """
        self.default_config = default_config or CircuitBreakerConfig()
        self._breakers: dict[str, CircuitBreaker] = {}
        self._lock = asyncio.Lock()

    def get(
        self,
        name: str,
        config: CircuitBreakerConfig | None = None
    ) -> CircuitBreaker:
        """Get or create a circuit breaker.

        Args:
            name: Circuit breaker name
            config: Optional custom config

        Returns:
            CircuitBreaker instance
        """
        if name not in self._breakers:
            cfg = config or CircuitBreakerConfig(
                failure_threshold=self.default_config.failure_threshold,
                success_threshold=self.default_config.success_threshold,
                timeout=self.default_config.timeout,
                name=name,
            )
            self._breakers[name] = CircuitBreaker(cfg)
        return self._breakers[name]

    def get_all_stats(self) -> dict[str, dict[str, Any]]:
        """Get stats for all circuit breakers."""
        return {name: breaker.get_stats() for name, breaker in self._breakers.items()}

    def reset_all(self) -> None:
        """Reset all circuit breakers."""
        for breaker in self._breakers.values():
            breaker.reset()

    def get_open_circuits(self) -> list[str]:
        """Get names of all open circuits."""
        return [name for name, breaker in self._breakers.items() if breaker.is_open]


# =============================================================================
# GLOBAL REGISTRY
# =============================================================================

_registry: CircuitBreakerRegistry | None = None


def get_circuit_breaker_registry() -> CircuitBreakerRegistry:
    """Get the global circuit breaker registry."""
    global _registry
    if _registry is None:
        _registry = CircuitBreakerRegistry(
            default_config=CircuitBreakerConfig(
                failure_threshold=5,
                success_threshold=2,
                timeout=60.0,
            )
        )
    return _registry


def get_circuit_breaker(name: str) -> CircuitBreaker:
    """Get a circuit breaker by name from the global registry.

    Args:
        name: Circuit breaker name (e.g., provider name)

    Returns:
        CircuitBreaker instance
    """
    return get_circuit_breaker_registry().get(name)


# =============================================================================
# CONVENIENCE DECORATORS
# =============================================================================


def with_circuit_breaker(name: str) -> Callable[[F], F]:
    """Decorator to wrap a function with a named circuit breaker.

    Example:
        @with_circuit_breaker("claude")
        async def call_claude():
            pass
    """

    def decorator(func: F) -> F:
        breaker = get_circuit_breaker(name)
        return breaker(func)

    return decorator


def with_circuit_breaker_fallback(
    name: str,
    fallback: Callable[..., Any]
) -> Callable[[F], F]:
    """Decorator with circuit breaker and fallback.

    Example:
        @with_circuit_breaker_fallback("claude", fallback=lambda: "default")
        async def call_claude():
            pass
    """

    def decorator(func: F) -> F:
        breaker = get_circuit_breaker(name)
        return breaker.with_fallback(fallback)(func)

    return decorator

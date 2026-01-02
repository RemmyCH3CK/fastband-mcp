"""AI Provider implementations."""

from fastband.providers.base import AIProvider, Capability, CompletionResponse, ProviderConfig
from fastband.providers.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerError,
    CircuitBreakerRegistry,
    CircuitState,
    get_circuit_breaker,
    get_circuit_breaker_registry,
    with_circuit_breaker,
    with_circuit_breaker_fallback,
)
from fastband.providers.registry import ProviderRegistry, get_provider

__all__ = [
    # Base provider
    "AIProvider",
    "Capability",
    "ProviderConfig",
    "CompletionResponse",
    "ProviderRegistry",
    "get_provider",
    # Circuit breaker
    "CircuitBreaker",
    "CircuitBreakerConfig",
    "CircuitBreakerError",
    "CircuitBreakerRegistry",
    "CircuitState",
    "get_circuit_breaker",
    "get_circuit_breaker_registry",
    "with_circuit_breaker",
    "with_circuit_breaker_fallback",
]

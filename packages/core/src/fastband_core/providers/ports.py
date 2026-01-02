"""
Provider port interfaces.

Abstract interfaces that all AI providers must implement. These define
the contract between the core system and provider implementations.

Architecture Rules:
- No side effects on import
- No external SDK imports
- No framework imports (FastAPI, Flask)
- Pure interface definitions only
"""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Sequence
from typing import Any, Protocol, runtime_checkable

from fastband_core.providers.capabilities import Capability, CapabilitySet, ModelInfo
from fastband_core.providers.model import (
    CompletionResponse,
    EmbeddingConfig,
    EmbeddingResult,
    ProviderConfig,
    ProviderHealth,
)


# =============================================================================
# COMPLETION PROVIDER
# =============================================================================


class CompletionProvider(ABC):
    """
    Abstract base class for AI completion providers.

    All completion providers (Claude, OpenAI, Gemini, etc.) must implement
    this interface for consistent behavior across the platform.
    """

    def __init__(self, config: ProviderConfig):
        """Initialize with configuration."""
        self.config = config
        self._validate_config()

    @abstractmethod
    def _validate_config(self) -> None:
        """
        Validate provider-specific configuration.

        Raises:
            ValueError: If configuration is invalid.
        """
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Return provider name (claude, openai, gemini, etc.)."""
        ...

    @property
    @abstractmethod
    def capabilities(self) -> CapabilitySet:
        """Return the provider's capabilities."""
        ...

    @abstractmethod
    async def complete(
        self,
        prompt: str,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> CompletionResponse:
        """
        Send a completion request to the AI.

        Args:
            prompt: The user prompt.
            system_prompt: Optional system prompt.
            **kwargs: Additional provider-specific parameters.

        Returns:
            CompletionResponse with the completion result.

        Raises:
            ProviderError: If the request fails.
        """
        ...

    @abstractmethod
    async def complete_with_tools(
        self,
        prompt: str,
        tools: list[dict[str, Any]],
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> CompletionResponse:
        """
        Complete with tool/function calling support.

        Args:
            prompt: The user prompt.
            tools: List of tool definitions.
            system_prompt: Optional system prompt.
            **kwargs: Additional provider-specific parameters.

        Returns:
            CompletionResponse, potentially with tool calls.

        Raises:
            ProviderError: If the request fails.
        """
        ...

    @abstractmethod
    async def stream(
        self,
        prompt: str,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """
        Stream completion response.

        Args:
            prompt: The user prompt.
            system_prompt: Optional system prompt.
            **kwargs: Additional provider-specific parameters.

        Yields:
            String chunks of the completion.

        Raises:
            ProviderError: If the request fails.
        """
        ...

    async def analyze_image(
        self,
        image_data: bytes,
        prompt: str,
        **kwargs: Any,
    ) -> CompletionResponse:
        """
        Analyze an image (vision capability).

        Args:
            image_data: Raw image bytes.
            prompt: Analysis prompt.
            **kwargs: Additional parameters.

        Returns:
            CompletionResponse with analysis.

        Raises:
            NotImplementedError: If vision not supported.
        """
        raise NotImplementedError("Vision not supported by this provider")

    def supports(self, capability: Capability) -> bool:
        """Check if provider supports a capability."""
        return self.capabilities.supports(capability)

    def get_recommended_model(self, task: str) -> str:
        """
        Get recommended model for a specific task type.

        Args:
            task: Task identifier (e.g., "coding", "analysis").

        Returns:
            Model identifier string.
        """
        return self.config.model or ""


# =============================================================================
# EMBEDDING PROVIDER
# =============================================================================


class EmbeddingProvider(ABC):
    """
    Abstract base class for embedding providers.

    All embedding providers (OpenAI, Gemini, Ollama) implement this interface
    for consistent embedding generation across the platform.
    """

    def __init__(self, config: EmbeddingConfig):
        """Initialize with configuration."""
        self.config = config
        self._validate_config()

    @abstractmethod
    def _validate_config(self) -> None:
        """
        Validate provider-specific configuration.

        Raises:
            ValueError: If configuration is invalid.
        """
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Return provider name (openai, gemini, ollama)."""
        ...

    @property
    @abstractmethod
    def default_model(self) -> str:
        """Return the default embedding model for this provider."""
        ...

    @property
    @abstractmethod
    def dimensions(self) -> int:
        """Return the embedding dimensions for the current model."""
        ...

    @abstractmethod
    async def embed(self, texts: Sequence[str]) -> EmbeddingResult:
        """
        Generate embeddings for a list of texts.

        Args:
            texts: List of text strings to embed.

        Returns:
            EmbeddingResult with embedding vectors and metadata.

        Note:
            Implementations should handle batching internally if the
            provider has limits on texts per request.
        """
        ...

    async def embed_single(self, text: str) -> tuple[float, ...]:
        """
        Embed a single text string.

        Convenience method that wraps embed() for single texts.

        Args:
            text: Text string to embed.

        Returns:
            Single embedding vector as tuple.
        """
        result = await self.embed([text])
        return result.embeddings[0] if result.embeddings else ()


# =============================================================================
# PROVIDER REGISTRY
# =============================================================================


@runtime_checkable
class ProviderRegistry(Protocol):
    """
    Protocol for provider registries.

    Defines the interface for registering and retrieving providers.
    """

    def register(self, name: str, provider_class: type) -> None:
        """
        Register a provider class.

        Args:
            name: Provider name (will be lowercased).
            provider_class: The provider class to register.
        """
        ...

    def get(
        self, name: str, config: ProviderConfig | EmbeddingConfig | None = None
    ) -> CompletionProvider | EmbeddingProvider:
        """
        Get or create a provider instance.

        Args:
            name: Provider name.
            config: Optional configuration.

        Returns:
            Provider instance.

        Raises:
            ValueError: If provider not found.
        """
        ...

    def available_providers(self) -> list[str]:
        """
        List all registered providers.

        Returns:
            List of provider names.
        """
        ...

    def is_registered(self, name: str) -> bool:
        """
        Check if a provider is registered.

        Args:
            name: Provider name.

        Returns:
            True if registered.
        """
        ...


# =============================================================================
# PROVIDER HEALTH CHECK
# =============================================================================


@runtime_checkable
class HealthCheckable(Protocol):
    """
    Protocol for providers that support health checks.

    Providers implementing this can report their health status.
    """

    async def health_check(self) -> ProviderHealth:
        """
        Perform a health check.

        Returns:
            ProviderHealth with current status.
        """
        ...


# =============================================================================
# MODEL CATALOG
# =============================================================================


@runtime_checkable
class ModelCatalog(Protocol):
    """
    Protocol for model catalogs.

    Provides access to available models and their capabilities.
    """

    def list_models(self, provider: str | None = None) -> list[ModelInfo]:
        """
        List available models.

        Args:
            provider: Optional filter by provider.

        Returns:
            List of model information.
        """
        ...

    def get_model(self, model_id: str) -> ModelInfo | None:
        """
        Get information about a specific model.

        Args:
            model_id: Model identifier.

        Returns:
            ModelInfo or None if not found.
        """
        ...

    def find_models(
        self,
        *capabilities: Capability,
        provider: str | None = None,
    ) -> list[ModelInfo]:
        """
        Find models with specific capabilities.

        Args:
            *capabilities: Required capabilities.
            provider: Optional provider filter.

        Returns:
            List of matching models.
        """
        ...


# =============================================================================
# PROVIDER FACTORY
# =============================================================================


class ProviderFactory(ABC):
    """
    Abstract factory for creating provider instances.

    Allows for custom provider instantiation logic.
    """

    @abstractmethod
    def create_completion_provider(
        self,
        name: str,
        config: ProviderConfig,
    ) -> CompletionProvider:
        """
        Create a completion provider.

        Args:
            name: Provider name.
            config: Provider configuration.

        Returns:
            CompletionProvider instance.
        """
        ...

    @abstractmethod
    def create_embedding_provider(
        self,
        name: str,
        config: EmbeddingConfig,
    ) -> EmbeddingProvider:
        """
        Create an embedding provider.

        Args:
            name: Provider name.
            config: Provider configuration.

        Returns:
            EmbeddingProvider instance.
        """
        ...


# =============================================================================
# CIRCUIT BREAKER (RESILIENCE)
# =============================================================================


class CircuitBreakerState:
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation, requests allowed
    OPEN = "open"  # Failing, requests blocked
    HALF_OPEN = "half_open"  # Testing if service recovered


@runtime_checkable
class CircuitBreaker(Protocol):
    """
    Protocol for circuit breakers.

    Implements the circuit breaker pattern for resilient provider calls.
    """

    @property
    def state(self) -> str:
        """Get current circuit state."""
        ...

    @property
    def is_open(self) -> bool:
        """Check if circuit is open (blocking requests)."""
        ...

    @property
    def is_closed(self) -> bool:
        """Check if circuit is closed (normal operation)."""
        ...

    async def call(self, func: Any, *args: Any, **kwargs: Any) -> Any:
        """
        Execute a function through the circuit breaker.

        Args:
            func: Function to call.
            *args: Positional arguments.
            **kwargs: Keyword arguments.

        Returns:
            Function result.

        Raises:
            CircuitBreakerError: If circuit is open.
        """
        ...

    def reset(self) -> None:
        """Reset circuit breaker to closed state."""
        ...

    def force_open(self) -> None:
        """Force circuit to open state."""
        ...

    def get_stats(self) -> dict[str, Any]:
        """Get circuit breaker statistics."""
        ...


# =============================================================================
# RATE LIMITER
# =============================================================================


@runtime_checkable
class ProviderRateLimiter(Protocol):
    """
    Protocol for provider-specific rate limiting.

    Tracks and enforces rate limits for provider API calls.
    """

    async def acquire(self, tokens: int = 1) -> bool:
        """
        Acquire rate limit tokens.

        Args:
            tokens: Number of tokens to acquire.

        Returns:
            True if acquired, False if rate limited.
        """
        ...

    async def wait(self, tokens: int = 1) -> None:
        """
        Wait until tokens are available.

        Args:
            tokens: Number of tokens needed.
        """
        ...

    def get_remaining(self) -> int:
        """
        Get remaining tokens in current window.

        Returns:
            Number of remaining tokens.
        """
        ...

    def get_reset_time(self) -> float:
        """
        Get time until rate limit resets.

        Returns:
            Seconds until reset.
        """
        ...

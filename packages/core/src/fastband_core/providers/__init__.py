"""
Fastband Core Providers - Provider abstraction layer.

This module provides pure abstractions for AI provider interactions.
These abstractions are shared between Fastband Dev and Fastband Enterprise,
enabling consistent provider handling across products.

Architecture Rules:
- No side effects on import
- No external SDK imports (anthropic, openai, google, etc.)
- No framework imports (FastAPI, Flask)
- No database driver imports
- No environment file loading

Usage:
    from fastband_core.providers import (
        # Ports (interfaces)
        CompletionProvider,
        EmbeddingProvider,
        ProviderRegistry,
        HealthCheckable,

        # Domain models
        ProviderConfig,
        CompletionResponse,
        EmbeddingResult,
        ProviderHealth,

        # Capabilities
        Capability,
        CapabilitySet,
        ModelInfo,
    )
"""

# Domain models
from fastband_core.providers.model import (
    CompletionResponse,
    EmbeddingConfig,
    EmbeddingResult,
    FinishReason,
    ProviderConfig,
    ProviderCredentials,
    ProviderError,
    ProviderErrorType,
    ProviderHealth,
    ProviderStatus,
    ProviderType,
    TokenUsage,
    ToolCall,
)

# Capabilities
from fastband_core.providers.capabilities import (
    Capability,
    CapabilityInfo,
    CapabilityLevel,
    CapabilityRequirements,
    CapabilitySet,
    ModelInfo,
)

# Ports (interfaces)
from fastband_core.providers.ports import (
    CircuitBreaker,
    CircuitBreakerState,
    CompletionProvider,
    EmbeddingProvider,
    HealthCheckable,
    ModelCatalog,
    ProviderFactory,
    ProviderRateLimiter,
    ProviderRegistry,
)

__all__ = [
    # Domain models
    "ProviderType",
    "ProviderStatus",
    "ProviderCredentials",
    "ProviderConfig",
    "TokenUsage",
    "FinishReason",
    "ToolCall",
    "CompletionResponse",
    "EmbeddingConfig",
    "EmbeddingResult",
    "ProviderHealth",
    "ProviderErrorType",
    "ProviderError",
    # Capabilities
    "Capability",
    "CapabilityLevel",
    "CapabilityInfo",
    "CapabilitySet",
    "ModelInfo",
    "CapabilityRequirements",
    # Ports (interfaces)
    "CompletionProvider",
    "EmbeddingProvider",
    "ProviderRegistry",
    "HealthCheckable",
    "ModelCatalog",
    "ProviderFactory",
    "CircuitBreakerState",
    "CircuitBreaker",
    "ProviderRateLimiter",
]

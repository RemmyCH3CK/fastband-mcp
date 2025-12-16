"""
AI Provider Registry.

Manages registration and instantiation of AI providers.
"""

from typing import Dict, Type, Optional, List
import os

from fastband.providers.base import AIProvider, ProviderConfig


class ProviderRegistry:
    """Registry for AI providers with lazy loading."""

    _providers: Dict[str, Type[AIProvider]] = {}
    _instances: Dict[str, AIProvider] = {}

    @classmethod
    def register(cls, name: str, provider_class: Type[AIProvider]) -> None:
        """Register a provider class."""
        cls._providers[name.lower()] = provider_class

    @classmethod
    def get(cls, name: str, config: Optional[ProviderConfig] = None) -> AIProvider:
        """
        Get or create a provider instance.

        Args:
            name: Provider name (claude, openai, gemini, ollama)
            config: Optional configuration (uses env vars if not provided)
        """
        name = name.lower()

        # Return cached instance if exists and no new config
        if name in cls._instances and config is None:
            return cls._instances[name]

        if name not in cls._providers:
            raise ValueError(
                f"Unknown provider: {name}. "
                f"Available: {list(cls._providers.keys())}"
            )

        # Create configuration from environment if not provided
        if config is None:
            config = cls._config_from_env(name)

        instance = cls._providers[name](config)
        cls._instances[name] = instance
        return instance

    @classmethod
    def _config_from_env(cls, name: str) -> ProviderConfig:
        """Create config from environment variables."""
        env_mappings = {
            "claude": ("ANTHROPIC_API_KEY", "claude-sonnet-4-20250514"),
            "openai": ("OPENAI_API_KEY", "gpt-4-turbo"),
            "gemini": ("GOOGLE_API_KEY", "gemini-pro"),
            "ollama": (None, "llama2"),
        }

        api_key_env, default_model = env_mappings.get(name, (None, None))

        return ProviderConfig(
            name=name,
            api_key=os.getenv(api_key_env) if api_key_env else None,
            model=os.getenv(f"{name.upper()}_MODEL", default_model),
        )

    @classmethod
    def available_providers(cls) -> List[str]:
        """List registered providers."""
        return list(cls._providers.keys())

    @classmethod
    def is_registered(cls, name: str) -> bool:
        """Check if provider is registered."""
        return name.lower() in cls._providers


def get_provider(name: Optional[str] = None) -> AIProvider:
    """
    Get the configured AI provider.

    If name is not specified, uses FASTBAND_AI_PROVIDER env var,
    defaulting to 'claude'.
    """
    if name is None:
        name = os.getenv("FASTBAND_AI_PROVIDER", "claude")
    return ProviderRegistry.get(name)

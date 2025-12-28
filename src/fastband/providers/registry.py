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


def _register_builtin_providers():
    """Register all built-in providers (lazy imports)."""
    # These are registered but not imported until used
    _provider_classes = {
        "claude": ("fastband.providers.claude", "ClaudeProvider"),
        "openai": ("fastband.providers.openai", "OpenAIProvider"),
        "gemini": ("fastband.providers.gemini", "GeminiProvider"),
        "ollama": ("fastband.providers.ollama", "OllamaProvider"),
    }

    for name, (module_path, class_name) in _provider_classes.items():
        # Create a lazy loader
        def make_loader(mod_path: str, cls_name: str):
            def loader(config: ProviderConfig) -> AIProvider:
                import importlib
                module = importlib.import_module(mod_path)
                provider_class = getattr(module, cls_name)
                return provider_class(config)
            return loader

        # Store the loader for lazy instantiation
        ProviderRegistry._provider_loaders = getattr(ProviderRegistry, '_provider_loaders', {})
        ProviderRegistry._provider_loaders[name] = make_loader(module_path, class_name)


# Update ProviderRegistry.get to use lazy loading
_original_get = ProviderRegistry.get


@classmethod
def _lazy_get(cls, name: str, config: Optional[ProviderConfig] = None) -> AIProvider:
    """Get or create a provider instance with lazy loading."""
    name = name.lower()

    # Return cached instance if exists and no new config
    if name in cls._instances and config is None:
        return cls._instances[name]

    # Check for lazy loader
    loaders = getattr(cls, '_provider_loaders', {})
    if name in loaders:
        if config is None:
            config = cls._config_from_env(name)
        instance = loaders[name](config)
        cls._instances[name] = instance
        return instance

    # Fall back to registered classes
    if name in cls._providers:
        if config is None:
            config = cls._config_from_env(name)
        instance = cls._providers[name](config)
        cls._instances[name] = instance
        return instance

    available = list(cls._providers.keys()) + list(loaders.keys())
    raise ValueError(f"Unknown provider: {name}. Available: {available}")


ProviderRegistry.get = _lazy_get

# Register providers on module load
_register_builtin_providers()

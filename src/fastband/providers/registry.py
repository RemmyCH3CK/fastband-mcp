"""
AI Provider Registry.

Manages registration and instantiation of AI providers.

Performance Optimizations (Issue #38):
- Lazy loading: Provider modules are only imported when first accessed
- Instance caching: Provider instances are reused across calls
- Fast path: Cached instance lookup is O(1)
"""

import importlib
import logging
import os
import time
from dataclasses import dataclass

from fastband.providers.base import AIProvider, ProviderConfig

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class LazyProviderSpec:
    """
    Specification for a lazily-loaded provider.

    Stores the module path and class name instead of importing immediately.
    The provider class is only imported when get_class() is called.
    """

    module_path: str
    class_name: str
    _class: type[AIProvider] | None = None
    _load_time_ms: float = 0.0

    def get_class(self) -> type[AIProvider]:
        """
        Get the provider class, importing the module if needed.

        This is where lazy loading happens - the module is only
        imported when this method is first called.
        """
        if self._class is None:
            start = time.perf_counter()
            module = importlib.import_module(self.module_path)
            self._class = getattr(module, self.class_name)
            self._load_time_ms = (time.perf_counter() - start) * 1000
            logger.debug(
                f"Lazy-loaded provider {self.class_name} from {self.module_path} "
                f"in {self._load_time_ms:.2f}ms"
            )
        return self._class

    @property
    def is_loaded(self) -> bool:
        """Check if the provider class has been imported."""
        return self._class is not None


class ProviderRegistry:
    """
    Registry for AI providers with lazy loading.

    Features:
    - Lazy loading: Provider modules are only imported when first used
    - Instance caching: Provider instances are reused for efficiency
    - Environment-based configuration: Auto-configures from env vars

    Example:
        # Get default provider (uses FASTBAND_AI_PROVIDER or 'claude')
        provider = ProviderRegistry.get("claude")

        # Get with custom config
        config = ProviderConfig(name="openai", api_key="...", model="gpt-4")
        provider = ProviderRegistry.get("openai", config)
    """

    # Class-level storage for providers
    _providers: dict[str, type[AIProvider]] = {}
    _lazy_specs: dict[str, LazyProviderSpec] = {}
    _instances: dict[str, AIProvider] = {}
    _env_cache: dict[str, ProviderConfig] = {}  # Cache env-based configs

    @classmethod
    def register(cls, name: str, provider_class: type[AIProvider]) -> None:
        """
        Register a provider class (eager registration).

        Args:
            name: Provider name (will be lowercased)
            provider_class: The AIProvider subclass to register
        """
        name = name.lower()
        cls._providers[name] = provider_class
        # Remove from lazy specs if present
        cls._lazy_specs.pop(name, None)
        logger.debug(f"Registered provider: {name}")

    @classmethod
    def register_lazy(
        cls,
        name: str,
        module_path: str,
        class_name: str,
    ) -> None:
        """
        Register a provider for lazy loading.

        The provider module will only be imported when the provider
        is first accessed, improving startup time.

        Args:
            name: Provider name (will be lowercased)
            module_path: Full module path (e.g., "fastband.providers.claude")
            class_name: Class name within the module (e.g., "ClaudeProvider")
        """
        name = name.lower()
        if name in cls._providers:
            logger.warning(
                f"Provider {name} already registered eagerly, skipping lazy registration"
            )
            return

        cls._lazy_specs[name] = LazyProviderSpec(
            module_path=module_path,
            class_name=class_name,
        )
        logger.debug(f"Registered lazy provider: {name}")

    @classmethod
    def _get_provider_class(cls, name: str) -> type[AIProvider] | None:
        """
        Get the provider class, handling lazy loading if needed.

        Args:
            name: Provider name (already lowercased)

        Returns:
            Provider class or None if not found
        """
        # Check eagerly registered first (fast path)
        if name in cls._providers:
            return cls._providers[name]

        # Check lazy specs and load if found
        if name in cls._lazy_specs:
            spec = cls._lazy_specs[name]
            provider_class = spec.get_class()
            # Move to eager registry once loaded
            cls._providers[name] = provider_class
            return provider_class

        return None

    @classmethod
    def get(cls, name: str, config: ProviderConfig | None = None) -> AIProvider:
        """
        Get or create a provider instance.

        Uses cached instances when possible. If no config is provided,
        creates one from environment variables.

        Args:
            name: Provider name (claude, openai, gemini, ollama)
            config: Optional configuration (uses env vars if not provided)

        Returns:
            AIProvider instance

        Raises:
            ValueError: If provider is not registered
        """
        name = name.lower()
        start = time.perf_counter()

        # Fast path: return cached instance if no new config
        if name in cls._instances and config is None:
            return cls._instances[name]

        # Get the provider class
        provider_class = cls._get_provider_class(name)
        if provider_class is None:
            available = cls.available_providers()
            raise ValueError(f"Unknown provider: {name}. Available: {available}")

        # Create configuration from environment if not provided
        if config is None:
            config = cls._config_from_env(name)

        # Create and cache the instance
        instance = provider_class(config)
        cls._instances[name] = instance

        elapsed = (time.perf_counter() - start) * 1000
        logger.debug(f"Created provider instance: {name} in {elapsed:.2f}ms")

        return instance

    @classmethod
    def _config_from_env(cls, name: str) -> ProviderConfig:
        """
        Create config from environment variables.

        Uses caching to avoid repeated env var lookups.
        """
        # Return cached config if available
        if name in cls._env_cache:
            return cls._env_cache[name]

        env_mappings = {
            "claude": ("ANTHROPIC_API_KEY", "claude-sonnet-4-20250514"),
            "openai": ("OPENAI_API_KEY", "gpt-4-turbo"),
            "gemini": ("GOOGLE_API_KEY", "gemini-pro"),
            "ollama": (None, "llama2"),
        }

        api_key_env, default_model = env_mappings.get(name, (None, None))

        config = ProviderConfig(
            name=name,
            api_key=os.getenv(api_key_env) if api_key_env else None,
            model=os.getenv(f"{name.upper()}_MODEL", default_model),
        )

        cls._env_cache[name] = config
        return config

    @classmethod
    def available_providers(cls) -> list[str]:
        """
        List all registered providers (both eager and lazy).

        Returns:
            List of provider names
        """
        names = set(cls._providers.keys())
        names.update(cls._lazy_specs.keys())
        return sorted(names)

    @classmethod
    def is_registered(cls, name: str) -> bool:
        """Check if a provider is registered (eager or lazy)."""
        name = name.lower()
        return name in cls._providers or name in cls._lazy_specs

    @classmethod
    def is_loaded(cls, name: str) -> bool:
        """Check if a provider class has been loaded (imported)."""
        name = name.lower()
        if name in cls._providers:
            return True
        if name in cls._lazy_specs:
            return cls._lazy_specs[name].is_loaded
        return False

    @classmethod
    def is_instantiated(cls, name: str) -> bool:
        """Check if a provider instance exists."""
        return name.lower() in cls._instances

    @classmethod
    def clear_instances(cls) -> None:
        """
        Clear all cached provider instances.

        Useful for testing or when switching configurations.
        """
        cls._instances.clear()
        cls._env_cache.clear()

    @classmethod
    def clear_all(cls) -> None:
        """
        Clear all registrations and instances.

        Useful for testing.
        """
        cls._providers.clear()
        cls._lazy_specs.clear()
        cls._instances.clear()
        cls._env_cache.clear()


def get_provider(name: str | None = None) -> AIProvider:
    """
    Get the configured AI provider.

    If name is not specified, uses FASTBAND_AI_PROVIDER env var,
    defaulting to 'claude'.

    Args:
        name: Optional provider name

    Returns:
        AIProvider instance
    """
    if name is None:
        name = os.getenv("FASTBAND_AI_PROVIDER", "claude")
    return ProviderRegistry.get(name)


def _register_builtin_providers() -> None:
    """
    Register all built-in providers for lazy loading.

    This is called on module import to set up the default providers.
    No actual imports happen until a provider is first accessed.
    """
    builtin_providers = {
        "claude": ("fastband.providers.claude", "ClaudeProvider"),
        "openai": ("fastband.providers.openai", "OpenAIProvider"),
        "gemini": ("fastband.providers.gemini", "GeminiProvider"),
        "ollama": ("fastband.providers.ollama", "OllamaProvider"),
    }

    for name, (module_path, class_name) in builtin_providers.items():
        ProviderRegistry.register_lazy(name, module_path, class_name)


# Register providers on module load (lazy - no actual imports)
_register_builtin_providers()

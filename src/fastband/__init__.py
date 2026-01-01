"""
Fastband Agent Control - Universal platform for AI agent coordination.

AI agent orchestration, multi-agent coordination, and autonomous
development workflows with adaptive tools and ticket management.
"""

__version__ = "1.2026.01.02"
__version_tuple__ = (1, 2026, 1, 2)
__author__ = "Fastband Team"

from fastband.core.config import FastbandConfig, get_config
from fastband.providers.registry import ProviderRegistry, get_provider

__all__ = [
    "__version__",
    "__version_tuple__",
    "get_config",
    "FastbandConfig",
    "get_provider",
    "ProviderRegistry",
]

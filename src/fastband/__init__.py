"""
Fastband MCP - Universal AI-powered development platform.

An AI-agnostic MCP server with adaptive tools, ticket management,
and multi-agent coordination.
"""

__version__ = "1.2025.12.0"
__version_tuple__ = (1, 2025, 12, 0)
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

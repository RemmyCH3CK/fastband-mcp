"""
Fastband Core - Shared foundations for Fastband products.

This package contains the shared core components used by both
Fastband Dev and Fastband Enterprise. It must not import from
either product package.

Architecture Rules:
- Core must not import fastband_dev or fastband_enterprise
- Core provides foundational abstractions only
- No product-specific conveniences or features
"""

__version__ = "0.0.1"
__all__: list[str] = []

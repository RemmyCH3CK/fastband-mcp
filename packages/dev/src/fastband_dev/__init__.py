"""
Fastband Dev - Lightweight, local-first developer tool suite.

This package provides developer-focused tooling for local development
workflows. It builds on fastband_core but must not import from
fastband_enterprise.

Architecture Rules:
- Dev may import fastband_core
- Dev must not import fastband_enterprise
- Dev features must not leak into Enterprise builds
"""

__version__ = "0.0.1"
__all__: list[str] = []

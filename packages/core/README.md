# Fastband Core

Shared foundations for Fastband products.

## Purpose

This package contains the shared core components used by both Fastband Dev and Fastband Enterprise.

## Architecture Rules

- **Must not import** `fastband_dev` or `fastband_enterprise`
- Provides foundational abstractions only
- No product-specific conveniences or features

## Installation

```bash
pip install fastband-core
```

## Development

```bash
pip install -e ".[dev]"
```

# Fastband Dev

Lightweight, local-first developer tool suite.

## Purpose

This package provides developer-focused tooling for local development workflows.

## Architecture Rules

- **May import** `fastband_core`
- **Must not import** `fastband_enterprise`
- Dev features must not leak into Enterprise builds

## Installation

```bash
pip install fastband-dev
```

## Development

```bash
pip install -e ".[dev]"
```

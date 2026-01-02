# Fastband Enterprise

Governed, auditable control plane.

## Purpose

This package provides the enterprise control plane with governance, audit logging, and compliance features.

## Architecture Rules

- **Must not import** `fastband_dev`
- Enterprise defaults must fail closed (refuse to start if insecure)
- No feature flags to toggle Dev ↔ Enterprise behavior

## Building

```bash
go build ./cmd/...
```

## Development

```bash
go mod tidy
go test ./...
```

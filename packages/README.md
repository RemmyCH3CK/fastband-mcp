# Fastband Packages

This directory contains the dual-product architecture for Fastband.

## Package Structure

```
packages/
├── core/           # Shared foundations (Python)
├── dev/            # Fastband Dev - local-first tooling (Python)
└── enterprise/     # Fastband Enterprise - governed control plane (Go)
```

## Architecture Rules

### Import Boundaries (Non-Negotiable)

```
┌─────────────────────────────────────────────────────────┐
│                                                         │
│   ┌─────────────┐                                       │
│   │    Core     │  ← Cannot import Dev or Enterprise    │
│   └──────┬──────┘                                       │
│          │                                              │
│          ▼                                              │
│   ┌─────────────┐     ┌─────────────────┐               │
│   │     Dev     │     │   Enterprise    │               │
│   └─────────────┘     └─────────────────┘               │
│          │                    │                         │
│          └────────────────────┘                         │
│                    ✗                                    │
│          Dev cannot import Enterprise                   │
│          Enterprise cannot import Dev                   │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

1. **Core must not import Dev or Enterprise**
2. **Dev must not import Enterprise**
3. **Enterprise must not import Dev**
4. **No feature flags to toggle Dev ↔ Enterprise behavior**

### Package Purposes

| Package | Language | Purpose |
|---------|----------|---------|
| `core` | Python | Shared abstractions, data models, utilities |
| `dev` | Python | CLI tools, local workflows, developer conveniences |
| `enterprise` | Go | Governed control plane, audit logging, compliance |

### Build Artifacts

Each package produces independent artifacts:

- `fastband-core` → PyPI package
- `fastband-dev` → PyPI package (depends on core)
- `fastband-enterprise` → Go binary

### Development

```bash
# Install core for development
pip install -e packages/core

# Install dev (includes core dependency)
pip install -e packages/dev

# Build enterprise
cd packages/enterprise && go build ./cmd/...
```

## CI Guardrails

Import boundaries are enforced by CI. See `.github/workflows/import-boundaries.yml`.

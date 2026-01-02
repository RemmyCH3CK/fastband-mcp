# Fastband Core Examples

This directory contains examples and demos for Fastband Core.

## Core Demo

The `core_demo.py` script validates that Fastband Core can run independently without:
- External SDKs (anthropic, openai, etc.)
- Web frameworks (FastAPI, Flask)
- Database drivers
- Network calls
- Environment file loading

### Running the Demo

```bash
# From the repository root
python packages/core/examples/core_demo.py

# Or from the package root
cd packages/core
python -m examples.core_demo
```

### What the Demo Validates

The demo executes 9 validation steps:

1. **Mock Adapters** - Initializes in-memory mock implementations for all Core ports
2. **Authentication** - Creates a session and validates authorization
3. **Tool Registry** - Registers and executes tools through the registry
4. **Domain Events** - Creates and publishes domain events via event bus
5. **Audit Records** - Creates and stores audit records in memory
6. **Providers** - Tests completion and embedding provider abstractions
7. **Storage** - Validates key-value and document store operations
8. **Policy** - Tests policy evaluation, rate limiting, and feature flags
9. **Telemetry** - Validates logging, tracing, and metrics collection

### Expected Output

```
============================================================
  FASTBAND CORE DEMO - Core Independence Validation
============================================================

Step 1: Initializing mock adapters...
  [OK] Storage adapters: KeyValue + Document stores
  [OK] Auth adapters: Authenticator + Authorizer + TokenProvider
  ...

============================================================
  DEMO COMPLETED SUCCESSFULLY
============================================================

  Elapsed: 0.003s
  Events:  1
  Audit:   1
  Tools:   2
  Logs:    2
  Spans:   1

  Core independence validated - no network calls made!
============================================================
```

## Files

| File | Description |
|------|-------------|
| `core_demo.py` | Main demo script that validates Core independence |
| `mocks.py` | Mock implementations for all Core ports and providers |
| `test_core_demo.py` | Tests for the demo and mock implementations |

## Mock Implementations

The `mocks.py` file provides in-memory mock implementations for:

### Storage
- `MockKeyValueStore` - Simple key-value storage with TTL support
- `MockDocumentStore` - Document storage with query support

### Authentication
- `MockAuthenticator` - Accepts demo credentials and creates sessions
- `MockAuthorizer` - Role-based authorization (admin/user roles)
- `MockTokenProvider` - Generates and validates mock tokens

### Policy
- `MockPolicyEvaluator` - Always allows for demo purposes
- `MockRateLimiter` - Tracks request counts without limiting
- `MockFeatureFlagProvider` - Returns preset flag values

### Telemetry
- `MockLoggerFactory` / `MockLogger` - Collects log entries in memory
- `MockTracer` / `MockSpan` - Creates spans with proper context
- `MockMetricsRegistry` - Collects counters, gauges, and histograms

### Events
- `MockEventPublisher` - Stores published events
- `MockEventBus` - Routes events to subscribed handlers

### Providers
- `MockCompletionProvider` - Returns deterministic mock responses
- `MockEmbeddingProvider` - Returns deterministic mock embeddings

### Utilities
- `DemoContext` - Aggregates all mock adapters for easy demo setup
- `MockAuditStore` - Stores audit records in memory

## Running Tests

```bash
# From the examples directory
pytest test_core_demo.py -v

# From repository root
pytest packages/core/examples/test_core_demo.py -v
```

## Architecture Notes

This demo demonstrates Core's architecture principles:

1. **Port/Adapter Pattern** - Core defines abstract ports; mocks provide concrete adapters
2. **No Side Effects** - Imports have no side effects; mocks are stateless on creation
3. **Stdlib Only** - Mocks use only Python stdlib (no external dependencies)
4. **Protocol Agnostic** - Tool definitions work with any protocol (MCP, OpenAI, etc.)

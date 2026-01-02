# Fastband Enterprise Control Plane

Governed, auditable control plane for the Fastband platform.

## Overview

The Fastband Enterprise Control Plane provides centralized coordination, policy enforcement, and audit logging for distributed execution planes (Python Dev/Core runtimes). It implements:

- **Fail-closed startup**: Server refuses to start without valid configuration
- **Authentication middleware**: All API endpoints require valid Bearer tokens
- **Health endpoints**: Kubernetes-style liveness and readiness probes
- **v1 API envelope**: Consistent JSON response format for all endpoints

## Architecture Rules

- **Must not import** `packages/core` or `packages/dev`
- Enterprise defaults must **fail closed** (refuse to start if insecure)
- No feature flags to toggle Dev ↔ Enterprise behavior

## Requirements

- Go 1.22+
- golangci-lint (for linting)

## Quick Start

```bash
# Build
make build

# Run tests
make test

# Run linter
make lint

# Run server (requires auth secret)
FASTBAND_AUTH_SECRET=your-secret make run

# Run in development mode (with example secret)
make run-dev
```

## Configuration

### Required Environment Variables

| Variable | Description |
|----------|-------------|
| `FASTBAND_AUTH_SECRET` | Authentication secret for Bearer token validation. **Required** - server fails to start without it. |

### Optional Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `FASTBAND_LISTEN_ADDR` | `:8080` | HTTP server listen address |
| `FASTBAND_SHUTDOWN_TIMEOUT` | `30s` | Graceful shutdown timeout |
| `FASTBAND_ENABLE_EVENT_STREAM` | `false` | Enable SSE event stream (future) |

## API Endpoints

### Health (Public - No Auth Required)

| Endpoint | Description |
|----------|-------------|
| `GET /healthz` | Liveness probe |
| `GET /readyz` | Readiness probe |
| `GET /v1/health` | Health status with version |
| `GET /v1/ready` | Readiness status |

### API v1 (Requires Authentication)

All endpoints under `/v1/*` require a valid `Authorization: Bearer <token>` header.

#### Tickets
- `POST /v1/tickets` - Create ticket
- `GET /v1/tickets` - List tickets
- `GET /v1/tickets/{id}` - Get ticket
- `PATCH /v1/tickets/{id}` - Update ticket
- `POST /v1/tickets/{id}/jobs` - Create job

#### Jobs
- `GET /v1/jobs/{id}` - Get job
- `PATCH /v1/jobs/{id}` - Update job

#### Policy
- `POST /v1/policy/check` - Check policy

#### Approvals
- `GET /v1/approvals` - List approvals
- `GET /v1/approvals/{id}` - Get approval
- `POST /v1/approvals/{id}/approve` - Approve
- `POST /v1/approvals/{id}/deny` - Deny

#### Audit
- `POST /v1/audit` - Create audit record
- `GET /v1/audit` - List audit records
- `GET /v1/audit/{id}` - Get audit record

#### Events
- `GET /v1/events/stream` - SSE event stream

**Note:** All stub endpoints currently return `501 Not Implemented` with the v1 error envelope format.

## Response Format

### Success Response

```json
{
  "success": true,
  "data": { ... },
  "meta": {
    "request_id": "req_abc123",
    "correlation_id": "cor_xyz789",
    "timestamp": "2026-01-02T12:00:00Z"
  }
}
```

### Error Response

```json
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable message",
    "details": { ... }
  },
  "meta": {
    "request_id": "req_abc123",
    "correlation_id": "cor_xyz789",
    "timestamp": "2026-01-02T12:00:00Z"
  }
}
```

## Fail-Closed Behavior

The server implements fail-closed semantics:

1. **Missing `FASTBAND_AUTH_SECRET`**: Server refuses to start
2. **Missing authentication header**: Returns 401
3. **Invalid token**: Returns 401
4. **Unknown endpoints**: Returns 404

To verify fail-closed behavior:

```bash
make verify-fail-closed
```

## Development

### Project Structure

```
packages/enterprise/
├── cmd/fastband-enterprise/   # Main entrypoint
├── internal/
│   ├── config/                # Configuration loading
│   ├── handlers/              # HTTP handlers
│   ├── health/                # Health check endpoints
│   ├── middleware/auth/       # Authentication middleware
│   ├── requestid/             # Request ID generation
│   ├── response/              # Response envelope formatting
│   ├── router/                # HTTP routing
│   └── server/                # HTTP server lifecycle
├── specs/                     # API specifications
├── go.mod
├── go.sum
├── Makefile
└── README.md
```

### Running Tests

```bash
# Run all tests
make test

# Run tests with coverage
make test-cover

# Run specific package tests
go test -v ./internal/config/
```

### Code Style

- Use Go 1.22 features where appropriate
- Structured logging with `log/slog`
- Context propagation
- No global state
- Explicit error handling

## License

Proprietary - Fastband

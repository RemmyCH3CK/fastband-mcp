"""
Fastband AI Hub - Telemetry & Observability.

OpenTelemetry-based distributed tracing, metrics, and logging for
enterprise deployments.

Features:
- Distributed tracing with automatic span propagation
- Metrics collection (counters, histograms, gauges)
- FastAPI auto-instrumentation
- HTTP client instrumentation (httpx, requests)
- Custom span decorators
- Multiple exporter support (OTLP, Jaeger, Zipkin, Console)

Configuration via environment variables:
- OTEL_SERVICE_NAME: Service name (default: fastband-hub)
- OTEL_EXPORTER_OTLP_ENDPOINT: OTLP collector endpoint
- OTEL_EXPORTER_OTLP_HEADERS: Headers for OTLP exporter
- OTEL_TRACES_SAMPLER: Sampling strategy
- OTEL_TRACES_SAMPLER_ARG: Sampling ratio
"""

from fastband.hub.telemetry.tracing import (
    TracingConfig,
    TracingService,
    get_tracing_service,
    instrument_fastapi,
    span,
    with_span,
)

__all__ = [
    "TracingService",
    "TracingConfig",
    "get_tracing_service",
    "instrument_fastapi",
    "span",
    "with_span",
]

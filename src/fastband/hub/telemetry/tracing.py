"""
Fastband AI Hub - OpenTelemetry Tracing.

Distributed tracing implementation using OpenTelemetry for
observability in enterprise deployments.
"""

import logging
import os
from contextvars import ContextVar
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps
from typing import Any, Callable, TypeVar

from fastapi import FastAPI, Request

logger = logging.getLogger(__name__)

# Type var for decorated functions
F = TypeVar("F", bound=Callable[..., Any])

# Context var for current span
_current_span: ContextVar[Any] = ContextVar("current_span", default=None)


# =============================================================================
# CONFIGURATION
# =============================================================================


class ExporterType(str, Enum):
    """Supported trace exporters."""

    CONSOLE = "console"  # Debug: logs to console
    OTLP = "otlp"  # OpenTelemetry Protocol (Jaeger, Grafana, etc.)
    JAEGER = "jaeger"  # Jaeger direct
    ZIPKIN = "zipkin"  # Zipkin direct
    NONE = "none"  # Disabled


class SamplerType(str, Enum):
    """Trace sampling strategies."""

    ALWAYS_ON = "always_on"  # Sample all traces
    ALWAYS_OFF = "always_off"  # Sample no traces
    RATIO = "ratio"  # Probabilistic sampling
    PARENT = "parent"  # Parent-based sampling


@dataclass(slots=True)
class TracingConfig:
    """OpenTelemetry tracing configuration.

    Attributes:
        service_name: Name of this service in traces
        exporter: Trace exporter type
        endpoint: OTLP/Jaeger/Zipkin collector endpoint
        headers: HTTP headers for exporter auth
        sampler: Sampling strategy
        sample_ratio: Sampling ratio (for ratio sampler)
        enable_http_instrumentation: Instrument HTTP clients
        enable_logging_instrumentation: Instrument logging
        enabled: Enable/disable tracing entirely
    """

    service_name: str = "fastband-hub"
    exporter: ExporterType = ExporterType.OTLP
    endpoint: str = ""
    headers: dict[str, str] = field(default_factory=dict)
    sampler: SamplerType = SamplerType.ALWAYS_ON
    sample_ratio: float = 1.0
    enable_http_instrumentation: bool = True
    enable_logging_instrumentation: bool = True
    enabled: bool = True

    @classmethod
    def from_env(cls) -> "TracingConfig":
        """Load configuration from environment variables."""
        # Parse headers from env (comma-separated key=value pairs)
        headers_str = os.getenv("OTEL_EXPORTER_OTLP_HEADERS", "")
        headers = {}
        if headers_str:
            for pair in headers_str.split(","):
                if "=" in pair:
                    key, value = pair.split("=", 1)
                    headers[key.strip()] = value.strip()

        # Determine exporter type
        endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "")
        exporter_type = ExporterType.OTLP if endpoint else ExporterType.NONE

        return cls(
            service_name=os.getenv("OTEL_SERVICE_NAME", "fastband-hub"),
            exporter=ExporterType(os.getenv("OTEL_EXPORTER_TYPE", exporter_type.value)),
            endpoint=endpoint,
            headers=headers,
            sampler=SamplerType(os.getenv("OTEL_TRACES_SAMPLER", "always_on")),
            sample_ratio=float(os.getenv("OTEL_TRACES_SAMPLER_ARG", "1.0")),
            enabled=os.getenv("OTEL_TRACING_ENABLED", "true").lower() not in ("false", "0", "no"),
        )


# =============================================================================
# TRACING SERVICE
# =============================================================================


class TracingService:
    """OpenTelemetry tracing service.

    Manages tracer initialization, span creation, and instrumentation.

    Example:
        config = TracingConfig.from_env()
        tracing = TracingService(config)
        tracing.initialize()

        # Use decorator
        @tracing.with_span("my_operation")
        async def my_function():
            pass

        # Manual span
        with tracing.span("custom_operation") as span:
            span.set_attribute("key", "value")
    """

    def __init__(self, config: TracingConfig | None = None):
        """Initialize tracing service.

        Args:
            config: Tracing configuration
        """
        self.config = config or TracingConfig.from_env()
        self._tracer = None
        self._meter = None
        self._initialized = False

    def initialize(self) -> bool:
        """Initialize OpenTelemetry tracing.

        Returns:
            True if initialization successful
        """
        if not self.config.enabled:
            logger.info("OpenTelemetry tracing disabled")
            return False

        if self._initialized:
            return True

        try:
            from opentelemetry import trace
            from opentelemetry.sdk.resources import Resource
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import BatchSpanProcessor

            # Create resource with service info
            resource = Resource.create(
                {
                    "service.name": self.config.service_name,
                    "service.version": self._get_version(),
                }
            )

            # Create tracer provider
            provider = TracerProvider(resource=resource)

            # Configure sampler
            # Note: Sampler is set at provider creation - using default for now
            # Custom sampling can be added if needed

            # Add exporter
            exporter = self._create_exporter()
            if exporter:
                provider.add_span_processor(BatchSpanProcessor(exporter))

            # Set global tracer provider
            trace.set_tracer_provider(provider)

            # Get tracer
            self._tracer = trace.get_tracer(
                self.config.service_name,
                self._get_version(),
            )

            self._initialized = True
            logger.info(f"OpenTelemetry tracing initialized: {self.config.exporter.value}")
            return True

        except ImportError as e:
            logger.warning(
                f"OpenTelemetry not installed. Run: pip install 'fastband-agent-control[tracing]'"
            )
            logger.debug(f"Import error: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to initialize tracing: {e}")
            return False

    def _get_version(self) -> str:
        """Get service version."""
        try:
            from fastband import __version__

            return __version__
        except ImportError:
            return "0.0.0"

    def _create_exporter(self):
        """Create span exporter based on configuration."""
        if self.config.exporter == ExporterType.NONE:
            return None

        if self.config.exporter == ExporterType.CONSOLE:
            from opentelemetry.sdk.trace.export import ConsoleSpanExporter

            return ConsoleSpanExporter()

        if self.config.exporter == ExporterType.OTLP:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

            return OTLPSpanExporter(
                endpoint=self.config.endpoint,
                headers=self.config.headers or None,
            )

        if self.config.exporter == ExporterType.JAEGER:
            from opentelemetry.exporter.jaeger.thrift import JaegerExporter

            return JaegerExporter(
                agent_host_name=self.config.endpoint.split(":")[0] if self.config.endpoint else "localhost",
                agent_port=int(self.config.endpoint.split(":")[1]) if ":" in self.config.endpoint else 6831,
            )

        if self.config.exporter == ExporterType.ZIPKIN:
            from opentelemetry.exporter.zipkin.json import ZipkinExporter

            return ZipkinExporter(endpoint=self.config.endpoint)

        return None

    def span(self, name: str, attributes: dict[str, Any] | None = None):
        """Create a trace span context manager.

        Args:
            name: Span name
            attributes: Initial span attributes

        Returns:
            Span context manager

        Example:
            with tracing.span("process_request", {"user_id": "123"}) as span:
                result = process()
                span.set_attribute("result_count", len(result))
        """
        if not self._initialized:
            # Return a no-op context manager when not initialized
            from contextlib import nullcontext

            return nullcontext()

        span = self._tracer.start_as_current_span(name, attributes=attributes)
        return span

    def with_span(self, name: str, attributes: dict[str, Any] | None = None) -> Callable[[F], F]:
        """Decorator to wrap a function in a span.

        Args:
            name: Span name
            attributes: Initial span attributes

        Returns:
            Decorator function

        Example:
            @tracing.with_span("my_operation")
            async def my_function():
                pass
        """

        def decorator(func: F) -> F:
            if not self._initialized:
                return func

            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                with self._tracer.start_as_current_span(name, attributes=attributes) as span:
                    try:
                        result = await func(*args, **kwargs)
                        return result
                    except Exception as e:
                        span.record_exception(e)
                        span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                        raise

            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                with self._tracer.start_as_current_span(name, attributes=attributes) as span:
                    try:
                        result = func(*args, **kwargs)
                        return result
                    except Exception as e:
                        span.record_exception(e)
                        span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                        raise

            import asyncio

            if asyncio.iscoroutinefunction(func):
                return async_wrapper  # type: ignore
            return sync_wrapper  # type: ignore

        return decorator

    def get_current_span(self):
        """Get the current active span.

        Returns:
            Current span or None
        """
        if not self._initialized:
            return None

        from opentelemetry import trace

        return trace.get_current_span()

    def add_event(self, name: str, attributes: dict[str, Any] | None = None) -> None:
        """Add an event to the current span.

        Args:
            name: Event name
            attributes: Event attributes
        """
        span = self.get_current_span()
        if span:
            span.add_event(name, attributes=attributes)

    def set_attribute(self, key: str, value: Any) -> None:
        """Set an attribute on the current span.

        Args:
            key: Attribute key
            value: Attribute value
        """
        span = self.get_current_span()
        if span:
            span.set_attribute(key, value)

    def record_exception(self, exception: Exception) -> None:
        """Record an exception on the current span.

        Args:
            exception: Exception to record
        """
        span = self.get_current_span()
        if span:
            span.record_exception(exception)


# =============================================================================
# FASTAPI INSTRUMENTATION
# =============================================================================


def instrument_fastapi(app: FastAPI, config: TracingConfig | None = None) -> TracingService:
    """Instrument a FastAPI application with OpenTelemetry.

    Args:
        app: FastAPI application
        config: Tracing configuration

    Returns:
        Initialized TracingService

    Example:
        from fastapi import FastAPI
        from fastband.hub.telemetry import instrument_fastapi

        app = FastAPI()
        tracing = instrument_fastapi(app)
    """
    tracing = TracingService(config)
    if not tracing.initialize():
        return tracing

    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.instrument_app(app)
        logger.info("FastAPI instrumentation enabled")
    except ImportError:
        logger.warning(
            "FastAPI instrumentation not available. Install: pip install opentelemetry-instrumentation-fastapi"
        )
    except Exception as e:
        logger.error(f"Failed to instrument FastAPI: {e}")

    # Instrument HTTP clients if enabled
    if tracing.config.enable_http_instrumentation:
        _instrument_http_clients()

    return tracing


def _instrument_http_clients():
    """Instrument HTTP client libraries."""
    # Instrument httpx
    try:
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

        HTTPXClientInstrumentor().instrument()
        logger.debug("HTTPX instrumentation enabled")
    except ImportError:
        pass
    except Exception as e:
        logger.debug(f"HTTPX instrumentation failed: {e}")

    # Instrument requests
    try:
        from opentelemetry.instrumentation.requests import RequestsInstrumentor

        RequestsInstrumentor().instrument()
        logger.debug("Requests instrumentation enabled")
    except ImportError:
        pass
    except Exception as e:
        logger.debug(f"Requests instrumentation failed: {e}")


# =============================================================================
# GLOBAL SERVICE & HELPERS
# =============================================================================

_tracing_service: TracingService | None = None


def get_tracing_service() -> TracingService:
    """Get or create the global tracing service."""
    global _tracing_service
    if _tracing_service is None:
        _tracing_service = TracingService()
        _tracing_service.initialize()
    return _tracing_service


def span(name: str, attributes: dict[str, Any] | None = None):
    """Create a span using the global tracing service.

    Convenience function for quick span creation.

    Example:
        with span("my_operation") as s:
            s.set_attribute("key", "value")
            do_work()
    """
    return get_tracing_service().span(name, attributes)


def with_span(name: str, attributes: dict[str, Any] | None = None) -> Callable[[F], F]:
    """Decorator using the global tracing service.

    Example:
        @with_span("my_operation")
        async def my_function():
            pass
    """
    return get_tracing_service().with_span(name, attributes)


# Import trace for the decorator - handle when not installed
try:
    from opentelemetry import trace
except ImportError:
    # Create stub when not installed
    class trace:  # type: ignore
        class Status:
            def __init__(self, code, description=None):
                pass

        class StatusCode:
            ERROR = None

"""
Telemetry port interfaces.

Defines abstractions for observability: metrics, tracing, and logging.
Implementations may use OpenTelemetry, Prometheus, or custom backends.

These are pure interfaces - no telemetry SDK imports allowed.
"""

from abc import ABC, abstractmethod
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Generator, Protocol, runtime_checkable


class LogLevel(Enum):
    """Standard log levels."""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class MetricType(Enum):
    """Types of metrics."""

    COUNTER = "counter"  # Monotonically increasing
    GAUGE = "gauge"  # Point-in-time value
    HISTOGRAM = "histogram"  # Distribution of values
    SUMMARY = "summary"  # Statistical summary


@dataclass
class LogRecord:
    """
    A structured log record.

    Contains message, level, and structured context.
    """

    message: str
    level: LogLevel
    timestamp: datetime = field(default_factory=datetime.utcnow)
    logger_name: str = "fastband"
    context: dict[str, Any] = field(default_factory=dict)
    exception: Exception | None = None
    trace_id: str | None = None
    span_id: str | None = None


@runtime_checkable
class Logger(Protocol):
    """
    Protocol for structured logging.

    Implementations should support structured context and trace correlation.
    """

    def debug(self, message: str, **context: Any) -> None:
        """Log at DEBUG level."""
        ...

    def info(self, message: str, **context: Any) -> None:
        """Log at INFO level."""
        ...

    def warning(self, message: str, **context: Any) -> None:
        """Log at WARNING level."""
        ...

    def error(self, message: str, **context: Any) -> None:
        """Log at ERROR level."""
        ...

    def critical(self, message: str, **context: Any) -> None:
        """Log at CRITICAL level."""
        ...

    def exception(self, message: str, exc: Exception, **context: Any) -> None:
        """Log an exception with traceback."""
        ...

    def with_context(self, **context: Any) -> "Logger":
        """Create a child logger with additional context."""
        ...


class LoggerFactory(ABC):
    """
    Abstract base for creating loggers.

    Creates named loggers with consistent configuration.
    """

    @abstractmethod
    def get_logger(self, name: str) -> Logger:
        """
        Get a named logger.

        Args:
            name: Logger name (typically module path).

        Returns:
            A logger instance.
        """
        ...

    @abstractmethod
    def set_level(self, level: LogLevel) -> None:
        """
        Set global log level.

        Args:
            level: Minimum level to log.
        """
        ...


@dataclass
class MetricLabels:
    """Labels/tags for a metric."""

    values: dict[str, str] = field(default_factory=dict)

    def with_label(self, key: str, value: str) -> "MetricLabels":
        """Add a label, returning a new MetricLabels instance."""
        new_values = self.values.copy()
        new_values[key] = value
        return MetricLabels(new_values)


class Counter(ABC):
    """
    Abstract base for counter metrics.

    Monotonically increasing value (e.g., request count).
    """

    @abstractmethod
    def inc(self, value: float = 1.0, labels: MetricLabels | None = None) -> None:
        """
        Increment the counter.

        Args:
            value: Amount to increment (must be positive).
            labels: Optional metric labels.
        """
        ...


class Gauge(ABC):
    """
    Abstract base for gauge metrics.

    Point-in-time value that can go up or down (e.g., active connections).
    """

    @abstractmethod
    def set(self, value: float, labels: MetricLabels | None = None) -> None:
        """
        Set the gauge value.

        Args:
            value: The value to set.
            labels: Optional metric labels.
        """
        ...

    @abstractmethod
    def inc(self, value: float = 1.0, labels: MetricLabels | None = None) -> None:
        """Increment the gauge."""
        ...

    @abstractmethod
    def dec(self, value: float = 1.0, labels: MetricLabels | None = None) -> None:
        """Decrement the gauge."""
        ...


class Histogram(ABC):
    """
    Abstract base for histogram metrics.

    Distribution of values (e.g., request latency).
    """

    @abstractmethod
    def observe(self, value: float, labels: MetricLabels | None = None) -> None:
        """
        Record an observation.

        Args:
            value: The value to record.
            labels: Optional metric labels.
        """
        ...

    @abstractmethod
    @contextmanager
    def time(
        self, labels: MetricLabels | None = None
    ) -> Generator[None, None, None]:
        """
        Context manager to time a block and record duration.

        Args:
            labels: Optional metric labels.
        """
        ...


class MetricsRegistry(ABC):
    """
    Abstract base for metrics registration and creation.

    Creates and manages metric instances.
    """

    @abstractmethod
    def counter(
        self,
        name: str,
        description: str,
        label_names: list[str] | None = None,
    ) -> Counter:
        """
        Create or retrieve a counter metric.

        Args:
            name: Metric name.
            description: Human-readable description.
            label_names: Names of labels this metric uses.

        Returns:
            A counter instance.
        """
        ...

    @abstractmethod
    def gauge(
        self,
        name: str,
        description: str,
        label_names: list[str] | None = None,
    ) -> Gauge:
        """
        Create or retrieve a gauge metric.

        Args:
            name: Metric name.
            description: Human-readable description.
            label_names: Names of labels this metric uses.

        Returns:
            A gauge instance.
        """
        ...

    @abstractmethod
    def histogram(
        self,
        name: str,
        description: str,
        label_names: list[str] | None = None,
        buckets: list[float] | None = None,
    ) -> Histogram:
        """
        Create or retrieve a histogram metric.

        Args:
            name: Metric name.
            description: Human-readable description.
            label_names: Names of labels this metric uses.
            buckets: Histogram bucket boundaries.

        Returns:
            A histogram instance.
        """
        ...


@dataclass
class SpanContext:
    """Context for distributed tracing."""

    trace_id: str
    span_id: str
    parent_span_id: str | None = None
    trace_flags: int = 0
    trace_state: dict[str, str] = field(default_factory=dict)


class SpanStatus(Enum):
    """Status of a trace span."""

    UNSET = "unset"
    OK = "ok"
    ERROR = "error"


@dataclass
class SpanEvent:
    """An event within a span."""

    name: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    attributes: dict[str, Any] = field(default_factory=dict)


class Span(ABC):
    """
    Abstract base for trace spans.

    Represents a unit of work in a distributed trace.
    """

    @property
    @abstractmethod
    def context(self) -> SpanContext:
        """Get the span context."""
        ...

    @abstractmethod
    def set_attribute(self, key: str, value: Any) -> None:
        """
        Set a span attribute.

        Args:
            key: Attribute name.
            value: Attribute value.
        """
        ...

    @abstractmethod
    def set_status(self, status: SpanStatus, description: str | None = None) -> None:
        """
        Set the span status.

        Args:
            status: The status code.
            description: Optional status description.
        """
        ...

    @abstractmethod
    def add_event(
        self,
        name: str,
        attributes: dict[str, Any] | None = None,
    ) -> None:
        """
        Add an event to the span.

        Args:
            name: Event name.
            attributes: Optional event attributes.
        """
        ...

    @abstractmethod
    def record_exception(self, exception: Exception) -> None:
        """
        Record an exception on the span.

        Args:
            exception: The exception to record.
        """
        ...

    @abstractmethod
    def end(self) -> None:
        """End the span."""
        ...


class Tracer(ABC):
    """
    Abstract base for distributed tracing.

    Creates and manages trace spans.
    """

    @abstractmethod
    def start_span(
        self,
        name: str,
        parent: SpanContext | None = None,
        attributes: dict[str, Any] | None = None,
    ) -> Span:
        """
        Start a new span.

        Args:
            name: Span name.
            parent: Optional parent span context.
            attributes: Initial span attributes.

        Returns:
            A new span.
        """
        ...

    @abstractmethod
    @contextmanager
    def span(
        self,
        name: str,
        attributes: dict[str, Any] | None = None,
    ) -> Generator[Span, None, None]:
        """
        Context manager for span lifecycle.

        Args:
            name: Span name.
            attributes: Initial span attributes.

        Yields:
            The created span.
        """
        ...

    @abstractmethod
    def get_current_span(self) -> Span | None:
        """Get the current active span."""
        ...

    @abstractmethod
    def inject_context(self, carrier: dict[str, str]) -> None:
        """
        Inject trace context into a carrier (e.g., HTTP headers).

        Args:
            carrier: Dictionary to inject context into.
        """
        ...

    @abstractmethod
    def extract_context(self, carrier: dict[str, str]) -> SpanContext | None:
        """
        Extract trace context from a carrier.

        Args:
            carrier: Dictionary containing trace context.

        Returns:
            Extracted span context, or None if not found.
        """
        ...


class TelemetryProvider(ABC):
    """
    Abstract base for unified telemetry access.

    Provides access to all telemetry components.
    """

    @property
    @abstractmethod
    def logger_factory(self) -> LoggerFactory:
        """Get the logger factory."""
        ...

    @property
    @abstractmethod
    def metrics(self) -> MetricsRegistry:
        """Get the metrics registry."""
        ...

    @property
    @abstractmethod
    def tracer(self) -> Tracer:
        """Get the tracer."""
        ...

    @abstractmethod
    def shutdown(self) -> None:
        """Shutdown and flush all telemetry."""
        ...

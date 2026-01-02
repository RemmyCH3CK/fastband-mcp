"""
Mock implementations for Core ports.

Provides in-memory mock adapters for validating Core independence.
These mocks implement the Core port interfaces without any external
dependencies.

Architecture Rules:
- No side effects on import
- No external SDK imports
- No framework imports
- No network calls
- All state is in-memory
"""

from collections.abc import AsyncIterator, Generator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

# Import Core ports
from fastband_core.ports import (
    Authenticator,
    Authorizer,
    Event,
    EventBus,
    EventPublisher,
    KeyValueStore,
    Logger,
    LoggerFactory,
    LogLevel,
    MetricsRegistry,
    Principal,
    Session,
    Subscription,
    TelemetryProvider,
    TokenPair,
    TokenProvider,
    Tracer,
    DeliveryResult,
)

# Import span types from telemetry
from fastband_core.ports.telemetry import (
    Span,
    SpanContext,
    SpanStatus,
)

# Import policy types separately (they have different interface)
from fastband_core.ports.policy import (
    PolicyEvaluator,
    PolicyContext,
    PolicyResult,
    PolicyDecision,
    RateLimiter,
    RateLimitConfig,
    RateLimitStatus,
    FeatureFlagProvider,
    FeatureFlagContext,
)

# Import Core domain models
from fastband_core.events import DomainEvent, EventMetadata
from fastband_core.audit import AuditRecord, AuditActor

# Import Core provider abstractions
from fastband_core.providers import (
    Capability,
    CapabilitySet,
    CompletionProvider,
    CompletionResponse,
    EmbeddingConfig,
    EmbeddingProvider,
    EmbeddingResult,
    FinishReason,
    ProviderConfig,
    TokenUsage,
)


def _utc_now() -> datetime:
    """Get current UTC time."""
    return datetime.now(timezone.utc)


def _generate_id() -> str:
    """Generate a unique ID."""
    return str(uuid4())


# =============================================================================
# STORAGE MOCKS
# =============================================================================


class MockKeyValueStore(KeyValueStore):
    """In-memory key-value store."""

    def __init__(self) -> None:
        self._data: dict[str, bytes] = {}
        self._ttls: dict[str, datetime] = {}

    async def get(self, key: str) -> bytes | None:
        if key in self._ttls:
            if _utc_now() > self._ttls[key]:
                del self._data[key]
                del self._ttls[key]
                return None
        return self._data.get(key)

    async def set(self, key: str, value: bytes, ttl: int | None = None) -> None:
        self._data[key] = value
        if ttl:
            from datetime import timedelta
            self._ttls[key] = _utc_now() + timedelta(seconds=ttl)

    async def delete(self, key: str) -> bool:
        if key in self._data:
            del self._data[key]
            self._ttls.pop(key, None)
            return True
        return False

    async def exists(self, key: str) -> bool:
        return key in self._data

    async def keys(self, pattern: str = "*") -> list[str]:
        if pattern == "*":
            return list(self._data.keys())
        # Simple pattern matching
        import fnmatch
        return [k for k in self._data.keys() if fnmatch.fnmatch(k, pattern)]


class MockDocumentStore:
    """
    Simple in-memory document store.

    Note: This is a simplified mock that doesn't inherit from the full
    DocumentStore ABC, which requires entity type generics.
    """

    def __init__(self) -> None:
        self._collections: dict[str, dict[str, dict[str, Any]]] = {}

    async def get(self, collection: str, doc_id: str) -> dict[str, Any] | None:
        """Get a document by collection and ID."""
        return self._collections.get(collection, {}).get(doc_id)

    async def set(self, collection: str, doc_id: str, document: dict[str, Any]) -> None:
        """Set a document (create or update)."""
        if collection not in self._collections:
            self._collections[collection] = {}
        self._collections[collection][doc_id] = document

    async def delete(self, collection: str, doc_id: str) -> bool:
        """Delete a document."""
        if collection in self._collections and doc_id in self._collections[collection]:
            del self._collections[collection][doc_id]
            return True
        return False

    async def query(
        self,
        collection: str,
        conditions: dict[str, Any] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Query documents with optional conditions."""
        docs = list(self._collections.get(collection, {}).values())
        # Simple filtering if conditions provided
        if conditions:
            filtered = []
            for doc in docs:
                match = True
                for key, value in conditions.items():
                    if doc.get(key) != value:
                        match = False
                        break
                if match:
                    filtered.append(doc)
            docs = filtered
        return docs[offset : offset + limit]

    async def count(self, collection: str, conditions: dict[str, Any] | None = None) -> int:
        """Count documents."""
        docs = await self.query(collection, conditions, limit=1000000)
        return len(docs)


# =============================================================================
# AUTH MOCKS
# =============================================================================


class MockAuthenticator(Authenticator):
    """Mock authenticator that accepts any credentials."""

    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}
        self._users: dict[str, Principal] = {
            "demo-user": Principal(
                id="demo-user",
                type="user",
                attributes={
                    "display_name": "Demo User",
                    "roles": ["user", "admin"],
                },
            ),
            "system": Principal(
                id="system",
                type="system",
                attributes={
                    "display_name": "System",
                    "roles": ["system"],
                },
            ),
        }

    async def authenticate(self, credentials: dict[str, Any]) -> Session | None:
        user_id = credentials.get("user_id", "demo-user")
        principal = self._users.get(user_id)
        if principal:
            session = Session(
                id=_generate_id(),
                principal=principal,
                created_at=_utc_now(),
            )
            self._sessions[session.id] = session
            return session
        return None

    async def validate_session(self, session_id: str) -> Session | None:
        session = self._sessions.get(session_id)
        if session and not session.is_expired:
            return session
        return None

    async def invalidate_session(self, session_id: str) -> bool:
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False


class MockAuthorizer(Authorizer):
    """Mock authorizer that allows everything for demo."""

    def _get_roles(self, principal: Principal) -> list[str]:
        """Extract roles from principal attributes."""
        return principal.attributes.get("roles", [])

    async def authorize(
        self,
        principal: Principal,
        action: str,
        resource: str,
    ) -> bool:
        roles = self._get_roles(principal)
        # Demo: admin can do anything, users have limited access
        if "admin" in roles or "system" in roles:
            return True
        # Regular users can only read
        return action in ("read", "list", "view")

    async def get_permissions(
        self,
        principal: Principal,
        resource: str,
    ) -> set[str]:
        roles = self._get_roles(principal)
        if "admin" in roles or "system" in roles:
            return {"read", "write", "delete", "admin"}
        return {"read", "list", "view"}


class MockTokenProvider(TokenProvider):
    """Mock token provider."""

    def __init__(self) -> None:
        self._tokens: dict[str, dict[str, Any]] = {}
        self._revoked: set[str] = set()

    async def generate(
        self,
        principal: Principal,
        expires_in_seconds: int | None = None,
    ) -> TokenPair:
        from datetime import timedelta

        access_token = f"mock-access-{_generate_id()[:8]}"
        refresh_token = f"mock-refresh-{_generate_id()[:8]}"

        expires = expires_in_seconds or 3600
        access_expires = _utc_now() + timedelta(seconds=expires)
        refresh_expires = _utc_now() + timedelta(seconds=expires * 24)

        self._tokens[access_token] = {
            "principal_id": principal.id,
            "principal_type": principal.type,
            "token_type": "access",
            "expires_at": access_expires.isoformat(),
        }
        self._tokens[refresh_token] = {
            "principal_id": principal.id,
            "principal_type": principal.type,
            "token_type": "refresh",
            "expires_at": refresh_expires.isoformat(),
        }

        return TokenPair(
            access_token=access_token,
            refresh_token=refresh_token,
            access_expires_at=access_expires,
            refresh_expires_at=refresh_expires,
        )

    async def validate(self, token: str) -> Principal:
        if token in self._revoked:
            raise ValueError("Token has been revoked")
        if token not in self._tokens:
            raise ValueError("Invalid token")
        data = self._tokens[token]
        return Principal(
            id=data["principal_id"],
            type=data["principal_type"],
        )

    async def refresh(self, refresh_token: str) -> TokenPair:
        if refresh_token in self._revoked:
            raise ValueError("Refresh token has been revoked")
        if refresh_token not in self._tokens:
            raise ValueError("Invalid refresh token")

        data = self._tokens[refresh_token]
        principal = Principal(id=data["principal_id"], type=data["principal_type"])

        # Revoke old refresh token
        await self.revoke(refresh_token)

        # Generate new token pair
        return await self.generate(principal)

    async def revoke(self, token: str) -> bool:
        if token in self._revoked:
            return False
        self._revoked.add(token)
        self._tokens.pop(token, None)
        return True


# =============================================================================
# POLICY MOCKS
# =============================================================================


class MockPolicyEvaluator(PolicyEvaluator):
    """Mock policy evaluator."""

    async def evaluate(self, context: PolicyContext) -> PolicyResult:
        """Evaluate all policies - always allow for demo."""
        return PolicyResult(
            decision=PolicyDecision.ALLOW,
            policy_id="default",
            reason="Demo policy - always allow",
        )

    async def evaluate_policy(
        self,
        policy_id: str,
        context: PolicyContext,
    ) -> PolicyResult:
        """Evaluate a specific policy - always allow for demo."""
        return PolicyResult(
            decision=PolicyDecision.ALLOW,
            policy_id=policy_id,
            reason=f"Demo policy {policy_id} - always allow",
        )


class MockRateLimiter(RateLimiter):
    """Mock rate limiter that never limits."""

    def __init__(self) -> None:
        self._counts: dict[str, int] = {}

    def _get_status(self, key: str, config: RateLimitConfig) -> RateLimitStatus:
        """Generate rate limit status."""
        from datetime import timedelta
        count = self._counts.get(key, 0)
        return RateLimitStatus(
            key=key,
            limit=config.max_requests,
            remaining=max(0, config.max_requests - count),
            reset_at=_utc_now() + timedelta(seconds=config.window_seconds),
        )

    async def check(self, key: str, config: RateLimitConfig) -> RateLimitStatus:
        """Check rate limit status without consuming."""
        return self._get_status(key, config)

    async def acquire(
        self,
        key: str,
        config: RateLimitConfig,
        cost: int = 1,
    ) -> RateLimitStatus:
        """Acquire rate limit tokens."""
        self._counts[key] = self._counts.get(key, 0) + cost
        return self._get_status(key, config)

    async def reset(self, key: str) -> bool:
        """Reset a rate limit."""
        if key in self._counts:
            del self._counts[key]
            return True
        return False


class MockFeatureFlagProvider:
    """
    Mock feature flag provider.

    Note: FeatureFlagProvider is a Protocol, so we just need to implement
    the expected methods without inheriting.
    """

    def __init__(self) -> None:
        self._flags: dict[str, Any] = {
            "demo-feature": True,
            "experimental": False,
            "max-items": 100,
            "theme": "dark",
        }

    async def get_flag(self, key: str, context: FeatureFlagContext) -> Any | None:
        """Get the value of a feature flag."""
        return self._flags.get(key)

    async def get_bool(
        self,
        key: str,
        context: FeatureFlagContext,
        default: bool = False,
    ) -> bool:
        """Get a boolean flag value."""
        value = self._flags.get(key)
        if value is None:
            return default
        return bool(value)

    async def get_string(
        self,
        key: str,
        context: FeatureFlagContext,
        default: str = "",
    ) -> str:
        """Get a string flag value."""
        value = self._flags.get(key)
        if value is None:
            return default
        return str(value)

    async def get_int(
        self,
        key: str,
        context: FeatureFlagContext,
        default: int = 0,
    ) -> int:
        """Get an integer flag value."""
        value = self._flags.get(key)
        if value is None:
            return default
        return int(value)


# =============================================================================
# TELEMETRY MOCKS
# =============================================================================


class MockLogger(Logger):
    """Mock logger that collects log entries."""

    def __init__(self) -> None:
        self.entries: list[dict[str, Any]] = []

    def log(
        self,
        level: LogLevel,
        message: str,
        **context: Any,
    ) -> None:
        self.entries.append({
            "level": level.value,
            "message": message,
            "context": context,
            "timestamp": _utc_now().isoformat(),
        })

    def debug(self, message: str, **context: Any) -> None:
        self.log(LogLevel.DEBUG, message, **context)

    def info(self, message: str, **context: Any) -> None:
        self.log(LogLevel.INFO, message, **context)

    def warning(self, message: str, **context: Any) -> None:
        self.log(LogLevel.WARNING, message, **context)

    def error(self, message: str, **context: Any) -> None:
        self.log(LogLevel.ERROR, message, **context)


class MockLoggerFactory(LoggerFactory):
    """Mock logger factory that creates named loggers."""

    def __init__(self) -> None:
        self._loggers: dict[str, MockLogger] = {}
        self._level = LogLevel.DEBUG
        # Create a default logger for easy access
        self._default = MockLogger()

    def get_logger(self, name: str) -> Logger:
        """Get or create a named logger."""
        if name not in self._loggers:
            self._loggers[name] = MockLogger()
        return self._loggers[name]

    def set_level(self, level: LogLevel) -> None:
        """Set global log level."""
        self._level = level

    @property
    def entries(self) -> list[dict[str, Any]]:
        """Get all entries from all loggers."""
        all_entries = list(self._default.entries)
        for logger in self._loggers.values():
            all_entries.extend(logger.entries)
        return all_entries


class MockSpan(Span):
    """Mock span implementation."""

    def __init__(
        self,
        name: str,
        trace_id: str,
        span_id: str,
        parent_span_id: str | None = None,
        attributes: dict[str, Any] | None = None,
    ) -> None:
        self._name = name
        self._context = SpanContext(
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=parent_span_id,
        )
        self._attributes: dict[str, Any] = attributes or {}
        self._status = SpanStatus.UNSET
        self._status_description: str | None = None
        self._events: list[dict[str, Any]] = []
        self._ended = False
        self._start_time = _utc_now()
        self._end_time: datetime | None = None

    @property
    def context(self) -> SpanContext:
        """Get the span context."""
        return self._context

    @property
    def name(self) -> str:
        return self._name

    def set_attribute(self, key: str, value: Any) -> None:
        """Set a span attribute."""
        self._attributes[key] = value

    def set_status(self, status: SpanStatus, description: str | None = None) -> None:
        """Set the span status."""
        self._status = status
        self._status_description = description

    def add_event(
        self,
        name: str,
        attributes: dict[str, Any] | None = None,
    ) -> None:
        """Add an event to the span."""
        self._events.append({
            "name": name,
            "timestamp": _utc_now().isoformat(),
            "attributes": attributes or {},
        })

    def record_exception(self, exception: Exception) -> None:
        """Record an exception on the span."""
        self._events.append({
            "name": "exception",
            "timestamp": _utc_now().isoformat(),
            "attributes": {
                "exception.type": type(exception).__name__,
                "exception.message": str(exception),
            },
        })
        self._status = SpanStatus.ERROR
        self._status_description = str(exception)

    def end(self) -> None:
        """End the span."""
        self._ended = True
        self._end_time = _utc_now()


class MockTracer(Tracer):
    """Mock tracer that collects spans."""

    def __init__(self) -> None:
        self.spans: list[MockSpan] = []
        self._current_trace_id: str | None = None
        self._current_span: MockSpan | None = None

    def start_span(
        self,
        name: str,
        parent: SpanContext | None = None,
        attributes: dict[str, Any] | None = None,
    ) -> Span:
        """Start a new span."""
        if self._current_trace_id is None:
            self._current_trace_id = _generate_id()[:16]

        span_id = _generate_id()[:16]
        parent_span_id = parent.span_id if parent else None

        span = MockSpan(
            name=name,
            trace_id=self._current_trace_id,
            span_id=span_id,
            parent_span_id=parent_span_id,
            attributes=attributes,
        )
        self.spans.append(span)
        self._current_span = span
        return span

    @contextmanager
    def span(
        self,
        name: str,
        attributes: dict[str, Any] | None = None,
    ) -> Generator[Span, None, None]:
        """Context manager for span lifecycle."""
        span = self.start_span(name, attributes=attributes)
        try:
            yield span
        except Exception as e:
            span.record_exception(e)
            raise
        finally:
            span.end()

    def get_current_span(self) -> Span | None:
        """Get the current active span."""
        return self._current_span

    def inject_context(self, carrier: dict[str, str]) -> None:
        """Inject trace context into a carrier."""
        if self._current_span:
            ctx = self._current_span.context
            carrier["traceparent"] = f"00-{ctx.trace_id}-{ctx.span_id}-00"

    def extract_context(self, carrier: dict[str, str]) -> SpanContext | None:
        """Extract trace context from a carrier."""
        traceparent = carrier.get("traceparent")
        if not traceparent:
            return None
        parts = traceparent.split("-")
        if len(parts) >= 3:
            return SpanContext(
                trace_id=parts[1],
                span_id=parts[2],
            )
        return None


class MockMetricsRegistry(MetricsRegistry):
    """Mock metrics registry that collects metrics."""

    def __init__(self) -> None:
        self.counters: dict[str, int] = {}
        self.gauges: dict[str, float] = {}
        self.histograms: dict[str, list[float]] = {}

    def counter(self, name: str, value: int = 1, **labels: str) -> None:
        key = f"{name}:{labels}"
        self.counters[key] = self.counters.get(key, 0) + value

    def gauge(self, name: str, value: float, **labels: str) -> None:
        key = f"{name}:{labels}"
        self.gauges[key] = value

    def histogram(self, name: str, value: float, **labels: str) -> None:
        key = f"{name}:{labels}"
        if key not in self.histograms:
            self.histograms[key] = []
        self.histograms[key].append(value)


class MockTelemetryProvider(TelemetryProvider):
    """Mock telemetry provider combining logger factory, tracer, and metrics."""

    def __init__(self) -> None:
        self._logger_factory = MockLoggerFactory()
        self._tracer = MockTracer()
        self._metrics = MockMetricsRegistry()

    @property
    def logger_factory(self) -> LoggerFactory:
        """Get the logger factory."""
        return self._logger_factory

    @property
    def logger(self) -> MockLoggerFactory:
        """Convenience accessor for demo (returns factory for entry access)."""
        return self._logger_factory

    @property
    def tracer(self) -> Tracer:
        """Get the tracer."""
        return self._tracer

    @property
    def metrics(self) -> MetricsRegistry:
        """Get the metrics registry."""
        return self._metrics

    def shutdown(self) -> None:
        """Shutdown and flush all telemetry."""
        pass  # No-op for mock


# =============================================================================
# EVENT MOCKS
# =============================================================================


class MockEventPublisher(EventPublisher):
    """Mock event publisher that stores events in memory."""

    def __init__(self) -> None:
        self.published: list[Event] = []

    async def publish(self, event: Event) -> str:
        self.published.append(event)
        return event.metadata.event_id

    async def publish_many(self, events: list[Event]) -> list[str]:
        ids = []
        for event in events:
            ids.append(await self.publish(event))
        return ids

    async def publish_delayed(self, event: Event, delay_seconds: int) -> str:
        # For mock, just publish immediately
        return await self.publish(event)


class MockEventBus(EventBus):
    """Mock event bus for in-process events."""

    def __init__(self) -> None:
        self.events: list[Event] = []
        self._handlers: dict[str, list[Any]] = {}
        self._subscriptions: dict[str, Subscription] = {}

    async def publish(self, event: Event) -> list[DeliveryResult]:
        self.events.append(event)
        results = []

        # Deliver to matching handlers
        for topic, handlers in self._handlers.items():
            if self._matches_topic(event.type, topic):
                for handler in handlers:
                    try:
                        await handler(event)
                        results.append(DeliveryResult(
                            success=True,
                            event_id=event.metadata.event_id,
                        ))
                    except Exception as e:
                        results.append(DeliveryResult(
                            success=False,
                            event_id=event.metadata.event_id,
                            error=str(e),
                        ))

        return results

    async def subscribe(self, topic: str, handler: Any) -> Subscription:
        if topic not in self._handlers:
            self._handlers[topic] = []
        self._handlers[topic].append(handler)

        sub = Subscription(
            id=_generate_id(),
            topic=topic,
            handler_name=handler.__name__ if hasattr(handler, "__name__") else "handler",
        )
        self._subscriptions[sub.id] = sub
        return sub

    async def unsubscribe(self, subscription_id: str) -> bool:
        if subscription_id in self._subscriptions:
            sub = self._subscriptions.pop(subscription_id)
            if sub.topic in self._handlers:
                # Remove handler (simplified)
                pass
            return True
        return False

    def _matches_topic(self, event_type: str, topic: str) -> bool:
        if topic == "*":
            return True
        if topic.endswith(".*"):
            prefix = topic[:-2]
            return event_type.startswith(prefix)
        return event_type == topic


# =============================================================================
# PROVIDER MOCKS
# =============================================================================


class MockCompletionProvider(CompletionProvider):
    """Mock completion provider that returns deterministic responses."""

    def __init__(self, config: ProviderConfig) -> None:
        super().__init__(config)
        self._call_count = 0

    def _validate_config(self) -> None:
        # No validation needed for mock
        pass

    @property
    def name(self) -> str:
        return "mock"

    @property
    def capabilities(self) -> CapabilitySet:
        return CapabilitySet.from_capabilities(
            Capability.TEXT_COMPLETION,
            Capability.STREAMING,
            Capability.FUNCTION_CALLING,
        )

    async def complete(
        self,
        prompt: str,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> CompletionResponse:
        self._call_count += 1
        return CompletionResponse(
            content=f"Mock response #{self._call_count} to: {prompt[:50]}...",
            model=self.config.model or "mock-model-1",
            provider=self.name,
            usage=TokenUsage(
                prompt_tokens=len(prompt.split()),
                completion_tokens=10,
                total_tokens=len(prompt.split()) + 10,
            ),
            finish_reason=FinishReason.STOP,
        )

    async def complete_with_tools(
        self,
        prompt: str,
        tools: list[dict[str, Any]],
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> CompletionResponse:
        return await self.complete(prompt, system_prompt, **kwargs)

    async def stream(
        self,
        prompt: str,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        response = await self.complete(prompt, system_prompt, **kwargs)
        for word in response.content.split():
            yield word + " "


class MockEmbeddingProvider(EmbeddingProvider):
    """Mock embedding provider that returns deterministic embeddings."""

    def __init__(self, config: EmbeddingConfig) -> None:
        super().__init__(config)

    def _validate_config(self) -> None:
        pass

    @property
    def name(self) -> str:
        return "mock"

    @property
    def default_model(self) -> str:
        return "mock-embed-1"

    @property
    def dimensions(self) -> int:
        return 384

    async def embed(self, texts: Sequence[str]) -> EmbeddingResult:
        # Generate deterministic embeddings based on text hash
        embeddings = []
        for text in texts:
            # Simple deterministic embedding based on text
            import hashlib
            h = hashlib.sha256(text.encode()).digest()
            # Convert bytes to floats in range [-1, 1]
            embedding = tuple(
                (b / 127.5) - 1.0 for b in h[:self.dimensions] * (self.dimensions // 32 + 1)
            )[:self.dimensions]
            embeddings.append(embedding)

        return EmbeddingResult(
            embeddings=tuple(embeddings),
            model=self.config.model or self.default_model,
            provider=self.name,
            dimensions=self.dimensions,
            usage=TokenUsage(
                prompt_tokens=sum(len(t.split()) for t in texts),
                total_tokens=sum(len(t.split()) for t in texts),
            ),
        )


# =============================================================================
# AUDIT STORE MOCK
# =============================================================================


class MockAuditStore:
    """Mock audit store that collects audit records in memory."""

    def __init__(self) -> None:
        self.records: list[AuditRecord] = []

    def append(self, record: AuditRecord) -> str:
        self.records.append(record)
        return record.record_id

    def query(
        self,
        event_type: str | None = None,
        limit: int = 100,
    ) -> list[AuditRecord]:
        results = self.records
        if event_type:
            results = [r for r in results if r.event_type == event_type]
        return results[:limit]

    def count(self) -> int:
        return len(self.records)


# =============================================================================
# DEMO CONTEXT
# =============================================================================


@dataclass
class DemoContext:
    """
    Context object containing all mock adapters for the demo.

    Provides a single point of access to all Core services.
    """

    # Storage
    kv_store: MockKeyValueStore = field(default_factory=MockKeyValueStore)
    doc_store: MockDocumentStore = field(default_factory=MockDocumentStore)

    # Auth
    authenticator: MockAuthenticator = field(default_factory=MockAuthenticator)
    authorizer: MockAuthorizer = field(default_factory=MockAuthorizer)
    token_provider: MockTokenProvider = field(default_factory=MockTokenProvider)

    # Policy
    policy_evaluator: MockPolicyEvaluator = field(default_factory=MockPolicyEvaluator)
    rate_limiter: MockRateLimiter = field(default_factory=MockRateLimiter)
    feature_flags: MockFeatureFlagProvider = field(default_factory=MockFeatureFlagProvider)

    # Telemetry
    telemetry: MockTelemetryProvider = field(default_factory=MockTelemetryProvider)

    # Events
    event_publisher: MockEventPublisher = field(default_factory=MockEventPublisher)
    event_bus: MockEventBus = field(default_factory=MockEventBus)

    # Audit
    audit_store: MockAuditStore = field(default_factory=MockAuditStore)

    # Providers
    completion_provider: MockCompletionProvider | None = None
    embedding_provider: MockEmbeddingProvider | None = None

    def __post_init__(self) -> None:
        if self.completion_provider is None:
            self.completion_provider = MockCompletionProvider(
                ProviderConfig(name="mock", model="mock-model-1")
            )
        if self.embedding_provider is None:
            self.embedding_provider = MockEmbeddingProvider(
                EmbeddingConfig(model="mock-embed-1")
            )

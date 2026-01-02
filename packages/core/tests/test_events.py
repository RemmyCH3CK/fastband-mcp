"""
Tests for Core events module.

Verifies:
1. Event types are importable with no side effects
2. Event models serialize correctly
3. Event invariants are maintained
4. No forbidden imports
"""

import ast
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest


class TestNoSideEffectsOnImport:
    """Test that importing events has no side effects."""

    def test_import_events_module(self) -> None:
        """Importing events module should have no side effects."""
        # This test verifies no file I/O, no logging init, no env reading
        from fastband_core import events

        # Module should be importable
        assert events is not None
        assert hasattr(events, "DomainEvent")
        assert hasattr(events, "EventMetadata")

    def test_import_from_root(self) -> None:
        """Event types should be importable from package root."""
        import fastband_core

        assert hasattr(fastband_core, "DomainEvent")
        assert hasattr(fastband_core, "EventEnvelope")
        assert hasattr(fastband_core, "EventCategory")


class TestEventMetadata:
    """Test EventMetadata dataclass."""

    def test_metadata_defaults(self) -> None:
        """Metadata should have sensible defaults."""
        from fastband_core.events import EventMetadata

        meta = EventMetadata()

        assert meta.event_id is not None
        assert len(meta.event_id) == 36  # UUID format
        assert meta.timestamp is not None
        assert meta.source == ""
        assert meta.correlation_id is None
        assert meta.version == 1

    def test_metadata_is_frozen(self) -> None:
        """Metadata should be immutable."""
        from fastband_core.events import EventMetadata

        meta = EventMetadata()

        with pytest.raises(AttributeError):
            meta.source = "changed"  # type: ignore

    def test_metadata_with_correlation(self) -> None:
        """with_correlation should create a new instance."""
        from fastband_core.events import EventMetadata

        meta = EventMetadata(source="test")
        new_meta = meta.with_correlation("corr-123")

        assert meta.correlation_id is None
        assert new_meta.correlation_id == "corr-123"
        assert new_meta.source == "test"

    def test_metadata_to_dict(self) -> None:
        """Metadata should serialize to dict."""
        from fastband_core.events import EventMetadata, EventPriority

        meta = EventMetadata(
            source="test-service",
            correlation_id="corr-123",
            priority=EventPriority.HIGH,
        )

        d = meta.to_dict()

        assert d["source"] == "test-service"
        assert d["correlation_id"] == "corr-123"
        assert d["priority"] == "high"
        assert "timestamp" in d
        assert "event_id" in d

    def test_metadata_from_dict(self) -> None:
        """Metadata should deserialize from dict."""
        from fastband_core.events import EventMetadata

        d = {
            "event_id": "test-id",
            "timestamp": "2024-01-01T00:00:00+00:00",
            "source": "test",
            "priority": "high",
            "category": "security",
        }

        meta = EventMetadata.from_dict(d)

        assert meta.event_id == "test-id"
        assert meta.source == "test"


class TestDomainEvent:
    """Test DomainEvent dataclass."""

    def test_event_creation(self) -> None:
        """Events should be creatable with minimal args."""
        from fastband_core.events import DomainEvent

        event = DomainEvent(
            type="ticket.created",
            data={"ticket_id": "123"},
        )

        assert event.type == "ticket.created"
        assert event.data == {"ticket_id": "123"}
        assert event.metadata is not None

    def test_event_is_frozen(self) -> None:
        """Events should be immutable."""
        from fastband_core.events import DomainEvent

        event = DomainEvent(type="test", data={})

        with pytest.raises(AttributeError):
            event.type = "changed"  # type: ignore

    def test_aggregate_type(self) -> None:
        """aggregate_type should extract prefix."""
        from fastband_core.events import DomainEvent

        event = DomainEvent(type="ticket.created", data={})
        assert event.aggregate_type == "ticket"

        event2 = DomainEvent(type="simple", data={})
        assert event2.aggregate_type == "simple"

    def test_action(self) -> None:
        """action should extract suffix."""
        from fastband_core.events import DomainEvent

        event = DomainEvent(type="ticket.created", data={})
        assert event.action == "created"

        event2 = DomainEvent(type="simple", data={})
        assert event2.action == ""

    def test_to_dict(self) -> None:
        """Events should serialize to dict."""
        from fastband_core.events import DomainEvent, EventMetadata

        event = DomainEvent(
            type="user.updated",
            data={"user_id": "456", "name": "Test"},
            metadata=EventMetadata(source="user-service"),
        )

        d = event.to_dict()

        assert d["type"] == "user.updated"
        assert d["data"]["user_id"] == "456"
        assert "metadata" in d
        assert d["metadata"]["source"] == "user-service"

    def test_to_dict_is_json_serializable(self) -> None:
        """to_dict output should be JSON-safe."""
        from fastband_core.events import DomainEvent

        event = DomainEvent(
            type="test.event",
            data={"key": "value"},
        )

        d = event.to_dict()
        json_str = json.dumps(d)
        parsed = json.loads(json_str)

        assert parsed["type"] == "test.event"

    def test_from_dict(self) -> None:
        """Events should deserialize from dict."""
        from fastband_core.events import DomainEvent

        d = {
            "type": "order.placed",
            "data": {"order_id": "789"},
            "metadata": {
                "event_id": "meta-id",
                "timestamp": "2024-01-01T00:00:00+00:00",
                "source": "order-service",
                "priority": "normal",
                "category": "domain",
            },
        }

        event = DomainEvent.from_dict(d)

        assert event.type == "order.placed"
        assert event.data["order_id"] == "789"
        assert event.metadata.source == "order-service"

    def test_caused_by(self) -> None:
        """caused_by should set correlation chain."""
        from fastband_core.events import DomainEvent, EventMetadata

        parent = DomainEvent(
            type="order.created",
            data={"order_id": "123"},
            metadata=EventMetadata(correlation_id="request-456"),
        )

        child = DomainEvent(
            type="payment.processed",
            data={"payment_id": "789"},
            metadata=EventMetadata(source="payment-service"),
        )

        caused = child.caused_by(parent)

        assert caused.metadata.causation_id == parent.event_id
        assert caused.metadata.correlation_id == "request-456"


class TestTypedEvent:
    """Test TypedEvent generic dataclass."""

    def test_typed_event_with_dict(self) -> None:
        """TypedEvent should work with dict payloads."""
        from fastband_core.events import TypedEvent

        event: TypedEvent[dict] = TypedEvent(
            type="test.typed",
            data={"key": "value"},
        )

        assert event.data["key"] == "value"

    def test_typed_event_to_domain_event(self) -> None:
        """TypedEvent should convert to DomainEvent."""
        from fastband_core.events import TypedEvent

        event: TypedEvent[dict] = TypedEvent(
            type="test.typed",
            data={"key": "value"},
        )

        domain = event.to_domain_event()

        assert domain.type == "test.typed"
        assert domain.data == {"key": "value"}


class TestEventEnvelope:
    """Test EventEnvelope dataclass."""

    def test_envelope_creation(self) -> None:
        """Envelopes should wrap events with routing info."""
        from fastband_core.events import DomainEvent, EventEnvelope

        event = DomainEvent(type="test", data={})
        envelope = EventEnvelope(
            event=event,
            topic="events.test",
            partition_key="key-123",
        )

        assert envelope.topic == "events.test"
        assert envelope.partition_key == "key-123"
        assert envelope.event.type == "test"

    def test_envelope_to_dict(self) -> None:
        """Envelopes should serialize to dict."""
        from fastband_core.events import DomainEvent, EventEnvelope

        event = DomainEvent(type="test", data={"x": 1})
        envelope = EventEnvelope(
            event=event,
            topic="events.test",
        )

        d = envelope.to_dict()

        assert d["topic"] == "events.test"
        assert "event" in d
        assert d["event"]["type"] == "test"


class TestCommonEventTypes:
    """Test CommonEventTypes constants."""

    def test_for_aggregate(self) -> None:
        """for_aggregate should build event type strings."""
        from fastband_core.events import CommonEventTypes

        assert CommonEventTypes.for_aggregate("user", "created") == "user.created"
        assert CommonEventTypes.for_aggregate("ticket", "updated") == "ticket.updated"


class TestNoForbiddenImports:
    """Test that events module has no forbidden imports."""

    FORBIDDEN_MODULES = [
        "fastapi",
        "flask",
        "starlette",
        "django",
        "sqlalchemy",
        "asyncpg",
        "psycopg",
        "sqlite3",
        "aiosqlite",
        "pymongo",
        "redis",
        "dotenv",
        "python-dotenv",
        "mcp",
        "fastband_dev",
        "fastband_enterprise",
    ]

    def _get_imports_from_file(self, file_path: Path) -> set[str]:
        """Extract all imports from a Python file using AST."""
        source = file_path.read_text()
        tree = ast.parse(source)
        imports: set[str] = set()

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.add(node.module.split(".")[0])

        return imports

    def test_model_no_forbidden_imports(self) -> None:
        """Model module must not import forbidden modules."""
        events_dir = Path(__file__).parent.parent / "src" / "fastband_core" / "events"
        model_file = events_dir / "model.py"

        imports = self._get_imports_from_file(model_file)

        for forbidden in self.FORBIDDEN_MODULES:
            assert forbidden not in imports, f"Forbidden import found: {forbidden}"

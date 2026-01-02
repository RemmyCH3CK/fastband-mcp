"""
Tests for Core audit module.

Verifies:
1. Audit types are importable with no side effects
2. Audit models serialize correctly
3. Audit invariants are maintained
4. No forbidden imports
"""

import ast
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest


class TestNoSideEffectsOnImport:
    """Test that importing audit has no side effects."""

    def test_import_audit_module(self) -> None:
        """Importing audit module should have no side effects."""
        from fastband_core import audit

        assert audit is not None
        assert hasattr(audit, "AuditRecord")
        assert hasattr(audit, "AuditActor")

    def test_import_from_root(self) -> None:
        """Audit types should be importable from package root."""
        import fastband_core

        assert hasattr(fastband_core, "AuditRecord")
        assert hasattr(fastband_core, "AuditActor")
        assert hasattr(fastband_core, "AuditSeverity")


class TestAuditSeverity:
    """Test AuditSeverity enum."""

    def test_severity_values(self) -> None:
        """Severity should have expected values."""
        from fastband_core.audit import AuditSeverity

        assert AuditSeverity.INFO.value == "info"
        assert AuditSeverity.WARNING.value == "warning"
        assert AuditSeverity.CRITICAL.value == "critical"


class TestAuditCategory:
    """Test AuditCategory enum."""

    def test_category_values(self) -> None:
        """Category should have expected values."""
        from fastband_core.audit import AuditCategory

        assert AuditCategory.AUTHENTICATION.value == "authentication"
        assert AuditCategory.SECURITY.value == "security"
        assert AuditCategory.DATA_ACCESS.value == "data_access"


class TestAuditActor:
    """Test AuditActor dataclass."""

    def test_actor_defaults(self) -> None:
        """Actor should have sensible defaults."""
        from fastband_core.audit import AuditActor

        actor = AuditActor()

        assert actor.actor_id is None
        assert actor.actor_type == "user"

    def test_actor_is_frozen(self) -> None:
        """Actor should be immutable."""
        from fastband_core.audit import AuditActor

        actor = AuditActor(actor_id="user-123")

        with pytest.raises(AttributeError):
            actor.actor_id = "changed"  # type: ignore

    def test_actor_system(self) -> None:
        """system() factory should create system actor."""
        from fastband_core.audit import AuditActor

        actor = AuditActor.system()

        assert actor.actor_type == "system"
        assert actor.display_name == "System"

    def test_actor_anonymous(self) -> None:
        """anonymous() factory should create anonymous actor."""
        from fastband_core.audit import AuditActor

        actor = AuditActor.anonymous(ip_address="192.168.1.1")

        assert actor.actor_type == "anonymous"
        assert actor.ip_address == "192.168.1.1"

    def test_actor_to_dict(self) -> None:
        """Actor should serialize to dict."""
        from fastband_core.audit import AuditActor

        actor = AuditActor(
            actor_id="user-123",
            display_name="Test User",
            ip_address="10.0.0.1",
        )

        d = actor.to_dict()

        assert d["actor_id"] == "user-123"
        assert d["display_name"] == "Test User"
        assert d["ip_address"] == "10.0.0.1"

    def test_actor_from_dict(self) -> None:
        """Actor should deserialize from dict."""
        from fastband_core.audit import AuditActor

        d = {
            "actor_id": "user-456",
            "actor_type": "service",
            "display_name": "API Service",
        }

        actor = AuditActor.from_dict(d)

        assert actor.actor_id == "user-456"
        assert actor.actor_type == "service"


class TestAuditResource:
    """Test AuditResource dataclass."""

    def test_resource_creation(self) -> None:
        """Resource should be creatable."""
        from fastband_core.audit import AuditResource

        resource = AuditResource(
            resource_type="ticket",
            resource_id="ticket-123",
            resource_name="Bug fix #123",
        )

        assert resource.resource_type == "ticket"
        assert resource.resource_id == "ticket-123"

    def test_resource_is_frozen(self) -> None:
        """Resource should be immutable."""
        from fastband_core.audit import AuditResource

        resource = AuditResource(resource_type="test")

        with pytest.raises(AttributeError):
            resource.resource_type = "changed"  # type: ignore

    def test_resource_to_dict(self) -> None:
        """Resource should serialize to dict."""
        from fastband_core.audit import AuditResource

        resource = AuditResource(
            resource_type="config",
            resource_id="api_key",
        )

        d = resource.to_dict()

        assert d["resource_type"] == "config"
        assert d["resource_id"] == "api_key"


class TestAuditRecord:
    """Test AuditRecord dataclass."""

    def test_record_defaults(self) -> None:
        """Record should have sensible defaults."""
        from fastband_core.audit import AuditRecord, AuditOutcome, AuditSeverity

        record = AuditRecord(event_type="test", action="test_action")

        assert record.record_id is not None
        assert len(record.record_id) == 36  # UUID format
        assert record.timestamp is not None
        assert record.severity == AuditSeverity.INFO
        assert record.outcome == AuditOutcome.SUCCESS

    def test_record_is_frozen(self) -> None:
        """Record should be immutable."""
        from fastband_core.audit import AuditRecord

        record = AuditRecord(event_type="test", action="action")

        with pytest.raises(AttributeError):
            record.event_type = "changed"  # type: ignore

    def test_record_create_factory(self) -> None:
        """create() factory should validate required fields."""
        from fastband_core.audit import AuditRecord

        # Should raise for empty event_type
        with pytest.raises(ValueError, match="event_type is required"):
            AuditRecord.create(event_type="", action="test")

        # Should raise for empty action
        with pytest.raises(ValueError, match="action is required"):
            AuditRecord.create(event_type="test", action="")

        # Should succeed with required fields
        record = AuditRecord.create(
            event_type="auth:login",
            action="authenticate",
        )
        assert record.event_type == "auth:login"

    def test_record_with_actor(self) -> None:
        """Record should include actor info."""
        from fastband_core.audit import AuditActor, AuditCategory, AuditRecord

        actor = AuditActor(actor_id="user-123", ip_address="192.168.1.1")
        record = AuditRecord.create(
            event_type="auth:login",
            action="login",
            actor=actor,
            category=AuditCategory.AUTHENTICATION,
        )

        assert record.actor is not None
        assert record.actor.actor_id == "user-123"
        assert record.category == AuditCategory.AUTHENTICATION

    def test_record_with_resource(self) -> None:
        """Record should include resource info."""
        from fastband_core.audit import AuditRecord, AuditResource

        resource = AuditResource(resource_type="backup", resource_id="backup-456")
        record = AuditRecord.create(
            event_type="backup:created",
            action="create",
            resource=resource,
        )

        assert record.resource is not None
        assert record.resource.resource_type == "backup"

    def test_record_to_dict(self) -> None:
        """Record should serialize to dict."""
        from fastband_core.audit import (
            AuditActor,
            AuditCategory,
            AuditOutcome,
            AuditRecord,
            AuditSeverity,
        )

        record = AuditRecord.create(
            event_type="config:changed",
            action="update",
            actor=AuditActor(actor_id="admin"),
            category=AuditCategory.CONFIGURATION,
            severity=AuditSeverity.WARNING,
            details={"key": "api_key", "masked": True},
            tags=["sensitive", "config"],
        )

        d = record.to_dict()

        assert d["event_type"] == "config:changed"
        assert d["action"] == "update"
        assert d["category"] == "configuration"
        assert d["severity"] == "warning"
        assert d["outcome"] == "success"
        assert d["actor"]["actor_id"] == "admin"
        assert d["details"]["key"] == "api_key"
        assert "sensitive" in d["tags"]
        assert "record_id" in d
        assert "timestamp" in d

    def test_record_to_dict_is_json_serializable(self) -> None:
        """to_dict output should be JSON-safe."""
        from fastband_core.audit import AuditRecord

        record = AuditRecord.create(
            event_type="test:event",
            action="test",
        )

        d = record.to_dict()
        json_str = json.dumps(d)
        parsed = json.loads(json_str)

        assert parsed["event_type"] == "test:event"

    def test_record_from_dict(self) -> None:
        """Record should deserialize from dict."""
        from fastband_core.audit import AuditRecord

        d = {
            "record_id": "rec-123",
            "timestamp": "2024-01-01T00:00:00+00:00",
            "event_type": "security:blocked",
            "action": "block",
            "category": "security",
            "severity": "critical",
            "outcome": "denied",
            "actor": {"actor_id": "attacker", "ip_address": "1.2.3.4"},
        }

        record = AuditRecord.from_dict(d)

        assert record.record_id == "rec-123"
        assert record.event_type == "security:blocked"
        assert record.actor is not None
        assert record.actor.ip_address == "1.2.3.4"

    def test_is_security_event(self) -> None:
        """is_security_event should detect security events."""
        from fastband_core.audit import AuditCategory, AuditRecord, AuditSeverity

        # Security category
        record1 = AuditRecord.create(
            event_type="test",
            action="test",
            category=AuditCategory.SECURITY,
        )
        assert record1.is_security_event is True

        # Critical severity
        record2 = AuditRecord.create(
            event_type="test",
            action="test",
            severity=AuditSeverity.CRITICAL,
        )
        assert record2.is_security_event is True

        # security: prefix
        record3 = AuditRecord.create(
            event_type="security:rate_limited",
            action="block",
        )
        assert record3.is_security_event is True

        # Normal event
        record4 = AuditRecord.create(
            event_type="data:read",
            action="read",
        )
        assert record4.is_security_event is False

    def test_is_failure(self) -> None:
        """is_failure should detect failed outcomes."""
        from fastband_core.audit import AuditOutcome, AuditRecord

        for outcome in [AuditOutcome.FAILURE, AuditOutcome.ERROR, AuditOutcome.DENIED]:
            record = AuditRecord(
                event_type="test",
                action="test",
                outcome=outcome,
            )
            assert record.is_failure is True

        record_success = AuditRecord(
            event_type="test",
            action="test",
            outcome=AuditOutcome.SUCCESS,
        )
        assert record_success.is_failure is False


class TestAuditEventTypes:
    """Test AuditEventTypes constants."""

    def test_auth_constants(self) -> None:
        """Auth event types should exist."""
        from fastband_core.audit import AuditEventTypes

        assert AuditEventTypes.AUTH_LOGIN == "auth:login"
        assert AuditEventTypes.AUTH_FAILURE == "auth:failure"

    def test_security_constants(self) -> None:
        """Security event types should exist."""
        from fastband_core.audit import AuditEventTypes

        assert AuditEventTypes.SECURITY_RATE_LIMITED == "security:rate_limited"
        assert AuditEventTypes.SECURITY_ACCESS_DENIED == "security:access_denied"


class TestNoForbiddenImports:
    """Test that audit module has no forbidden imports."""

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
        "logging",  # No logging initialization on import!
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
        audit_dir = Path(__file__).parent.parent / "src" / "fastband_core" / "audit"
        model_file = audit_dir / "model.py"

        imports = self._get_imports_from_file(model_file)

        for forbidden in self.FORBIDDEN_MODULES:
            assert forbidden not in imports, f"Forbidden import found: {forbidden}"

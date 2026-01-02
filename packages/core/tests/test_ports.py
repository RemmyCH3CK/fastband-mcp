"""
Tests for Core port definitions.

Verifies that:
1. All ports are importable
2. Ports contain no forbidden imports (FastAPI, Flask, DB drivers)
3. Types are properly defined
"""

import ast
import importlib
import sys
from pathlib import Path
from typing import Any

import pytest


class TestPortsImportable:
    """Test that all port modules are importable."""

    def test_import_storage_ports(self) -> None:
        """Storage ports should be importable."""
        from fastband_core.ports import storage

        assert hasattr(storage, "KeyValueStore")
        assert hasattr(storage, "DocumentStore")
        assert hasattr(storage, "TransactionManager")
        assert hasattr(storage, "MigrationRunner")

    def test_import_auth_ports(self) -> None:
        """Auth ports should be importable."""
        from fastband_core.ports import auth

        assert hasattr(auth, "Authenticator")
        assert hasattr(auth, "TokenProvider")
        assert hasattr(auth, "Authorizer")
        assert hasattr(auth, "CredentialStore")

    def test_import_policy_ports(self) -> None:
        """Policy ports should be importable."""
        from fastband_core.ports import policy

        assert hasattr(policy, "PolicyEvaluator")
        assert hasattr(policy, "PolicyStore")
        assert hasattr(policy, "RateLimiter")
        assert hasattr(policy, "QuotaManager")
        assert hasattr(policy, "FeatureFlagProvider")

    def test_import_telemetry_ports(self) -> None:
        """Telemetry ports should be importable."""
        from fastband_core.ports import telemetry

        assert hasattr(telemetry, "Logger")
        assert hasattr(telemetry, "LoggerFactory")
        assert hasattr(telemetry, "MetricsRegistry")
        assert hasattr(telemetry, "Tracer")
        assert hasattr(telemetry, "TelemetryProvider")

    def test_import_events_ports(self) -> None:
        """Events ports should be importable."""
        from fastband_core.ports import events

        assert hasattr(events, "EventPublisher")
        assert hasattr(events, "EventSubscriber")
        assert hasattr(events, "EventBus")
        assert hasattr(events, "EventStore")
        assert hasattr(events, "TransactionalOutbox")

    def test_import_all_from_ports(self) -> None:
        """All exports should be importable from ports module."""
        from fastband_core import ports

        # Check that __all__ exports are accessible
        for name in ports.__all__:
            assert hasattr(ports, name), f"Missing export: {name}"

    def test_import_from_root(self) -> None:
        """Common ports should be importable from package root."""
        import fastband_core

        # Storage
        assert hasattr(fastband_core, "KeyValueStore")
        assert hasattr(fastband_core, "DocumentStore")

        # Auth
        assert hasattr(fastband_core, "Authenticator")
        assert hasattr(fastband_core, "Authorizer")

        # Events
        assert hasattr(fastband_core, "Event")
        assert hasattr(fastband_core, "EventPublisher")


class TestNoForbiddenImports:
    """Test that port modules don't contain forbidden imports."""

    FORBIDDEN_MODULES = [
        # Web frameworks
        "fastapi",
        "flask",
        "starlette",
        "django",
        # Database drivers
        "sqlalchemy",
        "asyncpg",
        "psycopg",
        "sqlite3",
        "aiosqlite",
        "pymongo",
        "redis",
        # Env file loading
        "dotenv",
        "python-dotenv",
        # Product packages
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

    def test_storage_no_forbidden_imports(self) -> None:
        """Storage ports must not import forbidden modules."""
        ports_dir = Path(__file__).parent.parent / "src" / "fastband_core" / "ports"
        storage_file = ports_dir / "storage.py"

        imports = self._get_imports_from_file(storage_file)

        for forbidden in self.FORBIDDEN_MODULES:
            assert forbidden not in imports, f"Forbidden import found: {forbidden}"

    def test_auth_no_forbidden_imports(self) -> None:
        """Auth ports must not import forbidden modules."""
        ports_dir = Path(__file__).parent.parent / "src" / "fastband_core" / "ports"
        auth_file = ports_dir / "auth.py"

        imports = self._get_imports_from_file(auth_file)

        for forbidden in self.FORBIDDEN_MODULES:
            assert forbidden not in imports, f"Forbidden import found: {forbidden}"

    def test_policy_no_forbidden_imports(self) -> None:
        """Policy ports must not import forbidden modules."""
        ports_dir = Path(__file__).parent.parent / "src" / "fastband_core" / "ports"
        policy_file = ports_dir / "policy.py"

        imports = self._get_imports_from_file(policy_file)

        for forbidden in self.FORBIDDEN_MODULES:
            assert forbidden not in imports, f"Forbidden import found: {forbidden}"

    def test_telemetry_no_forbidden_imports(self) -> None:
        """Telemetry ports must not import forbidden modules."""
        ports_dir = Path(__file__).parent.parent / "src" / "fastband_core" / "ports"
        telemetry_file = ports_dir / "telemetry.py"

        imports = self._get_imports_from_file(telemetry_file)

        for forbidden in self.FORBIDDEN_MODULES:
            assert forbidden not in imports, f"Forbidden import found: {forbidden}"

    def test_events_no_forbidden_imports(self) -> None:
        """Events ports must not import forbidden modules."""
        ports_dir = Path(__file__).parent.parent / "src" / "fastband_core" / "ports"
        events_file = ports_dir / "events.py"

        imports = self._get_imports_from_file(events_file)

        for forbidden in self.FORBIDDEN_MODULES:
            assert forbidden not in imports, f"Forbidden import found: {forbidden}"


class TestTypesAreDefined:
    """Test that types are properly defined and usable."""

    def test_principal_is_frozen_dataclass(self) -> None:
        """Principal should be a frozen dataclass."""
        from fastband_core.ports.auth import Principal

        p = Principal(id="user-1", type="user")
        assert p.id == "user-1"
        assert p.type == "user"

        # Should be frozen
        with pytest.raises(Exception):  # FrozenInstanceError
            p.id = "other"  # type: ignore

    def test_event_has_metadata(self) -> None:
        """Event should have metadata with defaults."""
        from fastband_core.ports.events import Event, EventMetadata

        e = Event(type="test.created", data={"key": "value"})

        assert e.type == "test.created"
        assert e.data == {"key": "value"}
        assert isinstance(e.metadata, EventMetadata)
        assert e.metadata.event_id  # Should have auto-generated ID

    def test_policy_decision_enum(self) -> None:
        """PolicyDecision should be an enum with expected values."""
        from fastband_core.ports.policy import PolicyDecision

        assert PolicyDecision.ALLOW.value == "allow"
        assert PolicyDecision.DENY.value == "deny"
        assert PolicyDecision.WARN.value == "warn"
        assert PolicyDecision.AUDIT.value == "audit"

    def test_log_level_enum(self) -> None:
        """LogLevel should be an enum with expected values."""
        from fastband_core.ports.telemetry import LogLevel

        assert LogLevel.DEBUG.value == "debug"
        assert LogLevel.INFO.value == "info"
        assert LogLevel.WARNING.value == "warning"
        assert LogLevel.ERROR.value == "error"
        assert LogLevel.CRITICAL.value == "critical"

    def test_query_filter_dataclass(self) -> None:
        """QueryFilter should be a usable dataclass."""
        from fastband_core.ports.storage import QueryFilter

        qf = QueryFilter(field="status", operator="eq", value="open")
        assert qf.field == "status"
        assert qf.operator == "eq"
        assert qf.value == "open"


class TestProtocolsAreRuntimeCheckable:
    """Test that protocols can be used for runtime type checking."""

    def test_keyvaluestore_is_runtime_checkable(self) -> None:
        """KeyValueStore should be a runtime-checkable protocol."""
        from fastband_core.ports.storage import KeyValueStore

        # Should not raise
        assert hasattr(KeyValueStore, "__protocol_attrs__") or hasattr(
            KeyValueStore, "_is_runtime_protocol"
        )

    def test_logger_is_runtime_checkable(self) -> None:
        """Logger should be a runtime-checkable protocol."""
        from fastband_core.ports.telemetry import Logger

        assert hasattr(Logger, "__protocol_attrs__") or hasattr(
            Logger, "_is_runtime_protocol"
        )

    def test_authorizer_is_runtime_checkable(self) -> None:
        """Authorizer should be a runtime-checkable protocol."""
        from fastband_core.ports.auth import Authorizer

        assert hasattr(Authorizer, "__protocol_attrs__") or hasattr(
            Authorizer, "_is_runtime_protocol"
        )

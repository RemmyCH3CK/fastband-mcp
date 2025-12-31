"""
Comprehensive tests for the Agent Operations Log module.

Tests cover:
- EventType enum
- LogEntry dataclass (creation, serialization, TTL, expiration)
- OpsLog class (CRUD, filtering, rotation, archival)
- Coordination features (holds, clearances, conflicts)
- Global singleton function
"""

import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

from fastband.agents.ops_log import (
    EventType,
    LogEntry,
    OpsLog,
    get_ops_log,
)

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def tmp_log_path(tmp_path):
    """Create a temporary log path."""
    return tmp_path / ".fastband" / "ops_log.json"


@pytest.fixture
def tmp_archive_dir(tmp_path):
    """Create a temporary archive directory."""
    return tmp_path / ".fastband" / "ops_log_archive"


@pytest.fixture
def ops_log(tmp_log_path, tmp_archive_dir):
    """Create an OpsLog instance with temporary paths."""
    return OpsLog(
        log_path=tmp_log_path,
        archive_dir=tmp_archive_dir,
        auto_rotate=False,
        auto_expire=False,
    )


@pytest.fixture
def ops_log_with_auto(tmp_log_path, tmp_archive_dir):
    """Create an OpsLog instance with auto features enabled."""
    return OpsLog(
        log_path=tmp_log_path,
        archive_dir=tmp_archive_dir,
        auto_rotate=True,
        auto_expire=True,
    )


# =============================================================================
# EVENT TYPE TESTS
# =============================================================================


class TestEventType:
    """Tests for EventType enum."""

    def test_all_event_types_exist(self):
        """Test that all expected event types exist."""
        assert EventType.CLEARANCE_GRANTED.value == "clearance_granted"
        assert EventType.HOLD.value == "hold"
        assert EventType.REBUILD_REQUESTED.value == "rebuild_requested"
        assert EventType.REBUILD_COMPLETE.value == "rebuild_complete"
        assert EventType.TICKET_CLAIMED.value == "ticket_claimed"
        assert EventType.TICKET_COMPLETED.value == "ticket_completed"
        assert EventType.STATUS_UPDATE.value == "status_update"
        assert EventType.CONFLICT_DETECTED.value == "conflict_detected"
        assert EventType.AGENT_STARTED.value == "agent_started"
        assert EventType.AGENT_STOPPED.value == "agent_stopped"
        assert EventType.ERROR.value == "error"

    def test_event_type_is_string(self):
        """Test that EventType inherits from str."""
        assert isinstance(EventType.HOLD, str)
        assert EventType.HOLD == "hold"

    def test_event_type_count(self):
        """Test that we have the expected number of event types."""
        assert len(EventType) == 11


# =============================================================================
# LOG ENTRY TESTS
# =============================================================================


class TestLogEntry:
    """Tests for LogEntry dataclass."""

    def test_create_minimal(self):
        """Test creating a LogEntry with minimal fields."""
        entry = LogEntry(
            id="test123",
            timestamp="2025-12-30T10:00:00Z",
            agent="test-agent",
            event_type="agent_started",
            message="Agent started",
        )
        assert entry.id == "test123"
        assert entry.agent == "test-agent"
        assert entry.event_type == "agent_started"
        assert entry.message == "Agent started"
        assert entry.ticket_id is None
        assert entry.metadata == {}
        assert entry.ttl_seconds is None
        assert entry.expires_at is None

    def test_create_full(self):
        """Test creating a LogEntry with all fields."""
        entry = LogEntry(
            id="test123",
            timestamp="2025-12-30T10:00:00Z",
            agent="test-agent",
            event_type="ticket_claimed",
            message="Claimed ticket",
            ticket_id="FB-001",
            metadata={"priority": "high"},
            ttl_seconds=3600,
            expires_at="2025-12-30T11:00:00Z",
        )
        assert entry.ticket_id == "FB-001"
        assert entry.metadata == {"priority": "high"}
        assert entry.ttl_seconds == 3600
        assert entry.expires_at == "2025-12-30T11:00:00Z"

    def test_create_factory_with_enum(self):
        """Test LogEntry.create() factory with EventType enum."""
        entry = LogEntry.create(
            agent="test-agent",
            event_type=EventType.AGENT_STARTED,
            message="Started",
        )
        assert entry.id  # Auto-generated
        assert entry.timestamp  # Auto-generated
        assert entry.agent == "test-agent"
        assert entry.event_type == "agent_started"
        assert entry.message == "Started"

    def test_create_factory_with_string(self):
        """Test LogEntry.create() factory with string event type."""
        entry = LogEntry.create(
            agent="test-agent",
            event_type="custom_event",
            message="Custom message",
        )
        assert entry.event_type == "custom_event"

    def test_create_factory_with_ttl(self):
        """Test LogEntry.create() with TTL."""
        entry = LogEntry.create(
            agent="test-agent",
            event_type=EventType.REBUILD_REQUESTED,
            message="Rebuild",
            ttl_seconds=3600,
        )
        assert entry.ttl_seconds == 3600
        assert entry.expires_at is not None

    def test_create_factory_with_ticket_id(self):
        """Test LogEntry.create() with ticket_id."""
        entry = LogEntry.create(
            agent="test-agent",
            event_type=EventType.TICKET_CLAIMED,
            message="Claimed",
            ticket_id="FB-001",
        )
        assert entry.ticket_id == "FB-001"

    def test_create_factory_with_metadata(self):
        """Test LogEntry.create() with metadata."""
        entry = LogEntry.create(
            agent="test-agent",
            event_type=EventType.STATUS_UPDATE,
            message="Update",
            metadata={"key": "value"},
        )
        assert entry.metadata == {"key": "value"}

    def test_to_dict(self):
        """Test converting LogEntry to dictionary."""
        entry = LogEntry(
            id="test123",
            timestamp="2025-12-30T10:00:00Z",
            agent="test-agent",
            event_type="agent_started",
            message="Started",
            ticket_id="FB-001",
            metadata={"key": "value"},
        )
        data = entry.to_dict()
        assert isinstance(data, dict)
        assert data["id"] == "test123"
        assert data["agent"] == "test-agent"
        assert data["ticket_id"] == "FB-001"
        assert data["metadata"] == {"key": "value"}

    def test_from_dict(self):
        """Test creating LogEntry from dictionary."""
        data = {
            "id": "test123",
            "timestamp": "2025-12-30T10:00:00Z",
            "agent": "test-agent",
            "event_type": "agent_started",
            "message": "Started",
            "ticket_id": "FB-001",
            "metadata": {"key": "value"},
            "ttl_seconds": 3600,
            "expires_at": "2025-12-30T11:00:00Z",
        }
        entry = LogEntry.from_dict(data)
        assert entry.id == "test123"
        assert entry.agent == "test-agent"
        assert entry.ticket_id == "FB-001"
        assert entry.ttl_seconds == 3600

    def test_from_dict_minimal(self):
        """Test creating LogEntry from minimal dictionary."""
        data = {
            "id": "test123",
            "timestamp": "2025-12-30T10:00:00Z",
            "agent": "test-agent",
            "event_type": "agent_started",
            "message": "Started",
        }
        entry = LogEntry.from_dict(data)
        assert entry.ticket_id is None
        assert entry.metadata == {}
        assert entry.ttl_seconds is None

    def test_is_expired_no_ttl(self):
        """Test is_expired returns False when no TTL set."""
        entry = LogEntry(
            id="test123",
            timestamp="2025-12-30T10:00:00Z",
            agent="test-agent",
            event_type="agent_started",
            message="Started",
        )
        assert entry.is_expired() is False

    def test_is_expired_not_expired(self):
        """Test is_expired returns False when entry hasn't expired."""
        future = (datetime.utcnow() + timedelta(hours=1)).isoformat() + "Z"
        entry = LogEntry(
            id="test123",
            timestamp="2025-12-30T10:00:00Z",
            agent="test-agent",
            event_type="agent_started",
            message="Started",
            expires_at=future,
        )
        assert entry.is_expired() is False

    def test_is_expired_expired(self):
        """Test is_expired returns True when entry has expired."""
        past = (datetime.utcnow() - timedelta(hours=1)).isoformat() + "Z"
        entry = LogEntry(
            id="test123",
            timestamp="2025-12-30T10:00:00Z",
            agent="test-agent",
            event_type="agent_started",
            message="Started",
            expires_at=past,
        )
        assert entry.is_expired() is True

    def test_is_expired_invalid_format(self):
        """Test is_expired handles invalid expires_at format."""
        entry = LogEntry(
            id="test123",
            timestamp="2025-12-30T10:00:00Z",
            agent="test-agent",
            event_type="agent_started",
            message="Started",
            expires_at="invalid-date",
        )
        assert entry.is_expired() is False

    def test_formatted(self):
        """Test formatted string representation."""
        entry = LogEntry(
            id="test123",
            timestamp="2025-12-30T10:00:00Z",
            agent="test-agent",
            event_type="agent_started",
            message="Agent started successfully",
        )
        formatted = entry.formatted()
        assert "[2025-12-30T10:00:00Z]" in formatted
        assert "[test-agent]" in formatted
        assert "agent_started" in formatted
        assert "Agent started successfully" in formatted

    def test_formatted_with_ticket(self):
        """Test formatted string with ticket ID."""
        entry = LogEntry(
            id="test123",
            timestamp="2025-12-30T10:00:00Z",
            agent="test-agent",
            event_type="ticket_claimed",
            message="Claimed ticket",
            ticket_id="FB-001",
        )
        formatted = entry.formatted()
        assert "[Ticket #FB-001]" in formatted


# =============================================================================
# OPS LOG INITIALIZATION TESTS
# =============================================================================


class TestOpsLogInit:
    """Tests for OpsLog initialization."""

    def test_init_defaults(self, tmp_path):
        """Test initialization with defaults."""
        ops_log = OpsLog()
        assert ops_log.log_path == Path(".fastband/ops_log.json")
        assert ops_log.archive_dir == Path(".fastband/ops_log_archive")
        assert ops_log.auto_rotate is True
        assert ops_log.auto_expire is True

    def test_init_custom_paths(self, tmp_log_path, tmp_archive_dir):
        """Test initialization with custom paths."""
        ops_log = OpsLog(log_path=tmp_log_path, archive_dir=tmp_archive_dir)
        assert ops_log.log_path == tmp_log_path
        assert ops_log.archive_dir == tmp_archive_dir

    def test_init_disable_auto_features(self, tmp_log_path, tmp_archive_dir):
        """Test initialization with auto features disabled."""
        ops_log = OpsLog(
            log_path=tmp_log_path,
            archive_dir=tmp_archive_dir,
            auto_rotate=False,
            auto_expire=False,
        )
        assert ops_log.auto_rotate is False
        assert ops_log.auto_expire is False

    def test_init_creates_empty_log(self, ops_log):
        """Test that initialization creates empty log."""
        assert ops_log.count() == 0

    def test_init_loads_existing_log(self, tmp_log_path, tmp_archive_dir):
        """Test that initialization loads existing log."""
        # Create a log file first
        tmp_log_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "metadata": {"version": "1.0"},
            "entries": [
                {
                    "id": "test123",
                    "timestamp": "2025-12-30T10:00:00Z",
                    "agent": "test-agent",
                    "event_type": "agent_started",
                    "message": "Started",
                }
            ],
        }
        with open(tmp_log_path, "w") as f:
            json.dump(data, f)

        # Now create OpsLog - it should load the existing entry
        ops_log = OpsLog(
            log_path=tmp_log_path,
            archive_dir=tmp_archive_dir,
            auto_expire=False,
        )
        assert ops_log.count() == 1

    def test_init_handles_corrupted_file(self, tmp_log_path, tmp_archive_dir):
        """Test that initialization handles corrupted log file."""
        tmp_log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(tmp_log_path, "w") as f:
            f.write("invalid json{{{")

        ops_log = OpsLog(log_path=tmp_log_path, archive_dir=tmp_archive_dir)
        assert ops_log.count() == 0


# =============================================================================
# OPS LOG WRITE/READ TESTS
# =============================================================================


class TestOpsLogWriteRead:
    """Tests for OpsLog write and read operations."""

    def test_write_entry(self, ops_log):
        """Test writing an entry."""
        entry = ops_log.write_entry(
            agent="test-agent",
            event_type=EventType.AGENT_STARTED,
            message="Agent started",
        )
        assert entry.id
        assert entry.agent == "test-agent"
        assert entry.event_type == "agent_started"
        assert ops_log.count() == 1

    def test_write_entry_with_string_event_type(self, ops_log):
        """Test writing an entry with string event type."""
        entry = ops_log.write_entry(
            agent="test-agent",
            event_type="custom_event",
            message="Custom message",
        )
        assert entry.event_type == "custom_event"

    def test_write_entry_with_metadata(self, ops_log):
        """Test writing an entry with metadata."""
        entry = ops_log.write_entry(
            agent="test-agent",
            event_type=EventType.STATUS_UPDATE,
            message="Update",
            metadata={"status": "running"},
        )
        assert entry.metadata == {"status": "running"}

    def test_write_entry_with_ticket_id(self, ops_log):
        """Test writing an entry with ticket_id."""
        entry = ops_log.write_entry(
            agent="test-agent",
            event_type=EventType.TICKET_CLAIMED,
            message="Claimed",
            ticket_id="FB-001",
        )
        assert entry.ticket_id == "FB-001"

    def test_write_entry_with_ttl(self, ops_log):
        """Test writing an entry with TTL."""
        entry = ops_log.write_entry(
            agent="test-agent",
            event_type=EventType.REBUILD_REQUESTED,
            message="Rebuild",
            ttl_seconds=3600,
        )
        assert entry.ttl_seconds == 3600
        assert entry.expires_at is not None

    def test_write_entry_persists(self, tmp_log_path, tmp_archive_dir):
        """Test that written entries are persisted to file."""
        ops_log = OpsLog(
            log_path=tmp_log_path,
            archive_dir=tmp_archive_dir,
            auto_rotate=False,
        )
        ops_log.write_entry(
            agent="test-agent",
            event_type=EventType.AGENT_STARTED,
            message="Started",
        )

        # Create a new OpsLog instance and verify entry is loaded
        ops_log2 = OpsLog(
            log_path=tmp_log_path,
            archive_dir=tmp_archive_dir,
            auto_expire=False,
        )
        assert ops_log2.count() == 1

    def test_read_entries_empty(self, ops_log):
        """Test reading entries from empty log."""
        entries = ops_log.read_entries()
        assert entries == []

    def test_read_entries_all(self, ops_log):
        """Test reading all entries."""
        ops_log.write_entry("agent-1", EventType.AGENT_STARTED, "Started 1")
        ops_log.write_entry("agent-2", EventType.AGENT_STARTED, "Started 2")
        ops_log.write_entry("agent-1", EventType.STATUS_UPDATE, "Update")

        entries = ops_log.read_entries()
        assert len(entries) == 3

    def test_read_entries_ordered_newest_first(self, ops_log):
        """Test that entries are returned newest first."""
        ops_log.write_entry("agent-1", EventType.AGENT_STARTED, "First")
        time.sleep(0.01)  # Ensure different timestamps
        ops_log.write_entry("agent-2", EventType.AGENT_STARTED, "Second")
        time.sleep(0.01)
        ops_log.write_entry("agent-3", EventType.AGENT_STARTED, "Third")

        entries = ops_log.read_entries()
        assert entries[0].message == "Third"
        assert entries[2].message == "First"

    def test_read_entries_filter_by_agent(self, ops_log):
        """Test filtering entries by agent."""
        ops_log.write_entry("agent-1", EventType.AGENT_STARTED, "Started 1")
        ops_log.write_entry("agent-2", EventType.AGENT_STARTED, "Started 2")
        ops_log.write_entry("agent-1", EventType.STATUS_UPDATE, "Update")

        entries = ops_log.read_entries(agent="agent-1")
        assert len(entries) == 2
        assert all(e.agent == "agent-1" for e in entries)

    def test_read_entries_filter_by_event_type_enum(self, ops_log):
        """Test filtering entries by event type (enum)."""
        ops_log.write_entry("agent-1", EventType.AGENT_STARTED, "Started")
        ops_log.write_entry("agent-1", EventType.STATUS_UPDATE, "Update 1")
        ops_log.write_entry("agent-1", EventType.STATUS_UPDATE, "Update 2")

        entries = ops_log.read_entries(event_type=EventType.STATUS_UPDATE)
        assert len(entries) == 2
        assert all(e.event_type == "status_update" for e in entries)

    def test_read_entries_filter_by_event_type_string(self, ops_log):
        """Test filtering entries by event type (string)."""
        ops_log.write_entry("agent-1", EventType.AGENT_STARTED, "Started")
        ops_log.write_entry("agent-1", EventType.STATUS_UPDATE, "Update")

        entries = ops_log.read_entries(event_type="status_update")
        assert len(entries) == 1

    def test_read_entries_filter_by_ticket_id(self, ops_log):
        """Test filtering entries by ticket_id."""
        ops_log.write_entry(
            "agent-1", EventType.TICKET_CLAIMED, "Claimed 1", ticket_id="FB-001"
        )
        ops_log.write_entry(
            "agent-1", EventType.TICKET_CLAIMED, "Claimed 2", ticket_id="FB-002"
        )
        ops_log.write_entry(
            "agent-1", EventType.TICKET_COMPLETED, "Completed", ticket_id="FB-001"
        )

        entries = ops_log.read_entries(ticket_id="FB-001")
        assert len(entries) == 2
        assert all(e.ticket_id == "FB-001" for e in entries)

    def test_read_entries_limit(self, ops_log):
        """Test limiting number of entries returned."""
        for i in range(10):
            ops_log.write_entry("agent-1", EventType.STATUS_UPDATE, f"Update {i}")

        entries = ops_log.read_entries(limit=5)
        assert len(entries) == 5

    def test_read_entries_since_minutes(self, ops_log):
        """Test filtering by time (minutes)."""
        ops_log.write_entry("agent-1", EventType.AGENT_STARTED, "Started")

        entries = ops_log.read_entries(since="60m")
        assert len(entries) == 1

    def test_read_entries_since_hours(self, ops_log):
        """Test filtering by time (hours)."""
        ops_log.write_entry("agent-1", EventType.AGENT_STARTED, "Started")

        entries = ops_log.read_entries(since="1h")
        assert len(entries) == 1

    def test_read_entries_since_days(self, ops_log):
        """Test filtering by time (days)."""
        ops_log.write_entry("agent-1", EventType.AGENT_STARTED, "Started")

        entries = ops_log.read_entries(since="1d")
        assert len(entries) == 1

    def test_read_entries_since_iso(self, ops_log):
        """Test filtering by time (ISO format)."""
        ops_log.write_entry("agent-1", EventType.AGENT_STARTED, "Started")

        past = (datetime.utcnow() - timedelta(hours=1)).isoformat()
        entries = ops_log.read_entries(since=past)
        assert len(entries) == 1

    def test_read_entries_since_future(self, ops_log):
        """Test filtering by future time returns no entries."""
        ops_log.write_entry("agent-1", EventType.AGENT_STARTED, "Started")

        future = (datetime.utcnow() + timedelta(hours=1)).isoformat()
        entries = ops_log.read_entries(since=future)
        assert len(entries) == 0

    def test_read_entries_combined_filters(self, ops_log):
        """Test combining multiple filters."""
        ops_log.write_entry(
            "agent-1", EventType.TICKET_CLAIMED, "Claimed", ticket_id="FB-001"
        )
        ops_log.write_entry(
            "agent-2", EventType.TICKET_CLAIMED, "Claimed", ticket_id="FB-001"
        )
        ops_log.write_entry(
            "agent-1", EventType.STATUS_UPDATE, "Update", ticket_id="FB-001"
        )

        entries = ops_log.read_entries(
            agent="agent-1",
            event_type=EventType.TICKET_CLAIMED,
            ticket_id="FB-001",
        )
        assert len(entries) == 1


# =============================================================================
# OPS LOG EXPIRATION TESTS
# =============================================================================


class TestOpsLogExpiration:
    """Tests for OpsLog entry expiration."""

    def test_expired_entries_excluded(self, ops_log):
        """Test that expired entries are excluded by default."""
        past = (datetime.utcnow() - timedelta(hours=1)).isoformat() + "Z"
        ops_log._entries.append(
            LogEntry(
                id="expired",
                timestamp="2025-12-30T10:00:00Z",
                agent="test-agent",
                event_type="agent_started",
                message="Started",
                expires_at=past,
            )
        )
        ops_log.write_entry("agent-1", EventType.AGENT_STARTED, "Fresh")

        entries = ops_log.read_entries()
        assert len(entries) == 1
        assert entries[0].message == "Fresh"

    def test_expired_entries_included_when_requested(self, ops_log):
        """Test including expired entries when requested."""
        past = (datetime.utcnow() - timedelta(hours=1)).isoformat() + "Z"
        ops_log._entries.append(
            LogEntry(
                id="expired",
                timestamp="2025-12-30T10:00:00Z",
                agent="test-agent",
                event_type="agent_started",
                message="Started",
                expires_at=past,
            )
        )
        ops_log.write_entry("agent-1", EventType.AGENT_STARTED, "Fresh")

        entries = ops_log.read_entries(include_expired=True)
        assert len(entries) == 2

    def test_auto_expire_on_read(self, ops_log_with_auto):
        """Test auto-expire removes expired entries on read."""
        past = (datetime.utcnow() - timedelta(hours=1)).isoformat() + "Z"
        ops_log_with_auto._entries.append(
            LogEntry(
                id="expired",
                timestamp="2025-12-30T10:00:00Z",
                agent="test-agent",
                event_type="agent_started",
                message="Started",
                expires_at=past,
            )
        )
        ops_log_with_auto._entries.append(
            LogEntry.create("agent-1", EventType.AGENT_STARTED, "Fresh")
        )

        # Read triggers auto-expire
        entries = ops_log_with_auto.read_entries()

        # Expired entry should be removed from internal list
        assert ops_log_with_auto.count() == 1


# =============================================================================
# OPS LOG ROTATION TESTS
# =============================================================================


class TestOpsLogRotation:
    """Tests for OpsLog rotation."""

    def test_rotate_empty_log(self, ops_log):
        """Test rotating empty log returns None."""
        result = ops_log.rotate()
        assert result is None

    def test_rotate_creates_archive(self, ops_log):
        """Test rotation creates archive file."""
        ops_log.write_entry("agent-1", EventType.AGENT_STARTED, "Started")

        archive_path = ops_log.rotate(reason="test")

        assert archive_path is not None
        assert archive_path.exists()
        assert "test" in archive_path.name

    def test_rotate_clears_entries(self, ops_log):
        """Test rotation clears current entries."""
        ops_log.write_entry("agent-1", EventType.AGENT_STARTED, "Started")
        assert ops_log.count() == 1

        ops_log.rotate()

        assert ops_log.count() == 0

    def test_rotate_updates_last_rotation(self, ops_log):
        """Test rotation updates last_rotation timestamp."""
        ops_log.write_entry("agent-1", EventType.AGENT_STARTED, "Started")

        ops_log.rotate()

        assert ops_log._last_rotation is not None
        assert ops_log._metadata.get("last_rotation") is not None

    def test_should_rotate_size(self, tmp_log_path, tmp_archive_dir):
        """Test _should_rotate detects size threshold."""
        ops_log = OpsLog(
            log_path=tmp_log_path,
            archive_dir=tmp_archive_dir,
            auto_rotate=False,
        )

        # Write enough entries to exceed size threshold
        # First write some entries to create the file
        for i in range(100):
            ops_log.write_entry("agent-1", EventType.STATUS_UPDATE, "x" * 1000)

        # Mock the size check
        original_size = OpsLog.MAX_SIZE_BYTES
        OpsLog.MAX_SIZE_BYTES = 100  # Very small for testing

        should_rotate = ops_log._should_rotate()

        OpsLog.MAX_SIZE_BYTES = original_size  # Restore

        assert should_rotate is True

    def test_should_rotate_no_file(self, ops_log):
        """Test _should_rotate returns False when no log file."""
        assert ops_log._should_rotate() is False


# =============================================================================
# OPS LOG DIRECTIVE TESTS
# =============================================================================


class TestOpsLogDirectives:
    """Tests for OpsLog directive operations (holds/clearances)."""

    def test_issue_hold(self, ops_log):
        """Test issuing a hold directive."""
        entry = ops_log.issue_hold(
            agent="admin",
            affected_agents=["agent-1", "agent-2"],
            tickets=["FB-001"],
            reason="Conflict detected",
        )

        assert entry.event_type == "hold"
        assert entry.metadata["affected_agents"] == ["agent-1", "agent-2"]
        assert entry.metadata["tickets"] == ["FB-001"]
        assert entry.metadata["is_global"] is False

    def test_issue_global_hold(self, ops_log):
        """Test issuing a global hold directive."""
        entry = ops_log.issue_hold(
            agent="admin",
            affected_agents=["all"],
            tickets=None,
            reason="System maintenance",
        )

        assert entry.metadata["is_global"] is True
        assert entry.metadata["tickets"] == []

    def test_grant_clearance(self, ops_log):
        """Test granting clearance."""
        entry = ops_log.grant_clearance(
            agent="admin",
            granted_to=["agent-1", "agent-2"],
            tickets=["FB-001", "FB-002"],
            reason="Ready to proceed",
        )

        assert entry.event_type == "clearance_granted"
        assert entry.metadata["granted_to"] == ["agent-1", "agent-2"]
        assert entry.metadata["tickets"] == ["FB-001", "FB-002"]
        assert entry.metadata["reason"] == "Ready to proceed"

    def test_get_latest_directive_none(self, ops_log):
        """Test get_latest_directive when no directives exist."""
        ops_log.write_entry("agent-1", EventType.AGENT_STARTED, "Started")

        directive = ops_log.get_latest_directive()

        assert directive is None

    def test_get_latest_directive_hold(self, ops_log):
        """Test get_latest_directive returns hold."""
        ops_log.issue_hold("admin", ["agent-1"], reason="Test hold")

        directive = ops_log.get_latest_directive()

        assert directive is not None
        assert directive.event_type == "hold"

    def test_get_latest_directive_clearance(self, ops_log):
        """Test get_latest_directive returns clearance."""
        ops_log.grant_clearance("admin", ["agent-1"], ["FB-001"], "Test clearance")

        directive = ops_log.get_latest_directive()

        assert directive is not None
        assert directive.event_type == "clearance_granted"

    def test_get_latest_directive_returns_most_recent(self, ops_log):
        """Test get_latest_directive returns most recent directive."""
        ops_log.issue_hold("admin", ["agent-1"], reason="First")
        time.sleep(0.01)
        ops_log.grant_clearance("admin", ["agent-1"], ["FB-001"], "Second")
        time.sleep(0.01)
        ops_log.issue_hold("admin", ["agent-2"], reason="Third")

        directive = ops_log.get_latest_directive()

        assert directive.metadata["affected_agents"] == ["agent-2"]

    def test_get_latest_directive_excludes_expired(self, ops_log):
        """Test get_latest_directive excludes expired directives."""
        # Add expired hold
        past = (datetime.utcnow() - timedelta(hours=1)).isoformat() + "Z"
        ops_log._entries.append(
            LogEntry(
                id="expired-hold",
                timestamp="2025-12-30T10:00:00Z",
                agent="admin",
                event_type="hold",
                message="Expired hold",
                expires_at=past,
            )
        )

        directive = ops_log.get_latest_directive()

        assert directive is None


# =============================================================================
# OPS LOG TICKET OPERATIONS TESTS
# =============================================================================


class TestOpsLogTicketOperations:
    """Tests for OpsLog ticket-related operations."""

    def test_claim_ticket(self, ops_log):
        """Test claiming a ticket."""
        entry, conflicts = ops_log.claim_ticket("agent-1", "FB-001")

        assert entry.event_type == "ticket_claimed"
        assert entry.ticket_id == "FB-001"
        assert entry.metadata["conflicts_at_claim"] == 0
        assert conflicts == []

    def test_claim_ticket_with_conflict(self, ops_log):
        """Test claiming a ticket that has conflicts."""
        # First agent claims
        ops_log.claim_ticket("agent-1", "FB-001")

        # Second agent tries to claim same ticket
        entry, conflicts = ops_log.claim_ticket("agent-2", "FB-001")

        assert len(conflicts) == 1
        assert conflicts[0].agent == "agent-1"

    def test_claim_ticket_no_conflict_check(self, ops_log):
        """Test claiming without conflict check."""
        ops_log.claim_ticket("agent-1", "FB-001")

        entry, conflicts = ops_log.claim_ticket(
            "agent-2", "FB-001", check_conflicts=False
        )

        assert conflicts == []

    def test_complete_ticket(self, ops_log):
        """Test completing a ticket."""
        entry = ops_log.complete_ticket("agent-1", "FB-001")

        assert entry.event_type == "ticket_completed"
        assert entry.ticket_id == "FB-001"

    def test_complete_ticket_with_summary(self, ops_log):
        """Test completing a ticket with summary."""
        entry = ops_log.complete_ticket("agent-1", "FB-001", summary="Fixed the bug")

        assert "Fixed the bug" in entry.message
        assert entry.metadata["summary"] == "Fixed the bug"


# =============================================================================
# OPS LOG CONFLICT DETECTION TESTS
# =============================================================================


class TestOpsLogConflictDetection:
    """Tests for OpsLog conflict detection."""

    def test_detect_conflicts_none(self, ops_log):
        """Test detecting no conflicts."""
        conflicts = ops_log.detect_conflicts("FB-001", "agent-1")
        assert conflicts == []

    def test_detect_conflicts_claimed_by_other(self, ops_log):
        """Test detecting conflict when claimed by another agent."""
        ops_log.claim_ticket("agent-1", "FB-001")

        conflicts = ops_log.detect_conflicts("FB-001", "agent-2")

        assert len(conflicts) == 1
        assert conflicts[0].agent == "agent-1"

    def test_detect_conflicts_hold_on_ticket(self, ops_log):
        """Test detecting conflict when hold exists on ticket."""
        ops_log.issue_hold("admin", ["agent-1"], tickets=["FB-001"], reason="Hold")

        conflicts = ops_log.detect_conflicts("FB-001", "agent-1")

        assert len(conflicts) == 1
        assert conflicts[0].event_type == "hold"

    def test_detect_conflicts_global_hold(self, ops_log):
        """Test detecting conflict when global hold exists."""
        ops_log.issue_hold("admin", ["all"], tickets=None, reason="Global hold")

        conflicts = ops_log.detect_conflicts("FB-001", "agent-1")

        assert len(conflicts) == 1

    def test_detect_conflicts_own_claim(self, ops_log):
        """Test no conflict detected for own claim."""
        ops_log.claim_ticket("agent-1", "FB-001")

        conflicts = ops_log.detect_conflicts("FB-001", "agent-1")

        assert conflicts == []


# =============================================================================
# OPS LOG REBUILD ANNOUNCEMENT TESTS
# =============================================================================


class TestOpsLogRebuildAnnouncement:
    """Tests for OpsLog rebuild announcement."""

    def test_announce_rebuild_requested(self, ops_log):
        """Test announcing rebuild requested."""
        entry = ops_log.announce_rebuild(
            agent="agent-1",
            container="web-app",
            status="requested",
        )

        assert entry.event_type == "rebuild_requested"
        assert entry.metadata["container"] == "web-app"
        assert entry.metadata["status"] == "requested"
        assert entry.ttl_seconds == 3600

    def test_announce_rebuild_complete(self, ops_log):
        """Test announcing rebuild complete."""
        entry = ops_log.announce_rebuild(
            agent="agent-1",
            container="web-app",
            status="complete",
        )

        assert entry.event_type == "rebuild_complete"
        assert entry.metadata["status"] == "complete"

    def test_announce_rebuild_with_files(self, ops_log):
        """Test announcing rebuild with changed files."""
        entry = ops_log.announce_rebuild(
            agent="agent-1",
            container="web-app",
            files_changed=["app.py", "config.py"],
        )

        assert entry.metadata["files_changed"] == ["app.py", "config.py"]

    def test_announce_rebuild_with_ticket(self, ops_log):
        """Test announcing rebuild with ticket."""
        entry = ops_log.announce_rebuild(
            agent="agent-1",
            container="web-app",
            ticket_id="FB-001",
        )

        assert entry.ticket_id == "FB-001"


# =============================================================================
# OPS LOG ACTIVE AGENTS TESTS
# =============================================================================


class TestOpsLogActiveAgents:
    """Tests for OpsLog active agents tracking."""

    def test_check_active_agents_empty(self, ops_log):
        """Test checking active agents when none exist."""
        agents = ops_log.check_active_agents()
        assert agents == {}

    def test_check_active_agents_single(self, ops_log):
        """Test checking single active agent."""
        ops_log.write_entry("agent-1", EventType.AGENT_STARTED, "Started")

        agents = ops_log.check_active_agents()

        assert "agent-1" in agents
        assert agents["agent-1"]["last_action"] == "agent_started"
        assert agents["agent-1"]["activity_count"] == 1

    def test_check_active_agents_multiple(self, ops_log):
        """Test checking multiple active agents."""
        ops_log.write_entry("agent-1", EventType.AGENT_STARTED, "Started")
        ops_log.write_entry("agent-2", EventType.AGENT_STARTED, "Started")

        agents = ops_log.check_active_agents()

        assert len(agents) == 2
        assert "agent-1" in agents
        assert "agent-2" in agents

    def test_check_active_agents_tracks_ticket(self, ops_log):
        """Test that active agents tracks current ticket."""
        ops_log.write_entry(
            "agent-1", EventType.TICKET_CLAIMED, "Claimed", ticket_id="FB-001"
        )

        agents = ops_log.check_active_agents()

        assert agents["agent-1"]["current_ticket"] == "FB-001"

    def test_check_active_agents_clears_completed_ticket(self, ops_log):
        """Test that completed ticket clears current_ticket."""
        ops_log.write_entry(
            "agent-1", EventType.TICKET_CLAIMED, "Claimed", ticket_id="FB-001"
        )
        ops_log.write_entry(
            "agent-1", EventType.TICKET_COMPLETED, "Completed", ticket_id="FB-001"
        )

        agents = ops_log.check_active_agents()

        assert agents["agent-1"]["current_ticket"] is None

    def test_check_active_agents_activity_count(self, ops_log):
        """Test activity count accumulation."""
        ops_log.write_entry("agent-1", EventType.AGENT_STARTED, "Started")
        ops_log.write_entry("agent-1", EventType.STATUS_UPDATE, "Update 1")
        ops_log.write_entry("agent-1", EventType.STATUS_UPDATE, "Update 2")

        agents = ops_log.check_active_agents()

        assert agents["agent-1"]["activity_count"] == 3


# =============================================================================
# OPS LOG UTILITY TESTS
# =============================================================================


class TestOpsLogUtilities:
    """Tests for OpsLog utility methods."""

    def test_count_empty(self, ops_log):
        """Test count on empty log."""
        assert ops_log.count() == 0

    def test_count_with_entries(self, ops_log):
        """Test count with entries."""
        ops_log.write_entry("agent-1", EventType.AGENT_STARTED, "Started 1")
        ops_log.write_entry("agent-2", EventType.AGENT_STARTED, "Started 2")
        assert ops_log.count() == 2

    def test_clear(self, ops_log):
        """Test clearing the log."""
        ops_log.write_entry("agent-1", EventType.AGENT_STARTED, "Started")
        ops_log.write_entry("agent-2", EventType.AGENT_STARTED, "Started")

        cleared = ops_log.clear()

        assert cleared == 2
        assert ops_log.count() == 0

    def test_get_stats_empty(self, ops_log):
        """Test getting stats on empty log."""
        stats = ops_log.get_stats()

        assert stats["current_entries"] == 0
        assert stats["event_counts"] == {}
        assert stats["agent_counts"] == {}
        assert stats["archive_files"] == 0

    def test_get_stats_with_entries(self, ops_log):
        """Test getting stats with entries."""
        ops_log.write_entry("agent-1", EventType.AGENT_STARTED, "Started")
        ops_log.write_entry("agent-1", EventType.STATUS_UPDATE, "Update")
        ops_log.write_entry("agent-2", EventType.AGENT_STARTED, "Started")

        stats = ops_log.get_stats()

        assert stats["current_entries"] == 3
        assert stats["event_counts"]["agent_started"] == 2
        assert stats["event_counts"]["status_update"] == 1
        assert stats["agent_counts"]["agent-1"] == 2
        assert stats["agent_counts"]["agent-2"] == 1

    def test_get_stats_with_archive(self, ops_log):
        """Test getting stats counts archives."""
        ops_log.write_entry("agent-1", EventType.AGENT_STARTED, "Started")
        ops_log.rotate(reason="test1")
        ops_log.write_entry("agent-1", EventType.AGENT_STARTED, "Started")
        ops_log.rotate(reason="test2")

        stats = ops_log.get_stats()

        assert stats["archive_files"] == 2

    def test_prune_no_archives(self, ops_log):
        """Test pruning when no archives exist."""
        deleted = ops_log.prune()
        assert deleted == 0

    def test_prune_keeps_recent(self, ops_log):
        """Test pruning keeps recent archives."""
        ops_log.write_entry("agent-1", EventType.AGENT_STARTED, "Started")
        ops_log.rotate(reason="test")

        deleted = ops_log.prune(keep_days=30)

        assert deleted == 0


# =============================================================================
# GLOBAL SINGLETON TESTS
# =============================================================================


class TestGetOpsLog:
    """Tests for get_ops_log global function."""

    def test_get_singleton(self, tmp_path):
        """Test getting the singleton instance."""
        with patch("fastband.agents.ops_log._ops_log", None):
            log1 = get_ops_log(project_path=tmp_path)
            log2 = get_ops_log(project_path=tmp_path)

            assert log1 is log2

    def test_get_singleton_reset(self, tmp_path):
        """Test resetting the singleton instance."""
        with patch("fastband.agents.ops_log._ops_log", None):
            log1 = get_ops_log(project_path=tmp_path)
            log2 = get_ops_log(project_path=tmp_path, reset=True)

            assert log1 is not log2

    def test_get_singleton_default_path(self):
        """Test getting singleton with default path."""
        with patch("fastband.agents.ops_log._ops_log", None):
            log = get_ops_log(reset=True)

            assert log.log_path.name == "ops_log.json"
            assert ".fastband" in str(log.log_path)


# =============================================================================
# TIME FILTER PARSING TESTS
# =============================================================================


class TestTimeFilterParsing:
    """Tests for time filter parsing."""

    def test_parse_minutes(self, ops_log):
        """Test parsing minutes filter."""
        result = ops_log._parse_time_filter("30m")
        assert result is not None
        assert datetime.utcnow() - result < timedelta(minutes=31)

    def test_parse_hours(self, ops_log):
        """Test parsing hours filter."""
        result = ops_log._parse_time_filter("2h")
        assert result is not None
        assert datetime.utcnow() - result < timedelta(hours=3)

    def test_parse_days(self, ops_log):
        """Test parsing days filter."""
        result = ops_log._parse_time_filter("7d")
        assert result is not None
        assert datetime.utcnow() - result < timedelta(days=8)

    def test_parse_iso(self, ops_log):
        """Test parsing ISO format."""
        result = ops_log._parse_time_filter("2025-12-30T10:00:00")
        assert result is not None
        assert result.year == 2025
        assert result.month == 12
        assert result.day == 30

    def test_parse_iso_with_z(self, ops_log):
        """Test parsing ISO format with Z suffix."""
        result = ops_log._parse_time_filter("2025-12-30T10:00:00Z")
        assert result is not None
        assert result.year == 2025

    def test_parse_invalid(self, ops_log):
        """Test parsing invalid filter returns None."""
        result = ops_log._parse_time_filter("invalid")
        assert result is None

    def test_parse_invalid_number(self, ops_log):
        """Test parsing invalid number in filter."""
        result = ops_log._parse_time_filter("abch")
        assert result is None

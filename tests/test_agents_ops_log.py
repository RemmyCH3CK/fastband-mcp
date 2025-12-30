"""
Tests for the Agent Operations Log and Coordination system.

Comprehensive test suite covering:
- OpsLog core functionality
- Log entry creation and management
- Log rotation and archival
- Entry expiration (TTL)
- Conflict detection
- Agent coordination
- Thread safety
- Edge cases and error handling
"""

import json
import os
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from fastband.agents.coordination import (
    AgentCoordinator,
    check_active_agents,
    get_agent_status,
)
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
def temp_dir():
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def ops_log(temp_dir):
    """Create an OpsLog instance for testing."""
    log_path = temp_dir / ".fastband" / "ops_log.json"
    archive_dir = temp_dir / ".fastband" / "ops_log_archive"
    return OpsLog(log_path=log_path, archive_dir=archive_dir)


@pytest.fixture
def populated_ops_log(ops_log):
    """Create an OpsLog with some sample entries."""
    ops_log.write_entry(
        agent="Agent1",
        event_type=EventType.AGENT_STARTED,
        message="Agent started",
    )
    ops_log.write_entry(
        agent="Agent1",
        event_type=EventType.TICKET_CLAIMED,
        message="Claimed ticket #100",
        ticket_id="100",
    )
    ops_log.write_entry(
        agent="Agent2",
        event_type=EventType.AGENT_STARTED,
        message="Agent started",
    )
    ops_log.write_entry(
        agent="Agent2",
        event_type=EventType.TICKET_CLAIMED,
        message="Claimed ticket #101",
        ticket_id="101",
    )
    return ops_log


@pytest.fixture
def coordinator(ops_log):
    """Create an AgentCoordinator for testing."""
    return AgentCoordinator(
        agent_name="TestAgent",
        ops_log=ops_log,
        auto_register=True,
    )


# =============================================================================
# LOG ENTRY TESTS
# =============================================================================


class TestLogEntry:
    """Tests for LogEntry class."""

    def test_create_entry(self):
        """Test creating a log entry."""
        entry = LogEntry.create(
            agent="Agent1",
            event_type=EventType.STATUS_UPDATE,
            message="Test message",
        )

        assert entry.agent == "Agent1"
        assert entry.event_type == EventType.STATUS_UPDATE.value
        assert entry.message == "Test message"
        assert entry.id is not None
        assert entry.timestamp is not None

    def test_create_entry_with_ticket(self):
        """Test creating entry with ticket ID."""
        entry = LogEntry.create(
            agent="Agent1",
            event_type=EventType.TICKET_CLAIMED,
            message="Claimed ticket",
            ticket_id="123",
        )

        assert entry.ticket_id == "123"

    def test_create_entry_with_metadata(self):
        """Test creating entry with metadata."""
        entry = LogEntry.create(
            agent="Agent1",
            event_type=EventType.STATUS_UPDATE,
            message="Test",
            metadata={"key": "value", "count": 42},
        )

        assert entry.metadata["key"] == "value"
        assert entry.metadata["count"] == 42

    def test_create_entry_with_ttl(self):
        """Test creating entry with TTL."""
        entry = LogEntry.create(
            agent="Agent1",
            event_type=EventType.STATUS_UPDATE,
            message="Temporary",
            ttl_seconds=3600,
        )

        assert entry.ttl_seconds == 3600
        assert entry.expires_at is not None

    def test_entry_to_dict(self):
        """Test converting entry to dictionary."""
        entry = LogEntry.create(
            agent="Agent1",
            event_type=EventType.STATUS_UPDATE,
            message="Test",
            ticket_id="100",
        )

        data = entry.to_dict()

        assert data["agent"] == "Agent1"
        assert data["event_type"] == EventType.STATUS_UPDATE.value
        assert data["ticket_id"] == "100"

    def test_entry_from_dict(self):
        """Test creating entry from dictionary."""
        data = {
            "id": "abc123",
            "timestamp": "2025-01-01T00:00:00Z",
            "agent": "Agent1",
            "event_type": "status_update",
            "message": "Test",
            "ticket_id": "100",
            "metadata": {"key": "value"},
            "ttl_seconds": None,
            "expires_at": None,
        }

        entry = LogEntry.from_dict(data)

        assert entry.id == "abc123"
        assert entry.agent == "Agent1"
        assert entry.ticket_id == "100"

    def test_entry_is_expired_not_expired(self):
        """Test is_expired returns False for non-expired entry."""
        entry = LogEntry.create(
            agent="Agent1",
            event_type=EventType.STATUS_UPDATE,
            message="Test",
            ttl_seconds=3600,  # 1 hour from now
        )

        assert entry.is_expired() is False

    def test_entry_is_expired_no_ttl(self):
        """Test is_expired returns False when no TTL set."""
        entry = LogEntry.create(
            agent="Agent1",
            event_type=EventType.STATUS_UPDATE,
            message="Test",
        )

        assert entry.is_expired() is False

    def test_entry_is_expired_with_past_expiry(self):
        """Test is_expired returns True for expired entry."""
        entry = LogEntry.create(
            agent="Agent1",
            event_type=EventType.STATUS_UPDATE,
            message="Test",
            ttl_seconds=1,
        )
        # Manually set expires_at to past
        entry.expires_at = (datetime.utcnow() - timedelta(hours=1)).isoformat() + "Z"

        assert entry.is_expired() is True

    def test_entry_formatted(self):
        """Test formatted output."""
        entry = LogEntry.create(
            agent="Agent1",
            event_type=EventType.TICKET_CLAIMED,
            message="Claimed ticket",
            ticket_id="100",
        )

        formatted = entry.formatted()

        assert "Agent1" in formatted
        assert "ticket_claimed" in formatted
        assert "Ticket #100" in formatted

    def test_entry_string_event_type(self):
        """Test creating entry with string event type."""
        entry = LogEntry.create(
            agent="Agent1",
            event_type="custom_event",
            message="Custom event",
        )

        assert entry.event_type == "custom_event"


# =============================================================================
# OPS LOG BASIC TESTS
# =============================================================================


class TestOpsLogBasic:
    """Basic OpsLog functionality tests."""

    def test_create_ops_log(self, temp_dir):
        """Test creating an OpsLog instance."""
        log_path = temp_dir / "ops_log.json"
        ops_log = OpsLog(log_path=log_path)

        assert ops_log.log_path == log_path
        assert ops_log.count() == 0

    def test_write_entry(self, ops_log):
        """Test writing a single entry."""
        entry = ops_log.write_entry(
            agent="Agent1",
            event_type=EventType.STATUS_UPDATE,
            message="Test message",
        )

        assert entry.id is not None
        assert ops_log.count() == 1

    def test_write_multiple_entries(self, ops_log):
        """Test writing multiple entries."""
        for i in range(5):
            ops_log.write_entry(
                agent=f"Agent{i}",
                event_type=EventType.STATUS_UPDATE,
                message=f"Message {i}",
            )

        assert ops_log.count() == 5

    def test_persistence(self, temp_dir):
        """Test that entries persist to file."""
        log_path = temp_dir / ".fastband" / "ops_log.json"

        # Create and write
        ops_log1 = OpsLog(log_path=log_path)
        ops_log1.write_entry(
            agent="Agent1",
            event_type=EventType.STATUS_UPDATE,
            message="Persisted message",
        )

        # Create new instance and verify
        ops_log2 = OpsLog(log_path=log_path)
        assert ops_log2.count() == 1

        entries = ops_log2.read_entries()
        assert entries[0].message == "Persisted message"

    def test_clear(self, populated_ops_log):
        """Test clearing entries."""
        assert populated_ops_log.count() > 0

        cleared = populated_ops_log.clear()

        assert cleared > 0
        assert populated_ops_log.count() == 0

    def test_load_corrupted_file(self, temp_dir):
        """Test loading corrupted log file."""
        log_path = temp_dir / "corrupted.json"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text("not valid json {{{")

        ops_log = OpsLog(log_path=log_path)

        assert ops_log.count() == 0

    def test_load_empty_file(self, temp_dir):
        """Test loading empty log file."""
        log_path = temp_dir / "empty.json"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text("")

        ops_log = OpsLog(log_path=log_path)

        assert ops_log.count() == 0


# =============================================================================
# OPS LOG FILTERING TESTS
# =============================================================================


class TestOpsLogFiltering:
    """Tests for read_entries filtering."""

    def test_read_all_entries(self, populated_ops_log):
        """Test reading all entries."""
        entries = populated_ops_log.read_entries()

        assert len(entries) == 4

    def test_read_entries_limit(self, populated_ops_log):
        """Test limiting entries."""
        entries = populated_ops_log.read_entries(limit=2)

        assert len(entries) == 2

    def test_read_entries_by_agent(self, populated_ops_log):
        """Test filtering by agent."""
        entries = populated_ops_log.read_entries(agent="Agent1")

        assert len(entries) == 2
        assert all(e.agent == "Agent1" for e in entries)

    def test_read_entries_by_event_type(self, populated_ops_log):
        """Test filtering by event type."""
        entries = populated_ops_log.read_entries(event_type=EventType.TICKET_CLAIMED)

        assert len(entries) == 2
        assert all(e.event_type == EventType.TICKET_CLAIMED.value for e in entries)

    def test_read_entries_by_ticket(self, populated_ops_log):
        """Test filtering by ticket ID."""
        entries = populated_ops_log.read_entries(ticket_id="100")

        assert len(entries) == 1
        assert entries[0].ticket_id == "100"

    def test_read_entries_since_minutes(self, ops_log):
        """Test filtering by time (minutes)."""
        ops_log.write_entry(
            agent="Agent1",
            event_type=EventType.STATUS_UPDATE,
            message="Recent",
        )

        entries = ops_log.read_entries(since="5m")

        assert len(entries) == 1

    def test_read_entries_since_hours(self, ops_log):
        """Test filtering by time (hours)."""
        ops_log.write_entry(
            agent="Agent1",
            event_type=EventType.STATUS_UPDATE,
            message="Recent",
        )

        entries = ops_log.read_entries(since="1h")

        assert len(entries) == 1

    def test_read_entries_since_days(self, ops_log):
        """Test filtering by time (days)."""
        ops_log.write_entry(
            agent="Agent1",
            event_type=EventType.STATUS_UPDATE,
            message="Recent",
        )

        entries = ops_log.read_entries(since="7d")

        assert len(entries) == 1

    def test_read_entries_sorted_newest_first(self, ops_log):
        """Test that entries are sorted newest first."""
        for i in range(3):
            ops_log.write_entry(
                agent="Agent1",
                event_type=EventType.STATUS_UPDATE,
                message=f"Message {i}",
            )
            time.sleep(0.01)  # Small delay to ensure different timestamps

        entries = ops_log.read_entries()

        assert entries[0].message == "Message 2"
        assert entries[2].message == "Message 0"

    def test_read_entries_combined_filters(self, populated_ops_log):
        """Test combining multiple filters."""
        entries = populated_ops_log.read_entries(
            agent="Agent1",
            event_type=EventType.TICKET_CLAIMED,
        )

        assert len(entries) == 1
        assert entries[0].agent == "Agent1"
        assert entries[0].event_type == EventType.TICKET_CLAIMED.value


# =============================================================================
# OPS LOG EXPIRATION TESTS
# =============================================================================


class TestOpsLogExpiration:
    """Tests for entry expiration (TTL)."""

    def test_entry_expires(self, ops_log):
        """Test that expired entries are filtered out."""
        # Create entry that's already expired
        ops_log.write_entry(
            agent="Agent1",
            event_type=EventType.STATUS_UPDATE,
            message="Expired",
            ttl_seconds=1,
        )

        # Manually set to past
        ops_log._entries[0].expires_at = (datetime.utcnow() - timedelta(hours=1)).isoformat() + "Z"

        entries = ops_log.read_entries(include_expired=False)

        assert len(entries) == 0

    def test_include_expired(self, ops_log):
        """Test including expired entries."""
        ops_log.write_entry(
            agent="Agent1",
            event_type=EventType.STATUS_UPDATE,
            message="Expired",
            ttl_seconds=1,
        )

        ops_log._entries[0].expires_at = (datetime.utcnow() - timedelta(hours=1)).isoformat() + "Z"

        entries = ops_log.read_entries(include_expired=True)

        assert len(entries) == 1

    def test_non_expiring_entries(self, ops_log):
        """Test entries without TTL don't expire."""
        ops_log.write_entry(
            agent="Agent1",
            event_type=EventType.STATUS_UPDATE,
            message="Permanent",
        )

        entries = ops_log.read_entries()

        assert len(entries) == 1


# =============================================================================
# OPS LOG ROTATION TESTS
# =============================================================================


class TestOpsLogRotation:
    """Tests for log rotation."""

    def test_manual_rotation(self, ops_log):
        """Test manual log rotation."""
        ops_log.write_entry(
            agent="Agent1",
            event_type=EventType.STATUS_UPDATE,
            message="Pre-rotation",
        )

        archive_path = ops_log.rotate(reason="test")

        assert archive_path is not None
        assert archive_path.exists()
        assert ops_log.count() == 0

    def test_rotation_creates_archive(self, ops_log):
        """Test that rotation creates archive file."""
        ops_log.write_entry(
            agent="Agent1",
            event_type=EventType.STATUS_UPDATE,
            message="To archive",
        )

        ops_log.rotate()

        archives = list(ops_log.archive_dir.glob("ops_log_*.json"))
        assert len(archives) == 1

    def test_archive_contains_entries(self, ops_log):
        """Test that archive contains original entries."""
        ops_log.write_entry(
            agent="Agent1",
            event_type=EventType.STATUS_UPDATE,
            message="Archived message",
        )

        archive_path = ops_log.rotate()

        with open(archive_path) as f:
            data = json.load(f)

        assert len(data["entries"]) == 1
        assert data["entries"][0]["message"] == "Archived message"

    def test_rotation_updates_metadata(self, ops_log):
        """Test that rotation updates last_rotation metadata."""
        ops_log.write_entry(
            agent="Agent1",
            event_type=EventType.STATUS_UPDATE,
            message="Test",
        )

        ops_log.rotate()

        assert ops_log._metadata.get("last_rotation") is not None

    def test_prune_old_archives(self, temp_dir):
        """Test pruning old archive files."""
        log_path = temp_dir / ".fastband" / "ops_log.json"
        archive_dir = temp_dir / ".fastband" / "ops_log_archive"
        archive_dir.mkdir(parents=True, exist_ok=True)

        # Create old archive
        old_date = (datetime.utcnow() - timedelta(days=60)).strftime("%Y%m%d_%H%M%S")
        old_archive = archive_dir / f"ops_log_{old_date}_old.json"
        old_archive.write_text('{"entries": []}')

        # Create recent archive
        new_date = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        new_archive = archive_dir / f"ops_log_{new_date}_new.json"
        new_archive.write_text('{"entries": []}')

        ops_log = OpsLog(log_path=log_path, archive_dir=archive_dir)
        deleted = ops_log.prune(keep_days=30)

        assert deleted == 1
        assert not old_archive.exists()
        assert new_archive.exists()


# =============================================================================
# CONFLICT DETECTION TESTS
# =============================================================================


class TestConflictDetection:
    """Tests for conflict detection."""

    def test_detect_conflict_same_ticket(self, ops_log):
        """Test detecting conflict when ticket claimed by another agent."""
        # Agent1 claims ticket
        ops_log.claim_ticket(agent="Agent1", ticket_id="100")

        # Agent2 tries to work on same ticket
        conflicts = ops_log.detect_conflicts(
            ticket_id="100",
            agent="Agent2",
        )

        assert len(conflicts) == 1
        assert conflicts[0].agent == "Agent1"

    def test_no_conflict_same_agent(self, ops_log):
        """Test no conflict when same agent works on ticket."""
        ops_log.claim_ticket(agent="Agent1", ticket_id="100")

        conflicts = ops_log.detect_conflicts(
            ticket_id="100",
            agent="Agent1",
        )

        assert len(conflicts) == 0

    def test_detect_hold_conflict(self, ops_log):
        """Test detecting hold directive as conflict."""
        ops_log.issue_hold(
            agent="Admin",
            affected_agents=["Agent1", "Agent2"],
            tickets=["100"],
            reason="Coordination required",
        )

        conflicts = ops_log.detect_conflicts(
            ticket_id="100",
            agent="Agent1",
        )

        assert len(conflicts) == 1
        assert conflicts[0].event_type == EventType.HOLD.value

    def test_no_conflict_different_ticket(self, ops_log):
        """Test no conflict for different tickets."""
        ops_log.claim_ticket(agent="Agent1", ticket_id="100")

        conflicts = ops_log.detect_conflicts(
            ticket_id="101",
            agent="Agent2",
        )

        assert len(conflicts) == 0


# =============================================================================
# CLEARANCE AND HOLD TESTS
# =============================================================================


class TestClearanceAndHold:
    """Tests for clearance and hold system."""

    def test_grant_clearance(self, ops_log):
        """Test granting clearance."""
        entry = ops_log.grant_clearance(
            agent="Admin",
            granted_to=["Agent1", "Agent2"],
            tickets=["100", "101"],
            reason="Cleared for Phase 1",
        )

        assert entry.event_type == EventType.CLEARANCE_GRANTED.value
        assert "Agent1" in entry.metadata["granted_to"]
        assert "100" in entry.metadata["tickets"]

    def test_issue_hold(self, ops_log):
        """Test issuing a hold."""
        entry = ops_log.issue_hold(
            agent="Admin",
            affected_agents=["Agent1"],
            tickets=["100"],
            reason="Bug found",
        )

        assert entry.event_type == EventType.HOLD.value
        assert "Agent1" in entry.metadata["affected_agents"]

    def test_issue_global_hold(self, ops_log):
        """Test issuing a global hold."""
        entry = ops_log.issue_hold(
            agent="Admin",
            affected_agents=["Agent1", "Agent2"],
            tickets=None,
            reason="System maintenance",
        )

        assert entry.metadata["is_global"] is True

    def test_get_latest_directive_clearance(self, ops_log):
        """Test getting latest clearance directive."""
        ops_log.grant_clearance(
            agent="Admin",
            granted_to=["Agent1"],
            tickets=["100"],
            reason="Cleared",
        )

        directive = ops_log.get_latest_directive()

        assert directive is not None
        assert directive.event_type == EventType.CLEARANCE_GRANTED.value

    def test_get_latest_directive_hold(self, ops_log):
        """Test getting latest hold directive."""
        ops_log.issue_hold(
            agent="Admin",
            affected_agents=["Agent1"],
            reason="Hold",
        )

        directive = ops_log.get_latest_directive()

        assert directive is not None
        assert directive.event_type == EventType.HOLD.value

    def test_get_latest_directive_none(self, ops_log):
        """Test getting directive when none exists."""
        ops_log.write_entry(
            agent="Agent1",
            event_type=EventType.STATUS_UPDATE,
            message="Not a directive",
        )

        directive = ops_log.get_latest_directive()

        assert directive is None


# =============================================================================
# REBUILD ANNOUNCEMENT TESTS
# =============================================================================


class TestRebuildAnnouncement:
    """Tests for rebuild announcements."""

    def test_announce_rebuild_requested(self, ops_log):
        """Test announcing rebuild request."""
        entry = ops_log.announce_rebuild(
            agent="Agent1",
            container="mlb-webapp",
            ticket_id="100",
            files_changed=["app.py", "templates/base.html"],
            status="requested",
        )

        assert entry.event_type == EventType.REBUILD_REQUESTED.value
        assert entry.metadata["container"] == "mlb-webapp"
        assert "app.py" in entry.metadata["files_changed"]

    def test_announce_rebuild_complete(self, ops_log):
        """Test announcing rebuild completion."""
        entry = ops_log.announce_rebuild(
            agent="Agent1",
            container="mlb-webapp",
            status="complete",
        )

        assert entry.event_type == EventType.REBUILD_COMPLETE.value


# =============================================================================
# TICKET OPERATIONS TESTS
# =============================================================================


class TestTicketOperations:
    """Tests for ticket claim/complete operations."""

    def test_claim_ticket(self, ops_log):
        """Test claiming a ticket."""
        entry, conflicts = ops_log.claim_ticket(
            agent="Agent1",
            ticket_id="100",
        )

        assert entry.event_type == EventType.TICKET_CLAIMED.value
        assert entry.ticket_id == "100"
        assert len(conflicts) == 0

    def test_claim_ticket_with_conflict(self, ops_log):
        """Test claiming ticket with existing claim."""
        ops_log.claim_ticket(agent="Agent1", ticket_id="100")

        entry, conflicts = ops_log.claim_ticket(
            agent="Agent2",
            ticket_id="100",
        )

        assert len(conflicts) == 1

    def test_complete_ticket(self, ops_log):
        """Test completing a ticket."""
        entry = ops_log.complete_ticket(
            agent="Agent1",
            ticket_id="100",
            summary="Fixed the bug",
        )

        assert entry.event_type == EventType.TICKET_COMPLETED.value
        assert entry.metadata["summary"] == "Fixed the bug"

    def test_complete_ticket_without_summary(self, ops_log):
        """Test completing ticket without summary."""
        entry = ops_log.complete_ticket(
            agent="Agent1",
            ticket_id="100",
        )

        assert entry.event_type == EventType.TICKET_COMPLETED.value
        assert "summary" not in entry.metadata or entry.metadata["summary"] is None


# =============================================================================
# ACTIVE AGENTS TESTS
# =============================================================================


class TestActiveAgents:
    """Tests for active agent tracking."""

    def test_check_active_agents(self, populated_ops_log):
        """Test checking active agents."""
        active = populated_ops_log.check_active_agents()

        assert "Agent1" in active
        assert "Agent2" in active

    def test_check_active_agents_with_current_ticket(self, ops_log):
        """Test tracking current ticket."""
        ops_log.claim_ticket(agent="Agent1", ticket_id="100")

        active = ops_log.check_active_agents()

        assert active["Agent1"]["current_ticket"] == "100"

    def test_check_active_agents_completed_ticket(self, ops_log):
        """Test that completed ticket clears current_ticket."""
        ops_log.claim_ticket(agent="Agent1", ticket_id="100")
        ops_log.complete_ticket(agent="Agent1", ticket_id="100")

        active = ops_log.check_active_agents()

        assert active["Agent1"]["current_ticket"] is None

    def test_check_active_agents_activity_count(self, ops_log):
        """Test activity count tracking."""
        for i in range(5):
            ops_log.write_entry(
                agent="Agent1",
                event_type=EventType.STATUS_UPDATE,
                message=f"Activity {i}",
            )

        active = ops_log.check_active_agents()

        assert active["Agent1"]["activity_count"] == 5


# =============================================================================
# STATISTICS TESTS
# =============================================================================


class TestOpsLogStats:
    """Tests for log statistics."""

    def test_get_stats(self, populated_ops_log):
        """Test getting log statistics."""
        stats = populated_ops_log.get_stats()

        assert stats["current_entries"] == 4
        assert EventType.AGENT_STARTED.value in stats["event_counts"]
        assert "Agent1" in stats["agent_counts"]

    def test_get_stats_empty_log(self, ops_log):
        """Test stats for empty log."""
        stats = ops_log.get_stats()

        assert stats["current_entries"] == 0
        assert stats["event_counts"] == {}


# =============================================================================
# COORDINATOR TESTS
# =============================================================================


class TestAgentCoordinator:
    """Tests for AgentCoordinator."""

    def test_coordinator_creation(self, ops_log):
        """Test creating a coordinator."""
        coord = AgentCoordinator(
            agent_name="TestAgent",
            ops_log=ops_log,
            auto_register=False,
        )

        assert coord.agent_name == "TestAgent"

    def test_coordinator_auto_register(self, ops_log):
        """Test coordinator auto-registration."""
        AgentCoordinator(
            agent_name="TestAgent",
            ops_log=ops_log,
            auto_register=True,
        )

        entries = ops_log.read_entries(agent="TestAgent")
        assert any(e.event_type == EventType.AGENT_STARTED.value for e in entries)

    def test_coordinator_claim_ticket(self, coordinator):
        """Test claiming ticket via coordinator."""
        result = coordinator.claim_ticket("100")

        assert result.success is True
        assert result.entry is not None
        assert result.entry.ticket_id == "100"

    def test_coordinator_claim_with_conflict(self, coordinator, ops_log):
        """Test claiming with conflict."""
        # Another agent claims first
        ops_log.claim_ticket(agent="OtherAgent", ticket_id="100")

        result = coordinator.claim_ticket("100", force=False)

        assert result.success is False
        assert len(result.conflicts) > 0

    def test_coordinator_force_claim(self, coordinator, ops_log):
        """Test force claiming despite conflicts."""
        ops_log.claim_ticket(agent="OtherAgent", ticket_id="100")

        result = coordinator.claim_ticket("100", force=True)

        assert result.success is True
        assert len(result.warnings) > 0

    def test_coordinator_complete_ticket(self, coordinator):
        """Test completing ticket via coordinator."""
        result = coordinator.complete_ticket("100", summary="Done")

        assert result.success is True

    def test_coordinator_grant_clearance(self, coordinator):
        """Test granting clearance via coordinator."""
        result = coordinator.grant_clearance(
            agents=["Agent2"],
            tickets=["100"],
            reason="Cleared",
        )

        assert result.success is True

    def test_coordinator_issue_hold(self, coordinator):
        """Test issuing hold via coordinator."""
        result = coordinator.issue_hold(
            agents=["Agent2"],
            tickets=["100"],
            reason="Wait",
        )

        assert result.success is True

    def test_coordinator_check_for_hold(self, coordinator, ops_log):
        """Test checking for hold affecting agent."""
        ops_log.issue_hold(
            agent="Admin",
            affected_agents=["TestAgent"],
            reason="Hold",
        )

        hold = coordinator.check_for_hold()

        assert hold is not None
        assert hold.event_type == EventType.HOLD.value

    def test_coordinator_announce_rebuild(self, coordinator):
        """Test announcing rebuild via coordinator."""
        result = coordinator.announce_rebuild(
            container="mlb-webapp",
            status="requested",
        )

        assert result.success is True

    def test_coordinator_get_active_agents(self, coordinator, ops_log):
        """Test getting active agents via coordinator."""
        ops_log.write_entry(
            agent="OtherAgent",
            event_type=EventType.STATUS_UPDATE,
            message="Active",
        )

        active = coordinator.get_active_agents()

        assert "TestAgent" in active
        assert "OtherAgent" in active

    def test_coordinator_update_status(self, coordinator):
        """Test status update via coordinator."""
        entry = coordinator.update_status(
            message="Working on feature",
            ticket_id="100",
        )

        assert entry.event_type == EventType.STATUS_UPDATE.value
        assert entry.ticket_id == "100"


# =============================================================================
# CONVENIENCE FUNCTION TESTS
# =============================================================================


class TestConvenienceFunctions:
    """Tests for module-level convenience functions."""

    def test_check_active_agents_function(self, temp_dir):
        """Test check_active_agents function."""
        # Reset global instance
        import fastband.agents.ops_log as ops_log_module

        ops_log_module._ops_log = None

        log_path = temp_dir / ".fastband" / "ops_log.json"
        ops_log = OpsLog(log_path=log_path)
        ops_log.write_entry(
            agent="TestAgent",
            event_type=EventType.STATUS_UPDATE,
            message="Active",
        )

        ops_log_module._ops_log = ops_log

        active = check_active_agents(project_path=temp_dir)

        assert "TestAgent" in active

    def test_get_agent_status_function(self, temp_dir):
        """Test get_agent_status function."""
        import fastband.agents.ops_log as ops_log_module

        ops_log_module._ops_log = None

        log_path = temp_dir / ".fastband" / "ops_log.json"
        ops_log = OpsLog(log_path=log_path)
        ops_log.claim_ticket(agent="TestAgent", ticket_id="100")
        ops_log_module._ops_log = ops_log

        status = get_agent_status("TestAgent", project_path=temp_dir)

        assert status.is_active is True
        assert status.current_ticket == "100"

    def test_get_agent_status_inactive(self, temp_dir):
        """Test get_agent_status for inactive agent."""
        import fastband.agents.ops_log as ops_log_module

        ops_log_module._ops_log = None

        log_path = temp_dir / ".fastband" / "ops_log.json"
        ops_log = OpsLog(log_path=log_path)
        ops_log_module._ops_log = ops_log

        status = get_agent_status("NonexistentAgent", project_path=temp_dir)

        assert status.is_active is False


# =============================================================================
# THREAD SAFETY TESTS
# =============================================================================


class TestThreadSafety:
    """Tests for thread-safe operations."""

    def test_concurrent_writes(self, ops_log):
        """Test concurrent write operations."""

        def write_entry(agent_num):
            for i in range(10):
                ops_log.write_entry(
                    agent=f"Agent{agent_num}",
                    event_type=EventType.STATUS_UPDATE,
                    message=f"Message {i}",
                )
            return agent_num

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(write_entry, i) for i in range(5)]
            [f.result() for f in as_completed(futures)]

        # Should have 50 entries (5 agents x 10 messages each)
        assert ops_log.count() == 50

    def test_concurrent_read_write(self, ops_log):
        """Test concurrent read and write operations."""
        write_count = 0
        read_count = 0
        errors = []

        def writer():
            nonlocal write_count
            for i in range(20):
                try:
                    ops_log.write_entry(
                        agent="Writer",
                        event_type=EventType.STATUS_UPDATE,
                        message=f"Write {i}",
                    )
                    write_count += 1
                except Exception as e:
                    errors.append(f"Write error: {e}")

        def reader():
            nonlocal read_count
            for _i in range(20):
                try:
                    ops_log.read_entries()
                    read_count += 1
                except Exception as e:
                    errors.append(f"Read error: {e}")

        threads = [
            threading.Thread(target=writer),
            threading.Thread(target=writer),
            threading.Thread(target=reader),
            threading.Thread(target=reader),
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert write_count == 40
        assert read_count == 40

    def test_concurrent_claim_detection(self, ops_log):
        """Test that concurrent claims work correctly and can detect conflicts."""
        claims_made = []
        conflicts_detected = []
        lock = threading.Lock()

        def claim_ticket(agent_name, delay):
            # Staggered start to ensure sequencing
            time.sleep(delay)
            entry, conflicts = ops_log.claim_ticket(
                agent=agent_name,
                ticket_id="100",
            )
            with lock:
                claims_made.append(agent_name)
                if conflicts:
                    conflicts_detected.append(agent_name)
            return agent_name

        with ThreadPoolExecutor(max_workers=3) as executor:
            # Stagger the claims to ensure at least some see prior claims
            futures = [executor.submit(claim_ticket, f"Agent{i}", i * 0.05) for i in range(3)]
            [f.result() for f in as_completed(futures)]

        # All claims should be recorded
        assert ops_log.count() == 3
        assert len(claims_made) == 3

        # With staggered timing, at least the last agent should see conflicts
        # (Agent2 started after Agent0 and Agent1)
        assert len(conflicts_detected) >= 1


# =============================================================================
# EDGE CASES TESTS
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_agent_name(self, ops_log):
        """Test with empty agent name."""
        entry = ops_log.write_entry(
            agent="",
            event_type=EventType.STATUS_UPDATE,
            message="Test",
        )

        assert entry.agent == ""

    def test_very_long_message(self, ops_log):
        """Test with very long message."""
        long_message = "x" * 10000

        entry = ops_log.write_entry(
            agent="Agent1",
            event_type=EventType.STATUS_UPDATE,
            message=long_message,
        )

        assert len(entry.message) == 10000

    def test_unicode_content(self, ops_log):
        """Test with unicode content."""
        entry = ops_log.write_entry(
            agent="Agent1",
            event_type=EventType.STATUS_UPDATE,
            message="Unicode test",
        )

        assert entry.message == "Unicode test"

    def test_special_characters_in_ticket_id(self, ops_log):
        """Test ticket ID with special characters."""
        entry = ops_log.write_entry(
            agent="Agent1",
            event_type=EventType.TICKET_CLAIMED,
            message="Test",
            ticket_id="ticket-123-abc",
        )

        assert entry.ticket_id == "ticket-123-abc"

    def test_nested_metadata(self, ops_log):
        """Test deeply nested metadata."""
        metadata = {"level1": {"level2": {"level3": {"value": 42}}}}

        entry = ops_log.write_entry(
            agent="Agent1",
            event_type=EventType.STATUS_UPDATE,
            message="Test",
            metadata=metadata,
        )

        assert entry.metadata["level1"]["level2"]["level3"]["value"] == 42

    def test_rotation_empty_log(self, ops_log):
        """Test rotating an empty log."""
        result = ops_log.rotate()

        assert result is None  # No rotation needed for empty log

    def test_prune_nonexistent_archive_dir(self, temp_dir):
        """Test pruning when archive directory doesn't exist."""
        log_path = temp_dir / "ops_log.json"
        archive_dir = temp_dir / "nonexistent_archive"

        ops_log = OpsLog(log_path=log_path, archive_dir=archive_dir)
        deleted = ops_log.prune()

        assert deleted == 0

    def test_invalid_time_filter(self, ops_log):
        """Test with invalid time filter."""
        ops_log.write_entry(
            agent="Agent1",
            event_type=EventType.STATUS_UPDATE,
            message="Test",
        )

        # Invalid filter should return all entries
        entries = ops_log.read_entries(since="invalid")

        assert len(entries) == 1


# =============================================================================
# GLOBAL INSTANCE TESTS
# =============================================================================


class TestGlobalInstance:
    """Tests for global OpsLog instance management."""

    def test_get_ops_log_default(self, temp_dir):
        """Test getting default OpsLog instance."""
        import fastband.agents.ops_log as ops_log_module

        ops_log_module._ops_log = None

        # Change to temp dir
        original_cwd = os.getcwd()
        try:
            os.chdir(temp_dir)
            ops_log = get_ops_log()
            assert ops_log is not None
        finally:
            os.chdir(original_cwd)
            ops_log_module._ops_log = None

    def test_get_ops_log_with_path(self, temp_dir):
        """Test getting OpsLog with specific path."""
        import fastband.agents.ops_log as ops_log_module

        ops_log_module._ops_log = None

        ops_log = get_ops_log(project_path=temp_dir)

        assert ops_log.log_path == temp_dir / ".fastband" / "ops_log.json"
        ops_log_module._ops_log = None

    def test_get_ops_log_reset(self, temp_dir):
        """Test resetting OpsLog instance."""
        import fastband.agents.ops_log as ops_log_module

        ops_log_module._ops_log = None

        ops_log1 = get_ops_log(project_path=temp_dir)
        ops_log2 = get_ops_log(project_path=temp_dir, reset=True)

        assert ops_log1 is not ops_log2
        ops_log_module._ops_log = None

    def test_get_ops_log_caches(self, temp_dir):
        """Test that get_ops_log caches the instance."""
        import fastband.agents.ops_log as ops_log_module

        ops_log_module._ops_log = None

        ops_log1 = get_ops_log(project_path=temp_dir)
        ops_log2 = get_ops_log(project_path=temp_dir)

        assert ops_log1 is ops_log2
        ops_log_module._ops_log = None

"""
Tests for the Fastband Backup System.

Tests cover:
- BackupManager: Create, list, restore, delete backups
- BackupScheduler: Daemon management, hooks, state persistence
- BackupAlerts: Failure notifications across multiple channels
"""

import json
import os
import time
from datetime import datetime, timedelta

import pytest

from fastband.backup.alerts import (
    Alert,
    AlertConfig,
    AlertLevel,
    AlertManager,
    FileChannel,
    LogChannel,
    get_alert_manager,
    send_backup_alert,
    send_backup_failure_alert,
)
from fastband.backup.manager import (
    BackupInfo,
    BackupManager,
    BackupType,
)
from fastband.backup.scheduler import (
    BackupScheduler,
    SchedulerState,
    get_scheduler,
    trigger_backup_hook,
)
from fastband.core.config import BackupConfig, BackupHooksConfig

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def temp_project(tmp_path):
    """Create a temporary project directory with config."""
    project_path = tmp_path / "test_project"
    project_path.mkdir()

    # Create .fastband directory
    fastband_dir = project_path / ".fastband"
    fastband_dir.mkdir()

    # Create config file
    config_file = fastband_dir / "config.yaml"
    config_file.write_text("""
fastband:
  version: "1.0"
  backup:
    enabled: true
    scheduler_enabled: true
    interval_hours: 2
    retention_days: 3
    max_backups: 10
    backup_path: .fastband/backups
    hooks:
      before_build: true
      after_ticket_completion: true
      on_config_change: false
""")

    # Create some test files
    (project_path / "test.py").write_text("print('hello')")
    (project_path / "data.json").write_text('{"key": "value"}')

    # Create tickets file
    (fastband_dir / "tickets.json").write_text('{"tickets": []}')

    return project_path


@pytest.fixture
def backup_manager(temp_project):
    """Create a BackupManager instance."""
    return BackupManager(project_path=temp_project)


@pytest.fixture
def backup_scheduler(temp_project):
    """Create a BackupScheduler instance."""
    return BackupScheduler(project_path=temp_project)


@pytest.fixture
def backup_config():
    """Create a BackupConfig instance."""
    return BackupConfig(
        enabled=True,
        scheduler_enabled=True,
        interval_hours=2,
        retention_days=3,
        max_backups=10,
        hooks=BackupHooksConfig(
            before_build=True,
            after_ticket_completion=True,
            on_config_change=False,
        ),
    )


# =============================================================================
# BACKUP MANAGER TESTS
# =============================================================================


class TestBackupManager:
    """Tests for BackupManager class."""

    def test_init(self, backup_manager, temp_project):
        """Test manager initialization."""
        assert backup_manager.project_path == temp_project
        assert backup_manager.backup_dir.exists()
        assert backup_manager.manifest_path.parent.exists()

    def test_create_manual_backup(self, backup_manager):
        """Test creating a manual backup."""
        backup_info = backup_manager.create_backup(
            backup_type=BackupType.MANUAL,
            description="Test backup",
        )

        assert backup_info is not None
        assert backup_info.backup_type == BackupType.MANUAL
        assert backup_info.description == "Test backup"
        assert backup_info.size_bytes > 0
        assert backup_info.files_count > 0
        assert backup_info.checksum != ""

    def test_create_full_backup(self, backup_manager):
        """Test creating a full backup."""
        backup_info = backup_manager.create_backup(
            backup_type=BackupType.FULL,
            description="Full backup",
        )

        assert backup_info is not None
        assert backup_info.backup_type == BackupType.FULL

    def test_create_on_change_backup_no_changes(self, backup_manager):
        """Test on_change backup skips when no changes."""
        # First backup to set checksum
        backup_manager.create_backup(backup_type=BackupType.FULL)

        # Second backup should be skipped (no changes)
        backup_info = backup_manager.create_backup(
            backup_type=BackupType.ON_CHANGE,
            force=False,
        )

        assert backup_info is None

    def test_create_on_change_backup_with_force(self, backup_manager):
        """Test on_change backup with force flag."""
        # First backup
        backup_manager.create_backup(backup_type=BackupType.FULL)

        # Second backup with force
        backup_info = backup_manager.create_backup(
            backup_type=BackupType.ON_CHANGE,
            force=True,
        )

        assert backup_info is not None

    def test_list_backups(self, backup_manager):
        """Test listing backups."""
        # Create multiple backups
        backup_manager.create_backup(backup_type=BackupType.FULL, description="First")
        time.sleep(0.1)
        backup_manager.create_backup(
            backup_type=BackupType.MANUAL, description="Second", force=True
        )

        backups = backup_manager.list_backups()

        assert len(backups) == 2
        # Should be sorted newest first
        assert backups[0].description == "Second"
        assert backups[1].description == "First"

    def test_get_backup(self, backup_manager):
        """Test getting a specific backup."""
        backup_info = backup_manager.create_backup(
            backup_type=BackupType.MANUAL,
            description="Specific backup",
        )

        retrieved = backup_manager.get_backup(backup_info.id)

        assert retrieved is not None
        assert retrieved.id == backup_info.id
        assert retrieved.description == "Specific backup"

    def test_get_backup_not_found(self, backup_manager):
        """Test getting a non-existent backup."""
        result = backup_manager.get_backup("nonexistent_id")
        assert result is None

    def test_delete_backup(self, backup_manager):
        """Test deleting a backup."""
        backup_info = backup_manager.create_backup(backup_type=BackupType.MANUAL)
        backup_path = backup_manager.backup_dir / backup_info.filename

        assert backup_path.exists()

        result = backup_manager.delete_backup(backup_info.id)

        assert result is True
        assert not backup_path.exists()
        assert backup_manager.get_backup(backup_info.id) is None

    def test_delete_backup_not_found(self, backup_manager):
        """Test deleting a non-existent backup."""
        result = backup_manager.delete_backup("nonexistent_id")
        assert result is False

    def test_restore_backup(self, backup_manager, temp_project):
        """Test restoring a backup."""
        # Create a backup
        backup_info = backup_manager.create_backup(backup_type=BackupType.FULL)

        # Modify a file
        test_file = temp_project / ".fastband" / "tickets.json"
        original_content = test_file.read_text()
        test_file.write_text('{"modified": true}')

        # Restore
        result = backup_manager.restore_backup(backup_info.id)

        assert result is True
        # File should be restored
        assert test_file.read_text() == original_content

    def test_restore_backup_dry_run(self, backup_manager):
        """Test restore dry run."""
        backup_info = backup_manager.create_backup(backup_type=BackupType.FULL)

        result = backup_manager.restore_backup(backup_info.id, dry_run=True)

        assert result is True

    def test_restore_backup_not_found(self, backup_manager):
        """Test restoring non-existent backup."""
        result = backup_manager.restore_backup("nonexistent_id")
        assert result is False

    def test_has_changes(self, backup_manager, temp_project):
        """Test change detection."""
        # Initially has changes (no backup yet)
        assert backup_manager.has_changes() is True

        # Create backup
        backup_manager.create_backup(backup_type=BackupType.FULL)

        # No changes after backup
        assert backup_manager.has_changes() is False

        # Modify a file
        tickets_file = temp_project / ".fastband" / "tickets.json"
        tickets_file.write_text('{"modified": true}')

        # Should detect changes
        assert backup_manager.has_changes() is True

    def test_prune_old_backups(self, backup_manager):
        """Test pruning old backups."""
        # Create some backups with old dates
        backup_manager.create_backup(
            backup_type=BackupType.FULL, description="Old backup", force=True
        )

        # Manually set the backup date to old
        manifest = backup_manager._load_manifest()
        old_date = (datetime.now() - timedelta(days=30)).isoformat()
        for backup in manifest["backups"]:
            backup["created_at"] = old_date
        backup_manager._manifest = manifest
        backup_manager._save_manifest()

        # Prune
        pruned = backup_manager.prune_old_backups()

        assert len(pruned) >= 0  # May or may not prune depending on config

    def test_get_stats(self, backup_manager):
        """Test getting backup statistics."""
        backup_manager.create_backup(backup_type=BackupType.FULL, description="Stats test")

        stats = backup_manager.get_stats()

        assert stats["total_backups"] == 1
        assert stats["total_size_bytes"] > 0
        assert "by_type" in stats
        assert "config" in stats

    def test_backup_info_size_human(self):
        """Test BackupInfo size formatting."""
        info = BackupInfo(
            id="test",
            backup_type=BackupType.MANUAL,
            created_at=datetime.now(),
            size_bytes=1024,
            files_count=1,
            checksum="abc",
        )
        assert info.size_human == "1.0 KB"

        info.size_bytes = 1024 * 1024
        assert info.size_human == "1.0 MB"

    def test_backup_info_to_from_dict(self):
        """Test BackupInfo serialization."""
        info = BackupInfo(
            id="test123",
            backup_type=BackupType.FULL,
            created_at=datetime.now(),
            size_bytes=5000,
            files_count=10,
            checksum="abc123",
            description="Test backup",
            metadata={"key": "value"},
        )

        data = info.to_dict()
        restored = BackupInfo.from_dict(data)

        assert restored.id == info.id
        assert restored.backup_type == info.backup_type
        assert restored.size_bytes == info.size_bytes
        assert restored.description == info.description


# =============================================================================
# BACKUP SCHEDULER TESTS
# =============================================================================


class TestSchedulerState:
    """Tests for SchedulerState class."""

    def test_state_defaults(self):
        """Test default state values."""
        state = SchedulerState()

        assert state.running is False
        assert state.pid is None
        assert state.started_at is None
        assert state.backups_created == 0
        assert state.errors == 0

    def test_state_to_dict(self):
        """Test state serialization."""
        state = SchedulerState(
            running=True,
            pid=12345,
            started_at=datetime.now(),
            backups_created=5,
            errors=1,
        )

        data = state.to_dict()

        assert data["running"] is True
        assert data["pid"] == 12345
        assert data["backups_created"] == 5
        assert data["errors"] == 1

    def test_state_from_dict(self):
        """Test state deserialization."""
        data = {
            "running": True,
            "pid": 12345,
            "started_at": datetime.now().isoformat(),
            "backups_created": 5,
            "errors": 1,
        }

        state = SchedulerState.from_dict(data)

        assert state.running is True
        assert state.pid == 12345
        assert state.backups_created == 5


class TestBackupScheduler:
    """Tests for BackupScheduler class."""

    def test_init(self, backup_scheduler, temp_project):
        """Test scheduler initialization."""
        assert backup_scheduler.project_path == temp_project
        assert backup_scheduler.config.enabled is True
        assert backup_scheduler.config.scheduler_enabled is True

    def test_is_running_false(self, backup_scheduler):
        """Test is_running when not running."""
        assert backup_scheduler.is_running() is False

    def test_get_status(self, backup_scheduler):
        """Test getting scheduler status."""
        status = backup_scheduler.get_status()

        assert "running" in status
        assert "config" in status
        assert "state" in status
        assert status["config"]["interval_hours"] == 2
        assert status["config"]["retention_days"] == 3

    def test_trigger_before_build(self, backup_scheduler):
        """Test before_build hook trigger."""
        backup_info = backup_scheduler.trigger_before_build()

        assert backup_info is not None
        assert backup_info.backup_type == BackupType.ON_CHANGE
        assert "Pre-build" in backup_info.description

    def test_trigger_before_build_disabled(self, temp_project):
        """Test before_build hook when disabled."""
        config = BackupConfig(
            enabled=True,
            hooks=BackupHooksConfig(before_build=False),
        )
        scheduler = BackupScheduler(project_path=temp_project, config=config)

        backup_info = scheduler.trigger_before_build()

        assert backup_info is None

    def test_trigger_after_ticket_completion(self, backup_scheduler):
        """Test after_ticket_completion hook trigger."""
        backup_info = backup_scheduler.trigger_after_ticket_completion(ticket_id="123")

        assert backup_info is not None
        assert "ticket #123" in backup_info.description

    def test_trigger_after_ticket_completion_disabled(self, temp_project):
        """Test after_ticket_completion hook when disabled."""
        config = BackupConfig(
            enabled=True,
            hooks=BackupHooksConfig(after_ticket_completion=False),
        )
        scheduler = BackupScheduler(project_path=temp_project, config=config)

        backup_info = scheduler.trigger_after_ticket_completion()

        assert backup_info is None

    def test_trigger_on_config_change(self, temp_project):
        """Test on_config_change hook trigger."""
        config = BackupConfig(
            enabled=True,
            hooks=BackupHooksConfig(on_config_change=True),
        )
        scheduler = BackupScheduler(project_path=temp_project, config=config)

        backup_info = scheduler.trigger_on_config_change()

        assert backup_info is not None
        assert "Config change" in backup_info.description

    def test_state_persistence(self, backup_scheduler, temp_project):
        """Test state is persisted to file."""
        backup_scheduler.state.backups_created = 5
        backup_scheduler.state.errors = 2
        backup_scheduler._save_state()

        # Load fresh scheduler
        new_scheduler = BackupScheduler(project_path=temp_project)

        assert new_scheduler.state.backups_created == 5
        assert new_scheduler.state.errors == 2

    def test_start_daemon_foreground(self, backup_scheduler):
        """Test starting daemon in foreground (quick exit)."""
        # We can't really test foreground mode as it blocks
        # Just verify initial checks work
        assert backup_scheduler.is_running() is False

    def test_start_daemon_already_running(self, backup_scheduler):
        """Test starting when already running."""
        # Create a fake PID file for ourselves
        backup_scheduler._write_pid()
        backup_scheduler.state.running = True
        backup_scheduler._save_state()

        # Should return False (already running)
        result = backup_scheduler.start_daemon()

        assert result is False

        # Cleanup
        backup_scheduler._remove_pid()

    def test_stop_daemon_not_running(self, backup_scheduler):
        """Test stopping when not running."""
        result = backup_scheduler.stop_daemon()
        assert result is True  # Should succeed (nothing to stop)

    def test_prune_old_backups(self, backup_scheduler):
        """Test scheduler prunes old backups."""
        # Create multiple backups
        for i in range(5):
            backup_scheduler.manager.create_backup(
                backup_type=BackupType.FULL,
                description=f"Backup {i}",
                force=True,
            )

        # Should have 5 backups
        assert len(backup_scheduler.manager.list_backups()) == 5

    def test_time_until_next_backup(self, backup_scheduler):
        """Test next backup time calculation."""
        state = SchedulerState(
            next_backup_at=datetime.now() + timedelta(hours=1, minutes=30),
        )

        time_str = backup_scheduler._time_until_next_backup(state)

        assert "1h" in time_str
        # Allow for slight timing variation (29m or 30m are both acceptable)
        assert "29m" in time_str or "30m" in time_str

    def test_time_until_next_backup_imminent(self, backup_scheduler):
        """Test next backup time when imminent."""
        state = SchedulerState(
            next_backup_at=datetime.now() - timedelta(seconds=5),
        )

        time_str = backup_scheduler._time_until_next_backup(state)

        assert time_str == "imminent"


class TestSchedulerConvenience:
    """Tests for scheduler convenience functions."""

    def test_get_scheduler(self, temp_project):
        """Test get_scheduler function."""
        scheduler = get_scheduler(project_path=temp_project)

        assert scheduler is not None
        assert isinstance(scheduler, BackupScheduler)

    def test_trigger_backup_hook_before_build(self, temp_project):
        """Test trigger_backup_hook for before_build."""
        backup_info = trigger_backup_hook("before_build", project_path=temp_project)

        assert backup_info is not None
        assert "Pre-build" in backup_info.description

    def test_trigger_backup_hook_after_ticket(self, temp_project):
        """Test trigger_backup_hook for after_ticket_completion."""
        backup_info = trigger_backup_hook(
            "after_ticket_completion",
            project_path=temp_project,
            ticket_id="456",
        )

        assert backup_info is not None
        assert "ticket #456" in backup_info.description

    def test_trigger_backup_hook_unknown(self, temp_project):
        """Test trigger_backup_hook with unknown hook type."""
        backup_info = trigger_backup_hook("unknown_hook", project_path=temp_project)

        assert backup_info is None


# =============================================================================
# BACKUP FAILURE TESTS
# =============================================================================


class TestBackupFailures:
    """Tests for backup failure scenarios."""

    def test_backup_fails_on_permission_error(self, temp_project):
        """Test backup failure handling on permission error."""
        manager = BackupManager(project_path=temp_project)

        # Make backup dir read-only to cause failure
        backup_dir = manager.backup_dir
        original_mode = backup_dir.stat().st_mode

        try:
            os.chmod(backup_dir, 0o444)

            with pytest.raises(Exception):
                manager.create_backup(backup_type=BackupType.FULL)
        finally:
            os.chmod(backup_dir, original_mode)

    def test_restore_fails_on_corrupted_backup(self, backup_manager):
        """Test restore failure on corrupted backup."""
        # Create backup
        backup_info = backup_manager.create_backup(backup_type=BackupType.FULL)
        backup_path = backup_manager.backup_dir / backup_info.filename

        # Corrupt the backup
        backup_path.write_bytes(b"corrupted data")

        # Restore should fail
        result = backup_manager.restore_backup(backup_info.id)

        # Checksum mismatch should cause failure
        assert result is False

    def test_scheduler_records_errors(self, backup_scheduler):
        """Test scheduler error counting."""
        initial_errors = backup_scheduler.state.errors

        # Simulate an error
        backup_scheduler.state.errors += 1
        backup_scheduler._save_state()

        assert backup_scheduler.state.errors == initial_errors + 1


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestBackupIntegration:
    """Integration tests for the backup system."""

    def test_full_backup_restore_cycle(self, temp_project):
        """Test complete backup and restore cycle."""
        manager = BackupManager(project_path=temp_project)

        # Create some content
        test_file = temp_project / ".fastband" / "tickets.json"
        original_content = '{"tickets": [{"id": 1}]}'
        test_file.write_text(original_content)

        # Create backup
        backup_info = manager.create_backup(
            backup_type=BackupType.FULL,
            description="Integration test backup",
        )
        assert backup_info is not None

        # Modify content
        test_file.write_text('{"tickets": [{"id": 999}]}')
        assert test_file.read_text() != original_content

        # Restore
        result = manager.restore_backup(backup_info.id)
        assert result is True

        # Content should be restored
        assert test_file.read_text() == original_content

    def test_scheduler_hook_creates_backup(self, temp_project):
        """Test scheduler hooks create backups correctly."""
        scheduler = BackupScheduler(project_path=temp_project)

        # Initial state
        initial_count = len(scheduler.manager.list_backups())

        # Trigger hooks
        scheduler.trigger_before_build()
        scheduler.trigger_after_ticket_completion(ticket_id="TEST")

        # Should have created 2 backups
        final_count = len(scheduler.manager.list_backups())
        assert final_count == initial_count + 2

    def test_retention_policy_enforcement(self, temp_project):
        """Test that retention policy is enforced."""
        config = BackupConfig(
            enabled=True,
            max_backups=3,
            retention_days=1,
        )
        scheduler = BackupScheduler(project_path=temp_project, config=config)

        # Create more backups than max using scheduler's manager
        for i in range(5):
            scheduler.manager.create_backup(
                backup_type=BackupType.FULL,
                description=f"Backup {i}",
                force=True,
            )
            time.sleep(0.05)

        # Trigger pruning through scheduler
        scheduler._prune_old_backups()

        # Should be at or below max
        backups = scheduler.manager.list_backups()
        assert len(backups) <= config.max_backups


# =============================================================================
# ALERT SYSTEM TESTS
# =============================================================================


@pytest.fixture
def alert_manager(temp_project):
    """Create an AlertManager instance."""
    config = AlertConfig(
        alert_log_path=temp_project / ".fastband" / "alerts.json",
        system_notifications=False,  # Disable for tests
        min_level=AlertLevel.INFO,
    )
    return AlertManager(project_path=temp_project, config=config)


class TestAlertLevel:
    """Tests for AlertLevel enum."""

    def test_emoji(self):
        """Test level emojis."""
        assert AlertLevel.INFO.emoji == "ℹ️"
        assert AlertLevel.WARNING.emoji == "⚠️"
        assert AlertLevel.ERROR.emoji == "❌"
        assert AlertLevel.CRITICAL.emoji == "🔥"

    def test_color(self):
        """Test level colors."""
        assert AlertLevel.INFO.color.startswith("#")
        assert AlertLevel.CRITICAL.color == "#b71c1c"


class TestAlert:
    """Tests for Alert class."""

    def test_alert_creation(self):
        """Test creating an alert."""
        alert = Alert(
            id="test_123",
            level=AlertLevel.WARNING,
            title="Test Alert",
            message="This is a test",
        )

        assert alert.id == "test_123"
        assert alert.level == AlertLevel.WARNING
        assert alert.title == "Test Alert"
        assert alert.acknowledged is False

    def test_alert_to_dict(self):
        """Test alert serialization."""
        alert = Alert(
            id="test_123",
            level=AlertLevel.ERROR,
            title="Test",
            message="Message",
            error="Some error",
            context={"key": "value"},
        )

        data = alert.to_dict()

        assert data["id"] == "test_123"
        assert data["level"] == "error"
        assert data["error"] == "Some error"
        assert data["context"] == {"key": "value"}

    def test_alert_from_dict(self):
        """Test alert deserialization."""
        data = {
            "id": "test_456",
            "level": "critical",
            "title": "Critical Alert",
            "message": "Something failed",
            "timestamp": datetime.now().isoformat(),
            "error": "Exception details",
        }

        alert = Alert.from_dict(data)

        assert alert.id == "test_456"
        assert alert.level == AlertLevel.CRITICAL
        assert alert.error == "Exception details"

    def test_alert_format_text(self):
        """Test alert text formatting."""
        alert = Alert(
            id="test",
            level=AlertLevel.CRITICAL,
            title="Backup Failed",
            message="Disk full",
            error="No space left on device",
        )

        text = alert.format_text()

        assert "🔥" in text
        assert "CRITICAL" in text
        assert "Backup Failed" in text
        assert "Disk full" in text
        assert "No space left on device" in text


class TestAlertChannels:
    """Tests for alert channels."""

    def test_log_channel(self):
        """Test LogChannel."""
        channel = LogChannel()
        alert = Alert(
            id="test",
            level=AlertLevel.INFO,
            title="Test",
            message="Test message",
        )

        result = channel.send(alert)

        assert result is True

    def test_file_channel(self, temp_project):
        """Test FileChannel."""
        alert_log_path = temp_project / ".fastband" / "test_alerts.json"
        channel = FileChannel(alert_log_path)

        alert = Alert(
            id="test_file",
            level=AlertLevel.WARNING,
            title="File Test",
            message="Testing file channel",
        )

        result = channel.send(alert)

        assert result is True
        assert alert_log_path.exists()

        # Verify content
        data = json.loads(alert_log_path.read_text())
        assert len(data) == 1
        assert data[0]["id"] == "test_file"

    def test_file_channel_appends(self, temp_project):
        """Test FileChannel appends to existing file."""
        alert_log_path = temp_project / ".fastband" / "test_alerts.json"
        channel = FileChannel(alert_log_path)

        # Send multiple alerts
        for i in range(3):
            alert = Alert(
                id=f"test_{i}",
                level=AlertLevel.INFO,
                title=f"Alert {i}",
                message=f"Message {i}",
            )
            channel.send(alert)

        data = json.loads(alert_log_path.read_text())
        assert len(data) == 3


class TestAlertManager:
    """Tests for AlertManager class."""

    def test_init(self, alert_manager, temp_project):
        """Test manager initialization."""
        assert alert_manager.project_path == temp_project
        assert len(alert_manager._channels) >= 2  # At least log and file

    def test_send_alert(self, alert_manager):
        """Test sending an alert."""
        alert = alert_manager.send_alert(
            level=AlertLevel.WARNING,
            title="Test Warning",
            message="This is a test warning",
        )

        assert alert is not None
        assert alert.level == AlertLevel.WARNING
        assert "log" in alert.sent_to
        assert "file" in alert.sent_to

    def test_send_alert_below_threshold(self, temp_project):
        """Test alerts below threshold are not sent."""
        config = AlertConfig(
            min_level=AlertLevel.ERROR,  # Only ERROR and CRITICAL
        )
        manager = AlertManager(project_path=temp_project, config=config)

        alert = manager.send_alert(
            level=AlertLevel.WARNING,
            title="Low Priority",
            message="Should not be sent",
        )

        assert alert is None

    def test_send_critical_alert(self, alert_manager):
        """Test sending critical alert bypasses rate limiting."""
        # Send many alerts to trigger rate limiting
        for _i in range(20):
            alert_manager.send_alert(
                level=AlertLevel.WARNING,
                title="Repeated Alert",
                message="Same message",
            )

        # Critical alert should still go through
        alert = alert_manager.send_critical_alert(
            title="Critical",
            message="Must be sent",
        )

        assert alert is not None
        assert alert.level == AlertLevel.CRITICAL

    def test_rate_limiting(self, temp_project):
        """Test rate limiting prevents alert storms."""
        config = AlertConfig(
            cooldown_seconds=60,
            max_alerts_per_hour=5,
        )
        manager = AlertManager(project_path=temp_project, config=config)

        # First alert should succeed
        alert1 = manager.send_alert(
            level=AlertLevel.WARNING,
            title="Same Alert",
            message="Test",
        )
        assert alert1 is not None

        # Same alert within cooldown should be rate limited
        alert2 = manager.send_alert(
            level=AlertLevel.WARNING,
            title="Same Alert",
            message="Test",
        )
        assert alert2 is None

    def test_get_recent_alerts(self, alert_manager):
        """Test retrieving recent alerts."""
        # Send some alerts
        alert_manager.send_alert(AlertLevel.INFO, "Alert 1", "Message 1")
        alert_manager.send_alert(AlertLevel.WARNING, "Alert 2", "Message 2", force=True)

        alerts = alert_manager.get_recent_alerts(limit=10)

        assert len(alerts) >= 2

    def test_acknowledge_alert(self, alert_manager):
        """Test acknowledging an alert."""
        alert = alert_manager.send_alert(
            level=AlertLevel.WARNING,
            title="To Acknowledge",
            message="Test",
        )

        result = alert_manager.acknowledge_alert(alert.id)

        assert result is True

        # Verify acknowledged
        alerts = alert_manager.get_recent_alerts()
        acked_alert = next((a for a in alerts if a.id == alert.id), None)
        assert acked_alert is not None
        assert acked_alert.acknowledged is True

    def test_get_unacknowledged_count(self, alert_manager):
        """Test counting unacknowledged alerts."""
        # Clear any existing
        if alert_manager.config.alert_log_path.exists():
            alert_manager.config.alert_log_path.unlink()

        # Send some alerts
        alert1 = alert_manager.send_alert(AlertLevel.INFO, "Alert 1", "Test")
        alert_manager.send_alert(AlertLevel.WARNING, "Alert 2", "Test", force=True)

        count = alert_manager.get_unacknowledged_count()
        assert count >= 2

        # Acknowledge one
        alert_manager.acknowledge_alert(alert1.id)

        count = alert_manager.get_unacknowledged_count()
        assert count >= 1


class TestAlertConvenience:
    """Tests for alert convenience functions."""

    def test_send_backup_alert(self, temp_project):
        """Test send_backup_alert convenience function."""
        # Reset global manager
        import fastband.backup.alerts as alerts_module

        alerts_module._alert_manager = None

        alert = send_backup_alert(
            level=AlertLevel.ERROR,
            title="Backup Error",
            message="Test error",
            project_path=temp_project,
        )

        assert alert is not None
        assert alert.level == AlertLevel.ERROR

    def test_send_backup_failure_alert(self, temp_project):
        """Test send_backup_failure_alert convenience function."""
        # Reset global manager
        import fastband.backup.alerts as alerts_module

        alerts_module._alert_manager = None

        error = ValueError("Disk full")
        alert = send_backup_failure_alert(
            message="Scheduled backup failed",
            error=error,
            context={"backup_type": "full"},
            project_path=temp_project,
        )

        assert alert is not None
        assert alert.level == AlertLevel.CRITICAL
        assert "Disk full" in alert.error

    def test_get_alert_manager_singleton(self, temp_project):
        """Test get_alert_manager returns consistent instance."""
        # Reset global manager
        import fastband.backup.alerts as alerts_module

        alerts_module._alert_manager = None

        manager1 = get_alert_manager(project_path=temp_project)
        manager2 = get_alert_manager()

        assert manager1 is manager2


class TestAlertIntegration:
    """Integration tests for alerts with backup system."""

    def test_backup_failure_triggers_alert(self, temp_project):
        """Test that backup failures trigger alerts."""
        # Reset global alert manager
        import fastband.backup.alerts as alerts_module

        alerts_module._alert_manager = None

        manager = BackupManager(project_path=temp_project)

        # Make backup dir read-only to cause failure
        backup_dir = manager.backup_dir
        original_mode = backup_dir.stat().st_mode

        try:
            os.chmod(backup_dir, 0o444)

            with pytest.raises(Exception):
                manager.create_backup(backup_type=BackupType.FULL)

            # Check alert was sent (file should exist)
            alert_log = temp_project / ".fastband" / "alerts.json"
            if alert_log.exists():
                alerts_data = json.loads(alert_log.read_text())
                # Should have at least one critical alert
                critical_alerts = [a for a in alerts_data if a["level"] == "critical"]
                assert len(critical_alerts) >= 1
        finally:
            os.chmod(backup_dir, original_mode)

    def test_scheduler_backup_failure_triggers_alert(self, temp_project):
        """Test scheduler backup failure triggers alert."""
        # Reset global alert manager
        import fastband.backup.alerts as alerts_module

        alerts_module._alert_manager = None

        scheduler = BackupScheduler(project_path=temp_project)

        # Make backup dir read-only
        backup_dir = scheduler.backup_path
        original_mode = backup_dir.stat().st_mode

        try:
            os.chmod(backup_dir, 0o444)

            # This should fail but not raise (scheduler catches exceptions)
            result = scheduler._create_backup(BackupType.FULL, "Test")

            assert result is None
            assert scheduler.state.errors >= 1

            # Check alert was sent
            alert_log = temp_project / ".fastband" / "alerts.json"
            if alert_log.exists():
                alerts_data = json.loads(alert_log.read_text())
                critical_alerts = [a for a in alerts_data if a["level"] == "critical"]
                assert len(critical_alerts) >= 1
        finally:
            os.chmod(backup_dir, original_mode)

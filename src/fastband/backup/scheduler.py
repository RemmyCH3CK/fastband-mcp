"""
Backup Scheduler implementation.

Provides automatic backup scheduling with:
- Interval-based backups (default: every 2 hours)
- Hook-based backups (before build, after ticket completion)
- Background daemon management
"""

import asyncio
import json
import logging
import os
import signal
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from fastband.backup.manager import BackupInfo, BackupManager, BackupType
from fastband.core.config import BackupConfig, get_config

# Import alerts (lazy to avoid circular imports)
_alerts_module = None


def _get_alerts():
    """Lazy import of alerts module."""
    global _alerts_module
    if _alerts_module is None:
        from fastband.backup import alerts

        _alerts_module = alerts
    return _alerts_module


logger = logging.getLogger(__name__)


@dataclass
class SchedulerState:
    """Scheduler runtime state."""

    running: bool = False
    pid: int | None = None
    started_at: datetime | None = None
    last_backup_at: datetime | None = None
    next_backup_at: datetime | None = None
    backups_created: int = 0
    errors: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "running": self.running,
            "pid": self.pid,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "last_backup_at": self.last_backup_at.isoformat() if self.last_backup_at else None,
            "next_backup_at": self.next_backup_at.isoformat() if self.next_backup_at else None,
            "backups_created": self.backups_created,
            "errors": self.errors,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SchedulerState":
        """Create from dictionary."""
        return cls(
            running=data.get("running", False),
            pid=data.get("pid"),
            started_at=datetime.fromisoformat(data["started_at"])
            if data.get("started_at")
            else None,
            last_backup_at=datetime.fromisoformat(data["last_backup_at"])
            if data.get("last_backup_at")
            else None,
            next_backup_at=datetime.fromisoformat(data["next_backup_at"])
            if data.get("next_backup_at")
            else None,
            backups_created=data.get("backups_created", 0),
            errors=data.get("errors", 0),
        )


class BackupScheduler:
    """
    Manages scheduled backups for a project.

    Features:
    - Interval-based full backups (configurable, default 2 hours)
    - Hook triggers for before_build and after_ticket_completion
    - Background daemon with PID file management
    - State persistence across restarts
    """

    def __init__(
        self,
        project_path: Path | None = None,
        config: BackupConfig | None = None,
    ):
        """
        Initialize the backup scheduler.

        Args:
            project_path: Path to the project directory
            config: Backup configuration
        """
        self.project_path = Path(project_path or Path.cwd()).resolve()
        self.fastband_dir = self.project_path / ".fastband"
        self.state_file = self.fastband_dir / "scheduler_state.json"
        self.pid_file = self.fastband_dir / "scheduler.pid"
        self.log_file = self.fastband_dir / "scheduler.log"

        # Load config
        if config:
            self.config = config
        else:
            full_config = get_config(self.project_path)
            self.config = full_config.backup

        # Get backup path from config
        backup_path = self.config.backup_path
        if not Path(backup_path).is_absolute():
            backup_path = str(self.project_path / backup_path)
        self.backup_path = Path(backup_path)

        # Create backup manager with custom path
        self.manager = BackupManager(project_path=self.project_path)
        # Override backup directory
        self.manager.backup_dir = self.backup_path
        self.manager.manifest_path = self.backup_path / "manifest.json"
        self.backup_path.mkdir(parents=True, exist_ok=True)

        # State
        self.state = self._load_state()
        self._running = False
        self._shutdown_event: asyncio.Event | None = None

    def _load_state(self) -> SchedulerState:
        """Load scheduler state from file."""
        if self.state_file.exists():
            try:
                data = json.loads(self.state_file.read_text())
                return SchedulerState.from_dict(data)
            except (json.JSONDecodeError, KeyError):
                pass
        return SchedulerState()

    def _save_state(self) -> None:
        """Save scheduler state to file."""
        self.fastband_dir.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text(json.dumps(self.state.to_dict(), indent=2))

    def _write_pid(self) -> None:
        """Write PID file."""
        self.pid_file.write_text(str(os.getpid()))

    def _read_pid(self) -> int | None:
        """Read PID from file."""
        if self.pid_file.exists():
            try:
                return int(self.pid_file.read_text().strip())
            except (ValueError, OSError):
                pass
        return None

    def _remove_pid(self) -> None:
        """Remove PID file."""
        if self.pid_file.exists():
            self.pid_file.unlink()

    def _is_process_running(self, pid: int) -> bool:
        """Check if a process is running."""
        try:
            os.kill(pid, 0)
            return True
        except (OSError, ProcessLookupError):
            return False

    def is_running(self) -> bool:
        """Check if scheduler is running."""
        pid = self._read_pid()
        if pid and self._is_process_running(pid):
            return True
        # Clean up stale PID file
        if pid:
            self._remove_pid()
            self.state.running = False
            self._save_state()
        return False

    def get_status(self) -> dict[str, Any]:
        """Get scheduler status."""
        running = self.is_running()
        state = self._load_state()

        return {
            "running": running,
            "pid": self._read_pid() if running else None,
            "config": {
                "enabled": self.config.enabled,
                "scheduler_enabled": self.config.scheduler_enabled,
                "interval_hours": self.config.interval_hours,
                "backup_path": str(self.backup_path),
                "retention_days": self.config.retention_days,
                "hooks": {
                    "before_build": self.config.hooks.before_build,
                    "after_ticket_completion": self.config.hooks.after_ticket_completion,
                    "on_config_change": self.config.hooks.on_config_change,
                },
            },
            "state": state.to_dict(),
            "next_backup_in": self._time_until_next_backup(state) if running else None,
        }

    def _time_until_next_backup(self, state: SchedulerState) -> str | None:
        """Calculate time until next backup."""
        if not state.next_backup_at:
            return None

        delta = state.next_backup_at - datetime.now()
        if delta.total_seconds() < 0:
            return "imminent"

        hours, remainder = divmod(int(delta.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)

        if hours > 0:
            return f"{hours}h {minutes}m"
        elif minutes > 0:
            return f"{minutes}m {seconds}s"
        else:
            return f"{seconds}s"

    def _create_backup(self, backup_type: BackupType, description: str = "") -> BackupInfo | None:
        """Create a backup and update state."""
        try:
            backup_info = self.manager.create_backup(
                backup_type=backup_type,
                description=description,
                force=True,  # Always create scheduled backups
            )

            if backup_info:
                self.state.last_backup_at = datetime.now()
                self.state.backups_created += 1
                self._save_state()

                # Prune old backups based on retention
                self._prune_old_backups()

                logger.info(f"Backup created: {backup_info.id} ({backup_info.size_human})")
                return backup_info

        except Exception as e:
            self.state.errors += 1
            self._save_state()
            logger.error(f"Backup failed: {e}")

            # Send CRITICAL alert (fire alarm)
            try:
                alerts = _get_alerts()
                alerts.send_backup_failure_alert(
                    message=f"Scheduled backup failed: {description or backup_type.value}",
                    error=e,
                    context={
                        "backup_type": backup_type.value,
                        "description": description,
                        "project_path": str(self.project_path),
                        "scheduler_errors": self.state.errors,
                    },
                    project_path=self.project_path,
                )
            except Exception as alert_error:
                logger.error(f"Failed to send backup failure alert: {alert_error}")

        return None

    def _prune_old_backups(self) -> None:
        """Prune backups older than retention period."""
        backups = self.manager.list_backups()
        cutoff = datetime.now() - timedelta(days=self.config.retention_days)

        pruned_count = 0
        for backup in backups:
            if backup.created_at < cutoff:
                if self.manager.delete_backup(backup.id):
                    pruned_count += 1

        # Also enforce max_backups limit
        remaining = self.manager.list_backups()
        if len(remaining) > self.config.max_backups:
            # Delete oldest backups
            to_delete = remaining[self.config.max_backups :]
            for backup in to_delete:
                if self.manager.delete_backup(backup.id):
                    pruned_count += 1

        if pruned_count > 0:
            logger.info(f"Pruned {pruned_count} old backups")

    # =========================================================================
    # HOOK METHODS - Called by external code
    # =========================================================================

    def trigger_before_build(self) -> BackupInfo | None:
        """
        Trigger backup before a build operation.

        Called by build commands when hooks.before_build is enabled.
        """
        if not self.config.enabled or not self.config.hooks.before_build:
            return None

        logger.info("Triggering pre-build backup")
        return self._create_backup(BackupType.ON_CHANGE, description="Pre-build backup")

    def trigger_after_ticket_completion(self, ticket_id: str = "") -> BackupInfo | None:
        """
        Trigger backup after ticket completion.

        Called by ticket completion code when hooks.after_ticket_completion is enabled.
        """
        if not self.config.enabled or not self.config.hooks.after_ticket_completion:
            return None

        description = "Post-completion backup"
        if ticket_id:
            description = f"Post-completion backup (ticket #{ticket_id})"

        logger.info("Triggering post-ticket-completion backup")
        return self._create_backup(BackupType.ON_CHANGE, description=description)

    def trigger_on_config_change(self) -> BackupInfo | None:
        """
        Trigger backup when configuration changes.

        Called when config files are modified.
        """
        if not self.config.enabled or not self.config.hooks.on_config_change:
            return None

        logger.info("Triggering config-change backup")
        return self._create_backup(BackupType.ON_CHANGE, description="Config change backup")

    # =========================================================================
    # DAEMON METHODS
    # =========================================================================

    async def _run_scheduler_loop(self) -> None:
        """Main scheduler loop."""
        interval_seconds = self.config.interval_hours * 3600

        while self._running:
            # Calculate next backup time
            self.state.next_backup_at = datetime.now() + timedelta(seconds=interval_seconds)
            self._save_state()

            # Wait for interval or shutdown
            try:
                await asyncio.wait_for(self._shutdown_event.wait(), timeout=interval_seconds)
                # Shutdown requested
                break
            except asyncio.TimeoutError:
                # Interval elapsed, create backup
                pass

            if not self._running:
                break

            # Create scheduled backup
            self._create_backup(
                BackupType.FULL,
                description=f"Scheduled backup (every {self.config.interval_hours}h)",
            )

    def start_daemon(self, foreground: bool = False) -> bool:
        """
        Start the backup scheduler daemon.

        Args:
            foreground: Run in foreground instead of daemonizing

        Returns:
            True if started successfully
        """
        if self.is_running():
            logger.warning("Scheduler is already running")
            return False

        if not self.config.enabled or not self.config.scheduler_enabled:
            logger.warning("Scheduler is disabled in config")
            return False

        if foreground:
            return self._run_foreground()
        else:
            return self._daemonize()

    def _run_foreground(self) -> bool:
        """Run scheduler in foreground."""
        self._running = True
        self._shutdown_event = asyncio.Event()

        # Set up signal handlers
        def handle_shutdown(signum, frame):
            logger.info("Shutdown signal received")
            self._running = False
            if self._shutdown_event:
                self._shutdown_event.set()

        signal.signal(signal.SIGTERM, handle_shutdown)
        signal.signal(signal.SIGINT, handle_shutdown)

        # Write PID and update state
        self._write_pid()
        self.state.running = True
        self.state.pid = os.getpid()
        self.state.started_at = datetime.now()
        self.state.next_backup_at = datetime.now() + timedelta(hours=self.config.interval_hours)
        self._save_state()

        logger.info(
            f"Scheduler started (PID: {os.getpid()}, interval: {self.config.interval_hours}h)"
        )

        # Create initial backup
        self._create_backup(BackupType.FULL, description="Scheduler start backup")

        try:
            asyncio.run(self._run_scheduler_loop())
        finally:
            self._running = False
            self.state.running = False
            self._save_state()
            self._remove_pid()
            logger.info("Scheduler stopped")

        return True

    def _daemonize(self) -> bool:
        """Fork and run as daemon."""
        # Double fork to prevent zombie processes
        try:
            pid = os.fork()
            if pid > 0:
                # Parent returns immediately
                # Wait a moment for child to write PID
                time.sleep(0.5)
                return self.is_running()
        except OSError as e:
            logger.error(f"Fork failed: {e}")
            return False

        # Child process
        os.setsid()

        try:
            pid = os.fork()
            if pid > 0:
                os._exit(0)
        except OSError as e:
            logger.error(f"Second fork failed: {e}")
            os._exit(1)

        # Grandchild - the actual daemon
        # Redirect stdout/stderr to log file
        sys.stdout.flush()
        sys.stderr.flush()

        # Set up logging to file
        self.fastband_dir.mkdir(parents=True, exist_ok=True)
        logging.basicConfig(
            filename=str(self.log_file),
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )

        # Run the scheduler
        self._run_foreground()
        os._exit(0)

    def stop_daemon(self) -> bool:
        """
        Stop the running scheduler daemon.

        Returns:
            True if stopped successfully
        """
        pid = self._read_pid()
        if not pid:
            logger.info("No scheduler running (no PID file)")
            return True

        if not self._is_process_running(pid):
            self._remove_pid()
            self.state.running = False
            self._save_state()
            logger.info("Scheduler was not running (stale PID)")
            return True

        try:
            os.kill(pid, signal.SIGTERM)
            # Wait for process to stop
            for _ in range(30):  # Wait up to 3 seconds
                if not self._is_process_running(pid):
                    break
                time.sleep(0.1)

            if self._is_process_running(pid):
                # Force kill
                os.kill(pid, signal.SIGKILL)
                time.sleep(0.1)

            self._remove_pid()
            self.state.running = False
            self._save_state()
            logger.info(f"Scheduler stopped (PID: {pid})")
            return True

        except ProcessLookupError:
            self._remove_pid()
            self.state.running = False
            self._save_state()
            return True
        except Exception as e:
            logger.error(f"Failed to stop scheduler: {e}")
            return False


# Convenience functions


def get_scheduler(project_path: Path | None = None) -> BackupScheduler:
    """Get a BackupScheduler instance for a project."""
    return BackupScheduler(project_path=project_path)


def trigger_backup_hook(
    hook_type: str, project_path: Path | None = None, **kwargs
) -> BackupInfo | None:
    """
    Trigger a backup hook.

    Args:
        hook_type: Type of hook ("before_build", "after_ticket_completion", "on_config_change")
        project_path: Path to the project
        **kwargs: Additional arguments for the hook

    Returns:
        BackupInfo if backup created, None otherwise
    """
    scheduler = get_scheduler(project_path)

    if hook_type == "before_build":
        return scheduler.trigger_before_build()
    elif hook_type == "after_ticket_completion":
        return scheduler.trigger_after_ticket_completion(kwargs.get("ticket_id", ""))
    elif hook_type == "on_config_change":
        return scheduler.trigger_on_config_change()
    else:
        logger.warning(f"Unknown hook type: {hook_type}")
        return None

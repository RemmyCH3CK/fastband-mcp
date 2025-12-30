"""
Fastband Backup Manager.

Provides automated backup functionality for Fastband projects including:
- Full and incremental backups
- Change detection
- Retention policy management
- Restore capabilities
- Scheduled backups with interval and hooks
- Fire-alarm alerts for backup failures
"""

from fastband.backup.alerts import (
    Alert,
    AlertConfig,
    AlertLevel,
    AlertManager,
    get_alert_manager,
    send_backup_alert,
    send_backup_failure_alert,
)
from fastband.backup.manager import (
    BackupInfo,
    BackupManager,
    BackupType,
    get_backup_manager,
)
from fastband.backup.scheduler import (
    BackupScheduler,
    SchedulerState,
    get_scheduler,
    trigger_backup_hook,
)

__all__ = [
    # Manager
    "BackupManager",
    "BackupInfo",
    "BackupType",
    "get_backup_manager",
    # Scheduler
    "BackupScheduler",
    "SchedulerState",
    "get_scheduler",
    "trigger_backup_hook",
    # Alerts
    "Alert",
    "AlertConfig",
    "AlertLevel",
    "AlertManager",
    "get_alert_manager",
    "send_backup_alert",
    "send_backup_failure_alert",
]

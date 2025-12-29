"""
Fastband Backup Manager.

Provides automated backup functionality for Fastband projects including:
- Full and incremental backups
- Change detection
- Retention policy management
- Restore capabilities
- Scheduled backups with interval and hooks
"""

from fastband.backup.manager import (
    BackupManager,
    BackupInfo,
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
]

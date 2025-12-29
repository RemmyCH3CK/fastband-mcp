"""
Fastband Backup Manager.

Provides automated backup functionality for Fastband projects including:
- Full and incremental backups
- Change detection
- Retention policy management
- Restore capabilities
"""

from fastband.backup.manager import (
    BackupManager,
    BackupInfo,
    BackupType,
    get_backup_manager,
)

__all__ = [
    "BackupManager",
    "BackupInfo",
    "BackupType",
    "get_backup_manager",
]

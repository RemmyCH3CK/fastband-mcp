"""
Backup Manager implementation.

Handles creation, restoration, and management of project backups.
"""

import hashlib
import json
import logging
import shutil
import tarfile
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any

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


class BackupType(Enum):
    """Type of backup."""

    FULL = "full"
    INCREMENTAL = "incremental"
    ON_CHANGE = "on_change"
    MANUAL = "manual"


@dataclass
class BackupInfo:
    """Information about a backup."""

    id: str
    backup_type: BackupType
    created_at: datetime
    size_bytes: int
    files_count: int
    checksum: str
    description: str = ""
    parent_id: str | None = None  # For incremental backups
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "backup_type": self.backup_type.value,
            "created_at": self.created_at.isoformat(),
            "size_bytes": self.size_bytes,
            "files_count": self.files_count,
            "checksum": self.checksum,
            "description": self.description,
            "parent_id": self.parent_id,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BackupInfo":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            backup_type=BackupType(data["backup_type"]),
            created_at=datetime.fromisoformat(data["created_at"]),
            size_bytes=data["size_bytes"],
            files_count=data["files_count"],
            checksum=data["checksum"],
            description=data.get("description", ""),
            parent_id=data.get("parent_id"),
            metadata=data.get("metadata", {}),
        )

    @property
    def filename(self) -> str:
        """Get the backup filename."""
        return f"backup_{self.id}.tar.gz"

    @property
    def size_human(self) -> str:
        """Get human-readable size."""
        size = self.size_bytes
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"


class BackupManager:
    """
    Manages project backups.

    Handles:
    - Creating full and incremental backups
    - Change detection for smart backups
    - Retention policy enforcement
    - Restore operations
    """

    # Files/directories to always back up
    BACKUP_TARGETS = [
        ".fastband/config.yaml",
        ".fastband/tickets.json",
        ".fastband/agents.json",
        ".fastband/ops_log.json",
    ]

    # Directories to back up (if they exist)
    BACKUP_DIRS = [
        ".fastband/memory",
        ".fastband/cache",
    ]

    # Files to exclude from backups
    EXCLUDE_PATTERNS = [
        "*.pyc",
        "__pycache__",
        ".git",
        "node_modules",
        ".venv",
        "venv",
        "*.log",
        ".DS_Store",
    ]

    def __init__(
        self,
        project_path: Path | None = None,
        config: BackupConfig | None = None,
    ):
        """
        Initialize the backup manager.

        Args:
            project_path: Path to the project directory
            config: Backup configuration (loaded from project config if not provided)
        """
        self.project_path = Path(project_path or Path.cwd()).resolve()
        self.fastband_dir = self.project_path / ".fastband"
        self.backup_dir = self.fastband_dir / "backups"
        self.manifest_path = self.backup_dir / "manifest.json"
        self.checksum_cache_path = self.backup_dir / ".checksums"

        # Load config
        if config:
            self.config = config
        else:
            full_config = get_config(self.project_path)
            self.config = full_config.backup

        # Ensure backup directory exists
        self.backup_dir.mkdir(parents=True, exist_ok=True)

        # Load manifest
        self._manifest = self._load_manifest()

    def _load_manifest(self) -> dict[str, Any]:
        """Load the backup manifest."""
        if self.manifest_path.exists():
            try:
                return json.loads(self.manifest_path.read_text())
            except (json.JSONDecodeError, OSError):
                pass
        return {"backups": [], "last_checksum": None}

    def _save_manifest(self) -> None:
        """Save the backup manifest."""
        self.manifest_path.write_text(json.dumps(self._manifest, indent=2, default=str))

    def _calculate_checksum(self, file_path: Path) -> str:
        """Calculate MD5 checksum of a file."""
        hash_md5 = hashlib.md5()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except OSError:
            return ""

    def _calculate_content_checksum(self) -> str:
        """Calculate a combined checksum of all backup targets."""
        checksums = []
        for target in self.BACKUP_TARGETS:
            target_path = self.project_path / target
            if target_path.exists():
                checksums.append(self._calculate_checksum(target_path))

        for dir_name in self.BACKUP_DIRS:
            dir_path = self.project_path / dir_name
            if dir_path.exists() and dir_path.is_dir():
                for file_path in sorted(dir_path.rglob("*")):
                    if file_path.is_file():
                        checksums.append(self._calculate_checksum(file_path))

        return hashlib.md5("".join(checksums).encode()).hexdigest()

    def has_changes(self) -> bool:
        """
        Check if there are changes since the last backup.

        Returns:
            True if changes detected, False otherwise
        """
        current_checksum = self._calculate_content_checksum()
        last_checksum = self._manifest.get("last_checksum")
        return current_checksum != last_checksum

    def _generate_backup_id(self) -> str:
        """Generate a unique backup ID with microseconds for uniqueness."""
        import uuid

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # Add short UUID suffix to prevent collisions when multiple backups
        # are created in the same second (e.g., pre-restore backup)
        suffix = uuid.uuid4().hex[:6]
        return f"{timestamp}_{suffix}"

    def _should_exclude(self, path: Path) -> bool:
        """Check if a path should be excluded from backup."""
        name = path.name
        for pattern in self.EXCLUDE_PATTERNS:
            if pattern.startswith("*"):
                if name.endswith(pattern[1:]):
                    return True
            elif name == pattern:
                return True
        return False

    def create_backup(
        self,
        backup_type: BackupType = BackupType.MANUAL,
        description: str = "",
        force: bool = False,
    ) -> BackupInfo | None:
        """
        Create a new backup.

        Args:
            backup_type: Type of backup to create
            description: Optional description for the backup
            force: Create backup even if no changes detected

        Returns:
            BackupInfo if backup created, None if skipped
        """
        # Check for changes if using on_change type
        if backup_type == BackupType.ON_CHANGE and not force:
            if not self.has_changes():
                logger.info("No changes detected, skipping backup")
                return None

        backup_id = self._generate_backup_id()
        backup_filename = f"backup_{backup_id}.tar.gz"
        backup_path = self.backup_dir / backup_filename

        logger.info(f"Creating backup: {backup_id}")

        files_count = 0
        temp_dir = self.backup_dir / f".temp_{backup_id}"

        try:
            # Create temp directory for staging
            temp_dir.mkdir(parents=True, exist_ok=True)

            # Copy files to temp directory
            for target in self.BACKUP_TARGETS:
                source = self.project_path / target
                if source.exists():
                    dest = temp_dir / target
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, dest)
                    files_count += 1

            # Copy directories
            for dir_name in self.BACKUP_DIRS:
                source_dir = self.project_path / dir_name
                if source_dir.exists() and source_dir.is_dir():
                    dest_dir = temp_dir / dir_name
                    shutil.copytree(
                        source_dir,
                        dest_dir,
                        ignore=shutil.ignore_patterns(*self.EXCLUDE_PATTERNS),
                    )
                    files_count += sum(1 for _ in dest_dir.rglob("*") if _.is_file())

            # Create compressed archive
            with tarfile.open(backup_path, "w:gz") as tar:
                tar.add(temp_dir, arcname=".")

            # Calculate checksum of backup file
            backup_checksum = self._calculate_checksum(backup_path)
            backup_size = backup_path.stat().st_size

            # Create backup info
            backup_info = BackupInfo(
                id=backup_id,
                backup_type=backup_type,
                created_at=datetime.now(),
                size_bytes=backup_size,
                files_count=files_count,
                checksum=backup_checksum,
                description=description,
                metadata={
                    "project_path": str(self.project_path),
                    "fastband_version": "1.2025.12",
                },
            )

            # Update manifest
            self._manifest["backups"].append(backup_info.to_dict())
            self._manifest["last_checksum"] = self._calculate_content_checksum()
            self._save_manifest()

            logger.info(
                f"Backup created: {backup_id} ({backup_info.size_human}, {files_count} files)"
            )
            return backup_info

        except Exception as e:
            logger.error(f"Backup failed: {e}")
            # Clean up failed backup
            if backup_path.exists():
                backup_path.unlink()

            # Send CRITICAL alert (fire alarm)
            try:
                alerts = _get_alerts()
                alerts.send_backup_failure_alert(
                    message=f"Backup creation failed: {description or backup_type.value}",
                    error=e,
                    context={
                        "backup_type": backup_type.value,
                        "description": description,
                        "project_path": str(self.project_path),
                    },
                    project_path=self.project_path,
                )
            except Exception as alert_error:
                logger.error(f"Failed to send backup failure alert: {alert_error}")

            raise

        finally:
            # Clean up temp directory
            if temp_dir.exists():
                shutil.rmtree(temp_dir)

    def list_backups(self) -> list[BackupInfo]:
        """
        List all available backups.

        Returns:
            List of BackupInfo objects, sorted by creation date (newest first)
        """
        backups = []
        for backup_data in self._manifest.get("backups", []):
            try:
                backup_info = BackupInfo.from_dict(backup_data)
                # Verify backup file exists
                backup_path = self.backup_dir / backup_info.filename
                if backup_path.exists():
                    backups.append(backup_info)
            except (KeyError, ValueError) as e:
                logger.warning(f"Invalid backup entry in manifest: {e}")

        # Sort by creation date (newest first)
        backups.sort(key=lambda b: b.created_at, reverse=True)
        return backups

    def get_backup(self, backup_id: str) -> BackupInfo | None:
        """
        Get information about a specific backup.

        Args:
            backup_id: ID of the backup

        Returns:
            BackupInfo if found, None otherwise
        """
        for backup in self.list_backups():
            if backup.id == backup_id:
                return backup
        return None

    def restore_backup(
        self,
        backup_id: str,
        target_path: Path | None = None,
        dry_run: bool = False,
    ) -> bool:
        """
        Restore from a backup.

        Args:
            backup_id: ID of the backup to restore
            target_path: Where to restore (default: project_path)
            dry_run: If True, only show what would be restored

        Returns:
            True if restore succeeded, False otherwise
        """
        backup_info = self.get_backup(backup_id)
        if not backup_info:
            logger.error(f"Backup not found: {backup_id}")
            return False

        backup_path = self.backup_dir / backup_info.filename
        if not backup_path.exists():
            logger.error(f"Backup file missing: {backup_path}")
            return False

        # Verify checksum
        current_checksum = self._calculate_checksum(backup_path)
        if current_checksum != backup_info.checksum:
            logger.error("Backup checksum mismatch - file may be corrupted")
            return False

        restore_path = Path(target_path) if target_path else self.project_path

        if dry_run:
            logger.info(f"Would restore backup {backup_id} to {restore_path}")
            with tarfile.open(backup_path, "r:gz") as tar:
                for member in tar.getmembers():
                    logger.info(f"  Would restore: {member.name}")
            return True

        logger.info(f"Restoring backup {backup_id} to {restore_path}")

        try:
            # Create a pre-restore backup
            pre_restore_backup = self.create_backup(
                backup_type=BackupType.MANUAL,
                description=f"Pre-restore backup before restoring {backup_id}",
            )
            if pre_restore_backup:
                logger.info(f"Created pre-restore backup: {pre_restore_backup.id}")

            # Extract backup to system temp directory (outside project path)
            # to avoid deleting extracted content when restoring .fastband
            import tempfile

            with tempfile.TemporaryDirectory(prefix=f"fastband_restore_{backup_id}_") as temp_dir:
                temp_path = Path(temp_dir)

                with tarfile.open(backup_path, "r:gz") as tar:
                    tar.extractall(temp_path)

                # Move files to target (outside tarfile context)
                for item in temp_path.iterdir():
                    target = restore_path / item.name
                    if item.is_dir():
                        if target.exists():
                            shutil.rmtree(target)
                        shutil.copytree(item, target)
                    else:
                        target.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(item, target)

            logger.info(f"Restore completed: {backup_info.files_count} files")
            return True

        except Exception as e:
            logger.error(f"Restore failed: {e}")

            # Send CRITICAL alert (fire alarm)
            try:
                alerts = _get_alerts()
                alerts.send_backup_failure_alert(
                    message=f"Backup restore failed: {backup_id}",
                    error=e,
                    context={
                        "backup_id": backup_id,
                        "target_path": str(restore_path),
                        "project_path": str(self.project_path),
                    },
                    project_path=self.project_path,
                )
            except Exception as alert_error:
                logger.error(f"Failed to send restore failure alert: {alert_error}")

            return False

    def delete_backup(self, backup_id: str) -> bool:
        """
        Delete a specific backup.

        Args:
            backup_id: ID of the backup to delete

        Returns:
            True if deleted, False otherwise
        """
        backup_info = self.get_backup(backup_id)
        if not backup_info:
            logger.error(f"Backup not found: {backup_id}")
            return False

        backup_path = self.backup_dir / backup_info.filename

        try:
            if backup_path.exists():
                backup_path.unlink()

            # Update manifest
            self._manifest["backups"] = [
                b for b in self._manifest["backups"] if b.get("id") != backup_id
            ]
            self._save_manifest()

            logger.info(f"Deleted backup: {backup_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete backup: {e}")
            return False

    def prune_old_backups(self, dry_run: bool = False) -> list[BackupInfo]:
        """
        Remove old backups based on retention policy.

        Args:
            dry_run: If True, only show what would be pruned

        Returns:
            List of pruned BackupInfo objects
        """
        backups = self.list_backups()
        now = datetime.now()
        pruned = []

        # Separate by type
        daily_backups = [
            b for b in backups if b.backup_type in (BackupType.FULL, BackupType.ON_CHANGE)
        ]
        manual_backups = [b for b in backups if b.backup_type == BackupType.MANUAL]

        # Determine cutoff dates
        daily_cutoff = now - timedelta(days=self.config.daily_retention)
        weekly_cutoff = now - timedelta(weeks=self.config.weekly_retention)

        for backup in daily_backups:
            if backup.created_at < daily_cutoff:
                if dry_run:
                    logger.info(f"Would prune: {backup.id} (created {backup.created_at})")
                else:
                    if self.delete_backup(backup.id):
                        pruned.append(backup)

        # Keep manual backups longer (use weekly retention)
        for backup in manual_backups:
            if backup.created_at < weekly_cutoff:
                if dry_run:
                    logger.info(f"Would prune manual: {backup.id} (created {backup.created_at})")
                else:
                    if self.delete_backup(backup.id):
                        pruned.append(backup)

        if pruned:
            logger.info(f"Pruned {len(pruned)} old backups")
        else:
            logger.info("No backups to prune")

        return pruned

    def get_stats(self) -> dict[str, Any]:
        """
        Get backup statistics.

        Returns:
            Dictionary with backup statistics
        """
        backups = self.list_backups()

        total_size = sum(b.size_bytes for b in backups)
        by_type = {}
        for backup in backups:
            type_name = backup.backup_type.value
            by_type[type_name] = by_type.get(type_name, 0) + 1

        return {
            "total_backups": len(backups),
            "total_size_bytes": total_size,
            "total_size_human": BackupInfo(
                id="",
                backup_type=BackupType.MANUAL,
                created_at=datetime.now(),
                size_bytes=total_size,
                files_count=0,
                checksum="",
            ).size_human
            if total_size > 0
            else "0 B",
            "by_type": by_type,
            "oldest": backups[-1].created_at.isoformat() if backups else None,
            "newest": backups[0].created_at.isoformat() if backups else None,
            "has_changes": self.has_changes(),
            "config": {
                "enabled": self.config.enabled,
                "daily_enabled": self.config.daily_enabled,
                "daily_retention": self.config.daily_retention,
                "weekly_enabled": self.config.weekly_enabled,
                "weekly_retention": self.config.weekly_retention,
                "change_detection": self.config.change_detection,
            },
        }


# Convenience function
def get_backup_manager(project_path: Path | None = None) -> BackupManager:
    """
    Get a BackupManager instance for a project.

    Args:
        project_path: Path to the project directory

    Returns:
        BackupManager instance
    """
    return BackupManager(project_path=project_path)

# Fastband Companion Products

## Overview

Fastband MCP includes two essential companion products that enable enterprise-grade development workflows:

1. **Fastband Backup Manager** - Automated platform backup with change detection
2. **Agent Ops Log** - Multi-agent coordination and collision prevention

These are **mandatory components** for production deployments and are automatically installed with Fastband.

---

## 1. Fastband Backup Manager

### Purpose

Automated, intelligent backup system that:
- Detects changes before creating backups (no unnecessary backups)
- Supports multiple database backends (SQLite, PostgreSQL, MySQL)
- Prevents concurrent backup operations
- Maintains configurable retention policies
- Provides one-command disaster recovery

### Architecture

```
.fastband/
├── backups/
│   ├── daily/
│   │   ├── 2025-12-16_001/
│   │   │   ├── manifest.json       # What's in this backup
│   │   │   ├── code_backup.tar.gz  # Application code
│   │   │   ├── config.tar.gz       # Configuration files
│   │   │   ├── data_backup.tar.gz  # Data files (JSON, etc.)
│   │   │   ├── database.dump       # Database backup
│   │   │   └── git_backup.tar.gz   # Git repository
│   │   └── 2025-12-15_001/
│   │
│   ├── weekly/
│   │   └── 2025-W50/
│   │
│   └── manual/
│       └── before_major_refactor/
│
├── .backup_hash                    # Last backup state hash
├── .backup.lock                    # Concurrent backup prevention
└── backup_config.yaml              # Backup configuration
```

### Core Implementation

```python
# src/fastband/backup/manager.py
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
import hashlib
import fcntl
import tarfile
import shutil
import json


@dataclass
class BackupConfig:
    """Backup configuration."""
    enabled: bool = True

    # Schedule
    daily_enabled: bool = True
    daily_time: str = "02:00"       # 2 AM local
    daily_retention: int = 7        # Keep 7 daily backups

    weekly_enabled: bool = True
    weekly_day: str = "sunday"
    weekly_retention: int = 4       # Keep 4 weekly backups

    # Change detection
    change_detection: bool = True   # Only backup when changes detected

    # What to backup
    backup_code: bool = True
    backup_config: bool = True
    backup_data: bool = True
    backup_database: bool = True
    backup_git: bool = True

    # Exclusions
    exclude_patterns: List[str] = None  # ["*.log", "__pycache__", ".git"]


@dataclass
class BackupManifest:
    """Describes a backup."""
    id: str
    created_at: str
    project_path: str
    backup_type: str              # "daily", "weekly", "manual"
    trigger: str                  # "scheduled", "manual", "pre_operation"
    content_hash: str
    size_bytes: int
    components: Dict[str, bool]   # What was backed up
    database_type: Optional[str]  # "sqlite", "postgres", "mysql"
    retention_until: str          # When this backup can be deleted


class BackupManager:
    """
    Intelligent backup manager with change detection.

    Features:
    - Change detection via content hashing
    - Concurrent backup prevention via file locking
    - Multiple database backend support
    - Configurable retention policies
    - One-command restore
    """

    def __init__(self, project_path: Path, config: Optional[BackupConfig] = None):
        self.project_path = project_path
        self.fastband_dir = project_path / ".fastband"
        self.backup_dir = self.fastband_dir / "backups"
        self.lock_file = self.fastband_dir / ".backup.lock"
        self.hash_file = self.fastband_dir / ".backup_hash"
        self.config = config or self._load_config()

        self._ensure_structure()

    def _ensure_structure(self):
        """Create backup directory structure."""
        (self.backup_dir / "daily").mkdir(parents=True, exist_ok=True)
        (self.backup_dir / "weekly").mkdir(parents=True, exist_ok=True)
        (self.backup_dir / "manual").mkdir(parents=True, exist_ok=True)

    # =========================================================================
    # CHANGE DETECTION
    # =========================================================================

    def calculate_content_hash(self) -> str:
        """
        Calculate hash of project content for change detection.

        Hashes all tracked files to detect if anything changed since last backup.
        """
        hasher = hashlib.md5()

        # File patterns to include in hash
        patterns = ["*.py", "*.js", "*.ts", "*.html", "*.css", "*.json", "*.yaml", "*.yml"]

        # Directories to exclude
        exclude_dirs = {".git", "__pycache__", "node_modules", "logs", "thumbnails", ".fastband"}

        for pattern in patterns:
            for file_path in self.project_path.rglob(pattern):
                # Skip excluded directories
                if any(excluded in file_path.parts for excluded in exclude_dirs):
                    continue

                try:
                    with open(file_path, "rb") as f:
                        hasher.update(f.read())
                except (IOError, OSError):
                    continue

        return hasher.hexdigest()

    def has_changes(self) -> bool:
        """Check if project has changed since last backup."""
        if not self.config.change_detection:
            return True  # Always backup if change detection disabled

        current_hash = self.calculate_content_hash()

        if not self.hash_file.exists():
            return True  # No previous backup

        last_hash = self.hash_file.read_text().strip()
        return current_hash != last_hash

    def _save_hash(self, hash_value: str):
        """Save current content hash after backup."""
        self.hash_file.write_text(hash_value)

    # =========================================================================
    # LOCKING
    # =========================================================================

    def _acquire_lock(self) -> bool:
        """Acquire backup lock to prevent concurrent backups."""
        try:
            self.lock_file.parent.mkdir(parents=True, exist_ok=True)
            self._lock_fd = open(self.lock_file, "w")

            # Write PID for debugging
            self._lock_fd.write(str(os.getpid()))
            self._lock_fd.flush()

            # Try non-blocking lock
            fcntl.flock(self._lock_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True

        except (IOError, OSError):
            return False

    def _release_lock(self):
        """Release backup lock."""
        if hasattr(self, "_lock_fd") and self._lock_fd:
            try:
                fcntl.flock(self._lock_fd.fileno(), fcntl.LOCK_UN)
                self._lock_fd.close()
            except Exception:
                pass

    # =========================================================================
    # BACKUP OPERATIONS
    # =========================================================================

    def create_backup(
        self,
        backup_type: str = "manual",
        trigger: str = "manual",
        name: Optional[str] = None,
        force: bool = False,
    ) -> Dict[str, Any]:
        """
        Create a full backup of the project.

        Args:
            backup_type: "daily", "weekly", or "manual"
            trigger: What triggered this backup
            name: Optional custom name for manual backups
            force: Bypass change detection

        Returns:
            Dict with backup result and manifest
        """
        # Check for changes unless forced
        if not force and not self.has_changes():
            return {
                "success": True,
                "skipped": True,
                "reason": "No changes detected since last backup",
            }

        # Acquire lock
        if not self._acquire_lock():
            return {
                "success": False,
                "error": "Another backup is in progress",
            }

        try:
            # Generate backup ID and directory
            timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
            if name:
                backup_id = f"{name}_{timestamp}"
            else:
                backup_id = timestamp

            backup_path = self.backup_dir / backup_type / backup_id
            backup_path.mkdir(parents=True, exist_ok=True)

            manifest = BackupManifest(
                id=backup_id,
                created_at=datetime.now().isoformat(),
                project_path=str(self.project_path),
                backup_type=backup_type,
                trigger=trigger,
                content_hash=self.calculate_content_hash(),
                size_bytes=0,
                components={},
                database_type=None,
                retention_until=self._calculate_retention(backup_type),
            )

            total_size = 0

            # Backup components
            if self.config.backup_code:
                size = self._backup_code(backup_path)
                manifest.components["code"] = True
                total_size += size

            if self.config.backup_config:
                size = self._backup_config(backup_path)
                manifest.components["config"] = True
                total_size += size

            if self.config.backup_data:
                size = self._backup_data(backup_path)
                manifest.components["data"] = True
                total_size += size

            if self.config.backup_database:
                db_type, size = self._backup_database(backup_path)
                manifest.components["database"] = True
                manifest.database_type = db_type
                total_size += size

            if self.config.backup_git:
                size = self._backup_git(backup_path)
                manifest.components["git"] = True
                total_size += size

            manifest.size_bytes = total_size

            # Save manifest
            manifest_path = backup_path / "manifest.json"
            with open(manifest_path, "w") as f:
                json.dump(manifest.__dict__, f, indent=2)

            # Update content hash
            self._save_hash(manifest.content_hash)

            # Cleanup old backups
            self._cleanup_old_backups(backup_type)

            return {
                "success": True,
                "backup_id": backup_id,
                "path": str(backup_path),
                "size_bytes": total_size,
                "manifest": manifest.__dict__,
            }

        finally:
            self._release_lock()

    def _backup_code(self, backup_path: Path) -> int:
        """Backup application code."""
        tar_path = backup_path / "code_backup.tar.gz"

        exclude = [
            "data", "logs", "thumbnails", "__pycache__",
            "*.pyc", ".git", ".fastband", "node_modules"
        ]

        with tarfile.open(tar_path, "w:gz") as tar:
            for item in self.project_path.iterdir():
                if item.name not in exclude and not any(
                    item.match(pattern) for pattern in exclude
                ):
                    tar.add(item, arcname=item.name)

        return tar_path.stat().st_size

    def _backup_config(self, backup_path: Path) -> int:
        """Backup configuration files."""
        config_dir = backup_path / "config"
        config_dir.mkdir(exist_ok=True)

        config_files = [".env", "docker-compose.yml", "Dockerfile", "requirements.txt", "package.json"]
        total = 0

        for config_file in config_files:
            src = self.project_path / config_file
            if src.exists():
                shutil.copy2(src, config_dir / config_file)
                total += src.stat().st_size

        return total

    def _backup_data(self, backup_path: Path) -> int:
        """Backup data files."""
        tar_path = backup_path / "data_backup.tar.gz"

        data_dir = self.project_path / "data"
        if not data_dir.exists():
            return 0

        with tarfile.open(tar_path, "w:gz") as tar:
            tar.add(data_dir, arcname="data")

        return tar_path.stat().st_size

    def _backup_database(self, backup_path: Path) -> tuple[str, int]:
        """
        Backup database based on detected type.

        Returns:
            Tuple of (database_type, size_bytes)
        """
        # Detect database type from config
        db_config = self._detect_database_config()

        if db_config["type"] == "sqlite":
            return self._backup_sqlite(backup_path, db_config)
        elif db_config["type"] == "postgres":
            return self._backup_postgres(backup_path, db_config)
        elif db_config["type"] == "mysql":
            return self._backup_mysql(backup_path, db_config)
        else:
            return ("none", 0)

    def _backup_sqlite(self, backup_path: Path, config: dict) -> tuple[str, int]:
        """Backup SQLite database."""
        import sqlite3

        db_path = Path(config["path"])
        if not db_path.exists():
            return ("sqlite", 0)

        backup_db = backup_path / "database.sqlite"

        # Use SQLite's backup API for consistent backup
        src = sqlite3.connect(str(db_path))
        dst = sqlite3.connect(str(backup_db))
        src.backup(dst)
        src.close()
        dst.close()

        return ("sqlite", backup_db.stat().st_size)

    def _backup_postgres(self, backup_path: Path, config: dict) -> tuple[str, int]:
        """Backup PostgreSQL database."""
        import subprocess

        backup_file = backup_path / "database.dump"

        # Use pg_dump with custom format for compression
        cmd = [
            "pg_dump",
            "-h", config.get("host", "localhost"),
            "-p", str(config.get("port", 5432)),
            "-U", config["user"],
            "-Fc",  # Custom format
            config["database"],
        ]

        env = os.environ.copy()
        env["PGPASSWORD"] = config.get("password", "")

        with open(backup_file, "wb") as f:
            subprocess.run(cmd, stdout=f, env=env, check=True)

        return ("postgres", backup_file.stat().st_size)

    def _backup_mysql(self, backup_path: Path, config: dict) -> tuple[str, int]:
        """Backup MySQL database."""
        import subprocess

        backup_file = backup_path / "database.sql.gz"

        cmd = [
            "mysqldump",
            "-h", config.get("host", "localhost"),
            "-P", str(config.get("port", 3306)),
            "-u", config["user"],
            f"-p{config.get('password', '')}",
            config["database"],
        ]

        # Pipe through gzip for compression
        with open(backup_file, "wb") as f:
            dump = subprocess.Popen(cmd, stdout=subprocess.PIPE)
            subprocess.run(["gzip"], stdin=dump.stdout, stdout=f)
            dump.wait()

        return ("mysql", backup_file.stat().st_size)

    def _backup_git(self, backup_path: Path) -> int:
        """Backup git repository."""
        git_dir = self.project_path / ".git"
        if not git_dir.exists():
            return 0

        tar_path = backup_path / "git_backup.tar.gz"

        with tarfile.open(tar_path, "w:gz") as tar:
            tar.add(git_dir, arcname=".git")

        return tar_path.stat().st_size

    # =========================================================================
    # RESTORE OPERATIONS
    # =========================================================================

    def restore(
        self,
        backup_id: str,
        components: Optional[List[str]] = None,
        confirm: bool = False,
    ) -> Dict[str, Any]:
        """
        Restore from a backup.

        Args:
            backup_id: Backup identifier
            components: Which components to restore (None = all)
            confirm: Must be True to execute

        Returns:
            Dict with restore result
        """
        if not confirm:
            return {
                "success": False,
                "error": "Restore requires confirm=True",
                "warning": "This will overwrite current project files!",
            }

        backup_path = self._find_backup(backup_id)
        if not backup_path:
            return {
                "success": False,
                "error": f"Backup not found: {backup_id}",
            }

        # Load manifest
        manifest_path = backup_path / "manifest.json"
        with open(manifest_path) as f:
            manifest = json.load(f)

        restored = []

        # Restore each component
        if components is None:
            components = list(manifest.get("components", {}).keys())

        if "code" in components and manifest["components"].get("code"):
            self._restore_code(backup_path)
            restored.append("code")

        if "config" in components and manifest["components"].get("config"):
            self._restore_config(backup_path)
            restored.append("config")

        if "data" in components and manifest["components"].get("data"):
            self._restore_data(backup_path)
            restored.append("data")

        if "database" in components and manifest["components"].get("database"):
            self._restore_database(backup_path, manifest["database_type"])
            restored.append("database")

        if "git" in components and manifest["components"].get("git"):
            self._restore_git(backup_path)
            restored.append("git")

        return {
            "success": True,
            "backup_id": backup_id,
            "restored_components": restored,
            "manifest": manifest,
        }

    # =========================================================================
    # RETENTION & CLEANUP
    # =========================================================================

    def _cleanup_old_backups(self, backup_type: str):
        """Remove old backups beyond retention limit."""
        if backup_type == "daily":
            retention = self.config.daily_retention
        elif backup_type == "weekly":
            retention = self.config.weekly_retention
        else:
            return  # Don't auto-cleanup manual backups

        backup_type_dir = self.backup_dir / backup_type
        backups = sorted(backup_type_dir.iterdir(), reverse=True)

        for backup in backups[retention:]:
            shutil.rmtree(backup)

    def list_backups(self) -> List[Dict]:
        """List all available backups."""
        backups = []

        for backup_type in ["daily", "weekly", "manual"]:
            type_dir = self.backup_dir / backup_type
            if not type_dir.exists():
                continue

            for backup_dir in type_dir.iterdir():
                manifest_path = backup_dir / "manifest.json"
                if manifest_path.exists():
                    with open(manifest_path) as f:
                        manifest = json.load(f)
                    backups.append({
                        "id": manifest["id"],
                        "type": backup_type,
                        "created_at": manifest["created_at"],
                        "size_bytes": manifest["size_bytes"],
                        "path": str(backup_dir),
                    })

        return sorted(backups, key=lambda b: b["created_at"], reverse=True)
```

### CLI Commands

```bash
# List available backups
$ fastband backup list
┌────────────────────────────────────────────────────────────────┐
│                      Available Backups                         │
├──────────────┬──────────┬─────────────────┬───────────────────┤
│  Type        │  ID      │  Created        │  Size             │
├──────────────┼──────────┼─────────────────┼───────────────────┤
│  daily       │  12-16   │  2025-12-16 02  │  45.2 MB          │
│  daily       │  12-15   │  2025-12-15 02  │  44.8 MB          │
│  manual      │  pre-ref │  2025-12-14 14  │  43.1 MB          │
│  weekly      │  W50     │  2025-12-08 02  │  42.5 MB          │
└──────────────┴──────────┴─────────────────┴───────────────────┘

# Create manual backup
$ fastband backup create --name "before_migration"
✓ Created backup: before_migration_20251216_143022
  Size: 45.2 MB
  Location: .fastband/backups/manual/before_migration_20251216_143022/

# Restore from backup
$ fastband backup restore 12-15 --confirm
⚠️  This will restore from backup 12-15
    Components: code, config, data, database, git

Restoring...
✓ Restored code
✓ Restored config
✓ Restored data
✓ Restored database (PostgreSQL)
✓ Restored git

✓ Restore complete!

# Check backup status
$ fastband backup status
Last backup: 2025-12-16 02:00:05 (14 hours ago)
Changes since: Yes (3 files modified)
Next scheduled: 2025-12-17 02:00:00

Storage:
  Daily backups: 7 (315 MB)
  Weekly backups: 4 (170 MB)
  Manual backups: 2 (90 MB)
  Total: 575 MB
```

---

## 2. Agent Ops Log (Multi-Agent Coordination)

### Purpose

Enable multiple AI agents to work on the same project simultaneously without conflicts:

- **Clearance System**: Agents request and grant permission for operations
- **Hold Directives**: Pause all agent work during critical operations
- **Rebuild Announcements**: Notify agents when containers are rebuilding
- **Collision Prevention**: Detect when agents might conflict

### Architecture

```
.fastband/
└── agent_ops/
    ├── current.json              # Active log entries
    ├── archive/
    │   ├── 2025-12-15.json       # Archived daily logs
    │   └── 2025-12-14.json
    ├── metadata.json             # Stats and config
    ├── .ops_log.lock             # Write lock
    └── agents/
        ├── MCP_Agent1.json       # Agent session state
        └── MCP_Agent2.json
```

### Event Types

| Event Type | Purpose | Example |
|------------|---------|---------|
| `clearance_granted` | Agent grants permission to others | "MCP_Agent1 grants clearance to MCP_Agent2 for tickets #1205, #1206" |
| `hold` | Pause all agent work | "HOLD: Major database migration in progress" |
| `rebuild_requested` | Container rebuild starting | "Rebuilding mlb-webapp for ticket #1207" |
| `rebuild_complete` | Container rebuild finished | "Rebuild complete, services ready" |
| `ticket_claimed` | Agent starting work on ticket | "MCP_Agent1 claimed ticket #1205" |
| `ticket_completed` | Agent finished work | "MCP_Agent1 completed ticket #1205" |
| `status_update` | General status message | "Starting Phase 4 work" |

### Core Implementation

```python
# src/fastband/coordination/ops_log.py
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
import uuid
import json
import fcntl


@dataclass
class OpsLogEntry:
    """A single operations log entry."""
    id: str
    timestamp: str
    agent: str
    event_type: str
    message: str
    ticket_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def format_display(self) -> str:
        """Human-readable format."""
        ts = self.timestamp[:19].replace('T', ' ')
        ticket = f" [#{self.ticket_id}]" if self.ticket_id else ""
        return f"[{self.agent}][{ts}]{ticket} {self.message}"


class AgentOpsLog:
    """
    Multi-agent coordination through operations logging.

    Key Features:
    - Clearance/hold directives for coordination
    - Rebuild announcements
    - Automatic rotation and retention
    - Fast queries for recent entries
    """

    EVENT_TYPES = {
        "clearance_granted",
        "hold",
        "rebuild_requested",
        "rebuild_complete",
        "ticket_claimed",
        "ticket_completed",
        "status_update",
        "review_complete",
        "general",
    }

    def __init__(self, project_path: Path):
        self.base_path = project_path / ".fastband" / "agent_ops"
        self.current_file = self.base_path / "current.json"
        self.archive_dir = self.base_path / "archive"
        self.lock_file = self.base_path / ".ops_log.lock"

        self._ensure_structure()

    def _ensure_structure(self):
        """Create directory structure."""
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.archive_dir.mkdir(exist_ok=True)

        if not self.current_file.exists():
            self._save_json(self.current_file, {"entries": []})

    # =========================================================================
    # WRITE OPERATIONS
    # =========================================================================

    def write(
        self,
        agent: str,
        event_type: str,
        message: str,
        ticket_id: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Append entry to operations log."""
        if event_type not in self.EVENT_TYPES:
            return {"success": False, "error": f"Invalid event_type: {event_type}"}

        entry = OpsLogEntry(
            id=str(uuid.uuid4())[:8],
            timestamp=datetime.now().isoformat(),
            agent=agent,
            event_type=event_type,
            message=message,
            ticket_id=ticket_id,
            metadata=metadata or {},
        )

        with self._file_lock():
            data = self._load_json(self.current_file)
            data["entries"].append(asdict(entry))
            self._save_json(self.current_file, data)
            self._maybe_rotate()

        return {
            "success": True,
            "entry_id": entry.id,
            "formatted": entry.format_display(),
        }

    def write_clearance(
        self,
        agent: str,
        granted_to: List[str],
        tickets: List[str],
        reason: str,
        is_hold: bool = False,
    ) -> Dict[str, Any]:
        """Write clearance grant or hold directive."""
        event_type = "hold" if is_hold else "clearance_granted"
        action = "HOLD" if is_hold else "CLEARANCE GRANTED"

        message = f"{action} for {', '.join(granted_to)} on tickets {', '.join(tickets)}. {reason}"

        return self.write(
            agent=agent,
            event_type=event_type,
            message=message,
            metadata={
                "granted_to": granted_to,
                "tickets": tickets,
                "reason": reason,
                "is_hold": is_hold,
            }
        )

    def write_rebuild(
        self,
        agent: str,
        ticket_id: str,
        container: str,
        files_changed: List[str],
        status: str = "requested",
    ) -> Dict[str, Any]:
        """Announce container rebuild."""
        event_type = "rebuild_complete" if status == "complete" else "rebuild_requested"
        action = "REBUILD COMPLETE" if status == "complete" else "REBUILD REQUESTED"

        message = f"{action} for {container} (Ticket #{ticket_id})"

        return self.write(
            agent=agent,
            event_type=event_type,
            message=message,
            ticket_id=ticket_id,
            metadata={
                "container": container,
                "files_changed": files_changed,
                "status": status,
            }
        )

    # =========================================================================
    # READ OPERATIONS
    # =========================================================================

    def read(
        self,
        since: str = "1h",
        agent: Optional[str] = None,
        event_type: Optional[str] = None,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """Query operations log."""
        cutoff = self._parse_since(since)

        data = self._load_json(self.current_file)
        entries = [OpsLogEntry(**e) for e in data.get("entries", [])]

        # Filter
        filtered = []
        for entry in entries:
            entry_time = datetime.fromisoformat(entry.timestamp)
            if entry_time < cutoff:
                continue
            if agent and entry.agent != agent:
                continue
            if event_type and entry.event_type != event_type:
                continue
            filtered.append(entry)

        # Sort and limit
        filtered.sort(key=lambda e: e.timestamp, reverse=True)
        filtered = filtered[:limit]

        return {
            "success": True,
            "entries": [asdict(e) for e in filtered],
            "count": len(filtered),
            "formatted": [e.format_display() for e in filtered],
        }

    def get_latest_directive(self) -> Dict[str, Any]:
        """
        Get most recent clearance or hold directive.

        CRITICAL: Agents should call this before starting work!
        """
        result = self.read(since="24h", limit=100)

        for entry in result["entries"]:
            if entry["event_type"] in ("clearance_granted", "hold"):
                return {
                    "success": True,
                    "directive_found": True,
                    "is_hold": entry["event_type"] == "hold",
                    "is_clearance": entry["event_type"] == "clearance_granted",
                    "agent": entry["agent"],
                    "affected_agents": entry["metadata"].get("granted_to", []),
                    "affected_tickets": entry["metadata"].get("tickets", []),
                    "formatted": OpsLogEntry(**entry).format_display(),
                }

        return {
            "success": True,
            "directive_found": False,
            "message": "No active directives. Safe to proceed.",
        }

    def check_rebuild_in_progress(self) -> Dict[str, Any]:
        """Check if a container rebuild is in progress."""
        result = self.read(since="30m", event_type="rebuild_requested", limit=10)

        for entry in result["entries"]:
            # Check if there's a matching rebuild_complete
            complete_result = self.read(
                since="30m",
                event_type="rebuild_complete",
                limit=10
            )

            container = entry["metadata"].get("container")
            is_complete = any(
                c["metadata"].get("container") == container
                and c["timestamp"] > entry["timestamp"]
                for c in complete_result["entries"]
            )

            if not is_complete:
                return {
                    "rebuild_in_progress": True,
                    "container": container,
                    "started_by": entry["agent"],
                    "ticket_id": entry["ticket_id"],
                    "recommendation": "Wait for rebuild to complete before making changes",
                }

        return {
            "rebuild_in_progress": False,
            "message": "No active rebuilds",
        }

    # =========================================================================
    # AGENT SESSION MANAGEMENT
    # =========================================================================

    def register_agent(self, agent_name: str) -> Dict[str, Any]:
        """Register an agent session."""
        agents_dir = self.base_path / "agents"
        agents_dir.mkdir(exist_ok=True)

        session = {
            "agent": agent_name,
            "started_at": datetime.now().isoformat(),
            "current_ticket": None,
            "status": "active",
        }

        agent_file = agents_dir / f"{agent_name}.json"
        self._save_json(agent_file, session)

        return {
            "success": True,
            "agent": agent_name,
            "session_started": session["started_at"],
        }

    def get_active_agents(self) -> Dict[str, Any]:
        """Get list of currently active agents."""
        agents_dir = self.base_path / "agents"
        if not agents_dir.exists():
            return {"agents": [], "count": 0}

        agents = []
        cutoff = datetime.now() - timedelta(hours=2)  # Consider inactive after 2h

        for agent_file in agents_dir.glob("*.json"):
            data = self._load_json(agent_file)
            started = datetime.fromisoformat(data["started_at"])

            if started > cutoff:
                agents.append({
                    "name": data["agent"],
                    "started_at": data["started_at"],
                    "current_ticket": data.get("current_ticket"),
                    "status": data.get("status", "active"),
                })

        return {
            "agents": agents,
            "count": len(agents),
        }

    # =========================================================================
    # COORDINATION HELPERS
    # =========================================================================

    def check_ticket_conflicts(self, ticket_id: str, agent: str) -> Dict[str, Any]:
        """Check if another agent is working on the same ticket."""
        active = self.get_active_agents()

        for other_agent in active["agents"]:
            if other_agent["name"] != agent:
                if other_agent["current_ticket"] == ticket_id:
                    return {
                        "conflict": True,
                        "conflicting_agent": other_agent["name"],
                        "recommendation": f"Contact {other_agent['name']} before claiming this ticket",
                    }

        return {"conflict": False}

    def request_clearance(
        self,
        agent: str,
        tickets: List[str],
        reason: str,
    ) -> Dict[str, Any]:
        """
        Request clearance from other active agents.

        This posts a status update that other agents should see.
        """
        active = self.get_active_agents()
        other_agents = [a["name"] for a in active["agents"] if a["name"] != agent]

        message = f"CLEARANCE REQUEST from {agent} for tickets {', '.join(tickets)}. {reason}"

        self.write(
            agent=agent,
            event_type="status_update",
            message=message,
            metadata={
                "type": "clearance_request",
                "requested_tickets": tickets,
                "reason": reason,
            }
        )

        return {
            "success": True,
            "other_agents": other_agents,
            "message": f"Clearance request posted. {len(other_agents)} other agent(s) notified.",
        }
```

### Usage Example

```python
# Agent startup
from fastband.coordination import AgentOpsLog

log = AgentOpsLog(project_path=Path("/my/project"))

# Check for holds before starting work
directive = log.get_latest_directive()
if directive["directive_found"] and directive["is_hold"]:
    print(f"HOLD in effect: {directive['formatted']}")
    print("Waiting for hold to be lifted...")
    exit(1)

# Check for active rebuilds
rebuild = log.check_rebuild_in_progress()
if rebuild["rebuild_in_progress"]:
    print(f"Rebuild in progress: {rebuild['container']}")
    print("Waiting for rebuild to complete...")
    exit(1)

# Register agent session
log.register_agent("MCP_Agent1")

# Claim ticket
log.write(
    agent="MCP_Agent1",
    event_type="ticket_claimed",
    message="Starting work on ticket #1205",
    ticket_id="1205"
)

# Before rebuild, announce
log.write_rebuild(
    agent="MCP_Agent1",
    ticket_id="1205",
    container="webapp",
    files_changed=["templates/base.html", "static/css/main.css"],
    status="requested"
)

# ... do rebuild ...

# After rebuild, announce completion
log.write_rebuild(
    agent="MCP_Agent1",
    ticket_id="1205",
    container="webapp",
    files_changed=["templates/base.html", "static/css/main.css"],
    status="complete"
)

# Complete ticket
log.write(
    agent="MCP_Agent1",
    event_type="ticket_completed",
    message="Completed ticket #1205 - Fixed header alignment",
    ticket_id="1205"
)
```

### CLI Commands

```bash
# Check coordination status before starting work
$ fastband agents status
Active Agents:
  MCP_Agent1: Working on ticket #1205 (started 45m ago)
  MCP_Agent2: Idle (started 2h ago)

Latest Directive:
  [MCP_Agent1][2025-12-16 14:30] CLEARANCE GRANTED for MCP_Agent2 on tickets #1206, #1207

Rebuild Status: No active rebuilds

# Read recent operations
$ fastband ops read --since 1h
[MCP_Agent1][14:45] Completed ticket #1205 - Fixed header alignment
[MCP_Agent1][14:30] REBUILD COMPLETE for webapp
[MCP_Agent1][14:28] REBUILD REQUESTED for webapp (Ticket #1205)
[MCP_Agent1][14:00] Started work on ticket #1205

# Post hold directive
$ fastband ops hold "Database migration in progress - do not modify data files"
⚠️  HOLD posted - all agents notified

# Grant clearance
$ fastband ops clearance --to MCP_Agent2 --tickets 1206,1207 --reason "No conflicts with my work"
✓ Clearance granted to MCP_Agent2 for tickets #1206, #1207
```

---

## Integration with Fastband Core

Both companion products are automatically initialized when Fastband is set up:

```python
# During fastband init
from fastband.backup import BackupManager
from fastband.coordination import AgentOpsLog

# Initialize backup manager
backup = BackupManager(project_path)
backup.schedule_daily()

# Initialize ops log
ops_log = AgentOpsLog(project_path)

# Every agent tool call should check ops log
def check_coordination(agent_name: str) -> bool:
    directive = ops_log.get_latest_directive()
    if directive["is_hold"]:
        raise CoordinationError(f"HOLD in effect: {directive['formatted']}")

    rebuild = ops_log.check_rebuild_in_progress()
    if rebuild["rebuild_in_progress"]:
        raise CoordinationError(f"Rebuild in progress: {rebuild['container']}")

    return True
```

---

## Summary

| Feature | Backup Manager | Agent Ops Log |
|---------|----------------|---------------|
| **Purpose** | Data protection | Multi-agent coordination |
| **Trigger** | Scheduled / Manual | Real-time events |
| **Storage** | tar.gz + database dumps | JSON with rotation |
| **Retention** | Configurable (7 daily, 4 weekly) | 30 days |
| **Key Feature** | Change detection | Clearance/hold system |

Both are essential for production Fastband deployments with multiple AI agents working simultaneously.

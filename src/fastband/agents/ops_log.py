"""
Agent Operations Log for multi-agent coordination.

Provides a structured logging system for agent communication and coordination:
- Thread-safe log entries with timestamps
- Clearance/hold system for work coordination
- Log rotation and archival
- TTL-based entry expiration
- Conflict detection
"""

import json
import shutil
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any


class EventType(str, Enum):
    """Types of events that can be logged."""

    CLEARANCE_GRANTED = "clearance_granted"
    HOLD = "hold"
    REBUILD_REQUESTED = "rebuild_requested"
    REBUILD_COMPLETE = "rebuild_complete"
    TICKET_CLAIMED = "ticket_claimed"
    TICKET_COMPLETED = "ticket_completed"
    STATUS_UPDATE = "status_update"
    CONFLICT_DETECTED = "conflict_detected"
    AGENT_STARTED = "agent_started"
    AGENT_STOPPED = "agent_stopped"
    ERROR = "error"


@dataclass
class LogEntry:
    """A single log entry in the operations log."""

    id: str
    timestamp: str
    agent: str
    event_type: str
    message: str
    ticket_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    ttl_seconds: int | None = None
    expires_at: str | None = None

    @classmethod
    def create(
        cls,
        agent: str,
        event_type: EventType | str,
        message: str,
        ticket_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        ttl_seconds: int | None = None,
    ) -> "LogEntry":
        """Create a new log entry with auto-generated ID and timestamp."""
        now = datetime.utcnow()
        entry_id = str(uuid.uuid4())[:8]

        expires_at = None
        if ttl_seconds:
            expires_at = (now + timedelta(seconds=ttl_seconds)).isoformat() + "Z"

        event_type_str = event_type.value if isinstance(event_type, EventType) else event_type

        return cls(
            id=entry_id,
            timestamp=now.isoformat() + "Z",
            agent=agent,
            event_type=event_type_str,
            message=message,
            ticket_id=ticket_id,
            metadata=metadata or {},
            ttl_seconds=ttl_seconds,
            expires_at=expires_at,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert entry to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LogEntry":
        """Create entry from dictionary."""
        return cls(
            id=data["id"],
            timestamp=data["timestamp"],
            agent=data["agent"],
            event_type=data["event_type"],
            message=data["message"],
            ticket_id=data.get("ticket_id"),
            metadata=data.get("metadata", {}),
            ttl_seconds=data.get("ttl_seconds"),
            expires_at=data.get("expires_at"),
        )

    def is_expired(self) -> bool:
        """Check if entry has expired based on TTL."""
        if not self.expires_at:
            return False

        try:
            expires = datetime.fromisoformat(self.expires_at.rstrip("Z"))
            return datetime.utcnow() > expires
        except (ValueError, TypeError):
            return False

    def formatted(self) -> str:
        """Return a human-readable formatted string."""
        ticket_info = f" [Ticket #{self.ticket_id}]" if self.ticket_id else ""
        return f"[{self.timestamp}] [{self.agent}] {self.event_type}: {self.message}{ticket_info}"


class OpsLog:
    """
    Agent Operations Log.

    Thread-safe logging system for multi-agent coordination with:
    - JSON-based persistence
    - Log rotation (by size and age)
    - Entry expiration (TTL)
    - Conflict detection
    - Archive management
    """

    # Log rotation thresholds
    MAX_SIZE_BYTES = 1024 * 1024  # 1MB
    MAX_AGE_HOURS = 24

    # Default TTL for entries (7 days)
    DEFAULT_TTL_SECONDS = 7 * 24 * 60 * 60

    def __init__(
        self,
        log_path: Path | None = None,
        archive_dir: Path | None = None,
        auto_rotate: bool = True,
        auto_expire: bool = True,
    ):
        """
        Initialize the operations log.

        Args:
            log_path: Path to the log file (default: .fastband/ops_log.json)
            archive_dir: Path for archived logs (default: .fastband/ops_log_archive/)
            auto_rotate: Automatically rotate logs when thresholds are met
            auto_expire: Automatically remove expired entries on read
        """
        self.log_path = log_path or Path(".fastband/ops_log.json")
        self.archive_dir = archive_dir or Path(".fastband/ops_log_archive")
        self.auto_rotate = auto_rotate
        self.auto_expire = auto_expire

        self._lock = threading.RLock()
        self._entries: list[LogEntry] = []
        self._last_rotation: datetime | None = None
        self._metadata: dict[str, Any] = {
            "version": "1.0",
            "created": datetime.utcnow().isoformat() + "Z",
            "last_rotation": None,
        }

        # Load existing log
        self._load()

    def _load(self) -> None:
        """Load log entries from file."""
        if not self.log_path.exists():
            return

        try:
            with open(self.log_path) as f:
                data = json.load(f)

            self._metadata = data.get("metadata", self._metadata)
            entries_data = data.get("entries", [])

            self._entries = [LogEntry.from_dict(e) for e in entries_data]

            if self._metadata.get("last_rotation"):
                self._last_rotation = datetime.fromisoformat(
                    self._metadata["last_rotation"].rstrip("Z")
                )

            # Remove expired entries on load
            if self.auto_expire:
                self._expire_entries()

        except (json.JSONDecodeError, KeyError, TypeError):
            # Corrupted file - start fresh
            self._entries = []

    def _save(self) -> None:
        """Save log entries to file."""
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "metadata": self._metadata,
            "entries": [e.to_dict() for e in self._entries],
        }

        with open(self.log_path, "w") as f:
            json.dump(data, f, indent=2)

    def _expire_entries(self) -> int:
        """Remove expired entries. Returns count of removed entries."""
        before_count = len(self._entries)
        self._entries = [e for e in self._entries if not e.is_expired()]
        return before_count - len(self._entries)

    def _should_rotate(self) -> bool:
        """Check if log should be rotated."""
        if not self.log_path.exists():
            return False

        # Check size
        if self.log_path.stat().st_size >= self.MAX_SIZE_BYTES:
            return True

        # Check age
        if self._last_rotation:
            age = datetime.utcnow() - self._last_rotation
            if age >= timedelta(hours=self.MAX_AGE_HOURS):
                return True
        elif self._entries:
            # Check oldest entry
            try:
                oldest = datetime.fromisoformat(self._entries[0].timestamp.rstrip("Z"))
                age = datetime.utcnow() - oldest
                if age >= timedelta(hours=self.MAX_AGE_HOURS):
                    return True
            except (ValueError, IndexError):
                pass

        return False

    def rotate(self, reason: str = "manual") -> Path | None:
        """
        Rotate the log file to archive.

        Args:
            reason: Reason for rotation (e.g., "size", "age", "manual")

        Returns:
            Path to the archived file, or None if no rotation needed
        """
        with self._lock:
            if not self._entries and not self.log_path.exists():
                return None

            # Create archive directory
            self.archive_dir.mkdir(parents=True, exist_ok=True)

            # Generate archive filename
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            archive_name = f"ops_log_{timestamp}_{reason}.json"
            archive_path = self.archive_dir / archive_name

            # Copy current log to archive
            if self.log_path.exists():
                shutil.copy2(self.log_path, archive_path)
            else:
                # Save current entries as archive
                self._save()
                if self.log_path.exists():
                    shutil.copy2(self.log_path, archive_path)

            # Clear entries and update metadata
            self._entries = []
            self._last_rotation = datetime.utcnow()
            self._metadata["last_rotation"] = self._last_rotation.isoformat() + "Z"

            # Save empty log
            self._save()

            return archive_path

    def write_entry(
        self,
        agent: str,
        event_type: EventType | str,
        message: str,
        ticket_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        ttl_seconds: int | None = None,
    ) -> LogEntry:
        """
        Write a new entry to the log.

        Args:
            agent: Agent name/identifier
            event_type: Type of event
            message: Human-readable message
            ticket_id: Related ticket ID (optional)
            metadata: Additional structured data (optional)
            ttl_seconds: Time-to-live in seconds (optional)

        Returns:
            The created LogEntry
        """
        with self._lock:
            entry = LogEntry.create(
                agent=agent,
                event_type=event_type,
                message=message,
                ticket_id=ticket_id,
                metadata=metadata,
                ttl_seconds=ttl_seconds,
            )

            self._entries.append(entry)
            self._save()

            # Check if rotation needed
            if self.auto_rotate and self._should_rotate():
                self.rotate(reason="auto")

            return entry

    def read_entries(
        self,
        since: str | None = None,
        agent: str | None = None,
        event_type: EventType | str | None = None,
        ticket_id: str | None = None,
        limit: int = 100,
        include_expired: bool = False,
    ) -> list[LogEntry]:
        """
        Read log entries with optional filters.

        Args:
            since: Time filter (e.g., "1h", "30m", "24h", "7d", or ISO timestamp)
            agent: Filter by agent name
            event_type: Filter by event type
            ticket_id: Filter by ticket ID
            limit: Maximum entries to return
            include_expired: Include expired entries

        Returns:
            List of matching LogEntry objects (newest first)
        """
        with self._lock:
            # Expire old entries if auto_expire is enabled
            if self.auto_expire and not include_expired:
                self._expire_entries()
                self._save()

            entries = self._entries.copy()

        # Filter by expiration
        if not include_expired:
            entries = [e for e in entries if not e.is_expired()]

        # Filter by time
        if since:
            since_dt = self._parse_time_filter(since)
            if since_dt:
                entries = [
                    e
                    for e in entries
                    if datetime.fromisoformat(e.timestamp.rstrip("Z")) >= since_dt
                ]

        # Filter by agent
        if agent:
            entries = [e for e in entries if e.agent == agent]

        # Filter by event type
        if event_type:
            event_type_str = event_type.value if isinstance(event_type, EventType) else event_type
            entries = [e for e in entries if e.event_type == event_type_str]

        # Filter by ticket
        if ticket_id:
            entries = [e for e in entries if e.ticket_id == ticket_id]

        # Sort by timestamp (newest first) and limit
        entries.sort(key=lambda e: e.timestamp, reverse=True)

        return entries[:limit]

    def _parse_time_filter(self, since: str) -> datetime | None:
        """Parse a time filter string into a datetime."""
        now = datetime.utcnow()

        # Try relative time formats
        if since.endswith("m"):
            try:
                minutes = int(since[:-1])
                return now - timedelta(minutes=minutes)
            except ValueError:
                pass
        elif since.endswith("h"):
            try:
                hours = int(since[:-1])
                return now - timedelta(hours=hours)
            except ValueError:
                pass
        elif since.endswith("d"):
            try:
                days = int(since[:-1])
                return now - timedelta(days=days)
            except ValueError:
                pass

        # Try ISO format
        try:
            return datetime.fromisoformat(since.rstrip("Z"))
        except ValueError:
            return None

    def get_latest_directive(self) -> LogEntry | None:
        """
        Get the most recent clearance or hold directive.

        Returns:
            The most recent CLEARANCE_GRANTED or HOLD entry, or None
        """
        directive_types = [EventType.CLEARANCE_GRANTED.value, EventType.HOLD.value]

        with self._lock:
            for entry in reversed(self._entries):
                if entry.event_type in directive_types and not entry.is_expired():
                    return entry

        return None

    def check_active_agents(self, within_hours: float = 1.0) -> dict[str, dict[str, Any]]:
        """
        Check which agents have been active recently.

        Args:
            within_hours: Time window to check for activity

        Returns:
            Dict mapping agent names to their activity info
        """
        since = f"{int(within_hours * 60)}m"
        entries = self.read_entries(since=since)

        # Reverse to process in chronological order (oldest first)
        # This ensures we track ticket state correctly (claim -> complete)
        entries = list(reversed(entries))

        agents: dict[str, dict[str, Any]] = {}

        for entry in entries:
            if entry.agent not in agents:
                agents[entry.agent] = {
                    "last_seen": entry.timestamp,
                    "last_action": entry.event_type,
                    "current_ticket": None,
                    "activity_count": 0,
                }

            # Update last_seen to most recent
            agents[entry.agent]["last_seen"] = entry.timestamp
            agents[entry.agent]["last_action"] = entry.event_type
            agents[entry.agent]["activity_count"] += 1

            # Track current ticket from claims
            if entry.event_type == EventType.TICKET_CLAIMED.value:
                agents[entry.agent]["current_ticket"] = entry.ticket_id
            elif entry.event_type == EventType.TICKET_COMPLETED.value:
                if agents[entry.agent]["current_ticket"] == entry.ticket_id:
                    agents[entry.agent]["current_ticket"] = None

        return agents

    def detect_conflicts(
        self,
        ticket_id: str,
        agent: str,
        action: str = "claim",
    ) -> list[LogEntry]:
        """
        Detect potential conflicts for a ticket operation.

        Args:
            ticket_id: Ticket being operated on
            agent: Agent attempting the operation
            action: Type of action ("claim", "modify", etc.)

        Returns:
            List of conflicting entries
        """
        conflicts: list[LogEntry] = []

        # Look for recent activity on this ticket
        entries = self.read_entries(ticket_id=ticket_id, since="1h")

        for entry in entries:
            if entry.agent != agent:
                # Another agent has activity on this ticket
                if entry.event_type == EventType.TICKET_CLAIMED.value:
                    # Ticket claimed by another agent
                    conflicts.append(entry)
                elif entry.event_type == EventType.HOLD.value:
                    # There's a hold affecting this ticket
                    conflicts.append(entry)

        # Check for active holds
        directive = self.get_latest_directive()
        if directive and directive.event_type == EventType.HOLD.value:
            if directive.agent != agent:
                # Check if hold affects this ticket or is global
                hold_tickets = directive.metadata.get("tickets", [])
                if not hold_tickets or ticket_id in hold_tickets:
                    if directive not in conflicts:
                        conflicts.append(directive)

        return conflicts

    def announce_rebuild(
        self,
        agent: str,
        container: str,
        ticket_id: str | None = None,
        files_changed: list[str] | None = None,
        status: str = "requested",
    ) -> LogEntry:
        """
        Announce a container rebuild operation.

        Args:
            agent: Agent performing the rebuild
            container: Container name being rebuilt
            ticket_id: Related ticket (optional)
            files_changed: List of changed files (optional)
            status: "requested" or "complete"

        Returns:
            The created LogEntry
        """
        event_type = (
            EventType.REBUILD_REQUESTED if status == "requested" else EventType.REBUILD_COMPLETE
        )

        message = f"Container '{container}' rebuild {status}"

        metadata = {
            "container": container,
            "status": status,
        }
        if files_changed:
            metadata["files_changed"] = files_changed

        return self.write_entry(
            agent=agent,
            event_type=event_type,
            message=message,
            ticket_id=ticket_id,
            metadata=metadata,
            ttl_seconds=3600,  # Rebuild announcements expire after 1 hour
        )

    def grant_clearance(
        self,
        agent: str,
        granted_to: list[str],
        tickets: list[str],
        reason: str,
    ) -> LogEntry:
        """
        Grant clearance to agents for specific tickets.

        Args:
            agent: Agent granting clearance
            granted_to: List of agents being cleared
            tickets: List of ticket IDs covered
            reason: Reason for clearance

        Returns:
            The created LogEntry
        """
        message = f"Clearance granted to {', '.join(granted_to)} for tickets {', '.join(tickets)}: {reason}"

        return self.write_entry(
            agent=agent,
            event_type=EventType.CLEARANCE_GRANTED,
            message=message,
            metadata={
                "granted_to": granted_to,
                "tickets": tickets,
                "reason": reason,
            },
        )

    def issue_hold(
        self,
        agent: str,
        affected_agents: list[str],
        tickets: list[str] | None = None,
        reason: str = "Coordination required",
    ) -> LogEntry:
        """
        Issue a hold directive.

        Args:
            agent: Agent issuing the hold
            affected_agents: Agents who should pause work
            tickets: Specific tickets affected (None = global hold)
            reason: Reason for the hold

        Returns:
            The created LogEntry
        """
        ticket_info = f" on tickets {', '.join(tickets)}" if tickets else " (global)"
        message = f"HOLD issued to {', '.join(affected_agents)}{ticket_info}: {reason}"

        return self.write_entry(
            agent=agent,
            event_type=EventType.HOLD,
            message=message,
            metadata={
                "affected_agents": affected_agents,
                "tickets": tickets or [],
                "reason": reason,
                "is_global": tickets is None or len(tickets) == 0,
            },
        )

    def claim_ticket(
        self,
        agent: str,
        ticket_id: str,
        check_conflicts: bool = True,
    ) -> tuple[LogEntry, list[LogEntry]]:
        """
        Claim a ticket for work.

        Args:
            agent: Agent claiming the ticket
            ticket_id: Ticket being claimed
            check_conflicts: Whether to check for conflicts first

        Returns:
            Tuple of (claim entry, list of conflicts)
        """
        conflicts = []
        if check_conflicts:
            conflicts = self.detect_conflicts(ticket_id, agent, "claim")

        entry = self.write_entry(
            agent=agent,
            event_type=EventType.TICKET_CLAIMED,
            message=f"Claimed ticket #{ticket_id}",
            ticket_id=ticket_id,
            metadata={"conflicts_at_claim": len(conflicts)},
        )

        return entry, conflicts

    def complete_ticket(
        self,
        agent: str,
        ticket_id: str,
        summary: str | None = None,
    ) -> LogEntry:
        """
        Mark a ticket as completed.

        Args:
            agent: Agent completing the ticket
            ticket_id: Ticket being completed
            summary: Brief completion summary (optional)

        Returns:
            The created LogEntry
        """
        message = f"Completed ticket #{ticket_id}"
        if summary:
            message += f": {summary}"

        return self.write_entry(
            agent=agent,
            event_type=EventType.TICKET_COMPLETED,
            message=message,
            ticket_id=ticket_id,
            metadata={"summary": summary} if summary else {},
        )

    def count(self) -> int:
        """Return the number of entries in the log."""
        with self._lock:
            return len(self._entries)

    def clear(self) -> int:
        """
        Clear all entries from the log.

        Returns:
            Number of entries cleared
        """
        with self._lock:
            count = len(self._entries)
            self._entries = []
            self._save()
            return count

    def prune(self, keep_days: int = 30) -> int:
        """
        Prune archived logs older than specified days.

        Args:
            keep_days: Number of days to keep archives

        Returns:
            Number of archive files deleted
        """
        if not self.archive_dir.exists():
            return 0

        cutoff = datetime.utcnow() - timedelta(days=keep_days)
        deleted = 0

        for archive_file in self.archive_dir.glob("ops_log_*.json"):
            try:
                # Parse timestamp from filename
                parts = archive_file.stem.split("_")
                if len(parts) >= 3:
                    date_str = parts[2]  # ops_log_YYYYMMDD_HHMMSS_reason
                    time_str = parts[3] if len(parts) > 3 else "000000"
                    file_dt = datetime.strptime(f"{date_str}_{time_str}", "%Y%m%d_%H%M%S")

                    if file_dt < cutoff:
                        archive_file.unlink()
                        deleted += 1
            except (ValueError, IndexError):
                continue

        return deleted

    def get_stats(self) -> dict[str, Any]:
        """
        Get statistics about the operations log.

        Returns:
            Dictionary with log statistics
        """
        with self._lock:
            entries = self._entries.copy()

        # Count by event type
        event_counts: dict[str, int] = {}
        for entry in entries:
            event_counts[entry.event_type] = event_counts.get(entry.event_type, 0) + 1

        # Count by agent
        agent_counts: dict[str, int] = {}
        for entry in entries:
            agent_counts[entry.agent] = agent_counts.get(entry.agent, 0) + 1

        # Archive count
        archive_count = 0
        if self.archive_dir.exists():
            archive_count = len(list(self.archive_dir.glob("ops_log_*.json")))

        return {
            "current_entries": len(entries),
            "event_counts": event_counts,
            "agent_counts": agent_counts,
            "archive_files": archive_count,
            "log_file_size": self.log_path.stat().st_size if self.log_path.exists() else 0,
            "last_rotation": self._metadata.get("last_rotation"),
            "created": self._metadata.get("created"),
        }


# Global OpsLog instance
_ops_log: OpsLog | None = None


def get_ops_log(
    project_path: Path | None = None,
    reset: bool = False,
) -> OpsLog:
    """
    Get the global OpsLog instance.

    Args:
        project_path: Path to project directory (default: current directory)
        reset: Force creation of a new instance

    Returns:
        The global OpsLog instance
    """
    global _ops_log

    if _ops_log is None or reset:
        if project_path is None:
            project_path = Path.cwd()

        log_path = project_path / ".fastband" / "ops_log.json"
        archive_dir = project_path / ".fastband" / "ops_log_archive"

        _ops_log = OpsLog(log_path=log_path, archive_dir=archive_dir)

    return _ops_log

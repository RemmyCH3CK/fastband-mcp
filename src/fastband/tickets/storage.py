"""
Ticket storage backends.

Provides:
- TicketStore: Abstract base class for storage
- JSONTicketStore: JSON file-based storage
- SQLiteTicketStore: SQLite database storage
- StorageFactory: Factory for creating stores

Performance Optimizations (Issue #38):
- Result caching: Frequently accessed tickets are cached
- Lazy loading: Tickets are only parsed from JSON when accessed
- Query optimization: SQLite uses indexed columns for filtering
- Thread-safe: Uses locks for concurrent access
"""

import builtins
import json
import logging
import shutil
import sqlite3
import threading
import time
from abc import ABC, abstractmethod
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from fastband.tickets.models import (
    Agent,
    Ticket,
    TicketPriority,
    TicketStatus,
    TicketType,
)

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class CacheStats:
    """Statistics for cache performance monitoring."""

    hits: int = 0
    misses: int = 0
    evictions: int = 0

    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0


class TicketCache:
    """
    Simple LRU cache for ticket objects.

    Caches parsed Ticket objects to avoid repeated JSON parsing
    and object instantiation for frequently accessed tickets.
    """

    __slots__ = ("_cache", "_max_size", "_stats", "_lock")

    def __init__(self, max_size: int = 100):
        self._cache: dict[str, tuple[Ticket, float]] = {}  # id -> (ticket, timestamp)
        self._max_size = max_size
        self._stats = CacheStats()
        self._lock = threading.Lock()

    def get(self, ticket_id: str) -> Ticket | None:
        """Get a ticket from cache."""
        with self._lock:
            if ticket_id in self._cache:
                self._stats.hits += 1
                ticket, _ = self._cache[ticket_id]
                # Update access time (LRU)
                self._cache[ticket_id] = (ticket, time.time())
                return ticket
            self._stats.misses += 1
            return None

    def put(self, ticket: Ticket) -> None:
        """Put a ticket in cache."""
        with self._lock:
            # Evict oldest if at capacity
            if len(self._cache) >= self._max_size and ticket.id not in self._cache:
                self._evict_oldest()

            self._cache[ticket.id] = (ticket, time.time())

    def invalidate(self, ticket_id: str) -> None:
        """Remove a ticket from cache."""
        with self._lock:
            self._cache.pop(ticket_id, None)

    def invalidate_all(self) -> None:
        """Clear the entire cache."""
        with self._lock:
            self._cache.clear()

    def _evict_oldest(self) -> None:
        """Evict the least recently used entry."""
        if not self._cache:
            return

        oldest_id = min(self._cache.keys(), key=lambda k: self._cache[k][1])
        del self._cache[oldest_id]
        self._stats.evictions += 1

    @property
    def stats(self) -> CacheStats:
        """Get cache statistics."""
        return self._stats

    def __len__(self) -> int:
        return len(self._cache)


class TicketStore(ABC):
    """
    Abstract base class for ticket storage.

    All storage backends must implement these methods.
    """

    @abstractmethod
    def create(self, ticket: Ticket, prefix: str = "FB") -> Ticket:
        """Create a new ticket with auto-generated ticket_number."""
        pass

    @abstractmethod
    def get(self, ticket_id: str) -> Ticket | None:
        """
        Get a ticket by ID or ticket_number.

        Accepts:
        - UUID: "ea81b2e3-272f-4618-809a-d2c03873b003"
        - Ticket number: "FB-042"
        - Short number: "42" (assumes configured prefix)
        """
        pass

    @abstractmethod
    def update(self, ticket: Ticket) -> bool:
        """Update an existing ticket."""
        pass

    @abstractmethod
    def delete(self, ticket_id: str) -> bool:
        """Delete a ticket by ID."""
        pass

    @abstractmethod
    def list(
        self,
        status: TicketStatus | None = None,
        priority: TicketPriority | None = None,
        ticket_type: TicketType | None = None,
        assigned_to: str | None = None,
        labels: list[str] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Ticket]:
        """List tickets with optional filters."""
        pass

    @abstractmethod
    def search(self, query: str, fields: builtins.list[str] | None = None) -> builtins.list[Ticket]:
        """Search tickets by text query."""
        pass

    @abstractmethod
    def count(
        self,
        status: TicketStatus | None = None,
        priority: TicketPriority | None = None,
    ) -> int:
        """Count tickets with optional filters."""
        pass

    @abstractmethod
    def get_next_id(self) -> str:
        """Get the next available sequence number (internal)."""
        pass

    @abstractmethod
    def get_next_ticket_number(self, prefix: str = "FB") -> str:
        """Get the next ticket number (e.g., FB-001)."""
        pass

    @abstractmethod
    def get_by_number(self, ticket_number: str) -> Ticket | None:
        """Get a ticket by its human-friendly ticket_number."""
        pass

    # Agent management
    @abstractmethod
    def get_agent(self, name: str) -> Agent | None:
        """Get an agent by name."""
        pass

    @abstractmethod
    def save_agent(self, agent: Agent) -> Agent:
        """Save or update an agent."""
        pass

    @abstractmethod
    def list_agents(self, active_only: bool = True) -> builtins.list[Agent]:
        """List all agents."""
        pass

    # Backup support
    @abstractmethod
    def backup(self, backup_path: Path) -> bool:
        """Create a backup of the storage."""
        pass

    @abstractmethod
    def restore(self, backup_path: Path) -> bool:
        """Restore from a backup."""
        pass


class JSONTicketStore(TicketStore):
    """
    JSON file-based ticket storage.

    Stores tickets in a JSON file with the structure:
    {
        "tickets": {...},
        "agents": {...},
        "metadata": {...}
    }

    Performance features:
    - LRU cache for frequently accessed tickets
    - Lazy ticket parsing (raw JSON stored until access)
    - Batch save optimization with auto_save toggle
    """

    __slots__ = ("path", "auto_save", "_data", "_lock", "_cache", "_dirty")

    def __init__(self, path: Path, auto_save: bool = True, cache_size: int = 100):
        self.path = Path(path)
        self.auto_save = auto_save
        self._data: dict[str, Any] = {
            "tickets": {},
            "agents": {},
            "metadata": {
                "version": "1.0",
                "created_at": datetime.now().isoformat(),
                "last_modified": datetime.now().isoformat(),
                "next_id": 1,
            },
        }
        self._lock = threading.RLock()
        self._cache = TicketCache(max_size=cache_size)
        self._dirty = False  # Track if data needs saving
        self._load()

    def _load(self) -> None:
        """Load data from file."""
        if self.path.exists():
            with self._lock:
                try:
                    with open(self.path, encoding="utf-8") as f:
                        self._data = json.load(f)
                    # Ensure required keys exist
                    self._data.setdefault("tickets", {})
                    self._data.setdefault("agents", {})
                    self._data.setdefault("metadata", {"next_id": 1})
                    # Clear cache on reload
                    self._cache.invalidate_all()
                    self._dirty = False
                except json.JSONDecodeError:
                    logger.warning(f"Failed to load {self.path}, starting fresh")

    def _save(self) -> None:
        """Save data to file."""
        with self._lock:
            if not self._dirty and self.path.exists():
                return  # Skip save if nothing changed

            self._data["metadata"]["last_modified"] = datetime.now().isoformat()
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
            self._dirty = False

    def _mark_dirty(self) -> None:
        """Mark data as needing save."""
        self._dirty = True
        if self.auto_save:
            self._save()

    def create(self, ticket: Ticket, prefix: str = "FB") -> Ticket:
        """Create a new ticket with auto-generated ticket_number."""
        with self._lock:
            # Assign UUID if not set
            if not ticket.id or ticket.id in self._data["tickets"]:
                ticket.id = str(__import__("uuid").uuid4())

            # Assign ticket_number if not set
            if not ticket.ticket_number:
                ticket.ticket_number = self.get_next_ticket_number(prefix)

            self._data["tickets"][ticket.id] = ticket.to_dict()
            self._cache.put(ticket)  # Cache the new ticket
            self._mark_dirty()

            return ticket

    def get(self, ticket_id: str) -> Ticket | None:
        """
        Get a ticket by ID or ticket_number.

        Accepts:
        - UUID: "ea81b2e3-272f-4618-809a-d2c03873b003"
        - Ticket number: "FB-042"
        - Short number: "42" (will try to find by number suffix)
        """
        ticket_id = str(ticket_id).strip()

        # Try cache first (fast path)
        cached = self._cache.get(ticket_id)
        if cached is not None:
            return cached

        # Check if it looks like a ticket number (contains hyphen or is numeric)
        if "-" in ticket_id or ticket_id.isdigit():
            ticket = self.get_by_number(ticket_id)
            if ticket:
                return ticket

        # Fall back to UUID lookup
        with self._lock:
            data = self._data["tickets"].get(ticket_id)
            if data:
                ticket = Ticket.from_dict(data)
                self._cache.put(ticket)  # Cache for future access
                return ticket
            return None

    def update(self, ticket: Ticket) -> bool:
        """Update an existing ticket."""
        with self._lock:
            if ticket.id not in self._data["tickets"]:
                return False

            ticket.updated_at = datetime.now()
            self._data["tickets"][ticket.id] = ticket.to_dict()
            self._cache.put(ticket)  # Update cache
            self._mark_dirty()

            return True

    def delete(self, ticket_id: str) -> bool:
        """Delete a ticket by ID."""
        with self._lock:
            if ticket_id not in self._data["tickets"]:
                return False

            del self._data["tickets"][ticket_id]
            self._cache.invalidate(ticket_id)  # Remove from cache
            self._mark_dirty()

            return True

    def list(
        self,
        status: TicketStatus | None = None,
        priority: TicketPriority | None = None,
        ticket_type: TicketType | None = None,
        assigned_to: str | None = None,
        labels: list[str] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Ticket]:
        """List tickets with optional filters."""
        with self._lock:
            tickets = []

            for data in self._data["tickets"].values():
                ticket = Ticket.from_dict(data)

                # Apply filters
                if status and ticket.status != status:
                    continue
                if priority and ticket.priority != priority:
                    continue
                if ticket_type and ticket.ticket_type != ticket_type:
                    continue
                if assigned_to and ticket.assigned_to != assigned_to:
                    continue
                if labels:
                    if not any(label in ticket.labels for label in labels):
                        continue

                tickets.append(ticket)

            # Sort by priority then created_at
            tickets.sort(
                key=lambda t: (t.priority.sort_order, t.created_at),
            )

            # Apply pagination
            return tickets[offset : offset + limit]

    def search(self, query: str, fields: builtins.list[str] | None = None) -> builtins.list[Ticket]:
        """Search tickets by text query."""
        if fields is None:
            fields = ["title", "description", "requirements", "notes"]

        query_lower = query.lower()
        results = []

        with self._lock:
            for data in self._data["tickets"].values():
                ticket = Ticket.from_dict(data)

                for field in fields:
                    value = getattr(ticket, field, None)
                    if value is None:
                        continue

                    if isinstance(value, str):
                        if query_lower in value.lower():
                            results.append(ticket)
                            break
                    elif isinstance(value, list):
                        if any(query_lower in str(item).lower() for item in value):
                            results.append(ticket)
                            break

        return results

    def count(
        self,
        status: TicketStatus | None = None,
        priority: TicketPriority | None = None,
    ) -> int:
        """Count tickets with optional filters."""
        with self._lock:
            if status is None and priority is None:
                return len(self._data["tickets"])

            count = 0
            for data in self._data["tickets"].values():
                if status:
                    ticket_status = TicketStatus.from_string(data.get("status", "open"))
                    if ticket_status != status:
                        continue
                if priority:
                    ticket_priority = TicketPriority.from_string(data.get("priority", "medium"))
                    if ticket_priority != priority:
                        continue
                count += 1

            return count

    def get_next_id(self) -> str:
        """Get the next available sequence number (internal)."""
        with self._lock:
            next_id = self._data["metadata"].get("next_id", 1)
            self._data["metadata"]["next_id"] = next_id + 1
            self._mark_dirty()
            return str(next_id)

    def get_next_ticket_number(self, prefix: str = "FB") -> str:
        """Get the next ticket number (e.g., FB-001)."""
        seq = int(self.get_next_id())
        return f"{prefix}-{seq:03d}"

    def get_by_number(self, ticket_number: str) -> Ticket | None:
        """
        Get a ticket by its human-friendly ticket_number.

        Supports:
        - Full number: "FB-042"
        - Just number: "42" (matches any prefix ending with -42)
        """
        ticket_number = ticket_number.strip().upper()

        with self._lock:
            for data in self._data["tickets"].values():
                stored_num = data.get("ticket_number", "")
                if not stored_num:
                    continue

                # Exact match
                if stored_num.upper() == ticket_number:
                    ticket = Ticket.from_dict(data)
                    self._cache.put(ticket)
                    return ticket

                # Partial match (just the number part)
                if ticket_number.isdigit():
                    # Match if stored number ends with the same digits
                    if stored_num.upper().endswith(f"-{int(ticket_number):03d}"):
                        ticket = Ticket.from_dict(data)
                        self._cache.put(ticket)
                        return ticket

        return None

    def get_agent(self, name: str) -> Agent | None:
        """Get an agent by name."""
        with self._lock:
            data = self._data["agents"].get(name)
            if data:
                return Agent.from_dict(data)
            return None

    def save_agent(self, agent: Agent) -> Agent:
        """Save or update an agent."""
        with self._lock:
            agent.last_seen = datetime.now()
            self._data["agents"][agent.name] = agent.to_dict()
            self._mark_dirty()
            return agent

    def list_agents(self, active_only: bool = True) -> builtins.list[Agent]:
        """List all agents."""
        with self._lock:
            agents = []
            for data in self._data["agents"].values():
                agent = Agent.from_dict(data)
                if active_only and not agent.active:
                    continue
                agents.append(agent)
            return agents

    def backup(self, backup_path: Path) -> bool:
        """Create a backup of the storage."""
        try:
            with self._lock:
                backup_path = Path(backup_path)
                backup_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(self.path, backup_path)
            return True
        except Exception:
            return False

    def restore(self, backup_path: Path) -> bool:
        """Restore from a backup."""
        try:
            backup_path = Path(backup_path)
            if not backup_path.exists():
                return False

            with self._lock:
                shutil.copy2(backup_path, self.path)
                self._load()
            return True
        except Exception:
            return False

    def save(self) -> None:
        """Manually save data (forces save even if not dirty)."""
        self._dirty = True
        self._save()

    def get_cache_stats(self) -> dict[str, Any]:
        """
        Get cache performance statistics.

        Returns:
            Dict with hit_rate, hits, misses, evictions, and size
        """
        stats = self._cache.stats
        return {
            "hit_rate": round(stats.hit_rate * 100, 1),
            "hits": stats.hits,
            "misses": stats.misses,
            "evictions": stats.evictions,
            "size": len(self._cache),
        }


class SQLiteTicketStore(TicketStore):
    """
    SQLite database ticket storage.

    Uses SQLite for better performance with large ticket counts.
    """

    def __init__(self, path: Path):
        self.path = Path(path)
        self._local = threading.local()
        self._init_db()

    @property
    def _conn(self) -> sqlite3.Connection:
        """Get thread-local connection."""
        if not hasattr(self._local, "conn"):
            self._local.conn = sqlite3.connect(
                self.path,
                check_same_thread=False,
            )
            self._local.conn.row_factory = sqlite3.Row
        return self._local.conn

    @contextmanager
    def _cursor(self) -> Iterator[sqlite3.Cursor]:
        """Get a cursor with automatic commit."""
        cursor = self._conn.cursor()
        try:
            yield cursor
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise
        finally:
            cursor.close()

    def _init_db(self) -> None:
        """Initialize database schema."""
        self.path.parent.mkdir(parents=True, exist_ok=True)

        with self._cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tickets (
                    id TEXT PRIMARY KEY,
                    ticket_number TEXT UNIQUE,
                    title TEXT NOT NULL,
                    description TEXT,
                    ticket_type TEXT NOT NULL DEFAULT 'task',
                    priority TEXT NOT NULL DEFAULT 'medium',
                    status TEXT NOT NULL DEFAULT 'open',
                    assigned_to TEXT,
                    created_by TEXT DEFAULT 'system',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT,
                    due_date TEXT,
                    notes TEXT,
                    resolution TEXT,
                    app TEXT,
                    app_version TEXT,
                    problem_summary TEXT,
                    solution_summary TEXT,
                    testing_notes TEXT,
                    before_screenshot TEXT,
                    after_screenshot TEXT,
                    review_status TEXT,
                    data TEXT NOT NULL  -- Full JSON data
                )
            """)

            # Add ticket_number column if it doesn't exist (migration)
            try:
                cursor.execute("ALTER TABLE tickets ADD COLUMN ticket_number TEXT UNIQUE")
            except sqlite3.OperationalError:
                pass  # Column already exists

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS agents (
                    name TEXT PRIMARY KEY,
                    agent_type TEXT NOT NULL DEFAULT 'ai',
                    active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    last_seen TEXT NOT NULL,
                    data TEXT NOT NULL  -- Full JSON data
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            """)

            # Initialize next_id if not exists
            cursor.execute("INSERT OR IGNORE INTO metadata (key, value) VALUES ('next_id', '1')")

            # Create indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tickets_priority ON tickets(priority)")
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_tickets_assigned ON tickets(assigned_to)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_tickets_number ON tickets(ticket_number)"
            )

    def create(self, ticket: Ticket, prefix: str = "FB") -> Ticket:
        """Create a new ticket with auto-generated ticket_number."""
        if not ticket.id:
            ticket.id = str(__import__("uuid").uuid4())

        # Assign ticket_number if not set
        if not ticket.ticket_number:
            ticket.ticket_number = self.get_next_ticket_number(prefix)

        with self._cursor() as cursor:
            data = ticket.to_dict()
            cursor.execute(
                """
                INSERT INTO tickets (
                    id, ticket_number, title, description, ticket_type, priority, status,
                    assigned_to, created_by, created_at, updated_at,
                    started_at, completed_at, due_date, notes, resolution,
                    app, app_version, problem_summary, solution_summary,
                    testing_notes, before_screenshot, after_screenshot,
                    review_status, data
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
            """,
                (
                    ticket.id,
                    ticket.ticket_number,
                    ticket.title,
                    ticket.description,
                    ticket.ticket_type.value,
                    ticket.priority.value,
                    ticket.status.value,
                    ticket.assigned_to,
                    ticket.created_by,
                    ticket.created_at.isoformat(),
                    ticket.updated_at.isoformat(),
                    ticket.started_at.isoformat() if ticket.started_at else None,
                    ticket.completed_at.isoformat() if ticket.completed_at else None,
                    ticket.due_date.isoformat() if ticket.due_date else None,
                    ticket.notes,
                    ticket.resolution,
                    ticket.app,
                    ticket.app_version,
                    ticket.problem_summary,
                    ticket.solution_summary,
                    ticket.testing_notes,
                    ticket.before_screenshot,
                    ticket.after_screenshot,
                    ticket.review_status,
                    json.dumps(data),
                ),
            )

        return ticket

    def get(self, ticket_id: str) -> Ticket | None:
        """
        Get a ticket by ID or ticket_number.

        Accepts:
        - UUID: "ea81b2e3-272f-4618-809a-d2c03873b003"
        - Ticket number: "FB-042"
        - Short number: "42" (will try to find by number suffix)
        """
        ticket_id = str(ticket_id).strip()

        # Check if it looks like a ticket number (contains hyphen or is numeric)
        if "-" in ticket_id or ticket_id.isdigit():
            ticket = self.get_by_number(ticket_id)
            if ticket:
                return ticket

        # Fall back to UUID lookup
        with self._cursor() as cursor:
            cursor.execute("SELECT data FROM tickets WHERE id = ?", (ticket_id,))
            row = cursor.fetchone()
            if row:
                return Ticket.from_dict(json.loads(row["data"]))
            return None

    def update(self, ticket: Ticket) -> bool:
        """Update an existing ticket."""
        ticket.updated_at = datetime.now()

        with self._cursor() as cursor:
            data = ticket.to_dict()
            cursor.execute(
                """
                UPDATE tickets SET
                    title = ?, description = ?, ticket_type = ?, priority = ?,
                    status = ?, assigned_to = ?, updated_at = ?,
                    started_at = ?, completed_at = ?, notes = ?, resolution = ?,
                    problem_summary = ?, solution_summary = ?, testing_notes = ?,
                    before_screenshot = ?, after_screenshot = ?, review_status = ?,
                    data = ?
                WHERE id = ?
            """,
                (
                    ticket.title,
                    ticket.description,
                    ticket.ticket_type.value,
                    ticket.priority.value,
                    ticket.status.value,
                    ticket.assigned_to,
                    ticket.updated_at.isoformat(),
                    ticket.started_at.isoformat() if ticket.started_at else None,
                    ticket.completed_at.isoformat() if ticket.completed_at else None,
                    ticket.notes,
                    ticket.resolution,
                    ticket.problem_summary,
                    ticket.solution_summary,
                    ticket.testing_notes,
                    ticket.before_screenshot,
                    ticket.after_screenshot,
                    ticket.review_status,
                    json.dumps(data),
                    ticket.id,
                ),
            )
            return cursor.rowcount > 0

    def delete(self, ticket_id: str) -> bool:
        """Delete a ticket by ID."""
        with self._cursor() as cursor:
            cursor.execute("DELETE FROM tickets WHERE id = ?", (ticket_id,))
            return cursor.rowcount > 0

    def list(
        self,
        status: TicketStatus | None = None,
        priority: TicketPriority | None = None,
        ticket_type: TicketType | None = None,
        assigned_to: str | None = None,
        labels: list[str] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Ticket]:
        """List tickets with optional filters."""
        query = "SELECT data FROM tickets WHERE 1=1"
        params: list[Any] = []

        if status:
            query += " AND status = ?"
            params.append(status.value)
        if priority:
            query += " AND priority = ?"
            params.append(priority.value)
        if ticket_type:
            query += " AND ticket_type = ?"
            params.append(ticket_type.value)
        if assigned_to:
            query += " AND assigned_to = ?"
            params.append(assigned_to)

        # Labels require JSON search
        if labels:
            for label in labels:
                query += " AND data LIKE ?"
                params.append(f'%"{label}"%')

        query += " ORDER BY priority, created_at LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with self._cursor() as cursor:
            cursor.execute(query, params)
            return [Ticket.from_dict(json.loads(row["data"])) for row in cursor.fetchall()]

    def search(self, query: str, fields: builtins.list[str] | None = None) -> builtins.list[Ticket]:
        """Search tickets by text query."""
        if fields is None:
            fields = ["title", "description", "notes"]

        # Build search query
        conditions = []
        params = []
        for field in fields:
            if field in ["title", "description", "notes", "resolution"]:
                conditions.append(f"{field} LIKE ?")
                params.append(f"%{query}%")
            else:
                # Search in JSON data
                conditions.append("data LIKE ?")
                params.append(f'%"{query}"%')

        if not conditions:
            return []

        sql = f"SELECT data FROM tickets WHERE {' OR '.join(conditions)}"

        with self._cursor() as cursor:
            cursor.execute(sql, params)
            return [Ticket.from_dict(json.loads(row["data"])) for row in cursor.fetchall()]

    def count(
        self,
        status: TicketStatus | None = None,
        priority: TicketPriority | None = None,
    ) -> int:
        """Count tickets with optional filters."""
        query = "SELECT COUNT(*) as count FROM tickets WHERE 1=1"
        params: list[Any] = []

        if status:
            query += " AND status = ?"
            params.append(status.value)
        if priority:
            query += " AND priority = ?"
            params.append(priority.value)

        with self._cursor() as cursor:
            cursor.execute(query, params)
            row = cursor.fetchone()
            return row["count"] if row else 0

    def get_next_id(self) -> str:
        """Get the next available sequence number (internal)."""
        with self._cursor() as cursor:
            cursor.execute("SELECT value FROM metadata WHERE key = 'next_id'")
            row = cursor.fetchone()
            next_id = int(row["value"]) if row else 1

            cursor.execute(
                "UPDATE metadata SET value = ? WHERE key = 'next_id'",
                (str(next_id + 1),),
            )

            return str(next_id)

    def get_next_ticket_number(self, prefix: str = "FB") -> str:
        """Get the next ticket number (e.g., FB-001)."""
        seq = int(self.get_next_id())
        return f"{prefix}-{seq:03d}"

    def get_by_number(self, ticket_number: str) -> Ticket | None:
        """
        Get a ticket by its human-friendly ticket_number.

        Supports:
        - Full number: "FB-042"
        - Just number: "42" (matches any prefix ending with -042)
        """
        ticket_number = ticket_number.strip().upper()

        with self._cursor() as cursor:
            # Try exact match first
            cursor.execute(
                "SELECT data FROM tickets WHERE UPPER(ticket_number) = ?", (ticket_number,)
            )
            row = cursor.fetchone()
            if row:
                return Ticket.from_dict(json.loads(row["data"]))

            # Try partial match (just the number part)
            if ticket_number.isdigit():
                pattern = f"%-{int(ticket_number):03d}"
                cursor.execute(
                    "SELECT data FROM tickets WHERE UPPER(ticket_number) LIKE ?", (pattern,)
                )
                row = cursor.fetchone()
                if row:
                    return Ticket.from_dict(json.loads(row["data"]))

        return None

    def get_agent(self, name: str) -> Agent | None:
        """Get an agent by name."""
        with self._cursor() as cursor:
            cursor.execute("SELECT data FROM agents WHERE name = ?", (name,))
            row = cursor.fetchone()
            if row:
                return Agent.from_dict(json.loads(row["data"]))
            return None

    def save_agent(self, agent: Agent) -> Agent:
        """Save or update an agent."""
        agent.last_seen = datetime.now()
        data = agent.to_dict()

        with self._cursor() as cursor:
            cursor.execute(
                """
                INSERT OR REPLACE INTO agents (name, agent_type, active, created_at, last_seen, data)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                (
                    agent.name,
                    agent.agent_type,
                    1 if agent.active else 0,
                    agent.created_at.isoformat(),
                    agent.last_seen.isoformat(),
                    json.dumps(data),
                ),
            )

        return agent

    def list_agents(self, active_only: bool = True) -> builtins.list[Agent]:
        """List all agents."""
        query = "SELECT data FROM agents"
        if active_only:
            query += " WHERE active = 1"

        with self._cursor() as cursor:
            cursor.execute(query)
            return [Agent.from_dict(json.loads(row["data"])) for row in cursor.fetchall()]

    def backup(self, backup_path: Path) -> bool:
        """Create a backup of the storage."""
        try:
            backup_path = Path(backup_path)
            backup_path.parent.mkdir(parents=True, exist_ok=True)

            # Use SQLite backup API
            backup_conn = sqlite3.connect(backup_path)
            self._conn.backup(backup_conn)
            backup_conn.close()
            return True
        except Exception:
            return False

    def restore(self, backup_path: Path) -> bool:
        """Restore from a backup."""
        try:
            backup_path = Path(backup_path)
            if not backup_path.exists():
                return False

            # Close current connection
            if hasattr(self._local, "conn"):
                self._local.conn.close()
                delattr(self._local, "conn")

            # Copy backup over
            shutil.copy2(backup_path, self.path)
            return True
        except Exception:
            return False

    def close(self) -> None:
        """Close the database connection."""
        if hasattr(self._local, "conn"):
            self._local.conn.close()
            delattr(self._local, "conn")


class StorageFactory:
    """Factory for creating ticket storage instances."""

    _stores: dict[str, TicketStore] = {}

    @classmethod
    def create(
        cls,
        storage_type: str,
        path: Path,
        **kwargs: Any,
    ) -> TicketStore:
        """
        Create a ticket store.

        Args:
            storage_type: "json" or "sqlite"
            path: Path to storage file
            **kwargs: Additional arguments for the store

        Returns:
            TicketStore instance
        """
        key = f"{storage_type}:{path}"

        if key not in cls._stores:
            if storage_type == "json":
                cls._stores[key] = JSONTicketStore(path, **kwargs)
            elif storage_type == "sqlite":
                cls._stores[key] = SQLiteTicketStore(path)
            else:
                raise ValueError(f"Unknown storage type: {storage_type}")

        return cls._stores[key]

    @classmethod
    def get_default(cls, project_path: Path) -> TicketStore:
        """
        Get the default store for a project.

        Uses JSON storage in .fastband/tickets.json by default.
        """
        tickets_path = project_path / ".fastband" / "tickets.json"
        return cls.create("json", tickets_path)

    @classmethod
    def clear_cache(cls) -> None:
        """Clear the store cache."""
        cls._stores.clear()


def get_store(
    path: Path | None = None,
    storage_type: str = "json",
) -> TicketStore:
    """
    Get a ticket store.

    Convenience function for getting a store instance.

    Args:
        path: Path to storage file (defaults to current directory)
        storage_type: "json" or "sqlite"

    Returns:
        TicketStore instance
    """
    if path is None:
        path = Path.cwd() / ".fastband" / "tickets.json"

    return StorageFactory.create(storage_type, path)

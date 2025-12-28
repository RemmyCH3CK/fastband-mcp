"""
Ticket storage backends.

Provides:
- TicketStore: Abstract base class for storage
- JSONTicketStore: JSON file-based storage
- SQLiteTicketStore: SQLite database storage
- StorageFactory: Factory for creating stores
"""

import json
import sqlite3
import shutil
from abc import ABC, abstractmethod
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Callable
import threading

from fastband.tickets.models import (
    Ticket,
    TicketStatus,
    TicketPriority,
    TicketType,
    Agent,
)


class TicketStore(ABC):
    """
    Abstract base class for ticket storage.

    All storage backends must implement these methods.
    """

    @abstractmethod
    def create(self, ticket: Ticket) -> Ticket:
        """Create a new ticket."""
        pass

    @abstractmethod
    def get(self, ticket_id: str) -> Optional[Ticket]:
        """Get a ticket by ID."""
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
        status: Optional[TicketStatus] = None,
        priority: Optional[TicketPriority] = None,
        ticket_type: Optional[TicketType] = None,
        assigned_to: Optional[str] = None,
        labels: Optional[List[str]] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Ticket]:
        """List tickets with optional filters."""
        pass

    @abstractmethod
    def search(self, query: str, fields: Optional[List[str]] = None) -> List[Ticket]:
        """Search tickets by text query."""
        pass

    @abstractmethod
    def count(
        self,
        status: Optional[TicketStatus] = None,
        priority: Optional[TicketPriority] = None,
    ) -> int:
        """Count tickets with optional filters."""
        pass

    @abstractmethod
    def get_next_id(self) -> str:
        """Get the next available ticket ID."""
        pass

    # Agent management
    @abstractmethod
    def get_agent(self, name: str) -> Optional[Agent]:
        """Get an agent by name."""
        pass

    @abstractmethod
    def save_agent(self, agent: Agent) -> Agent:
        """Save or update an agent."""
        pass

    @abstractmethod
    def list_agents(self, active_only: bool = True) -> List[Agent]:
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
    """

    def __init__(self, path: Path, auto_save: bool = True):
        self.path = Path(path)
        self.auto_save = auto_save
        self._data: Dict[str, Any] = {
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
        self._load()

    def _load(self) -> None:
        """Load data from file."""
        if self.path.exists():
            with self._lock:
                try:
                    with open(self.path, "r", encoding="utf-8") as f:
                        self._data = json.load(f)
                    # Ensure required keys exist
                    self._data.setdefault("tickets", {})
                    self._data.setdefault("agents", {})
                    self._data.setdefault("metadata", {"next_id": 1})
                except json.JSONDecodeError:
                    # Start fresh if file is corrupted
                    pass

    def _save(self) -> None:
        """Save data to file."""
        with self._lock:
            self._data["metadata"]["last_modified"] = datetime.now().isoformat()
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)

    def create(self, ticket: Ticket) -> Ticket:
        """Create a new ticket."""
        with self._lock:
            # Assign ID if not set
            if not ticket.id or ticket.id in self._data["tickets"]:
                ticket.id = self.get_next_id()

            self._data["tickets"][ticket.id] = ticket.to_dict()

            if self.auto_save:
                self._save()

            return ticket

    def get(self, ticket_id: str) -> Optional[Ticket]:
        """Get a ticket by ID."""
        with self._lock:
            data = self._data["tickets"].get(str(ticket_id))
            if data:
                return Ticket.from_dict(data)
            return None

    def update(self, ticket: Ticket) -> bool:
        """Update an existing ticket."""
        with self._lock:
            if ticket.id not in self._data["tickets"]:
                return False

            ticket.updated_at = datetime.now()
            self._data["tickets"][ticket.id] = ticket.to_dict()

            if self.auto_save:
                self._save()

            return True

    def delete(self, ticket_id: str) -> bool:
        """Delete a ticket by ID."""
        with self._lock:
            if ticket_id not in self._data["tickets"]:
                return False

            del self._data["tickets"][ticket_id]

            if self.auto_save:
                self._save()

            return True

    def list(
        self,
        status: Optional[TicketStatus] = None,
        priority: Optional[TicketPriority] = None,
        ticket_type: Optional[TicketType] = None,
        assigned_to: Optional[str] = None,
        labels: Optional[List[str]] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Ticket]:
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

    def search(self, query: str, fields: Optional[List[str]] = None) -> List[Ticket]:
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
        status: Optional[TicketStatus] = None,
        priority: Optional[TicketPriority] = None,
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
        """Get the next available ticket ID."""
        with self._lock:
            next_id = self._data["metadata"].get("next_id", 1)
            self._data["metadata"]["next_id"] = next_id + 1

            if self.auto_save:
                self._save()

            return str(next_id)

    def get_agent(self, name: str) -> Optional[Agent]:
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

            if self.auto_save:
                self._save()

            return agent

    def list_agents(self, active_only: bool = True) -> List[Agent]:
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
        """Manually save data."""
        self._save()


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
            cursor.execute(
                "INSERT OR IGNORE INTO metadata (key, value) VALUES ('next_id', '1')"
            )

            # Create indexes
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets(status)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_tickets_priority ON tickets(priority)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_tickets_assigned ON tickets(assigned_to)"
            )

    def create(self, ticket: Ticket) -> Ticket:
        """Create a new ticket."""
        if not ticket.id:
            ticket.id = self.get_next_id()

        with self._cursor() as cursor:
            data = ticket.to_dict()
            cursor.execute(
                """
                INSERT INTO tickets (
                    id, title, description, ticket_type, priority, status,
                    assigned_to, created_by, created_at, updated_at,
                    started_at, completed_at, due_date, notes, resolution,
                    app, app_version, problem_summary, solution_summary,
                    testing_notes, before_screenshot, after_screenshot,
                    review_status, data
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
            """,
                (
                    ticket.id,
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

    def get(self, ticket_id: str) -> Optional[Ticket]:
        """Get a ticket by ID."""
        with self._cursor() as cursor:
            cursor.execute("SELECT data FROM tickets WHERE id = ?", (str(ticket_id),))
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
        status: Optional[TicketStatus] = None,
        priority: Optional[TicketPriority] = None,
        ticket_type: Optional[TicketType] = None,
        assigned_to: Optional[str] = None,
        labels: Optional[List[str]] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Ticket]:
        """List tickets with optional filters."""
        query = "SELECT data FROM tickets WHERE 1=1"
        params: List[Any] = []

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

    def search(self, query: str, fields: Optional[List[str]] = None) -> List[Ticket]:
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
        status: Optional[TicketStatus] = None,
        priority: Optional[TicketPriority] = None,
    ) -> int:
        """Count tickets with optional filters."""
        query = "SELECT COUNT(*) as count FROM tickets WHERE 1=1"
        params: List[Any] = []

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
        """Get the next available ticket ID."""
        with self._cursor() as cursor:
            cursor.execute("SELECT value FROM metadata WHERE key = 'next_id'")
            row = cursor.fetchone()
            next_id = int(row["value"]) if row else 1

            cursor.execute(
                "UPDATE metadata SET value = ? WHERE key = 'next_id'",
                (str(next_id + 1),),
            )

            return str(next_id)

    def get_agent(self, name: str) -> Optional[Agent]:
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

    def list_agents(self, active_only: bool = True) -> List[Agent]:
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

    _stores: Dict[str, TicketStore] = {}

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
    path: Optional[Path] = None,
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

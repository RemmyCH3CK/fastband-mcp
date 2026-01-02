"""
Storage port interfaces.

Defines abstractions for persistent storage operations. Implementations
may use SQLite, PostgreSQL, Redis, file systems, or any other backend.

These are pure interfaces - no database drivers or ORM imports allowed.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Generic, Protocol, TypeVar, runtime_checkable

# Type variables for generic storage
K = TypeVar("K")  # Key type
V = TypeVar("V")  # Value type
T = TypeVar("T")  # Entity type


@dataclass(frozen=True)
class StorageError(Exception):
    """Base exception for storage operations."""

    message: str
    cause: Exception | None = None


@dataclass(frozen=True)
class NotFoundError(StorageError):
    """Raised when a requested item is not found."""

    key: str = ""


@dataclass(frozen=True)
class ConflictError(StorageError):
    """Raised on version/uniqueness conflicts."""

    key: str = ""
    expected_version: int | None = None
    actual_version: int | None = None


@runtime_checkable
class KeyValueStore(Protocol[K, V]):
    """
    Protocol for simple key-value storage operations.

    Implementations should be thread-safe and handle serialization
    of values transparently.
    """

    async def get(self, key: K) -> V | None:
        """
        Retrieve a value by key.

        Args:
            key: The key to look up.

        Returns:
            The value if found, None otherwise.
        """
        ...

    async def set(self, key: K, value: V, ttl_seconds: int | None = None) -> None:
        """
        Store a value with optional TTL.

        Args:
            key: The key to store under.
            value: The value to store.
            ttl_seconds: Optional time-to-live in seconds.
        """
        ...

    async def delete(self, key: K) -> bool:
        """
        Delete a value by key.

        Args:
            key: The key to delete.

        Returns:
            True if deleted, False if key didn't exist.
        """
        ...

    async def exists(self, key: K) -> bool:
        """
        Check if a key exists.

        Args:
            key: The key to check.

        Returns:
            True if the key exists.
        """
        ...


@dataclass
class QueryFilter:
    """Filter criteria for document queries."""

    field: str
    operator: str  # eq, ne, gt, gte, lt, lte, in, contains
    value: Any


@dataclass
class QueryOrder:
    """Ordering specification for queries."""

    field: str
    ascending: bool = True


@dataclass
class QueryResult(Generic[T]):
    """Paginated query result."""

    items: list[T]
    total: int
    offset: int
    limit: int
    has_more: bool


class DocumentStore(ABC, Generic[T]):
    """
    Abstract base for document/entity storage.

    Provides CRUD operations with filtering, pagination, and versioning.
    Implementations handle serialization and indexing.
    """

    @abstractmethod
    async def create(self, entity: T) -> T:
        """
        Create a new entity.

        Args:
            entity: The entity to create.

        Returns:
            The created entity with any generated fields (id, timestamps).

        Raises:
            ConflictError: If entity with same ID already exists.
        """
        ...

    @abstractmethod
    async def get(self, entity_id: str) -> T | None:
        """
        Retrieve an entity by ID.

        Args:
            entity_id: The unique identifier.

        Returns:
            The entity if found, None otherwise.
        """
        ...

    @abstractmethod
    async def update(self, entity: T) -> T:
        """
        Update an existing entity.

        Args:
            entity: The entity with updated fields.

        Returns:
            The updated entity.

        Raises:
            NotFoundError: If entity doesn't exist.
            ConflictError: If version mismatch (optimistic locking).
        """
        ...

    @abstractmethod
    async def delete(self, entity_id: str) -> bool:
        """
        Delete an entity by ID.

        Args:
            entity_id: The unique identifier.

        Returns:
            True if deleted, False if not found.
        """
        ...

    @abstractmethod
    async def query(
        self,
        filters: list[QueryFilter] | None = None,
        order_by: list[QueryOrder] | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> QueryResult[T]:
        """
        Query entities with filtering and pagination.

        Args:
            filters: Optional filter criteria.
            order_by: Optional ordering.
            offset: Number of items to skip.
            limit: Maximum items to return.

        Returns:
            Paginated query result.
        """
        ...


class TransactionManager(ABC):
    """
    Abstract base for transaction management.

    Provides atomic operations across multiple storage calls.
    """

    @abstractmethod
    async def begin(self) -> None:
        """Begin a new transaction."""
        ...

    @abstractmethod
    async def commit(self) -> None:
        """Commit the current transaction."""
        ...

    @abstractmethod
    async def rollback(self) -> None:
        """Rollback the current transaction."""
        ...

    async def __aenter__(self) -> "TransactionManager":
        """Context manager entry."""
        await self.begin()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> bool:
        """Context manager exit with auto-commit/rollback."""
        if exc_type is not None:
            await self.rollback()
            return False
        await self.commit()
        return True


@dataclass
class MigrationInfo:
    """Information about a database migration."""

    version: str
    name: str
    applied_at: datetime | None = None
    checksum: str | None = None


class MigrationRunner(ABC):
    """
    Abstract base for schema migrations.

    Implementations handle database-specific migration logic.
    """

    @abstractmethod
    async def get_current_version(self) -> str | None:
        """Get the currently applied migration version."""
        ...

    @abstractmethod
    async def get_pending_migrations(self) -> list[MigrationInfo]:
        """List migrations that haven't been applied."""
        ...

    @abstractmethod
    async def apply(self, version: str) -> None:
        """Apply a specific migration version."""
        ...

    @abstractmethod
    async def rollback(self, version: str) -> None:
        """Rollback to a specific migration version."""
        ...

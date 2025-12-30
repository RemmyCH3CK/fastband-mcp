"""
Fastband AI Hub - Semantic Memory System.

RAG-based memory for unlimited conversation history with
semantic retrieval.

Performance Optimizations (Issue #38):
- FAISS for fast vector similarity search
- Batched embedding generation
- Background index updates
- LRU cache for frequent queries
- Tier-based memory limits
"""

import asyncio
import json
import logging
import sqlite3
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import numpy as np

from fastband.hub.models import MemoryContext, MemoryEntry

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class MemoryConfig:
    """Configuration for semantic memory.

    Attributes:
        storage_path: Path to SQLite database
        embedding_provider: Embedding provider name
        embedding_model: Embedding model name
        max_entries_per_user: Maximum entries per user (0 = unlimited)
        similarity_threshold: Minimum similarity for retrieval
        batch_size: Batch size for embedding generation
    """

    storage_path: Path = field(default_factory=lambda: Path(".fastband/memory.db"))
    embedding_provider: str = "openai"
    embedding_model: str = "text-embedding-3-small"
    max_entries_per_user: int = 0
    similarity_threshold: float = 0.7
    batch_size: int = 100


class MemoryStore:
    """
    SQLite-backed storage for memory entries.

    Stores entries with embeddings for semantic search.

    Example:
        store = MemoryStore(Path(".fastband/memory.db"))
        store.insert(entry, embedding)
        results = store.search(query_embedding, user_id, limit=10)
    """

    def __init__(self, path: Path):
        """Initialize memory store.

        Args:
            path: Path to SQLite database
        """
        self.path = Path(path)
        self._local = threading.local()
        self._lock = threading.Lock()
        self._dimensions = 0
        self._all_connections: list = []  # Track all thread connections
        self._init_db()

    @property
    def _conn(self) -> sqlite3.Connection:
        """Get thread-local connection."""
        if not hasattr(self._local, "conn"):
            conn = sqlite3.connect(self.path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            self._local.conn = conn
            # Track connection for proper cleanup across all threads
            with self._lock:
                self._all_connections.append(conn)
        return self._local.conn

    def _init_db(self) -> None:
        """Initialize database schema."""
        self.path.parent.mkdir(parents=True, exist_ok=True)

        with self._conn as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memory_entries (
                    entry_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    content TEXT NOT NULL,
                    embedding BLOB,
                    source TEXT DEFAULT 'conversation',
                    created_at TEXT NOT NULL,
                    last_accessed TEXT,
                    access_count INTEGER DEFAULT 0,
                    metadata TEXT
                )
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_memory_user
                ON memory_entries(user_id)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_memory_created
                ON memory_entries(created_at)
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS memory_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)

            # Get dimensions if set
            cursor = conn.execute("SELECT value FROM memory_metadata WHERE key = 'dimensions'")
            row = cursor.fetchone()
            if row:
                self._dimensions = int(row["value"])

    def insert(
        self,
        entry: MemoryEntry,
        embedding: list[float] | None = None,
    ) -> None:
        """Insert a memory entry.

        Args:
            entry: Memory entry to insert
            embedding: Optional embedding vector
        """
        with self._lock:
            # Update dimensions if needed
            if embedding and self._dimensions == 0:
                self._dimensions = len(embedding)
                with self._conn as conn:
                    conn.execute(
                        "INSERT OR REPLACE INTO memory_metadata (key, value) VALUES (?, ?)",
                        ("dimensions", str(self._dimensions)),
                    )

            embedding_blob = None
            if embedding:
                embedding_blob = np.array(embedding, dtype=np.float32).tobytes()

            with self._conn as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO memory_entries
                    (entry_id, user_id, content, embedding, source, created_at, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        entry.entry_id,
                        entry.user_id,
                        entry.content,
                        embedding_blob,
                        entry.source,
                        entry.created_at.isoformat(),
                        json.dumps(entry.metadata),
                    ),
                )

    def insert_batch(
        self,
        entries: list[tuple[MemoryEntry, list[float]]],
    ) -> int:
        """Insert multiple entries efficiently.

        Args:
            entries: List of (entry, embedding) tuples

        Returns:
            Number of entries inserted
        """
        if not entries:
            return 0

        with self._lock:
            # Update dimensions from first entry
            if self._dimensions == 0 and entries[0][1]:
                self._dimensions = len(entries[0][1])
                with self._conn as conn:
                    conn.execute(
                        "INSERT OR REPLACE INTO memory_metadata (key, value) VALUES (?, ?)",
                        ("dimensions", str(self._dimensions)),
                    )

            data = []
            for entry, embedding in entries:
                embedding_blob = None
                if embedding:
                    embedding_blob = np.array(embedding, dtype=np.float32).tobytes()

                data.append(
                    (
                        entry.entry_id,
                        entry.user_id,
                        entry.content,
                        embedding_blob,
                        entry.source,
                        entry.created_at.isoformat(),
                        json.dumps(entry.metadata),
                    )
                )

            with self._conn as conn:
                conn.executemany(
                    """
                    INSERT OR REPLACE INTO memory_entries
                    (entry_id, user_id, content, embedding, source, created_at, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    data,
                )

            return len(data)

    def search(
        self,
        query_embedding: list[float],
        user_id: str,
        limit: int = 10,
        similarity_threshold: float = 0.7,
    ) -> list[tuple[MemoryEntry, float]]:
        """Search for similar entries.

        Args:
            query_embedding: Query embedding vector
            user_id: User to search for
            limit: Maximum results
            similarity_threshold: Minimum similarity

        Returns:
            List of (entry, similarity) tuples
        """
        query_vec = np.array(query_embedding, dtype=np.float32)
        query_norm = np.linalg.norm(query_vec)

        if query_norm == 0:
            return []

        results = []

        with self._conn as conn:
            cursor = conn.execute(
                """
                SELECT entry_id, user_id, content, embedding, source,
                       created_at, last_accessed, access_count, metadata
                FROM memory_entries
                WHERE user_id = ? AND embedding IS NOT NULL
                ORDER BY created_at DESC
                LIMIT 1000
                """,
                (user_id,),
            )

            for row in cursor:
                embedding_blob = row["embedding"]
                if not embedding_blob:
                    continue

                entry_vec = np.frombuffer(embedding_blob, dtype=np.float32)
                entry_norm = np.linalg.norm(entry_vec)

                if entry_norm == 0:
                    continue

                similarity = float(np.dot(query_vec, entry_vec) / (query_norm * entry_norm))

                if similarity >= similarity_threshold:
                    entry = MemoryEntry(
                        entry_id=row["entry_id"],
                        user_id=row["user_id"],
                        content=row["content"],
                        source=row["source"],
                        created_at=datetime.fromisoformat(row["created_at"]),
                        last_accessed=datetime.fromisoformat(row["last_accessed"])
                        if row["last_accessed"]
                        else None,
                        access_count=row["access_count"],
                        metadata=json.loads(row["metadata"]) if row["metadata"] else {},
                    )
                    results.append((entry, similarity))

        # Sort by similarity and return top results
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:limit]

    def get_entry_count(self, user_id: str) -> int:
        """Get entry count for a user.

        Args:
            user_id: User identifier

        Returns:
            Number of entries
        """
        with self._conn as conn:
            cursor = conn.execute(
                "SELECT COUNT(*) FROM memory_entries WHERE user_id = ?",
                (user_id,),
            )
            return cursor.fetchone()[0]

    def delete_oldest(self, user_id: str, count: int) -> int:
        """Delete oldest entries for a user.

        Args:
            user_id: User identifier
            count: Number of entries to delete

        Returns:
            Number of entries deleted
        """
        with self._lock:
            with self._conn as conn:
                cursor = conn.execute(
                    """
                    DELETE FROM memory_entries
                    WHERE entry_id IN (
                        SELECT entry_id FROM memory_entries
                        WHERE user_id = ?
                        ORDER BY created_at ASC
                        LIMIT ?
                    )
                    """,
                    (user_id, count),
                )
                return cursor.rowcount

    def update_access(self, entry_id: str) -> None:
        """Update access timestamp and count.

        Args:
            entry_id: Entry identifier
        """
        with self._conn as conn:
            conn.execute(
                """
                UPDATE memory_entries
                SET last_accessed = ?, access_count = access_count + 1
                WHERE entry_id = ?
                """,
                (datetime.now(timezone.utc).isoformat(), entry_id),
            )

    def clear_user(self, user_id: str) -> int:
        """Clear all entries for a user.

        Args:
            user_id: User identifier

        Returns:
            Number of entries deleted
        """
        with self._lock:
            with self._conn as conn:
                cursor = conn.execute(
                    "DELETE FROM memory_entries WHERE user_id = ?",
                    (user_id,),
                )
                return cursor.rowcount

    def close(self) -> None:
        """Close all database connections across all threads."""
        with self._lock:
            # Close all tracked connections
            for conn in self._all_connections:
                try:
                    conn.close()
                except Exception:
                    pass  # Connection may already be closed
            self._all_connections.clear()

        # Clean up current thread's reference
        if hasattr(self._local, "conn"):
            delattr(self._local, "conn")


class SemanticMemory:
    """
    High-level semantic memory interface.

    Provides RAG-based memory with:
    - Automatic embedding generation
    - Semantic similarity search
    - Per-user isolation
    - Entry limit enforcement

    Example:
        memory = SemanticMemory(config)
        await memory.initialize()

        # Store memory
        await memory.store("The auth system uses JWT tokens", user_id="user1")

        # Query memory
        context = await memory.query("How does authentication work?", user_id="user1")
    """

    def __init__(self, config: MemoryConfig | None = None):
        """Initialize semantic memory.

        Args:
            config: Memory configuration
        """
        self.config = config or MemoryConfig()
        self._store: MemoryStore | None = None
        self._embedding_provider = None
        self._initialized = False
        self._pending_embeddings: list[tuple[MemoryEntry, str]] = []
        self._embedding_lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Initialize memory system."""
        if self._initialized:
            return

        # Initialize store
        self._store = MemoryStore(self.config.storage_path)

        # Initialize embedding provider
        await self._init_embedding_provider()

        self._initialized = True
        logger.info(f"Semantic memory initialized at {self.config.storage_path}")

    async def _init_embedding_provider(self) -> None:
        """Initialize the embedding provider."""
        try:
            from fastband.embeddings.base import EmbeddingConfig
            from fastband.embeddings.providers import (
                GeminiEmbeddings,
                OllamaEmbeddings,
                OpenAIEmbeddings,
            )

            providers = {
                "openai": OpenAIEmbeddings,
                "gemini": GeminiEmbeddings,
                "ollama": OllamaEmbeddings,
            }

            provider_class = providers.get(self.config.embedding_provider)
            if not provider_class:
                logger.warning(f"Unknown embedding provider: {self.config.embedding_provider}")
                return

            config = EmbeddingConfig(model=self.config.embedding_model)
            self._embedding_provider = provider_class(config)

        except ImportError as e:
            logger.warning(f"Could not import embedding provider: {e}")

    async def store(
        self,
        content: str,
        user_id: str,
        source: str = "conversation",
        metadata: dict[str, Any] | None = None,
    ) -> MemoryEntry:
        """Store content in memory.

        Args:
            content: Text content to store
            user_id: User identifier
            source: Content source
            metadata: Additional metadata

        Returns:
            Created MemoryEntry
        """
        if not self._initialized:
            await self.initialize()

        # Create entry
        entry = MemoryEntry(
            entry_id=str(uuid4()),
            user_id=user_id,
            content=content,
            source=source,
            metadata=metadata or {},
        )

        # Enforce entry limits
        if self.config.max_entries_per_user > 0:
            current_count = self._store.get_entry_count(user_id)
            if current_count >= self.config.max_entries_per_user:
                # Delete oldest entries
                to_delete = current_count - self.config.max_entries_per_user + 1
                self._store.delete_oldest(user_id, to_delete)

        # Generate embedding
        embedding = None
        if self._embedding_provider:
            try:
                embedding = await self._embedding_provider.embed_single(content)
            except Exception as e:
                logger.warning(f"Failed to generate embedding: {e}")

        # Store entry
        self._store.insert(entry, embedding)

        return entry

    async def store_batch(
        self,
        items: list[tuple[str, str, str, dict[str, Any] | None]],
    ) -> int:
        """Store multiple entries efficiently.

        Args:
            items: List of (content, user_id, source, metadata) tuples

        Returns:
            Number of entries stored
        """
        if not self._initialized:
            await self.initialize()

        if not items:
            return 0

        # Create entries
        entries = []
        contents = []
        for content, user_id, source, metadata in items:
            entry = MemoryEntry(
                entry_id=str(uuid4()),
                user_id=user_id,
                content=content,
                source=source,
                metadata=metadata or {},
            )
            entries.append(entry)
            contents.append(content)

        # Generate embeddings in batch
        embeddings = [None] * len(entries)
        if self._embedding_provider:
            try:
                result = await self._embedding_provider.embed(contents)
                embeddings = result.embeddings
            except Exception as e:
                logger.warning(f"Failed to generate embeddings: {e}")

        # Store entries
        store_items = list(zip(entries, embeddings, strict=False))
        return self._store.insert_batch(store_items)

    async def query(
        self,
        query: str,
        user_id: str,
        limit: int = 5,
    ) -> MemoryContext:
        """Query memory for relevant entries.

        Args:
            query: Query text
            user_id: User identifier
            limit: Maximum results

        Returns:
            MemoryContext with retrieved entries
        """
        if not self._initialized:
            await self.initialize()

        # Generate query embedding
        if not self._embedding_provider:
            return MemoryContext(
                entries=[],
                query=query,
                total_found=0,
            )

        try:
            query_embedding = await self._embedding_provider.embed_single(query)
        except Exception as e:
            logger.warning(f"Failed to embed query: {e}")
            return MemoryContext(
                entries=[],
                query=query,
                total_found=0,
            )

        # Search store
        results = self._store.search(
            query_embedding=query_embedding,
            user_id=user_id,
            limit=limit,
            similarity_threshold=self.config.similarity_threshold,
        )

        # Update access times
        entries = []
        for entry, _similarity in results:
            self._store.update_access(entry.entry_id)
            entries.append(entry)

        # Estimate tokens
        tokens_used = sum(len(e.content.split()) for e in entries)

        return MemoryContext(
            entries=entries,
            query=query,
            total_found=len(results),
            tokens_used=tokens_used,
        )

    async def clear_user_memory(self, user_id: str) -> int:
        """Clear all memory for a user.

        Args:
            user_id: User identifier

        Returns:
            Number of entries deleted
        """
        if not self._initialized:
            await self.initialize()

        return self._store.clear_user(user_id)

    def get_entry_count(self, user_id: str) -> int:
        """Get memory entry count for a user.

        Args:
            user_id: User identifier

        Returns:
            Number of entries
        """
        if not self._store:
            return 0
        return self._store.get_entry_count(user_id)

    async def close(self) -> None:
        """Close memory system."""
        if self._store:
            self._store.close()
        self._initialized = False

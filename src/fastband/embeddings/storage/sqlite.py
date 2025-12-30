"""
SQLite vector storage implementation.

Stores embeddings as BLOBs in SQLite with metadata columns for filtering.
Uses brute-force cosine similarity search (suitable for <200k vectors).
"""

import json
import logging
import math
import sqlite3
import struct
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from fastband.embeddings.base import ChunkMetadata, ChunkType
from fastband.embeddings.storage.base import IndexStats, SearchResult, VectorStore

logger = logging.getLogger(__name__)


def _pack_embedding(embedding: list[float]) -> bytes:
    """Pack embedding list to bytes."""
    return struct.pack(f"{len(embedding)}f", *embedding)


def _unpack_embedding(data: bytes) -> list[float]:
    """Unpack bytes to embedding list."""
    count = len(data) // 4  # 4 bytes per float
    return list(struct.unpack(f"{count}f", data))


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Calculate cosine similarity between two vectors."""
    dot_product = sum(x * y for x, y in zip(a, b, strict=False))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return dot_product / (norm_a * norm_b)


class SQLiteVectorStore(VectorStore):
    """
    SQLite-based vector storage.

    Stores embeddings as packed float BLOBs with metadata columns
    for efficient filtering. Uses brute-force cosine similarity
    for search (suitable for up to ~200k vectors).

    Features:
    - Thread-safe with thread-local connections
    - Proper connection cleanup across all threads
    - Indexed columns for filtering
    - Efficient batch inserts
    - Automatic schema migration

    Example:
        store = SQLiteVectorStore(Path(".fastband/vectors.db"))
        store.store(chunk_id, embedding, content, metadata)
        results = store.search(query_embedding, limit=5)
    """

    def __init__(
        self,
        path: Path,
        provider: str = "unknown",
        model: str = "unknown",
    ):
        self.path = Path(path)
        self._provider = provider
        self._model = model
        self._dimensions = 0
        self._local = threading.local()
        self._lock = threading.Lock()
        self._all_connections: list[sqlite3.Connection] = []  # Track all thread connections
        self._init_db()

    @property
    def _conn(self) -> sqlite3.Connection:
        """Get thread-local connection, tracking for cleanup."""
        if not hasattr(self._local, "conn"):
            conn = sqlite3.connect(
                self.path,
                check_same_thread=False,
            )
            conn.row_factory = sqlite3.Row
            self._local.conn = conn
            # Track connection for cleanup
            with self._lock:
                self._all_connections.append(conn)
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
            # Main vectors table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS vectors (
                    chunk_id TEXT PRIMARY KEY,
                    embedding BLOB NOT NULL,
                    content TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    chunk_type TEXT NOT NULL,
                    start_line INTEGER NOT NULL,
                    end_line INTEGER NOT NULL,
                    name TEXT,
                    docstring TEXT,
                    imports TEXT,
                    parent_name TEXT,
                    file_type TEXT,
                    last_modified TEXT,
                    chunk_hash TEXT,
                    created_at TEXT NOT NULL
                )
            """)

            # Metadata table for index-level info
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            """)

            # Create indexes for filtering
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_vectors_file_path ON vectors(file_path)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_vectors_file_type ON vectors(file_type)")
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_vectors_chunk_type ON vectors(chunk_type)"
            )

            # Initialize metadata
            cursor.execute(
                "INSERT OR IGNORE INTO metadata (key, value) VALUES ('provider', ?)",
                (self._provider,),
            )
            cursor.execute(
                "INSERT OR IGNORE INTO metadata (key, value) VALUES ('model', ?)", (self._model,)
            )
            cursor.execute("INSERT OR IGNORE INTO metadata (key, value) VALUES ('dimensions', '0')")

    def store(
        self,
        chunk_id: str,
        embedding: list[float],
        content: str,
        metadata: ChunkMetadata,
    ) -> None:
        """Store a single chunk."""
        with self._lock:
            # Update dimensions if not set
            if self._dimensions == 0:
                self._dimensions = len(embedding)
                with self._cursor() as cursor:
                    cursor.execute(
                        "UPDATE metadata SET value = ? WHERE key = 'dimensions'",
                        (str(self._dimensions),),
                    )

            packed = _pack_embedding(embedding)

            with self._cursor() as cursor:
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO vectors (
                        chunk_id, embedding, content, file_path, chunk_type,
                        start_line, end_line, name, docstring, imports,
                        parent_name, file_type, last_modified, chunk_hash, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        chunk_id,
                        packed,
                        content,
                        metadata.file_path,
                        metadata.chunk_type.value,
                        metadata.start_line,
                        metadata.end_line,
                        metadata.name,
                        metadata.docstring,
                        json.dumps(metadata.imports),
                        metadata.parent_name,
                        metadata.file_type,
                        metadata.last_modified.isoformat() if metadata.last_modified else None,
                        metadata.chunk_hash,
                        datetime.now().isoformat(),
                    ),
                )

    def store_batch(self, items: list[tuple]) -> int:
        """Store multiple chunks efficiently."""
        if not items:
            return 0

        with self._lock:
            # Update dimensions from first item
            if self._dimensions == 0 and items:
                self._dimensions = len(items[0][1])
                with self._cursor() as cursor:
                    cursor.execute(
                        "UPDATE metadata SET value = ? WHERE key = 'dimensions'",
                        (str(self._dimensions),),
                    )

            rows = []
            for chunk_id, embedding, content, metadata in items:
                packed = _pack_embedding(embedding)
                rows.append(
                    (
                        chunk_id,
                        packed,
                        content,
                        metadata.file_path,
                        metadata.chunk_type.value,
                        metadata.start_line,
                        metadata.end_line,
                        metadata.name,
                        metadata.docstring,
                        json.dumps(metadata.imports),
                        metadata.parent_name,
                        metadata.file_type,
                        metadata.last_modified.isoformat() if metadata.last_modified else None,
                        metadata.chunk_hash,
                        datetime.now().isoformat(),
                    )
                )

            with self._cursor() as cursor:
                cursor.executemany(
                    """
                    INSERT OR REPLACE INTO vectors (
                        chunk_id, embedding, content, file_path, chunk_type,
                        start_line, end_line, name, docstring, imports,
                        parent_name, file_type, last_modified, chunk_hash, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    rows,
                )

            return len(rows)

    def search(
        self,
        query_embedding: list[float],
        limit: int = 10,
        filter_file_type: str | None = None,
        filter_file_path: str | None = None,
    ) -> list[SearchResult]:
        """Search for similar chunks using cosine similarity."""
        # Build query with optional filters
        query = "SELECT * FROM vectors WHERE 1=1"
        params: list[Any] = []

        if filter_file_type:
            query += " AND file_type = ?"
            params.append(filter_file_type)

        if filter_file_path:
            query += " AND file_path LIKE ?"
            params.append(f"%{filter_file_path}%")

        with self._cursor() as cursor:
            cursor.execute(query, params)
            rows = cursor.fetchall()

        # Calculate similarities
        results = []
        for row in rows:
            embedding = _unpack_embedding(row["embedding"])
            score = _cosine_similarity(query_embedding, embedding)

            results.append(
                SearchResult(
                    chunk_id=row["chunk_id"],
                    content=row["content"],
                    metadata=self._row_to_metadata(row),
                    score=score,
                )
            )

        # Sort by score descending and limit
        results.sort(key=lambda r: r.score, reverse=True)
        return results[:limit]

    def get(self, chunk_id: str) -> SearchResult | None:
        """Get a specific chunk by ID."""
        with self._cursor() as cursor:
            cursor.execute("SELECT * FROM vectors WHERE chunk_id = ?", (chunk_id,))
            row = cursor.fetchone()

            if not row:
                return None

            return SearchResult(
                chunk_id=row["chunk_id"],
                content=row["content"],
                metadata=self._row_to_metadata(row),
                score=1.0,  # Not from search
            )

    def delete(self, chunk_id: str) -> bool:
        """Delete a chunk by ID."""
        with self._cursor() as cursor:
            cursor.execute("DELETE FROM vectors WHERE chunk_id = ?", (chunk_id,))
            return cursor.rowcount > 0

    def delete_by_file(self, file_path: str) -> int:
        """Delete all chunks for a file."""
        with self._cursor() as cursor:
            cursor.execute("DELETE FROM vectors WHERE file_path = ?", (file_path,))
            return cursor.rowcount

    def get_stats(self) -> IndexStats:
        """Get index statistics."""
        with self._cursor() as cursor:
            # Count chunks
            cursor.execute("SELECT COUNT(*) as count FROM vectors")
            total_chunks = cursor.fetchone()["count"]

            # Count unique files
            cursor.execute("SELECT COUNT(DISTINCT file_path) as count FROM vectors")
            total_files = cursor.fetchone()["count"]

            # Get metadata
            cursor.execute("SELECT key, value FROM metadata")
            meta = {row["key"]: row["value"] for row in cursor.fetchall()}

        # Get file size
        try:
            size_bytes = self.path.stat().st_size
        except Exception:
            size_bytes = 0

        return IndexStats(
            total_chunks=total_chunks,
            total_files=total_files,
            dimensions=int(meta.get("dimensions", 0)),
            provider=meta.get("provider", "unknown"),
            model=meta.get("model", "unknown"),
            last_updated=meta.get("last_updated"),
            size_bytes=size_bytes,
        )

    def clear(self) -> None:
        """Clear all stored data."""
        with self._cursor() as cursor:
            cursor.execute("DELETE FROM vectors")
            cursor.execute("UPDATE metadata SET value = '0' WHERE key = 'dimensions'")

    def get_file_hashes(self) -> dict[str, str]:
        """Get hash values for all indexed files."""
        with self._cursor() as cursor:
            cursor.execute("""
                SELECT DISTINCT file_path, chunk_hash
                FROM vectors
                WHERE chunk_hash IS NOT NULL
            """)

            hashes = {}
            for row in cursor.fetchall():
                file_path = row["file_path"]
                # Use first chunk's hash as file hash
                if file_path not in hashes:
                    hashes[file_path] = row["chunk_hash"]

            return hashes

    def update_metadata(self, key: str, value: str) -> None:
        """Update index metadata."""
        with self._cursor() as cursor:
            cursor.execute(
                "INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)", (key, value)
            )

    def _row_to_metadata(self, row: sqlite3.Row) -> ChunkMetadata:
        """Convert database row to ChunkMetadata."""
        return ChunkMetadata(
            file_path=row["file_path"],
            chunk_type=ChunkType(row["chunk_type"]),
            start_line=row["start_line"],
            end_line=row["end_line"],
            name=row["name"],
            docstring=row["docstring"],
            imports=json.loads(row["imports"]) if row["imports"] else [],
            parent_name=row["parent_name"],
            file_type=row["file_type"],
            last_modified=datetime.fromisoformat(row["last_modified"])
            if row["last_modified"]
            else None,
            chunk_hash=row["chunk_hash"],
        )

    def close(self) -> None:
        """Close all database connections across threads."""
        with self._lock:
            for conn in self._all_connections:
                try:
                    conn.close()
                except Exception:
                    pass
            self._all_connections.clear()

        if hasattr(self._local, "conn"):
            delattr(self._local, "conn")

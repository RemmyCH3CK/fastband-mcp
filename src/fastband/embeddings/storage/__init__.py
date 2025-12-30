"""
Vector storage backends for embeddings.

Provides:
- VectorStore: Abstract base class for vector storage
- SQLiteVectorStore: SQLite-based vector storage
"""

from fastband.embeddings.storage.base import SearchResult, VectorStore
from fastband.embeddings.storage.sqlite import SQLiteVectorStore

__all__ = [
    "VectorStore",
    "SearchResult",
    "SQLiteVectorStore",
]

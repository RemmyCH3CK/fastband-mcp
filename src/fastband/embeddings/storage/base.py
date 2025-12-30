"""
Base vector storage interface.

Defines the abstract interface for storing and searching embeddings.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from fastband.embeddings.base import ChunkMetadata


@dataclass(slots=True)
class SearchResult:
    """A single search result."""

    chunk_id: str
    content: str
    metadata: ChunkMetadata
    score: float  # Similarity score (higher is more similar)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "chunk_id": self.chunk_id,
            "content": self.content,
            "metadata": self.metadata.to_dict(),
            "score": self.score,
        }


@dataclass
class IndexStats:
    """Statistics about the vector index."""

    total_chunks: int
    total_files: int
    dimensions: int
    provider: str
    model: str
    last_updated: str | None = None
    size_bytes: int = 0


class VectorStore(ABC):
    """
    Abstract base class for vector storage.

    Vector stores persist embedding vectors and support similarity search.
    Implementations handle storage format and search algorithms.

    Example:
        class MyStore(VectorStore):
            def store(self, chunk_id, embedding, content, metadata):
                # Store in your backend
                pass

            def search(self, query_embedding, limit):
                # Find similar vectors
                return [SearchResult(...), ...]
    """

    @abstractmethod
    def store(
        self,
        chunk_id: str,
        embedding: list[float],
        content: str,
        metadata: ChunkMetadata,
    ) -> None:
        """
        Store a chunk with its embedding.

        Args:
            chunk_id: Unique identifier for the chunk
            embedding: Embedding vector
            content: Original text content
            metadata: Chunk metadata
        """
        pass

    @abstractmethod
    def store_batch(
        self,
        items: list[tuple],  # List of (chunk_id, embedding, content, metadata)
    ) -> int:
        """
        Store multiple chunks efficiently.

        Args:
            items: List of (chunk_id, embedding, content, metadata) tuples

        Returns:
            Number of items stored
        """
        pass

    @abstractmethod
    def search(
        self,
        query_embedding: list[float],
        limit: int = 10,
        filter_file_type: str | None = None,
        filter_file_path: str | None = None,
    ) -> list[SearchResult]:
        """
        Search for similar chunks.

        Args:
            query_embedding: Query embedding vector
            limit: Maximum results to return
            filter_file_type: Optional file type filter
            filter_file_path: Optional file path pattern filter

        Returns:
            List of SearchResult ordered by similarity (highest first)
        """
        pass

    @abstractmethod
    def get(self, chunk_id: str) -> SearchResult | None:
        """
        Get a specific chunk by ID.

        Args:
            chunk_id: Chunk identifier

        Returns:
            SearchResult or None if not found
        """
        pass

    @abstractmethod
    def delete(self, chunk_id: str) -> bool:
        """
        Delete a chunk.

        Args:
            chunk_id: Chunk identifier

        Returns:
            True if deleted, False if not found
        """
        pass

    @abstractmethod
    def delete_by_file(self, file_path: str) -> int:
        """
        Delete all chunks for a file.

        Args:
            file_path: Path to the file

        Returns:
            Number of chunks deleted
        """
        pass

    @abstractmethod
    def get_stats(self) -> IndexStats:
        """Get index statistics."""
        pass

    @abstractmethod
    def clear(self) -> None:
        """Clear all stored data."""
        pass

    @abstractmethod
    def get_file_hashes(self) -> dict[str, str]:
        """
        Get hash values for all indexed files.

        Returns:
            Dict mapping file_path -> hash
            Used for change detection during incremental indexing.
        """
        pass

    def close(self) -> None:
        """Close any open connections (optional to implement)."""
        pass

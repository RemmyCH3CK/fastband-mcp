"""
Embeddings module for semantic code search.

This module provides:
- EmbeddingProvider: Abstract interface for embedding providers
- Chunker: Code splitting for optimal embedding
- VectorStore: Storage for embedding vectors
- SemanticIndex: Orchestration of indexing and search

Example:
    from fastband.embeddings import SemanticIndex, OpenAIEmbeddings

    # Create index with OpenAI embeddings
    index = SemanticIndex(
        provider=OpenAIEmbeddings(api_key="..."),
        storage_path=Path(".fastband/semantic_index.db"),
    )

    # Index a codebase
    await index.index_directory(Path("src/"))

    # Search for relevant code
    results = await index.search("authentication logic", limit=5)
"""

from fastband.embeddings.base import (
    ChunkMetadata,
    EmbeddingConfig,
    EmbeddingProvider,
    EmbeddingResult,
)
from fastband.embeddings.index import SemanticIndex

__all__ = [
    "EmbeddingProvider",
    "EmbeddingResult",
    "EmbeddingConfig",
    "ChunkMetadata",
    "SemanticIndex",
]

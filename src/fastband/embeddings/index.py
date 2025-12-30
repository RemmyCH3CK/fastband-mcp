"""
Semantic Index - Main orchestrator for code indexing and search.

Combines embedding providers, chunkers, and storage into a cohesive
semantic code search system.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from fastband.embeddings.base import (
    CodeChunk,
    EmbeddingConfig,
    EmbeddingProvider,
)
from fastband.embeddings.chunkers.base import Chunker
from fastband.embeddings.chunkers.semantic import SemanticChunker
from fastband.embeddings.storage.base import IndexStats, SearchResult, VectorStore
from fastband.embeddings.storage.sqlite import SQLiteVectorStore

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class IndexingProgress:
    """Progress of an indexing operation."""

    total_files: int = 0
    processed_files: int = 0
    total_chunks: int = 0
    embedded_chunks: int = 0
    skipped_files: int = 0
    errors: list[str] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []

    @property
    def percent_complete(self) -> float:
        if self.total_files == 0:
            return 0.0
        return (self.processed_files / self.total_files) * 100


@dataclass(slots=True)
class IndexingResult:
    """Result of an indexing operation."""

    success: bool
    chunks_indexed: int
    files_processed: int
    files_skipped: int
    duration_seconds: float
    errors: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "chunks_indexed": self.chunks_indexed,
            "files_processed": self.files_processed,
            "files_skipped": self.files_skipped,
            "duration_seconds": round(self.duration_seconds, 2),
            "errors": self.errors,
        }


class SemanticIndex:
    """
    Main orchestrator for semantic code search.

    Coordinates chunking, embedding, and storage to provide
    semantic search over codebases.

    Example:
        from fastband.embeddings import SemanticIndex
        from fastband.embeddings.providers import OpenAIEmbeddings

        index = SemanticIndex(
            provider=OpenAIEmbeddings(),
            storage_path=Path(".fastband/semantic.db"),
        )

        # Index a codebase
        result = await index.index_directory(Path("src/"))

        # Search for relevant code
        results = await index.search("authentication logic", limit=5)
    """

    def __init__(
        self,
        provider: EmbeddingProvider,
        storage_path: Path | None = None,
        chunker: Chunker | None = None,
        store: VectorStore | None = None,
    ):
        """
        Initialize the semantic index.

        Args:
            provider: Embedding provider to use
            storage_path: Path for the SQLite database (default: .fastband/semantic.db)
            chunker: Code chunker (default: SemanticChunker)
            store: Vector store (default: SQLiteVectorStore at storage_path)
        """
        self.provider = provider
        self.chunker = chunker or SemanticChunker()

        if store:
            self.store = store
        else:
            storage_path = storage_path or Path(".fastband/semantic.db")
            self.store = SQLiteVectorStore(
                path=storage_path,
                provider=provider.name,
                model=provider.config.model or provider.default_model,
            )

    async def index_directory(
        self,
        directory: Path,
        incremental: bool = True,
        progress_callback: Callable[[object], None] | None = None,
    ) -> IndexingResult:
        """
        Index all code files in a directory.

        Args:
            directory: Directory to index
            incremental: Only re-index changed files (default: True)
            progress_callback: Optional callback for progress updates

        Returns:
            IndexingResult with statistics
        """
        start_time = datetime.now()
        directory = Path(directory).resolve()

        progress = IndexingProgress()

        try:
            # Get existing file hashes for incremental indexing
            existing_hashes = self.store.get_file_hashes() if incremental else {}

            # Chunk all files
            logger.info(f"Chunking files in {directory}")
            all_chunks = self.chunker.chunk_directory(directory, recursive=True)
            progress.total_chunks = len(all_chunks)

            # Group chunks by file
            chunks_by_file: dict[str, list[CodeChunk]] = {}
            for chunk in all_chunks:
                file_path = chunk.metadata.file_path
                if file_path not in chunks_by_file:
                    chunks_by_file[file_path] = []
                chunks_by_file[file_path].append(chunk)

            progress.total_files = len(chunks_by_file)

            # Filter out unchanged files
            chunks_to_index = []
            for file_path, chunks in chunks_by_file.items():
                if incremental and file_path in existing_hashes:
                    # Check if file changed
                    current_hash = chunks[0].metadata.chunk_hash if chunks else None
                    if current_hash == existing_hashes.get(file_path):
                        progress.skipped_files += 1
                        continue

                    # File changed - delete old chunks
                    self.store.delete_by_file(file_path)

                chunks_to_index.extend(chunks)
                progress.processed_files += 1

                if progress_callback:
                    progress_callback(progress)

            if not chunks_to_index:
                logger.info("No files to index (all up to date)")
                return IndexingResult(
                    success=True,
                    chunks_indexed=0,
                    files_processed=0,
                    files_skipped=progress.skipped_files,
                    duration_seconds=(datetime.now() - start_time).total_seconds(),
                    errors=[],
                )

            # Embed chunks in batches
            logger.info(f"Embedding {len(chunks_to_index)} chunks")
            batch_size = self.provider.config.batch_size
            store_items = []

            for i in range(0, len(chunks_to_index), batch_size):
                batch = chunks_to_index[i : i + batch_size]
                texts = [chunk.content for chunk in batch]

                try:
                    result = await self.provider.embed(texts)

                    for chunk, embedding in zip(batch, result.embeddings, strict=False):
                        store_items.append(
                            (
                                chunk.chunk_id,
                                embedding,
                                chunk.content,
                                chunk.metadata,
                            )
                        )
                        progress.embedded_chunks += 1

                except Exception as e:
                    error_msg = f"Embedding batch failed: {e}"
                    logger.error(error_msg)
                    progress.errors.append(error_msg)

                if progress_callback:
                    progress_callback(progress)

            # Store all embeddings
            logger.info(f"Storing {len(store_items)} embeddings")
            self.store.store_batch(store_items)

            # Update last_updated metadata
            if isinstance(self.store, SQLiteVectorStore):
                self.store.update_metadata("last_updated", datetime.now().isoformat())

            duration = (datetime.now() - start_time).total_seconds()
            logger.info(
                f"Indexing complete: {len(store_items)} chunks from "
                f"{progress.processed_files} files in {duration:.1f}s"
            )

            return IndexingResult(
                success=len(progress.errors) == 0,
                chunks_indexed=len(store_items),
                files_processed=progress.processed_files,
                files_skipped=progress.skipped_files,
                duration_seconds=duration,
                errors=progress.errors,
            )

        except Exception as e:
            logger.error(f"Indexing failed: {e}")
            return IndexingResult(
                success=False,
                chunks_indexed=progress.embedded_chunks,
                files_processed=progress.processed_files,
                files_skipped=progress.skipped_files,
                duration_seconds=(datetime.now() - start_time).total_seconds(),
                errors=[str(e)],
            )

    async def index_file(self, file_path: Path) -> IndexingResult:
        """
        Index a single file.

        Args:
            file_path: Path to the file

        Returns:
            IndexingResult with statistics
        """
        start_time = datetime.now()
        file_path = Path(file_path).resolve()

        # Validate file exists and is a file
        if not file_path.exists():
            return IndexingResult(
                success=False,
                chunks_indexed=0,
                files_processed=0,
                files_skipped=0,
                duration_seconds=(datetime.now() - start_time).total_seconds(),
                errors=[f"File not found: {file_path}"],
            )

        if not file_path.is_file():
            return IndexingResult(
                success=False,
                chunks_indexed=0,
                files_processed=0,
                files_skipped=0,
                duration_seconds=(datetime.now() - start_time).total_seconds(),
                errors=[f"Not a file: {file_path}"],
            )

        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
            chunks = self.chunker.chunk_file(file_path, content)

            if not chunks:
                return IndexingResult(
                    success=True,
                    chunks_indexed=0,
                    files_processed=1,
                    files_skipped=0,
                    duration_seconds=(datetime.now() - start_time).total_seconds(),
                    errors=[],
                )

            # Delete existing chunks for this file
            self.store.delete_by_file(str(file_path))

            # Embed and store
            texts = [chunk.content for chunk in chunks]
            result = await self.provider.embed(texts)

            store_items = [
                (chunk.chunk_id, embedding, chunk.content, chunk.metadata)
                for chunk, embedding in zip(chunks, result.embeddings, strict=False)
            ]
            self.store.store_batch(store_items)

            return IndexingResult(
                success=True,
                chunks_indexed=len(store_items),
                files_processed=1,
                files_skipped=0,
                duration_seconds=(datetime.now() - start_time).total_seconds(),
                errors=[],
            )

        except Exception as e:
            logger.error(f"Failed to index {file_path}: {e}")
            return IndexingResult(
                success=False,
                chunks_indexed=0,
                files_processed=0,
                files_skipped=0,
                duration_seconds=(datetime.now() - start_time).total_seconds(),
                errors=[str(e)],
            )

    async def search(
        self,
        query: str,
        limit: int = 10,
        file_type: str | None = None,
        file_path_pattern: str | None = None,
    ) -> list[SearchResult]:
        """
        Search for code chunks matching a query.

        Args:
            query: Natural language search query
            limit: Maximum results to return
            file_type: Filter by file type (e.g., "py", "js")
            file_path_pattern: Filter by file path pattern

        Returns:
            List of SearchResult ordered by relevance
        """
        # Embed the query
        query_embedding = await self.provider.embed_single(query)

        # Search
        results = self.store.search(
            query_embedding=query_embedding,
            limit=limit,
            filter_file_type=file_type,
            filter_file_path=file_path_pattern,
        )

        return results

    def get_stats(self) -> IndexStats:
        """Get index statistics."""
        return self.store.get_stats()

    def clear(self) -> None:
        """Clear the entire index."""
        self.store.clear()

    def close(self) -> None:
        """Close resources."""
        self.store.close()


def create_index(
    provider_name: str = "openai",
    storage_path: Path | None = None,
    **provider_kwargs,
) -> SemanticIndex:
    """
    Factory function to create a SemanticIndex with common configurations.

    Args:
        provider_name: Embedding provider ("openai", "gemini", "ollama")
        storage_path: Path for the SQLite database
        **provider_kwargs: Additional provider configuration

    Returns:
        Configured SemanticIndex

    Example:
        index = create_index("openai", api_key="sk-...")
        index = create_index("ollama", model="nomic-embed-text")
    """
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

    if provider_name not in providers:
        raise ValueError(f"Unknown provider: {provider_name}. Supported: {list(providers.keys())}")

    config = EmbeddingConfig(**provider_kwargs)
    provider = providers[provider_name](config)

    return SemanticIndex(
        provider=provider,
        storage_path=storage_path,
    )

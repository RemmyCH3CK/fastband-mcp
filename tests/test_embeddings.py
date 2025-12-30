"""
Tests for the embeddings module.

Tests cover:
- Base classes and data structures
- Chunkers (semantic and fixed)
- Vector storage (SQLite)
- SemanticIndex orchestration
"""

import tempfile
from pathlib import Path

import pytest

from fastband.embeddings.base import (
    ChunkMetadata,
    ChunkType,
    CodeChunk,
    EmbeddingConfig,
    EmbeddingProvider,
    EmbeddingResult,
)
from fastband.embeddings.chunkers.base import ChunkerConfig
from fastband.embeddings.chunkers.fixed import FixedChunker
from fastband.embeddings.chunkers.semantic import SemanticChunker
from fastband.embeddings.storage.sqlite import SQLiteVectorStore

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def temp_dir():
    """Create a temporary directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_python_file(temp_dir):
    """Create a sample Python file for testing."""
    content = '''"""Module docstring."""

import os
from pathlib import Path


class MyClass:
    """A sample class."""

    def __init__(self, name: str):
        """Initialize with name."""
        self.name = name

    def greet(self) -> str:
        """Return a greeting."""
        return f"Hello, {self.name}!"


def standalone_function(x: int, y: int) -> int:
    """Add two numbers."""
    return x + y


def another_function():
    """Another function without params."""
    pass
'''
    file_path = temp_dir / "sample.py"
    file_path.write_text(content)
    return file_path


@pytest.fixture
def sample_js_file(temp_dir):
    """Create a sample JavaScript file for testing."""
    content = """import { useState } from 'react';

export function MyComponent({ name }) {
    const [count, setCount] = useState(0);
    return <div>{name}: {count}</div>;
}

class UserService {
    constructor(apiUrl) {
        this.apiUrl = apiUrl;
    }

    async getUser(id) {
        const response = await fetch(`${this.apiUrl}/users/${id}`);
        return response.json();
    }
}

const helperFunction = (a, b) => a + b;
"""
    file_path = temp_dir / "sample.js"
    file_path.write_text(content)
    return file_path


@pytest.fixture
def mock_embedding_provider():
    """Create a mock embedding provider."""

    class MockProvider(EmbeddingProvider):
        def __init__(self):
            config = EmbeddingConfig()
            super().__init__(config)

        def _validate_config(self):
            pass

        @property
        def name(self) -> str:
            return "mock"

        @property
        def default_model(self) -> str:
            return "mock-model"

        @property
        def dimensions(self) -> int:
            return 384

        async def embed(self, texts):
            # Return random-ish embeddings
            embeddings = []
            for i, text in enumerate(texts):
                # Simple deterministic embedding based on text length
                emb = [float(i) / 100 + len(text) / 1000] * 384
                embeddings.append(emb)

            return EmbeddingResult(
                embeddings=embeddings,
                model="mock-model",
                provider="mock",
                dimensions=384,
                usage={"prompt_tokens": len(texts) * 10, "total_tokens": len(texts) * 10},
            )

    return MockProvider()


@pytest.fixture
def vector_store(temp_dir):
    """Create a temporary vector store."""
    db_path = temp_dir / "test_vectors.db"
    store = SQLiteVectorStore(path=db_path, provider="test", model="test-model")
    yield store
    store.close()


# =============================================================================
# CHUNK METADATA TESTS
# =============================================================================


class TestChunkMetadata:
    """Tests for ChunkMetadata."""

    def test_to_dict(self):
        """Test conversion to dictionary."""
        metadata = ChunkMetadata(
            file_path="/test/file.py",
            chunk_type=ChunkType.FUNCTION,
            start_line=10,
            end_line=20,
            name="my_function",
            docstring="A test function",
            imports=["import os"],
            file_type="python",
        )

        d = metadata.to_dict()

        assert d["file_path"] == "/test/file.py"
        assert d["chunk_type"] == "function"
        assert d["name"] == "my_function"
        assert d["imports"] == ["import os"]

    def test_from_dict(self):
        """Test creation from dictionary."""
        d = {
            "file_path": "/test/file.py",
            "chunk_type": "class",
            "start_line": 1,
            "end_line": 50,
            "name": "MyClass",
            "file_type": "python",
        }

        metadata = ChunkMetadata.from_dict(d)

        assert metadata.file_path == "/test/file.py"
        assert metadata.chunk_type == ChunkType.CLASS
        assert metadata.name == "MyClass"


class TestCodeChunk:
    """Tests for CodeChunk."""

    def test_chunk_id(self):
        """Test chunk ID generation."""
        metadata = ChunkMetadata(
            file_path="/test/file.py",
            chunk_type=ChunkType.FUNCTION,
            start_line=10,
            end_line=20,
        )
        chunk = CodeChunk(content="def test(): pass", metadata=metadata)

        chunk_id = chunk.chunk_id
        assert len(chunk_id) == 16  # SHA256 truncated

    def test_compute_hash(self):
        """Test content hash computation."""
        metadata = ChunkMetadata(
            file_path="/test/file.py",
            chunk_type=ChunkType.FUNCTION,
            start_line=1,
            end_line=1,
        )
        chunk = CodeChunk(content="def test(): pass", metadata=metadata)

        hash1 = chunk.compute_hash()
        assert len(hash1) == 16

        # Different content should have different hash
        chunk2 = CodeChunk(content="def other(): pass", metadata=metadata)
        hash2 = chunk2.compute_hash()
        assert hash1 != hash2


# =============================================================================
# SEMANTIC CHUNKER TESTS
# =============================================================================


class TestSemanticChunker:
    """Tests for SemanticChunker."""

    def test_chunk_python_file(self, sample_python_file):
        """Test chunking a Python file."""
        chunker = SemanticChunker()
        content = sample_python_file.read_text()

        chunks = chunker.chunk_file(sample_python_file, content)

        # Should find class and functions
        assert len(chunks) >= 3

        # Check chunk types
        chunk_types = [c.metadata.chunk_type for c in chunks]
        assert ChunkType.CLASS in chunk_types or ChunkType.FUNCTION in chunk_types

        # Check names are extracted
        names = [c.metadata.name for c in chunks if c.metadata.name]
        assert "MyClass" in names or "standalone_function" in names

    def test_chunk_javascript_file(self, sample_js_file):
        """Test chunking a JavaScript file."""
        chunker = SemanticChunker()
        content = sample_js_file.read_text()

        chunks = chunker.chunk_file(sample_js_file, content)

        # Should find function and class
        assert len(chunks) >= 1

    def test_chunk_directory(self, temp_dir, sample_python_file, sample_js_file):
        """Test chunking a directory."""
        chunker = SemanticChunker()

        chunks = chunker.chunk_directory(temp_dir)

        # Should find chunks from both files
        assert len(chunks) >= 2

        # Check file paths are different
        file_paths = {c.metadata.file_path for c in chunks}
        assert len(file_paths) >= 2

    def test_extract_imports(self, sample_python_file):
        """Test import extraction."""
        chunker = SemanticChunker()
        content = sample_python_file.read_text()

        chunks = chunker.chunk_file(sample_python_file, content)

        # At least one chunk should have imports
        has_imports = any(c.metadata.imports for c in chunks)
        assert has_imports

    def test_exclude_patterns(self, temp_dir):
        """Test that exclude patterns work."""
        # Create a file in __pycache__
        cache_dir = temp_dir / "__pycache__"
        cache_dir.mkdir()
        (cache_dir / "module.pyc").write_text("cached")

        # Create a normal file
        (temp_dir / "normal.py").write_text("def test(): pass")

        chunker = SemanticChunker()
        chunks = chunker.chunk_directory(temp_dir)

        # Should not include __pycache__ files
        file_paths = [c.metadata.file_path for c in chunks]
        assert not any("__pycache__" in p for p in file_paths)


# =============================================================================
# FIXED CHUNKER TESTS
# =============================================================================


class TestFixedChunker:
    """Tests for FixedChunker."""

    def test_chunk_small_file(self, temp_dir):
        """Test chunking a small file."""
        content = "def test():\n    pass\n"
        file_path = temp_dir / "small.py"
        file_path.write_text(content)

        chunker = FixedChunker(ChunkerConfig(max_chunk_size=500))
        chunks = chunker.chunk_file(file_path, content)

        # Small file should be one chunk
        assert len(chunks) == 1
        assert chunks[0].metadata.chunk_type == ChunkType.FILE

    def test_chunk_large_file(self, temp_dir):
        """Test chunking a large file."""
        # Create a file with many lines
        lines = [f"line {i}: " + "x" * 50 for i in range(500)]
        content = "\n".join(lines)
        file_path = temp_dir / "large.py"
        file_path.write_text(content)

        config = ChunkerConfig(max_chunk_size=200, overlap=20)
        chunker = FixedChunker(config)
        chunks = chunker.chunk_file(file_path, content)

        # Should have multiple chunks
        assert len(chunks) > 1

        # Chunks should be BLOCK type
        assert all(c.metadata.chunk_type == ChunkType.BLOCK for c in chunks)


# =============================================================================
# SQLITE VECTOR STORE TESTS
# =============================================================================


class TestSQLiteVectorStore:
    """Tests for SQLiteVectorStore."""

    def test_store_and_get(self, vector_store):
        """Test storing and retrieving a chunk."""
        metadata = ChunkMetadata(
            file_path="/test/file.py",
            chunk_type=ChunkType.FUNCTION,
            start_line=1,
            end_line=10,
            name="test_func",
            file_type="python",
        )

        embedding = [0.1] * 384
        vector_store.store("chunk1", embedding, "def test(): pass", metadata)

        result = vector_store.get("chunk1")

        assert result is not None
        assert result.chunk_id == "chunk1"
        assert result.content == "def test(): pass"
        assert result.metadata.name == "test_func"

    def test_store_batch(self, vector_store):
        """Test batch storage."""
        items = []
        for i in range(10):
            metadata = ChunkMetadata(
                file_path=f"/test/file{i}.py",
                chunk_type=ChunkType.FUNCTION,
                start_line=1,
                end_line=10,
                file_type="python",
            )
            items.append((f"chunk{i}", [float(i) / 10] * 384, f"content {i}", metadata))

        count = vector_store.store_batch(items)

        assert count == 10

        stats = vector_store.get_stats()
        assert stats.total_chunks == 10

    def test_search(self, vector_store):
        """Test similarity search."""
        # Store some embeddings
        for i in range(5):
            metadata = ChunkMetadata(
                file_path=f"/test/file{i}.py",
                chunk_type=ChunkType.FUNCTION,
                start_line=1,
                end_line=10,
                file_type="python",
            )
            # Create embeddings that are increasingly similar to query
            embedding = [float(i) / 10] * 384
            vector_store.store(f"chunk{i}", embedding, f"content {i}", metadata)

        # Query with embedding most similar to chunk4
        query_embedding = [0.4] * 384
        results = vector_store.search(query_embedding, limit=3)

        assert len(results) == 3
        # Results should be sorted by similarity
        assert results[0].score >= results[1].score >= results[2].score

    def test_search_with_filter(self, vector_store):
        """Test search with file type filter."""
        # Store Python and JavaScript chunks
        for ext, file_type in [(".py", "python"), (".js", "javascript")]:
            for i in range(3):
                metadata = ChunkMetadata(
                    file_path=f"/test/file{i}{ext}",
                    chunk_type=ChunkType.FUNCTION,
                    start_line=1,
                    end_line=10,
                    file_type=file_type,
                )
                vector_store.store(f"chunk_{file_type}_{i}", [0.5] * 384, "content", metadata)

        # Search only Python files
        results = vector_store.search([0.5] * 384, limit=10, filter_file_type="python")

        assert all(r.metadata.file_type == "python" for r in results)
        assert len(results) == 3

    def test_delete(self, vector_store):
        """Test deleting a chunk."""
        metadata = ChunkMetadata(
            file_path="/test/file.py",
            chunk_type=ChunkType.FUNCTION,
            start_line=1,
            end_line=10,
            file_type="python",
        )
        vector_store.store("chunk1", [0.5] * 384, "content", metadata)

        assert vector_store.get("chunk1") is not None

        result = vector_store.delete("chunk1")
        assert result is True

        assert vector_store.get("chunk1") is None

    def test_delete_by_file(self, vector_store):
        """Test deleting all chunks for a file."""
        file_path = "/test/file.py"
        for i in range(5):
            metadata = ChunkMetadata(
                file_path=file_path,
                chunk_type=ChunkType.FUNCTION,
                start_line=i * 10,
                end_line=(i + 1) * 10,
                file_type="python",
            )
            vector_store.store(f"chunk{i}", [0.5] * 384, f"content {i}", metadata)

        count = vector_store.delete_by_file(file_path)

        assert count == 5
        assert vector_store.get_stats().total_chunks == 0

    def test_get_stats(self, vector_store):
        """Test getting index statistics."""
        # Empty store
        stats = vector_store.get_stats()
        assert stats.total_chunks == 0
        assert stats.provider == "test"

        # Add some chunks
        for i in range(3):
            metadata = ChunkMetadata(
                file_path=f"/test/file{i}.py",
                chunk_type=ChunkType.FUNCTION,
                start_line=1,
                end_line=10,
                file_type="python",
            )
            vector_store.store(f"chunk{i}", [0.5] * 384, "content", metadata)

        stats = vector_store.get_stats()
        assert stats.total_chunks == 3
        assert stats.total_files == 3
        assert stats.dimensions == 384

    def test_clear(self, vector_store):
        """Test clearing the store."""
        metadata = ChunkMetadata(
            file_path="/test/file.py",
            chunk_type=ChunkType.FUNCTION,
            start_line=1,
            end_line=10,
            file_type="python",
        )
        vector_store.store("chunk1", [0.5] * 384, "content", metadata)

        vector_store.clear()

        assert vector_store.get_stats().total_chunks == 0


# =============================================================================
# SEMANTIC INDEX TESTS
# =============================================================================


class TestSemanticIndex:
    """Tests for SemanticIndex."""

    @pytest.mark.asyncio
    async def test_index_file(self, temp_dir, sample_python_file, mock_embedding_provider):
        """Test indexing a single file."""
        from fastband.embeddings.index import SemanticIndex

        storage_path = temp_dir / "test.db"
        index = SemanticIndex(
            provider=mock_embedding_provider,
            storage_path=storage_path,
        )

        try:
            result = await index.index_file(sample_python_file)

            assert result.success
            assert result.chunks_indexed > 0
            assert result.files_processed == 1

            # Check stats
            stats = index.get_stats()
            assert stats.total_chunks > 0

        finally:
            index.close()

    @pytest.mark.asyncio
    async def test_index_directory(self, temp_dir, sample_python_file, mock_embedding_provider):
        """Test indexing a directory."""
        from fastband.embeddings.index import SemanticIndex

        storage_path = temp_dir / "test.db"
        index = SemanticIndex(
            provider=mock_embedding_provider,
            storage_path=storage_path,
        )

        try:
            result = await index.index_directory(temp_dir)

            assert result.success
            assert result.chunks_indexed > 0
            assert result.files_processed >= 1

        finally:
            index.close()

    @pytest.mark.asyncio
    async def test_search(self, temp_dir, sample_python_file, mock_embedding_provider):
        """Test semantic search."""
        from fastband.embeddings.index import SemanticIndex

        storage_path = temp_dir / "test.db"
        index = SemanticIndex(
            provider=mock_embedding_provider,
            storage_path=storage_path,
        )

        try:
            # Index first
            await index.index_file(sample_python_file)

            # Search
            results = await index.search("greeting function", limit=5)

            assert len(results) > 0
            assert all(hasattr(r, "score") for r in results)

        finally:
            index.close()

    @pytest.mark.asyncio
    async def test_incremental_indexing(self, temp_dir, mock_embedding_provider):
        """Test incremental indexing skips unchanged files."""
        from fastband.embeddings.index import SemanticIndex

        # Create a file
        file1 = temp_dir / "file1.py"
        file1.write_text("def test1(): pass")

        storage_path = temp_dir / "test.db"
        index = SemanticIndex(
            provider=mock_embedding_provider,
            storage_path=storage_path,
        )

        try:
            # Initial index
            result1 = await index.index_directory(temp_dir, incremental=True)
            assert result1.files_processed >= 1

            # Re-index without changes
            result2 = await index.index_directory(temp_dir, incremental=True)
            assert result2.files_skipped >= 1

        finally:
            index.close()


# =============================================================================
# CONTEXT TOOLS TESTS
# =============================================================================


class TestContextTools:
    """Tests for context MCP tools."""

    @pytest.mark.asyncio
    async def test_index_status_no_index(self, temp_dir):
        """Test index status when no index exists."""
        from fastband.tools.context import IndexStatusTool

        tool = IndexStatusTool()
        result = await tool.execute(directory=str(temp_dir))

        assert result.success
        assert result.data["indexed"] is False

    @pytest.mark.asyncio
    async def test_semantic_search_no_index(self, temp_dir):
        """Test search when no index exists."""
        from fastband.tools.context import SemanticSearchTool

        tool = SemanticSearchTool()
        result = await tool.execute(
            query="test query",
            directory=str(temp_dir),
        )

        assert result.success is False
        assert "No index found" in result.error

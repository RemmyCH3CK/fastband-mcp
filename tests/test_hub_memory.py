"""Tests for Fastband Hub memory system."""

import os
import tempfile
from pathlib import Path

import pytest

from fastband.hub.memory import MemoryConfig, MemoryStore, SemanticMemory
from fastband.hub.models import MemoryContext, MemoryEntry


class TestMemoryStore:
    """Test MemoryStore class."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database file."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            path = f.name
        yield Path(path)
        # Cleanup
        if os.path.exists(path):
            os.unlink(path)

    @pytest.fixture
    def store(self, temp_db):
        """Create a MemoryStore instance."""
        store = MemoryStore(path=temp_db)
        yield store
        store.close()  # Ensure proper cleanup

    def test_store_initialization(self, store):
        """Test store initializes correctly."""
        assert store.path is not None
        # DB file should exist after init
        assert store.path.exists()

    def test_insert_entry(self, store):
        """Test inserting a memory entry."""
        entry = MemoryEntry(
            entry_id="mem_123",
            user_id="user_123",
            content="Test content",
            source="conversation",
        )

        store.insert(entry)

        # Verify by getting count
        count = store.get_entry_count("user_123")
        assert count == 1

    def test_insert_entry_with_embedding(self, store):
        """Test inserting entry with embedding."""
        embedding = [0.1, 0.2, 0.3, 0.4, 0.5]
        entry = MemoryEntry(
            entry_id="mem_456",
            user_id="user_123",
            content="Embedded content",
            source="file",
        )

        store.insert(entry, embedding)

        count = store.get_entry_count("user_123")
        assert count == 1

    def test_insert_batch(self, store):
        """Test batch inserting entries."""
        entries = []
        for i in range(5):
            entry = MemoryEntry(
                entry_id=f"batch_{i}",
                user_id="user_1",
                content=f"Batch content {i}",
                source="test",
            )
            embedding = [0.1 * i, 0.2 * i, 0.3 * i]
            entries.append((entry, embedding))

        count = store.insert_batch(entries)

        assert count == 5
        assert store.get_entry_count("user_1") == 5

    def test_search_with_embeddings(self, store):
        """Test searching with embeddings."""
        # Insert entries with embeddings
        for i in range(3):
            entry = MemoryEntry(
                entry_id=f"search_{i}",
                user_id="user_search",
                content=f"Search content {i}",
                source="test",
            )
            embedding = [float(i + 1), float(i + 2), float(i + 3)]
            store.insert(entry, embedding)

        # Search with similar embedding
        query_embedding = [1.0, 2.0, 3.0]
        results = store.search(
            query_embedding=query_embedding,
            user_id="user_search",
            limit=10,
            similarity_threshold=0.0,  # Low threshold to get results
        )

        assert len(results) >= 1
        # Results are (entry, similarity) tuples
        for entry, similarity in results:
            assert entry.user_id == "user_search"
            assert isinstance(similarity, float)

    def test_get_entry_count(self, store):
        """Test counting entries by user."""
        for i in range(7):
            store.insert(
                MemoryEntry(
                    entry_id=f"count_{i}",
                    user_id="user_count",
                    content=f"Content {i}",
                    source="test",
                )
            )

        count = store.get_entry_count("user_count")
        assert count == 7

    def test_delete_oldest(self, store):
        """Test deleting oldest entries."""
        # Save some entries
        for i in range(10):
            store.insert(
                MemoryEntry(
                    entry_id=f"delete_{i}",
                    user_id="user_delete",
                    content=f"Content {i}",
                    source="test",
                )
            )

        # Delete 5 oldest
        deleted = store.delete_oldest("user_delete", 5)

        assert deleted == 5
        assert store.get_entry_count("user_delete") == 5

    def test_update_access(self, store):
        """Test updating access count."""
        entry = MemoryEntry(
            entry_id="mem_access",
            user_id="user_1",
            content="Access me",
            source="test",
        )
        store.insert(entry)

        # Update access
        store.update_access("mem_access")
        store.update_access("mem_access")

        # Verify access was tracked (internal check, no public getter)
        count = store.get_entry_count("user_1")
        assert count == 1

    def test_clear_user(self, store):
        """Test clearing all entries for a user."""
        # Save entries for different users
        for i in range(3):
            store.insert(
                MemoryEntry(
                    entry_id=f"mem_user1_{i}",
                    user_id="user_1",
                    content=f"Content {i}",
                    source="test",
                )
            )

        for i in range(2):
            store.insert(
                MemoryEntry(
                    entry_id=f"mem_user2_{i}",
                    user_id="user_2",
                    content=f"Content {i}",
                    source="test",
                )
            )

        # Clear user_1
        deleted = store.clear_user("user_1")

        assert deleted == 3
        assert store.get_entry_count("user_1") == 0
        assert store.get_entry_count("user_2") == 2


class TestSemanticMemory:
    """Test SemanticMemory class."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database file."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            path = f.name
        yield Path(path)
        if os.path.exists(path):
            os.unlink(path)

    @pytest.fixture
    async def memory(self, temp_db):
        """Create a SemanticMemory instance."""
        config = MemoryConfig(
            storage_path=temp_db,
            embedding_provider="none",  # Don't use real embeddings in tests
        )
        memory = SemanticMemory(config)
        yield memory
        await memory.close()  # Ensure proper cleanup

    @pytest.mark.asyncio
    async def test_store_memory(self, memory):
        """Test storing a memory."""
        entry = await memory.store(
            content="Test memory content",
            user_id="user_123",
            source="conversation",
        )

        assert entry is not None
        # Entry ID is a UUID
        assert entry.entry_id is not None
        assert len(entry.entry_id) > 0
        assert entry.content == "Test memory content"
        assert entry.user_id == "user_123"

    @pytest.mark.asyncio
    async def test_store_with_metadata(self, memory):
        """Test storing memory with metadata."""
        entry = await memory.store(
            content="Memory with metadata",
            user_id="user_123",
            source="file",
            metadata={"file_path": "/test/file.py", "line": 42},
        )

        assert entry is not None
        assert entry.metadata == {"file_path": "/test/file.py", "line": 42}

    @pytest.mark.asyncio
    async def test_query_without_embeddings(self, memory):
        """Test querying without embeddings returns empty context."""
        # Store some entries
        await memory.store("Content 1", "user_123", "test")
        await memory.store("Content 2", "user_123", "test")

        # Query without embeddings - should return empty (no embedding provider)
        context = await memory.query("search query", "user_123")

        # Without embeddings, should return empty
        assert isinstance(context, MemoryContext)
        assert len(context.entries) == 0

    @pytest.mark.asyncio
    async def test_clear_user_memory(self, memory):
        """Test clearing all memory for a user."""
        # Store multiple entries
        for i in range(5):
            await memory.store(f"Content {i}", "user_to_clear", "test")

        # Verify entries exist
        count = memory.get_entry_count("user_to_clear")
        assert count == 5

        # Clear
        deleted = await memory.clear_user_memory("user_to_clear")

        assert deleted == 5
        # Verify cleared
        count = memory.get_entry_count("user_to_clear")
        assert count == 0

    @pytest.mark.asyncio
    async def test_get_entry_count(self, memory):
        """Test getting entry count."""
        # Store some entries
        for i in range(3):
            await memory.store(f"Content {i}", "user_stats", "test")

        count = memory.get_entry_count("user_stats")
        assert count == 3


class TestMemoryConfig:
    """Test MemoryConfig class."""

    def test_default_config(self):
        """Test default configuration."""
        config = MemoryConfig()

        # storage_path is a Path, not string
        assert config.storage_path == Path(".fastband/memory.db")
        assert config.embedding_provider == "openai"
        assert config.embedding_model == "text-embedding-3-small"
        assert config.similarity_threshold == 0.7
        # max_entries_per_user defaults to 0 (unlimited)
        assert config.max_entries_per_user == 0

    def test_custom_config(self):
        """Test custom configuration."""
        config = MemoryConfig(
            storage_path=Path("/custom/path.db"),
            embedding_provider="sentence-transformers",
            similarity_threshold=0.8,
            max_entries_per_user=5000,
        )

        assert config.storage_path == Path("/custom/path.db")
        assert config.embedding_provider == "sentence-transformers"
        assert config.similarity_threshold == 0.8
        assert config.max_entries_per_user == 5000

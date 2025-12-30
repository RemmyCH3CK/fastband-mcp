"""Tests for ticket storage backends."""

import tempfile
from pathlib import Path

import pytest

from fastband.tickets.models import (
    Agent,
    Ticket,
    TicketPriority,
    TicketStatus,
    TicketType,
)
from fastband.tickets.storage import (
    JSONTicketStore,
    SQLiteTicketStore,
    StorageFactory,
    get_store,
)

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def temp_dir():
    """Create a temporary directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def json_store(temp_dir):
    """Create a JSON store for testing."""
    path = temp_dir / "tickets.json"
    return JSONTicketStore(path)


@pytest.fixture
def sqlite_store(temp_dir):
    """Create a SQLite store for testing."""
    path = temp_dir / "tickets.db"
    return SQLiteTicketStore(path)


@pytest.fixture(params=["json", "sqlite"])
def store(request, temp_dir):
    """Parametrized fixture for both store types."""
    if request.param == "json":
        path = temp_dir / "tickets.json"
        return JSONTicketStore(path)
    else:
        path = temp_dir / "tickets.db"
        return SQLiteTicketStore(path)


@pytest.fixture
def sample_ticket():
    """Create a sample ticket for testing."""
    return Ticket(
        title="Test Ticket",
        description="Test description",
        ticket_type=TicketType.BUG,
        priority=TicketPriority.HIGH,
        requirements=["Req 1", "Req 2"],
        labels=["bug", "urgent"],
    )


# =============================================================================
# JSON STORE TESTS
# =============================================================================


class TestJSONStore:
    """Tests specific to JSONTicketStore."""

    def test_store_creation(self, temp_dir):
        """Test store creates file on first save."""
        path = temp_dir / "test.json"
        store = JSONTicketStore(path)

        assert store.path == path
        assert store.auto_save is True

    def test_load_empty_file(self, temp_dir):
        """Test loading non-existent file."""
        path = temp_dir / "nonexistent.json"
        store = JSONTicketStore(path)

        assert store.count() == 0

    def test_load_corrupted_file(self, temp_dir):
        """Test loading corrupted file."""
        path = temp_dir / "corrupted.json"
        path.write_text("not valid json")

        store = JSONTicketStore(path)
        assert store.count() == 0

    def test_manual_save(self, temp_dir):
        """Test manual save method."""
        path = temp_dir / "test.json"
        store = JSONTicketStore(path, auto_save=False)

        ticket = Ticket(title="Test")
        store.create(ticket)

        # File shouldn't exist yet
        assert not path.exists()

        store.save()
        assert path.exists()


# =============================================================================
# SQLITE STORE TESTS
# =============================================================================


class TestSQLiteStore:
    """Tests specific to SQLiteTicketStore."""

    def test_store_creation(self, temp_dir):
        """Test store creates database file."""
        path = temp_dir / "test.db"
        store = SQLiteTicketStore(path)

        assert path.exists()
        store.close()

    def test_schema_creation(self, temp_dir):
        """Test database schema is created."""
        path = temp_dir / "test.db"
        store = SQLiteTicketStore(path)

        # Verify tables exist by querying
        ticket = Ticket(title="Test")
        created = store.create(ticket)
        assert created.id is not None
        store.close()

    def test_close_connection(self, sqlite_store):
        """Test closing connection."""
        sqlite_store.close()
        # Should be able to reconnect
        ticket = Ticket(title="Test")
        sqlite_store.create(ticket)


# =============================================================================
# COMMON CRUD TESTS (Both Stores)
# =============================================================================


class TestTicketCRUD:
    """Tests for CRUD operations on both stores."""

    def test_create_ticket(self, store, sample_ticket):
        """Test creating a ticket."""
        created = store.create(sample_ticket)

        assert created.id is not None
        assert created.title == sample_ticket.title

    def test_create_assigns_id(self, store):
        """Test that create assigns ID."""
        ticket = Ticket(title="Test")
        ticket.id = ""  # Clear ID

        created = store.create(ticket)
        assert created.id != ""

    def test_get_ticket(self, store, sample_ticket):
        """Test getting a ticket."""
        created = store.create(sample_ticket)
        retrieved = store.get(created.id)

        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.title == sample_ticket.title

    def test_get_nonexistent(self, store):
        """Test getting non-existent ticket."""
        result = store.get("nonexistent-id")
        assert result is None

    def test_update_ticket(self, store, sample_ticket):
        """Test updating a ticket."""
        created = store.create(sample_ticket)

        created.title = "Updated Title"
        created.priority = TicketPriority.CRITICAL

        result = store.update(created)
        assert result is True

        retrieved = store.get(created.id)
        assert retrieved.title == "Updated Title"
        assert retrieved.priority == TicketPriority.CRITICAL

    def test_update_nonexistent(self, store):
        """Test updating non-existent ticket."""
        ticket = Ticket(id="nonexistent", title="Test")
        result = store.update(ticket)
        assert result is False

    def test_delete_ticket(self, store, sample_ticket):
        """Test deleting a ticket."""
        created = store.create(sample_ticket)

        result = store.delete(created.id)
        assert result is True

        retrieved = store.get(created.id)
        assert retrieved is None

    def test_delete_nonexistent(self, store):
        """Test deleting non-existent ticket."""
        result = store.delete("nonexistent-id")
        assert result is False


# =============================================================================
# LIST AND FILTER TESTS
# =============================================================================


class TestTicketListing:
    """Tests for listing and filtering tickets."""

    def test_list_all(self, store):
        """Test listing all tickets."""
        for i in range(5):
            store.create(Ticket(title=f"Ticket {i}"))

        tickets = store.list()
        assert len(tickets) == 5

    def test_list_with_limit(self, store):
        """Test listing with limit."""
        for i in range(10):
            store.create(Ticket(title=f"Ticket {i}"))

        tickets = store.list(limit=5)
        assert len(tickets) == 5

    def test_list_with_offset(self, store):
        """Test listing with offset."""
        for i in range(10):
            store.create(Ticket(title=f"Ticket {i}"))

        tickets = store.list(limit=5, offset=5)
        assert len(tickets) == 5

    def test_filter_by_status(self, store):
        """Test filtering by status."""
        store.create(Ticket(title="Open", status=TicketStatus.OPEN))
        store.create(Ticket(title="In Progress", status=TicketStatus.IN_PROGRESS))
        store.create(Ticket(title="Resolved", status=TicketStatus.RESOLVED))

        open_tickets = store.list(status=TicketStatus.OPEN)
        assert len(open_tickets) == 1
        assert open_tickets[0].title == "Open"

    def test_filter_by_priority(self, store):
        """Test filtering by priority."""
        store.create(Ticket(title="High", priority=TicketPriority.HIGH))
        store.create(Ticket(title="Low", priority=TicketPriority.LOW))

        high_tickets = store.list(priority=TicketPriority.HIGH)
        assert len(high_tickets) == 1
        assert high_tickets[0].title == "High"

    def test_filter_by_type(self, store):
        """Test filtering by ticket type."""
        store.create(Ticket(title="Bug", ticket_type=TicketType.BUG))
        store.create(Ticket(title="Feature", ticket_type=TicketType.FEATURE))

        bugs = store.list(ticket_type=TicketType.BUG)
        assert len(bugs) == 1
        assert bugs[0].title == "Bug"

    def test_filter_by_assigned_to(self, store):
        """Test filtering by assignee."""
        store.create(Ticket(title="Ticket 1", assigned_to="Agent1"))
        store.create(Ticket(title="Ticket 2", assigned_to="Agent2"))

        agent1_tickets = store.list(assigned_to="Agent1")
        assert len(agent1_tickets) == 1

    def test_filter_by_labels(self, store):
        """Test filtering by labels."""
        store.create(Ticket(title="Urgent", labels=["urgent", "bug"]))
        store.create(Ticket(title="Normal", labels=["enhancement"]))

        urgent = store.list(labels=["urgent"])
        assert len(urgent) == 1
        assert urgent[0].title == "Urgent"


# =============================================================================
# SEARCH TESTS
# =============================================================================


class TestTicketSearch:
    """Tests for ticket search functionality."""

    def test_search_in_title(self, store):
        """Test searching in title."""
        store.create(Ticket(title="Fix login bug"))
        store.create(Ticket(title="Add new feature"))

        results = store.search("login")
        assert len(results) == 1
        assert "login" in results[0].title.lower()

    def test_search_in_description(self, store):
        """Test searching in description."""
        store.create(Ticket(title="Bug", description="The login page crashes"))
        store.create(Ticket(title="Feature", description="Add dark mode"))

        results = store.search("crashes")
        assert len(results) == 1

    def test_search_case_insensitive(self, store):
        """Test case-insensitive search."""
        store.create(Ticket(title="LOGIN Bug"))

        results = store.search("login")
        assert len(results) == 1

    def test_search_no_results(self, store):
        """Test search with no results."""
        store.create(Ticket(title="Test ticket"))

        results = store.search("nonexistent")
        assert len(results) == 0


# =============================================================================
# COUNT TESTS
# =============================================================================


class TestTicketCount:
    """Tests for ticket counting."""

    def test_count_all(self, store):
        """Test counting all tickets."""
        for i in range(5):
            store.create(Ticket(title=f"Ticket {i}"))

        assert store.count() == 5

    def test_count_by_status(self, store):
        """Test counting by status."""
        store.create(Ticket(title="Open 1", status=TicketStatus.OPEN))
        store.create(Ticket(title="Open 2", status=TicketStatus.OPEN))
        store.create(Ticket(title="Closed", status=TicketStatus.CLOSED))

        assert store.count(status=TicketStatus.OPEN) == 2
        assert store.count(status=TicketStatus.CLOSED) == 1

    def test_count_by_priority(self, store):
        """Test counting by priority."""
        store.create(Ticket(title="High 1", priority=TicketPriority.HIGH))
        store.create(Ticket(title="High 2", priority=TicketPriority.HIGH))
        store.create(Ticket(title="Low", priority=TicketPriority.LOW))

        assert store.count(priority=TicketPriority.HIGH) == 2

    def test_count_empty(self, store):
        """Test counting empty store."""
        assert store.count() == 0


# =============================================================================
# ID GENERATION TESTS
# =============================================================================


class TestIDGeneration:
    """Tests for ticket ID generation."""

    def test_get_next_id(self, store):
        """Test getting next ID."""
        id1 = store.get_next_id()
        id2 = store.get_next_id()

        assert id1 != id2
        assert int(id2) == int(id1) + 1

    def test_ids_are_sequential(self, store):
        """Test IDs are sequential."""
        ids = [store.get_next_id() for _ in range(5)]
        int_ids = [int(id) for id in ids]

        for i in range(1, len(int_ids)):
            assert int_ids[i] == int_ids[i - 1] + 1


# =============================================================================
# AGENT MANAGEMENT TESTS
# =============================================================================


class TestAgentManagement:
    """Tests for agent management."""

    def test_save_agent(self, store):
        """Test saving an agent."""
        agent = Agent(name="MCP_Agent1", agent_type="ai")
        saved = store.save_agent(agent)

        assert saved.name == "MCP_Agent1"

    def test_get_agent(self, store):
        """Test getting an agent."""
        agent = Agent(name="MCP_Agent1", capabilities=["review"])
        store.save_agent(agent)

        retrieved = store.get_agent("MCP_Agent1")
        assert retrieved is not None
        assert retrieved.name == "MCP_Agent1"
        assert "review" in retrieved.capabilities

    def test_get_nonexistent_agent(self, store):
        """Test getting non-existent agent."""
        result = store.get_agent("nonexistent")
        assert result is None

    def test_update_agent(self, store):
        """Test updating an agent."""
        agent = Agent(name="MCP_Agent1", tickets_completed=0)
        store.save_agent(agent)

        agent.tickets_completed = 5
        store.save_agent(agent)

        retrieved = store.get_agent("MCP_Agent1")
        assert retrieved.tickets_completed == 5

    def test_list_agents(self, store):
        """Test listing agents."""
        store.save_agent(Agent(name="Agent1", active=True))
        store.save_agent(Agent(name="Agent2", active=True))
        store.save_agent(Agent(name="Agent3", active=False))

        active = store.list_agents(active_only=True)
        assert len(active) == 2

        all_agents = store.list_agents(active_only=False)
        assert len(all_agents) == 3


# =============================================================================
# BACKUP AND RESTORE TESTS
# =============================================================================


class TestBackupRestore:
    """Tests for backup and restore functionality."""

    def test_backup(self, store, temp_dir, sample_ticket):
        """Test creating a backup."""
        store.create(sample_ticket)

        backup_path = temp_dir / "backup" / "tickets.bak"
        result = store.backup(backup_path)

        assert result is True
        assert backup_path.exists()

    def test_restore(self, store, temp_dir, sample_ticket):
        """Test restoring from backup."""
        # Create and backup
        created = store.create(sample_ticket)
        backup_path = temp_dir / "backup.bak"
        store.backup(backup_path)

        # Delete ticket
        store.delete(created.id)
        assert store.get(created.id) is None

        # Restore
        result = store.restore(backup_path)
        assert result is True

        # Verify ticket is back
        restored = store.get(created.id)
        assert restored is not None
        assert restored.title == sample_ticket.title

    def test_restore_nonexistent(self, store, temp_dir):
        """Test restoring non-existent backup."""
        result = store.restore(temp_dir / "nonexistent.bak")
        assert result is False


# =============================================================================
# STORAGE FACTORY TESTS
# =============================================================================


class TestStorageFactory:
    """Tests for StorageFactory."""

    def test_create_json_store(self, temp_dir):
        """Test creating JSON store."""
        StorageFactory.clear_cache()
        path = temp_dir / "test.json"
        store = StorageFactory.create("json", path)

        assert isinstance(store, JSONTicketStore)

    def test_create_sqlite_store(self, temp_dir):
        """Test creating SQLite store."""
        StorageFactory.clear_cache()
        path = temp_dir / "test.db"
        store = StorageFactory.create("sqlite", path)

        assert isinstance(store, SQLiteTicketStore)

    def test_invalid_type(self, temp_dir):
        """Test creating invalid store type."""
        with pytest.raises(ValueError):
            StorageFactory.create("invalid", temp_dir / "test")

    def test_caching(self, temp_dir):
        """Test store caching."""
        StorageFactory.clear_cache()
        path = temp_dir / "test.json"

        store1 = StorageFactory.create("json", path)
        store2 = StorageFactory.create("json", path)

        assert store1 is store2

    def test_get_default(self, temp_dir):
        """Test getting default store."""
        StorageFactory.clear_cache()
        store = StorageFactory.get_default(temp_dir)

        assert isinstance(store, JSONTicketStore)
        assert ".fastband" in str(store.path)


# =============================================================================
# GET_STORE FUNCTION TESTS
# =============================================================================


class TestGetStore:
    """Tests for get_store convenience function."""

    def test_get_store_default(self, temp_dir, monkeypatch):
        """Test get_store with defaults."""
        monkeypatch.chdir(temp_dir)
        StorageFactory.clear_cache()

        store = get_store()
        assert isinstance(store, JSONTicketStore)

    def test_get_store_with_path(self, temp_dir):
        """Test get_store with custom path."""
        StorageFactory.clear_cache()
        path = temp_dir / "custom.json"

        store = get_store(path=path)
        assert store.path == path

    def test_get_store_sqlite(self, temp_dir):
        """Test get_store with SQLite."""
        StorageFactory.clear_cache()
        path = temp_dir / "custom.db"

        store = get_store(path=path, storage_type="sqlite")
        assert isinstance(store, SQLiteTicketStore)


# =============================================================================
# EDGE CASES
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases."""

    def test_empty_title(self, store):
        """Test ticket with empty title."""
        ticket = Ticket(title="")
        created = store.create(ticket)

        assert created.id is not None

    def test_special_characters(self, store):
        """Test ticket with special characters."""
        ticket = Ticket(
            title="Test <script>alert('xss')</script>",
            description="Unicode: 日本語 🎉",
        )
        created = store.create(ticket)
        retrieved = store.get(created.id)

        assert retrieved.title == ticket.title
        assert retrieved.description == ticket.description

    def test_large_description(self, store):
        """Test ticket with large description."""
        ticket = Ticket(
            title="Test",
            description="A" * 10000,
        )
        created = store.create(ticket)
        retrieved = store.get(created.id)

        assert len(retrieved.description) == 10000

    def test_concurrent_access(self, json_store):
        """Test concurrent access to JSON store."""
        import threading

        results = []

        def create_ticket(store, index):
            ticket = Ticket(title=f"Ticket {index}")
            created = store.create(ticket)
            results.append(created.id)

        threads = [threading.Thread(target=create_ticket, args=(json_store, i)) for i in range(10)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(results) == 10
        assert len(set(results)) == 10  # All IDs unique

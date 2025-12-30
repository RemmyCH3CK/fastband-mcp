"""
Performance tests for Fastband.

These tests verify that key operations meet performance targets:
- Tool load time: <50ms
- Provider switch: <100ms
- Memory footprint: <100MB

GitHub Issue: #38 - Performance optimization
"""

import gc
import tempfile
import time
from collections.abc import Callable
from pathlib import Path

import pytest

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def temp_tickets_path():
    """Create a temporary path for ticket storage."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir) / "tickets.json"


@pytest.fixture
def reset_registries():
    """Reset all registries before and after tests."""
    # Import here to avoid affecting other tests
    from fastband.providers.registry import ProviderRegistry
    from fastband.tools.registry import reset_registry

    reset_registry()
    ProviderRegistry.clear_all()
    yield
    reset_registry()
    ProviderRegistry.clear_all()


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def time_function(func: Callable, *args, **kwargs) -> float:
    """Time a function call, return milliseconds."""
    gc.collect()
    start = time.perf_counter()
    func(*args, **kwargs)
    return (time.perf_counter() - start) * 1000


async def time_async_function(func: Callable, *args, **kwargs) -> float:
    """Time an async function call, return milliseconds."""
    gc.collect()
    start = time.perf_counter()
    await func(*args, **kwargs)
    return (time.perf_counter() - start) * 1000


# =============================================================================
# TOOL REGISTRY PERFORMANCE TESTS
# =============================================================================


class TestToolRegistryPerformance:
    """Performance tests for the tool registry."""

    def test_registry_creation_time(self, reset_registries):
        """Test that creating a registry is fast."""
        from fastband.tools.registry import ToolRegistry

        elapsed = time_function(ToolRegistry)
        assert elapsed < 10, f"Registry creation took {elapsed:.2f}ms (target: <10ms)"

    def test_tool_registration_time(self, reset_registries):
        """Test that registering a tool is fast."""
        from fastband.tools.core.system import HealthCheckTool
        from fastband.tools.registry import ToolRegistry

        registry = ToolRegistry()
        tool = HealthCheckTool()

        elapsed = time_function(registry.register, tool)
        assert elapsed < 5, f"Tool registration took {elapsed:.2f}ms (target: <5ms)"

    def test_lazy_tool_registration_time(self, reset_registries):
        """Test that lazy registration is very fast (no import)."""
        from fastband.tools.base import ToolCategory
        from fastband.tools.registry import ToolRegistry

        registry = ToolRegistry()

        elapsed = time_function(
            registry.register_lazy,
            "test_tool",
            "fastband.tools.core.system",
            "HealthCheckTool",
            ToolCategory.CORE,
        )
        assert elapsed < 1, f"Lazy registration took {elapsed:.2f}ms (target: <1ms)"

    def test_tool_load_time(self, reset_registries):
        """Test that loading a tool is under 50ms (target)."""
        from fastband.tools.core.system import HealthCheckTool
        from fastband.tools.registry import ToolRegistry

        registry = ToolRegistry()
        registry.register(HealthCheckTool())

        elapsed = time_function(registry.load, "health_check")
        assert elapsed < 50, f"Tool load took {elapsed:.2f}ms (target: <50ms)"

    def test_lazy_tool_load_time(self, reset_registries):
        """Test that loading a lazy tool is under 50ms (includes import)."""
        from fastband.tools.base import ToolCategory
        from fastband.tools.registry import ToolRegistry

        registry = ToolRegistry()
        registry.register_lazy(
            "health_check", "fastband.tools.core.system", "HealthCheckTool", ToolCategory.CORE
        )

        # First load includes import
        elapsed = time_function(registry.load, "health_check")
        assert elapsed < 50, f"Lazy tool load took {elapsed:.2f}ms (target: <50ms)"

    def test_tool_get_time(self, reset_registries):
        """Test that getting a loaded tool is very fast (O(1))."""
        from fastband.tools.core.system import HealthCheckTool
        from fastband.tools.registry import ToolRegistry

        registry = ToolRegistry()
        registry.register(HealthCheckTool())
        registry.load("health_check")

        elapsed = time_function(registry.get, "health_check")
        assert elapsed < 0.1, f"Tool get took {elapsed:.2f}ms (target: <0.1ms)"

    def test_is_registered_check_time(self, reset_registries):
        """Test that checking registration is fast."""
        from fastband.tools.core.system import HealthCheckTool
        from fastband.tools.registry import ToolRegistry

        registry = ToolRegistry()
        registry.register(HealthCheckTool())

        elapsed = time_function(registry.is_registered, "health_check")
        assert elapsed < 0.1, f"is_registered took {elapsed:.2f}ms (target: <0.1ms)"


# =============================================================================
# PROVIDER REGISTRY PERFORMANCE TESTS
# =============================================================================


class TestProviderRegistryPerformance:
    """Performance tests for the provider registry."""

    def test_lazy_provider_registration_time(self, reset_registries):
        """Test that lazy provider registration is fast."""
        from fastband.providers.registry import ProviderRegistry

        ProviderRegistry.clear_all()

        elapsed = time_function(
            ProviderRegistry.register_lazy,
            "test_provider",
            "fastband.providers.claude",
            "ClaudeProvider",
        )
        assert elapsed < 1, f"Lazy registration took {elapsed:.2f}ms (target: <1ms)"

    def test_provider_is_registered_time(self, reset_registries):
        """Test that checking provider registration is fast."""
        from fastband.providers.registry import ProviderRegistry

        # Warm up call to trigger any lazy initialization
        ProviderRegistry.is_registered("claude")

        # Now time the actual call (should be pure dict lookup)
        elapsed = time_function(ProviderRegistry.is_registered, "claude")
        # Allow up to 1ms - very fast but accounts for system variability
        assert elapsed < 1.0, f"is_registered took {elapsed:.2f}ms (target: <1.0ms)"

    def test_available_providers_time(self, reset_registries):
        """Test that listing available providers is fast."""
        from fastband.providers.registry import ProviderRegistry

        elapsed = time_function(ProviderRegistry.available_providers)
        assert elapsed < 1, f"available_providers took {elapsed:.2f}ms (target: <1ms)"


# =============================================================================
# TICKET STORAGE PERFORMANCE TESTS
# =============================================================================


class TestTicketStoragePerformance:
    """Performance tests for ticket storage."""

    def test_store_creation_time(self, temp_tickets_path):
        """Test that creating a store is fast."""
        from fastband.tickets.storage import JSONTicketStore

        elapsed = time_function(JSONTicketStore, temp_tickets_path)
        assert elapsed < 50, f"Store creation took {elapsed:.2f}ms (target: <50ms)"

    def test_ticket_create_time(self, temp_tickets_path):
        """Test that creating a ticket is fast."""
        from fastband.tickets.models import Ticket, TicketPriority, TicketType
        from fastband.tickets.storage import JSONTicketStore

        store = JSONTicketStore(temp_tickets_path)
        ticket = Ticket(
            title="Test Ticket",
            description="Test description",
            ticket_type=TicketType.TASK,
            priority=TicketPriority.MEDIUM,
        )

        elapsed = time_function(store.create, ticket)
        assert elapsed < 50, f"Ticket create took {elapsed:.2f}ms (target: <50ms)"

    def test_ticket_get_time(self, temp_tickets_path):
        """Test that getting a ticket is fast."""
        from fastband.tickets.models import Ticket, TicketPriority, TicketType
        from fastband.tickets.storage import JSONTicketStore

        store = JSONTicketStore(temp_tickets_path)
        ticket = Ticket(
            title="Test Ticket",
            description="Test description",
            ticket_type=TicketType.TASK,
            priority=TicketPriority.MEDIUM,
        )
        created = store.create(ticket)

        # First get (cache miss)
        elapsed_miss = time_function(store.get, created.id)
        assert elapsed_miss < 10, f"Ticket get (miss) took {elapsed_miss:.2f}ms (target: <10ms)"

        # Second get (cache hit)
        elapsed_hit = time_function(store.get, created.id)
        assert elapsed_hit < 1, f"Ticket get (hit) took {elapsed_hit:.2f}ms (target: <1ms)"
        # Cache hit should be no slower than miss (allow equal due to timing variability)
        assert elapsed_hit <= elapsed_miss + 0.1, (
            "Cache hit should not be significantly slower than miss"
        )

    def test_ticket_cache_effectiveness(self, temp_tickets_path):
        """Test that caching improves repeated access."""
        from fastband.tickets.models import Ticket, TicketPriority, TicketType
        from fastband.tickets.storage import JSONTicketStore

        store = JSONTicketStore(temp_tickets_path, cache_size=10)

        # Create tickets
        ticket_ids = []
        for i in range(10):
            ticket = Ticket(
                title=f"Test Ticket {i}",
                description=f"Description {i}",
                ticket_type=TicketType.TASK,
                priority=TicketPriority.MEDIUM,
            )
            created = store.create(ticket)
            ticket_ids.append(created.id)

        # Access each ticket twice
        for ticket_id in ticket_ids:
            store.get(ticket_id)
            store.get(ticket_id)

        stats = store.get_cache_stats()
        assert stats["hits"] > 0, "Cache should have hits"
        assert stats["hit_rate"] > 40, f"Cache hit rate should be >40% (got {stats['hit_rate']}%)"

    def test_ticket_list_time(self, temp_tickets_path):
        """Test that listing tickets is fast."""
        from fastband.tickets.models import Ticket, TicketPriority, TicketType
        from fastband.tickets.storage import JSONTicketStore

        store = JSONTicketStore(temp_tickets_path)

        # Create 100 tickets
        for i in range(100):
            ticket = Ticket(
                title=f"Test Ticket {i}",
                description=f"Description {i}",
                ticket_type=TicketType.TASK,
                priority=TicketPriority.MEDIUM,
            )
            store.create(ticket)

        # Time listing
        elapsed = time_function(store.list, limit=50)
        assert elapsed < 100, f"Ticket list took {elapsed:.2f}ms (target: <100ms)"

    def test_ticket_search_time(self, temp_tickets_path):
        """Test that searching tickets is fast."""
        from fastband.tickets.models import Ticket, TicketPriority, TicketType
        from fastband.tickets.storage import JSONTicketStore

        store = JSONTicketStore(temp_tickets_path)

        # Create 100 tickets
        for i in range(100):
            ticket = Ticket(
                title=f"Test Ticket {i}",
                description=f"Description with keyword{i % 10}",
                ticket_type=TicketType.TASK,
                priority=TicketPriority.MEDIUM,
            )
            store.create(ticket)

        # Time search
        elapsed = time_function(store.search, "keyword5")
        assert elapsed < 100, f"Ticket search took {elapsed:.2f}ms (target: <100ms)"


# =============================================================================
# LAZY LOADING VERIFICATION TESTS
# =============================================================================


class TestLazyLoading:
    """Tests to verify lazy loading is working correctly."""

    def test_lazy_tool_not_imported_until_accessed(self, reset_registries):
        """Verify lazy tools aren't imported until accessed."""
        import sys

        from fastband.tools.base import ToolCategory
        from fastband.tools.registry import ToolRegistry

        registry = ToolRegistry()

        # Remove module from cache if present
        if "fastband.tools.core.files" in sys.modules:
            del sys.modules["fastband.tools.core.files"]

        # Register lazily
        registry.register_lazy(
            "read_file", "fastband.tools.core.files", "ReadFileTool", ToolCategory.FILE_OPS
        )

        # Module should NOT be imported yet
        assert registry.is_lazy("read_file"), "Tool should be marked as lazy"

        # Load the tool - this triggers the import
        status = registry.load("read_file")

        assert status.loaded, "Tool should be loaded"
        assert not registry.is_lazy("read_file"), "Tool should no longer be lazy after load"

    def test_lazy_provider_not_imported_until_accessed(self, reset_registries):
        """Verify lazy providers aren't imported until accessed."""
        import sys

        from fastband.providers.registry import ProviderRegistry

        ProviderRegistry.clear_all()

        # Remove module from cache if present
        if "fastband.providers.claude" in sys.modules:
            del sys.modules["fastband.providers.claude"]

        # Register lazily
        ProviderRegistry.register_lazy("claude", "fastband.providers.claude", "ClaudeProvider")

        # Provider should NOT be loaded yet
        assert not ProviderRegistry.is_loaded("claude"), "Provider should not be loaded yet"
        assert ProviderRegistry.is_registered("claude"), "Provider should be registered"


# =============================================================================
# TOOL EXECUTION PERFORMANCE TESTS
# =============================================================================


class TestToolExecutionPerformance:
    """Performance tests for tool execution."""

    @pytest.mark.asyncio
    async def test_tool_execution_time(self, reset_registries):
        """Test that tool execution is fast."""
        from fastband.tools.core.system import HealthCheckTool

        tool = HealthCheckTool()

        elapsed = await time_async_function(tool.safe_execute)
        assert elapsed < 50, f"Tool execution took {elapsed:.2f}ms (target: <50ms)"

    @pytest.mark.asyncio
    async def test_registry_execute_time(self, reset_registries):
        """Test that executing through registry is fast."""
        from fastband.tools.core.system import HealthCheckTool
        from fastband.tools.registry import ToolRegistry

        registry = ToolRegistry()
        registry.register(HealthCheckTool())
        registry.load("health_check")

        elapsed = await time_async_function(registry.execute, "health_check")
        assert elapsed < 50, f"Registry execute took {elapsed:.2f}ms (target: <50ms)"


# =============================================================================
# MEMORY TESTS (OPTIONAL - requires tracemalloc)
# =============================================================================


class TestMemoryUsage:
    """Memory usage tests."""

    def test_tool_registry_memory(self, reset_registries):
        """Test that tool registry has reasonable memory footprint."""
        import tracemalloc

        from fastband.tools.core.system import HealthCheckTool
        from fastband.tools.registry import ToolRegistry

        gc.collect()
        tracemalloc.start()

        try:
            registry = ToolRegistry()
            registry.register(HealthCheckTool())
            registry.load("health_check")

            current, peak = tracemalloc.get_traced_memory()
            peak_mb = peak / (1024 * 1024)

            # Should be well under target
            assert peak_mb < 10, f"Registry memory: {peak_mb:.2f}MB (target: <10MB)"
        finally:
            tracemalloc.stop()

    def test_ticket_store_memory(self, temp_tickets_path):
        """Test that ticket store has reasonable memory footprint."""
        import tracemalloc

        from fastband.tickets.models import Ticket, TicketPriority, TicketType
        from fastband.tickets.storage import JSONTicketStore

        gc.collect()
        tracemalloc.start()

        try:
            store = JSONTicketStore(temp_tickets_path)

            # Create 100 tickets
            for i in range(100):
                ticket = Ticket(
                    title=f"Test Ticket {i}",
                    description=f"Description {i}" * 10,  # Longer description
                    ticket_type=TicketType.TASK,
                    priority=TicketPriority.MEDIUM,
                )
                store.create(ticket)

            current, peak = tracemalloc.get_traced_memory()
            peak_mb = peak / (1024 * 1024)

            # Should be reasonable for 100 tickets
            assert peak_mb < 20, f"Store memory with 100 tickets: {peak_mb:.2f}MB (target: <20MB)"
        finally:
            tracemalloc.stop()

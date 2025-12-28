#!/usr/bin/env python3
"""
Performance Benchmark Script for Fastband.

Measures key performance metrics:
- Tool loading time (target: <50ms)
- Provider switch time (target: <100ms)
- Ticket CRUD operations
- Memory footprint (target: <100MB)

Usage:
    python scripts/benchmark.py [--iterations N] [--verbose]

GitHub Issue: #38 - Performance optimization
"""

import argparse
import asyncio
import gc
import json
import statistics
import sys
import tempfile
import time
import tracemalloc
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


@dataclass
class BenchmarkResult:
    """Result from a benchmark run."""
    name: str
    iterations: int
    times_ms: List[float] = field(default_factory=list)
    memory_bytes: Optional[int] = None
    target_ms: Optional[float] = None
    passed: bool = True
    error: Optional[str] = None

    @property
    def mean_ms(self) -> float:
        """Mean execution time in milliseconds."""
        return statistics.mean(self.times_ms) if self.times_ms else 0

    @property
    def median_ms(self) -> float:
        """Median execution time in milliseconds."""
        return statistics.median(self.times_ms) if self.times_ms else 0

    @property
    def min_ms(self) -> float:
        """Minimum execution time in milliseconds."""
        return min(self.times_ms) if self.times_ms else 0

    @property
    def max_ms(self) -> float:
        """Maximum execution time in milliseconds."""
        return max(self.times_ms) if self.times_ms else 0

    @property
    def std_dev_ms(self) -> float:
        """Standard deviation in milliseconds."""
        if len(self.times_ms) < 2:
            return 0
        return statistics.stdev(self.times_ms)

    @property
    def memory_mb(self) -> float:
        """Memory usage in megabytes."""
        if self.memory_bytes is None:
            return 0
        return self.memory_bytes / (1024 * 1024)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON output."""
        return {
            "name": self.name,
            "iterations": self.iterations,
            "mean_ms": round(self.mean_ms, 2),
            "median_ms": round(self.median_ms, 2),
            "min_ms": round(self.min_ms, 2),
            "max_ms": round(self.max_ms, 2),
            "std_dev_ms": round(self.std_dev_ms, 2),
            "memory_mb": round(self.memory_mb, 2) if self.memory_bytes else None,
            "target_ms": self.target_ms,
            "passed": self.passed,
            "error": self.error,
        }


class Benchmark:
    """Benchmark runner for Fastband performance testing."""

    def __init__(self, iterations: int = 10, verbose: bool = False):
        self.iterations = iterations
        self.verbose = verbose
        self.results: List[BenchmarkResult] = []

    def log(self, message: str) -> None:
        """Log a message if verbose mode is enabled."""
        if self.verbose:
            print(f"  [DEBUG] {message}")

    def time_sync(self, func: Callable, *args, **kwargs) -> float:
        """Time a synchronous function call, return milliseconds."""
        gc.collect()  # Ensure clean state
        start = time.perf_counter()
        func(*args, **kwargs)
        return (time.perf_counter() - start) * 1000

    async def time_async(self, func: Callable, *args, **kwargs) -> float:
        """Time an async function call, return milliseconds."""
        gc.collect()
        start = time.perf_counter()
        await func(*args, **kwargs)
        return (time.perf_counter() - start) * 1000

    def measure_memory(self, func: Callable, *args, **kwargs) -> int:
        """Measure peak memory usage of a function, return bytes."""
        gc.collect()
        tracemalloc.start()
        try:
            func(*args, **kwargs)
            current, peak = tracemalloc.get_traced_memory()
            return peak
        finally:
            tracemalloc.stop()

    def run_benchmark(
        self,
        name: str,
        func: Callable,
        target_ms: Optional[float] = None,
        setup: Optional[Callable] = None,
        teardown: Optional[Callable] = None,
    ) -> BenchmarkResult:
        """Run a synchronous benchmark."""
        result = BenchmarkResult(
            name=name,
            iterations=self.iterations,
            target_ms=target_ms,
        )

        print(f"\nBenchmark: {name}")

        try:
            for i in range(self.iterations):
                if setup:
                    setup()

                elapsed = self.time_sync(func)
                result.times_ms.append(elapsed)
                self.log(f"  Iteration {i + 1}: {elapsed:.2f}ms")

                if teardown:
                    teardown()

            # Check target
            if target_ms and result.mean_ms > target_ms:
                result.passed = False

            print(f"  Mean: {result.mean_ms:.2f}ms | Median: {result.median_ms:.2f}ms | Min: {result.min_ms:.2f}ms | Max: {result.max_ms:.2f}ms")
            if target_ms:
                status = "PASS" if result.passed else "FAIL"
                print(f"  Target: {target_ms}ms | Status: {status}")

        except Exception as e:
            result.error = str(e)
            result.passed = False
            print(f"  ERROR: {e}")

        self.results.append(result)
        return result

    async def run_async_benchmark(
        self,
        name: str,
        func: Callable,
        target_ms: Optional[float] = None,
        setup: Optional[Callable] = None,
        teardown: Optional[Callable] = None,
    ) -> BenchmarkResult:
        """Run an async benchmark."""
        result = BenchmarkResult(
            name=name,
            iterations=self.iterations,
            target_ms=target_ms,
        )

        print(f"\nBenchmark: {name}")

        try:
            for i in range(self.iterations):
                if setup:
                    if asyncio.iscoroutinefunction(setup):
                        await setup()
                    else:
                        setup()

                elapsed = await self.time_async(func)
                result.times_ms.append(elapsed)
                self.log(f"  Iteration {i + 1}: {elapsed:.2f}ms")

                if teardown:
                    if asyncio.iscoroutinefunction(teardown):
                        await teardown()
                    else:
                        teardown()

            # Check target
            if target_ms and result.mean_ms > target_ms:
                result.passed = False

            print(f"  Mean: {result.mean_ms:.2f}ms | Median: {result.median_ms:.2f}ms | Min: {result.min_ms:.2f}ms | Max: {result.max_ms:.2f}ms")
            if target_ms:
                status = "PASS" if result.passed else "FAIL"
                print(f"  Target: {target_ms}ms | Status: {status}")

        except Exception as e:
            result.error = str(e)
            result.passed = False
            print(f"  ERROR: {e}")

        self.results.append(result)
        return result

    def run_memory_benchmark(
        self,
        name: str,
        func: Callable,
        target_mb: Optional[float] = None,
    ) -> BenchmarkResult:
        """Run a memory usage benchmark."""
        result = BenchmarkResult(
            name=name,
            iterations=1,
            target_ms=target_mb * 1024 * 1024 if target_mb else None,  # Store as bytes
        )

        print(f"\nBenchmark: {name} (Memory)")

        try:
            memory_bytes = self.measure_memory(func)
            result.memory_bytes = memory_bytes
            result.times_ms = [0]  # No timing

            memory_mb = memory_bytes / (1024 * 1024)
            if target_mb and memory_mb > target_mb:
                result.passed = False

            print(f"  Peak Memory: {memory_mb:.2f}MB")
            if target_mb:
                status = "PASS" if result.passed else "FAIL"
                print(f"  Target: {target_mb}MB | Status: {status}")

        except Exception as e:
            result.error = str(e)
            result.passed = False
            print(f"  ERROR: {e}")

        self.results.append(result)
        return result

    def summary(self) -> Dict[str, Any]:
        """Generate a summary of all benchmark results."""
        passed = sum(1 for r in self.results if r.passed)
        failed = len(self.results) - passed

        return {
            "timestamp": datetime.now().isoformat(),
            "total_benchmarks": len(self.results),
            "passed": passed,
            "failed": failed,
            "results": [r.to_dict() for r in self.results],
        }

    def print_summary(self) -> None:
        """Print a summary of all benchmark results."""
        print("\n" + "=" * 60)
        print("BENCHMARK SUMMARY")
        print("=" * 60)

        summary = self.summary()
        print(f"\nTotal: {summary['total_benchmarks']} | Passed: {summary['passed']} | Failed: {summary['failed']}")

        if summary["failed"] > 0:
            print("\nFailed benchmarks:")
            for result in self.results:
                if not result.passed:
                    if result.error:
                        print(f"  - {result.name}: ERROR - {result.error}")
                    elif result.target_ms:
                        print(f"  - {result.name}: {result.mean_ms:.2f}ms (target: {result.target_ms}ms)")
                    elif result.memory_bytes:
                        print(f"  - {result.name}: {result.memory_mb:.2f}MB")


# =============================================================================
# BENCHMARK FUNCTIONS
# =============================================================================

def benchmark_tool_registry_import() -> None:
    """Benchmark importing the tool registry."""
    # Force reimport
    import importlib
    import sys

    # Remove from cache if present
    modules_to_remove = [k for k in sys.modules if k.startswith("fastband.tools")]
    for mod in modules_to_remove:
        del sys.modules[mod]

    # Import
    from fastband.tools import registry as _


def benchmark_tool_registry_creation() -> None:
    """Benchmark creating a new ToolRegistry instance."""
    from fastband.tools.registry import ToolRegistry
    _ = ToolRegistry()


def benchmark_tool_load() -> None:
    """Benchmark loading a single tool."""
    from fastband.tools.registry import ToolRegistry
    from fastband.tools.core.system import HealthCheckTool

    registry = ToolRegistry()
    tool = HealthCheckTool()
    registry.register(tool)
    registry.load(tool.name)


def benchmark_tool_load_all_core() -> None:
    """Benchmark loading all core tools."""
    from fastband.tools.registry import ToolRegistry
    from fastband.tools.core.system import HealthCheckTool
    from fastband.tools.core.files import ReadFileTool, WriteFileTool

    registry = ToolRegistry()

    # Register core tools
    for tool_class in [HealthCheckTool, ReadFileTool, WriteFileTool]:
        registry.register(tool_class())

    # Load all core
    registry.load_core()


def benchmark_provider_import() -> None:
    """Benchmark importing the provider registry."""
    import importlib
    import sys

    # Remove from cache
    modules_to_remove = [k for k in sys.modules if k.startswith("fastband.providers")]
    for mod in modules_to_remove:
        del sys.modules[mod]

    from fastband.providers import registry as _


def benchmark_provider_registry_get() -> None:
    """Benchmark getting a provider from registry."""
    from fastband.providers.registry import ProviderRegistry
    from fastband.providers.base import ProviderConfig

    # Clear instances to force fresh load
    ProviderRegistry._instances.clear()

    config = ProviderConfig(
        name="claude",
        api_key="test-key",
        model="claude-sonnet-4-20250514",
    )
    try:
        ProviderRegistry.get("claude", config)
    except Exception:
        pass  # API key validation may fail


def create_temp_store():
    """Create a temporary ticket store for benchmarking."""
    from fastband.tickets.storage import JSONTicketStore

    temp_dir = tempfile.mkdtemp()
    path = Path(temp_dir) / "tickets.json"
    return JSONTicketStore(path)


def benchmark_ticket_create():
    """Benchmark creating a ticket."""
    from fastband.tickets.models import Ticket, TicketType, TicketPriority

    store = create_temp_store()

    ticket = Ticket(
        title="Test Ticket",
        description="This is a test ticket for benchmarking",
        ticket_type=TicketType.TASK,
        priority=TicketPriority.MEDIUM,
    )
    store.create(ticket)


def benchmark_ticket_read():
    """Benchmark reading a ticket."""
    from fastband.tickets.models import Ticket, TicketType, TicketPriority

    store = create_temp_store()

    # Create ticket first
    ticket = Ticket(
        title="Test Ticket",
        description="This is a test ticket for benchmarking",
        ticket_type=TicketType.TASK,
        priority=TicketPriority.MEDIUM,
    )
    created = store.create(ticket)

    # Benchmark read
    store.get(created.id)


def benchmark_ticket_update():
    """Benchmark updating a ticket."""
    from fastband.tickets.models import Ticket, TicketType, TicketPriority

    store = create_temp_store()

    # Create ticket first
    ticket = Ticket(
        title="Test Ticket",
        description="This is a test ticket for benchmarking",
        ticket_type=TicketType.TASK,
        priority=TicketPriority.MEDIUM,
    )
    created = store.create(ticket)
    created.title = "Updated Title"
    store.update(created)


def benchmark_ticket_list():
    """Benchmark listing tickets."""
    from fastband.tickets.models import Ticket, TicketType, TicketPriority

    store = create_temp_store()

    # Create 100 tickets
    for i in range(100):
        ticket = Ticket(
            title=f"Test Ticket {i}",
            description=f"Description for ticket {i}",
            ticket_type=TicketType.TASK,
            priority=TicketPriority.MEDIUM,
        )
        store.create(ticket)

    # Benchmark list
    store.list(limit=50)


def benchmark_ticket_search():
    """Benchmark searching tickets."""
    from fastband.tickets.models import Ticket, TicketType, TicketPriority

    store = create_temp_store()

    # Create 100 tickets
    for i in range(100):
        ticket = Ticket(
            title=f"Test Ticket {i}",
            description=f"Description for ticket {i} with some keyword{i % 10}",
            ticket_type=TicketType.TASK,
            priority=TicketPriority.MEDIUM,
        )
        store.create(ticket)

    # Benchmark search
    store.search("keyword5")


def benchmark_memory_full_import():
    """Benchmark memory usage of full fastband import."""
    import sys

    # Clear all fastband modules
    modules_to_remove = [k for k in sys.modules if k.startswith("fastband")]
    for mod in modules_to_remove:
        del sys.modules[mod]

    gc.collect()

    # Import everything
    import fastband
    from fastband.tools import get_registry
    from fastband.providers import get_provider
    from fastband.tickets import get_store


async def benchmark_tool_execute():
    """Benchmark tool execution."""
    from fastband.tools.core.system import HealthCheckTool

    tool = HealthCheckTool()
    await tool.safe_execute()


def run_all_benchmarks(iterations: int = 10, verbose: bool = False) -> Benchmark:
    """Run all benchmarks."""
    bench = Benchmark(iterations=iterations, verbose=verbose)

    print("=" * 60)
    print("FASTBAND PERFORMANCE BENCHMARKS")
    print(f"Iterations per benchmark: {iterations}")
    print("=" * 60)

    # Tool Registry Benchmarks
    print("\n--- TOOL REGISTRY ---")

    bench.run_benchmark(
        "Tool Registry Import",
        benchmark_tool_registry_import,
        target_ms=50,
    )

    bench.run_benchmark(
        "Tool Registry Creation",
        benchmark_tool_registry_creation,
        target_ms=10,
    )

    bench.run_benchmark(
        "Single Tool Load",
        benchmark_tool_load,
        target_ms=50,
    )

    bench.run_benchmark(
        "Core Tools Load",
        benchmark_tool_load_all_core,
        target_ms=50,
    )

    # Provider Registry Benchmarks
    print("\n--- PROVIDER REGISTRY ---")

    bench.run_benchmark(
        "Provider Registry Import",
        benchmark_provider_import,
        target_ms=100,
    )

    bench.run_benchmark(
        "Provider Get (with lazy load)",
        benchmark_provider_registry_get,
        target_ms=100,
    )

    # Ticket Benchmarks
    print("\n--- TICKET OPERATIONS ---")

    bench.run_benchmark(
        "Ticket Create",
        benchmark_ticket_create,
        target_ms=50,
    )

    bench.run_benchmark(
        "Ticket Read",
        benchmark_ticket_read,
        target_ms=10,
    )

    bench.run_benchmark(
        "Ticket Update",
        benchmark_ticket_update,
        target_ms=50,
    )

    bench.run_benchmark(
        "Ticket List (100 tickets, fetch 50)",
        benchmark_ticket_list,
        target_ms=100,
    )

    bench.run_benchmark(
        "Ticket Search (100 tickets)",
        benchmark_ticket_search,
        target_ms=100,
    )

    # Memory Benchmarks
    print("\n--- MEMORY USAGE ---")

    bench.run_memory_benchmark(
        "Full Import Memory",
        benchmark_memory_full_import,
        target_mb=100,
    )

    # Async Benchmarks
    print("\n--- ASYNC OPERATIONS ---")

    asyncio.run(
        bench.run_async_benchmark(
            "Tool Execute (HealthCheck)",
            benchmark_tool_execute,
            target_ms=50,
        )
    )

    return bench


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Run Fastband performance benchmarks"
    )
    parser.add_argument(
        "-n", "--iterations",
        type=int,
        default=10,
        help="Number of iterations per benchmark (default: 10)"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output"
    )
    parser.add_argument(
        "-o", "--output",
        type=str,
        help="Output JSON file for results"
    )

    args = parser.parse_args()

    bench = run_all_benchmarks(
        iterations=args.iterations,
        verbose=args.verbose,
    )

    bench.print_summary()

    if args.output:
        with open(args.output, "w") as f:
            json.dump(bench.summary(), f, indent=2)
        print(f"\nResults saved to: {args.output}")

    # Exit with error code if any benchmark failed
    if any(not r.passed for r in bench.results):
        sys.exit(1)


if __name__ == "__main__":
    main()

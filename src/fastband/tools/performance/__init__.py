"""
Performance Tools - Performance analysis and benchmarking.

Provides MCP tools for:
- Bundle size analysis
- Build time profiling
- HTTP endpoint benchmarking
- Performance report generation

Usage:
    # Analyze bundle
    result = await perf_bundle()
    print(f"Bundle: {result['total_size_mb']}MB")

    # Time build
    result = await perf_build("npm run build")
    print(f"Build time: {result['total_seconds']}s")

    # Benchmark endpoint
    result = await perf_benchmark("https://api.example.com/health")
    print(f"Response time: {result['value']}ms")
"""

from fastband.tools.performance.models import (
    BuildTiming,
    BundleAnalysis,
    BundleFile,
    PerformanceBenchmark,
    PerformanceMetricType,
    PerformanceReport,
    TrendDirection,
)
from fastband.tools.performance.tool import (
    PerformanceTool,
    analyze_bundle,
    benchmark_url,
    perf_benchmark,
    perf_build,
    perf_bundle,
    perf_report,
    time_build_command,
)

__all__ = [
    # Main tool
    "PerformanceTool",
    # Utility functions
    "analyze_bundle",
    "time_build_command",
    "benchmark_url",
    # MCP functions
    "perf_bundle",
    "perf_build",
    "perf_benchmark",
    "perf_report",
    # Models
    "PerformanceMetricType",
    "TrendDirection",
    "BundleFile",
    "BundleAnalysis",
    "BuildTiming",
    "PerformanceBenchmark",
    "PerformanceReport",
]


# =========================================================================
# MCP TOOL REGISTRATION
# =========================================================================

def register_tools(mcp_server):
    """Register performance tools with the MCP server."""

    @mcp_server.tool()
    async def perf_analyze_bundle(output_dir: str = "", path: str = "") -> dict:
        """
        Analyze bundle size from build output.

        Scans build output for JS, CSS, and assets,
        calculating total size and identifying large files.

        Args:
            output_dir: Build output directory (auto-detects if empty)
            path: Project path

        Returns:
            Bundle analysis:
            - total_size_mb: Total bundle size
            - breakdown: Size by file type
            - largest_files: Top files by size
            - recommendations: Optimization suggestions

        Example:
            {} or {"output_dir": "dist"}
        """
        return await perf_bundle(output_dir=output_dir, path=path)

    @mcp_server.tool()
    async def perf_time_build(command: str = "", path: str = "") -> dict:
        """
        Time a build command execution.

        Measures total build time and attempts to parse
        phase timing from output.

        Args:
            command: Build command (auto-detects if empty)
            path: Project path

        Returns:
            Build timing:
            - total_seconds: Total build time
            - phases: Time per build phase
            - is_regression: If slower than baseline

        Example:
            {} or {"command": "npm run build"}
        """
        return await perf_build(command=command, path=path)

    @mcp_server.tool()
    async def perf_benchmark_url(
        url: str,
        iterations: int = 5,
        path: str = "",
    ) -> dict:
        """
        Benchmark HTTP endpoint response time.

        Makes multiple requests to measure average,
        min, max, and percentile response times.

        Args:
            url: URL to benchmark
            iterations: Number of requests (default: 5)
            path: Project path

        Returns:
            Benchmark results:
            - value: Average response time (ms)
            - min_value: Fastest response
            - max_value: Slowest response
            - p95: 95th percentile

        Example:
            {"url": "https://api.example.com/health"}
        """
        return await perf_benchmark(url=url, iterations=iterations, path=path)

    @mcp_server.tool()
    async def perf_get_report(include_build: bool = False, path: str = "") -> dict:
        """
        Generate comprehensive performance report.

        Combines bundle analysis, build timing, and
        benchmarks into a single scored report.

        Args:
            include_build: Include build timing (slower)
            path: Project path

        Returns:
            Performance report:
            - overall_score: Combined score (0-100)
            - grade: Letter grade (A-F)
            - bundle/build/runtime scores
            - recommendations

        Example:
            {} or {"include_build": true}
        """
        return await perf_report(include_build=include_build, path=path)

    return [
        "perf_analyze_bundle",
        "perf_time_build",
        "perf_benchmark_url",
        "perf_get_report",
    ]

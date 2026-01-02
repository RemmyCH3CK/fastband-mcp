"""
Performance Tool - Performance analysis and benchmarking.

Provides MCP tools for:
- Bundle size analysis
- Build time profiling
- Response time benchmarking
- Performance regression detection
"""

import gzip
import json
import logging
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastband.tools.performance.models import (
    BuildTiming,
    BundleAnalysis,
    BundleFile,
    PerformanceBenchmark,
    PerformanceMetricType,
    PerformanceReport,
    TrendDirection,
)

logger = logging.getLogger(__name__)


# Bundle size thresholds (in KB)
BUNDLE_THRESHOLDS = {
    "warning": 500,  # 500KB warning
    "critical": 1000,  # 1MB critical
}

# Build time thresholds (in seconds)
BUILD_THRESHOLDS = {
    "warning": 60,  # 1 minute warning
    "critical": 180,  # 3 minutes critical
}


def analyze_bundle(output_dir: str) -> BundleAnalysis:
    """Analyze bundle size from build output directory."""
    path = Path(output_dir)

    if not path.exists():
        return BundleAnalysis(recommendations=["Build output directory not found"])

    analysis = BundleAnalysis()
    files = []

    # Scan for JS, CSS, and asset files
    for pattern, is_vendor in [
        ("**/*.js", False),
        ("**/vendor*.js", True),
        ("**/node_modules/**/*.js", True),
        ("**/*.css", False),
        ("**/*.png", False),
        ("**/*.jpg", False),
        ("**/*.svg", False),
        ("**/*.woff*", False),
    ]:
        for file_path in path.glob(pattern):
            if file_path.is_file():
                try:
                    size = file_path.stat().st_size

                    # Calculate gzip size for JS/CSS
                    gzip_size = 0
                    if file_path.suffix in (".js", ".css"):
                        with open(file_path, "rb") as f:
                            content = f.read()
                            gzip_size = len(gzip.compress(content))

                    bundle_file = BundleFile(
                        path=str(file_path.relative_to(path)),
                        size_bytes=size,
                        gzip_size_bytes=gzip_size,
                        is_vendor="vendor" in str(file_path).lower() or "node_modules" in str(file_path),
                    )
                    files.append(bundle_file)

                    # Update totals
                    analysis.total_size_bytes += size
                    analysis.total_gzip_bytes += gzip_size

                    if file_path.suffix == ".js":
                        analysis.js_size_bytes += size
                    elif file_path.suffix == ".css":
                        analysis.css_size_bytes += size
                    else:
                        analysis.assets_size_bytes += size

                    if bundle_file.is_vendor:
                        analysis.vendor_size_bytes += size
                    else:
                        analysis.app_size_bytes += size

                except OSError:
                    continue

    # Sort and get largest files
    files.sort(key=lambda f: f.size_bytes, reverse=True)
    analysis.files = files
    analysis.largest_files = files[:10]

    # Generate recommendations
    if analysis.total_size_bytes > BUNDLE_THRESHOLDS["critical"] * 1024:
        analysis.recommendations.append("Bundle size is critical - consider code splitting")

    if analysis.vendor_percentage > 70:
        analysis.recommendations.append("Vendor code is >70% of bundle - review dependencies")

    if any(f.size_bytes > 200 * 1024 for f in files if f.path.endswith(".js")):
        analysis.recommendations.append("Large JS files detected - consider lazy loading")

    return analysis


def time_build_command(command: str, cwd: str) -> BuildTiming:
    """Time a build command execution."""
    timing = BuildTiming(build_command=command)

    start_time = time.time()

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=600,  # 10 minute timeout
        )

        end_time = time.time()
        timing.total_time_ms = int((end_time - start_time) * 1000)

        # Try to parse phase timing from output
        output = result.stdout + result.stderr

        # Common patterns for phase timing
        phase_patterns = [
            (r"Compiled in (\d+(?:\.\d+)?)\s*(?:ms|s)", "compile"),
            (r"Built in (\d+(?:\.\d+)?)\s*(?:ms|s)", "build"),
            (r"Bundled in (\d+(?:\.\d+)?)\s*(?:ms|s)", "bundle"),
            (r"Type checking: (\d+(?:\.\d+)?)\s*(?:ms|s)", "typecheck"),
        ]

        import re
        for pattern, phase_name in phase_patterns:
            match = re.search(pattern, output, re.IGNORECASE)
            if match:
                value = float(match.group(1))
                # Convert to ms if in seconds
                if "s" in match.group(0).lower() and "ms" not in match.group(0).lower():
                    value *= 1000
                timing.phases[phase_name] = int(value)

    except subprocess.TimeoutExpired:
        timing.total_time_ms = 600000
        timing.phases["error"] = "timeout"
    except Exception as e:
        logger.warning(f"Build timing failed: {e}")

    return timing


def benchmark_url(url: str, iterations: int = 5) -> PerformanceBenchmark:
    """Benchmark response time for a URL."""
    import urllib.request

    times = []

    for _ in range(iterations):
        try:
            start = time.time()
            req = urllib.request.Request(url)
            req.add_header("User-Agent", "Fastband-Benchmark/1.0")

            with urllib.request.urlopen(req, timeout=30) as response:
                _ = response.read()

            end = time.time()
            times.append((end - start) * 1000)  # ms
        except Exception:
            continue

    if not times:
        return PerformanceBenchmark(
            name=url,
            metric_type=PerformanceMetricType.RESPONSE_TIME,
            value=0,
            unit="ms",
        )

    times.sort()

    return PerformanceBenchmark(
        name=url,
        metric_type=PerformanceMetricType.RESPONSE_TIME,
        value=sum(times) / len(times),
        unit="ms",
        min_value=times[0],
        max_value=times[-1],
        p50=times[len(times) // 2],
        p95=times[int(len(times) * 0.95)] if len(times) >= 20 else times[-1],
        warning_threshold=1000,  # 1 second
        critical_threshold=3000,  # 3 seconds
    )


class PerformanceTool:
    """Unified performance analysis tool."""

    def __init__(self, project_root: str):
        self.project_root = Path(project_root)

    async def analyze_bundle(self, output_dir: str = "") -> dict[str, Any]:
        """Analyze bundle size."""
        # Try common output directories
        if not output_dir:
            for candidate in ["dist", "build", ".next", "out", "public"]:
                candidate_path = self.project_root / candidate
                if candidate_path.exists():
                    output_dir = str(candidate_path)
                    break

        if not output_dir:
            return {"error": "No build output directory found"}

        analysis = analyze_bundle(output_dir)

        # Calculate score
        total_kb = analysis.total_size_bytes / 1024
        if total_kb < BUNDLE_THRESHOLDS["warning"]:
            score = 100
        elif total_kb < BUNDLE_THRESHOLDS["critical"]:
            score = 70
        else:
            score = 40

        return {
            "type": "bundle_analysis",
            "score": score,
            "output_dir": output_dir,
            **analysis.to_dict(),
        }

    async def time_build(self, command: str = "") -> dict[str, Any]:
        """Time a build command."""
        # Auto-detect build command
        if not command:
            pkg_json = self.project_root / "package.json"
            if pkg_json.exists():
                with open(pkg_json) as f:
                    pkg = json.load(f)
                    scripts = pkg.get("scripts", {})
                    if "build" in scripts:
                        command = "npm run build"

            if not command:
                pyproject = self.project_root / "pyproject.toml"
                if pyproject.exists():
                    command = "python -m build"

        if not command:
            return {"error": "No build command specified or detected"}

        timing = time_build_command(command, str(self.project_root))

        # Calculate score
        total_s = timing.total_seconds
        if total_s < BUILD_THRESHOLDS["warning"]:
            score = 100
        elif total_s < BUILD_THRESHOLDS["critical"]:
            score = 70
        else:
            score = 40

        return {
            "type": "build_timing",
            "score": score,
            **timing.to_dict(),
        }

    async def benchmark_endpoint(
        self,
        url: str,
        iterations: int = 5,
    ) -> dict[str, Any]:
        """Benchmark an HTTP endpoint."""
        if not url:
            return {"error": "URL is required"}

        benchmark = benchmark_url(url, iterations)

        return {
            "type": "endpoint_benchmark",
            **benchmark.to_dict(),
        }

    async def get_report(self, include_build: bool = False) -> dict[str, Any]:
        """Generate comprehensive performance report."""
        report = PerformanceReport(
            project_name=self.project_root.name,
        )

        # Bundle analysis
        bundle_result = await self.analyze_bundle()
        if "error" not in bundle_result:
            report.bundle_score = bundle_result.get("score", 100)

            if bundle_result.get("total_size_mb", 0) > 1:
                report.warnings.append(f"Bundle size is {bundle_result.get('total_size_mb')}MB")

            report.recommendations.extend(bundle_result.get("recommendations", []))

        # Build timing (optional - can be slow)
        if include_build:
            build_result = await self.time_build()
            if "error" not in build_result:
                report.build_score = build_result.get("score", 100)

                if build_result.get("is_regression"):
                    report.warnings.append("Build time has regressed")

        # Calculate overall score
        scores = [report.bundle_score, report.build_score, report.runtime_score]
        report.overall_score = sum(scores) // len(scores)

        return report.to_dict()


# =============================================================================
# MCP-FACING FUNCTIONS
# =============================================================================

async def perf_bundle(output_dir: str = "", path: str = "") -> dict[str, Any]:
    """Analyze bundle size."""
    project_path = path or os.getcwd()
    tool = PerformanceTool(project_path)
    return await tool.analyze_bundle(output_dir)


async def perf_build(command: str = "", path: str = "") -> dict[str, Any]:
    """Time a build command."""
    project_path = path or os.getcwd()
    tool = PerformanceTool(project_path)
    return await tool.time_build(command)


async def perf_benchmark(
    url: str,
    iterations: int = 5,
    path: str = "",
) -> dict[str, Any]:
    """Benchmark an HTTP endpoint."""
    project_path = path or os.getcwd()
    tool = PerformanceTool(project_path)
    return await tool.benchmark_endpoint(url, iterations)


async def perf_report(include_build: bool = False, path: str = "") -> dict[str, Any]:
    """Generate performance report."""
    project_path = path or os.getcwd()
    tool = PerformanceTool(project_path)
    return await tool.get_report(include_build)

"""
Performance Models - Data structures for performance analysis.

Supports:
- Bundle size analysis
- Build time profiling
- Memory/CPU benchmarks
- Performance regression detection
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class PerformanceMetricType(str, Enum):
    """Types of performance metrics."""
    BUNDLE_SIZE = "bundle_size"
    BUILD_TIME = "build_time"
    RESPONSE_TIME = "response_time"
    MEMORY_USAGE = "memory_usage"
    CPU_USAGE = "cpu_usage"
    STARTUP_TIME = "startup_time"


class TrendDirection(str, Enum):
    """Performance trend direction."""
    IMPROVING = "improving"
    STABLE = "stable"
    DEGRADING = "degrading"


@dataclass
class BundleFile:
    """A single file in the bundle."""

    path: str
    size_bytes: int
    gzip_size_bytes: int = 0

    # Source info
    is_vendor: bool = False
    is_source_mapped: bool = False

    # Tree shaking
    can_tree_shake: bool = True
    unused_exports: int = 0

    @property
    def size_kb(self) -> float:
        return self.size_bytes / 1024

    @property
    def gzip_kb(self) -> float:
        return self.gzip_size_bytes / 1024

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "size_kb": round(self.size_kb, 2),
            "gzip_kb": round(self.gzip_kb, 2),
            "is_vendor": self.is_vendor,
        }


@dataclass
class BundleAnalysis:
    """Bundle size analysis results."""

    analyzed_at: datetime = field(default_factory=_utc_now)

    # Totals
    total_size_bytes: int = 0
    total_gzip_bytes: int = 0

    # Breakdown
    js_size_bytes: int = 0
    css_size_bytes: int = 0
    assets_size_bytes: int = 0

    # Files
    files: list[BundleFile] = field(default_factory=list)
    largest_files: list[BundleFile] = field(default_factory=list)

    # Dependencies contribution
    vendor_size_bytes: int = 0
    app_size_bytes: int = 0

    # Recommendations
    recommendations: list[str] = field(default_factory=list)

    @property
    def total_size_mb(self) -> float:
        return self.total_size_bytes / (1024 * 1024)

    @property
    def vendor_percentage(self) -> float:
        if self.total_size_bytes == 0:
            return 0
        return (self.vendor_size_bytes / self.total_size_bytes) * 100

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_size_mb": round(self.total_size_mb, 2),
            "total_gzip_kb": round(self.total_gzip_bytes / 1024, 2),
            "breakdown": {
                "js_kb": round(self.js_size_bytes / 1024, 2),
                "css_kb": round(self.css_size_bytes / 1024, 2),
                "assets_kb": round(self.assets_size_bytes / 1024, 2),
            },
            "vendor_percentage": round(self.vendor_percentage, 1),
            "file_count": len(self.files),
            "largest_files": [f.to_dict() for f in self.largest_files[:5]],
            "recommendations": self.recommendations[:5],
        }


@dataclass
class BuildTiming:
    """Build time analysis."""

    build_command: str
    total_time_ms: int = 0

    # Phases
    phases: dict[str, int] = field(default_factory=dict)

    # Comparison
    previous_time_ms: int | None = None
    change_percentage: float | None = None

    # Environment
    node_version: str = ""
    cpu_cores: int = 0
    memory_gb: float = 0

    @property
    def total_seconds(self) -> float:
        return self.total_time_ms / 1000

    @property
    def is_regression(self) -> bool:
        if self.change_percentage is None:
            return False
        return self.change_percentage > 10  # 10% slower

    def to_dict(self) -> dict[str, Any]:
        return {
            "command": self.build_command,
            "total_seconds": round(self.total_seconds, 2),
            "phases": {
                k: round(v / 1000, 2)
                for k, v in self.phases.items()
            },
            "change": f"{self.change_percentage:+.1f}%" if self.change_percentage else None,
            "is_regression": self.is_regression,
        }


@dataclass
class PerformanceBenchmark:
    """Performance benchmark results."""

    name: str
    metric_type: PerformanceMetricType

    # Values
    value: float
    unit: str
    baseline: float | None = None

    # Statistics
    min_value: float | None = None
    max_value: float | None = None
    p50: float | None = None
    p95: float | None = None
    p99: float | None = None

    # Comparison
    change_from_baseline: float | None = None
    trend: TrendDirection = TrendDirection.STABLE

    # Thresholds
    warning_threshold: float | None = None
    critical_threshold: float | None = None

    @property
    def exceeds_warning(self) -> bool:
        if self.warning_threshold is None:
            return False
        return self.value > self.warning_threshold

    @property
    def exceeds_critical(self) -> bool:
        if self.critical_threshold is None:
            return False
        return self.value > self.critical_threshold

    def to_dict(self) -> dict[str, Any]:
        result = {
            "name": self.name,
            "type": self.metric_type.value,
            "value": round(self.value, 2),
            "unit": self.unit,
            "trend": self.trend.value,
        }

        if self.baseline:
            result["baseline"] = round(self.baseline, 2)
            if self.change_from_baseline:
                result["change"] = f"{self.change_from_baseline:+.1f}%"

        if self.p95:
            result["p95"] = round(self.p95, 2)

        if self.exceeds_critical:
            result["status"] = "critical"
        elif self.exceeds_warning:
            result["status"] = "warning"
        else:
            result["status"] = "ok"

        return result


@dataclass
class PerformanceReport:
    """Comprehensive performance report."""

    project_name: str
    generated_at: datetime = field(default_factory=_utc_now)

    # Scores (0-100)
    overall_score: int = 100
    bundle_score: int = 100
    build_score: int = 100
    runtime_score: int = 100

    # Components
    bundle_analysis: BundleAnalysis | None = None
    build_timing: BuildTiming | None = None
    benchmarks: list[PerformanceBenchmark] = field(default_factory=list)

    # Issues
    critical_issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    # Recommendations
    recommendations: list[str] = field(default_factory=list)

    @property
    def grade(self) -> str:
        if self.overall_score >= 90:
            return "A"
        elif self.overall_score >= 80:
            return "B"
        elif self.overall_score >= 70:
            return "C"
        elif self.overall_score >= 60:
            return "D"
        else:
            return "F"

    def to_dict(self) -> dict[str, Any]:
        return {
            "project": self.project_name,
            "overall_score": self.overall_score,
            "grade": self.grade,
            "scores": {
                "bundle": self.bundle_score,
                "build": self.build_score,
                "runtime": self.runtime_score,
            },
            "bundle": self.bundle_analysis.to_dict() if self.bundle_analysis else None,
            "build": self.build_timing.to_dict() if self.build_timing else None,
            "benchmarks": [b.to_dict() for b in self.benchmarks],
            "critical_issues": self.critical_issues,
            "warnings": self.warnings[:5],
            "recommendations": self.recommendations[:5],
        }

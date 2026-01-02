"""
Codebase Context Models - Data structures for ambient intelligence.

These models represent the knowledge the system maintains about the codebase:
- FileContext: Everything known about a single file
- ImpactGraph: Dependency relationships and change impact
- LearnedPattern: Patterns extracted from past work
- CodebaseSnapshot: Point-in-time codebase state
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set


def _utc_now() -> datetime:
    """Get current UTC time."""
    return datetime.now(timezone.utc)


class FileType(str, Enum):
    """Detected file type for language-specific handling."""

    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    GO = "go"
    RUST = "rust"
    JAVA = "java"
    CSS = "css"
    HTML = "html"
    JSON = "json"
    YAML = "yaml"
    MARKDOWN = "markdown"
    SQL = "sql"
    SHELL = "shell"
    DOCKERFILE = "dockerfile"
    UNKNOWN = "unknown"


class Severity(str, Enum):
    """Issue severity levels."""

    CRITICAL = "critical"  # Will break production
    HIGH = "high"          # Likely to cause bugs
    MEDIUM = "medium"      # Should be fixed
    LOW = "low"            # Style/preference
    INFO = "info"          # Informational only


class ImpactLevel(str, Enum):
    """How much impact a change to this file would have."""

    CRITICAL = "critical"  # Core infrastructure, many dependents
    HIGH = "high"          # Important file, several dependents
    MEDIUM = "medium"      # Normal file, some dependents
    LOW = "low"            # Leaf file, few/no dependents
    ISOLATED = "isolated"  # No dependencies either direction


@dataclass
class FileMetrics:
    """Quantitative metrics about a file."""

    lines_of_code: int = 0
    lines_of_comments: int = 0
    blank_lines: int = 0
    complexity_score: float = 0.0  # Cyclomatic complexity
    maintainability_index: float = 100.0  # 0-100, higher is better
    test_coverage: Optional[float] = None  # 0-100 if known
    duplicate_ratio: float = 0.0  # 0-1, how much is duplicated

    @property
    def total_lines(self) -> int:
        return self.lines_of_code + self.lines_of_comments + self.blank_lines

    @property
    def comment_ratio(self) -> float:
        if self.lines_of_code == 0:
            return 0.0
        return self.lines_of_comments / self.lines_of_code


@dataclass
class FileHistory:
    """Historical information about a file."""

    created_at: Optional[datetime] = None
    last_modified: Optional[datetime] = None
    modification_count: int = 0  # Total commits touching this file
    recent_authors: List[str] = field(default_factory=list)  # Last N authors
    churn_rate: float = 0.0  # Changes per week (higher = volatile)

    # Issue history
    bugs_fixed: int = 0
    bugs_introduced: int = 0  # Times this file was the source of a bug
    hotspot_score: float = 0.0  # Combined metric: high churn + bugs = hotspot


@dataclass
class PastIssue:
    """A past issue associated with this file."""

    issue_id: str
    issue_type: str  # "bug", "lint", "type_error", "security", etc.
    title: str
    description: str
    severity: Severity
    fixed: bool
    fix_summary: Optional[str] = None
    fixed_at: Optional[datetime] = None
    recurred: bool = False  # Did similar issue come back?


@dataclass
class ImportRelation:
    """An import relationship between files."""

    source_file: str  # File doing the importing
    target_file: str  # File being imported
    import_type: str  # "direct", "from", "dynamic", "type_only"
    symbols: List[str] = field(default_factory=list)  # What symbols are imported
    is_test_import: bool = False  # Is this from a test file


@dataclass
class ImpactGraph:
    """
    Dependency graph and impact analysis for a file.

    Answers: "If I change this file, what else might break?"
    """

    file_path: str

    # Direct relationships
    imports_from: List[str] = field(default_factory=list)  # Files this imports
    imported_by: List[str] = field(default_factory=list)  # Files that import this

    # Detailed import info
    import_details: List[ImportRelation] = field(default_factory=list)

    # Transitive impact
    transitive_dependents: List[str] = field(default_factory=list)  # All files affected by change
    transitive_depth: int = 0  # How deep the dependency tree goes

    # Impact assessment
    impact_level: ImpactLevel = ImpactLevel.MEDIUM
    impact_score: float = 0.0  # 0-100, higher = more impact

    # Critical paths
    is_on_critical_path: bool = False  # Part of core application flow
    critical_path_reason: Optional[str] = None

    # Test coverage
    test_files: List[str] = field(default_factory=list)  # Tests for this file
    tests_to_run: List[str] = field(default_factory=list)  # All tests that might be affected

    @property
    def total_dependents(self) -> int:
        return len(self.imported_by) + len(self.transitive_dependents)

    def get_files_to_review(self, max_files: int = 10) -> List[str]:
        """Get prioritized list of files to review after changing this file."""
        # Direct importers first, then transitive
        files = list(self.imported_by)
        for f in self.transitive_dependents:
            if f not in files:
                files.append(f)
        return files[:max_files]


@dataclass
class LearnedPattern:
    """A pattern learned from past agent work."""

    pattern_id: str
    pattern_type: str  # "common_mistake", "best_practice", "gotcha", "fix_pattern"
    description: str

    # When this applies
    applies_to_files: List[str] = field(default_factory=list)  # Glob patterns
    applies_to_types: List[FileType] = field(default_factory=list)
    trigger_keywords: List[str] = field(default_factory=list)

    # What to do
    recommendation: str = ""
    example_fix: Optional[str] = None

    # Confidence
    occurrence_count: int = 0
    success_rate: float = 0.0  # How often following this worked
    last_seen: Optional[datetime] = None

    # Source
    source_tickets: List[str] = field(default_factory=list)


@dataclass
class FileContext:
    """
    Complete context about a single file.

    This is the main data structure agents receive when asking
    about a file. Contains everything known about it.
    """

    # Identity
    file_path: str
    file_type: FileType = FileType.UNKNOWN
    exists: bool = True

    # Metrics
    metrics: FileMetrics = field(default_factory=FileMetrics)

    # History
    history: FileHistory = field(default_factory=FileHistory)
    past_issues: List[PastIssue] = field(default_factory=list)

    # Relationships
    impact_graph: Optional[ImpactGraph] = None

    # Learned patterns
    applicable_patterns: List[LearnedPattern] = field(default_factory=list)
    common_mistakes: List[str] = field(default_factory=list)

    # Recommendations
    recommendations: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    # Cache metadata
    context_generated_at: datetime = field(default_factory=_utc_now)
    cache_valid_until: Optional[datetime] = None

    def is_cache_valid(self) -> bool:
        """Check if cached context is still valid."""
        if self.cache_valid_until is None:
            return False
        return datetime.now(timezone.utc) < self.cache_valid_until

    def get_risk_level(self) -> str:
        """Calculate overall risk level for modifying this file."""
        risk_score = 0

        # High complexity = risky
        if self.metrics.complexity_score > 20:
            risk_score += 2
        elif self.metrics.complexity_score > 10:
            risk_score += 1

        # Bug hotspot = risky
        if self.history.hotspot_score > 0.7:
            risk_score += 2
        elif self.history.hotspot_score > 0.4:
            risk_score += 1

        # Many dependents = risky
        if self.impact_graph:
            if self.impact_graph.impact_level == ImpactLevel.CRITICAL:
                risk_score += 2
            elif self.impact_graph.impact_level == ImpactLevel.HIGH:
                risk_score += 1

        # Past issues that recurred = risky
        recurring = sum(1 for i in self.past_issues if i.recurred)
        if recurring > 2:
            risk_score += 2
        elif recurring > 0:
            risk_score += 1

        if risk_score >= 5:
            return "critical"
        elif risk_score >= 3:
            return "high"
        elif risk_score >= 1:
            return "medium"
        return "low"

    def to_summary(self) -> Dict[str, Any]:
        """Generate a summary for agent consumption."""
        summary = {
            "file": self.file_path,
            "type": self.file_type.value,
            "risk_level": self.get_risk_level(),
            "metrics": {
                "lines": self.metrics.total_lines,
                "complexity": self.metrics.complexity_score,
                "coverage": self.metrics.test_coverage,
            },
            "history": {
                "last_modified": self.history.last_modified.isoformat() if self.history.last_modified else None,
                "bugs_fixed": self.history.bugs_fixed,
                "hotspot_score": self.history.hotspot_score,
            },
        }

        if self.impact_graph:
            summary["impact"] = {
                "level": self.impact_graph.impact_level.value,
                "dependents": self.impact_graph.total_dependents,
                "tests_to_run": len(self.impact_graph.tests_to_run),
            }

        if self.warnings:
            summary["warnings"] = self.warnings

        if self.recommendations:
            summary["recommendations"] = self.recommendations[:3]  # Top 3

        if self.common_mistakes:
            summary["watch_out_for"] = self.common_mistakes[:3]

        return summary


@dataclass
class CodebaseSnapshot:
    """
    Point-in-time snapshot of codebase state.

    Used for:
    - Comparing changes over time
    - Detecting drift
    - Warm-starting the cache
    """

    snapshot_id: str
    taken_at: datetime = field(default_factory=_utc_now)

    # File inventory
    total_files: int = 0
    files_by_type: Dict[str, int] = field(default_factory=dict)

    # Aggregate metrics
    total_lines: int = 0
    average_complexity: float = 0.0
    average_coverage: Optional[float] = None

    # Hotspots
    hotspot_files: List[str] = field(default_factory=list)  # Top N risky files

    # Graph stats
    most_depended_on: List[str] = field(default_factory=list)  # Core files
    orphan_files: List[str] = field(default_factory=list)  # No imports/exports

    # Git state
    git_branch: Optional[str] = None
    git_commit: Optional[str] = None


@dataclass
class ContextQuery:
    """
    A query for codebase context.

    Allows flexible querying with filters and options.
    """

    # What to get context for
    files: List[str] = field(default_factory=list)
    directories: List[str] = field(default_factory=list)
    file_types: List[FileType] = field(default_factory=list)

    # What to include
    include_metrics: bool = True
    include_history: bool = True
    include_impact: bool = True
    include_patterns: bool = True

    # Depth
    impact_depth: int = 2  # How many levels of transitive deps
    max_files: int = 50  # Limit for directory queries

    # Freshness
    max_cache_age_seconds: int = 300  # 5 minutes default
    force_refresh: bool = False


@dataclass
class ContextResult:
    """
    Result of a context query.
    """

    query: ContextQuery

    # Results
    file_contexts: Dict[str, FileContext] = field(default_factory=dict)

    # Aggregate insights
    cross_file_patterns: List[LearnedPattern] = field(default_factory=list)
    shared_dependencies: List[str] = field(default_factory=list)
    suggested_review_order: List[str] = field(default_factory=list)

    # Metadata
    cache_hits: int = 0
    cache_misses: int = 0
    query_time_ms: int = 0

    def get_all_recommendations(self) -> List[str]:
        """Aggregate recommendations from all files."""
        recs = []
        seen = set()
        for ctx in self.file_contexts.values():
            for rec in ctx.recommendations:
                if rec not in seen:
                    recs.append(rec)
                    seen.add(rec)
        return recs

    def get_all_warnings(self) -> List[str]:
        """Aggregate warnings from all files."""
        warnings = []
        seen = set()
        for ctx in self.file_contexts.values():
            for w in ctx.warnings:
                if w not in seen:
                    warnings.append(w)
                    seen.add(w)
        return warnings

    def get_tests_to_run(self) -> List[str]:
        """Get all tests that should be run based on files queried."""
        tests = set()
        for ctx in self.file_contexts.values():
            if ctx.impact_graph:
                tests.update(ctx.impact_graph.tests_to_run)
        return sorted(tests)

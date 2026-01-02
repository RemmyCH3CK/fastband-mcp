"""
Code Quality Models - Data structures for quality analysis.

Defines standardized representations for:
- Quality issues from any linter
- Analysis reports with context
- Fix suggestions with confidence
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class IssueSeverity(str, Enum):
    """Severity levels for quality issues."""

    ERROR = "error"          # Will break at runtime
    WARNING = "warning"      # Likely to cause problems
    INFO = "info"            # Suggestion/improvement
    HINT = "hint"            # Style preference


class IssueCategory(str, Enum):
    """Categories of quality issues."""

    # Correctness
    SYNTAX = "syntax"           # Syntax errors
    TYPE = "type"               # Type errors
    LOGIC = "logic"             # Logic errors
    RUNTIME = "runtime"         # Runtime issues

    # Security
    SECURITY = "security"       # Security vulnerabilities
    INJECTION = "injection"     # Injection vulnerabilities
    AUTH = "auth"               # Auth/authz issues

    # Quality
    COMPLEXITY = "complexity"   # High complexity
    DUPLICATION = "duplication" # Code duplication
    DEAD_CODE = "dead_code"     # Unused code

    # Style
    FORMATTING = "formatting"   # Formatting issues
    NAMING = "naming"           # Naming conventions
    DOCUMENTATION = "documentation"  # Missing docs

    # Best Practices
    BEST_PRACTICE = "best_practice"  # General best practices
    PERFORMANCE = "performance"      # Performance issues
    MAINTAINABILITY = "maintainability"  # Maintainability


class FixConfidence(str, Enum):
    """Confidence level for suggested fixes."""

    HIGH = "high"        # Safe to auto-apply
    MEDIUM = "medium"    # Review recommended
    LOW = "low"          # Manual review required


@dataclass
class SourceLocation:
    """Location in source code."""

    file: str
    line: int
    column: int = 0
    end_line: int | None = None
    end_column: int | None = None

    def to_string(self) -> str:
        """Format as file:line:column."""
        if self.column:
            return f"{self.file}:{self.line}:{self.column}"
        return f"{self.file}:{self.line}"


@dataclass
class SuggestedFix:
    """A suggested fix for an issue."""

    description: str
    confidence: FixConfidence

    # The actual fix
    replacement_text: str | None = None  # Direct replacement
    diff: str | None = None              # Unified diff

    # Context
    requires_import: str | None = None   # Import to add
    affects_files: list[str] = field(default_factory=list)  # Other files affected

    # Learning
    from_pattern: str | None = None      # Pattern ID if from memory
    past_success_rate: float | None = None  # Historical success


@dataclass
class QualityIssue:
    """
    A single quality issue found during analysis.

    Standardized format that all linters/checkers convert to.
    """

    # Identity
    issue_id: str
    rule_id: str                    # e.g., "E501", "no-unused-vars"

    # Classification
    severity: IssueSeverity
    category: IssueCategory

    # Location
    location: SourceLocation

    # Description
    message: str
    detail: str | None = None    # Extended explanation

    # Source
    source: str = "unknown"         # e.g., "ruff", "eslint", "mypy"
    documentation_url: str | None = None

    # Fix
    suggested_fix: SuggestedFix | None = None
    is_auto_fixable: bool = False

    # Context from CodebaseContext
    file_risk_level: str | None = None   # "low", "medium", "high", "critical"
    impact_level: str | None = None       # How much impact fixing this has
    related_files: list[str] = field(default_factory=list)  # Files that might be affected

    # Learning
    seen_before: bool = False               # Seen this pattern before?
    past_fix_worked: bool | None = None  # Did past fix work?
    similar_issues: list[str] = field(default_factory=list)  # Similar past issue IDs

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "issue_id": self.issue_id,
            "rule_id": self.rule_id,
            "severity": self.severity.value,
            "category": self.category.value,
            "location": self.location.to_string(),
            "message": self.message,
            "source": self.source,
            "is_auto_fixable": self.is_auto_fixable,
            "file_risk_level": self.file_risk_level,
        }


@dataclass
class FileAnalysis:
    """Analysis results for a single file."""

    file_path: str
    issues: list[QualityIssue] = field(default_factory=list)

    # Metrics
    lines_analyzed: int = 0
    analysis_time_ms: int = 0

    # Context (from CodebaseContext)
    complexity_score: float = 0.0
    risk_level: str = "low"
    impact_level: str = "low"

    # Summary
    error_count: int = 0
    warning_count: int = 0
    info_count: int = 0

    # Recommendations from context
    recommendations: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def add_issue(self, issue: QualityIssue) -> None:
        """Add an issue and update counts."""
        self.issues.append(issue)
        if issue.severity == IssueSeverity.ERROR:
            self.error_count += 1
        elif issue.severity == IssueSeverity.WARNING:
            self.warning_count += 1
        else:
            self.info_count += 1

    @property
    def total_issues(self) -> int:
        return len(self.issues)

    @property
    def has_errors(self) -> bool:
        return self.error_count > 0

    def get_issues_by_severity(self, severity: IssueSeverity) -> list[QualityIssue]:
        return [i for i in self.issues if i.severity == severity]

    def get_issues_by_category(self, category: IssueCategory) -> list[QualityIssue]:
        return [i for i in self.issues if i.category == category]

    def get_auto_fixable(self) -> list[QualityIssue]:
        return [i for i in self.issues if i.is_auto_fixable]


@dataclass
class QualityReport:
    """
    Complete quality analysis report.

    Aggregates results from all analyzers across all files,
    enriched with context and learning.
    """

    # Identity
    report_id: str
    created_at: datetime = field(default_factory=_utc_now)

    # Scope
    project_root: str = ""
    files_analyzed: list[str] = field(default_factory=list)

    # Results
    file_analyses: dict[str, FileAnalysis] = field(default_factory=dict)

    # Aggregate counts
    total_issues: int = 0
    total_errors: int = 0
    total_warnings: int = 0
    total_info: int = 0

    # Auto-fix summary
    auto_fixable_count: int = 0
    fixes_applied: int = 0

    # Performance
    analysis_time_ms: int = 0

    # Context insights
    high_risk_files: list[str] = field(default_factory=list)
    hotspot_files: list[str] = field(default_factory=list)
    files_needing_tests: list[str] = field(default_factory=list)

    # Impact analysis
    affected_files: list[str] = field(default_factory=list)  # Files affected by issues
    tests_to_run: list[str] = field(default_factory=list)    # Tests that should run

    # Learning
    known_patterns_found: int = 0
    new_patterns_detected: int = 0

    # Recommendations (aggregated)
    top_recommendations: list[str] = field(default_factory=list)
    critical_warnings: list[str] = field(default_factory=list)

    def add_file_analysis(self, analysis: FileAnalysis) -> None:
        """Add file analysis and update aggregates."""
        self.file_analyses[analysis.file_path] = analysis
        self.files_analyzed.append(analysis.file_path)

        # Update counts
        self.total_issues += analysis.total_issues
        self.total_errors += analysis.error_count
        self.total_warnings += analysis.warning_count
        self.total_info += analysis.info_count
        self.auto_fixable_count += len(analysis.get_auto_fixable())

        # Track high-risk files
        if analysis.risk_level in ["high", "critical"]:
            self.high_risk_files.append(analysis.file_path)

    def get_all_issues(self) -> list[QualityIssue]:
        """Get all issues across all files."""
        issues = []
        for analysis in self.file_analyses.values():
            issues.extend(analysis.issues)
        return issues

    def get_issues_by_severity(self, severity: IssueSeverity) -> list[QualityIssue]:
        """Get all issues of a specific severity."""
        return [i for i in self.get_all_issues() if i.severity == severity]

    def get_prioritized_issues(self, limit: int = 10) -> list[QualityIssue]:
        """Get issues prioritized by severity and impact."""
        issues = self.get_all_issues()

        def priority_score(issue: QualityIssue) -> int:
            score = 0
            # Severity
            if issue.severity == IssueSeverity.ERROR:
                score += 1000
            elif issue.severity == IssueSeverity.WARNING:
                score += 100
            # Risk level
            if issue.file_risk_level == "critical":
                score += 500
            elif issue.file_risk_level == "high":
                score += 200
            # Category
            if issue.category in [IssueCategory.SECURITY, IssueCategory.INJECTION]:
                score += 800
            elif issue.category in [IssueCategory.TYPE, IssueCategory.RUNTIME]:
                score += 300
            return score

        issues.sort(key=priority_score, reverse=True)
        return issues[:limit]

    def to_summary(self) -> dict[str, Any]:
        """Generate a summary for agent consumption."""
        return {
            "report_id": self.report_id,
            "files_analyzed": len(self.files_analyzed),
            "total_issues": self.total_issues,
            "errors": self.total_errors,
            "warnings": self.total_warnings,
            "info": self.total_info,
            "auto_fixable": self.auto_fixable_count,
            "high_risk_files": len(self.high_risk_files),
            "tests_to_run": len(self.tests_to_run),
            "analysis_time_ms": self.analysis_time_ms,
            "top_issues": [i.to_dict() for i in self.get_prioritized_issues(5)],
            "recommendations": self.top_recommendations[:3],
            "critical_warnings": self.critical_warnings[:3],
        }

    def to_markdown(self) -> str:
        """Generate markdown report."""
        lines = [
            "# Code Quality Report",
            "",
            f"**Report ID:** {self.report_id}",
            f"**Generated:** {self.created_at.strftime('%Y-%m-%d %H:%M:%S')} UTC",
            f"**Files Analyzed:** {len(self.files_analyzed)}",
            f"**Analysis Time:** {self.analysis_time_ms}ms",
            "",
            "## Summary",
            "",
            "| Metric | Count |",
            "|--------|-------|",
            f"| Total Issues | {self.total_issues} |",
            f"| Errors | {self.total_errors} |",
            f"| Warnings | {self.total_warnings} |",
            f"| Info | {self.total_info} |",
            f"| Auto-fixable | {self.auto_fixable_count} |",
            "",
        ]

        if self.total_errors > 0:
            lines.extend([
                f"## ❌ Errors ({self.total_errors})",
                "",
            ])
            for issue in self.get_issues_by_severity(IssueSeverity.ERROR)[:10]:
                lines.append(f"- **{issue.location.to_string()}**: {issue.message}")
            lines.append("")

        if self.total_warnings > 0:
            lines.extend([
                f"## ⚠️ Warnings ({self.total_warnings})",
                "",
            ])
            for issue in self.get_issues_by_severity(IssueSeverity.WARNING)[:10]:
                lines.append(f"- **{issue.location.to_string()}**: {issue.message}")
            lines.append("")

        if self.critical_warnings:
            lines.extend([
                "## 🚨 Critical Warnings",
                "",
            ])
            for warning in self.critical_warnings:
                lines.append(f"- {warning}")
            lines.append("")

        if self.top_recommendations:
            lines.extend([
                "## 💡 Recommendations",
                "",
            ])
            for rec in self.top_recommendations:
                lines.append(f"- {rec}")
            lines.append("")

        if self.tests_to_run:
            lines.extend([
                "## 🧪 Tests to Run",
                "",
            ])
            for test in self.tests_to_run[:10]:
                lines.append(f"- `{test}`")
            lines.append("")

        return "\n".join(lines)

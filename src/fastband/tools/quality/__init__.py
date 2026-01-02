"""
Code Quality Tools - Intelligent linting with ambient context.

Provides MCP tools for comprehensive code quality analysis:
- Multi-linter support (ruff, mypy, eslint, golangci-lint)
- CodebaseContext integration for impact analysis
- Learning from past fixes via memory system
- Smart prioritization of issues

Usage:
    # Quick check on a file
    result = await code_quality_check_file("src/api/routes.py")
    print(result["status"])  # "pass" or "fail"

    # Full analysis with recommendations
    result = await code_quality_analyze(
        path="src/",
        mode="directory",
        severity="warning",
    )
    print(result["markdown"])

    # Apply auto-fixes (dry run first)
    result = await code_quality_fix("src/", dry_run=True)
    if result["would_fix"] > 0:
        result = await code_quality_fix("src/", dry_run=False)
"""

from fastband.tools.quality.models import (
    FileAnalysis,
    FixConfidence,
    IssueCategory,
    IssueSeverity,
    QualityIssue,
    QualityReport,
    SourceLocation,
    SuggestedFix,
)
from fastband.tools.quality.runners import (
    ESLintRunner,
    GolangCILintRunner,
    LinterOrchestrator,
    LinterResult,
    LinterRunner,
    MypyRunner,
    RuffRunner,
)
from fastband.tools.quality.tool import (
    AnalysisConfig,
    CodeQualityTool,
    code_quality_analyze,
    code_quality_check_file,
    code_quality_fix,
)

__all__ = [
    # Main tool
    "CodeQualityTool",
    "AnalysisConfig",
    # MCP functions
    "code_quality_analyze",
    "code_quality_fix",
    "code_quality_check_file",
    # Models
    "QualityIssue",
    "FileAnalysis",
    "QualityReport",
    "IssueSeverity",
    "IssueCategory",
    "FixConfidence",
    "SourceLocation",
    "SuggestedFix",
    # Runners
    "LinterRunner",
    "LinterResult",
    "LinterOrchestrator",
    "RuffRunner",
    "MypyRunner",
    "ESLintRunner",
    "GolangCILintRunner",
]


# =========================================================================
# MCP TOOL REGISTRATION
# =========================================================================

def register_tools(mcp_server):
    """Register code quality tools with the MCP server."""

    @mcp_server.tool()
    async def code_quality(
        path: str,
        mode: str = "file",
        severity: str = "info",
        linters: str = "",
        include_impact: bool = True,
    ) -> dict:
        """
        Analyze code quality with intelligent context awareness.

        Runs language-appropriate linters and provides prioritized issues
        with CodebaseContext enrichment for understanding impact.

        Args:
            path: File or directory path to analyze
            mode: Analysis mode:
                - "file": Single file analysis
                - "directory": Full directory scan
                - "changes": Only git-changed files
            severity: Minimum severity to report:
                - "error": Only errors
                - "warning": Warnings and errors
                - "info": All except hints
                - "hint": Everything including style hints
            linters: Comma-separated linter names (empty = all available)
                Available: ruff, mypy, eslint, golangci-lint
            include_impact: Include impact analysis (affected files, tests to run)

        Returns:
            Quality report with:
            - issues: List of quality issues found
            - summary: Counts by severity
            - recommendations: AI-generated improvement suggestions
            - affected_files: Files that may be impacted
            - tests_to_run: Tests that should be run

        Example:
            # Check a single file
            {"path": "src/api/auth.py", "mode": "file"}

            # Scan entire source directory
            {"path": "src/", "mode": "directory", "severity": "warning"}

            # Check only changed files before commit
            {"path": ".", "mode": "changes"}
        """
        linter_list = [l.strip() for l in linters.split(",") if l.strip()] or None
        return await code_quality_analyze(
            path=path,
            mode=mode,
            severity=severity,
            linters=linter_list,
            include_impact=include_impact,
        )

    @mcp_server.tool()
    async def code_quality_autofix(
        path: str,
        dry_run: bool = True,
    ) -> dict:
        """
        Apply automatic fixes for code quality issues.

        Uses linter auto-fix capabilities to resolve issues safely.
        Always run with dry_run=True first to preview changes.

        Args:
            path: File or directory to fix
            dry_run: If True, only show what would be fixed (default: True)

        Returns:
            Fix summary:
            - dry_run: Whether this was a preview
            - would_fix/fixed: Number of issues fixed
            - issues: Details of fixes (in dry run)
            - errors: Any errors encountered

        Example:
            # Preview fixes
            {"path": "src/", "dry_run": true}

            # Apply fixes
            {"path": "src/", "dry_run": false}
        """
        return await code_quality_fix(path=path, dry_run=dry_run)

    @mcp_server.tool()
    async def code_quality_quick_check(file_path: str) -> dict:
        """
        Quick quality check for a single file.

        Ideal for pre-commit validation or quick sanity checks.
        Returns pass/fail status with key issues.

        Args:
            file_path: Path to file to check

        Returns:
            Quick summary:
            - passed: Boolean pass/fail
            - status: "pass" or "fail"
            - errors: Count of errors
            - warnings: Count of warnings
            - top_issues: Most important issues

        Example:
            {"file_path": "src/api/routes.py"}
        """
        return await code_quality_check_file(file_path)

    return [
        "code_quality",
        "code_quality_autofix",
        "code_quality_quick_check",
    ]

"""
Code Quality Tool - Intelligent code analysis with ambient context.

Provides comprehensive code quality analysis with:
- Multi-linter support (ruff, mypy, eslint, golangci-lint)
- CodebaseContext integration for impact analysis
- Learning from past fixes via memory system
- Smart prioritization of issues
"""

import asyncio
import logging
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastband.context import (
    CodebaseContext,
    FileContext,
    ImpactLevel,
    get_codebase_context,
)
from fastband.tools.quality.models import (
    FileAnalysis,
    FixConfidence,
    IssueCategory,
    IssueSeverity,
    QualityIssue,
    QualityReport,
)
from fastband.tools.quality.runners import (
    LinterOrchestrator,
    LinterResult,
)

logger = logging.getLogger(__name__)


@dataclass
class AnalysisConfig:
    """Configuration for code quality analysis."""

    # Linters to use
    linters: list[str] | None = None  # None = all available
    run_type_checker: bool = True  # Include mypy for Python

    # Scope
    include_patterns: list[str] = field(default_factory=lambda: ["*.py", "*.js", "*.ts", "*.tsx", "*.go"])
    exclude_patterns: list[str] = field(default_factory=lambda: [
        "**/node_modules/**",
        "**/.venv/**",
        "**/venv/**",
        "**/__pycache__/**",
        "**/dist/**",
        "**/build/**",
        "**/.git/**",
        "**/migrations/**",
    ])

    # Severity filtering
    min_severity: IssueSeverity = IssueSeverity.INFO
    include_hints: bool = False

    # Context integration
    use_context: bool = True  # Use CodebaseContext for enrichment
    prioritize_by_risk: bool = True  # Prioritize issues in risky files
    include_impact_analysis: bool = True  # Include affected file analysis

    # Learning
    check_past_fixes: bool = True  # Check memory for past fixes
    learn_from_session: bool = True  # Learn patterns from this session

    # Output
    max_issues_per_file: int = 50
    max_total_issues: int = 200


class CodeQualityTool:
    """
    Intelligent code quality analysis tool.

    Integrates multiple linters with CodebaseContext for comprehensive,
    context-aware code quality analysis.
    """

    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.orchestrator = LinterOrchestrator(str(self.project_root))
        self._context: CodebaseContext | None = None

    async def get_context(self) -> CodebaseContext:
        """Get or create CodebaseContext."""
        if self._context is None:
            self._context = await get_codebase_context(str(self.project_root))
        return self._context

    # =========================================================================
    # MAIN ANALYSIS METHODS
    # =========================================================================

    async def analyze_file(
        self,
        file_path: str,
        config: AnalysisConfig | None = None,
    ) -> FileAnalysis:
        """
        Analyze a single file for code quality issues.

        Args:
            file_path: Path to file (relative or absolute)
            config: Analysis configuration

        Returns:
            FileAnalysis with all issues found
        """
        config = config or AnalysisConfig()

        # Normalize path
        if os.path.isabs(file_path):
            rel_path = os.path.relpath(file_path, self.project_root)
        else:
            rel_path = file_path

        # Run linters
        results = await self.orchestrator.analyze_files([rel_path], config.linters)

        # Build file analysis
        analysis = self.orchestrator.build_file_analysis(rel_path, results)

        # Enrich with context
        if config.use_context:
            await self._enrich_with_context(analysis, config)

        # Filter by severity
        self._filter_by_severity(analysis, config)

        # Check past fixes
        if config.check_past_fixes:
            await self._check_past_fixes(analysis)

        return analysis

    async def analyze_files(
        self,
        file_paths: list[str],
        config: AnalysisConfig | None = None,
    ) -> QualityReport:
        """
        Analyze multiple files for code quality issues.

        Args:
            file_paths: Paths to files
            config: Analysis configuration

        Returns:
            QualityReport with all issues
        """
        config = config or AnalysisConfig()
        report = QualityReport(
            report_id=str(uuid.uuid4())[:8],
            project_root=str(self.project_root),
        )

        import time
        start_time = time.time()

        # Normalize paths
        rel_paths = []
        for fp in file_paths:
            if os.path.isabs(fp):
                rel_paths.append(os.path.relpath(fp, self.project_root))
            else:
                rel_paths.append(fp)

        # Run linters on all files
        results = await self.orchestrator.analyze_files(rel_paths, config.linters)

        # Build analysis for each file
        for rel_path in rel_paths:
            analysis = self.orchestrator.build_file_analysis(rel_path, results)

            if config.use_context:
                await self._enrich_with_context(analysis, config)

            self._filter_by_severity(analysis, config)

            if config.check_past_fixes:
                await self._check_past_fixes(analysis)

            report.add_file_analysis(analysis)

        # Calculate impact
        if config.include_impact_analysis:
            await self._calculate_impact(report)

        # Add recommendations
        self._generate_recommendations(report, config)

        report.analysis_time_ms = int((time.time() - start_time) * 1000)

        return report

    async def analyze_directory(
        self,
        directory: str = ".",
        config: AnalysisConfig | None = None,
    ) -> QualityReport:
        """
        Analyze all files in a directory.

        Args:
            directory: Directory to analyze
            config: Analysis configuration

        Returns:
            QualityReport with all issues
        """
        config = config or AnalysisConfig()
        report = QualityReport(
            report_id=str(uuid.uuid4())[:8],
            project_root=str(self.project_root),
        )

        import time
        start_time = time.time()

        # Run linters on directory
        results = await self.orchestrator.analyze_directory(
            directory,
            config.include_patterns,
            config.exclude_patterns,
        )

        # Collect all files from results
        files_with_issues: dict[str, FileAnalysis] = {}

        for linter_name, result in results.items():
            for issue in result.issues:
                file_path = issue.location.file
                if file_path not in files_with_issues:
                    files_with_issues[file_path] = FileAnalysis(file_path=file_path)
                files_with_issues[file_path].add_issue(issue)
                files_with_issues[file_path].analysis_time_ms += result.execution_time_ms

        # Enrich each file
        for file_path, analysis in files_with_issues.items():
            if config.use_context:
                await self._enrich_with_context(analysis, config)

            self._filter_by_severity(analysis, config)

            if config.check_past_fixes:
                await self._check_past_fixes(analysis)

            report.add_file_analysis(analysis)

        # Calculate impact
        if config.include_impact_analysis:
            await self._calculate_impact(report)

        # Generate recommendations
        self._generate_recommendations(report, config)

        report.analysis_time_ms = int((time.time() - start_time) * 1000)

        return report

    async def analyze_changes(
        self,
        base_ref: str = "HEAD~1",
        config: AnalysisConfig | None = None,
    ) -> QualityReport:
        """
        Analyze only changed files (git diff).

        Args:
            base_ref: Git ref to compare against
            config: Analysis configuration

        Returns:
            QualityReport for changed files only
        """
        import subprocess

        # Get changed files
        try:
            result = subprocess.run(
                ["git", "diff", "--name-only", base_ref],
                capture_output=True,
                text=True,
                cwd=str(self.project_root),
            )
            if result.returncode != 0:
                logger.warning(f"git diff failed: {result.stderr}")
                return QualityReport(report_id="error")

            changed_files = [
                f.strip() for f in result.stdout.split("\n")
                if f.strip() and os.path.exists(self.project_root / f)
            ]

        except Exception as e:
            logger.error(f"Failed to get changed files: {e}")
            return QualityReport(report_id="error")

        if not changed_files:
            return QualityReport(
                report_id=str(uuid.uuid4())[:8],
                project_root=str(self.project_root),
            )

        return await self.analyze_files(changed_files, config)

    # =========================================================================
    # CONTEXT ENRICHMENT
    # =========================================================================

    async def _enrich_with_context(
        self,
        analysis: FileAnalysis,
        config: AnalysisConfig,
    ) -> None:
        """Enrich file analysis with CodebaseContext information."""
        try:
            context = await self.get_context()
            file_ctx = await context.get_file_context(analysis.file_path)

            if file_ctx:
                # Set file-level context
                analysis.risk_level = file_ctx.risk_level
                analysis.complexity_score = file_ctx.metrics.complexity if file_ctx.metrics else 0.0

                # Add impact level
                if file_ctx.impact_graph:
                    analysis.impact_level = file_ctx.impact_graph.impact_level.value

                # Add recommendations from context
                if file_ctx.recommendations:
                    analysis.recommendations.extend(file_ctx.recommendations)

                if file_ctx.warnings:
                    analysis.warnings.extend(file_ctx.warnings)

                # Enrich each issue with context
                for issue in analysis.issues:
                    issue.file_risk_level = file_ctx.risk_level
                    if file_ctx.impact_graph:
                        issue.impact_level = file_ctx.impact_graph.impact_level.value
                        issue.related_files = list(file_ctx.impact_graph.imported_by)[:5]

        except Exception as e:
            logger.debug(f"Failed to enrich with context: {e}")

    async def _check_past_fixes(self, analysis: FileAnalysis) -> None:
        """Check memory for past fixes to similar issues."""
        try:
            context = await self.get_context()
            file_ctx = await context.get_file_context(analysis.file_path)

            if file_ctx and file_ctx.learned_patterns:
                for issue in analysis.issues:
                    # Check if we've seen this rule before
                    for pattern in file_ctx.learned_patterns:
                        if pattern.pattern_id.startswith(issue.rule_id):
                            issue.seen_before = True
                            issue.past_fix_worked = pattern.success_rate > 0.7
                            break

        except Exception as e:
            logger.debug(f"Failed to check past fixes: {e}")

    async def _calculate_impact(self, report: QualityReport) -> None:
        """Calculate which files and tests are affected by issues."""
        try:
            context = await self.get_context()

            affected_files = set()
            tests_to_run = set()

            for file_path in report.files_analyzed:
                file_ctx = await context.get_file_context(file_path)
                if file_ctx and file_ctx.impact_graph:
                    affected_files.update(file_ctx.impact_graph.imported_by)
                    tests_to_run.update(file_ctx.impact_graph.tests_to_run)

            report.affected_files = list(affected_files)[:20]
            report.tests_to_run = list(tests_to_run)[:20]

        except Exception as e:
            logger.debug(f"Failed to calculate impact: {e}")

    # =========================================================================
    # FILTERING & RECOMMENDATIONS
    # =========================================================================

    def _filter_by_severity(
        self,
        analysis: FileAnalysis,
        config: AnalysisConfig,
    ) -> None:
        """Filter issues by severity threshold."""
        severity_order = [
            IssueSeverity.HINT,
            IssueSeverity.INFO,
            IssueSeverity.WARNING,
            IssueSeverity.ERROR,
        ]

        min_index = severity_order.index(config.min_severity)
        if not config.include_hints and config.min_severity == IssueSeverity.HINT:
            min_index = 1  # Skip HINT

        # Filter issues
        filtered = [
            issue for issue in analysis.issues
            if severity_order.index(issue.severity) >= min_index
        ]

        # Apply limits
        if len(filtered) > config.max_issues_per_file:
            # Keep highest severity issues
            filtered.sort(
                key=lambda i: severity_order.index(i.severity),
                reverse=True,
            )
            filtered = filtered[:config.max_issues_per_file]

        # Update analysis
        analysis.issues = filtered
        # Recount
        analysis.error_count = sum(1 for i in filtered if i.severity == IssueSeverity.ERROR)
        analysis.warning_count = sum(1 for i in filtered if i.severity == IssueSeverity.WARNING)
        analysis.info_count = sum(1 for i in filtered if i.severity in (IssueSeverity.INFO, IssueSeverity.HINT))

    def _generate_recommendations(
        self,
        report: QualityReport,
        config: AnalysisConfig,
    ) -> None:
        """Generate prioritized recommendations for the report."""
        recommendations = []
        warnings = []

        # Security issues are critical
        security_issues = [
            i for i in report.get_all_issues()
            if i.category in (IssueCategory.SECURITY, IssueCategory.INJECTION, IssueCategory.AUTH)
        ]
        if security_issues:
            warnings.append(
                f"Found {len(security_issues)} security issues that should be addressed immediately"
            )

        # Type errors are important
        type_errors = [
            i for i in report.get_all_issues()
            if i.category == IssueCategory.TYPE and i.severity == IssueSeverity.ERROR
        ]
        if type_errors:
            recommendations.append(
                f"Fix {len(type_errors)} type errors to prevent runtime issues"
            )

        # Auto-fixable issues
        if report.auto_fixable_count > 5:
            recommendations.append(
                f"Run auto-fix to resolve {report.auto_fixable_count} issues automatically"
            )

        # High-risk files with issues
        risky_files_with_issues = [
            fp for fp in report.high_risk_files
            if fp in report.file_analyses and report.file_analyses[fp].has_errors
        ]
        if risky_files_with_issues:
            warnings.append(
                f"{len(risky_files_with_issues)} high-risk files have errors - prioritize these"
            )

        # Files needing tests
        files_without_tests = []
        for fp, analysis in report.file_analyses.items():
            if analysis.has_errors and not any("test" in t.lower() for t in getattr(analysis, "tests_to_run", [])):
                files_without_tests.append(fp)

        if files_without_tests:
            recommendations.append(
                f"Add tests for {len(files_without_tests)} files with errors"
            )

        # Complexity issues
        complex_issues = [
            i for i in report.get_all_issues()
            if i.category == IssueCategory.COMPLEXITY
        ]
        if complex_issues:
            recommendations.append(
                f"Consider refactoring {len(complex_issues)} complex code sections"
            )

        report.top_recommendations = recommendations[:5]
        report.critical_warnings = warnings[:3]

    # =========================================================================
    # FIX OPERATIONS
    # =========================================================================

    async def apply_auto_fixes(
        self,
        report: QualityReport,
        dry_run: bool = True,
    ) -> dict[str, Any]:
        """
        Apply auto-fixes for issues.

        Args:
            report: QualityReport with issues
            dry_run: If True, only show what would be fixed

        Returns:
            Summary of fixes applied
        """
        fixable_issues = [i for i in report.get_all_issues() if i.is_auto_fixable]

        if dry_run:
            return {
                "dry_run": True,
                "would_fix": len(fixable_issues),
                "issues": [
                    {
                        "file": i.location.file,
                        "line": i.location.line,
                        "rule": i.rule_id,
                        "message": i.message,
                    }
                    for i in fixable_issues[:20]
                ],
            }

        # Group by source linter
        by_source: dict[str, list[str]] = {}
        for issue in fixable_issues:
            if issue.source not in by_source:
                by_source[issue.source] = []
            if issue.location.file not in by_source[issue.source]:
                by_source[issue.source].append(issue.location.file)

        fixed_count = 0
        errors = []

        # Apply fixes by linter
        for source, files in by_source.items():
            try:
                if source == "ruff":
                    result = await self._apply_ruff_fixes(files)
                    fixed_count += result.get("fixed", 0)
                elif source == "eslint":
                    result = await self._apply_eslint_fixes(files)
                    fixed_count += result.get("fixed", 0)
            except Exception as e:
                errors.append(f"{source}: {str(e)}")

        return {
            "dry_run": False,
            "fixed": fixed_count,
            "errors": errors,
        }

    async def _apply_ruff_fixes(self, files: list[str]) -> dict[str, Any]:
        """Apply ruff auto-fixes."""
        import subprocess

        cmd = ["ruff", "check", "--fix", *files]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(self.project_root),
        )

        # Count fixed issues (ruff outputs "[*] X fixable with --fix")
        import re
        match = re.search(r"\[.\]\s*(\d+)\s+fixable", result.stdout)
        fixed = int(match.group(1)) if match else 0

        return {"fixed": fixed}

    async def _apply_eslint_fixes(self, files: list[str]) -> dict[str, Any]:
        """Apply eslint auto-fixes."""
        import subprocess

        eslint_path = str(self.project_root / "node_modules" / ".bin" / "eslint")
        if not os.path.exists(eslint_path):
            eslint_path = "eslint"

        cmd = [eslint_path, "--fix", *files]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(self.project_root),
        )

        # ESLint doesn't report fix count easily
        return {"fixed": len(files)}

    # =========================================================================
    # UTILITY METHODS
    # =========================================================================

    def get_available_linters(self) -> list[str]:
        """Get list of available linters."""
        return self.orchestrator.get_available_linters()

    async def get_file_summary(self, file_path: str) -> dict[str, Any]:
        """Get a quick summary of issues in a file."""
        analysis = await self.analyze_file(file_path)
        return {
            "file": file_path,
            "total_issues": analysis.total_issues,
            "errors": analysis.error_count,
            "warnings": analysis.warning_count,
            "auto_fixable": len(analysis.get_auto_fixable()),
            "risk_level": analysis.risk_level,
            "top_issues": [
                {"line": i.location.line, "rule": i.rule_id, "message": i.message}
                for i in analysis.issues[:5]
            ],
        }


# =========================================================================
# MCP TOOL DEFINITIONS
# =========================================================================

async def code_quality_analyze(
    path: str,
    mode: str = "file",
    severity: str = "info",
    linters: list[str] | None = None,
    include_impact: bool = True,
) -> dict[str, Any]:
    """
    Analyze code quality with intelligent context.

    Args:
        path: File or directory path to analyze
        mode: "file", "directory", or "changes"
        severity: Minimum severity ("error", "warning", "info", "hint")
        linters: Specific linters to run (default: all available)
        include_impact: Include impact analysis

    Returns:
        Quality report with issues and recommendations
    """
    # Determine project root
    if os.path.isabs(path):
        project_root = os.path.dirname(path)
    else:
        project_root = os.getcwd()

    tool = CodeQualityTool(project_root)

    # Build config
    config = AnalysisConfig(
        linters=linters,
        min_severity=IssueSeverity(severity.lower()),
        include_impact_analysis=include_impact,
    )

    # Run analysis
    if mode == "file":
        analysis = await tool.analyze_file(path, config)
        return {
            "type": "file_analysis",
            "file": path,
            "issues": [i.to_dict() for i in analysis.issues],
            "summary": {
                "total": analysis.total_issues,
                "errors": analysis.error_count,
                "warnings": analysis.warning_count,
                "auto_fixable": len(analysis.get_auto_fixable()),
            },
            "risk_level": analysis.risk_level,
            "recommendations": analysis.recommendations,
        }

    elif mode == "directory":
        report = await tool.analyze_directory(path, config)
        return {
            "type": "directory_analysis",
            **report.to_summary(),
            "markdown": report.to_markdown(),
        }

    elif mode == "changes":
        report = await tool.analyze_changes(config=config)
        return {
            "type": "changes_analysis",
            **report.to_summary(),
            "markdown": report.to_markdown(),
        }

    else:
        return {"error": f"Unknown mode: {mode}"}


async def code_quality_fix(
    path: str,
    dry_run: bool = True,
) -> dict[str, Any]:
    """
    Apply auto-fixes for code quality issues.

    Args:
        path: File or directory to fix
        dry_run: If True, only show what would be fixed

    Returns:
        Summary of fixes applied or to be applied
    """
    project_root = os.path.dirname(path) if os.path.isabs(path) else os.getcwd()
    tool = CodeQualityTool(project_root)

    # First analyze
    if os.path.isfile(path):
        analysis = await tool.analyze_file(path)
        report = QualityReport(report_id="fix")
        report.add_file_analysis(analysis)
    else:
        report = await tool.analyze_directory(path)

    # Apply fixes
    return await tool.apply_auto_fixes(report, dry_run=dry_run)


async def code_quality_check_file(file_path: str) -> dict[str, Any]:
    """
    Quick quality check for a single file.

    Ideal for pre-commit hooks or quick validation.

    Args:
        file_path: Path to file

    Returns:
        Quick summary with pass/fail status
    """
    project_root = os.path.dirname(file_path) if os.path.isabs(file_path) else os.getcwd()
    tool = CodeQualityTool(project_root)

    summary = await tool.get_file_summary(file_path)

    # Determine pass/fail
    passed = summary["errors"] == 0

    return {
        "passed": passed,
        "status": "pass" if passed else "fail",
        **summary,
    }

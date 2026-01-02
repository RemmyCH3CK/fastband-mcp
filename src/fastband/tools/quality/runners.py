"""
Linter Runners - Language-specific code quality analyzers.

Provides unified interface to run linters and convert their output
to standardized QualityIssue format.

Supported linters:
- Python: ruff (fast, comprehensive)
- JavaScript/TypeScript: eslint
- Go: golangci-lint
- Generic: custom regex patterns

Each runner integrates with CodebaseContext for impact analysis.
"""

import asyncio
import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastband.tools.quality.models import (
    FileAnalysis,
    FixConfidence,
    IssueCategory,
    IssueSeverity,
    QualityIssue,
    SourceLocation,
    SuggestedFix,
)

logger = logging.getLogger(__name__)


@dataclass
class LinterResult:
    """Raw result from a linter execution."""

    success: bool
    issues: list[QualityIssue]
    raw_output: str
    error_message: str | None = None
    execution_time_ms: int = 0


class LinterRunner(ABC):
    """Abstract base class for linter runners."""

    name: str = "base"
    file_extensions: list[str] = []

    def __init__(self, project_root: str):
        self.project_root = Path(project_root)

    @abstractmethod
    async def run(self, files: list[str]) -> LinterResult:
        """Run linter on specified files."""
        pass

    @abstractmethod
    def parse_output(self, output: str) -> list[QualityIssue]:
        """Parse linter output into QualityIssue objects."""
        pass

    def is_available(self) -> bool:
        """Check if linter is installed and available."""
        return False

    def supports_file(self, file_path: str) -> bool:
        """Check if this runner supports the given file type."""
        return any(file_path.endswith(ext) for ext in self.file_extensions)

    async def _run_command(
        self,
        cmd: list[str],
        cwd: str | None = None,
        timeout: int = 120,
    ) -> tuple[int, str, str]:
        """Run a command and return exit code, stdout, stderr."""
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd or str(self.project_root),
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=timeout,
            )
            return (
                proc.returncode or 0,
                stdout.decode("utf-8", errors="replace"),
                stderr.decode("utf-8", errors="replace"),
            )
        except asyncio.TimeoutError:
            logger.warning(f"{self.name} timed out after {timeout}s")
            return -1, "", f"Timeout after {timeout}s"
        except Exception as e:
            logger.error(f"Error running {self.name}: {e}")
            return -1, "", str(e)


class RuffRunner(LinterRunner):
    """
    Ruff linter for Python files.

    Ruff is an extremely fast Python linter written in Rust.
    It covers rules from flake8, pyflakes, pycodestyle, isort, and more.
    """

    name = "ruff"
    file_extensions = [".py"]

    # Mapping of ruff codes to our categories
    CATEGORY_MAP = {
        "E": IssueCategory.SYNTAX,  # pycodestyle errors
        "W": IssueCategory.FORMATTING,  # pycodestyle warnings
        "F": IssueCategory.LOGIC,  # Pyflakes
        "C": IssueCategory.COMPLEXITY,  # McCabe complexity
        "I": IssueCategory.FORMATTING,  # isort
        "N": IssueCategory.NAMING,  # pep8-naming
        "D": IssueCategory.DOCUMENTATION,  # pydocstyle
        "UP": IssueCategory.BEST_PRACTICE,  # pyupgrade
        "B": IssueCategory.LOGIC,  # flake8-bugbear
        "A": IssueCategory.NAMING,  # flake8-builtins
        "S": IssueCategory.SECURITY,  # flake8-bandit
        "T": IssueCategory.DEAD_CODE,  # flake8-print
        "SIM": IssueCategory.BEST_PRACTICE,  # flake8-simplify
        "ARG": IssueCategory.DEAD_CODE,  # flake8-unused-arguments
        "PTH": IssueCategory.BEST_PRACTICE,  # flake8-use-pathlib
        "ERA": IssueCategory.DEAD_CODE,  # eradicate (commented code)
        "PL": IssueCategory.LOGIC,  # Pylint
        "RUF": IssueCategory.BEST_PRACTICE,  # Ruff-specific
    }

    SEVERITY_MAP = {
        "E": IssueSeverity.ERROR,
        "F": IssueSeverity.ERROR,
        "W": IssueSeverity.WARNING,
        "C": IssueSeverity.INFO,
        "S": IssueSeverity.WARNING,  # Security issues are warnings
    }

    def is_available(self) -> bool:
        """Check if ruff is installed."""
        return shutil.which("ruff") is not None

    async def run(self, files: list[str]) -> LinterResult:
        """Run ruff on specified files."""
        import time

        start_time = time.time()

        if not self.is_available():
            return LinterResult(
                success=False,
                issues=[],
                raw_output="",
                error_message="ruff not installed. Install with: pip install ruff",
            )

        if not files:
            return LinterResult(success=True, issues=[], raw_output="")

        # Build ruff command with JSON output
        cmd = [
            "ruff",
            "check",
            "--output-format=json",
            "--no-fix",  # Don't auto-fix, just report
            *files,
        ]

        exit_code, stdout, stderr = await self._run_command(cmd)
        execution_time = int((time.time() - start_time) * 1000)

        # Ruff returns 1 if issues found, 0 if clean
        if exit_code not in (0, 1):
            return LinterResult(
                success=False,
                issues=[],
                raw_output=stdout,
                error_message=stderr or f"ruff exited with code {exit_code}",
                execution_time_ms=execution_time,
            )

        issues = self.parse_output(stdout)

        return LinterResult(
            success=True,
            issues=issues,
            raw_output=stdout,
            execution_time_ms=execution_time,
        )

    def parse_output(self, output: str) -> list[QualityIssue]:
        """Parse ruff JSON output into QualityIssue objects."""
        if not output.strip():
            return []

        try:
            data = json.loads(output)
        except json.JSONDecodeError:
            logger.warning("Failed to parse ruff JSON output")
            return []

        issues = []
        for item in data:
            try:
                issue = self._parse_issue(item)
                if issue:
                    issues.append(issue)
            except Exception as e:
                logger.debug(f"Failed to parse ruff issue: {e}")
                continue

        return issues

    def _parse_issue(self, item: dict[str, Any]) -> QualityIssue | None:
        """Parse a single ruff issue."""
        code = item.get("code", "")
        message = item.get("message", "")
        filename = item.get("filename", "")
        location = item.get("location", {})
        end_location = item.get("end_location", {})
        fix = item.get("fix")

        # Determine category from code prefix
        category = IssueCategory.BEST_PRACTICE
        for prefix, cat in self.CATEGORY_MAP.items():
            if code.startswith(prefix):
                category = cat
                break

        # Determine severity
        severity = IssueSeverity.WARNING
        for prefix, sev in self.SEVERITY_MAP.items():
            if code.startswith(prefix):
                severity = sev
                break

        # Build location
        src_location = SourceLocation(
            file=filename,
            line=location.get("row", 1),
            column=location.get("column", 0),
            end_line=end_location.get("row"),
            end_column=end_location.get("column"),
        )

        # Build suggested fix if available
        suggested_fix = None
        is_auto_fixable = False
        if fix:
            is_auto_fixable = fix.get("applicability") == "safe"
            suggested_fix = SuggestedFix(
                description=fix.get("message", "Apply suggested fix"),
                confidence=FixConfidence.HIGH if is_auto_fixable else FixConfidence.MEDIUM,
                replacement_text=self._build_replacement(fix.get("edits", [])),
            )

        return QualityIssue(
            issue_id=f"ruff-{code}-{filename}-{location.get('row', 0)}",
            rule_id=code,
            severity=severity,
            category=category,
            location=src_location,
            message=message,
            source="ruff",
            documentation_url=f"https://docs.astral.sh/ruff/rules/{code}",
            suggested_fix=suggested_fix,
            is_auto_fixable=is_auto_fixable,
        )

    def _build_replacement(self, edits: list[dict[str, Any]]) -> str | None:
        """Build replacement text from ruff edits."""
        if not edits:
            return None
        # For simple cases, just return the first edit's content
        if len(edits) == 1:
            return edits[0].get("content", "")
        # For multiple edits, we'd need more complex logic
        return None


class ESLintRunner(LinterRunner):
    """
    ESLint runner for JavaScript and TypeScript files.

    Supports both eslint and the new flat config format.
    """

    name = "eslint"
    file_extensions = [".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"]

    CATEGORY_MAP = {
        "no-unused-vars": IssueCategory.DEAD_CODE,
        "no-undef": IssueCategory.TYPE,
        "no-console": IssueCategory.BEST_PRACTICE,
        "@typescript-eslint/no-unused-vars": IssueCategory.DEAD_CODE,
        "@typescript-eslint/no-explicit-any": IssueCategory.TYPE,
        "react/": IssueCategory.BEST_PRACTICE,
        "import/": IssueCategory.BEST_PRACTICE,
        "security/": IssueCategory.SECURITY,
    }

    def is_available(self) -> bool:
        """Check if eslint is installed."""
        # Check for local node_modules first
        local_eslint = self.project_root / "node_modules" / ".bin" / "eslint"
        if local_eslint.exists():
            return True
        return shutil.which("eslint") is not None

    def _get_eslint_path(self) -> str:
        """Get path to eslint executable."""
        local_eslint = self.project_root / "node_modules" / ".bin" / "eslint"
        if local_eslint.exists():
            return str(local_eslint)
        return "eslint"

    async def run(self, files: list[str]) -> LinterResult:
        """Run eslint on specified files."""
        import time

        start_time = time.time()

        if not self.is_available():
            return LinterResult(
                success=False,
                issues=[],
                raw_output="",
                error_message="eslint not installed. Install with: npm install eslint",
            )

        if not files:
            return LinterResult(success=True, issues=[], raw_output="")

        # Filter to supported files
        supported_files = [f for f in files if self.supports_file(f)]
        if not supported_files:
            return LinterResult(success=True, issues=[], raw_output="")

        eslint_path = self._get_eslint_path()
        cmd = [
            eslint_path,
            "--format=json",
            "--no-error-on-unmatched-pattern",
            *supported_files,
        ]

        exit_code, stdout, stderr = await self._run_command(cmd)
        execution_time = int((time.time() - start_time) * 1000)

        # ESLint returns 1 for issues, 2 for fatal errors
        if exit_code == 2:
            return LinterResult(
                success=False,
                issues=[],
                raw_output=stdout,
                error_message=stderr or "ESLint fatal error",
                execution_time_ms=execution_time,
            )

        issues = self.parse_output(stdout)

        return LinterResult(
            success=True,
            issues=issues,
            raw_output=stdout,
            execution_time_ms=execution_time,
        )

    def parse_output(self, output: str) -> list[QualityIssue]:
        """Parse eslint JSON output."""
        if not output.strip():
            return []

        try:
            data = json.loads(output)
        except json.JSONDecodeError:
            logger.warning("Failed to parse eslint JSON output")
            return []

        issues = []
        for file_result in data:
            file_path = file_result.get("filePath", "")
            for msg in file_result.get("messages", []):
                try:
                    issue = self._parse_message(file_path, msg)
                    if issue:
                        issues.append(issue)
                except Exception as e:
                    logger.debug(f"Failed to parse eslint message: {e}")

        return issues

    def _parse_message(
        self, file_path: str, msg: dict[str, Any]
    ) -> QualityIssue | None:
        """Parse a single eslint message."""
        rule_id = msg.get("ruleId", "unknown")
        message = msg.get("message", "")
        severity_code = msg.get("severity", 1)  # 1 = warning, 2 = error
        line = msg.get("line", 1)
        column = msg.get("column", 0)
        end_line = msg.get("endLine")
        end_column = msg.get("endColumn")
        fix = msg.get("fix")

        # Determine category
        category = IssueCategory.BEST_PRACTICE
        for prefix, cat in self.CATEGORY_MAP.items():
            if rule_id.startswith(prefix):
                category = cat
                break

        # Determine severity
        severity = IssueSeverity.ERROR if severity_code == 2 else IssueSeverity.WARNING

        location = SourceLocation(
            file=file_path,
            line=line,
            column=column,
            end_line=end_line,
            end_column=end_column,
        )

        # Build fix if available
        suggested_fix = None
        is_auto_fixable = fix is not None
        if fix:
            suggested_fix = SuggestedFix(
                description="Apply ESLint auto-fix",
                confidence=FixConfidence.HIGH,
                replacement_text=fix.get("text"),
            )

        return QualityIssue(
            issue_id=f"eslint-{rule_id}-{file_path}-{line}",
            rule_id=rule_id,
            severity=severity,
            category=category,
            location=location,
            message=message,
            source="eslint",
            documentation_url=f"https://eslint.org/docs/rules/{rule_id}" if not rule_id.startswith("@") else None,
            suggested_fix=suggested_fix,
            is_auto_fixable=is_auto_fixable,
        )


class GolangCILintRunner(LinterRunner):
    """
    golangci-lint runner for Go files.

    Aggregates many Go linters into one fast tool.
    """

    name = "golangci-lint"
    file_extensions = [".go"]

    CATEGORY_MAP = {
        "errcheck": IssueCategory.LOGIC,
        "gosimple": IssueCategory.BEST_PRACTICE,
        "govet": IssueCategory.LOGIC,
        "ineffassign": IssueCategory.DEAD_CODE,
        "staticcheck": IssueCategory.LOGIC,
        "typecheck": IssueCategory.TYPE,
        "unused": IssueCategory.DEAD_CODE,
        "gosec": IssueCategory.SECURITY,
        "gofmt": IssueCategory.FORMATTING,
        "goimports": IssueCategory.FORMATTING,
        "revive": IssueCategory.BEST_PRACTICE,
    }

    def is_available(self) -> bool:
        """Check if golangci-lint is installed."""
        return shutil.which("golangci-lint") is not None

    async def run(self, files: list[str]) -> LinterResult:
        """Run golangci-lint on specified files."""
        import time

        start_time = time.time()

        if not self.is_available():
            return LinterResult(
                success=False,
                issues=[],
                raw_output="",
                error_message="golangci-lint not installed. Install from: https://golangci-lint.run/usage/install/",
            )

        if not files:
            return LinterResult(success=True, issues=[], raw_output="")

        # golangci-lint works on packages, not individual files
        # Get unique directories
        directories = set()
        for f in files:
            if f.endswith(".go"):
                directories.add(os.path.dirname(f) or ".")

        if not directories:
            return LinterResult(success=True, issues=[], raw_output="")

        cmd = [
            "golangci-lint",
            "run",
            "--out-format=json",
            "--allow-parallel-runners",
            *[f"{d}/..." for d in directories],
        ]

        exit_code, stdout, stderr = await self._run_command(cmd)
        execution_time = int((time.time() - start_time) * 1000)

        # golangci-lint returns 1 for issues
        if exit_code not in (0, 1):
            return LinterResult(
                success=False,
                issues=[],
                raw_output=stdout,
                error_message=stderr or f"golangci-lint exited with code {exit_code}",
                execution_time_ms=execution_time,
            )

        issues = self.parse_output(stdout)

        return LinterResult(
            success=True,
            issues=issues,
            raw_output=stdout,
            execution_time_ms=execution_time,
        )

    def parse_output(self, output: str) -> list[QualityIssue]:
        """Parse golangci-lint JSON output."""
        if not output.strip():
            return []

        try:
            data = json.loads(output)
        except json.JSONDecodeError:
            logger.warning("Failed to parse golangci-lint JSON output")
            return []

        issues = []
        for item in data.get("Issues", []):
            try:
                issue = self._parse_issue(item)
                if issue:
                    issues.append(issue)
            except Exception as e:
                logger.debug(f"Failed to parse golangci-lint issue: {e}")

        return issues

    def _parse_issue(self, item: dict[str, Any]) -> QualityIssue | None:
        """Parse a single golangci-lint issue."""
        linter = item.get("FromLinter", "unknown")
        text = item.get("Text", "")
        pos = item.get("Pos", {})
        source_lines = item.get("SourceLines", [])
        replacement = item.get("Replacement")

        filename = pos.get("Filename", "")
        line = pos.get("Line", 1)
        column = pos.get("Column", 0)

        # Determine category
        category = self.CATEGORY_MAP.get(linter, IssueCategory.BEST_PRACTICE)

        # Determine severity based on linter
        severity = IssueSeverity.WARNING
        if linter in ("typecheck", "govet", "errcheck"):
            severity = IssueSeverity.ERROR
        elif linter in ("gosec",):
            severity = IssueSeverity.WARNING

        location = SourceLocation(
            file=filename,
            line=line,
            column=column,
        )

        # Build fix if replacement available
        suggested_fix = None
        is_auto_fixable = replacement is not None
        if replacement:
            suggested_fix = SuggestedFix(
                description=f"Apply {linter} fix",
                confidence=FixConfidence.HIGH,
                replacement_text=replacement.get("NewText"),
            )

        return QualityIssue(
            issue_id=f"golangci-{linter}-{filename}-{line}",
            rule_id=linter,
            severity=severity,
            category=category,
            location=location,
            message=text,
            source="golangci-lint",
            suggested_fix=suggested_fix,
            is_auto_fixable=is_auto_fixable,
        )


class MypyRunner(LinterRunner):
    """
    Mypy runner for Python type checking.

    Provides static type analysis beyond what ruff covers.
    """

    name = "mypy"
    file_extensions = [".py"]

    def is_available(self) -> bool:
        """Check if mypy is installed."""
        return shutil.which("mypy") is not None

    async def run(self, files: list[str]) -> LinterResult:
        """Run mypy on specified files."""
        import time

        start_time = time.time()

        if not self.is_available():
            return LinterResult(
                success=False,
                issues=[],
                raw_output="",
                error_message="mypy not installed. Install with: pip install mypy",
            )

        if not files:
            return LinterResult(success=True, issues=[], raw_output="")

        # Filter to Python files
        py_files = [f for f in files if f.endswith(".py")]
        if not py_files:
            return LinterResult(success=True, issues=[], raw_output="")

        cmd = [
            "mypy",
            "--no-error-summary",
            "--show-error-codes",
            "--no-pretty",
            *py_files,
        ]

        exit_code, stdout, stderr = await self._run_command(cmd, timeout=180)
        execution_time = int((time.time() - start_time) * 1000)

        # mypy returns 1 for type errors
        issues = self.parse_output(stdout)

        return LinterResult(
            success=True,
            issues=issues,
            raw_output=stdout,
            execution_time_ms=execution_time,
        )

    def parse_output(self, output: str) -> list[QualityIssue]:
        """Parse mypy output."""
        issues = []
        # Pattern: file.py:line:col: error: message [error-code]
        pattern = r"^(.+?):(\d+):(\d+): (error|warning|note): (.+?)(?:\s+\[([^\]]+)\])?$"

        for line in output.split("\n"):
            match = re.match(pattern, line.strip())
            if match:
                filename, line_num, col, severity_str, message, error_code = match.groups()

                severity = IssueSeverity.ERROR if severity_str == "error" else IssueSeverity.WARNING
                if severity_str == "note":
                    severity = IssueSeverity.INFO

                location = SourceLocation(
                    file=filename,
                    line=int(line_num),
                    column=int(col),
                )

                issues.append(
                    QualityIssue(
                        issue_id=f"mypy-{error_code or 'unknown'}-{filename}-{line_num}",
                        rule_id=error_code or "mypy-error",
                        severity=severity,
                        category=IssueCategory.TYPE,
                        location=location,
                        message=message,
                        source="mypy",
                        documentation_url=f"https://mypy.readthedocs.io/en/stable/error_codes.html#{error_code}" if error_code else None,
                    )
                )

        return issues


class LinterOrchestrator:
    """
    Orchestrates multiple linters for comprehensive code analysis.

    Selects appropriate linters based on file types and combines results.
    """

    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.runners: list[LinterRunner] = [
            RuffRunner(project_root),
            MypyRunner(project_root),
            ESLintRunner(project_root),
            GolangCILintRunner(project_root),
        ]

    def get_available_linters(self) -> list[str]:
        """Get list of available linters."""
        return [r.name for r in self.runners if r.is_available()]

    def get_runners_for_files(self, files: list[str]) -> list[LinterRunner]:
        """Get appropriate runners for given files."""
        runners = []
        for runner in self.runners:
            if runner.is_available():
                if any(runner.supports_file(f) for f in files):
                    runners.append(runner)
        return runners

    async def analyze_files(
        self,
        files: list[str],
        linters: list[str] | None = None,
    ) -> dict[str, LinterResult]:
        """
        Run all applicable linters on files.

        Args:
            files: Files to analyze
            linters: Optional specific linters to run (defaults to all available)

        Returns:
            Dictionary mapping linter name to its result
        """
        results: dict[str, LinterResult] = {}

        # Select runners
        runners = self.get_runners_for_files(files)
        if linters:
            runners = [r for r in runners if r.name in linters]

        # Run all linters in parallel
        tasks = []
        for runner in runners:
            runner_files = [f for f in files if runner.supports_file(f)]
            if runner_files:
                tasks.append((runner.name, runner.run(runner_files)))

        # Gather results
        for name, task in tasks:
            try:
                results[name] = await task
            except Exception as e:
                logger.error(f"Linter {name} failed: {e}")
                results[name] = LinterResult(
                    success=False,
                    issues=[],
                    raw_output="",
                    error_message=str(e),
                )

        return results

    async def analyze_directory(
        self,
        directory: str = ".",
        include_patterns: list[str] | None = None,
        exclude_patterns: list[str] | None = None,
    ) -> dict[str, LinterResult]:
        """
        Analyze all files in a directory.

        Args:
            directory: Directory to analyze (relative to project root)
            include_patterns: Glob patterns to include
            exclude_patterns: Glob patterns to exclude

        Returns:
            Dictionary mapping linter name to its result
        """
        import fnmatch

        dir_path = self.project_root / directory
        files = []

        # Default patterns
        if not include_patterns:
            include_patterns = ["*.py", "*.js", "*.jsx", "*.ts", "*.tsx", "*.go"]
        if not exclude_patterns:
            exclude_patterns = [
                "**/node_modules/**",
                "**/.venv/**",
                "**/venv/**",
                "**/__pycache__/**",
                "**/dist/**",
                "**/build/**",
                "**/.git/**",
            ]

        # Walk directory
        for root, dirs, filenames in os.walk(dir_path):
            # Skip excluded directories
            rel_root = os.path.relpath(root, self.project_root)
            if any(fnmatch.fnmatch(f"{rel_root}/", pat) for pat in exclude_patterns):
                continue

            for filename in filenames:
                rel_path = os.path.relpath(os.path.join(root, filename), self.project_root)

                # Check exclusions
                if any(fnmatch.fnmatch(rel_path, pat) for pat in exclude_patterns):
                    continue

                # Check inclusions
                if any(fnmatch.fnmatch(filename, pat) for pat in include_patterns):
                    files.append(rel_path)

        return await self.analyze_files(files)

    def build_file_analysis(
        self,
        file_path: str,
        results: dict[str, LinterResult],
    ) -> FileAnalysis:
        """
        Build FileAnalysis from linter results.

        Aggregates issues from all linters for a single file.
        """
        analysis = FileAnalysis(file_path=file_path)

        for linter_name, result in results.items():
            for issue in result.issues:
                if issue.location.file == file_path or issue.location.file.endswith(file_path):
                    analysis.add_issue(issue)

            analysis.analysis_time_ms += result.execution_time_ms

        return analysis

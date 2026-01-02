"""
Documentation Tool - Auto-documentation and analysis.

Provides MCP tools for:
- Documentation coverage analysis
- Changelog generation from commits
- README template generation
- API documentation extraction
"""

import json
import logging
import os
import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class DocCoverage:
    """Documentation coverage analysis."""

    total_files: int = 0
    documented_files: int = 0

    total_functions: int = 0
    documented_functions: int = 0

    total_classes: int = 0
    documented_classes: int = 0

    # Missing docs
    missing_docs: list[dict[str, str]] = field(default_factory=list)

    @property
    def coverage_percentage(self) -> float:
        total = self.total_functions + self.total_classes
        documented = self.documented_functions + self.documented_classes
        return (documented / total * 100) if total > 0 else 100

    def to_dict(self) -> dict[str, Any]:
        return {
            "coverage_percentage": round(self.coverage_percentage, 1),
            "files": {
                "total": self.total_files,
                "documented": self.documented_files,
            },
            "functions": {
                "total": self.total_functions,
                "documented": self.documented_functions,
            },
            "classes": {
                "total": self.total_classes,
                "documented": self.documented_classes,
            },
            "missing_docs": self.missing_docs[:20],
        }


@dataclass
class ChangelogEntry:
    """A single changelog entry."""

    version: str
    date: str
    changes: list[dict[str, str]] = field(default_factory=list)

    def to_markdown(self) -> str:
        lines = [f"## [{self.version}] - {self.date}", ""]

        # Group by type
        by_type: dict[str, list[str]] = {}
        for change in self.changes:
            change_type = change.get("type", "other")
            if change_type not in by_type:
                by_type[change_type] = []
            by_type[change_type].append(change.get("message", ""))

        type_labels = {
            "feat": "### Added",
            "fix": "### Fixed",
            "refactor": "### Changed",
            "perf": "### Performance",
            "docs": "### Documentation",
            "test": "### Tests",
            "chore": "### Maintenance",
            "breaking": "### Breaking Changes",
        }

        for change_type, label in type_labels.items():
            if change_type in by_type:
                lines.append(label)
                for msg in by_type[change_type]:
                    lines.append(f"- {msg}")
                lines.append("")

        return "\n".join(lines)


def analyze_doc_coverage(project_root: str, language: str = "python") -> DocCoverage:
    """Analyze documentation coverage in code files."""
    root = Path(project_root)
    coverage = DocCoverage()

    if language == "python":
        patterns = ["**/*.py"]
        func_pattern = r"^\s*(?:async\s+)?def\s+(\w+)"
        class_pattern = r"^\s*class\s+(\w+)"
        doc_pattern = r'^\s*"""'
    elif language in ("javascript", "typescript"):
        patterns = ["**/*.js", "**/*.ts", "**/*.jsx", "**/*.tsx"]
        func_pattern = r"^\s*(?:export\s+)?(?:async\s+)?function\s+(\w+)"
        class_pattern = r"^\s*(?:export\s+)?class\s+(\w+)"
        doc_pattern = r"^\s*/\*\*"
    else:
        return coverage

    for pattern in patterns:
        for file_path in root.glob(pattern):
            # Skip common exclusions
            if any(skip in str(file_path) for skip in [
                "node_modules", "venv", ".venv", "__pycache__",
                "test_", "_test.py", ".test.", "migrations",
            ]):
                continue

            coverage.total_files += 1

            try:
                with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
                    lines = content.split("\n")

                file_has_docs = False

                for i, line in enumerate(lines):
                    # Check for functions
                    func_match = re.match(func_pattern, line)
                    if func_match:
                        func_name = func_match.group(1)
                        if func_name.startswith("_") and not func_name.startswith("__"):
                            continue  # Skip private functions

                        coverage.total_functions += 1

                        # Check if next line has docstring
                        has_doc = False
                        if i + 1 < len(lines):
                            next_line = lines[i + 1]
                            if re.match(doc_pattern, next_line):
                                has_doc = True
                                file_has_docs = True

                        if has_doc:
                            coverage.documented_functions += 1
                        else:
                            coverage.missing_docs.append({
                                "type": "function",
                                "name": func_name,
                                "file": str(file_path.relative_to(root)),
                                "line": i + 1,
                            })

                    # Check for classes
                    class_match = re.match(class_pattern, line)
                    if class_match:
                        class_name = class_match.group(1)
                        coverage.total_classes += 1

                        # Check if next line has docstring
                        has_doc = False
                        if i + 1 < len(lines):
                            next_line = lines[i + 1]
                            if re.match(doc_pattern, next_line):
                                has_doc = True
                                file_has_docs = True

                        if has_doc:
                            coverage.documented_classes += 1
                        else:
                            coverage.missing_docs.append({
                                "type": "class",
                                "name": class_name,
                                "file": str(file_path.relative_to(root)),
                                "line": i + 1,
                            })

                if file_has_docs:
                    coverage.documented_files += 1

            except Exception as e:
                logger.debug(f"Error analyzing {file_path}: {e}")

    return coverage


def generate_changelog_from_commits(
    project_root: str,
    since: str = "",
    version: str = "Unreleased",
) -> ChangelogEntry:
    """Generate changelog from git commits."""
    entry = ChangelogEntry(
        version=version,
        date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    )

    try:
        cmd = ["git", "log", "--pretty=format:%s|%h|%an"]
        if since:
            cmd.append(f"{since}..HEAD")
        else:
            cmd.extend(["-n", "50"])  # Last 50 commits

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            cwd=project_root,
        )

        if result.returncode != 0:
            return entry

        for line in result.stdout.strip().split("\n"):
            if not line:
                continue

            parts = line.split("|", 2)
            if len(parts) < 2:
                continue

            message, commit_hash = parts[0], parts[1]

            # Parse conventional commits
            change_type = "other"
            clean_message = message

            # Match conventional commit format
            conv_match = re.match(r"^(feat|fix|docs|style|refactor|perf|test|chore|breaking)(?:\(.+\))?[!:]?\s*(.+)", message, re.I)
            if conv_match:
                change_type = conv_match.group(1).lower()
                clean_message = conv_match.group(2)

            entry.changes.append({
                "type": change_type,
                "message": clean_message,
                "commit": commit_hash,
            })

    except Exception as e:
        logger.warning(f"Error generating changelog: {e}")

    return entry


def generate_readme_template(project_root: str) -> str:
    """Generate a README template based on project structure."""
    root = Path(project_root)
    project_name = root.name

    # Detect project type
    project_type = "unknown"
    if (root / "package.json").exists():
        project_type = "node"
    elif (root / "pyproject.toml").exists() or (root / "setup.py").exists():
        project_type = "python"
    elif (root / "Cargo.toml").exists():
        project_type = "rust"
    elif (root / "go.mod").exists():
        project_type = "go"

    # Build template
    lines = [
        f"# {project_name}",
        "",
        "## Description",
        "",
        "<!-- Add project description here -->",
        "",
        "## Installation",
        "",
    ]

    if project_type == "node":
        lines.extend([
            "```bash",
            "npm install",
            "```",
        ])
    elif project_type == "python":
        lines.extend([
            "```bash",
            "pip install -e .",
            "```",
        ])
    elif project_type == "rust":
        lines.extend([
            "```bash",
            "cargo build",
            "```",
        ])
    elif project_type == "go":
        lines.extend([
            "```bash",
            "go build",
            "```",
        ])

    lines.extend([
        "",
        "## Usage",
        "",
        "```bash",
        f"# Run {project_name}",
        "```",
        "",
        "## License",
        "",
        "MIT",
        "",
    ])

    return "\n".join(lines)


class DocumentationTool:
    """Unified documentation tool."""

    def __init__(self, project_root: str):
        self.project_root = Path(project_root)

    async def analyze_coverage(self, language: str = "") -> dict[str, Any]:
        """Analyze documentation coverage."""
        # Auto-detect language
        if not language:
            if (self.project_root / "package.json").exists():
                language = "javascript"
            elif any(self.project_root.glob("**/*.py")):
                language = "python"
            else:
                language = "python"

        coverage = analyze_doc_coverage(str(self.project_root), language)

        grade = "A" if coverage.coverage_percentage >= 80 else \
                "B" if coverage.coverage_percentage >= 60 else \
                "C" if coverage.coverage_percentage >= 40 else \
                "D" if coverage.coverage_percentage >= 20 else "F"

        return {
            "type": "doc_coverage",
            "language": language,
            "grade": grade,
            **coverage.to_dict(),
        }

    async def generate_changelog(
        self,
        since: str = "",
        version: str = "Unreleased",
    ) -> dict[str, Any]:
        """Generate changelog from commits."""
        entry = generate_changelog_from_commits(
            str(self.project_root),
            since=since,
            version=version,
        )

        return {
            "type": "changelog",
            "version": entry.version,
            "date": entry.date,
            "change_count": len(entry.changes),
            "changes": entry.changes[:20],
            "markdown": entry.to_markdown(),
        }

    async def generate_readme(self) -> dict[str, Any]:
        """Generate README template."""
        template = generate_readme_template(str(self.project_root))

        return {
            "type": "readme_template",
            "project": self.project_root.name,
            "markdown": template,
        }

    async def check_docs(self) -> dict[str, Any]:
        """Check documentation files exist."""
        checks = []

        doc_files = [
            ("README.md", "Required", True),
            ("LICENSE", "Recommended", True),
            ("CONTRIBUTING.md", "Optional", False),
            ("CHANGELOG.md", "Recommended", False),
            ("docs/", "Optional", False),
        ]

        for file_name, importance, required in doc_files:
            exists = (self.project_root / file_name).exists()
            checks.append({
                "file": file_name,
                "exists": exists,
                "importance": importance,
                "required": required,
            })

        missing_required = [c for c in checks if c["required"] and not c["exists"]]
        missing_recommended = [c for c in checks if c["importance"] == "Recommended" and not c["exists"]]

        return {
            "type": "doc_check",
            "checks": checks,
            "missing_required": [c["file"] for c in missing_required],
            "missing_recommended": [c["file"] for c in missing_recommended],
            "complete": len(missing_required) == 0,
        }


# =============================================================================
# MCP-FACING FUNCTIONS
# =============================================================================

async def docs_coverage(language: str = "", path: str = "") -> dict[str, Any]:
    """Analyze documentation coverage."""
    project_path = path or os.getcwd()
    tool = DocumentationTool(project_path)
    return await tool.analyze_coverage(language)


async def docs_changelog(since: str = "", version: str = "Unreleased", path: str = "") -> dict[str, Any]:
    """Generate changelog from commits."""
    project_path = path or os.getcwd()
    tool = DocumentationTool(project_path)
    return await tool.generate_changelog(since, version)


async def docs_readme(path: str = "") -> dict[str, Any]:
    """Generate README template."""
    project_path = path or os.getcwd()
    tool = DocumentationTool(project_path)
    return await tool.generate_readme()


async def docs_check(path: str = "") -> dict[str, Any]:
    """Check documentation files."""
    project_path = path or os.getcwd()
    tool = DocumentationTool(project_path)
    return await tool.check_docs()

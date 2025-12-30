"""
Fastband AI Hub - Platform Analyzer.

Analyzes existing codebases to understand structure, tech stack,
and recommend optimal MCP workflow configurations.

Features:
- Language and framework detection
- CI/CD pipeline analysis
- Team workflow inference
- MCP tool recommendations
- Integration suggestions
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)


class ConnectionType(str, Enum):
    """How the codebase is connected."""

    LOCAL = "local"
    GITHUB = "github"
    GITLAB = "gitlab"
    BITBUCKET = "bitbucket"
    SSH = "ssh"
    UPLOAD = "upload"


class AnalysisPhase(str, Enum):
    """Analysis phases."""

    CONNECTING = "connecting"
    SCANNING = "scanning"
    DETECTING = "detecting"
    ANALYZING = "analyzing"
    RECOMMENDING = "recommending"
    COMPLETE = "complete"
    FAILED = "failed"


@dataclass(slots=True)
class FileStats:
    """Statistics about files in the codebase."""

    total_files: int = 0
    total_lines: int = 0
    by_extension: dict[str, int] = field(default_factory=dict)
    by_directory: dict[str, int] = field(default_factory=dict)


@dataclass(slots=True)
class TechStack:
    """Detected technology stack."""

    primary_language: str = "unknown"
    languages: dict[str, float] = field(default_factory=dict)  # language -> percentage
    frameworks: list[str] = field(default_factory=list)
    databases: list[str] = field(default_factory=list)
    cloud_providers: list[str] = field(default_factory=list)
    ci_cd: list[str] = field(default_factory=list)
    testing: list[str] = field(default_factory=list)
    package_managers: list[str] = field(default_factory=list)


@dataclass(slots=True)
class WorkflowInfo:
    """Detected team workflow patterns."""

    has_git: bool = False
    default_branch: str = "main"
    branch_pattern: str | None = None  # e.g., "feature/*"
    has_ci: bool = False
    has_tests: bool = False
    has_docs: bool = False
    has_docker: bool = False
    has_kubernetes: bool = False


@dataclass(slots=True)
class MCPRecommendation:
    """MCP workflow recommendation."""

    tool_category: str
    tools: list[str]
    priority: str  # "essential", "recommended", "optional"
    rationale: str
    configuration: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AnalysisReport:
    """Complete analysis report."""

    report_id: str
    project_name: str
    connection_type: ConnectionType
    phase: AnalysisPhase
    started_at: datetime
    completed_at: datetime | None = None

    # Analysis results
    file_stats: FileStats | None = None
    tech_stack: TechStack | None = None
    workflow: WorkflowInfo | None = None
    recommendations: list[MCPRecommendation] = field(default_factory=list)

    # Summary
    summary: str = ""
    confidence: float = 0.0
    warnings: list[str] = field(default_factory=list)


class PlatformAnalyzer:
    """
    Analyzes platforms and codebases for MCP integration.

    Performs comprehensive analysis of:
    - Code structure and languages
    - Frameworks and libraries
    - CI/CD pipelines
    - Team workflows
    - Testing practices

    Then generates recommendations for optimal MCP configuration.

    Example:
        analyzer = PlatformAnalyzer()
        report = await analyzer.analyze_local(Path("/path/to/project"))
        print(report.recommendations)
    """

    # File patterns for detection
    LANGUAGE_EXTENSIONS = {
        ".py": "Python",
        ".js": "JavaScript",
        ".ts": "TypeScript",
        ".jsx": "JavaScript",
        ".tsx": "TypeScript",
        ".go": "Go",
        ".rs": "Rust",
        ".java": "Java",
        ".kt": "Kotlin",
        ".rb": "Ruby",
        ".php": "PHP",
        ".cs": "C#",
        ".cpp": "C++",
        ".c": "C",
        ".swift": "Swift",
    }

    FRAMEWORK_INDICATORS = {
        "requirements.txt": ("Python", ["pip"]),
        "pyproject.toml": ("Python", ["poetry", "pip"]),
        "setup.py": ("Python", ["pip"]),
        "Pipfile": ("Python", ["pipenv"]),
        "package.json": ("JavaScript", ["npm", "yarn"]),
        "yarn.lock": ("JavaScript", ["yarn"]),
        "pnpm-lock.yaml": ("JavaScript", ["pnpm"]),
        "go.mod": ("Go", ["go modules"]),
        "Cargo.toml": ("Rust", ["cargo"]),
        "Gemfile": ("Ruby", ["bundler"]),
        "composer.json": ("PHP", ["composer"]),
        "pom.xml": ("Java", ["maven"]),
        "build.gradle": ("Java", ["gradle"]),
    }

    FRAMEWORK_PATTERNS = {
        # Python
        "django": ["Django", "django"],
        "flask": ["Flask", "flask"],
        "fastapi": ["FastAPI", "fastapi"],
        "pytorch": ["PyTorch", "torch"],
        "tensorflow": ["TensorFlow", "tensorflow"],
        # JavaScript
        "react": ["React", "react"],
        "vue": ["Vue", "vue"],
        "angular": ["Angular", "@angular"],
        "next": ["Next.js", "next"],
        "express": ["Express", "express"],
        "nest": ["NestJS", "@nestjs"],
        # Go
        "gin": ["Gin", "gin-gonic"],
        "fiber": ["Fiber", "gofiber"],
    }

    CI_CD_FILES = {
        ".github/workflows": "GitHub Actions",
        ".gitlab-ci.yml": "GitLab CI",
        "Jenkinsfile": "Jenkins",
        ".circleci": "CircleCI",
        ".travis.yml": "Travis CI",
        "azure-pipelines.yml": "Azure Pipelines",
        "bitbucket-pipelines.yml": "Bitbucket Pipelines",
    }

    DATABASE_PATTERNS = {
        "postgresql": "PostgreSQL",
        "postgres": "PostgreSQL",
        "mysql": "MySQL",
        "mongodb": "MongoDB",
        "redis": "Redis",
        "sqlite": "SQLite",
        "dynamodb": "DynamoDB",
        "firestore": "Firestore",
    }

    def __init__(self):
        """Initialize the platform analyzer."""
        self._progress_callback = None

    def on_progress(self, callback):
        """Set progress callback."""
        self._progress_callback = callback

    def _report_progress(self, phase: AnalysisPhase, message: str):
        """Report progress to callback."""
        if self._progress_callback:
            self._progress_callback(phase, message)
        logger.info(f"[{phase.value}] {message}")

    async def analyze_local(self, path: Path) -> AnalysisReport:
        """Analyze a local codebase.

        Args:
            path: Path to the project directory

        Returns:
            Complete analysis report
        """
        path = Path(path).resolve()

        if not path.exists():
            raise ValueError(f"Path does not exist: {path}")

        if not path.is_dir():
            raise ValueError(f"Path is not a directory: {path}")

        report = AnalysisReport(
            report_id=str(uuid4()),
            project_name=path.name,
            connection_type=ConnectionType.LOCAL,
            phase=AnalysisPhase.SCANNING,
            started_at=datetime.utcnow(),
        )

        try:
            # Phase 1: Scan files
            self._report_progress(AnalysisPhase.SCANNING, "Scanning directory structure...")
            report.file_stats = await self._scan_files(path)

            # Phase 2: Detect tech stack
            self._report_progress(AnalysisPhase.DETECTING, "Detecting technology stack...")
            report.tech_stack = await self._detect_tech_stack(path, report.file_stats)

            # Phase 3: Analyze workflow
            self._report_progress(AnalysisPhase.ANALYZING, "Analyzing team workflow...")
            report.workflow = await self._analyze_workflow(path)

            # Phase 4: Generate recommendations
            self._report_progress(AnalysisPhase.RECOMMENDING, "Generating recommendations...")
            report.recommendations = self._generate_recommendations(
                report.tech_stack,
                report.workflow,
            )

            # Generate summary
            report.summary = self._generate_summary(report)
            report.confidence = self._calculate_confidence(report)
            report.phase = AnalysisPhase.COMPLETE
            report.completed_at = datetime.utcnow()

            self._report_progress(AnalysisPhase.COMPLETE, "Analysis complete!")

        except Exception as e:
            logger.error(f"Analysis failed: {e}")
            report.phase = AnalysisPhase.FAILED
            report.warnings.append(str(e))
            report.completed_at = datetime.utcnow()

        return report

    async def analyze_github(
        self,
        repo_url: str,
        access_token: str | None = None,
    ) -> AnalysisReport:
        """Analyze a GitHub repository.

        Args:
            repo_url: GitHub repository URL
            access_token: GitHub access token for private repos

        Returns:
            Complete analysis report
        """
        # Parse repo URL
        match = re.match(r"https?://github\.com/([^/]+)/([^/]+)", repo_url)
        if not match:
            raise ValueError(f"Invalid GitHub URL: {repo_url}")

        owner, repo = match.groups()
        repo = repo.rstrip(".git")

        report = AnalysisReport(
            report_id=str(uuid4()),
            project_name=repo,
            connection_type=ConnectionType.GITHUB,
            phase=AnalysisPhase.CONNECTING,
            started_at=datetime.utcnow(),
        )

        try:
            # For now, we'll use the GitHub API to analyze
            # In production, this would clone or use GitHub's API
            self._report_progress(AnalysisPhase.CONNECTING, f"Connecting to {owner}/{repo}...")

            # Placeholder - would use GitHub API here
            report.warnings.append("GitHub analysis requires cloning. Using limited API analysis.")
            report.phase = AnalysisPhase.COMPLETE
            report.completed_at = datetime.utcnow()

        except Exception as e:
            logger.error(f"GitHub analysis failed: {e}")
            report.phase = AnalysisPhase.FAILED
            report.warnings.append(str(e))

        return report

    async def _scan_files(self, path: Path) -> FileStats:
        """Scan directory for file statistics."""
        stats = FileStats()
        ignored_dirs = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build"}

        for item in path.rglob("*"):
            # Skip ignored directories
            if any(ignored in item.parts for ignored in ignored_dirs):
                continue

            if item.is_file():
                stats.total_files += 1

                # Count by extension
                ext = item.suffix.lower()
                if ext:
                    stats.by_extension[ext] = stats.by_extension.get(ext, 0) + 1

                # Count by top-level directory
                try:
                    rel_path = item.relative_to(path)
                    top_dir = rel_path.parts[0] if len(rel_path.parts) > 1 else "."
                    stats.by_directory[top_dir] = stats.by_directory.get(top_dir, 0) + 1
                except ValueError:
                    pass

                # Count lines (for code files)
                if ext in self.LANGUAGE_EXTENSIONS:
                    try:
                        stats.total_lines += sum(1 for _ in item.open(errors="ignore"))
                    except Exception:
                        pass

        return stats

    async def _detect_tech_stack(self, path: Path, stats: FileStats) -> TechStack:
        """Detect the technology stack."""
        stack = TechStack()

        # Detect languages from file extensions
        total_code_files = sum(
            count for ext, count in stats.by_extension.items() if ext in self.LANGUAGE_EXTENSIONS
        )

        if total_code_files > 0:
            for ext, count in stats.by_extension.items():
                if ext in self.LANGUAGE_EXTENSIONS:
                    lang = self.LANGUAGE_EXTENSIONS[ext]
                    pct = (count / total_code_files) * 100
                    stack.languages[lang] = round(pct, 1)

            # Primary language is the most common
            if stack.languages:
                stack.primary_language = max(stack.languages, key=stack.languages.get)

        # Detect package managers and hints from config files
        for filename, (lang, pm_list) in self.FRAMEWORK_INDICATORS.items():
            if (path / filename).exists():
                for pm in pm_list:
                    if pm not in stack.package_managers:
                        stack.package_managers.append(pm)

        # Detect frameworks from dependency files
        await self._detect_frameworks(path, stack)

        # Detect databases
        await self._detect_databases(path, stack)

        # Detect CI/CD
        for ci_path, ci_name in self.CI_CD_FILES.items():
            if (path / ci_path).exists():
                stack.ci_cd.append(ci_name)

        # Detect testing frameworks
        await self._detect_testing(path, stack)

        return stack

    async def _detect_frameworks(self, path: Path, stack: TechStack):
        """Detect frameworks from dependency files."""
        # Check Python requirements
        for req_file in ["requirements.txt", "pyproject.toml", "Pipfile"]:
            req_path = path / req_file
            if req_path.exists():
                try:
                    content = req_path.read_text(errors="ignore").lower()
                    for pattern, (name, _) in self.FRAMEWORK_PATTERNS.items():
                        if pattern in content:
                            if name not in stack.frameworks:
                                stack.frameworks.append(name)
                except Exception:
                    pass

        # Check package.json
        pkg_path = path / "package.json"
        if pkg_path.exists():
            try:
                import json

                pkg = json.loads(pkg_path.read_text())
                deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
                for dep in deps:
                    for pattern, (name, _) in self.FRAMEWORK_PATTERNS.items():
                        if pattern in dep.lower():
                            if name not in stack.frameworks:
                                stack.frameworks.append(name)
            except Exception:
                pass

    async def _detect_databases(self, path: Path, stack: TechStack):
        """Detect database usage from config files."""
        config_files = ["docker-compose.yml", "docker-compose.yaml", ".env", ".env.example"]

        for config_file in config_files:
            config_path = path / config_file
            if config_path.exists():
                try:
                    content = config_path.read_text(errors="ignore").lower()
                    for pattern, db_name in self.DATABASE_PATTERNS.items():
                        if pattern in content:
                            if db_name not in stack.databases:
                                stack.databases.append(db_name)
                except Exception:
                    pass

    async def _detect_testing(self, path: Path, stack: TechStack):
        """Detect testing frameworks."""
        test_indicators = {
            "pytest.ini": "pytest",
            "setup.cfg": "pytest",  # Often contains pytest config
            "jest.config.js": "Jest",
            "jest.config.ts": "Jest",
            "karma.conf.js": "Karma",
            "cypress.json": "Cypress",
            "cypress.config.js": "Cypress",
            ".rspec": "RSpec",
        }

        for indicator, framework in test_indicators.items():
            if (path / indicator).exists():
                if framework not in stack.testing:
                    stack.testing.append(framework)

        # Check for test directories
        test_dirs = ["tests", "test", "spec", "__tests__", "e2e"]
        for test_dir in test_dirs:
            if (path / test_dir).is_dir():
                # Infer test framework from language
                if stack.primary_language == "Python" and "pytest" not in stack.testing:
                    stack.testing.append("pytest")
                elif (
                    stack.primary_language in ("JavaScript", "TypeScript")
                    and "Jest" not in stack.testing
                ):
                    stack.testing.append("Jest")
                break

    async def _analyze_workflow(self, path: Path) -> WorkflowInfo:
        """Analyze team workflow patterns."""
        workflow = WorkflowInfo()

        # Check for Git
        git_dir = path / ".git"
        if git_dir.is_dir():
            workflow.has_git = True

            # Try to get default branch
            try:
                head_ref = (git_dir / "HEAD").read_text().strip()
                if head_ref.startswith("ref: refs/heads/"):
                    workflow.default_branch = head_ref.replace("ref: refs/heads/", "")
            except Exception:
                pass

        # Check for CI
        for ci_path in self.CI_CD_FILES:
            if (path / ci_path).exists():
                workflow.has_ci = True
                break

        # Check for tests
        test_dirs = ["tests", "test", "spec", "__tests__"]
        for test_dir in test_dirs:
            if (path / test_dir).is_dir():
                workflow.has_tests = True
                break

        # Check for docs
        doc_indicators = ["docs", "documentation", "README.md", "CONTRIBUTING.md"]
        for doc in doc_indicators:
            if (path / doc).exists():
                workflow.has_docs = True
                break

        # Check for Docker
        docker_files = ["Dockerfile", "docker-compose.yml", "docker-compose.yaml"]
        for docker_file in docker_files:
            if (path / docker_file).exists():
                workflow.has_docker = True
                break

        # Check for Kubernetes
        k8s_indicators = ["kubernetes", "k8s", "helm"]
        for k8s in k8s_indicators:
            if (path / k8s).is_dir():
                workflow.has_kubernetes = True
                break

        return workflow

    def _generate_recommendations(
        self,
        stack: TechStack,
        workflow: WorkflowInfo,
    ) -> list[MCPRecommendation]:
        """Generate MCP configuration recommendations."""
        recommendations = []

        # Essential: File and search tools
        recommendations.append(
            MCPRecommendation(
                tool_category="core",
                tools=["read_file", "write_file", "search_files", "list_directory"],
                priority="essential",
                rationale="Core file operations are required for any development workflow.",
            )
        )

        # Git tools if using git
        if workflow.has_git:
            recommendations.append(
                MCPRecommendation(
                    tool_category="git",
                    tools=["git_status", "git_diff", "git_commit", "git_log"],
                    priority="essential",
                    rationale="Git integration for version control workflow.",
                    configuration={"default_branch": workflow.default_branch},
                )
            )

        # Language-specific tools
        if stack.primary_language == "Python":
            recommendations.append(
                MCPRecommendation(
                    tool_category="python",
                    tools=["run_python", "pip_install", "pytest_run"],
                    priority="recommended",
                    rationale="Python-specific development tools.",
                )
            )

        elif stack.primary_language in ("JavaScript", "TypeScript"):
            recommendations.append(
                MCPRecommendation(
                    tool_category="javascript",
                    tools=["npm_run", "npm_install"],
                    priority="recommended",
                    rationale="JavaScript/TypeScript development tools.",
                )
            )

        # Testing tools if tests exist
        if workflow.has_tests:
            recommendations.append(
                MCPRecommendation(
                    tool_category="testing",
                    tools=["run_tests", "test_coverage"],
                    priority="recommended",
                    rationale="Testing tools for your existing test suite.",
                    configuration={"frameworks": stack.testing},
                )
            )

        # Docker tools
        if workflow.has_docker:
            recommendations.append(
                MCPRecommendation(
                    tool_category="docker",
                    tools=["docker_build", "docker_run", "docker_compose"],
                    priority="recommended",
                    rationale="Docker containerization tools.",
                )
            )

        # Semantic search for larger codebases
        recommendations.append(
            MCPRecommendation(
                tool_category="context",
                tools=["semantic_search", "index_codebase"],
                priority="recommended",
                rationale="AI-powered code search for navigating the codebase.",
            )
        )

        # Ticket management
        recommendations.append(
            MCPRecommendation(
                tool_category="tickets",
                tools=["create_ticket", "list_tickets", "update_ticket"],
                priority="optional",
                rationale="Task and ticket management for organized development.",
            )
        )

        return recommendations

    def _generate_summary(self, report: AnalysisReport) -> str:
        """Generate a human-readable summary."""
        parts = []

        if report.tech_stack:
            stack = report.tech_stack
            parts.append(f"Primary language: {stack.primary_language}")

            if stack.frameworks:
                parts.append(f"Frameworks: {', '.join(stack.frameworks)}")

            if stack.databases:
                parts.append(f"Databases: {', '.join(stack.databases)}")

        if report.file_stats:
            parts.append(f"Files: {report.file_stats.total_files:,}")
            parts.append(f"Lines of code: {report.file_stats.total_lines:,}")

        if report.workflow:
            features = []
            if report.workflow.has_git:
                features.append("Git")
            if report.workflow.has_ci:
                features.append("CI/CD")
            if report.workflow.has_tests:
                features.append("Tests")
            if report.workflow.has_docker:
                features.append("Docker")

            if features:
                parts.append(f"Workflow features: {', '.join(features)}")

        parts.append(f"Recommendations: {len(report.recommendations)} tool categories")

        return " | ".join(parts)

    def _calculate_confidence(self, report: AnalysisReport) -> float:
        """Calculate confidence score for the analysis."""
        score = 0.0
        max_score = 0.0

        # File analysis confidence
        max_score += 0.3
        if report.file_stats and report.file_stats.total_files > 0:
            score += 0.3

        # Tech stack confidence
        max_score += 0.3
        if report.tech_stack:
            if report.tech_stack.primary_language != "unknown":
                score += 0.2
            if report.tech_stack.frameworks:
                score += 0.1

        # Workflow confidence
        max_score += 0.2
        if report.workflow:
            if report.workflow.has_git:
                score += 0.1
            if report.workflow.has_ci or report.workflow.has_tests:
                score += 0.1

        # Recommendations confidence
        max_score += 0.2
        if report.recommendations:
            score += 0.2

        return round(score / max_score, 2) if max_score > 0 else 0.0

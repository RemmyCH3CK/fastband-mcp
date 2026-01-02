"""
CodebaseContext - Ambient Intelligence Layer for the Codebase.

The brain that maintains awareness of the entire codebase:
- File relationships and impact analysis
- Historical patterns and learned behaviors
- Smart caching to avoid repeated work
- Memory integration for cross-session learning

Usage:
    context = CodebaseContext("/path/to/project")
    await context.initialize()

    # Get context for a file before modifying it
    file_ctx = await context.get_file_context("src/auth/login.py")
    print(file_ctx.recommendations)
    print(file_ctx.common_mistakes)

    # Warm up context for files agent will likely touch
    await context.warm_cache(["src/api/routes.py", "src/models/user.py"])
"""

import asyncio
import logging
import os
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from fastband.context.cache import ContextCache
from fastband.context.graph import DependencyGraph
from fastband.context.models import (
    CodebaseSnapshot,
    ContextQuery,
    ContextResult,
    FileContext,
    FileHistory,
    FileMetrics,
    FileType,
    ImpactGraph,
    LearnedPattern,
    PastIssue,
    Severity,
)

logger = logging.getLogger(__name__)


class CodebaseContext:
    """
    Maintains ambient awareness of the entire codebase.

    This is the central intelligence layer that other tools use
    to understand the context of files they're working with.

    Features:
    - Lazy initialization for fast startup
    - Smart caching to avoid repeated analysis
    - Memory integration for learning from past work
    - Git integration for history analysis
    - Async-first design for parallel operations
    """

    def __init__(
        self,
        project_root: str,
        memory_enabled: bool = True,
        cache_ttl_seconds: int = 300,
        max_cached_files: int = 500,
    ):
        """
        Initialize CodebaseContext.

        Args:
            project_root: Root directory of the project
            memory_enabled: Whether to integrate with memory system
            cache_ttl_seconds: How long to cache file contexts
            max_cached_files: Maximum files to keep in cache
        """
        self.project_root = Path(project_root).resolve()
        self.memory_enabled = memory_enabled

        # Core components (lazy initialized)
        self._graph: Optional[DependencyGraph] = None
        self._cache: Optional[ContextCache] = None
        self._memory_manager = None

        # Configuration
        self._cache_ttl = cache_ttl_seconds
        self._max_cached = max_cached_files

        # State
        self._initialized = False
        self._last_scan: Optional[datetime] = None
        self._snapshot: Optional[CodebaseSnapshot] = None

        # Async lock for initialization
        self._init_lock = asyncio.Lock()

    async def initialize(self, force_scan: bool = False) -> None:
        """
        Initialize the context system.

        This is called lazily on first use, but can be called
        explicitly for eager initialization.

        Args:
            force_scan: Force a full codebase scan even if cached
        """
        async with self._init_lock:
            if self._initialized and not force_scan:
                return

            logger.info(f"Initializing CodebaseContext for {self.project_root}")

            # Initialize cache
            self._cache = ContextCache(
                str(self.project_root),
                max_file_contexts=self._max_cached,
                context_ttl_seconds=self._cache_ttl,
            )

            # Initialize dependency graph
            self._graph = DependencyGraph(str(self.project_root))

            # Scan codebase for dependencies
            files_scanned = await asyncio.to_thread(
                self._graph.scan_directory
            )
            logger.info(f"Scanned {files_scanned} files for dependencies")

            # Initialize memory integration
            if self.memory_enabled:
                try:
                    from fastband.memory import get_memory_manager
                    self._memory_manager = get_memory_manager()
                except ImportError:
                    logger.warning("Memory system not available")
                    self._memory_manager = None

            self._last_scan = datetime.now(timezone.utc)
            self._initialized = True

    async def _ensure_initialized(self) -> None:
        """Ensure context is initialized before use."""
        if not self._initialized:
            await self.initialize()

    # =========================================================================
    # FILE CONTEXT
    # =========================================================================

    async def get_file_context(
        self,
        file_path: str,
        include_impact: bool = True,
        include_history: bool = True,
        include_patterns: bool = True,
        force_refresh: bool = False,
    ) -> FileContext:
        """
        Get complete context for a file.

        This is the main entry point for getting information about a file.
        Returns everything the agent needs to know before modifying it.

        Args:
            file_path: Path to file (relative or absolute)
            include_impact: Include dependency impact analysis
            include_history: Include git history
            include_patterns: Include learned patterns from memory
            force_refresh: Bypass cache

        Returns:
            FileContext with complete file information
        """
        await self._ensure_initialized()

        # Normalize path
        rel_path = self._normalize_path(file_path)
        full_path = self.project_root / rel_path

        # Check cache first
        if not force_refresh:
            cached = self._cache.get_file_context(rel_path)
            if cached is not None:
                return cached

        # Build context
        context = FileContext(
            file_path=rel_path,
            file_type=self._graph.get_file_type(rel_path),
            exists=full_path.exists(),
        )

        # Gather information in parallel
        tasks = []

        if include_impact:
            tasks.append(self._get_impact_graph(rel_path))

        if include_history:
            tasks.append(self._get_file_history(rel_path))

        if include_patterns and self._memory_manager:
            tasks.append(self._get_learned_patterns(rel_path))

        # Always get metrics
        tasks.append(self._get_file_metrics(rel_path))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Assign results
        result_idx = 0

        if include_impact:
            if not isinstance(results[result_idx], Exception):
                context.impact_graph = results[result_idx]
            result_idx += 1

        if include_history:
            if not isinstance(results[result_idx], Exception):
                context.history = results[result_idx]
                context.past_issues = await self._get_past_issues(rel_path)
            result_idx += 1

        if include_patterns and self._memory_manager:
            if not isinstance(results[result_idx], Exception):
                patterns_data = results[result_idx]
                context.applicable_patterns = patterns_data.get("patterns", [])
                context.common_mistakes = patterns_data.get("mistakes", [])
            result_idx += 1

        # Metrics are always last
        if not isinstance(results[result_idx], Exception):
            context.metrics = results[result_idx]

        # Generate recommendations based on all data
        context.recommendations = self._generate_recommendations(context)
        context.warnings = self._generate_warnings(context)

        # Cache and return
        context.cache_valid_until = datetime.now(timezone.utc) + timedelta(
            seconds=self._cache_ttl
        )
        self._cache.set_file_context(rel_path, context)

        return context

    async def _get_impact_graph(self, file_path: str) -> ImpactGraph:
        """Get impact graph for a file."""
        # Check cache
        cached = self._cache.get_impact_graph(file_path)
        if cached:
            return cached

        # Build graph
        graph = await asyncio.to_thread(
            self._graph.get_impact_graph, file_path
        )

        # Cache and return
        self._cache.set_impact_graph(file_path, graph)
        return graph

    async def _get_file_history(self, file_path: str) -> FileHistory:
        """Get git history for a file."""
        history = FileHistory()

        try:
            full_path = self.project_root / file_path

            # Get last modified from git
            result = await asyncio.to_thread(
                subprocess.run,
                ["git", "log", "-1", "--format=%aI", "--", str(full_path)],
                cwd=str(self.project_root),
                capture_output=True,
                text=True,
            )
            if result.returncode == 0 and result.stdout.strip():
                history.last_modified = datetime.fromisoformat(
                    result.stdout.strip().replace("Z", "+00:00")
                )

            # Get commit count
            result = await asyncio.to_thread(
                subprocess.run,
                ["git", "rev-list", "--count", "HEAD", "--", str(full_path)],
                cwd=str(self.project_root),
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                history.modification_count = int(result.stdout.strip())

            # Get recent authors
            result = await asyncio.to_thread(
                subprocess.run,
                ["git", "log", "-5", "--format=%an", "--", str(full_path)],
                cwd=str(self.project_root),
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                authors = result.stdout.strip().split("\n")
                history.recent_authors = list(dict.fromkeys(authors))  # Unique, preserve order

            # Calculate churn rate (commits in last 30 days)
            result = await asyncio.to_thread(
                subprocess.run,
                [
                    "git", "rev-list", "--count", "--since=30.days",
                    "HEAD", "--", str(full_path)
                ],
                cwd=str(self.project_root),
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                commits_30d = int(result.stdout.strip())
                history.churn_rate = commits_30d / 4  # Per week

        except Exception as e:
            logger.warning(f"Error getting git history for {file_path}: {e}")

        return history

    async def _get_file_metrics(self, file_path: str) -> FileMetrics:
        """Calculate metrics for a file."""
        # Check cache
        cached = self._cache.get_metrics(file_path)
        if cached:
            return cached

        metrics = FileMetrics()
        full_path = self.project_root / file_path

        if not full_path.exists():
            return metrics

        try:
            content = await asyncio.to_thread(
                full_path.read_text, encoding="utf-8", errors="ignore"
            )
            lines = content.split("\n")

            for line in lines:
                stripped = line.strip()
                if not stripped:
                    metrics.blank_lines += 1
                elif self._is_comment_line(stripped, file_path):
                    metrics.lines_of_comments += 1
                else:
                    metrics.lines_of_code += 1

            # Calculate complexity for Python files
            if file_path.endswith(".py"):
                metrics.complexity_score = await self._calculate_python_complexity(
                    content
                )

        except Exception as e:
            logger.warning(f"Error calculating metrics for {file_path}: {e}")

        self._cache.set_metrics(file_path, metrics)
        return metrics

    def _is_comment_line(self, line: str, file_path: str) -> bool:
        """Check if a line is a comment."""
        ext = Path(file_path).suffix.lower()

        if ext in [".py"]:
            return line.startswith("#") or line.startswith('"""') or line.startswith("'''")
        elif ext in [".js", ".ts", ".jsx", ".tsx", ".go", ".java", ".c", ".cpp"]:
            return line.startswith("//") or line.startswith("/*") or line.startswith("*")
        elif ext in [".html", ".xml"]:
            return line.startswith("<!--")
        elif ext in [".css", ".scss"]:
            return line.startswith("/*")
        elif ext in [".sh", ".bash", ".yaml", ".yml"]:
            return line.startswith("#")

        return False

    async def _calculate_python_complexity(self, content: str) -> float:
        """Calculate cyclomatic complexity for Python code."""
        try:
            import ast

            tree = ast.parse(content)
            complexity = 1  # Base complexity

            for node in ast.walk(tree):
                # Each decision point adds complexity
                if isinstance(node, (ast.If, ast.While, ast.For, ast.ExceptHandler)):
                    complexity += 1
                elif isinstance(node, ast.BoolOp):
                    complexity += len(node.values) - 1
                elif isinstance(node, ast.comprehension):
                    complexity += 1

            return float(complexity)

        except Exception:
            return 0.0

    async def _get_learned_patterns(self, file_path: str) -> Dict[str, Any]:
        """Get learned patterns from memory system."""
        patterns = []
        mistakes = []

        if not self._memory_manager:
            return {"patterns": patterns, "mistakes": mistakes}

        try:
            # Query memory for patterns related to this file
            results = self._memory_manager.get_relevant_patterns(
                query=file_path,
                files=[file_path],
            )

            for pattern in results:
                patterns.append(
                    LearnedPattern(
                        pattern_id=pattern.pattern_id,
                        pattern_type=pattern.pattern_type if hasattr(pattern, 'pattern_type') else "general",
                        description=pattern.description if hasattr(pattern, 'description') else "",
                        recommendation=pattern.solution_template if hasattr(pattern, 'solution_template') else "",
                        occurrence_count=pattern.occurrence_count if hasattr(pattern, 'occurrence_count') else 0,
                    )
                )

                # Extract common mistakes from patterns
                if hasattr(pattern, 'common_files_to_check'):
                    for f in pattern.common_files_to_check:
                        if f not in mistakes:
                            mistakes.append(f"Check {f} when modifying this file")

        except Exception as e:
            logger.warning(f"Error getting patterns for {file_path}: {e}")

        return {"patterns": patterns, "mistakes": mistakes}

    async def _get_past_issues(self, file_path: str) -> List[PastIssue]:
        """Get past issues related to this file from memory."""
        issues = []

        if not self._memory_manager:
            return issues

        try:
            # Query memory for past tickets involving this file
            results = self._memory_manager.query_memories(
                query=file_path,
                files=[file_path],
                max_results=5,
            )

            for memory, score in results:
                issues.append(
                    PastIssue(
                        issue_id=memory.ticket_id,
                        issue_type=memory.ticket_type,
                        title=memory.title,
                        description=memory.problem_summary,
                        severity=Severity.MEDIUM,  # Could be enhanced
                        fixed=True,
                        fix_summary=memory.solution_summary,
                    )
                )

        except Exception as e:
            logger.warning(f"Error getting past issues for {file_path}: {e}")

        return issues

    def _generate_recommendations(self, context: FileContext) -> List[str]:
        """Generate recommendations based on file context."""
        recommendations = []

        # Based on impact
        if context.impact_graph:
            if context.impact_graph.impact_level.value in ["critical", "high"]:
                recommendations.append(
                    f"High-impact file: Changes affect {context.impact_graph.total_dependents} other files"
                )

            if context.impact_graph.tests_to_run:
                tests = context.impact_graph.tests_to_run[:3]
                recommendations.append(
                    f"Run tests: {', '.join(tests)}"
                )

            if context.impact_graph.is_on_critical_path:
                recommendations.append(
                    f"Critical path: {context.impact_graph.critical_path_reason}"
                )

        # Based on history
        if context.history.churn_rate > 2:
            recommendations.append(
                "High churn file - consider extra review"
            )

        if context.history.hotspot_score > 0.5:
            recommendations.append(
                "Bug hotspot - proceed carefully"
            )

        # Based on metrics
        if context.metrics.complexity_score > 15:
            recommendations.append(
                f"High complexity ({context.metrics.complexity_score:.0f}) - consider refactoring"
            )

        if context.metrics.test_coverage is not None and context.metrics.test_coverage < 50:
            recommendations.append(
                f"Low test coverage ({context.metrics.test_coverage:.0f}%) - add tests"
            )

        # Based on patterns
        for pattern in context.applicable_patterns[:2]:
            if pattern.recommendation:
                recommendations.append(pattern.recommendation)

        return recommendations

    def _generate_warnings(self, context: FileContext) -> List[str]:
        """Generate warnings based on file context."""
        warnings = []

        # Recurring issues
        recurring = [i for i in context.past_issues if i.recurred]
        if recurring:
            warnings.append(
                f"⚠️ {len(recurring)} past issues have recurred in this file"
            )

        # High complexity + high churn
        if context.metrics.complexity_score > 20 and context.history.churn_rate > 1:
            warnings.append(
                "⚠️ Complex file with high churn - high risk of introducing bugs"
            )

        # Critical path without tests
        if (
            context.impact_graph
            and context.impact_graph.is_on_critical_path
            and not context.impact_graph.test_files
        ):
            warnings.append(
                "⚠️ Critical path file with no direct tests"
            )

        return warnings

    # =========================================================================
    # BULK OPERATIONS
    # =========================================================================

    async def warm_cache(
        self,
        files: List[str],
        include_related: bool = True,
    ) -> int:
        """
        Pre-load context for files agent will likely touch.

        Args:
            files: List of file paths
            include_related: Also warm related files (imports, importers)

        Returns:
            Number of files warmed
        """
        await self._ensure_initialized()

        files_to_warm = set(self._normalize_path(f) for f in files)

        # Include related files
        if include_related:
            for file_path in list(files_to_warm):
                graph = await self._get_impact_graph(file_path)
                # Add direct imports and importers
                files_to_warm.update(graph.imports_from[:5])
                files_to_warm.update(graph.imported_by[:5])

        # Warm in parallel
        tasks = [
            self.get_file_context(f, force_refresh=False)
            for f in files_to_warm
        ]

        await asyncio.gather(*tasks, return_exceptions=True)

        return len(files_to_warm)

    async def query(self, query: ContextQuery) -> ContextResult:
        """
        Execute a context query.

        Args:
            query: ContextQuery specifying what to retrieve

        Returns:
            ContextResult with all requested information
        """
        await self._ensure_initialized()

        import time
        start = time.time()

        result = ContextResult(query=query)

        # Gather files to query
        files_to_query = set()

        for f in query.files:
            files_to_query.add(self._normalize_path(f))

        for d in query.directories:
            dir_path = self.project_root / d
            if dir_path.exists():
                for file_path in dir_path.rglob("*"):
                    if file_path.is_file():
                        rel = str(file_path.relative_to(self.project_root))
                        files_to_query.add(rel)

                        if len(files_to_query) >= query.max_files:
                            break

        # Filter by type if specified
        if query.file_types:
            type_values = {t.value for t in query.file_types}
            files_to_query = {
                f for f in files_to_query
                if self._graph.get_file_type(f).value in type_values
            }

        # Get contexts
        for file_path in files_to_query:
            try:
                ctx = await self.get_file_context(
                    file_path,
                    include_impact=query.include_impact,
                    include_history=query.include_history,
                    include_patterns=query.include_patterns,
                    force_refresh=query.force_refresh,
                )
                result.file_contexts[file_path] = ctx

                # Track cache hits/misses
                if ctx.is_cache_valid():
                    result.cache_hits += 1
                else:
                    result.cache_misses += 1

            except Exception as e:
                logger.warning(f"Error getting context for {file_path}: {e}")

        # Calculate suggested review order
        result.suggested_review_order = self._calculate_review_order(
            result.file_contexts
        )

        result.query_time_ms = int((time.time() - start) * 1000)

        return result

    def _calculate_review_order(
        self,
        contexts: Dict[str, FileContext],
    ) -> List[str]:
        """Calculate optimal review order for files."""
        # Score each file: higher = review first
        scores = []

        for path, ctx in contexts.items():
            score = 0

            # Core files first
            if ctx.impact_graph and ctx.impact_graph.is_on_critical_path:
                score += 100

            # High impact files
            if ctx.impact_graph:
                score += ctx.impact_graph.impact_score

            # Bug hotspots
            score += ctx.history.hotspot_score * 50

            # High complexity
            score += min(ctx.metrics.complexity_score * 2, 30)

            scores.append((path, score))

        # Sort by score descending
        scores.sort(key=lambda x: x[1], reverse=True)

        return [path for path, _ in scores]

    # =========================================================================
    # INVALIDATION
    # =========================================================================

    def invalidate_file(self, file_path: str) -> None:
        """Invalidate cache for a file (call when file changes)."""
        if self._cache:
            rel_path = self._normalize_path(file_path)
            self._cache.invalidate_file(rel_path)

    def invalidate_all(self) -> None:
        """Invalidate all cached context."""
        if self._cache:
            self._cache.clear_all()

    # =========================================================================
    # UTILITIES
    # =========================================================================

    def _normalize_path(self, file_path: str) -> str:
        """Normalize a file path to relative format."""
        path = Path(file_path)

        if path.is_absolute():
            try:
                return str(path.relative_to(self.project_root))
            except ValueError:
                return str(path)

        return str(path)

    async def get_snapshot(self) -> CodebaseSnapshot:
        """Get a snapshot of current codebase state."""
        await self._ensure_initialized()

        from uuid import uuid4

        snapshot = CodebaseSnapshot(
            snapshot_id=str(uuid4()),
            total_files=len(self._graph.nodes),
        )

        # Count files by type
        for path in self._graph.nodes:
            file_type = self._graph.get_file_type(path)
            type_key = file_type.value
            snapshot.files_by_type[type_key] = snapshot.files_by_type.get(type_key, 0) + 1

        # Get most depended on files
        most_depended = self._graph.get_most_depended_files(10)
        snapshot.most_depended_on = [path for path, _ in most_depended]

        # Get orphan files
        snapshot.orphan_files = self._graph.get_orphan_files()[:20]

        # Git state
        try:
            result = subprocess.run(
                ["git", "branch", "--show-current"],
                cwd=str(self.project_root),
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                snapshot.git_branch = result.stdout.strip()

            result = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                cwd=str(self.project_root),
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                snapshot.git_commit = result.stdout.strip()

        except Exception:
            pass

        self._snapshot = snapshot
        return snapshot

    def get_stats(self) -> Dict[str, Any]:
        """Get context system statistics."""
        stats = {
            "initialized": self._initialized,
            "project_root": str(self.project_root),
            "last_scan": self._last_scan.isoformat() if self._last_scan else None,
            "memory_enabled": self.memory_enabled,
        }

        if self._graph:
            stats["graph"] = {
                "nodes": len(self._graph.nodes),
            }

        if self._cache:
            stats["cache"] = self._cache.get_stats()

        return stats


# =============================================================================
# SINGLETON ACCESSOR
# =============================================================================

_context_instances: Dict[str, CodebaseContext] = {}
_context_lock = asyncio.Lock()


async def get_codebase_context(project_root: str) -> CodebaseContext:
    """
    Get or create a CodebaseContext for a project.

    This maintains a singleton per project root.
    """
    global _context_instances

    project_root = str(Path(project_root).resolve())

    async with _context_lock:
        if project_root not in _context_instances:
            context = CodebaseContext(project_root)
            await context.initialize()
            _context_instances[project_root] = context

        return _context_instances[project_root]


def get_codebase_context_sync(project_root: str) -> CodebaseContext:
    """
    Synchronous version for non-async contexts.

    Note: This creates an uninitialized context.
    Call context.initialize() or use get_file_context() which auto-initializes.
    """
    global _context_instances

    project_root = str(Path(project_root).resolve())

    if project_root not in _context_instances:
        _context_instances[project_root] = CodebaseContext(project_root)

    return _context_instances[project_root]

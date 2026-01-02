"""
Fastband Codebase Context - Ambient Intelligence Layer.

Provides contextual awareness of the entire codebase for intelligent
tool execution and decision making.

Key Components:
- CodebaseContext: Main interface for getting file context
- DependencyGraph: Import/export relationship analyzer
- ContextCache: Smart caching with file modification tracking

Usage:
    from fastband.context import get_codebase_context

    # Get context singleton for a project
    context = await get_codebase_context("/path/to/project")

    # Get full context for a file before modifying it
    file_ctx = await context.get_file_context("src/auth/login.py")

    # Access recommendations
    print(file_ctx.recommendations)  # What to watch out for
    print(file_ctx.warnings)         # Potential issues
    print(file_ctx.common_mistakes)  # Learned from past work

    # Access impact analysis
    print(file_ctx.impact_graph.imported_by)     # Who uses this
    print(file_ctx.impact_graph.tests_to_run)    # Tests to run
    print(file_ctx.impact_graph.is_on_critical_path)  # Is this core?

    # Warm cache for files agent will touch
    await context.warm_cache(["src/api/routes.py", "src/models/user.py"])
"""

from fastband.context.cache import ContextCache, LRUCache
from fastband.context.codebase import (
    CodebaseContext,
    get_codebase_context,
    get_codebase_context_sync,
)
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
    ImpactLevel,
    ImportRelation,
    LearnedPattern,
    PastIssue,
    Severity,
)

__all__ = [
    # Main interface
    "CodebaseContext",
    "get_codebase_context",
    "get_codebase_context_sync",
    # Graph
    "DependencyGraph",
    # Cache
    "ContextCache",
    "LRUCache",
    # Models
    "FileContext",
    "FileMetrics",
    "FileHistory",
    "FileType",
    "ImpactGraph",
    "ImpactLevel",
    "ImportRelation",
    "LearnedPattern",
    "PastIssue",
    "Severity",
    "CodebaseSnapshot",
    "ContextQuery",
    "ContextResult",
]

"""
Fastband Tool Garage System.

Provides tool registration, loading, and execution for the MCP server.

Performance Notes (Issue #38):
- Use register_lazy() instead of register() for faster startup
- Tools are only imported when first accessed via load() or get_available()
- Use get_available_names() to list tools without importing them
- The global registry (get_registry()) is lazily created on first access

Example of lazy registration:
    registry = get_registry()
    registry.register_lazy(
        "my_tool",
        "mypackage.tools",
        "MyToolClass",
        ToolCategory.CORE
    )
    # Module not imported until:
    registry.load("my_tool")  # or registry.get_available("my_tool")
"""

from fastband.tools.base import (
    Tool,
    ToolDefinition,
    ToolParameter,
    ToolMetadata,
    ToolCategory,
    ToolResult,
)
from fastband.tools.registry import (
    ToolRegistry,
    get_registry,
    LazyToolSpec,  # For type hints
)
from fastband.tools.recommender import (
    ToolRecommender,
    ToolRecommendation,
    RecommendationResult,
    get_recommender,
    recommend_tools,
)


# =============================================================================
# LAZY LOADING SETUP
# =============================================================================
# For better startup performance, we register tool modules lazily.
# The actual tool classes are only imported when first accessed.

def _register_builtin_tools() -> None:
    """
    Register built-in tools for lazy loading.

    This is called on module import but doesn't actually import the tool modules.
    Tool classes are only imported when they're first loaded.
    """
    registry = get_registry()

    # Git tools
    git_tools = [
        ("git_status", "GitStatusTool"),
        ("git_commit", "GitCommitTool"),
        ("git_diff", "GitDiffTool"),
        ("git_log", "GitLogTool"),
        ("git_branch", "GitBranchTool"),
    ]
    for name, class_name in git_tools:
        registry.register_lazy(
            name,
            "fastband.tools.git",
            class_name,
            ToolCategory.GIT
        )

    # Ticket tools
    ticket_tools = [
        ("list_tickets", "ListTicketsTool"),
        ("get_ticket_details", "GetTicketDetailsTool"),
        ("create_ticket", "CreateTicketTool"),
        ("claim_ticket", "ClaimTicketTool"),
        ("complete_ticket_safely", "CompleteTicketSafelyTool"),
        ("update_ticket", "UpdateTicketTool"),
        ("search_tickets", "SearchTicketsTool"),
        ("add_ticket_comment", "AddTicketCommentTool"),
    ]
    for name, class_name in ticket_tools:
        registry.register_lazy(
            name,
            "fastband.tools.tickets",
            class_name,
            ToolCategory.TICKETS
        )


# Register on import (but don't import tool modules yet)
_register_builtin_tools()


# =============================================================================
# BACKWARDS COMPATIBILITY
# =============================================================================
# These imports are kept for backwards compatibility but may trigger
# eager loading. Prefer using the registry's lazy loading for new code.

# Optional git tools import - available when git module is loaded
try:
    from fastband.tools.git import (
        GitStatusTool,
        GitCommitTool,
        GitDiffTool,
        GitLogTool,
        GitBranchTool,
        GIT_TOOLS,
    )
    _git_available = True
except ImportError:
    _git_available = False
    GIT_TOOLS = []

# Ticket tools - always available
try:
    from fastband.tools.tickets import (
        ListTicketsTool,
        GetTicketDetailsTool,
        CreateTicketTool,
        ClaimTicketTool,
        CompleteTicketSafelyTool,
        UpdateTicketTool,
        SearchTicketsTool,
        AddTicketCommentTool,
        TICKET_TOOLS,
    )
    _tickets_available = True
except ImportError:
    _tickets_available = False
    TICKET_TOOLS = []

__all__ = [
    # Base
    "Tool",
    "ToolDefinition",
    "ToolParameter",
    "ToolMetadata",
    "ToolCategory",
    "ToolResult",
    # Registry
    "ToolRegistry",
    "get_registry",
    "LazyToolSpec",
    # Recommender
    "ToolRecommender",
    "ToolRecommendation",
    "RecommendationResult",
    "get_recommender",
    "recommend_tools",
    # Git tools (conditionally available)
    "GIT_TOOLS",
    # Ticket tools
    "TICKET_TOOLS",
]

# Add git tool classes to __all__ if available
if _git_available:
    __all__.extend([
        "GitStatusTool",
        "GitCommitTool",
        "GitDiffTool",
        "GitLogTool",
        "GitBranchTool",
    ])

# Add ticket tool classes to __all__ if available
if _tickets_available:
    __all__.extend([
        "ListTicketsTool",
        "GetTicketDetailsTool",
        "CreateTicketTool",
        "ClaimTicketTool",
        "CompleteTicketSafelyTool",
        "UpdateTicketTool",
        "SearchTicketsTool",
        "AddTicketCommentTool",
    ])

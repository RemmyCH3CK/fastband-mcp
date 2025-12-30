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
    ToolCategory,
    ToolDefinition,
    ToolMetadata,
    ToolParameter,
    ToolResult,
)
from fastband.tools.recommender import (
    RecommendationResult,
    ToolRecommendation,
    ToolRecommender,
    get_recommender,
    recommend_tools,
)
from fastband.tools.registry import (
    LazyToolSpec,  # For type hints
    ToolRegistry,
    get_registry,
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
        registry.register_lazy(name, "fastband.tools.git", class_name, ToolCategory.GIT)

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
        registry.register_lazy(name, "fastband.tools.tickets", class_name, ToolCategory.TICKETS)

    # Context/Semantic Search tools
    context_tools = [
        ("index_codebase", "IndexCodebaseTool"),
        ("semantic_search", "SemanticSearchTool"),
        ("index_status", "IndexStatusTool"),
    ]
    for name, class_name in context_tools:
        registry.register_lazy(name, "fastband.tools.context", class_name, ToolCategory.AI)

    # Agent onboarding tools
    agent_tools = [
        ("start_onboarding", "StartOnboardingTool"),
        ("acknowledge_document", "AcknowledgeDocumentTool"),
        ("complete_onboarding", "CompleteOnboardingTool"),
        ("get_onboarding_status", "GetOnboardingStatusTool"),
    ]
    for name, class_name in agent_tools:
        registry.register_lazy(name, "fastband.tools.agents", class_name, ToolCategory.CORE)


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
        GIT_TOOLS,
        GitBranchTool,
        GitCommitTool,
        GitDiffTool,
        GitLogTool,
        GitStatusTool,
    )

    _git_available = True
except ImportError:
    _git_available = False
    GIT_TOOLS = []

# Ticket tools - always available
try:
    from fastband.tools.tickets import (
        TICKET_TOOLS,
        AddTicketCommentTool,
        ClaimTicketTool,
        CompleteTicketSafelyTool,
        CreateTicketTool,
        GetTicketDetailsTool,
        ListTicketsTool,
        SearchTicketsTool,
        UpdateTicketTool,
    )

    _tickets_available = True
except ImportError:
    _tickets_available = False
    TICKET_TOOLS = []

# Agent onboarding tools
try:
    from fastband.tools.agents import (
        AGENT_TOOLS,
        AcknowledgeDocumentTool,
        CompleteOnboardingTool,
        GetOnboardingStatusTool,
        StartOnboardingTool,
    )

    _agents_available = True
except ImportError:
    _agents_available = False
    AGENT_TOOLS = []

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
    # Agent tools
    "AGENT_TOOLS",
]

# Add git tool classes to __all__ if available
if _git_available:
    __all__.extend(
        [
            "GitStatusTool",
            "GitCommitTool",
            "GitDiffTool",
            "GitLogTool",
            "GitBranchTool",
        ]
    )

# Add ticket tool classes to __all__ if available
if _tickets_available:
    __all__.extend(
        [
            "ListTicketsTool",
            "GetTicketDetailsTool",
            "CreateTicketTool",
            "ClaimTicketTool",
            "CompleteTicketSafelyTool",
            "UpdateTicketTool",
            "SearchTicketsTool",
            "AddTicketCommentTool",
        ]
    )

# Add agent tool classes to __all__ if available
if _agents_available:
    __all__.extend(
        [
            "StartOnboardingTool",
            "AcknowledgeDocumentTool",
            "CompleteOnboardingTool",
            "GetOnboardingStatusTool",
        ]
    )

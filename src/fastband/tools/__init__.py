"""
Fastband Tool Garage System.

Provides tool registration, loading, and execution for the MCP server.
"""

from fastband.tools.base import (
    Tool,
    ToolDefinition,
    ToolParameter,
    ToolMetadata,
    ToolCategory,
    ToolResult,
)
from fastband.tools.registry import ToolRegistry, get_registry
from fastband.tools.recommender import (
    ToolRecommender,
    ToolRecommendation,
    RecommendationResult,
    get_recommender,
    recommend_tools,
)

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

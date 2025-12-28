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
]

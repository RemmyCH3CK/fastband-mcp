"""
Tool Recommender - AI-powered tool recommendations.

Analyzes project context and usage patterns to recommend
relevant tools from the Tool Garage.
"""

import logging
from dataclasses import dataclass
from pathlib import Path

from fastband.core.detection import (
    Framework,
    Language,
    ProjectDetector,
    ProjectInfo,
    ProjectType,
)
from fastband.tools.base import Tool, ToolCategory

logger = logging.getLogger(__name__)


@dataclass
class ToolRecommendation:
    """A recommended tool with reasoning."""

    tool_name: str
    category: ToolCategory
    relevance_score: float  # 0.0 to 1.0
    reason: str
    priority: int  # 1 = high, 2 = medium, 3 = low


@dataclass
class RecommendationResult:
    """Result of tool recommendation analysis."""

    project_info: ProjectInfo | None
    recommendations: list[ToolRecommendation]
    already_loaded: list[str]
    total_available: int

    def get_by_priority(self, priority: int) -> list[ToolRecommendation]:
        """Get recommendations filtered by priority."""
        return [r for r in self.recommendations if r.priority == priority]

    def get_high_priority(self) -> list[ToolRecommendation]:
        """Get high priority recommendations."""
        return self.get_by_priority(1)


# Mapping from project detection types to tool categories
PROJECT_TYPE_TOOLS: dict[ProjectType, list[ToolCategory]] = {
    ProjectType.WEB_APP: [
        ToolCategory.WEB,
        ToolCategory.TESTING,
        ToolCategory.SCREENSHOTS,
    ],
    ProjectType.API_SERVICE: [
        ToolCategory.TESTING,
        ToolCategory.DEVOPS,
        ToolCategory.ANALYSIS,
    ],
    ProjectType.MOBILE_IOS: [
        ToolCategory.MOBILE,
        ToolCategory.TESTING,
        ToolCategory.SCREENSHOTS,
    ],
    ProjectType.MOBILE_ANDROID: [
        ToolCategory.MOBILE,
        ToolCategory.TESTING,
        ToolCategory.SCREENSHOTS,
    ],
    ProjectType.MOBILE_CROSS: [
        ToolCategory.MOBILE,
        ToolCategory.TESTING,
        ToolCategory.SCREENSHOTS,
    ],
    ProjectType.DESKTOP_ELECTRON: [
        ToolCategory.DESKTOP,
        ToolCategory.WEB,
        ToolCategory.TESTING,
    ],
    ProjectType.DESKTOP_NATIVE: [
        ToolCategory.DESKTOP,
        ToolCategory.TESTING,
    ],
    ProjectType.CLI_TOOL: [
        ToolCategory.TESTING,
        ToolCategory.DEVOPS,
    ],
    ProjectType.LIBRARY: [
        ToolCategory.TESTING,
        ToolCategory.ANALYSIS,
        ToolCategory.DEVOPS,
    ],
    ProjectType.MONOREPO: [
        ToolCategory.DEVOPS,
        ToolCategory.TESTING,
        ToolCategory.COORDINATION,
    ],
}

# Framework-specific tool recommendations
FRAMEWORK_TOOLS: dict[Framework, list[str]] = {
    Framework.FLASK: ["test_api", "debug_server"],
    Framework.DJANGO: ["test_api", "manage_django", "debug_server"],
    Framework.FASTAPI: ["test_api", "openapi_gen"],
    Framework.REACT: ["build_frontend", "test_components", "screenshot_page"],
    Framework.VUE: ["build_frontend", "test_components"],
    Framework.NEXTJS: ["build_frontend", "test_ssr"],
    Framework.REACT_NATIVE: ["mobile_build", "mobile_test", "device_screenshot"],
    Framework.FLUTTER: ["flutter_build", "flutter_test", "device_screenshot"],
    Framework.ELECTRON: ["electron_build", "electron_test"],
}

# Language-specific tool recommendations
LANGUAGE_TOOLS: dict[Language, list[str]] = {
    Language.PYTHON: ["pytest_run", "pylint_check", "mypy_check"],
    Language.JAVASCRIPT: ["npm_test", "eslint_check"],
    Language.TYPESCRIPT: ["npm_test", "tsc_check", "eslint_check"],
    Language.RUST: ["cargo_test", "cargo_clippy"],
    Language.GO: ["go_test", "go_vet"],
}


class ToolRecommender:
    """
    Recommends tools based on project context and usage patterns.

    Example:
        recommender = ToolRecommender()
        result = recommender.analyze("/path/to/project")

        for rec in result.get_high_priority():
            print(f"{rec.tool_name}: {rec.reason}")
    """

    def __init__(self, registry=None):
        """
        Initialize recommender.

        Args:
            registry: ToolRegistry instance (uses global if not provided)
        """
        self._registry = registry
        self._usage_stats: dict[str, int] = {}  # tool_name -> usage count
        self._project_detector = ProjectDetector()

    @property
    def registry(self):
        """Get the tool registry."""
        if self._registry is None:
            from fastband.tools.registry import get_registry

            self._registry = get_registry()
        return self._registry

    def analyze(self, path: Path | None = None) -> RecommendationResult:
        """
        Analyze project and recommend tools.

        Args:
            path: Project path (default: current directory)

        Returns:
            RecommendationResult with recommendations
        """
        # Detect project info
        try:
            project_info = self._project_detector.detect(path)
        except Exception as e:
            logger.warning(f"Could not detect project: {e}")
            project_info = None

        # Get currently loaded tools
        loaded_tools = {t.name for t in self.registry.get_active_tools()}
        available_tools = self.registry.get_available_tools()

        recommendations = []

        if project_info:
            # Recommend based on project type
            recommendations.extend(
                self._recommend_for_project_type(
                    project_info.primary_type,
                    available_tools,
                    loaded_tools,
                )
            )

            # Recommend based on frameworks
            for fw in project_info.frameworks:
                recommendations.extend(
                    self._recommend_for_framework(
                        fw.framework,
                        available_tools,
                        loaded_tools,
                    )
                )

            # Recommend based on language
            recommendations.extend(
                self._recommend_for_language(
                    project_info.primary_language,
                    available_tools,
                    loaded_tools,
                )
            )

        # Always recommend git tools if .git exists
        if path and (Path(path) / ".git").exists():
            recommendations.extend(
                self._recommend_category(
                    ToolCategory.GIT,
                    "Git repository detected",
                    available_tools,
                    loaded_tools,
                    priority=1,
                )
            )

        # Sort by relevance score
        recommendations.sort(key=lambda r: (-r.relevance_score, r.priority))

        # Remove duplicates (keep highest scoring)
        seen = set()
        unique_recommendations = []
        for rec in recommendations:
            if rec.tool_name not in seen:
                seen.add(rec.tool_name)
                unique_recommendations.append(rec)

        return RecommendationResult(
            project_info=project_info,
            recommendations=unique_recommendations,
            already_loaded=list(loaded_tools),
            total_available=len(available_tools),
        )

    def _recommend_for_project_type(
        self,
        project_type: ProjectType,
        available: list[Tool],
        loaded: set[str],
    ) -> list[ToolRecommendation]:
        """Recommend tools based on project type."""
        recommendations = []
        categories = PROJECT_TYPE_TOOLS.get(project_type, [])

        for category in categories:
            recommendations.extend(
                self._recommend_category(
                    category,
                    f"Recommended for {project_type.value} projects",
                    available,
                    loaded,
                    priority=2,
                )
            )

        return recommendations

    def _recommend_for_framework(
        self,
        framework: Framework,
        available: list[Tool],
        loaded: set[str],
    ) -> list[ToolRecommendation]:
        """Recommend tools based on framework."""
        recommendations = []
        tool_names = FRAMEWORK_TOOLS.get(framework, [])

        for tool in available:
            if tool.name in tool_names and tool.name not in loaded:
                recommendations.append(
                    ToolRecommendation(
                        tool_name=tool.name,
                        category=tool.category,
                        relevance_score=0.9,
                        reason=f"Optimized for {framework.value} development",
                        priority=1,
                    )
                )

        return recommendations

    def _recommend_for_language(
        self,
        language: Language,
        available: list[Tool],
        loaded: set[str],
    ) -> list[ToolRecommendation]:
        """Recommend tools based on language."""
        recommendations = []
        tool_names = LANGUAGE_TOOLS.get(language, [])

        for tool in available:
            if tool.name in tool_names and tool.name not in loaded:
                recommendations.append(
                    ToolRecommendation(
                        tool_name=tool.name,
                        category=tool.category,
                        relevance_score=0.8,
                        reason=f"Essential for {language.value} development",
                        priority=2,
                    )
                )

        return recommendations

    def _recommend_category(
        self,
        category: ToolCategory,
        reason: str,
        available: list[Tool],
        loaded: set[str],
        priority: int = 2,
    ) -> list[ToolRecommendation]:
        """Recommend all tools in a category."""
        recommendations = []

        for tool in available:
            if tool.category == category and tool.name not in loaded:
                # Check if tool has project type hints that match
                metadata = tool.definition.metadata
                relevance = 0.7

                if metadata.project_types:
                    relevance = 0.85

                recommendations.append(
                    ToolRecommendation(
                        tool_name=tool.name,
                        category=category,
                        relevance_score=relevance,
                        reason=reason,
                        priority=priority,
                    )
                )

        return recommendations

    def track_usage(self, tool_name: str) -> None:
        """
        Track tool usage for learning.

        Args:
            tool_name: Name of tool that was used
        """
        self._usage_stats[tool_name] = self._usage_stats.get(tool_name, 0) + 1

    def get_usage_stats(self) -> dict[str, int]:
        """Get tool usage statistics."""
        return dict(self._usage_stats)

    def get_frequently_used(self, min_uses: int = 5) -> list[str]:
        """Get frequently used tools."""
        return [name for name, count in self._usage_stats.items() if count >= min_uses]


# Global recommender instance
_recommender: ToolRecommender | None = None


def get_recommender() -> ToolRecommender:
    """Get the global tool recommender."""
    global _recommender
    if _recommender is None:
        _recommender = ToolRecommender()
    return _recommender


def recommend_tools(path: Path | None = None) -> RecommendationResult:
    """
    Convenience function to get tool recommendations.

    Args:
        path: Project path (default: current directory)

    Returns:
        RecommendationResult with recommendations
    """
    return get_recommender().analyze(path)

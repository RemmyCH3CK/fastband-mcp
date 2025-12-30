"""Tests for tool recommender."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from fastband.core.detection import (
    Framework,
    Language,
    ProjectType,
)
from fastband.tools.base import Tool, ToolCategory
from fastband.tools.recommender import (
    FRAMEWORK_TOOLS,
    LANGUAGE_TOOLS,
    PROJECT_TYPE_TOOLS,
    RecommendationResult,
    ToolRecommendation,
    ToolRecommender,
    get_recommender,
    recommend_tools,
)

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def python_flask_project(temp_dir):
    """Create a Python Flask project."""
    (temp_dir / "pyproject.toml").write_text("""
[project]
name = "flask-app"
version = "1.0.0"
dependencies = ["flask>=2.0"]
""")
    (temp_dir / "requirements.txt").write_text("flask>=2.0\n")

    src = temp_dir / "src"
    src.mkdir()
    (src / "app.py").write_text("from flask import Flask\napp = Flask(__name__)")

    return temp_dir


@pytest.fixture
def react_project(temp_dir):
    """Create a React project."""
    (temp_dir / "package.json").write_text(
        json.dumps({"name": "react-app", "dependencies": {"react": "^18.2.0"}})
    )
    (temp_dir / "package-lock.json").write_text("{}")

    src = temp_dir / "src"
    src.mkdir()
    (src / "App.jsx").write_text("export function App() {}")

    return temp_dir


@pytest.fixture
def git_project(temp_dir):
    """Create a project with git."""
    (temp_dir / ".git").mkdir()
    (temp_dir / "README.md").write_text("# Project")
    return temp_dir


@pytest.fixture
def mock_tool():
    """Create a mock tool for testing."""

    def _create_tool(name: str, category: ToolCategory):
        tool = MagicMock(spec=Tool)
        tool.name = name
        tool.category = category
        tool.definition = MagicMock()
        tool.definition.metadata = MagicMock()
        tool.definition.metadata.project_types = []
        return tool

    return _create_tool


@pytest.fixture
def mock_registry(mock_tool):
    """Create a mock registry with tools."""
    registry = MagicMock()

    # Create mock tools for different categories
    tools = [
        mock_tool("test_api", ToolCategory.TESTING),
        mock_tool("debug_server", ToolCategory.DEVOPS),
        mock_tool("build_frontend", ToolCategory.WEB),
        mock_tool("screenshot_page", ToolCategory.SCREENSHOTS),
        mock_tool("pytest_run", ToolCategory.TESTING),
        mock_tool("git_status", ToolCategory.GIT),
    ]

    registry.get_available_tools.return_value = tools
    registry.get_active_tools.return_value = []

    return registry


# =============================================================================
# DATACLASS TESTS
# =============================================================================


class TestToolRecommendation:
    """Tests for ToolRecommendation dataclass."""

    def test_create_recommendation(self):
        """Test creating a recommendation."""
        rec = ToolRecommendation(
            tool_name="pytest_run",
            category=ToolCategory.TESTING,
            relevance_score=0.9,
            reason="Essential for Python development",
            priority=1,
        )

        assert rec.tool_name == "pytest_run"
        assert rec.category == ToolCategory.TESTING
        assert rec.relevance_score == 0.9
        assert rec.reason == "Essential for Python development"
        assert rec.priority == 1

    def test_recommendation_priority_levels(self):
        """Test different priority levels."""
        high = ToolRecommendation("a", ToolCategory.TESTING, 0.9, "test", 1)
        medium = ToolRecommendation("b", ToolCategory.TESTING, 0.7, "test", 2)
        low = ToolRecommendation("c", ToolCategory.TESTING, 0.5, "test", 3)

        assert high.priority < medium.priority < low.priority


class TestRecommendationResult:
    """Tests for RecommendationResult dataclass."""

    def test_create_result(self):
        """Test creating a result."""
        result = RecommendationResult(
            project_info=None,
            recommendations=[],
            already_loaded=["tool1"],
            total_available=10,
        )

        assert result.project_info is None
        assert result.recommendations == []
        assert result.already_loaded == ["tool1"]
        assert result.total_available == 10

    def test_get_by_priority(self):
        """Test filtering by priority."""
        recs = [
            ToolRecommendation("a", ToolCategory.TESTING, 0.9, "test", 1),
            ToolRecommendation("b", ToolCategory.TESTING, 0.7, "test", 2),
            ToolRecommendation("c", ToolCategory.TESTING, 0.9, "test", 1),
            ToolRecommendation("d", ToolCategory.TESTING, 0.5, "test", 3),
        ]

        result = RecommendationResult(None, recs, [], 10)

        high_priority = result.get_by_priority(1)
        assert len(high_priority) == 2
        assert all(r.priority == 1 for r in high_priority)

        medium_priority = result.get_by_priority(2)
        assert len(medium_priority) == 1

    def test_get_high_priority(self):
        """Test getting high priority recommendations."""
        recs = [
            ToolRecommendation("a", ToolCategory.TESTING, 0.9, "test", 1),
            ToolRecommendation("b", ToolCategory.TESTING, 0.7, "test", 2),
        ]

        result = RecommendationResult(None, recs, [], 10)

        high = result.get_high_priority()
        assert len(high) == 1
        assert high[0].tool_name == "a"


# =============================================================================
# MAPPING TESTS
# =============================================================================


class TestMappings:
    """Tests for recommendation mappings."""

    def test_project_type_tools_mapping(self):
        """Test PROJECT_TYPE_TOOLS has expected mappings."""
        assert ProjectType.WEB_APP in PROJECT_TYPE_TOOLS
        assert ToolCategory.WEB in PROJECT_TYPE_TOOLS[ProjectType.WEB_APP]

        assert ProjectType.API_SERVICE in PROJECT_TYPE_TOOLS
        assert ToolCategory.TESTING in PROJECT_TYPE_TOOLS[ProjectType.API_SERVICE]

        assert ProjectType.CLI_TOOL in PROJECT_TYPE_TOOLS
        assert ProjectType.LIBRARY in PROJECT_TYPE_TOOLS

    def test_framework_tools_mapping(self):
        """Test FRAMEWORK_TOOLS has expected mappings."""
        assert Framework.FLASK in FRAMEWORK_TOOLS
        assert "test_api" in FRAMEWORK_TOOLS[Framework.FLASK]

        assert Framework.REACT in FRAMEWORK_TOOLS
        assert "build_frontend" in FRAMEWORK_TOOLS[Framework.REACT]

        assert Framework.FLUTTER in FRAMEWORK_TOOLS

    def test_language_tools_mapping(self):
        """Test LANGUAGE_TOOLS has expected mappings."""
        assert Language.PYTHON in LANGUAGE_TOOLS
        assert "pytest_run" in LANGUAGE_TOOLS[Language.PYTHON]

        assert Language.JAVASCRIPT in LANGUAGE_TOOLS
        assert Language.TYPESCRIPT in LANGUAGE_TOOLS
        assert Language.RUST in LANGUAGE_TOOLS


# =============================================================================
# TOOL RECOMMENDER TESTS
# =============================================================================


class TestToolRecommender:
    """Tests for ToolRecommender class."""

    def test_init_default_registry(self):
        """Test initialization with default registry."""
        recommender = ToolRecommender()
        assert recommender._registry is None
        assert recommender._usage_stats == {}

    def test_init_custom_registry(self, mock_registry):
        """Test initialization with custom registry."""
        recommender = ToolRecommender(registry=mock_registry)
        assert recommender._registry is mock_registry

    def test_registry_property_lazy_load(self, mock_registry):
        """Test registry property lazy loads."""
        recommender = ToolRecommender()

        # Patch at the import location inside the property
        with patch("fastband.tools.registry.get_registry", return_value=mock_registry):
            reg = recommender.registry
            assert reg is mock_registry

    def test_analyze_empty_project(self, temp_dir, mock_registry):
        """Test analyzing empty project."""
        recommender = ToolRecommender(registry=mock_registry)
        result = recommender.analyze(temp_dir)

        assert isinstance(result, RecommendationResult)
        assert result.project_info is not None
        assert result.total_available == 6  # Our mock has 6 tools

    def test_analyze_with_git(self, git_project, mock_registry):
        """Test analyzing project with git recommends git tools."""
        recommender = ToolRecommender(registry=mock_registry)
        result = recommender.analyze(git_project)

        git_recs = [r for r in result.recommendations if r.category == ToolCategory.GIT]
        assert len(git_recs) > 0

    def test_analyze_excludes_loaded_tools(self, temp_dir, mock_registry, mock_tool):
        """Test that already loaded tools are excluded from recommendations."""
        # Mark one tool as loaded
        loaded_tool = mock_tool("git_status", ToolCategory.GIT)
        mock_registry.get_active_tools.return_value = [loaded_tool]

        recommender = ToolRecommender(registry=mock_registry)

        # Create git project to trigger git recommendations
        (temp_dir / ".git").mkdir()

        result = recommender.analyze(temp_dir)

        # git_status should be in already_loaded, not recommendations
        assert "git_status" in result.already_loaded
        rec_names = [r.tool_name for r in result.recommendations]
        assert "git_status" not in rec_names

    def test_analyze_sorts_by_relevance(self, temp_dir, mock_registry):
        """Test recommendations are sorted by relevance."""
        recommender = ToolRecommender(registry=mock_registry)
        result = recommender.analyze(temp_dir)

        if len(result.recommendations) > 1:
            scores = [r.relevance_score for r in result.recommendations]
            # Should be sorted descending
            assert scores == sorted(scores, reverse=True)

    def test_analyze_removes_duplicates(self, temp_dir, mock_registry):
        """Test duplicate recommendations are removed."""
        recommender = ToolRecommender(registry=mock_registry)
        result = recommender.analyze(temp_dir)

        tool_names = [r.tool_name for r in result.recommendations]
        assert len(tool_names) == len(set(tool_names))


class TestUsageTracking:
    """Tests for usage tracking."""

    def test_track_usage(self):
        """Test tracking tool usage."""
        recommender = ToolRecommender()

        recommender.track_usage("pytest_run")
        recommender.track_usage("pytest_run")
        recommender.track_usage("git_status")

        stats = recommender.get_usage_stats()
        assert stats["pytest_run"] == 2
        assert stats["git_status"] == 1

    def test_get_usage_stats_empty(self):
        """Test getting stats when empty."""
        recommender = ToolRecommender()
        assert recommender.get_usage_stats() == {}

    def test_get_frequently_used(self):
        """Test getting frequently used tools."""
        recommender = ToolRecommender()

        for _ in range(10):
            recommender.track_usage("frequent_tool")

        for _ in range(3):
            recommender.track_usage("rare_tool")

        frequent = recommender.get_frequently_used(min_uses=5)
        assert "frequent_tool" in frequent
        assert "rare_tool" not in frequent

    def test_get_frequently_used_empty(self):
        """Test getting frequent tools when none qualify."""
        recommender = ToolRecommender()
        recommender.track_usage("tool1")

        frequent = recommender.get_frequently_used(min_uses=5)
        assert frequent == []


# =============================================================================
# CONVENIENCE FUNCTION TESTS
# =============================================================================


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_get_recommender_singleton(self):
        """Test get_recommender returns singleton."""
        rec1 = get_recommender()
        rec2 = get_recommender()
        assert rec1 is rec2

    def test_recommend_tools_function(self, temp_dir):
        """Test recommend_tools convenience function."""
        result = recommend_tools(temp_dir)

        assert isinstance(result, RecommendationResult)
        assert result.project_info is not None


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestRecommenderIntegration:
    """Integration tests with real detection."""

    def test_python_project_recommendations(self, python_flask_project, mock_registry, mock_tool):
        """Test recommendations for Python Flask project."""
        # Add Python-specific tools to mock registry
        mock_registry.get_available_tools.return_value = [
            mock_tool("pytest_run", ToolCategory.TESTING),
            mock_tool("test_api", ToolCategory.TESTING),
            mock_tool("debug_server", ToolCategory.DEVOPS),
        ]

        recommender = ToolRecommender(registry=mock_registry)
        result = recommender.analyze(python_flask_project)

        # Should detect Python
        assert result.project_info is not None
        assert result.project_info.primary_language == Language.PYTHON

        # Should have recommendations (with mock tools available)
        assert len(result.recommendations) > 0

    def test_react_project_recommendations(self, react_project, mock_registry, mock_tool):
        """Test recommendations for React project."""
        # Add JS-specific tools to mock registry
        mock_registry.get_available_tools.return_value = [
            mock_tool("build_frontend", ToolCategory.WEB),
            mock_tool("test_components", ToolCategory.TESTING),
            mock_tool("screenshot_page", ToolCategory.SCREENSHOTS),
        ]

        recommender = ToolRecommender(registry=mock_registry)
        result = recommender.analyze(react_project)

        # Should detect JavaScript/TypeScript
        assert result.project_info is not None
        assert result.project_info.primary_language in [Language.JAVASCRIPT, Language.TYPESCRIPT]

        # Should have recommendations (with mock tools available)
        assert len(result.recommendations) > 0

    def test_empty_project_still_works(self, temp_dir):
        """Test that empty project doesn't crash."""
        result = recommend_tools(temp_dir)

        assert result.project_info is not None
        # Empty project may have no recommendations, but shouldn't crash
        assert isinstance(result.recommendations, list)

"""Tests for the Tool Selection Wizard Step."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from fastband.core.config import FastbandConfig
from fastband.tools.base import (
    Tool,
    ToolCategory,
    ToolDefinition,
    ToolMetadata,
    ToolResult,
)
from fastband.tools.recommender import (
    RecommendationResult,
    ToolRecommendation,
    ToolRecommender,
)
from fastband.wizard.base import StepStatus, WizardContext
from fastband.wizard.steps.tools import ToolSelectionStep

# =============================================================================
# TEST FIXTURES
# =============================================================================


@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def wizard_context(temp_dir):
    """Create a wizard context for testing."""
    return WizardContext(
        project_path=temp_dir,
        config=FastbandConfig(),
        interactive=True,
    )


@pytest.fixture
def non_interactive_context(temp_dir):
    """Create a non-interactive wizard context."""
    return WizardContext(
        project_path=temp_dir,
        config=FastbandConfig(),
        interactive=False,
    )


@pytest.fixture
def mock_recommendations():
    """Create mock tool recommendations."""
    return [
        ToolRecommendation(
            tool_name="pytest_run",
            category=ToolCategory.TESTING,
            relevance_score=0.9,
            reason="Essential for Python development",
            priority=1,
        ),
        ToolRecommendation(
            tool_name="pylint_check",
            category=ToolCategory.ANALYSIS,
            relevance_score=0.8,
            reason="Code quality for Python projects",
            priority=2,
        ),
        ToolRecommendation(
            tool_name="git_status",
            category=ToolCategory.GIT,
            relevance_score=0.85,
            reason="Git repository detected",
            priority=1,
        ),
        ToolRecommendation(
            tool_name="build_frontend",
            category=ToolCategory.WEB,
            relevance_score=0.7,
            reason="Recommended for web_app projects",
            priority=2,
        ),
    ]


@pytest.fixture
def mock_recommender(mock_recommendations):
    """Create a mock ToolRecommender."""
    recommender = MagicMock(spec=ToolRecommender)
    recommender.analyze.return_value = RecommendationResult(
        project_info=None,
        recommendations=mock_recommendations,
        already_loaded=[],
        total_available=10,
    )
    return recommender


class MockTool(Tool):
    """Mock tool for testing."""

    def __init__(
        self,
        name: str,
        category: ToolCategory = ToolCategory.CORE,
        conflicts_with: list = None,
        requires_tools: list = None,
    ):
        self._name = name
        self._category = category
        self._conflicts_with = conflicts_with or []
        self._requires_tools = requires_tools or []

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            metadata=ToolMetadata(
                name=self._name,
                description=f"Mock tool: {self._name}",
                category=self._category,
                conflicts_with=self._conflicts_with,
                requires_tools=self._requires_tools,
            ),
            parameters=[],
        )

    async def execute(self, **kwargs) -> ToolResult:
        return ToolResult(success=True, data={"tool": self._name})


# =============================================================================
# TOOL SELECTION STEP PROPERTY TESTS
# =============================================================================


class TestToolSelectionStepProperties:
    """Tests for ToolSelectionStep properties."""

    def test_name_property(self):
        """Test name property returns 'tools'."""
        step = ToolSelectionStep()
        assert step.name == "tools"

    def test_title_property(self):
        """Test title property returns 'Tool Selection'."""
        step = ToolSelectionStep()
        assert step.title == "Tool Selection"

    def test_description_property(self):
        """Test description property is set."""
        step = ToolSelectionStep()
        assert step.description != ""
        assert "tool" in step.description.lower()

    def test_required_property(self):
        """Test required property is False."""
        step = ToolSelectionStep()
        assert step.required is False

    def test_initial_status(self):
        """Test initial status is PENDING."""
        step = ToolSelectionStep()
        assert step.status == StepStatus.PENDING

    def test_custom_recommender(self, mock_recommender):
        """Test that custom recommender can be provided."""
        step = ToolSelectionStep(recommender=mock_recommender)
        assert step.recommender is mock_recommender

    def test_lazy_recommender_initialization(self):
        """Test that recommender is lazily initialized."""
        step = ToolSelectionStep()
        # Access recommender property
        recommender = step.recommender
        assert recommender is not None
        assert isinstance(recommender, ToolRecommender)


# =============================================================================
# TOOL RECOMMENDATIONS TESTS
# =============================================================================


class TestToolRecommendations:
    """Tests for tool recommendations with mocked recommender."""

    @pytest.mark.asyncio
    async def test_recommendations_called(self, non_interactive_context, mock_recommender):
        """Test that recommender.analyze is called with project path."""
        step = ToolSelectionStep(recommender=mock_recommender)

        await step.execute(non_interactive_context)

        mock_recommender.analyze.assert_called_once_with(non_interactive_context.project_path)

    @pytest.mark.asyncio
    async def test_recommendations_processed(self, non_interactive_context, mock_recommender):
        """Test that recommendations are properly processed."""
        step = ToolSelectionStep(recommender=mock_recommender)

        result = await step.execute(non_interactive_context)

        assert result.success is True
        assert "selected_tools" in result.data
        assert len(result.data["selected_tools"]) == 4

    @pytest.mark.asyncio
    async def test_empty_recommendations(self, non_interactive_context):
        """Test handling of empty recommendations."""
        mock_recommender = MagicMock(spec=ToolRecommender)
        mock_recommender.analyze.return_value = RecommendationResult(
            project_info=None,
            recommendations=[],
            already_loaded=[],
            total_available=0,
        )

        step = ToolSelectionStep(recommender=mock_recommender)
        result = await step.execute(non_interactive_context)

        assert result.success is True
        assert result.data["selected_tools"] == []

    @pytest.mark.asyncio
    async def test_recommendation_categories(self, non_interactive_context, mock_recommendations):
        """Test that recommendations preserve categories."""
        mock_recommender = MagicMock(spec=ToolRecommender)
        mock_recommender.analyze.return_value = RecommendationResult(
            project_info=None,
            recommendations=mock_recommendations,
            already_loaded=[],
            total_available=10,
        )

        step = ToolSelectionStep(recommender=mock_recommender)
        result = await step.execute(non_interactive_context)

        # All recommendations should be in selected tools
        expected_tools = {rec.tool_name for rec in mock_recommendations}
        selected_tools = set(result.data["selected_tools"])
        assert selected_tools == expected_tools


# =============================================================================
# TOOL SELECTION TESTS
# =============================================================================


class TestToolSelection:
    """Tests for tool selection functionality."""

    @pytest.mark.asyncio
    async def test_selected_tools_saved_to_context(self, non_interactive_context, mock_recommender):
        """Test that selected tools are saved to context."""
        step = ToolSelectionStep(recommender=mock_recommender)

        await step.execute(non_interactive_context)

        assert len(non_interactive_context.selected_tools) == 4
        assert "pytest_run" in non_interactive_context.selected_tools
        assert "pylint_check" in non_interactive_context.selected_tools

    @pytest.mark.asyncio
    async def test_selected_tools_saved_to_config(self, non_interactive_context, mock_recommender):
        """Test that selected tools are saved to config.tools."""
        step = ToolSelectionStep(recommender=mock_recommender)

        await step.execute(non_interactive_context)

        assert len(non_interactive_context.config.tools) == 4
        assert "pytest_run" in non_interactive_context.config.tools

    @pytest.mark.asyncio
    async def test_step_result_data(self, non_interactive_context, mock_recommender):
        """Test that step result contains correct data."""
        step = ToolSelectionStep(recommender=mock_recommender)

        result = await step.execute(non_interactive_context)

        assert result.success is True
        assert "selected_tools" in result.data
        assert "mode" in result.data

    def test_group_by_category(self, mock_recommendations):
        """Test _group_by_category method."""
        step = ToolSelectionStep()

        grouped = step._group_by_category(mock_recommendations)

        assert ToolCategory.TESTING in grouped
        assert ToolCategory.ANALYSIS in grouped
        assert ToolCategory.GIT in grouped
        assert ToolCategory.WEB in grouped

        assert len(grouped[ToolCategory.TESTING]) == 1
        assert grouped[ToolCategory.TESTING][0].tool_name == "pytest_run"


# =============================================================================
# NON-INTERACTIVE MODE TESTS
# =============================================================================


class TestNonInteractiveMode:
    """Tests for non-interactive mode."""

    @pytest.mark.asyncio
    async def test_accepts_all_recommendations(self, non_interactive_context, mock_recommender):
        """Test that non-interactive mode accepts all recommended tools."""
        step = ToolSelectionStep(recommender=mock_recommender)

        result = await step.execute(non_interactive_context)

        assert result.success is True
        assert result.data["mode"] == "non-interactive"
        assert len(result.data["selected_tools"]) == 4

    @pytest.mark.asyncio
    async def test_no_prompts_in_non_interactive(self, non_interactive_context, mock_recommender):
        """Test that no user prompts occur in non-interactive mode."""
        step = ToolSelectionStep(recommender=mock_recommender)

        # This should complete without requiring any user input
        result = await step.execute(non_interactive_context)

        assert result.success is True

    @pytest.mark.asyncio
    async def test_context_interactive_false(self, temp_dir, mock_recommender):
        """Test behavior when context.interactive is False."""
        context = WizardContext(
            project_path=temp_dir,
            config=FastbandConfig(),
            interactive=False,
        )
        step = ToolSelectionStep(recommender=mock_recommender)

        result = await step.execute(context)

        # Should not require user interaction
        assert result.success is True
        assert result.data["mode"] == "non-interactive"

    @pytest.mark.asyncio
    async def test_success_message_in_result(self, non_interactive_context, mock_recommender):
        """Test that success message is included in result."""
        step = ToolSelectionStep(recommender=mock_recommender)

        result = await step.execute(non_interactive_context)

        assert result.message != ""
        assert "4" in result.message or "tool" in result.message.lower()


# =============================================================================
# TOOL COMPATIBILITY VALIDATION TESTS
# =============================================================================


class TestToolCompatibilityValidation:
    """Tests for tool compatibility validation."""

    def test_no_conflicts_valid(self):
        """Test validation passes when there are no conflicts."""
        step = ToolSelectionStep()

        with patch("fastband.tools.registry.get_registry") as mock_get_registry:
            mock_registry = MagicMock()
            mock_registry.get_available.return_value = MockTool("tool_a")
            mock_get_registry.return_value = mock_registry

            result = step._validate_tool_compatibility(["tool_a"], [])

            assert result["valid"] is True

    def test_conflict_detected(self):
        """Test validation detects tool conflicts."""
        step = ToolSelectionStep()

        with patch("fastband.tools.registry.get_registry") as mock_get_registry:
            mock_registry = MagicMock()

            # tool_a conflicts with tool_b
            tool_a = MockTool("tool_a", conflicts_with=["tool_b"])
            tool_b = MockTool("tool_b")

            mock_registry.get_available.side_effect = lambda name: {
                "tool_a": tool_a,
                "tool_b": tool_b,
            }.get(name)
            mock_get_registry.return_value = mock_registry

            result = step._validate_tool_compatibility(["tool_a", "tool_b"], [])

            assert result["valid"] is False
            assert "conflicts" in result["message"].lower()
            assert len(result["conflicts"]) == 1

    def test_missing_dependency_detected(self):
        """Test validation detects missing dependencies."""
        step = ToolSelectionStep()

        with patch("fastband.tools.registry.get_registry") as mock_get_registry:
            mock_registry = MagicMock()

            # tool_a requires tool_c
            tool_a = MockTool("tool_a", requires_tools=["tool_c"])
            tool_b = MockTool("tool_b")

            mock_registry.get_available.side_effect = lambda name: {
                "tool_a": tool_a,
                "tool_b": tool_b,
            }.get(name)
            mock_get_registry.return_value = mock_registry

            result = step._validate_tool_compatibility(["tool_a", "tool_b"], [])

            assert result["valid"] is False
            assert (
                "dependencies" in result["message"].lower()
                or "requires" in result["message"].lower()
            )
            assert len(result["missing_deps"]) == 1

    def test_dependency_in_already_loaded(self):
        """Test validation passes when dependency is already loaded."""
        step = ToolSelectionStep()

        with patch("fastband.tools.registry.get_registry") as mock_get_registry:
            mock_registry = MagicMock()

            # tool_a requires tool_c (which is already loaded)
            tool_a = MockTool("tool_a", requires_tools=["tool_c"])

            mock_registry.get_available.side_effect = lambda name: {
                "tool_a": tool_a,
            }.get(name)
            mock_get_registry.return_value = mock_registry

            result = step._validate_tool_compatibility(["tool_a"], ["tool_c"])

            assert result["valid"] is True

    def test_unknown_tool_ignored(self):
        """Test that unknown tools are ignored in validation."""
        step = ToolSelectionStep()

        with patch("fastband.tools.registry.get_registry") as mock_get_registry:
            mock_registry = MagicMock()
            mock_registry.get_available.return_value = None  # Tool not found
            mock_get_registry.return_value = mock_registry

            result = step._validate_tool_compatibility(["unknown_tool"], [])

            assert result["valid"] is True


# =============================================================================
# DISPLAY TESTS
# =============================================================================


class TestDisplayMethods:
    """Tests for display-related methods."""

    def test_display_category_table_no_error(self, mock_recommendations, capsys):
        """Test that _display_category_table doesn't raise errors."""
        step = ToolSelectionStep()

        testing_tools = [r for r in mock_recommendations if r.category == ToolCategory.TESTING]
        recommended_names = {"pytest_run"}

        # Should not raise
        step._display_category_table(ToolCategory.TESTING, testing_tools, recommended_names)

    def test_display_tool_categories_no_error(self, mock_recommendations):
        """Test that _display_tool_categories doesn't raise errors."""
        step = ToolSelectionStep()

        grouped = step._group_by_category(mock_recommendations)
        recommended_names = {"pytest_run", "pylint_check"}

        # Should not raise
        step._display_tool_categories(grouped, recommended_names)

    def test_display_empty_categories(self):
        """Test display with empty category dictionary."""
        step = ToolSelectionStep()

        # Should not raise
        step._display_tool_categories({}, set())


# =============================================================================
# STEP VALIDATION TESTS
# =============================================================================


class TestStepValidation:
    """Tests for step validation."""

    @pytest.mark.asyncio
    async def test_validate_returns_true(self, wizard_context):
        """Test that validate returns True."""
        step = ToolSelectionStep()

        result = await step.validate(wizard_context)

        assert result is True

    @pytest.mark.asyncio
    async def test_validate_initializes_selected_tools(self, wizard_context):
        """Test that validate initializes selected_tools if None."""
        step = ToolSelectionStep()
        wizard_context.selected_tools = None

        await step.validate(wizard_context)

        assert wizard_context.selected_tools == []

    @pytest.mark.asyncio
    async def test_validate_preserves_existing_selection(self, wizard_context):
        """Test that validate preserves existing selections."""
        step = ToolSelectionStep()
        wizard_context.selected_tools = ["tool_a", "tool_b"]

        await step.validate(wizard_context)

        assert wizard_context.selected_tools == ["tool_a", "tool_b"]


# =============================================================================
# EDGE CASES
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_large_number_of_recommendations(self, non_interactive_context):
        """Test handling of many recommendations."""
        # Create 50 recommendations
        recommendations = [
            ToolRecommendation(
                tool_name=f"tool_{i}",
                category=ToolCategory.CORE,
                relevance_score=0.5,
                reason=f"Reason {i}",
                priority=2,
            )
            for i in range(50)
        ]

        mock_recommender = MagicMock(spec=ToolRecommender)
        mock_recommender.analyze.return_value = RecommendationResult(
            project_info=None,
            recommendations=recommendations,
            already_loaded=[],
            total_available=50,
        )

        step = ToolSelectionStep(recommender=mock_recommender)
        result = await step.execute(non_interactive_context)

        assert result.success is True
        assert len(result.data["selected_tools"]) == 50

    @pytest.mark.asyncio
    async def test_duplicate_tool_names_in_recommendations(self, non_interactive_context):
        """Test handling when recommendations have duplicate names."""
        # This shouldn't happen in practice, but test defensively
        recommendations = [
            ToolRecommendation(
                tool_name="same_tool",
                category=ToolCategory.CORE,
                relevance_score=0.9,
                reason="Reason 1",
                priority=1,
            ),
            ToolRecommendation(
                tool_name="same_tool",
                category=ToolCategory.CORE,
                relevance_score=0.8,
                reason="Reason 2",
                priority=2,
            ),
        ]

        mock_recommender = MagicMock(spec=ToolRecommender)
        mock_recommender.analyze.return_value = RecommendationResult(
            project_info=None,
            recommendations=recommendations,
            already_loaded=[],
            total_available=2,
        )

        step = ToolSelectionStep(recommender=mock_recommender)
        result = await step.execute(non_interactive_context)

        # Should handle duplicates gracefully
        assert result.success is True

    @pytest.mark.asyncio
    async def test_special_characters_in_tool_names(self, non_interactive_context):
        """Test handling of special characters in tool names."""
        recommendations = [
            ToolRecommendation(
                tool_name="tool-with-dashes",
                category=ToolCategory.CORE,
                relevance_score=0.9,
                reason="Tool with dashes",
                priority=1,
            ),
            ToolRecommendation(
                tool_name="tool_with_underscores",
                category=ToolCategory.CORE,
                relevance_score=0.8,
                reason="Tool with underscores",
                priority=1,
            ),
        ]

        mock_recommender = MagicMock(spec=ToolRecommender)
        mock_recommender.analyze.return_value = RecommendationResult(
            project_info=None,
            recommendations=recommendations,
            already_loaded=[],
            total_available=2,
        )

        step = ToolSelectionStep(recommender=mock_recommender)
        result = await step.execute(non_interactive_context)

        assert result.success is True
        assert "tool-with-dashes" in result.data["selected_tools"]
        assert "tool_with_underscores" in result.data["selected_tools"]

    @pytest.mark.asyncio
    async def test_all_categories_present(self, non_interactive_context):
        """Test that all ToolCategory values can be handled."""
        recommendations = [
            ToolRecommendation(
                tool_name=f"{cat.value}_tool",
                category=cat,
                relevance_score=0.8,
                reason=f"Test for {cat.value}",
                priority=2,
            )
            for cat in ToolCategory
        ]

        mock_recommender = MagicMock(spec=ToolRecommender)
        mock_recommender.analyze.return_value = RecommendationResult(
            project_info=None,
            recommendations=recommendations,
            already_loaded=[],
            total_available=len(ToolCategory),
        )

        step = ToolSelectionStep(recommender=mock_recommender)
        result = await step.execute(non_interactive_context)

        assert result.success is True
        assert len(result.data["selected_tools"]) == len(ToolCategory)


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestIntegration:
    """Integration tests for ToolSelectionStep."""

    @pytest.mark.asyncio
    async def test_full_non_interactive_flow(self, temp_dir):
        """Test complete non-interactive flow with real recommender."""
        context = WizardContext(
            project_path=temp_dir,
            config=FastbandConfig(),
            interactive=False,
        )

        # Use real recommender (will analyze temp_dir which is empty)
        step = ToolSelectionStep()

        result = await step.execute(context)

        # Should succeed even with no recommendations
        assert result.success is True
        assert isinstance(context.selected_tools, list)
        assert isinstance(context.config.tools, list)

    @pytest.mark.asyncio
    async def test_step_status_changes(self, non_interactive_context, mock_recommender):
        """Test that step status can be changed."""
        step = ToolSelectionStep(recommender=mock_recommender)

        assert step.status == StepStatus.PENDING

        step.status = StepStatus.IN_PROGRESS
        assert step.status == StepStatus.IN_PROGRESS

        await step.execute(non_interactive_context)

        step.status = StepStatus.COMPLETED
        assert step.status == StepStatus.COMPLETED

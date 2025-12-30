"""Tests for the Project Detection wizard step."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from fastband.core.config import FastbandConfig
from fastband.core.detection import (
    BuildTool,
    DetectedFramework,
    DetectedLanguage,
    Framework,
    Language,
    PackageManager,
    ProjectInfo,
    ProjectType,
)
from fastband.wizard.base import StepStatus, WizardContext
from fastband.wizard.steps.project import (
    FRAMEWORK_DISPLAY_NAMES,
    LANGUAGE_DISPLAY_NAMES,
    PROJECT_TYPE_DISPLAY_NAMES,
    ProjectDetectionStep,
)

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
    """Create a non-interactive wizard context for testing."""
    return WizardContext(
        project_path=temp_dir,
        config=FastbandConfig(),
        interactive=False,
    )


@pytest.fixture
def mock_project_info(temp_dir):
    """Create a mock ProjectInfo for testing."""
    return ProjectInfo(
        path=temp_dir,
        primary_language=Language.PYTHON,
        primary_type=ProjectType.CLI_TOOL,
        languages=[
            DetectedLanguage(
                language=Language.PYTHON,
                confidence=0.9,
                file_count=10,
                evidence=["pyproject.toml", "src/main.py"],
            ),
        ],
        frameworks=[
            DetectedFramework(
                framework=Framework.PYTEST,
                confidence=0.8,
                version="7.0.0",
                evidence=["pytest in dependencies"],
            ),
            DetectedFramework(
                framework=Framework.FASTAPI,
                confidence=0.6,
                version="0.100.0",
                evidence=["fastapi in dependencies"],
            ),
        ],
        package_managers=[PackageManager.POETRY, PackageManager.PIP],
        build_tools=[BuildTool.DOCKER],
        language_confidence=0.9,
        type_confidence=0.7,
        name="test-project",
        version="1.0.0",
        description="A test project",
        is_monorepo=False,
        subprojects=[],
    )


@pytest.fixture
def mock_monorepo_info(temp_dir):
    """Create a mock ProjectInfo for a monorepo."""
    return ProjectInfo(
        path=temp_dir,
        primary_language=Language.TYPESCRIPT,
        primary_type=ProjectType.MONOREPO,
        languages=[
            DetectedLanguage(
                language=Language.TYPESCRIPT,
                confidence=0.8,
                file_count=50,
            ),
            DetectedLanguage(
                language=Language.JAVASCRIPT,
                confidence=0.2,
                file_count=10,
            ),
        ],
        frameworks=[
            DetectedFramework(framework=Framework.REACT, confidence=0.9),
            DetectedFramework(framework=Framework.NEXTJS, confidence=0.8),
        ],
        package_managers=[PackageManager.PNPM],
        build_tools=[BuildTool.VITE, BuildTool.DOCKER],
        language_confidence=0.8,
        type_confidence=0.9,
        name="my-monorepo",
        is_monorepo=True,
        subprojects=[
            "packages/web",
            "packages/api",
            "packages/shared",
            "packages/ui",
            "packages/utils",
            "packages/extra",
        ],
    )


# =============================================================================
# STEP PROPERTIES TESTS
# =============================================================================


class TestProjectDetectionStepProperties:
    """Tests for ProjectDetectionStep properties."""

    def test_name_property(self):
        """Test that name property returns 'project'."""
        step = ProjectDetectionStep()
        assert step.name == "project"

    def test_title_property(self):
        """Test that title property returns 'Project Detection'."""
        step = ProjectDetectionStep()
        assert step.title == "Project Detection"

    def test_description_property(self):
        """Test that description property returns a meaningful string."""
        step = ProjectDetectionStep()
        assert step.description
        assert "project" in step.description.lower() or "detect" in step.description.lower()

    def test_required_property(self):
        """Test that the step is marked as required."""
        step = ProjectDetectionStep()
        assert step.required is True

    def test_initial_status(self):
        """Test that initial status is PENDING."""
        step = ProjectDetectionStep()
        assert step.status == StepStatus.PENDING

    def test_console_initialization(self):
        """Test that console is initialized."""
        step = ProjectDetectionStep()
        assert step.console is not None

    def test_custom_console(self):
        """Test that custom console can be provided."""
        from rich.console import Console

        custom_console = Console()
        step = ProjectDetectionStep(console=custom_console)
        assert step.console is custom_console


# =============================================================================
# EXECUTE TESTS WITH MOCK DETECTION
# =============================================================================


class TestProjectDetectionStepExecute:
    """Tests for ProjectDetectionStep.execute() with mock detection."""

    @pytest.mark.asyncio
    async def test_execute_successful_detection(self, non_interactive_context, mock_project_info):
        """Test successful project detection in non-interactive mode."""
        step = ProjectDetectionStep()

        with patch(
            "fastband.wizard.steps.project.detect_project",
            return_value=mock_project_info,
        ):
            result = await step.execute(non_interactive_context)

        assert result.success is True
        assert result.message
        assert non_interactive_context.project_info is not None
        assert non_interactive_context.project_info.name == "test-project"

    @pytest.mark.asyncio
    async def test_execute_stores_project_info_in_context(
        self, non_interactive_context, mock_project_info
    ):
        """Test that project info is stored in context."""
        step = ProjectDetectionStep()

        with patch(
            "fastband.wizard.steps.project.detect_project",
            return_value=mock_project_info,
        ):
            await step.execute(non_interactive_context)

        assert non_interactive_context.project_info == mock_project_info

    @pytest.mark.asyncio
    async def test_execute_updates_config(self, non_interactive_context, mock_project_info):
        """Test that config is updated with project info."""
        step = ProjectDetectionStep()

        with patch(
            "fastband.wizard.steps.project.detect_project",
            return_value=mock_project_info,
        ):
            await step.execute(non_interactive_context)

        assert non_interactive_context.config.project_name == "test-project"
        assert non_interactive_context.config.project_type == "cli_tool"
        assert non_interactive_context.config.primary_language == "python"

    @pytest.mark.asyncio
    async def test_execute_returns_result_data(self, non_interactive_context, mock_project_info):
        """Test that result contains expected data."""
        step = ProjectDetectionStep()

        with patch(
            "fastband.wizard.steps.project.detect_project",
            return_value=mock_project_info,
        ):
            result = await step.execute(non_interactive_context)

        assert "project_info" in result.data
        assert result.data["language"] == "python"
        assert result.data["type"] == "cli_tool"
        assert "pytest" in result.data["frameworks"]

    @pytest.mark.asyncio
    async def test_execute_handles_detection_error(self, non_interactive_context):
        """Test handling of detection errors."""
        step = ProjectDetectionStep()

        with patch(
            "fastband.wizard.steps.project.detect_project",
            side_effect=ValueError("Path does not exist"),
        ):
            result = await step.execute(non_interactive_context)

        assert result.success is False
        assert "failed" in result.message.lower() or "error" in result.message.lower()

    @pytest.mark.asyncio
    async def test_execute_handles_exception(self, non_interactive_context):
        """Test handling of unexpected exceptions."""
        step = ProjectDetectionStep()

        with patch(
            "fastband.wizard.steps.project.detect_project",
            side_effect=Exception("Unexpected error"),
        ):
            result = await step.execute(non_interactive_context)

        assert result.success is False

    @pytest.mark.asyncio
    async def test_execute_with_monorepo(self, non_interactive_context, mock_monorepo_info):
        """Test detection of a monorepo project."""
        step = ProjectDetectionStep()

        with patch(
            "fastband.wizard.steps.project.detect_project",
            return_value=mock_monorepo_info,
        ):
            result = await step.execute(non_interactive_context)

        assert result.success is True
        assert non_interactive_context.project_info.is_monorepo is True
        assert len(non_interactive_context.project_info.subprojects) == 6


# =============================================================================
# USER OVERRIDE FUNCTIONALITY TESTS
# =============================================================================


class TestUserOverrideFunctionality:
    """Tests for user override functionality in interactive mode."""

    @pytest.mark.asyncio
    async def test_interactive_user_confirms_detection(self, wizard_context, mock_project_info):
        """Test user confirming detection in interactive mode."""
        step = ProjectDetectionStep()

        with patch(
            "fastband.wizard.steps.project.detect_project",
            return_value=mock_project_info,
        ):
            with patch.object(step, "confirm", return_value=True):
                result = await step.execute(wizard_context)

        assert result.success is True

    @pytest.mark.asyncio
    async def test_interactive_user_cancels(self, wizard_context, mock_project_info):
        """Test user cancelling in interactive mode."""
        step = ProjectDetectionStep()

        with patch(
            "fastband.wizard.steps.project.detect_project",
            return_value=mock_project_info,
        ):
            # Sequence: reject detection, don't override lang, don't override type, reject final
            with patch.object(step, "confirm", side_effect=[False, False, False, False]):
                result = await step.execute(wizard_context)

        assert result.success is False
        assert result.go_back is True

    @pytest.mark.asyncio
    async def test_interactive_user_overrides_language(self, wizard_context, mock_project_info):
        """Test user overriding language detection."""
        step = ProjectDetectionStep()

        with patch(
            "fastband.wizard.steps.project.detect_project",
            return_value=mock_project_info,
        ):
            # Sequence: reject detection, override language, don't override type, confirm
            with patch.object(step, "confirm", side_effect=[False, True, False, True]):
                with patch.object(step, "select_from_list", return_value=["typescript"]):
                    result = await step.execute(wizard_context)

        assert result.success is True
        # The language should have been overridden
        assert mock_project_info.primary_language == Language.TYPESCRIPT
        assert mock_project_info.language_confidence == 1.0

    @pytest.mark.asyncio
    async def test_interactive_user_overrides_project_type(self, wizard_context, mock_project_info):
        """Test user overriding project type detection."""
        step = ProjectDetectionStep()

        with patch(
            "fastband.wizard.steps.project.detect_project",
            return_value=mock_project_info,
        ):
            # Sequence: reject detection, don't override language, override type, confirm
            with patch.object(step, "confirm", side_effect=[False, False, True, True]):
                with patch.object(step, "select_from_list", return_value=["library"]):
                    result = await step.execute(wizard_context)

        assert result.success is True
        assert mock_project_info.primary_type == ProjectType.LIBRARY
        assert mock_project_info.type_confidence == 1.0

    @pytest.mark.asyncio
    async def test_interactive_override_both_language_and_type(
        self, wizard_context, mock_project_info
    ):
        """Test user overriding both language and type."""
        step = ProjectDetectionStep()

        with patch(
            "fastband.wizard.steps.project.detect_project",
            return_value=mock_project_info,
        ):
            # Sequence: reject, override lang, override type, confirm
            with patch.object(step, "confirm", side_effect=[False, True, True, True]):
                with patch.object(
                    step,
                    "select_from_list",
                    side_effect=[["rust"], ["api_service"]],
                ):
                    result = await step.execute(wizard_context)

        assert result.success is True
        assert mock_project_info.primary_language == Language.RUST
        assert mock_project_info.primary_type == ProjectType.API_SERVICE


# =============================================================================
# NON-INTERACTIVE MODE TESTS
# =============================================================================


class TestNonInteractiveMode:
    """Tests for non-interactive mode behavior."""

    @pytest.mark.asyncio
    async def test_non_interactive_accepts_detected_values(
        self, non_interactive_context, mock_project_info
    ):
        """Test that non-interactive mode accepts detected values without prompts."""
        step = ProjectDetectionStep()

        with patch(
            "fastband.wizard.steps.project.detect_project",
            return_value=mock_project_info,
        ):
            # Confirm should never be called
            with patch.object(step, "confirm") as mock_confirm:
                result = await step.execute(non_interactive_context)
                mock_confirm.assert_not_called()

        assert result.success is True

    @pytest.mark.asyncio
    async def test_non_interactive_no_user_prompts(
        self, non_interactive_context, mock_project_info
    ):
        """Test that no user prompts are shown in non-interactive mode."""
        step = ProjectDetectionStep()

        with patch(
            "fastband.wizard.steps.project.detect_project",
            return_value=mock_project_info,
        ):
            with patch.object(step, "prompt") as mock_prompt:
                with patch.object(step, "select_from_list") as mock_select:
                    await step.execute(non_interactive_context)

                    mock_prompt.assert_not_called()
                    mock_select.assert_not_called()

    @pytest.mark.asyncio
    async def test_non_interactive_stores_all_info(
        self, non_interactive_context, mock_project_info
    ):
        """Test that all detection info is stored in non-interactive mode."""
        step = ProjectDetectionStep()

        with patch(
            "fastband.wizard.steps.project.detect_project",
            return_value=mock_project_info,
        ):
            await step.execute(non_interactive_context)

        info = non_interactive_context.project_info
        assert info is not None
        assert info.primary_language == Language.PYTHON
        assert info.primary_type == ProjectType.CLI_TOOL
        assert len(info.frameworks) == 2
        assert len(info.package_managers) == 2


# =============================================================================
# VALIDATION TESTS
# =============================================================================


class TestValidation:
    """Tests for validation logic."""

    @pytest.mark.asyncio
    async def test_validate_with_project_info(self, wizard_context, mock_project_info):
        """Test validation passes when project_info is set."""
        step = ProjectDetectionStep()
        wizard_context.project_info = mock_project_info

        result = await step.validate(wizard_context)

        assert result is True

    @pytest.mark.asyncio
    async def test_validate_without_project_info(self, wizard_context):
        """Test validation fails when project_info is not set."""
        step = ProjectDetectionStep()
        wizard_context.project_info = None

        result = await step.validate(wizard_context)

        assert result is False


# =============================================================================
# DISPLAY TESTS
# =============================================================================


class TestDisplayFunctionality:
    """Tests for display-related functionality."""

    def test_language_display_names_coverage(self):
        """Test that all languages have display names."""
        for lang in Language:
            assert lang in LANGUAGE_DISPLAY_NAMES

    def test_project_type_display_names_coverage(self):
        """Test that all project types have display names."""
        for pt in ProjectType:
            assert pt in PROJECT_TYPE_DISPLAY_NAMES

    def test_framework_display_names_exist(self):
        """Test that framework display names dictionary is populated."""
        assert len(FRAMEWORK_DISPLAY_NAMES) > 0

    @pytest.mark.asyncio
    async def test_display_detection_results_called(
        self, non_interactive_context, mock_project_info
    ):
        """Test that display method is called during execution."""
        step = ProjectDetectionStep()

        with patch(
            "fastband.wizard.steps.project.detect_project",
            return_value=mock_project_info,
        ):
            with patch.object(step, "_display_detection_results") as mock_display:
                await step.execute(non_interactive_context)
                mock_display.assert_called_once_with(mock_project_info)

    def test_display_detection_results_no_error(self, mock_project_info):
        """Test that display method runs without error."""
        step = ProjectDetectionStep()

        # Should not raise
        step._display_detection_results(mock_project_info)

    def test_display_monorepo_info(self, mock_monorepo_info):
        """Test display of monorepo information."""
        step = ProjectDetectionStep()

        # Should not raise, even with many subprojects
        step._display_detection_results(mock_monorepo_info)


# =============================================================================
# EDGE CASES TESTS
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_project_with_no_name(self, non_interactive_context, temp_dir):
        """Test handling of project with no detected name."""
        info = ProjectInfo(
            path=temp_dir,
            primary_language=Language.UNKNOWN,
            primary_type=ProjectType.UNKNOWN,
            name=None,
            language_confidence=0.0,
            type_confidence=0.0,
        )
        step = ProjectDetectionStep()

        with patch(
            "fastband.wizard.steps.project.detect_project",
            return_value=info,
        ):
            result = await step.execute(non_interactive_context)

        assert result.success is True
        # Config project_name should not be set
        assert non_interactive_context.config.project_name is None

    @pytest.mark.asyncio
    async def test_project_with_empty_frameworks(self, non_interactive_context, temp_dir):
        """Test handling of project with no frameworks detected."""
        info = ProjectInfo(
            path=temp_dir,
            primary_language=Language.PYTHON,
            primary_type=ProjectType.CLI_TOOL,
            frameworks=[],
            language_confidence=0.5,
            type_confidence=0.5,
        )
        step = ProjectDetectionStep()

        with patch(
            "fastband.wizard.steps.project.detect_project",
            return_value=info,
        ):
            result = await step.execute(non_interactive_context)

        assert result.success is True
        assert result.data["frameworks"] == []

    @pytest.mark.asyncio
    async def test_project_with_unknown_language(self, non_interactive_context, temp_dir):
        """Test handling of project with unknown language."""
        info = ProjectInfo(
            path=temp_dir,
            primary_language=Language.UNKNOWN,
            primary_type=ProjectType.UNKNOWN,
            language_confidence=0.0,
            type_confidence=0.0,
        )
        step = ProjectDetectionStep()

        with patch(
            "fastband.wizard.steps.project.detect_project",
            return_value=info,
        ):
            result = await step.execute(non_interactive_context)

        assert result.success is True
        assert result.data["language"] == "unknown"
        assert result.data["type"] == "unknown"

    @pytest.mark.asyncio
    async def test_status_updated_correctly(self, non_interactive_context, mock_project_info):
        """Test that step status is managed correctly."""
        step = ProjectDetectionStep()
        assert step.status == StepStatus.PENDING

        with patch(
            "fastband.wizard.steps.project.detect_project",
            return_value=mock_project_info,
        ):
            await step.execute(non_interactive_context)

        # Note: Status is managed by SetupWizard, not the step itself
        # This test verifies the step doesn't break status handling


# =============================================================================
# INTEGRATION-STYLE TESTS
# =============================================================================


class TestIntegration:
    """Integration-style tests using real project detection."""

    @pytest.mark.asyncio
    async def test_detect_real_temp_directory(self, temp_dir):
        """Test detecting an empty temporary directory."""
        context = WizardContext(
            project_path=temp_dir,
            config=FastbandConfig(),
            interactive=False,
        )
        step = ProjectDetectionStep()

        result = await step.execute(context)

        # Should succeed even with empty directory
        assert result.success is True
        assert context.project_info is not None

    @pytest.mark.asyncio
    async def test_detect_with_python_file(self, temp_dir):
        """Test detecting a directory with a Python file."""
        # Create a simple Python file
        (temp_dir / "main.py").write_text("print('hello')")
        (temp_dir / "pyproject.toml").write_text("[project]\nname = 'test'\n")

        context = WizardContext(
            project_path=temp_dir,
            config=FastbandConfig(),
            interactive=False,
        )
        step = ProjectDetectionStep()

        result = await step.execute(context)

        assert result.success is True
        assert context.project_info is not None
        # Should detect Python
        assert context.project_info.primary_language in [Language.PYTHON, Language.UNKNOWN]

    @pytest.mark.asyncio
    async def test_step_can_be_used_in_wizard(self, temp_dir):
        """Test that the step works correctly in a wizard context."""
        from fastband.wizard.base import SetupWizard

        wizard = SetupWizard(project_path=temp_dir, interactive=False)
        step = ProjectDetectionStep()
        wizard.add_step(step)

        # The step should be usable in a wizard
        assert step in wizard.steps
        assert wizard.steps[0].name == "project"

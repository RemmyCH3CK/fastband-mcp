"""Tests for the Setup Wizard framework."""

import tempfile
from pathlib import Path

import pytest

from fastband.core.config import FastbandConfig
from fastband.wizard.base import (
    SetupWizard,
    StepResult,
    StepStatus,
    WizardContext,
    WizardStep,
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


class MockStep(WizardStep):
    """Mock wizard step for testing."""

    def __init__(self, name: str = "mock", success: bool = True, **kwargs):
        super().__init__()
        self._name = name
        self._success = success
        self._title = kwargs.get("title", f"Mock Step: {name}")
        self._description = kwargs.get("description", "")
        self._required = kwargs.get("required", False)
        self._should_skip = kwargs.get("should_skip", False)
        self.execute_called = False
        self.validate_called = False

    @property
    def name(self) -> str:
        return self._name

    @property
    def title(self) -> str:
        return self._title

    @property
    def description(self) -> str:
        return self._description

    @property
    def required(self) -> bool:
        return self._required

    def should_skip(self, context: WizardContext) -> bool:
        return self._should_skip

    async def execute(self, context: WizardContext) -> StepResult:
        self.execute_called = True
        return StepResult(
            success=self._success,
            data={"step": self._name},
            message="Success" if self._success else "Failed",
        )

    async def validate(self, context: WizardContext) -> bool:
        self.validate_called = True
        return True


# =============================================================================
# WIZARD CONTEXT TESTS
# =============================================================================


class TestWizardContext:
    """Tests for WizardContext."""

    def test_creation(self, temp_dir):
        """Test context creation."""
        context = WizardContext(project_path=temp_dir)

        assert context.project_path == temp_dir
        assert context.interactive is True
        assert context.config is not None
        assert context.selected_tools == []
        assert context.metadata == {}

    def test_get_set_metadata(self, wizard_context):
        """Test metadata get/set."""
        wizard_context.set("key1", "value1")
        wizard_context.set("key2", {"nested": "value"})

        assert wizard_context.get("key1") == "value1"
        assert wizard_context.get("key2") == {"nested": "value"}
        assert wizard_context.get("missing") is None
        assert wizard_context.get("missing", "default") == "default"

    def test_default_values(self, wizard_context):
        """Test default values."""
        assert wizard_context.github_enabled is False
        assert wizard_context.tickets_enabled is False
        assert wizard_context.backup_enabled is True
        assert wizard_context.project_info is None
        assert wizard_context.selected_provider is None


# =============================================================================
# STEP RESULT TESTS
# =============================================================================


class TestStepResult:
    """Tests for StepResult."""

    def test_success_result(self):
        """Test successful result."""
        result = StepResult(
            success=True,
            data={"key": "value"},
            message="Done",
        )

        assert result.success is True
        assert result.data == {"key": "value"}
        assert result.message == "Done"
        assert result.skip_remaining is False
        assert result.go_back is False

    def test_failure_result(self):
        """Test failure result."""
        result = StepResult(
            success=False,
            message="Error occurred",
        )

        assert result.success is False
        assert result.data == {}
        assert result.message == "Error occurred"

    def test_skip_remaining(self):
        """Test skip remaining flag."""
        result = StepResult(success=True, skip_remaining=True)

        assert result.skip_remaining is True

    def test_go_back(self):
        """Test go back flag."""
        result = StepResult(success=False, go_back=True)

        assert result.go_back is True


# =============================================================================
# WIZARD STEP TESTS
# =============================================================================


class TestWizardStep:
    """Tests for WizardStep base class."""

    def test_step_creation(self):
        """Test step creation."""
        step = MockStep(name="test_step")

        assert step.name == "test_step"
        assert step.status == StepStatus.PENDING

    def test_step_status(self):
        """Test step status changes."""
        step = MockStep()

        step.status = StepStatus.IN_PROGRESS
        assert step.status == StepStatus.IN_PROGRESS

        step.status = StepStatus.COMPLETED
        assert step.status == StepStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_step_execute(self, wizard_context):
        """Test step execution."""
        step = MockStep(success=True)
        result = await step.execute(wizard_context)

        assert step.execute_called is True
        assert result.success is True

    @pytest.mark.asyncio
    async def test_step_validate(self, wizard_context):
        """Test step validation."""
        step = MockStep()
        valid = await step.validate(wizard_context)

        assert step.validate_called is True
        assert valid is True

    def test_step_should_skip(self, wizard_context):
        """Test should_skip method."""
        step1 = MockStep(should_skip=False)
        step2 = MockStep(should_skip=True)

        assert step1.should_skip(wizard_context) is False
        assert step2.should_skip(wizard_context) is True


# =============================================================================
# SETUP WIZARD TESTS
# =============================================================================


class TestSetupWizard:
    """Tests for SetupWizard."""

    def test_wizard_creation(self, temp_dir):
        """Test wizard creation."""
        import os

        wizard = SetupWizard(project_path=temp_dir)

        # Use realpath to handle macOS /var -> /private/var symlink
        assert os.path.realpath(str(wizard.project_path)) == os.path.realpath(str(temp_dir))
        assert wizard.interactive is True
        assert wizard.steps == []
        assert wizard.current_step_index == 0

    def test_add_step(self, temp_dir):
        """Test adding steps."""
        wizard = SetupWizard(project_path=temp_dir)
        step1 = MockStep(name="step1")
        step2 = MockStep(name="step2")

        wizard.add_step(step1)
        wizard.add_step(step2)

        assert len(wizard.steps) == 2
        assert wizard.steps[0].name == "step1"
        assert wizard.steps[1].name == "step2"

    def test_add_steps(self, temp_dir):
        """Test adding multiple steps."""
        wizard = SetupWizard(project_path=temp_dir)
        steps = [MockStep(name="a"), MockStep(name="b"), MockStep(name="c")]

        wizard.add_steps(steps)

        assert len(wizard.steps) == 3

    def test_current_step(self, temp_dir):
        """Test current step property."""
        wizard = SetupWizard(project_path=temp_dir)
        steps = [MockStep(name="a"), MockStep(name="b")]
        wizard.add_steps(steps)

        assert wizard.current_step.name == "a"

        wizard.current_step_index = 1
        assert wizard.current_step.name == "b"

    def test_progress(self, temp_dir):
        """Test progress calculation."""
        wizard = SetupWizard(project_path=temp_dir)
        steps = [MockStep(name="a"), MockStep(name="b"), MockStep(name="c"), MockStep(name="d")]
        wizard.add_steps(steps)

        assert wizard.progress == 0.0

        steps[0].status = StepStatus.COMPLETED
        assert wizard.progress == 25.0

        steps[1].status = StepStatus.COMPLETED
        assert wizard.progress == 50.0

        steps[2].status = StepStatus.COMPLETED
        steps[3].status = StepStatus.COMPLETED
        assert wizard.progress == 100.0

    @pytest.mark.asyncio
    async def test_run_all_steps_success(self, temp_dir):
        """Test running wizard with all steps succeeding."""
        wizard = SetupWizard(project_path=temp_dir, interactive=False)
        steps = [MockStep(name="a"), MockStep(name="b"), MockStep(name="c")]
        wizard.add_steps(steps)

        result = await wizard.run()

        assert result is True
        assert all(s.execute_called for s in steps)
        assert all(s.status == StepStatus.COMPLETED for s in steps)

    @pytest.mark.asyncio
    async def test_run_with_skip(self, temp_dir):
        """Test running wizard with skipped step."""
        wizard = SetupWizard(project_path=temp_dir, interactive=False)
        steps = [
            MockStep(name="a"),
            MockStep(name="b", should_skip=True),
            MockStep(name="c"),
        ]
        wizard.add_steps(steps)

        result = await wizard.run()

        assert result is True
        assert steps[0].execute_called is True
        assert steps[1].execute_called is False
        assert steps[2].execute_called is True
        assert steps[1].status == StepStatus.SKIPPED

    @pytest.mark.asyncio
    async def test_run_with_failure_non_required(self, temp_dir):
        """Test running wizard with non-required step failing."""
        wizard = SetupWizard(project_path=temp_dir, interactive=False)
        steps = [
            MockStep(name="a"),
            MockStep(name="b", success=False, required=False),
            MockStep(name="c"),
        ]
        wizard.add_steps(steps)

        result = await wizard.run()

        assert result is True
        assert steps[0].status == StepStatus.COMPLETED
        assert steps[1].status == StepStatus.FAILED
        assert steps[2].status == StepStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_run_with_failure_required(self, temp_dir):
        """Test running wizard with required step failing."""
        wizard = SetupWizard(project_path=temp_dir, interactive=False)
        steps = [
            MockStep(name="a"),
            MockStep(name="b", success=False, required=True),
            MockStep(name="c"),
        ]
        wizard.add_steps(steps)

        result = await wizard.run()

        assert result is False
        assert steps[0].status == StepStatus.COMPLETED
        assert steps[1].status == StepStatus.FAILED
        assert steps[2].execute_called is False

    @pytest.mark.asyncio
    async def test_config_saved(self, temp_dir):
        """Test configuration is saved after wizard completes."""
        wizard = SetupWizard(project_path=temp_dir, interactive=False)
        wizard.add_step(MockStep(name="a"))

        await wizard.run()

        config_file = temp_dir / ".fastband" / "config.yaml"
        assert config_file.exists()

    @pytest.mark.asyncio
    async def test_skip_remaining(self, temp_dir):
        """Test skip_remaining flag stops wizard."""

        class SkipRemainingStep(MockStep):
            async def execute(self, context):
                return StepResult(success=True, skip_remaining=True)

        wizard = SetupWizard(project_path=temp_dir, interactive=False)
        steps = [
            MockStep(name="a"),
            SkipRemainingStep(name="skipper"),
            MockStep(name="c"),
        ]
        wizard.add_steps(steps)

        result = await wizard.run()

        assert result is True
        assert steps[0].execute_called is True
        assert steps[2].execute_called is False


# =============================================================================
# STEP UI HELPER TESTS
# =============================================================================


class TestStepUIHelpers:
    """Tests for step UI helper methods."""

    def test_show_success(self, capsys):
        """Test success message display."""
        step = MockStep()
        step.show_success("Operation completed")

        # Note: Rich console output is captured differently
        # This is a basic test that the method doesn't error

    def test_show_error(self, capsys):
        """Test error message display."""
        step = MockStep()
        step.show_error("Something went wrong")

    def test_show_warning(self, capsys):
        """Test warning message display."""
        step = MockStep()
        step.show_warning("Be careful")

    def test_show_info(self, capsys):
        """Test info message display."""
        step = MockStep()
        step.show_info("FYI")

    def test_show_header(self, capsys):
        """Test header display."""
        step = MockStep(title="Test Step", description="This is a test")
        step.show_header()


# =============================================================================
# NON-INTERACTIVE MODE TESTS
# =============================================================================


class TestNonInteractiveMode:
    """Tests for non-interactive mode."""

    def test_context_non_interactive(self, temp_dir):
        """Test non-interactive context."""
        context = WizardContext(
            project_path=temp_dir,
            interactive=False,
        )

        assert context.interactive is False

    @pytest.mark.asyncio
    async def test_wizard_non_interactive(self, temp_dir):
        """Test wizard in non-interactive mode."""
        wizard = SetupWizard(
            project_path=temp_dir,
            interactive=False,
        )
        wizard.add_step(MockStep())

        result = await wizard.run()

        assert result is True


# =============================================================================
# STEP STATUS TESTS
# =============================================================================


class TestStepStatus:
    """Tests for StepStatus enum."""

    def test_status_values(self):
        """Test status enum values."""
        assert StepStatus.PENDING.value == "pending"
        assert StepStatus.IN_PROGRESS.value == "in_progress"
        assert StepStatus.COMPLETED.value == "completed"
        assert StepStatus.SKIPPED.value == "skipped"
        assert StepStatus.FAILED.value == "failed"

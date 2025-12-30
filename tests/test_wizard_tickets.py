"""Tests for the Ticket Manager wizard step."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from fastband.core.config import FastbandConfig, TicketsConfig
from fastband.wizard.base import (
    StepStatus,
    WizardContext,
    WizardStep,
)
from fastband.wizard.steps.tickets import TicketManagerStep

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
def ticket_step():
    """Create a TicketManagerStep instance."""
    return TicketManagerStep()


@pytest.fixture
def large_project_context(temp_dir):
    """Create a context representing a large project."""
    context = WizardContext(
        project_path=temp_dir,
        config=FastbandConfig(),
        interactive=False,
    )
    # Simulate large project via metadata
    context.set("file_count", 100)
    return context


# =============================================================================
# TICKET MANAGER STEP PROPERTY TESTS
# =============================================================================


class TestTicketManagerStepProperties:
    """Tests for TicketManagerStep properties."""

    def test_name(self, ticket_step):
        """Test step name property."""
        assert ticket_step.name == "tickets"

    def test_title(self, ticket_step):
        """Test step title property."""
        assert ticket_step.title == "Ticket Manager Setup"

    def test_description(self, ticket_step):
        """Test step description property."""
        assert ticket_step.description == "Configure ticket tracking and agent coordination"

    def test_required_is_false(self, ticket_step):
        """Test that the step is not required."""
        assert ticket_step.required is False

    def test_inherits_from_wizard_step(self, ticket_step):
        """Test that TicketManagerStep inherits from WizardStep."""
        assert isinstance(ticket_step, WizardStep)

    def test_initial_status(self, ticket_step):
        """Test initial step status is PENDING."""
        assert ticket_step.status == StepStatus.PENDING

    def test_mode_options_structure(self, ticket_step):
        """Test MODE_OPTIONS has correct structure."""
        assert len(ticket_step.MODE_OPTIONS) == 3

        for option in ticket_step.MODE_OPTIONS:
            assert "value" in option
            assert "label" in option
            assert "description" in option

    def test_mode_options_values(self, ticket_step):
        """Test MODE_OPTIONS contains expected values."""
        values = [opt["value"] for opt in ticket_step.MODE_OPTIONS]
        assert "cli" in values
        assert "web" in values
        assert "disabled" in values

    def test_default_web_port(self, ticket_step):
        """Test default web port constant."""
        assert ticket_step.DEFAULT_WEB_PORT == 5050

    def test_large_project_threshold(self, ticket_step):
        """Test large project file count threshold."""
        assert ticket_step.LARGE_PROJECT_FILE_COUNT == 50


# =============================================================================
# MODE SELECTION TESTS
# =============================================================================


class TestModeSelection:
    """Tests for mode selection logic."""

    def test_get_default_mode_small_project(self, ticket_step, wizard_context):
        """Test default mode for small project is disabled."""
        default_mode = ticket_step._get_default_mode(wizard_context)
        assert default_mode == "disabled"

    def test_get_default_mode_large_project(self, ticket_step, large_project_context):
        """Test default mode for large project is web."""
        default_mode = ticket_step._get_default_mode(large_project_context)
        assert default_mode == "web"

    def test_is_large_project_false(self, ticket_step, wizard_context):
        """Test small project detection."""
        assert ticket_step._is_large_project(wizard_context) is False

    def test_is_large_project_true(self, ticket_step, large_project_context):
        """Test large project detection."""
        assert ticket_step._is_large_project(large_project_context) is True

    def test_is_large_project_threshold(self, ticket_step, temp_dir):
        """Test project size at threshold."""
        context = WizardContext(project_path=temp_dir, interactive=False)
        context.set("file_count", 50)  # Exactly at threshold
        assert ticket_step._is_large_project(context) is True

        context.set("file_count", 49)  # Just below threshold
        assert ticket_step._is_large_project(context) is False

    def test_translate_mode_cli(self, ticket_step):
        """Test mode translation for CLI."""
        assert ticket_step._translate_mode("cli") == "cli"

    def test_translate_mode_web(self, ticket_step):
        """Test mode translation for web."""
        assert ticket_step._translate_mode("web") == "cli_web"

    def test_translate_mode_disabled(self, ticket_step):
        """Test mode translation for disabled."""
        assert ticket_step._translate_mode("disabled") == "cli"

    def test_translate_mode_unknown(self, ticket_step):
        """Test mode translation for unknown mode defaults to cli."""
        assert ticket_step._translate_mode("unknown") == "cli"


# =============================================================================
# PORT CONFIGURATION TESTS
# =============================================================================


class TestPortConfiguration:
    """Tests for web dashboard port configuration."""

    @pytest.mark.asyncio
    async def test_configure_web_port_default(self, ticket_step):
        """Test default port configuration."""
        with patch.object(ticket_step, "prompt", return_value="5050"):
            port = await ticket_step._configure_web_port()
            assert port == 5050

    @pytest.mark.asyncio
    async def test_configure_web_port_custom(self, ticket_step):
        """Test custom port configuration."""
        with patch.object(ticket_step, "prompt", return_value="8080"):
            port = await ticket_step._configure_web_port()
            assert port == 8080

    @pytest.mark.asyncio
    async def test_configure_web_port_invalid_returns_default(self, ticket_step):
        """Test invalid port returns default."""
        with patch.object(ticket_step, "prompt", return_value="invalid"):
            with patch.object(ticket_step, "show_warning"):
                port = await ticket_step._configure_web_port()
                assert port == ticket_step.DEFAULT_WEB_PORT

    @pytest.mark.asyncio
    async def test_configure_web_port_too_low(self, ticket_step):
        """Test port below valid range returns default."""
        with patch.object(ticket_step, "prompt", return_value="80"):
            with patch.object(ticket_step, "show_warning") as mock_warning:
                port = await ticket_step._configure_web_port()
                assert port == ticket_step.DEFAULT_WEB_PORT
                mock_warning.assert_called_once()

    @pytest.mark.asyncio
    async def test_configure_web_port_too_high(self, ticket_step):
        """Test port above valid range returns default."""
        with patch.object(ticket_step, "prompt", return_value="99999"):
            with patch.object(ticket_step, "show_warning") as mock_warning:
                port = await ticket_step._configure_web_port()
                assert port == ticket_step.DEFAULT_WEB_PORT
                mock_warning.assert_called_once()

    @pytest.mark.asyncio
    async def test_configure_web_port_boundary_low(self, ticket_step):
        """Test port at lower boundary (1024) is valid."""
        with patch.object(ticket_step, "prompt", return_value="1024"):
            port = await ticket_step._configure_web_port()
            assert port == 1024

    @pytest.mark.asyncio
    async def test_configure_web_port_boundary_high(self, ticket_step):
        """Test port at upper boundary (65535) is valid."""
        with patch.object(ticket_step, "prompt", return_value="65535"):
            port = await ticket_step._configure_web_port()
            assert port == 65535


# =============================================================================
# NON-INTERACTIVE MODE TESTS
# =============================================================================


class TestNonInteractiveMode:
    """Tests for non-interactive mode execution."""

    @pytest.mark.asyncio
    async def test_non_interactive_small_project_disabled(
        self, ticket_step, non_interactive_context
    ):
        """Test non-interactive mode disables tickets for small projects."""
        result = await ticket_step.execute(non_interactive_context)

        assert result.success is True
        assert result.data["mode"] == "disabled"
        assert result.data["enabled"] is False
        assert non_interactive_context.tickets_enabled is False

    @pytest.mark.asyncio
    async def test_non_interactive_large_project_web(self, ticket_step, large_project_context):
        """Test non-interactive mode enables web for large projects."""
        result = await ticket_step.execute(large_project_context)

        assert result.success is True
        assert result.data["mode"] == "web"
        assert result.data["enabled"] is True
        assert result.data["web_port"] == 5050
        assert large_project_context.tickets_enabled is True

    @pytest.mark.asyncio
    async def test_non_interactive_sets_config(self, ticket_step, non_interactive_context):
        """Test non-interactive mode sets config correctly."""
        await ticket_step.execute(non_interactive_context)

        config = non_interactive_context.config.tickets
        assert isinstance(config, TicketsConfig)
        assert config.enabled is False

    @pytest.mark.asyncio
    async def test_non_interactive_large_project_config(self, ticket_step, large_project_context):
        """Test non-interactive mode sets correct config for large project."""
        await ticket_step.execute(large_project_context)

        config = large_project_context.config.tickets
        assert config.enabled is True
        assert config.mode == "cli_web"
        assert config.web_port == 5050
        assert config.review_agents is True

    @pytest.mark.asyncio
    async def test_non_interactive_result_message(self, ticket_step, non_interactive_context):
        """Test result message in non-interactive mode."""
        result = await ticket_step.execute(non_interactive_context)

        assert "disabled" in result.message.lower()


# =============================================================================
# INTERACTIVE MODE TESTS
# =============================================================================


class TestInteractiveMode:
    """Tests for interactive mode execution."""

    @pytest.mark.asyncio
    async def test_interactive_cli_mode_selection(self, ticket_step, wizard_context):
        """Test selecting CLI mode in interactive mode."""
        with patch.object(ticket_step, "select_from_list", return_value=["cli"]):
            with patch.object(ticket_step, "confirm", return_value=False):
                with patch.object(ticket_step, "show_info"):
                    with patch.object(ticket_step, "show_success"):
                        result = await ticket_step.execute(wizard_context)

        assert result.success is True
        assert result.data["mode"] == "cli"
        assert result.data["enabled"] is True
        assert wizard_context.tickets_enabled is True

    @pytest.mark.asyncio
    async def test_interactive_disabled_mode_selection(self, ticket_step, wizard_context):
        """Test selecting disabled mode in interactive mode."""
        with patch.object(ticket_step, "select_from_list", return_value=["disabled"]):
            with patch.object(ticket_step, "show_info"):
                with patch.object(ticket_step, "show_success"):
                    result = await ticket_step.execute(wizard_context)

        assert result.success is True
        assert result.data["mode"] == "disabled"
        assert result.data["enabled"] is False
        assert wizard_context.tickets_enabled is False

    @pytest.mark.asyncio
    async def test_interactive_web_mode_selection(self, ticket_step, wizard_context):
        """Test selecting web mode in interactive mode."""
        with patch.object(ticket_step, "select_from_list", return_value=["web"]):
            with patch.object(ticket_step, "_configure_web_port", return_value=5050):
                with patch.object(
                    ticket_step, "_configure_workflow_options", return_value={"review_agents": True}
                ):
                    with patch.object(ticket_step, "_configure_agent_coordination"):
                        with patch.object(ticket_step, "show_success"):
                            result = await ticket_step.execute(wizard_context)

        assert result.success is True
        assert result.data["mode"] == "web"
        assert result.data["enabled"] is True
        assert result.data["web_port"] == 5050
        assert result.data["review_agents"] is True

    @pytest.mark.asyncio
    async def test_interactive_web_mode_custom_port(self, ticket_step, wizard_context):
        """Test web mode with custom port."""
        with patch.object(ticket_step, "select_from_list", return_value=["web"]):
            with patch.object(ticket_step, "_configure_web_port", return_value=8080):
                with patch.object(
                    ticket_step,
                    "_configure_workflow_options",
                    return_value={"review_agents": False},
                ):
                    with patch.object(ticket_step, "_configure_agent_coordination"):
                        with patch.object(ticket_step, "show_success"):
                            result = await ticket_step.execute(wizard_context)

        assert result.data["web_port"] == 8080
        assert wizard_context.config.tickets.web_port == 8080

    @pytest.mark.asyncio
    async def test_interactive_cli_review_agents(self, ticket_step, wizard_context):
        """Test CLI mode with review agents enabled."""
        with patch.object(ticket_step, "select_from_list", return_value=["cli"]):
            with patch.object(ticket_step, "confirm", return_value=True):
                with patch.object(ticket_step, "show_info"):
                    with patch.object(ticket_step, "show_success"):
                        result = await ticket_step.execute(wizard_context)

        assert result.data["review_agents"] is True
        assert wizard_context.config.tickets.review_agents is True


# =============================================================================
# WORKFLOW CONFIGURATION TESTS
# =============================================================================


class TestWorkflowConfiguration:
    """Tests for workflow configuration."""

    @pytest.mark.asyncio
    async def test_configure_workflow_options(self, ticket_step):
        """Test workflow options configuration."""
        with patch.object(ticket_step, "confirm", return_value=True):
            options = await ticket_step._configure_workflow_options()

        assert options["review_agents"] is True

    @pytest.mark.asyncio
    async def test_configure_workflow_options_no_review(self, ticket_step):
        """Test workflow options without review agents."""
        with patch.object(ticket_step, "confirm", return_value=False):
            options = await ticket_step._configure_workflow_options()

        assert options["review_agents"] is False

    @pytest.mark.asyncio
    async def test_configure_agent_coordination_enabled(self, ticket_step, wizard_context):
        """Test agent coordination configuration when enabled."""
        with patch.object(ticket_step, "confirm", return_value=True):
            with patch.object(ticket_step, "show_info"):
                await ticket_step._configure_agent_coordination(wizard_context)

        assert wizard_context.get("multi_agent_enabled") is True

    @pytest.mark.asyncio
    async def test_configure_agent_coordination_disabled(self, ticket_step, wizard_context):
        """Test agent coordination configuration when disabled."""
        with patch.object(ticket_step, "confirm", return_value=False):
            await ticket_step._configure_agent_coordination(wizard_context)

        assert wizard_context.get("multi_agent_enabled") is False


# =============================================================================
# VALIDATION TESTS
# =============================================================================


class TestValidation:
    """Tests for step validation."""

    @pytest.mark.asyncio
    async def test_validate_success(self, ticket_step, wizard_context):
        """Test successful validation."""
        wizard_context.config.tickets = TicketsConfig(
            enabled=True,
            mode="cli_web",
            web_port=5050,
        )

        result = await ticket_step.validate(wizard_context)
        assert result is True

    @pytest.mark.asyncio
    async def test_validate_invalid_port_zero(self, ticket_step, wizard_context):
        """Test validation fails for zero port."""
        wizard_context.config.tickets = TicketsConfig(
            enabled=True,
            mode="cli_web",
            web_port=0,
        )

        with patch.object(ticket_step, "show_error"):
            result = await ticket_step.validate(wizard_context)

        assert result is False

    @pytest.mark.asyncio
    async def test_validate_invalid_port_too_high(self, ticket_step, wizard_context):
        """Test validation fails for port > 65535."""
        wizard_context.config.tickets = TicketsConfig(
            enabled=True,
            mode="cli_web",
            web_port=70000,
        )

        with patch.object(ticket_step, "show_error"):
            result = await ticket_step.validate(wizard_context)

        assert result is False

    @pytest.mark.asyncio
    async def test_validate_cli_mode_skips_port_check(self, ticket_step, wizard_context):
        """Test CLI mode doesn't validate port."""
        wizard_context.config.tickets = TicketsConfig(
            enabled=True,
            mode="cli",
            web_port=0,  # Invalid, but shouldn't matter for CLI mode
        )

        result = await ticket_step.validate(wizard_context)
        assert result is True

    @pytest.mark.asyncio
    async def test_validate_disabled_mode(self, ticket_step, wizard_context):
        """Test validation passes for disabled mode."""
        wizard_context.config.tickets = TicketsConfig(
            enabled=False,
            mode="cli",
            web_port=5050,
        )

        result = await ticket_step.validate(wizard_context)
        assert result is True


# =============================================================================
# CONTEXT UPDATE TESTS
# =============================================================================


class TestContextUpdates:
    """Tests for context updates during execution."""

    @pytest.mark.asyncio
    async def test_context_tickets_enabled_set(self, ticket_step, non_interactive_context):
        """Test tickets_enabled is set in context."""
        non_interactive_context.set("file_count", 100)  # Large project
        await ticket_step.execute(non_interactive_context)

        assert non_interactive_context.tickets_enabled is True

    @pytest.mark.asyncio
    async def test_context_config_updated(self, ticket_step, non_interactive_context):
        """Test config.tickets is updated in context."""
        await ticket_step.execute(non_interactive_context)

        assert non_interactive_context.config.tickets is not None
        assert isinstance(non_interactive_context.config.tickets, TicketsConfig)

    @pytest.mark.asyncio
    async def test_context_metadata_tickets_mode(self, ticket_step, wizard_context):
        """Test tickets_mode metadata is set for enabled modes."""
        with patch.object(ticket_step, "select_from_list", return_value=["cli"]):
            with patch.object(ticket_step, "confirm", return_value=False):
                with patch.object(ticket_step, "show_info"):
                    with patch.object(ticket_step, "show_success"):
                        await ticket_step.execute(wizard_context)

        assert wizard_context.get("tickets_mode") == "cli"

    @pytest.mark.asyncio
    async def test_context_metadata_not_set_for_disabled(self, ticket_step, wizard_context):
        """Test tickets_mode metadata is not set for disabled mode."""
        with patch.object(ticket_step, "select_from_list", return_value=["disabled"]):
            with patch.object(ticket_step, "show_info"):
                with patch.object(ticket_step, "show_success"):
                    await ticket_step.execute(wizard_context)

        assert wizard_context.get("tickets_mode") is None


# =============================================================================
# STEP RESULT TESTS
# =============================================================================


class TestStepResult:
    """Tests for StepResult content."""

    @pytest.mark.asyncio
    async def test_result_contains_mode(self, ticket_step, non_interactive_context):
        """Test result contains mode."""
        result = await ticket_step.execute(non_interactive_context)

        assert "mode" in result.data
        assert result.data["mode"] in ["cli", "web", "disabled"]

    @pytest.mark.asyncio
    async def test_result_contains_enabled(self, ticket_step, non_interactive_context):
        """Test result contains enabled flag."""
        result = await ticket_step.execute(non_interactive_context)

        assert "enabled" in result.data
        assert isinstance(result.data["enabled"], bool)

    @pytest.mark.asyncio
    async def test_result_web_port_for_web_mode(self, ticket_step, large_project_context):
        """Test result contains web_port for web mode."""
        result = await ticket_step.execute(large_project_context)

        assert result.data["mode"] == "web"
        assert result.data["web_port"] == 5050

    @pytest.mark.asyncio
    async def test_result_web_port_none_for_disabled(self, ticket_step, non_interactive_context):
        """Test result web_port is None for disabled mode."""
        result = await ticket_step.execute(non_interactive_context)

        assert result.data["mode"] == "disabled"
        assert result.data["web_port"] is None

    @pytest.mark.asyncio
    async def test_result_success_always_true(self, ticket_step, non_interactive_context):
        """Test result is always successful (optional step)."""
        result = await ticket_step.execute(non_interactive_context)

        assert result.success is True

    @pytest.mark.asyncio
    async def test_result_message_not_empty(self, ticket_step, non_interactive_context):
        """Test result message is not empty."""
        result = await ticket_step.execute(non_interactive_context)

        assert result.message != ""
        assert len(result.message) > 0


# =============================================================================
# INTEGRATION-STYLE TESTS
# =============================================================================


class TestIntegration:
    """Integration-style tests combining multiple operations."""

    @pytest.mark.asyncio
    async def test_full_web_mode_flow(self, ticket_step, wizard_context):
        """Test complete web mode configuration flow."""
        with patch.object(ticket_step, "select_from_list", return_value=["web"]):
            with patch.object(ticket_step, "prompt", return_value="9090"):
                with patch.object(ticket_step, "confirm", side_effect=[True, True]):
                    with patch.object(ticket_step, "show_info"):
                        with patch.object(ticket_step, "show_success"):
                            result = await ticket_step.execute(wizard_context)

        # Verify result
        assert result.success is True
        assert result.data["mode"] == "web"
        assert result.data["web_port"] == 9090
        assert result.data["review_agents"] is True

        # Verify context
        assert wizard_context.tickets_enabled is True
        assert wizard_context.config.tickets.enabled is True
        assert wizard_context.config.tickets.mode == "cli_web"
        assert wizard_context.config.tickets.web_port == 9090
        assert wizard_context.config.tickets.review_agents is True
        assert wizard_context.get("multi_agent_enabled") is True

    @pytest.mark.asyncio
    async def test_full_disabled_mode_flow(self, ticket_step, wizard_context):
        """Test complete disabled mode configuration flow."""
        with patch.object(ticket_step, "select_from_list", return_value=["disabled"]):
            with patch.object(ticket_step, "show_info"):
                with patch.object(ticket_step, "show_success"):
                    result = await ticket_step.execute(wizard_context)

        # Verify result
        assert result.success is True
        assert result.data["mode"] == "disabled"
        assert result.data["enabled"] is False

        # Verify context
        assert wizard_context.tickets_enabled is False
        assert wizard_context.config.tickets.enabled is False

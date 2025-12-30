"""Tests for the GitHub Integration wizard step."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from fastband.core.config import FastbandConfig, GitHubConfig
from fastband.wizard.base import StepStatus, WizardContext
from fastband.wizard.steps.github import (
    GitHubIntegrationStep,
    is_gh_authenticated,
    is_gh_installed,
    is_git_repository,
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
def github_step():
    """Create a GitHubIntegrationStep for testing."""
    return GitHubIntegrationStep()


# =============================================================================
# STEP PROPERTIES TESTS
# =============================================================================


class TestGitHubIntegrationStepProperties:
    """Tests for GitHubIntegrationStep properties."""

    def test_name(self, github_step):
        """Test step name."""
        assert github_step.name == "github"

    def test_title(self, github_step):
        """Test step title."""
        assert github_step.title == "GitHub Integration"

    def test_description(self, github_step):
        """Test step description."""
        assert "GitHub" in github_step.description
        assert len(github_step.description) > 0

    def test_required(self, github_step):
        """Test step is not required (optional)."""
        assert github_step.required is False

    def test_initial_status(self, github_step):
        """Test initial status is PENDING."""
        assert github_step.status == StepStatus.PENDING


# =============================================================================
# GIT REPOSITORY DETECTION TESTS
# =============================================================================


class TestGitRepositoryDetection:
    """Tests for git repository detection."""

    def test_is_git_repository_true(self, temp_dir):
        """Test detection of a git repository."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "true\n"

        with patch("fastband.wizard.steps.github._run_command", return_value=mock_result):
            assert is_git_repository(str(temp_dir)) is True

    def test_is_git_repository_false(self, temp_dir):
        """Test detection of non-git directory."""
        mock_result = MagicMock()
        mock_result.returncode = 128
        mock_result.stdout = ""

        with patch("fastband.wizard.steps.github._run_command", return_value=mock_result):
            assert is_git_repository(str(temp_dir)) is False

    def test_is_git_repository_git_not_installed(self, temp_dir):
        """Test handling when git is not installed."""
        with patch(
            "fastband.wizard.steps.github._run_command",
            side_effect=FileNotFoundError("git not found"),
        ):
            assert is_git_repository(str(temp_dir)) is False


# =============================================================================
# GITHUB CLI DETECTION TESTS
# =============================================================================


class TestGitHubCLIDetection:
    """Tests for GitHub CLI detection."""

    def test_is_gh_installed_true(self):
        """Test detection when gh is installed."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "gh version 2.40.0"

        with patch("fastband.wizard.steps.github._run_command", return_value=mock_result):
            assert is_gh_installed() is True

    def test_is_gh_installed_false(self):
        """Test detection when gh is not installed."""
        with patch(
            "fastband.wizard.steps.github._run_command",
            side_effect=FileNotFoundError("gh not found"),
        ):
            assert is_gh_installed() is False

    def test_is_gh_authenticated_true(self):
        """Test detection when gh is authenticated."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Logged in to github.com"

        with patch("fastband.wizard.steps.github._run_command", return_value=mock_result):
            assert is_gh_authenticated() is True

    def test_is_gh_authenticated_false(self):
        """Test detection when gh is not authenticated."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "You are not logged in"

        with patch("fastband.wizard.steps.github._run_command", return_value=mock_result):
            assert is_gh_authenticated() is False

    def test_is_gh_authenticated_not_installed(self):
        """Test handling when gh is not installed during auth check."""
        with patch(
            "fastband.wizard.steps.github._run_command",
            side_effect=FileNotFoundError("gh not found"),
        ):
            assert is_gh_authenticated() is False


# =============================================================================
# STEP EXECUTION TESTS - NOT A GIT REPOSITORY
# =============================================================================


class TestGitHubStepNotGitRepo:
    """Tests for step execution when not in a git repository."""

    @pytest.mark.asyncio
    async def test_execute_not_git_repo(self, github_step, wizard_context):
        """Test execution when not in a git repository."""
        with patch("fastband.wizard.steps.github.is_git_repository", return_value=False):
            result = await github_step.execute(wizard_context)

        assert result.success is True
        assert result.data["github_enabled"] is False
        assert result.data["reason"] == "not_git_repository"
        assert wizard_context.github_enabled is False
        assert wizard_context.config.github.enabled is False


# =============================================================================
# STEP EXECUTION TESTS - GH NOT INSTALLED
# =============================================================================


class TestGitHubStepGhNotInstalled:
    """Tests for step execution when GitHub CLI is not installed."""

    @pytest.mark.asyncio
    async def test_execute_gh_not_installed(self, github_step, wizard_context):
        """Test execution when gh is not installed."""
        with patch("fastband.wizard.steps.github.is_git_repository", return_value=True):
            with patch("fastband.wizard.steps.github.is_gh_installed", return_value=False):
                result = await github_step.execute(wizard_context)

        assert result.success is True
        assert result.data["github_enabled"] is False
        assert result.data["reason"] == "gh_not_installed"
        assert wizard_context.github_enabled is False


# =============================================================================
# STEP EXECUTION TESTS - GH NOT AUTHENTICATED
# =============================================================================


class TestGitHubStepGhNotAuthenticated:
    """Tests for step execution when GitHub CLI is not authenticated."""

    @pytest.mark.asyncio
    async def test_execute_gh_not_authenticated(self, github_step, wizard_context):
        """Test execution when gh is not authenticated."""
        with patch("fastband.wizard.steps.github.is_git_repository", return_value=True):
            with patch("fastband.wizard.steps.github.is_gh_installed", return_value=True):
                with patch("fastband.wizard.steps.github.is_gh_authenticated", return_value=False):
                    result = await github_step.execute(wizard_context)

        assert result.success is True
        assert result.data["github_enabled"] is False
        assert result.data["reason"] == "gh_not_authenticated"
        assert wizard_context.github_enabled is False


# =============================================================================
# NON-INTERACTIVE MODE TESTS
# =============================================================================


class TestGitHubStepNonInteractive:
    """Tests for non-interactive mode."""

    @pytest.mark.asyncio
    async def test_non_interactive_not_enabled(self, github_step, non_interactive_context):
        """Test non-interactive mode when GitHub not already enabled."""
        # Ensure github is not enabled in config
        non_interactive_context.config.github = GitHubConfig(enabled=False)

        with patch("fastband.wizard.steps.github.is_git_repository", return_value=True):
            with patch("fastband.wizard.steps.github.is_gh_installed", return_value=True):
                with patch("fastband.wizard.steps.github.is_gh_authenticated", return_value=True):
                    result = await github_step.execute(non_interactive_context)

        assert result.success is True
        assert result.data["github_enabled"] is False
        assert result.data["reason"] == "non_interactive"
        assert result.data["already_configured"] is False
        assert non_interactive_context.github_enabled is False

    @pytest.mark.asyncio
    async def test_non_interactive_already_enabled(self, github_step, non_interactive_context):
        """Test non-interactive mode when GitHub already enabled in config."""
        # Set github as already enabled in config
        non_interactive_context.config.github = GitHubConfig(
            enabled=True,
            automation_level="hybrid",
            default_branch="main",
        )

        with patch("fastband.wizard.steps.github.is_git_repository", return_value=True):
            with patch("fastband.wizard.steps.github.is_gh_installed", return_value=True):
                with patch("fastband.wizard.steps.github.is_gh_authenticated", return_value=True):
                    result = await github_step.execute(non_interactive_context)

        assert result.success is True
        assert result.data["github_enabled"] is True
        assert result.data["reason"] == "non_interactive"
        assert result.data["already_configured"] is True
        assert non_interactive_context.github_enabled is True


# =============================================================================
# INTERACTIVE MODE TESTS
# =============================================================================


class TestGitHubStepInteractive:
    """Tests for interactive mode."""

    @pytest.mark.asyncio
    async def test_interactive_user_enables(self, github_step, wizard_context):
        """Test interactive mode when user enables GitHub."""
        with patch("fastband.wizard.steps.github.is_git_repository", return_value=True):
            with patch("fastband.wizard.steps.github.is_gh_installed", return_value=True):
                with patch("fastband.wizard.steps.github.is_gh_authenticated", return_value=True):
                    with patch.object(github_step, "confirm", return_value=True):
                        with patch.object(
                            github_step, "_select_automation_level", return_value="hybrid"
                        ):
                            with patch.object(
                                github_step, "_get_default_branch", return_value="main"
                            ):
                                result = await github_step.execute(wizard_context)

        assert result.success is True
        assert result.data["github_enabled"] is True
        assert result.data["automation_level"] == "hybrid"
        assert result.data["default_branch"] == "main"
        assert wizard_context.github_enabled is True
        assert wizard_context.config.github.enabled is True
        assert wizard_context.config.github.automation_level == "hybrid"

    @pytest.mark.asyncio
    async def test_interactive_user_declines(self, github_step, wizard_context):
        """Test interactive mode when user declines GitHub."""
        with patch("fastband.wizard.steps.github.is_git_repository", return_value=True):
            with patch("fastband.wizard.steps.github.is_gh_installed", return_value=True):
                with patch("fastband.wizard.steps.github.is_gh_authenticated", return_value=True):
                    with patch.object(github_step, "confirm", return_value=False):
                        result = await github_step.execute(wizard_context)

        assert result.success is True
        assert result.data["github_enabled"] is False
        assert result.data["reason"] == "user_declined"
        assert wizard_context.github_enabled is False
        assert wizard_context.config.github.enabled is False


# =============================================================================
# AUTOMATION LEVEL SELECTION TESTS
# =============================================================================


class TestAutomationLevelSelection:
    """Tests for automation level selection."""

    def test_select_automation_level_full(self, github_step):
        """Test selecting full automation."""
        with patch.object(github_step, "select_from_list", return_value=["full"]):
            result = github_step._select_automation_level()
        assert result == "full"

    def test_select_automation_level_hybrid(self, github_step):
        """Test selecting hybrid automation."""
        with patch.object(github_step, "select_from_list", return_value=["hybrid"]):
            result = github_step._select_automation_level()
        assert result == "hybrid"

    def test_select_automation_level_guided(self, github_step):
        """Test selecting guided automation."""
        with patch.object(github_step, "select_from_list", return_value=["guided"]):
            result = github_step._select_automation_level()
        assert result == "guided"

    def test_select_automation_level_none(self, github_step):
        """Test selecting read-only (none) automation."""
        with patch.object(github_step, "select_from_list", return_value=["none"]):
            result = github_step._select_automation_level()
        assert result == "none"

    def test_select_automation_level_empty_defaults_to_hybrid(self, github_step):
        """Test that empty selection defaults to hybrid."""
        with patch.object(github_step, "select_from_list", return_value=[]):
            result = github_step._select_automation_level()
        assert result == "hybrid"


# =============================================================================
# DEFAULT BRANCH DETECTION TESTS
# =============================================================================


class TestDefaultBranchDetection:
    """Tests for default branch detection."""

    def test_get_default_branch_from_config(self, github_step, temp_dir):
        """Test getting default branch from git config."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "develop\n"

        with patch("fastband.wizard.steps.github._run_command", return_value=mock_result):
            result = github_step._get_default_branch(str(temp_dir))
        assert result == "develop"

    def test_get_default_branch_from_remote(self, github_step, temp_dir):
        """Test getting default branch from remote HEAD."""
        # First call returns empty (no config)
        config_result = MagicMock()
        config_result.returncode = 1
        config_result.stdout = ""

        # Second call returns remote HEAD
        remote_result = MagicMock()
        remote_result.returncode = 0
        remote_result.stdout = "refs/remotes/origin/main\n"

        with patch(
            "fastband.wizard.steps.github._run_command",
            side_effect=[config_result, remote_result],
        ):
            result = github_step._get_default_branch(str(temp_dir))
        assert result == "main"

    def test_get_default_branch_from_current(self, github_step, temp_dir):
        """Test getting default branch from current branch."""
        # First two calls return empty
        empty_result = MagicMock()
        empty_result.returncode = 1
        empty_result.stdout = ""

        # Third call returns current branch
        current_result = MagicMock()
        current_result.returncode = 0
        current_result.stdout = "feature-branch\n"

        with patch(
            "fastband.wizard.steps.github._run_command",
            side_effect=[empty_result, empty_result, current_result],
        ):
            result = github_step._get_default_branch(str(temp_dir))
        assert result == "feature-branch"

    def test_get_default_branch_fallback_to_main(self, github_step, temp_dir):
        """Test fallback to 'main' when detection fails."""
        # All calls fail
        fail_result = MagicMock()
        fail_result.returncode = 1
        fail_result.stdout = ""

        with patch(
            "fastband.wizard.steps.github._run_command",
            side_effect=[fail_result, fail_result, fail_result],
        ):
            result = github_step._get_default_branch(str(temp_dir))
        assert result == "main"

    def test_get_default_branch_exception_fallback(self, github_step, temp_dir):
        """Test fallback to 'main' on exception."""
        with patch(
            "fastband.wizard.steps.github._run_command",
            side_effect=Exception("Unexpected error"),
        ):
            result = github_step._get_default_branch(str(temp_dir))
        assert result == "main"


# =============================================================================
# INSTRUCTION DISPLAY TESTS
# =============================================================================


class TestInstructionDisplay:
    """Tests for instruction display methods."""

    def test_show_gh_install_instructions(self, github_step):
        """Test that install instructions don't raise errors."""
        # Just verify it doesn't raise an exception
        github_step._show_gh_install_instructions()

    def test_show_gh_auth_instructions(self, github_step):
        """Test that auth instructions don't raise errors."""
        # Just verify it doesn't raise an exception
        github_step._show_gh_auth_instructions()


# =============================================================================
# CONTEXT CONFIGURATION TESTS
# =============================================================================


class TestContextConfiguration:
    """Tests for context and config updates."""

    @pytest.mark.asyncio
    async def test_context_github_config_updated(self, github_step, wizard_context):
        """Test that context.config.github is properly updated."""
        with patch("fastband.wizard.steps.github.is_git_repository", return_value=True):
            with patch("fastband.wizard.steps.github.is_gh_installed", return_value=True):
                with patch("fastband.wizard.steps.github.is_gh_authenticated", return_value=True):
                    with patch.object(github_step, "confirm", return_value=True):
                        with patch.object(
                            github_step, "_select_automation_level", return_value="full"
                        ):
                            with patch.object(
                                github_step, "_get_default_branch", return_value="develop"
                            ):
                                await github_step.execute(wizard_context)

        assert wizard_context.config.github.enabled is True
        assert wizard_context.config.github.automation_level == "full"
        assert wizard_context.config.github.default_branch == "develop"

    @pytest.mark.asyncio
    async def test_github_enabled_flag_set(self, github_step, wizard_context):
        """Test that context.github_enabled is properly set."""
        with patch("fastband.wizard.steps.github.is_git_repository", return_value=True):
            with patch("fastband.wizard.steps.github.is_gh_installed", return_value=True):
                with patch("fastband.wizard.steps.github.is_gh_authenticated", return_value=True):
                    with patch.object(github_step, "confirm", return_value=True):
                        with patch.object(
                            github_step, "_select_automation_level", return_value="hybrid"
                        ):
                            with patch.object(
                                github_step, "_get_default_branch", return_value="main"
                            ):
                                await github_step.execute(wizard_context)

        assert wizard_context.github_enabled is True

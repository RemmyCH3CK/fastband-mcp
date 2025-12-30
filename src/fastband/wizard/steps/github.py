"""
GitHub Integration wizard step.

Detects git repository and GitHub CLI, offers to enable GitHub features.
"""

import subprocess

from fastband.core.config import GitHubConfig
from fastband.wizard.base import StepResult, WizardContext, WizardStep


def _run_command(args: list[str], cwd: str | None = None) -> subprocess.CompletedProcess:
    """
    Run a command and return the result.

    Args:
        args: Command arguments
        cwd: Working directory for the command

    Returns:
        CompletedProcess with stdout and stderr
    """
    return subprocess.run(
        args,
        cwd=cwd,
        capture_output=True,
        text=True,
    )


def is_git_repository(path: str) -> bool:
    """
    Check if the given path is inside a git repository.

    Args:
        path: Path to check

    Returns:
        True if inside a git repository, False otherwise
    """
    try:
        result = _run_command(["git", "rev-parse", "--is-inside-work-tree"], cwd=path)
        return result.returncode == 0 and result.stdout.strip() == "true"
    except FileNotFoundError:
        return False


def is_gh_installed() -> bool:
    """
    Check if GitHub CLI (gh) is installed.

    Returns:
        True if gh is installed, False otherwise
    """
    try:
        result = _run_command(["gh", "--version"])
        return result.returncode == 0
    except FileNotFoundError:
        return False


def is_gh_authenticated() -> bool:
    """
    Check if GitHub CLI is authenticated.

    Returns:
        True if gh auth status returns success, False otherwise
    """
    try:
        result = _run_command(["gh", "auth", "status"])
        return result.returncode == 0
    except FileNotFoundError:
        return False


class GitHubIntegrationStep(WizardStep):
    """
    GitHub Integration wizard step.

    Detects git repository and GitHub CLI, offers to enable GitHub features
    like issue tracking and PR integration.
    """

    @property
    def name(self) -> str:
        return "github"

    @property
    def title(self) -> str:
        return "GitHub Integration"

    @property
    def description(self) -> str:
        return "Configure GitHub features for issue tracking and PR integration"

    @property
    def required(self) -> bool:
        return False

    async def execute(self, context: WizardContext) -> StepResult:
        """
        Execute the GitHub integration step.

        Args:
            context: Wizard context with project info and settings

        Returns:
            StepResult indicating success/failure and configuration
        """
        project_path = str(context.project_path)

        # Check if in a git repository
        if not is_git_repository(project_path):
            self.show_warning("Not a git repository - GitHub integration disabled")
            context.github_enabled = False
            context.config.github = GitHubConfig(enabled=False)
            return StepResult(
                success=True,
                data={"github_enabled": False, "reason": "not_git_repository"},
                message="Skipped - not a git repository",
            )

        self.show_success("Git repository detected")

        # Check if GitHub CLI is installed
        gh_installed = is_gh_installed()
        if not gh_installed:
            self._show_gh_install_instructions()
            context.github_enabled = False
            context.config.github = GitHubConfig(enabled=False)
            return StepResult(
                success=True,
                data={"github_enabled": False, "reason": "gh_not_installed"},
                message="GitHub CLI not installed",
            )

        self.show_success("GitHub CLI detected")

        # Check if GitHub CLI is authenticated
        gh_authenticated = is_gh_authenticated()
        if not gh_authenticated:
            self._show_gh_auth_instructions()
            context.github_enabled = False
            context.config.github = GitHubConfig(enabled=False)
            return StepResult(
                success=True,
                data={"github_enabled": False, "reason": "gh_not_authenticated"},
                message="GitHub CLI not authenticated",
            )

        self.show_success("GitHub CLI authenticated")

        # In non-interactive mode, enable only if already configured
        if not context.interactive:
            # Check if GitHub was already enabled in existing config
            already_enabled = context.config.github.enabled
            context.github_enabled = already_enabled
            return StepResult(
                success=True,
                data={
                    "github_enabled": already_enabled,
                    "reason": "non_interactive",
                    "already_configured": already_enabled,
                },
                message="GitHub integration preserved from config"
                if already_enabled
                else "GitHub integration not enabled (non-interactive mode)",
            )

        # Interactive mode - ask user
        self.console.print()
        self.console.print("[bold]Available GitHub Features:[/bold]")
        self.console.print("  - Issue tracking: Create and manage GitHub issues")
        self.console.print("  - PR integration: Create and review pull requests")
        self.console.print("  - Automation: Auto-update issues based on commits")
        self.console.print()

        enable_github = self.confirm(
            "Enable GitHub integration?",
            default=True,
        )

        if enable_github:
            # Ask for automation level
            automation_level = self._select_automation_level()
            default_branch = self._get_default_branch(project_path)

            context.github_enabled = True
            context.config.github = GitHubConfig(
                enabled=True,
                automation_level=automation_level,
                default_branch=default_branch,
            )

            self.show_success(f"GitHub integration enabled (automation: {automation_level})")
            return StepResult(
                success=True,
                data={
                    "github_enabled": True,
                    "automation_level": automation_level,
                    "default_branch": default_branch,
                },
                message="GitHub integration enabled",
            )
        else:
            context.github_enabled = False
            context.config.github = GitHubConfig(enabled=False)
            self.show_info("GitHub integration disabled")
            return StepResult(
                success=True,
                data={"github_enabled": False, "reason": "user_declined"},
                message="GitHub integration disabled by user",
            )

    def _show_gh_install_instructions(self) -> None:
        """Display instructions for installing GitHub CLI."""
        self.show_warning("GitHub CLI (gh) is not installed")
        self.console.print()
        self.console.print("[bold]To install GitHub CLI:[/bold]")
        self.console.print("  macOS:   [dim]brew install gh[/dim]")
        self.console.print(
            "  Linux:   [dim]See https://github.com/cli/cli/blob/trunk/docs/install_linux.md[/dim]"
        )
        self.console.print("  Windows: [dim]winget install --id GitHub.cli[/dim]")
        self.console.print()
        self.console.print("After installing, run: [dim]gh auth login[/dim]")
        self.console.print()

    def _show_gh_auth_instructions(self) -> None:
        """Display instructions for authenticating GitHub CLI."""
        self.show_warning("GitHub CLI is not authenticated")
        self.console.print()
        self.console.print("[bold]To authenticate GitHub CLI:[/bold]")
        self.console.print("  1. Run: [dim]gh auth login[/dim]")
        self.console.print("  2. Follow the prompts to authenticate")
        self.console.print("  3. Re-run the Fastband setup wizard")
        self.console.print()

    def _select_automation_level(self) -> str:
        """
        Let user select the GitHub automation level.

        Returns:
            Selected automation level
        """
        options = [
            {
                "value": "full",
                "label": "Full Automation",
                "description": "Automatically create issues, PRs, and update status",
            },
            {
                "value": "hybrid",
                "label": "Hybrid (Recommended)",
                "description": "Agent suggests, you approve before action",
            },
            {
                "value": "guided",
                "label": "Guided",
                "description": "Agent provides commands, you execute manually",
            },
            {
                "value": "none",
                "label": "Read-Only",
                "description": "Only read GitHub data, no modifications",
            },
        ]

        selected = self.select_from_list(
            "Select GitHub automation level:",
            options,
            allow_multiple=False,
        )

        return selected[0] if selected else "hybrid"

    def _get_default_branch(self, project_path: str) -> str:
        """
        Detect the default branch of the repository.

        Args:
            project_path: Path to the git repository

        Returns:
            Default branch name (defaults to 'main')
        """
        try:
            # Try to get the default branch from git config
            result = _run_command(
                ["git", "config", "--get", "init.defaultBranch"],
                cwd=project_path,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()

            # Try to detect from remote
            result = _run_command(
                ["git", "symbolic-ref", "refs/remotes/origin/HEAD"],
                cwd=project_path,
            )
            if result.returncode == 0:
                # Format: refs/remotes/origin/main
                ref = result.stdout.strip()
                if ref:
                    return ref.split("/")[-1]

            # Try current branch
            result = _run_command(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=project_path,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()

        except Exception:
            pass

        return "main"

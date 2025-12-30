"""
Setup Wizard base classes and framework.

Provides the foundation for the interactive setup wizard including:
- WizardStep: Base class for individual wizard steps
- SetupWizard: Main wizard controller with step navigation
- WizardContext: Shared context across all steps
- StepResult: Result object from step execution
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

from fastband.core.config import FastbandConfig


class StepStatus(Enum):
    """Status of a wizard step."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass
class StepResult:
    """Result from executing a wizard step."""

    success: bool
    data: dict[str, Any] = field(default_factory=dict)
    message: str = ""
    skip_remaining: bool = False  # Skip all remaining steps
    go_back: bool = False  # User wants to go back


@dataclass
class WizardContext:
    """
    Shared context across all wizard steps.

    Stores configuration being built, project info, and user choices.
    """

    project_path: Path
    config: FastbandConfig = field(default_factory=FastbandConfig)
    interactive: bool = True

    # Collected data from steps
    project_info: Any | None = None  # ProjectInfo from detection
    selected_provider: str | None = None
    selected_tools: list[str] = field(default_factory=list)
    github_enabled: bool = False
    tickets_enabled: bool = False
    backup_enabled: bool = True

    # Additional metadata
    metadata: dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        """Get a value from metadata."""
        return self.metadata.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set a value in metadata."""
        self.metadata[key] = value


class WizardStep(ABC):
    """
    Base class for wizard steps.

    Each step represents a configuration section in the setup wizard.
    Steps can be interactive (prompt user) or automatic (detect and suggest).
    """

    def __init__(self, console: Console | None = None):
        self.console = console or Console()
        self._status = StepStatus.PENDING

    @property
    @abstractmethod
    def name(self) -> str:
        """Short name for the step."""
        pass

    @property
    @abstractmethod
    def title(self) -> str:
        """Display title for the step."""
        pass

    @property
    def description(self) -> str:
        """Optional description shown before step execution."""
        return ""

    @property
    def required(self) -> bool:
        """Whether this step is required (cannot be skipped)."""
        return False

    @property
    def status(self) -> StepStatus:
        """Current step status."""
        return self._status

    @status.setter
    def status(self, value: StepStatus) -> None:
        self._status = value

    def should_skip(self, context: WizardContext) -> bool:
        """
        Check if this step should be skipped based on context.

        Override in subclasses to conditionally skip steps.
        """
        return False

    @abstractmethod
    async def execute(self, context: WizardContext) -> StepResult:
        """
        Execute the step.

        Args:
            context: Shared wizard context

        Returns:
            StepResult indicating success/failure and any data
        """
        pass

    async def validate(self, context: WizardContext) -> bool:
        """
        Validate step configuration before proceeding.

        Override in subclasses for custom validation.
        """
        return True

    def show_header(self) -> None:
        """Display step header."""
        self.console.print()
        self.console.print(
            Panel(
                f"[bold blue]{self.title}[/bold blue]",
                subtitle=self.description if self.description else None,
                border_style="blue",
            )
        )

    def show_success(self, message: str) -> None:
        """Display success message."""
        self.console.print(f"[green]✓[/green] {message}")

    def show_error(self, message: str) -> None:
        """Display error message."""
        self.console.print(f"[red]✗[/red] {message}")

    def show_warning(self, message: str) -> None:
        """Display warning message."""
        self.console.print(f"[yellow]![/yellow] {message}")

    def show_info(self, message: str) -> None:
        """Display info message."""
        self.console.print(f"[blue]ℹ[/blue] {message}")

    def prompt(
        self,
        message: str,
        default: str | None = None,
        choices: list[str] | None = None,
    ) -> str:
        """Prompt user for input."""
        return Prompt.ask(
            message,
            default=default,
            choices=choices,
            console=self.console,
        )

    def confirm(self, message: str, default: bool = True) -> bool:
        """Prompt user for confirmation."""
        return Confirm.ask(message, default=default, console=self.console)

    def select_from_list(
        self,
        title: str,
        options: list[dict[str, str]],
        allow_multiple: bool = False,
    ) -> list[str]:
        """
        Display a selection list and get user choice(s).

        Args:
            title: Title for the selection
            options: List of dicts with 'value', 'label', and optional 'description'
            allow_multiple: Whether multiple selections are allowed

        Returns:
            List of selected values
        """
        table = Table(
            title=title,
            box=box.ROUNDED,
            show_header=True,
        )
        table.add_column("#", style="dim", width=3)
        table.add_column("Option", style="cyan")
        table.add_column("Description", style="dim")

        for i, opt in enumerate(options, 1):
            table.add_row(
                str(i),
                opt.get("label", opt["value"]),
                opt.get("description", ""),
            )

        self.console.print(table)

        if allow_multiple:
            prompt = "Enter numbers separated by commas (e.g., 1,3,5)"
        else:
            prompt = "Enter number"

        while True:
            choice = self.prompt(prompt)
            try:
                if allow_multiple:
                    indices = [int(x.strip()) for x in choice.split(",")]
                else:
                    indices = [int(choice.strip())]

                # Validate indices
                if all(1 <= i <= len(options) for i in indices):
                    return [options[i - 1]["value"] for i in indices]
                else:
                    self.show_error(f"Please enter numbers between 1 and {len(options)}")
            except ValueError:
                self.show_error("Please enter valid number(s)")


class SetupWizard:
    """
    Main wizard controller.

    Manages step execution, navigation, and configuration persistence.
    """

    def __init__(
        self,
        project_path: Path,
        console: Console | None = None,
        interactive: bool = True,
    ):
        self.project_path = project_path.resolve()
        self.console = console or Console()
        self.interactive = interactive

        self.steps: list[WizardStep] = []
        self.current_step_index = 0
        self.context = WizardContext(
            project_path=self.project_path,
            interactive=interactive,
        )

    def add_step(self, step: WizardStep) -> "SetupWizard":
        """Add a step to the wizard."""
        step.console = self.console
        self.steps.append(step)
        return self

    def add_steps(self, steps: list[WizardStep]) -> "SetupWizard":
        """Add multiple steps to the wizard."""
        for step in steps:
            self.add_step(step)
        return self

    @property
    def current_step(self) -> WizardStep | None:
        """Get the current step."""
        if 0 <= self.current_step_index < len(self.steps):
            return self.steps[self.current_step_index]
        return None

    @property
    def progress(self) -> float:
        """Get wizard progress as percentage."""
        if not self.steps:
            return 0.0
        completed = sum(1 for s in self.steps if s.status == StepStatus.COMPLETED)
        return (completed / len(self.steps)) * 100

    def show_welcome(self) -> None:
        """Display welcome message."""
        self.console.print()
        self.console.print(
            Panel.fit(
                "[bold blue]Fastband Setup Wizard[/bold blue]\n\n"
                f"[dim]Project: {self.project_path}[/dim]",
                border_style="blue",
            )
        )
        self.console.print()
        self.console.print(
            "This wizard will guide you through configuring Fastband for your project."
        )
        self.console.print("Press [bold]Ctrl+C[/bold] at any time to cancel.\n")

    def show_progress(self) -> None:
        """Display progress bar showing completed steps."""
        table = Table(
            box=box.SIMPLE,
            show_header=False,
            padding=(0, 1),
        )
        table.add_column("Step", style="dim")
        table.add_column("Status")

        status_icons = {
            StepStatus.PENDING: "[dim]○[/dim]",
            StepStatus.IN_PROGRESS: "[blue]●[/blue]",
            StepStatus.COMPLETED: "[green]✓[/green]",
            StepStatus.SKIPPED: "[yellow]○[/yellow]",
            StepStatus.FAILED: "[red]✗[/red]",
        }

        for i, step in enumerate(self.steps):
            marker = "→ " if i == self.current_step_index else "  "
            icon = status_icons.get(step.status, "○")
            style = "bold" if i == self.current_step_index else ""
            table.add_row(
                f"{marker}{step.name}",
                icon,
                style=style,
            )

        self.console.print(table)

    async def run(self) -> bool:
        """
        Run the wizard.

        Returns:
            True if wizard completed successfully, False otherwise
        """
        if self.interactive:
            self.show_welcome()

        try:
            while self.current_step_index < len(self.steps):
                step = self.current_step
                if step is None:
                    break

                # Check if step should be skipped
                if step.should_skip(self.context):
                    step.status = StepStatus.SKIPPED
                    self.current_step_index += 1
                    continue

                # Show progress in interactive mode
                if self.interactive:
                    self.show_progress()

                # Execute step
                step.status = StepStatus.IN_PROGRESS
                step.show_header()

                try:
                    result = await step.execute(self.context)
                except KeyboardInterrupt:
                    self.console.print("\n[yellow]Wizard cancelled by user.[/yellow]")
                    return False
                except Exception as e:
                    step.status = StepStatus.FAILED
                    step.show_error(f"Step failed: {e}")
                    if self.interactive:
                        if not Confirm.ask("Continue anyway?", default=False):
                            return False
                    else:
                        return False
                    self.current_step_index += 1
                    continue

                # Handle result
                if result.go_back and self.current_step_index > 0:
                    step.status = StepStatus.PENDING
                    self.current_step_index -= 1
                    continue

                if result.skip_remaining:
                    step.status = StepStatus.COMPLETED
                    break

                if result.success:
                    step.status = StepStatus.COMPLETED
                    # Validate before proceeding
                    if not await step.validate(self.context):
                        step.show_warning("Validation failed, please try again")
                        step.status = StepStatus.PENDING
                        continue
                else:
                    step.status = StepStatus.FAILED
                    if step.required:
                        step.show_error(result.message or "Step failed")
                        if self.interactive:
                            if Confirm.ask("Try again?", default=True):
                                step.status = StepStatus.PENDING
                                continue
                        return False

                self.current_step_index += 1

            # Save configuration
            await self.save_config()

            if self.interactive:
                self.show_completion()

            return True

        except KeyboardInterrupt:
            self.console.print("\n[yellow]Wizard cancelled.[/yellow]")
            return False

    async def save_config(self) -> None:
        """Save the configuration to disk."""
        config_dir = self.project_path / ".fastband"
        config_dir.mkdir(parents=True, exist_ok=True)

        config_file = config_dir / "config.yaml"
        self.context.config.save(config_file)

        self.console.print(f"\n[green]✓[/green] Configuration saved to {config_file}")

    def show_completion(self) -> None:
        """Display completion message with next steps."""
        self.console.print()
        self.console.print(
            Panel.fit(
                "[bold green]Setup Complete![/bold green]\n\n"
                "Fastband is now configured for your project.",
                border_style="green",
            )
        )

        self.console.print("\n[bold]Next steps:[/bold]")
        self.console.print("  1. Start the MCP server: [dim]fastband serve[/dim]")
        self.console.print("  2. Check status: [dim]fastband status[/dim]")
        self.console.print("  3. View available tools: [dim]fastband tools list[/dim]")

        if self.context.github_enabled:
            self.console.print("  4. View GitHub integration: [dim]fastband github status[/dim]")

        if self.context.tickets_enabled:
            self.console.print("  5. Start ticket dashboard: [dim]fastband tickets serve[/dim]")


# Convenience function to run wizard with default steps
async def run_setup_wizard(
    project_path: Path,
    interactive: bool = True,
    steps: list[WizardStep] | None = None,
) -> bool:
    """
    Run the setup wizard with optional custom steps.

    Args:
        project_path: Path to the project
        interactive: Whether to run in interactive mode
        steps: Optional list of steps (uses defaults if not provided)

    Returns:
        True if wizard completed successfully
    """
    wizard = SetupWizard(
        project_path=project_path,
        interactive=interactive,
    )

    if steps:
        wizard.add_steps(steps)
    else:
        # Import default steps
        from fastband.wizard.steps import get_default_steps

        wizard.add_steps(get_default_steps())

    return await wizard.run()

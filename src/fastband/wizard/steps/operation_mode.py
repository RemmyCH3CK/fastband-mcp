"""
Operation mode wizard step.

Allows users to choose between Manual and YOLO automation modes.
"""

from rich.panel import Panel
from rich.table import Table
from rich import box

from fastband.wizard.base import StepResult, WizardContext, WizardStep


class OperationModeStep(WizardStep):
    """
    Choose automation level for AI agents.

    - Manual: Agents confirm all actions via chat/CLI
    - YOLO: Full automation following Agent Bible laws
    """

    @property
    def name(self) -> str:
        return "Operation Mode"

    @property
    def title(self) -> str:
        return "Agent Operation Mode"

    @property
    def description(self) -> str:
        return "Choose how autonomous your AI agents should be"

    @property
    def required(self) -> bool:
        return True

    async def execute(self, context: WizardContext) -> StepResult:
        """Execute the operation mode selection step."""

        # Display mode comparison
        self.console.print(
            Panel(
                "[bold]Choose Your Automation Level[/bold]\n\n"
                "This setting controls how much autonomy AI agents have\n"
                "when performing tasks in your project.",
                border_style="cyan",
            )
        )

        # Create comparison table
        table = Table(
            box=box.ROUNDED,
            show_header=True,
            header_style="bold cyan",
        )
        table.add_column("Aspect", style="dim")
        table.add_column("Manual Mode", style="yellow")
        table.add_column("YOLO Mode", style="magenta")

        table.add_row(
            "Confirmation",
            "Ask before every action",
            "Autonomous execution",
        )
        table.add_row(
            "Code Changes",
            "Propose & await approval",
            "Apply directly (with review)",
        )
        table.add_row(
            "Git Operations",
            "Confirm each commit/push",
            "Auto-commit following patterns",
        )
        table.add_row(
            "Deployments",
            "Manual trigger required",
            "Auto-deploy if tests pass",
        )
        table.add_row(
            "Ticket Claims",
            "Suggest & await approval",
            "Auto-claim matching tickets",
        )
        table.add_row(
            "Best For",
            "Learning, critical systems",
            "Trusted workflows, speed",
        )

        self.console.print(table)
        self.console.print()

        # Mode selection
        choices = [
            {
                "value": "manual",
                "label": "Manual Mode (Recommended)",
                "description": "Agents confirm all actions - maximum control",
            },
            {
                "value": "yolo",
                "label": "YOLO Mode",
                "description": "Full automation following Agent Bible laws",
            },
        ]

        selection = self.select_from_list("Select operation mode", choices)
        mode = selection[0] if selection else "manual"

        if mode == "yolo":
            # Show YOLO warning
            self.console.print()
            self.console.print(
                Panel(
                    "[bold yellow]YOLO Mode Warning[/bold yellow]\n\n"
                    "[yellow]In YOLO mode, agents will:[/yellow]\n"
                    "  • Automatically execute code changes\n"
                    "  • Push commits without confirmation\n"
                    "  • Deploy changes if tests pass\n"
                    "  • Claim and work on tickets autonomously\n\n"
                    "[dim]Agents will follow rules defined in your Agent Bible.\n"
                    "You can edit these rules at any time via:[/dim]\n"
                    "  • Hub: Settings → Agent Bible\n"
                    "  • CLI: fastband bible edit\n\n"
                    "[bold]Make sure your AGENT_BIBLE.md has clear safety rules![/bold]",
                    border_style="yellow",
                )
            )

            if not self.confirm("Enable YOLO mode?", default=False):
                mode = "manual"
                self.show_info("Switched to Manual mode")

        # Save to context and config
        context.set("operation_mode", mode)
        context.config.operation_mode = mode

        if mode == "manual":
            self.show_success("Manual mode enabled - agents will confirm all actions")
        else:
            self.show_success("YOLO mode enabled - agents will operate autonomously")

        # Remind about Agent Bible
        self.console.print()
        self.console.print(
            "[dim]Tip: Define agent rules in AGENT_BIBLE.md to customize behavior.[/dim]"
        )

        return StepResult(
            success=True,
            data={"operation_mode": mode},
        )

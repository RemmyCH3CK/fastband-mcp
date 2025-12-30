"""
Ticket Manager setup wizard step.

Configures the ticket management system including:
- Interface mode (CLI, Web Dashboard, or Disabled)
- Web dashboard port configuration
- Ticket workflow options
- Agent coordination settings
"""

from fastband.core.config import TicketsConfig
from fastband.wizard.base import StepResult, WizardContext, WizardStep


class TicketManagerStep(WizardStep):
    """
    Wizard step for configuring the Ticket Manager.

    This step allows users to:
    - Choose ticket interface mode (cli, web, disabled)
    - Configure web dashboard port if web mode selected
    - Set up initial ticket workflow options
    - Configure agent coordination settings
    """

    # Mode options with descriptions
    MODE_OPTIONS = [
        {
            "value": "cli",
            "label": "CLI Only",
            "description": "Command-line ticket management (lightweight)",
        },
        {
            "value": "web",
            "label": "Web Dashboard",
            "description": "Full web-based ticket interface with dashboard",
        },
        {
            "value": "disabled",
            "label": "Disabled",
            "description": "No ticket management (can enable later)",
        },
    ]

    # Default port for web dashboard
    DEFAULT_WEB_PORT = 5050

    # Threshold for considering a project "large"
    LARGE_PROJECT_FILE_COUNT = 50

    @property
    def name(self) -> str:
        """Short name for the step."""
        return "tickets"

    @property
    def title(self) -> str:
        """Display title for the step."""
        return "Ticket Manager Setup"

    @property
    def description(self) -> str:
        """Description shown before step execution."""
        return "Configure ticket tracking and agent coordination"

    @property
    def required(self) -> bool:
        """This step is optional."""
        return False

    def _is_large_project(self, context: WizardContext) -> bool:
        """
        Determine if the project is considered large.

        A large project benefits more from ticket management.
        """
        file_count = 0

        # First try to get from project_info if available
        project_info = context.project_info
        if project_info is not None:
            file_count = getattr(project_info, "file_count", 0)

        # Fall back to metadata if project_info doesn't have it
        if file_count == 0:
            file_count = context.get("file_count", 0)

        return file_count >= self.LARGE_PROJECT_FILE_COUNT

    def _get_default_mode(self, context: WizardContext) -> str:
        """
        Get the default mode based on project characteristics.

        Large projects default to 'web', others to 'disabled'.
        """
        if self._is_large_project(context):
            return "web"
        return "disabled"

    async def execute(self, context: WizardContext) -> StepResult:
        """
        Execute the ticket manager setup step.

        Args:
            context: Shared wizard context

        Returns:
            StepResult indicating success and any data collected
        """
        if not context.interactive:
            # Non-interactive mode: use defaults based on project size
            return await self._execute_non_interactive(context)

        return await self._execute_interactive(context)

    async def _execute_non_interactive(self, context: WizardContext) -> StepResult:
        """Execute in non-interactive mode with sensible defaults."""
        default_mode = self._get_default_mode(context)

        # Configure based on default mode
        tickets_config = TicketsConfig(
            enabled=default_mode != "disabled",
            mode=self._translate_mode(default_mode),
            web_port=self.DEFAULT_WEB_PORT,
            review_agents=default_mode == "web",  # Enable review agents for web mode
        )

        # Save to context
        context.tickets_enabled = default_mode != "disabled"
        context.config.tickets = tickets_config

        self.show_info(f"Ticket manager set to: {default_mode}")

        return StepResult(
            success=True,
            data={
                "mode": default_mode,
                "enabled": context.tickets_enabled,
                "web_port": tickets_config.web_port if default_mode == "web" else None,
            },
            message=f"Ticket manager configured in {default_mode} mode",
        )

    async def _execute_interactive(self, context: WizardContext) -> StepResult:
        """Execute in interactive mode with user prompts."""
        # Show current recommendation
        default_mode = self._get_default_mode(context)
        if self._is_large_project(context):
            self.show_info("Detected large project - ticket management recommended")

        # Select mode
        self.console.print("\nSelect ticket management mode:")
        selected = self.select_from_list(
            title="Ticket Interface Mode",
            options=self.MODE_OPTIONS,
            allow_multiple=False,
        )
        mode = selected[0] if selected else default_mode

        # Initialize config
        web_port = self.DEFAULT_WEB_PORT
        review_agents = False

        if mode == "web":
            # Configure web dashboard
            web_port = await self._configure_web_port()

            # Configure workflow options
            workflow_options = await self._configure_workflow_options()
            review_agents = workflow_options.get("review_agents", True)

            # Configure agent coordination
            await self._configure_agent_coordination(context)

        elif mode == "cli":
            # CLI mode - simpler configuration
            self.show_info("CLI mode enabled - use 'fastband tickets' commands")
            review_agents = self.confirm(
                "Enable agent code review workflow?",
                default=False,
            )

        else:
            # Disabled mode
            self.show_info("Ticket management disabled - you can enable it later")

        # Create configuration
        tickets_config = TicketsConfig(
            enabled=mode != "disabled",
            mode=self._translate_mode(mode),
            web_port=web_port,
            review_agents=review_agents,
        )

        # Save to context
        context.tickets_enabled = mode != "disabled"
        context.config.tickets = tickets_config

        # Store additional workflow settings in metadata
        if mode != "disabled":
            context.set("tickets_mode", mode)

        self.show_success(f"Ticket manager configured: {mode}")

        return StepResult(
            success=True,
            data={
                "mode": mode,
                "enabled": context.tickets_enabled,
                "web_port": web_port if mode == "web" else None,
                "review_agents": review_agents,
            },
            message=f"Ticket manager configured in {mode} mode",
        )

    async def _configure_web_port(self) -> int:
        """Configure the web dashboard port."""
        self.console.print()
        port_str = self.prompt(
            "Web dashboard port",
            default=str(self.DEFAULT_WEB_PORT),
        )

        try:
            port = int(port_str)
            if port < 1024 or port > 65535:
                self.show_warning(
                    f"Port {port} may require elevated privileges or be invalid. "
                    f"Using default {self.DEFAULT_WEB_PORT}."
                )
                return self.DEFAULT_WEB_PORT
            return port
        except ValueError:
            self.show_warning(f"Invalid port. Using default {self.DEFAULT_WEB_PORT}.")
            return self.DEFAULT_WEB_PORT

    async def _configure_workflow_options(self) -> dict:
        """Configure ticket workflow options."""
        self.console.print("\n[bold]Workflow Options[/bold]")

        review_agents = self.confirm(
            "Enable automated code review agents?",
            default=True,
        )

        return {
            "review_agents": review_agents,
        }

    async def _configure_agent_coordination(self, context: WizardContext) -> None:
        """Configure agent coordination settings."""
        self.console.print("\n[bold]Agent Coordination[/bold]")

        # Ask about multi-agent support
        multi_agent = self.confirm(
            "Enable multi-agent coordination (for parallel agent work)?",
            default=True,
        )

        context.set("multi_agent_enabled", multi_agent)

        if multi_agent:
            self.show_info("Multi-agent mode enabled - agents can work on tickets concurrently")

    def _translate_mode(self, mode: str) -> str:
        """
        Translate wizard mode to config mode.

        Wizard uses: cli, web, disabled
        Config uses: cli, cli_web, embedded (and enabled flag)
        """
        mode_mapping = {
            "cli": "cli",
            "web": "cli_web",
            "disabled": "cli",  # Mode doesn't matter when disabled
        }
        return mode_mapping.get(mode, "cli")

    async def validate(self, context: WizardContext) -> bool:
        """
        Validate the ticket configuration.

        Ensures the configuration is valid before proceeding.
        """
        tickets_config = context.config.tickets

        # Validate port if web mode
        if tickets_config.mode == "cli_web":
            if tickets_config.web_port < 1 or tickets_config.web_port > 65535:
                self.show_error(f"Invalid port: {tickets_config.web_port}")
                return False

        return True

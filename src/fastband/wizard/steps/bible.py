"""
Agent Bible generation wizard step.

Generates a project-specific AGENT_BIBLE.md that defines the rules
and conventions all AI agents must follow when working on this project.
"""

from pathlib import Path

from rich.console import Console
from rich.panel import Panel

from fastband.wizard.base import StepResult, WizardContext, WizardStep
from fastband.wizard.bible_generator import (
    AgentBibleGenerator,
    DatabaseRule,
    ProjectConfig,
)


class AgentBibleStep(WizardStep):
    """
    Wizard step for generating the Agent Bible.

    This step:
    1. Collects project configuration from previous steps
    2. Prompts for additional Agent Bible settings
    3. Generates AGENT_BIBLE.md using the template
    4. Saves it to .fastband/AGENT_BIBLE.md
    """

    def __init__(self, console: Console | None = None):
        super().__init__(console)

    @property
    def name(self) -> str:
        return "bible"

    @property
    def title(self) -> str:
        return "Agent Bible Generation"

    @property
    def description(self) -> str:
        return "Generate project rules and conventions for AI agents"

    @property
    def required(self) -> bool:
        return True  # Agent Bible is essential for agent governance

    async def execute(self, context: WizardContext) -> StepResult:
        """
        Execute Agent Bible generation step.

        Args:
            context: Wizard context with project info

        Returns:
            StepResult indicating success/failure
        """
        self.show_header()

        # Get project info from context
        project_info = context.project_info

        if not project_info:
            self.show_warning("Project detection was skipped. Using default configuration.")

        # Build configuration from context
        config = self._build_config_from_context(context)

        # Interactive mode: prompt for additional settings
        if context.interactive:
            config = await self._interactive_config(config, context)

        # Generate the Agent Bible
        try:
            generator = AgentBibleGenerator()
            output_path = context.project_path / ".fastband" / "AGENT_BIBLE.md"

            # Ensure directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Generate and save
            generator.save(config, output_path)

            self.show_success(f"Generated Agent Bible: {output_path}")

            # Store path in context for MCP onboarding
            context.set("agent_bible_path", str(output_path))
            context.set("agent_bible_config", config)

            # Show summary
            self._show_summary(config, output_path)

            return StepResult(
                success=True,
                data={
                    "bible_path": str(output_path),
                    "project_name": config.name,
                    "ticket_prefix": config.ticket_prefix,
                },
                message="Agent Bible generated successfully",
            )

        except Exception as e:
            self.show_error(f"Failed to generate Agent Bible: {e}")
            return StepResult(
                success=False,
                message=str(e),
            )

    def _build_config_from_context(self, context: WizardContext) -> ProjectConfig:
        """Build ProjectConfig from wizard context."""
        project_info = context.project_info

        # Determine project type and language
        if project_info:
            project_type = (
                project_info.project_type.value if project_info.project_type else "unknown"
            )
            language = (
                project_info.primary_language.value if project_info.primary_language else "unknown"
            )
            name = project_info.name or context.project_path.name
        else:
            project_type = "unknown"
            language = "unknown"
            name = context.project_path.name

        # Build base config
        config = ProjectConfig(
            name=name,
            type=project_type,
            language=language,
            root_path=str(context.project_path),
            ticket_prefix=self._suggest_ticket_prefix(name),
            fastband_path=".fastband",
        )

        # Add settings from context
        if context.get("dev_url"):
            config.dev_url = context.get("dev_url")
        if context.get("container_name"):
            config.container_name = context.get("container_name")
        if context.get("database_type"):
            config.database_type = context.get("database_type")
            config.database_rule = self._get_database_rule(context.get("database_type"))

        return config

    async def _interactive_config(
        self, config: ProjectConfig, context: WizardContext
    ) -> ProjectConfig:
        """Interactively configure Agent Bible settings."""
        self.console.print()
        self.console.print("[bold]Configure Agent Bible settings:[/bold]")
        self.console.print()

        # Project name
        config.name = self.prompt(
            "Project name",
            default=config.name,
        )

        # Ticket prefix
        config.ticket_prefix = self.prompt(
            "Ticket prefix (e.g., FB, APP, API)",
            default=config.ticket_prefix,
        ).upper()

        # Development URL
        config.dev_url = self.prompt(
            "Development URL",
            default=config.dev_url or "http://localhost:5000",
        )

        # Container name (if applicable)
        if self.confirm("Does this project use Docker containers?", default=False):
            config.container_name = self.prompt(
                "Container name",
                default=config.container_name or f"{config.name.lower().replace(' ', '-')}-dev",
            )
            config.service_name = self.prompt(
                "Docker Compose service name",
                default=config.service_name or "webapp",
            )

        # Database configuration
        if self.confirm("Does this project use a database?", default=True):
            db_choices = [
                {
                    "value": "postgresql",
                    "label": "PostgreSQL",
                    "description": "Recommended for production",
                },
                {"value": "sqlite", "label": "SQLite", "description": "Simple, file-based"},
                {
                    "value": "mysql",
                    "label": "MySQL/MariaDB",
                    "description": "Popular relational DB",
                },
                {
                    "value": "none",
                    "label": "No database rules",
                    "description": "Skip database rules",
                },
            ]
            db_type = self.select("Select database type:", db_choices)[0]

            if db_type != "none":
                config.database_type = db_type.upper()
                config.database_rule = self._get_database_rule(db_type)

        # Review agent count
        review_choices = [
            {"value": "1", "label": "1 Agent", "description": "Minimal review (code only)"},
            {"value": "2", "label": "2 Agents", "description": "Code + Process review"},
            {
                "value": "3",
                "label": "3 Agents",
                "description": "Full review (Code + Process + UI/UX)",
            },
        ]
        config.review_agent_count = int(self.select("Number of review agents:", review_choices)[0])

        return config

    def _suggest_ticket_prefix(self, name: str) -> str:
        """Suggest a ticket prefix based on project name."""
        # Take first letters of words, or first 2-3 chars
        words = name.replace("-", " ").replace("_", " ").split()
        if len(words) >= 2:
            prefix = "".join(w[0].upper() for w in words[:3])
        else:
            prefix = name[:3].upper()
        return prefix

    def _get_database_rule(self, db_type: str) -> DatabaseRule | None:
        """Get database rule for type."""
        db_type = db_type.lower()
        if db_type == "postgresql":
            return DatabaseRule.postgresql()
        elif db_type == "sqlite":
            return DatabaseRule.sqlite()
        elif db_type == "mysql":
            return DatabaseRule.mysql()
        return None

    def _show_summary(self, config: ProjectConfig, output_path: Path) -> None:
        """Display configuration summary."""
        self.console.print()
        self.console.print(
            Panel.fit(
                f"[bold green]Agent Bible Generated[/bold green]\n\n"
                f"[cyan]Project:[/cyan] {config.name}\n"
                f"[cyan]Type:[/cyan] {config.type}\n"
                f"[cyan]Language:[/cyan] {config.language}\n"
                f"[cyan]Ticket Prefix:[/cyan] {config.ticket_prefix}\n"
                f"[cyan]Review Agents:[/cyan] {config.review_agent_count}\n"
                f"[cyan]Database:[/cyan] {config.database_type or 'None'}\n"
                f"\n[dim]Saved to: {output_path}[/dim]",
                border_style="green",
                title="Summary",
            )
        )
        self.console.print()
        self.console.print(
            "[bold yellow]⚠️  Important:[/bold yellow] All AI agents working on this project "
            "will be required to read and acknowledge the Agent Bible before making changes."
        )

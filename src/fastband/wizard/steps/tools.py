"""
Tool Selection Wizard Step.

Allows users to select tools for their project based on recommendations.
"""

from rich import box
from rich.console import Console
from rich.table import Table

from fastband.tools.base import ToolCategory
from fastband.tools.recommender import ToolRecommendation, ToolRecommender
from fastband.wizard.base import StepResult, WizardContext, WizardStep


class ToolSelectionStep(WizardStep):
    """
    Wizard step for selecting project tools.

    Features:
    - Recommends tools based on detected project type
    - Groups tools by category for easy browsing
    - Shows recommendations with relevance scores
    - Validates tool compatibility
    - Supports non-interactive mode (accepts recommended tools)
    """

    def __init__(self, console: Console | None = None, recommender: ToolRecommender | None = None):
        super().__init__(console)
        self._recommender = recommender

    @property
    def name(self) -> str:
        return "tools"

    @property
    def title(self) -> str:
        return "Tool Selection"

    @property
    def description(self) -> str:
        return "Select the tools you want to use for your project"

    @property
    def required(self) -> bool:
        return False

    @property
    def recommender(self) -> ToolRecommender:
        """Get the tool recommender (lazily initialized)."""
        if self._recommender is None:
            self._recommender = ToolRecommender()
        return self._recommender

    async def execute(self, context: WizardContext) -> StepResult:
        """Execute the tool selection step."""
        # Get recommendations based on project
        result = self.recommender.analyze(context.project_path)

        # Get recommended tool names
        {rec.tool_name for rec in result.recommendations}

        if not context.interactive:
            # Non-interactive mode: accept all recommended tools
            return self._accept_recommended_tools(context, result.recommendations)

        # Interactive mode: let user select tools
        return await self._interactive_selection(context, result)

    def _accept_recommended_tools(
        self, context: WizardContext, recommendations: list[ToolRecommendation]
    ) -> StepResult:
        """Accept all recommended tools (non-interactive mode)."""
        selected = [rec.tool_name for rec in recommendations]

        # Save to context
        context.selected_tools = selected
        context.config.tools = selected

        tool_count = len(selected)
        self.show_success(f"Accepted {tool_count} recommended tool(s)")

        return StepResult(
            success=True,
            data={"selected_tools": selected, "mode": "non-interactive"},
            message=f"Selected {tool_count} recommended tools",
        )

    async def _interactive_selection(self, context: WizardContext, result) -> StepResult:
        """Interactive tool selection."""

        recommendations = result.recommendations
        recommended_names = {rec.tool_name for rec in recommendations}

        # Group tools by category
        tools_by_category = self._group_by_category(recommendations)

        # Display tools grouped by category
        self._display_tool_categories(tools_by_category, recommended_names)

        # Let user select/deselect tools
        selected = await self._get_user_selections(recommendations, recommended_names)

        # Validate tool compatibility
        validation_result = self._validate_tool_compatibility(selected, result.already_loaded)
        if not validation_result["valid"]:
            self.show_warning(validation_result["message"])
            if not self.confirm("Continue anyway?", default=False):
                return StepResult(
                    success=False,
                    message="Tool selection cancelled due to compatibility issues",
                    go_back=True,
                )

        # Save to context
        context.selected_tools = selected
        context.config.tools = selected

        self.show_success(f"Selected {len(selected)} tool(s)")

        return StepResult(
            success=True,
            data={"selected_tools": selected, "mode": "interactive"},
            message=f"Selected {len(selected)} tools",
        )

    def _group_by_category(
        self, recommendations: list[ToolRecommendation]
    ) -> dict[ToolCategory, list[ToolRecommendation]]:
        """Group recommendations by category."""
        grouped: dict[ToolCategory, list[ToolRecommendation]] = {}
        for rec in recommendations:
            if rec.category not in grouped:
                grouped[rec.category] = []
            grouped[rec.category].append(rec)
        return grouped

    def _display_tool_categories(
        self,
        tools_by_category: dict[ToolCategory, list[ToolRecommendation]],
        recommended_names: set[str],
    ) -> None:
        """Display tools grouped by category using Rich tables."""
        if not tools_by_category:
            self.show_info("No tools available for recommendation")
            return

        for category, tools in sorted(tools_by_category.items(), key=lambda x: x[0].value):
            self._display_category_table(category, tools, recommended_names)

    def _display_category_table(
        self, category: ToolCategory, tools: list[ToolRecommendation], recommended_names: set[str]
    ) -> None:
        """Display a single category's tools in a table."""
        table = Table(
            title=f"[bold]{category.value.title()} Tools[/bold]",
            box=box.ROUNDED,
            show_header=True,
            header_style="bold cyan",
        )

        table.add_column("#", style="dim", width=4)
        table.add_column("Tool", style="cyan", min_width=20)
        table.add_column("Description", min_width=30)
        table.add_column("Recommended", justify="center", width=12)

        for i, rec in enumerate(tools, 1):
            is_recommended = rec.tool_name in recommended_names
            rec_marker = "[green]Yes[/green]" if is_recommended else "[dim]No[/dim]"

            table.add_row(
                str(i),
                rec.tool_name,
                rec.reason,
                rec_marker,
            )

        self.console.print(table)
        self.console.print()

    async def _get_user_selections(
        self, recommendations: list[ToolRecommendation], recommended_names: set[str]
    ) -> list[str]:
        """Get tool selections from user."""
        # Start with recommended tools selected
        selected = set(recommended_names)

        self.console.print("[bold]Tool Selection Options:[/bold]")
        self.console.print("  [dim]1.[/dim] Accept recommended tools")
        self.console.print("  [dim]2.[/dim] Select all tools")
        self.console.print("  [dim]3.[/dim] Deselect all tools")
        self.console.print("  [dim]4.[/dim] Customize selection")
        self.console.print()

        choice = self.prompt(
            "Choose an option",
            choices=["1", "2", "3", "4"],
            default="1",
        )

        if choice == "1":
            # Accept recommended
            return list(recommended_names)
        elif choice == "2":
            # Select all
            return [rec.tool_name for rec in recommendations]
        elif choice == "3":
            # Deselect all
            return []
        else:
            # Customize
            return self._customize_selection(recommendations, selected)

    def _customize_selection(
        self, recommendations: list[ToolRecommendation], current_selection: set[str]
    ) -> list[str]:
        """Allow user to customize tool selection."""
        self.console.print("\n[bold]Customize Tool Selection[/bold]")
        self.console.print("[dim]Enter tool numbers separated by commas to toggle selection[/dim]")
        self.console.print("[dim]Press Enter when done[/dim]\n")

        # Create a numbered list of all tools
        all_tools = [(i, rec) for i, rec in enumerate(recommendations, 1)]

        # Show current selection status
        table = Table(box=box.SIMPLE, show_header=True)
        table.add_column("#", style="dim", width=4)
        table.add_column("Tool", style="cyan")
        table.add_column("Selected", justify="center")

        for num, rec in all_tools:
            is_selected = rec.tool_name in current_selection
            status = "[green]X[/green]" if is_selected else "[dim]-[/dim]"
            table.add_row(str(num), rec.tool_name, status)

        self.console.print(table)

        # Get user input
        user_input = self.prompt("Toggle tools (e.g., 1,3,5) or press Enter to finish", default="")

        if user_input.strip():
            try:
                indices = [int(x.strip()) for x in user_input.split(",")]
                for idx in indices:
                    if 1 <= idx <= len(all_tools):
                        tool_name = all_tools[idx - 1][1].tool_name
                        if tool_name in current_selection:
                            current_selection.discard(tool_name)
                        else:
                            current_selection.add(tool_name)
            except ValueError:
                self.show_error("Invalid input. Keeping current selection.")

        return list(current_selection)

    def _validate_tool_compatibility(
        self, selected_tools: list[str], already_loaded: list[str]
    ) -> dict:
        """Validate that selected tools are compatible with each other."""
        # Get the registry to check tool metadata
        from fastband.tools.registry import get_registry

        registry = get_registry()

        conflicts = []
        missing_deps = []

        for tool_name in selected_tools:
            tool = registry.get_available(tool_name)
            if tool is None:
                continue

            metadata = tool.definition.metadata

            # Check for conflicts
            for conflict in metadata.conflicts_with:
                if conflict in selected_tools:
                    conflicts.append((tool_name, conflict))

            # Check for required dependencies
            for required in metadata.requires_tools:
                if required not in selected_tools and required not in already_loaded:
                    missing_deps.append((tool_name, required))

        if conflicts or missing_deps:
            messages = []
            if conflicts:
                conflict_msgs = [f"{a} conflicts with {b}" for a, b in conflicts]
                messages.append("Conflicts: " + ", ".join(conflict_msgs))
            if missing_deps:
                dep_msgs = [f"{a} requires {b}" for a, b in missing_deps]
                messages.append("Missing dependencies: " + ", ".join(dep_msgs))

            return {
                "valid": False,
                "message": "; ".join(messages),
                "conflicts": conflicts,
                "missing_deps": missing_deps,
            }

        return {"valid": True, "message": "All tools compatible"}

    async def validate(self, context: WizardContext) -> bool:
        """Validate the tool selection."""
        # Ensure selected_tools is set
        if context.selected_tools is None:
            context.selected_tools = []

        return True

"""
Fastband CLI - Tools subcommand.

Provides commands for managing the Tool Garage:
- list: List available and active tools
- load: Load a tool into active tools
- unload: Unload a tool from active tools
- info: Show detailed tool information
- stats: Show tool usage statistics
"""

import typer
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from fastband.tools.base import ToolCategory
from fastband.tools.registry import get_registry

# Create the tools subcommand app
tools_app = typer.Typer(
    name="tools",
    help="Tool Garage management commands",
    no_args_is_help=True,
)

# Rich console for output
console = Console()


# =============================================================================
# LIST COMMAND
# =============================================================================


@tools_app.command("list")
def list_tools(
    category: str | None = typer.Option(
        None,
        "--category",
        "-c",
        help="Filter by category (e.g., core, file_ops, git, testing)",
    ),
    active_only: bool = typer.Option(
        False,
        "--active",
        "-a",
        help="Show only active (loaded) tools",
    ),
    available_only: bool = typer.Option(
        False,
        "--available",
        help="Show only available (unloaded) tools",
    ),
):
    """
    List available tools in the Tool Garage.

    Shows all registered tools with their name, category, and status
    (loaded or available). Use filters to narrow down the list.
    """
    registry = get_registry()

    # Get all tools
    if active_only:
        tools = registry.get_active_tools()
        title = "Active Tools"
    elif available_only:
        active_names = {t.name for t in registry.get_active_tools()}
        tools = [t for t in registry.get_available_tools() if t.name not in active_names]
        title = "Available Tools (Not Loaded)"
    else:
        tools = registry.get_available_tools()
        title = "All Tools"

    # Filter by category if specified
    if category:
        try:
            cat_enum = ToolCategory(category.lower())
            tools = [t for t in tools if t.category == cat_enum]
            title = f"{title} - {category.capitalize()}"
        except ValueError:
            valid_categories = [c.value for c in ToolCategory]
            console.print(f"[red]Invalid category: {category}[/red]")
            console.print(f"Valid categories: {', '.join(valid_categories)}")
            raise typer.Exit(1)

    if not tools:
        console.print("[yellow]No tools found matching criteria.[/yellow]")
        raise typer.Exit(0)

    # Create table
    table = Table(
        title=title,
        box=box.ROUNDED,
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("Name", style="bold")
    table.add_column("Category")
    table.add_column("Status")
    table.add_column("Description", max_width=50)

    # Sort by category, then name
    sorted_tools = sorted(tools, key=lambda t: (t.category.value, t.name))

    for tool in sorted_tools:
        is_loaded = registry.is_loaded(tool.name)
        status = "[green]Loaded[/green]" if is_loaded else "[dim]Available[/dim]"

        table.add_row(
            tool.name,
            tool.category.value,
            status,
            tool.definition.metadata.description[:50] + "..."
            if len(tool.definition.metadata.description) > 50
            else tool.definition.metadata.description,
        )

    console.print(table)

    # Show summary
    active_count = len(registry.get_active_tools())
    available_count = len(registry.get_available_tools())
    console.print(f"\n[dim]Active: {active_count} | Available: {available_count}[/dim]")


# =============================================================================
# LOAD COMMAND
# =============================================================================


@tools_app.command("load")
def load_tool(
    name: str = typer.Argument(
        ...,
        help="Name of the tool to load",
    ),
):
    """
    Load a tool into the active tool set.

    Loads a registered tool from the garage into the active set,
    making it available for execution. Core tools are loaded by default.
    """
    registry = get_registry()

    # Check if tool exists
    if not registry.is_registered(name):
        console.print(f"[red]Tool not found: {name}[/red]")

        # Suggest similar tools
        available = registry.get_available_tools()
        similar = [t.name for t in available if name.lower() in t.name.lower()]
        if similar:
            console.print(f"[dim]Did you mean: {', '.join(similar[:3])}?[/dim]")

        raise typer.Exit(1)

    # Check if already loaded
    if registry.is_loaded(name):
        console.print(f"[yellow]Tool already loaded: {name}[/yellow]")
        raise typer.Exit(0)

    # Load the tool
    status = registry.load(name)

    if status.loaded:
        console.print(f"[green]Loaded tool: {name}[/green]")
        console.print(
            f"[dim]Category: {status.category.value} | Load time: {status.load_time_ms:.2f}ms[/dim]"
        )
    else:
        console.print(f"[red]Failed to load tool: {name}[/red]")
        if status.error:
            console.print(f"[red]Error: {status.error}[/red]")
        raise typer.Exit(1)


# =============================================================================
# UNLOAD COMMAND
# =============================================================================


@tools_app.command("unload")
def unload_tool(
    name: str = typer.Argument(
        ...,
        help="Name of the tool to unload",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Force unload (warning: may affect running operations)",
    ),
):
    """
    Unload a tool from the active tool set.

    Removes a tool from the active set, freeing resources.
    Core tools cannot be unloaded unless --force is used.
    """
    registry = get_registry()

    # Check if tool exists
    if not registry.is_registered(name):
        console.print(f"[red]Tool not found: {name}[/red]")
        raise typer.Exit(1)

    # Check if loaded
    if not registry.is_loaded(name):
        console.print(f"[yellow]Tool not loaded: {name}[/yellow]")
        raise typer.Exit(0)

    # Check if core tool
    tool = registry.get(name)
    if tool and tool.category == ToolCategory.CORE and not force:
        console.print(f"[red]Cannot unload core tool: {name}[/red]")
        console.print("[dim]Use --force to override (not recommended)[/dim]")
        raise typer.Exit(1)

    # Unload the tool
    if force and tool and tool.category == ToolCategory.CORE:
        # Force unload core tool by directly removing from active
        del registry._active[name]
        console.print(f"[yellow]Force unloaded core tool: {name}[/yellow]")
        console.print("[yellow]Warning: This may affect system stability[/yellow]")
    else:
        success = registry.unload(name)
        if success:
            console.print(f"[green]Unloaded tool: {name}[/green]")
        else:
            console.print(f"[red]Failed to unload tool: {name}[/red]")
            raise typer.Exit(1)


# =============================================================================
# INFO COMMAND
# =============================================================================


@tools_app.command("info")
def tool_info(
    name: str = typer.Argument(
        ...,
        help="Name of the tool to get information about",
    ),
):
    """
    Show detailed information about a tool.

    Displays the tool's metadata, parameters, and execution statistics.
    """
    registry = get_registry()

    # Get the tool (from available, not just active)
    tool = registry.get_available(name)
    if not tool:
        console.print(f"[red]Tool not found: {name}[/red]")
        raise typer.Exit(1)

    definition = tool.definition
    metadata = definition.metadata

    # Tool overview panel
    is_loaded = registry.is_loaded(name)
    status_text = "[green]Loaded[/green]" if is_loaded else "[dim]Not Loaded[/dim]"

    console.print(
        Panel.fit(
            f"[bold blue]{metadata.name}[/bold blue]\n"
            f"[dim]{metadata.description}[/dim]\n\n"
            f"Status: {status_text}",
            title="Tool Information",
            border_style="blue",
        )
    )

    # Metadata table
    meta_table = Table(
        title="Metadata",
        box=box.ROUNDED,
        show_header=False,
    )
    meta_table.add_column("Property", style="cyan")
    meta_table.add_column("Value")

    meta_table.add_row("Category", metadata.category.value)
    meta_table.add_row("Version", metadata.version)
    meta_table.add_row("Author", metadata.author)
    meta_table.add_row(
        "Curated", "[green]Yes[/green]" if metadata.curated else "[yellow]No[/yellow]"
    )

    if metadata.project_types:
        types = ", ".join(pt.value for pt in metadata.project_types)
        meta_table.add_row("Project Types", types)

    if metadata.tech_stack_hints:
        hints = ", ".join(metadata.tech_stack_hints)
        meta_table.add_row("Tech Stack Hints", hints)

    if metadata.memory_intensive:
        meta_table.add_row("Memory Intensive", "[yellow]Yes[/yellow]")
    if metadata.network_required:
        meta_table.add_row("Network Required", "[yellow]Yes[/yellow]")
    if metadata.requires_filesystem:
        meta_table.add_row("Filesystem Access", "[yellow]Yes[/yellow]")

    if metadata.requires_tools:
        meta_table.add_row("Requires", ", ".join(metadata.requires_tools))
    if metadata.conflicts_with:
        meta_table.add_row("Conflicts With", ", ".join(metadata.conflicts_with))

    console.print(meta_table)

    # Parameters table
    if definition.parameters:
        param_table = Table(
            title="Parameters",
            box=box.ROUNDED,
            show_header=True,
            header_style="bold cyan",
        )
        param_table.add_column("Name", style="bold")
        param_table.add_column("Type")
        param_table.add_column("Required")
        param_table.add_column("Default")
        param_table.add_column("Description", max_width=40)

        for param in definition.parameters:
            required = "[green]Yes[/green]" if param.required else "[dim]No[/dim]"
            default = str(param.default) if param.default is not None else "[dim]-[/dim]"

            param_table.add_row(
                param.name,
                param.type,
                required,
                default,
                param.description[:40] + "..."
                if len(param.description) > 40
                else param.description,
            )

        console.print(param_table)
    else:
        console.print("\n[dim]No parameters required[/dim]")

    # Execution stats (if available)
    stats = registry.get_tool_stats(name)
    if stats:
        stats_table = Table(
            title="Execution Statistics",
            box=box.ROUNDED,
            show_header=False,
        )
        stats_table.add_column("Metric", style="cyan")
        stats_table.add_column("Value")

        stats_table.add_row("Total Executions", str(stats["total_executions"]))
        stats_table.add_row("Average Time", f"{stats['average_time_ms']:.2f}ms")
        stats_table.add_row("Min Time", f"{stats['min_time_ms']:.2f}ms")
        stats_table.add_row("Max Time", f"{stats['max_time_ms']:.2f}ms")

        console.print(stats_table)


# =============================================================================
# STATS COMMAND
# =============================================================================


@tools_app.command("stats")
def tool_stats(
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show detailed statistics for each tool",
    ),
):
    """
    Show tool usage statistics and performance report.

    Displays overall tool garage metrics including active tools,
    performance status, and execution statistics.
    """
    registry = get_registry()
    report = registry.get_performance_report()

    # Performance overview panel
    status_colors = {
        "optimal": "green",
        "moderate": "yellow",
        "heavy": "yellow",
        "overloaded": "red",
    }
    status_color = status_colors.get(report.status, "white")

    console.print(
        Panel.fit(
            f"[bold blue]Tool Garage Statistics[/bold blue]\n\n"
            f"Status: [{status_color}]{report.status.upper()}[/{status_color}]",
            border_style="blue",
        )
    )

    # Main stats table
    stats_table = Table(
        title="Overview",
        box=box.ROUNDED,
        show_header=False,
    )
    stats_table.add_column("Metric", style="cyan")
    stats_table.add_column("Value")

    stats_table.add_row("Active Tools", str(report.active_tools))
    stats_table.add_row("Available Tools", str(report.available_tools))
    stats_table.add_row("Max Recommended", str(report.max_recommended))
    stats_table.add_row("Total Executions", str(report.total_executions))

    if report.average_execution_time_ms > 0:
        stats_table.add_row("Avg Execution Time", f"{report.average_execution_time_ms:.2f}ms")

    console.print(stats_table)

    # Category breakdown
    if report.categories:
        cat_table = Table(
            title="Tools by Category",
            box=box.ROUNDED,
            show_header=True,
            header_style="bold cyan",
        )
        cat_table.add_column("Category")
        cat_table.add_column("Active", justify="right")

        for category, count in sorted(report.categories.items()):
            cat_table.add_row(category, str(count))

        console.print(cat_table)

    # Performance recommendation
    if report.recommendation:
        console.print(
            Panel(
                f"[yellow]{report.recommendation}[/yellow]",
                title="Recommendation",
                border_style="yellow",
            )
        )

    # Verbose: per-tool stats
    if verbose:
        active_tools = registry.get_active_tools()
        tools_with_stats = []

        for tool in active_tools:
            stats = registry.get_tool_stats(tool.name)
            if stats:
                tools_with_stats.append(stats)

        if tools_with_stats:
            detail_table = Table(
                title="Per-Tool Execution Statistics",
                box=box.ROUNDED,
                show_header=True,
                header_style="bold cyan",
            )
            detail_table.add_column("Tool")
            detail_table.add_column("Executions", justify="right")
            detail_table.add_column("Avg (ms)", justify="right")
            detail_table.add_column("Min (ms)", justify="right")
            detail_table.add_column("Max (ms)", justify="right")

            # Sort by total executions descending
            sorted_stats = sorted(
                tools_with_stats, key=lambda s: s["total_executions"], reverse=True
            )

            for stats in sorted_stats:
                detail_table.add_row(
                    stats["name"],
                    str(stats["total_executions"]),
                    f"{stats['average_time_ms']:.2f}",
                    f"{stats['min_time_ms']:.2f}",
                    f"{stats['max_time_ms']:.2f}",
                )

            console.print(detail_table)
        else:
            console.print("\n[dim]No execution statistics available yet.[/dim]")

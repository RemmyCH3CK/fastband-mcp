"""
Fastband CLI - Main entry point.

Provides commands for initializing, configuring, and managing
Fastband MCP servers.
"""

import asyncio
from pathlib import Path

import typer
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from fastband import __version__
from fastband.cli.backup import backup_app
from fastband.cli.plugins import plugins_app
from fastband.cli.tickets import tickets_app
from fastband.cli.tools import tools_app
from fastband.core.config import FastbandConfig, get_config
from fastband.core.detection import Language, ProjectInfo, detect_project

# Create the main CLI app
app = typer.Typer(
    name="fastband",
    help="Fastband MCP Server - AI-powered development tools",
    no_args_is_help=True,
    rich_markup_mode="rich",
)

# Config subcommand group
config_app = typer.Typer(
    name="config",
    help="Configuration management commands",
    no_args_is_help=True,
)
app.add_typer(config_app, name="config")

# Tools subcommand group
app.add_typer(tools_app, name="tools")

# Tickets subcommand group
app.add_typer(tickets_app, name="tickets")

# Backup subcommand group
app.add_typer(backup_app, name="backup")

# Plugins subcommand group
app.add_typer(plugins_app, name="plugins")

# Rich console for output
console = Console()


def version_callback(value: bool):
    """Show version and exit."""
    if value:
        console.print(f"[bold blue]fastband[/bold blue] version [green]{__version__}[/green]")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        None,
        "--version",
        "-v",
        help="Show version and exit.",
        callback=version_callback,
        is_eager=True,
    ),
):
    """
    Fastband MCP Server CLI.

    A powerful AI-powered development tool server that provides
    context-aware tools for your projects.
    """
    pass


# =============================================================================
# INIT COMMAND
# =============================================================================


@app.command()
def init(
    path: Path | None = typer.Argument(
        None,
        help="Project path to initialize (default: current directory)",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Overwrite existing configuration",
    ),
    skip_detection: bool = typer.Option(
        False,
        "--skip-detection",
        help="Skip project detection",
    ),
):
    """
    Initialize Fastband in a project directory.

    Creates a .fastband/ configuration directory and detects
    project type to recommend appropriate tools.
    """
    project_path = (path or Path.cwd()).resolve()

    # Check if already initialized
    fastband_dir = project_path / ".fastband"
    config_file = fastband_dir / "config.yaml"

    if config_file.exists() and not force:
        console.print(f"[yellow]Fastband already initialized in {project_path}[/yellow]")
        console.print("Use [bold]--force[/bold] to reinitialize")
        raise typer.Exit(1)

    console.print(
        Panel.fit(
            "[bold blue]Initializing Fastband[/bold blue]",
            border_style="blue",
        )
    )

    # Detect project
    project_info: ProjectInfo | None = None
    if not skip_detection:
        with console.status("[bold green]Detecting project type..."):
            try:
                project_info = detect_project(project_path)
            except Exception as e:
                console.print(f"[yellow]Could not detect project: {e}[/yellow]")

    if project_info:
        _display_project_info(project_info)

    # Create configuration
    console.print("\n[bold]Creating configuration...[/bold]")

    config = FastbandConfig()

    # Add detected provider hints
    if project_info:
        # Set default providers based on project type
        if project_info.primary_language == Language.PYTHON:
            from fastband.core.config import AIProviderConfig

            config.providers["claude"] = AIProviderConfig(model="claude-sonnet-4-20250514")

    # Save configuration
    fastband_dir.mkdir(parents=True, exist_ok=True)
    config.save(config_file)

    console.print(f"[green]✓[/green] Created {config_file}")
    console.print(f"[green]✓[/green] Fastband initialized in [bold]{project_path}[/bold]")

    # Show next steps
    console.print("\n[bold]Next steps:[/bold]")
    console.print(
        "  1. Configure AI providers: [dim]fastband config set ai.default_provider claude[/dim]"
    )
    console.print("  2. Set API key: [dim]export ANTHROPIC_API_KEY=your-key[/dim]")
    console.print("  3. Start server: [dim]fastband serve[/dim]")


def _display_project_info(info: ProjectInfo) -> None:
    """Display detected project information."""
    table = Table(
        title="Detected Project",
        box=box.ROUNDED,
        show_header=False,
        title_style="bold",
    )
    table.add_column("Property", style="cyan")
    table.add_column("Value")

    table.add_row("Language", info.primary_language.value)
    table.add_row("Type", info.primary_type.value)
    table.add_row("Confidence", f"{info.language_confidence:.0%}")

    if info.name:
        table.add_row("Name", info.name)
    if info.version:
        table.add_row("Version", info.version)

    if info.frameworks:
        fw_list = ", ".join(f.framework.value for f in info.frameworks)
        table.add_row("Frameworks", fw_list)

    if info.package_managers:
        pm_list = ", ".join(pm.value for pm in info.package_managers)
        table.add_row("Package Managers", pm_list)

    console.print(table)


# =============================================================================
# STATUS COMMAND
# =============================================================================


@app.command()
def status(
    path: Path | None = typer.Option(
        None,
        "--path",
        "-p",
        help="Project path (default: current directory)",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show detailed status",
    ),
):
    """
    Show Fastband status for the current project.

    Displays configuration, loaded tools, and server status.
    """
    project_path = (path or Path.cwd()).resolve()

    # Check if initialized
    fastband_dir = project_path / ".fastband"
    fastband_dir / "config.yaml"

    if not fastband_dir.exists():
        console.print(f"[red]Fastband not initialized in {project_path}[/red]")
        console.print("Run [bold]fastband init[/bold] first")
        raise typer.Exit(1)

    # Load configuration
    config = get_config(project_path)

    # Display status
    console.print(
        Panel.fit(
            f"[bold blue]Fastband Status[/bold blue]\n[dim]{project_path}[/dim]",
            border_style="blue",
        )
    )

    # Configuration overview
    table = Table(
        title="Configuration",
        box=box.ROUNDED,
        show_header=True,
    )
    table.add_column("Setting", style="cyan")
    table.add_column("Value")

    table.add_row("Version", config.version)
    table.add_row("Default Provider", config.default_provider)
    table.add_row("Storage Backend", config.storage_backend)
    table.add_row("Tools Max Active", str(config.tools.max_active))
    table.add_row("Tickets Enabled", "✓" if config.tickets.enabled else "✗")
    table.add_row("GitHub Enabled", "✓" if config.github.enabled else "✗")

    console.print(table)

    if verbose:
        # Show providers
        if config.providers:
            provider_table = Table(
                title="Configured Providers",
                box=box.ROUNDED,
            )
            provider_table.add_column("Provider", style="cyan")
            provider_table.add_column("Model")
            provider_table.add_column("Max Tokens")

            for name, prov in config.providers.items():
                provider_table.add_row(
                    name,
                    prov.model,
                    str(prov.max_tokens),
                )

            console.print(provider_table)

        # Show backup config
        backup_table = Table(
            title="Backup Configuration",
            box=box.ROUNDED,
            show_header=False,
        )
        backup_table.add_column("Setting", style="cyan")
        backup_table.add_column("Value")

        backup_table.add_row("Enabled", "✓" if config.backup.enabled else "✗")
        backup_table.add_row(
            "Daily Backup", config.backup.daily_time if config.backup.daily_enabled else "Disabled"
        )
        backup_table.add_row(
            "Weekly Backup",
            config.backup.weekly_day if config.backup.weekly_enabled else "Disabled",
        )
        backup_table.add_row("Change Detection", "✓" if config.backup.change_detection else "✗")

        console.print(backup_table)


# =============================================================================
# CONFIG COMMANDS
# =============================================================================


@config_app.command("show")
def config_show(
    path: Path | None = typer.Option(
        None,
        "--path",
        "-p",
        help="Project path (default: current directory)",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output as JSON",
    ),
):
    """Show current configuration."""
    import json as json_lib

    import yaml

    project_path = (path or Path.cwd()).resolve()
    config = get_config(project_path)

    if json_output:
        console.print(json_lib.dumps(config.to_dict(), indent=2))
    else:
        console.print(yaml.dump(config.to_dict(), default_flow_style=False))


@config_app.command("set")
def config_set(
    key: str = typer.Argument(
        ...,
        help="Configuration key (e.g., ai.default_provider)",
    ),
    value: str = typer.Argument(
        ...,
        help="Value to set",
    ),
    path: Path | None = typer.Option(
        None,
        "--path",
        "-p",
        help="Project path (default: current directory)",
    ),
):
    """Set a configuration value."""
    project_path = (path or Path.cwd()).resolve()
    config_file = project_path / ".fastband" / "config.yaml"

    if not config_file.exists():
        console.print("[red]No configuration found. Run fastband init first.[/red]")
        raise typer.Exit(1)

    # Load current config
    config = FastbandConfig.from_file(config_file)
    config_dict = config.to_dict()["fastband"]

    # Parse key path
    keys = key.split(".")
    current = config_dict

    # Navigate to parent
    for k in keys[:-1]:
        if k not in current:
            current[k] = {}
        current = current[k]

    # Set value (try to convert to appropriate type)
    final_key = keys[-1]
    try:
        # Try int
        current[final_key] = int(value)
    except ValueError:
        try:
            # Try float
            current[final_key] = float(value)
        except ValueError:
            # Try bool
            if value.lower() in ("true", "yes", "1"):
                current[final_key] = True
            elif value.lower() in ("false", "no", "0"):
                current[final_key] = False
            else:
                current[final_key] = value

    # Save
    new_config = FastbandConfig.from_dict(config_dict)
    new_config.save(config_file)

    console.print(f"[green]✓[/green] Set [bold]{key}[/bold] = [cyan]{value}[/cyan]")


@config_app.command("get")
def config_get(
    key: str = typer.Argument(
        ...,
        help="Configuration key (e.g., ai.default_provider)",
    ),
    path: Path | None = typer.Option(
        None,
        "--path",
        "-p",
        help="Project path (default: current directory)",
    ),
):
    """Get a configuration value."""
    project_path = (path or Path.cwd()).resolve()
    config = get_config(project_path)
    config_dict = config.to_dict()["fastband"]

    # Navigate key path
    keys = key.split(".")
    current = config_dict

    try:
        for k in keys:
            current = current[k]
        console.print(current)
    except (KeyError, TypeError):
        console.print(f"[red]Key not found: {key}[/red]")
        raise typer.Exit(1)


@config_app.command("reset")
def config_reset(
    path: Path | None = typer.Option(
        None,
        "--path",
        "-p",
        help="Project path (default: current directory)",
    ),
    confirm: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Skip confirmation",
    ),
):
    """Reset configuration to defaults."""
    project_path = (path or Path.cwd()).resolve()
    config_file = project_path / ".fastband" / "config.yaml"

    if not config_file.exists():
        console.print("[red]No configuration found.[/red]")
        raise typer.Exit(1)

    if not confirm:
        confirm = typer.confirm("Reset configuration to defaults?")

    if confirm:
        config = FastbandConfig()
        config.save(config_file)
        console.print("[green]✓[/green] Configuration reset to defaults")
    else:
        console.print("Cancelled")


# =============================================================================
# SERVE COMMAND
# =============================================================================


@app.command()
def serve(
    path: Path | None = typer.Option(
        None,
        "--path",
        "-p",
        help="Project path (default: current directory)",
    ),
    no_core: bool = typer.Option(
        False,
        "--no-core",
        help="Don't load core tools",
    ),
    all_tools: bool = typer.Option(
        False,
        "--all",
        "-a",
        help="Load all tools (core, git, tickets, context) - recommended for full functionality",
    ),
    hub: bool = typer.Option(
        False,
        "--hub",
        help="Also start the Hub server with dashboard (port 8080)",
    ),
    hub_only: bool = typer.Option(
        False,
        "--hub-only",
        help="Only start the Hub server (no MCP server)",
    ),
    hub_port: int = typer.Option(
        8080,
        "--hub-port",
        help="Port for Hub server (default: 8080)",
    ),
    no_dashboard: bool = typer.Option(
        False,
        "--no-dashboard",
        help="Run Hub without the React dashboard",
    ),
):
    """
    Start the Fastband MCP server.

    Launches the MCP server for the current project,
    loading configured tools and providers.

    By default, only core tools are loaded. Use --all to load all available tools
    including git, tickets, and context/semantic search tools.

    Use --hub to also start the Hub server with the React dashboard.
    Use --hub-only to only start the Hub server without the MCP server.
    """
    project_path = (path or Path.cwd()).resolve()

    if hub_only:
        # Only run Hub server
        from fastband.hub.server import run_server as run_hub_server

        console.print(
            Panel.fit(
                f"[bold blue]Starting Fastband Hub[/bold blue]\n"
                f"[dim]Dashboard: http://localhost:{hub_port}/[/dim]",
                border_style="blue",
            )
        )

        asyncio.run(
            run_hub_server(
                host="0.0.0.0",
                port=hub_port,
                with_dashboard=not no_dashboard,
            )
        )
    elif hub:
        # Run both MCP and Hub servers
        from fastband.core.engine import run_server
        from fastband.hub.server import run_server as run_hub_server

        tool_mode = "all" if all_tools else ("minimal" if no_core else "core")
        console.print(
            Panel.fit(
                f"[bold blue]Starting Fastband[/bold blue]\n"
                f"[dim]{project_path}[/dim]\n"
                f"[dim]Tool mode: {tool_mode}[/dim]\n"
                f"[dim]Dashboard: http://localhost:{hub_port}/[/dim]",
                border_style="blue",
            )
        )

        async def run_both():
            """Run MCP and Hub servers concurrently."""
            mcp_task = asyncio.create_task(
                run_server(
                    project_path=project_path,
                    load_core=not no_core,
                    load_all=all_tools,
                )
            )
            hub_task = asyncio.create_task(
                run_hub_server(
                    host="0.0.0.0",
                    port=hub_port,
                    with_dashboard=not no_dashboard,
                )
            )
            await asyncio.gather(mcp_task, hub_task)

        asyncio.run(run_both())
    else:
        # Just run MCP server
        from fastband.core.engine import run_server

        tool_mode = "all" if all_tools else ("minimal" if no_core else "core")
        console.print(
            Panel.fit(
                f"[bold blue]Starting Fastband MCP Server[/bold blue]\n"
                f"[dim]{project_path}[/dim]\n"
                f"[dim]Tool mode: {tool_mode}[/dim]",
                border_style="blue",
            )
        )

        asyncio.run(
            run_server(
                project_path=project_path,
                load_core=not no_core,
                load_all=all_tools,
            )
        )


# =============================================================================
# BUILD-DASHBOARD COMMAND
# =============================================================================


@app.command("build-dashboard")
def build_dashboard(
    clean: bool = typer.Option(
        False,
        "--clean",
        "-c",
        help="Clean build artifacts before building",
    ),
    clean_all: bool = typer.Option(
        False,
        "--clean-all",
        help="Remove node_modules as well (full clean)",
    ),
):
    """
    Build the React dashboard for packaging.

    Runs npm install and npm run build, then copies the output
    to the static directory for inclusion in the Python package.

    Requires Node.js 18+ to be installed.
    """
    import sys

    from fastband.hub.web.build import build
    from fastband.hub.web.build import clean as do_clean

    if clean or clean_all:
        if clean_all:
            sys.argv = ["build", "clean", "--all"]
        else:
            sys.argv = ["build", "clean"]
        do_clean()

        if clean_all or clean:
            console.print()  # Add spacing

    if not (clean and not clean_all):
        # Build unless just cleaning
        success = build()
        if not success:
            raise typer.Exit(1)


# =============================================================================
# ENTRY POINT
# =============================================================================


def cli():
    """CLI entry point."""
    app()


if __name__ == "__main__":
    cli()

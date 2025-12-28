"""
Fastband CLI - Main entry point.

Provides commands for initializing, configuring, and managing
Fastband MCP servers.
"""

import typer
from pathlib import Path
from typing import Optional
import asyncio

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.tree import Tree
from rich import box

from fastband import __version__
from fastband.core.config import FastbandConfig, get_config
from fastband.core.detection import detect_project, ProjectInfo, Language, ProjectType
from fastband.cli.tools import tools_app
from fastband.cli.tickets import tickets_app

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
    path: Optional[Path] = typer.Argument(
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
        console.print(
            f"[yellow]Fastband already initialized in {project_path}[/yellow]"
        )
        console.print("Use [bold]--force[/bold] to reinitialize")
        raise typer.Exit(1)

    console.print(Panel.fit(
        "[bold blue]Initializing Fastband[/bold blue]",
        border_style="blue",
    ))

    # Detect project
    project_info: Optional[ProjectInfo] = None
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
            config.providers["claude"] = FastbandConfig().providers.get(
                "claude",
                type("obj", (object,), {"model": "claude-sonnet-4-20250514"})()
            )

    # Save configuration
    fastband_dir.mkdir(parents=True, exist_ok=True)
    config.save(config_file)

    console.print(f"[green]✓[/green] Created {config_file}")
    console.print(f"[green]✓[/green] Fastband initialized in [bold]{project_path}[/bold]")

    # Show next steps
    console.print("\n[bold]Next steps:[/bold]")
    console.print("  1. Configure AI providers: [dim]fastband config set ai.default_provider claude[/dim]")
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
    path: Optional[Path] = typer.Option(
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
    config_file = fastband_dir / "config.yaml"

    if not fastband_dir.exists():
        console.print(f"[red]Fastband not initialized in {project_path}[/red]")
        console.print("Run [bold]fastband init[/bold] first")
        raise typer.Exit(1)

    # Load configuration
    config = get_config(project_path)

    # Display status
    console.print(Panel.fit(
        f"[bold blue]Fastband Status[/bold blue]\n[dim]{project_path}[/dim]",
        border_style="blue",
    ))

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
        backup_table.add_row("Daily Backup", config.backup.daily_time if config.backup.daily_enabled else "Disabled")
        backup_table.add_row("Weekly Backup", config.backup.weekly_day if config.backup.weekly_enabled else "Disabled")
        backup_table.add_row("Change Detection", "✓" if config.backup.change_detection else "✗")

        console.print(backup_table)


# =============================================================================
# CONFIG COMMANDS
# =============================================================================


@config_app.command("show")
def config_show(
    path: Optional[Path] = typer.Option(
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
    path: Optional[Path] = typer.Option(
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
    path: Optional[Path] = typer.Option(
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
    path: Optional[Path] = typer.Option(
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
    path: Optional[Path] = typer.Option(
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
):
    """
    Start the Fastband MCP server.

    Launches the MCP server for the current project,
    loading configured tools and providers.
    """
    from fastband.core.engine import run_server

    project_path = (path or Path.cwd()).resolve()

    console.print(Panel.fit(
        f"[bold blue]Starting Fastband MCP Server[/bold blue]\n[dim]{project_path}[/dim]",
        border_style="blue",
    ))

    # Run the server
    asyncio.run(run_server(
        project_path=project_path,
        load_core=not no_core,
    ))


# =============================================================================
# ENTRY POINT
# =============================================================================


def cli():
    """CLI entry point."""
    app()


if __name__ == "__main__":
    cli()

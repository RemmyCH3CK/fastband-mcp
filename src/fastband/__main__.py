"""
Fastband MCP CLI entry point.

Usage:
    fastband [OPTIONS] COMMAND [ARGS]...
    fb [OPTIONS] COMMAND [ARGS]...  # Short alias
"""

import click
from rich.console import Console

from fastband import __version__

console = Console()


@click.group()
@click.version_option(version=__version__, prog_name="fastband")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
@click.pass_context
def cli(ctx, verbose):
    """Fastband MCP - Universal AI-powered development platform."""
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose


@cli.command()
@click.option("--project-path", "-p", default=".", help="Project directory")
def init(project_path):
    """Initialize Fastband in a project directory."""
    console.print(f"[bold green]Initializing Fastband MCP in {project_path}...[/bold green]")
    console.print("\n[yellow]Setup wizard coming soon in next release![/yellow]")
    console.print("\nFor now, create a .fastband directory manually:")
    console.print("  mkdir -p .fastband")
    console.print("  touch .fastband/config.yaml")


@cli.command()
def status():
    """Show Fastband status for current project."""
    console.print("[bold]Fastband MCP Status[/bold]\n")
    console.print(f"Version: {__version__}")
    console.print("Status: [yellow]Alpha - Core features in development[/yellow]")


@cli.group()
def tools():
    """Manage Fastband tools."""
    pass


@tools.command("list")
def tools_list():
    """List available tools."""
    console.print("[bold]Available Tools[/bold]\n")
    console.print("[yellow]Tool registry coming soon![/yellow]")


@cli.group()
def tickets():
    """Manage project tickets."""
    pass


@tickets.command("list")
def tickets_list():
    """List project tickets."""
    console.print("[bold]Project Tickets[/bold]\n")
    console.print("[yellow]Ticket manager coming soon![/yellow]")


@cli.group()
def backup():
    """Manage backups."""
    pass


@backup.command("list")
def backup_list():
    """List available backups."""
    console.print("[bold]Available Backups[/bold]\n")
    console.print("[yellow]Backup manager coming soon![/yellow]")


@cli.group()
def agents():
    """Multi-agent coordination."""
    pass


@agents.command("status")
def agents_status():
    """Show active agents and coordination status."""
    console.print("[bold]Agent Coordination Status[/bold]\n")
    console.print("[yellow]Agent ops log coming soon![/yellow]")


@cli.group()
def ops():
    """Operations log commands."""
    pass


@ops.command("read")
@click.option("--since", default="1h", help="Time window (e.g., 1h, 30m, 24h)")
def ops_read(since):
    """Read recent operations log entries."""
    console.print(f"[bold]Operations Log (since {since})[/bold]\n")
    console.print("[yellow]Ops log coming soon![/yellow]")


def main():
    """Main entry point."""
    cli()


if __name__ == "__main__":
    main()

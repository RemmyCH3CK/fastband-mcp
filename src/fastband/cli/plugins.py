"""
Fastband CLI - Plugin management commands.

Provides commands for discovering, loading, and managing plugins.
"""

import asyncio

import typer
from rich import box
from rich.console import Console
from rich.table import Table

console = Console()

# Create plugins subcommand app
plugins_app = typer.Typer(
    name="plugins",
    help="Plugin management commands",
    no_args_is_help=True,
)


@plugins_app.command("list")
def plugins_list(
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show detailed plugin information",
    ),
):
    """
    List all discovered plugins.

    Shows plugins registered via Python entry points.
    """
    from fastband.core.plugins import get_plugin_manager

    manager = get_plugin_manager()
    plugins = manager.discover()

    if not plugins:
        console.print("[yellow]No plugins found.[/yellow]")
        console.print("\nTo create a plugin, add an entry point in pyproject.toml:")
        console.print('[dim][project.entry-points."fastband.plugins"][/dim]')
        console.print('[dim]my_plugin = "my_package.plugin:MyPlugin"[/dim]')
        return

    table = Table(
        title="Fastband Plugins",
        box=box.ROUNDED,
    )
    table.add_column("Name", style="cyan")
    table.add_column("Version")
    table.add_column("Status")

    if verbose:
        table.add_column("Description")
        table.add_column("Provides")

    loaded_names = set(manager.loaded.keys())

    for plugin in plugins:
        status = "[green]Loaded[/green]" if plugin.name in loaded_names else "[dim]Available[/dim]"

        row = [plugin.name, plugin.version, status]

        if verbose:
            provides = []
            if plugin.provides_tools:
                provides.append("tools")
            if plugin.provides_routes:
                provides.append("routes")
            if plugin.provides_cli:
                provides.append("cli")

            row.append(plugin.description or "[dim]—[/dim]")
            row.append(", ".join(provides) if provides else "[dim]—[/dim]")

        table.add_row(*row)

    console.print(table)
    console.print(f"\n[dim]{len(plugins)} plugin(s) discovered, {len(loaded_names)} loaded[/dim]")


@plugins_app.command("load")
def plugins_load(
    name: str = typer.Argument(
        ...,
        help="Plugin name to load",
    ),
):
    """
    Load a plugin by name.

    The plugin must be discoverable via entry points.
    """
    from fastband.core.plugins import get_plugin_manager

    manager = get_plugin_manager()

    # Discover if not already done
    manager.ensure_discovered()

    if not manager.is_discovered(name):
        console.print(f"[red]Plugin not found: {name}[/red]")
        console.print("\nAvailable plugins:")
        for p in manager.discover():
            console.print(f"  - {p.name}")
        raise typer.Exit(1)

    if name in manager.loaded:
        console.print(f"[yellow]Plugin already loaded: {name}[/yellow]")
        return

    async def _load():
        return await manager.load(name)

    success = asyncio.run(_load())

    if success:
        plugin = manager.get_plugin(name)
        console.print(f"[green]✓[/green] Loaded plugin: {name} v{plugin.version}")
    else:
        console.print(f"[red]Failed to load plugin: {name}[/red]")
        raise typer.Exit(1)


@plugins_app.command("unload")
def plugins_unload(
    name: str = typer.Argument(
        ...,
        help="Plugin name to unload",
    ),
):
    """
    Unload a loaded plugin.
    """
    from fastband.core.plugins import get_plugin_manager

    manager = get_plugin_manager()

    if name not in manager.loaded:
        console.print(f"[yellow]Plugin not loaded: {name}[/yellow]")
        return

    async def _unload():
        return await manager.unload(name)

    success = asyncio.run(_unload())

    if success:
        console.print(f"[green]✓[/green] Unloaded plugin: {name}")
    else:
        console.print(f"[red]Failed to unload plugin: {name}[/red]")
        raise typer.Exit(1)


@plugins_app.command("info")
def plugins_info(
    name: str = typer.Argument(
        ...,
        help="Plugin name to show info for",
    ),
):
    """
    Show detailed information about a plugin.
    """
    from fastband.core.plugins import get_plugin_manager

    manager = get_plugin_manager()

    # Discover if needed
    manager.ensure_discovered()

    # Get plugin instance and metadata
    plugin = manager.get_plugin_instance(name)
    if plugin is None:
        console.print(f"[red]Plugin not found: {name}[/red]")
        raise typer.Exit(1)

    metadata = plugin.get_metadata()

    # Display info
    console.print(f"\n[bold cyan]{metadata.name}[/bold cyan] v{metadata.version}")

    if metadata.description:
        console.print(f"  {metadata.description}")

    if metadata.author:
        console.print(f"  [dim]Author: {metadata.author}[/dim]")

    console.print(f"\n  Entry point: [dim]{metadata.entry_point}[/dim]")
    console.print(f"  Module: [dim]{metadata.module}[/dim]")

    # Capabilities
    console.print("\n  [bold]Provides:[/bold]")
    if metadata.provides_tools:
        tools = plugin.get_tools()
        console.print(f"    - Tools: {len(tools)} tool(s)")
    if metadata.provides_routes:
        console.print("    - API routes")
    if metadata.provides_cli:
        console.print("    - CLI commands")

    if not any([metadata.provides_tools, metadata.provides_routes, metadata.provides_cli]):
        console.print("    [dim]Event handlers only[/dim]")

    # Status
    is_loaded = name in manager.loaded
    console.print(
        f"\n  Status: {'[green]Loaded[/green]' if is_loaded else '[dim]Not loaded[/dim]'}"
    )

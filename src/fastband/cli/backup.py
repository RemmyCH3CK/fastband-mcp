"""
Fastband CLI - Backup subcommand.

Provides commands for managing project backups:
- create: Create a new backup
- list: List available backups
- show: Show backup details
- restore: Restore from a backup
- prune: Remove old backups
- stats: Show backup statistics
"""

import json
import typer
from datetime import datetime
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

from fastband.backup import BackupManager, BackupInfo, BackupType

# Create the backup subcommand app
backup_app = typer.Typer(
    name="backup",
    help="Backup management commands",
    no_args_is_help=True,
)

# Rich console for output
console = Console()


def _get_manager(path: Optional[Path] = None) -> BackupManager:
    """Get the backup manager for the project."""
    project_path = (path or Path.cwd()).resolve()
    return BackupManager(project_path=project_path)


def _format_type(backup_type: BackupType) -> str:
    """Format backup type with color."""
    color_map = {
        BackupType.FULL: "green",
        BackupType.INCREMENTAL: "cyan",
        BackupType.ON_CHANGE: "yellow",
        BackupType.MANUAL: "blue",
    }
    color = color_map.get(backup_type, "white")
    return f"[{color}]{backup_type.value}[/{color}]"


def _format_size(size_bytes: int) -> str:
    """Format size in human-readable format."""
    size = size_bytes
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def _backup_to_dict(backup: BackupInfo) -> dict:
    """Convert backup to dictionary for JSON output."""
    return backup.to_dict()


# =============================================================================
# CREATE COMMAND
# =============================================================================


@backup_app.command("create")
def create_backup(
    description: Optional[str] = typer.Option(
        None,
        "--description",
        "-d",
        help="Description for this backup",
    ),
    backup_type: str = typer.Option(
        "manual",
        "--type",
        "-t",
        help="Backup type (manual, full, on_change)",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Create backup even if no changes detected",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output as JSON",
    ),
    path: Optional[Path] = typer.Option(
        None,
        "--path",
        "-p",
        help="Project path (default: current directory)",
    ),
):
    """
    Create a new backup of project data.

    Creates a compressed archive of Fastband configuration, tickets,
    and other project data.
    """
    manager = _get_manager(path)

    # Parse backup type
    try:
        btype = BackupType(backup_type)
    except ValueError:
        console.print(f"[red]Invalid backup type: {backup_type}[/red]")
        valid = [t.value for t in BackupType]
        console.print(f"[dim]Valid types: {', '.join(valid)}[/dim]")
        raise typer.Exit(1)

    if not json_output:
        console.print(Panel.fit(
            "[bold blue]Creating Backup[/bold blue]",
            border_style="blue",
        ))

    try:
        backup_info = manager.create_backup(
            backup_type=btype,
            description=description or "",
            force=force,
        )

        if backup_info is None:
            if json_output:
                console.print(json.dumps({
                    "success": False,
                    "message": "No changes detected, backup skipped",
                }, indent=2))
            else:
                console.print("[yellow]No changes detected. Use --force to create backup anyway.[/yellow]")
            raise typer.Exit(0)

        if json_output:
            console.print(json.dumps({
                "success": True,
                "backup": _backup_to_dict(backup_info),
            }, indent=2))
        else:
            console.print(f"[green]Backup created successfully[/green]")
            console.print(f"  ID: [bold]{backup_info.id}[/bold]")
            console.print(f"  Type: {_format_type(backup_info.backup_type)}")
            console.print(f"  Size: {backup_info.size_human}")
            console.print(f"  Files: {backup_info.files_count}")
            if description:
                console.print(f"  Description: {description}")

    except Exception as e:
        if json_output:
            console.print(json.dumps({
                "success": False,
                "error": str(e),
            }, indent=2))
        else:
            console.print(f"[red]Backup failed: {e}[/red]")
        raise typer.Exit(1)


# =============================================================================
# LIST COMMAND
# =============================================================================


@backup_app.command("list")
def list_backups(
    limit: int = typer.Option(
        20,
        "--limit",
        "-l",
        help="Maximum number of backups to show",
    ),
    backup_type: Optional[str] = typer.Option(
        None,
        "--type",
        "-t",
        help="Filter by backup type",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output as JSON",
    ),
    path: Optional[Path] = typer.Option(
        None,
        "--path",
        "-p",
        help="Project path (default: current directory)",
    ),
):
    """
    List available backups.

    Shows all backups with their ID, type, size, and creation date.
    """
    manager = _get_manager(path)
    backups = manager.list_backups()

    # Filter by type if specified
    if backup_type:
        try:
            btype = BackupType(backup_type)
            backups = [b for b in backups if b.backup_type == btype]
        except ValueError:
            console.print(f"[red]Invalid backup type: {backup_type}[/red]")
            raise typer.Exit(1)

    # Apply limit
    backups = backups[:limit]

    if not backups:
        if json_output:
            console.print("[]")
        else:
            console.print("[yellow]No backups found.[/yellow]")
            console.print("[dim]Run 'fastband backup create' to create a backup.[/dim]")
        raise typer.Exit(0)

    if json_output:
        output = [_backup_to_dict(b) for b in backups]
        console.print(json.dumps(output, indent=2))
        raise typer.Exit(0)

    # Create table
    table = Table(
        title="Available Backups",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("ID", style="bold", width=18)
    table.add_column("Type")
    table.add_column("Size", justify="right")
    table.add_column("Files", justify="right")
    table.add_column("Created", width=20)
    table.add_column("Description", max_width=30)

    for backup in backups:
        table.add_row(
            backup.id,
            _format_type(backup.backup_type),
            backup.size_human,
            str(backup.files_count),
            backup.created_at.strftime("%Y-%m-%d %H:%M"),
            backup.description[:30] + "..." if len(backup.description) > 30 else backup.description or "[dim]-[/dim]",
        )

    console.print(table)
    console.print(f"\n[dim]Showing {len(backups)} backup(s)[/dim]")


# =============================================================================
# SHOW COMMAND
# =============================================================================


@backup_app.command("show")
def show_backup(
    backup_id: str = typer.Argument(
        ...,
        help="Backup ID to show",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output as JSON",
    ),
    path: Optional[Path] = typer.Option(
        None,
        "--path",
        "-p",
        help="Project path (default: current directory)",
    ),
):
    """
    Show detailed information about a backup.

    Displays all backup metadata including checksum and file count.
    """
    manager = _get_manager(path)
    backup = manager.get_backup(backup_id)

    if not backup:
        console.print(f"[red]Backup not found: {backup_id}[/red]")
        raise typer.Exit(1)

    if json_output:
        console.print(json.dumps(_backup_to_dict(backup), indent=2))
        raise typer.Exit(0)

    # Header panel
    console.print(Panel.fit(
        f"[bold blue]Backup {backup.id}[/bold blue]\n"
        f"[dim]{backup.description or 'No description'}[/dim]",
        title="Backup Details",
        border_style="blue",
    ))

    # Info table
    info_table = Table(
        box=box.ROUNDED,
        show_header=False,
    )
    info_table.add_column("Field", style="cyan")
    info_table.add_column("Value")

    info_table.add_row("ID", backup.id)
    info_table.add_row("Type", _format_type(backup.backup_type))
    info_table.add_row("Created", backup.created_at.strftime("%Y-%m-%d %H:%M:%S"))
    info_table.add_row("Size", backup.size_human)
    info_table.add_row("Files", str(backup.files_count))
    info_table.add_row("Checksum", backup.checksum[:16] + "...")
    info_table.add_row("Filename", backup.filename)

    if backup.parent_id:
        info_table.add_row("Parent Backup", backup.parent_id)

    console.print(info_table)

    if backup.metadata:
        console.print("\n[bold]Metadata:[/bold]")
        for key, value in backup.metadata.items():
            console.print(f"  {key}: {value}")


# =============================================================================
# RESTORE COMMAND
# =============================================================================


@backup_app.command("restore")
def restore_backup(
    backup_id: str = typer.Argument(
        ...,
        help="Backup ID to restore",
    ),
    target: Optional[Path] = typer.Option(
        None,
        "--target",
        "-t",
        help="Target path for restore (default: project path)",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        "-n",
        help="Show what would be restored without actually restoring",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Skip confirmation prompt",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output as JSON",
    ),
    path: Optional[Path] = typer.Option(
        None,
        "--path",
        "-p",
        help="Project path (default: current directory)",
    ),
):
    """
    Restore from a backup.

    Restores project data from a backup archive. Creates a pre-restore
    backup automatically before restoring.
    """
    manager = _get_manager(path)
    backup = manager.get_backup(backup_id)

    if not backup:
        if json_output:
            console.print(json.dumps({
                "success": False,
                "error": f"Backup not found: {backup_id}",
            }, indent=2))
        else:
            console.print(f"[red]Backup not found: {backup_id}[/red]")
        raise typer.Exit(1)

    if dry_run:
        console.print(Panel.fit(
            f"[bold yellow]Dry Run - Restore Preview[/bold yellow]\n"
            f"[dim]Backup: {backup_id}[/dim]",
            border_style="yellow",
        ))

        success = manager.restore_backup(backup_id, target_path=target, dry_run=True)

        if json_output:
            console.print(json.dumps({
                "dry_run": True,
                "backup_id": backup_id,
                "would_restore": success,
            }, indent=2))
        raise typer.Exit(0)

    # Confirm restore
    if not force and not json_output:
        console.print(Panel.fit(
            f"[bold red]Restore Backup[/bold red]\n"
            f"Backup: {backup_id}\n"
            f"Created: {backup.created_at.strftime('%Y-%m-%d %H:%M')}\n"
            f"Size: {backup.size_human}\n\n"
            f"[yellow]This will overwrite current project data![/yellow]\n"
            f"[dim]A pre-restore backup will be created automatically.[/dim]",
            border_style="red",
        ))

        confirm = typer.confirm("Proceed with restore?")
        if not confirm:
            console.print("[yellow]Restore cancelled[/yellow]")
            raise typer.Exit(0)

    # Perform restore
    try:
        success = manager.restore_backup(backup_id, target_path=target, dry_run=False)

        if json_output:
            console.print(json.dumps({
                "success": success,
                "backup_id": backup_id,
                "message": "Restore completed" if success else "Restore failed",
            }, indent=2))
        else:
            if success:
                console.print(f"[green]Restore completed successfully[/green]")
                console.print(f"  Backup: {backup_id}")
                console.print(f"  Files restored: {backup.files_count}")
            else:
                console.print(f"[red]Restore failed[/red]")
                raise typer.Exit(1)

    except Exception as e:
        if json_output:
            console.print(json.dumps({
                "success": False,
                "error": str(e),
            }, indent=2))
        else:
            console.print(f"[red]Restore failed: {e}[/red]")
        raise typer.Exit(1)


# =============================================================================
# PRUNE COMMAND
# =============================================================================


@backup_app.command("prune")
def prune_backups(
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        "-n",
        help="Show what would be pruned without actually deleting",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Skip confirmation prompt",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output as JSON",
    ),
    path: Optional[Path] = typer.Option(
        None,
        "--path",
        "-p",
        help="Project path (default: current directory)",
    ),
):
    """
    Remove old backups based on retention policy.

    Uses the configured retention settings to determine which backups
    to remove. Manual backups are kept longer than automatic ones.
    """
    manager = _get_manager(path)

    if dry_run:
        if not json_output:
            console.print(Panel.fit(
                "[bold yellow]Dry Run - Prune Preview[/bold yellow]",
                border_style="yellow",
            ))

        pruned = manager.prune_old_backups(dry_run=True)

        if json_output:
            console.print(json.dumps({
                "dry_run": True,
                "would_prune": len(pruned),
                "backups": [_backup_to_dict(b) for b in pruned],
            }, indent=2))
        else:
            if pruned:
                console.print(f"[yellow]Would prune {len(pruned)} backup(s)[/yellow]")
            else:
                console.print("[green]No backups to prune[/green]")
        raise typer.Exit(0)

    # Get count first
    would_prune = manager.prune_old_backups(dry_run=True)

    if not would_prune:
        if json_output:
            console.print(json.dumps({
                "success": True,
                "pruned": 0,
                "message": "No backups to prune",
            }, indent=2))
        else:
            console.print("[green]No backups to prune[/green]")
        raise typer.Exit(0)

    # Confirm
    if not force and not json_output:
        console.print(f"[yellow]Will prune {len(would_prune)} old backup(s)[/yellow]")
        confirm = typer.confirm("Proceed?")
        if not confirm:
            console.print("[yellow]Prune cancelled[/yellow]")
            raise typer.Exit(0)

    # Prune
    pruned = manager.prune_old_backups(dry_run=False)

    if json_output:
        console.print(json.dumps({
            "success": True,
            "pruned": len(pruned),
            "backups": [_backup_to_dict(b) for b in pruned],
        }, indent=2))
    else:
        console.print(f"[green]Pruned {len(pruned)} old backup(s)[/green]")
        for backup in pruned:
            console.print(f"  - {backup.id} ({backup.size_human})")


# =============================================================================
# DELETE COMMAND
# =============================================================================


@backup_app.command("delete")
def delete_backup(
    backup_id: str = typer.Argument(
        ...,
        help="Backup ID to delete",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Skip confirmation prompt",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output as JSON",
    ),
    path: Optional[Path] = typer.Option(
        None,
        "--path",
        "-p",
        help="Project path (default: current directory)",
    ),
):
    """
    Delete a specific backup.

    Permanently removes a backup archive and its manifest entry.
    """
    manager = _get_manager(path)
    backup = manager.get_backup(backup_id)

    if not backup:
        if json_output:
            console.print(json.dumps({
                "success": False,
                "error": f"Backup not found: {backup_id}",
            }, indent=2))
        else:
            console.print(f"[red]Backup not found: {backup_id}[/red]")
        raise typer.Exit(1)

    # Confirm
    if not force and not json_output:
        console.print(f"Delete backup [bold]{backup_id}[/bold]?")
        console.print(f"  Type: {_format_type(backup.backup_type)}")
        console.print(f"  Size: {backup.size_human}")
        console.print(f"  Created: {backup.created_at.strftime('%Y-%m-%d %H:%M')}")

        confirm = typer.confirm("Proceed?")
        if not confirm:
            console.print("[yellow]Delete cancelled[/yellow]")
            raise typer.Exit(0)

    # Delete
    success = manager.delete_backup(backup_id)

    if json_output:
        console.print(json.dumps({
            "success": success,
            "backup_id": backup_id,
        }, indent=2))
    else:
        if success:
            console.print(f"[green]Deleted backup: {backup_id}[/green]")
        else:
            console.print(f"[red]Failed to delete backup[/red]")
            raise typer.Exit(1)


# =============================================================================
# STATS COMMAND
# =============================================================================


@backup_app.command("stats")
def backup_stats(
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output as JSON",
    ),
    path: Optional[Path] = typer.Option(
        None,
        "--path",
        "-p",
        help="Project path (default: current directory)",
    ),
):
    """
    Show backup statistics.

    Displays summary of all backups including total count, size,
    and retention configuration.
    """
    manager = _get_manager(path)
    stats = manager.get_stats()

    if json_output:
        console.print(json.dumps(stats, indent=2))
        raise typer.Exit(0)

    console.print(Panel.fit(
        "[bold blue]Backup Statistics[/bold blue]",
        border_style="blue",
    ))

    # Overview table
    table = Table(
        box=box.ROUNDED,
        show_header=False,
    )
    table.add_column("Metric", style="cyan")
    table.add_column("Value")

    table.add_row("Total Backups", str(stats["total_backups"]))
    table.add_row("Total Size", stats["total_size_human"])

    if stats["oldest"]:
        table.add_row("Oldest", stats["oldest"][:10])
    if stats["newest"]:
        table.add_row("Newest", stats["newest"][:10])

    has_changes = stats["has_changes"]
    changes_status = "[yellow]Changes detected[/yellow]" if has_changes else "[green]No changes[/green]"
    table.add_row("Status", changes_status)

    console.print(table)

    # By type breakdown
    if stats["by_type"]:
        console.print("\n[bold]By Type:[/bold]")
        for type_name, count in stats["by_type"].items():
            console.print(f"  {type_name}: {count}")

    # Config
    config = stats["config"]
    console.print("\n[bold]Configuration:[/bold]")
    console.print(f"  Enabled: {'Yes' if config['enabled'] else 'No'}")
    console.print(f"  Daily: {'Yes' if config['daily_enabled'] else 'No'} (retention: {config['daily_retention']} days)")
    console.print(f"  Weekly: {'Yes' if config['weekly_enabled'] else 'No'} (retention: {config['weekly_retention']} weeks)")
    console.print(f"  Change detection: {'Yes' if config['change_detection'] else 'No'}")

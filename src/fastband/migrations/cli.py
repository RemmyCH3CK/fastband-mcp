"""
Database migration CLI commands.

Provides Alembic-based migration management for Fastband databases.

Commands:
    fastband db current    - Show current migration version
    fastband db upgrade    - Apply pending migrations
    fastband db downgrade  - Roll back migrations
    fastband db history    - Show migration history
    fastband db revision   - Create a new migration
"""

import os
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

console = Console()
app = typer.Typer(
    name="db",
    help="Database migration commands (requires alembic)",
    no_args_is_help=True,
)


def _get_alembic_config():
    """Get Alembic configuration."""
    try:
        from alembic.config import Config
    except ImportError:
        console.print(
            "[red]Alembic is not installed.[/red]\n"
            "Install with: pip install 'fastband-agent-control[migrations]'"
        )
        raise typer.Exit(1)

    # Path to our alembic.ini
    migrations_dir = Path(__file__).parent
    config_path = migrations_dir / "alembic.ini"

    if not config_path.exists():
        console.print(f"[red]Alembic config not found at {config_path}[/red]")
        raise typer.Exit(1)

    config = Config(str(config_path))
    config.set_main_option("script_location", str(migrations_dir))

    return config


def _get_database_url(database: str = "tickets") -> str:
    """Get database URL based on database type."""
    # Check for explicit URL
    env_url = os.environ.get("FASTBAND_DATABASE_URL")
    if env_url:
        return env_url

    # Default paths
    db_paths = {
        "tickets": Path.cwd() / ".fastband" / "tickets.db",
        "embeddings": Path.cwd() / ".fastband" / "embeddings.db",
    }

    db_path = db_paths.get(database, db_paths["tickets"])
    return f"sqlite:///{db_path}"


@app.command()
def current(
    database: str = typer.Option("tickets", help="Database to check (tickets or embeddings)"),
):
    """Show current migration version."""
    from alembic import command

    config = _get_alembic_config()
    os.environ["FASTBAND_DATABASE_URL"] = _get_database_url(database)

    console.print(f"\n[bold]Current migration version for {database} database:[/bold]")
    command.current(config, verbose=True)


@app.command()
def upgrade(
    revision: str = typer.Argument("head", help="Target revision (default: head)"),
    database: str = typer.Option("tickets", help="Database to upgrade"),
    sql: bool = typer.Option(False, "--sql", help="Generate SQL instead of applying"),
):
    """Apply pending migrations."""
    from alembic import command

    config = _get_alembic_config()
    os.environ["FASTBAND_DATABASE_URL"] = _get_database_url(database)

    console.print(f"\n[bold]Upgrading {database} database to {revision}...[/bold]")

    if sql:
        command.upgrade(config, revision, sql=True)
    else:
        command.upgrade(config, revision)
        console.print("[green]Upgrade complete![/green]")


@app.command()
def downgrade(
    revision: str = typer.Argument(..., help="Target revision (e.g., '-1' for one step back)"),
    database: str = typer.Option("tickets", help="Database to downgrade"),
    sql: bool = typer.Option(False, "--sql", help="Generate SQL instead of applying"),
):
    """Roll back migrations."""
    from alembic import command

    config = _get_alembic_config()
    os.environ["FASTBAND_DATABASE_URL"] = _get_database_url(database)

    console.print(f"\n[bold yellow]Downgrading {database} database to {revision}...[/bold yellow]")

    if sql:
        command.downgrade(config, revision, sql=True)
    else:
        command.downgrade(config, revision)
        console.print("[green]Downgrade complete![/green]")


@app.command()
def history(
    database: str = typer.Option("tickets", help="Database to show history for"),
    verbose: bool = typer.Option(False, "-v", "--verbose", help="Show detailed info"),
):
    """Show migration history."""
    from alembic import command

    config = _get_alembic_config()
    os.environ["FASTBAND_DATABASE_URL"] = _get_database_url(database)

    console.print(f"\n[bold]Migration history for {database} database:[/bold]")
    command.history(config, verbose=verbose)


@app.command()
def revision(
    message: str = typer.Option(..., "-m", "--message", help="Migration message"),
    autogenerate: bool = typer.Option(
        False, "--autogenerate", help="Auto-detect schema changes (requires SQLAlchemy models)"
    ),
):
    """Create a new migration revision."""
    from alembic import command

    config = _get_alembic_config()

    console.print(f"\n[bold]Creating new migration: {message}[/bold]")
    command.revision(config, message=message, autogenerate=autogenerate)
    console.print("[green]Migration created![/green]")


@app.command()
def heads():
    """Show current head revisions."""
    from alembic import command

    config = _get_alembic_config()
    command.heads(config, verbose=True)


@app.command()
def stamp(
    revision: str = typer.Argument(..., help="Revision to stamp (e.g., 'head' or revision ID)"),
    database: str = typer.Option("tickets", help="Database to stamp"),
):
    """Stamp the database with a specific revision without running migrations.

    Useful for marking existing databases as up-to-date.
    """
    from alembic import command

    config = _get_alembic_config()
    os.environ["FASTBAND_DATABASE_URL"] = _get_database_url(database)

    console.print(f"\n[bold]Stamping {database} database with revision {revision}...[/bold]")
    command.stamp(config, revision)
    console.print("[green]Database stamped![/green]")


@app.command()
def check(
    database: str = typer.Option("tickets", help="Database to check"),
):
    """Check if database is up to date with migrations."""
    from alembic import command
    from alembic.script import ScriptDirectory
    from alembic.runtime.migration import MigrationContext
    from sqlalchemy import create_engine

    config = _get_alembic_config()
    db_url = _get_database_url(database)
    os.environ["FASTBAND_DATABASE_URL"] = db_url

    script = ScriptDirectory.from_config(config)
    engine = create_engine(db_url)

    with engine.connect() as conn:
        context = MigrationContext.configure(conn)
        current_rev = context.get_current_revision()
        head_rev = script.get_current_head()

        table = Table(title=f"Migration Status: {database}")
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Current Revision", current_rev or "(none)")
        table.add_row("Head Revision", head_rev or "(none)")
        table.add_row("Up to Date", "Yes" if current_rev == head_rev else "[red]No[/red]")

        console.print(table)

        if current_rev != head_rev:
            console.print("\n[yellow]Run 'fastband db upgrade head' to apply pending migrations.[/yellow]")

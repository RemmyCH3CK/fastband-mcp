"""
Alembic Environment Configuration for Fastband.

This module configures how Alembic runs migrations:
- Connects to the appropriate database (tickets or embeddings)
- Handles both online and offline migration modes
- Supports SQLite and PostgreSQL
"""

import os
from logging.config import fileConfig
from pathlib import Path

from alembic import context

# this is the Alembic Config object
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def get_database_url() -> str:
    """Get the database URL for migrations.

    Priority:
    1. FASTBAND_DATABASE_URL environment variable
    2. Default to .fastband/tickets.db in current directory
    """
    # Check for explicit database URL
    db_url = os.environ.get("FASTBAND_DATABASE_URL")
    if db_url:
        return db_url

    # Default to tickets database
    db_path = Path.cwd() / ".fastband" / "tickets.db"
    return f"sqlite:///{db_path}"


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This generates SQL scripts without connecting to the database.
    Useful for review or applying to production via other tools.
    """
    url = get_database_url()
    context.configure(
        url=url,
        target_metadata=None,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    This connects to the database and applies migrations directly.
    """
    from sqlalchemy import create_engine, pool

    url = get_database_url()

    # SQLite doesn't support ALTER TABLE well, so we need to use batch mode
    is_sqlite = url.startswith("sqlite")

    connectable = create_engine(
        url,
        poolclass=pool.NullPool if is_sqlite else None,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=None,
            # SQLite-specific: use batch mode for table alterations
            render_as_batch=is_sqlite,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

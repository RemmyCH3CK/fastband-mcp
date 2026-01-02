"""
Fastband Database Migrations.

This module provides Alembic-based database migrations for Fastband.

Enterprise Features:
- Schema versioning for tickets database
- Schema versioning for embeddings database
- Automatic migration on startup (optional)
- Migration history tracking

Usage:
    # Check current version
    fastband db current

    # Create a new migration
    fastband db revision -m "Add column to tickets"

    # Apply migrations
    fastband db upgrade head

    # Rollback one version
    fastband db downgrade -1

Environment Variables:
    FASTBAND_DB_AUTO_MIGRATE=true  # Auto-migrate on Hub startup
"""

from pathlib import Path

# Migration directory path
MIGRATIONS_DIR = Path(__file__).parent
VERSIONS_DIR = MIGRATIONS_DIR / "versions"

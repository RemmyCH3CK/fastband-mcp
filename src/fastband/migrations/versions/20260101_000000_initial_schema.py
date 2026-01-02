"""Initial schema for tickets database.

Revision ID: 001_initial
Revises: None
Create Date: 2026-01-01 00:00:00.000000

This migration captures the initial database schema for:
- tickets: Main ticket storage table
- agents: AI agent tracking
- metadata: Key-value storage for settings

Note: This migration is for documentation/reference. Existing databases
already have this schema created by the application code.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create initial database schema."""
    # Create tickets table
    op.create_table(
        "tickets",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("ticket_number", sa.Text(), unique=True, nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("ticket_type", sa.Text(), nullable=False, server_default="task"),
        sa.Column("priority", sa.Text(), nullable=False, server_default="medium"),
        sa.Column("status", sa.Text(), nullable=False, server_default="open"),
        sa.Column("assigned_to", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Text(), server_default="system"),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.Column("started_at", sa.Text(), nullable=True),
        sa.Column("completed_at", sa.Text(), nullable=True),
        sa.Column("due_date", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("resolution", sa.Text(), nullable=True),
        sa.Column("app", sa.Text(), nullable=True),
        sa.Column("app_version", sa.Text(), nullable=True),
        sa.Column("problem_summary", sa.Text(), nullable=True),
        sa.Column("solution_summary", sa.Text(), nullable=True),
        sa.Column("testing_notes", sa.Text(), nullable=True),
        sa.Column("before_screenshot", sa.Text(), nullable=True),
        sa.Column("after_screenshot", sa.Text(), nullable=True),
        sa.Column("review_status", sa.Text(), nullable=True),
        sa.Column("data", sa.Text(), nullable=False),  # Full JSON data
    )

    # Create indexes on tickets
    op.create_index("idx_tickets_status", "tickets", ["status"])
    op.create_index("idx_tickets_priority", "tickets", ["priority"])
    op.create_index("idx_tickets_assigned", "tickets", ["assigned_to"])
    op.create_index("idx_tickets_number", "tickets", ["ticket_number"])

    # Create agents table
    op.create_table(
        "agents",
        sa.Column("name", sa.Text(), primary_key=True),
        sa.Column("agent_type", sa.Text(), nullable=False, server_default="ai"),
        sa.Column("active", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("last_seen", sa.Text(), nullable=False),
        sa.Column("data", sa.Text(), nullable=False),  # Full JSON data
    )

    # Create metadata table
    op.create_table(
        "metadata",
        sa.Column("key", sa.Text(), primary_key=True),
        sa.Column("value", sa.Text(), nullable=False),
    )

    # Initialize next_id in metadata
    op.execute("INSERT OR IGNORE INTO metadata (key, value) VALUES ('next_id', '1')")


def downgrade() -> None:
    """Drop all tables."""
    op.drop_index("idx_tickets_number", "tickets")
    op.drop_index("idx_tickets_assigned", "tickets")
    op.drop_index("idx_tickets_priority", "tickets")
    op.drop_index("idx_tickets_status", "tickets")
    op.drop_table("metadata")
    op.drop_table("agents")
    op.drop_table("tickets")

"""
Fastband Ticket Management System.

Provides an adaptive ticket management system for development workflows:
- Ticket data models with status and priority management
- Storage backends (JSON, SQLite)
- Code review workflow management
- CLI commands for ticket operations
- Web dashboard for visualization
- MCP tools for AI agent integration
"""

from fastband.tickets.models import (
    Ticket,
    TicketStatus,
    TicketPriority,
    TicketType,
    Agent,
    TicketHistory,
    TicketComment,
)
from fastband.tickets.storage import (
    TicketStore,
    JSONTicketStore,
    SQLiteTicketStore,
    StorageFactory,
    get_store,
)
from fastband.tickets.review import (
    ReviewManager,
    ReviewResult,
    ReviewType,
    ReviewStatus,
    ReviewStatistics,
)

__all__ = [
    # Models
    "Ticket",
    "TicketStatus",
    "TicketPriority",
    "TicketType",
    "Agent",
    "TicketHistory",
    "TicketComment",
    # Storage
    "TicketStore",
    "JSONTicketStore",
    "SQLiteTicketStore",
    "StorageFactory",
    "get_store",
    # Review
    "ReviewManager",
    "ReviewResult",
    "ReviewType",
    "ReviewStatus",
    "ReviewStatistics",
]

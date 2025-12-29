#!/usr/bin/env python3
"""
Custom MCP Server with Fastband Ticket Tools.

This example shows how to build your own MCP server that includes
Fastband's ticket management tools plus your custom tools.

Usage:
    python custom_ticket_server.py

Then connect from Claude Code or any MCP client.
"""

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Import Fastband ticket system
from fastband.tickets.models import Ticket, TicketStatus, TicketPriority, TicketType
from fastband.tickets.storage import SQLiteTicketStore


# =============================================================================
# CUSTOM MCP SERVER
# =============================================================================

app = Server("my-ticket-server")

# Initialize ticket storage (SQLite database)
TICKETS_DB = Path("./my_tickets.db")
store: SQLiteTicketStore | None = None


def get_store() -> SQLiteTicketStore:
    """Get or create ticket storage."""
    global store
    if store is None:
        store = SQLiteTicketStore(TICKETS_DB)
    return store


def generate_ticket_id() -> str:
    """Generate a short ticket ID."""
    return f"TKT-{uuid4().hex[:8].upper()}"


# =============================================================================
# TOOL DEFINITIONS
# =============================================================================

TOOLS = [
    # --- Fastband Ticket Tools ---
    Tool(
        name="list_tickets",
        description="List all tickets with optional filtering by status or priority",
        inputSchema={
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["open", "in_progress", "review", "resolved", "closed"],
                    "description": "Filter by status"
                },
                "priority": {
                    "type": "string",
                    "enum": ["low", "medium", "high", "critical"],
                    "description": "Filter by priority"
                },
                "limit": {
                    "type": "integer",
                    "description": "Max tickets to return",
                    "default": 20
                }
            }
        }
    ),
    Tool(
        name="create_ticket",
        description="Create a new ticket for tracking work",
        inputSchema={
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Ticket title"
                },
                "description": {
                    "type": "string",
                    "description": "Detailed description"
                },
                "priority": {
                    "type": "string",
                    "enum": ["low", "medium", "high", "critical"],
                    "default": "medium"
                },
                "labels": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Labels/tags for the ticket"
                }
            },
            "required": ["title"]
        }
    ),
    Tool(
        name="get_ticket",
        description="Get details of a specific ticket by ID",
        inputSchema={
            "type": "object",
            "properties": {
                "ticket_id": {
                    "type": "string",
                    "description": "Ticket ID"
                }
            },
            "required": ["ticket_id"]
        }
    ),
    Tool(
        name="update_ticket_status",
        description="Update a ticket's status",
        inputSchema={
            "type": "object",
            "properties": {
                "ticket_id": {"type": "string"},
                "status": {
                    "type": "string",
                    "enum": ["open", "in_progress", "review", "resolved", "closed"]
                }
            },
            "required": ["ticket_id", "status"]
        }
    ),
    Tool(
        name="close_ticket",
        description="Close a ticket with a resolution message",
        inputSchema={
            "type": "object",
            "properties": {
                "ticket_id": {"type": "string"},
                "resolution": {"type": "string"}
            },
            "required": ["ticket_id"]
        }
    ),

    # --- Custom Tools (Your Own) ---
    Tool(
        name="ticket_stats",
        description="Get statistics about all tickets",
        inputSchema={
            "type": "object",
            "properties": {}
        }
    ),
    Tool(
        name="bulk_create",
        description="Create multiple tickets at once from a list",
        inputSchema={
            "type": "object",
            "properties": {
                "tickets": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "description": {"type": "string"},
                            "priority": {"type": "string"}
                        },
                        "required": ["title"]
                    }
                }
            },
            "required": ["tickets"]
        }
    ),
    Tool(
        name="search_tickets",
        description="Search tickets by keyword in title or description",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"}
            },
            "required": ["query"]
        }
    ),
]


# =============================================================================
# TOOL HANDLERS
# =============================================================================

@app.list_tools()
async def list_tools():
    """Return all available tools."""
    return TOOLS


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls."""

    storage = get_store()

    try:
        if name == "list_tickets":
            return await handle_list_tickets(storage, arguments)

        elif name == "create_ticket":
            return await handle_create_ticket(storage, arguments)

        elif name == "get_ticket":
            return await handle_get_ticket(storage, arguments)

        elif name == "update_ticket_status":
            return await handle_update_status(storage, arguments)

        elif name == "close_ticket":
            return await handle_close_ticket(storage, arguments)

        elif name == "ticket_stats":
            return await handle_ticket_stats(storage, arguments)

        elif name == "bulk_create":
            return await handle_bulk_create(storage, arguments)

        elif name == "search_tickets":
            return await handle_search_tickets(storage, arguments)

        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]

    except Exception as e:
        return [TextContent(type="text", text=f"Error: {str(e)}")]


# =============================================================================
# HANDLER IMPLEMENTATIONS
# =============================================================================

def status_to_enum(status: str) -> TicketStatus:
    """Convert string to TicketStatus enum."""
    mapping = {
        "open": TicketStatus.OPEN,
        "in_progress": TicketStatus.IN_PROGRESS,
        "review": TicketStatus.UNDER_REVIEW,
        "resolved": TicketStatus.RESOLVED,
        "closed": TicketStatus.CLOSED,
    }
    return mapping.get(status, TicketStatus.OPEN)


def priority_to_enum(priority: str) -> TicketPriority:
    """Convert string to TicketPriority enum."""
    mapping = {
        "low": TicketPriority.LOW,
        "medium": TicketPriority.MEDIUM,
        "high": TicketPriority.HIGH,
        "critical": TicketPriority.CRITICAL,
    }
    return mapping.get(priority, TicketPriority.MEDIUM)


async def handle_list_tickets(storage: SQLiteTicketStore, args: dict) -> list[TextContent]:
    """List tickets with optional filters."""
    status = status_to_enum(args["status"]) if args.get("status") else None
    priority = priority_to_enum(args["priority"]) if args.get("priority") else None

    tickets = storage.list(
        status=status,
        priority=priority,
        limit=args.get("limit", 20)
    )

    if not tickets:
        return [TextContent(type="text", text="No tickets found.")]

    lines = ["# Tickets\n"]
    for t in tickets:
        status_emoji = {
            TicketStatus.OPEN: "🔴",
            TicketStatus.IN_PROGRESS: "🟡",
            TicketStatus.UNDER_REVIEW: "🔵",
            TicketStatus.RESOLVED: "🟢",
            TicketStatus.CLOSED: "⚫",
        }.get(t.status, "⚪")

        lines.append(f"{status_emoji} **{t.id}** [{t.priority.value}] {t.title}")

    return [TextContent(type="text", text="\n".join(lines))]


async def handle_create_ticket(storage: SQLiteTicketStore, args: dict) -> list[TextContent]:
    """Create a new ticket."""
    ticket = Ticket(
        id=generate_ticket_id(),
        title=args["title"],
        description=args.get("description", ""),
        status=TicketStatus.OPEN,
        priority=priority_to_enum(args.get("priority", "medium")),
        ticket_type=TicketType.TASK,
        labels=args.get("labels", []),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    created = storage.create(ticket)

    return [TextContent(
        type="text",
        text=f"✅ Created ticket **{created.id}**\n\n"
             f"**Title:** {created.title}\n"
             f"**Priority:** {created.priority.value}\n"
             f"**Status:** {created.status.value}"
    )]


async def handle_get_ticket(storage: SQLiteTicketStore, args: dict) -> list[TextContent]:
    """Get ticket details."""
    ticket = storage.get(args["ticket_id"])

    if not ticket:
        return [TextContent(type="text", text=f"Ticket {args['ticket_id']} not found.")]

    return [TextContent(
        type="text",
        text=f"# {ticket.title}\n\n"
             f"**ID:** {ticket.id}\n"
             f"**Status:** {ticket.status.value}\n"
             f"**Priority:** {ticket.priority.value}\n"
             f"**Type:** {ticket.type.value}\n"
             f"**Labels:** {', '.join(ticket.labels) if ticket.labels else 'None'}\n"
             f"**Created:** {ticket.created_at}\n\n"
             f"## Description\n{ticket.description or 'No description'}"
    )]


async def handle_update_status(storage: SQLiteTicketStore, args: dict) -> list[TextContent]:
    """Update a ticket's status."""
    ticket = storage.get(args["ticket_id"])

    if not ticket:
        return [TextContent(type="text", text=f"Ticket {args['ticket_id']} not found.")]

    ticket.status = status_to_enum(args["status"])
    ticket.updated_at = datetime.now(timezone.utc)

    storage.update(ticket)

    return [TextContent(
        type="text",
        text=f"✅ Updated ticket **{ticket.id}** status to **{ticket.status.value}**"
    )]


async def handle_close_ticket(storage: SQLiteTicketStore, args: dict) -> list[TextContent]:
    """Close a ticket."""
    ticket = storage.get(args["ticket_id"])

    if not ticket:
        return [TextContent(type="text", text=f"Ticket {args['ticket_id']} not found.")]

    ticket.status = TicketStatus.CLOSED
    ticket.updated_at = datetime.now(timezone.utc)
    if args.get("resolution"):
        ticket.resolution = args["resolution"]

    storage.update(ticket)

    return [TextContent(
        type="text",
        text=f"✅ Closed ticket **{ticket.id}**\n\n"
             f"Resolution: {args.get('resolution', 'Completed')}"
    )]


async def handle_ticket_stats(storage: SQLiteTicketStore, args: dict) -> list[TextContent]:
    """Get ticket statistics."""
    all_tickets = storage.list(limit=1000)

    stats = {
        "total": len(all_tickets),
        "by_status": {},
        "by_priority": {}
    }

    for t in all_tickets:
        status_key = t.status.value
        priority_key = t.priority.value
        stats["by_status"][status_key] = stats["by_status"].get(status_key, 0) + 1
        stats["by_priority"][priority_key] = stats["by_priority"].get(priority_key, 0) + 1

    lines = [
        "# Ticket Statistics\n",
        f"**Total:** {stats['total']}\n",
        "## By Status"
    ]

    for status, count in stats["by_status"].items():
        lines.append(f"- {status}: {count}")

    lines.append("\n## By Priority")
    for priority, count in stats["by_priority"].items():
        lines.append(f"- {priority}: {count}")

    return [TextContent(type="text", text="\n".join(lines))]


async def handle_bulk_create(storage: SQLiteTicketStore, args: dict) -> list[TextContent]:
    """Create multiple tickets at once."""
    tickets_data = args["tickets"]
    created = []

    for data in tickets_data:
        ticket = Ticket(
            id=generate_ticket_id(),
            title=data["title"],
            description=data.get("description", ""),
            status=TicketStatus.OPEN,
            priority=priority_to_enum(data.get("priority", "medium")),
            ticket_type=TicketType.TASK,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        storage.create(ticket)
        created.append(ticket)

    lines = [f"✅ Created {len(created)} tickets:\n"]
    for t in created:
        lines.append(f"- **{t.id}**: {t.title}")

    return [TextContent(type="text", text="\n".join(lines))]


async def handle_search_tickets(storage: SQLiteTicketStore, args: dict) -> list[TextContent]:
    """Search tickets by keyword."""
    query = args["query"].lower()
    all_tickets = storage.list(limit=1000)

    matches = [
        t for t in all_tickets
        if query in t.title.lower() or query in (t.description or "").lower()
    ]

    if not matches:
        return [TextContent(type="text", text=f"No tickets matching '{args['query']}'")]

    lines = [f"# Search Results for '{args['query']}'\n", f"Found {len(matches)} tickets:\n"]
    for t in matches:
        lines.append(f"- **{t.id}** [{t.status.value}] {t.title}")

    return [TextContent(type="text", text="\n".join(lines))]


# =============================================================================
# MAIN
# =============================================================================

async def main():
    """Run the MCP server."""
    import sys
    print("Starting Custom Ticket Server...", file=sys.stderr, flush=True)
    print(f"Database: {TICKETS_DB.absolute()}", file=sys.stderr, flush=True)
    print(f"Tools available: {len(TOOLS)}", file=sys.stderr, flush=True)

    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())

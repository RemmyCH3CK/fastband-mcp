"""
Fastband CLI - Tickets subcommand.

Provides commands for managing tickets:
- list: List tickets with optional filters
- create: Create a new ticket
- show: Show detailed ticket information
- claim: Claim a ticket for work
- complete: Complete a ticket
- search: Search tickets by query
- update: Update ticket fields
- web: Start the web dashboard
"""

import json
from pathlib import Path

import typer
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from fastband.tickets import (
    Ticket,
    TicketPriority,
    TicketStatus,
    TicketType,
    get_store,
)

# Create the tickets subcommand app
tickets_app = typer.Typer(
    name="tickets",
    help="Ticket management commands",
    no_args_is_help=True,
)

# Rich console for output
console = Console()


def _get_store(path: Path | None = None):
    """Get the ticket store for the project."""
    if path is None:
        path = Path.cwd() / ".fastband" / "tickets.json"
    return get_store(path)


def _format_status(status: TicketStatus) -> str:
    """Format status with color."""
    color_map = {
        TicketStatus.OPEN: "red",
        TicketStatus.IN_PROGRESS: "yellow",
        TicketStatus.UNDER_REVIEW: "blue",
        TicketStatus.AWAITING_APPROVAL: "cyan",
        TicketStatus.RESOLVED: "green",
        TicketStatus.CLOSED: "dim",
        TicketStatus.BLOCKED: "magenta",
    }
    color = color_map.get(status, "white")
    return f"[{color}]{status.display_name}[/{color}]"


def _format_priority(priority: TicketPriority) -> str:
    """Format priority with color."""
    color_map = {
        TicketPriority.CRITICAL: "red bold",
        TicketPriority.HIGH: "red",
        TicketPriority.MEDIUM: "yellow",
        TicketPriority.LOW: "green",
    }
    color = color_map.get(priority, "white")
    return f"[{color}]{priority.display_name}[/{color}]"


def _format_type(ticket_type: TicketType) -> str:
    """Format ticket type with color."""
    color_map = {
        TicketType.BUG: "red",
        TicketType.FEATURE: "green",
        TicketType.ENHANCEMENT: "cyan",
        TicketType.TASK: "blue",
        TicketType.DOCUMENTATION: "magenta",
        TicketType.MAINTENANCE: "yellow",
        TicketType.SECURITY: "red bold",
        TicketType.PERFORMANCE: "yellow",
    }
    color = color_map.get(ticket_type, "white")
    return f"[{color}]{ticket_type.display_name}[/{color}]"


def _ticket_to_dict(ticket: Ticket) -> dict:
    """Convert ticket to dictionary for JSON output."""
    return {
        "id": ticket.id,
        "ticket_number": ticket.ticket_number,
        "title": ticket.title,
        "description": ticket.description,
        "type": ticket.ticket_type.value,
        "priority": ticket.priority.value,
        "status": ticket.status.value,
        "assigned_to": ticket.assigned_to,
        "created_at": ticket.created_at.isoformat(),
        "updated_at": ticket.updated_at.isoformat(),
        "labels": ticket.labels,
    }


def _format_ticket_id(ticket: Ticket) -> str:
    """Format ticket ID for display (prefer ticket_number)."""
    if ticket.ticket_number:
        return f"[bold cyan]{ticket.ticket_number}[/bold cyan]"
    return f"[dim]{ticket.id[:8]}[/dim]"


# =============================================================================
# LIST COMMAND
# =============================================================================


@tickets_app.command("list")
def list_tickets(
    status: str | None = typer.Option(
        None,
        "--status",
        "-s",
        help="Filter by status (open, in_progress, under_review, awaiting_approval, resolved, closed, blocked)",
    ),
    priority: str | None = typer.Option(
        None,
        "--priority",
        "-p",
        help="Filter by priority (critical, high, medium, low)",
    ),
    assigned_to: str | None = typer.Option(
        None,
        "--assigned-to",
        "-a",
        help="Filter by assigned agent",
    ),
    ticket_type: str | None = typer.Option(
        None,
        "--type",
        "-t",
        help="Filter by type (bug, feature, enhancement, task, etc.)",
    ),
    limit: int = typer.Option(
        50,
        "--limit",
        "-l",
        help="Maximum number of tickets to show",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output as JSON",
    ),
    path: Path | None = typer.Option(
        None,
        "--path",
        help="Path to ticket storage file",
    ),
):
    """
    List tickets with optional filters.

    Shows tickets in a table format with ID, title, status, priority,
    type, and assignee. Use filters to narrow down the list.
    """
    store = _get_store(path)

    # Parse filters
    status_filter = None
    if status:
        try:
            status_filter = TicketStatus.from_string(status)
        except ValueError:
            console.print(f"[red]Invalid status: {status}[/red]")
            valid = [s.value for s in TicketStatus]
            console.print(f"[dim]Valid statuses: {', '.join(valid)}[/dim]")
            raise typer.Exit(1)

    priority_filter = None
    if priority:
        try:
            priority_filter = TicketPriority.from_string(priority)
        except ValueError:
            console.print(f"[red]Invalid priority: {priority}[/red]")
            valid = [p.value for p in TicketPriority]
            console.print(f"[dim]Valid priorities: {', '.join(valid)}[/dim]")
            raise typer.Exit(1)

    type_filter = None
    if ticket_type:
        try:
            type_filter = TicketType.from_string(ticket_type)
        except ValueError:
            console.print(f"[red]Invalid type: {ticket_type}[/red]")
            valid = [t.value for t in TicketType]
            console.print(f"[dim]Valid types: {', '.join(valid)}[/dim]")
            raise typer.Exit(1)

    # Get tickets
    tickets = store.list(
        status=status_filter,
        priority=priority_filter,
        ticket_type=type_filter,
        assigned_to=assigned_to,
        limit=limit,
    )

    if not tickets:
        if json_output:
            console.print("[]")
        else:
            console.print("[yellow]No tickets found matching criteria.[/yellow]")
        raise typer.Exit(0)

    if json_output:
        output = [_ticket_to_dict(t) for t in tickets]
        console.print(json.dumps(output, indent=2, ensure_ascii=False))
        raise typer.Exit(0)

    # Build filter description
    filter_parts = []
    if status:
        filter_parts.append(f"status={status}")
    if priority:
        filter_parts.append(f"priority={priority}")
    if ticket_type:
        filter_parts.append(f"type={ticket_type}")
    if assigned_to:
        filter_parts.append(f"assigned_to={assigned_to}")

    title = "Tickets"
    if filter_parts:
        title += f" ({', '.join(filter_parts)})"

    # Create table
    table = Table(
        title=title,
        box=box.ROUNDED,
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("ID", style="bold cyan", width=10)
    table.add_column("Title", max_width=40)
    table.add_column("Status")
    table.add_column("Priority")
    table.add_column("Type")
    table.add_column("Assigned To", max_width=15)

    for ticket in tickets:
        ticket_id = ticket.ticket_number or ticket.id[:8]
        table.add_row(
            ticket_id,
            ticket.title[:40] + "..." if len(ticket.title) > 40 else ticket.title,
            _format_status(ticket.status),
            _format_priority(ticket.priority),
            _format_type(ticket.ticket_type),
            ticket.assigned_to or "[dim]-[/dim]",
        )

    console.print(table)
    console.print(f"\n[dim]Showing {len(tickets)} ticket(s)[/dim]")


# =============================================================================
# CREATE COMMAND
# =============================================================================


@tickets_app.command("create")
def create_ticket(
    title: str | None = typer.Option(
        None,
        "--title",
        "-t",
        help="Ticket title",
    ),
    description: str | None = typer.Option(
        None,
        "--description",
        "-d",
        help="Ticket description",
    ),
    ticket_type: str = typer.Option(
        "task",
        "--type",
        help="Ticket type (bug, feature, enhancement, task, etc.)",
    ),
    priority: str = typer.Option(
        "medium",
        "--priority",
        "-p",
        help="Priority (critical, high, medium, low)",
    ),
    assigned_to: str | None = typer.Option(
        None,
        "--assigned-to",
        "-a",
        help="Assign to agent",
    ),
    labels: str | None = typer.Option(
        None,
        "--labels",
        "-l",
        help="Comma-separated labels",
    ),
    interactive: bool = typer.Option(
        False,
        "--interactive",
        "-i",
        help="Create ticket interactively",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output created ticket as JSON",
    ),
    path: Path | None = typer.Option(
        None,
        "--path",
        help="Path to ticket storage file",
    ),
):
    """
    Create a new ticket.

    Can be used with command-line options or interactively with --interactive.
    """
    store = _get_store(path)

    # Interactive mode
    if interactive:
        title = typer.prompt("Title")
        description = typer.prompt("Description", default="")

        type_choices = [t.value for t in TicketType]
        ticket_type = typer.prompt(f"Type ({', '.join(type_choices)})", default="task")

        priority_choices = [p.value for p in TicketPriority]
        priority = typer.prompt(f"Priority ({', '.join(priority_choices)})", default="medium")

        assigned_to = typer.prompt("Assign to (optional)", default="")
        if not assigned_to:
            assigned_to = None

        labels = typer.prompt("Labels (comma-separated, optional)", default="")

    # Validate required fields
    if not title:
        console.print("[red]Title is required[/red]")
        console.print("[dim]Use --title or --interactive[/dim]")
        raise typer.Exit(1)

    # Parse type
    try:
        parsed_type = TicketType.from_string(ticket_type)
    except ValueError:
        console.print(f"[red]Invalid type: {ticket_type}[/red]")
        valid = [t.value for t in TicketType]
        console.print(f"[dim]Valid types: {', '.join(valid)}[/dim]")
        raise typer.Exit(1)

    # Parse priority
    try:
        parsed_priority = TicketPriority.from_string(priority)
    except ValueError:
        console.print(f"[red]Invalid priority: {priority}[/red]")
        valid = [p.value for p in TicketPriority]
        console.print(f"[dim]Valid priorities: {', '.join(valid)}[/dim]")
        raise typer.Exit(1)

    # Parse labels
    label_list = []
    if labels:
        label_list = [l.strip() for l in labels.split(",") if l.strip()]

    # Create ticket (set id="" to let store assign sequential ID)
    ticket = Ticket(
        id="",
        title=title,
        description=description or "",
        ticket_type=parsed_type,
        priority=parsed_priority,
        assigned_to=assigned_to,
        labels=label_list,
    )

    created = store.create(ticket)

    if json_output:
        console.print(json.dumps(_ticket_to_dict(created), indent=2, ensure_ascii=False))
        raise typer.Exit(0)

    ticket_id = created.ticket_number or created.id[:8]
    console.print(f"[green]Created ticket {ticket_id}[/green]")
    console.print(f"  Title: {created.title}")
    console.print(f"  Type: {_format_type(created.ticket_type)}")
    console.print(f"  Priority: {_format_priority(created.priority)}")
    console.print(f"  Status: {_format_status(created.status)}")
    if created.assigned_to:
        console.print(f"  Assigned to: {created.assigned_to}")
    if created.labels:
        console.print(f"  Labels: {', '.join(created.labels)}")


# =============================================================================
# SHOW COMMAND
# =============================================================================


@tickets_app.command("show")
def show_ticket(
    ticket_id: str = typer.Argument(
        ...,
        help="Ticket ID to show",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output as JSON",
    ),
    path: Path | None = typer.Option(
        None,
        "--path",
        help="Path to ticket storage file",
    ),
):
    """
    Show detailed information about a ticket.

    Displays all ticket fields including description, requirements,
    history, and comments.
    """
    store = _get_store(path)

    ticket = store.get(ticket_id)
    if not ticket:
        console.print(f"[red]Ticket not found: {ticket_id}[/red]")
        raise typer.Exit(1)

    if json_output:
        console.print(json.dumps(ticket.to_dict(), indent=2, default=str, ensure_ascii=False))
        raise typer.Exit(0)

    # Header panel
    ticket_id = ticket.ticket_number or ticket.id[:8]
    console.print(
        Panel.fit(
            f"[bold blue]{ticket_id}[/bold blue] {ticket.title}\n"
            f"[dim]{ticket.description or 'No description'}[/dim]",
            title="Ticket Details",
            border_style="blue",
        )
    )

    # Info table
    info_table = Table(
        box=box.ROUNDED,
        show_header=False,
    )
    info_table.add_column("Field", style="cyan")
    info_table.add_column("Value")

    info_table.add_row("Status", _format_status(ticket.status))
    info_table.add_row("Priority", _format_priority(ticket.priority))
    info_table.add_row("Type", _format_type(ticket.ticket_type))
    info_table.add_row("Assigned To", ticket.assigned_to or "[dim]Unassigned[/dim]")
    info_table.add_row("Created By", ticket.created_by)
    info_table.add_row("Created At", ticket.created_at.strftime("%Y-%m-%d %H:%M"))
    info_table.add_row("Updated At", ticket.updated_at.strftime("%Y-%m-%d %H:%M"))

    if ticket.started_at:
        info_table.add_row("Started At", ticket.started_at.strftime("%Y-%m-%d %H:%M"))
    if ticket.completed_at:
        info_table.add_row("Completed At", ticket.completed_at.strftime("%Y-%m-%d %H:%M"))
    if ticket.due_date:
        info_table.add_row("Due Date", ticket.due_date.strftime("%Y-%m-%d"))

    if ticket.labels:
        info_table.add_row("Labels", ", ".join(ticket.labels))

    console.print(info_table)

    # Requirements
    if ticket.requirements:
        console.print("\n[bold]Requirements:[/bold]")
        for i, req in enumerate(ticket.requirements, 1):
            console.print(f"  {i}. {req}")

    # Files to modify
    if ticket.files_to_modify:
        console.print("\n[bold]Files to Modify:[/bold]")
        for f in ticket.files_to_modify:
            console.print(f"  - {f}")

    # Work summary
    if ticket.problem_summary or ticket.solution_summary:
        console.print("\n[bold]Work Summary:[/bold]")
        if ticket.problem_summary:
            console.print(f"  Problem: {ticket.problem_summary}")
        if ticket.solution_summary:
            console.print(f"  Solution: {ticket.solution_summary}")
        if ticket.testing_notes:
            console.print(f"  Testing: {ticket.testing_notes}")

    # Files modified
    if ticket.files_modified:
        console.print("\n[bold]Files Modified:[/bold]")
        for f in ticket.files_modified:
            console.print(f"  - {f}")

    # Notes
    if ticket.notes:
        console.print("\n[bold]Notes:[/bold]")
        console.print(f"  {ticket.notes}")

    # Resolution
    if ticket.resolution:
        console.print("\n[bold]Resolution:[/bold]")
        console.print(f"  {ticket.resolution}")

    # History
    if ticket.history:
        console.print("\n[bold]History:[/bold]")
        for entry in ticket.history[-5:]:  # Show last 5 entries
            timestamp = entry.timestamp.strftime("%Y-%m-%d %H:%M")
            console.print(f"  [{timestamp}] {entry.actor}: {entry.message or entry.action}")

    # Comments
    if ticket.comments:
        console.print("\n[bold]Comments:[/bold]")
        for comment in ticket.comments[-3:]:  # Show last 3 comments
            timestamp = comment.created_at.strftime("%Y-%m-%d %H:%M")
            console.print(f"  [{timestamp}] {comment.author}:")
            console.print(
                f"    {comment.content[:100]}{'...' if len(comment.content) > 100 else ''}"
            )


# =============================================================================
# CLAIM COMMAND
# =============================================================================


@tickets_app.command("claim")
def claim_ticket(
    ticket_id: str = typer.Argument(
        ...,
        help="Ticket ID to claim",
    ),
    agent: str = typer.Option(
        ...,
        "--agent",
        "-a",
        help="Agent name claiming the ticket",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output as JSON",
    ),
    path: Path | None = typer.Option(
        None,
        "--path",
        help="Path to ticket storage file",
    ),
):
    """
    Claim a ticket for work.

    Sets the ticket status to IN_PROGRESS and assigns it to the specified agent.
    Only tickets in OPEN or BLOCKED status can be claimed.
    """
    store = _get_store(path)

    ticket = store.get(ticket_id)
    if not ticket:
        console.print(f"[red]Ticket not found: {ticket_id}[/red]")
        raise typer.Exit(1)

    # Check if ticket can be claimed
    if ticket.status not in [TicketStatus.OPEN, TicketStatus.BLOCKED]:
        console.print(f"[red]Cannot claim ticket with status: {ticket.status.display_name}[/red]")
        console.print("[dim]Only OPEN or BLOCKED tickets can be claimed[/dim]")
        raise typer.Exit(1)

    # Claim the ticket
    success = ticket.claim(agent)
    if not success:
        console.print(f"[red]Failed to claim ticket #{ticket_id}[/red]")
        raise typer.Exit(1)

    # Save
    store.update(ticket)

    display_id = ticket.ticket_number or ticket.id[:8]
    if json_output:
        console.print(
            json.dumps(
                {
                    "success": True,
                    "ticket_id": ticket.id,
                    "ticket_number": ticket.ticket_number,
                    "agent": agent,
                    "status": ticket.status.value,
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        raise typer.Exit(0)

    console.print(f"[green]Claimed ticket {display_id}[/green]")
    console.print(f"  Title: {ticket.title}")
    console.print(f"  Assigned to: {agent}")
    console.print(f"  Status: {_format_status(ticket.status)}")
    console.print(
        f"  Started at: {ticket.started_at.strftime('%Y-%m-%d %H:%M') if ticket.started_at else 'N/A'}"
    )


# =============================================================================
# COMPLETE COMMAND
# =============================================================================


@tickets_app.command("complete")
def complete_ticket(
    ticket_id: str = typer.Argument(
        ...,
        help="Ticket ID to complete",
    ),
    problem: str = typer.Option(
        ...,
        "--problem",
        "-p",
        help="Summary of the problem that was fixed",
    ),
    solution: str = typer.Option(
        ...,
        "--solution",
        "-s",
        help="Summary of the solution implemented",
    ),
    files: str | None = typer.Option(
        None,
        "--files",
        "-f",
        help="Comma-separated list of files modified",
    ),
    testing: str | None = typer.Option(
        None,
        "--testing",
        "-t",
        help="Testing notes",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output as JSON",
    ),
    path: Path | None = typer.Option(
        None,
        "--path",
        help="Path to ticket storage file",
    ),
):
    """
    Complete a ticket and submit for review.

    Moves the ticket from IN_PROGRESS to UNDER_REVIEW status.
    Requires problem summary, solution summary, and optionally files modified.
    """
    store = _get_store(path)

    ticket = store.get(ticket_id)
    if not ticket:
        console.print(f"[red]Ticket not found: {ticket_id}[/red]")
        raise typer.Exit(1)

    # Check if ticket is in progress
    if ticket.status != TicketStatus.IN_PROGRESS:
        console.print(
            f"[red]Cannot complete ticket with status: {ticket.status.display_name}[/red]"
        )
        console.print("[dim]Only IN_PROGRESS tickets can be completed[/dim]")
        raise typer.Exit(1)

    # Parse files
    file_list = []
    if files:
        file_list = [f.strip() for f in files.split(",") if f.strip()]

    # Complete the ticket
    actor = ticket.assigned_to or "system"
    success = ticket.complete(
        problem_summary=problem,
        solution_summary=solution,
        files_modified=file_list,
        testing_notes=testing or "",
        actor=actor,
        actor_type="ai",
    )

    if not success:
        console.print(f"[red]Failed to complete ticket #{ticket_id}[/red]")
        raise typer.Exit(1)

    # Save
    store.update(ticket)

    display_id = ticket.ticket_number or ticket.id[:8]
    if json_output:
        console.print(
            json.dumps(
                {
                    "success": True,
                    "ticket_id": ticket.id,
                    "ticket_number": ticket.ticket_number,
                    "status": ticket.status.value,
                    "problem_summary": problem,
                    "solution_summary": solution,
                    "files_modified": file_list,
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        raise typer.Exit(0)

    console.print(f"[green]Completed ticket {display_id}[/green]")
    console.print(f"  Status: {_format_status(ticket.status)}")
    console.print(f"  Problem: {problem}")
    console.print(f"  Solution: {solution}")
    if file_list:
        console.print(f"  Files modified: {', '.join(file_list)}")
    console.print("\n[dim]Ticket is now awaiting code review[/dim]")


# =============================================================================
# SEARCH COMMAND
# =============================================================================


@tickets_app.command("search")
def search_tickets(
    query: str = typer.Argument(
        ...,
        help="Search query",
    ),
    fields: str | None = typer.Option(
        None,
        "--fields",
        "-f",
        help="Comma-separated list of fields to search (title, description, requirements, notes)",
    ),
    limit: int = typer.Option(
        20,
        "--limit",
        "-l",
        help="Maximum number of results",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output as JSON",
    ),
    path: Path | None = typer.Option(
        None,
        "--path",
        help="Path to ticket storage file",
    ),
):
    """
    Search tickets by text query.

    Searches across title, description, requirements, and notes by default.
    Use --fields to limit which fields are searched.
    """
    store = _get_store(path)

    # Parse fields
    field_list = None
    if fields:
        field_list = [f.strip() for f in fields.split(",") if f.strip()]

    # Search
    results = store.search(query, fields=field_list)
    results = results[:limit]

    if not results:
        if json_output:
            console.print("[]")
        else:
            console.print(f"[yellow]No tickets found matching: {query}[/yellow]")
        raise typer.Exit(0)

    if json_output:
        output = [_ticket_to_dict(t) for t in results]
        console.print(json.dumps(output, indent=2, ensure_ascii=False))
        raise typer.Exit(0)

    # Create table
    table = Table(
        title=f"Search Results for '{query}'",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("ID", style="bold cyan", width=10)
    table.add_column("Title", max_width=40)
    table.add_column("Status")
    table.add_column("Priority")
    table.add_column("Type")

    for ticket in results:
        ticket_id = ticket.ticket_number or ticket.id[:8]
        table.add_row(
            ticket_id,
            ticket.title[:40] + "..." if len(ticket.title) > 40 else ticket.title,
            _format_status(ticket.status),
            _format_priority(ticket.priority),
            _format_type(ticket.ticket_type),
        )

    console.print(table)
    console.print(f"\n[dim]Found {len(results)} ticket(s)[/dim]")


# =============================================================================
# UPDATE COMMAND
# =============================================================================


@tickets_app.command("update")
def update_ticket(
    ticket_id: str = typer.Argument(
        ...,
        help="Ticket ID to update",
    ),
    title: str | None = typer.Option(
        None,
        "--title",
        "-t",
        help="New title",
    ),
    description: str | None = typer.Option(
        None,
        "--description",
        "-d",
        help="New description",
    ),
    priority: str | None = typer.Option(
        None,
        "--priority",
        "-p",
        help="New priority (critical, high, medium, low)",
    ),
    status: str | None = typer.Option(
        None,
        "--status",
        "-s",
        help="New status (only valid transitions allowed)",
    ),
    assigned_to: str | None = typer.Option(
        None,
        "--assigned-to",
        "-a",
        help="Assign to agent (use empty string to unassign)",
    ),
    labels: str | None = typer.Option(
        None,
        "--labels",
        "-l",
        help="New labels (comma-separated, replaces existing)",
    ),
    notes: str | None = typer.Option(
        None,
        "--notes",
        "-n",
        help="Add notes (appends to existing)",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output as JSON",
    ),
    path: Path | None = typer.Option(
        None,
        "--path",
        help="Path to ticket storage file",
    ),
):
    """
    Update ticket fields.

    Allows updating title, description, priority, status, assignment,
    labels, and notes. Status changes must follow valid transitions.
    """
    store = _get_store(path)

    ticket = store.get(ticket_id)
    if not ticket:
        console.print(f"[red]Ticket not found: {ticket_id}[/red]")
        raise typer.Exit(1)

    changes = []

    # Update title
    if title is not None:
        old_title = ticket.title
        ticket.title = title
        ticket.add_history(
            action="field_updated",
            actor="cli",
            actor_type="system",
            field_changed="title",
            old_value=old_title,
            new_value=title,
        )
        changes.append(f"title: {title}")

    # Update description
    if description is not None:
        ticket.description = description
        changes.append("description: updated")

    # Update priority
    if priority is not None:
        try:
            new_priority = TicketPriority.from_string(priority)
            old_priority = ticket.priority
            ticket.priority = new_priority
            ticket.add_history(
                action="priority_changed",
                actor="cli",
                actor_type="system",
                field_changed="priority",
                old_value=old_priority.value,
                new_value=new_priority.value,
            )
            changes.append(f"priority: {new_priority.value}")
        except ValueError:
            console.print(f"[red]Invalid priority: {priority}[/red]")
            valid = [p.value for p in TicketPriority]
            console.print(f"[dim]Valid priorities: {', '.join(valid)}[/dim]")
            raise typer.Exit(1)

    # Update status
    if status is not None:
        try:
            new_status = TicketStatus.from_string(status)
            if not ticket.status.can_transition_to(new_status):
                console.print(
                    f"[red]Invalid status transition: {ticket.status.value} -> {new_status.value}[/red]"
                )
                raise typer.Exit(1)
            success = ticket.transition_status(new_status, actor="cli", actor_type="system")
            if success:
                changes.append(f"status: {new_status.value}")
            else:
                console.print("[red]Failed to transition status[/red]")
                raise typer.Exit(1)
        except ValueError:
            console.print(f"[red]Invalid status: {status}[/red]")
            valid = [s.value for s in TicketStatus]
            console.print(f"[dim]Valid statuses: {', '.join(valid)}[/dim]")
            raise typer.Exit(1)

    # Update assigned_to
    if assigned_to is not None:
        if assigned_to == "":
            ticket.assigned_to = None
            changes.append("unassigned")
        else:
            ticket.assign(assigned_to, actor="cli", actor_type="system")
            changes.append(f"assigned_to: {assigned_to}")

    # Update labels
    if labels is not None:
        label_list = [l.strip() for l in labels.split(",") if l.strip()]
        ticket.labels = label_list
        changes.append(f"labels: {', '.join(label_list) if label_list else 'cleared'}")

    # Add notes
    if notes is not None:
        if ticket.notes:
            ticket.notes = f"{ticket.notes}\n\n{notes}"
        else:
            ticket.notes = notes
        changes.append("notes: appended")

    if not changes:
        console.print("[yellow]No changes specified[/yellow]")
        raise typer.Exit(0)

    # Save
    store.update(ticket)

    display_id = ticket.ticket_number or ticket.id[:8]
    if json_output:
        console.print(
            json.dumps(
                {
                    "success": True,
                    "ticket_id": ticket.id,
                    "ticket_number": ticket.ticket_number,
                    "changes": changes,
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        raise typer.Exit(0)

    console.print(f"[green]Updated ticket {display_id}[/green]")
    for change in changes:
        console.print(f"  - {change}")


# =============================================================================
# WEB COMMAND
# =============================================================================


@tickets_app.command("web")
def start_web(
    host: str = typer.Option(
        "127.0.0.1",
        "--host",
        "-h",
        help="Host address to bind to",
    ),
    port: int = typer.Option(
        5000,
        "--port",
        "-p",
        help="Port number to listen on",
    ),
    debug: bool = typer.Option(
        False,
        "--debug",
        "-d",
        help="Enable debug mode with auto-reload",
    ),
    open_browser: bool = typer.Option(
        True,
        "--open/--no-open",
        help="Open browser automatically",
    ),
    path: Path | None = typer.Option(
        None,
        "--path",
        help="Path to ticket storage file",
    ),
):
    """
    Start the ticket web dashboard.

    Launches a web interface for viewing and managing tickets with:
    - Dashboard with statistics and overview
    - Ticket listing with filters
    - Ticket detail views
    - JSON API endpoints
    - Dark/light mode toggle
    """
    import webbrowser

    from fastband.tickets.web.app import serve as serve_web

    store = _get_store(path)

    url = f"http://{host}:{port}"
    console.print(
        Panel.fit(
            f"[bold blue]Ticket Web Dashboard[/bold blue]\n[dim]Starting at {url}[/dim]",
            border_style="blue",
        )
    )

    console.print(
        f"[green]✓[/green] Serving tickets from: {store.path if hasattr(store, 'path') else 'default store'}"
    )
    console.print(f"[green]✓[/green] Debug mode: {'enabled' if debug else 'disabled'}")
    console.print("\n[dim]Press Ctrl+C to stop the server[/dim]\n")

    # Open browser if requested
    if open_browser:
        # Delay browser open slightly to let server start
        import threading

        def open_delayed():
            import time

            time.sleep(1)
            webbrowser.open(url)

        threading.Thread(target=open_delayed, daemon=True).start()

    # Start the server
    try:
        serve_web(store=store, host=host, port=port, debug=debug)
    except KeyboardInterrupt:
        console.print("\n[yellow]Server stopped[/yellow]")

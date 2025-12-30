"""
MCP Ticket Tools for AI Agents.

Provides comprehensive ticket management tools for AI agents working
on development tasks. Implements agent enforcement and status workflow.

Tools:
- list_tickets: List tickets with filters
- get_ticket_details: Get full ticket details
- create_ticket: Create a new ticket
- claim_ticket: Claim a ticket for work (AI agents only)
- complete_ticket_safely: Complete work with screenshots
- update_ticket: Update ticket fields
- search_tickets: Search tickets by query
- add_ticket_comment: Add a comment to a ticket
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastband.backup import trigger_backup_hook
from fastband.tickets.models import (
    Agent,
    Ticket,
    TicketComment,
    TicketPriority,
    TicketStatus,
    TicketType,
)
from fastband.tickets.storage import TicketStore, get_store
from fastband.tools.base import (
    Tool,
    ToolCategory,
    ToolDefinition,
    ToolMetadata,
    ToolParameter,
    ToolResult,
)

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def _ticket_to_summary(ticket: Ticket) -> dict[str, Any]:
    """Convert ticket to summary dict for listing."""
    return {
        "id": ticket.id,
        "title": ticket.title,
        "status": ticket.status.display_name,
        "priority": ticket.priority.display_name,
        "ticket_type": ticket.ticket_type.display_name,
        "assigned_to": ticket.assigned_to,
        "created_at": ticket.created_at.isoformat(),
        "updated_at": ticket.updated_at.isoformat(),
        "labels": ticket.labels,
    }


def _ticket_to_full_dict(ticket: Ticket) -> dict[str, Any]:
    """Convert ticket to full dict with all details."""
    data = ticket.to_dict()
    # Add display names for enums
    data["status_display"] = ticket.status.display_name
    data["priority_display"] = ticket.priority.display_name
    data["ticket_type_display"] = ticket.ticket_type.display_name
    return data


def _validate_agent_name(agent_name: str) -> tuple[bool, str | None]:
    """Validate agent name format."""
    if not agent_name:
        return False, "Agent name is required"
    if not agent_name.strip():
        return False, "Agent name cannot be empty"
    # Allow common formats: MCP_Agent1, claude-agent, AI_Agent_1
    if len(agent_name) > 50:
        return False, "Agent name too long (max 50 characters)"
    return True, None


def _get_or_create_agent(store: TicketStore, agent_name: str, agent_type: str = "ai") -> Agent:
    """Get or create an agent by name."""
    agent = store.get_agent(agent_name)
    if not agent:
        agent = Agent(
            name=agent_name,
            agent_type=agent_type,
        )
        store.save_agent(agent)
    return agent


# =============================================================================
# LIST TICKETS TOOL
# =============================================================================


class ListTicketsTool(Tool):
    """
    List tickets with optional filters.

    Returns a paginated list of tickets matching the filter criteria.
    Useful for finding available work or checking ticket status.
    """

    def __init__(self, store: TicketStore | None = None):
        self._store = store

    @property
    def store(self) -> TicketStore:
        """Get ticket store (lazy load if not provided)."""
        if self._store is None:
            self._store = get_store()
        return self._store

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            metadata=ToolMetadata(
                name="list_tickets",
                description="List tickets with optional filters. Use to find available work or check status.",
                category=ToolCategory.TICKETS,
                version="1.0.0",
            ),
            parameters=[
                ToolParameter(
                    name="status",
                    type="string",
                    description="Filter by status: open, in_progress, under_review, awaiting_approval, resolved, closed, blocked",
                    required=False,
                    enum=[
                        "open",
                        "in_progress",
                        "under_review",
                        "awaiting_approval",
                        "resolved",
                        "closed",
                        "blocked",
                    ],
                ),
                ToolParameter(
                    name="priority",
                    type="string",
                    description="Filter by priority: critical, high, medium, low",
                    required=False,
                    enum=["critical", "high", "medium", "low"],
                ),
                ToolParameter(
                    name="ticket_type",
                    type="string",
                    description="Filter by type: bug, feature, enhancement, task, documentation, maintenance, security, performance",
                    required=False,
                    enum=[
                        "bug",
                        "feature",
                        "enhancement",
                        "task",
                        "documentation",
                        "maintenance",
                        "security",
                        "performance",
                    ],
                ),
                ToolParameter(
                    name="assigned_to",
                    type="string",
                    description="Filter by assigned agent name",
                    required=False,
                ),
                ToolParameter(
                    name="limit",
                    type="integer",
                    description="Maximum number of tickets to return (default: 50)",
                    required=False,
                    default=50,
                ),
                ToolParameter(
                    name="offset",
                    type="integer",
                    description="Number of tickets to skip for pagination (default: 0)",
                    required=False,
                    default=0,
                ),
            ],
        )

    async def execute(
        self,
        status: str | None = None,
        priority: str | None = None,
        ticket_type: str | None = None,
        assigned_to: str | None = None,
        limit: int = 50,
        offset: int = 0,
        **kwargs,
    ) -> ToolResult:
        """List tickets with filters."""
        try:
            # Convert string filters to enums
            status_enum = TicketStatus.from_string(status) if status else None
            priority_enum = TicketPriority.from_string(priority) if priority else None
            type_enum = TicketType.from_string(ticket_type) if ticket_type else None

            # Get tickets from store
            tickets = self.store.list(
                status=status_enum,
                priority=priority_enum,
                ticket_type=type_enum,
                assigned_to=assigned_to,
                limit=limit,
                offset=offset,
            )

            # Get total count for pagination info
            total_count = self.store.count(
                status=status_enum,
                priority=priority_enum,
            )

            return ToolResult(
                success=True,
                data={
                    "tickets": [_ticket_to_summary(t) for t in tickets],
                    "count": len(tickets),
                    "total": total_count,
                    "limit": limit,
                    "offset": offset,
                    "has_more": offset + len(tickets) < total_count,
                },
            )

        except ValueError as e:
            return ToolResult(success=False, error=f"Invalid filter value: {e}")
        except Exception as e:
            return ToolResult(success=False, error=f"Failed to list tickets: {e}")


# =============================================================================
# GET TICKET DETAILS TOOL
# =============================================================================


class GetTicketDetailsTool(Tool):
    """
    Get full details for a specific ticket.

    Returns complete ticket information including history and comments.
    """

    def __init__(self, store: TicketStore | None = None):
        self._store = store

    @property
    def store(self) -> TicketStore:
        if self._store is None:
            self._store = get_store()
        return self._store

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            metadata=ToolMetadata(
                name="get_ticket_details",
                description="Get full details for a specific ticket including history and comments.",
                category=ToolCategory.TICKETS,
                version="1.0.0",
            ),
            parameters=[
                ToolParameter(
                    name="ticket_id",
                    type="string",
                    description="The ticket ID to retrieve",
                    required=True,
                ),
            ],
        )

    async def execute(
        self,
        ticket_id: str,
        **kwargs,
    ) -> ToolResult:
        """Get ticket details."""
        try:
            ticket = self.store.get(ticket_id)
            if not ticket:
                return ToolResult(
                    success=False,
                    error=f"Ticket not found: {ticket_id}",
                )

            return ToolResult(
                success=True,
                data={
                    "ticket": _ticket_to_full_dict(ticket),
                },
            )

        except Exception as e:
            return ToolResult(success=False, error=f"Failed to get ticket: {e}")


# =============================================================================
# CREATE TICKET TOOL
# =============================================================================


class CreateTicketTool(Tool):
    """
    Create a new ticket.

    Creates a ticket with the specified details. The ticket starts
    in OPEN status and is assigned an auto-generated ID.
    """

    def __init__(self, store: TicketStore | None = None):
        self._store = store

    @property
    def store(self) -> TicketStore:
        if self._store is None:
            self._store = get_store()
        return self._store

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            metadata=ToolMetadata(
                name="create_ticket",
                description="Create a new ticket. Returns the created ticket with its assigned ID.",
                category=ToolCategory.TICKETS,
                version="1.0.0",
            ),
            parameters=[
                ToolParameter(
                    name="title",
                    type="string",
                    description="Ticket title (required)",
                    required=True,
                ),
                ToolParameter(
                    name="description",
                    type="string",
                    description="Detailed description of the task or issue",
                    required=True,
                ),
                ToolParameter(
                    name="ticket_type",
                    type="string",
                    description="Ticket type (default: task)",
                    required=False,
                    default="task",
                    enum=[
                        "bug",
                        "feature",
                        "enhancement",
                        "task",
                        "documentation",
                        "maintenance",
                        "security",
                        "performance",
                    ],
                ),
                ToolParameter(
                    name="priority",
                    type="string",
                    description="Priority level (default: medium)",
                    required=False,
                    default="medium",
                    enum=["critical", "high", "medium", "low"],
                ),
                ToolParameter(
                    name="requirements",
                    type="array",
                    description="List of specific requirements or acceptance criteria",
                    required=False,
                ),
                ToolParameter(
                    name="files_to_modify",
                    type="array",
                    description="List of files expected to be modified",
                    required=False,
                ),
                ToolParameter(
                    name="labels",
                    type="array",
                    description="Labels for categorization",
                    required=False,
                ),
                ToolParameter(
                    name="app",
                    type="string",
                    description="Application this ticket belongs to",
                    required=False,
                ),
                ToolParameter(
                    name="created_by",
                    type="string",
                    description="Creator name (default: system)",
                    required=False,
                    default="system",
                ),
            ],
        )

    async def execute(
        self,
        title: str,
        description: str,
        ticket_type: str = "task",
        priority: str = "medium",
        requirements: list[str] | None = None,
        files_to_modify: list[str] | None = None,
        labels: list[str] | None = None,
        app: str | None = None,
        created_by: str = "system",
        **kwargs,
    ) -> ToolResult:
        """Create a new ticket."""
        try:
            # Validate inputs
            if not title.strip():
                return ToolResult(success=False, error="Title is required")
            if not description.strip():
                return ToolResult(success=False, error="Description is required")

            # Parse enums
            ticket_type_enum = TicketType.from_string(ticket_type)
            priority_enum = TicketPriority.from_string(priority)

            # Create ticket
            ticket = Ticket(
                title=title.strip(),
                description=description.strip(),
                ticket_type=ticket_type_enum,
                priority=priority_enum,
                status=TicketStatus.OPEN,
                requirements=requirements or [],
                files_to_modify=files_to_modify or [],
                labels=labels or [],
                app=app,
                created_by=created_by,
            )

            # Add creation history
            ticket.add_history(
                action="created",
                actor=created_by,
                actor_type="system" if created_by == "system" else "human",
                message="Ticket created",
            )

            # Save to store
            created_ticket = self.store.create(ticket)

            return ToolResult(
                success=True,
                data={
                    "ticket_id": created_ticket.id,
                    "ticket": _ticket_to_summary(created_ticket),
                    "message": f"Ticket {created_ticket.id} created successfully",
                },
            )

        except ValueError as e:
            return ToolResult(success=False, error=f"Invalid value: {e}")
        except Exception as e:
            return ToolResult(success=False, error=f"Failed to create ticket: {e}")


# =============================================================================
# CLAIM TICKET TOOL
# =============================================================================


class ClaimTicketTool(Tool):
    """
    Claim a ticket to start working on it.

    This tool is ONLY for AI agents. It:
    - Validates the agent name
    - Checks the ticket can be claimed (OPEN or BLOCKED status)
    - Assigns the ticket to the agent
    - Changes status to IN_PROGRESS
    - Records the action in history
    """

    def __init__(self, store: TicketStore | None = None):
        self._store = store

    @property
    def store(self) -> TicketStore:
        if self._store is None:
            self._store = get_store()
        return self._store

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            metadata=ToolMetadata(
                name="claim_ticket",
                description="Claim a ticket to start working on it. Sets status to IN_PROGRESS. AI agents only.",
                category=ToolCategory.TICKETS,
                version="1.0.0",
            ),
            parameters=[
                ToolParameter(
                    name="ticket_id",
                    type="string",
                    description="The ticket ID to claim",
                    required=True,
                ),
                ToolParameter(
                    name="agent_name",
                    type="string",
                    description="Your agent identifier (e.g., 'MCP_Agent1')",
                    required=True,
                ),
            ],
        )

    async def execute(
        self,
        ticket_id: str,
        agent_name: str,
        **kwargs,
    ) -> ToolResult:
        """Claim a ticket for work."""
        try:
            # Validate agent name
            is_valid, error = _validate_agent_name(agent_name)
            if not is_valid:
                return ToolResult(success=False, error=error)

            # Get ticket
            ticket = self.store.get(ticket_id)
            if not ticket:
                return ToolResult(
                    success=False,
                    error=f"Ticket not found: {ticket_id}",
                )

            # Check if ticket can be claimed
            if ticket.status not in [TicketStatus.OPEN, TicketStatus.BLOCKED]:
                return ToolResult(
                    success=False,
                    error=f"Cannot claim ticket in {ticket.status.display_name} status. "
                    f"Only OPEN or BLOCKED tickets can be claimed.",
                )

            # Check if already assigned to someone else
            if ticket.assigned_to and ticket.assigned_to != agent_name:
                return ToolResult(
                    success=False,
                    error=f"Ticket is already assigned to {ticket.assigned_to}",
                )

            # Get or create agent record
            agent = _get_or_create_agent(self.store, agent_name, "ai")
            agent.tickets_in_progress += 1
            self.store.save_agent(agent)

            # Claim the ticket
            if not ticket.claim(agent_name):
                return ToolResult(
                    success=False,
                    error="Failed to claim ticket (status transition failed)",
                )

            # Save changes
            self.store.update(ticket)

            return ToolResult(
                success=True,
                data={
                    "ticket_id": ticket.id,
                    "ticket": _ticket_to_summary(ticket),
                    "message": f"Ticket {ticket.id} claimed by {agent_name}",
                    "next_steps": [
                        "Take a BEFORE screenshot showing the current state",
                        "Make your changes to fix/implement the ticket",
                        "Take an AFTER screenshot showing the result",
                        "Use complete_ticket_safely to submit for review",
                    ],
                },
            )

        except Exception as e:
            return ToolResult(success=False, error=f"Failed to claim ticket: {e}")


# =============================================================================
# COMPLETE TICKET SAFELY TOOL
# =============================================================================


class CompleteTicketSafelyTool(Tool):
    """
    Complete ticket work and submit for review.

    This tool:
    - Requires before and after screenshots
    - Records problem summary, solution summary, and testing notes
    - Moves ticket to UNDER_REVIEW status
    - Does NOT resolve the ticket (requires human approval)
    """

    def __init__(self, store: TicketStore | None = None):
        self._store = store

    @property
    def store(self) -> TicketStore:
        if self._store is None:
            self._store = get_store()
        return self._store

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            metadata=ToolMetadata(
                name="complete_ticket_safely",
                description="Complete ticket work with screenshots and submit for review. Requires before/after screenshots.",
                category=ToolCategory.TICKETS,
                version="1.0.0",
            ),
            parameters=[
                ToolParameter(
                    name="ticket_id",
                    type="string",
                    description="The ticket ID to complete",
                    required=True,
                ),
                ToolParameter(
                    name="agent_name",
                    type="string",
                    description="Your agent identifier",
                    required=True,
                ),
                ToolParameter(
                    name="problem_summary",
                    type="string",
                    description="Summary of the problem that was addressed",
                    required=True,
                ),
                ToolParameter(
                    name="solution_summary",
                    type="string",
                    description="Summary of the solution implemented",
                    required=True,
                ),
                ToolParameter(
                    name="files_modified",
                    type="array",
                    description="List of files that were modified",
                    required=True,
                ),
                ToolParameter(
                    name="before_screenshot",
                    type="string",
                    description="Path to the before screenshot",
                    required=True,
                ),
                ToolParameter(
                    name="after_screenshot",
                    type="string",
                    description="Path to the after screenshot",
                    required=True,
                ),
                ToolParameter(
                    name="testing_notes",
                    type="string",
                    description="Notes about testing performed",
                    required=False,
                    default="",
                ),
            ],
        )

    async def execute(
        self,
        ticket_id: str,
        agent_name: str,
        problem_summary: str,
        solution_summary: str,
        files_modified: list[str],
        before_screenshot: str,
        after_screenshot: str,
        testing_notes: str = "",
        **kwargs,
    ) -> ToolResult:
        """Complete ticket work safely."""
        try:
            # Validate agent name
            is_valid, error = _validate_agent_name(agent_name)
            if not is_valid:
                return ToolResult(success=False, error=error)

            # Validate screenshots
            if not before_screenshot or not before_screenshot.strip():
                return ToolResult(
                    success=False,
                    error="Before screenshot is required",
                )
            if not after_screenshot or not after_screenshot.strip():
                return ToolResult(
                    success=False,
                    error="After screenshot is required",
                )

            # Validate summaries
            if not problem_summary or not problem_summary.strip():
                return ToolResult(
                    success=False,
                    error="Problem summary is required",
                )
            if not solution_summary or not solution_summary.strip():
                return ToolResult(
                    success=False,
                    error="Solution summary is required",
                )

            # Get ticket
            ticket = self.store.get(ticket_id)
            if not ticket:
                return ToolResult(
                    success=False,
                    error=f"Ticket not found: {ticket_id}",
                )

            # Check ticket is in progress
            if ticket.status != TicketStatus.IN_PROGRESS:
                return ToolResult(
                    success=False,
                    error=f"Cannot complete ticket in {ticket.status.display_name} status. "
                    f"Ticket must be IN_PROGRESS.",
                )

            # Check agent is assigned
            if ticket.assigned_to != agent_name:
                return ToolResult(
                    success=False,
                    error=f"Ticket is assigned to {ticket.assigned_to}, not {agent_name}. "
                    f"Only the assigned agent can complete a ticket.",
                )

            # Complete the ticket
            success = ticket.complete(
                problem_summary=problem_summary.strip(),
                solution_summary=solution_summary.strip(),
                files_modified=files_modified,
                testing_notes=testing_notes.strip() if testing_notes else "",
                before_screenshot=before_screenshot.strip(),
                after_screenshot=after_screenshot.strip(),
                actor=agent_name,
                actor_type="ai",
            )

            if not success:
                return ToolResult(
                    success=False,
                    error="Failed to complete ticket (status transition failed)",
                )

            # Update agent stats
            agent = self.store.get_agent(agent_name)
            if agent:
                agent.tickets_in_progress = max(0, agent.tickets_in_progress - 1)
                self.store.save_agent(agent)

            # Save changes
            self.store.update(ticket)

            # Trigger backup hook after ticket completion
            backup_info = None
            try:
                backup_info = trigger_backup_hook(
                    "after_ticket_completion",
                    ticket_id=ticket.id,
                )
            except Exception:
                pass  # Don't fail ticket completion if backup fails

            result_data = {
                "ticket_id": ticket.id,
                "ticket": _ticket_to_summary(ticket),
                "message": f"Ticket {ticket.id} submitted for review",
                "status": ticket.status.display_name,
                "next_steps": [
                    "Ticket is now under code review",
                    "Wait for review feedback",
                    "If changes requested, update and resubmit",
                ],
            }

            if backup_info:
                result_data["backup_created"] = backup_info.id

            return ToolResult(success=True, data=result_data)

        except Exception as e:
            return ToolResult(success=False, error=f"Failed to complete ticket: {e}")


# =============================================================================
# UPDATE TICKET TOOL
# =============================================================================


class UpdateTicketTool(Tool):
    """
    Update ticket fields.

    Allows updating various ticket fields with proper validation
    and history tracking.
    """

    def __init__(self, store: TicketStore | None = None):
        self._store = store

    @property
    def store(self) -> TicketStore:
        if self._store is None:
            self._store = get_store()
        return self._store

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            metadata=ToolMetadata(
                name="update_ticket",
                description="Update ticket fields. All fields are optional except ticket_id.",
                category=ToolCategory.TICKETS,
                version="1.0.0",
            ),
            parameters=[
                ToolParameter(
                    name="ticket_id",
                    type="string",
                    description="The ticket ID to update",
                    required=True,
                ),
                ToolParameter(
                    name="agent_name",
                    type="string",
                    description="Your agent identifier (for tracking who made changes)",
                    required=True,
                ),
                ToolParameter(
                    name="priority",
                    type="string",
                    description="New priority level",
                    required=False,
                    enum=["critical", "high", "medium", "low"],
                ),
                ToolParameter(
                    name="notes",
                    type="string",
                    description="Notes to append to the ticket",
                    required=False,
                ),
                ToolParameter(
                    name="labels",
                    type="array",
                    description="Labels to set on the ticket",
                    required=False,
                ),
                ToolParameter(
                    name="requirements",
                    type="array",
                    description="Requirements to set on the ticket",
                    required=False,
                ),
                ToolParameter(
                    name="files_to_modify",
                    type="array",
                    description="Files to modify list",
                    required=False,
                ),
            ],
        )

    async def execute(
        self,
        ticket_id: str,
        agent_name: str,
        priority: str | None = None,
        notes: str | None = None,
        labels: list[str] | None = None,
        requirements: list[str] | None = None,
        files_to_modify: list[str] | None = None,
        **kwargs,
    ) -> ToolResult:
        """Update ticket fields."""
        try:
            # Validate agent name
            is_valid, error = _validate_agent_name(agent_name)
            if not is_valid:
                return ToolResult(success=False, error=error)

            # Get ticket
            ticket = self.store.get(ticket_id)
            if not ticket:
                return ToolResult(
                    success=False,
                    error=f"Ticket not found: {ticket_id}",
                )

            changes_made = []

            # Update priority
            if priority:
                old_priority = ticket.priority.value
                ticket.priority = TicketPriority.from_string(priority)
                ticket.add_history(
                    action="field_updated",
                    actor=agent_name,
                    actor_type="ai",
                    field_changed="priority",
                    old_value=old_priority,
                    new_value=priority,
                    message=f"Priority changed from {old_priority} to {priority}",
                )
                changes_made.append(f"priority: {old_priority} -> {priority}")

            # Append notes
            if notes:
                ticket.notes = (
                    f"{ticket.notes}\n\n[{agent_name} - {datetime.now().isoformat()}]\n{notes}"
                    if ticket.notes
                    else notes
                )
                ticket.add_history(
                    action="notes_updated",
                    actor=agent_name,
                    actor_type="ai",
                    field_changed="notes",
                    message="Notes updated",
                )
                changes_made.append("notes updated")

            # Update labels
            if labels is not None:
                old_labels = ticket.labels
                ticket.labels = labels
                ticket.add_history(
                    action="field_updated",
                    actor=agent_name,
                    actor_type="ai",
                    field_changed="labels",
                    old_value=str(old_labels),
                    new_value=str(labels),
                    message="Labels updated",
                )
                changes_made.append("labels updated")

            # Update requirements
            if requirements is not None:
                old_requirements = ticket.requirements
                ticket.requirements = requirements
                ticket.add_history(
                    action="field_updated",
                    actor=agent_name,
                    actor_type="ai",
                    field_changed="requirements",
                    old_value=str(old_requirements),
                    new_value=str(requirements),
                    message="Requirements updated",
                )
                changes_made.append("requirements updated")

            # Update files_to_modify
            if files_to_modify is not None:
                old_files = ticket.files_to_modify
                ticket.files_to_modify = files_to_modify
                ticket.add_history(
                    action="field_updated",
                    actor=agent_name,
                    actor_type="ai",
                    field_changed="files_to_modify",
                    old_value=str(old_files),
                    new_value=str(files_to_modify),
                    message="Files to modify updated",
                )
                changes_made.append("files_to_modify updated")

            if not changes_made:
                return ToolResult(
                    success=True,
                    data={
                        "ticket_id": ticket.id,
                        "message": "No changes made",
                        "ticket": _ticket_to_summary(ticket),
                    },
                )

            # Save changes
            self.store.update(ticket)

            return ToolResult(
                success=True,
                data={
                    "ticket_id": ticket.id,
                    "changes": changes_made,
                    "message": f"Ticket {ticket.id} updated: {', '.join(changes_made)}",
                    "ticket": _ticket_to_summary(ticket),
                },
            )

        except ValueError as e:
            return ToolResult(success=False, error=f"Invalid value: {e}")
        except Exception as e:
            return ToolResult(success=False, error=f"Failed to update ticket: {e}")


# =============================================================================
# SEARCH TICKETS TOOL
# =============================================================================


class SearchTicketsTool(Tool):
    """
    Search tickets by text query.

    Searches across title, description, requirements, and notes fields.
    """

    def __init__(self, store: TicketStore | None = None):
        self._store = store

    @property
    def store(self) -> TicketStore:
        if self._store is None:
            self._store = get_store()
        return self._store

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            metadata=ToolMetadata(
                name="search_tickets",
                description="Search tickets by text query across title, description, and notes.",
                category=ToolCategory.TICKETS,
                version="1.0.0",
            ),
            parameters=[
                ToolParameter(
                    name="query",
                    type="string",
                    description="Search query text",
                    required=True,
                ),
                ToolParameter(
                    name="fields",
                    type="array",
                    description="Fields to search in (default: title, description, requirements, notes)",
                    required=False,
                ),
            ],
        )

    async def execute(
        self,
        query: str,
        fields: list[str] | None = None,
        **kwargs,
    ) -> ToolResult:
        """Search tickets by query."""
        try:
            if not query or not query.strip():
                return ToolResult(
                    success=False,
                    error="Search query is required",
                )

            tickets = self.store.search(query.strip(), fields=fields)

            return ToolResult(
                success=True,
                data={
                    "query": query,
                    "fields_searched": fields or ["title", "description", "requirements", "notes"],
                    "tickets": [_ticket_to_summary(t) for t in tickets],
                    "count": len(tickets),
                },
            )

        except Exception as e:
            return ToolResult(success=False, error=f"Failed to search tickets: {e}")


# =============================================================================
# ADD TICKET COMMENT TOOL
# =============================================================================


class AddTicketCommentTool(Tool):
    """
    Add a comment to a ticket.

    Supports regular comments, review feedback, and system messages.
    """

    def __init__(self, store: TicketStore | None = None):
        self._store = store

    @property
    def store(self) -> TicketStore:
        if self._store is None:
            self._store = get_store()
        return self._store

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            metadata=ToolMetadata(
                name="add_ticket_comment",
                description="Add a comment to a ticket. Use for questions, updates, or review feedback.",
                category=ToolCategory.TICKETS,
                version="1.0.0",
            ),
            parameters=[
                ToolParameter(
                    name="ticket_id",
                    type="string",
                    description="The ticket ID to comment on",
                    required=True,
                ),
                ToolParameter(
                    name="agent_name",
                    type="string",
                    description="Your agent identifier",
                    required=True,
                ),
                ToolParameter(
                    name="content",
                    type="string",
                    description="Comment content",
                    required=True,
                ),
                ToolParameter(
                    name="comment_type",
                    type="string",
                    description="Type of comment (default: comment)",
                    required=False,
                    default="comment",
                    enum=["comment", "review", "question", "update"],
                ),
            ],
        )

    async def execute(
        self,
        ticket_id: str,
        agent_name: str,
        content: str,
        comment_type: str = "comment",
        **kwargs,
    ) -> ToolResult:
        """Add a comment to a ticket."""
        try:
            # Validate agent name
            is_valid, error = _validate_agent_name(agent_name)
            if not is_valid:
                return ToolResult(success=False, error=error)

            # Validate content
            if not content or not content.strip():
                return ToolResult(
                    success=False,
                    error="Comment content is required",
                )

            # Get ticket
            ticket = self.store.get(ticket_id)
            if not ticket:
                return ToolResult(
                    success=False,
                    error=f"Ticket not found: {ticket_id}",
                )

            # Add comment
            comment = ticket.add_comment(
                content=content.strip(),
                author=agent_name,
                author_type="ai",
                comment_type=comment_type,
            )

            # Save changes
            self.store.update(ticket)

            return ToolResult(
                success=True,
                data={
                    "ticket_id": ticket.id,
                    "comment_id": comment.id,
                    "message": f"Comment added to ticket {ticket.id}",
                    "comment": comment.to_dict(),
                },
            )

        except Exception as e:
            return ToolResult(success=False, error=f"Failed to add comment: {e}")


# =============================================================================
# ALL TICKET TOOLS
# =============================================================================

TICKET_TOOLS = [
    ListTicketsTool,
    GetTicketDetailsTool,
    CreateTicketTool,
    ClaimTicketTool,
    CompleteTicketSafelyTool,
    UpdateTicketTool,
    SearchTicketsTool,
    AddTicketCommentTool,
]

__all__ = [
    # Tools
    "ListTicketsTool",
    "GetTicketDetailsTool",
    "CreateTicketTool",
    "ClaimTicketTool",
    "CompleteTicketSafelyTool",
    "UpdateTicketTool",
    "SearchTicketsTool",
    "AddTicketCommentTool",
    # Tool list
    "TICKET_TOOLS",
]

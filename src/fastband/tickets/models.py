"""
Ticket data models for the adaptive ticket manager.

Provides:
- Ticket: Main ticket dataclass with all fields
- TicketStatus: Status workflow enumeration
- TicketPriority: Priority levels
- TicketType: Ticket type classification
- Agent: Agent model for assignments
- TicketHistory: Change tracking
- TicketComment: Ticket comments/notes
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class TicketStatus(Enum):
    """
    Ticket status workflow.

    Status transitions:
    - OPEN -> IN_PROGRESS (when claimed)
    - IN_PROGRESS -> UNDER_REVIEW (when completed)
    - UNDER_REVIEW -> AWAITING_APPROVAL (when code review passes)
    - UNDER_REVIEW -> IN_PROGRESS (when code review requests changes)
    - AWAITING_APPROVAL -> RESOLVED (when human approves)
    - AWAITING_APPROVAL -> IN_PROGRESS (when human rejects)
    - RESOLVED -> CLOSED (manual close)
    - Any -> BLOCKED (when blocked by dependency)
    - BLOCKED -> previous status (when unblocked)
    """

    OPEN = "open"
    IN_PROGRESS = "in_progress"
    UNDER_REVIEW = "under_review"
    AWAITING_APPROVAL = "awaiting_approval"
    RESOLVED = "resolved"
    CLOSED = "closed"
    BLOCKED = "blocked"

    @classmethod
    def from_string(cls, value: str) -> "TicketStatus":
        """Convert string to TicketStatus, handling emoji prefixes."""
        # Remove emoji prefixes if present
        clean_value = value.strip()
        for prefix in ["🔴 ", "🟡 ", "🟢 ", "🔵 ", "⚫ ", "🔍 "]:
            if clean_value.startswith(prefix):
                clean_value = clean_value[len(prefix) :]
                break

        # Map common names to enum values
        name_map = {
            "open": cls.OPEN,
            "in progress": cls.IN_PROGRESS,
            "in_progress": cls.IN_PROGRESS,
            "under review": cls.UNDER_REVIEW,
            "under_review": cls.UNDER_REVIEW,
            "awaiting approval": cls.AWAITING_APPROVAL,
            "awaiting_approval": cls.AWAITING_APPROVAL,
            "resolved": cls.RESOLVED,
            "closed": cls.CLOSED,
            "blocked": cls.BLOCKED,
        }

        lower_value = clean_value.lower()
        if lower_value in name_map:
            return name_map[lower_value]

        # Try direct enum value match
        try:
            return cls(lower_value)
        except ValueError:
            raise ValueError(f"Unknown ticket status: {value}")

    @property
    def display_name(self) -> str:
        """Get display name with emoji prefix."""
        emoji_map = {
            self.OPEN: "🔴 Open",
            self.IN_PROGRESS: "🟡 In Progress",
            self.UNDER_REVIEW: "🔍 Under Review",
            self.AWAITING_APPROVAL: "🔵 Awaiting Approval",
            self.RESOLVED: "🟢 Resolved",
            self.CLOSED: "⚫ Closed",
            self.BLOCKED: "🚫 Blocked",
        }
        return emoji_map.get(self, self.value)

    def can_transition_to(self, new_status: "TicketStatus") -> bool:
        """Check if transition to new status is allowed."""
        valid_transitions = {
            self.OPEN: [self.IN_PROGRESS, self.BLOCKED, self.CLOSED],
            self.IN_PROGRESS: [self.UNDER_REVIEW, self.BLOCKED, self.OPEN],
            self.UNDER_REVIEW: [self.AWAITING_APPROVAL, self.IN_PROGRESS, self.BLOCKED],
            self.AWAITING_APPROVAL: [self.RESOLVED, self.IN_PROGRESS, self.BLOCKED],
            self.RESOLVED: [self.CLOSED, self.IN_PROGRESS],
            self.CLOSED: [self.OPEN],  # Reopen
            self.BLOCKED: [self.OPEN, self.IN_PROGRESS, self.UNDER_REVIEW],
        }
        return new_status in valid_transitions.get(self, [])


class TicketPriority(Enum):
    """Ticket priority levels."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

    @property
    def display_name(self) -> str:
        """Get display name with emoji."""
        emoji_map = {
            self.CRITICAL: "🔥 Critical",
            self.HIGH: "🔴 High",
            self.MEDIUM: "🟡 Medium",
            self.LOW: "🟢 Low",
        }
        return emoji_map.get(self, self.value)

    @property
    def sort_order(self) -> int:
        """Get sort order (lower = higher priority)."""
        order_map = {
            self.CRITICAL: 0,
            self.HIGH: 1,
            self.MEDIUM: 2,
            self.LOW: 3,
        }
        return order_map.get(self, 99)

    @classmethod
    def from_string(cls, value: str) -> "TicketPriority":
        """Convert string to TicketPriority."""
        clean_value = value.strip().lower()
        for priority in cls:
            if priority.value == clean_value or priority.name.lower() == clean_value:
                return priority
        raise ValueError(f"Unknown priority: {value}")


class TicketType(Enum):
    """Ticket type classification."""

    BUG = "bug"
    FEATURE = "feature"
    ENHANCEMENT = "enhancement"
    TASK = "task"
    DOCUMENTATION = "documentation"
    MAINTENANCE = "maintenance"
    SECURITY = "security"
    PERFORMANCE = "performance"

    @property
    def display_name(self) -> str:
        """Get display name with emoji."""
        emoji_map = {
            self.BUG: "🐛 Bug",
            self.FEATURE: "✨ Feature",
            self.ENHANCEMENT: "💡 Enhancement",
            self.TASK: "📋 Task",
            self.DOCUMENTATION: "📚 Documentation",
            self.MAINTENANCE: "🔧 Maintenance",
            self.SECURITY: "🔒 Security",
            self.PERFORMANCE: "⚡ Performance",
        }
        return emoji_map.get(self, self.value)

    @classmethod
    def from_string(cls, value: str) -> "TicketType":
        """Convert string to TicketType."""
        clean_value = value.strip().lower()
        for ticket_type in cls:
            if ticket_type.value == clean_value or ticket_type.name.lower() == clean_value:
                return ticket_type
        raise ValueError(f"Unknown ticket type: {value}")


@dataclass
class Agent:
    """
    Agent model for ticket assignments.

    Represents an AI agent or human user that can work on tickets.
    """

    name: str
    agent_type: str = "ai"  # "ai" or "human"
    capabilities: list[str] = field(default_factory=list)
    active: bool = True
    created_at: datetime = field(default_factory=datetime.now)
    last_seen: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)

    # Statistics
    tickets_completed: int = 0
    tickets_in_progress: int = 0
    average_completion_time: float | None = None  # in hours

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "agent_type": self.agent_type,
            "capabilities": self.capabilities,
            "active": self.active,
            "created_at": self.created_at.isoformat(),
            "last_seen": self.last_seen.isoformat(),
            "metadata": self.metadata,
            "tickets_completed": self.tickets_completed,
            "tickets_in_progress": self.tickets_in_progress,
            "average_completion_time": self.average_completion_time,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Agent":
        """Create from dictionary."""
        return cls(
            name=data["name"],
            agent_type=data.get("agent_type", "ai"),
            capabilities=data.get("capabilities", []),
            active=data.get("active", True),
            created_at=datetime.fromisoformat(data["created_at"])
            if "created_at" in data
            else datetime.now(),
            last_seen=datetime.fromisoformat(data["last_seen"])
            if "last_seen" in data
            else datetime.now(),
            metadata=data.get("metadata", {}),
            tickets_completed=data.get("tickets_completed", 0),
            tickets_in_progress=data.get("tickets_in_progress", 0),
            average_completion_time=data.get("average_completion_time"),
        )


@dataclass
class TicketHistory:
    """
    Ticket history entry for tracking changes.

    Records all changes to a ticket including status transitions,
    field updates, and agent actions.
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.now)
    action: str = ""  # e.g., "status_changed", "assigned", "comment_added"
    actor: str = ""  # Agent or user name
    actor_type: str = "system"  # "ai", "human", "system"
    field_changed: str | None = None
    old_value: str | None = None
    new_value: str | None = None
    message: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "action": self.action,
            "actor": self.actor,
            "actor_type": self.actor_type,
            "field_changed": self.field_changed,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "message": self.message,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TicketHistory":
        """Create from dictionary."""
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            timestamp=datetime.fromisoformat(data["timestamp"])
            if "timestamp" in data
            else datetime.now(),
            action=data.get("action", ""),
            actor=data.get("actor", ""),
            actor_type=data.get("actor_type", "system"),
            field_changed=data.get("field_changed"),
            old_value=data.get("old_value"),
            new_value=data.get("new_value"),
            message=data.get("message", ""),
            metadata=data.get("metadata", {}),
        )


@dataclass
class TicketComment:
    """
    Comment/note on a ticket.

    Supports text comments, code review feedback, and system messages.
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    ticket_id: str = ""
    author: str = ""
    author_type: str = "human"  # "ai", "human", "system"
    content: str = ""
    comment_type: str = "comment"  # "comment", "review", "system", "resolution"
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    # For review comments
    review_result: str | None = None  # "approved", "changes_requested"
    files_reviewed: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        result = {
            "id": self.id,
            "ticket_id": self.ticket_id,
            "author": self.author,
            "author_type": self.author_type,
            "content": self.content,
            "comment_type": self.comment_type,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata,
        }
        if self.updated_at:
            result["updated_at"] = self.updated_at.isoformat()
        if self.review_result:
            result["review_result"] = self.review_result
        if self.files_reviewed:
            result["files_reviewed"] = self.files_reviewed
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TicketComment":
        """Create from dictionary."""
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            ticket_id=data.get("ticket_id", ""),
            author=data.get("author", ""),
            author_type=data.get("author_type", "human"),
            content=data.get("content", ""),
            comment_type=data.get("comment_type", "comment"),
            created_at=datetime.fromisoformat(data["created_at"])
            if "created_at" in data
            else datetime.now(),
            updated_at=datetime.fromisoformat(data["updated_at"])
            if data.get("updated_at")
            else None,
            metadata=data.get("metadata", {}),
            review_result=data.get("review_result"),
            files_reviewed=data.get("files_reviewed", []),
        )


@dataclass
class Ticket:
    """
    Main ticket model.

    Represents a development task with full tracking capabilities.
    """

    # Core fields
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    ticket_number: str | None = None  # Human-friendly ID (e.g., "FB-042")
    title: str = ""
    description: str = ""

    # Classification
    ticket_type: TicketType = TicketType.TASK
    priority: TicketPriority = TicketPriority.MEDIUM
    status: TicketStatus = TicketStatus.OPEN

    # Assignment
    assigned_to: str | None = None  # Agent name
    created_by: str = "system"

    # Timestamps
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    due_date: datetime | None = None

    # Content
    requirements: list[str] = field(default_factory=list)
    files_to_modify: list[str] = field(default_factory=list)
    notes: str = ""
    resolution: str = ""

    # Relationships
    related_tickets: list[str] = field(default_factory=list)
    blocked_by: list[str] = field(default_factory=list)
    blocks: list[str] = field(default_factory=list)
    parent_ticket: str | None = None
    subtasks: list[str] = field(default_factory=list)

    # Labels and metadata
    labels: list[str] = field(default_factory=list)
    app: str | None = None  # Application this ticket belongs to
    app_version: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    # Work tracking
    problem_summary: str | None = None
    solution_summary: str | None = None
    testing_notes: str | None = None
    files_modified: list[str] = field(default_factory=list)

    # Screenshots (for before/after documentation)
    before_screenshot: str | None = None
    after_screenshot: str | None = None

    # History and comments
    history: list[TicketHistory] = field(default_factory=list)
    comments: list[TicketComment] = field(default_factory=list)

    # Review tracking
    review_status: str | None = None  # "pending", "approved", "changes_requested"
    reviewers: list[str] = field(default_factory=list)

    def __post_init__(self):
        """Ensure types are correct after initialization."""
        # Convert string types to enums if needed
        if isinstance(self.ticket_type, str):
            self.ticket_type = TicketType.from_string(self.ticket_type)
        if isinstance(self.priority, str):
            self.priority = TicketPriority.from_string(self.priority)
        if isinstance(self.status, str):
            self.status = TicketStatus.from_string(self.status)

    @property
    def is_open(self) -> bool:
        """Check if ticket is in an open state."""
        return self.status in [TicketStatus.OPEN, TicketStatus.IN_PROGRESS]

    @property
    def is_completed(self) -> bool:
        """Check if ticket is completed."""
        return self.status in [TicketStatus.RESOLVED, TicketStatus.CLOSED]

    @property
    def is_blocked(self) -> bool:
        """Check if ticket is blocked."""
        return self.status == TicketStatus.BLOCKED or bool(self.blocked_by)

    @property
    def time_in_progress(self) -> float | None:
        """Get time spent in progress (hours)."""
        if not self.started_at:
            return None
        end_time = self.completed_at or datetime.now()
        delta = end_time - self.started_at
        return delta.total_seconds() / 3600

    def add_history(
        self,
        action: str,
        actor: str,
        actor_type: str = "system",
        field_changed: str | None = None,
        old_value: str | None = None,
        new_value: str | None = None,
        message: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> TicketHistory:
        """Add a history entry."""
        entry = TicketHistory(
            action=action,
            actor=actor,
            actor_type=actor_type,
            field_changed=field_changed,
            old_value=old_value,
            new_value=new_value,
            message=message,
            metadata=metadata or {},
        )
        self.history.append(entry)
        self.updated_at = datetime.now()
        return entry

    def add_comment(
        self,
        content: str,
        author: str,
        author_type: str = "human",
        comment_type: str = "comment",
        metadata: dict[str, Any] | None = None,
    ) -> TicketComment:
        """Add a comment to the ticket."""
        comment = TicketComment(
            ticket_id=self.id,
            author=author,
            author_type=author_type,
            content=content,
            comment_type=comment_type,
            metadata=metadata or {},
        )
        self.comments.append(comment)
        self.add_history(
            action="comment_added",
            actor=author,
            actor_type=author_type,
            message=f"Added {comment_type}",
        )
        return comment

    def assign(self, agent_name: str, actor: str = "system", actor_type: str = "system") -> None:
        """Assign ticket to an agent."""
        old_assignee = self.assigned_to
        self.assigned_to = agent_name
        self.add_history(
            action="assigned",
            actor=actor,
            actor_type=actor_type,
            field_changed="assigned_to",
            old_value=old_assignee,
            new_value=agent_name,
            message=f"Assigned to {agent_name}",
        )

    def claim(self, agent_name: str) -> bool:
        """
        Claim ticket for work.

        Sets status to IN_PROGRESS and assigns to agent.
        Returns True if successful, False if ticket cannot be claimed.
        """
        if self.status not in [TicketStatus.OPEN, TicketStatus.BLOCKED]:
            return False

        self.assign(agent_name, actor=agent_name, actor_type="ai")
        self.transition_status(TicketStatus.IN_PROGRESS, actor=agent_name, actor_type="ai")
        self.started_at = datetime.now()
        return True

    def transition_status(
        self,
        new_status: TicketStatus,
        actor: str = "system",
        actor_type: str = "system",
        message: str = "",
    ) -> bool:
        """
        Transition to a new status.

        Validates the transition and records history.
        Returns True if successful, False if transition not allowed.
        """
        if not self.status.can_transition_to(new_status):
            return False

        old_status = self.status
        self.status = new_status

        # Update timestamps
        if new_status == TicketStatus.IN_PROGRESS and not self.started_at:
            self.started_at = datetime.now()
        elif new_status in [TicketStatus.RESOLVED, TicketStatus.CLOSED]:
            self.completed_at = datetime.now()

        self.add_history(
            action="status_changed",
            actor=actor,
            actor_type=actor_type,
            field_changed="status",
            old_value=old_status.value,
            new_value=new_status.value,
            message=message
            or f"Status changed from {old_status.display_name} to {new_status.display_name}",
        )

        return True

    def complete(
        self,
        problem_summary: str,
        solution_summary: str,
        files_modified: list[str],
        testing_notes: str = "",
        before_screenshot: str | None = None,
        after_screenshot: str | None = None,
        actor: str = "system",
        actor_type: str = "ai",
    ) -> bool:
        """
        Complete the ticket work and move to review.

        This does NOT resolve the ticket - it moves to UNDER_REVIEW.
        """
        if self.status != TicketStatus.IN_PROGRESS:
            return False

        self.problem_summary = problem_summary
        self.solution_summary = solution_summary
        self.files_modified = files_modified
        self.testing_notes = testing_notes
        self.before_screenshot = before_screenshot
        self.after_screenshot = after_screenshot

        return self.transition_status(
            TicketStatus.UNDER_REVIEW,
            actor=actor,
            actor_type=actor_type,
            message="Submitted for code review",
        )

    def approve_review(self, reviewer: str, actor_type: str = "ai") -> bool:
        """Approve code review and move to awaiting human approval."""
        if self.status != TicketStatus.UNDER_REVIEW:
            return False

        self.review_status = "approved"
        if reviewer not in self.reviewers:
            self.reviewers.append(reviewer)

        return self.transition_status(
            TicketStatus.AWAITING_APPROVAL,
            actor=reviewer,
            actor_type=actor_type,
            message=f"Code review approved by {reviewer}",
        )

    def request_changes(self, reviewer: str, feedback: str, actor_type: str = "ai") -> bool:
        """Request changes from code review."""
        if self.status != TicketStatus.UNDER_REVIEW:
            return False

        self.review_status = "changes_requested"
        if reviewer not in self.reviewers:
            self.reviewers.append(reviewer)

        self.add_comment(
            content=feedback,
            author=reviewer,
            author_type=actor_type,
            comment_type="review",
        )

        return self.transition_status(
            TicketStatus.IN_PROGRESS,
            actor=reviewer,
            actor_type=actor_type,
            message=f"Changes requested by {reviewer}",
        )

    def resolve(self, approver: str, notes: str = "") -> bool:
        """Resolve the ticket (human approval)."""
        if self.status != TicketStatus.AWAITING_APPROVAL:
            return False

        if notes:
            self.resolution = notes

        return self.transition_status(
            TicketStatus.RESOLVED,
            actor=approver,
            actor_type="human",
            message=f"Approved and resolved by {approver}",
        )

    def reject(self, approver: str, reason: str) -> bool:
        """Reject the ticket (human rejection)."""
        if self.status != TicketStatus.AWAITING_APPROVAL:
            return False

        self.add_comment(
            content=reason,
            author=approver,
            author_type="human",
            comment_type="review",
        )

        return self.transition_status(
            TicketStatus.IN_PROGRESS,
            actor=approver,
            actor_type="human",
            message=f"Rejected by {approver}: {reason}",
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "ticket_number": self.ticket_number,
            "title": self.title,
            "description": self.description,
            "ticket_type": self.ticket_type.value,
            "priority": self.priority.value,
            "status": self.status.value,
            "assigned_to": self.assigned_to,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "requirements": self.requirements,
            "files_to_modify": self.files_to_modify,
            "notes": self.notes,
            "resolution": self.resolution,
            "related_tickets": self.related_tickets,
            "blocked_by": self.blocked_by,
            "blocks": self.blocks,
            "parent_ticket": self.parent_ticket,
            "subtasks": self.subtasks,
            "labels": self.labels,
            "app": self.app,
            "app_version": self.app_version,
            "metadata": self.metadata,
            "problem_summary": self.problem_summary,
            "solution_summary": self.solution_summary,
            "testing_notes": self.testing_notes,
            "files_modified": self.files_modified,
            "before_screenshot": self.before_screenshot,
            "after_screenshot": self.after_screenshot,
            "history": [h.to_dict() for h in self.history],
            "comments": [c.to_dict() for c in self.comments],
            "review_status": self.review_status,
            "reviewers": self.reviewers,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Ticket":
        """Create from dictionary."""
        # Parse enums
        ticket_type = data.get("ticket_type", "task")
        if isinstance(ticket_type, str):
            ticket_type = TicketType.from_string(ticket_type)

        priority = data.get("priority", "medium")
        if isinstance(priority, str):
            priority = TicketPriority.from_string(priority)

        status = data.get("status", "open")
        if isinstance(status, str):
            status = TicketStatus.from_string(status)

        # Parse timestamps
        def parse_datetime(value: str | None) -> datetime | None:
            if not value:
                return None
            return datetime.fromisoformat(value)

        # Parse history and comments
        history = [TicketHistory.from_dict(h) for h in data.get("history", [])]
        comments = [TicketComment.from_dict(c) for c in data.get("comments", [])]

        return cls(
            id=data.get("id", str(uuid.uuid4())),
            ticket_number=data.get("ticket_number"),
            title=data.get("title", ""),
            description=data.get("description", ""),
            ticket_type=ticket_type,
            priority=priority,
            status=status,
            assigned_to=data.get("assigned_to"),
            created_by=data.get("created_by", "system"),
            created_at=parse_datetime(data.get("created_at")) or datetime.now(),
            updated_at=parse_datetime(data.get("updated_at")) or datetime.now(),
            started_at=parse_datetime(data.get("started_at")),
            completed_at=parse_datetime(data.get("completed_at")),
            due_date=parse_datetime(data.get("due_date")),
            requirements=data.get("requirements", []),
            files_to_modify=data.get("files_to_modify", []),
            notes=data.get("notes", ""),
            resolution=data.get("resolution", ""),
            related_tickets=data.get("related_tickets", []),
            blocked_by=data.get("blocked_by", []),
            blocks=data.get("blocks", []),
            parent_ticket=data.get("parent_ticket"),
            subtasks=data.get("subtasks", []),
            labels=data.get("labels", []),
            app=data.get("app"),
            app_version=data.get("app_version"),
            metadata=data.get("metadata", {}),
            problem_summary=data.get("problem_summary"),
            solution_summary=data.get("solution_summary"),
            testing_notes=data.get("testing_notes"),
            files_modified=data.get("files_modified", []),
            before_screenshot=data.get("before_screenshot"),
            after_screenshot=data.get("after_screenshot"),
            history=history,
            comments=comments,
            review_status=data.get("review_status"),
            reviewers=data.get("reviewers", []),
        )

    def __repr__(self) -> str:
        num = self.ticket_number or self.id[:8]
        return f"Ticket({num}, title={self.title!r}, status={self.status.value!r})"

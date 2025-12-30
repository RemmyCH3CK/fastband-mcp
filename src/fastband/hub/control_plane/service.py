"""
Control Plane Service - Main orchestrator for the Control Plane Dashboard.

Aggregates data from:
- Agent Operations Log (OpsLog)
- Ticket Storage
- Agent Coordinator

Provides real-time broadcasting via WebSocket.
"""

import asyncio
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from fastband.agents.ops_log import EventType, LogEntry, OpsLog, get_ops_log
from fastband.hub.websockets.manager import (
    WebSocketManager,
    WSEventType,
    get_websocket_manager,
)
from fastband.tickets.models import Ticket, TicketStatus
from fastband.tickets.storage import TicketStore, get_store

logger = logging.getLogger(__name__)


@dataclass
class AgentActivity:
    """Agent activity information for dashboard display."""

    name: str
    is_active: bool
    last_seen: str | None = None
    current_ticket: str | None = None
    last_action: str | None = None
    activity_count: int = 0
    has_clearance: bool = False
    under_hold: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TicketSummary:
    """Ticket summary for dashboard display."""

    id: str
    ticket_number: str
    title: str
    status: str
    priority: str
    assigned_to: str | None = None
    ticket_type: str = "task"
    created_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_ticket(cls, ticket: Ticket) -> "TicketSummary":
        return cls(
            id=ticket.id,
            ticket_number=ticket.ticket_number or ticket.id[:8],
            title=ticket.title,
            status=ticket.status.value,
            priority=ticket.priority.value,
            assigned_to=ticket.assigned_to,
            ticket_type=ticket.ticket_type.value,
            created_at=ticket.created_at.isoformat() if ticket.created_at else None,
        )


@dataclass
class DirectiveState:
    """Current state of holds and clearances."""

    has_active_hold: bool = False
    has_active_clearance: bool = False
    latest_directive: dict[str, Any] | None = None
    affected_agents: list[str] = field(default_factory=list)
    affected_tickets: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ControlPlaneDashboard:
    """Complete dashboard state."""

    agents: list[AgentActivity]
    ops_log_entries: list[dict[str, Any]]
    active_tickets: list[TicketSummary]
    directive_state: DirectiveState
    metrics: dict[str, Any]
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")

    def to_dict(self) -> dict[str, Any]:
        return {
            "agents": [a.to_dict() for a in self.agents],
            "ops_log_entries": self.ops_log_entries,
            "active_tickets": [t.to_dict() for t in self.active_tickets],
            "directive_state": self.directive_state.to_dict(),
            "metrics": self.metrics,
            "timestamp": self.timestamp,
        }


class ControlPlaneService:
    """
    Main orchestration service for the Control Plane.

    Aggregates data from OpsLog, Tickets, and AgentCoordinator.
    Broadcasts events to WebSocket clients.
    """

    def __init__(
        self,
        ops_log: OpsLog | None = None,
        ticket_store: TicketStore | None = None,
        ws_manager: WebSocketManager | None = None,
        project_path: Path | None = None,
    ):
        """
        Initialize the Control Plane service.

        Args:
            ops_log: OpsLog instance (default: global instance)
            ticket_store: Ticket storage (default: project default)
            ws_manager: WebSocket manager (default: global instance)
            project_path: Project path for storage (default: current directory)
        """
        self.project_path = project_path or Path.cwd()
        self._ops_log = ops_log
        self._ticket_store = ticket_store
        self._ws_manager = ws_manager

        # Polling configuration
        self._poll_interval = 1.0  # seconds
        self._poll_task: asyncio.Task | None = None
        self._last_entry_count = 0
        self._running = False

    @property
    def ops_log(self) -> OpsLog:
        """Get the OpsLog instance."""
        if self._ops_log is None:
            self._ops_log = get_ops_log(project_path=self.project_path)
        return self._ops_log

    @property
    def ticket_store(self) -> TicketStore:
        """Get the ticket store."""
        if self._ticket_store is None:
            self._ticket_store = get_store(path=self.project_path / ".fastband" / "tickets.json")
        return self._ticket_store

    @property
    def ws_manager(self) -> WebSocketManager:
        """Get the WebSocket manager."""
        if self._ws_manager is None:
            self._ws_manager = get_websocket_manager()
        return self._ws_manager

    async def start(self) -> None:
        """Start the Control Plane service (polling and broadcasting)."""
        if self._running:
            return

        self._running = True
        self._last_entry_count = self.ops_log.count()

        # Start polling task
        self._poll_task = asyncio.create_task(self._poll_ops_log())

        # Start WebSocket heartbeat
        await self.ws_manager.start_heartbeat()

        logger.info("Control Plane service started")

    async def stop(self) -> None:
        """Stop the Control Plane service."""
        self._running = False

        if self._poll_task:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
            self._poll_task = None

        await self.ws_manager.stop_heartbeat()

        logger.info("Control Plane service stopped")

    async def _poll_ops_log(self) -> None:
        """Poll the ops log for new entries and broadcast."""
        while self._running:
            try:
                await asyncio.sleep(self._poll_interval)

                current_count = self.ops_log.count()
                if current_count > self._last_entry_count:
                    # New entries detected
                    new_entries = self.ops_log.read_entries(
                        limit=current_count - self._last_entry_count
                    )

                    for entry in reversed(new_entries):  # Broadcast oldest first
                        await self._broadcast_ops_log_entry(entry)

                    self._last_entry_count = current_count

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error polling ops log: {e}")

    async def _broadcast_ops_log_entry(self, entry: LogEntry) -> None:
        """Broadcast an ops log entry to subscribed clients."""
        # Determine event type based on entry type
        event_type_map = {
            EventType.AGENT_STARTED.value: WSEventType.AGENT_STARTED,
            EventType.AGENT_STOPPED.value: WSEventType.AGENT_STOPPED,
            EventType.TICKET_CLAIMED.value: WSEventType.TICKET_CLAIMED,
            EventType.TICKET_COMPLETED.value: WSEventType.TICKET_COMPLETED,
            EventType.HOLD.value: WSEventType.DIRECTIVE_HOLD,
            EventType.CLEARANCE_GRANTED.value: WSEventType.DIRECTIVE_CLEARANCE,
        }

        ws_event_type = event_type_map.get(entry.event_type, WSEventType.OPS_LOG_ENTRY)

        await self.ws_manager.broadcast(
            event_type=ws_event_type,
            data=entry.to_dict(),
        )

    async def get_dashboard_state(self) -> ControlPlaneDashboard:
        """
        Get the complete dashboard state.

        Returns:
            ControlPlaneDashboard with all current data
        """
        # Get agents
        agents = await self.get_active_agents()

        # Get ops log entries
        entries = self.ops_log.read_entries(limit=100)
        ops_log_data = [e.to_dict() for e in entries]

        # Get active tickets
        tickets = await self.get_active_tickets()

        # Get directive state
        directive = await self.get_directive_state()

        # Compute metrics
        metrics = self._compute_metrics(agents, tickets, entries)

        return ControlPlaneDashboard(
            agents=agents,
            ops_log_entries=ops_log_data,
            active_tickets=tickets,
            directive_state=directive,
            metrics=metrics,
        )

    async def get_active_agents(
        self,
        within_hours: float = 1.0,
    ) -> list[AgentActivity]:
        """
        Get all recently active agents.

        Args:
            within_hours: Time window for activity

        Returns:
            List of AgentActivity objects
        """
        active_data = self.ops_log.check_active_agents(within_hours=within_hours)
        directive = self.ops_log.get_latest_directive()

        agents = []
        for agent_name, info in active_data.items():
            has_clearance = False
            under_hold = False

            if directive:
                if directive.event_type == EventType.CLEARANCE_GRANTED.value:
                    granted_to = directive.metadata.get("granted_to", [])
                    if agent_name in granted_to:
                        has_clearance = True
                elif directive.event_type == EventType.HOLD.value:
                    affected = directive.metadata.get("affected_agents", [])
                    is_global = directive.metadata.get("is_global", False)
                    if is_global or agent_name in affected:
                        under_hold = True

            agents.append(
                AgentActivity(
                    name=agent_name,
                    is_active=True,
                    last_seen=info.get("last_seen"),
                    current_ticket=info.get("current_ticket"),
                    last_action=info.get("last_action"),
                    activity_count=info.get("activity_count", 0),
                    has_clearance=has_clearance,
                    under_hold=under_hold,
                )
            )

        return agents

    async def get_operations_timeline(
        self,
        since: str | None = None,
        agent: str | None = None,
        event_type: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Get filtered operations log entries.

        Args:
            since: Time filter (e.g., "1h", "24h")
            agent: Filter by agent name
            event_type: Filter by event type
            limit: Maximum entries to return

        Returns:
            List of log entry dictionaries
        """
        entries = self.ops_log.read_entries(
            since=since,
            agent=agent,
            event_type=event_type,
            limit=limit,
        )
        return [e.to_dict() for e in entries]

    async def get_active_tickets(self) -> list[TicketSummary]:
        """
        Get all non-closed tickets.

        Returns:
            List of TicketSummary objects
        """
        # Get tickets that are not closed
        active_statuses = [
            TicketStatus.OPEN,
            TicketStatus.IN_PROGRESS,
            TicketStatus.UNDER_REVIEW,
            TicketStatus.AWAITING_APPROVAL,
        ]

        tickets = []
        for status in active_statuses:
            status_tickets = self.ticket_store.list(status=status, limit=50)
            tickets.extend(status_tickets)

        return [TicketSummary.from_ticket(t) for t in tickets]

    async def get_directive_state(self) -> DirectiveState:
        """
        Get the current directive state (holds/clearances).

        Returns:
            DirectiveState object
        """
        directive = self.ops_log.get_latest_directive()

        if not directive:
            return DirectiveState()

        is_hold = directive.event_type == EventType.HOLD.value
        is_clearance = directive.event_type == EventType.CLEARANCE_GRANTED.value

        affected_agents = directive.metadata.get("affected_agents" if is_hold else "granted_to", [])
        affected_tickets = directive.metadata.get("tickets", [])

        return DirectiveState(
            has_active_hold=is_hold,
            has_active_clearance=is_clearance,
            latest_directive=directive.to_dict(),
            affected_agents=affected_agents,
            affected_tickets=affected_tickets,
        )

    async def issue_hold(
        self,
        issuing_agent: str,
        affected_agents: list[str],
        tickets: list[str] | None = None,
        reason: str = "Coordination required",
    ) -> LogEntry:
        """
        Issue a hold directive.

        Args:
            issuing_agent: Agent issuing the hold
            affected_agents: Agents who should pause
            tickets: Specific tickets (None = global hold)
            reason: Reason for hold

        Returns:
            The created LogEntry
        """
        entry = self.ops_log.issue_hold(
            agent=issuing_agent,
            affected_agents=affected_agents,
            tickets=tickets,
            reason=reason,
        )

        # Broadcast immediately
        await self._broadcast_ops_log_entry(entry)

        return entry

    async def grant_clearance(
        self,
        granting_agent: str,
        granted_to: list[str],
        tickets: list[str],
        reason: str,
    ) -> LogEntry:
        """
        Grant clearance to agents.

        Args:
            granting_agent: Agent granting clearance
            granted_to: Agents being cleared
            tickets: Tickets covered by clearance
            reason: Reason for clearance

        Returns:
            The created LogEntry
        """
        entry = self.ops_log.grant_clearance(
            agent=granting_agent,
            granted_to=granted_to,
            tickets=tickets,
            reason=reason,
        )

        # Broadcast immediately
        await self._broadcast_ops_log_entry(entry)

        return entry

    def _compute_metrics(
        self,
        agents: list[AgentActivity],
        tickets: list[TicketSummary],
        entries: list[LogEntry],
    ) -> dict[str, Any]:
        """Compute dashboard metrics."""
        # Agent metrics
        active_agent_count = len([a for a in agents if a.is_active])
        agents_under_hold = len([a for a in agents if a.under_hold])

        # Ticket metrics
        open_tickets = len([t for t in tickets if t.status == "open"])
        in_progress_tickets = len([t for t in tickets if t.status == "in_progress"])
        under_review_tickets = len([t for t in tickets if t.status == "under_review"])

        # Activity metrics
        recent_entries = [
            e
            for e in entries
            if datetime.fromisoformat(e.timestamp.rstrip("Z"))
            > datetime.utcnow().replace(hour=0, minute=0, second=0)
        ]
        today_activity_count = len(recent_entries)

        return {
            "active_agents": active_agent_count,
            "agents_under_hold": agents_under_hold,
            "open_tickets": open_tickets,
            "in_progress_tickets": in_progress_tickets,
            "under_review_tickets": under_review_tickets,
            "total_active_tickets": len(tickets),
            "today_activity_count": today_activity_count,
            "websocket_connections": self.ws_manager.get_connection_count(),
        }


# Global Control Plane service instance
_control_plane_service: ControlPlaneService | None = None


def get_control_plane_service(
    project_path: Path | None = None,
    reset: bool = False,
) -> ControlPlaneService:
    """
    Get the global Control Plane service instance.

    Args:
        project_path: Path to project directory
        reset: Force creation of a new instance

    Returns:
        The global ControlPlaneService instance
    """
    global _control_plane_service

    if _control_plane_service is None or reset:
        _control_plane_service = ControlPlaneService(project_path=project_path)

    return _control_plane_service

"""
Agent coordination utilities.

Higher-level coordination functions built on top of OpsLog.
Provides convenient APIs for common multi-agent workflows.
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from fastband.agents.ops_log import (
    EventType,
    LogEntry,
    OpsLog,
    get_ops_log,
)


@dataclass
class AgentStatus:
    """Status information for an agent."""

    name: str
    is_active: bool
    last_seen: str | None = None
    current_ticket: str | None = None
    last_action: str | None = None
    activity_count: int = 0
    has_clearance: bool = False
    under_hold: bool = False


@dataclass
class CoordinationResult:
    """Result of a coordination operation."""

    success: bool
    message: str
    entry: LogEntry | None = None
    conflicts: list[LogEntry] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class AgentCoordinator:
    """
    High-level coordinator for multi-agent workflows.

    Provides:
    - Agent registration and status tracking
    - Clearance management
    - Conflict resolution
    - Rebuild coordination
    """

    def __init__(
        self,
        agent_name: str,
        ops_log: OpsLog | None = None,
        auto_register: bool = True,
    ):
        """
        Initialize the coordinator.

        Args:
            agent_name: Name of this agent
            ops_log: OpsLog instance (default: global instance)
            auto_register: Automatically log agent start
        """
        self.agent_name = agent_name
        self.ops_log = ops_log or get_ops_log()

        if auto_register:
            self.register()

    def register(self) -> LogEntry:
        """Register this agent as active."""
        return self.ops_log.write_entry(
            agent=self.agent_name,
            event_type=EventType.AGENT_STARTED,
            message=f"Agent {self.agent_name} started",
            metadata={"started_at": datetime.utcnow().isoformat() + "Z"},
        )

    def unregister(self) -> LogEntry:
        """Unregister this agent."""
        return self.ops_log.write_entry(
            agent=self.agent_name,
            event_type=EventType.AGENT_STOPPED,
            message=f"Agent {self.agent_name} stopped",
        )

    def claim_ticket(
        self,
        ticket_id: str,
        force: bool = False,
    ) -> CoordinationResult:
        """
        Attempt to claim a ticket.

        Args:
            ticket_id: Ticket to claim
            force: Force claim even with conflicts

        Returns:
            CoordinationResult with success/failure info
        """
        # Check for conflicts
        conflicts = self.ops_log.detect_conflicts(
            ticket_id=ticket_id,
            agent=self.agent_name,
            action="claim",
        )

        if conflicts and not force:
            return CoordinationResult(
                success=False,
                message=f"Conflicts detected: {len(conflicts)} blocking entries",
                conflicts=conflicts,
            )

        entry, detected_conflicts = self.ops_log.claim_ticket(
            agent=self.agent_name,
            ticket_id=ticket_id,
            check_conflicts=False,  # Already checked above
        )

        warnings = []
        if conflicts:
            warnings.append(f"Forced claim despite {len(conflicts)} conflicts")

        return CoordinationResult(
            success=True,
            message=f"Ticket #{ticket_id} claimed",
            entry=entry,
            conflicts=conflicts,
            warnings=warnings,
        )

    def complete_ticket(
        self,
        ticket_id: str,
        summary: str | None = None,
    ) -> CoordinationResult:
        """
        Mark a ticket as completed.

        Args:
            ticket_id: Ticket to complete
            summary: Completion summary

        Returns:
            CoordinationResult
        """
        entry = self.ops_log.complete_ticket(
            agent=self.agent_name,
            ticket_id=ticket_id,
            summary=summary,
        )

        return CoordinationResult(
            success=True,
            message=f"Ticket #{ticket_id} completed",
            entry=entry,
        )

    def request_clearance(
        self,
        tickets: list[str],
        reason: str,
    ) -> CoordinationResult:
        """
        Request clearance to work on tickets.

        This logs a status update requesting clearance. Another agent
        or human can then grant clearance using grant_clearance().

        Args:
            tickets: Tickets needing clearance
            reason: Reason for request

        Returns:
            CoordinationResult
        """
        entry = self.ops_log.write_entry(
            agent=self.agent_name,
            event_type=EventType.STATUS_UPDATE,
            message=f"Requesting clearance for tickets {', '.join(tickets)}: {reason}",
            metadata={
                "request_type": "clearance",
                "tickets": tickets,
                "reason": reason,
            },
        )

        return CoordinationResult(
            success=True,
            message="Clearance request logged",
            entry=entry,
        )

    def grant_clearance(
        self,
        agents: list[str],
        tickets: list[str],
        reason: str,
    ) -> CoordinationResult:
        """
        Grant clearance to other agents.

        Args:
            agents: Agents to clear
            tickets: Tickets being cleared
            reason: Reason for clearance

        Returns:
            CoordinationResult
        """
        entry = self.ops_log.grant_clearance(
            agent=self.agent_name,
            granted_to=agents,
            tickets=tickets,
            reason=reason,
        )

        return CoordinationResult(
            success=True,
            message=f"Clearance granted to {', '.join(agents)}",
            entry=entry,
        )

    def issue_hold(
        self,
        agents: list[str],
        tickets: list[str] | None = None,
        reason: str = "Coordination required",
    ) -> CoordinationResult:
        """
        Issue a hold directive.

        Args:
            agents: Agents who should pause
            tickets: Specific tickets (None = global hold)
            reason: Reason for hold

        Returns:
            CoordinationResult
        """
        entry = self.ops_log.issue_hold(
            agent=self.agent_name,
            affected_agents=agents,
            tickets=tickets,
            reason=reason,
        )

        return CoordinationResult(
            success=True,
            message=f"Hold issued to {', '.join(agents)}",
            entry=entry,
        )

    def check_for_hold(self) -> LogEntry | None:
        """
        Check if there's an active hold affecting this agent.

        Returns:
            The hold entry if active, None otherwise
        """
        directive = self.ops_log.get_latest_directive()

        if directive and directive.event_type == EventType.HOLD.value:
            affected = directive.metadata.get("affected_agents", [])
            is_global = directive.metadata.get("is_global", False)

            if is_global or self.agent_name in affected:
                return directive

        return None

    def announce_rebuild(
        self,
        container: str,
        ticket_id: str | None = None,
        files_changed: list[str] | None = None,
        status: str = "requested",
    ) -> CoordinationResult:
        """
        Announce a container rebuild.

        Args:
            container: Container being rebuilt
            ticket_id: Related ticket
            files_changed: Changed files
            status: "requested" or "complete"

        Returns:
            CoordinationResult
        """
        entry = self.ops_log.announce_rebuild(
            agent=self.agent_name,
            container=container,
            ticket_id=ticket_id,
            files_changed=files_changed,
            status=status,
        )

        return CoordinationResult(
            success=True,
            message=f"Rebuild {status} announced for {container}",
            entry=entry,
        )

    def get_active_agents(self, within_hours: float = 1.0) -> dict[str, AgentStatus]:
        """
        Get status of all recently active agents.

        Args:
            within_hours: Time window for activity

        Returns:
            Dict mapping agent names to AgentStatus
        """
        active = self.ops_log.check_active_agents(within_hours=within_hours)
        directive = self.ops_log.get_latest_directive()

        results: dict[str, AgentStatus] = {}

        for agent_name, info in active.items():
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

            results[agent_name] = AgentStatus(
                name=agent_name,
                is_active=True,
                last_seen=info.get("last_seen"),
                current_ticket=info.get("current_ticket"),
                last_action=info.get("last_action"),
                activity_count=info.get("activity_count", 0),
                has_clearance=has_clearance,
                under_hold=under_hold,
            )

        return results

    def update_status(
        self,
        message: str,
        ticket_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> LogEntry:
        """
        Post a general status update.

        Args:
            message: Status message
            ticket_id: Related ticket (optional)
            metadata: Additional data (optional)

        Returns:
            The created LogEntry
        """
        return self.ops_log.write_entry(
            agent=self.agent_name,
            event_type=EventType.STATUS_UPDATE,
            message=message,
            ticket_id=ticket_id,
            metadata=metadata,
        )


# Convenience functions for quick coordination tasks


def check_active_agents(
    within_hours: float = 1.0,
    project_path: Path | None = None,
) -> dict[str, dict[str, Any]]:
    """
    Check which agents are currently active.

    Args:
        within_hours: Time window to check
        project_path: Path to project directory

    Returns:
        Dict with agent activity information
    """
    ops_log = get_ops_log(project_path=project_path)
    return ops_log.check_active_agents(within_hours=within_hours)


def request_clearance(
    agent: str,
    tickets: list[str],
    reason: str,
    project_path: Path | None = None,
) -> LogEntry:
    """
    Request clearance to work on tickets.

    Args:
        agent: Agent requesting clearance
        tickets: Tickets needing clearance
        reason: Reason for request
        project_path: Path to project directory

    Returns:
        The created LogEntry
    """
    ops_log = get_ops_log(project_path=project_path)
    return ops_log.write_entry(
        agent=agent,
        event_type=EventType.STATUS_UPDATE,
        message=f"Clearance requested for tickets {', '.join(tickets)}: {reason}",
        metadata={
            "request_type": "clearance",
            "tickets": tickets,
            "reason": reason,
        },
    )


def announce_rebuild(
    agent: str,
    container: str,
    status: str = "requested",
    ticket_id: str | None = None,
    files_changed: list[str] | None = None,
    project_path: Path | None = None,
) -> LogEntry:
    """
    Announce a container rebuild.

    Args:
        agent: Agent performing rebuild
        container: Container name
        status: "requested" or "complete"
        ticket_id: Related ticket
        files_changed: Changed files
        project_path: Path to project directory

    Returns:
        The created LogEntry
    """
    ops_log = get_ops_log(project_path=project_path)
    return ops_log.announce_rebuild(
        agent=agent,
        container=container,
        ticket_id=ticket_id,
        files_changed=files_changed,
        status=status,
    )


def get_agent_status(
    agent_name: str,
    project_path: Path | None = None,
) -> AgentStatus:
    """
    Get status information for a specific agent.

    Args:
        agent_name: Agent to check
        project_path: Path to project directory

    Returns:
        AgentStatus for the agent
    """
    ops_log = get_ops_log(project_path=project_path)
    active = ops_log.check_active_agents(within_hours=24.0)

    if agent_name not in active:
        return AgentStatus(
            name=agent_name,
            is_active=False,
        )

    info = active[agent_name]
    directive = ops_log.get_latest_directive()

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

    return AgentStatus(
        name=agent_name,
        is_active=True,
        last_seen=info.get("last_seen"),
        current_ticket=info.get("current_ticket"),
        last_action=info.get("last_action"),
        activity_count=info.get("activity_count", 0),
        has_clearance=has_clearance,
        under_hold=under_hold,
    )


def get_latest_directive(
    project_path: Path | None = None,
) -> LogEntry | None:
    """
    Get the most recent clearance or hold directive.

    Args:
        project_path: Path to project directory

    Returns:
        The latest directive entry, or None
    """
    ops_log = get_ops_log(project_path=project_path)
    return ops_log.get_latest_directive()


def detect_conflicts(
    ticket_id: str,
    agent: str,
    project_path: Path | None = None,
) -> list[LogEntry]:
    """
    Detect conflicts for a ticket operation.

    Args:
        ticket_id: Ticket being operated on
        agent: Agent attempting operation
        project_path: Path to project directory

    Returns:
        List of conflicting entries
    """
    ops_log = get_ops_log(project_path=project_path)
    return ops_log.detect_conflicts(ticket_id=ticket_id, agent=agent)

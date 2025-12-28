"""
Fastband Agent Coordination System.

Provides multi-agent coordination capabilities:
- Operations log for agent communication
- Clearance/hold system for workflow coordination
- Conflict detection and resolution
- Rebuild announcements and status tracking
"""

from fastband.agents.ops_log import (
    OpsLog,
    LogEntry,
    EventType,
    get_ops_log,
)
from fastband.agents.coordination import (
    AgentCoordinator,
    check_active_agents,
    request_clearance,
    announce_rebuild,
    get_agent_status,
)

__all__ = [
    # Core ops log
    "OpsLog",
    "LogEntry",
    "EventType",
    "get_ops_log",
    # Coordination helpers
    "AgentCoordinator",
    "check_active_agents",
    "request_clearance",
    "announce_rebuild",
    "get_agent_status",
]

"""
Fastband Agent Coordination System.

Provides multi-agent coordination capabilities:
- Operations log for agent communication
- Clearance/hold system for workflow coordination
- Conflict detection and resolution
- Rebuild announcements and status tracking
- Agent onboarding and bible enforcement
"""

from fastband.agents.coordination import (
    AgentCoordinator,
    announce_rebuild,
    check_active_agents,
    get_agent_status,
    request_clearance,
)
from fastband.agents.onboarding import (
    AgentOnboarding,
    AgentSession,
    OnboardingRequirement,
    get_onboarding,
    reset_onboarding,
)
from fastband.agents.ops_log import (
    EventType,
    LogEntry,
    OpsLog,
    get_ops_log,
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
    # Agent onboarding
    "AgentOnboarding",
    "AgentSession",
    "OnboardingRequirement",
    "get_onboarding",
    "reset_onboarding",
]

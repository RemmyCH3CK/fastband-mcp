"""
Control Plane module for Fastband Agent Control Plane.

Provides the orchestration layer for multi-agent coordination:
- Real-time dashboard data aggregation
- WebSocket event broadcasting
- Hold/clearance management
- Agent activity monitoring
"""

from fastband.hub.control_plane.service import (
    AgentActivity,
    ControlPlaneDashboard,
    ControlPlaneService,
    DirectiveState,
    TicketSummary,
    get_control_plane_service,
)

__all__ = [
    "ControlPlaneService",
    "ControlPlaneDashboard",
    "AgentActivity",
    "DirectiveState",
    "TicketSummary",
    "get_control_plane_service",
]

"""
Control Plane API Routes.

REST endpoints for dashboard data and WebSocket endpoint for real-time updates.
"""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from fastband.hub.control_plane.service import (
    ControlPlaneService,
    get_control_plane_service,
)
from fastband.hub.websockets.manager import (
    WebSocketManager,
    get_websocket_manager,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/control-plane", tags=["control-plane"])


# Request/Response Models


class HoldRequest(BaseModel):
    """Request to issue a hold directive."""

    issuing_agent: str
    affected_agents: list[str]
    tickets: list[str] | None = None
    reason: str = "Coordination required"


class ClearanceRequest(BaseModel):
    """Request to grant clearance."""

    granting_agent: str
    granted_to: list[str]
    tickets: list[str]
    reason: str


class DirectiveResponse(BaseModel):
    """Response for directive operations."""

    success: bool
    entry_id: str
    message: str


# Dependency injection


def get_service() -> ControlPlaneService:
    """Get the Control Plane service."""
    return get_control_plane_service()


def get_ws_manager() -> WebSocketManager:
    """Get the WebSocket manager."""
    return get_websocket_manager()


# REST Endpoints


@router.get("/dashboard")
async def get_dashboard(
    service: ControlPlaneService = Depends(get_service),
):
    """
    Get the complete dashboard state.

    Returns all data needed for the Control Plane dashboard:
    - Active agents
    - Operations log entries
    - Active tickets
    - Directive state (holds/clearances)
    - Metrics
    """
    dashboard = await service.get_dashboard_state()
    return dashboard.to_dict()


@router.get("/agents")
async def get_agents(
    within_hours: float = Query(1.0, description="Time window for activity"),
    service: ControlPlaneService = Depends(get_service),
):
    """
    Get active agents.

    Args:
        within_hours: Time window to check for agent activity
    """
    agents = await service.get_active_agents(within_hours=within_hours)
    return {
        "agents": [a.to_dict() for a in agents],
        "count": len(agents),
    }


@router.get("/operations")
async def get_operations(
    since: str | None = Query(None, description="Time filter (e.g., '1h', '24h')"),
    agent: str | None = Query(None, description="Filter by agent name"),
    event_type: str | None = Query(None, description="Filter by event type"),
    limit: int = Query(100, le=500, description="Maximum entries to return"),
    service: ControlPlaneService = Depends(get_service),
):
    """
    Get operations log entries.

    Args:
        since: Time filter (e.g., "1h", "30m", "24h")
        agent: Filter by agent name
        event_type: Filter by event type
        limit: Maximum entries to return
    """
    entries = await service.get_operations_timeline(
        since=since,
        agent=agent,
        event_type=event_type,
        limit=limit,
    )
    return {
        "entries": entries,
        "count": len(entries),
    }


@router.get("/tickets")
async def get_tickets(
    service: ControlPlaneService = Depends(get_service),
):
    """
    Get active tickets (non-closed).
    """
    tickets = await service.get_active_tickets()
    return {
        "tickets": [t.to_dict() for t in tickets],
        "count": len(tickets),
    }


@router.get("/directives")
async def get_directives(
    service: ControlPlaneService = Depends(get_service),
):
    """
    Get current directive state (holds/clearances).
    """
    directive = await service.get_directive_state()
    return directive.to_dict()


@router.post("/hold", response_model=DirectiveResponse)
async def issue_hold(
    request: HoldRequest,
    service: ControlPlaneService = Depends(get_service),
):
    """
    Issue a hold directive.

    This pauses work for affected agents until cleared.
    """
    try:
        entry = await service.issue_hold(
            issuing_agent=request.issuing_agent,
            affected_agents=request.affected_agents,
            tickets=request.tickets,
            reason=request.reason,
        )

        return DirectiveResponse(
            success=True,
            entry_id=entry.id,
            message=f"Hold issued to {', '.join(request.affected_agents)}",
        )
    except Exception as e:
        logger.error(f"Failed to issue hold: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/clearance", response_model=DirectiveResponse)
async def grant_clearance(
    request: ClearanceRequest,
    service: ControlPlaneService = Depends(get_service),
):
    """
    Grant clearance to agents.

    This allows specified agents to work on specified tickets.
    """
    try:
        entry = await service.grant_clearance(
            granting_agent=request.granting_agent,
            granted_to=request.granted_to,
            tickets=request.tickets,
            reason=request.reason,
        )

        return DirectiveResponse(
            success=True,
            entry_id=entry.id,
            message=f"Clearance granted to {', '.join(request.granted_to)}",
        )
    except Exception as e:
        logger.error(f"Failed to grant clearance: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metrics")
async def get_metrics(
    service: ControlPlaneService = Depends(get_service),
):
    """
    Get dashboard metrics.
    """
    dashboard = await service.get_dashboard_state()
    return dashboard.metrics


# WebSocket Endpoint


@router.websocket("/ws")
async def control_plane_websocket(
    websocket: WebSocket,
    subscriptions: str = Query("all", description="Comma-separated subscription types"),
    ws_manager: WebSocketManager = Depends(get_ws_manager),
):
    """
    WebSocket endpoint for real-time Control Plane updates.

    Subscription types:
    - all: All updates (default)
    - agents: Agent status updates only
    - ops_log: Operations log entries only
    - tickets: Ticket updates only
    - directives: Hold/clearance directives only

    Multiple subscriptions can be specified as comma-separated values:
    ?subscriptions=agents,tickets
    """
    connection_id = str(uuid.uuid4())[:8]
    subscription_list = [s.strip() for s in subscriptions.split(",") if s.strip()]

    await ws_manager.connect(
        websocket=websocket,
        connection_id=connection_id,
        subscriptions=subscription_list,
    )

    try:
        while True:
            # Wait for incoming messages (ping/pong, subscription updates)
            message = await websocket.receive_text()
            await ws_manager.handle_client_message(connection_id, message)

    except WebSocketDisconnect:
        logger.info(f"WebSocket {connection_id} disconnected")
    except Exception as e:
        logger.error(f"WebSocket error for {connection_id}: {e}")
    finally:
        await ws_manager.disconnect(connection_id)

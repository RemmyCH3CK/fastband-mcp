"""
WebSocket Connection Manager for Control Plane.

Provides real-time event broadcasting with subscription-based filtering.
"""

import asyncio
import json
import logging
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class SubscriptionType(str, Enum):
    """Types of event subscriptions for Control Plane."""

    ALL = "all"  # Full control plane updates
    AGENTS = "agents"  # Agent status only
    OPS_LOG = "ops_log"  # Operations log only
    TICKETS = "tickets"  # Ticket updates only
    DIRECTIVES = "directives"  # Clearance/hold only


class WSEventType(str, Enum):
    """WebSocket event types."""

    # Agent events
    AGENT_STARTED = "agent:started"
    AGENT_STOPPED = "agent:stopped"
    AGENT_STATUS = "agent:status"

    # Operations log events
    OPS_LOG_ENTRY = "ops_log:entry"

    # Ticket events
    TICKET_CLAIMED = "ticket:claimed"
    TICKET_COMPLETED = "ticket:completed"
    TICKET_UPDATED = "ticket:updated"

    # Directive events
    DIRECTIVE_HOLD = "directive:hold"
    DIRECTIVE_CLEARANCE = "directive:clearance"

    # System events
    CONNECTED = "system:connected"
    PING = "system:ping"
    PONG = "system:pong"
    ERROR = "system:error"


@dataclass
class WSMessage:
    """WebSocket message format."""

    type: str
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    data: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, data: str) -> "WSMessage":
        """Create from JSON string."""
        parsed = json.loads(data)
        return cls(
            type=parsed.get("type", "unknown"),
            timestamp=parsed.get("timestamp", datetime.utcnow().isoformat() + "Z"),
            data=parsed.get("data", {}),
        )


# Map event types to subscription types
EVENT_SUBSCRIPTION_MAP: dict[WSEventType, list[SubscriptionType]] = {
    WSEventType.AGENT_STARTED: [SubscriptionType.ALL, SubscriptionType.AGENTS],
    WSEventType.AGENT_STOPPED: [SubscriptionType.ALL, SubscriptionType.AGENTS],
    WSEventType.AGENT_STATUS: [SubscriptionType.ALL, SubscriptionType.AGENTS],
    WSEventType.OPS_LOG_ENTRY: [SubscriptionType.ALL, SubscriptionType.OPS_LOG],
    WSEventType.TICKET_CLAIMED: [SubscriptionType.ALL, SubscriptionType.TICKETS],
    WSEventType.TICKET_COMPLETED: [SubscriptionType.ALL, SubscriptionType.TICKETS],
    WSEventType.TICKET_UPDATED: [SubscriptionType.ALL, SubscriptionType.TICKETS],
    WSEventType.DIRECTIVE_HOLD: [SubscriptionType.ALL, SubscriptionType.DIRECTIVES],
    WSEventType.DIRECTIVE_CLEARANCE: [SubscriptionType.ALL, SubscriptionType.DIRECTIVES],
}


@dataclass
class Connection:
    """Represents a WebSocket connection."""

    id: str
    websocket: WebSocket
    subscriptions: set[SubscriptionType]
    connected_at: datetime = field(default_factory=datetime.utcnow)
    last_ping: datetime | None = None


class WebSocketManager:
    """
    Manages WebSocket connections with subscription-based routing.

    Features:
    - Connection pool management
    - Subscription-based message filtering
    - Broadcast to all or specific subscription types
    - Heartbeat/ping-pong support
    - Auto-reconnect support (client-side)
    """

    def __init__(self):
        self._connections: dict[str, Connection] = {}
        self._lock = asyncio.Lock()
        self._heartbeat_interval = 30  # seconds
        self._heartbeat_task: asyncio.Task | None = None

    async def connect(
        self,
        websocket: WebSocket,
        connection_id: str,
        subscriptions: list[str] | None = None,
    ) -> None:
        """
        Accept and register a new WebSocket connection.

        Args:
            websocket: FastAPI WebSocket instance
            connection_id: Unique connection identifier
            subscriptions: List of subscription type strings
        """
        await websocket.accept()

        # Parse subscriptions
        sub_set: set[SubscriptionType] = set()
        if subscriptions:
            for sub in subscriptions:
                try:
                    sub_set.add(SubscriptionType(sub))
                except ValueError:
                    logger.warning(f"Unknown subscription type: {sub}")

        # Default to ALL if none specified
        if not sub_set:
            sub_set.add(SubscriptionType.ALL)

        async with self._lock:
            self._connections[connection_id] = Connection(
                id=connection_id,
                websocket=websocket,
                subscriptions=sub_set,
            )

        logger.info(f"WebSocket connected: {connection_id} with subscriptions: {sub_set}")

        # Send connection confirmation
        await self.send_to_connection(
            connection_id,
            WSMessage(
                type=WSEventType.CONNECTED.value,
                data={
                    "connection_id": connection_id,
                    "subscriptions": [s.value for s in sub_set],
                },
            ),
        )

    async def disconnect(self, connection_id: str) -> None:
        """
        Remove a WebSocket connection.

        Args:
            connection_id: Connection to remove
        """
        async with self._lock:
            if connection_id in self._connections:
                del self._connections[connection_id]
                logger.info(f"WebSocket disconnected: {connection_id}")

    async def send_to_connection(
        self,
        connection_id: str,
        message: WSMessage,
    ) -> bool:
        """
        Send a message to a specific connection.

        Args:
            connection_id: Target connection
            message: Message to send

        Returns:
            True if sent successfully
        """
        async with self._lock:
            conn = self._connections.get(connection_id)

        if not conn:
            return False

        try:
            await conn.websocket.send_text(message.to_json())
            return True
        except Exception as e:
            logger.error(f"Failed to send to {connection_id}: {e}")
            await self.disconnect(connection_id)
            return False

    async def broadcast(
        self,
        event_type: WSEventType,
        data: dict[str, Any],
    ) -> int:
        """
        Broadcast an event to all subscribed connections.

        Args:
            event_type: Type of event
            data: Event data

        Returns:
            Number of connections that received the message
        """
        message = WSMessage(type=event_type.value, data=data)

        # Get subscription types for this event
        target_subs = EVENT_SUBSCRIPTION_MAP.get(event_type, [SubscriptionType.ALL])

        async with self._lock:
            connections = list(self._connections.values())

        sent_count = 0
        failed_ids: list[str] = []

        for conn in connections:
            # Check if connection is subscribed to this event type
            if not conn.subscriptions.intersection(target_subs):
                continue

            try:
                await conn.websocket.send_text(message.to_json())
                sent_count += 1
            except Exception as e:
                logger.error(f"Failed to broadcast to {conn.id}: {e}")
                failed_ids.append(conn.id)

        # Clean up failed connections
        for conn_id in failed_ids:
            await self.disconnect(conn_id)

        return sent_count

    async def broadcast_to_subscription(
        self,
        subscription: SubscriptionType,
        message: WSMessage,
    ) -> int:
        """
        Broadcast a message to all connections with a specific subscription.

        Args:
            subscription: Target subscription type
            message: Message to send

        Returns:
            Number of connections that received the message
        """
        async with self._lock:
            connections = list(self._connections.values())

        sent_count = 0
        failed_ids: list[str] = []

        for conn in connections:
            if (
                subscription not in conn.subscriptions
                and SubscriptionType.ALL not in conn.subscriptions
            ):
                continue

            try:
                await conn.websocket.send_text(message.to_json())
                sent_count += 1
            except Exception as e:
                logger.error(f"Failed to send to {conn.id}: {e}")
                failed_ids.append(conn.id)

        for conn_id in failed_ids:
            await self.disconnect(conn_id)

        return sent_count

    async def broadcast_all(self, message: WSMessage) -> int:
        """
        Broadcast a message to ALL connections regardless of subscription.

        Args:
            message: Message to send

        Returns:
            Number of connections that received the message
        """
        async with self._lock:
            connections = list(self._connections.values())

        sent_count = 0
        failed_ids: list[str] = []

        for conn in connections:
            try:
                await conn.websocket.send_text(message.to_json())
                sent_count += 1
            except Exception as e:
                logger.error(f"Failed to send to {conn.id}: {e}")
                failed_ids.append(conn.id)

        for conn_id in failed_ids:
            await self.disconnect(conn_id)

        return sent_count

    async def update_subscriptions(
        self,
        connection_id: str,
        subscriptions: list[SubscriptionType],
    ) -> bool:
        """
        Update subscriptions for a connection.

        Args:
            connection_id: Connection to update
            subscriptions: New subscription list

        Returns:
            True if updated successfully
        """
        async with self._lock:
            if connection_id not in self._connections:
                return False

            self._connections[connection_id].subscriptions = set(subscriptions)
            return True

    def get_connection_count(self) -> int:
        """Get the number of active connections."""
        return len(self._connections)

    def get_subscription_counts(self) -> dict[str, int]:
        """Get count of connections per subscription type."""
        counts: dict[str, int] = {}
        for sub in SubscriptionType:
            counts[sub.value] = sum(
                1 for conn in self._connections.values() if sub in conn.subscriptions
            )
        return counts

    async def handle_client_message(
        self,
        connection_id: str,
        message: str,
        handler: Callable[[str, WSMessage], None] | None = None,
    ) -> None:
        """
        Handle an incoming message from a client.

        Args:
            connection_id: Source connection
            message: Raw message string
            handler: Optional callback for custom message handling
        """
        try:
            ws_message = WSMessage.from_json(message)

            # Handle ping/pong
            if ws_message.type == WSEventType.PING.value:
                await self.send_to_connection(
                    connection_id,
                    WSMessage(type=WSEventType.PONG.value, data={}),
                )
                return

            # Call custom handler if provided
            if handler:
                handler(connection_id, ws_message)

        except json.JSONDecodeError:
            logger.error(f"Invalid JSON from {connection_id}: {message}")
            await self.send_to_connection(
                connection_id,
                WSMessage(
                    type=WSEventType.ERROR.value,
                    data={"error": "Invalid JSON format"},
                ),
            )

    async def start_heartbeat(self) -> None:
        """Start the heartbeat task to keep connections alive."""
        if self._heartbeat_task is not None:
            return

        async def heartbeat_loop():
            while True:
                await asyncio.sleep(self._heartbeat_interval)
                await self.broadcast_all(WSMessage(type=WSEventType.PING.value, data={}))

        self._heartbeat_task = asyncio.create_task(heartbeat_loop())
        logger.info("WebSocket heartbeat started")

    async def stop_heartbeat(self) -> None:
        """Stop the heartbeat task."""
        if self._heartbeat_task is not None:
            self._heartbeat_task.cancel()
            self._heartbeat_task = None
            logger.info("WebSocket heartbeat stopped")


# Global WebSocket manager instance
_websocket_manager: WebSocketManager | None = None


def get_websocket_manager() -> WebSocketManager:
    """
    Get the global WebSocket manager instance.

    Returns:
        The global WebSocketManager instance
    """
    global _websocket_manager

    if _websocket_manager is None:
        _websocket_manager = WebSocketManager()

    return _websocket_manager

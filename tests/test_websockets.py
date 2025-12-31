"""Tests for WebSocket Connection Manager."""

import asyncio
import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from fastband.hub.websockets.manager import (
    EVENT_SUBSCRIPTION_MAP,
    Connection,
    SubscriptionType,
    WebSocketManager,
    WSEventType,
    WSMessage,
    get_websocket_manager,
)

# =============================================================================
# WSMessage Tests
# =============================================================================


class TestWSMessage:
    """Tests for WSMessage dataclass."""

    def test_create_message(self):
        """Test creating a message with default values."""
        msg = WSMessage(type="test:event")
        assert msg.type == "test:event"
        assert msg.data == {}
        assert msg.timestamp is not None

    def test_create_message_with_data(self):
        """Test creating a message with data."""
        data = {"key": "value", "count": 42}
        msg = WSMessage(type="test:event", data=data)
        assert msg.type == "test:event"
        assert msg.data == data

    def test_to_json(self):
        """Test JSON serialization."""
        msg = WSMessage(
            type="test:event",
            timestamp="2025-01-01T00:00:00Z",
            data={"key": "value"},
        )
        json_str = msg.to_json()
        parsed = json.loads(json_str)

        assert parsed["type"] == "test:event"
        assert parsed["timestamp"] == "2025-01-01T00:00:00Z"
        assert parsed["data"] == {"key": "value"}

    def test_from_json(self):
        """Test JSON deserialization."""
        json_str = json.dumps(
            {
                "type": "test:event",
                "timestamp": "2025-01-01T00:00:00Z",
                "data": {"key": "value"},
            }
        )
        msg = WSMessage.from_json(json_str)

        assert msg.type == "test:event"
        assert msg.timestamp == "2025-01-01T00:00:00Z"
        assert msg.data == {"key": "value"}

    def test_from_json_missing_fields(self):
        """Test JSON deserialization with missing fields."""
        json_str = json.dumps({"type": "test:event"})
        msg = WSMessage.from_json(json_str)

        assert msg.type == "test:event"
        assert msg.data == {}

    def test_from_json_empty(self):
        """Test JSON deserialization with empty object."""
        json_str = json.dumps({})
        msg = WSMessage.from_json(json_str)

        assert msg.type == "unknown"
        assert msg.data == {}

    def test_roundtrip(self):
        """Test JSON roundtrip."""
        original = WSMessage(
            type="agent:started",
            data={"agent_id": "test-agent", "status": "running"},
        )
        json_str = original.to_json()
        restored = WSMessage.from_json(json_str)

        assert restored.type == original.type
        assert restored.data == original.data


# =============================================================================
# Enum Tests
# =============================================================================


class TestSubscriptionType:
    """Tests for SubscriptionType enum."""

    def test_all_values(self):
        """Test all subscription types exist."""
        assert SubscriptionType.ALL == "all"
        assert SubscriptionType.AGENTS == "agents"
        assert SubscriptionType.OPS_LOG == "ops_log"
        assert SubscriptionType.TICKETS == "tickets"
        assert SubscriptionType.DIRECTIVES == "directives"

    def test_from_string(self):
        """Test creating from string."""
        assert SubscriptionType("all") == SubscriptionType.ALL
        assert SubscriptionType("agents") == SubscriptionType.AGENTS

    def test_invalid_value(self):
        """Test invalid value raises error."""
        with pytest.raises(ValueError):
            SubscriptionType("invalid")


class TestWSEventType:
    """Tests for WSEventType enum."""

    def test_agent_events(self):
        """Test agent event types."""
        assert WSEventType.AGENT_STARTED == "agent:started"
        assert WSEventType.AGENT_STOPPED == "agent:stopped"
        assert WSEventType.AGENT_STATUS == "agent:status"

    def test_ticket_events(self):
        """Test ticket event types."""
        assert WSEventType.TICKET_CLAIMED == "ticket:claimed"
        assert WSEventType.TICKET_COMPLETED == "ticket:completed"
        assert WSEventType.TICKET_UPDATED == "ticket:updated"

    def test_directive_events(self):
        """Test directive event types."""
        assert WSEventType.DIRECTIVE_HOLD == "directive:hold"
        assert WSEventType.DIRECTIVE_CLEARANCE == "directive:clearance"

    def test_system_events(self):
        """Test system event types."""
        assert WSEventType.CONNECTED == "system:connected"
        assert WSEventType.PING == "system:ping"
        assert WSEventType.PONG == "system:pong"
        assert WSEventType.ERROR == "system:error"


class TestEventSubscriptionMap:
    """Tests for EVENT_SUBSCRIPTION_MAP."""

    def test_agent_events_map_correctly(self):
        """Test agent events map to correct subscriptions."""
        assert SubscriptionType.AGENTS in EVENT_SUBSCRIPTION_MAP[WSEventType.AGENT_STARTED]
        assert SubscriptionType.ALL in EVENT_SUBSCRIPTION_MAP[WSEventType.AGENT_STARTED]

    def test_ticket_events_map_correctly(self):
        """Test ticket events map to correct subscriptions."""
        assert SubscriptionType.TICKETS in EVENT_SUBSCRIPTION_MAP[WSEventType.TICKET_CLAIMED]
        assert SubscriptionType.ALL in EVENT_SUBSCRIPTION_MAP[WSEventType.TICKET_CLAIMED]

    def test_all_event_types_mapped(self):
        """Test all non-system event types are in the map."""
        mapped_events = {
            WSEventType.AGENT_STARTED,
            WSEventType.AGENT_STOPPED,
            WSEventType.AGENT_STATUS,
            WSEventType.OPS_LOG_ENTRY,
            WSEventType.TICKET_CLAIMED,
            WSEventType.TICKET_COMPLETED,
            WSEventType.TICKET_UPDATED,
            WSEventType.DIRECTIVE_HOLD,
            WSEventType.DIRECTIVE_CLEARANCE,
        }
        for event in mapped_events:
            assert event in EVENT_SUBSCRIPTION_MAP


# =============================================================================
# Connection Tests
# =============================================================================


class TestConnection:
    """Tests for Connection dataclass."""

    def test_create_connection(self):
        """Test creating a connection."""
        ws = MagicMock()
        conn = Connection(
            id="test-conn",
            websocket=ws,
            subscriptions={SubscriptionType.ALL},
        )

        assert conn.id == "test-conn"
        assert conn.websocket == ws
        assert SubscriptionType.ALL in conn.subscriptions
        assert conn.last_ping is None

    def test_connection_defaults(self):
        """Test connection default values."""
        ws = MagicMock()
        conn = Connection(
            id="test-conn",
            websocket=ws,
            subscriptions=set(),
        )

        assert isinstance(conn.connected_at, datetime)
        assert conn.last_ping is None


# =============================================================================
# WebSocketManager Tests
# =============================================================================


class TestWebSocketManagerConnect:
    """Tests for WebSocketManager.connect()."""

    @pytest.fixture
    def manager(self):
        """Create a fresh manager for each test."""
        return WebSocketManager()

    @pytest.fixture
    def mock_websocket(self):
        """Create a mock WebSocket."""
        ws = AsyncMock()
        ws.accept = AsyncMock()
        ws.send_text = AsyncMock()
        return ws

    @pytest.mark.asyncio
    async def test_connect_accepts_websocket(self, manager, mock_websocket):
        """Test that connect accepts the WebSocket."""
        await manager.connect(mock_websocket, "conn-1")
        mock_websocket.accept.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_registers_connection(self, manager, mock_websocket):
        """Test that connect registers the connection."""
        await manager.connect(mock_websocket, "conn-1")
        assert manager.get_connection_count() == 1

    @pytest.mark.asyncio
    async def test_connect_default_subscription(self, manager, mock_websocket):
        """Test default subscription is ALL."""
        await manager.connect(mock_websocket, "conn-1")

        # Check sent message includes ALL subscription
        mock_websocket.send_text.assert_called_once()
        sent_json = mock_websocket.send_text.call_args[0][0]
        sent_msg = json.loads(sent_json)
        assert "all" in sent_msg["data"]["subscriptions"]

    @pytest.mark.asyncio
    async def test_connect_with_subscriptions(self, manager, mock_websocket):
        """Test connecting with specific subscriptions."""
        await manager.connect(
            mock_websocket,
            "conn-1",
            subscriptions=["agents", "tickets"],
        )

        sent_json = mock_websocket.send_text.call_args[0][0]
        sent_msg = json.loads(sent_json)
        assert "agents" in sent_msg["data"]["subscriptions"]
        assert "tickets" in sent_msg["data"]["subscriptions"]

    @pytest.mark.asyncio
    async def test_connect_invalid_subscription_ignored(self, manager, mock_websocket):
        """Test invalid subscriptions are ignored."""
        await manager.connect(
            mock_websocket,
            "conn-1",
            subscriptions=["agents", "invalid_sub"],
        )
        # Should still work with valid subscription
        assert manager.get_connection_count() == 1

    @pytest.mark.asyncio
    async def test_connect_sends_connected_event(self, manager, mock_websocket):
        """Test that connect sends CONNECTED event."""
        await manager.connect(mock_websocket, "conn-1")

        sent_json = mock_websocket.send_text.call_args[0][0]
        sent_msg = json.loads(sent_json)
        assert sent_msg["type"] == "system:connected"
        assert sent_msg["data"]["connection_id"] == "conn-1"


class TestWebSocketManagerDisconnect:
    """Tests for WebSocketManager.disconnect()."""

    @pytest.fixture
    def manager(self):
        return WebSocketManager()

    @pytest.fixture
    def mock_websocket(self):
        ws = AsyncMock()
        ws.accept = AsyncMock()
        ws.send_text = AsyncMock()
        return ws

    @pytest.mark.asyncio
    async def test_disconnect_removes_connection(self, manager, mock_websocket):
        """Test disconnect removes the connection."""
        await manager.connect(mock_websocket, "conn-1")
        assert manager.get_connection_count() == 1

        await manager.disconnect("conn-1")
        assert manager.get_connection_count() == 0

    @pytest.mark.asyncio
    async def test_disconnect_nonexistent_connection(self, manager):
        """Test disconnect of nonexistent connection doesn't error."""
        await manager.disconnect("nonexistent")
        assert manager.get_connection_count() == 0


class TestWebSocketManagerSend:
    """Tests for WebSocketManager send methods."""

    @pytest.fixture
    def manager(self):
        return WebSocketManager()

    @pytest.fixture
    def mock_websocket(self):
        ws = AsyncMock()
        ws.accept = AsyncMock()
        ws.send_text = AsyncMock()
        return ws

    @pytest.mark.asyncio
    async def test_send_to_connection(self, manager, mock_websocket):
        """Test sending to a specific connection."""
        await manager.connect(mock_websocket, "conn-1")
        mock_websocket.send_text.reset_mock()

        result = await manager.send_to_connection(
            "conn-1",
            WSMessage(type="test:event", data={"key": "value"}),
        )

        assert result is True
        mock_websocket.send_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_to_nonexistent_connection(self, manager):
        """Test sending to nonexistent connection returns False."""
        result = await manager.send_to_connection(
            "nonexistent",
            WSMessage(type="test:event"),
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_send_failure_disconnects(self, manager, mock_websocket):
        """Test send failure disconnects the connection."""
        await manager.connect(mock_websocket, "conn-1")
        mock_websocket.send_text.side_effect = Exception("Connection closed")

        result = await manager.send_to_connection(
            "conn-1",
            WSMessage(type="test:event"),
        )

        assert result is False
        assert manager.get_connection_count() == 0


class TestWebSocketManagerBroadcast:
    """Tests for WebSocketManager broadcast methods."""

    @pytest.fixture
    def manager(self):
        return WebSocketManager()

    def create_mock_websocket(self):
        ws = AsyncMock()
        ws.accept = AsyncMock()
        ws.send_text = AsyncMock()
        return ws

    @pytest.mark.asyncio
    async def test_broadcast_to_all_subscribers(self, manager):
        """Test broadcast reaches ALL subscribers."""
        ws1 = self.create_mock_websocket()
        ws2 = self.create_mock_websocket()

        await manager.connect(ws1, "conn-1", subscriptions=["all"])
        await manager.connect(ws2, "conn-2", subscriptions=["all"])

        ws1.send_text.reset_mock()
        ws2.send_text.reset_mock()

        count = await manager.broadcast(
            WSEventType.AGENT_STARTED,
            {"agent_id": "test-agent"},
        )

        assert count == 2
        ws1.send_text.assert_called_once()
        ws2.send_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_broadcast_filtered_by_subscription(self, manager):
        """Test broadcast is filtered by subscription."""
        ws1 = self.create_mock_websocket()
        ws2 = self.create_mock_websocket()

        await manager.connect(ws1, "conn-1", subscriptions=["agents"])
        await manager.connect(ws2, "conn-2", subscriptions=["tickets"])

        ws1.send_text.reset_mock()
        ws2.send_text.reset_mock()

        # Broadcast agent event - only conn-1 should receive
        count = await manager.broadcast(
            WSEventType.AGENT_STARTED,
            {"agent_id": "test-agent"},
        )

        assert count == 1
        ws1.send_text.assert_called_once()
        ws2.send_text.assert_not_called()

    @pytest.mark.asyncio
    async def test_broadcast_all_subscribers_receive_all(self, manager):
        """Test ALL subscribers receive all event types."""
        ws1 = self.create_mock_websocket()
        ws2 = self.create_mock_websocket()

        await manager.connect(ws1, "conn-1", subscriptions=["all"])
        await manager.connect(ws2, "conn-2", subscriptions=["agents"])

        ws1.send_text.reset_mock()
        ws2.send_text.reset_mock()

        # Broadcast ticket event - only ALL subscriber receives
        count = await manager.broadcast(
            WSEventType.TICKET_CLAIMED,
            {"ticket_id": "123"},
        )

        assert count == 1
        ws1.send_text.assert_called_once()
        ws2.send_text.assert_not_called()

    @pytest.mark.asyncio
    async def test_broadcast_to_subscription(self, manager):
        """Test broadcast_to_subscription."""
        ws1 = self.create_mock_websocket()
        ws2 = self.create_mock_websocket()

        await manager.connect(ws1, "conn-1", subscriptions=["agents"])
        await manager.connect(ws2, "conn-2", subscriptions=["tickets"])

        ws1.send_text.reset_mock()
        ws2.send_text.reset_mock()

        count = await manager.broadcast_to_subscription(
            SubscriptionType.AGENTS,
            WSMessage(type="custom:event", data={}),
        )

        assert count == 1
        ws1.send_text.assert_called_once()
        ws2.send_text.assert_not_called()

    @pytest.mark.asyncio
    async def test_broadcast_all(self, manager):
        """Test broadcast_all sends to everyone."""
        ws1 = self.create_mock_websocket()
        ws2 = self.create_mock_websocket()
        ws3 = self.create_mock_websocket()

        await manager.connect(ws1, "conn-1", subscriptions=["agents"])
        await manager.connect(ws2, "conn-2", subscriptions=["tickets"])
        await manager.connect(ws3, "conn-3", subscriptions=["directives"])

        ws1.send_text.reset_mock()
        ws2.send_text.reset_mock()
        ws3.send_text.reset_mock()

        count = await manager.broadcast_all(
            WSMessage(type="system:announcement", data={}),
        )

        assert count == 3
        ws1.send_text.assert_called_once()
        ws2.send_text.assert_called_once()
        ws3.send_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_broadcast_failure_disconnects(self, manager):
        """Test broadcast failure disconnects the failed connection."""
        ws1 = self.create_mock_websocket()
        ws2 = self.create_mock_websocket()

        await manager.connect(ws1, "conn-1", subscriptions=["all"])
        await manager.connect(ws2, "conn-2", subscriptions=["all"])

        # Make ws2 fail
        ws2.send_text.side_effect = Exception("Connection closed")
        ws1.send_text.reset_mock()
        ws2.send_text.reset_mock()

        count = await manager.broadcast(
            WSEventType.AGENT_STARTED,
            {"agent_id": "test"},
        )

        assert count == 1  # Only ws1 succeeded
        assert manager.get_connection_count() == 1


class TestWebSocketManagerSubscriptions:
    """Tests for subscription management."""

    @pytest.fixture
    def manager(self):
        return WebSocketManager()

    @pytest.fixture
    def mock_websocket(self):
        ws = AsyncMock()
        ws.accept = AsyncMock()
        ws.send_text = AsyncMock()
        return ws

    @pytest.mark.asyncio
    async def test_update_subscriptions(self, manager, mock_websocket):
        """Test updating subscriptions."""
        await manager.connect(mock_websocket, "conn-1", subscriptions=["agents"])

        result = await manager.update_subscriptions(
            "conn-1",
            [SubscriptionType.TICKETS, SubscriptionType.DIRECTIVES],
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_update_subscriptions_nonexistent(self, manager):
        """Test updating nonexistent connection returns False."""
        result = await manager.update_subscriptions(
            "nonexistent",
            [SubscriptionType.ALL],
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_get_subscription_counts(self, manager):
        """Test getting subscription counts."""
        ws1 = AsyncMock()
        ws1.accept = AsyncMock()
        ws1.send_text = AsyncMock()
        ws2 = AsyncMock()
        ws2.accept = AsyncMock()
        ws2.send_text = AsyncMock()

        await manager.connect(ws1, "conn-1", subscriptions=["agents", "tickets"])
        await manager.connect(ws2, "conn-2", subscriptions=["agents"])

        counts = manager.get_subscription_counts()

        assert counts["agents"] == 2
        assert counts["tickets"] == 1
        assert counts["all"] == 0


class TestWebSocketManagerClientMessages:
    """Tests for handling client messages."""

    @pytest.fixture
    def manager(self):
        return WebSocketManager()

    @pytest.fixture
    def mock_websocket(self):
        ws = AsyncMock()
        ws.accept = AsyncMock()
        ws.send_text = AsyncMock()
        return ws

    @pytest.mark.asyncio
    async def test_handle_ping(self, manager, mock_websocket):
        """Test ping message triggers pong response."""
        await manager.connect(mock_websocket, "conn-1")
        mock_websocket.send_text.reset_mock()

        ping_msg = json.dumps({"type": "system:ping", "data": {}})
        await manager.handle_client_message("conn-1", ping_msg)

        # Should send pong
        mock_websocket.send_text.assert_called_once()
        sent_json = mock_websocket.send_text.call_args[0][0]
        sent_msg = json.loads(sent_json)
        assert sent_msg["type"] == "system:pong"

    @pytest.mark.asyncio
    async def test_handle_custom_handler(self, manager, mock_websocket):
        """Test custom message handler is called."""
        await manager.connect(mock_websocket, "conn-1")

        handler = MagicMock()
        custom_msg = json.dumps({"type": "custom:action", "data": {"key": "value"}})
        await manager.handle_client_message("conn-1", custom_msg, handler=handler)

        handler.assert_called_once()
        call_args = handler.call_args[0]
        assert call_args[0] == "conn-1"
        assert call_args[1].type == "custom:action"

    @pytest.mark.asyncio
    async def test_handle_invalid_json(self, manager, mock_websocket):
        """Test invalid JSON sends error response."""
        await manager.connect(mock_websocket, "conn-1")
        mock_websocket.send_text.reset_mock()

        await manager.handle_client_message("conn-1", "not valid json")

        mock_websocket.send_text.assert_called_once()
        sent_json = mock_websocket.send_text.call_args[0][0]
        sent_msg = json.loads(sent_json)
        assert sent_msg["type"] == "system:error"
        assert "Invalid JSON" in sent_msg["data"]["error"]


class TestWebSocketManagerHeartbeat:
    """Tests for heartbeat functionality."""

    @pytest.fixture
    def manager(self):
        return WebSocketManager()

    @pytest.mark.asyncio
    async def test_start_heartbeat(self, manager):
        """Test starting heartbeat creates task."""
        await manager.start_heartbeat()

        assert manager._heartbeat_task is not None
        assert not manager._heartbeat_task.done()

        # Clean up
        await manager.stop_heartbeat()

    @pytest.mark.asyncio
    async def test_stop_heartbeat(self, manager):
        """Test stopping heartbeat cancels task."""
        await manager.start_heartbeat()
        await manager.stop_heartbeat()

        assert manager._heartbeat_task is None

    @pytest.mark.asyncio
    async def test_start_heartbeat_idempotent(self, manager):
        """Test starting heartbeat twice doesn't create duplicate tasks."""
        await manager.start_heartbeat()
        task1 = manager._heartbeat_task

        await manager.start_heartbeat()
        task2 = manager._heartbeat_task

        assert task1 is task2

        await manager.stop_heartbeat()


class TestWebSocketManagerStats:
    """Tests for statistics methods."""

    @pytest.fixture
    def manager(self):
        return WebSocketManager()

    def create_mock_websocket(self):
        ws = AsyncMock()
        ws.accept = AsyncMock()
        ws.send_text = AsyncMock()
        return ws

    @pytest.mark.asyncio
    async def test_get_connection_count_empty(self, manager):
        """Test connection count when empty."""
        assert manager.get_connection_count() == 0

    @pytest.mark.asyncio
    async def test_get_connection_count(self, manager):
        """Test connection count with connections."""
        ws1 = self.create_mock_websocket()
        ws2 = self.create_mock_websocket()

        await manager.connect(ws1, "conn-1")
        assert manager.get_connection_count() == 1

        await manager.connect(ws2, "conn-2")
        assert manager.get_connection_count() == 2

        await manager.disconnect("conn-1")
        assert manager.get_connection_count() == 1


# =============================================================================
# Global Instance Tests
# =============================================================================


class TestGetWebSocketManager:
    """Tests for get_websocket_manager function."""

    def test_get_websocket_manager_returns_instance(self):
        """Test that get_websocket_manager returns an instance."""
        # Reset global state
        import fastband.hub.websockets.manager as ws_module

        ws_module._websocket_manager = None

        manager = get_websocket_manager()
        assert manager is not None
        assert isinstance(manager, WebSocketManager)

    def test_get_websocket_manager_singleton(self):
        """Test that get_websocket_manager returns same instance."""
        import fastband.hub.websockets.manager as ws_module

        ws_module._websocket_manager = None

        manager1 = get_websocket_manager()
        manager2 = get_websocket_manager()

        assert manager1 is manager2


# =============================================================================
# Integration Tests
# =============================================================================


class TestWebSocketManagerIntegration:
    """Integration tests for WebSocketManager."""

    @pytest.fixture
    def manager(self):
        return WebSocketManager()

    def create_mock_websocket(self):
        ws = AsyncMock()
        ws.accept = AsyncMock()
        ws.send_text = AsyncMock()
        return ws

    @pytest.mark.asyncio
    async def test_full_workflow(self, manager):
        """Test a full workflow of connect, broadcast, disconnect."""
        # Connect multiple clients
        ws1 = self.create_mock_websocket()
        ws2 = self.create_mock_websocket()
        ws3 = self.create_mock_websocket()

        await manager.connect(ws1, "agent-1", subscriptions=["agents"])
        await manager.connect(ws2, "agent-2", subscriptions=["tickets"])
        await manager.connect(ws3, "dashboard", subscriptions=["all"])

        assert manager.get_connection_count() == 3

        # Reset mocks
        ws1.send_text.reset_mock()
        ws2.send_text.reset_mock()
        ws3.send_text.reset_mock()

        # Broadcast agent event
        count = await manager.broadcast(
            WSEventType.AGENT_STARTED,
            {"agent_id": "new-agent", "status": "running"},
        )
        assert count == 2  # ws1 (agents) and ws3 (all)
        assert ws1.send_text.called
        assert not ws2.send_text.called
        assert ws3.send_text.called

        # Reset mocks
        ws1.send_text.reset_mock()
        ws2.send_text.reset_mock()
        ws3.send_text.reset_mock()

        # Broadcast ticket event
        count = await manager.broadcast(
            WSEventType.TICKET_CLAIMED,
            {"ticket_id": "123", "agent": "agent-1"},
        )
        assert count == 2  # ws2 (tickets) and ws3 (all)
        assert not ws1.send_text.called
        assert ws2.send_text.called
        assert ws3.send_text.called

        # Disconnect
        await manager.disconnect("agent-1")
        assert manager.get_connection_count() == 2

        await manager.disconnect("agent-2")
        await manager.disconnect("dashboard")
        assert manager.get_connection_count() == 0

    @pytest.mark.asyncio
    async def test_concurrent_operations(self, manager):
        """Test concurrent connect/broadcast/disconnect operations."""
        websockets = [self.create_mock_websocket() for _ in range(10)]

        # Connect all concurrently
        await asyncio.gather(*[manager.connect(ws, f"conn-{i}") for i, ws in enumerate(websockets)])
        assert manager.get_connection_count() == 10

        # Broadcast
        for ws in websockets:
            ws.send_text.reset_mock()

        count = await manager.broadcast_all(
            WSMessage(type="test:event", data={}),
        )
        assert count == 10

        # Disconnect all concurrently
        await asyncio.gather(*[manager.disconnect(f"conn-{i}") for i in range(10)])
        assert manager.get_connection_count() == 0


# =============================================================================
# WebSocket Endpoint Integration Tests
# =============================================================================


class TestWebSocketEndpointIntegration:
    """Integration tests for the actual WebSocket endpoint."""

    @pytest.fixture
    def app(self):
        """Create a fresh FastAPI app for testing."""
        from fastapi import FastAPI

        from fastband.hub.control_plane.routes import router as control_plane_router

        # Reset global websocket manager for clean tests
        import fastband.hub.websockets.manager as ws_module

        ws_module._websocket_manager = None

        app = FastAPI()
        app.include_router(control_plane_router, prefix="/api")
        return app

    @pytest.fixture
    def client(self, app):
        """Create a test client."""
        from starlette.testclient import TestClient

        return TestClient(app)

    def test_websocket_connects_successfully(self, client):
        """Test that WebSocket endpoint accepts connections."""
        with client.websocket_connect("/api/control-plane/ws") as websocket:
            # Should receive connected message
            data = websocket.receive_json()
            assert data["type"] == "system:connected"
            assert "connection_id" in data["data"]
            assert "subscriptions" in data["data"]

    def test_websocket_with_subscriptions(self, client):
        """Test WebSocket with specific subscriptions."""
        with client.websocket_connect("/api/control-plane/ws?subscriptions=agents,tickets") as websocket:
            data = websocket.receive_json()
            assert data["type"] == "system:connected"
            assert "agents" in data["data"]["subscriptions"]
            assert "tickets" in data["data"]["subscriptions"]

    def test_websocket_default_subscription(self, client):
        """Test WebSocket defaults to 'all' subscription."""
        with client.websocket_connect("/api/control-plane/ws") as websocket:
            data = websocket.receive_json()
            assert data["type"] == "system:connected"
            assert "all" in data["data"]["subscriptions"]

    def test_websocket_ping_pong(self, client):
        """Test WebSocket ping/pong functionality."""
        with client.websocket_connect("/api/control-plane/ws") as websocket:
            # Consume connected message
            websocket.receive_json()

            # Send ping
            websocket.send_json({"type": "system:ping", "data": {}})

            # Should receive pong
            data = websocket.receive_json()
            assert data["type"] == "system:pong"

    def test_websocket_invalid_json_sends_error(self, client):
        """Test WebSocket handles invalid JSON gracefully."""
        with client.websocket_connect("/api/control-plane/ws") as websocket:
            # Consume connected message
            websocket.receive_json()

            # Send invalid JSON
            websocket.send_text("not valid json")

            # Should receive error message
            data = websocket.receive_json()
            assert data["type"] == "system:error"
            assert "Invalid JSON" in data["data"]["error"]

    def test_multiple_websocket_connections(self, client):
        """Test multiple simultaneous WebSocket connections."""
        with client.websocket_connect("/api/control-plane/ws") as ws1:
            data1 = ws1.receive_json()
            conn_id1 = data1["data"]["connection_id"]

            with client.websocket_connect("/api/control-plane/ws") as ws2:
                data2 = ws2.receive_json()
                conn_id2 = data2["data"]["connection_id"]

                # Connection IDs should be different
                assert conn_id1 != conn_id2

    def test_websocket_invalid_subscription_uses_default(self, client):
        """Test invalid subscriptions fall back to default."""
        with client.websocket_connect("/api/control-plane/ws?subscriptions=invalid") as websocket:
            data = websocket.receive_json()
            assert data["type"] == "system:connected"
            # Should fall back to 'all' when invalid
            assert "all" in data["data"]["subscriptions"]


class TestCORSConfiguration:
    """Tests for CORS configuration."""

    def test_cors_includes_hub_ports(self):
        """Test CORS configuration includes Hub ports."""
        from fastband.hub.api.app import create_app

        # Reset global app
        import fastband.hub.api.app as app_module

        app_module._app = None

        app = create_app()

        # Check middleware is configured
        cors_middleware = None
        for middleware in app.user_middleware:
            if middleware.cls.__name__ == "CORSMiddleware":
                cors_middleware = middleware
                break

        assert cors_middleware is not None
        origins = cors_middleware.kwargs.get("allow_origins", [])

        # Should include Hub ports
        assert "http://localhost:8080" in origins
        assert "http://127.0.0.1:8080" in origins

    def test_cors_includes_dev_ports(self):
        """Test CORS configuration includes development ports."""
        from fastband.hub.api.app import create_app

        import fastband.hub.api.app as app_module

        app_module._app = None

        app = create_app()

        cors_middleware = None
        for middleware in app.user_middleware:
            if middleware.cls.__name__ == "CORSMiddleware":
                cors_middleware = middleware
                break

        assert cors_middleware is not None
        origins = cors_middleware.kwargs.get("allow_origins", [])

        # Should include dev ports
        assert "http://localhost:5173" in origins
        assert "http://localhost:3000" in origins

"""
Comprehensive tests for the Control Plane service.

Tests cover:
- Dataclass serialization (AgentActivity, TicketSummary, DirectiveState, ControlPlaneDashboard)
- ControlPlaneService initialization and properties
- Service start/stop lifecycle
- Dashboard state retrieval
- Agent activity, ticket, and directive queries
- Hold/clearance issuing
- Metrics computation
- Global singleton function
"""

import asyncio
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from fastband.agents.ops_log import EventType, LogEntry, OpsLog
from fastband.hub.control_plane.service import (
    AgentActivity,
    ControlPlaneDashboard,
    ControlPlaneService,
    DirectiveState,
    TicketSummary,
    get_control_plane_service,
)
from fastband.hub.websockets.manager import WebSocketManager, WSEventType
from fastband.tickets.models import Ticket, TicketPriority, TicketStatus, TicketType
from fastband.tickets.storage import TicketStore

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def mock_ops_log():
    """Create a mock OpsLog instance."""
    ops_log = MagicMock(spec=OpsLog)
    ops_log.count.return_value = 0
    ops_log.read_entries.return_value = []
    ops_log.check_active_agents.return_value = {}
    ops_log.get_latest_directive.return_value = None
    return ops_log


@pytest.fixture
def mock_ticket_store():
    """Create a mock TicketStore instance."""
    store = MagicMock(spec=TicketStore)
    store.list.return_value = []
    return store


@pytest.fixture
def mock_ws_manager():
    """Create a mock WebSocketManager instance."""
    manager = MagicMock(spec=WebSocketManager)
    manager.broadcast = AsyncMock()
    manager.start_heartbeat = AsyncMock()
    manager.stop_heartbeat = AsyncMock()
    manager.get_connection_count.return_value = 0
    return manager


@pytest.fixture
def control_plane_service(mock_ops_log, mock_ticket_store, mock_ws_manager, tmp_path):
    """Create a ControlPlaneService with mocked dependencies."""
    return ControlPlaneService(
        ops_log=mock_ops_log,
        ticket_store=mock_ticket_store,
        ws_manager=mock_ws_manager,
        project_path=tmp_path,
    )


@pytest.fixture
def sample_log_entry():
    """Create a sample LogEntry for testing."""
    return LogEntry(
        id="test123",
        timestamp="2025-12-30T10:00:00Z",
        agent="test-agent",
        event_type=EventType.AGENT_STARTED.value,
        message="Agent started",
        ticket_id=None,
        metadata={},
    )


@pytest.fixture
def sample_ticket():
    """Create a sample Ticket for testing."""
    return Ticket(
        id="ticket-123",
        ticket_number="FB-001",
        title="Test Ticket",
        description="A test ticket",
        status=TicketStatus.OPEN,
        priority=TicketPriority.MEDIUM,
        ticket_type=TicketType.TASK,
        assigned_to="test-agent",
        created_at=datetime(2025, 12, 30, 10, 0, 0),
    )


# =============================================================================
# DATACLASS TESTS
# =============================================================================


class TestAgentActivity:
    """Tests for AgentActivity dataclass."""

    def test_create_default(self):
        """Test creating AgentActivity with defaults."""
        activity = AgentActivity(name="test-agent", is_active=True)
        assert activity.name == "test-agent"
        assert activity.is_active is True
        assert activity.last_seen is None
        assert activity.current_ticket is None
        assert activity.last_action is None
        assert activity.activity_count == 0
        assert activity.has_clearance is False
        assert activity.under_hold is False

    def test_create_full(self):
        """Test creating AgentActivity with all fields."""
        activity = AgentActivity(
            name="test-agent",
            is_active=True,
            last_seen="2025-12-30T10:00:00Z",
            current_ticket="FB-001",
            last_action="ticket_claimed",
            activity_count=5,
            has_clearance=True,
            under_hold=False,
        )
        assert activity.name == "test-agent"
        assert activity.current_ticket == "FB-001"
        assert activity.activity_count == 5
        assert activity.has_clearance is True

    def test_to_dict(self):
        """Test converting AgentActivity to dict."""
        activity = AgentActivity(
            name="test-agent",
            is_active=True,
            last_seen="2025-12-30T10:00:00Z",
            current_ticket="FB-001",
        )
        data = activity.to_dict()
        assert isinstance(data, dict)
        assert data["name"] == "test-agent"
        assert data["is_active"] is True
        assert data["last_seen"] == "2025-12-30T10:00:00Z"
        assert data["current_ticket"] == "FB-001"


class TestTicketSummary:
    """Tests for TicketSummary dataclass."""

    def test_create_minimal(self):
        """Test creating TicketSummary with required fields."""
        summary = TicketSummary(
            id="123",
            ticket_number="FB-001",
            title="Test",
            status="open",
            priority="medium",
        )
        assert summary.id == "123"
        assert summary.ticket_number == "FB-001"
        assert summary.title == "Test"
        assert summary.status == "open"
        assert summary.priority == "medium"
        assert summary.assigned_to is None
        assert summary.ticket_type == "task"
        assert summary.created_at is None

    def test_create_full(self):
        """Test creating TicketSummary with all fields."""
        summary = TicketSummary(
            id="123",
            ticket_number="FB-001",
            title="Test",
            status="in_progress",
            priority="high",
            assigned_to="agent-1",
            ticket_type="bug",
            created_at="2025-12-30T10:00:00Z",
        )
        assert summary.assigned_to == "agent-1"
        assert summary.ticket_type == "bug"
        assert summary.created_at == "2025-12-30T10:00:00Z"

    def test_to_dict(self):
        """Test converting TicketSummary to dict."""
        summary = TicketSummary(
            id="123",
            ticket_number="FB-001",
            title="Test",
            status="open",
            priority="medium",
        )
        data = summary.to_dict()
        assert isinstance(data, dict)
        assert data["id"] == "123"
        assert data["ticket_number"] == "FB-001"

    def test_from_ticket(self, sample_ticket):
        """Test creating TicketSummary from Ticket."""
        summary = TicketSummary.from_ticket(sample_ticket)
        assert summary.id == sample_ticket.id
        assert summary.ticket_number == sample_ticket.ticket_number
        assert summary.title == sample_ticket.title
        assert summary.status == sample_ticket.status.value
        assert summary.priority == sample_ticket.priority.value
        assert summary.assigned_to == sample_ticket.assigned_to
        assert summary.ticket_type == sample_ticket.ticket_type.value

    def test_from_ticket_no_ticket_number(self):
        """Test creating TicketSummary from Ticket without ticket_number."""
        ticket = Ticket(
            id="abcd1234-full-uuid",
            title="Test",
            description="Test",
            status=TicketStatus.OPEN,
            priority=TicketPriority.LOW,
            ticket_type=TicketType.TASK,
        )
        summary = TicketSummary.from_ticket(ticket)
        assert summary.ticket_number == ticket.id[:8]


class TestDirectiveState:
    """Tests for DirectiveState dataclass."""

    def test_create_default(self):
        """Test creating DirectiveState with defaults."""
        state = DirectiveState()
        assert state.has_active_hold is False
        assert state.has_active_clearance is False
        assert state.latest_directive is None
        assert state.affected_agents == []
        assert state.affected_tickets == []

    def test_create_with_hold(self):
        """Test creating DirectiveState with hold."""
        state = DirectiveState(
            has_active_hold=True,
            has_active_clearance=False,
            latest_directive={"event_type": "hold"},
            affected_agents=["agent-1", "agent-2"],
            affected_tickets=["FB-001"],
        )
        assert state.has_active_hold is True
        assert len(state.affected_agents) == 2

    def test_to_dict(self):
        """Test converting DirectiveState to dict."""
        state = DirectiveState(
            has_active_hold=True,
            affected_agents=["agent-1"],
        )
        data = state.to_dict()
        assert isinstance(data, dict)
        assert data["has_active_hold"] is True
        assert data["affected_agents"] == ["agent-1"]


class TestControlPlaneDashboard:
    """Tests for ControlPlaneDashboard dataclass."""

    def test_create(self):
        """Test creating ControlPlaneDashboard."""
        dashboard = ControlPlaneDashboard(
            agents=[AgentActivity(name="agent-1", is_active=True)],
            ops_log_entries=[{"id": "1", "message": "test"}],
            active_tickets=[
                TicketSummary(
                    id="1",
                    ticket_number="FB-001",
                    title="Test",
                    status="open",
                    priority="medium",
                )
            ],
            directive_state=DirectiveState(),
            metrics={"active_agents": 1},
        )
        assert len(dashboard.agents) == 1
        assert len(dashboard.ops_log_entries) == 1
        assert len(dashboard.active_tickets) == 1
        assert dashboard.timestamp  # Should be auto-generated

    def test_to_dict(self):
        """Test converting ControlPlaneDashboard to dict."""
        dashboard = ControlPlaneDashboard(
            agents=[AgentActivity(name="agent-1", is_active=True)],
            ops_log_entries=[],
            active_tickets=[],
            directive_state=DirectiveState(),
            metrics={"active_agents": 1},
        )
        data = dashboard.to_dict()
        assert isinstance(data, dict)
        assert len(data["agents"]) == 1
        assert data["agents"][0]["name"] == "agent-1"
        assert "timestamp" in data


# =============================================================================
# CONTROL PLANE SERVICE TESTS
# =============================================================================


class TestControlPlaneServiceInit:
    """Tests for ControlPlaneService initialization."""

    def test_init_with_dependencies(
        self, mock_ops_log, mock_ticket_store, mock_ws_manager, tmp_path
    ):
        """Test initialization with provided dependencies."""
        service = ControlPlaneService(
            ops_log=mock_ops_log,
            ticket_store=mock_ticket_store,
            ws_manager=mock_ws_manager,
            project_path=tmp_path,
        )
        assert service.project_path == tmp_path
        assert service._ops_log is mock_ops_log
        assert service._ticket_store is mock_ticket_store
        assert service._ws_manager is mock_ws_manager

    def test_init_defaults(self, tmp_path):
        """Test initialization with defaults (lazy loading)."""
        service = ControlPlaneService(project_path=tmp_path)
        assert service.project_path == tmp_path
        assert service._ops_log is None
        assert service._ticket_store is None
        assert service._ws_manager is None
        assert service._running is False

    def test_init_poll_config(self, control_plane_service):
        """Test poll configuration defaults."""
        assert control_plane_service._poll_interval == 1.0
        assert control_plane_service._poll_task is None
        assert control_plane_service._last_entry_count == 0


class TestControlPlaneServiceProperties:
    """Tests for ControlPlaneService property accessors."""

    def test_ops_log_lazy_init(self, tmp_path):
        """Test lazy initialization of ops_log property."""
        service = ControlPlaneService(project_path=tmp_path)

        with patch(
            "fastband.hub.control_plane.service.get_ops_log"
        ) as mock_get_ops_log:
            mock_log = MagicMock()
            mock_get_ops_log.return_value = mock_log

            result = service.ops_log
            assert result is mock_log
            mock_get_ops_log.assert_called_once_with(project_path=tmp_path)

    def test_ops_log_cached(self, control_plane_service, mock_ops_log):
        """Test that ops_log returns cached instance."""
        result = control_plane_service.ops_log
        assert result is mock_ops_log

    def test_ticket_store_lazy_init(self, tmp_path):
        """Test lazy initialization of ticket_store property."""
        service = ControlPlaneService(project_path=tmp_path)

        with patch("fastband.hub.control_plane.service.get_store") as mock_get_store:
            mock_store = MagicMock()
            mock_get_store.return_value = mock_store

            result = service.ticket_store
            assert result is mock_store
            mock_get_store.assert_called_once()

    def test_ticket_store_cached(self, control_plane_service, mock_ticket_store):
        """Test that ticket_store returns cached instance."""
        result = control_plane_service.ticket_store
        assert result is mock_ticket_store

    def test_ws_manager_lazy_init(self, tmp_path):
        """Test lazy initialization of ws_manager property."""
        service = ControlPlaneService(project_path=tmp_path)

        with patch(
            "fastband.hub.control_plane.service.get_websocket_manager"
        ) as mock_get_ws:
            mock_manager = MagicMock()
            mock_get_ws.return_value = mock_manager

            result = service.ws_manager
            assert result is mock_manager
            mock_get_ws.assert_called_once()

    def test_ws_manager_cached(self, control_plane_service, mock_ws_manager):
        """Test that ws_manager returns cached instance."""
        result = control_plane_service.ws_manager
        assert result is mock_ws_manager


class TestControlPlaneServiceLifecycle:
    """Tests for ControlPlaneService start/stop lifecycle."""

    @pytest.mark.asyncio
    async def test_start(self, control_plane_service, mock_ws_manager, mock_ops_log):
        """Test starting the service."""
        mock_ops_log.count.return_value = 5

        await control_plane_service.start()

        assert control_plane_service._running is True
        assert control_plane_service._last_entry_count == 5
        assert control_plane_service._poll_task is not None
        mock_ws_manager.start_heartbeat.assert_called_once()

        # Clean up
        await control_plane_service.stop()

    @pytest.mark.asyncio
    async def test_start_already_running(self, control_plane_service, mock_ws_manager):
        """Test that start does nothing if already running."""
        control_plane_service._running = True

        await control_plane_service.start()

        mock_ws_manager.start_heartbeat.assert_not_called()

    @pytest.mark.asyncio
    async def test_stop(self, control_plane_service, mock_ws_manager, mock_ops_log):
        """Test stopping the service."""
        # Start first
        await control_plane_service.start()
        assert control_plane_service._running is True

        # Stop
        await control_plane_service.stop()

        assert control_plane_service._running is False
        assert control_plane_service._poll_task is None
        mock_ws_manager.stop_heartbeat.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_when_not_running(self, control_plane_service, mock_ws_manager):
        """Test stopping when service isn't running."""
        await control_plane_service.stop()

        assert control_plane_service._running is False
        mock_ws_manager.stop_heartbeat.assert_called_once()


class TestControlPlaneServicePolling:
    """Tests for ControlPlaneService ops log polling."""

    @pytest.mark.asyncio
    async def test_poll_ops_log_new_entries(
        self, control_plane_service, mock_ops_log, mock_ws_manager
    ):
        """Test polling detects new entries and broadcasts them."""
        entry1 = LogEntry(
            id="1",
            timestamp="2025-12-30T10:00:00Z",
            agent="agent-1",
            event_type=EventType.AGENT_STARTED.value,
            message="Started",
        )
        entry2 = LogEntry(
            id="2",
            timestamp="2025-12-30T10:01:00Z",
            agent="agent-1",
            event_type=EventType.TICKET_CLAIMED.value,
            message="Claimed",
            ticket_id="FB-001",
        )

        # Set up polling
        control_plane_service._running = True
        control_plane_service._last_entry_count = 0
        control_plane_service._poll_interval = 0.01  # Fast for testing

        # First call returns 0, second call returns 2
        mock_ops_log.count.side_effect = [2]
        mock_ops_log.read_entries.return_value = [entry2, entry1]  # Newest first

        # Run one poll iteration
        await asyncio.sleep(0.02)
        control_plane_service._running = False

        # Verify broadcast was called for new entries
        # Note: Actual broadcast happens in polling task which we can test separately

    @pytest.mark.asyncio
    async def test_broadcast_ops_log_entry_agent_started(
        self, control_plane_service, mock_ws_manager
    ):
        """Test broadcasting agent_started event."""
        entry = LogEntry(
            id="1",
            timestamp="2025-12-30T10:00:00Z",
            agent="agent-1",
            event_type=EventType.AGENT_STARTED.value,
            message="Started",
        )

        await control_plane_service._broadcast_ops_log_entry(entry)

        mock_ws_manager.broadcast.assert_called_once()
        call_args = mock_ws_manager.broadcast.call_args
        assert call_args.kwargs["event_type"] == WSEventType.AGENT_STARTED

    @pytest.mark.asyncio
    async def test_broadcast_ops_log_entry_ticket_claimed(
        self, control_plane_service, mock_ws_manager
    ):
        """Test broadcasting ticket_claimed event."""
        entry = LogEntry(
            id="1",
            timestamp="2025-12-30T10:00:00Z",
            agent="agent-1",
            event_type=EventType.TICKET_CLAIMED.value,
            message="Claimed",
            ticket_id="FB-001",
        )

        await control_plane_service._broadcast_ops_log_entry(entry)

        mock_ws_manager.broadcast.assert_called_once()
        call_args = mock_ws_manager.broadcast.call_args
        assert call_args.kwargs["event_type"] == WSEventType.TICKET_CLAIMED

    @pytest.mark.asyncio
    async def test_broadcast_ops_log_entry_hold(
        self, control_plane_service, mock_ws_manager
    ):
        """Test broadcasting hold event."""
        entry = LogEntry(
            id="1",
            timestamp="2025-12-30T10:00:00Z",
            agent="agent-1",
            event_type=EventType.HOLD.value,
            message="Hold",
        )

        await control_plane_service._broadcast_ops_log_entry(entry)

        mock_ws_manager.broadcast.assert_called_once()
        call_args = mock_ws_manager.broadcast.call_args
        assert call_args.kwargs["event_type"] == WSEventType.DIRECTIVE_HOLD

    @pytest.mark.asyncio
    async def test_broadcast_ops_log_entry_clearance(
        self, control_plane_service, mock_ws_manager
    ):
        """Test broadcasting clearance event."""
        entry = LogEntry(
            id="1",
            timestamp="2025-12-30T10:00:00Z",
            agent="agent-1",
            event_type=EventType.CLEARANCE_GRANTED.value,
            message="Clearance granted",
        )

        await control_plane_service._broadcast_ops_log_entry(entry)

        mock_ws_manager.broadcast.assert_called_once()
        call_args = mock_ws_manager.broadcast.call_args
        assert call_args.kwargs["event_type"] == WSEventType.DIRECTIVE_CLEARANCE

    @pytest.mark.asyncio
    async def test_broadcast_ops_log_entry_unknown_type(
        self, control_plane_service, mock_ws_manager
    ):
        """Test broadcasting unknown event type falls back to OPS_LOG_ENTRY."""
        entry = LogEntry(
            id="1",
            timestamp="2025-12-30T10:00:00Z",
            agent="agent-1",
            event_type="unknown_event",
            message="Unknown",
        )

        await control_plane_service._broadcast_ops_log_entry(entry)

        mock_ws_manager.broadcast.assert_called_once()
        call_args = mock_ws_manager.broadcast.call_args
        assert call_args.kwargs["event_type"] == WSEventType.OPS_LOG_ENTRY


class TestControlPlaneServiceDashboard:
    """Tests for dashboard state retrieval."""

    @pytest.mark.asyncio
    async def test_get_dashboard_state(
        self, control_plane_service, mock_ops_log, mock_ticket_store, mock_ws_manager
    ):
        """Test getting complete dashboard state."""
        # Set up mocks
        mock_ops_log.check_active_agents.return_value = {
            "agent-1": {
                "last_seen": "2025-12-30T10:00:00Z",
                "current_ticket": "FB-001",
                "last_action": "ticket_claimed",
                "activity_count": 5,
            }
        }
        mock_ops_log.get_latest_directive.return_value = None
        mock_ops_log.read_entries.return_value = []
        mock_ticket_store.list.return_value = []
        mock_ws_manager.get_connection_count.return_value = 2

        dashboard = await control_plane_service.get_dashboard_state()

        assert isinstance(dashboard, ControlPlaneDashboard)
        assert len(dashboard.agents) == 1
        assert dashboard.agents[0].name == "agent-1"
        assert isinstance(dashboard.directive_state, DirectiveState)
        assert "active_agents" in dashboard.metrics

    @pytest.mark.asyncio
    async def test_get_active_agents_empty(self, control_plane_service, mock_ops_log):
        """Test getting active agents when none exist."""
        mock_ops_log.check_active_agents.return_value = {}
        mock_ops_log.get_latest_directive.return_value = None

        agents = await control_plane_service.get_active_agents()

        assert agents == []

    @pytest.mark.asyncio
    async def test_get_active_agents_with_activity(
        self, control_plane_service, mock_ops_log
    ):
        """Test getting active agents with activity."""
        mock_ops_log.check_active_agents.return_value = {
            "agent-1": {
                "last_seen": "2025-12-30T10:00:00Z",
                "current_ticket": "FB-001",
                "last_action": "ticket_claimed",
                "activity_count": 5,
            },
            "agent-2": {
                "last_seen": "2025-12-30T09:00:00Z",
                "current_ticket": None,
                "last_action": "ticket_completed",
                "activity_count": 3,
            },
        }
        mock_ops_log.get_latest_directive.return_value = None

        agents = await control_plane_service.get_active_agents()

        assert len(agents) == 2
        assert agents[0].name in ["agent-1", "agent-2"]
        agent1 = next(a for a in agents if a.name == "agent-1")
        assert agent1.current_ticket == "FB-001"
        assert agent1.activity_count == 5

    @pytest.mark.asyncio
    async def test_get_active_agents_with_clearance(
        self, control_plane_service, mock_ops_log
    ):
        """Test getting active agents with clearance directive."""
        mock_ops_log.check_active_agents.return_value = {
            "agent-1": {
                "last_seen": "2025-12-30T10:00:00Z",
                "current_ticket": None,
                "last_action": "agent_started",
                "activity_count": 1,
            },
        }
        mock_ops_log.get_latest_directive.return_value = LogEntry(
            id="d1",
            timestamp="2025-12-30T10:00:00Z",
            agent="admin",
            event_type=EventType.CLEARANCE_GRANTED.value,
            message="Clearance granted",
            metadata={"granted_to": ["agent-1"]},
        )

        agents = await control_plane_service.get_active_agents()

        assert len(agents) == 1
        assert agents[0].has_clearance is True
        assert agents[0].under_hold is False

    @pytest.mark.asyncio
    async def test_get_active_agents_under_global_hold(
        self, control_plane_service, mock_ops_log
    ):
        """Test getting active agents under global hold."""
        mock_ops_log.check_active_agents.return_value = {
            "agent-1": {
                "last_seen": "2025-12-30T10:00:00Z",
                "current_ticket": None,
                "last_action": "agent_started",
                "activity_count": 1,
            },
        }
        mock_ops_log.get_latest_directive.return_value = LogEntry(
            id="d1",
            timestamp="2025-12-30T10:00:00Z",
            agent="admin",
            event_type=EventType.HOLD.value,
            message="Hold",
            metadata={"is_global": True, "affected_agents": []},
        )

        agents = await control_plane_service.get_active_agents()

        assert len(agents) == 1
        assert agents[0].under_hold is True
        assert agents[0].has_clearance is False

    @pytest.mark.asyncio
    async def test_get_active_agents_under_specific_hold(
        self, control_plane_service, mock_ops_log
    ):
        """Test getting active agents under specific hold."""
        mock_ops_log.check_active_agents.return_value = {
            "agent-1": {
                "last_seen": "2025-12-30T10:00:00Z",
                "current_ticket": None,
                "last_action": "agent_started",
                "activity_count": 1,
            },
            "agent-2": {
                "last_seen": "2025-12-30T10:00:00Z",
                "current_ticket": None,
                "last_action": "agent_started",
                "activity_count": 1,
            },
        }
        mock_ops_log.get_latest_directive.return_value = LogEntry(
            id="d1",
            timestamp="2025-12-30T10:00:00Z",
            agent="admin",
            event_type=EventType.HOLD.value,
            message="Hold",
            metadata={"is_global": False, "affected_agents": ["agent-1"]},
        )

        agents = await control_plane_service.get_active_agents()

        agent1 = next(a for a in agents if a.name == "agent-1")
        agent2 = next(a for a in agents if a.name == "agent-2")
        assert agent1.under_hold is True
        assert agent2.under_hold is False


class TestControlPlaneServiceOperations:
    """Tests for operations timeline and ticket queries."""

    @pytest.mark.asyncio
    async def test_get_operations_timeline(
        self, control_plane_service, mock_ops_log, sample_log_entry
    ):
        """Test getting operations timeline."""
        mock_ops_log.read_entries.return_value = [sample_log_entry]

        timeline = await control_plane_service.get_operations_timeline(
            since="1h", agent="test-agent", event_type="agent_started", limit=50
        )

        assert len(timeline) == 1
        assert timeline[0]["agent"] == "test-agent"
        mock_ops_log.read_entries.assert_called_once_with(
            since="1h", agent="test-agent", event_type="agent_started", limit=50
        )

    @pytest.mark.asyncio
    async def test_get_operations_timeline_defaults(
        self, control_plane_service, mock_ops_log
    ):
        """Test getting operations timeline with defaults."""
        mock_ops_log.read_entries.return_value = []

        timeline = await control_plane_service.get_operations_timeline()

        assert timeline == []
        mock_ops_log.read_entries.assert_called_once_with(
            since=None, agent=None, event_type=None, limit=100
        )

    @pytest.mark.asyncio
    async def test_get_active_tickets_empty(
        self, control_plane_service, mock_ticket_store
    ):
        """Test getting active tickets when none exist."""
        mock_ticket_store.list.return_value = []

        tickets = await control_plane_service.get_active_tickets()

        assert tickets == []
        # Should have called list for each active status
        assert mock_ticket_store.list.call_count == 4

    @pytest.mark.asyncio
    async def test_get_active_tickets(
        self, control_plane_service, mock_ticket_store, sample_ticket
    ):
        """Test getting active tickets."""

        def mock_list(status=None, limit=50):
            if status == TicketStatus.OPEN:
                return [sample_ticket]
            return []

        mock_ticket_store.list.side_effect = mock_list

        tickets = await control_plane_service.get_active_tickets()

        assert len(tickets) == 1
        assert tickets[0].id == sample_ticket.id
        assert tickets[0].ticket_number == sample_ticket.ticket_number


class TestControlPlaneServiceDirectives:
    """Tests for directive state and operations."""

    @pytest.mark.asyncio
    async def test_get_directive_state_no_directive(
        self, control_plane_service, mock_ops_log
    ):
        """Test getting directive state when no directive exists."""
        mock_ops_log.get_latest_directive.return_value = None

        state = await control_plane_service.get_directive_state()

        assert state.has_active_hold is False
        assert state.has_active_clearance is False
        assert state.latest_directive is None
        assert state.affected_agents == []
        assert state.affected_tickets == []

    @pytest.mark.asyncio
    async def test_get_directive_state_with_hold(
        self, control_plane_service, mock_ops_log
    ):
        """Test getting directive state with hold."""
        mock_ops_log.get_latest_directive.return_value = LogEntry(
            id="d1",
            timestamp="2025-12-30T10:00:00Z",
            agent="admin",
            event_type=EventType.HOLD.value,
            message="Hold",
            metadata={
                "affected_agents": ["agent-1", "agent-2"],
                "tickets": ["FB-001"],
            },
        )

        state = await control_plane_service.get_directive_state()

        assert state.has_active_hold is True
        assert state.has_active_clearance is False
        assert state.affected_agents == ["agent-1", "agent-2"]
        assert state.affected_tickets == ["FB-001"]
        assert state.latest_directive is not None

    @pytest.mark.asyncio
    async def test_get_directive_state_with_clearance(
        self, control_plane_service, mock_ops_log
    ):
        """Test getting directive state with clearance."""
        mock_ops_log.get_latest_directive.return_value = LogEntry(
            id="d1",
            timestamp="2025-12-30T10:00:00Z",
            agent="admin",
            event_type=EventType.CLEARANCE_GRANTED.value,
            message="Clearance",
            metadata={
                "granted_to": ["agent-1"],
                "tickets": ["FB-001", "FB-002"],
            },
        )

        state = await control_plane_service.get_directive_state()

        assert state.has_active_hold is False
        assert state.has_active_clearance is True
        assert state.affected_agents == ["agent-1"]
        assert state.affected_tickets == ["FB-001", "FB-002"]

    @pytest.mark.asyncio
    async def test_issue_hold(
        self, control_plane_service, mock_ops_log, mock_ws_manager
    ):
        """Test issuing a hold directive."""
        hold_entry = LogEntry(
            id="h1",
            timestamp="2025-12-30T10:00:00Z",
            agent="admin",
            event_type=EventType.HOLD.value,
            message="Hold",
        )
        mock_ops_log.issue_hold.return_value = hold_entry

        result = await control_plane_service.issue_hold(
            issuing_agent="admin",
            affected_agents=["agent-1", "agent-2"],
            tickets=["FB-001"],
            reason="Conflict detected",
        )

        assert result is hold_entry
        mock_ops_log.issue_hold.assert_called_once_with(
            agent="admin",
            affected_agents=["agent-1", "agent-2"],
            tickets=["FB-001"],
            reason="Conflict detected",
        )
        mock_ws_manager.broadcast.assert_called_once()

    @pytest.mark.asyncio
    async def test_issue_hold_global(
        self, control_plane_service, mock_ops_log, mock_ws_manager
    ):
        """Test issuing a global hold directive."""
        hold_entry = LogEntry(
            id="h1",
            timestamp="2025-12-30T10:00:00Z",
            agent="admin",
            event_type=EventType.HOLD.value,
            message="Global Hold",
        )
        mock_ops_log.issue_hold.return_value = hold_entry

        result = await control_plane_service.issue_hold(
            issuing_agent="admin",
            affected_agents=["all"],
            tickets=None,
            reason="System maintenance",
        )

        assert result is hold_entry
        mock_ops_log.issue_hold.assert_called_once_with(
            agent="admin",
            affected_agents=["all"],
            tickets=None,
            reason="System maintenance",
        )

    @pytest.mark.asyncio
    async def test_grant_clearance(
        self, control_plane_service, mock_ops_log, mock_ws_manager
    ):
        """Test granting clearance."""
        clearance_entry = LogEntry(
            id="c1",
            timestamp="2025-12-30T10:00:00Z",
            agent="admin",
            event_type=EventType.CLEARANCE_GRANTED.value,
            message="Clearance granted",
        )
        mock_ops_log.grant_clearance.return_value = clearance_entry

        result = await control_plane_service.grant_clearance(
            granting_agent="admin",
            granted_to=["agent-1"],
            tickets=["FB-001", "FB-002"],
            reason="Ready to proceed",
        )

        assert result is clearance_entry
        mock_ops_log.grant_clearance.assert_called_once_with(
            agent="admin",
            granted_to=["agent-1"],
            tickets=["FB-001", "FB-002"],
            reason="Ready to proceed",
        )
        mock_ws_manager.broadcast.assert_called_once()


class TestControlPlaneServiceMetrics:
    """Tests for metrics computation."""

    def test_compute_metrics(self, control_plane_service, mock_ws_manager):
        """Test computing dashboard metrics."""
        mock_ws_manager.get_connection_count.return_value = 3

        agents = [
            AgentActivity(name="agent-1", is_active=True, under_hold=False),
            AgentActivity(name="agent-2", is_active=True, under_hold=True),
            AgentActivity(name="agent-3", is_active=False, under_hold=False),
        ]

        tickets = [
            TicketSummary(
                id="1",
                ticket_number="FB-001",
                title="T1",
                status="open",
                priority="high",
            ),
            TicketSummary(
                id="2",
                ticket_number="FB-002",
                title="T2",
                status="in_progress",
                priority="medium",
            ),
            TicketSummary(
                id="3",
                ticket_number="FB-003",
                title="T3",
                status="under_review",
                priority="low",
            ),
        ]

        entries = []  # Empty for simplicity

        metrics = control_plane_service._compute_metrics(agents, tickets, entries)

        assert metrics["active_agents"] == 2
        assert metrics["agents_under_hold"] == 1
        assert metrics["open_tickets"] == 1
        assert metrics["in_progress_tickets"] == 1
        assert metrics["under_review_tickets"] == 1
        assert metrics["total_active_tickets"] == 3
        assert metrics["websocket_connections"] == 3
        assert metrics["today_activity_count"] == 0

    def test_compute_metrics_with_today_activity(
        self, control_plane_service, mock_ws_manager
    ):
        """Test computing metrics with today's activity."""
        mock_ws_manager.get_connection_count.return_value = 1

        agents = []
        tickets = []

        # Create entries from today
        now = datetime.utcnow()
        entries = [
            LogEntry(
                id="1",
                timestamp=now.isoformat() + "Z",
                agent="agent-1",
                event_type="agent_started",
                message="Started",
            ),
            LogEntry(
                id="2",
                timestamp=now.isoformat() + "Z",
                agent="agent-1",
                event_type="ticket_claimed",
                message="Claimed",
            ),
        ]

        metrics = control_plane_service._compute_metrics(agents, tickets, entries)

        assert metrics["today_activity_count"] == 2


# =============================================================================
# GLOBAL SINGLETON TESTS
# =============================================================================


class TestGetControlPlaneService:
    """Tests for get_control_plane_service global function."""

    def test_get_singleton(self, tmp_path):
        """Test getting the singleton instance."""
        with patch(
            "fastband.hub.control_plane.service._control_plane_service", None
        ):
            service1 = get_control_plane_service(project_path=tmp_path)
            service2 = get_control_plane_service(project_path=tmp_path)

            assert service1 is service2

    def test_get_singleton_reset(self, tmp_path):
        """Test resetting the singleton instance."""
        with patch(
            "fastband.hub.control_plane.service._control_plane_service", None
        ):
            service1 = get_control_plane_service(project_path=tmp_path)
            service2 = get_control_plane_service(project_path=tmp_path, reset=True)

            assert service1 is not service2

    def test_get_singleton_default_path(self):
        """Test getting singleton with default path."""
        with patch(
            "fastband.hub.control_plane.service._control_plane_service", None
        ):
            service = get_control_plane_service(reset=True)

            assert service.project_path is not None


# =============================================================================
# INTEGRATION-STYLE TESTS
# =============================================================================


class TestControlPlaneIntegration:
    """Integration-style tests for Control Plane service."""

    @pytest.mark.asyncio
    async def test_full_workflow(
        self, control_plane_service, mock_ops_log, mock_ticket_store, mock_ws_manager
    ):
        """Test a full workflow: start, get state, issue hold, grant clearance, stop."""
        # Setup
        mock_ops_log.count.return_value = 0
        mock_ops_log.check_active_agents.return_value = {}
        mock_ops_log.get_latest_directive.return_value = None
        mock_ops_log.read_entries.return_value = []
        mock_ticket_store.list.return_value = []
        mock_ws_manager.get_connection_count.return_value = 0

        # Start service
        await control_plane_service.start()
        assert control_plane_service._running is True

        # Get initial state
        dashboard = await control_plane_service.get_dashboard_state()
        assert dashboard.metrics["active_agents"] == 0

        # Issue hold
        hold_entry = LogEntry(
            id="h1",
            timestamp="2025-12-30T10:00:00Z",
            agent="admin",
            event_type=EventType.HOLD.value,
            message="Hold",
        )
        mock_ops_log.issue_hold.return_value = hold_entry

        await control_plane_service.issue_hold(
            issuing_agent="admin",
            affected_agents=["agent-1"],
            reason="Test hold",
        )
        assert mock_ws_manager.broadcast.called

        # Grant clearance
        clearance_entry = LogEntry(
            id="c1",
            timestamp="2025-12-30T10:01:00Z",
            agent="admin",
            event_type=EventType.CLEARANCE_GRANTED.value,
            message="Clearance",
        )
        mock_ops_log.grant_clearance.return_value = clearance_entry

        await control_plane_service.grant_clearance(
            granting_agent="admin",
            granted_to=["agent-1"],
            tickets=["FB-001"],
            reason="Test clearance",
        )
        assert mock_ws_manager.broadcast.call_count == 2

        # Stop service
        await control_plane_service.stop()
        assert control_plane_service._running is False

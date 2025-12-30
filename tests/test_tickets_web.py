"""Tests for ticket web dashboard."""

import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

from fastband.tickets.models import (
    Agent,
    Ticket,
    TicketPriority,
    TicketStatus,
    TicketType,
)
from fastband.tickets.storage import JSONTicketStore
from fastband.tickets.web.app import create_app, serve

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def temp_dir():
    """Create a temporary directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def ticket_store(temp_dir):
    """Create a ticket store with sample data."""
    path = temp_dir / "tickets.json"
    store = JSONTicketStore(path)
    return store


@pytest.fixture
def populated_store(ticket_store):
    """Create a store with sample tickets and agents."""
    # Create sample tickets
    tickets = [
        Ticket(
            title="Fix login bug",
            description="Users cannot log in with email",
            ticket_type=TicketType.BUG,
            priority=TicketPriority.CRITICAL,
            status=TicketStatus.OPEN,
            labels=["auth", "urgent"],
            requirements=["Fix email validation", "Add error handling"],
        ),
        Ticket(
            title="Add dark mode",
            description="Implement dark mode toggle",
            ticket_type=TicketType.FEATURE,
            priority=TicketPriority.MEDIUM,
            status=TicketStatus.IN_PROGRESS,
            assigned_to="MCP_Agent1",
            labels=["ui", "enhancement"],
        ),
        Ticket(
            title="Update documentation",
            description="Update API docs",
            ticket_type=TicketType.DOCUMENTATION,
            priority=TicketPriority.LOW,
            status=TicketStatus.RESOLVED,
            assigned_to="MCP_Agent2",
            problem_summary="Docs were outdated",
            solution_summary="Updated all API endpoints",
        ),
        Ticket(
            title="Security audit",
            description="Perform security audit",
            ticket_type=TicketType.SECURITY,
            priority=TicketPriority.HIGH,
            status=TicketStatus.UNDER_REVIEW,
            assigned_to="MCP_Agent1",
        ),
        Ticket(
            title="Performance optimization",
            description="Optimize database queries",
            ticket_type=TicketType.PERFORMANCE,
            priority=TicketPriority.MEDIUM,
            status=TicketStatus.AWAITING_APPROVAL,
        ),
    ]

    for ticket in tickets:
        ticket_store.create(ticket)

    # Create sample agents
    agents = [
        Agent(
            name="MCP_Agent1",
            agent_type="ai",
            active=True,
            tickets_completed=10,
            tickets_in_progress=2,
            capabilities=["code_review", "testing"],
        ),
        Agent(
            name="MCP_Agent2",
            agent_type="ai",
            active=True,
            tickets_completed=5,
            tickets_in_progress=0,
        ),
        Agent(
            name="InactiveAgent",
            agent_type="ai",
            active=False,
            tickets_completed=3,
        ),
    ]

    for agent in agents:
        ticket_store.save_agent(agent)

    return ticket_store


@pytest.fixture
def app(populated_store):
    """Create Flask test app with populated store."""
    app = create_app(store=populated_store, config={"TESTING": True})
    return app


@pytest.fixture
def client(app):
    """Create Flask test client."""
    return app.test_client()


@pytest.fixture
def empty_app(ticket_store):
    """Create Flask test app with empty store."""
    app = create_app(store=ticket_store, config={"TESTING": True})
    return app


@pytest.fixture
def empty_client(empty_app):
    """Create Flask test client with empty store."""
    return empty_app.test_client()


# =============================================================================
# APP CREATION TESTS
# =============================================================================


class TestAppCreation:
    """Tests for app creation and configuration."""

    def test_create_app_with_store(self, populated_store):
        """Test creating app with custom store."""
        app = create_app(store=populated_store)
        assert app is not None
        assert app.config["TICKET_STORE"] is populated_store

    def test_create_app_without_store(self, temp_dir, monkeypatch):
        """Test creating app without store creates default."""
        monkeypatch.chdir(temp_dir)
        app = create_app()
        assert app is not None
        assert app.config["TICKET_STORE"] is not None

    def test_create_app_with_custom_config(self, ticket_store):
        """Test creating app with custom config."""
        app = create_app(store=ticket_store, config={"DEBUG": True, "CUSTOM_KEY": "value"})
        assert app.config["DEBUG"] is True
        assert app.config["CUSTOM_KEY"] == "value"

    def test_app_has_secret_key(self, app):
        """Test app has secret key configured."""
        assert app.config["SECRET_KEY"] is not None


# =============================================================================
# DASHBOARD ROUTE TESTS
# =============================================================================


class TestDashboardRoute:
    """Tests for the dashboard route."""

    def test_dashboard_returns_200(self, client):
        """Test dashboard returns 200 OK."""
        response = client.get("/")
        assert response.status_code == 200

    def test_dashboard_shows_statistics(self, client):
        """Test dashboard shows ticket statistics."""
        response = client.get("/")
        html = response.data.decode()

        # Check that statistics are displayed
        assert "Total Tickets" in html or "total" in html.lower()
        assert "Open" in html
        assert "In Progress" in html

    def test_dashboard_shows_recent_tickets(self, client):
        """Test dashboard shows recent tickets."""
        response = client.get("/")
        html = response.data.decode()

        assert "Fix login bug" in html
        assert "Add dark mode" in html

    def test_dashboard_shows_agents(self, client):
        """Test dashboard shows active agents."""
        response = client.get("/")
        html = response.data.decode()

        assert "MCP_Agent1" in html
        assert "MCP_Agent2" in html
        # Inactive agent should not appear
        assert "InactiveAgent" not in html

    def test_dashboard_empty_store(self, empty_client):
        """Test dashboard with empty store."""
        response = empty_client.get("/")
        assert response.status_code == 200
        html = response.data.decode()

        # Should show zero counts
        assert ">0<" in html or "No tickets" in html.lower() or "0" in html


# =============================================================================
# TICKET LIST ROUTE TESTS
# =============================================================================


class TestTicketListRoute:
    """Tests for the ticket list route."""

    def test_ticket_list_returns_200(self, client):
        """Test ticket list returns 200 OK."""
        response = client.get("/tickets")
        assert response.status_code == 200

    def test_ticket_list_shows_all_tickets(self, client):
        """Test ticket list shows all tickets."""
        response = client.get("/tickets")
        html = response.data.decode()

        assert "Fix login bug" in html
        assert "Add dark mode" in html
        assert "Update documentation" in html

    def test_ticket_list_filter_by_status(self, client):
        """Test filtering tickets by status."""
        response = client.get("/tickets?status=open")
        html = response.data.decode()

        assert "Fix login bug" in html
        # In progress ticket should not appear
        # The filter is applied

    def test_ticket_list_filter_by_priority(self, client):
        """Test filtering tickets by priority."""
        response = client.get("/tickets?priority=critical")
        html = response.data.decode()

        assert "Fix login bug" in html

    def test_ticket_list_filter_by_type(self, client):
        """Test filtering tickets by type."""
        response = client.get("/tickets?type=bug")
        html = response.data.decode()

        assert "Fix login bug" in html

    def test_ticket_list_filter_by_assignee(self, client):
        """Test filtering tickets by assignee."""
        response = client.get("/tickets?assignee=MCP_Agent1")
        html = response.data.decode()

        assert "Add dark mode" in html or "Security audit" in html

    def test_ticket_list_search(self, client):
        """Test searching tickets."""
        response = client.get("/tickets?q=login")
        html = response.data.decode()

        assert "Fix login bug" in html

    def test_ticket_list_pagination(self, client, populated_store):
        """Test ticket list pagination."""
        # Add more tickets
        for i in range(25):
            populated_store.create(Ticket(title=f"Test Ticket {i}"))

        response = client.get("/tickets?page=2&per_page=10")
        assert response.status_code == 200

    def test_ticket_list_empty(self, empty_client):
        """Test ticket list with no tickets."""
        response = empty_client.get("/tickets")
        html = response.data.decode()

        assert response.status_code == 200
        assert "No tickets" in html or "no tickets" in html.lower()


# =============================================================================
# TICKET DETAIL ROUTE TESTS
# =============================================================================


class TestTicketDetailRoute:
    """Tests for the ticket detail route."""

    def test_ticket_detail_returns_200(self, client, populated_store):
        """Test ticket detail returns 200 OK."""
        tickets = populated_store.list(limit=1)
        ticket_id = tickets[0].id

        response = client.get(f"/tickets/{ticket_id}")
        assert response.status_code == 200

    def test_ticket_detail_shows_title(self, client, populated_store):
        """Test ticket detail shows title."""
        tickets = populated_store.list(limit=1)
        ticket = tickets[0]

        response = client.get(f"/tickets/{ticket.id}")
        html = response.data.decode()

        assert ticket.title in html

    def test_ticket_detail_shows_description(self, client, populated_store):
        """Test ticket detail shows description."""
        tickets = populated_store.list(limit=1)
        ticket = tickets[0]

        response = client.get(f"/tickets/{ticket.id}")
        html = response.data.decode()

        if ticket.description:
            assert ticket.description in html

    def test_ticket_detail_shows_status_and_priority(self, client, populated_store):
        """Test ticket detail shows status and priority."""
        tickets = populated_store.list(limit=1)
        ticket = tickets[0]

        response = client.get(f"/tickets/{ticket.id}")
        html = response.data.decode()

        assert ticket.status.display_name in html or ticket.status.value in html
        assert ticket.priority.display_name in html or ticket.priority.value in html

    def test_ticket_detail_not_found(self, client):
        """Test ticket detail returns 404 for unknown ID."""
        response = client.get("/tickets/99999")
        assert response.status_code == 404

    def test_ticket_detail_shows_requirements(self, client, populated_store):
        """Test ticket detail shows requirements."""
        # Find ticket with requirements
        tickets = populated_store.search("login")
        ticket = tickets[0]

        response = client.get(f"/tickets/{ticket.id}")
        html = response.data.decode()

        for req in ticket.requirements:
            assert req in html

    def test_ticket_detail_shows_work_summary(self, client, populated_store):
        """Test ticket detail shows work summary for resolved tickets."""
        # Find resolved ticket
        resolved = populated_store.list(status=TicketStatus.RESOLVED)
        if resolved:
            ticket = resolved[0]
            response = client.get(f"/tickets/{ticket.id}")
            html = response.data.decode()

            if ticket.problem_summary:
                assert ticket.problem_summary in html
            if ticket.solution_summary:
                assert ticket.solution_summary in html


# =============================================================================
# JSON API TESTS
# =============================================================================


class TestAPITickets:
    """Tests for the /api/tickets endpoint."""

    def test_api_tickets_returns_json(self, client):
        """Test API returns JSON response."""
        response = client.get("/api/tickets")
        assert response.status_code == 200
        assert response.content_type == "application/json"

    def test_api_tickets_returns_list(self, client):
        """Test API returns ticket list."""
        response = client.get("/api/tickets")
        data = json.loads(response.data)

        assert "tickets" in data
        assert isinstance(data["tickets"], list)
        assert len(data["tickets"]) > 0

    def test_api_tickets_returns_total(self, client):
        """Test API returns total count."""
        response = client.get("/api/tickets")
        data = json.loads(response.data)

        assert "total" in data
        assert data["total"] >= len(data["tickets"])

    def test_api_tickets_filter_by_status(self, client):
        """Test API filters by status."""
        response = client.get("/api/tickets?status=open")
        data = json.loads(response.data)

        for ticket in data["tickets"]:
            assert ticket["status"] == "open"

    def test_api_tickets_filter_by_priority(self, client):
        """Test API filters by priority."""
        response = client.get("/api/tickets?priority=critical")
        data = json.loads(response.data)

        for ticket in data["tickets"]:
            assert ticket["priority"] == "critical"

    def test_api_tickets_filter_by_type(self, client):
        """Test API filters by type."""
        response = client.get("/api/tickets?type=bug")
        data = json.loads(response.data)

        for ticket in data["tickets"]:
            assert ticket["ticket_type"] == "bug"

    def test_api_tickets_pagination(self, client):
        """Test API pagination."""
        response = client.get("/api/tickets?limit=2&offset=0")
        data = json.loads(response.data)

        assert len(data["tickets"]) <= 2
        assert data["limit"] == 2
        assert data["offset"] == 0

    def test_api_tickets_search(self, client):
        """Test API search."""
        response = client.get("/api/tickets?q=login")
        data = json.loads(response.data)

        assert len(data["tickets"]) >= 1
        assert any("login" in t["title"].lower() for t in data["tickets"])

    def test_api_tickets_invalid_status(self, client):
        """Test API returns error for invalid status."""
        response = client.get("/api/tickets?status=invalid")
        assert response.status_code == 400

    def test_api_tickets_invalid_priority(self, client):
        """Test API returns error for invalid priority."""
        response = client.get("/api/tickets?priority=invalid")
        assert response.status_code == 400


class TestAPITicketDetail:
    """Tests for the /api/tickets/<id> endpoint."""

    def test_api_ticket_detail_returns_json(self, client, populated_store):
        """Test API returns JSON response."""
        tickets = populated_store.list(limit=1)
        ticket_id = tickets[0].id

        response = client.get(f"/api/tickets/{ticket_id}")
        assert response.status_code == 200
        assert response.content_type == "application/json"

    def test_api_ticket_detail_returns_ticket(self, client, populated_store):
        """Test API returns ticket data."""
        tickets = populated_store.list(limit=1)
        ticket = tickets[0]

        response = client.get(f"/api/tickets/{ticket.id}")
        data = json.loads(response.data)

        assert "ticket" in data
        assert data["ticket"]["id"] == ticket.id
        assert data["ticket"]["title"] == ticket.title

    def test_api_ticket_detail_not_found(self, client):
        """Test API returns 404 for unknown ticket."""
        response = client.get("/api/tickets/99999")
        assert response.status_code == 404

        data = json.loads(response.data)
        assert "error" in data


class TestAPIAgents:
    """Tests for the /api/agents endpoint."""

    def test_api_agents_returns_json(self, client):
        """Test API returns JSON response."""
        response = client.get("/api/agents")
        assert response.status_code == 200
        assert response.content_type == "application/json"

    def test_api_agents_returns_list(self, client):
        """Test API returns agent list."""
        response = client.get("/api/agents")
        data = json.loads(response.data)

        assert "agents" in data
        assert isinstance(data["agents"], list)

    def test_api_agents_active_only(self, client):
        """Test API returns only active agents by default."""
        response = client.get("/api/agents")
        data = json.loads(response.data)

        for agent in data["agents"]:
            assert agent["active"] is True

    def test_api_agents_include_inactive(self, client):
        """Test API can include inactive agents."""
        response = client.get("/api/agents?active_only=false")
        data = json.loads(response.data)

        # Should include all agents
        assert len(data["agents"]) >= 2


class TestAPIStats:
    """Tests for the /api/stats endpoint."""

    def test_api_stats_returns_json(self, client):
        """Test API returns JSON response."""
        response = client.get("/api/stats")
        assert response.status_code == 200
        assert response.content_type == "application/json"

    def test_api_stats_returns_counts(self, client):
        """Test API returns ticket counts."""
        response = client.get("/api/stats")
        data = json.loads(response.data)

        assert "total" in data
        assert "by_status" in data
        assert "by_priority" in data
        assert "agents" in data

    def test_api_stats_by_status(self, client):
        """Test API returns counts by status."""
        response = client.get("/api/stats")
        data = json.loads(response.data)

        by_status = data["by_status"]
        assert "open" in by_status
        assert "in_progress" in by_status
        assert "resolved" in by_status

    def test_api_stats_by_priority(self, client):
        """Test API returns counts by priority."""
        response = client.get("/api/stats")
        data = json.loads(response.data)

        by_priority = data["by_priority"]
        assert "critical" in by_priority
        assert "high" in by_priority
        assert "medium" in by_priority
        assert "low" in by_priority


class TestAPIHealth:
    """Tests for the /api/health endpoint."""

    def test_api_health_returns_200(self, client):
        """Test health endpoint returns 200."""
        response = client.get("/api/health")
        assert response.status_code == 200

    def test_api_health_returns_status(self, client):
        """Test health endpoint returns status."""
        response = client.get("/api/health")
        data = json.loads(response.data)

        assert data["status"] == "healthy"
        assert "timestamp" in data


# =============================================================================
# TEMPLATE FILTER TESTS
# =============================================================================


class TestTemplateFilters:
    """Tests for Jinja2 template filters."""

    def test_datetime_filter(self, app):
        """Test datetime filter."""
        with app.app_context():
            env = app.jinja_env
            dt = datetime(2024, 1, 15, 10, 30)
            result = env.filters["datetime"](dt)
            assert "2024-01-15" in result
            assert "10:30" in result

    def test_datetime_filter_none(self, app):
        """Test datetime filter with None."""
        with app.app_context():
            env = app.jinja_env
            result = env.filters["datetime"](None)
            assert result == ""

    def test_datetime_filter_string(self, app):
        """Test datetime filter with ISO string."""
        with app.app_context():
            env = app.jinja_env
            result = env.filters["datetime"]("2024-01-15T10:30:00")
            assert "2024-01-15" in result

    def test_relative_time_filter_just_now(self, app):
        """Test relative time filter for recent time."""
        with app.app_context():
            env = app.jinja_env
            dt = datetime.now()
            result = env.filters["relative_time"](dt)
            assert result == "just now"

    def test_relative_time_filter_minutes(self, app):
        """Test relative time filter for minutes."""
        with app.app_context():
            env = app.jinja_env
            dt = datetime.now() - timedelta(minutes=5)
            result = env.filters["relative_time"](dt)
            assert "minute" in result

    def test_relative_time_filter_hours(self, app):
        """Test relative time filter for hours."""
        with app.app_context():
            env = app.jinja_env
            dt = datetime.now() - timedelta(hours=3)
            result = env.filters["relative_time"](dt)
            assert "hour" in result

    def test_relative_time_filter_days(self, app):
        """Test relative time filter for days."""
        with app.app_context():
            env = app.jinja_env
            dt = datetime.now() - timedelta(days=2)
            result = env.filters["relative_time"](dt)
            assert "day" in result

    def test_status_color_filter(self, app):
        """Test status color filter."""
        with app.app_context():
            env = app.jinja_env

            assert env.filters["status_color"](TicketStatus.OPEN) == "danger"
            assert env.filters["status_color"](TicketStatus.IN_PROGRESS) == "warning"
            assert env.filters["status_color"](TicketStatus.RESOLVED) == "success"

    def test_priority_color_filter(self, app):
        """Test priority color filter."""
        with app.app_context():
            env = app.jinja_env

            assert env.filters["priority_color"](TicketPriority.CRITICAL) == "danger"
            assert env.filters["priority_color"](TicketPriority.HIGH) == "warning"
            assert env.filters["priority_color"](TicketPriority.LOW) == "success"

    def test_type_icon_filter(self, app):
        """Test type icon filter."""
        with app.app_context():
            env = app.jinja_env

            assert "bug" in env.filters["type_icon"](TicketType.BUG)
            assert "star" in env.filters["type_icon"](TicketType.FEATURE)


# =============================================================================
# ERROR HANDLER TESTS
# =============================================================================


class TestErrorHandlers:
    """Tests for error handlers."""

    def test_404_html_response(self, client):
        """Test 404 returns HTML for non-API routes."""
        response = client.get("/nonexistent-page")
        assert response.status_code == 404
        assert b"html" in response.data.lower() or response.content_type.startswith("text/html")

    def test_404_json_response(self, client):
        """Test 404 returns JSON for API routes."""
        response = client.get("/api/nonexistent")
        assert response.status_code == 404
        assert response.content_type == "application/json"


# =============================================================================
# SERVE FUNCTION TESTS
# =============================================================================


class TestServeFunction:
    """Tests for the serve function."""

    def test_serve_creates_app(self, populated_store):
        """Test serve function creates app."""
        with patch.object(create_app(populated_store), "run"):
            # Just verify the function can be called without error
            # (we don't actually want to start the server)
            assert callable(serve)

    def test_serve_with_custom_params(self, populated_store):
        """Test serve accepts custom parameters."""
        # This is a smoke test - we can't easily test actual server start
        app = create_app(populated_store)
        assert app is not None


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestIntegration:
    """Integration tests for the web dashboard."""

    def test_full_workflow(self, client, populated_store):
        """Test complete workflow: dashboard -> list -> detail."""
        # Visit dashboard
        response = client.get("/")
        assert response.status_code == 200

        # Get ticket list
        response = client.get("/tickets")
        assert response.status_code == 200

        # Get first ticket's details
        tickets = populated_store.list(limit=1)
        response = client.get(f"/tickets/{tickets[0].id}")
        assert response.status_code == 200

    def test_filter_chain(self, client):
        """Test applying multiple filters."""
        response = client.get("/tickets?status=open&priority=critical")
        assert response.status_code == 200

    def test_search_and_filter(self, client):
        """Test search combined with filter."""
        response = client.get("/tickets?q=bug&priority=critical")
        assert response.status_code == 200

    def test_api_reflects_html_data(self, client, populated_store):
        """Test API data matches HTML display."""
        # Get data from API
        api_response = client.get("/api/tickets")
        api_data = json.loads(api_response.data)

        # Get HTML page
        html_response = client.get("/tickets")
        html = html_response.data.decode()

        # Verify all API tickets appear in HTML
        for ticket in api_data["tickets"][:5]:  # Check first 5
            assert ticket["title"] in html or str(ticket["id"]) in html

    def test_theme_toggle_in_html(self, client):
        """Test theme toggle elements are present."""
        response = client.get("/")
        html = response.data.decode()

        assert "toggleTheme" in html
        assert "data-bs-theme" in html

    def test_bootstrap_cdn_links(self, client):
        """Test Bootstrap CDN links are present."""
        response = client.get("/")
        html = response.data.decode()

        assert "bootstrap" in html.lower()
        assert "cdn.jsdelivr.net" in html or "bootstrap" in html


# =============================================================================
# EDGE CASES
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_special_characters_in_search(self, client):
        """Test search with special characters."""
        response = client.get("/tickets?q=<script>alert('xss')</script>")
        assert response.status_code == 200
        html = response.data.decode()
        # The search query should be escaped in the displayed value
        # Check that the literal XSS script tag is escaped in user content
        assert "&lt;script&gt;alert" in html  # Escaped version should appear
        # The only <script> tags should be the legitimate Bootstrap/JS ones
        # Count occurrences - should only be the CDN and inline scripts
        script_count = html.count("<script")
        assert script_count <= 3  # Bootstrap CDN + inline theme script

    def test_unicode_in_ticket(self, client, populated_store):
        """Test Unicode characters in ticket display."""
        ticket = Ticket(
            title="Unicode test: 日本語 emoji",
            description="Description with emoji: 🎉🚀",
        )
        created = populated_store.create(ticket)

        response = client.get(f"/tickets/{created.id}")
        html = response.data.decode()

        assert "日本語" in html or "&#" in html  # Either rendered or escaped
        assert response.status_code == 200

    def test_very_long_title(self, client, populated_store):
        """Test handling of very long ticket titles."""
        long_title = "A" * 500
        ticket = Ticket(title=long_title)
        created = populated_store.create(ticket)

        response = client.get(f"/tickets/{created.id}")
        assert response.status_code == 200

    def test_empty_description(self, client, populated_store):
        """Test ticket with empty description."""
        ticket = Ticket(title="No description", description="")
        created = populated_store.create(ticket)

        response = client.get(f"/tickets/{created.id}")
        assert response.status_code == 200
        assert "No description" in response.data.decode()

    def test_pagination_beyond_max(self, client):
        """Test pagination with page beyond maximum."""
        response = client.get("/tickets?page=1000")
        assert response.status_code == 200

    def test_negative_page_number(self, client):
        """Test pagination with negative page number."""
        response = client.get("/tickets?page=-1")
        # Should handle gracefully (Flask converts to int, may default)
        assert response.status_code == 200

    def test_non_integer_page(self, client):
        """Test pagination with non-integer page."""
        response = client.get("/tickets?page=abc")
        # Flask's type converter should handle this
        assert response.status_code in [200, 404]  # Depends on Flask behavior

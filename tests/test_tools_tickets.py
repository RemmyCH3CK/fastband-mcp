"""
Tests for MCP Ticket Tools.

Tests all ticket management tools for AI agents including:
- list_tickets
- get_ticket_details
- create_ticket
- claim_ticket
- complete_ticket_safely
- update_ticket
- search_tickets
- add_ticket_comment
"""

import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from fastband.tickets.models import (
    Agent,
    Ticket,
    TicketPriority,
    TicketStatus,
    TicketType,
)
from fastband.tickets.storage import JSONTicketStore, TicketStore
from fastband.tools.tickets import (
    TICKET_TOOLS,
    AddTicketCommentTool,
    ClaimTicketTool,
    CompleteTicketSafelyTool,
    CreateTicketTool,
    GetTicketDetailsTool,
    ListTicketsTool,
    SearchTicketsTool,
    UpdateTicketTool,
)

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def temp_store_path():
    """Create a temporary path for test store."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir) / "test_tickets.json"


@pytest.fixture
def store(temp_store_path):
    """Create a test ticket store."""
    return JSONTicketStore(temp_store_path, auto_save=True)


@pytest.fixture
def store_with_tickets(store):
    """Create a store with sample tickets."""
    # Create sample tickets
    tickets = [
        Ticket(
            id="1",
            title="Fix login button",
            description="The login button is not responding",
            ticket_type=TicketType.BUG,
            priority=TicketPriority.HIGH,
            status=TicketStatus.OPEN,
            labels=["frontend", "urgent"],
            app="web-app",
        ),
        Ticket(
            id="2",
            title="Add dark mode",
            description="Implement dark mode theme switching",
            ticket_type=TicketType.FEATURE,
            priority=TicketPriority.MEDIUM,
            status=TicketStatus.OPEN,
            labels=["frontend", "theme"],
        ),
        Ticket(
            id="3",
            title="Refactor database module",
            description="Clean up database connection handling",
            ticket_type=TicketType.MAINTENANCE,
            priority=TicketPriority.LOW,
            status=TicketStatus.IN_PROGRESS,
            assigned_to="MCP_Agent1",
        ),
        Ticket(
            id="4",
            title="Update API documentation",
            description="Document new endpoints",
            ticket_type=TicketType.DOCUMENTATION,
            priority=TicketPriority.MEDIUM,
            status=TicketStatus.RESOLVED,
        ),
    ]

    for ticket in tickets:
        store.create(ticket)

    return store


@pytest.fixture
def claimed_ticket_store(store):
    """Create a store with a claimed ticket."""
    ticket = Ticket(
        id="100",
        title="Test claimed ticket",
        description="A ticket that has been claimed",
        ticket_type=TicketType.BUG,
        priority=TicketPriority.HIGH,
        status=TicketStatus.IN_PROGRESS,
        assigned_to="TestAgent",
        started_at=datetime.now(),
    )
    store.create(ticket)

    # Also create the agent
    agent = Agent(name="TestAgent", agent_type="ai", tickets_in_progress=1)
    store.save_agent(agent)

    return store


# =============================================================================
# LIST TICKETS TOOL TESTS
# =============================================================================


class TestListTicketsTool:
    """Tests for ListTicketsTool."""

    @pytest.mark.asyncio
    async def test_list_all_tickets(self, store_with_tickets):
        """Test listing all tickets."""
        tool = ListTicketsTool(store=store_with_tickets)
        result = await tool.execute()

        assert result.success is True
        assert result.data["count"] == 4
        assert len(result.data["tickets"]) == 4
        assert "total" in result.data

    @pytest.mark.asyncio
    async def test_list_tickets_by_status(self, store_with_tickets):
        """Test filtering by status."""
        tool = ListTicketsTool(store=store_with_tickets)
        result = await tool.execute(status="open")

        assert result.success is True
        assert result.data["count"] == 2
        for ticket in result.data["tickets"]:
            assert "Open" in ticket["status"]

    @pytest.mark.asyncio
    async def test_list_tickets_by_priority(self, store_with_tickets):
        """Test filtering by priority."""
        tool = ListTicketsTool(store=store_with_tickets)
        result = await tool.execute(priority="high")

        assert result.success is True
        assert result.data["count"] == 1
        assert result.data["tickets"][0]["title"] == "Fix login button"

    @pytest.mark.asyncio
    async def test_list_tickets_by_type(self, store_with_tickets):
        """Test filtering by ticket type."""
        tool = ListTicketsTool(store=store_with_tickets)
        result = await tool.execute(ticket_type="bug")

        assert result.success is True
        assert result.data["count"] == 1
        assert "Bug" in result.data["tickets"][0]["ticket_type"]

    @pytest.mark.asyncio
    async def test_list_tickets_by_assigned(self, store_with_tickets):
        """Test filtering by assigned agent."""
        tool = ListTicketsTool(store=store_with_tickets)
        result = await tool.execute(assigned_to="MCP_Agent1")

        assert result.success is True
        assert result.data["count"] == 1
        assert result.data["tickets"][0]["assigned_to"] == "MCP_Agent1"

    @pytest.mark.asyncio
    async def test_list_tickets_with_pagination(self, store_with_tickets):
        """Test pagination."""
        tool = ListTicketsTool(store=store_with_tickets)
        result = await tool.execute(limit=2, offset=0)

        assert result.success is True
        assert result.data["count"] == 2
        assert result.data["limit"] == 2
        assert result.data["offset"] == 0
        assert result.data["has_more"] is True

    @pytest.mark.asyncio
    async def test_list_tickets_invalid_status(self, store_with_tickets):
        """Test invalid status filter."""
        tool = ListTicketsTool(store=store_with_tickets)
        result = await tool.execute(status="invalid_status")

        assert result.success is False
        assert "Invalid" in result.error

    @pytest.mark.asyncio
    async def test_list_tickets_definition(self, store):
        """Test tool definition."""
        tool = ListTicketsTool(store=store)
        definition = tool.definition

        assert definition.metadata.name == "list_tickets"
        assert definition.metadata.category.value == "tickets"
        assert len(definition.parameters) >= 5


# =============================================================================
# GET TICKET DETAILS TOOL TESTS
# =============================================================================


class TestGetTicketDetailsTool:
    """Tests for GetTicketDetailsTool."""

    @pytest.mark.asyncio
    async def test_get_existing_ticket(self, store_with_tickets):
        """Test getting an existing ticket."""
        tool = GetTicketDetailsTool(store=store_with_tickets)
        result = await tool.execute(ticket_id="1")

        assert result.success is True
        assert result.data["ticket"]["id"] == "1"
        assert result.data["ticket"]["title"] == "Fix login button"
        assert "status_display" in result.data["ticket"]

    @pytest.mark.asyncio
    async def test_get_nonexistent_ticket(self, store):
        """Test getting a non-existent ticket."""
        tool = GetTicketDetailsTool(store=store)
        result = await tool.execute(ticket_id="999")

        assert result.success is False
        assert "not found" in result.error.lower()

    @pytest.mark.asyncio
    async def test_get_ticket_includes_history(self, store):
        """Test that ticket details include history."""
        # Create ticket with history
        ticket = Ticket(id="test", title="Test", description="Test description")
        ticket.add_history(action="created", actor="system", message="Created")
        store.create(ticket)

        tool = GetTicketDetailsTool(store=store)
        result = await tool.execute(ticket_id="test")

        assert result.success is True
        assert "history" in result.data["ticket"]
        assert len(result.data["ticket"]["history"]) >= 1


# =============================================================================
# CREATE TICKET TOOL TESTS
# =============================================================================


class TestCreateTicketTool:
    """Tests for CreateTicketTool."""

    @pytest.mark.asyncio
    async def test_create_basic_ticket(self, store):
        """Test creating a basic ticket."""
        tool = CreateTicketTool(store=store)
        result = await tool.execute(
            title="New feature request",
            description="Implement new functionality",
        )

        assert result.success is True
        assert "ticket_id" in result.data
        assert result.data["ticket"]["title"] == "New feature request"

    @pytest.mark.asyncio
    async def test_create_ticket_with_all_fields(self, store):
        """Test creating a ticket with all optional fields."""
        tool = CreateTicketTool(store=store)
        result = await tool.execute(
            title="Complete ticket",
            description="Full description",
            ticket_type="feature",
            priority="high",
            requirements=["Req 1", "Req 2"],
            files_to_modify=["file1.py", "file2.py"],
            labels=["important", "frontend"],
            app="test-app",
            created_by="admin",
        )

        assert result.success is True
        # Verify ticket was created in store
        ticket = store.get(result.data["ticket_id"])
        assert ticket.ticket_type == TicketType.FEATURE
        assert ticket.priority == TicketPriority.HIGH
        assert ticket.requirements == ["Req 1", "Req 2"]
        assert ticket.labels == ["important", "frontend"]

    @pytest.mark.asyncio
    async def test_create_ticket_missing_title(self, store):
        """Test creating a ticket without title."""
        tool = CreateTicketTool(store=store)
        result = await tool.execute(
            title="",
            description="Description",
        )

        assert result.success is False
        assert "title" in result.error.lower()

    @pytest.mark.asyncio
    async def test_create_ticket_missing_description(self, store):
        """Test creating a ticket without description."""
        tool = CreateTicketTool(store=store)
        result = await tool.execute(
            title="Title",
            description="",
        )

        assert result.success is False
        assert "description" in result.error.lower()

    @pytest.mark.asyncio
    async def test_create_ticket_invalid_priority(self, store):
        """Test creating a ticket with invalid priority."""
        tool = CreateTicketTool(store=store)
        result = await tool.execute(
            title="Title",
            description="Description",
            priority="super_urgent",
        )

        assert result.success is False
        assert "invalid" in result.error.lower()

    @pytest.mark.asyncio
    async def test_create_ticket_auto_generates_id(self, store):
        """Test that ticket ID is auto-generated."""
        tool = CreateTicketTool(store=store)

        result1 = await tool.execute(title="First", description="First description")
        result2 = await tool.execute(title="Second", description="Second description")

        assert result1.success is True
        assert result2.success is True
        assert result1.data["ticket_id"] != result2.data["ticket_id"]


# =============================================================================
# CLAIM TICKET TOOL TESTS
# =============================================================================


class TestClaimTicketTool:
    """Tests for ClaimTicketTool."""

    @pytest.mark.asyncio
    async def test_claim_open_ticket(self, store_with_tickets):
        """Test claiming an open ticket."""
        tool = ClaimTicketTool(store=store_with_tickets)
        result = await tool.execute(
            ticket_id="1",
            agent_name="MCP_Agent2",
        )

        assert result.success is True
        assert result.data["ticket"]["assigned_to"] == "MCP_Agent2"
        assert "In Progress" in result.data["ticket"]["status"]
        assert "next_steps" in result.data

    @pytest.mark.asyncio
    async def test_claim_in_progress_ticket_fails(self, store_with_tickets):
        """Test that claiming an in-progress ticket fails."""
        tool = ClaimTicketTool(store=store_with_tickets)
        result = await tool.execute(
            ticket_id="3",  # Already in progress
            agent_name="MCP_Agent2",
        )

        assert result.success is False
        assert "IN_PROGRESS" in result.error or "In Progress" in result.error

    @pytest.mark.asyncio
    async def test_claim_resolved_ticket_fails(self, store_with_tickets):
        """Test that claiming a resolved ticket fails."""
        tool = ClaimTicketTool(store=store_with_tickets)
        result = await tool.execute(
            ticket_id="4",  # Resolved
            agent_name="MCP_Agent1",
        )

        assert result.success is False
        assert "Resolved" in result.error or "RESOLVED" in result.error

    @pytest.mark.asyncio
    async def test_claim_nonexistent_ticket(self, store):
        """Test claiming a non-existent ticket."""
        tool = ClaimTicketTool(store=store)
        result = await tool.execute(
            ticket_id="999",
            agent_name="MCP_Agent1",
        )

        assert result.success is False
        assert "not found" in result.error.lower()

    @pytest.mark.asyncio
    async def test_claim_ticket_empty_agent_name(self, store_with_tickets):
        """Test claiming with empty agent name."""
        tool = ClaimTicketTool(store=store_with_tickets)
        result = await tool.execute(
            ticket_id="1",
            agent_name="",
        )

        assert result.success is False
        assert "agent" in result.error.lower()

    @pytest.mark.asyncio
    async def test_claim_ticket_creates_agent(self, store_with_tickets):
        """Test that claiming creates agent if not exists."""
        tool = ClaimTicketTool(store=store_with_tickets)
        result = await tool.execute(
            ticket_id="1",
            agent_name="NewAgent",
        )

        assert result.success is True
        agent = store_with_tickets.get_agent("NewAgent")
        assert agent is not None
        assert agent.tickets_in_progress == 1

    @pytest.mark.asyncio
    async def test_claim_ticket_updates_history(self, store_with_tickets):
        """Test that claiming adds history entry."""
        tool = ClaimTicketTool(store=store_with_tickets)
        await tool.execute(ticket_id="1", agent_name="Agent1")

        ticket = store_with_tickets.get("1")
        # Should have history entries for assignment and status change
        assert len(ticket.history) >= 2

    @pytest.mark.asyncio
    async def test_claim_ticket_assigned_to_other(self, store_with_tickets):
        """Test claiming a ticket assigned to someone else."""
        # First claim
        tool = ClaimTicketTool(store=store_with_tickets)
        await tool.execute(ticket_id="1", agent_name="Agent1")

        # Try to claim by another agent (but ticket is now in_progress)
        result = await tool.execute(ticket_id="1", agent_name="Agent2")

        assert result.success is False


# =============================================================================
# COMPLETE TICKET SAFELY TOOL TESTS
# =============================================================================


class TestCompleteTicketSafelyTool:
    """Tests for CompleteTicketSafelyTool."""

    @pytest.mark.asyncio
    async def test_complete_ticket_successfully(self, claimed_ticket_store):
        """Test completing a ticket with all required fields."""
        tool = CompleteTicketSafelyTool(store=claimed_ticket_store)
        result = await tool.execute(
            ticket_id="100",
            agent_name="TestAgent",
            problem_summary="The button was broken",
            solution_summary="Fixed the click handler",
            files_modified=["app.py", "templates/button.html"],
            before_screenshot="/screenshots/before.png",
            after_screenshot="/screenshots/after.png",
            testing_notes="Tested in Chrome and Firefox",
        )

        assert result.success is True
        assert "Under Review" in result.data["status"]  # Status includes emoji prefix
        assert "next_steps" in result.data

        # Verify ticket was updated
        ticket = claimed_ticket_store.get("100")
        assert ticket.status == TicketStatus.UNDER_REVIEW
        assert ticket.problem_summary == "The button was broken"
        assert ticket.solution_summary == "Fixed the click handler"
        assert ticket.before_screenshot == "/screenshots/before.png"

    @pytest.mark.asyncio
    async def test_complete_ticket_missing_before_screenshot(self, claimed_ticket_store):
        """Test completing without before screenshot."""
        tool = CompleteTicketSafelyTool(store=claimed_ticket_store)
        result = await tool.execute(
            ticket_id="100",
            agent_name="TestAgent",
            problem_summary="Problem",
            solution_summary="Solution",
            files_modified=["file.py"],
            before_screenshot="",
            after_screenshot="/after.png",
        )

        assert result.success is False
        assert "before screenshot" in result.error.lower()

    @pytest.mark.asyncio
    async def test_complete_ticket_missing_after_screenshot(self, claimed_ticket_store):
        """Test completing without after screenshot."""
        tool = CompleteTicketSafelyTool(store=claimed_ticket_store)
        result = await tool.execute(
            ticket_id="100",
            agent_name="TestAgent",
            problem_summary="Problem",
            solution_summary="Solution",
            files_modified=["file.py"],
            before_screenshot="/before.png",
            after_screenshot="",
        )

        assert result.success is False
        assert "after screenshot" in result.error.lower()

    @pytest.mark.asyncio
    async def test_complete_ticket_missing_problem_summary(self, claimed_ticket_store):
        """Test completing without problem summary."""
        tool = CompleteTicketSafelyTool(store=claimed_ticket_store)
        result = await tool.execute(
            ticket_id="100",
            agent_name="TestAgent",
            problem_summary="",
            solution_summary="Solution",
            files_modified=["file.py"],
            before_screenshot="/before.png",
            after_screenshot="/after.png",
        )

        assert result.success is False
        assert "problem summary" in result.error.lower()

    @pytest.mark.asyncio
    async def test_complete_ticket_wrong_agent(self, claimed_ticket_store):
        """Test completing by wrong agent."""
        tool = CompleteTicketSafelyTool(store=claimed_ticket_store)
        result = await tool.execute(
            ticket_id="100",
            agent_name="WrongAgent",
            problem_summary="Problem",
            solution_summary="Solution",
            files_modified=["file.py"],
            before_screenshot="/before.png",
            after_screenshot="/after.png",
        )

        assert result.success is False
        assert "TestAgent" in result.error  # Should mention assigned agent

    @pytest.mark.asyncio
    async def test_complete_open_ticket_fails(self, store_with_tickets):
        """Test completing an open ticket fails."""
        tool = CompleteTicketSafelyTool(store=store_with_tickets)
        result = await tool.execute(
            ticket_id="1",  # Open ticket
            agent_name="Agent1",
            problem_summary="Problem",
            solution_summary="Solution",
            files_modified=["file.py"],
            before_screenshot="/before.png",
            after_screenshot="/after.png",
        )

        assert result.success is False
        assert "IN_PROGRESS" in result.error or "In Progress" in result.error

    @pytest.mark.asyncio
    async def test_complete_ticket_updates_agent_stats(self, claimed_ticket_store):
        """Test that completing updates agent stats."""
        tool = CompleteTicketSafelyTool(store=claimed_ticket_store)
        await tool.execute(
            ticket_id="100",
            agent_name="TestAgent",
            problem_summary="Problem",
            solution_summary="Solution",
            files_modified=["file.py"],
            before_screenshot="/before.png",
            after_screenshot="/after.png",
        )

        agent = claimed_ticket_store.get_agent("TestAgent")
        assert agent.tickets_in_progress == 0


# =============================================================================
# UPDATE TICKET TOOL TESTS
# =============================================================================


class TestUpdateTicketTool:
    """Tests for UpdateTicketTool."""

    @pytest.mark.asyncio
    async def test_update_priority(self, store_with_tickets):
        """Test updating ticket priority."""
        tool = UpdateTicketTool(store=store_with_tickets)
        result = await tool.execute(
            ticket_id="1",
            agent_name="Agent1",
            priority="critical",
        )

        assert result.success is True
        assert "priority" in str(result.data["changes"])

        ticket = store_with_tickets.get("1")
        assert ticket.priority == TicketPriority.CRITICAL

    @pytest.mark.asyncio
    async def test_update_notes(self, store_with_tickets):
        """Test updating ticket notes."""
        tool = UpdateTicketTool(store=store_with_tickets)
        result = await tool.execute(
            ticket_id="1",
            agent_name="Agent1",
            notes="Additional notes here",
        )

        assert result.success is True
        ticket = store_with_tickets.get("1")
        assert "Additional notes here" in ticket.notes

    @pytest.mark.asyncio
    async def test_update_labels(self, store_with_tickets):
        """Test updating ticket labels."""
        tool = UpdateTicketTool(store=store_with_tickets)
        result = await tool.execute(
            ticket_id="1",
            agent_name="Agent1",
            labels=["new-label", "another-label"],
        )

        assert result.success is True
        ticket = store_with_tickets.get("1")
        assert "new-label" in ticket.labels

    @pytest.mark.asyncio
    async def test_update_nonexistent_ticket(self, store):
        """Test updating non-existent ticket."""
        tool = UpdateTicketTool(store=store)
        result = await tool.execute(
            ticket_id="999",
            agent_name="Agent1",
            priority="high",
        )

        assert result.success is False
        assert "not found" in result.error.lower()

    @pytest.mark.asyncio
    async def test_update_no_changes(self, store_with_tickets):
        """Test update with no actual changes."""
        tool = UpdateTicketTool(store=store_with_tickets)
        result = await tool.execute(
            ticket_id="1",
            agent_name="Agent1",
        )

        assert result.success is True
        assert "No changes made" in result.data["message"]

    @pytest.mark.asyncio
    async def test_update_multiple_fields(self, store_with_tickets):
        """Test updating multiple fields at once."""
        tool = UpdateTicketTool(store=store_with_tickets)
        result = await tool.execute(
            ticket_id="1",
            agent_name="Agent1",
            priority="low",
            labels=["updated"],
            notes="New note",
        )

        assert result.success is True
        assert len(result.data["changes"]) >= 3

    @pytest.mark.asyncio
    async def test_update_records_history(self, store_with_tickets):
        """Test that updates are recorded in history."""
        tool = UpdateTicketTool(store=store_with_tickets)
        original_ticket = store_with_tickets.get("1")
        original_history_len = len(original_ticket.history)

        await tool.execute(
            ticket_id="1",
            agent_name="Agent1",
            priority="critical",
        )

        ticket = store_with_tickets.get("1")
        assert len(ticket.history) > original_history_len


# =============================================================================
# SEARCH TICKETS TOOL TESTS
# =============================================================================


class TestSearchTicketsTool:
    """Tests for SearchTicketsTool."""

    @pytest.mark.asyncio
    async def test_search_by_title(self, store_with_tickets):
        """Test searching by title."""
        tool = SearchTicketsTool(store=store_with_tickets)
        result = await tool.execute(query="login")

        assert result.success is True
        assert result.data["count"] >= 1
        assert any("login" in t["title"].lower() for t in result.data["tickets"])

    @pytest.mark.asyncio
    async def test_search_by_description(self, store_with_tickets):
        """Test searching by description."""
        tool = SearchTicketsTool(store=store_with_tickets)
        result = await tool.execute(query="theme switching")

        assert result.success is True
        assert result.data["count"] >= 1

    @pytest.mark.asyncio
    async def test_search_no_results(self, store_with_tickets):
        """Test search with no results."""
        tool = SearchTicketsTool(store=store_with_tickets)
        result = await tool.execute(query="zzzznonexistent")

        assert result.success is True
        assert result.data["count"] == 0

    @pytest.mark.asyncio
    async def test_search_empty_query(self, store_with_tickets):
        """Test search with empty query."""
        tool = SearchTicketsTool(store=store_with_tickets)
        result = await tool.execute(query="")

        assert result.success is False
        assert "required" in result.error.lower()

    @pytest.mark.asyncio
    async def test_search_specific_fields(self, store_with_tickets):
        """Test searching in specific fields."""
        tool = SearchTicketsTool(store=store_with_tickets)
        result = await tool.execute(
            query="button",
            fields=["title"],
        )

        assert result.success is True
        assert result.data["fields_searched"] == ["title"]


# =============================================================================
# ADD TICKET COMMENT TOOL TESTS
# =============================================================================


class TestAddTicketCommentTool:
    """Tests for AddTicketCommentTool."""

    @pytest.mark.asyncio
    async def test_add_comment(self, store_with_tickets):
        """Test adding a comment."""
        tool = AddTicketCommentTool(store=store_with_tickets)
        result = await tool.execute(
            ticket_id="1",
            agent_name="Agent1",
            content="This is a test comment",
        )

        assert result.success is True
        assert "comment_id" in result.data

        ticket = store_with_tickets.get("1")
        assert len(ticket.comments) >= 1
        assert ticket.comments[-1].content == "This is a test comment"

    @pytest.mark.asyncio
    async def test_add_review_comment(self, store_with_tickets):
        """Test adding a review comment."""
        tool = AddTicketCommentTool(store=store_with_tickets)
        result = await tool.execute(
            ticket_id="1",
            agent_name="Reviewer",
            content="Code looks good",
            comment_type="review",
        )

        assert result.success is True
        ticket = store_with_tickets.get("1")
        assert ticket.comments[-1].comment_type == "review"

    @pytest.mark.asyncio
    async def test_add_comment_empty_content(self, store_with_tickets):
        """Test adding empty comment."""
        tool = AddTicketCommentTool(store=store_with_tickets)
        result = await tool.execute(
            ticket_id="1",
            agent_name="Agent1",
            content="",
        )

        assert result.success is False
        assert "content" in result.error.lower()

    @pytest.mark.asyncio
    async def test_add_comment_nonexistent_ticket(self, store):
        """Test adding comment to non-existent ticket."""
        tool = AddTicketCommentTool(store=store)
        result = await tool.execute(
            ticket_id="999",
            agent_name="Agent1",
            content="Comment",
        )

        assert result.success is False
        assert "not found" in result.error.lower()

    @pytest.mark.asyncio
    async def test_add_comment_records_in_history(self, store_with_tickets):
        """Test that comments are recorded in history."""
        tool = AddTicketCommentTool(store=store_with_tickets)
        original_ticket = store_with_tickets.get("1")
        original_history_len = len(original_ticket.history)

        await tool.execute(
            ticket_id="1",
            agent_name="Agent1",
            content="Test comment",
        )

        ticket = store_with_tickets.get("1")
        assert len(ticket.history) > original_history_len
        assert any("comment" in h.action for h in ticket.history)


# =============================================================================
# TOOL REGISTRATION TESTS
# =============================================================================


class TestToolRegistration:
    """Tests for tool registration and definitions."""

    def test_all_tools_exported(self):
        """Test all ticket tools are exported."""
        assert len(TICKET_TOOLS) == 8
        tool_names = [tool.__name__ for tool in TICKET_TOOLS]
        assert "ListTicketsTool" in tool_names
        assert "GetTicketDetailsTool" in tool_names
        assert "CreateTicketTool" in tool_names
        assert "ClaimTicketTool" in tool_names
        assert "CompleteTicketSafelyTool" in tool_names
        assert "UpdateTicketTool" in tool_names
        assert "SearchTicketsTool" in tool_names
        assert "AddTicketCommentTool" in tool_names

    def test_all_tools_have_valid_definitions(self, store):
        """Test all tools have valid definitions."""
        for ToolClass in TICKET_TOOLS:
            tool = ToolClass(store=store)
            definition = tool.definition

            assert definition.metadata.name, f"{ToolClass.__name__} missing name"
            assert definition.metadata.description, f"{ToolClass.__name__} missing description"
            assert definition.metadata.category.value == "tickets"

    def test_tool_mcp_schema(self, store):
        """Test tools generate valid MCP schemas."""
        for ToolClass in TICKET_TOOLS:
            tool = ToolClass(store=store)
            schema = tool.definition.to_mcp_schema()

            assert "name" in schema
            assert "description" in schema
            assert "inputSchema" in schema
            assert schema["inputSchema"]["type"] == "object"


# =============================================================================
# AGENT ENFORCEMENT TESTS
# =============================================================================


class TestAgentEnforcement:
    """Tests for agent enforcement rules."""

    @pytest.mark.asyncio
    async def test_claim_requires_agent_name(self, store_with_tickets):
        """Test that claim requires agent name."""
        tool = ClaimTicketTool(store=store_with_tickets)
        result = await tool.safe_execute(ticket_id="1")

        assert result.success is False
        # Should fail validation for missing required param
        assert "agent_name" in result.error

    @pytest.mark.asyncio
    async def test_complete_requires_agent_name(self, claimed_ticket_store):
        """Test that complete requires agent name."""
        tool = CompleteTicketSafelyTool(store=claimed_ticket_store)
        result = await tool.safe_execute(
            ticket_id="100",
            problem_summary="Problem",
            solution_summary="Solution",
            files_modified=["file.py"],
            before_screenshot="/before.png",
            after_screenshot="/after.png",
        )

        assert result.success is False
        assert "agent_name" in result.error

    @pytest.mark.asyncio
    async def test_agent_name_validation_too_long(self, store_with_tickets):
        """Test agent name length validation."""
        tool = ClaimTicketTool(store=store_with_tickets)
        result = await tool.execute(
            ticket_id="1",
            agent_name="A" * 100,  # Too long
        )

        assert result.success is False
        assert "too long" in result.error.lower()


# =============================================================================
# STATUS TRANSITION TESTS
# =============================================================================


class TestStatusTransitions:
    """Tests for ticket status workflow transitions."""

    @pytest.mark.asyncio
    async def test_open_to_in_progress(self, store_with_tickets):
        """Test transition from OPEN to IN_PROGRESS."""
        tool = ClaimTicketTool(store=store_with_tickets)
        result = await tool.execute(ticket_id="1", agent_name="Agent1")

        assert result.success is True
        ticket = store_with_tickets.get("1")
        assert ticket.status == TicketStatus.IN_PROGRESS

    @pytest.mark.asyncio
    async def test_in_progress_to_under_review(self, claimed_ticket_store):
        """Test transition from IN_PROGRESS to UNDER_REVIEW."""
        tool = CompleteTicketSafelyTool(store=claimed_ticket_store)
        result = await tool.execute(
            ticket_id="100",
            agent_name="TestAgent",
            problem_summary="Problem",
            solution_summary="Solution",
            files_modified=["file.py"],
            before_screenshot="/before.png",
            after_screenshot="/after.png",
        )

        assert result.success is True
        ticket = claimed_ticket_store.get("100")
        assert ticket.status == TicketStatus.UNDER_REVIEW


# =============================================================================
# ERROR HANDLING TESTS
# =============================================================================


class TestErrorHandling:
    """Tests for error handling."""

    @pytest.mark.asyncio
    async def test_store_exception_handling(self):
        """Test handling of store exceptions."""
        mock_store = MagicMock(spec=TicketStore)
        mock_store.list.side_effect = Exception("Database error")

        tool = ListTicketsTool(store=mock_store)
        result = await tool.execute()

        assert result.success is False
        assert "Database error" in result.error

    @pytest.mark.asyncio
    async def test_invalid_enum_value_handling(self, store):
        """Test handling of invalid enum values."""
        tool = CreateTicketTool(store=store)
        result = await tool.execute(
            title="Test",
            description="Test description",
            ticket_type="invalid_type",
        )

        assert result.success is False
        assert "invalid" in result.error.lower()


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestIntegration:
    """Integration tests for complete workflows."""

    @pytest.mark.asyncio
    async def test_complete_ticket_workflow(self, store):
        """Test complete ticket lifecycle."""
        # 1. Create ticket
        create_tool = CreateTicketTool(store=store)
        create_result = await create_tool.execute(
            title="Integration test ticket",
            description="Test the full workflow",
            ticket_type="task",
            priority="medium",
        )
        assert create_result.success is True
        ticket_id = create_result.data["ticket_id"]

        # 2. Claim ticket
        claim_tool = ClaimTicketTool(store=store)
        claim_result = await claim_tool.execute(
            ticket_id=ticket_id,
            agent_name="IntegrationTestAgent",
        )
        assert claim_result.success is True

        # 3. Add a comment
        comment_tool = AddTicketCommentTool(store=store)
        comment_result = await comment_tool.execute(
            ticket_id=ticket_id,
            agent_name="IntegrationTestAgent",
            content="Working on this now",
        )
        assert comment_result.success is True

        # 4. Update the ticket
        update_tool = UpdateTicketTool(store=store)
        update_result = await update_tool.execute(
            ticket_id=ticket_id,
            agent_name="IntegrationTestAgent",
            notes="Found the issue",
        )
        assert update_result.success is True

        # 5. Complete the ticket
        complete_tool = CompleteTicketSafelyTool(store=store)
        complete_result = await complete_tool.execute(
            ticket_id=ticket_id,
            agent_name="IntegrationTestAgent",
            problem_summary="The integration needed testing",
            solution_summary="Added comprehensive tests",
            files_modified=["tests/integration.py"],
            before_screenshot="/screenshots/before.png",
            after_screenshot="/screenshots/after.png",
            testing_notes="All tests pass",
        )
        assert complete_result.success is True

        # 6. Verify final state
        get_tool = GetTicketDetailsTool(store=store)
        get_result = await get_tool.execute(ticket_id=ticket_id)
        assert get_result.success is True

        ticket = get_result.data["ticket"]
        assert ticket["status"] == "under_review"
        assert len(ticket["comments"]) >= 1
        assert len(ticket["history"]) >= 4  # created, assigned, status changes, etc.

    @pytest.mark.asyncio
    async def test_search_and_list_consistency(self, store_with_tickets):
        """Test that search and list return consistent results."""
        list_tool = ListTicketsTool(store=store_with_tickets)
        search_tool = SearchTicketsTool(store=store_with_tickets)

        # List all high priority
        list_result = await list_tool.execute(priority="high")

        # Search for "button" (the high priority ticket)
        search_result = await search_tool.execute(query="button")

        # Both should find the same ticket
        assert list_result.success is True
        assert search_result.success is True

        list_ids = {t["id"] for t in list_result.data["tickets"]}
        search_ids = {t["id"] for t in search_result.data["tickets"]}

        # The high priority "login button" ticket should be in both
        assert "1" in list_ids
        assert "1" in search_ids

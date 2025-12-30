"""Tests for Fastband CLI tickets subcommand."""

import json
import re
import tempfile
from pathlib import Path

import pytest
from typer.testing import CliRunner

from fastband.cli.main import app
from fastband.tickets import (
    StorageFactory,
    Ticket,
    TicketPriority,
    TicketStatus,
    TicketType,
    get_store,
)

runner = CliRunner()

# Regex to strip ANSI escape codes from output
ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*m")


def strip_ansi(text: str) -> str:
    """Strip ANSI escape codes from text."""
    return ANSI_ESCAPE.sub("", text)


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture(autouse=True)
def clear_store_cache():
    """Clear the storage factory cache before each test."""
    StorageFactory.clear_cache()
    yield
    StorageFactory.clear_cache()


@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def ticket_store(temp_dir):
    """Create a ticket store for testing."""
    store_path = temp_dir / "tickets.json"
    return get_store(store_path)


@pytest.fixture
def store_path(temp_dir):
    """Return the store path for CLI commands."""
    return temp_dir / "tickets.json"


@pytest.fixture
def populated_store(store_path):
    """Create a store with sample tickets."""
    store = get_store(store_path)

    # Create sample tickets with known IDs for testing
    tickets = [
        Ticket(
            id="1",
            title="Fix login bug",
            description="Users cannot log in with special characters in password",
            ticket_type=TicketType.BUG,
            priority=TicketPriority.HIGH,
            status=TicketStatus.OPEN,
            labels=["auth", "urgent"],
        ),
        Ticket(
            id="2",
            title="Add dark mode",
            description="Implement dark mode toggle in settings",
            ticket_type=TicketType.FEATURE,
            priority=TicketPriority.MEDIUM,
            status=TicketStatus.IN_PROGRESS,
            assigned_to="Agent1",
            labels=["ui"],
        ),
        Ticket(
            id="3",
            title="Update documentation",
            description="Update API docs for v2.0",
            ticket_type=TicketType.DOCUMENTATION,
            priority=TicketPriority.LOW,
            status=TicketStatus.OPEN,
        ),
        Ticket(
            id="4",
            title="Performance optimization",
            description="Optimize database queries",
            ticket_type=TicketType.PERFORMANCE,
            priority=TicketPriority.CRITICAL,
            status=TicketStatus.UNDER_REVIEW,
            assigned_to="Agent2",
        ),
        Ticket(
            id="5",
            title="Security audit",
            description="Conduct security review of auth module",
            ticket_type=TicketType.SECURITY,
            priority=TicketPriority.HIGH,
            status=TicketStatus.BLOCKED,
            labels=["security", "auth"],
        ),
    ]

    for ticket in tickets:
        store.create(ticket)

    return store


# =============================================================================
# HELP TESTS
# =============================================================================


class TestTicketsHelp:
    """Tests for tickets help output."""

    def test_tickets_help(self):
        """Test tickets command help."""
        result = runner.invoke(app, ["tickets", "--help"])
        assert result.exit_code == 0
        output = strip_ansi(result.stdout)
        assert "list" in output
        assert "create" in output
        assert "show" in output
        assert "claim" in output
        assert "complete" in output
        assert "search" in output
        assert "update" in output

    def test_tickets_list_help(self):
        """Test tickets list command help."""
        result = runner.invoke(app, ["tickets", "list", "--help"])
        assert result.exit_code == 0
        output = strip_ansi(result.stdout)
        assert "--status" in output
        assert "--priority" in output
        assert "--assigned-to" in output
        assert "--json" in output

    def test_tickets_create_help(self):
        """Test tickets create command help."""
        result = runner.invoke(app, ["tickets", "create", "--help"])
        assert result.exit_code == 0
        output = strip_ansi(result.stdout)
        assert "--title" in output
        assert "--description" in output
        assert "--type" in output
        assert "--priority" in output
        assert "--interactive" in output

    def test_tickets_show_help(self):
        """Test tickets show command help."""
        result = runner.invoke(app, ["tickets", "show", "--help"])
        assert result.exit_code == 0
        output = strip_ansi(result.stdout)
        assert "TICKET_ID" in output
        assert "--json" in output

    def test_tickets_claim_help(self):
        """Test tickets claim command help."""
        result = runner.invoke(app, ["tickets", "claim", "--help"])
        assert result.exit_code == 0
        output = strip_ansi(result.stdout)
        assert "TICKET_ID" in output
        assert "--agent" in output

    def test_tickets_complete_help(self):
        """Test tickets complete command help."""
        result = runner.invoke(app, ["tickets", "complete", "--help"])
        assert result.exit_code == 0
        output = strip_ansi(result.stdout)
        assert "--problem" in output
        assert "--solution" in output
        assert "--files" in output

    def test_tickets_search_help(self):
        """Test tickets search command help."""
        result = runner.invoke(app, ["tickets", "search", "--help"])
        assert result.exit_code == 0
        output = strip_ansi(result.stdout)
        assert "QUERY" in output
        assert "--fields" in output

    def test_tickets_update_help(self):
        """Test tickets update command help."""
        result = runner.invoke(app, ["tickets", "update", "--help"])
        assert result.exit_code == 0
        output = strip_ansi(result.stdout)
        assert "--title" in output
        assert "--status" in output
        assert "--priority" in output
        assert "--assigned-to" in output


# =============================================================================
# LIST COMMAND TESTS
# =============================================================================


class TestTicketsListCommand:
    """Tests for tickets list command."""

    def test_list_empty_store(self, store_path):
        """Test listing with no tickets."""
        result = runner.invoke(app, ["tickets", "list", "--path", str(store_path)])
        assert result.exit_code == 0
        assert "no tickets found" in result.stdout.lower()

    def test_list_shows_tickets(self, populated_store, store_path):
        """Test listing shows all tickets."""
        result = runner.invoke(app, ["tickets", "list", "--path", str(store_path)])
        assert result.exit_code == 0
        # Check for parts of the titles (may be split across lines in table)
        assert "login" in result.stdout.lower() or "Fix" in result.stdout
        assert "dark" in result.stdout.lower() or "Add" in result.stdout
        assert "Showing 5 ticket" in result.stdout

    def test_list_shows_table_columns(self, populated_store, store_path):
        """Test list shows proper table columns."""
        result = runner.invoke(app, ["tickets", "list", "--path", str(store_path)])
        assert result.exit_code == 0
        assert "ID" in result.stdout
        assert "Title" in result.stdout
        assert "Status" in result.stdout
        assert "Priority" in result.stdout

    def test_list_filter_by_status(self, populated_store, store_path):
        """Test filtering tickets by status."""
        result = runner.invoke(
            app, ["tickets", "list", "--status", "open", "--path", str(store_path)]
        )
        assert result.exit_code == 0
        assert "login" in result.stdout.lower() or "Fix" in result.stdout
        # Verify we got 2 open tickets
        assert "Showing 2 ticket" in result.stdout

    def test_list_filter_by_priority(self, populated_store, store_path):
        """Test filtering tickets by priority."""
        result = runner.invoke(
            app, ["tickets", "list", "--priority", "high", "--path", str(store_path)]
        )
        assert result.exit_code == 0
        # Should have 2 high priority tickets
        assert "Showing 2 ticket" in result.stdout
        assert "High" in result.stdout

    def test_list_filter_by_type(self, populated_store, store_path):
        """Test filtering tickets by type."""
        result = runner.invoke(app, ["tickets", "list", "--type", "bug", "--path", str(store_path)])
        assert result.exit_code == 0
        assert "Showing 1 ticket" in result.stdout
        assert "Bug" in result.stdout

    def test_list_filter_by_assigned_to(self, populated_store, store_path):
        """Test filtering tickets by assignee."""
        result = runner.invoke(
            app, ["tickets", "list", "--assigned-to", "Agent1", "--path", str(store_path)]
        )
        assert result.exit_code == 0
        assert "Showing 1 ticket" in result.stdout
        assert "Agent1" in result.stdout

    def test_list_invalid_status(self, store_path):
        """Test list with invalid status."""
        result = runner.invoke(
            app, ["tickets", "list", "--status", "invalid", "--path", str(store_path)]
        )
        assert result.exit_code == 1
        assert "invalid status" in result.stdout.lower()

    def test_list_invalid_priority(self, store_path):
        """Test list with invalid priority."""
        result = runner.invoke(
            app, ["tickets", "list", "--priority", "invalid", "--path", str(store_path)]
        )
        assert result.exit_code == 1
        assert "invalid priority" in result.stdout.lower()

    def test_list_invalid_type(self, store_path):
        """Test list with invalid type."""
        result = runner.invoke(
            app, ["tickets", "list", "--type", "invalid", "--path", str(store_path)]
        )
        assert result.exit_code == 1
        assert "invalid type" in result.stdout.lower()

    def test_list_json_output(self, populated_store, store_path):
        """Test list with JSON output."""
        result = runner.invoke(app, ["tickets", "list", "--json", "--path", str(store_path)])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert isinstance(data, list)
        assert len(data) == 5
        assert all("id" in ticket for ticket in data)
        assert all("title" in ticket for ticket in data)

    def test_list_json_empty(self, store_path):
        """Test list JSON output when empty."""
        result = runner.invoke(app, ["tickets", "list", "--json", "--path", str(store_path)])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data == []

    def test_list_with_limit(self, populated_store, store_path):
        """Test list with limit."""
        result = runner.invoke(app, ["tickets", "list", "--limit", "2", "--path", str(store_path)])
        assert result.exit_code == 0
        assert "Showing 2 ticket" in result.stdout

    def test_list_combined_filters(self, populated_store, store_path):
        """Test list with multiple filters."""
        result = runner.invoke(
            app,
            [
                "tickets",
                "list",
                "--status",
                "open",
                "--priority",
                "high",
                "--path",
                str(store_path),
            ],
        )
        assert result.exit_code == 0
        # Only 1 ticket is both open AND high priority (Fix login bug)
        assert "Showing 1 ticket" in result.stdout


# =============================================================================
# CREATE COMMAND TESTS
# =============================================================================


class TestTicketsCreateCommand:
    """Tests for tickets create command."""

    def test_create_ticket_minimal(self, store_path):
        """Test creating a ticket with minimal options."""
        result = runner.invoke(
            app, ["tickets", "create", "--title", "Test ticket", "--path", str(store_path)]
        )
        assert result.exit_code == 0
        assert "Created ticket" in result.stdout

    def test_create_ticket_full(self, store_path):
        """Test creating a ticket with all options."""
        result = runner.invoke(
            app,
            [
                "tickets",
                "create",
                "--title",
                "Full ticket",
                "--description",
                "A complete ticket",
                "--type",
                "bug",
                "--priority",
                "high",
                "--assigned-to",
                "TestAgent",
                "--labels",
                "test,important",
                "--path",
                str(store_path),
            ],
        )
        assert result.exit_code == 0
        assert "Created ticket" in result.stdout
        assert "Full ticket" in result.stdout
        assert "high" in result.stdout.lower() or "High" in result.stdout

    def test_create_without_title(self, store_path):
        """Test create fails without title."""
        result = runner.invoke(
            app, ["tickets", "create", "--description", "No title", "--path", str(store_path)]
        )
        assert result.exit_code == 1
        assert "title is required" in result.stdout.lower()

    def test_create_invalid_type(self, store_path):
        """Test create with invalid type."""
        result = runner.invoke(
            app,
            [
                "tickets",
                "create",
                "--title",
                "Test",
                "--type",
                "invalid",
                "--path",
                str(store_path),
            ],
        )
        assert result.exit_code == 1
        assert "invalid type" in result.stdout.lower()

    def test_create_invalid_priority(self, store_path):
        """Test create with invalid priority."""
        result = runner.invoke(
            app,
            [
                "tickets",
                "create",
                "--title",
                "Test",
                "--priority",
                "invalid",
                "--path",
                str(store_path),
            ],
        )
        assert result.exit_code == 1
        assert "invalid priority" in result.stdout.lower()

    def test_create_json_output(self, store_path):
        """Test create with JSON output."""
        result = runner.invoke(
            app,
            ["tickets", "create", "--title", "JSON ticket", "--json", "--path", str(store_path)],
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["title"] == "JSON ticket"
        assert "id" in data

    def test_create_interactive(self, store_path):
        """Test interactive ticket creation."""
        result = runner.invoke(
            app,
            ["tickets", "create", "--interactive", "--path", str(store_path)],
            input="Interactive Ticket\nDescription here\ntask\nmedium\n\n\n",
        )
        assert result.exit_code == 0
        assert "Created ticket" in result.stdout

    def test_create_with_labels(self, store_path):
        """Test creating ticket with labels."""
        result = runner.invoke(
            app,
            [
                "tickets",
                "create",
                "--title",
                "Labeled ticket",
                "--labels",
                "label1, label2, label3",
                "--path",
                str(store_path),
            ],
        )
        assert result.exit_code == 0
        assert "label1" in result.stdout or "Created ticket" in result.stdout


# =============================================================================
# SHOW COMMAND TESTS
# =============================================================================


class TestTicketsShowCommand:
    """Tests for tickets show command."""

    def test_show_ticket(self, populated_store, store_path):
        """Test showing ticket details."""
        # Need to reference the store to ensure it's loaded
        _ = populated_store
        result = runner.invoke(app, ["tickets", "show", "1", "--path", str(store_path)])
        assert result.exit_code == 0
        assert "login" in result.stdout.lower()
        assert "Status" in result.stdout
        assert "Priority" in result.stdout

    def test_show_nonexistent_ticket(self, store_path):
        """Test showing nonexistent ticket."""
        result = runner.invoke(app, ["tickets", "show", "999", "--path", str(store_path)])
        assert result.exit_code == 1
        assert "not found" in result.stdout.lower()

    def test_show_json_output(self, populated_store, store_path):
        """Test show with JSON output."""
        _ = populated_store
        result = runner.invoke(app, ["tickets", "show", "1", "--json", "--path", str(store_path)])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["title"] == "Fix login bug"
        assert "id" in data
        assert "status" in data

    def test_show_displays_labels(self, populated_store, store_path):
        """Test show displays labels."""
        _ = populated_store
        result = runner.invoke(app, ["tickets", "show", "1", "--path", str(store_path)])
        assert result.exit_code == 0
        assert "auth" in result.stdout or "urgent" in result.stdout or "Labels" in result.stdout

    def test_show_displays_assignee(self, populated_store, store_path):
        """Test show displays assignee."""
        _ = populated_store
        result = runner.invoke(app, ["tickets", "show", "2", "--path", str(store_path)])
        assert result.exit_code == 0
        assert "Agent1" in result.stdout or "Assigned" in result.stdout


# =============================================================================
# CLAIM COMMAND TESTS
# =============================================================================


class TestTicketsClaimCommand:
    """Tests for tickets claim command."""

    def test_claim_open_ticket(self, populated_store, store_path):
        """Test claiming an open ticket."""
        _ = populated_store
        result = runner.invoke(
            app, ["tickets", "claim", "1", "--agent", "TestAgent", "--path", str(store_path)]
        )
        assert result.exit_code == 0
        assert "Claimed ticket" in result.stdout
        assert "TestAgent" in result.stdout

    def test_claim_blocked_ticket(self, populated_store, store_path):
        """Test claiming a blocked ticket."""
        _ = populated_store
        result = runner.invoke(
            app,
            [
                "tickets",
                "claim",
                "5",  # Security audit is blocked
                "--agent",
                "TestAgent",
                "--path",
                str(store_path),
            ],
        )
        assert result.exit_code == 0
        assert "Claimed ticket" in result.stdout

    def test_claim_in_progress_ticket(self, populated_store, store_path):
        """Test cannot claim in-progress ticket."""
        _ = populated_store
        result = runner.invoke(
            app,
            [
                "tickets",
                "claim",
                "2",  # Add dark mode is in progress
                "--agent",
                "TestAgent",
                "--path",
                str(store_path),
            ],
        )
        assert result.exit_code == 1
        assert "cannot claim" in result.stdout.lower()

    def test_claim_nonexistent_ticket(self, store_path):
        """Test claiming nonexistent ticket."""
        result = runner.invoke(
            app, ["tickets", "claim", "999", "--agent", "TestAgent", "--path", str(store_path)]
        )
        assert result.exit_code == 1
        assert "not found" in result.stdout.lower()

    def test_claim_json_output(self, populated_store, store_path):
        """Test claim with JSON output."""
        _ = populated_store
        result = runner.invoke(
            app,
            ["tickets", "claim", "1", "--agent", "TestAgent", "--json", "--path", str(store_path)],
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["success"] is True
        assert data["agent"] == "TestAgent"
        assert data["status"] == "in_progress"

    def test_claim_updates_status(self, populated_store, store_path):
        """Test claiming updates ticket status."""
        _ = populated_store
        # Claim the ticket (use JSON to also verify status)
        result = runner.invoke(
            app,
            ["tickets", "claim", "1", "--agent", "TestAgent", "--json", "--path", str(store_path)],
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["status"] == "in_progress"
        assert data["agent"] == "TestAgent"


# =============================================================================
# COMPLETE COMMAND TESTS
# =============================================================================


class TestTicketsCompleteCommand:
    """Tests for tickets complete command."""

    def test_complete_in_progress_ticket(self, populated_store, store_path):
        """Test completing an in-progress ticket."""
        _ = populated_store
        result = runner.invoke(
            app,
            [
                "tickets",
                "complete",
                "2",  # Add dark mode is in progress
                "--problem",
                "Missing dark mode feature",
                "--solution",
                "Implemented theme toggle",
                "--path",
                str(store_path),
            ],
        )
        assert result.exit_code == 0
        assert "Completed ticket" in result.stdout

    def test_complete_with_files(self, populated_store, store_path):
        """Test completing with files modified."""
        _ = populated_store
        result = runner.invoke(
            app,
            [
                "tickets",
                "complete",
                "2",
                "--problem",
                "Missing feature",
                "--solution",
                "Added feature",
                "--files",
                "app.py, styles.css, config.json",
                "--path",
                str(store_path),
            ],
        )
        assert result.exit_code == 0
        assert "Completed ticket" in result.stdout

    def test_complete_with_testing_notes(self, populated_store, store_path):
        """Test completing with testing notes."""
        _ = populated_store
        result = runner.invoke(
            app,
            [
                "tickets",
                "complete",
                "2",
                "--problem",
                "Bug found",
                "--solution",
                "Fixed bug",
                "--testing",
                "Ran unit tests and manual testing",
                "--path",
                str(store_path),
            ],
        )
        assert result.exit_code == 0
        assert "Completed ticket" in result.stdout

    def test_complete_open_ticket(self, populated_store, store_path):
        """Test cannot complete open ticket."""
        _ = populated_store
        result = runner.invoke(
            app,
            [
                "tickets",
                "complete",
                "1",  # Fix login bug is open
                "--problem",
                "Problem",
                "--solution",
                "Solution",
                "--path",
                str(store_path),
            ],
        )
        assert result.exit_code == 1
        assert "cannot complete" in result.stdout.lower()

    def test_complete_nonexistent_ticket(self, store_path):
        """Test completing nonexistent ticket."""
        result = runner.invoke(
            app,
            [
                "tickets",
                "complete",
                "999",
                "--problem",
                "Problem",
                "--solution",
                "Solution",
                "--path",
                str(store_path),
            ],
        )
        assert result.exit_code == 1
        assert "not found" in result.stdout.lower()

    def test_complete_json_output(self, populated_store, store_path):
        """Test complete with JSON output."""
        _ = populated_store
        result = runner.invoke(
            app,
            [
                "tickets",
                "complete",
                "2",
                "--problem",
                "Problem summary",
                "--solution",
                "Solution summary",
                "--json",
                "--path",
                str(store_path),
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["success"] is True
        assert data["status"] == "under_review"
        assert data["problem_summary"] == "Problem summary"

    def test_complete_updates_status(self, populated_store, store_path):
        """Test completing updates ticket status to under_review."""
        _ = populated_store
        runner.invoke(
            app,
            [
                "tickets",
                "complete",
                "2",
                "--problem",
                "Problem",
                "--solution",
                "Solution",
                "--path",
                str(store_path),
            ],
        )
        result = runner.invoke(app, ["tickets", "show", "2", "--json", "--path", str(store_path)])
        data = json.loads(result.stdout)
        assert data["status"] == "under_review"


# =============================================================================
# SEARCH COMMAND TESTS
# =============================================================================


class TestTicketsSearchCommand:
    """Tests for tickets search command."""

    def test_search_by_title(self, populated_store, store_path):
        """Test searching by title."""
        result = runner.invoke(app, ["tickets", "search", "login", "--path", str(store_path)])
        assert result.exit_code == 0
        assert "Fix login bug" in result.stdout

    def test_search_by_description(self, populated_store, store_path):
        """Test searching by description."""
        result = runner.invoke(
            app, ["tickets", "search", "special characters", "--path", str(store_path)]
        )
        assert result.exit_code == 0
        assert "Fix login bug" in result.stdout

    def test_search_no_results(self, populated_store, store_path):
        """Test search with no matching results."""
        result = runner.invoke(
            app, ["tickets", "search", "nonexistent query xyz", "--path", str(store_path)]
        )
        assert result.exit_code == 0
        assert "no tickets found" in result.stdout.lower()

    def test_search_json_output(self, populated_store, store_path):
        """Test search with JSON output."""
        result = runner.invoke(
            app, ["tickets", "search", "login", "--json", "--path", str(store_path)]
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert isinstance(data, list)
        assert len(data) >= 1
        assert any("login" in t["title"].lower() for t in data)

    def test_search_empty_json(self, populated_store, store_path):
        """Test search JSON output when empty."""
        result = runner.invoke(
            app, ["tickets", "search", "xyz123nonexistent", "--json", "--path", str(store_path)]
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data == []

    def test_search_with_limit(self, populated_store, store_path):
        """Test search with limit."""
        result = runner.invoke(
            app,
            [
                "tickets",
                "search",
                "a",  # Broad search
                "--limit",
                "2",
                "--path",
                str(store_path),
            ],
        )
        assert result.exit_code == 0
        # Should find some results but limited

    def test_search_specific_fields(self, populated_store, store_path):
        """Test search in specific fields."""
        result = runner.invoke(
            app, ["tickets", "search", "dark", "--fields", "title", "--path", str(store_path)]
        )
        assert result.exit_code == 0
        assert "Add dark mode" in result.stdout

    def test_search_case_insensitive(self, populated_store, store_path):
        """Test search is case insensitive."""
        result = runner.invoke(app, ["tickets", "search", "LOGIN", "--path", str(store_path)])
        assert result.exit_code == 0
        assert "Fix login bug" in result.stdout


# =============================================================================
# UPDATE COMMAND TESTS
# =============================================================================


class TestTicketsUpdateCommand:
    """Tests for tickets update command."""

    def test_update_title(self, populated_store, store_path):
        """Test updating ticket title."""
        _ = populated_store
        result = runner.invoke(
            app, ["tickets", "update", "1", "--title", "New title", "--path", str(store_path)]
        )
        assert result.exit_code == 0
        assert "Updated ticket" in result.stdout
        assert "title" in result.stdout.lower()

    def test_update_description(self, populated_store, store_path):
        """Test updating ticket description."""
        _ = populated_store
        result = runner.invoke(
            app,
            [
                "tickets",
                "update",
                "1",
                "--description",
                "New description",
                "--path",
                str(store_path),
            ],
        )
        assert result.exit_code == 0
        assert "Updated ticket" in result.stdout

    def test_update_priority(self, populated_store, store_path):
        """Test updating ticket priority."""
        _ = populated_store
        result = runner.invoke(
            app,
            [
                "tickets",
                "update",
                "3",  # Update documentation - low priority
                "--priority",
                "high",
                "--path",
                str(store_path),
            ],
        )
        assert result.exit_code == 0
        assert "Updated ticket" in result.stdout
        assert "priority" in result.stdout.lower()

    def test_update_invalid_priority(self, populated_store, store_path):
        """Test update with invalid priority."""
        _ = populated_store
        result = runner.invoke(
            app, ["tickets", "update", "1", "--priority", "invalid", "--path", str(store_path)]
        )
        assert result.exit_code == 1
        assert "invalid priority" in result.stdout.lower()

    def test_update_status_valid_transition(self, populated_store, store_path):
        """Test updating status with valid transition."""
        _ = populated_store
        result = runner.invoke(
            app,
            [
                "tickets",
                "update",
                "1",  # Open ticket
                "--status",
                "in_progress",
                "--path",
                str(store_path),
            ],
        )
        assert result.exit_code == 0
        assert "Updated ticket" in result.stdout

    def test_update_status_invalid_transition(self, populated_store, store_path):
        """Test update with invalid status transition."""
        _ = populated_store
        result = runner.invoke(
            app,
            [
                "tickets",
                "update",
                "1",  # Open ticket
                "--status",
                "resolved",  # Can't go directly from open to resolved
                "--path",
                str(store_path),
            ],
        )
        assert result.exit_code == 1
        assert "invalid" in result.stdout.lower()

    def test_update_assign(self, populated_store, store_path):
        """Test assigning ticket."""
        _ = populated_store
        result = runner.invoke(
            app, ["tickets", "update", "1", "--assigned-to", "NewAgent", "--path", str(store_path)]
        )
        assert result.exit_code == 0
        assert "Updated ticket" in result.stdout
        assert "NewAgent" in result.stdout or "assigned" in result.stdout.lower()

    def test_update_unassign(self, populated_store, store_path):
        """Test unassigning ticket."""
        _ = populated_store
        result = runner.invoke(
            app,
            [
                "tickets",
                "update",
                "2",  # Already assigned
                "--assigned-to",
                "",
                "--path",
                str(store_path),
            ],
        )
        assert result.exit_code == 0
        assert "Updated ticket" in result.stdout
        assert "unassigned" in result.stdout.lower()

    def test_update_labels(self, populated_store, store_path):
        """Test updating labels."""
        _ = populated_store
        result = runner.invoke(
            app,
            [
                "tickets",
                "update",
                "1",
                "--labels",
                "new-label, another-label",
                "--path",
                str(store_path),
            ],
        )
        assert result.exit_code == 0
        assert "Updated ticket" in result.stdout
        assert "labels" in result.stdout.lower()

    def test_update_notes(self, populated_store, store_path):
        """Test adding notes."""
        _ = populated_store
        result = runner.invoke(
            app,
            [
                "tickets",
                "update",
                "1",
                "--notes",
                "Additional notes here",
                "--path",
                str(store_path),
            ],
        )
        assert result.exit_code == 0
        assert "Updated ticket" in result.stdout
        assert "notes" in result.stdout.lower()

    def test_update_nonexistent_ticket(self, store_path):
        """Test updating nonexistent ticket."""
        result = runner.invoke(
            app, ["tickets", "update", "999", "--title", "New title", "--path", str(store_path)]
        )
        assert result.exit_code == 1
        assert "not found" in result.stdout.lower()

    def test_update_no_changes(self, populated_store, store_path):
        """Test update with no changes specified."""
        _ = populated_store
        result = runner.invoke(app, ["tickets", "update", "1", "--path", str(store_path)])
        assert result.exit_code == 0
        assert "no changes" in result.stdout.lower()

    def test_update_multiple_fields(self, populated_store, store_path):
        """Test updating multiple fields at once."""
        _ = populated_store
        result = runner.invoke(
            app,
            [
                "tickets",
                "update",
                "1",
                "--title",
                "Updated title",
                "--priority",
                "critical",
                "--notes",
                "Important update",
                "--path",
                str(store_path),
            ],
        )
        assert result.exit_code == 0
        assert "Updated ticket" in result.stdout

    def test_update_json_output(self, populated_store, store_path):
        """Test update with JSON output."""
        _ = populated_store
        result = runner.invoke(
            app,
            [
                "tickets",
                "update",
                "1",
                "--title",
                "JSON update",
                "--json",
                "--path",
                str(store_path),
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["success"] is True
        assert "changes" in data


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestTicketsIntegration:
    """Integration tests for tickets CLI workflow."""

    def test_full_ticket_workflow(self, store_path):
        """Test complete ticket lifecycle."""
        # 1. Create ticket
        result = runner.invoke(
            app,
            [
                "tickets",
                "create",
                "--title",
                "Workflow test ticket",
                "--description",
                "Testing full workflow",
                "--type",
                "task",
                "--priority",
                "medium",
                "--path",
                str(store_path),
            ],
        )
        assert result.exit_code == 0
        assert "Created ticket" in result.stdout

        # 2. List to verify
        result = runner.invoke(app, ["tickets", "list", "--path", str(store_path)])
        assert "Showing 1 ticket" in result.stdout

        # 3. Show details - using the first ticket ID
        result = runner.invoke(app, ["tickets", "show", "1", "--path", str(store_path)])
        assert "Workflow" in result.stdout or result.exit_code == 0

        # 4. Claim ticket
        result = runner.invoke(
            app, ["tickets", "claim", "1", "--agent", "WorkflowAgent", "--path", str(store_path)]
        )
        assert result.exit_code == 0

        # 5. Complete ticket
        result = runner.invoke(
            app,
            [
                "tickets",
                "complete",
                "1",
                "--problem",
                "Task needed to be done",
                "--solution",
                "Completed the task",
                "--files",
                "file1.py, file2.py",
                "--path",
                str(store_path),
            ],
        )
        assert result.exit_code == 0

        # 6. Verify final status
        result = runner.invoke(app, ["tickets", "show", "1", "--json", "--path", str(store_path)])
        data = json.loads(result.stdout)
        assert data["status"] == "under_review"
        assert data["assigned_to"] == "WorkflowAgent"

    def test_search_after_create(self, store_path):
        """Test search finds newly created tickets."""
        # Create ticket with unique content
        runner.invoke(
            app,
            [
                "tickets",
                "create",
                "--title",
                "Unique searchable ticket xyz123",
                "--path",
                str(store_path),
            ],
        )

        # Search for it
        result = runner.invoke(app, ["tickets", "search", "xyz123", "--path", str(store_path)])
        assert "searchable" in result.stdout.lower() or "xyz123" in result.stdout

    def test_filter_after_update(self, store_path):
        """Test filters work correctly after updates."""
        # Create ticket
        runner.invoke(
            app,
            [
                "tickets",
                "create",
                "--title",
                "Filter test ticket",
                "--priority",
                "low",
                "--path",
                str(store_path),
            ],
        )

        # Verify low priority filter finds the ticket
        result = runner.invoke(
            app, ["tickets", "list", "--priority", "low", "--path", str(store_path)]
        )
        assert "Showing 1 ticket" in result.stdout

        # Update priority
        runner.invoke(
            app, ["tickets", "update", "1", "--priority", "high", "--path", str(store_path)]
        )

        # Verify high priority filter now includes it
        result = runner.invoke(
            app, ["tickets", "list", "--priority", "high", "--path", str(store_path)]
        )
        assert "Showing 1 ticket" in result.stdout

        # Low priority filter should not include it anymore
        result = runner.invoke(
            app, ["tickets", "list", "--priority", "low", "--path", str(store_path)]
        )
        assert "no tickets found" in result.stdout.lower()

    def test_main_help_includes_tickets(self):
        """Test main help includes tickets command."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "tickets" in result.stdout


# =============================================================================
# EDGE CASE TESTS
# =============================================================================


class TestTicketsEdgeCases:
    """Tests for edge cases and error handling."""

    def test_special_characters_in_title(self, store_path):
        """Test ticket with special characters in title."""
        result = runner.invoke(
            app,
            [
                "tickets",
                "create",
                "--title",
                "Test <script>alert('xss')</script>",
                "--path",
                str(store_path),
            ],
        )
        assert result.exit_code == 0
        assert "Created ticket" in result.stdout

    def test_unicode_in_description(self, store_path):
        """Test ticket with unicode in description."""
        result = runner.invoke(
            app,
            [
                "tickets",
                "create",
                "--title",
                "Unicode test",
                "--description",
                "Test with unicode: \u00e9\u00e8\u00e0\u00f1",
                "--path",
                str(store_path),
            ],
        )
        assert result.exit_code == 0

    def test_long_title_truncation(self, store_path):
        """Test long titles are handled in list view."""
        long_title = "A" * 100
        runner.invoke(app, ["tickets", "create", "--title", long_title, "--path", str(store_path)])

        result = runner.invoke(app, ["tickets", "list", "--path", str(store_path)])
        assert result.exit_code == 0
        # Title should be truncated - Rich uses ellipsis character
        assert "Showing 1 ticket" in result.stdout
        # Check that not all 100 A's are shown (truncation happened)
        assert "A" * 100 not in result.stdout

    def test_empty_labels(self, store_path):
        """Test creating ticket with empty labels."""
        result = runner.invoke(
            app,
            [
                "tickets",
                "create",
                "--title",
                "No labels",
                "--labels",
                "",
                "--path",
                str(store_path),
            ],
        )
        assert result.exit_code == 0

    def test_whitespace_labels(self, store_path):
        """Test labels with whitespace are trimmed."""
        result = runner.invoke(
            app,
            [
                "tickets",
                "create",
                "--title",
                "Whitespace labels",
                "--labels",
                "  label1  ,  label2  ",
                "--path",
                str(store_path),
            ],
        )
        assert result.exit_code == 0

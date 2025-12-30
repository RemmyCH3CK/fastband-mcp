"""Tests for ticket data models."""

from datetime import datetime, timedelta

import pytest

from fastband.tickets.models import (
    Agent,
    Ticket,
    TicketComment,
    TicketHistory,
    TicketPriority,
    TicketStatus,
    TicketType,
)

# =============================================================================
# TICKET STATUS TESTS
# =============================================================================


class TestTicketStatus:
    """Tests for TicketStatus enum."""

    def test_all_statuses_defined(self):
        """Test all expected statuses exist."""
        assert TicketStatus.OPEN.value == "open"
        assert TicketStatus.IN_PROGRESS.value == "in_progress"
        assert TicketStatus.UNDER_REVIEW.value == "under_review"
        assert TicketStatus.AWAITING_APPROVAL.value == "awaiting_approval"
        assert TicketStatus.RESOLVED.value == "resolved"
        assert TicketStatus.CLOSED.value == "closed"
        assert TicketStatus.BLOCKED.value == "blocked"

    def test_from_string_basic(self):
        """Test basic string conversion."""
        assert TicketStatus.from_string("open") == TicketStatus.OPEN
        assert TicketStatus.from_string("in_progress") == TicketStatus.IN_PROGRESS
        assert TicketStatus.from_string("resolved") == TicketStatus.RESOLVED

    def test_from_string_with_spaces(self):
        """Test conversion with space-separated names."""
        assert TicketStatus.from_string("in progress") == TicketStatus.IN_PROGRESS
        assert TicketStatus.from_string("under review") == TicketStatus.UNDER_REVIEW
        assert TicketStatus.from_string("awaiting approval") == TicketStatus.AWAITING_APPROVAL

    def test_from_string_with_emoji(self):
        """Test conversion with emoji prefixes."""
        assert TicketStatus.from_string("🔴 Open") == TicketStatus.OPEN
        assert TicketStatus.from_string("🟡 In Progress") == TicketStatus.IN_PROGRESS
        assert TicketStatus.from_string("🟢 Resolved") == TicketStatus.RESOLVED

    def test_from_string_invalid(self):
        """Test invalid status raises error."""
        with pytest.raises(ValueError):
            TicketStatus.from_string("invalid_status")

    def test_display_name(self):
        """Test display names include emoji."""
        assert "🔴" in TicketStatus.OPEN.display_name
        assert "🟡" in TicketStatus.IN_PROGRESS.display_name
        assert "🟢" in TicketStatus.RESOLVED.display_name

    def test_valid_transitions_from_open(self):
        """Test valid transitions from OPEN status."""
        assert TicketStatus.OPEN.can_transition_to(TicketStatus.IN_PROGRESS)
        assert TicketStatus.OPEN.can_transition_to(TicketStatus.BLOCKED)
        assert TicketStatus.OPEN.can_transition_to(TicketStatus.CLOSED)
        assert not TicketStatus.OPEN.can_transition_to(TicketStatus.RESOLVED)

    def test_valid_transitions_from_in_progress(self):
        """Test valid transitions from IN_PROGRESS status."""
        assert TicketStatus.IN_PROGRESS.can_transition_to(TicketStatus.UNDER_REVIEW)
        assert TicketStatus.IN_PROGRESS.can_transition_to(TicketStatus.BLOCKED)
        assert not TicketStatus.IN_PROGRESS.can_transition_to(TicketStatus.RESOLVED)

    def test_valid_transitions_from_under_review(self):
        """Test valid transitions from UNDER_REVIEW status."""
        assert TicketStatus.UNDER_REVIEW.can_transition_to(TicketStatus.AWAITING_APPROVAL)
        assert TicketStatus.UNDER_REVIEW.can_transition_to(TicketStatus.IN_PROGRESS)
        assert not TicketStatus.UNDER_REVIEW.can_transition_to(TicketStatus.RESOLVED)

    def test_valid_transitions_from_awaiting_approval(self):
        """Test valid transitions from AWAITING_APPROVAL status."""
        assert TicketStatus.AWAITING_APPROVAL.can_transition_to(TicketStatus.RESOLVED)
        assert TicketStatus.AWAITING_APPROVAL.can_transition_to(TicketStatus.IN_PROGRESS)
        assert not TicketStatus.AWAITING_APPROVAL.can_transition_to(TicketStatus.OPEN)


# =============================================================================
# TICKET PRIORITY TESTS
# =============================================================================


class TestTicketPriority:
    """Tests for TicketPriority enum."""

    def test_all_priorities_defined(self):
        """Test all expected priorities exist."""
        assert TicketPriority.CRITICAL.value == "critical"
        assert TicketPriority.HIGH.value == "high"
        assert TicketPriority.MEDIUM.value == "medium"
        assert TicketPriority.LOW.value == "low"

    def test_from_string(self):
        """Test string conversion."""
        assert TicketPriority.from_string("critical") == TicketPriority.CRITICAL
        assert TicketPriority.from_string("HIGH") == TicketPriority.HIGH
        assert TicketPriority.from_string("Medium") == TicketPriority.MEDIUM

    def test_from_string_invalid(self):
        """Test invalid priority raises error."""
        with pytest.raises(ValueError):
            TicketPriority.from_string("invalid")

    def test_display_name(self):
        """Test display names include emoji."""
        assert "🔥" in TicketPriority.CRITICAL.display_name
        assert "🔴" in TicketPriority.HIGH.display_name

    def test_sort_order(self):
        """Test sort order is correct."""
        assert TicketPriority.CRITICAL.sort_order < TicketPriority.HIGH.sort_order
        assert TicketPriority.HIGH.sort_order < TicketPriority.MEDIUM.sort_order
        assert TicketPriority.MEDIUM.sort_order < TicketPriority.LOW.sort_order


# =============================================================================
# TICKET TYPE TESTS
# =============================================================================


class TestTicketType:
    """Tests for TicketType enum."""

    def test_all_types_defined(self):
        """Test all expected types exist."""
        assert TicketType.BUG.value == "bug"
        assert TicketType.FEATURE.value == "feature"
        assert TicketType.ENHANCEMENT.value == "enhancement"
        assert TicketType.TASK.value == "task"

    def test_from_string(self):
        """Test string conversion."""
        assert TicketType.from_string("bug") == TicketType.BUG
        assert TicketType.from_string("FEATURE") == TicketType.FEATURE

    def test_display_name(self):
        """Test display names include emoji."""
        assert "🐛" in TicketType.BUG.display_name
        assert "✨" in TicketType.FEATURE.display_name


# =============================================================================
# AGENT TESTS
# =============================================================================


class TestAgent:
    """Tests for Agent model."""

    def test_agent_creation(self):
        """Test basic agent creation."""
        agent = Agent(name="MCP_Agent1")

        assert agent.name == "MCP_Agent1"
        assert agent.agent_type == "ai"
        assert agent.active is True
        assert agent.tickets_completed == 0

    def test_agent_with_capabilities(self):
        """Test agent with capabilities."""
        agent = Agent(
            name="Code_Review_Agent",
            capabilities=["code_review", "testing"],
        )

        assert "code_review" in agent.capabilities
        assert "testing" in agent.capabilities

    def test_agent_to_dict(self):
        """Test serialization to dict."""
        agent = Agent(name="Test_Agent", agent_type="ai")
        data = agent.to_dict()

        assert data["name"] == "Test_Agent"
        assert data["agent_type"] == "ai"
        assert "created_at" in data

    def test_agent_from_dict(self):
        """Test deserialization from dict."""
        data = {
            "name": "Test_Agent",
            "agent_type": "ai",
            "tickets_completed": 5,
        }
        agent = Agent.from_dict(data)

        assert agent.name == "Test_Agent"
        assert agent.tickets_completed == 5


# =============================================================================
# TICKET HISTORY TESTS
# =============================================================================


class TestTicketHistory:
    """Tests for TicketHistory model."""

    def test_history_creation(self):
        """Test basic history creation."""
        history = TicketHistory(
            action="status_changed",
            actor="MCP_Agent1",
            field_changed="status",
            old_value="open",
            new_value="in_progress",
        )

        assert history.action == "status_changed"
        assert history.actor == "MCP_Agent1"
        assert history.old_value == "open"
        assert history.new_value == "in_progress"

    def test_history_has_uuid(self):
        """Test history entries have unique IDs."""
        h1 = TicketHistory()
        h2 = TicketHistory()

        assert h1.id != h2.id

    def test_history_to_dict(self):
        """Test serialization."""
        history = TicketHistory(action="assigned", actor="User1")
        data = history.to_dict()

        assert data["action"] == "assigned"
        assert data["actor"] == "User1"

    def test_history_from_dict(self):
        """Test deserialization."""
        data = {
            "action": "comment_added",
            "actor": "User1",
            "message": "Test comment",
        }
        history = TicketHistory.from_dict(data)

        assert history.action == "comment_added"
        assert history.message == "Test comment"


# =============================================================================
# TICKET COMMENT TESTS
# =============================================================================


class TestTicketComment:
    """Tests for TicketComment model."""

    def test_comment_creation(self):
        """Test basic comment creation."""
        comment = TicketComment(
            ticket_id="123",
            author="User1",
            content="This is a test comment",
        )

        assert comment.ticket_id == "123"
        assert comment.author == "User1"
        assert comment.content == "This is a test comment"

    def test_comment_types(self):
        """Test different comment types."""
        regular = TicketComment(comment_type="comment")
        review = TicketComment(comment_type="review")
        system = TicketComment(comment_type="system")

        assert regular.comment_type == "comment"
        assert review.comment_type == "review"
        assert system.comment_type == "system"

    def test_review_comment(self):
        """Test review comment with result."""
        comment = TicketComment(
            author="Code_Review_Agent",
            author_type="ai",
            comment_type="review",
            review_result="approved",
            files_reviewed=["file1.py", "file2.py"],
        )

        assert comment.review_result == "approved"
        assert len(comment.files_reviewed) == 2

    def test_comment_to_dict(self):
        """Test serialization."""
        comment = TicketComment(
            author="User1",
            content="Test",
            comment_type="comment",
        )
        data = comment.to_dict()

        assert data["author"] == "User1"
        assert data["content"] == "Test"

    def test_comment_from_dict(self):
        """Test deserialization."""
        data = {
            "author": "User1",
            "content": "Test",
            "review_result": "changes_requested",
        }
        comment = TicketComment.from_dict(data)

        assert comment.author == "User1"
        assert comment.review_result == "changes_requested"


# =============================================================================
# TICKET TESTS - CREATION
# =============================================================================


class TestTicketCreation:
    """Tests for Ticket creation."""

    def test_basic_creation(self):
        """Test basic ticket creation with defaults."""
        ticket = Ticket(title="Test Ticket")

        assert ticket.title == "Test Ticket"
        assert ticket.status == TicketStatus.OPEN
        assert ticket.priority == TicketPriority.MEDIUM
        assert ticket.ticket_type == TicketType.TASK

    def test_full_creation(self):
        """Test full ticket creation with all fields."""
        ticket = Ticket(
            title="Fix bug",
            description="Bug description",
            ticket_type=TicketType.BUG,
            priority=TicketPriority.HIGH,
            requirements=["Fix issue", "Add test"],
            labels=["bug", "urgent"],
        )

        assert ticket.title == "Fix bug"
        assert ticket.ticket_type == TicketType.BUG
        assert ticket.priority == TicketPriority.HIGH
        assert len(ticket.requirements) == 2
        assert "urgent" in ticket.labels

    def test_creation_with_string_enums(self):
        """Test creation with string values for enums."""
        ticket = Ticket(
            title="Test",
            ticket_type="bug",
            priority="high",
            status="open",
        )

        assert ticket.ticket_type == TicketType.BUG
        assert ticket.priority == TicketPriority.HIGH
        assert ticket.status == TicketStatus.OPEN

    def test_ticket_has_uuid(self):
        """Test tickets have unique IDs."""
        t1 = Ticket(title="Ticket 1")
        t2 = Ticket(title="Ticket 2")

        assert t1.id != t2.id

    def test_ticket_timestamps(self):
        """Test timestamps are set."""
        ticket = Ticket(title="Test")

        assert ticket.created_at is not None
        assert ticket.updated_at is not None
        assert ticket.started_at is None
        assert ticket.completed_at is None


# =============================================================================
# TICKET TESTS - PROPERTIES
# =============================================================================


class TestTicketProperties:
    """Tests for Ticket properties."""

    def test_is_open_property(self):
        """Test is_open property."""
        ticket = Ticket(title="Test", status=TicketStatus.OPEN)
        assert ticket.is_open is True

        ticket.status = TicketStatus.IN_PROGRESS
        assert ticket.is_open is True

        ticket.status = TicketStatus.RESOLVED
        assert ticket.is_open is False

    def test_is_completed_property(self):
        """Test is_completed property."""
        ticket = Ticket(title="Test", status=TicketStatus.OPEN)
        assert ticket.is_completed is False

        ticket.status = TicketStatus.RESOLVED
        assert ticket.is_completed is True

        ticket.status = TicketStatus.CLOSED
        assert ticket.is_completed is True

    def test_is_blocked_property(self):
        """Test is_blocked property."""
        ticket = Ticket(title="Test")
        assert ticket.is_blocked is False

        ticket.status = TicketStatus.BLOCKED
        assert ticket.is_blocked is True

        ticket.status = TicketStatus.OPEN
        ticket.blocked_by = ["other-ticket-id"]
        assert ticket.is_blocked is True

    def test_time_in_progress_property(self):
        """Test time_in_progress calculation."""
        ticket = Ticket(title="Test")
        assert ticket.time_in_progress is None

        ticket.started_at = datetime.now() - timedelta(hours=2)
        time_hours = ticket.time_in_progress
        assert time_hours is not None
        assert 1.9 < time_hours < 2.1


# =============================================================================
# TICKET TESTS - WORKFLOW
# =============================================================================


class TestTicketWorkflow:
    """Tests for Ticket workflow methods."""

    def test_claim_ticket(self):
        """Test claiming a ticket."""
        ticket = Ticket(title="Test", status=TicketStatus.OPEN)

        result = ticket.claim("MCP_Agent1")

        assert result is True
        assert ticket.status == TicketStatus.IN_PROGRESS
        assert ticket.assigned_to == "MCP_Agent1"
        assert ticket.started_at is not None
        assert len(ticket.history) >= 2  # assign + status change

    def test_claim_in_progress_fails(self):
        """Test cannot claim already in-progress ticket."""
        ticket = Ticket(title="Test", status=TicketStatus.IN_PROGRESS)

        result = ticket.claim("MCP_Agent1")

        assert result is False
        assert ticket.assigned_to is None

    def test_transition_status(self):
        """Test status transitions."""
        ticket = Ticket(title="Test", status=TicketStatus.OPEN)

        result = ticket.transition_status(TicketStatus.IN_PROGRESS, actor="Agent1")

        assert result is True
        assert ticket.status == TicketStatus.IN_PROGRESS
        assert len(ticket.history) == 1

    def test_invalid_transition_fails(self):
        """Test invalid transition fails."""
        ticket = Ticket(title="Test", status=TicketStatus.OPEN)

        result = ticket.transition_status(TicketStatus.RESOLVED, actor="Agent1")

        assert result is False
        assert ticket.status == TicketStatus.OPEN

    def test_complete_ticket(self):
        """Test completing ticket work."""
        ticket = Ticket(title="Test", status=TicketStatus.IN_PROGRESS)

        result = ticket.complete(
            problem_summary="Issue was X",
            solution_summary="Fixed by doing Y",
            files_modified=["file.py"],
            testing_notes="Tested manually",
        )

        assert result is True
        assert ticket.status == TicketStatus.UNDER_REVIEW
        assert ticket.problem_summary == "Issue was X"
        assert ticket.solution_summary == "Fixed by doing Y"

    def test_approve_review(self):
        """Test approving code review."""
        ticket = Ticket(title="Test", status=TicketStatus.UNDER_REVIEW)

        result = ticket.approve_review("Code_Review_Agent")

        assert result is True
        assert ticket.status == TicketStatus.AWAITING_APPROVAL
        assert ticket.review_status == "approved"
        assert "Code_Review_Agent" in ticket.reviewers

    def test_request_changes(self):
        """Test requesting changes in review."""
        ticket = Ticket(title="Test", status=TicketStatus.UNDER_REVIEW)

        result = ticket.request_changes("Code_Review_Agent", "Please fix X")

        assert result is True
        assert ticket.status == TicketStatus.IN_PROGRESS
        assert ticket.review_status == "changes_requested"
        assert len(ticket.comments) == 1

    def test_resolve_ticket(self):
        """Test resolving ticket."""
        ticket = Ticket(title="Test", status=TicketStatus.AWAITING_APPROVAL)

        result = ticket.resolve("Admin", "Looks good!")

        assert result is True
        assert ticket.status == TicketStatus.RESOLVED
        assert ticket.completed_at is not None

    def test_reject_ticket(self):
        """Test rejecting ticket."""
        ticket = Ticket(title="Test", status=TicketStatus.AWAITING_APPROVAL)

        result = ticket.reject("Admin", "Need more work")

        assert result is True
        assert ticket.status == TicketStatus.IN_PROGRESS
        assert len(ticket.comments) == 1


# =============================================================================
# TICKET TESTS - HISTORY & COMMENTS
# =============================================================================


class TestTicketHistoryAndComments:
    """Tests for Ticket history and comments."""

    def test_add_history(self):
        """Test adding history entry."""
        ticket = Ticket(title="Test")

        entry = ticket.add_history(
            action="custom_action",
            actor="User1",
            message="Did something",
        )

        assert len(ticket.history) == 1
        assert entry.action == "custom_action"
        assert entry.actor == "User1"

    def test_add_comment(self):
        """Test adding comment."""
        ticket = Ticket(title="Test")

        comment = ticket.add_comment(
            content="Test comment",
            author="User1",
        )

        assert len(ticket.comments) == 1
        assert comment.content == "Test comment"
        # Adding comment should also add history
        assert len(ticket.history) == 1

    def test_assign_creates_history(self):
        """Test assignment creates history."""
        ticket = Ticket(title="Test")

        ticket.assign("MCP_Agent1", actor="Admin")

        assert ticket.assigned_to == "MCP_Agent1"
        assert len(ticket.history) == 1
        assert ticket.history[0].action == "assigned"


# =============================================================================
# TICKET TESTS - SERIALIZATION
# =============================================================================


class TestTicketSerialization:
    """Tests for Ticket serialization."""

    def test_to_dict_basic(self):
        """Test basic serialization."""
        ticket = Ticket(
            title="Test Ticket",
            description="Description",
            ticket_type=TicketType.BUG,
        )
        data = ticket.to_dict()

        assert data["title"] == "Test Ticket"
        assert data["description"] == "Description"
        assert data["ticket_type"] == "bug"
        assert data["status"] == "open"

    def test_to_dict_with_history(self):
        """Test serialization includes history."""
        ticket = Ticket(title="Test")
        ticket.add_history(action="test", actor="User1")

        data = ticket.to_dict()

        assert len(data["history"]) == 1
        assert data["history"][0]["action"] == "test"

    def test_to_dict_with_comments(self):
        """Test serialization includes comments."""
        ticket = Ticket(title="Test")
        ticket.add_comment(content="Comment", author="User1")

        data = ticket.to_dict()

        assert len(data["comments"]) == 1
        assert data["comments"][0]["content"] == "Comment"

    def test_from_dict_basic(self):
        """Test basic deserialization."""
        data = {
            "id": "test-123",
            "title": "Test Ticket",
            "ticket_type": "bug",
            "priority": "high",
            "status": "in_progress",
        }
        ticket = Ticket.from_dict(data)

        assert ticket.id == "test-123"
        assert ticket.title == "Test Ticket"
        assert ticket.ticket_type == TicketType.BUG
        assert ticket.priority == TicketPriority.HIGH
        assert ticket.status == TicketStatus.IN_PROGRESS

    def test_from_dict_with_timestamps(self):
        """Test deserialization with timestamps."""
        now = datetime.now()
        data = {
            "title": "Test",
            "created_at": now.isoformat(),
            "started_at": now.isoformat(),
        }
        ticket = Ticket.from_dict(data)

        assert ticket.created_at is not None
        assert ticket.started_at is not None

    def test_from_dict_with_history(self):
        """Test deserialization with history."""
        data = {
            "title": "Test",
            "history": [
                {"action": "created", "actor": "System"},
            ],
        }
        ticket = Ticket.from_dict(data)

        assert len(ticket.history) == 1

    def test_roundtrip_serialization(self):
        """Test full serialization roundtrip."""
        original = Ticket(
            title="Test Ticket",
            description="Description",
            ticket_type=TicketType.FEATURE,
            priority=TicketPriority.HIGH,
            requirements=["Req 1", "Req 2"],
            labels=["label1"],
        )
        original.claim("Agent1")
        original.add_comment(content="Comment", author="User1")

        data = original.to_dict()
        restored = Ticket.from_dict(data)

        assert restored.title == original.title
        assert restored.ticket_type == original.ticket_type
        assert restored.priority == original.priority
        assert restored.status == original.status
        assert restored.assigned_to == original.assigned_to
        assert len(restored.history) == len(original.history)
        assert len(restored.comments) == len(original.comments)


# =============================================================================
# TICKET TESTS - EDGE CASES
# =============================================================================


class TestTicketEdgeCases:
    """Tests for edge cases."""

    def test_empty_ticket(self):
        """Test ticket with minimal data."""
        ticket = Ticket()

        assert ticket.title == ""
        assert ticket.status == TicketStatus.OPEN
        assert ticket.id is not None

    def test_ticket_repr(self):
        """Test string representation."""
        ticket = Ticket(id="123", title="Test", status=TicketStatus.OPEN)

        repr_str = repr(ticket)
        assert "123" in repr_str
        assert "Test" in repr_str
        assert "open" in repr_str

    def test_multiple_reviewers(self):
        """Test multiple reviewers."""
        ticket = Ticket(title="Test", status=TicketStatus.UNDER_REVIEW)

        ticket.approve_review("Reviewer1")
        # Transition back for another review
        ticket.status = TicketStatus.UNDER_REVIEW
        ticket.approve_review("Reviewer2")

        assert "Reviewer1" in ticket.reviewers
        assert "Reviewer2" in ticket.reviewers

    def test_blocked_by_relationship(self):
        """Test blocked_by relationship."""
        ticket = Ticket(title="Test", blocked_by=["ticket-1", "ticket-2"])

        assert ticket.is_blocked is True
        assert len(ticket.blocked_by) == 2

    def test_subtasks(self):
        """Test subtasks relationship."""
        parent = Ticket(title="Parent", subtasks=["sub-1", "sub-2"])
        child = Ticket(title="Child", parent_ticket="parent-id")

        assert len(parent.subtasks) == 2
        assert child.parent_ticket == "parent-id"

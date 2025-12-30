"""Tests for the code review workflow."""

import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from fastband.tickets.models import (
    Ticket,
    TicketPriority,
    TicketStatus,
    TicketType,
)
from fastband.tickets.review import (
    ReviewManager,
    ReviewResult,
    ReviewStatistics,
    ReviewStatus,
    ReviewType,
)
from fastband.tickets.storage import JSONTicketStore

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def temp_dir():
    """Create a temporary directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def store(temp_dir):
    """Create a JSON store for testing."""
    path = temp_dir / "tickets.json"
    return JSONTicketStore(path)


@pytest.fixture
def review_manager(store):
    """Create a ReviewManager for testing."""
    return ReviewManager(store)


@pytest.fixture
def ticket_in_progress(store):
    """Create a ticket in IN_PROGRESS status."""
    ticket = Ticket(
        title="Test Feature",
        description="Implement test feature",
        ticket_type=TicketType.FEATURE,
        priority=TicketPriority.HIGH,
        status=TicketStatus.IN_PROGRESS,
        assigned_to="MCP_Agent1",
        files_to_modify=["src/app.py", "templates/test.html"],
    )
    return store.create(ticket)


@pytest.fixture
def ticket_under_review(store):
    """Create a ticket in UNDER_REVIEW status."""
    ticket = Ticket(
        title="Bug Fix",
        description="Fix critical bug",
        ticket_type=TicketType.BUG,
        priority=TicketPriority.CRITICAL,
        status=TicketStatus.UNDER_REVIEW,
        assigned_to="MCP_Agent1",
        files_modified=["src/bug.py", "tests/test_bug.py"],
        problem_summary="Bug caused crash",
        solution_summary="Fixed null reference",
    )
    return store.create(ticket)


@pytest.fixture
def approved_review_result():
    """Create an approved review result."""
    return ReviewResult(
        reviewer_name="Code_Review_Agent",
        review_type=ReviewType.CODE,
        status=ReviewStatus.APPROVED,
        summary="Code looks good",
        checks_passed=["syntax_valid", "no_security_issues", "tests_pass"],
        files_reviewed=["src/app.py"],
    )


@pytest.fixture
def rejected_review_result():
    """Create a rejected review result."""
    return ReviewResult(
        reviewer_name="Code_Review_Agent",
        review_type=ReviewType.CODE,
        status=ReviewStatus.CHANGES_REQUESTED,
        rejection_reason="Security vulnerability found",
        issues_found=["SQL injection vulnerability", "Missing input validation"],
        requested_changes=["Use parameterized queries", "Add input validation"],
        security_issues=["SQL injection in query builder"],
        files_reviewed=["src/database.py"],
    )


# =============================================================================
# REVIEW TYPE TESTS
# =============================================================================


class TestReviewType:
    """Tests for ReviewType enum."""

    def test_all_types_defined(self):
        """Test all expected types exist."""
        assert ReviewType.CODE.value == "code"
        assert ReviewType.PROCESS.value == "process"
        assert ReviewType.UIUX.value == "uiux"

    def test_from_string(self):
        """Test string conversion."""
        assert ReviewType.from_string("code") == ReviewType.CODE
        assert ReviewType.from_string("PROCESS") == ReviewType.PROCESS
        assert ReviewType.from_string("uiux") == ReviewType.UIUX

    def test_from_string_invalid(self):
        """Test invalid type raises error."""
        with pytest.raises(ValueError):
            ReviewType.from_string("invalid")

    def test_display_name(self):
        """Test display names."""
        assert ReviewType.CODE.display_name == "Code Review"
        assert ReviewType.PROCESS.display_name == "Process Audit"
        assert ReviewType.UIUX.display_name == "UI/UX Review"


# =============================================================================
# REVIEW STATUS TESTS
# =============================================================================


class TestReviewStatus:
    """Tests for ReviewStatus enum."""

    def test_all_statuses_defined(self):
        """Test all expected statuses exist."""
        assert ReviewStatus.PENDING.value == "pending"
        assert ReviewStatus.APPROVED.value == "approved"
        assert ReviewStatus.CHANGES_REQUESTED.value == "changes_requested"

    def test_from_string(self):
        """Test string conversion."""
        assert ReviewStatus.from_string("pending") == ReviewStatus.PENDING
        assert ReviewStatus.from_string("approved") == ReviewStatus.APPROVED
        assert ReviewStatus.from_string("changes_requested") == ReviewStatus.CHANGES_REQUESTED
        assert ReviewStatus.from_string("changes requested") == ReviewStatus.CHANGES_REQUESTED

    def test_from_string_invalid(self):
        """Test invalid status raises error."""
        with pytest.raises(ValueError):
            ReviewStatus.from_string("invalid")


# =============================================================================
# REVIEW RESULT TESTS
# =============================================================================


class TestReviewResult:
    """Tests for ReviewResult dataclass."""

    def test_basic_creation(self):
        """Test basic review result creation."""
        result = ReviewResult(
            reviewer_name="Reviewer1",
            review_type=ReviewType.CODE,
        )

        assert result.reviewer_name == "Reviewer1"
        assert result.review_type == ReviewType.CODE
        assert result.status == ReviewStatus.PENDING
        assert result.id is not None

    def test_approved_properties(self, approved_review_result):
        """Test properties for approved review."""
        assert approved_review_result.is_approved is True
        assert approved_review_result.is_rejected is False
        assert approved_review_result.is_pending is False
        assert approved_review_result.has_blocking_issues is False

    def test_rejected_properties(self, rejected_review_result):
        """Test properties for rejected review."""
        assert rejected_review_result.is_approved is False
        assert rejected_review_result.is_rejected is True
        assert rejected_review_result.is_pending is False
        assert rejected_review_result.has_blocking_issues is True

    def test_pending_properties(self):
        """Test properties for pending review."""
        result = ReviewResult(status=ReviewStatus.PENDING)

        assert result.is_approved is False
        assert result.is_rejected is False
        assert result.is_pending is True

    def test_has_blocking_issues(self):
        """Test blocking issues detection."""
        result = ReviewResult()
        assert result.has_blocking_issues is False

        result.security_issues = ["SQL injection"]
        assert result.has_blocking_issues is True

        result.security_issues = []
        result.bug_risks = ["Null reference"]
        assert result.has_blocking_issues is True

        result.bug_risks = []
        result.issues_found = ["Missing validation"]
        assert result.has_blocking_issues is True

    def test_to_dict(self, approved_review_result):
        """Test serialization to dict."""
        data = approved_review_result.to_dict()

        assert data["reviewer_name"] == "Code_Review_Agent"
        assert data["review_type"] == "code"
        assert data["status"] == "approved"
        assert "checks_passed" in data
        assert "created_at" in data

    def test_from_dict(self):
        """Test deserialization from dict."""
        data = {
            "reviewer_name": "Test_Reviewer",
            "review_type": "process",
            "status": "approved",
            "summary": "All good",
            "checks_passed": ["step1", "step2"],
        }
        result = ReviewResult.from_dict(data)

        assert result.reviewer_name == "Test_Reviewer"
        assert result.review_type == ReviewType.PROCESS
        assert result.status == ReviewStatus.APPROVED
        assert "step1" in result.checks_passed

    def test_roundtrip_serialization(self, rejected_review_result):
        """Test full serialization roundtrip."""
        data = rejected_review_result.to_dict()
        restored = ReviewResult.from_dict(data)

        assert restored.reviewer_name == rejected_review_result.reviewer_name
        assert restored.review_type == rejected_review_result.review_type
        assert restored.status == rejected_review_result.status
        assert restored.rejection_reason == rejected_review_result.rejection_reason
        assert restored.security_issues == rejected_review_result.security_issues


# =============================================================================
# REVIEW STATISTICS TESTS
# =============================================================================


class TestReviewStatistics:
    """Tests for ReviewStatistics dataclass."""

    def test_basic_creation(self):
        """Test basic statistics creation."""
        stats = ReviewStatistics()

        assert stats.total_reviews == 0
        assert stats.approved_count == 0
        assert stats.approval_rate == 0.0

    def test_approval_rate_calculation(self):
        """Test approval rate calculation."""
        stats = ReviewStatistics(
            approved_count=8,
            rejected_count=2,
        )

        assert stats.approval_rate == 0.8

    def test_approval_rate_no_reviews(self):
        """Test approval rate with no completed reviews."""
        stats = ReviewStatistics(
            approved_count=0,
            rejected_count=0,
        )

        assert stats.approval_rate == 0.0

    def test_to_dict(self):
        """Test serialization to dict."""
        stats = ReviewStatistics(
            total_reviews=10,
            approved_count=7,
            rejected_count=3,
            code_reviews=6,
            process_reviews=4,
        )
        data = stats.to_dict()

        assert data["total_reviews"] == 10
        assert data["approved_count"] == 7
        assert data["approval_rate"] == 0.7
        assert data["code_reviews"] == 6


# =============================================================================
# REVIEW MANAGER - REQUEST REVIEW TESTS
# =============================================================================


class TestReviewManagerRequestReview:
    """Tests for ReviewManager.request_review()."""

    def test_request_review_success(self, review_manager, ticket_under_review):
        """Test successful review request."""
        result = review_manager.request_review(
            ticket_id=ticket_under_review.id,
            review_type=ReviewType.CODE,
            notes="Please review carefully",
        )

        assert result["success"] is True
        assert result["ticket_id"] == ticket_under_review.id
        assert result["review_type"] == "code"

    def test_request_review_with_files(self, review_manager, ticket_under_review):
        """Test review request with specific files."""
        result = review_manager.request_review(
            ticket_id=ticket_under_review.id,
            review_type=ReviewType.CODE,
            files_to_review=["src/specific.py"],
        )

        assert result["success"] is True

        # Verify comment was added
        ticket = review_manager.store.get(ticket_under_review.id)
        assert len(ticket.comments) > 0

    def test_request_review_ticket_not_found(self, review_manager):
        """Test review request for non-existent ticket."""
        result = review_manager.request_review(
            ticket_id="nonexistent",
            review_type=ReviewType.CODE,
        )

        assert result["success"] is False
        assert "not found" in result["error"]

    def test_request_review_wrong_status(self, review_manager, ticket_in_progress):
        """Test review request for ticket not in UNDER_REVIEW status."""
        result = review_manager.request_review(
            ticket_id=ticket_in_progress.id,
            review_type=ReviewType.CODE,
        )

        assert result["success"] is False
        assert "UNDER_REVIEW" in result["error"]

    def test_request_multiple_review_types(self, review_manager, ticket_under_review):
        """Test requesting multiple review types."""
        result1 = review_manager.request_review(
            ticket_id=ticket_under_review.id,
            review_type=ReviewType.CODE,
        )
        result2 = review_manager.request_review(
            ticket_id=ticket_under_review.id,
            review_type=ReviewType.PROCESS,
        )

        assert result1["success"] is True
        assert result2["success"] is True

        ticket = review_manager.store.get(ticket_under_review.id)
        assert len(ticket.metadata.get("pending_reviews", [])) == 2


# =============================================================================
# REVIEW MANAGER - SUBMIT REVIEW TESTS
# =============================================================================


class TestReviewManagerSubmitReview:
    """Tests for ReviewManager.submit_review()."""

    def test_submit_approved_review(
        self, review_manager, ticket_under_review, approved_review_result
    ):
        """Test submitting an approved review."""
        result = review_manager.submit_review(
            ticket_id=ticket_under_review.id,
            reviewer_name="Code_Review_Agent",
            review_type=ReviewType.CODE,
            result=approved_review_result,
        )

        assert result["success"] is True
        assert result["status"] == "all_reviews_passed"

        ticket = review_manager.store.get(ticket_under_review.id)
        assert ticket.status == TicketStatus.AWAITING_APPROVAL
        assert "Code_Review_Agent" in ticket.reviewers

    def test_submit_rejected_review(
        self, review_manager, ticket_under_review, rejected_review_result
    ):
        """Test submitting a rejected review."""
        result = review_manager.submit_review(
            ticket_id=ticket_under_review.id,
            reviewer_name="Code_Review_Agent",
            review_type=ReviewType.CODE,
            result=rejected_review_result,
        )

        assert result["success"] is True
        assert result["status"] == "changes_requested"
        assert result["rejection_reason"] == "Security vulnerability found"

        ticket = review_manager.store.get(ticket_under_review.id)
        assert ticket.status == TicketStatus.IN_PROGRESS

    def test_submit_review_ticket_not_found(self, review_manager, approved_review_result):
        """Test submitting review for non-existent ticket."""
        result = review_manager.submit_review(
            ticket_id="nonexistent",
            reviewer_name="Reviewer",
            review_type=ReviewType.CODE,
            result=approved_review_result,
        )

        assert result["success"] is False
        assert "not found" in result["error"]

    def test_submit_review_wrong_status(
        self, review_manager, ticket_in_progress, approved_review_result
    ):
        """Test submitting review for ticket not in review."""
        result = review_manager.submit_review(
            ticket_id=ticket_in_progress.id,
            reviewer_name="Reviewer",
            review_type=ReviewType.CODE,
            result=approved_review_result,
        )

        assert result["success"] is False
        assert "UNDER_REVIEW" in result["error"]

    def test_submit_review_creates_comment(
        self, review_manager, ticket_under_review, approved_review_result
    ):
        """Test that submitting review creates comment."""
        review_manager.submit_review(
            ticket_id=ticket_under_review.id,
            reviewer_name="Code_Review_Agent",
            review_type=ReviewType.CODE,
            result=approved_review_result,
        )

        ticket = review_manager.store.get(ticket_under_review.id)
        review_comments = [c for c in ticket.comments if c.comment_type == "review"]

        assert len(review_comments) >= 1
        assert review_comments[-1].review_result == "approved"

    def test_submit_review_creates_history(
        self, review_manager, ticket_under_review, approved_review_result
    ):
        """Test that submitting review creates history entry."""
        initial_history = len(review_manager.store.get(ticket_under_review.id).history)

        review_manager.submit_review(
            ticket_id=ticket_under_review.id,
            reviewer_name="Code_Review_Agent",
            review_type=ReviewType.CODE,
            result=approved_review_result,
        )

        ticket = review_manager.store.get(ticket_under_review.id)
        # Should have at least one new history entry for review_submitted
        assert len(ticket.history) > initial_history


# =============================================================================
# REVIEW MANAGER - MULTI-REVIEWER TESTS
# =============================================================================


class TestReviewManagerMultiReviewer:
    """Tests for multi-reviewer scenarios."""

    def test_multiple_required_reviews(self, review_manager, ticket_under_review, store):
        """Test requiring multiple review types."""
        # Configure required reviews
        review_manager.configure_required_reviews(
            ticket_under_review.id,
            [ReviewType.CODE, ReviewType.PROCESS],
        )

        # Submit first review (code)
        code_result = ReviewResult(
            status=ReviewStatus.APPROVED,
            summary="Code looks good",
        )
        result1 = review_manager.submit_review(
            ticket_id=ticket_under_review.id,
            reviewer_name="Code_Review_Agent",
            review_type=ReviewType.CODE,
            result=code_result,
        )

        assert result1["success"] is True
        assert result1["status"] == "review_approved"
        assert "process" in result1["pending_reviews"]

        # Ticket should still be under review
        ticket = store.get(ticket_under_review.id)
        assert ticket.status == TicketStatus.UNDER_REVIEW

    def test_all_required_reviews_approved(self, review_manager, ticket_under_review, store):
        """Test that all required reviews must pass."""
        review_manager.configure_required_reviews(
            ticket_under_review.id,
            [ReviewType.CODE, ReviewType.PROCESS],
        )

        # Submit code review
        code_result = ReviewResult(status=ReviewStatus.APPROVED, summary="Code good")
        review_manager.submit_review(
            ticket_id=ticket_under_review.id,
            reviewer_name="Code_Review_Agent",
            review_type=ReviewType.CODE,
            result=code_result,
        )

        # Reload ticket and keep under review
        ticket = store.get(ticket_under_review.id)
        ticket.status = TicketStatus.UNDER_REVIEW
        store.update(ticket)

        # Submit process review
        process_result = ReviewResult(status=ReviewStatus.APPROVED, summary="Process good")
        result2 = review_manager.submit_review(
            ticket_id=ticket_under_review.id,
            reviewer_name="Process_Audit_Agent",
            review_type=ReviewType.PROCESS,
            result=process_result,
        )

        assert result2["status"] == "all_reviews_passed"

        ticket = store.get(ticket_under_review.id)
        assert ticket.status == TicketStatus.AWAITING_APPROVAL

    def test_one_rejection_sends_back(self, review_manager, ticket_under_review, store):
        """Test that one rejection sends ticket back."""
        review_manager.configure_required_reviews(
            ticket_under_review.id,
            [ReviewType.CODE, ReviewType.PROCESS],
        )

        # Submit code review - approved
        code_result = ReviewResult(status=ReviewStatus.APPROVED, summary="Code good")
        review_manager.submit_review(
            ticket_id=ticket_under_review.id,
            reviewer_name="Code_Review_Agent",
            review_type=ReviewType.CODE,
            result=code_result,
        )

        # Reload and keep under review
        ticket = store.get(ticket_under_review.id)
        ticket.status = TicketStatus.UNDER_REVIEW
        store.update(ticket)

        # Submit process review - rejected
        process_result = ReviewResult(
            status=ReviewStatus.CHANGES_REQUESTED,
            rejection_reason="Missing documentation",
        )
        result2 = review_manager.submit_review(
            ticket_id=ticket_under_review.id,
            reviewer_name="Process_Audit_Agent",
            review_type=ReviewType.PROCESS,
            result=process_result,
        )

        assert result2["status"] == "changes_requested"

        ticket = store.get(ticket_under_review.id)
        assert ticket.status == TicketStatus.IN_PROGRESS

    def test_get_required_reviews_default(self, review_manager, ticket_under_review):
        """Test default required reviews."""
        required = review_manager.get_required_reviews(ticket_under_review.id)

        assert ReviewType.CODE in required

    def test_different_reviewers_tracked(self, review_manager, ticket_under_review, store):
        """Test that different reviewers are tracked."""
        review_manager.configure_required_reviews(
            ticket_under_review.id,
            [ReviewType.CODE],
        )

        result = ReviewResult(status=ReviewStatus.APPROVED)
        review_manager.submit_review(
            ticket_id=ticket_under_review.id,
            reviewer_name="Reviewer_A",
            review_type=ReviewType.CODE,
            result=result,
        )

        ticket = store.get(ticket_under_review.id)
        assert "Reviewer_A" in ticket.reviewers


# =============================================================================
# REVIEW MANAGER - GET STATUS TESTS
# =============================================================================


class TestReviewManagerGetStatus:
    """Tests for ReviewManager.get_review_status()."""

    def test_get_status_no_reviews(self, review_manager, ticket_under_review):
        """Test getting status with no reviews."""
        status = review_manager.get_review_status(ticket_under_review.id)

        assert status["success"] is True
        assert status["overall_status"] == "needs_review"
        assert len(status["approved_reviews"]) == 0

    def test_get_status_after_approval(
        self, review_manager, ticket_under_review, approved_review_result
    ):
        """Test getting status after approval."""
        review_manager.submit_review(
            ticket_id=ticket_under_review.id,
            reviewer_name="Reviewer",
            review_type=ReviewType.CODE,
            result=approved_review_result,
        )

        status = review_manager.get_review_status(ticket_under_review.id)

        assert status["success"] is True
        assert status["overall_status"] == "all_approved"
        assert len(status["approved_reviews"]) == 1

    def test_get_status_after_rejection(
        self, review_manager, ticket_under_review, rejected_review_result
    ):
        """Test getting status after rejection."""
        review_manager.submit_review(
            ticket_id=ticket_under_review.id,
            reviewer_name="Reviewer",
            review_type=ReviewType.CODE,
            result=rejected_review_result,
        )

        status = review_manager.get_review_status(ticket_under_review.id)

        assert status["success"] is True
        assert status["overall_status"] == "changes_requested"
        assert len(status["rejected_reviews"]) == 1

    def test_get_status_ticket_not_found(self, review_manager):
        """Test getting status for non-existent ticket."""
        status = review_manager.get_review_status("nonexistent")

        assert status["success"] is False
        assert "not found" in status["error"]

    def test_get_status_mixed_reviews(self, review_manager, ticket_under_review, store):
        """Test status with mixed review results."""
        review_manager.configure_required_reviews(
            ticket_under_review.id,
            [ReviewType.CODE, ReviewType.PROCESS, ReviewType.UIUX],
        )

        # Approve code
        code_result = ReviewResult(status=ReviewStatus.APPROVED)
        review_manager.submit_review(
            ticket_id=ticket_under_review.id,
            reviewer_name="Code_Agent",
            review_type=ReviewType.CODE,
            result=code_result,
        )

        # Keep under review for status check
        ticket = store.get(ticket_under_review.id)
        ticket.status = TicketStatus.UNDER_REVIEW
        store.update(ticket)

        status = review_manager.get_review_status(ticket_under_review.id)

        assert "process" in status["missing_reviews"]
        assert "uiux" in status["missing_reviews"]
        assert len(status["approved_reviews"]) == 1


# =============================================================================
# REVIEW MANAGER - GET FEEDBACK TESTS
# =============================================================================


class TestReviewManagerGetFeedback:
    """Tests for ReviewManager.get_feedback()."""

    def test_get_feedback_empty(self, review_manager, ticket_under_review):
        """Test getting feedback with no reviews."""
        feedback = review_manager.get_feedback(ticket_under_review.id)

        assert feedback["success"] is True
        assert feedback["review_count"] == 0
        assert len(feedback["issues_found"]) == 0

    def test_get_feedback_with_issues(
        self, review_manager, ticket_under_review, rejected_review_result
    ):
        """Test getting feedback with issues."""
        review_manager.submit_review(
            ticket_id=ticket_under_review.id,
            reviewer_name="Reviewer",
            review_type=ReviewType.CODE,
            result=rejected_review_result,
        )

        feedback = review_manager.get_feedback(ticket_under_review.id)

        assert feedback["success"] is True
        assert len(feedback["issues_found"]) > 0
        assert len(feedback["security_issues"]) > 0
        assert feedback["has_blocking_issues"] is True

    def test_get_feedback_filter_by_type(self, review_manager, ticket_under_review, store):
        """Test filtering feedback by review type."""
        # Add code review
        code_result = ReviewResult(
            status=ReviewStatus.CHANGES_REQUESTED,
            issues_found=["Code issue"],
        )
        review_manager.submit_review(
            ticket_id=ticket_under_review.id,
            reviewer_name="Code_Agent",
            review_type=ReviewType.CODE,
            result=code_result,
        )

        # Keep under review
        ticket = store.get(ticket_under_review.id)
        ticket.status = TicketStatus.UNDER_REVIEW
        store.update(ticket)

        # Add process review
        process_result = ReviewResult(
            status=ReviewStatus.CHANGES_REQUESTED,
            issues_found=["Process issue"],
        )
        review_manager.submit_review(
            ticket_id=ticket_under_review.id,
            reviewer_name="Process_Agent",
            review_type=ReviewType.PROCESS,
            result=process_result,
        )

        # Get only code feedback
        feedback = review_manager.get_feedback(
            ticket_under_review.id,
            review_type=ReviewType.CODE,
        )

        assert feedback["review_count"] == 1
        assert "Code issue" in feedback["issues_found"]
        assert "Process issue" not in feedback["issues_found"]

    def test_get_feedback_ticket_not_found(self, review_manager):
        """Test getting feedback for non-existent ticket."""
        feedback = review_manager.get_feedback("nonexistent")

        assert feedback["success"] is False

    def test_get_feedback_aggregates_from_multiple(
        self, review_manager, ticket_under_review, store
    ):
        """Test feedback aggregation from multiple reviews."""
        # First review
        result1 = ReviewResult(
            status=ReviewStatus.CHANGES_REQUESTED,
            issues_found=["Issue 1"],
            suggestions=["Suggestion 1"],
        )
        review_manager.submit_review(
            ticket_id=ticket_under_review.id,
            reviewer_name="Reviewer1",
            review_type=ReviewType.CODE,
            result=result1,
        )

        # Keep under review
        ticket = store.get(ticket_under_review.id)
        ticket.status = TicketStatus.UNDER_REVIEW
        store.update(ticket)

        # Second review
        result2 = ReviewResult(
            status=ReviewStatus.CHANGES_REQUESTED,
            issues_found=["Issue 2"],
            suggestions=["Suggestion 2"],
        )
        review_manager.submit_review(
            ticket_id=ticket_under_review.id,
            reviewer_name="Reviewer2",
            review_type=ReviewType.PROCESS,
            result=result2,
        )

        feedback = review_manager.get_feedback(ticket_under_review.id)

        assert feedback["review_count"] == 2
        assert "Issue 1" in feedback["issues_found"]
        assert "Issue 2" in feedback["issues_found"]
        assert len(feedback["suggestions"]) == 2


# =============================================================================
# REVIEW MANAGER - STATISTICS TESTS
# =============================================================================


class TestReviewManagerStatistics:
    """Tests for ReviewManager.get_statistics()."""

    def test_statistics_empty(self, review_manager):
        """Test statistics with no reviews."""
        stats = review_manager.get_statistics()

        assert stats.total_reviews == 0
        assert stats.approval_rate == 0.0

    def test_statistics_counts(self, review_manager, ticket_under_review, store):
        """Test review counting in statistics."""
        # Add approved review
        approved = ReviewResult(status=ReviewStatus.APPROVED)
        review_manager.submit_review(
            ticket_id=ticket_under_review.id,
            reviewer_name="Reviewer1",
            review_type=ReviewType.CODE,
            result=approved,
        )

        # Create another ticket
        ticket2 = Ticket(
            title="Test 2",
            status=TicketStatus.UNDER_REVIEW,
        )
        ticket2 = store.create(ticket2)

        # Add rejected review
        rejected = ReviewResult(
            status=ReviewStatus.CHANGES_REQUESTED,
            issues_found=["Issue"],
        )
        review_manager.submit_review(
            ticket_id=ticket2.id,
            reviewer_name="Reviewer2",
            review_type=ReviewType.CODE,
            result=rejected,
        )

        stats = review_manager.get_statistics()

        assert stats.total_reviews == 2
        assert stats.approved_count == 1
        assert stats.rejected_count == 1
        assert stats.approval_rate == 0.5

    def test_statistics_by_type(self, review_manager, ticket_under_review, store):
        """Test statistics broken down by review type."""
        # Add code reviews
        for _ in range(3):
            result = ReviewResult(status=ReviewStatus.APPROVED)
            review_manager.submit_review(
                ticket_id=ticket_under_review.id,
                reviewer_name="Agent",
                review_type=ReviewType.CODE,
                result=result,
            )
            # Keep under review
            ticket = store.get(ticket_under_review.id)
            ticket.status = TicketStatus.UNDER_REVIEW
            store.update(ticket)

        # Add process reviews
        for _ in range(2):
            result = ReviewResult(status=ReviewStatus.APPROVED)
            review_manager.submit_review(
                ticket_id=ticket_under_review.id,
                reviewer_name="Agent",
                review_type=ReviewType.PROCESS,
                result=result,
            )
            ticket = store.get(ticket_under_review.id)
            ticket.status = TicketStatus.UNDER_REVIEW
            store.update(ticket)

        stats = review_manager.get_statistics()

        assert stats.code_reviews == 3
        assert stats.process_reviews == 2

    def test_statistics_filter_by_reviewer(self, review_manager, ticket_under_review, store):
        """Test filtering statistics by reviewer."""
        # Reviews from different reviewers
        r1 = ReviewResult(status=ReviewStatus.APPROVED)
        review_manager.submit_review(
            ticket_id=ticket_under_review.id,
            reviewer_name="Reviewer_A",
            review_type=ReviewType.CODE,
            result=r1,
        )

        ticket = store.get(ticket_under_review.id)
        ticket.status = TicketStatus.UNDER_REVIEW
        store.update(ticket)

        r2 = ReviewResult(status=ReviewStatus.APPROVED)
        review_manager.submit_review(
            ticket_id=ticket_under_review.id,
            reviewer_name="Reviewer_B",
            review_type=ReviewType.CODE,
            result=r2,
        )

        stats = review_manager.get_statistics(reviewer_name="Reviewer_A")

        assert stats.total_reviews == 1

    def test_statistics_issues_count(self, review_manager, ticket_under_review):
        """Test issue counting in statistics."""
        result = ReviewResult(
            status=ReviewStatus.CHANGES_REQUESTED,
            issues_found=["Issue 1", "Issue 2"],
            security_issues=["Security 1"],
            bug_risks=["Bug 1", "Bug 2", "Bug 3"],
            performance_concerns=["Perf 1"],
        )
        review_manager.submit_review(
            ticket_id=ticket_under_review.id,
            reviewer_name="Reviewer",
            review_type=ReviewType.CODE,
            result=result,
        )

        stats = review_manager.get_statistics()

        assert stats.total_issues_found == 2
        assert stats.total_security_issues == 1
        assert stats.total_bug_risks == 3
        assert stats.total_performance_concerns == 1

    def test_statistics_per_reviewer(self, review_manager, ticket_under_review, store):
        """Test per-reviewer statistics."""
        # Reviewer A: 2 approved
        for _ in range(2):
            result = ReviewResult(status=ReviewStatus.APPROVED)
            review_manager.submit_review(
                ticket_id=ticket_under_review.id,
                reviewer_name="Reviewer_A",
                review_type=ReviewType.CODE,
                result=result,
            )
            ticket = store.get(ticket_under_review.id)
            ticket.status = TicketStatus.UNDER_REVIEW
            store.update(ticket)

        # Reviewer A: 1 rejected
        result = ReviewResult(status=ReviewStatus.CHANGES_REQUESTED, issues_found=["x"])
        review_manager.submit_review(
            ticket_id=ticket_under_review.id,
            reviewer_name="Reviewer_A",
            review_type=ReviewType.CODE,
            result=result,
        )

        stats = review_manager.get_statistics()

        assert stats.reviews_by_reviewer["Reviewer_A"] == 3
        assert abs(stats.approval_rate_by_reviewer["Reviewer_A"] - 0.666) < 0.01


# =============================================================================
# REVIEW MANAGER - CONVENIENCE METHODS TESTS
# =============================================================================


class TestReviewManagerConvenienceMethods:
    """Tests for convenience methods (approve_review, reject_review)."""

    def test_approve_review_convenience(self, review_manager, ticket_under_review):
        """Test approve_review convenience method."""
        result = review_manager.approve_review(
            ticket_id=ticket_under_review.id,
            reviewer_name="Agent",
            review_type=ReviewType.CODE,
            summary="All good",
            checks_passed=["check1", "check2"],
            suggestions=["Optional improvement"],
        )

        assert result["success"] is True
        assert result["status"] == "all_reviews_passed"

    def test_reject_review_convenience(self, review_manager, ticket_under_review):
        """Test reject_review convenience method."""
        result = review_manager.reject_review(
            ticket_id=ticket_under_review.id,
            reviewer_name="Agent",
            review_type=ReviewType.CODE,
            rejection_reason="Bugs found",
            issues_found=["Bug 1", "Bug 2"],
            requested_changes=["Fix bug 1", "Fix bug 2"],
            security_issues=["SQL injection"],
        )

        assert result["success"] is True
        assert result["status"] == "changes_requested"
        assert result["rejection_reason"] == "Bugs found"


# =============================================================================
# REVIEW MANAGER - PENDING REVIEWS TESTS
# =============================================================================


class TestReviewManagerPendingReviews:
    """Tests for get_pending_reviews()."""

    def test_get_pending_reviews_empty(self, review_manager):
        """Test getting pending reviews when none exist."""
        pending = review_manager.get_pending_reviews()

        assert len(pending) == 0

    def test_get_pending_reviews_with_tickets(self, review_manager, ticket_under_review, store):
        """Test getting pending reviews with tickets awaiting review."""
        # Configure requirements
        review_manager.configure_required_reviews(
            ticket_under_review.id,
            [ReviewType.CODE, ReviewType.PROCESS],
        )

        pending = review_manager.get_pending_reviews()

        assert len(pending) == 1
        assert pending[0]["ticket_id"] == ticket_under_review.id
        assert "code" in pending[0]["missing_reviews"]
        assert "process" in pending[0]["missing_reviews"]

    def test_get_pending_reviews_partially_approved(
        self, review_manager, ticket_under_review, store
    ):
        """Test pending reviews with some already approved."""
        review_manager.configure_required_reviews(
            ticket_under_review.id,
            [ReviewType.CODE, ReviewType.PROCESS],
        )

        # Approve code review
        result = ReviewResult(status=ReviewStatus.APPROVED)
        review_manager.submit_review(
            ticket_id=ticket_under_review.id,
            reviewer_name="Agent",
            review_type=ReviewType.CODE,
            result=result,
        )

        # Keep under review
        ticket = store.get(ticket_under_review.id)
        ticket.status = TicketStatus.UNDER_REVIEW
        store.update(ticket)

        pending = review_manager.get_pending_reviews()

        assert len(pending) == 1
        assert "code" in pending[0]["approved_reviews"]
        assert "process" in pending[0]["missing_reviews"]


# =============================================================================
# REVIEW MANAGER - REASSIGN TESTS
# =============================================================================


class TestReviewManagerReassign:
    """Tests for reassign_review()."""

    def test_reassign_review_success(self, review_manager, ticket_under_review):
        """Test successful review reassignment."""
        result = review_manager.reassign_review(
            ticket_id=ticket_under_review.id,
            review_type=ReviewType.CODE,
            new_reviewer="New_Reviewer",
            reason="Previous reviewer unavailable",
        )

        assert result["success"] is True
        assert result["new_reviewer"] == "New_Reviewer"

        # Check history
        ticket = review_manager.store.get(ticket_under_review.id)
        reassign_history = [h for h in ticket.history if h.action == "review_reassigned"]
        assert len(reassign_history) == 1

    def test_reassign_review_ticket_not_found(self, review_manager):
        """Test reassignment for non-existent ticket."""
        result = review_manager.reassign_review(
            ticket_id="nonexistent",
            review_type=ReviewType.CODE,
            new_reviewer="Reviewer",
        )

        assert result["success"] is False


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestReviewWorkflowIntegration:
    """Integration tests for the complete review workflow."""

    def test_complete_workflow_approved(self, review_manager, store):
        """Test complete workflow from creation to approval."""
        # Create and move ticket through workflow
        ticket = Ticket(
            title="Feature Implementation",
            status=TicketStatus.OPEN,
        )
        ticket = store.create(ticket)

        # Claim ticket
        ticket.claim("Developer_Agent")
        store.update(ticket)

        # Complete work
        ticket.complete(
            problem_summary="Needed new feature",
            solution_summary="Implemented feature",
            files_modified=["src/feature.py"],
        )
        store.update(ticket)

        assert ticket.status == TicketStatus.UNDER_REVIEW

        # Submit code review
        result = review_manager.approve_review(
            ticket_id=ticket.id,
            reviewer_name="Code_Review_Agent",
            review_type=ReviewType.CODE,
            summary="Implementation looks good",
            checks_passed=["syntax", "security", "performance"],
        )

        assert result["success"] is True

        # Verify final state
        ticket = store.get(ticket.id)
        assert ticket.status == TicketStatus.AWAITING_APPROVAL

    def test_complete_workflow_rejected_then_approved(self, review_manager, store):
        """Test workflow with initial rejection then approval."""
        ticket = Ticket(
            title="Bug Fix",
            status=TicketStatus.UNDER_REVIEW,
            assigned_to="Developer",
            files_modified=["src/bug.py"],
        )
        ticket = store.create(ticket)

        # First review - rejected
        result1 = review_manager.reject_review(
            ticket_id=ticket.id,
            reviewer_name="Reviewer",
            review_type=ReviewType.CODE,
            rejection_reason="Missing tests",
            issues_found=["No unit tests"],
            requested_changes=["Add unit tests"],
        )

        assert result1["status"] == "changes_requested"

        ticket = store.get(ticket.id)
        assert ticket.status == TicketStatus.IN_PROGRESS

        # Developer fixes and resubmits
        ticket.status = TicketStatus.UNDER_REVIEW
        store.update(ticket)

        # Second review - approved
        result2 = review_manager.approve_review(
            ticket_id=ticket.id,
            reviewer_name="Reviewer",
            review_type=ReviewType.CODE,
            summary="Tests added, looks good now",
            checks_passed=["tests_added", "coverage_good"],
        )

        assert result2["success"] is True
        assert result2["status"] == "all_reviews_passed"

    def test_multiple_reviewers_workflow(self, review_manager, store):
        """Test workflow with multiple required reviewers."""
        ticket = Ticket(
            title="UI Feature",
            status=TicketStatus.UNDER_REVIEW,
            files_modified=["templates/ui.html", "static/css/style.css"],
        )
        ticket = store.create(ticket)

        # Configure all three review types
        review_manager.configure_required_reviews(
            ticket.id,
            [ReviewType.CODE, ReviewType.PROCESS, ReviewType.UIUX],
        )

        # Code review
        review_manager.approve_review(
            ticket_id=ticket.id,
            reviewer_name="Code_Agent",
            review_type=ReviewType.CODE,
            summary="Code is clean",
            checks_passed=["syntax", "security"],
        )

        ticket = store.get(ticket.id)
        ticket.status = TicketStatus.UNDER_REVIEW
        store.update(ticket)

        # Process review
        review_manager.approve_review(
            ticket_id=ticket.id,
            reviewer_name="Process_Agent",
            review_type=ReviewType.PROCESS,
            summary="Workflow followed correctly",
            checks_passed=["workflow_correct"],
        )

        ticket = store.get(ticket.id)
        ticket.status = TicketStatus.UNDER_REVIEW
        store.update(ticket)

        # UI/UX review
        result = review_manager.approve_review(
            ticket_id=ticket.id,
            reviewer_name="UIUX_Agent",
            review_type=ReviewType.UIUX,
            summary="UI meets design standards",
            checks_passed=["design_system", "accessibility"],
        )

        assert result["status"] == "all_reviews_passed"

        ticket = store.get(ticket.id)
        assert ticket.status == TicketStatus.AWAITING_APPROVAL
        assert len(ticket.reviewers) == 3


# =============================================================================
# EDGE CASES
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases."""

    def test_empty_review_result(self, review_manager, ticket_under_review):
        """Test submitting minimal review result."""
        result = ReviewResult(status=ReviewStatus.APPROVED)
        response = review_manager.submit_review(
            ticket_id=ticket_under_review.id,
            reviewer_name="Reviewer",
            review_type=ReviewType.CODE,
            result=result,
        )

        assert response["success"] is True

    def test_review_with_unicode_content(self, review_manager, ticket_under_review):
        """Test review with unicode characters."""
        result = ReviewResult(
            status=ReviewStatus.CHANGES_REQUESTED,
            summary="Issues found",
            issues_found=["Issue with Japanese text"],
            rejection_reason="Need to fix the issue",
        )
        response = review_manager.submit_review(
            ticket_id=ticket_under_review.id,
            reviewer_name="Reviewer",
            review_type=ReviewType.CODE,
            result=result,
        )

        assert response["success"] is True

    def test_very_long_feedback(self, review_manager, ticket_under_review):
        """Test review with very long feedback."""
        long_issues = [f"Issue {i}: " + "x" * 500 for i in range(10)]
        result = ReviewResult(
            status=ReviewStatus.CHANGES_REQUESTED,
            issues_found=long_issues,
            rejection_reason="Many issues found",
        )
        response = review_manager.submit_review(
            ticket_id=ticket_under_review.id,
            reviewer_name="Reviewer",
            review_type=ReviewType.CODE,
            result=result,
        )

        assert response["success"] is True

        feedback = review_manager.get_feedback(ticket_under_review.id)
        assert len(feedback["issues_found"]) == 10

    def test_same_reviewer_multiple_reviews(self, review_manager, ticket_under_review, store):
        """Test same reviewer submitting multiple reviews."""
        # First review - rejected
        r1 = ReviewResult(status=ReviewStatus.CHANGES_REQUESTED, issues_found=["Issue"])
        review_manager.submit_review(
            ticket_id=ticket_under_review.id,
            reviewer_name="Same_Reviewer",
            review_type=ReviewType.CODE,
            result=r1,
        )

        # Reopen for review
        ticket = store.get(ticket_under_review.id)
        ticket.status = TicketStatus.UNDER_REVIEW
        store.update(ticket)

        # Second review - approved
        r2 = ReviewResult(status=ReviewStatus.APPROVED, summary="Fixed")
        response = review_manager.submit_review(
            ticket_id=ticket_under_review.id,
            reviewer_name="Same_Reviewer",
            review_type=ReviewType.CODE,
            result=r2,
        )

        assert response["success"] is True

        # Reviewer should only appear once
        ticket = store.get(ticket_under_review.id)
        assert ticket.reviewers.count("Same_Reviewer") == 1

    def test_statistics_with_date_filter(self, review_manager, ticket_under_review):
        """Test statistics with date filtering."""
        result = ReviewResult(status=ReviewStatus.APPROVED)
        review_manager.submit_review(
            ticket_id=ticket_under_review.id,
            reviewer_name="Reviewer",
            review_type=ReviewType.CODE,
            result=result,
        )

        # Filter to include today's reviews
        stats = review_manager.get_statistics(since=datetime.now() - timedelta(hours=1))
        assert stats.total_reviews == 1

        # Filter to exclude today's reviews
        stats = review_manager.get_statistics(since=datetime.now() + timedelta(hours=1))
        assert stats.total_reviews == 0

"""
Code review workflow management for the ticket system.

Provides:
- ReviewManager: Manages code review workflow
- ReviewResult: Individual review result tracking
- ReviewType: Types of reviews supported

The review workflow:
1. Agent completes ticket -> status moves to UNDER_REVIEW
2. Code Review Agent reviews changes
3. If approved -> AWAITING_APPROVAL (for human)
4. If rejected -> back to IN_PROGRESS with feedback
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from fastband.tickets.models import (
    Ticket,
    TicketComment,
    TicketStatus,
)
from fastband.tickets.storage import TicketStore


class ReviewType(Enum):
    """Types of code reviews."""

    CODE = "code"  # Code quality review
    PROCESS = "process"  # Workflow compliance review
    UIUX = "uiux"  # UI/UX review for frontend changes

    @classmethod
    def from_string(cls, value: str) -> "ReviewType":
        """Convert string to ReviewType."""
        value_lower = value.lower().strip()
        for review_type in cls:
            if review_type.value == value_lower or review_type.name.lower() == value_lower:
                return review_type
        raise ValueError(f"Unknown review type: {value}")

    @property
    def display_name(self) -> str:
        """Get display name with emoji."""
        emoji_map = {
            self.CODE: "Code Review",
            self.PROCESS: "Process Audit",
            self.UIUX: "UI/UX Review",
        }
        return emoji_map.get(self, self.value)


class ReviewStatus(Enum):
    """Status of a review."""

    PENDING = "pending"
    APPROVED = "approved"
    CHANGES_REQUESTED = "changes_requested"

    @classmethod
    def from_string(cls, value: str) -> "ReviewStatus":
        """Convert string to ReviewStatus."""
        value_lower = value.lower().strip().replace(" ", "_")
        for status in cls:
            if status.value == value_lower or status.name.lower() == value_lower:
                return status
        raise ValueError(f"Unknown review status: {value}")


@dataclass
class ReviewResult:
    """
    Individual review result.

    Represents a single reviewer's assessment of a ticket.
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    ticket_id: str = ""
    reviewer_name: str = ""
    reviewer_type: str = "ai"  # "ai" or "human"
    review_type: ReviewType = ReviewType.CODE
    status: ReviewStatus = ReviewStatus.PENDING

    # Review content
    summary: str = ""
    checks_passed: list[str] = field(default_factory=list)
    issues_found: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)

    # For rejections
    rejection_reason: str = ""
    requested_changes: list[str] = field(default_factory=list)
    checklist_failures: list[str] = field(default_factory=list)

    # Security-specific
    security_issues: list[str] = field(default_factory=list)
    bug_risks: list[str] = field(default_factory=list)
    performance_concerns: list[str] = field(default_factory=list)
    code_quality_issues: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    # Timestamps
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime | None = None

    # Files reviewed
    files_reviewed: list[str] = field(default_factory=list)

    # Metadata
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_approved(self) -> bool:
        """Check if review is approved."""
        return self.status == ReviewStatus.APPROVED

    @property
    def is_rejected(self) -> bool:
        """Check if review requested changes."""
        return self.status == ReviewStatus.CHANGES_REQUESTED

    @property
    def is_pending(self) -> bool:
        """Check if review is pending."""
        return self.status == ReviewStatus.PENDING

    @property
    def has_blocking_issues(self) -> bool:
        """Check if there are blocking issues."""
        return bool(self.security_issues or self.bug_risks or self.issues_found)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "ticket_id": self.ticket_id,
            "reviewer_name": self.reviewer_name,
            "reviewer_type": self.reviewer_type,
            "review_type": self.review_type.value,
            "status": self.status.value,
            "summary": self.summary,
            "checks_passed": self.checks_passed,
            "issues_found": self.issues_found,
            "suggestions": self.suggestions,
            "rejection_reason": self.rejection_reason,
            "requested_changes": self.requested_changes,
            "checklist_failures": self.checklist_failures,
            "security_issues": self.security_issues,
            "bug_risks": self.bug_risks,
            "performance_concerns": self.performance_concerns,
            "code_quality_issues": self.code_quality_issues,
            "recommendations": self.recommendations,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "files_reviewed": self.files_reviewed,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ReviewResult":
        """Create from dictionary."""
        review_type = data.get("review_type", "code")
        if isinstance(review_type, str):
            review_type = ReviewType.from_string(review_type)

        status = data.get("status", "pending")
        if isinstance(status, str):
            status = ReviewStatus.from_string(status)

        return cls(
            id=data.get("id", str(uuid.uuid4())),
            ticket_id=data.get("ticket_id", ""),
            reviewer_name=data.get("reviewer_name", ""),
            reviewer_type=data.get("reviewer_type", "ai"),
            review_type=review_type,
            status=status,
            summary=data.get("summary", ""),
            checks_passed=data.get("checks_passed", []),
            issues_found=data.get("issues_found", []),
            suggestions=data.get("suggestions", []),
            rejection_reason=data.get("rejection_reason", ""),
            requested_changes=data.get("requested_changes", []),
            checklist_failures=data.get("checklist_failures", []),
            security_issues=data.get("security_issues", []),
            bug_risks=data.get("bug_risks", []),
            performance_concerns=data.get("performance_concerns", []),
            code_quality_issues=data.get("code_quality_issues", []),
            recommendations=data.get("recommendations", []),
            created_at=datetime.fromisoformat(data["created_at"])
            if data.get("created_at")
            else datetime.now(),
            updated_at=datetime.fromisoformat(data["updated_at"])
            if data.get("updated_at")
            else None,
            files_reviewed=data.get("files_reviewed", []),
            metadata=data.get("metadata", {}),
        )


@dataclass
class ReviewStatistics:
    """
    Aggregate statistics for reviews.
    """

    total_reviews: int = 0
    approved_count: int = 0
    rejected_count: int = 0
    pending_count: int = 0

    # By review type
    code_reviews: int = 0
    process_reviews: int = 0
    uiux_reviews: int = 0

    # Issues summary
    total_issues_found: int = 0
    total_security_issues: int = 0
    total_bug_risks: int = 0
    total_performance_concerns: int = 0

    # Timing
    average_review_time_hours: float | None = None

    # Per reviewer stats
    reviews_by_reviewer: dict[str, int] = field(default_factory=dict)
    approval_rate_by_reviewer: dict[str, float] = field(default_factory=dict)

    @property
    def approval_rate(self) -> float:
        """Calculate overall approval rate."""
        completed = self.approved_count + self.rejected_count
        if completed == 0:
            return 0.0
        return self.approved_count / completed

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total_reviews": self.total_reviews,
            "approved_count": self.approved_count,
            "rejected_count": self.rejected_count,
            "pending_count": self.pending_count,
            "approval_rate": self.approval_rate,
            "code_reviews": self.code_reviews,
            "process_reviews": self.process_reviews,
            "uiux_reviews": self.uiux_reviews,
            "total_issues_found": self.total_issues_found,
            "total_security_issues": self.total_security_issues,
            "total_bug_risks": self.total_bug_risks,
            "total_performance_concerns": self.total_performance_concerns,
            "average_review_time_hours": self.average_review_time_hours,
            "reviews_by_reviewer": self.reviews_by_reviewer,
            "approval_rate_by_reviewer": self.approval_rate_by_reviewer,
        }


class ReviewManager:
    """
    Manages the code review workflow for tickets.

    This class handles:
    - Requesting reviews for completed tickets
    - Tracking review status across multiple reviewers
    - Handling approvals and rejections
    - Collecting and aggregating feedback
    - Calculating review statistics

    Reviews are stored as comments on tickets with comment_type="review".
    """

    def __init__(self, store: TicketStore):
        """
        Initialize ReviewManager.

        Args:
            store: Ticket storage backend
        """
        self.store = store
        self._required_review_types: dict[str, list[ReviewType]] = {}

    def configure_required_reviews(
        self,
        ticket_id: str,
        review_types: list[ReviewType],
    ) -> None:
        """
        Configure which review types are required for a ticket.

        Args:
            ticket_id: Ticket ID
            review_types: List of required review types
        """
        self._required_review_types[ticket_id] = review_types

    def get_required_reviews(self, ticket_id: str) -> list[ReviewType]:
        """
        Get required review types for a ticket.

        Args:
            ticket_id: Ticket ID

        Returns:
            List of required review types (defaults to [CODE] if not configured)
        """
        return self._required_review_types.get(ticket_id, [ReviewType.CODE])

    def request_review(
        self,
        ticket_id: str,
        review_type: ReviewType = ReviewType.CODE,
        reviewer_name: str | None = None,
        files_to_review: list[str] | None = None,
        notes: str = "",
    ) -> dict[str, Any]:
        """
        Request a review for a ticket.

        This should be called when an agent completes their work and
        the ticket transitions to UNDER_REVIEW status.

        Args:
            ticket_id: Ticket to request review for
            review_type: Type of review requested
            reviewer_name: Specific reviewer to assign (optional)
            files_to_review: List of files that need review
            notes: Additional notes for the reviewer

        Returns:
            Dict with success status and review request details
        """
        ticket = self.store.get(ticket_id)
        if not ticket:
            return {
                "success": False,
                "error": f"Ticket {ticket_id} not found",
            }

        # Verify ticket is in correct status
        if ticket.status != TicketStatus.UNDER_REVIEW:
            return {
                "success": False,
                "error": f"Ticket must be in UNDER_REVIEW status to request review. Current: {ticket.status.value}",
            }

        # Create review request as a comment
        review_metadata = {
            "review_type": review_type.value,
            "review_status": "pending",
            "files_to_review": files_to_review or ticket.files_modified,
        }

        content = f"Review requested: {review_type.display_name}"
        if notes:
            content += f"\n\nNotes: {notes}"
        if files_to_review:
            content += "\n\nFiles to review:\n" + "\n".join(f"- {f}" for f in files_to_review)

        comment = ticket.add_comment(
            content=content,
            author=reviewer_name or "Review System",
            author_type="system",
            comment_type="review",
            metadata=review_metadata,
        )

        # Update ticket metadata
        if "pending_reviews" not in ticket.metadata:
            ticket.metadata["pending_reviews"] = []

        ticket.metadata["pending_reviews"].append(
            {
                "review_type": review_type.value,
                "requested_at": datetime.now().isoformat(),
                "reviewer": reviewer_name,
            }
        )

        self.store.update(ticket)

        return {
            "success": True,
            "ticket_id": ticket_id,
            "review_type": review_type.value,
            "comment_id": comment.id,
            "message": f"Review requested: {review_type.display_name}",
        }

    def submit_review(
        self,
        ticket_id: str,
        reviewer_name: str,
        review_type: ReviewType,
        result: ReviewResult,
    ) -> dict[str, Any]:
        """
        Submit a review result.

        This is called by review agents to submit their assessment.

        Args:
            ticket_id: Ticket being reviewed
            reviewer_name: Name of the reviewer
            review_type: Type of review
            result: The review result

        Returns:
            Dict with submission status and next steps
        """
        ticket = self.store.get(ticket_id)
        if not ticket:
            return {
                "success": False,
                "error": f"Ticket {ticket_id} not found",
            }

        # Verify ticket is in review
        if ticket.status != TicketStatus.UNDER_REVIEW:
            return {
                "success": False,
                "error": f"Ticket must be in UNDER_REVIEW status. Current: {ticket.status.value}",
            }

        # Build review content
        result.ticket_id = ticket_id
        result.reviewer_name = reviewer_name
        result.review_type = review_type
        result.updated_at = datetime.now()

        # Create review comment
        content = self._format_review_content(result)

        comment = TicketComment(
            ticket_id=ticket_id,
            author=reviewer_name,
            author_type=result.reviewer_type,
            content=content,
            comment_type="review",
            review_result=result.status.value,
            files_reviewed=result.files_reviewed,
            metadata=result.to_dict(),
        )

        ticket.comments.append(comment)

        # Track reviewer
        if reviewer_name not in ticket.reviewers:
            ticket.reviewers.append(reviewer_name)

        # Add to history
        ticket.add_history(
            action="review_submitted",
            actor=reviewer_name,
            actor_type=result.reviewer_type,
            message=f"{review_type.display_name} submitted: {result.status.value}",
            metadata={"review_id": result.id, "review_type": review_type.value},
        )

        # Handle review result
        if result.is_approved:
            return self._handle_approval(ticket, result)
        else:
            return self._handle_rejection(ticket, result)

    def _handle_approval(
        self,
        ticket: Ticket,
        result: ReviewResult,
    ) -> dict[str, Any]:
        """Handle an approved review."""
        # Check if all required reviews are approved
        required = self.get_required_reviews(ticket.id)
        approved_types = self._get_approved_review_types(ticket)

        all_approved = all(rt in approved_types for rt in required)

        if all_approved:
            # All reviews passed, move to awaiting approval
            ticket.review_status = "approved"
            ticket.transition_status(
                TicketStatus.AWAITING_APPROVAL,
                actor=result.reviewer_name,
                actor_type=result.reviewer_type,
                message="All code reviews passed",
            )
            self.store.update(ticket)

            return {
                "success": True,
                "ticket_id": ticket.id,
                "status": "all_reviews_passed",
                "ticket_status": ticket.status.value,
                "message": "All reviews passed. Ticket moved to awaiting approval.",
            }
        else:
            # More reviews needed
            pending = [rt.value for rt in required if rt not in approved_types]
            self.store.update(ticket)

            return {
                "success": True,
                "ticket_id": ticket.id,
                "status": "review_approved",
                "pending_reviews": pending,
                "message": f"Review approved. Pending reviews: {', '.join(pending)}",
            }

    def _handle_rejection(
        self,
        ticket: Ticket,
        result: ReviewResult,
    ) -> dict[str, Any]:
        """Handle a rejected review."""
        ticket.review_status = "changes_requested"
        ticket.transition_status(
            TicketStatus.IN_PROGRESS,
            actor=result.reviewer_name,
            actor_type=result.reviewer_type,
            message=f"Changes requested: {result.rejection_reason}",
        )
        self.store.update(ticket)

        return {
            "success": True,
            "ticket_id": ticket.id,
            "status": "changes_requested",
            "ticket_status": ticket.status.value,
            "rejection_reason": result.rejection_reason,
            "requested_changes": result.requested_changes,
            "issues_found": result.issues_found,
            "message": "Review rejected. Ticket moved back to in progress.",
        }

    def _get_approved_review_types(self, ticket: Ticket) -> list[ReviewType]:
        """Get list of approved review types for a ticket."""
        approved = []
        for comment in ticket.comments:
            if comment.comment_type == "review" and comment.review_result == "approved":
                review_type_str = comment.metadata.get("review_type", "code")
                try:
                    approved.append(ReviewType.from_string(review_type_str))
                except ValueError:
                    pass
        return approved

    def _format_review_content(self, result: ReviewResult) -> str:
        """Format review result as comment content."""
        lines = [f"## {result.review_type.display_name}"]
        lines.append(f"**Status:** {result.status.value}")

        if result.summary:
            lines.append(f"\n**Summary:** {result.summary}")

        if result.checks_passed:
            lines.append("\n### Checks Passed")
            for check in result.checks_passed:
                lines.append(f"- {check}")

        if result.issues_found:
            lines.append("\n### Issues Found")
            for issue in result.issues_found:
                lines.append(f"- {issue}")

        if result.security_issues:
            lines.append("\n### Security Issues")
            for issue in result.security_issues:
                lines.append(f"- {issue}")

        if result.bug_risks:
            lines.append("\n### Bug Risks")
            for risk in result.bug_risks:
                lines.append(f"- {risk}")

        if result.performance_concerns:
            lines.append("\n### Performance Concerns")
            for concern in result.performance_concerns:
                lines.append(f"- {concern}")

        if result.code_quality_issues:
            lines.append("\n### Code Quality Issues")
            for issue in result.code_quality_issues:
                lines.append(f"- {issue}")

        if result.requested_changes:
            lines.append("\n### Requested Changes")
            for change in result.requested_changes:
                lines.append(f"- {change}")

        if result.suggestions:
            lines.append("\n### Suggestions")
            for suggestion in result.suggestions:
                lines.append(f"- {suggestion}")

        if result.recommendations:
            lines.append("\n### Recommendations")
            for rec in result.recommendations:
                lines.append(f"- {rec}")

        if result.rejection_reason:
            lines.append(f"\n**Rejection Reason:** {result.rejection_reason}")

        return "\n".join(lines)

    def get_review_status(self, ticket_id: str) -> dict[str, Any]:
        """
        Get the current review status for a ticket.

        Args:
            ticket_id: Ticket ID

        Returns:
            Dict with review status details
        """
        ticket = self.store.get(ticket_id)
        if not ticket:
            return {
                "success": False,
                "error": f"Ticket {ticket_id} not found",
            }

        reviews = self._get_reviews(ticket)
        required = self.get_required_reviews(ticket_id)

        # Categorize reviews by status
        pending = []
        approved = []
        rejected = []

        approved_types = set()
        for review in reviews:
            if review.is_approved:
                approved.append(review)
                approved_types.add(review.review_type)
            elif review.is_rejected:
                rejected.append(review)
            else:
                pending.append(review)

        # Check which required reviews are missing
        missing_reviews = [rt for rt in required if rt not in approved_types]

        # Overall status
        if rejected:
            overall_status = "changes_requested"
        elif missing_reviews and not pending:
            overall_status = "needs_review"
        elif pending:
            overall_status = "pending"
        elif not missing_reviews:
            overall_status = "all_approved"
        else:
            overall_status = "unknown"

        return {
            "success": True,
            "ticket_id": ticket_id,
            "ticket_status": ticket.status.value,
            "review_status": ticket.review_status,
            "overall_status": overall_status,
            "required_reviews": [rt.value for rt in required],
            "approved_reviews": [r.to_dict() for r in approved],
            "rejected_reviews": [r.to_dict() for r in rejected],
            "pending_reviews": [r.to_dict() for r in pending],
            "missing_reviews": [rt.value for rt in missing_reviews],
            "reviewers": ticket.reviewers,
            "total_reviews": len(reviews),
        }

    def _get_reviews(self, ticket: Ticket) -> list[ReviewResult]:
        """Extract review results from ticket comments."""
        reviews = []
        for comment in ticket.comments:
            if comment.comment_type == "review" and comment.metadata.get("review_type"):
                try:
                    review = ReviewResult.from_dict(comment.metadata)
                    reviews.append(review)
                except (KeyError, ValueError):
                    # Skip malformed review data
                    pass
        return reviews

    def get_feedback(
        self,
        ticket_id: str,
        review_type: ReviewType | None = None,
        include_approved: bool = True,
    ) -> dict[str, Any]:
        """
        Get all feedback for a ticket.

        Args:
            ticket_id: Ticket ID
            review_type: Filter by review type (optional)
            include_approved: Include feedback from approved reviews

        Returns:
            Dict with aggregated feedback
        """
        ticket = self.store.get(ticket_id)
        if not ticket:
            return {
                "success": False,
                "error": f"Ticket {ticket_id} not found",
            }

        reviews = self._get_reviews(ticket)

        # Filter by type if specified
        if review_type:
            reviews = [r for r in reviews if r.review_type == review_type]

        # Filter approved if not included
        if not include_approved:
            reviews = [r for r in reviews if not r.is_approved]

        # Aggregate feedback
        all_issues = []
        all_suggestions = []
        all_changes_requested = []
        all_security_issues = []
        all_bug_risks = []
        all_performance_concerns = []
        all_recommendations = []
        rejection_reasons = []

        for review in reviews:
            all_issues.extend(review.issues_found)
            all_suggestions.extend(review.suggestions)
            all_changes_requested.extend(review.requested_changes)
            all_security_issues.extend(review.security_issues)
            all_bug_risks.extend(review.bug_risks)
            all_performance_concerns.extend(review.performance_concerns)
            all_recommendations.extend(review.recommendations)
            if review.rejection_reason:
                rejection_reasons.append(
                    {
                        "reviewer": review.reviewer_name,
                        "review_type": review.review_type.value,
                        "reason": review.rejection_reason,
                    }
                )

        return {
            "success": True,
            "ticket_id": ticket_id,
            "review_count": len(reviews),
            "issues_found": all_issues,
            "suggestions": all_suggestions,
            "requested_changes": all_changes_requested,
            "security_issues": all_security_issues,
            "bug_risks": all_bug_risks,
            "performance_concerns": all_performance_concerns,
            "recommendations": all_recommendations,
            "rejection_reasons": rejection_reasons,
            "has_blocking_issues": bool(all_security_issues or all_bug_risks),
        }

    def get_statistics(
        self,
        ticket_ids: list[str] | None = None,
        reviewer_name: str | None = None,
        review_type: ReviewType | None = None,
        since: datetime | None = None,
    ) -> ReviewStatistics:
        """
        Calculate review statistics.

        Args:
            ticket_ids: Filter by specific tickets (optional)
            reviewer_name: Filter by reviewer (optional)
            review_type: Filter by review type (optional)
            since: Only include reviews since this date (optional)

        Returns:
            ReviewStatistics with aggregated stats
        """
        stats = ReviewStatistics()
        reviews_by_reviewer: dict[str, list[ReviewResult]] = {}
        review_times: list[float] = []

        # Get all tickets or specific ones
        if ticket_ids:
            tickets = [self.store.get(tid) for tid in ticket_ids]
            tickets = [t for t in tickets if t is not None]
        else:
            tickets = self.store.list(limit=1000)

        for ticket in tickets:
            reviews = self._get_reviews(ticket)

            for review in reviews:
                # Apply filters
                if reviewer_name and review.reviewer_name != reviewer_name:
                    continue
                if review_type and review.review_type != review_type:
                    continue
                if since and review.created_at < since:
                    continue

                # Count totals
                stats.total_reviews += 1

                # Count by status
                if review.is_approved:
                    stats.approved_count += 1
                elif review.is_rejected:
                    stats.rejected_count += 1
                else:
                    stats.pending_count += 1

                # Count by type
                if review.review_type == ReviewType.CODE:
                    stats.code_reviews += 1
                elif review.review_type == ReviewType.PROCESS:
                    stats.process_reviews += 1
                elif review.review_type == ReviewType.UIUX:
                    stats.uiux_reviews += 1

                # Count issues
                stats.total_issues_found += len(review.issues_found)
                stats.total_security_issues += len(review.security_issues)
                stats.total_bug_risks += len(review.bug_risks)
                stats.total_performance_concerns += len(review.performance_concerns)

                # Track by reviewer
                if review.reviewer_name not in reviews_by_reviewer:
                    reviews_by_reviewer[review.reviewer_name] = []
                reviews_by_reviewer[review.reviewer_name].append(review)

                # Track review time
                if review.updated_at and review.created_at:
                    delta = (review.updated_at - review.created_at).total_seconds() / 3600
                    review_times.append(delta)

        # Calculate per-reviewer stats
        for reviewer, reviewer_reviews in reviews_by_reviewer.items():
            stats.reviews_by_reviewer[reviewer] = len(reviewer_reviews)
            approved = sum(1 for r in reviewer_reviews if r.is_approved)
            completed = sum(1 for r in reviewer_reviews if not r.is_pending)
            if completed > 0:
                stats.approval_rate_by_reviewer[reviewer] = approved / completed
            else:
                stats.approval_rate_by_reviewer[reviewer] = 0.0

        # Calculate average review time
        if review_times:
            stats.average_review_time_hours = sum(review_times) / len(review_times)

        return stats

    def approve_review(
        self,
        ticket_id: str,
        reviewer_name: str,
        review_type: ReviewType,
        summary: str,
        checks_passed: list[str],
        issues_found: list[str] | None = None,
        suggestions: list[str] | None = None,
        files_reviewed: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Convenience method to approve a review.

        Args:
            ticket_id: Ticket ID
            reviewer_name: Name of reviewer
            review_type: Type of review
            summary: Review summary
            checks_passed: List of checks that passed
            issues_found: Minor issues (non-blocking)
            suggestions: Optional improvements
            files_reviewed: Files that were reviewed

        Returns:
            Dict with approval result
        """
        result = ReviewResult(
            reviewer_name=reviewer_name,
            review_type=review_type,
            status=ReviewStatus.APPROVED,
            summary=summary,
            checks_passed=checks_passed,
            issues_found=issues_found or [],
            suggestions=suggestions or [],
            files_reviewed=files_reviewed or [],
        )

        return self.submit_review(
            ticket_id=ticket_id,
            reviewer_name=reviewer_name,
            review_type=review_type,
            result=result,
        )

    def reject_review(
        self,
        ticket_id: str,
        reviewer_name: str,
        review_type: ReviewType,
        rejection_reason: str,
        issues_found: list[str],
        requested_changes: list[str],
        checklist_failures: list[str] | None = None,
        security_issues: list[str] | None = None,
        bug_risks: list[str] | None = None,
        files_reviewed: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Convenience method to reject a review.

        Args:
            ticket_id: Ticket ID
            reviewer_name: Name of reviewer
            review_type: Type of review
            rejection_reason: Main reason for rejection
            issues_found: Critical issues that must be fixed
            requested_changes: Specific changes required
            checklist_failures: Failed checklist items
            security_issues: Security concerns
            bug_risks: Potential bugs found
            files_reviewed: Files that were reviewed

        Returns:
            Dict with rejection result
        """
        result = ReviewResult(
            reviewer_name=reviewer_name,
            review_type=review_type,
            status=ReviewStatus.CHANGES_REQUESTED,
            rejection_reason=rejection_reason,
            issues_found=issues_found,
            requested_changes=requested_changes,
            checklist_failures=checklist_failures or [],
            security_issues=security_issues or [],
            bug_risks=bug_risks or [],
            files_reviewed=files_reviewed or [],
        )

        return self.submit_review(
            ticket_id=ticket_id,
            reviewer_name=reviewer_name,
            review_type=review_type,
            result=result,
        )

    def get_pending_reviews(
        self,
        reviewer_name: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Get all tickets pending review.

        Args:
            reviewer_name: Filter by assigned reviewer (optional)

        Returns:
            List of tickets awaiting review
        """
        # Get all tickets in UNDER_REVIEW status
        tickets = self.store.list(status=TicketStatus.UNDER_REVIEW, limit=1000)

        pending = []
        for ticket in tickets:
            # Get required reviews
            required = self.get_required_reviews(ticket.id)
            approved_types = set(self._get_approved_review_types(ticket))
            missing = [rt for rt in required if rt not in approved_types]

            if missing:
                pending.append(
                    {
                        "ticket_id": ticket.id,
                        "title": ticket.title,
                        "assigned_to": ticket.assigned_to,
                        "files_modified": ticket.files_modified,
                        "missing_reviews": [rt.value for rt in missing],
                        "approved_reviews": [rt.value for rt in approved_types],
                        "reviewers": ticket.reviewers,
                    }
                )

        return pending

    def reassign_review(
        self,
        ticket_id: str,
        review_type: ReviewType,
        new_reviewer: str,
        reason: str = "",
    ) -> dict[str, Any]:
        """
        Reassign a review to a different reviewer.

        Args:
            ticket_id: Ticket ID
            review_type: Type of review to reassign
            new_reviewer: New reviewer name
            reason: Reason for reassignment

        Returns:
            Dict with reassignment status
        """
        ticket = self.store.get(ticket_id)
        if not ticket:
            return {
                "success": False,
                "error": f"Ticket {ticket_id} not found",
            }

        # Add history entry
        ticket.add_history(
            action="review_reassigned",
            actor="Review System",
            actor_type="system",
            message=f"{review_type.display_name} reassigned to {new_reviewer}. {reason}",
            metadata={
                "review_type": review_type.value,
                "new_reviewer": new_reviewer,
                "reason": reason,
            },
        )

        self.store.update(ticket)

        return {
            "success": True,
            "ticket_id": ticket_id,
            "review_type": review_type.value,
            "new_reviewer": new_reviewer,
            "message": f"Review reassigned to {new_reviewer}",
        }

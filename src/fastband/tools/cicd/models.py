"""
CI/CD Models - Data structures for workflow and pipeline management.

Defines standardized representations for:
- Workflows and pipelines
- Runs and jobs
- Build logs and artifacts
- Status and health metrics
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class CIProvider(str, Enum):
    """Supported CI/CD providers."""

    GITHUB_ACTIONS = "github_actions"
    GITLAB_CI = "gitlab_ci"
    CIRCLECI = "circleci"
    JENKINS = "jenkins"
    UNKNOWN = "unknown"


class WorkflowStatus(str, Enum):
    """Status of a workflow/pipeline."""

    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    WAITING = "waiting"
    REQUESTED = "requested"
    PENDING = "pending"
    UNKNOWN = "unknown"


class RunConclusion(str, Enum):
    """Conclusion of a completed run."""

    SUCCESS = "success"
    FAILURE = "failure"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"
    TIMED_OUT = "timed_out"
    ACTION_REQUIRED = "action_required"
    NEUTRAL = "neutral"
    STALE = "stale"
    STARTUP_FAILURE = "startup_failure"
    UNKNOWN = "unknown"

    @classmethod
    def from_string(cls, value: str | None) -> "RunConclusion":
        if not value:
            return cls.UNKNOWN
        mapping = {
            "success": cls.SUCCESS,
            "failure": cls.FAILURE,
            "failed": cls.FAILURE,
            "cancelled": cls.CANCELLED,
            "canceled": cls.CANCELLED,
            "skipped": cls.SKIPPED,
            "timed_out": cls.TIMED_OUT,
            "action_required": cls.ACTION_REQUIRED,
            "neutral": cls.NEUTRAL,
            "stale": cls.STALE,
            "startup_failure": cls.STARTUP_FAILURE,
        }
        return mapping.get(value.lower(), cls.UNKNOWN)


class JobStatus(str, Enum):
    """Status of a job within a run."""

    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    WAITING = "waiting"
    PENDING = "pending"
    UNKNOWN = "unknown"


@dataclass
class WorkflowFile:
    """A workflow definition file."""

    path: str  # e.g., ".github/workflows/ci.yml"
    name: str  # Human-readable name
    provider: CIProvider = CIProvider.GITHUB_ACTIONS

    # Triggers
    triggers: list[str] = field(default_factory=list)  # push, pull_request, etc.

    # Jobs defined
    job_names: list[str] = field(default_factory=list)

    # Metadata
    badge_url: str = ""
    html_url: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "name": self.name,
            "triggers": self.triggers,
            "jobs": self.job_names,
            "badge_url": self.badge_url,
        }


@dataclass
class Step:
    """A single step within a job."""

    name: str
    number: int
    status: JobStatus = JobStatus.UNKNOWN
    conclusion: RunConclusion = RunConclusion.UNKNOWN

    started_at: datetime | None = None
    completed_at: datetime | None = None

    # Output
    log: str = ""
    error_message: str = ""

    @property
    def duration_seconds(self) -> int | None:
        if self.started_at and self.completed_at:
            return int((self.completed_at - self.started_at).total_seconds())
        return None

    @property
    def is_failed(self) -> bool:
        return self.conclusion == RunConclusion.FAILURE

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "number": self.number,
            "status": self.status.value,
            "conclusion": self.conclusion.value,
            "duration_seconds": self.duration_seconds,
            "is_failed": self.is_failed,
        }


@dataclass
class Job:
    """A job within a workflow run."""

    id: int | str
    name: str
    status: JobStatus = JobStatus.UNKNOWN
    conclusion: RunConclusion = RunConclusion.UNKNOWN

    # Timing
    started_at: datetime | None = None
    completed_at: datetime | None = None

    # Steps
    steps: list[Step] = field(default_factory=list)

    # Environment
    runner_name: str = ""
    runner_os: str = ""

    # URLs
    html_url: str = ""
    logs_url: str = ""

    @property
    def duration_seconds(self) -> int | None:
        if self.started_at and self.completed_at:
            return int((self.completed_at - self.started_at).total_seconds())
        return None

    @property
    def is_failed(self) -> bool:
        return self.conclusion == RunConclusion.FAILURE

    @property
    def failed_steps(self) -> list[Step]:
        return [s for s in self.steps if s.is_failed]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status.value,
            "conclusion": self.conclusion.value,
            "duration_seconds": self.duration_seconds,
            "is_failed": self.is_failed,
            "runner": f"{self.runner_name} ({self.runner_os})" if self.runner_name else "",
            "steps_count": len(self.steps),
            "failed_steps": [s.name for s in self.failed_steps],
            "html_url": self.html_url,
        }


@dataclass
class WorkflowRun:
    """A single execution of a workflow."""

    id: int | str
    workflow_name: str
    workflow_id: int | str

    # Status
    status: WorkflowStatus = WorkflowStatus.UNKNOWN
    conclusion: RunConclusion = RunConclusion.UNKNOWN

    # Trigger
    event: str = ""  # push, pull_request, workflow_dispatch, etc.
    triggering_actor: str = ""

    # Git context
    head_branch: str = ""
    head_sha: str = ""
    head_commit_message: str = ""

    # PR context (if applicable)
    pull_request_number: int | None = None
    pull_request_title: str = ""

    # Timing
    created_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None

    # Jobs
    jobs: list[Job] = field(default_factory=list)

    # URLs
    html_url: str = ""
    logs_url: str = ""

    # Run attempt
    run_attempt: int = 1
    run_number: int = 0

    @property
    def duration_seconds(self) -> int | None:
        if self.started_at and self.completed_at:
            return int((self.completed_at - self.started_at).total_seconds())
        return None

    @property
    def is_failed(self) -> bool:
        return self.conclusion == RunConclusion.FAILURE

    @property
    def is_in_progress(self) -> bool:
        return self.status == WorkflowStatus.IN_PROGRESS

    @property
    def failed_jobs(self) -> list[Job]:
        return [j for j in self.jobs if j.is_failed]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "workflow": self.workflow_name,
            "status": self.status.value,
            "conclusion": self.conclusion.value,
            "event": self.event,
            "branch": self.head_branch,
            "sha": self.head_sha[:7] if self.head_sha else "",
            "commit_message": self.head_commit_message[:50] if self.head_commit_message else "",
            "duration_seconds": self.duration_seconds,
            "is_failed": self.is_failed,
            "jobs_count": len(self.jobs),
            "failed_jobs": [j.name for j in self.failed_jobs],
            "html_url": self.html_url,
            "run_number": self.run_number,
        }

    def to_summary(self) -> dict[str, Any]:
        """Shorter summary for lists."""
        status_emoji = {
            WorkflowStatus.COMPLETED: "✅" if self.conclusion == RunConclusion.SUCCESS else "❌",
            WorkflowStatus.IN_PROGRESS: "🔄",
            WorkflowStatus.QUEUED: "⏳",
            WorkflowStatus.WAITING: "⏸️",
        }.get(self.status, "❓")

        return {
            "id": self.id,
            "status": f"{status_emoji} {self.status.value}",
            "conclusion": self.conclusion.value if self.conclusion != RunConclusion.UNKNOWN else None,
            "workflow": self.workflow_name,
            "branch": self.head_branch,
            "event": self.event,
            "duration": f"{self.duration_seconds}s" if self.duration_seconds else "running",
        }


@dataclass
class BuildLog:
    """Parsed build log with error extraction."""

    run_id: int | str
    job_name: str
    step_name: str = ""

    # Raw content
    raw_log: str = ""
    line_count: int = 0

    # Extracted errors
    error_lines: list[str] = field(default_factory=list)
    warning_lines: list[str] = field(default_factory=list)

    # Annotations (if available)
    annotations: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "job": self.job_name,
            "step": self.step_name,
            "line_count": self.line_count,
            "error_count": len(self.error_lines),
            "warning_count": len(self.warning_lines),
            "errors": self.error_lines[:20],  # First 20 errors
            "warnings": self.warning_lines[:10],  # First 10 warnings
        }


@dataclass
class CIHealthMetrics:
    """Health metrics for CI/CD pipelines."""

    # Time period
    period_days: int = 7

    # Run statistics
    total_runs: int = 0
    successful_runs: int = 0
    failed_runs: int = 0
    cancelled_runs: int = 0

    # Success rate
    success_rate: float = 0.0

    # Timing
    average_duration_seconds: int = 0
    median_duration_seconds: int = 0
    p95_duration_seconds: int = 0

    # Trends
    trend: str = "stable"  # improving, declining, stable

    # Flaky tests (if detected)
    flaky_jobs: list[str] = field(default_factory=list)

    # Most common failures
    common_failure_reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "period_days": self.period_days,
            "total_runs": self.total_runs,
            "success_rate": f"{self.success_rate:.1%}",
            "successful": self.successful_runs,
            "failed": self.failed_runs,
            "cancelled": self.cancelled_runs,
            "avg_duration_seconds": self.average_duration_seconds,
            "trend": self.trend,
            "flaky_jobs": self.flaky_jobs[:5],
            "common_failures": self.common_failure_reasons[:5],
        }


@dataclass
class Artifact:
    """A build artifact from a workflow run."""

    id: int | str
    name: str
    size_bytes: int = 0
    expired: bool = False

    created_at: datetime | None = None
    expires_at: datetime | None = None

    download_url: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "size_mb": round(self.size_bytes / (1024 * 1024), 2),
            "expired": self.expired,
            "download_url": self.download_url,
        }


@dataclass
class CICDReport:
    """Complete CI/CD analysis report."""

    # Identity
    report_id: str
    created_at: datetime = field(default_factory=_utc_now)

    # Repository
    repository: str = ""
    default_branch: str = ""
    provider: CIProvider = CIProvider.GITHUB_ACTIONS

    # Workflows
    workflows: list[WorkflowFile] = field(default_factory=list)

    # Recent runs
    recent_runs: list[WorkflowRun] = field(default_factory=list)

    # Health
    health_metrics: CIHealthMetrics | None = None

    # Current status
    has_failing_runs: bool = False
    failing_workflows: list[str] = field(default_factory=list)

    # Analysis
    recommendations: list[str] = field(default_factory=list)

    def to_summary(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "repository": self.repository,
            "provider": self.provider.value,
            "workflow_count": len(self.workflows),
            "recent_runs_count": len(self.recent_runs),
            "has_failures": self.has_failing_runs,
            "failing_workflows": self.failing_workflows,
            "health": self.health_metrics.to_dict() if self.health_metrics else None,
            "recommendations": self.recommendations[:5],
        }

    def to_markdown(self) -> str:
        """Generate markdown report."""
        lines = [
            "# CI/CD Status Report",
            "",
            f"**Repository:** {self.repository}",
            f"**Provider:** {self.provider.value}",
            f"**Generated:** {self.created_at.strftime('%Y-%m-%d %H:%M:%S')} UTC",
            "",
        ]

        # Health summary
        if self.health_metrics:
            h = self.health_metrics
            lines.extend([
                "## Health Summary",
                "",
                "| Metric | Value |",
                "|--------|-------|",
                f"| Success Rate | {h.success_rate:.1%} |",
                f"| Total Runs ({h.period_days}d) | {h.total_runs} |",
                f"| Avg Duration | {h.average_duration_seconds}s |",
                f"| Trend | {h.trend} |",
                "",
            ])

        # Recent runs
        if self.recent_runs:
            lines.extend([
                "## Recent Runs",
                "",
                "| # | Workflow | Branch | Status | Duration |",
                "|---|----------|--------|--------|----------|",
            ])
            for run in self.recent_runs[:10]:
                status = "✅" if run.conclusion == RunConclusion.SUCCESS else "❌" if run.is_failed else "🔄"
                duration = f"{run.duration_seconds}s" if run.duration_seconds else "..."
                lines.append(f"| {run.run_number} | {run.workflow_name} | {run.head_branch} | {status} | {duration} |")
            lines.append("")

        # Failing workflows
        if self.failing_workflows:
            lines.extend([
                "## Failing Workflows",
                "",
            ])
            for wf in self.failing_workflows:
                lines.append(f"- ❌ {wf}")
            lines.append("")

        # Recommendations
        if self.recommendations:
            lines.extend([
                "## Recommendations",
                "",
            ])
            for rec in self.recommendations:
                lines.append(f"- {rec}")
            lines.append("")

        return "\n".join(lines)

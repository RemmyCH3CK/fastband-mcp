"""
GitHub Actions Integration - Interact with GitHub Actions workflows.

Provides:
- List workflows and runs
- Get run details and logs
- Trigger workflow dispatch
- Cancel/re-run workflows
- Extract errors from build logs
"""

import logging
import os
import re
import subprocess
from datetime import datetime, timezone
from typing import Any

from fastband.tools.cicd.models import (
    Artifact,
    BuildLog,
    CIHealthMetrics,
    CIProvider,
    Job,
    JobStatus,
    RunConclusion,
    Step,
    WorkflowFile,
    WorkflowRun,
    WorkflowStatus,
)

logger = logging.getLogger(__name__)


class GitHubActionsClient:
    """
    Client for interacting with GitHub Actions via gh CLI.

    Uses the GitHub CLI (gh) for authentication and API access,
    avoiding the need to manage tokens directly.
    """

    def __init__(self, repo: str | None = None):
        """
        Initialize the GitHub Actions client.

        Args:
            repo: Repository in owner/repo format. If None, uses current repo.
        """
        self.repo = repo or self._detect_repo()
        self._check_gh_cli()

    def _check_gh_cli(self) -> None:
        """Verify gh CLI is available and authenticated."""
        try:
            result = subprocess.run(
                ["gh", "auth", "status"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                logger.warning("gh CLI not authenticated. Some features may not work.")
        except FileNotFoundError:
            logger.warning("gh CLI not found. Install with: brew install gh")
        except Exception as e:
            logger.debug(f"gh CLI check failed: {e}")

    def _detect_repo(self) -> str:
        """Detect repository from git remote."""
        try:
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                url = result.stdout.strip()
                # Parse github.com/owner/repo from various URL formats
                patterns = [
                    r"github\.com[:/]([^/]+/[^/]+?)(?:\.git)?$",
                    r"^([^/]+/[^/]+)$",
                ]
                for pattern in patterns:
                    match = re.search(pattern, url)
                    if match:
                        return match.group(1).rstrip(".git")
        except Exception as e:
            logger.debug(f"Failed to detect repo: {e}")
        return ""

    def _run_gh(
        self,
        args: list[str],
        timeout: int = 30,
    ) -> dict[str, Any] | list[Any] | str | None:
        """
        Run a gh CLI command and return parsed JSON or text output.

        Args:
            args: Arguments to pass to gh
            timeout: Command timeout in seconds

        Returns:
            Parsed JSON response or raw text
        """
        cmd = ["gh"] + args
        if self.repo and "--repo" not in args and "-R" not in args:
            cmd.extend(["--repo", self.repo])

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )

            if result.returncode != 0:
                logger.debug(f"gh command failed: {result.stderr}")
                return None

            output = result.stdout.strip()
            if not output:
                return None

            # Try to parse as JSON
            import json
            try:
                return json.loads(output)
            except json.JSONDecodeError:
                return output

        except subprocess.TimeoutExpired:
            logger.warning(f"gh command timed out: {' '.join(cmd)}")
            return None
        except Exception as e:
            logger.debug(f"gh command error: {e}")
            return None

    # =========================================================================
    # WORKFLOWS
    # =========================================================================

    def list_workflows(self) -> list[WorkflowFile]:
        """List all workflows in the repository."""
        data = self._run_gh([
            "api",
            f"/repos/{self.repo}/actions/workflows",
            "--jq", ".workflows",
        ])

        if not isinstance(data, list):
            return []

        workflows = []
        for wf in data:
            workflow = WorkflowFile(
                path=wf.get("path", ""),
                name=wf.get("name", ""),
                provider=CIProvider.GITHUB_ACTIONS,
                badge_url=wf.get("badge_url", ""),
                html_url=wf.get("html_url", ""),
            )
            workflows.append(workflow)

        return workflows

    def get_workflow(self, workflow_id: int | str) -> WorkflowFile | None:
        """Get a specific workflow by ID or filename."""
        data = self._run_gh([
            "api",
            f"/repos/{self.repo}/actions/workflows/{workflow_id}",
        ])

        if not isinstance(data, dict):
            return None

        return WorkflowFile(
            path=data.get("path", ""),
            name=data.get("name", ""),
            provider=CIProvider.GITHUB_ACTIONS,
            badge_url=data.get("badge_url", ""),
            html_url=data.get("html_url", ""),
        )

    # =========================================================================
    # RUNS
    # =========================================================================

    def list_runs(
        self,
        workflow_id: int | str | None = None,
        branch: str | None = None,
        status: str | None = None,
        limit: int = 20,
    ) -> list[WorkflowRun]:
        """
        List workflow runs.

        Args:
            workflow_id: Filter by workflow (optional)
            branch: Filter by branch (optional)
            status: Filter by status: queued, in_progress, completed
            limit: Maximum runs to return
        """
        args = ["run", "list", "--json",
                "databaseId,workflowName,headBranch,headSha,status,conclusion,"
                "event,createdAt,updatedAt,url,number,workflowDatabaseId"]

        if workflow_id:
            args.extend(["--workflow", str(workflow_id)])
        if branch:
            args.extend(["--branch", branch])
        if status:
            args.extend(["--status", status])
        args.extend(["--limit", str(limit)])

        data = self._run_gh(args)

        if not isinstance(data, list):
            return []

        runs = []
        for run_data in data:
            run = self._parse_run(run_data)
            if run:
                runs.append(run)

        return runs

    def get_run(self, run_id: int | str) -> WorkflowRun | None:
        """Get details of a specific run."""
        data = self._run_gh([
            "api",
            f"/repos/{self.repo}/actions/runs/{run_id}",
        ])

        if not isinstance(data, dict):
            return None

        run = self._parse_run_api(data)

        # Also get jobs
        jobs = self.get_run_jobs(run_id)
        if run:
            run.jobs = jobs

        return run

    def get_run_jobs(self, run_id: int | str) -> list[Job]:
        """Get jobs for a workflow run."""
        data = self._run_gh([
            "api",
            f"/repos/{self.repo}/actions/runs/{run_id}/jobs",
            "--jq", ".jobs",
        ])

        if not isinstance(data, list):
            return []

        jobs = []
        for job_data in data:
            job = self._parse_job(job_data)
            if job:
                jobs.append(job)

        return jobs

    def get_run_logs(self, run_id: int | str) -> BuildLog | None:
        """
        Get logs for a workflow run.

        Note: This downloads the full log archive. For large logs,
        use get_job_logs for specific jobs.
        """
        # Use gh run view to get formatted logs
        output = self._run_gh([
            "run", "view", str(run_id), "--log",
        ], timeout=60)

        if not isinstance(output, str):
            return None

        # Parse the log output
        return self._parse_build_log(run_id, output)

    def get_job_logs(self, job_id: int | str) -> BuildLog | None:
        """Get logs for a specific job."""
        output = self._run_gh([
            "api",
            f"/repos/{self.repo}/actions/jobs/{job_id}/logs",
        ], timeout=60)

        if not isinstance(output, str):
            return None

        return self._parse_build_log(job_id, output)

    def get_failed_logs(self, run_id: int | str) -> BuildLog | None:
        """Get logs only for failed steps in a run."""
        output = self._run_gh([
            "run", "view", str(run_id), "--log-failed",
        ], timeout=60)

        if not isinstance(output, str):
            return None

        return self._parse_build_log(run_id, output, failed_only=True)

    # =========================================================================
    # ACTIONS
    # =========================================================================

    def trigger_workflow(
        self,
        workflow_id: int | str,
        ref: str = "main",
        inputs: dict[str, str] | None = None,
    ) -> bool:
        """
        Trigger a workflow_dispatch event.

        Args:
            workflow_id: Workflow ID or filename
            ref: Branch/tag/SHA to run on
            inputs: Input parameters for the workflow

        Returns:
            True if triggered successfully
        """
        args = ["workflow", "run", str(workflow_id), "--ref", ref]

        if inputs:
            for key, value in inputs.items():
                args.extend(["--field", f"{key}={value}"])

        result = self._run_gh(args)
        # gh workflow run returns empty on success
        return result is not None or result == ""

    def cancel_run(self, run_id: int | str) -> bool:
        """Cancel a workflow run."""
        result = self._run_gh(["run", "cancel", str(run_id)])
        return result is not None or result == ""

    def rerun_run(self, run_id: int | str, failed_only: bool = False) -> bool:
        """
        Re-run a workflow run.

        Args:
            run_id: Run ID to re-run
            failed_only: Only re-run failed jobs

        Returns:
            True if re-run triggered successfully
        """
        args = ["run", "rerun", str(run_id)]
        if failed_only:
            args.append("--failed")

        result = self._run_gh(args)
        return result is not None or result == ""

    # =========================================================================
    # ARTIFACTS
    # =========================================================================

    def list_artifacts(self, run_id: int | str) -> list[Artifact]:
        """List artifacts from a workflow run."""
        data = self._run_gh([
            "api",
            f"/repos/{self.repo}/actions/runs/{run_id}/artifacts",
            "--jq", ".artifacts",
        ])

        if not isinstance(data, list):
            return []

        artifacts = []
        for art_data in data:
            artifact = Artifact(
                id=art_data.get("id", 0),
                name=art_data.get("name", ""),
                size_bytes=art_data.get("size_in_bytes", 0),
                expired=art_data.get("expired", False),
                download_url=art_data.get("archive_download_url", ""),
            )
            if art_data.get("created_at"):
                artifact.created_at = self._parse_datetime(art_data["created_at"])
            if art_data.get("expires_at"):
                artifact.expires_at = self._parse_datetime(art_data["expires_at"])
            artifacts.append(artifact)

        return artifacts

    def download_artifact(
        self,
        artifact_id: int | str,
        output_dir: str,
    ) -> str | None:
        """
        Download an artifact to a directory.

        Returns:
            Path to downloaded artifact or None on failure
        """
        output = self._run_gh([
            "api",
            f"/repos/{self.repo}/actions/artifacts/{artifact_id}/zip",
            "--output", os.path.join(output_dir, f"artifact-{artifact_id}.zip"),
        ])
        if output is not None:
            return os.path.join(output_dir, f"artifact-{artifact_id}.zip")
        return None

    # =========================================================================
    # HEALTH METRICS
    # =========================================================================

    def get_health_metrics(
        self,
        workflow_id: int | str | None = None,
        days: int = 7,
    ) -> CIHealthMetrics:
        """
        Calculate health metrics for workflows.

        Args:
            workflow_id: Filter to specific workflow (optional)
            days: Number of days to analyze
        """
        # Get recent runs
        runs = self.list_runs(workflow_id=workflow_id, limit=100)

        # Filter to time period
        cutoff = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        from datetime import timedelta
        cutoff = cutoff - timedelta(days=days)

        recent_runs = [r for r in runs if r.created_at and r.created_at >= cutoff]

        if not recent_runs:
            return CIHealthMetrics(period_days=days)

        # Calculate metrics
        total = len(recent_runs)
        successful = sum(1 for r in recent_runs if r.conclusion == RunConclusion.SUCCESS)
        failed = sum(1 for r in recent_runs if r.conclusion == RunConclusion.FAILURE)
        cancelled = sum(1 for r in recent_runs if r.conclusion == RunConclusion.CANCELLED)

        # Durations
        durations = [r.duration_seconds for r in recent_runs if r.duration_seconds]
        avg_duration = int(sum(durations) / len(durations)) if durations else 0
        sorted_durations = sorted(durations)
        median_duration = sorted_durations[len(sorted_durations) // 2] if sorted_durations else 0
        p95_duration = sorted_durations[int(len(sorted_durations) * 0.95)] if len(sorted_durations) > 1 else 0

        # Trend (compare first half vs second half)
        mid = len(recent_runs) // 2
        if mid > 0:
            first_half_rate = sum(1 for r in recent_runs[:mid] if r.conclusion == RunConclusion.SUCCESS) / mid
            second_half_rate = sum(1 for r in recent_runs[mid:] if r.conclusion == RunConclusion.SUCCESS) / (len(recent_runs) - mid)
            if second_half_rate > first_half_rate + 0.1:
                trend = "improving"
            elif second_half_rate < first_half_rate - 0.1:
                trend = "declining"
            else:
                trend = "stable"
        else:
            trend = "stable"

        # Detect flaky jobs (failed then succeeded on same workflow)
        flaky_jobs: list[str] = []
        # This would require more sophisticated analysis

        return CIHealthMetrics(
            period_days=days,
            total_runs=total,
            successful_runs=successful,
            failed_runs=failed,
            cancelled_runs=cancelled,
            success_rate=successful / total if total > 0 else 0,
            average_duration_seconds=avg_duration,
            median_duration_seconds=median_duration,
            p95_duration_seconds=p95_duration,
            trend=trend,
            flaky_jobs=flaky_jobs,
        )

    # =========================================================================
    # PARSING HELPERS
    # =========================================================================

    def _parse_run(self, data: dict[str, Any]) -> WorkflowRun | None:
        """Parse run from gh run list JSON output."""
        try:
            status_map = {
                "queued": WorkflowStatus.QUEUED,
                "in_progress": WorkflowStatus.IN_PROGRESS,
                "completed": WorkflowStatus.COMPLETED,
                "waiting": WorkflowStatus.WAITING,
                "requested": WorkflowStatus.REQUESTED,
                "pending": WorkflowStatus.PENDING,
            }

            run = WorkflowRun(
                id=data.get("databaseId", 0),
                workflow_name=data.get("workflowName", ""),
                workflow_id=data.get("workflowDatabaseId", 0),
                status=status_map.get(data.get("status", "").lower(), WorkflowStatus.UNKNOWN),
                conclusion=RunConclusion.from_string(data.get("conclusion")),
                event=data.get("event", ""),
                head_branch=data.get("headBranch", ""),
                head_sha=data.get("headSha", ""),
                html_url=data.get("url", ""),
                run_number=data.get("number", 0),
            )

            if data.get("createdAt"):
                run.created_at = self._parse_datetime(data["createdAt"])
            if data.get("updatedAt"):
                run.completed_at = self._parse_datetime(data["updatedAt"])

            return run
        except Exception as e:
            logger.debug(f"Failed to parse run: {e}")
            return None

    def _parse_run_api(self, data: dict[str, Any]) -> WorkflowRun | None:
        """Parse run from API response."""
        try:
            status_map = {
                "queued": WorkflowStatus.QUEUED,
                "in_progress": WorkflowStatus.IN_PROGRESS,
                "completed": WorkflowStatus.COMPLETED,
                "waiting": WorkflowStatus.WAITING,
                "requested": WorkflowStatus.REQUESTED,
                "pending": WorkflowStatus.PENDING,
            }

            run = WorkflowRun(
                id=data.get("id", 0),
                workflow_name=data.get("name", ""),
                workflow_id=data.get("workflow_id", 0),
                status=status_map.get(data.get("status", "").lower(), WorkflowStatus.UNKNOWN),
                conclusion=RunConclusion.from_string(data.get("conclusion")),
                event=data.get("event", ""),
                triggering_actor=data.get("triggering_actor", {}).get("login", ""),
                head_branch=data.get("head_branch", ""),
                head_sha=data.get("head_sha", ""),
                html_url=data.get("html_url", ""),
                run_number=data.get("run_number", 0),
                run_attempt=data.get("run_attempt", 1),
            )

            # Commit message
            head_commit = data.get("head_commit", {})
            if head_commit:
                run.head_commit_message = head_commit.get("message", "")

            # PR info
            prs = data.get("pull_requests", [])
            if prs:
                run.pull_request_number = prs[0].get("number")

            # Timestamps
            if data.get("created_at"):
                run.created_at = self._parse_datetime(data["created_at"])
            if data.get("run_started_at"):
                run.started_at = self._parse_datetime(data["run_started_at"])
            if data.get("updated_at") and run.status == WorkflowStatus.COMPLETED:
                run.completed_at = self._parse_datetime(data["updated_at"])

            return run
        except Exception as e:
            logger.debug(f"Failed to parse run: {e}")
            return None

    def _parse_job(self, data: dict[str, Any]) -> Job | None:
        """Parse job from API response."""
        try:
            status_map = {
                "queued": JobStatus.QUEUED,
                "in_progress": JobStatus.IN_PROGRESS,
                "completed": JobStatus.COMPLETED,
                "waiting": JobStatus.WAITING,
                "pending": JobStatus.PENDING,
            }

            job = Job(
                id=data.get("id", 0),
                name=data.get("name", ""),
                status=status_map.get(data.get("status", "").lower(), JobStatus.UNKNOWN),
                conclusion=RunConclusion.from_string(data.get("conclusion")),
                runner_name=data.get("runner_name", ""),
                runner_os=data.get("runner_os", "") or data.get("labels", [""])[0] if data.get("labels") else "",
                html_url=data.get("html_url", ""),
            )

            if data.get("started_at"):
                job.started_at = self._parse_datetime(data["started_at"])
            if data.get("completed_at"):
                job.completed_at = self._parse_datetime(data["completed_at"])

            # Parse steps
            steps_data = data.get("steps", [])
            for step_data in steps_data:
                step = Step(
                    name=step_data.get("name", ""),
                    number=step_data.get("number", 0),
                    status=status_map.get(step_data.get("status", "").lower(), JobStatus.UNKNOWN),
                    conclusion=RunConclusion.from_string(step_data.get("conclusion")),
                )
                if step_data.get("started_at"):
                    step.started_at = self._parse_datetime(step_data["started_at"])
                if step_data.get("completed_at"):
                    step.completed_at = self._parse_datetime(step_data["completed_at"])
                job.steps.append(step)

            return job
        except Exception as e:
            logger.debug(f"Failed to parse job: {e}")
            return None

    def _parse_datetime(self, dt_str: str) -> datetime | None:
        """Parse ISO datetime string."""
        try:
            # Handle various ISO formats
            dt_str = dt_str.replace("Z", "+00:00")
            return datetime.fromisoformat(dt_str)
        except Exception:
            return None

    def _parse_build_log(
        self,
        run_or_job_id: int | str,
        log_text: str,
        failed_only: bool = False,
    ) -> BuildLog:
        """Parse build log and extract errors."""
        lines = log_text.split("\n")

        # Error patterns
        error_patterns = [
            r"(?i)^.*error[:\s].*$",
            r"(?i)^.*failed[:\s].*$",
            r"(?i)^.*exception[:\s].*$",
            r"(?i)^.*traceback.*$",
            r"(?i)^E\s+.*$",  # pytest errors
            r"(?i)^FAILED.*$",
            r"(?i)^error\[.*\].*$",  # Rust errors
            r"(?i)^.*npm ERR!.*$",
            r"(?i)^.*SyntaxError.*$",
            r"(?i)^.*TypeError.*$",
            r"(?i)^.*AssertionError.*$",
        ]

        warning_patterns = [
            r"(?i)^.*warning[:\s].*$",
            r"(?i)^.*warn[:\s].*$",
            r"(?i)^.*deprecated.*$",
        ]

        error_lines = []
        warning_lines = []
        job_name = ""
        step_name = ""

        for line in lines:
            # Try to extract job/step name from log format
            # GitHub format: "job-name\tstep-name\t..."
            if "\t" in line:
                parts = line.split("\t")
                if len(parts) >= 2:
                    job_name = parts[0]
                    step_name = parts[1] if len(parts) > 1 else ""

            # Check for errors
            for pattern in error_patterns:
                if re.search(pattern, line):
                    error_lines.append(line.strip())
                    break

            # Check for warnings
            for pattern in warning_patterns:
                if re.search(pattern, line):
                    warning_lines.append(line.strip())
                    break

        return BuildLog(
            run_id=run_or_job_id,
            job_name=job_name,
            step_name=step_name,
            raw_log=log_text if not failed_only else "",
            line_count=len(lines),
            error_lines=list(set(error_lines))[:50],  # Dedupe, limit
            warning_lines=list(set(warning_lines))[:30],
        )

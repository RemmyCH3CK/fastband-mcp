"""
CI/CD Tool - Unified interface for CI/CD operations.

Provides MCP tools for:
- Viewing workflow status and history
- Getting build logs and errors
- Triggering and managing workflow runs
- Health metrics and recommendations
"""

import logging
import os
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastband.tools.cicd.github import GitHubActionsClient
from fastband.tools.cicd.models import (
    CICDReport,
    CIProvider,
    RunConclusion,
    WorkflowStatus,
)

logger = logging.getLogger(__name__)


@dataclass
class CICDConfig:
    """Configuration for CI/CD operations."""

    provider: CIProvider = CIProvider.GITHUB_ACTIONS
    repo: str = ""  # owner/repo format
    default_branch: str = "main"


class CICDTool:
    """
    Unified CI/CD tool for workflow management.

    Currently supports GitHub Actions with extensibility for
    GitLab CI, CircleCI, etc.
    """

    def __init__(self, project_root: str, config: CICDConfig | None = None):
        self.project_root = Path(project_root)
        self.config = config or CICDConfig()

        # Initialize provider client
        self._github: GitHubActionsClient | None = None

    @property
    def github(self) -> GitHubActionsClient:
        """Get or create GitHub Actions client."""
        if self._github is None:
            self._github = GitHubActionsClient(self.config.repo or None)
        return self._github

    # =========================================================================
    # STATUS & OVERVIEW
    # =========================================================================

    async def get_status(self) -> CICDReport:
        """
        Get overall CI/CD status for the repository.

        Returns comprehensive report including:
        - All workflows
        - Recent runs
        - Health metrics
        - Recommendations
        """
        report = CICDReport(
            report_id=str(uuid.uuid4())[:8],
            repository=self.github.repo,
            provider=CIProvider.GITHUB_ACTIONS,
        )

        # Get workflows
        report.workflows = self.github.list_workflows()

        # Get recent runs
        report.recent_runs = self.github.list_runs(limit=20)

        # Check for failures
        failing = [r for r in report.recent_runs[:5] if r.is_failed]
        report.has_failing_runs = len(failing) > 0
        report.failing_workflows = list({r.workflow_name for r in failing})

        # Get health metrics
        report.health_metrics = self.github.get_health_metrics(days=7)

        # Generate recommendations
        report.recommendations = self._generate_recommendations(report)

        return report

    async def get_runs(
        self,
        workflow: str | None = None,
        branch: str | None = None,
        status: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """
        List workflow runs with optional filters.

        Args:
            workflow: Filter by workflow name/id
            branch: Filter by branch
            status: Filter by status (queued, in_progress, completed)
            limit: Maximum runs to return
        """
        runs = self.github.list_runs(
            workflow_id=workflow,
            branch=branch,
            status=status,
            limit=limit,
        )
        return [r.to_summary() for r in runs]

    async def get_run_details(self, run_id: int | str) -> dict[str, Any]:
        """
        Get detailed information about a workflow run.

        Includes jobs, steps, timing, and failure information.
        """
        run = self.github.get_run(run_id)
        if not run:
            return {"error": f"Run {run_id} not found"}

        result = run.to_dict()

        # Add job details
        result["jobs"] = [j.to_dict() for j in run.jobs]

        # If failed, get error summary
        if run.is_failed:
            failed_logs = self.github.get_failed_logs(run_id)
            if failed_logs:
                result["errors"] = failed_logs.error_lines[:10]
                result["failed_job"] = failed_logs.job_name
                result["failed_step"] = failed_logs.step_name

        return result

    async def get_logs(
        self,
        run_id: int | str,
        failed_only: bool = True,
    ) -> dict[str, Any]:
        """
        Get build logs from a workflow run.

        Args:
            run_id: Workflow run ID
            failed_only: Only return logs from failed steps

        Returns:
            Parsed log with extracted errors and warnings
        """
        if failed_only:
            log = self.github.get_failed_logs(run_id)
        else:
            log = self.github.get_run_logs(run_id)

        if not log:
            return {"error": f"Could not retrieve logs for run {run_id}"}

        return log.to_dict()

    # =========================================================================
    # ACTIONS
    # =========================================================================

    async def trigger_workflow(
        self,
        workflow: str,
        branch: str | None = None,
        inputs: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """
        Trigger a workflow run via workflow_dispatch.

        Args:
            workflow: Workflow filename or ID
            branch: Branch to run on (default: main)
            inputs: Input parameters for the workflow

        Returns:
            Success status and run URL
        """
        ref = branch or self.config.default_branch

        success = self.github.trigger_workflow(workflow, ref=ref, inputs=inputs)

        if success:
            return {
                "success": True,
                "message": f"Triggered workflow '{workflow}' on branch '{ref}'",
                "note": "Use cicd_status to check the run status",
            }
        else:
            return {
                "success": False,
                "error": f"Failed to trigger workflow '{workflow}'",
                "hint": "Ensure the workflow has workflow_dispatch trigger enabled",
            }

    async def cancel_run(self, run_id: int | str) -> dict[str, Any]:
        """Cancel a running workflow."""
        success = self.github.cancel_run(run_id)
        return {
            "success": success,
            "message": f"Cancelled run {run_id}" if success else f"Failed to cancel run {run_id}",
        }

    async def rerun(
        self,
        run_id: int | str,
        failed_only: bool = True,
    ) -> dict[str, Any]:
        """
        Re-run a workflow.

        Args:
            run_id: Run ID to re-run
            failed_only: Only re-run failed jobs (faster)
        """
        success = self.github.rerun_run(run_id, failed_only=failed_only)
        return {
            "success": success,
            "message": f"Re-running {'failed jobs in ' if failed_only else ''}run {run_id}" if success else f"Failed to re-run {run_id}",
        }

    # =========================================================================
    # HEALTH & ANALYSIS
    # =========================================================================

    async def get_health(
        self,
        workflow: str | None = None,
        days: int = 7,
    ) -> dict[str, Any]:
        """
        Get CI/CD health metrics.

        Args:
            workflow: Filter to specific workflow
            days: Time period to analyze

        Returns:
            Health metrics including success rate, trends, duration stats
        """
        metrics = self.github.get_health_metrics(
            workflow_id=workflow,
            days=days,
        )
        return metrics.to_dict()

    async def diagnose_failure(self, run_id: int | str) -> dict[str, Any]:
        """
        Diagnose why a run failed with actionable insights.

        Analyzes logs, identifies error patterns, and suggests fixes.
        """
        run = self.github.get_run(run_id)
        if not run:
            return {"error": f"Run {run_id} not found"}

        if not run.is_failed:
            return {
                "status": "not_failed",
                "message": f"Run {run_id} did not fail (status: {run.conclusion.value})",
            }

        # Get failed jobs
        failed_jobs = run.failed_jobs

        # Get error logs
        log = self.github.get_failed_logs(run_id)

        diagnosis = {
            "run_id": run_id,
            "workflow": run.workflow_name,
            "branch": run.head_branch,
            "commit": run.head_sha[:7],
            "failed_jobs": [j.name for j in failed_jobs],
            "errors": [],
            "suggestions": [],
        }

        if log:
            diagnosis["errors"] = log.error_lines[:20]

            # Analyze errors and suggest fixes
            suggestions = self._analyze_errors(log.error_lines)
            diagnosis["suggestions"] = suggestions

        # Add job-level details
        diagnosis["job_details"] = []
        for job in failed_jobs:
            job_info = {
                "name": job.name,
                "failed_steps": [s.name for s in job.failed_steps],
                "duration": job.duration_seconds,
            }
            diagnosis["job_details"].append(job_info)

        return diagnosis

    # =========================================================================
    # ARTIFACTS
    # =========================================================================

    async def list_artifacts(self, run_id: int | str) -> dict[str, Any]:
        """List artifacts from a workflow run."""
        artifacts = self.github.list_artifacts(run_id)
        return {
            "run_id": run_id,
            "artifact_count": len(artifacts),
            "artifacts": [a.to_dict() for a in artifacts],
        }

    # =========================================================================
    # HELPERS
    # =========================================================================

    def _generate_recommendations(self, report: CICDReport) -> list[str]:
        """Generate recommendations based on CI/CD status."""
        recommendations = []

        if report.health_metrics:
            h = report.health_metrics

            # Success rate recommendations
            if h.success_rate < 0.7:
                recommendations.append(
                    f"Low success rate ({h.success_rate:.0%}). Review failing workflows and fix flaky tests."
                )
            elif h.success_rate < 0.9:
                recommendations.append(
                    f"Success rate at {h.success_rate:.0%}. Consider investigating intermittent failures."
                )

            # Duration recommendations
            if h.average_duration_seconds > 600:  # > 10 min
                recommendations.append(
                    f"Average build time is {h.average_duration_seconds // 60} minutes. "
                    "Consider parallelizing jobs or caching dependencies."
                )

            # Trend recommendations
            if h.trend == "declining":
                recommendations.append(
                    "CI health is declining. Recent changes may have introduced instability."
                )

            # Flaky tests
            if h.flaky_jobs:
                recommendations.append(
                    f"Flaky jobs detected: {', '.join(h.flaky_jobs[:3])}. "
                    "Consider adding retry logic or investigating test isolation."
                )

        # Failing workflow recommendations
        if report.failing_workflows:
            for wf in report.failing_workflows[:3]:
                recommendations.append(
                    f"Workflow '{wf}' is failing. Use cicd_diagnose to investigate."
                )

        if not recommendations:
            recommendations.append("CI/CD pipelines are healthy. No immediate action needed.")

        return recommendations

    def _analyze_errors(self, error_lines: list[str]) -> list[str]:
        """Analyze error patterns and suggest fixes."""
        suggestions = []
        seen_suggestions = set()

        error_text = "\n".join(error_lines).lower()

        # Common error patterns and suggestions
        patterns = [
            # Dependencies
            (["npm err", "npm error", "package.json"], "Dependency installation failed. Try `npm ci` or clear node_modules cache."),
            (["pip install", "no matching distribution", "could not find"], "Python package installation failed. Check requirements.txt versions."),
            (["go mod", "module not found"], "Go module resolution failed. Run `go mod tidy`."),

            # Tests
            (["pytest", "failed", "error"], "Test failures detected. Review the test output above."),
            (["jest", "test failed"], "Jest tests failed. Check test assertions and mocks."),
            (["assertionerror", "assert"], "Assertion failed. Verify expected vs actual values."),

            # Linting
            (["eslint", "error"], "ESLint errors. Run `npm run lint -- --fix` locally."),
            (["ruff", "error"], "Ruff linting errors. Run `ruff check --fix` locally."),
            (["mypy", "error"], "Type errors found. Check type annotations."),

            # Build
            (["typeerror", "referenceerror"], "JavaScript runtime error. Check variable definitions and types."),
            (["syntaxerror"], "Syntax error in code. Check for typos or missing brackets."),
            (["build failed", "compilation error"], "Build failed. Check compiler output for specific errors."),

            # Docker
            (["docker", "failed to build"], "Docker build failed. Check Dockerfile and build context."),
            (["no space left on device"], "Disk space exhausted. Clean up old images/artifacts."),

            # Permissions
            (["permission denied", "eacces"], "Permission error. Check file permissions and user context."),
            (["authentication failed", "401", "403"], "Authentication/authorization error. Check credentials and tokens."),

            # Network
            (["timeout", "timed out"], "Operation timed out. Check network connectivity or increase timeout."),
            (["connection refused", "econnrefused"], "Connection refused. Verify service is running and accessible."),

            # Resources
            (["out of memory", "oom", "heap"], "Memory exhausted. Increase memory limit or optimize code."),
            (["killed", "signal 9"], "Process was killed. Likely out of memory or timeout."),
        ]

        for keywords, suggestion in patterns:
            if any(kw in error_text for kw in keywords):
                if suggestion not in seen_suggestions:
                    suggestions.append(suggestion)
                    seen_suggestions.add(suggestion)

        if not suggestions:
            suggestions.append("Review the error logs above for specific failure details.")

        return suggestions[:5]  # Limit suggestions


# =========================================================================
# MCP TOOL FUNCTIONS
# =========================================================================

async def cicd_status(repo: str = "") -> dict[str, Any]:
    """
    Get CI/CD pipeline status overview.

    Returns current state of all workflows, recent runs,
    health metrics, and recommendations.

    Args:
        repo: Repository in owner/repo format (optional, auto-detects)

    Returns:
        Complete CI/CD status report with:
        - workflows: List of workflow definitions
        - recent_runs: Recent workflow runs with status
        - health: Success rate, trends, duration stats
        - failing: Currently failing workflows
        - recommendations: Actionable suggestions
    """
    config = CICDConfig(repo=repo) if repo else CICDConfig()
    tool = CICDTool(os.getcwd(), config)

    report = await tool.get_status()

    return {
        "type": "cicd_status",
        **report.to_summary(),
        "markdown": report.to_markdown(),
    }


async def cicd_runs(
    workflow: str = "",
    branch: str = "",
    status: str = "",
    limit: int = 10,
) -> dict[str, Any]:
    """
    List workflow runs with optional filters.

    Args:
        workflow: Filter by workflow name (optional)
        branch: Filter by branch (optional)
        status: Filter by status: queued, in_progress, completed (optional)
        limit: Maximum runs to return (default: 10)

    Returns:
        List of workflow runs with status, branch, duration
    """
    tool = CICDTool(os.getcwd())

    runs = await tool.get_runs(
        workflow=workflow or None,
        branch=branch or None,
        status=status or None,
        limit=limit,
    )

    return {
        "type": "cicd_runs",
        "count": len(runs),
        "runs": runs,
    }


async def cicd_run_details(run_id: int) -> dict[str, Any]:
    """
    Get detailed information about a workflow run.

    Shows jobs, steps, timing, and errors for failed runs.

    Args:
        run_id: Workflow run ID

    Returns:
        Run details including:
        - status and conclusion
        - jobs with step-by-step breakdown
        - errors (if failed)
        - duration and timing
    """
    tool = CICDTool(os.getcwd())
    return await tool.get_run_details(run_id)


async def cicd_logs(
    run_id: int,
    failed_only: bool = True,
) -> dict[str, Any]:
    """
    Get build logs from a workflow run.

    Extracts and categorizes errors and warnings.

    Args:
        run_id: Workflow run ID
        failed_only: Only return failed step logs (default: true)

    Returns:
        Parsed logs with:
        - error_count: Number of errors found
        - errors: Extracted error lines
        - warnings: Extracted warning lines
    """
    tool = CICDTool(os.getcwd())
    return await tool.get_logs(run_id, failed_only=failed_only)


async def cicd_trigger(
    workflow: str,
    branch: str = "",
    inputs: str = "",
) -> dict[str, Any]:
    """
    Trigger a workflow run via workflow_dispatch.

    Args:
        workflow: Workflow filename (e.g., "ci.yml") or ID
        branch: Branch to run on (default: main)
        inputs: JSON string of input parameters (optional)

    Returns:
        Success status and instructions to check run

    Example:
        cicd_trigger("deploy.yml", branch="main", inputs='{"environment": "staging"}')
    """
    tool = CICDTool(os.getcwd())

    # Parse inputs if provided
    parsed_inputs = None
    if inputs:
        import json
        try:
            parsed_inputs = json.loads(inputs)
        except json.JSONDecodeError:
            return {"error": "Invalid JSON in inputs parameter"}

    return await tool.trigger_workflow(
        workflow=workflow,
        branch=branch or None,
        inputs=parsed_inputs,
    )


async def cicd_cancel(run_id: int) -> dict[str, Any]:
    """
    Cancel a running workflow.

    Args:
        run_id: Workflow run ID to cancel

    Returns:
        Success status
    """
    tool = CICDTool(os.getcwd())
    return await tool.cancel_run(run_id)


async def cicd_rerun(
    run_id: int,
    failed_only: bool = True,
) -> dict[str, Any]:
    """
    Re-run a workflow.

    Args:
        run_id: Workflow run ID to re-run
        failed_only: Only re-run failed jobs (faster, default: true)

    Returns:
        Success status
    """
    tool = CICDTool(os.getcwd())
    return await tool.rerun(run_id, failed_only=failed_only)


async def cicd_diagnose(run_id: int) -> dict[str, Any]:
    """
    Diagnose why a workflow run failed.

    Analyzes logs, identifies error patterns, and suggests fixes.

    Args:
        run_id: Failed workflow run ID

    Returns:
        Diagnosis with:
        - failed_jobs: Which jobs failed
        - errors: Extracted error messages
        - suggestions: Actionable fix suggestions
    """
    tool = CICDTool(os.getcwd())
    return await tool.diagnose_failure(run_id)


async def cicd_health(
    workflow: str = "",
    days: int = 7,
) -> dict[str, Any]:
    """
    Get CI/CD health metrics.

    Analyzes success rate, duration trends, and identifies problems.

    Args:
        workflow: Filter to specific workflow (optional)
        days: Time period to analyze (default: 7)

    Returns:
        Health metrics:
        - success_rate: Percentage of successful runs
        - total_runs: Number of runs in period
        - avg_duration_seconds: Average run time
        - trend: improving, stable, or declining
    """
    tool = CICDTool(os.getcwd())
    return await tool.get_health(
        workflow=workflow or None,
        days=days,
    )


async def cicd_artifacts(run_id: int) -> dict[str, Any]:
    """
    List artifacts from a workflow run.

    Args:
        run_id: Workflow run ID

    Returns:
        List of artifacts with name, size, and download info
    """
    tool = CICDTool(os.getcwd())
    return await tool.list_artifacts(run_id)

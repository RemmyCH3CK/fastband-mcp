"""
CI/CD Integration Tools - Workflow management and build analysis.

Provides MCP tools for:
- Viewing workflow status and history
- Getting build logs and errors
- Triggering and managing workflow runs
- Health metrics and failure diagnosis

Currently supports GitHub Actions with extensibility for other providers.

Usage:
    # Get overall CI/CD status
    result = await cicd_status()
    print(result["markdown"])

    # List recent runs
    result = await cicd_runs(branch="main", limit=5)
    for run in result["runs"]:
        print(f"{run['workflow']}: {run['status']}")

    # Diagnose a failure
    result = await cicd_diagnose(run_id=12345)
    for suggestion in result["suggestions"]:
        print(f"- {suggestion}")

    # Trigger a workflow
    result = await cicd_trigger("deploy.yml", branch="main")
"""

from fastband.tools.cicd.github import GitHubActionsClient
from fastband.tools.cicd.models import (
    Artifact,
    BuildLog,
    CICDReport,
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
from fastband.tools.cicd.tool import (
    CICDConfig,
    CICDTool,
    cicd_artifacts,
    cicd_cancel,
    cicd_diagnose,
    cicd_health,
    cicd_logs,
    cicd_rerun,
    cicd_run_details,
    cicd_runs,
    cicd_status,
    cicd_trigger,
)

__all__ = [
    # Main tool
    "CICDTool",
    "CICDConfig",
    # Provider clients
    "GitHubActionsClient",
    # MCP functions
    "cicd_status",
    "cicd_runs",
    "cicd_run_details",
    "cicd_logs",
    "cicd_trigger",
    "cicd_cancel",
    "cicd_rerun",
    "cicd_diagnose",
    "cicd_health",
    "cicd_artifacts",
    # Models
    "CIProvider",
    "WorkflowStatus",
    "RunConclusion",
    "JobStatus",
    "WorkflowFile",
    "WorkflowRun",
    "Job",
    "Step",
    "BuildLog",
    "Artifact",
    "CIHealthMetrics",
    "CICDReport",
]


# =========================================================================
# MCP TOOL REGISTRATION
# =========================================================================

def register_tools(mcp_server):
    """Register CI/CD tools with the MCP server."""

    @mcp_server.tool()
    async def cicd_get_status(repo: str = "") -> dict:
        """
        Get CI/CD pipeline status overview.

        Returns current state of all workflows, recent runs,
        health metrics, and recommendations.

        Args:
            repo: Repository in owner/repo format (auto-detects if not provided)

        Returns:
            Complete CI/CD status report with:
            - workflows: List of workflow definitions
            - recent_runs: Recent workflow runs with status
            - health: Success rate, trends, duration stats
            - failing: Currently failing workflows
            - recommendations: Actionable suggestions
            - markdown: Formatted report

        Example:
            {"repo": "owner/repo"} or {} for auto-detect
        """
        return await cicd_status(repo=repo)

    @mcp_server.tool()
    async def cicd_list_runs(
        workflow: str = "",
        branch: str = "",
        status: str = "",
        limit: int = 10,
    ) -> dict:
        """
        List workflow runs with optional filters.

        Args:
            workflow: Filter by workflow name (optional)
            branch: Filter by branch name (optional)
            status: Filter by status: queued, in_progress, completed (optional)
            limit: Maximum runs to return (default: 10)

        Returns:
            List of workflow runs with status, branch, duration

        Example:
            {"branch": "main", "status": "completed", "limit": 5}
        """
        return await cicd_runs(
            workflow=workflow,
            branch=branch,
            status=status,
            limit=limit,
        )

    @mcp_server.tool()
    async def cicd_get_run(run_id: int) -> dict:
        """
        Get detailed information about a workflow run.

        Shows jobs, steps, timing, and errors for failed runs.

        Args:
            run_id: Workflow run ID (from cicd_list_runs)

        Returns:
            Run details including:
            - status and conclusion
            - jobs with step-by-step breakdown
            - errors (if failed)
            - duration and timing
            - html_url for viewing in browser

        Example:
            {"run_id": 12345678}
        """
        return await cicd_run_details(run_id)

    @mcp_server.tool()
    async def cicd_get_logs(
        run_id: int,
        failed_only: bool = True,
    ) -> dict:
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
            - job: Job name
            - step: Step name

        Example:
            {"run_id": 12345678, "failed_only": true}
        """
        return await cicd_logs(run_id, failed_only=failed_only)

    @mcp_server.tool()
    async def cicd_trigger_workflow(
        workflow: str,
        branch: str = "",
        inputs: str = "",
    ) -> dict:
        """
        Trigger a workflow run via workflow_dispatch.

        The workflow must have 'workflow_dispatch' as a trigger.

        Args:
            workflow: Workflow filename (e.g., "ci.yml" or "deploy.yml")
            branch: Branch to run on (default: main)
            inputs: JSON string of input parameters (optional)

        Returns:
            Success status and instructions to check run

        Example:
            {"workflow": "deploy.yml", "branch": "main"}
            {"workflow": "release.yml", "inputs": "{\\"version\\": \\"1.0.0\\"}"}
        """
        return await cicd_trigger(
            workflow=workflow,
            branch=branch,
            inputs=inputs,
        )

    @mcp_server.tool()
    async def cicd_cancel_run(run_id: int) -> dict:
        """
        Cancel a running workflow.

        Args:
            run_id: Workflow run ID to cancel

        Returns:
            Success status

        Example:
            {"run_id": 12345678}
        """
        return await cicd_cancel(run_id)

    @mcp_server.tool()
    async def cicd_rerun_workflow(
        run_id: int,
        failed_only: bool = True,
    ) -> dict:
        """
        Re-run a workflow.

        Args:
            run_id: Workflow run ID to re-run
            failed_only: Only re-run failed jobs (faster, default: true)

        Returns:
            Success status

        Example:
            {"run_id": 12345678, "failed_only": true}
        """
        return await cicd_rerun(run_id, failed_only=failed_only)

    @mcp_server.tool()
    async def cicd_diagnose_failure(run_id: int) -> dict:
        """
        Diagnose why a workflow run failed.

        Analyzes logs, identifies error patterns, and suggests fixes.
        Use this when a run fails to get actionable remediation steps.

        Args:
            run_id: Failed workflow run ID

        Returns:
            Diagnosis with:
            - failed_jobs: Which jobs failed
            - errors: Extracted error messages
            - suggestions: Actionable fix suggestions
            - job_details: Per-job failure information

        Example:
            {"run_id": 12345678}
        """
        return await cicd_diagnose(run_id)

    @mcp_server.tool()
    async def cicd_get_health(
        workflow: str = "",
        days: int = 7,
    ) -> dict:
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
            - flaky_jobs: Jobs with intermittent failures

        Example:
            {"days": 14} or {"workflow": "ci.yml", "days": 7}
        """
        return await cicd_health(workflow=workflow, days=days)

    @mcp_server.tool()
    async def cicd_list_artifacts(run_id: int) -> dict:
        """
        List artifacts from a workflow run.

        Args:
            run_id: Workflow run ID

        Returns:
            List of artifacts with name, size, and download info

        Example:
            {"run_id": 12345678}
        """
        return await cicd_artifacts(run_id)

    return [
        "cicd_get_status",
        "cicd_list_runs",
        "cicd_get_run",
        "cicd_get_logs",
        "cicd_trigger_workflow",
        "cicd_cancel_run",
        "cicd_rerun_workflow",
        "cicd_diagnose_failure",
        "cicd_get_health",
        "cicd_list_artifacts",
    ]

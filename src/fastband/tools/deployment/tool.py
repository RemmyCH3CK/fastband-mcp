"""
Deployment Tool - Unified deployment management across platforms.

Provides MCP tools for:
- Platform detection and configuration
- Deployment listing and inspection
- Health checking
- Rollback management
- DORA metrics
"""

import logging
import os
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from fastband.tools.deployment.models import (
    Deployment,
    DeploymentConfig,
    DeploymentDiff,
    DeploymentHealth,
    DeploymentMetrics,
    DeploymentPlatform,
    DeploymentStatus,
    EnvironmentType,
    RollbackInfo,
)
from fastband.tools.deployment.platforms import (
    PlatformClient,
    check_deployment_health,
    detect_platform,
    get_platform_client,
)

logger = logging.getLogger(__name__)


class DeploymentTool:
    """
    Unified deployment tool for managing deployments across platforms.

    Auto-detects Vercel, Netlify, Railway, Fly.io, and other platforms.
    """

    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self._client: PlatformClient | None = None

    @property
    def client(self) -> PlatformClient | None:
        """Get or create the platform client."""
        if self._client is None:
            self._client = detect_platform(str(self.project_root))
        return self._client

    # =========================================================================
    # PLATFORM DETECTION
    # =========================================================================

    async def detect_platform(self) -> dict[str, Any]:
        """
        Detect the deployment platform for this project.

        Returns:
            Platform info with configuration
        """
        if not self.client:
            return {
                "detected": False,
                "platform": None,
                "message": "No deployment platform detected",
                "suggestions": [
                    "Add vercel.json for Vercel",
                    "Add netlify.toml for Netlify",
                    "Add fly.toml for Fly.io",
                    "Add Dockerfile for container deployments",
                ],
            }

        config = self.client.get_config()

        return {
            "detected": True,
            "platform": self.client.platform.value,
            "config": config.to_dict() if config else None,
        }

    # =========================================================================
    # DEPLOYMENT MANAGEMENT
    # =========================================================================

    async def list_deployments(
        self,
        limit: int = 10,
        environment: str = "",
    ) -> dict[str, Any]:
        """
        List recent deployments.

        Args:
            limit: Maximum number to return
            environment: Filter by environment (production, preview)

        Returns:
            List of deployments with status
        """
        if not self.client:
            return {"error": "No deployment platform detected"}

        deployments = self.client.list_deployments(limit=limit)

        if environment:
            env_type = EnvironmentType(environment.lower())
            deployments = [d for d in deployments if d.environment == env_type]

        return {
            "platform": self.client.platform.value,
            "count": len(deployments),
            "deployments": [d.to_dict() for d in deployments],
        }

    async def get_deployment(self, deployment_id: str) -> dict[str, Any]:
        """
        Get detailed information about a specific deployment.

        Args:
            deployment_id: The deployment ID

        Returns:
            Deployment details
        """
        if not self.client:
            return {"error": "No deployment platform detected"}

        deployment = self.client.get_deployment(deployment_id)

        if not deployment:
            return {"error": f"Deployment {deployment_id} not found"}

        return {
            "platform": self.client.platform.value,
            **deployment.to_dict(),
        }

    async def get_latest(self, environment: str = "production") -> dict[str, Any]:
        """
        Get the latest deployment for an environment.

        Args:
            environment: Environment type (production, preview, staging)

        Returns:
            Latest deployment info
        """
        if not self.client:
            return {"error": "No deployment platform detected"}

        env_type = EnvironmentType(environment.lower())
        deployment = self.client.get_latest_deployment(env_type)

        if not deployment:
            return {"error": f"No {environment} deployment found"}

        # Also check health
        health = check_deployment_health(deployment.url) if deployment.url else None

        result = {
            "platform": self.client.platform.value,
            **deployment.to_dict(),
        }

        if health:
            result["health"] = health.to_dict()

        return result

    async def get_status(self) -> dict[str, Any]:
        """
        Get deployment status overview for all environments.

        Returns:
            Status of production and preview deployments
        """
        if not self.client:
            return {"error": "No deployment platform detected"}

        prod = self.client.get_latest_deployment(EnvironmentType.PRODUCTION)
        preview = self.client.get_latest_deployment(EnvironmentType.PREVIEW)

        result = {
            "platform": self.client.platform.value,
            "environments": {},
        }

        if prod:
            prod_health = check_deployment_health(prod.url) if prod.url else None
            result["environments"]["production"] = {
                **prod.to_dict(),
                "healthy": prod_health.is_healthy if prod_health else None,
            }

        if preview:
            result["environments"]["preview"] = preview.to_dict()

        return result

    # =========================================================================
    # HEALTH CHECKING
    # =========================================================================

    async def check_health(self, url: str = "") -> dict[str, Any]:
        """
        Check health of a deployment URL.

        Args:
            url: URL to check. If empty, checks latest production deployment.

        Returns:
            Health status including response time and SSL info
        """
        if not url:
            if not self.client:
                return {"error": "No deployment platform detected"}

            prod = self.client.get_latest_deployment(EnvironmentType.PRODUCTION)
            if not prod or not prod.url:
                return {"error": "No production deployment URL available"}
            url = prod.url

        health = check_deployment_health(url)
        return health.to_dict()

    # =========================================================================
    # BUILD LOGS
    # =========================================================================

    async def get_logs(self, deployment_id: str = "", lines: int = 100) -> dict[str, Any]:
        """
        Get build logs for a deployment.

        Args:
            deployment_id: Deployment ID. If empty, uses latest.
            lines: Maximum lines to return

        Returns:
            Build log lines
        """
        if not self.client:
            return {"error": "No deployment platform detected"}

        if not deployment_id:
            latest = self.client.get_latest_deployment()
            if not latest:
                return {"error": "No deployments found"}
            deployment_id = latest.id

        logs = self.client.get_build_logs(deployment_id)

        return {
            "deployment_id": deployment_id,
            "line_count": len(logs),
            "logs": logs[-lines:] if len(logs) > lines else logs,
        }

    # =========================================================================
    # DEPLOYMENT COMPARISON
    # =========================================================================

    async def compare_deployments(
        self,
        from_id: str,
        to_id: str,
    ) -> dict[str, Any]:
        """
        Compare two deployments to see what changed.

        Args:
            from_id: Earlier deployment ID
            to_id: Later deployment ID

        Returns:
            Differences between deployments
        """
        if not self.client:
            return {"error": "No deployment platform detected"}

        from_deploy = self.client.get_deployment(from_id)
        to_deploy = self.client.get_deployment(to_id)

        if not from_deploy:
            return {"error": f"Deployment {from_id} not found"}
        if not to_deploy:
            return {"error": f"Deployment {to_id} not found"}

        diff = DeploymentDiff(
            from_deployment=from_deploy,
            to_deployment=to_deploy,
        )

        # Get commits between deployments using git
        if from_deploy.commit_sha and to_deploy.commit_sha:
            try:
                result = subprocess.run(
                    [
                        "git", "log",
                        "--pretty=format:%H|%an|%s",
                        f"{from_deploy.commit_sha}..{to_deploy.commit_sha}",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    cwd=self.project_root,
                )

                if result.returncode == 0:
                    for line in result.stdout.strip().split("\n"):
                        if line:
                            parts = line.split("|", 2)
                            if len(parts) >= 3:
                                diff.commits.append({
                                    "sha": parts[0][:8],
                                    "author": parts[1],
                                    "message": parts[2][:80],
                                })

                # Get files changed
                files_result = subprocess.run(
                    [
                        "git", "diff",
                        "--name-status",
                        f"{from_deploy.commit_sha}..{to_deploy.commit_sha}",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    cwd=self.project_root,
                )

                if files_result.returncode == 0:
                    for line in files_result.stdout.strip().split("\n"):
                        if line:
                            parts = line.split("\t")
                            if len(parts) >= 2:
                                status, file = parts[0], parts[-1]
                                if status == "A":
                                    diff.files_added.append(file)
                                elif status == "M":
                                    diff.files_modified.append(file)
                                elif status == "D":
                                    diff.files_deleted.append(file)

            except Exception as e:
                logger.debug(f"Git comparison failed: {e}")

        return diff.to_dict()

    # =========================================================================
    # METRICS
    # =========================================================================

    async def get_metrics(self, days: int = 30) -> dict[str, Any]:
        """
        Get deployment metrics and DORA statistics.

        Args:
            days: Number of days to analyze

        Returns:
            Deployment metrics including DORA metrics
        """
        if not self.client:
            return {"error": "No deployment platform detected"}

        # Get all deployments in the period
        deployments = self.client.list_deployments(limit=100)

        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        deployments = [d for d in deployments if d.created_at >= cutoff]

        metrics = DeploymentMetrics(period_days=days)
        metrics.total_deployments = len(deployments)
        metrics.successful_deployments = len([d for d in deployments if d.is_ready])
        metrics.failed_deployments = len([d for d in deployments if d.is_failed])

        # Count by environment
        metrics.production_deploys = len([
            d for d in deployments if d.environment == EnvironmentType.PRODUCTION
        ])
        metrics.preview_deploys = len([
            d for d in deployments if d.environment == EnvironmentType.PREVIEW
        ])

        # Calculate averages
        build_times = [d.build_duration_seconds for d in deployments if d.build_duration_seconds > 0]
        if build_times:
            metrics.avg_build_time_s = sum(build_times) / len(build_times)

        # Deploys per day
        if days > 0:
            metrics.deploys_per_day = metrics.total_deployments / days

        # Change failure rate (simplified)
        if metrics.total_deployments > 0:
            metrics.change_failure_rate = (metrics.failed_deployments / metrics.total_deployments) * 100

        return {
            "platform": self.client.platform.value,
            **metrics.to_dict(),
        }


# =============================================================================
# MCP-FACING FUNCTIONS
# =============================================================================

async def deploy_detect(path: str = "") -> dict[str, Any]:
    """
    Detect the deployment platform for a project.

    Args:
        path: Project path (defaults to current directory)

    Returns:
        Detected platform and configuration
    """
    project_path = path or os.getcwd()
    tool = DeploymentTool(project_path)
    return await tool.detect_platform()


async def deploy_list(
    limit: int = 10,
    environment: str = "",
    path: str = "",
) -> dict[str, Any]:
    """
    List recent deployments.

    Args:
        limit: Maximum number to return
        environment: Filter by environment (production, preview)
        path: Project path

    Returns:
        List of deployments
    """
    project_path = path or os.getcwd()
    tool = DeploymentTool(project_path)
    return await tool.list_deployments(limit=limit, environment=environment)


async def deploy_get(deployment_id: str, path: str = "") -> dict[str, Any]:
    """
    Get details for a specific deployment.

    Args:
        deployment_id: The deployment ID
        path: Project path

    Returns:
        Deployment details
    """
    project_path = path or os.getcwd()
    tool = DeploymentTool(project_path)
    return await tool.get_deployment(deployment_id)


async def deploy_latest(environment: str = "production", path: str = "") -> dict[str, Any]:
    """
    Get the latest deployment for an environment.

    Args:
        environment: Environment type (production, preview, staging)
        path: Project path

    Returns:
        Latest deployment with health status
    """
    project_path = path or os.getcwd()
    tool = DeploymentTool(project_path)
    return await tool.get_latest(environment=environment)


async def deploy_status(path: str = "") -> dict[str, Any]:
    """
    Get deployment status overview.

    Args:
        path: Project path

    Returns:
        Status of all environments
    """
    project_path = path or os.getcwd()
    tool = DeploymentTool(project_path)
    return await tool.get_status()


async def deploy_health(url: str = "", path: str = "") -> dict[str, Any]:
    """
    Check health of a deployment.

    Args:
        url: URL to check (uses production URL if empty)
        path: Project path

    Returns:
        Health status with response time and SSL info
    """
    project_path = path or os.getcwd()
    tool = DeploymentTool(project_path)
    return await tool.check_health(url=url)


async def deploy_logs(
    deployment_id: str = "",
    lines: int = 100,
    path: str = "",
) -> dict[str, Any]:
    """
    Get build logs for a deployment.

    Args:
        deployment_id: Deployment ID (uses latest if empty)
        lines: Maximum lines to return
        path: Project path

    Returns:
        Build log lines
    """
    project_path = path or os.getcwd()
    tool = DeploymentTool(project_path)
    return await tool.get_logs(deployment_id=deployment_id, lines=lines)


async def deploy_compare(
    from_id: str,
    to_id: str,
    path: str = "",
) -> dict[str, Any]:
    """
    Compare two deployments.

    Args:
        from_id: Earlier deployment ID
        to_id: Later deployment ID
        path: Project path

    Returns:
        Differences including commits, files, and env changes
    """
    project_path = path or os.getcwd()
    tool = DeploymentTool(project_path)
    return await tool.compare_deployments(from_id=from_id, to_id=to_id)


async def deploy_metrics(days: int = 30, path: str = "") -> dict[str, Any]:
    """
    Get deployment metrics and DORA statistics.

    Args:
        days: Number of days to analyze
        path: Project path

    Returns:
        Deployment metrics including DORA metrics
    """
    project_path = path or os.getcwd()
    tool = DeploymentTool(project_path)
    return await tool.get_metrics(days=days)

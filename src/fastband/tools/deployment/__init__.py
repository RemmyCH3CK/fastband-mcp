"""
Deployment Tools - Unified deployment management across platforms.

Provides MCP tools for:
- Platform auto-detection (Vercel, Netlify, Railway, Fly.io)
- Deployment listing and inspection
- Health monitoring with SSL checks
- Deployment comparison
- DORA metrics calculation

Usage:
    # Detect platform
    result = await deploy_detect()
    print(f"Platform: {result['platform']}")

    # List deployments
    result = await deploy_list(limit=5)
    for d in result["deployments"]:
        print(f"{d['id']}: {d['status']} - {d['url']}")

    # Check health
    result = await deploy_health()
    print(f"Healthy: {result['healthy']}")

    # Get DORA metrics
    result = await deploy_metrics(days=30)
    print(f"Success rate: {result['success_rate']}")
"""

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
    NetlifyClient,
    PlatformClient,
    VercelClient,
    check_deployment_health,
    detect_platform,
    get_platform_client,
)
from fastband.tools.deployment.tool import (
    DeploymentTool,
    deploy_compare,
    deploy_detect,
    deploy_get,
    deploy_health,
    deploy_latest,
    deploy_list,
    deploy_logs,
    deploy_metrics,
    deploy_status,
)

__all__ = [
    # Main tool
    "DeploymentTool",
    # Platform clients
    "PlatformClient",
    "VercelClient",
    "NetlifyClient",
    "detect_platform",
    "get_platform_client",
    "check_deployment_health",
    # MCP functions
    "deploy_detect",
    "deploy_list",
    "deploy_get",
    "deploy_latest",
    "deploy_status",
    "deploy_health",
    "deploy_logs",
    "deploy_compare",
    "deploy_metrics",
    # Models
    "DeploymentPlatform",
    "DeploymentStatus",
    "EnvironmentType",
    "DeploymentConfig",
    "Deployment",
    "DeploymentHealth",
    "DeploymentDiff",
    "DeploymentMetrics",
    "RollbackInfo",
]


# =========================================================================
# MCP TOOL REGISTRATION
# =========================================================================

def register_tools(mcp_server):
    """Register deployment tools with the MCP server."""

    @mcp_server.tool()
    async def deploy_detect_platform(path: str = "") -> dict:
        """
        Detect the deployment platform for a project.

        Auto-detects Vercel, Netlify, Railway, Fly.io based on
        configuration files in the project.

        Args:
            path: Project path (defaults to current directory)

        Returns:
            Detected platform with configuration:
            - detected: Whether a platform was found
            - platform: Platform name (vercel, netlify, etc.)
            - config: Platform-specific configuration

        Example:
            {} or {"path": "/path/to/project"}
        """
        return await deploy_detect(path=path)

    @mcp_server.tool()
    async def deploy_list_deployments(
        limit: int = 10,
        environment: str = "",
        path: str = "",
    ) -> dict:
        """
        List recent deployments.

        Shows deployments across environments with status and URLs.

        Args:
            limit: Maximum number to return (default: 10)
            environment: Filter by environment (production, preview)
            path: Project path

        Returns:
            List of deployments with:
            - id: Deployment ID
            - status: Current status
            - url: Deployment URL
            - branch: Git branch
            - environment: Environment type

        Example:
            {} or {"environment": "production", "limit": 5}
        """
        return await deploy_list(limit=limit, environment=environment, path=path)

    @mcp_server.tool()
    async def deploy_get_deployment(deployment_id: str, path: str = "") -> dict:
        """
        Get details for a specific deployment.

        Args:
            deployment_id: The deployment ID
            path: Project path

        Returns:
            Full deployment details including build info

        Example:
            {"deployment_id": "dpl_abc123"}
        """
        return await deploy_get(deployment_id=deployment_id, path=path)

    @mcp_server.tool()
    async def deploy_get_latest(environment: str = "production", path: str = "") -> dict:
        """
        Get the latest deployment for an environment.

        Also includes health check results.

        Args:
            environment: Environment type (production, preview, staging)
            path: Project path

        Returns:
            Latest deployment with health status

        Example:
            {} or {"environment": "preview"}
        """
        return await deploy_latest(environment=environment, path=path)

    @mcp_server.tool()
    async def deploy_get_status(path: str = "") -> dict:
        """
        Get deployment status overview.

        Shows current status of production and preview environments.

        Args:
            path: Project path

        Returns:
            Status of all environments with health info

        Example:
            {}
        """
        return await deploy_status(path=path)

    @mcp_server.tool()
    async def deploy_check_health(url: str = "", path: str = "") -> dict:
        """
        Check health of a deployment.

        Verifies URL is reachable, measures response time,
        and checks SSL certificate validity.

        Args:
            url: URL to check (uses production URL if empty)
            path: Project path

        Returns:
            Health status:
            - healthy: Overall health status
            - reachable: If URL responds
            - response_time_ms: Response time
            - ssl_valid: SSL certificate status
            - ssl_days_remaining: Days until SSL expiry

        Example:
            {} or {"url": "https://myapp.vercel.app"}
        """
        return await deploy_health(url=url, path=path)

    @mcp_server.tool()
    async def deploy_get_logs(
        deployment_id: str = "",
        lines: int = 100,
        path: str = "",
    ) -> dict:
        """
        Get build logs for a deployment.

        Args:
            deployment_id: Deployment ID (uses latest if empty)
            lines: Maximum lines to return (default: 100)
            path: Project path

        Returns:
            Build log lines

        Example:
            {} or {"deployment_id": "dpl_abc123", "lines": 50}
        """
        return await deploy_logs(deployment_id=deployment_id, lines=lines, path=path)

    @mcp_server.tool()
    async def deploy_compare_deployments(
        from_id: str,
        to_id: str,
        path: str = "",
    ) -> dict:
        """
        Compare two deployments to see what changed.

        Shows commits, file changes, and potential breaking changes
        between deployments.

        Args:
            from_id: Earlier deployment ID
            to_id: Later deployment ID
            path: Project path

        Returns:
            Differences:
            - commits: Commits between deployments
            - files: Added, modified, deleted files
            - has_breaking_changes: If breaking changes detected

        Example:
            {"from_id": "dpl_old123", "to_id": "dpl_new456"}
        """
        return await deploy_compare(from_id=from_id, to_id=to_id, path=path)

    @mcp_server.tool()
    async def deploy_get_metrics(days: int = 30, path: str = "") -> dict:
        """
        Get deployment metrics and DORA statistics.

        Calculates key DevOps metrics:
        - Deployment frequency
        - Success rate
        - Change failure rate
        - Lead time (commit to production)

        Args:
            days: Number of days to analyze (default: 30)
            path: Project path

        Returns:
            Deployment metrics:
            - total: Total deployments
            - success_rate: Percentage successful
            - deploys_per_day: Average daily deployments
            - dora_metrics: DORA performance indicators

        Example:
            {} or {"days": 7}
        """
        return await deploy_metrics(days=days, path=path)

    return [
        "deploy_detect_platform",
        "deploy_list_deployments",
        "deploy_get_deployment",
        "deploy_get_latest",
        "deploy_get_status",
        "deploy_check_health",
        "deploy_get_logs",
        "deploy_compare_deployments",
        "deploy_get_metrics",
    ]

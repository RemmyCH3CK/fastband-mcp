"""
Dependencies Tools - Unified dependency management across ecosystems.

Provides MCP tools for:
- Multi-ecosystem support (npm, pip, cargo, go)
- Dependency listing and analysis
- Outdated package detection
- Vulnerability scanning
- License compliance
- Update recommendations

Usage:
    # List dependencies
    result = await deps_list()
    for dep in result["dependencies"]:
        print(f"{dep['name']}: {dep['version']}")

    # Check for outdated
    result = await deps_outdated()
    print(f"Outdated: {result['outdated_count']}")

    # Security audit
    result = await deps_audit()
    print(f"Vulnerabilities: {result['vulnerability_count']}")

    # Get health score
    result = await deps_health()
    print(f"Health: {result['health_score']} (Grade: {result['grade']})")
"""

from fastband.tools.dependencies.models import (
    Dependency,
    DependencyHealth,
    DependencyTree,
    DependencyType,
    LicenseInfo,
    PackageManager,
    UpdateRecommendation,
    UpdateType,
    Vulnerability,
    VulnerabilitySeverity,
)
from fastband.tools.dependencies.parsers import (
    detect_package_manager,
    get_npm_audit,
    get_npm_outdated,
    get_pip_audit,
    get_pip_outdated,
    parse_package_json,
    parse_pyproject_toml,
    parse_requirements_txt,
)
from fastband.tools.dependencies.tool import (
    DependenciesTool,
    deps_audit,
    deps_health,
    deps_licenses,
    deps_list,
    deps_outdated,
    deps_updates,
)

__all__ = [
    # Main tool
    "DependenciesTool",
    # Parsers
    "detect_package_manager",
    "parse_package_json",
    "parse_requirements_txt",
    "parse_pyproject_toml",
    "get_npm_outdated",
    "get_pip_outdated",
    "get_npm_audit",
    "get_pip_audit",
    # MCP functions
    "deps_list",
    "deps_outdated",
    "deps_audit",
    "deps_licenses",
    "deps_health",
    "deps_updates",
    # Models
    "PackageManager",
    "DependencyType",
    "UpdateType",
    "VulnerabilitySeverity",
    "Dependency",
    "Vulnerability",
    "LicenseInfo",
    "DependencyTree",
    "DependencyHealth",
    "UpdateRecommendation",
]


# =========================================================================
# MCP TOOL REGISTRATION
# =========================================================================

def register_tools(mcp_server):
    """Register dependency tools with the MCP server."""

    @mcp_server.tool()
    async def deps_list_all(
        include_dev: bool = True,
        path: str = "",
    ) -> dict:
        """
        List all dependencies in the project.

        Auto-detects package manager (npm, pip, etc.) and lists
        all production and development dependencies.

        Args:
            include_dev: Include development dependencies (default: true)
            path: Project path (defaults to current directory)

        Returns:
            Dependencies with:
            - package_manager: Detected package manager
            - count: Total dependencies
            - dependencies: List of packages with versions

        Example:
            {} or {"include_dev": false}
        """
        return await deps_list(include_dev=include_dev, path=path)

    @mcp_server.tool()
    async def deps_check_outdated(path: str = "") -> dict:
        """
        Check for outdated dependencies.

        Shows packages with available updates and categorizes
        them by update type (major, minor, patch).

        Args:
            path: Project path

        Returns:
            Outdated packages with:
            - outdated_count: Number of outdated packages
            - major_updates: Breaking changes available
            - minor_updates: Feature updates available
            - patch_updates: Bug fixes available

        Example:
            {}
        """
        return await deps_outdated(path=path)

    @mcp_server.tool()
    async def deps_security_audit(path: str = "") -> dict:
        """
        Run security audit on dependencies.

        Scans for known vulnerabilities (CVEs) in dependencies.

        Args:
            path: Project path

        Returns:
            Vulnerabilities found:
            - vulnerability_count: Total vulnerabilities
            - critical/high/medium/low: By severity
            - vulnerabilities: Details with fix info

        Example:
            {}
        """
        return await deps_audit(path=path)

    @mcp_server.tool()
    async def deps_analyze_licenses(path: str = "") -> dict:
        """
        Analyze dependency licenses.

        Checks for license compliance issues including
        copyleft and restrictive licenses.

        Args:
            path: Project path

        Returns:
            License analysis:
            - permissive: Count of permissive licenses
            - copyleft: Count of copyleft licenses
            - high_risk: Packages with problematic licenses

        Example:
            {}
        """
        return await deps_licenses(path=path)

    @mcp_server.tool()
    async def deps_get_health(path: str = "") -> dict:
        """
        Get overall dependency health score.

        Combines security, freshness, and license metrics
        into a single health score (0-100).

        Args:
            path: Project path

        Returns:
            Health metrics:
            - health_score: Overall score (0-100)
            - grade: Letter grade (A-F)
            - updates: Outdated package counts
            - security: Vulnerability counts

        Example:
            {}
        """
        return await deps_health(path=path)

    @mcp_server.tool()
    async def deps_recommend_updates(
        security_only: bool = False,
        path: str = "",
    ) -> dict:
        """
        Get prioritized update recommendations.

        Provides a prioritized list of dependency updates,
        with security fixes first.

        Args:
            security_only: Only recommend security updates
            path: Project path

        Returns:
            Update recommendations:
            - security_updates: Security-related updates
            - breaking_updates: Updates with breaking changes
            - recommendations: Prioritized update list

        Example:
            {} or {"security_only": true}
        """
        return await deps_updates(security_only=security_only, path=path)

    return [
        "deps_list_all",
        "deps_check_outdated",
        "deps_security_audit",
        "deps_analyze_licenses",
        "deps_get_health",
        "deps_recommend_updates",
    ]

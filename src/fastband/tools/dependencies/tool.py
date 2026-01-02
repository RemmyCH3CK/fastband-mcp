"""
Dependencies Tool - Unified dependency management across ecosystems.

Provides MCP tools for:
- Dependency listing and analysis
- Outdated package detection
- Vulnerability scanning
- License compliance
- Update recommendations
"""

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastband.tools.dependencies.models import (
    Dependency,
    DependencyHealth,
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

logger = logging.getLogger(__name__)


# License classifications
LICENSE_CLASSIFICATIONS = {
    # Permissive - low risk
    "MIT": {"permissive": True, "copyleft": False, "risk": "low"},
    "Apache-2.0": {"permissive": True, "copyleft": False, "risk": "low"},
    "BSD-2-Clause": {"permissive": True, "copyleft": False, "risk": "low"},
    "BSD-3-Clause": {"permissive": True, "copyleft": False, "risk": "low"},
    "ISC": {"permissive": True, "copyleft": False, "risk": "low"},
    "0BSD": {"permissive": True, "copyleft": False, "risk": "low"},
    "Unlicense": {"permissive": True, "copyleft": False, "risk": "low"},
    "CC0-1.0": {"permissive": True, "copyleft": False, "risk": "low"},

    # Weak copyleft - medium risk
    "LGPL-2.1": {"permissive": False, "copyleft": True, "risk": "medium"},
    "LGPL-3.0": {"permissive": False, "copyleft": True, "risk": "medium"},
    "MPL-2.0": {"permissive": False, "copyleft": True, "risk": "medium"},
    "EPL-1.0": {"permissive": False, "copyleft": True, "risk": "medium"},
    "EPL-2.0": {"permissive": False, "copyleft": True, "risk": "medium"},

    # Strong copyleft - high risk
    "GPL-2.0": {"permissive": False, "copyleft": True, "risk": "high"},
    "GPL-3.0": {"permissive": False, "copyleft": True, "risk": "high"},
    "AGPL-3.0": {"permissive": False, "copyleft": True, "risk": "high"},

    # Restrictive - high risk
    "SSPL-1.0": {"permissive": False, "copyleft": False, "risk": "high"},
    "BSL-1.1": {"permissive": False, "copyleft": False, "risk": "high"},
    "Elastic-2.0": {"permissive": False, "copyleft": False, "risk": "high"},
}


class DependenciesTool:
    """
    Unified dependency management tool.

    Supports npm, pip, poetry, cargo, and go modules.
    """

    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self._package_manager: PackageManager | None = None

    @property
    def package_manager(self) -> PackageManager:
        """Detect or return cached package manager."""
        if self._package_manager is None:
            self._package_manager = detect_package_manager(str(self.project_root))
        return self._package_manager

    # =========================================================================
    # DEPENDENCY LISTING
    # =========================================================================

    async def list_dependencies(self, include_dev: bool = True) -> list[Dependency]:
        """
        List all dependencies in the project.

        Args:
            include_dev: Include development dependencies

        Returns:
            List of dependencies
        """
        pm = self.package_manager

        if pm in (PackageManager.NPM, PackageManager.YARN, PackageManager.PNPM):
            deps = parse_package_json(self.project_root / "package.json")
        elif pm in (PackageManager.PIP, PackageManager.POETRY, PackageManager.UV):
            deps = []
            # Try pyproject.toml first
            pyproject = self.project_root / "pyproject.toml"
            if pyproject.exists():
                deps = parse_pyproject_toml(pyproject)

            # Also check requirements.txt
            requirements = self.project_root / "requirements.txt"
            if requirements.exists():
                deps.extend(parse_requirements_txt(requirements))

            # Dev requirements
            dev_req = self.project_root / "requirements-dev.txt"
            if dev_req.exists():
                for dep in parse_requirements_txt(dev_req):
                    dep.dep_type = DependencyType.DEVELOPMENT
                    deps.append(dep)
        else:
            deps = []

        if not include_dev:
            deps = [d for d in deps if d.dep_type == DependencyType.PRODUCTION]

        return deps

    # =========================================================================
    # OUTDATED DETECTION
    # =========================================================================

    async def get_outdated(self) -> list[Dependency]:
        """
        Get list of outdated dependencies.

        Returns:
            List of dependencies with available updates
        """
        pm = self.package_manager

        if pm in (PackageManager.NPM, PackageManager.YARN, PackageManager.PNPM):
            return get_npm_outdated(str(self.project_root))
        elif pm in (PackageManager.PIP, PackageManager.POETRY, PackageManager.UV):
            return get_pip_outdated(str(self.project_root))
        else:
            return []

    # =========================================================================
    # VULNERABILITY SCANNING
    # =========================================================================

    async def audit(self) -> list[Vulnerability]:
        """
        Run security audit on dependencies.

        Returns:
            List of vulnerabilities found
        """
        pm = self.package_manager

        if pm in (PackageManager.NPM, PackageManager.YARN, PackageManager.PNPM):
            return get_npm_audit(str(self.project_root))
        elif pm in (PackageManager.PIP, PackageManager.POETRY, PackageManager.UV):
            return get_pip_audit(str(self.project_root))
        else:
            return []

    # =========================================================================
    # LICENSE ANALYSIS
    # =========================================================================

    async def analyze_licenses(self) -> list[LicenseInfo]:
        """
        Analyze licenses of all dependencies.

        Returns:
            List of license information for each dependency
        """
        deps = await self.list_dependencies()
        licenses = []

        for dep in deps:
            license_id = dep.license_spdx or dep.license or "UNKNOWN"
            classification = LICENSE_CLASSIFICATIONS.get(license_id, {
                "permissive": False,
                "copyleft": False,
                "risk": "unknown",
            })

            licenses.append(LicenseInfo(
                package=dep.name,
                license_id=license_id,
                is_permissive=classification.get("permissive", False),
                is_copyleft=classification.get("copyleft", False),
                risk_level=classification.get("risk", "unknown"),
                commercial_ok=not classification.get("copyleft", False),
            ))

        return licenses

    # =========================================================================
    # HEALTH ANALYSIS
    # =========================================================================

    async def get_health(self) -> DependencyHealth:
        """
        Get overall dependency health metrics.

        Returns:
            DependencyHealth with scores and metrics
        """
        deps = await self.list_dependencies()
        outdated = await self.get_outdated()
        vulns = await self.audit()

        health = DependencyHealth(
            package_manager=self.package_manager,
            total_dependencies=len(deps),
            direct_dependencies=len([d for d in deps if d.is_direct]),
            dev_dependencies=len([d for d in deps if d.dep_type == DependencyType.DEVELOPMENT]),
        )

        # Update stats
        health.outdated_count = len(outdated)
        health.major_updates = len([d for d in outdated if d.update_type == UpdateType.MAJOR])
        health.minor_updates = len([d for d in outdated if d.update_type == UpdateType.MINOR])
        health.patch_updates = len([d for d in outdated if d.update_type == UpdateType.PATCH])

        # Vulnerability stats
        health.vulnerabilities_critical = len([v for v in vulns if v.severity == VulnerabilitySeverity.CRITICAL])
        health.vulnerabilities_high = len([v for v in vulns if v.severity == VulnerabilitySeverity.HIGH])
        health.vulnerabilities_medium = len([v for v in vulns if v.severity == VulnerabilitySeverity.MEDIUM])
        health.vulnerabilities_low = len([v for v in vulns if v.severity == VulnerabilitySeverity.LOW])

        return health

    # =========================================================================
    # UPDATE RECOMMENDATIONS
    # =========================================================================

    async def get_update_recommendations(self, security_only: bool = False) -> list[UpdateRecommendation]:
        """
        Get prioritized update recommendations.

        Args:
            security_only: Only recommend security updates

        Returns:
            Prioritized list of update recommendations
        """
        outdated = await self.get_outdated()
        vulns = await self.audit()

        # Create set of packages with vulnerabilities
        vuln_packages = {v.package for v in vulns}

        recommendations = []

        for dep in outdated:
            # Skip if security_only and no vulnerability
            if security_only and dep.name not in vuln_packages:
                continue

            # Determine reason
            if dep.name in vuln_packages:
                reason = "security fix"
            elif dep.update_type == UpdateType.MAJOR:
                reason = "major update"
            elif dep.update_type == UpdateType.MINOR:
                reason = "feature update"
            else:
                reason = "bug fixes"

            recommendations.append(UpdateRecommendation(
                package=dep.name,
                current_version=dep.version,
                recommended_version=dep.latest_version,
                update_type=dep.update_type or UpdateType.PATCH,
                breaking_changes=dep.update_type == UpdateType.MAJOR,
                reason=reason,
            ))

        # Sort: security first, then by update type
        recommendations.sort(
            key=lambda r: (
                0 if r.reason == "security fix" else 1,
                0 if r.update_type == UpdateType.PATCH else
                1 if r.update_type == UpdateType.MINOR else 2,
            )
        )

        return recommendations


# =============================================================================
# MCP-FACING FUNCTIONS
# =============================================================================

async def deps_list(
    include_dev: bool = True,
    path: str = "",
) -> dict[str, Any]:
    """
    List all dependencies in the project.

    Args:
        include_dev: Include development dependencies
        path: Project path

    Returns:
        List of dependencies with versions
    """
    project_path = path or os.getcwd()
    tool = DependenciesTool(project_path)

    deps = await tool.list_dependencies(include_dev=include_dev)

    return {
        "package_manager": tool.package_manager.value,
        "count": len(deps),
        "production": len([d for d in deps if d.dep_type == DependencyType.PRODUCTION]),
        "development": len([d for d in deps if d.dep_type == DependencyType.DEVELOPMENT]),
        "dependencies": [d.to_dict() for d in deps],
    }


async def deps_outdated(path: str = "") -> dict[str, Any]:
    """
    Get outdated dependencies.

    Args:
        path: Project path

    Returns:
        List of outdated packages with available updates
    """
    project_path = path or os.getcwd()
    tool = DependenciesTool(project_path)

    outdated = await tool.get_outdated()

    return {
        "package_manager": tool.package_manager.value,
        "outdated_count": len(outdated),
        "major_updates": len([d for d in outdated if d.update_type == UpdateType.MAJOR]),
        "minor_updates": len([d for d in outdated if d.update_type == UpdateType.MINOR]),
        "patch_updates": len([d for d in outdated if d.update_type == UpdateType.PATCH]),
        "packages": [d.to_dict() for d in outdated],
    }


async def deps_audit(path: str = "") -> dict[str, Any]:
    """
    Run security audit on dependencies.

    Args:
        path: Project path

    Returns:
        Security vulnerabilities found
    """
    project_path = path or os.getcwd()
    tool = DependenciesTool(project_path)

    vulns = await tool.audit()

    return {
        "package_manager": tool.package_manager.value,
        "vulnerability_count": len(vulns),
        "critical": len([v for v in vulns if v.severity == VulnerabilitySeverity.CRITICAL]),
        "high": len([v for v in vulns if v.severity == VulnerabilitySeverity.HIGH]),
        "medium": len([v for v in vulns if v.severity == VulnerabilitySeverity.MEDIUM]),
        "low": len([v for v in vulns if v.severity == VulnerabilitySeverity.LOW]),
        "vulnerabilities": [v.to_dict() for v in vulns],
    }


async def deps_licenses(path: str = "") -> dict[str, Any]:
    """
    Analyze dependency licenses.

    Args:
        path: Project path

    Returns:
        License analysis with risk assessment
    """
    project_path = path or os.getcwd()
    tool = DependenciesTool(project_path)

    licenses = await tool.analyze_licenses()

    return {
        "package_manager": tool.package_manager.value,
        "total": len(licenses),
        "permissive": len([l for l in licenses if l.is_permissive]),
        "copyleft": len([l for l in licenses if l.is_copyleft]),
        "unknown": len([l for l in licenses if l.risk_level == "unknown"]),
        "high_risk": [l.to_dict() for l in licenses if l.risk_level == "high"],
        "licenses": [l.to_dict() for l in licenses],
    }


async def deps_health(path: str = "") -> dict[str, Any]:
    """
    Get overall dependency health.

    Args:
        path: Project path

    Returns:
        Health score and metrics
    """
    project_path = path or os.getcwd()
    tool = DependenciesTool(project_path)

    health = await tool.get_health()

    result = health.to_dict()
    result["grade"] = (
        "A" if health.health_score >= 90
        else "B" if health.health_score >= 80
        else "C" if health.health_score >= 70
        else "D" if health.health_score >= 60
        else "F"
    )

    return result


async def deps_updates(
    security_only: bool = False,
    path: str = "",
) -> dict[str, Any]:
    """
    Get prioritized update recommendations.

    Args:
        security_only: Only recommend security updates
        path: Project path

    Returns:
        Prioritized update recommendations
    """
    project_path = path or os.getcwd()
    tool = DependenciesTool(project_path)

    recommendations = await tool.get_update_recommendations(security_only=security_only)

    return {
        "package_manager": tool.package_manager.value,
        "total_recommendations": len(recommendations),
        "security_updates": len([r for r in recommendations if r.reason == "security fix"]),
        "breaking_updates": len([r for r in recommendations if r.breaking_changes]),
        "recommendations": [r.to_dict() for r in recommendations[:20]],
    }

"""
Dependencies Models - Data structures for dependency management.

Supports multiple package ecosystems:
- npm/yarn/pnpm (Node.js)
- pip/poetry/uv (Python)
- cargo (Rust)
- go modules (Go)
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class PackageManager(str, Enum):
    """Supported package managers."""
    NPM = "npm"
    YARN = "yarn"
    PNPM = "pnpm"
    PIP = "pip"
    POETRY = "poetry"
    UV = "uv"
    CARGO = "cargo"
    GO = "go"
    UNKNOWN = "unknown"


class DependencyType(str, Enum):
    """Type of dependency."""
    PRODUCTION = "production"
    DEVELOPMENT = "development"
    PEER = "peer"
    OPTIONAL = "optional"


class UpdateType(str, Enum):
    """Type of available update."""
    PATCH = "patch"
    MINOR = "minor"
    MAJOR = "major"


class VulnerabilitySeverity(str, Enum):
    """Vulnerability severity levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class Dependency:
    """A single dependency."""

    name: str
    version: str
    dep_type: DependencyType = DependencyType.PRODUCTION

    # Version info
    latest_version: str = ""
    wanted_version: str = ""  # Latest matching semver

    # Update available
    update_available: bool = False
    update_type: UpdateType | None = None

    # Source
    source: str = ""  # registry URL or git
    resolved: str = ""  # Actual resolved URL/path

    # License
    license: str = ""
    license_spdx: str = ""

    # Metadata
    description: str = ""
    homepage: str = ""
    repository: str = ""

    # Usage stats (from registry)
    weekly_downloads: int | None = None
    last_publish: datetime | None = None

    # Direct or transitive
    is_direct: bool = True
    parent: str = ""  # Parent dependency if transitive

    def to_dict(self) -> dict[str, Any]:
        result = {
            "name": self.name,
            "version": self.version,
            "type": self.dep_type.value,
            "license": self.license or "unknown",
        }

        if self.update_available:
            result["update"] = {
                "latest": self.latest_version,
                "type": self.update_type.value if self.update_type else "unknown",
            }

        if not self.is_direct:
            result["transitive"] = True
            result["parent"] = self.parent

        return result


@dataclass
class Vulnerability:
    """A security vulnerability in a dependency."""

    id: str  # CVE or advisory ID
    package: str
    severity: VulnerabilitySeverity
    title: str

    # Affected versions
    vulnerable_versions: str = ""
    patched_versions: str = ""

    # Details
    description: str = ""
    url: str = ""  # Advisory URL
    cwe: str = ""  # CWE ID

    # CVSS score
    cvss_score: float = 0.0
    cvss_vector: str = ""

    # Fix info
    has_fix: bool = False
    fix_version: str = ""

    # Metadata
    published_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "package": self.package,
            "severity": self.severity.value,
            "title": self.title,
            "cvss_score": self.cvss_score,
            "vulnerable_versions": self.vulnerable_versions,
            "fix_available": self.has_fix,
            "fix_version": self.fix_version if self.has_fix else None,
            "url": self.url,
        }


@dataclass
class LicenseInfo:
    """License information for a dependency."""

    package: str
    license_id: str  # SPDX identifier
    license_name: str = ""

    # Classification
    is_oss: bool = True
    is_copyleft: bool = False
    is_permissive: bool = True
    commercial_ok: bool = True

    # Restrictions
    requires_attribution: bool = False
    requires_disclosure: bool = False
    requires_same_license: bool = False

    # Risk level
    risk_level: str = "low"  # low, medium, high

    def to_dict(self) -> dict[str, Any]:
        return {
            "package": self.package,
            "license": self.license_id,
            "name": self.license_name,
            "type": (
                "copyleft" if self.is_copyleft
                else "permissive" if self.is_permissive
                else "proprietary"
            ),
            "risk": self.risk_level,
            "commercial_ok": self.commercial_ok,
        }


@dataclass
class DependencyTree:
    """Dependency tree structure."""

    root: str  # Project name
    package_manager: PackageManager

    # Direct dependencies
    direct_count: int = 0
    transitive_count: int = 0
    total_count: int = 0

    # Tree structure (nested dict)
    tree: dict[str, Any] = field(default_factory=dict)

    # Size info
    total_size_mb: float = 0.0
    largest_deps: list[tuple[str, float]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "root": self.root,
            "package_manager": self.package_manager.value,
            "counts": {
                "direct": self.direct_count,
                "transitive": self.transitive_count,
                "total": self.total_count,
            },
            "size_mb": round(self.total_size_mb, 2),
            "largest": [
                {"name": name, "size_mb": round(size, 2)}
                for name, size in self.largest_deps[:5]
            ],
        }


@dataclass
class DependencyHealth:
    """Overall health metrics for dependencies."""

    package_manager: PackageManager
    analyzed_at: datetime = field(default_factory=_utc_now)

    # Counts
    total_dependencies: int = 0
    direct_dependencies: int = 0
    dev_dependencies: int = 0

    # Updates
    outdated_count: int = 0
    major_updates: int = 0
    minor_updates: int = 0
    patch_updates: int = 0

    # Security
    vulnerabilities_critical: int = 0
    vulnerabilities_high: int = 0
    vulnerabilities_medium: int = 0
    vulnerabilities_low: int = 0

    # License
    unknown_licenses: int = 0
    copyleft_licenses: int = 0

    # Freshness
    avg_age_days: float = 0  # Average since last publish
    stale_count: int = 0  # Not updated in 2+ years

    @property
    def health_score(self) -> int:
        """Calculate dependency health score (0-100)."""
        score = 100

        # Deduct for vulnerabilities
        score -= self.vulnerabilities_critical * 20
        score -= self.vulnerabilities_high * 10
        score -= self.vulnerabilities_medium * 5
        score -= self.vulnerabilities_low * 2

        # Deduct for outdated
        score -= min(self.major_updates * 5, 20)
        score -= min(self.minor_updates * 2, 10)

        # Deduct for license issues
        score -= min(self.unknown_licenses * 3, 15)
        score -= min(self.copyleft_licenses * 2, 10)

        # Deduct for stale deps
        score -= min(self.stale_count * 2, 10)

        return max(0, score)

    def to_dict(self) -> dict[str, Any]:
        return {
            "package_manager": self.package_manager.value,
            "health_score": self.health_score,
            "dependencies": {
                "total": self.total_dependencies,
                "direct": self.direct_dependencies,
                "dev": self.dev_dependencies,
            },
            "updates": {
                "outdated": self.outdated_count,
                "major": self.major_updates,
                "minor": self.minor_updates,
                "patch": self.patch_updates,
            },
            "security": {
                "critical": self.vulnerabilities_critical,
                "high": self.vulnerabilities_high,
                "medium": self.vulnerabilities_medium,
                "low": self.vulnerabilities_low,
            },
            "licenses": {
                "unknown": self.unknown_licenses,
                "copyleft": self.copyleft_licenses,
            },
            "freshness": {
                "avg_age_days": round(self.avg_age_days),
                "stale": self.stale_count,
            },
        }


@dataclass
class UpdateRecommendation:
    """Recommended dependency updates."""

    package: str
    current_version: str
    recommended_version: str
    update_type: UpdateType

    # Risk assessment
    breaking_changes: bool = False
    changelog_url: str = ""

    # Reason for recommendation
    reason: str = ""  # e.g., "security fix", "performance", "stability"

    # Compatibility
    compatible: bool = True
    peer_deps_affected: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "package": self.package,
            "from": self.current_version,
            "to": self.recommended_version,
            "type": self.update_type.value,
            "breaking": self.breaking_changes,
            "reason": self.reason,
            "compatible": self.compatible,
        }

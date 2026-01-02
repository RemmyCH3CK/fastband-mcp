"""
Deployment Models - Data structures for deployment operations.

Supports multiple deployment targets:
- Vercel, Netlify, Railway, Fly.io
- Docker/Kubernetes
- Custom servers via SSH
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class DeploymentPlatform(str, Enum):
    """Supported deployment platforms."""
    VERCEL = "vercel"
    NETLIFY = "netlify"
    RAILWAY = "railway"
    FLY = "fly"
    DOCKER = "docker"
    KUBERNETES = "kubernetes"
    SSH = "ssh"
    UNKNOWN = "unknown"


class DeploymentStatus(str, Enum):
    """Deployment status states."""
    PENDING = "pending"
    BUILDING = "building"
    DEPLOYING = "deploying"
    READY = "ready"
    FAILED = "failed"
    CANCELLED = "cancelled"
    ROLLED_BACK = "rolled_back"


class EnvironmentType(str, Enum):
    """Deployment environment types."""
    PRODUCTION = "production"
    STAGING = "staging"
    PREVIEW = "preview"
    DEVELOPMENT = "development"


@dataclass
class DeploymentConfig:
    """Configuration for a deployment."""

    platform: DeploymentPlatform
    project_id: str = ""
    project_name: str = ""

    # Environment
    environment: EnvironmentType = EnvironmentType.PREVIEW

    # Build settings
    build_command: str = ""
    output_directory: str = ""
    install_command: str = ""

    # Environment variables
    env_vars: dict[str, str] = field(default_factory=dict)

    # Platform-specific
    region: str = ""
    framework: str = ""
    node_version: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "platform": self.platform.value,
            "project_id": self.project_id,
            "project_name": self.project_name,
            "environment": self.environment.value,
            "build_command": self.build_command,
            "output_directory": self.output_directory,
            "region": self.region,
            "framework": self.framework,
        }


@dataclass
class Deployment:
    """A single deployment instance."""

    id: str
    platform: DeploymentPlatform
    status: DeploymentStatus

    # URLs
    url: str = ""
    inspect_url: str = ""  # Dashboard URL

    # Git info
    branch: str = ""
    commit_sha: str = ""
    commit_message: str = ""

    # Environment
    environment: EnvironmentType = EnvironmentType.PREVIEW

    # Timing
    created_at: datetime = field(default_factory=_utc_now)
    ready_at: datetime | None = None

    # Build info
    build_duration_ms: int = 0

    # Errors
    error_message: str = ""
    error_code: str = ""

    # Metadata
    creator: str = ""

    @property
    def is_ready(self) -> bool:
        return self.status == DeploymentStatus.READY

    @property
    def is_failed(self) -> bool:
        return self.status == DeploymentStatus.FAILED

    @property
    def build_duration_seconds(self) -> float:
        return self.build_duration_ms / 1000

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "platform": self.platform.value,
            "status": self.status.value,
            "url": self.url,
            "branch": self.branch,
            "commit": self.commit_sha[:8] if self.commit_sha else "",
            "environment": self.environment.value,
            "created_at": self.created_at.isoformat(),
            "ready_at": self.ready_at.isoformat() if self.ready_at else None,
            "build_duration_s": self.build_duration_seconds,
            "error": self.error_message if self.is_failed else None,
        }


@dataclass
class RollbackInfo:
    """Information about a rollback operation."""

    from_deployment_id: str
    to_deployment_id: str

    reason: str = ""
    initiated_by: str = ""
    initiated_at: datetime = field(default_factory=_utc_now)

    # Status
    success: bool = False
    completed_at: datetime | None = None
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "from": self.from_deployment_id,
            "to": self.to_deployment_id,
            "reason": self.reason,
            "initiated_by": self.initiated_by,
            "initiated_at": self.initiated_at.isoformat(),
            "success": self.success,
            "error": self.error if not self.success else None,
        }


@dataclass
class DeploymentHealth:
    """Health status of a deployment."""

    deployment_id: str
    url: str

    # Health checks
    is_reachable: bool = False
    response_time_ms: int = 0
    status_code: int = 0

    # SSL
    ssl_valid: bool = False
    ssl_expires_at: datetime | None = None
    ssl_days_remaining: int = 0

    # Performance (if available)
    lighthouse_score: int | None = None

    # Errors
    error: str = ""

    checked_at: datetime = field(default_factory=_utc_now)

    @property
    def is_healthy(self) -> bool:
        return self.is_reachable and 200 <= self.status_code < 400

    def to_dict(self) -> dict[str, Any]:
        return {
            "deployment_id": self.deployment_id,
            "url": self.url,
            "healthy": self.is_healthy,
            "reachable": self.is_reachable,
            "response_time_ms": self.response_time_ms,
            "status_code": self.status_code,
            "ssl_valid": self.ssl_valid,
            "ssl_days_remaining": self.ssl_days_remaining if self.ssl_valid else None,
            "checked_at": self.checked_at.isoformat(),
            "error": self.error if not self.is_healthy else None,
        }


@dataclass
class DeploymentDiff:
    """Differences between two deployments."""

    from_deployment: Deployment
    to_deployment: Deployment

    # Changes
    files_added: list[str] = field(default_factory=list)
    files_modified: list[str] = field(default_factory=list)
    files_deleted: list[str] = field(default_factory=list)

    # Commits between
    commits: list[dict[str, str]] = field(default_factory=list)

    # Env var changes
    env_vars_added: list[str] = field(default_factory=list)
    env_vars_removed: list[str] = field(default_factory=list)
    env_vars_changed: list[str] = field(default_factory=list)

    # Dependencies
    deps_added: list[str] = field(default_factory=list)
    deps_removed: list[str] = field(default_factory=list)
    deps_updated: list[str] = field(default_factory=list)

    @property
    def total_changes(self) -> int:
        return (
            len(self.files_added) +
            len(self.files_modified) +
            len(self.files_deleted)
        )

    @property
    def has_breaking_changes(self) -> bool:
        # Heuristic: env var removal or major dep changes
        return (
            len(self.env_vars_removed) > 0 or
            any("major" in d.lower() for d in self.deps_updated)
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "from": self.from_deployment.id,
            "to": self.to_deployment.id,
            "files": {
                "added": self.files_added[:10],
                "modified": self.files_modified[:10],
                "deleted": self.files_deleted[:10],
                "total_changes": self.total_changes,
            },
            "commits": self.commits[:5],
            "env_changes": {
                "added": self.env_vars_added,
                "removed": self.env_vars_removed,
                "changed": self.env_vars_changed,
            },
            "deps_changes": {
                "added": self.deps_added[:5],
                "removed": self.deps_removed[:5],
                "updated": self.deps_updated[:5],
            },
            "has_breaking_changes": self.has_breaking_changes,
        }


@dataclass
class DeploymentMetrics:
    """Deployment frequency and health metrics."""

    period_days: int = 30

    # Counts
    total_deployments: int = 0
    successful_deployments: int = 0
    failed_deployments: int = 0
    rollbacks: int = 0

    # Timing
    avg_build_time_s: float = 0
    avg_deploy_time_s: float = 0

    # By environment
    production_deploys: int = 0
    preview_deploys: int = 0

    # Frequency
    deploys_per_day: float = 0

    # DORA metrics
    lead_time_hours: float = 0  # Commit to production
    mttr_hours: float = 0  # Mean time to recover
    change_failure_rate: float = 0  # % of deploys causing issues

    @property
    def success_rate(self) -> float:
        if self.total_deployments == 0:
            return 0
        return (self.successful_deployments / self.total_deployments) * 100

    def to_dict(self) -> dict[str, Any]:
        return {
            "period_days": self.period_days,
            "total": self.total_deployments,
            "successful": self.successful_deployments,
            "failed": self.failed_deployments,
            "rollbacks": self.rollbacks,
            "success_rate": f"{self.success_rate:.1f}%",
            "avg_build_time_s": round(self.avg_build_time_s, 1),
            "deploys_per_day": round(self.deploys_per_day, 2),
            "dora_metrics": {
                "lead_time_hours": round(self.lead_time_hours, 1),
                "mttr_hours": round(self.mttr_hours, 1),
                "change_failure_rate": f"{self.change_failure_rate:.1f}%",
            },
            "by_environment": {
                "production": self.production_deploys,
                "preview": self.preview_deploys,
            },
        }

"""
Environment Models - Data structures for environment variable management.

Supports:
- .env file parsing
- Environment comparison
- Secret detection
- Variable validation
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class EnvironmentType(str, Enum):
    """Environment types."""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TEST = "test"
    LOCAL = "local"


class VariableCategory(str, Enum):
    """Categories of environment variables."""
    DATABASE = "database"
    API_KEY = "api_key"
    SECRET = "secret"
    URL = "url"
    PORT = "port"
    FEATURE_FLAG = "feature_flag"
    CONFIG = "config"
    UNKNOWN = "unknown"


class SecretRisk(str, Enum):
    """Risk level for secrets."""
    CRITICAL = "critical"  # Exposed API key, password
    HIGH = "high"  # Potentially sensitive
    MEDIUM = "medium"  # Internal config
    LOW = "low"  # Non-sensitive


@dataclass
class EnvVariable:
    """A single environment variable."""

    name: str
    value: str = ""  # May be masked for security

    # Classification
    category: VariableCategory = VariableCategory.UNKNOWN
    is_secret: bool = False
    secret_risk: SecretRisk = SecretRisk.LOW

    # Source
    source_file: str = ""
    line_number: int = 0

    # Validation
    is_valid: bool = True
    validation_error: str = ""

    # Comparison
    differs_from_prod: bool = False
    prod_value: str = ""  # Masked

    # Documentation
    description: str = ""
    example: str = ""
    required: bool = False

    def to_dict(self, mask_secrets: bool = True) -> dict[str, Any]:
        value = self.value
        if mask_secrets and self.is_secret and value:
            # Mask all but first 4 chars
            value = value[:4] + "*" * (len(value) - 4) if len(value) > 4 else "****"

        return {
            "name": self.name,
            "value": value,
            "category": self.category.value,
            "is_secret": self.is_secret,
            "source": self.source_file,
            "valid": self.is_valid,
            "error": self.validation_error if not self.is_valid else None,
        }


@dataclass
class EnvFile:
    """Parsed .env file."""

    path: str
    environment: EnvironmentType = EnvironmentType.LOCAL

    variables: list[EnvVariable] = field(default_factory=list)

    # Metadata
    exists: bool = True
    last_modified: datetime | None = None

    # Stats
    total_vars: int = 0
    secret_count: int = 0
    empty_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "environment": self.environment.value,
            "exists": self.exists,
            "total_vars": self.total_vars,
            "secrets": self.secret_count,
            "empty": self.empty_count,
        }


@dataclass
class EnvComparison:
    """Comparison between two environments."""

    source_env: str
    target_env: str

    # Differences
    missing_in_target: list[str] = field(default_factory=list)
    missing_in_source: list[str] = field(default_factory=list)
    different_values: list[str] = field(default_factory=list)
    same_values: list[str] = field(default_factory=list)

    # Risk assessment
    missing_secrets: list[str] = field(default_factory=list)
    secrets_differ: list[str] = field(default_factory=list)

    @property
    def is_compatible(self) -> bool:
        return len(self.missing_in_target) == 0 and len(self.missing_secrets) == 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source_env,
            "target": self.target_env,
            "compatible": self.is_compatible,
            "missing_in_target": self.missing_in_target,
            "missing_in_source": self.missing_in_source,
            "different_values": len(self.different_values),
            "same_values": len(self.same_values),
            "risks": {
                "missing_secrets": self.missing_secrets,
                "secrets_differ": self.secrets_differ,
            },
        }


@dataclass
class EnvValidation:
    """Validation results for environment variables."""

    env_file: str
    passed: bool = True

    # Issues
    missing_required: list[str] = field(default_factory=list)
    invalid_format: list[dict[str, str]] = field(default_factory=list)
    exposed_secrets: list[dict[str, str]] = field(default_factory=list)
    empty_values: list[str] = field(default_factory=list)

    # Warnings
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "env_file": self.env_file,
            "passed": self.passed,
            "issues": {
                "missing_required": self.missing_required,
                "invalid_format": self.invalid_format,
                "exposed_secrets": self.exposed_secrets[:5],
                "empty_values": self.empty_values,
            },
            "warnings": self.warnings[:5],
        }


@dataclass
class EnvDocumentation:
    """Generated documentation for environment variables."""

    project_name: str
    generated_at: datetime = field(default_factory=_utc_now)

    # Variables by category
    variables: list[EnvVariable] = field(default_factory=list)

    # Stats
    total_count: int = 0
    required_count: int = 0
    optional_count: int = 0

    def to_markdown(self) -> str:
        """Generate markdown documentation."""
        lines = [
            f"# Environment Variables - {self.project_name}",
            "",
            f"Generated: {self.generated_at.strftime('%Y-%m-%d %H:%M UTC')}",
            "",
            f"Total: {self.total_count} variables ({self.required_count} required)",
            "",
            "## Variables",
            "",
        ]

        # Group by category
        by_category: dict[str, list[EnvVariable]] = {}
        for var in self.variables:
            cat = var.category.value
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(var)

        for category, vars in sorted(by_category.items()):
            lines.append(f"### {category.replace('_', ' ').title()}")
            lines.append("")
            lines.append("| Variable | Required | Description |")
            lines.append("|----------|----------|-------------|")

            for var in vars:
                required = "Yes" if var.required else "No"
                desc = var.description or "-"
                lines.append(f"| `{var.name}` | {required} | {desc} |")

            lines.append("")

        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "project": self.project_name,
            "total": self.total_count,
            "required": self.required_count,
            "optional": self.optional_count,
            "variables": [v.to_dict(mask_secrets=True) for v in self.variables],
        }

"""
Environment Tool - Environment variable management and validation.

Provides MCP tools for:
- Parsing .env files
- Secret detection
- Environment comparison
- Variable validation
- Documentation generation
"""

import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastband.tools.environment.models import (
    EnvComparison,
    EnvDocumentation,
    EnvFile,
    EnvValidation,
    EnvVariable,
    EnvironmentType,
    SecretRisk,
    VariableCategory,
)

logger = logging.getLogger(__name__)


# Patterns for secret detection
SECRET_PATTERNS = [
    (r"password", SecretRisk.CRITICAL),
    (r"secret", SecretRisk.CRITICAL),
    (r"api_?key", SecretRisk.CRITICAL),
    (r"auth_?token", SecretRisk.CRITICAL),
    (r"access_?token", SecretRisk.CRITICAL),
    (r"private_?key", SecretRisk.CRITICAL),
    (r"jwt_?secret", SecretRisk.CRITICAL),
    (r"encryption_?key", SecretRisk.CRITICAL),
    (r"aws_secret", SecretRisk.CRITICAL),
    (r"stripe_?key", SecretRisk.CRITICAL),
    (r"sendgrid", SecretRisk.HIGH),
    (r"twilio", SecretRisk.HIGH),
    (r"database_?url", SecretRisk.HIGH),
    (r"redis_?url", SecretRisk.HIGH),
    (r"connection_?string", SecretRisk.HIGH),
    (r"credentials", SecretRisk.HIGH),
]

# Patterns for categorization
CATEGORY_PATTERNS = {
    VariableCategory.DATABASE: [r"db_", r"database", r"mysql", r"postgres", r"mongo", r"redis", r"sql"],
    VariableCategory.API_KEY: [r"api_?key", r"_key$", r"_token$"],
    VariableCategory.SECRET: [r"secret", r"password", r"credential"],
    VariableCategory.URL: [r"_url$", r"_uri$", r"_host$", r"_endpoint$", r"http"],
    VariableCategory.PORT: [r"_port$", r"^port$"],
    VariableCategory.FEATURE_FLAG: [r"^feature_", r"^enable_", r"^disable_", r"^use_"],
}

# Required variables for common frameworks
COMMON_REQUIRED = {
    "DATABASE_URL", "SECRET_KEY", "API_KEY", "NODE_ENV", "NEXT_PUBLIC_",
    "VITE_", "REACT_APP_", "DJANGO_SECRET_KEY", "FLASK_SECRET_KEY",
}


def parse_env_file(file_path: str) -> EnvFile:
    """Parse a .env file and extract variables."""
    path = Path(file_path)

    env_file = EnvFile(
        path=str(path),
        exists=path.exists(),
    )

    if not path.exists():
        return env_file

    # Determine environment from filename
    name_lower = path.name.lower()
    if "prod" in name_lower:
        env_file.environment = EnvironmentType.PRODUCTION
    elif "stag" in name_lower:
        env_file.environment = EnvironmentType.STAGING
    elif "test" in name_lower:
        env_file.environment = EnvironmentType.TEST
    elif "dev" in name_lower:
        env_file.environment = EnvironmentType.DEVELOPMENT
    else:
        env_file.environment = EnvironmentType.LOCAL

    try:
        env_file.last_modified = datetime.fromtimestamp(
            path.stat().st_mtime,
            tz=timezone.utc
        )
    except OSError:
        pass

    # Parse file
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()

                # Skip empty lines and comments
                if not line or line.startswith("#"):
                    continue

                # Parse KEY=value
                if "=" in line:
                    key, _, value = line.partition("=")
                    key = key.strip()
                    value = value.strip()

                    # Remove quotes
                    if value and value[0] in ('"', "'") and value[-1] == value[0]:
                        value = value[1:-1]

                    var = EnvVariable(
                        name=key,
                        value=value,
                        source_file=str(path),
                        line_number=line_num,
                    )

                    # Categorize
                    var.category = _categorize_variable(key)

                    # Check if secret
                    is_secret, risk = _is_secret(key)
                    var.is_secret = is_secret
                    var.secret_risk = risk

                    # Check if empty
                    if not value:
                        env_file.empty_count += 1

                    env_file.variables.append(var)

    except OSError as e:
        logger.warning(f"Failed to parse {file_path}: {e}")

    env_file.total_vars = len(env_file.variables)
    env_file.secret_count = len([v for v in env_file.variables if v.is_secret])

    return env_file


def _categorize_variable(name: str) -> VariableCategory:
    """Categorize a variable based on its name."""
    name_lower = name.lower()

    for category, patterns in CATEGORY_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, name_lower):
                return category

    return VariableCategory.CONFIG


def _is_secret(name: str) -> tuple[bool, SecretRisk]:
    """Determine if a variable is a secret and its risk level."""
    name_lower = name.lower()

    for pattern, risk in SECRET_PATTERNS:
        if re.search(pattern, name_lower):
            return True, risk

    return False, SecretRisk.LOW


def find_env_files(project_root: str) -> list[str]:
    """Find all .env files in a project."""
    root = Path(project_root)
    env_files = []

    # Common .env file patterns
    patterns = [
        ".env",
        ".env.local",
        ".env.development",
        ".env.development.local",
        ".env.staging",
        ".env.production",
        ".env.test",
        ".env.example",
        ".env.sample",
    ]

    for pattern in patterns:
        env_path = root / pattern
        if env_path.exists():
            env_files.append(str(env_path))

    return env_files


def compare_env_files(source_path: str, target_path: str) -> EnvComparison:
    """Compare two .env files."""
    source = parse_env_file(source_path)
    target = parse_env_file(target_path)

    comparison = EnvComparison(
        source_env=source_path,
        target_env=target_path,
    )

    source_vars = {v.name: v for v in source.variables}
    target_vars = {v.name: v for v in target.variables}

    # Find missing
    for name in source_vars:
        if name not in target_vars:
            comparison.missing_in_target.append(name)
            if source_vars[name].is_secret:
                comparison.missing_secrets.append(name)

    for name in target_vars:
        if name not in source_vars:
            comparison.missing_in_source.append(name)

    # Find different values
    for name in source_vars:
        if name in target_vars:
            if source_vars[name].value != target_vars[name].value:
                comparison.different_values.append(name)
                if source_vars[name].is_secret:
                    comparison.secrets_differ.append(name)
            else:
                comparison.same_values.append(name)

    return comparison


def validate_env_file(
    file_path: str,
    required_vars: list[str] | None = None,
) -> EnvValidation:
    """Validate an .env file."""
    env_file = parse_env_file(file_path)

    validation = EnvValidation(
        env_file=file_path,
        passed=True,
    )

    if not env_file.exists:
        validation.passed = False
        validation.warnings.append(f"File {file_path} does not exist")
        return validation

    var_names = {v.name for v in env_file.variables}

    # Check required variables
    if required_vars:
        for req in required_vars:
            if req not in var_names:
                validation.missing_required.append(req)
                validation.passed = False

    # Check for empty values on secrets
    for var in env_file.variables:
        if var.is_secret and not var.value:
            validation.empty_values.append(var.name)
            validation.passed = False

        # Check for exposed secrets (in non-.example files)
        if var.is_secret and var.value and "example" not in file_path.lower():
            if var.secret_risk == SecretRisk.CRITICAL:
                validation.exposed_secrets.append({
                    "name": var.name,
                    "risk": var.secret_risk.value,
                    "line": var.line_number,
                })

    # Warnings
    if env_file.empty_count > 0:
        validation.warnings.append(f"{env_file.empty_count} variables have empty values")

    return validation


def find_missing_env_vars(project_root: str) -> list[str]:
    """Find environment variables referenced in code but not in .env files."""
    root = Path(project_root)

    # Get all defined env vars
    env_files = find_env_files(project_root)
    defined_vars = set()
    for env_path in env_files:
        env_file = parse_env_file(env_path)
        defined_vars.update(v.name for v in env_file.variables)

    # Find referenced vars in code
    referenced_vars = set()

    # Patterns to find env var references
    patterns = [
        r"process\.env\.([A-Z][A-Z0-9_]+)",  # Node.js
        r"os\.environ\[?['\"]([A-Z][A-Z0-9_]+)['\"]",  # Python
        r"os\.getenv\(['\"]([A-Z][A-Z0-9_]+)['\"]",  # Python
        r"ENV\[?['\"]([A-Z][A-Z0-9_]+)['\"]",  # Ruby
        r"\$\{([A-Z][A-Z0-9_]+)\}",  # Shell/Docker
    ]

    combined_pattern = "|".join(f"({p})" for p in patterns)

    # Search code files
    for ext in [".js", ".ts", ".jsx", ".tsx", ".py", ".rb", ".sh"]:
        for file_path in root.rglob(f"*{ext}"):
            # Skip node_modules, venv, etc.
            if any(skip in str(file_path) for skip in ["node_modules", "venv", ".venv", "__pycache__"]):
                continue

            try:
                with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
                    for match in re.finditer(combined_pattern, content):
                        # Get the actual captured group
                        for group in match.groups():
                            if group and group.isupper():
                                referenced_vars.add(group)
            except OSError:
                continue

    # Find missing
    missing = referenced_vars - defined_vars

    # Filter out common system vars
    system_vars = {"PATH", "HOME", "USER", "NODE_ENV", "DEBUG", "CI", "TERM"}
    missing = missing - system_vars

    return sorted(missing)


class EnvironmentTool:
    """Unified environment variable management tool."""

    def __init__(self, project_root: str):
        self.project_root = Path(project_root)

    async def list_env_files(self) -> list[dict[str, Any]]:
        """List all .env files in the project."""
        files = find_env_files(str(self.project_root))
        result = []

        for file_path in files:
            env_file = parse_env_file(file_path)
            result.append(env_file.to_dict())

        return result

    async def get_env_vars(self, file_path: str = ".env") -> dict[str, Any]:
        """Get variables from an .env file."""
        full_path = self.project_root / file_path
        env_file = parse_env_file(str(full_path))

        return {
            **env_file.to_dict(),
            "variables": [v.to_dict(mask_secrets=True) for v in env_file.variables],
        }

    async def validate(
        self,
        file_path: str = ".env",
        required: list[str] | None = None,
    ) -> dict[str, Any]:
        """Validate an .env file."""
        full_path = self.project_root / file_path
        validation = validate_env_file(str(full_path), required)
        return validation.to_dict()

    async def compare(
        self,
        source: str = ".env.development",
        target: str = ".env.production",
    ) -> dict[str, Any]:
        """Compare two .env files."""
        source_path = self.project_root / source
        target_path = self.project_root / target

        comparison = compare_env_files(str(source_path), str(target_path))
        return comparison.to_dict()

    async def find_missing(self) -> dict[str, Any]:
        """Find environment variables referenced but not defined."""
        missing = find_missing_env_vars(str(self.project_root))

        return {
            "missing_count": len(missing),
            "missing_vars": missing,
            "recommendation": (
                f"Add {len(missing)} missing variables to .env files"
                if missing
                else "All referenced environment variables are defined"
            ),
        }

    async def generate_documentation(self, file_path: str = ".env.example") -> dict[str, Any]:
        """Generate documentation for environment variables."""
        full_path = self.project_root / file_path
        env_file = parse_env_file(str(full_path))

        doc = EnvDocumentation(
            project_name=self.project_root.name,
            variables=env_file.variables,
            total_count=len(env_file.variables),
            required_count=len([v for v in env_file.variables if v.required]),
            optional_count=len([v for v in env_file.variables if not v.required]),
        )

        return {
            **doc.to_dict(),
            "markdown": doc.to_markdown(),
        }


# =============================================================================
# MCP-FACING FUNCTIONS
# =============================================================================

async def env_list(path: str = "") -> dict[str, Any]:
    """List all .env files in the project."""
    project_path = path or os.getcwd()
    tool = EnvironmentTool(project_path)
    files = await tool.list_env_files()
    return {
        "count": len(files),
        "files": files,
    }


async def env_vars(file_path: str = ".env", path: str = "") -> dict[str, Any]:
    """Get variables from an .env file."""
    project_path = path or os.getcwd()
    tool = EnvironmentTool(project_path)
    return await tool.get_env_vars(file_path)


async def env_validate(
    file_path: str = ".env",
    required: str = "",
    path: str = "",
) -> dict[str, Any]:
    """Validate an .env file."""
    project_path = path or os.getcwd()
    tool = EnvironmentTool(project_path)
    required_list = [r.strip() for r in required.split(",")] if required else None
    return await tool.validate(file_path, required_list)


async def env_compare(
    source: str = ".env.development",
    target: str = ".env.production",
    path: str = "",
) -> dict[str, Any]:
    """Compare two .env files."""
    project_path = path or os.getcwd()
    tool = EnvironmentTool(project_path)
    return await tool.compare(source, target)


async def env_missing(path: str = "") -> dict[str, Any]:
    """Find missing environment variables."""
    project_path = path or os.getcwd()
    tool = EnvironmentTool(project_path)
    return await tool.find_missing()


async def env_docs(file_path: str = ".env.example", path: str = "") -> dict[str, Any]:
    """Generate environment documentation."""
    project_path = path or os.getcwd()
    tool = EnvironmentTool(project_path)
    return await tool.generate_documentation(file_path)

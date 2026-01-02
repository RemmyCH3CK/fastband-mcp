"""
Environment Tools - Environment variable management and validation.

Provides MCP tools for:
- .env file parsing and listing
- Secret detection and masking
- Environment comparison (dev vs prod)
- Variable validation
- Missing variable detection
- Documentation generation

Usage:
    # List .env files
    result = await env_list()
    for f in result["files"]:
        print(f"{f['path']}: {f['total_vars']} vars")

    # Validate .env file
    result = await env_validate(".env", required="DATABASE_URL,SECRET_KEY")
    if not result["passed"]:
        print(f"Missing: {result['issues']['missing_required']}")

    # Compare environments
    result = await env_compare(".env.dev", ".env.prod")
    print(f"Missing in prod: {result['missing_in_target']}")
"""

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
from fastband.tools.environment.tool import (
    EnvironmentTool,
    compare_env_files,
    env_compare,
    env_docs,
    env_list,
    env_missing,
    env_validate,
    env_vars,
    find_env_files,
    find_missing_env_vars,
    parse_env_file,
    validate_env_file,
)

__all__ = [
    # Main tool
    "EnvironmentTool",
    # Utility functions
    "parse_env_file",
    "find_env_files",
    "compare_env_files",
    "validate_env_file",
    "find_missing_env_vars",
    # MCP functions
    "env_list",
    "env_vars",
    "env_validate",
    "env_compare",
    "env_missing",
    "env_docs",
    # Models
    "EnvironmentType",
    "VariableCategory",
    "SecretRisk",
    "EnvVariable",
    "EnvFile",
    "EnvComparison",
    "EnvValidation",
    "EnvDocumentation",
]


# =========================================================================
# MCP TOOL REGISTRATION
# =========================================================================

def register_tools(mcp_server):
    """Register environment tools with the MCP server."""

    @mcp_server.tool()
    async def env_list_files(path: str = "") -> dict:
        """
        List all .env files in the project.

        Discovers .env, .env.local, .env.development,
        .env.production, .env.example, etc.

        Args:
            path: Project path (defaults to current directory)

        Returns:
            List of .env files with:
            - path: File path
            - environment: Detected environment type
            - total_vars: Number of variables
            - secrets: Number of secret variables

        Example:
            {}
        """
        return await env_list(path=path)

    @mcp_server.tool()
    async def env_get_vars(file_path: str = ".env", path: str = "") -> dict:
        """
        Get variables from an .env file.

        Parses the file and categorizes variables,
        detecting secrets and masking their values.

        Args:
            file_path: Path to .env file (relative)
            path: Project path

        Returns:
            Variables with:
            - name: Variable name
            - value: Value (masked if secret)
            - category: Variable category
            - is_secret: If it's a secret

        Example:
            {} or {"file_path": ".env.production"}
        """
        return await env_vars(file_path=file_path, path=path)

    @mcp_server.tool()
    async def env_validate_file(
        file_path: str = ".env",
        required: str = "",
        path: str = "",
    ) -> dict:
        """
        Validate an .env file.

        Checks for missing required variables, empty values
        on secrets, and exposed credentials.

        Args:
            file_path: Path to .env file
            required: Comma-separated required variable names
            path: Project path

        Returns:
            Validation results:
            - passed: If validation passed
            - missing_required: Missing required variables
            - exposed_secrets: Secrets that might be exposed

        Example:
            {"required": "DATABASE_URL,SECRET_KEY"}
        """
        return await env_validate(file_path=file_path, required=required, path=path)

    @mcp_server.tool()
    async def env_compare_files(
        source: str = ".env.development",
        target: str = ".env.production",
        path: str = "",
    ) -> dict:
        """
        Compare two .env files.

        Identifies missing variables and different values
        between environments.

        Args:
            source: Source .env file
            target: Target .env file to compare
            path: Project path

        Returns:
            Comparison:
            - compatible: If environments are compatible
            - missing_in_target: Variables only in source
            - missing_in_source: Variables only in target
            - different_values: Count of differing values

        Example:
            {"source": ".env.development", "target": ".env.production"}
        """
        return await env_compare(source=source, target=target, path=path)

    @mcp_server.tool()
    async def env_find_missing(path: str = "") -> dict:
        """
        Find environment variables referenced but not defined.

        Scans code for process.env, os.environ, etc. and
        compares with defined variables in .env files.

        Args:
            path: Project path

        Returns:
            Missing variables:
            - missing_count: Number of missing variables
            - missing_vars: List of missing variable names

        Example:
            {}
        """
        return await env_missing(path=path)

    @mcp_server.tool()
    async def env_generate_docs(
        file_path: str = ".env.example",
        path: str = "",
    ) -> dict:
        """
        Generate documentation for environment variables.

        Creates markdown documentation from an .env.example file.

        Args:
            file_path: Source .env file for documentation
            path: Project path

        Returns:
            Documentation:
            - total: Total variables
            - required: Required variable count
            - markdown: Generated markdown documentation

        Example:
            {} or {"file_path": ".env.example"}
        """
        return await env_docs(file_path=file_path, path=path)

    return [
        "env_list_files",
        "env_get_vars",
        "env_validate_file",
        "env_compare_files",
        "env_find_missing",
        "env_generate_docs",
    ]

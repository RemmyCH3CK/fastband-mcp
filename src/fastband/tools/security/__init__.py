"""
Security Tools - Comprehensive security scanning with ambient context.

Provides MCP tools for:
- Dependency vulnerability scanning (SCA)
- Secret detection in source code
- SBOM generation for compliance
- CodebaseContext integration for risk assessment

Usage:
    # Full security scan
    result = await security_scan(".", scan_type="all")
    print(f"Risk Score: {result['risk_score']}/100")

    # Check dependencies only
    result = await security_scan_dependencies(".")
    print(f"Vulnerable packages: {result['vulnerable_dependencies']}")

    # Scan for secrets
    result = await security_scan_secrets(".", include_tests=False)
    print(f"Secrets found: {result['secrets_found']}")

    # Generate SBOM for compliance
    result = await security_generate_sbom(".", format="cyclonedx")
"""

from fastband.tools.security.dependencies import (
    DependencyScanner,
    ManifestInfo,
)
from fastband.tools.security.models import (
    SBOM,
    DependencyInfo,
    SBOMComponent,
    SecretFinding,
    SecretType,
    SecurityReport,
    SourceLocation,
    Vulnerability,
    VulnerabilitySeverity,
    VulnerabilityType,
)
from fastband.tools.security.secrets import (
    SecretPattern,
    SecretsScanner,
)
from fastband.tools.security.tool import (
    SecurityConfig,
    SecurityTool,
    security_check_file,
    security_generate_sbom,
    security_scan,
    security_scan_dependencies,
    security_scan_secrets,
)

__all__ = [
    # Main tool
    "SecurityTool",
    "SecurityConfig",
    # MCP functions
    "security_scan",
    "security_scan_dependencies",
    "security_scan_secrets",
    "security_generate_sbom",
    "security_check_file",
    # Models
    "Vulnerability",
    "VulnerabilitySeverity",
    "VulnerabilityType",
    "SecretFinding",
    "SecretType",
    "DependencyInfo",
    "SecurityReport",
    "SBOM",
    "SBOMComponent",
    "SourceLocation",
    # Scanners
    "DependencyScanner",
    "SecretsScanner",
    "ManifestInfo",
    "SecretPattern",
]


# =========================================================================
# MCP TOOL REGISTRATION
# =========================================================================

def register_tools(mcp_server):
    """Register security tools with the MCP server."""

    @mcp_server.tool()
    async def security_scan_project(
        path: str = ".",
        scan_type: str = "all",
        min_severity: str = "low",
        generate_sbom: bool = False,
    ) -> dict:
        """
        Run comprehensive security scan on a project.

        Scans for dependency vulnerabilities and exposed secrets,
        with optional SBOM generation for compliance.

        Args:
            path: Project path to scan (default: current directory)
            scan_type: What to scan:
                - "all": Dependencies and secrets
                - "dependencies": Only package vulnerabilities
                - "secrets": Only exposed secrets
            min_severity: Minimum severity to report:
                - "critical": Only critical issues
                - "high": High and above
                - "medium": Medium and above
                - "low": All issues (default)
            generate_sbom: Generate Software Bill of Materials

        Returns:
            Security report with:
            - risk_score: Overall risk score (0-100)
            - vulnerabilities: Counts by severity
            - findings: List of issues found
            - policy_passed: Whether scan passes security policy
            - sbom: SBOM data if requested

        Example:
            # Full security audit
            {"path": ".", "scan_type": "all", "generate_sbom": true}

            # Quick dependency check
            {"path": ".", "scan_type": "dependencies", "min_severity": "high"}
        """
        return await security_scan(
            path=path,
            scan_type=scan_type,
            min_severity=min_severity,
            generate_sbom=generate_sbom,
        )

    @mcp_server.tool()
    async def security_check_dependencies(
        path: str = ".",
        include_dev: bool = True,
    ) -> dict:
        """
        Scan project dependencies for known vulnerabilities.

        Checks packages in requirements.txt, package.json, go.mod, etc.
        against the OSV (Open Source Vulnerabilities) database.

        Args:
            path: Project path to scan
            include_dev: Include devDependencies (default: true)

        Returns:
            Dependency report with:
            - total_dependencies: Number of packages found
            - vulnerable_dependencies: Packages with known vulns
            - vulnerable_packages: Details of affected packages
            - manifests_scanned: Which package files were checked

        Example:
            {"path": ".", "include_dev": false}
        """
        return await security_scan_dependencies(
            path=path,
            include_dev=include_dev,
        )

    @mcp_server.tool()
    async def security_detect_secrets(
        path: str = ".",
        include_tests: bool = False,
    ) -> dict:
        """
        Scan source code for exposed secrets.

        Detects API keys, tokens, passwords, and private keys using
        pattern matching and entropy analysis.

        Supports detection of:
        - AWS, GCP, Azure credentials
        - GitHub, Slack, Discord tokens
        - Stripe, Twilio, SendGrid keys
        - Database connection strings
        - Private keys (RSA, EC, SSH)
        - Generic passwords and API keys

        Args:
            path: Project path to scan
            include_tests: Include test/example files (default: false)

        Returns:
            Secrets report with:
            - secrets_found: Total count
            - severity_counts: By severity level
            - findings: Details with remediation advice
            - high_risk_files: Files on critical paths with secrets

        Example:
            {"path": "src/", "include_tests": false}
        """
        return await security_scan_secrets(
            path=path,
            include_tests=include_tests,
        )

    @mcp_server.tool()
    async def security_sbom(
        path: str = ".",
        format: str = "cyclonedx",
    ) -> dict:
        """
        Generate Software Bill of Materials (SBOM).

        Creates a comprehensive inventory of all project dependencies
        for compliance audits (SOC2, HIPAA, etc.) and security tracking.

        Args:
            path: Project path
            format: Output format:
                - "cyclonedx": CycloneDX 1.5 format (default)
                - "spdx": SPDX 2.3 format

        Returns:
            SBOM with:
            - total_components: All dependencies
            - direct_dependencies: First-level deps
            - transitive_dependencies: Nested deps
            - vulnerable_components: With known vulns
            - sbom: Full SBOM document in requested format

        Example:
            {"path": ".", "format": "cyclonedx"}
        """
        return await security_generate_sbom(
            path=path,
            format=format,
        )

    @mcp_server.tool()
    async def security_quick_check(file_path: str) -> dict:
        """
        Quick security check for a single file.

        Fast scan for exposed secrets with pass/fail result.
        Ideal for pre-commit hooks or quick validation.

        Args:
            file_path: Path to file to check

        Returns:
            Quick check result:
            - passed: Boolean pass/fail
            - status: "pass" or "fail"
            - secrets_found: Count of secrets
            - findings: Details of issues found

        Example:
            {"file_path": "src/config.py"}
        """
        return await security_check_file(file_path)

    return [
        "security_scan_project",
        "security_check_dependencies",
        "security_detect_secrets",
        "security_sbom",
        "security_quick_check",
    ]

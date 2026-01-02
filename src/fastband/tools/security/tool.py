"""
Security Tool - Comprehensive security scanning with ambient context.

Provides unified security scanning with:
- Dependency vulnerability scanning (SCA)
- Secret detection in source code
- SBOM generation for compliance
- CodebaseContext integration for impact analysis
"""

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fastband.context import (
    CodebaseContext,
    get_codebase_context,
)
from fastband.tools.security.dependencies import DependencyScanner
from fastband.tools.security.models import (
    SBOM,
    DependencyInfo,
    SecretFinding,
    SecurityReport,
    Vulnerability,
    VulnerabilitySeverity,
    VulnerabilityType,
)
from fastband.tools.security.secrets import SecretsScanner

logger = logging.getLogger(__name__)


@dataclass
class SecurityConfig:
    """Configuration for security scanning."""

    # Scan types
    scan_dependencies: bool = True
    scan_secrets: bool = True
    generate_sbom: bool = False

    # Severity filtering
    min_severity: VulnerabilitySeverity = VulnerabilitySeverity.LOW
    fail_on_critical: bool = True
    fail_on_high: bool = False

    # Scope
    include_dev_dependencies: bool = True
    scan_test_files: bool = True

    # Context integration
    use_context: bool = True
    prioritize_by_risk: bool = True

    # Output
    max_findings: int = 200
    sbom_format: str = "cyclonedx"  # cyclonedx, spdx


class SecurityTool:
    """
    Comprehensive security scanning tool.

    Integrates dependency scanning, secret detection, and SBOM generation
    with CodebaseContext for intelligent risk assessment.
    """

    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.dep_scanner = DependencyScanner(str(self.project_root))
        self.secrets_scanner = SecretsScanner(str(self.project_root))
        self._context: CodebaseContext | None = None

    async def get_context(self) -> CodebaseContext:
        """Get or create CodebaseContext."""
        if self._context is None:
            self._context = await get_codebase_context(str(self.project_root))
        return self._context

    async def close(self):
        """Clean up resources."""
        await self.dep_scanner.close()

    # =========================================================================
    # MAIN SCAN METHODS
    # =========================================================================

    async def scan(
        self,
        config: SecurityConfig | None = None,
    ) -> SecurityReport:
        """
        Run comprehensive security scan.

        Args:
            config: Scan configuration

        Returns:
            SecurityReport with all findings
        """
        config = config or SecurityConfig()
        start_time = time.time()

        report = SecurityReport(
            report_id=str(uuid.uuid4())[:8],
            project_root=str(self.project_root),
        )

        # Run scans in parallel where possible
        tasks = []

        if config.scan_dependencies:
            tasks.append(("deps", self._scan_dependencies(config)))

        if config.scan_secrets:
            tasks.append(("secrets", self._scan_secrets(config)))

        # Execute scans
        results = {}
        for name, task in tasks:
            try:
                results[name] = await task
            except Exception as e:
                logger.error(f"Security scan {name} failed: {e}")
                results[name] = None

        # Process dependency results
        if results.get("deps"):
            deps, manifests = results["deps"]
            report.manifests_scanned = manifests
            report.dependencies = deps
            report.total_dependencies = len(deps)
            report.vulnerable_dependencies = sum(1 for d in deps if d.has_vulnerabilities)

            for dep in deps:
                for vuln in dep.vulnerabilities:
                    report.add_vulnerability(vuln)

        # Process secret results
        if results.get("secrets"):
            secrets = results["secrets"]
            for secret in secrets:
                report.add_secret(secret)
                if secret.location:
                    if secret.location.file not in report.files_scanned:
                        report.files_scanned.append(secret.location.file)

        # Generate SBOM if requested
        if config.generate_sbom and report.dependencies:
            report.sbom = self.dep_scanner.generate_sbom(
                report.dependencies,
                project_name=self.project_root.name,
            )

        # Enrich with context
        if config.use_context:
            await self._enrich_with_context(report)

        # Calculate timing
        report.scan_time_ms = int((time.time() - start_time) * 1000)

        return report

    async def scan_dependencies(
        self,
        config: SecurityConfig | None = None,
    ) -> SecurityReport:
        """Scan only dependencies for vulnerabilities."""
        config = config or SecurityConfig()
        config.scan_secrets = False
        return await self.scan(config)

    async def scan_secrets(
        self,
        config: SecurityConfig | None = None,
    ) -> SecurityReport:
        """Scan only for exposed secrets."""
        config = config or SecurityConfig()
        config.scan_dependencies = False
        return await self.scan(config)

    async def scan_file(
        self,
        file_path: str,
        config: SecurityConfig | None = None,
    ) -> SecurityReport:
        """Scan a single file for secrets."""
        config = config or SecurityConfig()
        start_time = time.time()

        report = SecurityReport(
            report_id=str(uuid.uuid4())[:8],
            project_root=str(self.project_root),
            files_scanned=[file_path],
        )

        secrets = self.secrets_scanner.scan_file(file_path)
        for secret in secrets:
            report.add_secret(secret)

        if config.use_context:
            await self._enrich_with_context(report)

        report.scan_time_ms = int((time.time() - start_time) * 1000)
        return report

    async def generate_sbom(
        self,
        format: str = "cyclonedx",
    ) -> SBOM:
        """Generate Software Bill of Materials."""
        deps, _ = await self.dep_scanner.scan()
        return self.dep_scanner.generate_sbom(
            deps,
            project_name=self.project_root.name,
        )

    # =========================================================================
    # INTERNAL SCAN METHODS
    # =========================================================================

    async def _scan_dependencies(
        self,
        config: SecurityConfig,
    ) -> tuple[list[DependencyInfo], list[str]]:
        """Run dependency vulnerability scan."""
        return await self.dep_scanner.scan()

    async def _scan_secrets(
        self,
        config: SecurityConfig,
    ) -> list[SecretFinding]:
        """Run secret detection scan."""
        # Run in thread pool since it's CPU-bound
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.secrets_scanner.scan)

    async def _enrich_with_context(self, report: SecurityReport) -> None:
        """Enrich report with CodebaseContext information."""
        try:
            context = await self.get_context()

            high_risk_files = set()

            for vuln in report.vulnerabilities:
                if vuln.location:
                    file_ctx = await context.get_file_context(vuln.location.file)
                    if file_ctx:
                        vuln.file_risk_level = file_ctx.risk_level
                        if file_ctx.risk_level in ["high", "critical"]:
                            high_risk_files.add(vuln.location.file)

                        # Get affected files
                        if file_ctx.impact_graph:
                            vuln.affected_files = list(file_ctx.impact_graph.imported_by)[:5]

                            # Check if on critical path
                            if file_ctx.impact_graph.is_on_critical_path:
                                report.critical_path_affected = True

            report.high_risk_files = list(high_risk_files)

        except Exception as e:
            logger.debug(f"Failed to enrich with context: {e}")

    # =========================================================================
    # UTILITY METHODS
    # =========================================================================

    def get_severity_counts(self, report: SecurityReport) -> dict[str, int]:
        """Get vulnerability counts by severity."""
        return {
            "critical": report.critical_count,
            "high": report.high_count,
            "medium": report.medium_count,
            "low": report.low_count,
        }

    def passes_policy(
        self,
        report: SecurityReport,
        config: SecurityConfig,
    ) -> tuple[bool, list[str]]:
        """
        Check if scan results pass security policy.

        Returns:
            Tuple of (passes, list of failure reasons)
        """
        failures = []

        if config.fail_on_critical and report.critical_count > 0:
            failures.append(f"Found {report.critical_count} critical vulnerabilities")

        if config.fail_on_high and report.high_count > 0:
            failures.append(f"Found {report.high_count} high severity vulnerabilities")

        return len(failures) == 0, failures


# =========================================================================
# MCP TOOL DEFINITIONS
# =========================================================================

async def security_scan(
    path: str = ".",
    scan_type: str = "all",
    min_severity: str = "low",
    generate_sbom: bool = False,
) -> dict[str, Any]:
    """
    Run security scan on project.

    Args:
        path: Project path to scan
        scan_type: Type of scan - "all", "dependencies", "secrets"
        min_severity: Minimum severity to report - "critical", "high", "medium", "low"
        generate_sbom: Generate Software Bill of Materials

    Returns:
        Security report with findings
    """
    import os

    if os.path.isabs(path):
        project_root = path
    else:
        project_root = os.getcwd()

    tool = SecurityTool(project_root)

    try:
        config = SecurityConfig(
            scan_dependencies=scan_type in ["all", "dependencies"],
            scan_secrets=scan_type in ["all", "secrets"],
            min_severity=VulnerabilitySeverity(min_severity.lower()),
            generate_sbom=generate_sbom,
        )

        report = await tool.scan(config)

        result = {
            "type": "security_report",
            **report.to_summary(),
            "markdown": report.to_markdown(),
        }

        if report.sbom:
            result["sbom"] = report.sbom.to_cyclonedx()

        # Add policy check
        passes, failures = tool.passes_policy(report, config)
        result["policy_passed"] = passes
        result["policy_failures"] = failures

        return result

    finally:
        await tool.close()


async def security_scan_dependencies(
    path: str = ".",
    include_dev: bool = True,
) -> dict[str, Any]:
    """
    Scan project dependencies for known vulnerabilities.

    Uses OSV (Open Source Vulnerabilities) database to check
    packages in requirements.txt, package.json, go.mod, etc.

    Args:
        path: Project path to scan
        include_dev: Include dev dependencies

    Returns:
        Dependency vulnerability report
    """
    import os

    if os.path.isabs(path):
        project_root = path
    else:
        project_root = os.getcwd()

    tool = SecurityTool(project_root)

    try:
        config = SecurityConfig(
            scan_dependencies=True,
            scan_secrets=False,
            include_dev_dependencies=include_dev,
        )

        report = await tool.scan(config)

        # Build dependency summary
        vuln_deps = [d for d in report.dependencies if d.has_vulnerabilities]

        return {
            "type": "dependency_scan",
            "total_dependencies": report.total_dependencies,
            "vulnerable_dependencies": report.vulnerable_dependencies,
            "manifests_scanned": report.manifests_scanned,
            "vulnerabilities": {
                "critical": report.critical_count,
                "high": report.high_count,
                "medium": report.medium_count,
                "low": report.low_count,
            },
            "vulnerable_packages": [
                {
                    "name": d.name,
                    "version": d.version,
                    "ecosystem": d.ecosystem,
                    "severity": d.max_severity.value,
                    "vulns": [
                        {
                            "id": v.cve_id or v.vuln_id,
                            "title": v.title,
                            "fixed_in": v.fixed_version,
                        }
                        for v in d.vulnerabilities
                    ],
                }
                for d in vuln_deps[:20]
            ],
            "scan_time_ms": report.scan_time_ms,
        }

    finally:
        await tool.close()


async def security_scan_secrets(
    path: str = ".",
    include_tests: bool = False,
) -> dict[str, Any]:
    """
    Scan source code for exposed secrets.

    Detects API keys, tokens, passwords, and private keys
    using pattern matching and entropy analysis.

    Args:
        path: Project path to scan
        include_tests: Include test files in scan

    Returns:
        Secret detection report
    """
    import os

    if os.path.isabs(path):
        project_root = path
    else:
        project_root = os.getcwd()

    tool = SecurityTool(project_root)

    try:
        config = SecurityConfig(
            scan_dependencies=False,
            scan_secrets=True,
            scan_test_files=include_tests,
        )

        report = await tool.scan(config)

        return {
            "type": "secrets_scan",
            "secrets_found": len(report.secrets),
            "files_scanned": len(report.files_scanned),
            "severity_counts": {
                "critical": report.critical_count,
                "high": report.high_count,
                "medium": report.medium_count,
                "low": report.low_count,
            },
            "findings": [
                {
                    "type": s.secret_type.value,
                    "severity": s.severity.value,
                    "file": s.location.to_string(),
                    "confidence": round(s.confidence, 2),
                    "is_test_file": s.is_test_file,
                    "remediation": s.remediation,
                }
                for s in report.secrets[:30]
            ],
            "high_risk_files": report.high_risk_files,
            "scan_time_ms": report.scan_time_ms,
        }

    finally:
        await tool.close()


async def security_generate_sbom(
    path: str = ".",
    format: str = "cyclonedx",
) -> dict[str, Any]:
    """
    Generate Software Bill of Materials (SBOM).

    Creates a comprehensive inventory of all project dependencies
    for compliance and security audit purposes.

    Args:
        path: Project path
        format: Output format - "cyclonedx" or "spdx"

    Returns:
        SBOM in requested format
    """
    import os

    if os.path.isabs(path):
        project_root = path
    else:
        project_root = os.getcwd()

    tool = SecurityTool(project_root)

    try:
        sbom = await tool.generate_sbom(format=format)

        if format == "spdx":
            sbom_data = sbom.to_spdx()
        else:
            sbom_data = sbom.to_cyclonedx()

        return {
            "type": "sbom",
            "format": format,
            "project_name": sbom.project_name,
            "total_components": sbom.total_components,
            "direct_dependencies": sbom.direct_dependencies,
            "transitive_dependencies": sbom.transitive_dependencies,
            "vulnerable_components": sbom.vulnerable_components,
            "sbom": sbom_data,
        }

    finally:
        await tool.close()


async def security_check_file(file_path: str) -> dict[str, Any]:
    """
    Quick security check for a single file.

    Scans for exposed secrets and returns pass/fail status.

    Args:
        file_path: Path to file to check

    Returns:
        Quick check result with pass/fail
    """
    import os

    project_root = os.path.dirname(file_path) if os.path.isabs(file_path) else os.getcwd()
    tool = SecurityTool(project_root)

    try:
        report = await tool.scan_file(file_path)

        passed = report.critical_count == 0 and report.high_count == 0

        return {
            "passed": passed,
            "status": "pass" if passed else "fail",
            "file": file_path,
            "secrets_found": len(report.secrets),
            "critical": report.critical_count,
            "high": report.high_count,
            "findings": [
                {
                    "type": s.secret_type.value,
                    "line": s.location.line,
                    "severity": s.severity.value,
                }
                for s in report.secrets[:10]
            ],
        }

    finally:
        await tool.close()

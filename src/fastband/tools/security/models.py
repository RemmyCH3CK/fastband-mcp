"""
Security Models - Data structures for security analysis.

Defines standardized representations for:
- Vulnerability findings (dependencies, code, secrets)
- SBOM (Software Bill of Materials)
- Security reports with risk assessment
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class VulnerabilitySeverity(str, Enum):
    """CVSS-aligned severity levels."""

    CRITICAL = "critical"  # CVSS 9.0-10.0
    HIGH = "high"          # CVSS 7.0-8.9
    MEDIUM = "medium"      # CVSS 4.0-6.9
    LOW = "low"            # CVSS 0.1-3.9
    UNKNOWN = "unknown"    # No CVSS available


class VulnerabilityType(str, Enum):
    """Types of security vulnerabilities."""

    # Dependency vulnerabilities
    DEPENDENCY = "dependency"
    OUTDATED = "outdated"
    MALICIOUS = "malicious"
    LICENSE = "license"

    # Secret leaks
    SECRET_API_KEY = "secret_api_key"
    SECRET_PASSWORD = "secret_password"
    SECRET_TOKEN = "secret_token"
    SECRET_PRIVATE_KEY = "secret_private_key"
    SECRET_CERTIFICATE = "secret_certificate"
    SECRET_GENERIC = "secret_generic"

    # Code vulnerabilities (SAST)
    INJECTION_SQL = "injection_sql"
    INJECTION_COMMAND = "injection_command"
    INJECTION_XSS = "injection_xss"
    INJECTION_PATH = "injection_path"
    AUTH_WEAKNESS = "auth_weakness"
    CRYPTO_WEAKNESS = "crypto_weakness"
    SENSITIVE_DATA = "sensitive_data"
    INSECURE_CONFIG = "insecure_config"


class SecretType(str, Enum):
    """Types of secrets that can be detected."""

    # Cloud providers
    AWS_ACCESS_KEY = "aws_access_key"
    AWS_SECRET_KEY = "aws_secret_key"
    GCP_API_KEY = "gcp_api_key"
    GCP_SERVICE_ACCOUNT = "gcp_service_account"
    AZURE_KEY = "azure_key"

    # Payment/Financial
    STRIPE_KEY = "stripe_key"
    STRIPE_SECRET = "stripe_secret"
    PAYPAL_KEY = "paypal_key"

    # Communication
    SLACK_TOKEN = "slack_token"
    SLACK_WEBHOOK = "slack_webhook"
    DISCORD_TOKEN = "discord_token"
    TWILIO_KEY = "twilio_key"
    SENDGRID_KEY = "sendgrid_key"

    # Database
    DATABASE_URL = "database_url"
    MONGODB_URI = "mongodb_uri"
    REDIS_URL = "redis_url"

    # Version Control
    GITHUB_TOKEN = "github_token"
    GITLAB_TOKEN = "gitlab_token"
    BITBUCKET_TOKEN = "bitbucket_token"

    # Auth
    JWT_SECRET = "jwt_secret"
    OAUTH_SECRET = "oauth_secret"
    API_KEY_GENERIC = "api_key_generic"

    # Crypto
    PRIVATE_KEY_RSA = "private_key_rsa"
    PRIVATE_KEY_EC = "private_key_ec"
    PRIVATE_KEY_SSH = "private_key_ssh"
    CERTIFICATE = "certificate"

    # Other
    PASSWORD = "password"
    GENERIC_SECRET = "generic_secret"


@dataclass
class SourceLocation:
    """Location in source code."""

    file: str
    line: int
    column: int = 0
    end_line: int | None = None
    end_column: int | None = None

    def to_string(self) -> str:
        """Format as file:line:column."""
        if self.column:
            return f"{self.file}:{self.line}:{self.column}"
        return f"{self.file}:{self.line}"


@dataclass
class Vulnerability:
    """
    A security vulnerability finding.

    Unified format for dependency, secret, and code vulnerabilities.
    """

    # Identity
    vuln_id: str
    vuln_type: VulnerabilityType
    severity: VulnerabilitySeverity

    # Description
    title: str
    description: str
    detail: str | None = None

    # Location
    location: SourceLocation | None = None
    package_name: str | None = None  # For dependency vulns
    package_version: str | None = None

    # References
    cve_id: str | None = None  # CVE-2024-XXXX
    cwe_id: str | None = None  # CWE-79
    cvss_score: float | None = None
    cvss_vector: str | None = None
    references: list[str] = field(default_factory=list)

    # Remediation
    fix_available: bool = False
    fixed_version: str | None = None
    remediation: str | None = None

    # Context (from CodebaseContext)
    file_risk_level: str | None = None
    affected_files: list[str] = field(default_factory=list)
    is_reachable: bool | None = None  # For deps: is the vuln code actually called?

    # For secrets
    secret_type: SecretType | None = None
    secret_entropy: float | None = None  # Higher = more likely real secret
    is_test_file: bool = False
    is_example: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "vuln_id": self.vuln_id,
            "type": self.vuln_type.value,
            "severity": self.severity.value,
            "title": self.title,
            "description": self.description,
            "location": self.location.to_string() if self.location else None,
            "package": f"{self.package_name}@{self.package_version}" if self.package_name else None,
            "cve_id": self.cve_id,
            "cvss_score": self.cvss_score,
            "fix_available": self.fix_available,
            "fixed_version": self.fixed_version,
        }


@dataclass
class DependencyInfo:
    """Information about a project dependency."""

    name: str
    version: str
    ecosystem: str  # npm, pypi, go, cargo, maven
    direct: bool = True  # Direct or transitive dependency

    # Source file
    manifest_file: str = ""  # package.json, requirements.txt, etc.
    lock_file: str | None = None  # package-lock.json, etc.

    # Metadata
    license: str | None = None
    description: str | None = None
    homepage: str | None = None
    repository: str | None = None

    # Vulnerability info
    vulnerabilities: list[Vulnerability] = field(default_factory=list)
    is_deprecated: bool = False
    is_outdated: bool = False
    latest_version: str | None = None

    @property
    def has_vulnerabilities(self) -> bool:
        return len(self.vulnerabilities) > 0

    @property
    def max_severity(self) -> VulnerabilitySeverity:
        """Get highest severity among vulnerabilities."""
        if not self.vulnerabilities:
            return VulnerabilitySeverity.UNKNOWN
        severity_order = [
            VulnerabilitySeverity.UNKNOWN,
            VulnerabilitySeverity.LOW,
            VulnerabilitySeverity.MEDIUM,
            VulnerabilitySeverity.HIGH,
            VulnerabilitySeverity.CRITICAL,
        ]
        return max(
            (v.severity for v in self.vulnerabilities),
            key=lambda s: severity_order.index(s),
        )


@dataclass
class SecretFinding:
    """A detected secret in source code."""

    secret_id: str
    secret_type: SecretType
    severity: VulnerabilitySeverity

    # Location
    location: SourceLocation
    line_content: str  # The line containing the secret (redacted)
    match_text: str  # The matched pattern (redacted)

    # Analysis
    entropy: float = 0.0  # Shannon entropy (higher = more random = likely real)
    confidence: float = 0.0  # Detection confidence 0-1

    # Context
    is_test_file: bool = False
    is_example: bool = False
    is_env_file: bool = False
    is_gitignored: bool = False

    # From CodebaseContext
    file_risk_level: str | None = None
    file_is_public: bool = False  # Is this file likely to be public?

    # Remediation
    already_rotated: bool = False
    remediation: str | None = None

    def to_vulnerability(self) -> Vulnerability:
        """Convert to unified Vulnerability format."""
        # Map secret types to vulnerability types
        type_map = {
            SecretType.AWS_ACCESS_KEY: VulnerabilityType.SECRET_API_KEY,
            SecretType.AWS_SECRET_KEY: VulnerabilityType.SECRET_API_KEY,
            SecretType.GCP_API_KEY: VulnerabilityType.SECRET_API_KEY,
            SecretType.GCP_SERVICE_ACCOUNT: VulnerabilityType.SECRET_API_KEY,
            SecretType.AZURE_KEY: VulnerabilityType.SECRET_API_KEY,
            SecretType.STRIPE_KEY: VulnerabilityType.SECRET_API_KEY,
            SecretType.STRIPE_SECRET: VulnerabilityType.SECRET_API_KEY,
            SecretType.PAYPAL_KEY: VulnerabilityType.SECRET_API_KEY,
            SecretType.SLACK_TOKEN: VulnerabilityType.SECRET_TOKEN,
            SecretType.SLACK_WEBHOOK: VulnerabilityType.SECRET_TOKEN,
            SecretType.DISCORD_TOKEN: VulnerabilityType.SECRET_TOKEN,
            SecretType.TWILIO_KEY: VulnerabilityType.SECRET_API_KEY,
            SecretType.SENDGRID_KEY: VulnerabilityType.SECRET_API_KEY,
            SecretType.DATABASE_URL: VulnerabilityType.SECRET_PASSWORD,
            SecretType.MONGODB_URI: VulnerabilityType.SECRET_PASSWORD,
            SecretType.REDIS_URL: VulnerabilityType.SECRET_PASSWORD,
            SecretType.GITHUB_TOKEN: VulnerabilityType.SECRET_TOKEN,
            SecretType.GITLAB_TOKEN: VulnerabilityType.SECRET_TOKEN,
            SecretType.BITBUCKET_TOKEN: VulnerabilityType.SECRET_TOKEN,
            SecretType.JWT_SECRET: VulnerabilityType.SECRET_TOKEN,
            SecretType.OAUTH_SECRET: VulnerabilityType.SECRET_TOKEN,
            SecretType.API_KEY_GENERIC: VulnerabilityType.SECRET_API_KEY,
            SecretType.PRIVATE_KEY_RSA: VulnerabilityType.SECRET_PRIVATE_KEY,
            SecretType.PRIVATE_KEY_EC: VulnerabilityType.SECRET_PRIVATE_KEY,
            SecretType.PRIVATE_KEY_SSH: VulnerabilityType.SECRET_PRIVATE_KEY,
            SecretType.CERTIFICATE: VulnerabilityType.SECRET_CERTIFICATE,
            SecretType.PASSWORD: VulnerabilityType.SECRET_PASSWORD,
            SecretType.GENERIC_SECRET: VulnerabilityType.SECRET_GENERIC,
        }
        vuln_type = type_map.get(self.secret_type, VulnerabilityType.SECRET_GENERIC)

        return Vulnerability(
            vuln_id=self.secret_id,
            vuln_type=vuln_type,
            severity=self.severity,
            title=f"Exposed {self.secret_type.value.replace('_', ' ').title()}",
            description=f"Detected potential {self.secret_type.value} in source code",
            detail=f"Found in {self.location.to_string()}",
            location=self.location,
            secret_type=self.secret_type,
            secret_entropy=self.entropy,
            is_test_file=self.is_test_file,
            is_example=self.is_example,
            remediation=self.remediation or "Rotate this credential immediately and remove from source code",
        )


@dataclass
class SBOMComponent:
    """A component in the Software Bill of Materials."""

    # Identity (following CycloneDX/SPDX)
    name: str
    version: str
    purl: str  # Package URL (pkg:npm/lodash@4.17.21)

    # Type
    component_type: str = "library"  # library, framework, application, device, etc.
    ecosystem: str = ""  # npm, pypi, go, cargo

    # Source
    manifest_file: str = ""
    is_direct: bool = True

    # Metadata
    license: str | None = None
    license_spdx: str | None = None  # SPDX identifier
    author: str | None = None
    description: str | None = None

    # Hashes
    sha256: str | None = None
    sha1: str | None = None
    md5: str | None = None

    # External references
    homepage: str | None = None
    repository: str | None = None
    download_url: str | None = None

    # Security
    vulnerabilities: list[Vulnerability] = field(default_factory=list)


@dataclass
class SBOM:
    """Software Bill of Materials."""

    # Identity
    sbom_id: str
    created_at: datetime = field(default_factory=_utc_now)
    format: str = "cyclonedx"  # cyclonedx, spdx
    spec_version: str = "1.5"

    # Project info
    project_name: str = ""
    project_version: str = ""
    project_root: str = ""

    # Components
    components: list[SBOMComponent] = field(default_factory=list)

    # Statistics
    total_components: int = 0
    direct_dependencies: int = 0
    transitive_dependencies: int = 0
    vulnerable_components: int = 0

    def to_cyclonedx(self) -> dict[str, Any]:
        """Export as CycloneDX format."""
        return {
            "bomFormat": "CycloneDX",
            "specVersion": self.spec_version,
            "serialNumber": f"urn:uuid:{self.sbom_id}",
            "version": 1,
            "metadata": {
                "timestamp": self.created_at.isoformat(),
                "component": {
                    "name": self.project_name,
                    "version": self.project_version,
                    "type": "application",
                },
            },
            "components": [
                {
                    "type": c.component_type,
                    "name": c.name,
                    "version": c.version,
                    "purl": c.purl,
                    "licenses": [{"license": {"id": c.license_spdx}}] if c.license_spdx else [],
                    "hashes": [{"alg": "SHA-256", "content": c.sha256}] if c.sha256 else [],
                }
                for c in self.components
            ],
        }

    def to_spdx(self) -> dict[str, Any]:
        """Export as SPDX format."""
        return {
            "spdxVersion": "SPDX-2.3",
            "dataLicense": "CC0-1.0",
            "SPDXID": f"SPDXRef-{self.sbom_id}",
            "name": self.project_name,
            "creationInfo": {
                "created": self.created_at.isoformat(),
                "creators": ["Tool: fastband-security"],
            },
            "packages": [
                {
                    "SPDXID": f"SPDXRef-Package-{c.name}-{c.version}",
                    "name": c.name,
                    "versionInfo": c.version,
                    "downloadLocation": c.download_url or "NOASSERTION",
                    "licenseConcluded": c.license_spdx or "NOASSERTION",
                    "externalRefs": [
                        {
                            "referenceCategory": "PACKAGE_MANAGER",
                            "referenceType": "purl",
                            "referenceLocator": c.purl,
                        }
                    ],
                }
                for c in self.components
            ],
        }


@dataclass
class SecurityReport:
    """
    Complete security analysis report.

    Aggregates all vulnerability findings across dependencies,
    secrets, and code analysis.
    """

    # Identity
    report_id: str
    created_at: datetime = field(default_factory=_utc_now)

    # Scope
    project_root: str = ""
    files_scanned: list[str] = field(default_factory=list)
    manifests_scanned: list[str] = field(default_factory=list)

    # Findings
    vulnerabilities: list[Vulnerability] = field(default_factory=list)
    secrets: list[SecretFinding] = field(default_factory=list)
    dependencies: list[DependencyInfo] = field(default_factory=list)

    # SBOM
    sbom: SBOM | None = None

    # Counts by severity
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0

    # Counts by type
    dependency_vulns: int = 0
    secret_findings: int = 0
    code_vulns: int = 0

    # Statistics
    total_dependencies: int = 0
    vulnerable_dependencies: int = 0
    outdated_dependencies: int = 0

    # Performance
    scan_time_ms: int = 0

    # Context
    high_risk_files: list[str] = field(default_factory=list)
    critical_path_affected: bool = False

    def add_vulnerability(self, vuln: Vulnerability) -> None:
        """Add a vulnerability and update counts."""
        self.vulnerabilities.append(vuln)

        # Update severity counts
        if vuln.severity == VulnerabilitySeverity.CRITICAL:
            self.critical_count += 1
        elif vuln.severity == VulnerabilitySeverity.HIGH:
            self.high_count += 1
        elif vuln.severity == VulnerabilitySeverity.MEDIUM:
            self.medium_count += 1
        elif vuln.severity == VulnerabilitySeverity.LOW:
            self.low_count += 1

        # Update type counts
        if vuln.vuln_type == VulnerabilityType.DEPENDENCY:
            self.dependency_vulns += 1
        elif vuln.vuln_type.value.startswith("secret_"):
            self.secret_findings += 1
        else:
            self.code_vulns += 1

    def add_secret(self, secret: SecretFinding) -> None:
        """Add a secret finding and update counts."""
        self.secrets.append(secret)
        self.add_vulnerability(secret.to_vulnerability())

    @property
    def total_findings(self) -> int:
        return len(self.vulnerabilities)

    @property
    def has_critical(self) -> bool:
        return self.critical_count > 0

    @property
    def risk_score(self) -> int:
        """Calculate overall risk score (0-100)."""
        score = 0
        score += self.critical_count * 25
        score += self.high_count * 10
        score += self.medium_count * 3
        score += self.low_count * 1
        return min(100, score)

    def get_by_severity(self, severity: VulnerabilitySeverity) -> list[Vulnerability]:
        """Get vulnerabilities by severity."""
        return [v for v in self.vulnerabilities if v.severity == severity]

    def get_actionable(self) -> list[Vulnerability]:
        """Get vulnerabilities that have fixes available."""
        return [v for v in self.vulnerabilities if v.fix_available]

    def to_summary(self) -> dict[str, Any]:
        """Generate summary for agent consumption."""
        return {
            "report_id": self.report_id,
            "risk_score": self.risk_score,
            "total_findings": self.total_findings,
            "critical": self.critical_count,
            "high": self.high_count,
            "medium": self.medium_count,
            "low": self.low_count,
            "dependency_vulns": self.dependency_vulns,
            "secret_findings": self.secret_findings,
            "code_vulns": self.code_vulns,
            "total_dependencies": self.total_dependencies,
            "vulnerable_dependencies": self.vulnerable_dependencies,
            "actionable_fixes": len(self.get_actionable()),
            "scan_time_ms": self.scan_time_ms,
        }

    def to_markdown(self) -> str:
        """Generate markdown report."""
        lines = [
            "# Security Scan Report",
            "",
            f"**Report ID:** {self.report_id}",
            f"**Generated:** {self.created_at.strftime('%Y-%m-%d %H:%M:%S')} UTC",
            f"**Risk Score:** {self.risk_score}/100",
            "",
            "## Summary",
            "",
            "| Severity | Count |",
            "|----------|-------|",
            f"| Critical | {self.critical_count} |",
            f"| High | {self.high_count} |",
            f"| Medium | {self.medium_count} |",
            f"| Low | {self.low_count} |",
            "",
            "| Category | Count |",
            "|----------|-------|",
            f"| Dependency Vulnerabilities | {self.dependency_vulns} |",
            f"| Secret Findings | {self.secret_findings} |",
            f"| Code Vulnerabilities | {self.code_vulns} |",
            "",
        ]

        if self.critical_count > 0:
            lines.extend([
                "## Critical Vulnerabilities",
                "",
            ])
            for vuln in self.get_by_severity(VulnerabilitySeverity.CRITICAL):
                lines.append(f"- **{vuln.title}**")
                if vuln.cve_id:
                    lines.append(f"  - CVE: {vuln.cve_id}")
                if vuln.package_name:
                    lines.append(f"  - Package: {vuln.package_name}@{vuln.package_version}")
                if vuln.fixed_version:
                    lines.append(f"  - Fix: Upgrade to {vuln.fixed_version}")
                lines.append("")

        if self.high_count > 0:
            lines.extend([
                "## High Severity",
                "",
            ])
            for vuln in self.get_by_severity(VulnerabilitySeverity.HIGH)[:10]:
                fix_note = f" (fix: {vuln.fixed_version})" if vuln.fixed_version else ""
                lines.append(f"- {vuln.title}{fix_note}")
            lines.append("")

        if self.secrets:
            lines.extend([
                "## Exposed Secrets",
                "",
            ])
            for secret in self.secrets[:10]:
                lines.append(f"- **{secret.secret_type.value}** in `{secret.location.to_string()}`")
            lines.append("")

        actionable = self.get_actionable()
        if actionable:
            lines.extend([
                "## Recommended Actions",
                "",
            ])
            for vuln in actionable[:10]:
                if vuln.fixed_version:
                    lines.append(f"- Upgrade `{vuln.package_name}` to `{vuln.fixed_version}`")
                elif vuln.remediation:
                    lines.append(f"- {vuln.remediation}")
            lines.append("")

        return "\n".join(lines)

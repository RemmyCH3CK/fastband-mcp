"""
Secrets Detection Scanner.

Detects exposed secrets in source code using:
- Pattern matching (regex) for known secret formats
- Entropy analysis for high-randomness strings
- Context analysis to reduce false positives

Supports detection of:
- API keys (AWS, GCP, Azure, Stripe, etc.)
- Tokens (GitHub, Slack, Discord, etc.)
- Private keys (RSA, EC, SSH)
- Database connection strings
- Generic passwords and secrets
"""

import logging
import math
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastband.tools.security.models import (
    SecretFinding,
    SecretType,
    SourceLocation,
    VulnerabilitySeverity,
)

logger = logging.getLogger(__name__)


@dataclass
class SecretPattern:
    """A pattern for detecting a specific type of secret."""

    secret_type: SecretType
    pattern: re.Pattern
    severity: VulnerabilitySeverity
    description: str
    entropy_threshold: float = 3.0  # Minimum entropy to consider
    min_length: int = 8
    max_length: int = 500


class SecretsScanner:
    """
    Scans source code for exposed secrets.

    Uses multiple detection methods:
    1. Regex patterns for known secret formats
    2. Entropy analysis for random-looking strings
    3. Context analysis (variable names, file types)
    """

    # File extensions to scan
    SCANNABLE_EXTENSIONS = {
        ".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".rs", ".rb", ".php",
        ".java", ".kt", ".scala", ".cs", ".cpp", ".c", ".h", ".hpp",
        ".sh", ".bash", ".zsh", ".ps1", ".bat", ".cmd",
        ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf",
        ".env", ".env.local", ".env.development", ".env.production",
        ".xml", ".properties", ".gradle", ".tf", ".tfvars",
        ".dockerfile", ".sql", ".graphql",
    }

    # Files/directories to skip
    SKIP_PATTERNS = {
        "node_modules", ".venv", "venv", "__pycache__", ".git",
        "dist", "build", ".next", ".nuxt", "coverage",
        "*.min.js", "*.bundle.js", "*.map",
        "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
        "poetry.lock", "Pipfile.lock", "Cargo.lock",
    }

    # Test/example file patterns (lower severity)
    TEST_PATTERNS = {
        "test", "spec", "mock", "fake", "stub", "fixture",
        "example", "sample", "demo", "dummy",
    }

    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.patterns = self._build_patterns()

    def _build_patterns(self) -> list[SecretPattern]:
        """Build the list of secret detection patterns."""
        return [
            # AWS
            SecretPattern(
                secret_type=SecretType.AWS_ACCESS_KEY,
                pattern=re.compile(r"(?:A3T[A-Z0-9]|AKIA|AGPA|AIDA|AROA|AIPA|ANPA|ANVA|ASIA)[A-Z0-9]{16}"),
                severity=VulnerabilitySeverity.CRITICAL,
                description="AWS Access Key ID",
                min_length=20,
                max_length=20,
            ),
            SecretPattern(
                secret_type=SecretType.AWS_SECRET_KEY,
                pattern=re.compile(r"(?i)aws[_\-]?secret[_\-]?(?:access[_\-]?)?key['\"]?\s*[:=]\s*['\"]?([A-Za-z0-9/+=]{40})['\"]?"),
                severity=VulnerabilitySeverity.CRITICAL,
                description="AWS Secret Access Key",
                min_length=40,
                max_length=40,
            ),

            # GCP
            SecretPattern(
                secret_type=SecretType.GCP_API_KEY,
                pattern=re.compile(r"AIza[0-9A-Za-z\-_]{35}"),
                severity=VulnerabilitySeverity.HIGH,
                description="Google Cloud API Key",
            ),
            SecretPattern(
                secret_type=SecretType.GCP_SERVICE_ACCOUNT,
                pattern=re.compile(r'"type"\s*:\s*"service_account"'),
                severity=VulnerabilitySeverity.CRITICAL,
                description="GCP Service Account Key File",
            ),

            # GitHub
            SecretPattern(
                secret_type=SecretType.GITHUB_TOKEN,
                pattern=re.compile(r"ghp_[0-9a-zA-Z]{36}"),
                severity=VulnerabilitySeverity.HIGH,
                description="GitHub Personal Access Token",
            ),
            SecretPattern(
                secret_type=SecretType.GITHUB_TOKEN,
                pattern=re.compile(r"github_pat_[0-9a-zA-Z]{22}_[0-9a-zA-Z]{59}"),
                severity=VulnerabilitySeverity.HIGH,
                description="GitHub Fine-Grained PAT",
            ),
            SecretPattern(
                secret_type=SecretType.GITHUB_TOKEN,
                pattern=re.compile(r"gho_[0-9a-zA-Z]{36}"),
                severity=VulnerabilitySeverity.HIGH,
                description="GitHub OAuth Token",
            ),
            SecretPattern(
                secret_type=SecretType.GITHUB_TOKEN,
                pattern=re.compile(r"ghu_[0-9a-zA-Z]{36}"),
                severity=VulnerabilitySeverity.HIGH,
                description="GitHub User-to-Server Token",
            ),

            # Stripe
            SecretPattern(
                secret_type=SecretType.STRIPE_KEY,
                pattern=re.compile(r"pk_live_[0-9a-zA-Z]{24,}"),
                severity=VulnerabilitySeverity.MEDIUM,
                description="Stripe Publishable Key (Live)",
            ),
            SecretPattern(
                secret_type=SecretType.STRIPE_SECRET,
                pattern=re.compile(r"sk_live_[0-9a-zA-Z]{24,}"),
                severity=VulnerabilitySeverity.CRITICAL,
                description="Stripe Secret Key (Live)",
            ),
            SecretPattern(
                secret_type=SecretType.STRIPE_KEY,
                pattern=re.compile(r"rk_live_[0-9a-zA-Z]{24,}"),
                severity=VulnerabilitySeverity.HIGH,
                description="Stripe Restricted Key (Live)",
            ),

            # Slack
            SecretPattern(
                secret_type=SecretType.SLACK_TOKEN,
                pattern=re.compile(r"xox[baprs]-[0-9]{10,13}-[0-9]{10,13}[a-zA-Z0-9-]*"),
                severity=VulnerabilitySeverity.HIGH,
                description="Slack Token",
            ),
            SecretPattern(
                secret_type=SecretType.SLACK_WEBHOOK,
                pattern=re.compile(r"https://hooks\.slack\.com/services/T[A-Z0-9]+/B[A-Z0-9]+/[a-zA-Z0-9]+"),
                severity=VulnerabilitySeverity.MEDIUM,
                description="Slack Webhook URL",
            ),

            # Discord
            SecretPattern(
                secret_type=SecretType.DISCORD_TOKEN,
                pattern=re.compile(r"[MN][A-Za-z\d]{23,}\.[\w-]{6}\.[\w-]{27}"),
                severity=VulnerabilitySeverity.HIGH,
                description="Discord Bot Token",
            ),

            # Twilio
            SecretPattern(
                secret_type=SecretType.TWILIO_KEY,
                pattern=re.compile(r"SK[0-9a-fA-F]{32}"),
                severity=VulnerabilitySeverity.HIGH,
                description="Twilio API Key",
            ),

            # SendGrid
            SecretPattern(
                secret_type=SecretType.SENDGRID_KEY,
                pattern=re.compile(r"SG\.[a-zA-Z0-9_-]{22}\.[a-zA-Z0-9_-]{43}"),
                severity=VulnerabilitySeverity.HIGH,
                description="SendGrid API Key",
            ),

            # Private Keys
            SecretPattern(
                secret_type=SecretType.PRIVATE_KEY_RSA,
                pattern=re.compile(r"-----BEGIN (?:RSA )?PRIVATE KEY-----"),
                severity=VulnerabilitySeverity.CRITICAL,
                description="RSA Private Key",
            ),
            SecretPattern(
                secret_type=SecretType.PRIVATE_KEY_EC,
                pattern=re.compile(r"-----BEGIN EC PRIVATE KEY-----"),
                severity=VulnerabilitySeverity.CRITICAL,
                description="EC Private Key",
            ),
            SecretPattern(
                secret_type=SecretType.PRIVATE_KEY_SSH,
                pattern=re.compile(r"-----BEGIN OPENSSH PRIVATE KEY-----"),
                severity=VulnerabilitySeverity.CRITICAL,
                description="OpenSSH Private Key",
            ),

            # Database URLs
            SecretPattern(
                secret_type=SecretType.DATABASE_URL,
                pattern=re.compile(r"(?:postgres|postgresql|mysql|mongodb|redis)://[^\s'\"]+:[^\s'\"]+@[^\s'\"]+"),
                severity=VulnerabilitySeverity.CRITICAL,
                description="Database Connection URL with credentials",
            ),
            SecretPattern(
                secret_type=SecretType.MONGODB_URI,
                pattern=re.compile(r"mongodb(?:\+srv)?://[^\s'\"]+:[^\s'\"]+@[^\s'\"]+"),
                severity=VulnerabilitySeverity.CRITICAL,
                description="MongoDB Connection String",
            ),

            # JWT Secrets
            SecretPattern(
                secret_type=SecretType.JWT_SECRET,
                pattern=re.compile(r"(?i)jwt[_\-]?secret['\"]?\s*[:=]\s*['\"]?([A-Za-z0-9/+=_-]{20,})['\"]?"),
                severity=VulnerabilitySeverity.HIGH,
                description="JWT Secret",
                entropy_threshold=3.5,
            ),

            # Generic API Keys (high entropy required)
            SecretPattern(
                secret_type=SecretType.API_KEY_GENERIC,
                pattern=re.compile(r"(?i)(?:api[_\-]?key|apikey|api_secret|auth_token|access_token)['\"]?\s*[:=]\s*['\"]?([A-Za-z0-9/+=_-]{20,64})['\"]?"),
                severity=VulnerabilitySeverity.MEDIUM,
                description="Generic API Key",
                entropy_threshold=4.0,
            ),

            # Passwords in config
            SecretPattern(
                secret_type=SecretType.PASSWORD,
                pattern=re.compile(r"(?i)(?:password|passwd|pwd)['\"]?\s*[:=]\s*['\"]?([^\s'\"]{8,64})['\"]?"),
                severity=VulnerabilitySeverity.HIGH,
                description="Hardcoded Password",
                entropy_threshold=3.0,
            ),
        ]

    def _calculate_entropy(self, text: str) -> float:
        """Calculate Shannon entropy of a string."""
        if not text:
            return 0.0

        # Count character frequencies
        freq: dict[str, int] = {}
        for char in text:
            freq[char] = freq.get(char, 0) + 1

        # Calculate entropy
        length = len(text)
        entropy = 0.0
        for count in freq.values():
            if count > 0:
                prob = count / length
                entropy -= prob * math.log2(prob)

        return entropy

    def _is_test_file(self, file_path: str) -> bool:
        """Check if file is a test or example file."""
        path_lower = file_path.lower()
        return any(pattern in path_lower for pattern in self.TEST_PATTERNS)

    def _is_env_file(self, file_path: str) -> bool:
        """Check if file is an environment file."""
        basename = os.path.basename(file_path).lower()
        return basename.startswith(".env") or basename.endswith(".env")

    def _should_skip_file(self, file_path: str) -> bool:
        """Check if file should be skipped."""
        path_str = str(file_path)
        return any(skip in path_str for skip in self.SKIP_PATTERNS)

    def _should_scan_file(self, file_path: str) -> bool:
        """Check if file should be scanned based on extension."""
        ext = os.path.splitext(file_path)[1].lower()
        basename = os.path.basename(file_path).lower()

        # Always scan .env files
        if basename.startswith(".env"):
            return True

        return ext in self.SCANNABLE_EXTENSIONS

    def _redact_secret(self, text: str, keep_chars: int = 4) -> str:
        """Redact a secret, keeping only first/last few chars."""
        if len(text) <= keep_chars * 2:
            return "*" * len(text)
        return text[:keep_chars] + "*" * (len(text) - keep_chars * 2) + text[-keep_chars:]

    def _is_false_positive(
        self,
        match_text: str,
        line_content: str,
        file_path: str,
    ) -> bool:
        """Check if a match is likely a false positive."""
        line_lower = line_content.lower()
        match_lower = match_text.lower()

        # Skip if in a comment (basic check)
        stripped = line_content.strip()
        if stripped.startswith("#") or stripped.startswith("//") or stripped.startswith("/*"):
            # But not if it looks like a real secret
            if not any(c in match_text for c in "abcdefghijklmnopqrstuvwxyz"):
                return True

        # Skip common false positives
        false_positive_patterns = [
            "example", "sample", "test", "demo", "dummy", "fake",
            "your_", "your-", "xxx", "aaa", "123", "placeholder",
            "changeme", "password123", "secret123", "todo",
            "insert_", "replace_", "<your", "${", "{{",
        ]
        if any(fp in match_lower for fp in false_positive_patterns):
            return True

        # Skip if it's a variable reference, not a literal
        if match_text.startswith("$") or match_text.startswith("%"):
            return True

        # Skip common environment variable patterns
        if re.match(r"^\$\{?\w+\}?$", match_text):
            return True

        return False

    def scan_file(self, file_path: str) -> list[SecretFinding]:
        """Scan a single file for secrets."""
        full_path = self.project_root / file_path
        findings = []

        if not full_path.exists():
            return findings

        try:
            content = full_path.read_text(errors="ignore")
        except Exception as e:
            logger.debug(f"Could not read {file_path}: {e}")
            return findings

        lines = content.split("\n")
        is_test = self._is_test_file(file_path)
        is_env = self._is_env_file(file_path)

        for line_num, line in enumerate(lines, start=1):
            for pattern in self.patterns:
                for match in pattern.pattern.finditer(line):
                    match_text = match.group(0)

                    # Extract the actual secret if it's a capture group
                    if match.lastindex and match.lastindex >= 1:
                        match_text = match.group(1)

                    # Length check
                    if len(match_text) < pattern.min_length:
                        continue
                    if len(match_text) > pattern.max_length:
                        continue

                    # Entropy check
                    entropy = self._calculate_entropy(match_text)
                    if entropy < pattern.entropy_threshold:
                        continue

                    # False positive check
                    if self._is_false_positive(match_text, line, file_path):
                        continue

                    # Calculate confidence
                    confidence = min(1.0, entropy / 5.0)  # Normalize to 0-1
                    if is_test:
                        confidence *= 0.5
                    if is_env and not self._is_gitignored(file_path):
                        confidence = min(1.0, confidence * 1.5)

                    # Adjust severity for test files
                    severity = pattern.severity
                    if is_test:
                        if severity == VulnerabilitySeverity.CRITICAL:
                            severity = VulnerabilitySeverity.MEDIUM
                        elif severity == VulnerabilitySeverity.HIGH:
                            severity = VulnerabilitySeverity.LOW

                    finding = SecretFinding(
                        secret_id=f"secret-{pattern.secret_type.value}-{file_path}-{line_num}",
                        secret_type=pattern.secret_type,
                        severity=severity,
                        location=SourceLocation(
                            file=file_path,
                            line=line_num,
                            column=match.start() + 1,
                        ),
                        line_content=self._redact_line(line, match_text),
                        match_text=self._redact_secret(match_text),
                        entropy=entropy,
                        confidence=confidence,
                        is_test_file=is_test,
                        is_example=is_test,
                        is_env_file=is_env,
                        is_gitignored=self._is_gitignored(file_path),
                        remediation=self._get_remediation(pattern.secret_type),
                    )
                    findings.append(finding)

        return findings

    def _redact_line(self, line: str, secret: str) -> str:
        """Redact the secret from the line content."""
        redacted = self._redact_secret(secret)
        return line.replace(secret, redacted)

    def _is_gitignored(self, file_path: str) -> bool:
        """Check if file is in .gitignore (basic check)."""
        gitignore_path = self.project_root / ".gitignore"
        if not gitignore_path.exists():
            return False

        try:
            content = gitignore_path.read_text()
            basename = os.path.basename(file_path)

            # Basic pattern matching
            for line in content.split("\n"):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if basename == line or file_path == line:
                    return True
                if line.endswith("*") and basename.startswith(line[:-1]):
                    return True
                if line.startswith("*") and basename.endswith(line[1:]):
                    return True
        except Exception:
            pass

        return False

    def _get_remediation(self, secret_type: SecretType) -> str:
        """Get remediation advice for a secret type."""
        remediations = {
            SecretType.AWS_ACCESS_KEY: "Rotate AWS credentials immediately. Use IAM roles or environment variables instead of hardcoded keys.",
            SecretType.AWS_SECRET_KEY: "Rotate AWS credentials immediately. Use IAM roles or AWS Secrets Manager.",
            SecretType.GCP_API_KEY: "Regenerate GCP API key. Consider using service accounts with appropriate scopes.",
            SecretType.GCP_SERVICE_ACCOUNT: "Rotate service account key. Store credentials in Secret Manager, not in code.",
            SecretType.GITHUB_TOKEN: "Revoke token at github.com/settings/tokens. Use fine-grained PATs with minimal permissions.",
            SecretType.STRIPE_SECRET: "Rotate key in Stripe Dashboard. Never commit live keys; use restricted keys.",
            SecretType.SLACK_TOKEN: "Regenerate token in Slack API settings. Use environment variables.",
            SecretType.DATABASE_URL: "Rotate database password. Use secrets management (Vault, AWS Secrets Manager).",
            SecretType.PRIVATE_KEY_RSA: "Generate new keypair immediately. Never commit private keys.",
            SecretType.PRIVATE_KEY_SSH: "Generate new SSH key. Add to .gitignore and use ssh-agent.",
            SecretType.JWT_SECRET: "Rotate JWT secret. Store in environment variables or secrets manager.",
            SecretType.PASSWORD: "Change password immediately. Use secrets management, not hardcoded values.",
        }
        return remediations.get(
            secret_type,
            "Rotate or revoke this credential immediately. Store secrets in environment variables or a secrets manager."
        )

    def scan(self) -> list[SecretFinding]:
        """Scan entire project for secrets."""
        findings = []

        for root, dirs, files in os.walk(self.project_root):
            # Skip directories in SKIP_PATTERNS
            dirs[:] = [d for d in dirs if not any(skip in d for skip in self.SKIP_PATTERNS)]

            for filename in files:
                full_path = Path(root) / filename
                rel_path = full_path.relative_to(self.project_root)

                if self._should_skip_file(str(rel_path)):
                    continue

                if not self._should_scan_file(str(rel_path)):
                    continue

                try:
                    file_findings = self.scan_file(str(rel_path))
                    findings.extend(file_findings)
                except Exception as e:
                    logger.debug(f"Error scanning {rel_path}: {e}")

        # Sort by severity
        severity_order = {
            VulnerabilitySeverity.CRITICAL: 0,
            VulnerabilitySeverity.HIGH: 1,
            VulnerabilitySeverity.MEDIUM: 2,
            VulnerabilitySeverity.LOW: 3,
            VulnerabilitySeverity.UNKNOWN: 4,
        }
        findings.sort(key=lambda f: severity_order[f.severity])

        return findings

    def scan_files(self, file_paths: list[str]) -> list[SecretFinding]:
        """Scan specific files for secrets."""
        findings = []
        for file_path in file_paths:
            if self._should_skip_file(file_path):
                continue
            try:
                file_findings = self.scan_file(file_path)
                findings.extend(file_findings)
            except Exception as e:
                logger.debug(f"Error scanning {file_path}: {e}")
        return findings

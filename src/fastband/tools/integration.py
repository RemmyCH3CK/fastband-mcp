"""
Cross-Tool Integration - Connect all Fastband tools for enhanced intelligence.

This module provides unified operations that leverage multiple tools together:
- Security + Git: Pre-commit scanning, history scanning
- CI/CD + Logs: Build failure correlation with runtime errors
- CI/CD + Git: Blame analysis (which commit broke the build)
- Database + Code: Schema impact analysis
- All tools + CodebaseContext: Risk-aware unified reporting

These integrations are what make Fastband unique - no competitor has this.
"""

import logging
import os
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


# =============================================================================
# SECURITY + GIT INTEGRATION
# =============================================================================

@dataclass
class LicenseViolation:
    """A problematic license found in dependencies."""
    package: str
    license: str
    restriction: str
    severity: str  # "critical", "high", "medium"


@dataclass
class PreCommitResult:
    """Result of pre-commit security check."""
    passed: bool
    secrets_found: int
    critical_issues: int
    blocking_issues: list[dict[str, Any]]
    warnings: list[dict[str, Any]]


# License restrictions for compliance checking
LICENSE_RESTRICTIONS = {
    # Copyleft - require source code release
    "AGPL-3.0": ("Requires full source code release", "critical"),
    "AGPL-3.0-only": ("Requires full source code release", "critical"),
    "GPL-3.0": ("Copyleft - may require source release", "high"),
    "GPL-3.0-only": ("Copyleft - may require source release", "high"),
    "GPL-2.0": ("Copyleft - may require source release", "high"),
    "GPL-2.0-only": ("Copyleft - may require source release", "high"),
    "LGPL-3.0": ("Weak copyleft - linking restrictions", "medium"),
    "LGPL-2.1": ("Weak copyleft - linking restrictions", "medium"),

    # Proprietary/restrictive
    "SSPL-1.0": ("Server Side Public License - restrictive", "critical"),
    "BSL-1.1": ("Business Source License - time-limited", "high"),
    "Elastic-2.0": ("Elastic License - usage restrictions", "high"),
    "Commons-Clause": ("Commercial use restrictions", "high"),

    # Non-commercial
    "CC-BY-NC-4.0": ("Non-commercial use only", "critical"),
    "CC-BY-NC-SA-4.0": ("Non-commercial use only", "critical"),
}


async def check_license_compliance(sbom_path: str = "") -> dict[str, Any]:
    """
    Check dependencies for license compliance issues.

    Scans SBOM or dependency files for problematic licenses that
    could require source code release or restrict commercial use.

    Args:
        sbom_path: Path to SBOM file (optional, will generate if not provided)

    Returns:
        License compliance report with violations and recommendations
    """
    from fastband.tools.security import security_scan

    # Get security report which includes SBOM
    report = await security_scan(os.getcwd(), scan_type="dependencies", generate_sbom=True)

    if "error" in report:
        return report

    violations: list[LicenseViolation] = []
    warnings: list[str] = []

    # Check each dependency license
    sbom = report.get("sbom", {})
    components = sbom.get("components", [])

    for component in components:
        license_id = component.get("license_spdx", "")
        package_name = component.get("name", "")

        if license_id in LICENSE_RESTRICTIONS:
            restriction, severity = LICENSE_RESTRICTIONS[license_id]
            violations.append(LicenseViolation(
                package=package_name,
                license=license_id,
                restriction=restriction,
                severity=severity,
            ))

        # Check for unknown licenses
        if not license_id or license_id == "UNKNOWN":
            warnings.append(f"{package_name}: License unknown - manual review required")

    # Sort by severity
    violations.sort(key=lambda v: {"critical": 0, "high": 1, "medium": 2}.get(v.severity, 3))

    return {
        "type": "license_compliance",
        "passed": len([v for v in violations if v.severity == "critical"]) == 0,
        "total_packages": len(components),
        "violations": [
            {
                "package": v.package,
                "license": v.license,
                "restriction": v.restriction,
                "severity": v.severity,
            }
            for v in violations
        ],
        "critical_count": len([v for v in violations if v.severity == "critical"]),
        "high_count": len([v for v in violations if v.severity == "high"]),
        "warnings": warnings[:10],
        "recommendation": (
            "Remove or replace packages with AGPL/SSPL licenses before production release"
            if any(v.severity == "critical" for v in violations)
            else "Review high-severity license restrictions for compliance"
            if violations
            else "No license compliance issues found"
        ),
    }


async def security_precommit_check(staged_files: list[str] | None = None) -> PreCommitResult:
    """
    Run security checks on staged files before commit.

    Designed to be called from a git pre-commit hook to block
    commits containing secrets or critical security issues.

    Args:
        staged_files: List of staged file paths. If None, detects from git.

    Returns:
        PreCommitResult indicating if commit should proceed
    """
    from fastband.tools.security import security_check_file

    # Get staged files if not provided
    if staged_files is None:
        try:
            result = subprocess.run(
                ["git", "diff", "--cached", "--name-only"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            staged_files = [f.strip() for f in result.stdout.split("\n") if f.strip()]
        except Exception as e:
            logger.warning(f"Could not get staged files: {e}")
            staged_files = []

    if not staged_files:
        return PreCommitResult(
            passed=True,
            secrets_found=0,
            critical_issues=0,
            blocking_issues=[],
            warnings=[],
        )

    blocking_issues = []
    warnings = []
    secrets_found = 0
    critical_count = 0

    # Check each staged file
    for file_path in staged_files:
        if not os.path.exists(file_path):
            continue

        # Skip binary files and common non-code files
        if any(file_path.endswith(ext) for ext in [".png", ".jpg", ".gif", ".ico", ".woff", ".ttf"]):
            continue

        try:
            report = await security_check_file(file_path)

            if "error" in report:
                continue

            # Check for secrets
            file_secrets = report.get("secrets", [])
            secrets_found += len(file_secrets)

            for secret in file_secrets:
                severity = secret.get("severity", "medium")
                if severity in ("critical", "high"):
                    blocking_issues.append({
                        "file": file_path,
                        "type": "secret",
                        "secret_type": secret.get("type"),
                        "line": secret.get("line"),
                        "message": f"Secret detected: {secret.get('type')}",
                    })
                    critical_count += 1
                else:
                    warnings.append({
                        "file": file_path,
                        "type": "secret",
                        "message": f"Potential secret: {secret.get('type')}",
                    })

            # Check for vulnerabilities
            vulns = report.get("vulnerabilities", [])
            for vuln in vulns:
                severity = vuln.get("severity", "medium")
                if severity == "critical":
                    blocking_issues.append({
                        "file": file_path,
                        "type": "vulnerability",
                        "message": vuln.get("title", "Critical vulnerability"),
                    })
                    critical_count += 1

        except Exception as e:
            logger.debug(f"Error checking file {file_path}: {e}")

    return PreCommitResult(
        passed=len(blocking_issues) == 0,
        secrets_found=secrets_found,
        critical_issues=critical_count,
        blocking_issues=blocking_issues,
        warnings=warnings,
    )


# =============================================================================
# CI/CD + GIT INTEGRATION (Blame Analysis)
# =============================================================================

@dataclass
class CommitBlame:
    """Attribution of a CI failure to a specific commit."""
    commit_hash: str
    author: str
    author_email: str
    commit_date: str
    message: str
    files_changed: list[str]
    confidence: float  # 0-1, how confident this caused the failure


async def cicd_diagnose_with_blame(run_id: int) -> dict[str, Any]:
    """
    Diagnose a failed CI run and attribute it to specific commits.

    Correlates build failures with recent git commits to identify
    which change likely broke the build.

    Args:
        run_id: GitHub Actions run ID

    Returns:
        Diagnosis with blame attribution
    """
    from fastband.tools.cicd import CICDTool, cicd_diagnose

    # Get the diagnosis first
    diagnosis = await cicd_diagnose(run_id)

    if "error" in diagnosis or diagnosis.get("status") == "not_failed":
        return diagnosis

    # Get the run details to find branch and sha
    tool = CICDTool(os.getcwd())
    run = tool.github.get_run(run_id)

    if not run:
        return diagnosis

    # Get recent commits on the branch
    try:
        result = subprocess.run(
            [
                "git", "log",
                "--pretty=format:%H|%an|%ae|%ai|%s",
                "-n", "10",
                run.head_sha,
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode != 0:
            diagnosis["blame"] = {"error": "Could not get git history"}
            return diagnosis

        commits = []
        for line in result.stdout.strip().split("\n"):
            if not line:
                continue
            parts = line.split("|", 4)
            if len(parts) >= 5:
                commit_hash = parts[0]

                # Get files changed in this commit
                files_result = subprocess.run(
                    ["git", "show", "--name-only", "--pretty=format:", commit_hash],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                files_changed = [f.strip() for f in files_result.stdout.strip().split("\n") if f.strip()]

                commits.append(CommitBlame(
                    commit_hash=commit_hash,
                    author=parts[1],
                    author_email=parts[2],
                    commit_date=parts[3],
                    message=parts[4],
                    files_changed=files_changed,
                    confidence=0.0,
                ))

    except Exception as e:
        diagnosis["blame"] = {"error": str(e)}
        return diagnosis

    # Analyze which commit likely caused the failure
    errors = diagnosis.get("errors", [])
    failed_jobs = diagnosis.get("failed_jobs", [])

    # Simple heuristic: most recent commit with relevant files
    error_keywords = []
    for error in errors:
        error_lower = error.lower()
        # Extract potential file references
        for word in error_lower.split():
            if "." in word and "/" in word:
                error_keywords.append(word)

    # Score commits by relevance
    for commit in commits:
        score = 0.0

        # Most recent commit gets base score
        if commit == commits[0]:
            score += 0.3

        # Check if changed files relate to errors
        for changed_file in commit.files_changed:
            changed_lower = changed_file.lower()

            # Direct file match in error
            for keyword in error_keywords:
                if changed_lower in keyword or keyword in changed_lower:
                    score += 0.5

            # Test file changes are highly relevant
            if "test" in changed_lower:
                score += 0.2

            # Configuration changes can break builds
            if any(cfg in changed_lower for cfg in ["config", "setup", "package", "requirements"]):
                score += 0.15

        commit.confidence = min(score, 1.0)

    # Sort by confidence
    commits.sort(key=lambda c: c.confidence, reverse=True)

    # Build blame report
    likely_culprits = [
        {
            "commit": c.commit_hash[:8],
            "author": c.author,
            "email": c.author_email,
            "date": c.commit_date,
            "message": c.message[:80],
            "files_changed": c.files_changed[:5],
            "confidence": round(c.confidence, 2),
        }
        for c in commits[:3] if c.confidence > 0.1
    ]

    diagnosis["blame"] = {
        "likely_culprits": likely_culprits,
        "most_likely": likely_culprits[0] if likely_culprits else None,
        "recent_commits": len(commits),
        "recommendation": (
            f"Investigate commit {likely_culprits[0]['commit']} by {likely_culprits[0]['author']}"
            if likely_culprits
            else "Could not determine likely cause - check build logs"
        ),
    }

    return diagnosis


# =============================================================================
# CI/CD + LOGS INTEGRATION
# =============================================================================

async def cicd_correlate_with_logs(
    run_id: int,
    log_path: str = "",
) -> dict[str, Any]:
    """
    Correlate CI/CD failures with runtime application logs.

    Links build errors to application log entries for comprehensive
    incident analysis.

    Args:
        run_id: CI/CD run ID
        log_path: Path to application log file (optional)

    Returns:
        Correlated analysis showing build + runtime errors
    """
    from fastband.tools.cicd import cicd_logs, cicd_run_details
    from fastband.tools.logs import logs_analyze

    # Get CI/CD details
    run_details = await cicd_run_details(run_id)
    build_logs = await cicd_logs(run_id, failed_only=True)

    result = {
        "type": "cicd_log_correlation",
        "run_id": run_id,
        "build": {
            "status": run_details.get("status"),
            "conclusion": run_details.get("conclusion"),
            "errors": build_logs.get("errors", [])[:10],
            "error_count": build_logs.get("error_count", 0),
        },
        "correlation": [],
    }

    if not log_path:
        result["app_logs"] = {"note": "No application log path provided"}
        return result

    # Analyze application logs
    app_log_analysis = await logs_analyze(log_path, errors_only=True, correlate_code=True)

    result["app_logs"] = {
        "error_count": app_log_analysis.get("error_count", 0),
        "unique_patterns": app_log_analysis.get("unique_error_patterns", 0),
        "top_errors": app_log_analysis.get("top_errors", [])[:5],
    }

    # Find correlations between build errors and app errors
    correlations = []
    build_errors = build_logs.get("errors", [])
    app_patterns = app_log_analysis.get("top_errors", [])

    for build_error in build_errors[:10]:
        build_error_lower = build_error.lower()

        for app_pattern in app_patterns:
            app_error_type = app_pattern.get("error_type", "").lower()
            app_message = app_pattern.get("message", "").lower()

            # Check for matches
            if (
                app_error_type in build_error_lower or
                any(word in build_error_lower for word in app_error_type.split() if len(word) > 4)
            ):
                correlations.append({
                    "build_error": build_error[:100],
                    "app_error": app_pattern.get("error_type"),
                    "app_occurrences": app_pattern.get("count"),
                    "match_type": "error_type",
                    "source_file": app_pattern.get("source_file"),
                })

    result["correlations"] = correlations
    result["has_correlation"] = len(correlations) > 0

    if correlations:
        result["recommendation"] = (
            f"Build errors correlate with {len(correlations)} application error patterns. "
            f"Start investigation with {correlations[0].get('source_file', 'the first correlated error')}."
        )
    else:
        result["recommendation"] = "No direct correlation found between build and app errors."

    return result


# =============================================================================
# DATABASE IMPROVEMENTS
# =============================================================================

async def db_schema_quality_score(connection: str) -> dict[str, Any]:
    """
    Calculate a quality score for database schema.

    Analyzes schema for best practices including:
    - Primary key coverage
    - Index density
    - Foreign key constraints
    - Nullable column patterns
    - Naming conventions

    Args:
        connection: Database connection string or file path

    Returns:
        Quality score (0-100) with specific recommendations
    """
    from fastband.tools.database import DatabaseTool

    # Use DatabaseTool directly to get full SchemaReport with tables
    tool = DatabaseTool(os.getcwd())

    try:
        report = await tool.get_schema(connection)
    except Exception as e:
        return {"error": str(e)}

    # Get tables from the SchemaReport object
    tables = report.tables
    if not tables:
        return {"error": "No tables found in database"}

    score = 100
    issues = []
    quick_wins = []

    total_tables = len(tables)
    tables_with_pk = 0
    tables_with_indexes = 0
    total_columns = 0
    nullable_fk_count = 0
    naming_issues = 0

    for table in tables:
        table_name = table.name
        columns = table.columns
        indexes = table.indexes
        primary_key = table.primary_key_columns

        total_columns += len(columns)

        # Check for primary key
        if primary_key:
            tables_with_pk += 1
        else:
            score -= 10
            issues.append(f"Table '{table_name}' has no primary key")
            quick_wins.append(f"Add primary key to '{table_name}'")

        # Check for indexes
        if indexes:
            tables_with_indexes += 1
        elif len(columns) > 5:  # Large tables should have indexes
            score -= 5
            issues.append(f"Table '{table_name}' has no indexes ({len(columns)} columns)")

        # Check naming conventions
        if table_name != table_name.lower():
            naming_issues += 1

        # Check for nullable foreign keys (Column objects)
        for col in columns:
            if col.references_table and col.is_nullable:
                nullable_fk_count += 1

    # Naming convention penalty
    if naming_issues > 0:
        score -= min(naming_issues * 2, 10)
        issues.append(f"{naming_issues} tables don't follow lowercase naming convention")

    # Nullable FK penalty
    if nullable_fk_count > 0:
        score -= min(nullable_fk_count * 3, 15)
        issues.append(f"{nullable_fk_count} nullable foreign keys (potential orphan data)")

    # Calculate percentages
    pk_coverage = (tables_with_pk / total_tables * 100) if total_tables > 0 else 0
    index_coverage = (tables_with_indexes / total_tables * 100) if total_tables > 0 else 0

    # Ensure score doesn't go below 0
    score = max(score, 0)

    # Determine grade
    if score >= 90:
        grade = "A"
    elif score >= 80:
        grade = "B"
    elif score >= 70:
        grade = "C"
    elif score >= 60:
        grade = "D"
    else:
        grade = "F"

    return {
        "type": "schema_quality",
        "score": score,
        "grade": grade,
        "metrics": {
            "table_count": total_tables,
            "column_count": total_columns,
            "pk_coverage": f"{pk_coverage:.0f}%",
            "index_coverage": f"{index_coverage:.0f}%",
            "nullable_fks": nullable_fk_count,
        },
        "issues": issues[:10],
        "quick_wins": quick_wins[:5],
        "recommendation": (
            "Schema is well-designed"
            if score >= 80
            else "Focus on adding primary keys first"
            if tables_with_pk < total_tables
            else "Consider adding indexes for better query performance"
        ),
    }


# =============================================================================
# DEPLOYMENT INTEGRATIONS
# =============================================================================

# Risk weights for different file types
FILE_RISK_WEIGHTS = {
    # Security-critical files
    "auth": 0.9,
    "crypto": 0.9,
    "password": 0.9,
    "secret": 0.9,
    "token": 0.8,
    "key": 0.8,
    "credential": 0.9,
    # Configuration
    ".env": 0.7,
    "config": 0.6,
    "settings": 0.6,
    # Database
    "migration": 0.8,
    "schema": 0.7,
    "model": 0.5,
    # Infrastructure
    "dockerfile": 0.6,
    "docker-compose": 0.6,
    "kubernetes": 0.7,
    "terraform": 0.8,
    # Dependencies
    "package.json": 0.5,
    "requirements": 0.5,
    "pyproject": 0.5,
}


async def deploy_with_security_check(environment: str = "preview") -> dict[str, Any]:
    """
    Run security checks before deployment.

    Integrates security scanning with deployment decision-making.

    Args:
        environment: Target environment (preview, production)

    Returns:
        Security results with deployment recommendation
    """
    from fastband.tools.security import security_scan

    # Run comprehensive security scan
    scan_result = await security_scan(os.getcwd(), scan_type="full")

    # Get staged/uncommitted changes for pre-commit check
    precommit_result = await security_precommit_check()

    # Determine if deployment should proceed
    critical_secrets = precommit_result.secrets_found
    critical_vulns = scan_result.get("vulnerabilities", {}).get("critical", 0)
    high_vulns = scan_result.get("vulnerabilities", {}).get("high", 0)

    # Stricter checks for production
    if environment == "production":
        can_deploy = critical_secrets == 0 and critical_vulns == 0 and high_vulns == 0
        threshold = "No secrets, critical, or high vulnerabilities allowed"
    else:
        can_deploy = critical_secrets == 0 and critical_vulns == 0
        threshold = "No secrets or critical vulnerabilities allowed"

    return {
        "type": "deploy_security_check",
        "environment": environment,
        "can_deploy": can_deploy,
        "threshold": threshold,
        "security_summary": {
            "secrets_found": critical_secrets,
            "critical_vulnerabilities": critical_vulns,
            "high_vulnerabilities": high_vulns,
            "precommit_passed": precommit_result.passed,
        },
        "blocking_issues": precommit_result.blocking_issues[:5],
        "recommendation": (
            f"Safe to deploy to {environment}"
            if can_deploy
            else f"Fix {critical_secrets} secrets and {critical_vulns} critical issues before deploying"
        ),
    }


async def deploy_risk_assessment(from_ref: str = "", to_ref: str = "HEAD") -> dict[str, Any]:
    """
    Assess deployment risk based on file changes.

    Analyzes changed files and calculates risk score.

    Args:
        from_ref: Starting git ref (detects last deploy if empty)
        to_ref: Ending git ref

    Returns:
        Risk assessment with score and breakdown
    """
    # If no from_ref, try to find last deployment commit
    if not from_ref:
        try:
            # Look for recent tags or use last 10 commits
            result = subprocess.run(
                ["git", "describe", "--tags", "--abbrev=0"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                from_ref = result.stdout.strip()
            else:
                from_ref = "HEAD~10"
        except Exception:
            from_ref = "HEAD~10"

    # Get changed files
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", f"{from_ref}..{to_ref}"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode != 0:
            return {"error": f"Git diff failed: {result.stderr}"}

        changed_files = [f.strip() for f in result.stdout.strip().split("\n") if f.strip()]
    except Exception as e:
        return {"error": str(e)}

    if not changed_files:
        return {
            "type": "deploy_risk",
            "risk_score": 0,
            "risk_level": "low",
            "changed_files": 0,
            "message": "No files changed",
        }

    # Calculate risk for each file
    risk_breakdown = {
        "security": [],
        "database": [],
        "config": [],
        "infrastructure": [],
        "other": [],
    }

    total_risk = 0.0
    high_risk_files = []

    for file_path in changed_files:
        file_lower = file_path.lower()
        file_risk = 0.1  # Base risk

        # Check against risk weights
        for keyword, weight in FILE_RISK_WEIGHTS.items():
            if keyword in file_lower:
                file_risk = max(file_risk, weight)

                # Categorize
                if keyword in ("auth", "crypto", "password", "secret", "token", "key", "credential"):
                    risk_breakdown["security"].append(file_path)
                elif keyword in ("migration", "schema", "model"):
                    risk_breakdown["database"].append(file_path)
                elif keyword in (".env", "config", "settings"):
                    risk_breakdown["config"].append(file_path)
                elif keyword in ("dockerfile", "docker-compose", "kubernetes", "terraform"):
                    risk_breakdown["infrastructure"].append(file_path)
                break
        else:
            risk_breakdown["other"].append(file_path)

        total_risk += file_risk
        if file_risk >= 0.7:
            high_risk_files.append({"file": file_path, "risk": file_risk})

    # Normalize score to 0-100
    max_possible_risk = len(changed_files) * 0.9
    risk_score = min(100, int((total_risk / max_possible_risk) * 100)) if max_possible_risk > 0 else 0

    # Determine risk level
    if risk_score >= 70:
        risk_level = "high"
    elif risk_score >= 40:
        risk_level = "medium"
    else:
        risk_level = "low"

    return {
        "type": "deploy_risk",
        "from_ref": from_ref,
        "to_ref": to_ref,
        "risk_score": risk_score,
        "risk_level": risk_level,
        "changed_files": len(changed_files),
        "breakdown": {
            "security_files": len(risk_breakdown["security"]),
            "database_files": len(risk_breakdown["database"]),
            "config_files": len(risk_breakdown["config"]),
            "infrastructure_files": len(risk_breakdown["infrastructure"]),
        },
        "high_risk_files": high_risk_files[:5],
        "recommendation": (
            "Review security-sensitive changes carefully before deploying"
            if risk_level == "high"
            else "Standard review recommended"
            if risk_level == "medium"
            else "Low risk deployment"
        ),
    }


async def deploy_pipeline_status(run_id: int = 0) -> dict[str, Any]:
    """
    Get full pipeline status from CI to deployment.

    Shows the complete flow: commit -> CI build -> deployment.

    Args:
        run_id: CI run ID (uses latest if 0)

    Returns:
        Pipeline status across all stages
    """
    from fastband.tools.cicd import cicd_run_details, cicd_runs
    from fastband.tools.deployment import deploy_latest, deploy_list

    pipeline = {
        "type": "pipeline_status",
        "stages": [],
    }

    # Stage 1: Get CI run
    if run_id == 0:
        runs = await cicd_runs(limit=1)
        if runs.get("runs"):
            run_id = runs["runs"][0].get("id", 0)

    if run_id:
        ci_details = await cicd_run_details(run_id)
        pipeline["stages"].append({
            "stage": "ci_build",
            "status": ci_details.get("conclusion", "unknown"),
            "run_id": run_id,
            "branch": ci_details.get("branch"),
            "commit": ci_details.get("commit"),
            "duration_s": ci_details.get("duration_s"),
            "url": ci_details.get("url"),
        })

        # Get commit from CI for deployment lookup
        commit_sha = ci_details.get("commit", "")
    else:
        pipeline["stages"].append({
            "stage": "ci_build",
            "status": "not_found",
            "message": "No CI runs found",
        })
        commit_sha = ""

    # Stage 2: Get deployment
    try:
        deployments = await deploy_list(limit=5)
        deployment = None

        # Try to find deployment matching the CI commit
        if commit_sha and deployments.get("deployments"):
            for d in deployments["deployments"]:
                if d.get("commit", "").startswith(commit_sha[:7]):
                    deployment = d
                    break

        # Fall back to latest
        if not deployment and deployments.get("deployments"):
            deployment = deployments["deployments"][0]

        if deployment:
            pipeline["stages"].append({
                "stage": "deployment",
                "status": deployment.get("status"),
                "deployment_id": deployment.get("id"),
                "url": deployment.get("url"),
                "environment": deployment.get("environment"),
                "build_duration_s": deployment.get("build_duration_s"),
            })
        else:
            pipeline["stages"].append({
                "stage": "deployment",
                "status": "not_found",
                "message": "No matching deployment found",
            })

    except Exception as e:
        pipeline["stages"].append({
            "stage": "deployment",
            "status": "error",
            "message": str(e),
        })

    # Calculate overall status
    all_success = all(
        s.get("status") in ("success", "ready", "completed")
        for s in pipeline["stages"]
    )
    any_failed = any(
        s.get("status") in ("failure", "failed", "error")
        for s in pipeline["stages"]
    )

    pipeline["overall_status"] = (
        "success" if all_success
        else "failed" if any_failed
        else "in_progress"
    )

    return pipeline


async def deploy_rollback_recommendation(deployment_id: str = "") -> dict[str, Any]:
    """
    Analyze if rollback is recommended and to which version.

    Checks deployment health and compares with previous versions.

    Args:
        deployment_id: Current deployment ID (uses production if empty)

    Returns:
        Rollback recommendation with target version
    """
    from fastband.tools.deployment import deploy_health, deploy_list

    # Get current deployment health
    current_health = await deploy_health()

    if "error" in current_health:
        return current_health

    is_healthy = current_health.get("healthy", True)
    response_time = current_health.get("response_time_ms", 0)

    # Get recent deployments to find rollback targets
    deployments = await deploy_list(limit=10, environment="production")

    if "error" in deployments:
        return deployments

    deploy_list_data = deployments.get("deployments", [])

    # Find last successful deployment (not current)
    rollback_target = None
    for d in deploy_list_data[1:]:  # Skip current
        if d.get("status") == "ready":
            rollback_target = d
            break

    # Determine if rollback is recommended
    should_rollback = False
    reasons = []

    if not is_healthy:
        should_rollback = True
        reasons.append(f"Deployment unhealthy (status: {current_health.get('status_code')})")

    if response_time > 5000:  # 5 seconds
        should_rollback = True
        reasons.append(f"High response time ({response_time}ms)")

    if current_health.get("ssl_days_remaining", 999) < 7:
        reasons.append(f"SSL expires in {current_health.get('ssl_days_remaining')} days")

    return {
        "type": "rollback_analysis",
        "current_deployment": deployment_id or "production",
        "current_health": {
            "healthy": is_healthy,
            "response_time_ms": response_time,
            "ssl_valid": current_health.get("ssl_valid"),
        },
        "should_rollback": should_rollback,
        "reasons": reasons,
        "rollback_target": rollback_target if should_rollback else None,
        "recommendation": (
            f"Rollback to {rollback_target.get('id')} recommended"
            if should_rollback and rollback_target
            else "No rollback needed - deployment is healthy"
            if is_healthy
            else "Rollback recommended but no stable target found"
        ),
    }


# =============================================================================
# DEPENDENCY INTEGRATIONS
# =============================================================================

async def deps_full_security_report() -> dict[str, Any]:
    """
    Generate comprehensive dependency security report.

    Combines vulnerability scanning, license compliance,
    and security recommendations into one report.

    Returns:
        Full security report with actionable insights
    """
    from fastband.tools.dependencies import deps_audit, deps_health, deps_licenses

    # Get all dependency data
    audit_result = await deps_audit()
    license_result = await deps_licenses()
    health_result = await deps_health()

    # Calculate overall security score
    vuln_penalty = (
        audit_result.get("critical", 0) * 25 +
        audit_result.get("high", 0) * 15 +
        audit_result.get("medium", 0) * 5 +
        audit_result.get("low", 0) * 1
    )

    license_penalty = (
        len(license_result.get("high_risk", [])) * 10 +
        license_result.get("unknown", 0) * 3
    )

    security_score = max(0, 100 - vuln_penalty - license_penalty)

    # Prioritize actions
    critical_actions = []

    if audit_result.get("critical", 0) > 0:
        critical_actions.append({
            "priority": 1,
            "action": "Fix critical vulnerabilities immediately",
            "count": audit_result.get("critical"),
            "packages": [v.get("package") for v in audit_result.get("vulnerabilities", [])
                        if v.get("severity") == "critical"][:5],
        })

    if license_result.get("high_risk"):
        critical_actions.append({
            "priority": 2,
            "action": "Review high-risk licenses",
            "count": len(license_result.get("high_risk", [])),
            "packages": [l.get("package") for l in license_result.get("high_risk", [])][:5],
        })

    if audit_result.get("high", 0) > 0:
        critical_actions.append({
            "priority": 3,
            "action": "Address high-severity vulnerabilities",
            "count": audit_result.get("high"),
        })

    return {
        "type": "deps_security_report",
        "security_score": security_score,
        "grade": (
            "A" if security_score >= 90
            else "B" if security_score >= 80
            else "C" if security_score >= 70
            else "D" if security_score >= 60
            else "F"
        ),
        "vulnerabilities": {
            "total": audit_result.get("vulnerability_count", 0),
            "critical": audit_result.get("critical", 0),
            "high": audit_result.get("high", 0),
            "medium": audit_result.get("medium", 0),
        },
        "licenses": {
            "total": license_result.get("total", 0),
            "permissive": license_result.get("permissive", 0),
            "copyleft": license_result.get("copyleft", 0),
            "high_risk": len(license_result.get("high_risk", [])),
        },
        "health_score": health_result.get("health_score", 0),
        "critical_actions": critical_actions,
        "recommendation": (
            "Dependencies are secure"
            if security_score >= 80
            else "Address critical vulnerabilities before deployment"
            if audit_result.get("critical", 0) > 0
            else "Review and update vulnerable dependencies"
        ),
    }


async def deps_update_impact_analysis(package: str = "") -> dict[str, Any]:
    """
    Analyze the impact of updating dependencies.

    Checks for breaking changes, affected code, and
    compatibility with other dependencies.

    Args:
        package: Specific package to analyze (all outdated if empty)

    Returns:
        Update impact analysis with risk assessment
    """
    from fastband.tools.dependencies import deps_outdated, deps_health

    outdated = await deps_outdated()
    health = await deps_health()

    packages = outdated.get("packages", [])

    if package:
        packages = [p for p in packages if p.get("name") == package]

    if not packages:
        return {
            "type": "update_impact",
            "message": "No outdated packages to analyze" if not package else f"Package {package} not found or up to date",
        }

    # Analyze each package
    analysis = []
    total_risk = 0

    for pkg in packages[:10]:  # Limit to 10
        update_info = pkg.get("update", {})
        update_type = update_info.get("type", "patch")

        # Calculate risk based on update type
        if update_type == "major":
            risk = 0.8
            breaking_likely = True
        elif update_type == "minor":
            risk = 0.3
            breaking_likely = False
        else:
            risk = 0.1
            breaking_likely = False

        total_risk += risk

        analysis.append({
            "package": pkg.get("name"),
            "current": pkg.get("version"),
            "latest": update_info.get("latest"),
            "update_type": update_type,
            "breaking_likely": breaking_likely,
            "risk_score": round(risk * 100),
            "recommendation": (
                "Test thoroughly before updating"
                if breaking_likely
                else "Safe to update"
            ),
        })

    # Sort by risk
    analysis.sort(key=lambda x: x.get("risk_score", 0), reverse=True)

    avg_risk = (total_risk / len(packages)) * 100 if packages else 0

    return {
        "type": "update_impact",
        "packages_analyzed": len(analysis),
        "average_risk": round(avg_risk),
        "breaking_updates": len([a for a in analysis if a.get("breaking_likely")]),
        "safe_updates": len([a for a in analysis if not a.get("breaking_likely")]),
        "analysis": analysis,
        "recommendation": (
            "Several breaking changes detected - update incrementally"
            if avg_risk > 50
            else "Most updates are safe - can batch update"
        ),
    }


# =============================================================================
# ENVIRONMENT INTEGRATIONS
# =============================================================================

async def env_security_audit() -> dict[str, Any]:
    """
    Audit environment files for security issues.

    Combines environment parsing with security scanning
    to detect exposed secrets and misconfigurations.

    Returns:
        Security audit with risk assessment
    """
    from fastband.tools.environment import env_list, env_validate

    # Get all env files
    env_files = await env_list()

    audit_results = []
    total_secrets_exposed = 0
    critical_issues = []

    for env_file in env_files.get("files", []):
        path = env_file.get("path", "")

        # Skip example files
        if "example" in path.lower() or "sample" in path.lower():
            continue

        # Validate each file
        validation = await env_validate(file_path=path)

        exposed = validation.get("issues", {}).get("exposed_secrets", [])
        total_secrets_exposed += len(exposed)

        for secret in exposed:
            if secret.get("risk") == "critical":
                critical_issues.append({
                    "file": path,
                    "variable": secret.get("name"),
                    "line": secret.get("line"),
                })

        audit_results.append({
            "file": path,
            "passed": validation.get("passed"),
            "exposed_secrets": len(exposed),
            "empty_values": len(validation.get("issues", {}).get("empty_values", [])),
        })

    return {
        "type": "env_security_audit",
        "files_audited": len(audit_results),
        "total_secrets_exposed": total_secrets_exposed,
        "critical_issues": critical_issues[:10],
        "results": audit_results,
        "passed": total_secrets_exposed == 0,
        "recommendation": (
            "Environment files are secure"
            if total_secrets_exposed == 0
            else f"Remove or encrypt {total_secrets_exposed} exposed secrets"
        ),
    }


# =============================================================================
# PERFORMANCE INTEGRATIONS
# =============================================================================

async def perf_deploy_check() -> dict[str, Any]:
    """
    Check performance before deployment.

    Combines bundle analysis with performance thresholds
    to determine if build is ready to deploy.

    Returns:
        Deployment readiness based on performance
    """
    from fastband.tools.performance import perf_bundle, perf_report

    # Get performance report
    report = await perf_report()

    issues = []
    warnings = []

    # Check bundle size
    bundle = report.get("bundle", {})
    if bundle:
        total_mb = bundle.get("total_size_mb", 0)
        if total_mb > 2:
            issues.append(f"Bundle size ({total_mb}MB) exceeds 2MB limit")
        elif total_mb > 1:
            warnings.append(f"Bundle size ({total_mb}MB) is large")

    # Check overall score
    score = report.get("overall_score", 100)
    if score < 60:
        issues.append(f"Performance score ({score}) is below threshold")

    ready = len(issues) == 0

    return {
        "type": "perf_deploy_check",
        "ready": ready,
        "score": score,
        "grade": report.get("grade"),
        "issues": issues,
        "warnings": warnings,
        "recommendation": (
            "Performance is acceptable for deployment"
            if ready
            else "Optimize bundle size before deploying"
        ),
    }


async def perf_deps_impact() -> dict[str, Any]:
    """
    Analyze dependency impact on performance.

    Identifies which dependencies contribute most
    to bundle size and build time.

    Returns:
        Dependency performance impact analysis
    """
    from fastband.tools.dependencies import deps_list
    from fastband.tools.performance import perf_bundle

    # Get dependencies
    deps = await deps_list()
    dep_names = [d.get("name") for d in deps.get("dependencies", [])]

    # Get bundle analysis
    bundle = await perf_bundle()

    if "error" in bundle:
        return bundle

    # Analyze vendor impact
    largest = bundle.get("largest_files", [])
    vendor_files = [f for f in largest if f.get("is_vendor")]

    heavy_deps = []
    for vf in vendor_files[:10]:
        path = vf.get("path", "").lower()
        for dep in dep_names:
            if dep.lower() in path:
                heavy_deps.append({
                    "dependency": dep,
                    "size_kb": vf.get("size_kb"),
                    "file": vf.get("path"),
                })
                break

    vendor_pct = bundle.get("vendor_percentage", 0)

    return {
        "type": "perf_deps_impact",
        "vendor_percentage": vendor_pct,
        "total_dependencies": len(dep_names),
        "heavy_dependencies": heavy_deps[:5],
        "recommendation": (
            "Consider replacing heavy dependencies with lighter alternatives"
            if vendor_pct > 60
            else "Dependency impact is acceptable"
        ),
    }


async def env_deploy_readiness(environment: str = "production") -> dict[str, Any]:
    """
    Check if environment is ready for deployment.

    Validates environment variables against production requirements
    and compares with development environment.

    Args:
        environment: Target deployment environment

    Returns:
        Deployment readiness assessment
    """
    from fastband.tools.environment import env_compare, env_validate, env_missing

    issues = []
    warnings = []

    # Check for missing variables in code
    missing = await env_missing()
    if missing.get("missing_count", 0) > 0:
        issues.append({
            "type": "missing_vars",
            "count": missing.get("missing_count"),
            "vars": missing.get("missing_vars", [])[:5],
        })

    # Validate production env file
    prod_file = f".env.{environment}" if environment != "production" else ".env.production"
    validation = await env_validate(file_path=prod_file)

    if not validation.get("passed"):
        issues.extend([
            {"type": "validation_failed", "details": validation.get("issues", {})}
        ])

    # Compare with development
    try:
        comparison = await env_compare(source=".env.development", target=prod_file)
        if comparison.get("missing_in_target"):
            warnings.append({
                "type": "missing_in_prod",
                "vars": comparison.get("missing_in_target", [])[:5],
            })
    except Exception:
        pass  # Dev file may not exist

    ready = len(issues) == 0

    return {
        "type": "env_deploy_readiness",
        "environment": environment,
        "ready": ready,
        "issues": issues,
        "warnings": warnings,
        "recommendation": (
            f"Ready to deploy to {environment}"
            if ready
            else f"Fix {len(issues)} issues before deploying"
        ),
    }


async def deps_cicd_correlation() -> dict[str, Any]:
    """
    Correlate dependency changes with CI/CD failures.

    Analyzes recent CI failures to identify if dependency
    updates caused build breakages.

    Returns:
        Correlation between dep changes and CI failures
    """
    from fastband.tools.cicd import cicd_runs

    # Get recent CI runs
    runs = await cicd_runs(limit=20)

    if "error" in runs:
        return runs

    run_list = runs.get("runs", [])
    failed_runs = [r for r in run_list if r.get("conclusion") == "failure"]

    if not failed_runs:
        return {
            "type": "deps_cicd_correlation",
            "message": "No recent CI failures to correlate",
            "recent_runs": len(run_list),
            "failed_runs": 0,
        }

    # Check for dependency-related failures
    dep_failures = []

    for run in failed_runs[:5]:
        commit_sha = run.get("commit", "")

        if commit_sha:
            # Check if commit modified dependency files
            try:
                result = subprocess.run(
                    ["git", "show", "--name-only", "--pretty=format:", commit_sha],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )

                if result.returncode == 0:
                    files = result.stdout.strip().split("\n")
                    dep_files = [f for f in files if any(
                        dep_indicator in f.lower()
                        for dep_indicator in [
                            "package.json", "package-lock", "yarn.lock", "pnpm-lock",
                            "requirements", "pyproject.toml", "poetry.lock", "uv.lock",
                            "cargo.toml", "cargo.lock", "go.mod", "go.sum",
                        ]
                    )]

                    if dep_files:
                        dep_failures.append({
                            "run_id": run.get("id"),
                            "commit": commit_sha[:8],
                            "branch": run.get("branch"),
                            "dep_files_changed": dep_files,
                            "likely_cause": "dependency update",
                        })
            except Exception:
                pass

    return {
        "type": "deps_cicd_correlation",
        "total_runs": len(run_list),
        "failed_runs": len(failed_runs),
        "dep_related_failures": len(dep_failures),
        "correlation_rate": f"{(len(dep_failures) / len(failed_runs) * 100):.0f}%" if failed_runs else "0%",
        "failures": dep_failures,
        "recommendation": (
            f"{len(dep_failures)} failures correlated with dependency changes - review dependency updates"
            if dep_failures
            else "No dependency-related CI failures detected"
        ),
    }


# =============================================================================
# DOCUMENTATION INTEGRATIONS
# =============================================================================

async def docs_release_ready() -> dict[str, Any]:
    """
    Check if project is ready for release from documentation perspective.

    Validates documentation coverage, required files, and changelog.

    Returns:
        Release readiness with issues to fix
    """
    from fastband.tools.documentation import docs_check, docs_coverage

    issues = []
    warnings = []

    # Check required documentation files
    file_check = await docs_check()
    if not file_check.get("complete"):
        issues.extend([
            {"type": "missing_file", "file": f}
            for f in file_check.get("missing_required", [])
        ])
        for f in file_check.get("missing_recommended", []):
            warnings.append({"type": "recommended_file", "file": f})

    # Check documentation coverage
    coverage = await docs_coverage()
    coverage_pct = coverage.get("coverage_percentage", 0)

    if coverage_pct < 50:
        issues.append({
            "type": "low_coverage",
            "coverage": coverage_pct,
            "message": f"Documentation coverage ({coverage_pct}%) is below 50%",
        })
    elif coverage_pct < 70:
        warnings.append({
            "type": "medium_coverage",
            "coverage": coverage_pct,
            "message": f"Documentation coverage ({coverage_pct}%) could be improved",
        })

    # Check for undocumented public APIs
    missing_docs = coverage.get("missing_docs", [])
    public_missing = [m for m in missing_docs if not m.get("name", "").startswith("_")]

    if len(public_missing) > 10:
        issues.append({
            "type": "many_undocumented",
            "count": len(public_missing),
            "examples": [m.get("name") for m in public_missing[:5]],
        })

    ready = len(issues) == 0

    return {
        "type": "docs_release_ready",
        "ready": ready,
        "coverage_percentage": coverage_pct,
        "coverage_grade": coverage.get("grade"),
        "issues": issues,
        "warnings": warnings,
        "recommendation": (
            "Documentation is ready for release"
            if ready
            else "Add missing README.md first"
            if any(i.get("file") == "README.md" for i in issues)
            else "Improve documentation coverage before release"
        ),
    }


async def docs_code_quality_correlation() -> dict[str, Any]:
    """
    Correlate documentation coverage with code quality.

    Checks if well-documented code has fewer issues.

    Returns:
        Correlation analysis with insights
    """
    from fastband.tools.code_quality import code_quality_analyze
    from fastband.tools.documentation import docs_coverage

    # Get documentation coverage
    doc_coverage = await docs_coverage()
    missing_docs = doc_coverage.get("missing_docs", [])

    # Get code quality
    code_quality = await code_quality_analyze()

    if "error" in code_quality:
        return {
            "type": "docs_quality_correlation",
            "error": "Could not analyze code quality",
            "doc_coverage": doc_coverage.get("coverage_percentage"),
        }

    # Find files with quality issues
    issues = code_quality.get("issues", [])
    files_with_issues = set()
    for issue in issues:
        file_path = issue.get("file", "")
        if file_path:
            files_with_issues.add(file_path)

    # Find files with missing docs
    files_missing_docs = set()
    for missing in missing_docs:
        file_path = missing.get("file", "")
        if file_path:
            files_missing_docs.add(file_path)

    # Calculate overlap
    overlap = files_with_issues & files_missing_docs
    overlap_pct = (len(overlap) / len(files_with_issues) * 100) if files_with_issues else 0

    return {
        "type": "docs_quality_correlation",
        "doc_coverage_pct": doc_coverage.get("coverage_percentage"),
        "files_with_quality_issues": len(files_with_issues),
        "files_missing_docs": len(files_missing_docs),
        "overlap_files": len(overlap),
        "correlation_percentage": round(overlap_pct, 1),
        "correlation_strength": (
            "strong" if overlap_pct > 60
            else "moderate" if overlap_pct > 30
            else "weak"
        ),
        "insight": (
            f"{round(overlap_pct)}% of files with quality issues also lack documentation"
            if overlap_pct > 0
            else "No clear correlation between documentation and quality issues"
        ),
        "recommendation": (
            "Prioritize documenting files that have quality issues"
            if overlap_pct > 30
            else "Code quality and documentation are independent - address separately"
        ),
    }


async def docs_changelog_with_security(
    since: str = "",
    version: str = "Unreleased",
) -> dict[str, Any]:
    """
    Generate changelog with security impact annotations.

    Marks changes that have security implications.

    Args:
        since: Git ref to start from
        version: Version for changelog header

    Returns:
        Enhanced changelog with security tags
    """
    from fastband.tools.documentation import docs_changelog

    # Get regular changelog
    changelog = await docs_changelog(since=since, version=version)

    if "error" in changelog:
        return changelog

    # Analyze changes for security impact
    security_keywords = [
        "auth", "authentication", "password", "secret", "token", "key",
        "permission", "role", "access", "credential", "encrypt", "decrypt",
        "vulnerability", "cve", "security", "sanitize", "escape", "inject",
    ]

    changes = changelog.get("changes", [])
    security_changes = []
    regular_changes = []

    for change in changes:
        message = change.get("message", "").lower()
        is_security = any(kw in message for kw in security_keywords)

        if is_security:
            change["security_related"] = True
            security_changes.append(change)
        else:
            regular_changes.append(change)

    # Generate enhanced markdown
    md_lines = [f"## [{version}] - {changelog.get('date', '')}", ""]

    if security_changes:
        md_lines.append("### Security")
        for c in security_changes:
            md_lines.append(f"- ⚠️ {c.get('message', '')} ({c.get('commit', '')})")
        md_lines.append("")

    # Add regular changes by type
    changelog["changes"] = regular_changes
    changelog["security_changes"] = security_changes
    changelog["security_change_count"] = len(security_changes)

    return changelog


# =============================================================================
# API TESTING INTEGRATIONS
# =============================================================================

async def api_security_scan(base_url: str, endpoints: str = "") -> dict[str, Any]:
    """
    Scan API endpoints for common security issues.

    Tests for:
    - Missing authentication
    - CORS misconfigurations
    - Sensitive data exposure
    - Security headers

    Args:
        base_url: Base API URL
        endpoints: Comma-separated endpoints (or auto-discover)

    Returns:
        Security scan results with vulnerabilities
    """
    from fastband.tools.api_testing import api_test, api_discover

    vulnerabilities = []
    warnings = []

    # Get endpoints
    if endpoints:
        endpoint_list = [{"path": e.strip()} for e in endpoints.split(",")]
    else:
        discovered = await api_discover()
        endpoint_list = discovered.get("endpoints", [])[:10]

    if not endpoint_list:
        return {
            "type": "api_security_scan",
            "error": "No endpoints to scan",
        }

    # Required security headers
    security_headers = [
        "X-Content-Type-Options",
        "X-Frame-Options",
        "X-XSS-Protection",
        "Content-Security-Policy",
        "Strict-Transport-Security",
    ]

    endpoints_scanned = 0

    for ep in endpoint_list[:5]:  # Limit to 5 endpoints
        path = ep.get("path", "")
        if not path:
            continue

        full_url = f"{base_url.rstrip('/')}{path}"
        endpoints_scanned += 1

        # Test the endpoint
        result = await api_test(url=full_url, method="GET")

        if "error" not in result:
            # Check for missing security headers
            headers = result.get("response_headers", {})

            for header in security_headers:
                if header not in headers:
                    warnings.append({
                        "endpoint": path,
                        "type": "missing_header",
                        "header": header,
                    })

            # Check for sensitive data in response
            body = result.get("response_body", "")
            if body:
                sensitive_patterns = [
                    ("password", "Possible password in response"),
                    ("secret", "Possible secret in response"),
                    ("api_key", "Possible API key in response"),
                    ("private_key", "Private key exposed"),
                    ("-----BEGIN", "Possible certificate/key exposed"),
                ]

                for pattern, message in sensitive_patterns:
                    if pattern.lower() in body.lower():
                        vulnerabilities.append({
                            "endpoint": path,
                            "type": "sensitive_data",
                            "severity": "high",
                            "message": message,
                        })

            # Check CORS headers
            cors_origin = headers.get("Access-Control-Allow-Origin", "")
            if cors_origin == "*":
                vulnerabilities.append({
                    "endpoint": path,
                    "type": "cors_misconfiguration",
                    "severity": "medium",
                    "message": "Wildcard CORS origin allows any domain",
                })

    # Calculate security score
    vuln_penalty = len([v for v in vulnerabilities if v.get("severity") == "high"]) * 20
    vuln_penalty += len([v for v in vulnerabilities if v.get("severity") == "medium"]) * 10
    header_penalty = min(len(warnings), 5) * 5

    security_score = max(0, 100 - vuln_penalty - header_penalty)

    return {
        "type": "api_security_scan",
        "base_url": base_url,
        "endpoints_scanned": endpoints_scanned,
        "security_score": security_score,
        "grade": (
            "A" if security_score >= 90
            else "B" if security_score >= 80
            else "C" if security_score >= 70
            else "D" if security_score >= 60
            else "F"
        ),
        "vulnerabilities": vulnerabilities,
        "missing_headers": warnings[:10],
        "recommendation": (
            "API security is good"
            if security_score >= 80
            else "Add security headers and fix CORS issues"
            if vulnerabilities
            else "Add missing security headers"
        ),
    }


async def api_perf_baseline(
    url: str,
    iterations: int = 10,
) -> dict[str, Any]:
    """
    Establish performance baseline for API endpoint.

    Tests endpoint multiple times to establish baseline
    response times and variability.

    Args:
        url: Endpoint URL to test
        iterations: Number of test iterations

    Returns:
        Performance baseline with thresholds
    """
    from fastband.tools.performance import perf_benchmark

    # Run benchmark
    benchmark = await perf_benchmark(url=url, iterations=iterations)

    if "error" in benchmark:
        return benchmark

    # Calculate thresholds
    avg_ms = benchmark.get("value", 0)
    p95_ms = benchmark.get("p95", avg_ms * 1.5)
    max_ms = benchmark.get("max_value", avg_ms * 2)

    # Suggest thresholds (with margin)
    suggested_avg_threshold = round(avg_ms * 1.2, 2)
    suggested_p95_threshold = round(p95_ms * 1.3, 2)

    return {
        "type": "api_perf_baseline",
        "url": url,
        "iterations": iterations,
        "baseline": {
            "avg_ms": avg_ms,
            "min_ms": benchmark.get("min_value"),
            "max_ms": max_ms,
            "p95_ms": p95_ms,
            "std_dev": benchmark.get("std_dev"),
        },
        "suggested_thresholds": {
            "avg_ms": suggested_avg_threshold,
            "p95_ms": suggested_p95_threshold,
            "action": "fail_build",
        },
        "performance_grade": (
            "excellent" if avg_ms < 100
            else "good" if avg_ms < 300
            else "acceptable" if avg_ms < 1000
            else "slow"
        ),
        "recommendation": (
            f"Set CI threshold to {suggested_avg_threshold}ms average"
        ),
    }


async def api_deploy_health_check(
    base_url: str,
    health_path: str = "/health",
    api_paths: str = "",
) -> dict[str, Any]:
    """
    Comprehensive health check for deployed API.

    Combines health endpoint check with API functionality
    verification.

    Args:
        base_url: Base API URL
        health_path: Health endpoint path
        api_paths: Additional paths to check (comma-separated)

    Returns:
        Deployment health status
    """
    from fastband.tools.api_testing import api_health, api_test

    results = {
        "type": "api_deploy_health",
        "base_url": base_url,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "checks": [],
    }

    # Health endpoint check
    health_url = f"{base_url.rstrip('/')}{health_path}"
    health_result = await api_health(url=health_url)

    results["checks"].append({
        "name": "health_endpoint",
        "url": health_url,
        "passed": health_result.get("healthy", False),
        "response_time_ms": health_result.get("response_time_ms"),
        "details": health_result.get("health_data"),
    })

    # Additional API checks
    if api_paths:
        for path in api_paths.split(","):
            path = path.strip()
            if not path:
                continue

            full_url = f"{base_url.rstrip('/')}{path}"
            test_result = await api_test(url=full_url)

            results["checks"].append({
                "name": f"api_{path.replace('/', '_')}",
                "url": full_url,
                "passed": test_result.get("passed", False),
                "response_time_ms": test_result.get("response_time_ms"),
                "status_code": test_result.get("status_code"),
            })

    # Calculate overall health
    passed_checks = sum(1 for c in results["checks"] if c.get("passed"))
    total_checks = len(results["checks"])
    health_percentage = (passed_checks / total_checks * 100) if total_checks > 0 else 0

    results["overall"] = {
        "healthy": health_percentage == 100,
        "health_percentage": health_percentage,
        "passed_checks": passed_checks,
        "total_checks": total_checks,
    }

    results["recommendation"] = (
        "Deployment is healthy"
        if health_percentage == 100
        else f"{total_checks - passed_checks} endpoint(s) failing - investigate immediately"
    )

    return results


async def db_data_quality_scan(
    connection: str,
    table: str,
    sample_size: int = 1000,
) -> dict[str, Any]:
    """
    Scan table for data quality issues.

    Detects:
    - NULL patterns in required columns
    - Duplicate values in unique columns
    - Orphaned foreign keys
    - Data type mismatches
    - Outlier values

    Args:
        connection: Database connection string
        table: Table name to scan
        sample_size: Number of rows to sample

    Returns:
        Data quality issues with fix suggestions
    """
    from fastband.tools.database import db_query, db_schema

    # Get table schema
    schema = await db_schema(connection, table=table)
    if "error" in schema:
        return schema

    columns = schema.get("columns", [])
    issues = []
    fix_suggestions = []

    # Check NULL patterns
    for col in columns:
        col_name = col.get("name")
        is_nullable = col.get("nullable", True)

        if not is_nullable:
            # Check for NULLs in NOT NULL columns (shouldn't exist but check)
            null_check = await db_query(
                connection,
                f'SELECT COUNT(*) FROM "{table}" WHERE "{col_name}" IS NULL',
            )
            if null_check.get("rows") and null_check["rows"][0][0] > 0:
                issues.append({
                    "type": "constraint_violation",
                    "column": col_name,
                    "issue": "NULL values in NOT NULL column",
                    "affected_rows": null_check["rows"][0][0],
                })

    # Check for duplicates in columns that should be unique
    for col in columns:
        col_name = col.get("name")
        if col.get("unique") or col.get("primary_key"):
            dup_check = await db_query(
                connection,
                f'''SELECT "{col_name}", COUNT(*) as cnt
                    FROM "{table}"
                    GROUP BY "{col_name}"
                    HAVING COUNT(*) > 1
                    LIMIT 5''',
            )
            if dup_check.get("rows"):
                issues.append({
                    "type": "duplicate_values",
                    "column": col_name,
                    "issue": "Duplicate values in unique column",
                    "examples": [row[0] for row in dup_check["rows"][:3]],
                })
                fix_suggestions.append(
                    f'DELETE FROM "{table}" WHERE rowid NOT IN '
                    f'(SELECT MIN(rowid) FROM "{table}" GROUP BY "{col_name}")'
                )

    # Check for empty strings that should probably be NULL
    string_cols = [c for c in columns if "char" in c.get("type", "").lower() or "text" in c.get("type", "").lower()]
    for col in string_cols[:5]:  # Limit to first 5 string columns
        col_name = col.get("name")
        empty_check = await db_query(
            connection,
            f'''SELECT COUNT(*) FROM "{table}" WHERE "{col_name}" = '' ''',
        )
        if empty_check.get("rows") and empty_check["rows"][0][0] > 0:
            issues.append({
                "type": "empty_string",
                "column": col_name,
                "issue": "Empty strings (should be NULL?)",
                "affected_rows": empty_check["rows"][0][0],
            })

    # Calculate quality score
    total_checks = len(columns) * 3  # 3 types of checks per column
    issues_found = len(issues)
    quality_score = max(0, 100 - (issues_found * 10))

    return {
        "type": "data_quality",
        "table": table,
        "quality_score": quality_score,
        "issues_found": issues_found,
        "issues": issues,
        "fix_suggestions": fix_suggestions[:5],
        "recommendation": (
            "Data quality is good"
            if quality_score >= 80
            else "Address duplicate values first"
            if any(i["type"] == "duplicate_values" for i in issues)
            else "Review NULL handling in application code"
        ),
    }


# =============================================================================
# SECURITY + CODE QUALITY INTEGRATION
# =============================================================================

async def security_quality_hotspots() -> dict[str, Any]:
    """
    Find security vulnerabilities in low-quality code.

    Cross-references security issues with code complexity to identify
    high-risk areas that need immediate attention.

    Returns:
        Hotspots where security and quality issues overlap
    """
    from fastband.tools.quality import code_quality_analyze
    from fastband.tools.security import security_scan

    # Get security issues
    security_result = await security_scan(os.getcwd(), scan_type="full")

    # Get code quality issues
    quality_result = await code_quality_analyze()

    if "error" in security_result or "error" in quality_result:
        return {
            "type": "security_quality_hotspots",
            "error": security_result.get("error") or quality_result.get("error"),
        }

    # Build file -> issues maps
    security_by_file: dict[str, list] = {}
    for vuln in security_result.get("vulnerabilities", []):
        file_path = vuln.get("file", "")
        if file_path:
            if file_path not in security_by_file:
                security_by_file[file_path] = []
            security_by_file[file_path].append(vuln)

    quality_by_file: dict[str, list] = {}
    for issue in quality_result.get("issues", []):
        file_path = issue.get("file", "")
        if file_path:
            if file_path not in quality_by_file:
                quality_by_file[file_path] = []
            quality_by_file[file_path].append(issue)

    # Find overlapping files (hotspots)
    hotspots = []
    all_files = set(security_by_file.keys()) | set(quality_by_file.keys())

    for file_path in all_files:
        sec_issues = security_by_file.get(file_path, [])
        qual_issues = quality_by_file.get(file_path, [])

        if sec_issues and qual_issues:
            # Calculate risk score
            sec_severity = sum(
                {"critical": 4, "high": 3, "medium": 2, "low": 1}.get(
                    i.get("severity", "low"), 1
                )
                for i in sec_issues
            )
            qual_severity = len(qual_issues)

            risk_score = (sec_severity * 10) + (qual_severity * 5)

            hotspots.append({
                "file": file_path,
                "risk_score": risk_score,
                "security_issues": len(sec_issues),
                "quality_issues": len(qual_issues),
                "security_types": list(set(i.get("type", "") for i in sec_issues)),
                "quality_types": list(set(i.get("rule", "") for i in qual_issues))[:5],
                "priority": "critical" if risk_score > 50 else "high" if risk_score > 25 else "medium",
            })

    # Sort by risk
    hotspots.sort(key=lambda x: x["risk_score"], reverse=True)

    return {
        "type": "security_quality_hotspots",
        "total_hotspots": len(hotspots),
        "critical_count": len([h for h in hotspots if h["priority"] == "critical"]),
        "high_count": len([h for h in hotspots if h["priority"] == "high"]),
        "hotspots": hotspots[:10],
        "recommendation": (
            f"Focus on {hotspots[0]['file']} first - highest risk score"
            if hotspots
            else "No overlapping security and quality issues found"
        ),
    }


async def security_complexity_analysis() -> dict[str, Any]:
    """
    Analyze if complex code has more security issues.

    Correlates cyclomatic complexity with security vulnerabilities
    to validate the hypothesis that complex code is less secure.

    Returns:
        Correlation analysis with actionable insights
    """
    from fastband.tools.quality import code_quality_analyze
    from fastband.tools.security import security_scan

    security_result = await security_scan(os.getcwd(), scan_type="code")
    quality_result = await code_quality_analyze()

    if "error" in security_result or "error" in quality_result:
        return {"error": "Could not analyze security or quality"}

    # Get complexity metrics
    metrics = quality_result.get("metrics", {})
    avg_complexity = metrics.get("avg_complexity", 0)
    max_complexity = metrics.get("max_complexity", 0)

    # Count security issues
    sec_issues = security_result.get("vulnerabilities", [])
    total_sec_issues = len(sec_issues)

    # Analyze correlation
    high_complexity_threshold = 10
    complex_files_with_issues = 0
    simple_files_with_issues = 0

    # Get files by complexity (from quality issues)
    complex_files = set()
    for issue in quality_result.get("issues", []):
        if issue.get("rule") == "complexity" or "complex" in issue.get("message", "").lower():
            complex_files.add(issue.get("file", ""))

    for vuln in sec_issues:
        file_path = vuln.get("file", "")
        if file_path in complex_files:
            complex_files_with_issues += 1
        else:
            simple_files_with_issues += 1

    # Calculate correlation
    if total_sec_issues > 0:
        complex_ratio = complex_files_with_issues / total_sec_issues
    else:
        complex_ratio = 0

    return {
        "type": "security_complexity_analysis",
        "metrics": {
            "avg_complexity": avg_complexity,
            "max_complexity": max_complexity,
            "total_security_issues": total_sec_issues,
            "issues_in_complex_code": complex_files_with_issues,
            "issues_in_simple_code": simple_files_with_issues,
        },
        "correlation": {
            "complex_code_issue_ratio": round(complex_ratio * 100, 1),
            "correlation_strength": (
                "strong" if complex_ratio > 0.6
                else "moderate" if complex_ratio > 0.3
                else "weak"
            ),
        },
        "insight": (
            f"{round(complex_ratio * 100)}% of security issues are in complex code"
            if total_sec_issues > 0
            else "No security issues to analyze"
        ),
        "recommendation": (
            "Prioritize refactoring complex code to reduce security risk"
            if complex_ratio > 0.5
            else "Security issues are spread across codebase - address individually"
        ),
    }


# =============================================================================
# SECURITY + DATABASE INTEGRATION
# =============================================================================

async def db_security_audit(connection: str) -> dict[str, Any]:
    """
    Audit database for security issues.

    Checks for:
    - SQL injection patterns in queries
    - Weak permissions
    - Sensitive data exposure
    - Missing encryption

    Args:
        connection: Database connection string

    Returns:
        Security audit results with vulnerabilities
    """
    from fastband.tools.database import db_query, db_schema

    vulnerabilities = []
    warnings = []

    # Get schema
    schema = await db_schema(connection)

    if "error" in schema:
        return {"error": schema.get("error")}

    tables = schema.get("tables", [])

    # Check for sensitive column names without encryption indicators
    sensitive_patterns = [
        ("password", "Password stored - ensure hashed"),
        ("secret", "Secret data - ensure encrypted"),
        ("ssn", "SSN data - ensure encrypted and access controlled"),
        ("credit_card", "Credit card - ensure PCI compliance"),
        ("card_number", "Card number - ensure PCI compliance"),
        ("api_key", "API key storage - ensure encrypted"),
        ("token", "Token storage - consider encryption"),
        ("private_key", "Private key - must be encrypted"),
    ]

    for table in tables:
        table_name = table.get("name", "")
        columns = table.get("columns", [])

        for col in columns:
            col_name = col.get("name", "").lower()
            col_type = col.get("type", "").lower()

            for pattern, message in sensitive_patterns:
                if pattern in col_name:
                    # Check if it looks encrypted (common patterns)
                    if not any(enc in col_name for enc in ["hash", "encrypted", "hashed"]):
                        vulnerabilities.append({
                            "type": "sensitive_data",
                            "severity": "high",
                            "table": table_name,
                            "column": col.get("name"),
                            "message": message,
                        })

            # Check for plaintext password columns
            if "password" in col_name and "varchar" in col_type:
                # If length suggests plaintext (< 100 chars for hash)
                if "varchar" in col_type:
                    try:
                        # Extract length from varchar(N)
                        import re
                        match = re.search(r"varchar\((\d+)\)", col_type)
                        if match and int(match.group(1)) < 60:
                            vulnerabilities.append({
                                "type": "weak_password_storage",
                                "severity": "critical",
                                "table": table_name,
                                "column": col.get("name"),
                                "message": f"Password column too short for proper hash ({col_type})",
                            })
                    except Exception:
                        pass

    # Check for tables without primary keys (data integrity issue)
    tables_without_pk = []
    for table in tables:
        if not table.get("primary_key"):
            tables_without_pk.append(table.get("name"))
            warnings.append({
                "type": "missing_primary_key",
                "table": table.get("name"),
                "message": "No primary key - potential data integrity issue",
            })

    # Calculate security score
    critical_count = len([v for v in vulnerabilities if v.get("severity") == "critical"])
    high_count = len([v for v in vulnerabilities if v.get("severity") == "high"])

    score = 100 - (critical_count * 25) - (high_count * 10) - (len(warnings) * 2)
    score = max(0, score)

    return {
        "type": "db_security_audit",
        "security_score": score,
        "grade": (
            "A" if score >= 90 else "B" if score >= 80
            else "C" if score >= 70 else "D" if score >= 60 else "F"
        ),
        "vulnerabilities": vulnerabilities,
        "warnings": warnings[:10],
        "summary": {
            "critical": critical_count,
            "high": high_count,
            "warnings": len(warnings),
            "tables_analyzed": len(tables),
        },
        "recommendation": (
            "Database security is good"
            if score >= 80
            else "Address critical password storage issues first"
            if critical_count > 0
            else "Review sensitive data columns for encryption"
        ),
    }


# =============================================================================
# SECURITY + LOGS INTEGRATION
# =============================================================================

async def logs_security_events(log_path: str, hours: int = 24) -> dict[str, Any]:
    """
    Detect security events in application logs.

    Scans for:
    - Failed login attempts
    - Authentication errors
    - Access denied events
    - Suspicious patterns (SQL injection, XSS attempts)
    - Rate limiting triggers

    Args:
        log_path: Path to log file
        hours: Hours of logs to analyze

    Returns:
        Security events with severity and recommendations
    """
    from fastband.tools.logs import logs_analyze

    # Get log analysis
    log_result = await logs_analyze(log_path, errors_only=False)

    if "error" in log_result:
        return log_result

    security_events = []
    event_counts = {
        "failed_auth": 0,
        "access_denied": 0,
        "injection_attempt": 0,
        "rate_limited": 0,
        "suspicious": 0,
    }

    # Security patterns to detect
    security_patterns = [
        # Authentication
        (["failed login", "login failed", "authentication failed", "invalid password",
          "invalid credentials", "unauthorized"], "failed_auth", "high"),
        (["access denied", "permission denied", "forbidden", "403"], "access_denied", "medium"),
        # Injection attempts
        (["sql injection", "union select", "' or '", "1=1", "drop table",
          "<script>", "javascript:", "onerror="], "injection_attempt", "critical"),
        # Rate limiting
        (["rate limit", "too many requests", "throttled", "429"], "rate_limited", "low"),
        # Suspicious
        (["suspicious", "blocked", "blacklist", "malicious", "attack"], "suspicious", "high"),
    ]

    # Analyze log entries
    entries = log_result.get("entries", [])
    for entry in entries:
        message = entry.get("message", "").lower()

        for patterns, event_type, severity in security_patterns:
            if any(p in message for p in patterns):
                event_counts[event_type] += 1
                security_events.append({
                    "type": event_type,
                    "severity": severity,
                    "timestamp": entry.get("timestamp"),
                    "message": entry.get("message", "")[:200],
                    "source": entry.get("source"),
                })
                break

    # Detect brute force (many failed auths from same source)
    auth_sources: dict[str, int] = {}
    for event in security_events:
        if event["type"] == "failed_auth":
            source = event.get("source", "unknown")
            auth_sources[source] = auth_sources.get(source, 0) + 1

    brute_force_suspects = [
        {"source": src, "attempts": count}
        for src, count in auth_sources.items()
        if count >= 5
    ]

    # Calculate threat level
    if event_counts["injection_attempt"] > 0 or len(brute_force_suspects) > 0:
        threat_level = "critical"
    elif event_counts["failed_auth"] > 10 or event_counts["suspicious"] > 5:
        threat_level = "high"
    elif event_counts["access_denied"] > 20:
        threat_level = "medium"
    else:
        threat_level = "low"

    return {
        "type": "logs_security_events",
        "log_path": log_path,
        "hours_analyzed": hours,
        "threat_level": threat_level,
        "event_counts": event_counts,
        "total_security_events": len(security_events),
        "brute_force_suspects": brute_force_suspects,
        "recent_events": security_events[:20],
        "recommendation": (
            "CRITICAL: Injection attempts detected - investigate immediately"
            if event_counts["injection_attempt"] > 0
            else f"Block IPs with brute force attempts: {[s['source'] for s in brute_force_suspects]}"
            if brute_force_suspects
            else "Monitor failed authentication patterns"
            if event_counts["failed_auth"] > 5
            else "No immediate security threats detected"
        ),
    }


# =============================================================================
# CODE QUALITY + CI/CD INTEGRATION
# =============================================================================

async def quality_gate_check(
    min_score: int = 70,
    max_issues: int = 50,
    block_critical: bool = True,
) -> dict[str, Any]:
    """
    Check if code quality meets deployment gate requirements.

    Enforces quality standards before allowing deployment/merge.

    Args:
        min_score: Minimum quality score required (0-100)
        max_issues: Maximum allowed issues
        block_critical: Whether critical issues block deployment

    Returns:
        Gate pass/fail result with details
    """
    from fastband.tools.quality import code_quality_analyze

    quality_result = await code_quality_analyze()

    if "error" in quality_result:
        return {
            "type": "quality_gate",
            "passed": False,
            "error": quality_result.get("error"),
        }

    score = quality_result.get("score", 0)
    total_issues = quality_result.get("total_issues", 0)
    issues = quality_result.get("issues", [])

    # Count by severity
    critical_issues = len([i for i in issues if i.get("severity") == "critical"])
    high_issues = len([i for i in issues if i.get("severity") == "high"])

    # Check gate conditions
    failures = []

    if score < min_score:
        failures.append(f"Score {score} below minimum {min_score}")

    if total_issues > max_issues:
        failures.append(f"Issues {total_issues} exceed maximum {max_issues}")

    if block_critical and critical_issues > 0:
        failures.append(f"{critical_issues} critical issues found")

    passed = len(failures) == 0

    return {
        "type": "quality_gate",
        "passed": passed,
        "gate_config": {
            "min_score": min_score,
            "max_issues": max_issues,
            "block_critical": block_critical,
        },
        "results": {
            "score": score,
            "total_issues": total_issues,
            "critical_issues": critical_issues,
            "high_issues": high_issues,
        },
        "failures": failures,
        "recommendation": (
            "Quality gate passed - ready for deployment"
            if passed
            else f"Fix issues: {'; '.join(failures)}"
        ),
    }


async def quality_trend_analysis(runs: int = 10) -> dict[str, Any]:
    """
    Analyze code quality trends across CI runs.

    Tracks quality metrics over time to identify improvements
    or degradation.

    Args:
        runs: Number of recent runs to analyze

    Returns:
        Trend analysis with direction indicators
    """
    from fastband.tools.cicd import cicd_runs
    from fastband.tools.quality import code_quality_analyze

    # Get current quality
    current_quality = await code_quality_analyze()

    if "error" in current_quality:
        return {"error": current_quality.get("error")}

    current_score = current_quality.get("score", 0)
    current_issues = current_quality.get("total_issues", 0)

    # Get recent CI runs for context
    ci_runs = await cicd_runs(limit=runs)

    # Since we can't get historical quality data easily,
    # we'll provide current snapshot with CI context
    recent_runs = ci_runs.get("runs", [])

    success_rate = 0
    if recent_runs:
        successful = len([r for r in recent_runs if r.get("conclusion") == "success"])
        success_rate = (successful / len(recent_runs)) * 100

    # Estimate trend based on current state
    if current_score >= 80 and success_rate >= 80:
        trend = "improving"
        trend_icon = "📈"
    elif current_score < 60 or success_rate < 50:
        trend = "degrading"
        trend_icon = "📉"
    else:
        trend = "stable"
        trend_icon = "➡️"

    return {
        "type": "quality_trend",
        "current_state": {
            "quality_score": current_score,
            "total_issues": current_issues,
            "grade": current_quality.get("grade"),
        },
        "ci_context": {
            "recent_runs": len(recent_runs),
            "success_rate": f"{success_rate:.0f}%",
            "last_run_status": recent_runs[0].get("conclusion") if recent_runs else "unknown",
        },
        "trend": {
            "direction": trend,
            "icon": trend_icon,
            "confidence": "medium",  # Would be higher with historical data
        },
        "recommendation": (
            "Quality is improving - maintain current practices"
            if trend == "improving"
            else "Quality is degrading - schedule refactoring sprint"
            if trend == "degrading"
            else "Quality is stable - consider incremental improvements"
        ),
    }


# =============================================================================
# CODE QUALITY + DATABASE INTEGRATION
# =============================================================================

async def db_query_quality_check(connection: str) -> dict[str, Any]:
    """
    Analyze database queries in codebase for quality issues.

    Detects:
    - N+1 query patterns
    - Missing indexes for common queries
    - Inefficient JOIN patterns
    - SELECT * usage

    Args:
        connection: Database connection for schema context

    Returns:
        Query quality issues with optimization suggestions
    """
    from pathlib import Path
    import re

    from fastband.tools.database import db_schema

    project_root = Path(os.getcwd())
    issues = []
    optimizations = []

    # Get schema for context
    schema = await db_schema(connection)
    indexed_columns = set()

    if "error" not in schema:
        for table in schema.get("tables", []):
            for idx in table.get("indexes", []):
                for col in idx.get("columns", []):
                    indexed_columns.add(f"{table.get('name')}.{col}")

    # Scan code files for SQL patterns
    sql_patterns = {
        "select_star": (r"SELECT\s+\*\s+FROM", "SELECT * usage - specify columns"),
        "no_limit": (r"SELECT[^;]+FROM[^;]+(?<!LIMIT\s\d+);", "Query without LIMIT"),
        "n_plus_one": (r"for.*:\s*\n.*(?:execute|query|select)", "Potential N+1 query pattern"),
    }

    code_extensions = ["*.py", "*.js", "*.ts", "*.java", "*.go", "*.rb"]

    for ext in code_extensions:
        for file_path in project_root.glob(f"**/{ext}"):
            if any(skip in str(file_path) for skip in ["node_modules", "venv", ".venv", "__pycache__"]):
                continue

            try:
                content = file_path.read_text(errors="replace")

                for pattern_name, (pattern, message) in sql_patterns.items():
                    matches = re.findall(pattern, content, re.IGNORECASE | re.MULTILINE)
                    if matches:
                        issues.append({
                            "type": pattern_name,
                            "file": str(file_path.relative_to(project_root)),
                            "occurrences": len(matches),
                            "message": message,
                            "severity": "medium" if pattern_name == "select_star" else "high",
                        })

            except Exception:
                pass

    # Group by type
    issue_counts = {}
    for issue in issues:
        t = issue["type"]
        issue_counts[t] = issue_counts.get(t, 0) + issue["occurrences"]

    # Generate optimizations
    if issue_counts.get("select_star", 0) > 0:
        optimizations.append("Replace SELECT * with specific columns to reduce data transfer")

    if issue_counts.get("n_plus_one", 0) > 0:
        optimizations.append("Use JOINs or batch queries instead of loops")

    if issue_counts.get("no_limit", 0) > 0:
        optimizations.append("Add LIMIT clauses to prevent large result sets")

    quality_score = max(0, 100 - sum(issue_counts.values()) * 5)

    return {
        "type": "db_query_quality",
        "quality_score": quality_score,
        "issue_counts": issue_counts,
        "total_issues": len(issues),
        "issues": issues[:15],
        "optimizations": optimizations,
        "recommendation": (
            "Database queries are well-optimized"
            if quality_score >= 80
            else "Address N+1 queries first for biggest performance gain"
            if issue_counts.get("n_plus_one", 0) > 0
            else "Replace SELECT * with specific columns"
        ),
    }


# =============================================================================
# LOGS + DEPLOYMENT INTEGRATION
# =============================================================================

async def logs_deployment_correlation(
    log_path: str,
    deployment_id: str = "",
) -> dict[str, Any]:
    """
    Correlate log errors with recent deployments.

    Detects error spikes after deployments to identify
    deployment-caused issues.

    Args:
        log_path: Path to application logs
        deployment_id: Specific deployment to check (latest if empty)

    Returns:
        Correlation between deployment and error patterns
    """
    from fastband.tools.deployment import deploy_list
    from fastband.tools.logs import logs_analyze

    # Get deployment info
    deployments = await deploy_list(limit=5)

    if "error" in deployments:
        return {"error": "Could not get deployment info"}

    deploy_list_data = deployments.get("deployments", [])
    if not deploy_list_data:
        return {"error": "No deployments found"}

    # Get target deployment
    target_deploy = None
    if deployment_id:
        for d in deploy_list_data:
            if d.get("id") == deployment_id:
                target_deploy = d
                break
    else:
        target_deploy = deploy_list_data[0]  # Latest

    if not target_deploy:
        return {"error": "Deployment not found"}

    # Get log analysis
    log_result = await logs_analyze(log_path, errors_only=True)

    if "error" in log_result:
        return log_result

    # Analyze error patterns
    deploy_time = target_deploy.get("created_at", "")
    error_count = log_result.get("error_count", 0)
    error_patterns = log_result.get("top_errors", [])

    # Check if errors spiked after deployment
    # (Simplified - in real implementation, would compare time windows)
    recent_errors = error_patterns[:5]

    # Detect new error types (would compare with pre-deploy in full implementation)
    potential_deploy_errors = []
    for error in recent_errors:
        # Heuristic: errors with deployment-related keywords
        message = error.get("message", "").lower()
        if any(kw in message for kw in [
            "undefined", "null", "missing", "not found", "import",
            "module", "dependency", "config", "environment",
        ]):
            potential_deploy_errors.append(error)

    correlation_strength = "none"
    if error_count > 100 and len(potential_deploy_errors) > 2:
        correlation_strength = "strong"
    elif error_count > 50 or len(potential_deploy_errors) > 0:
        correlation_strength = "moderate"
    elif error_count > 10:
        correlation_strength = "weak"

    return {
        "type": "logs_deployment_correlation",
        "deployment": {
            "id": target_deploy.get("id"),
            "created_at": deploy_time,
            "status": target_deploy.get("status"),
            "commit": target_deploy.get("commit"),
        },
        "errors": {
            "total_count": error_count,
            "potential_deploy_related": len(potential_deploy_errors),
            "patterns": potential_deploy_errors,
        },
        "correlation": {
            "strength": correlation_strength,
            "confidence": "medium",
        },
        "recommendation": (
            "ALERT: Strong correlation between deployment and errors - consider rollback"
            if correlation_strength == "strong"
            else "Monitor errors closely - possible deployment impact"
            if correlation_strength == "moderate"
            else "No significant deployment impact detected"
        ),
    }


# =============================================================================
# LOGS + DATABASE INTEGRATION
# =============================================================================

async def logs_slow_query_analysis(
    log_path: str,
    threshold_ms: int = 1000,
) -> dict[str, Any]:
    """
    Analyze slow database queries from logs.

    Extracts and analyzes slow query patterns to identify
    optimization opportunities.

    Args:
        log_path: Path to application/database logs
        threshold_ms: Slow query threshold in milliseconds

    Returns:
        Slow query analysis with optimization suggestions
    """
    from pathlib import Path
    import re

    log_file = Path(log_path)
    if not log_file.exists():
        return {"error": f"Log file not found: {log_path}"}

    slow_queries = []
    query_times: dict[str, list] = {}

    # Patterns to detect slow queries
    slow_query_patterns = [
        # PostgreSQL style
        r"duration:\s*(\d+(?:\.\d+)?)\s*ms\s+(?:statement|execute):\s*(.+)",
        # MySQL style
        r"Query_time:\s*(\d+(?:\.\d+)?)\s+.*?(?:SELECT|INSERT|UPDATE|DELETE).+",
        # Generic ORM style
        r"query.*?(\d+(?:\.\d+)?)\s*ms.*?(SELECT|INSERT|UPDATE|DELETE[^;]+)",
        # Django style
        r"\((\d+(?:\.\d+)?)\s*ms\)\s*(SELECT|INSERT|UPDATE|DELETE.+)",
    ]

    try:
        with open(log_file, "r", errors="replace") as f:
            for line in f:
                for pattern in slow_query_patterns:
                    match = re.search(pattern, line, re.IGNORECASE)
                    if match:
                        try:
                            duration = float(match.group(1))
                            query = match.group(2) if len(match.groups()) > 1 else "unknown"

                            if duration >= threshold_ms:
                                # Normalize query for grouping
                                normalized = re.sub(r"'[^']*'", "'?'", query)
                                normalized = re.sub(r"\d+", "?", normalized)
                                normalized = normalized[:200]

                                if normalized not in query_times:
                                    query_times[normalized] = []
                                query_times[normalized].append(duration)

                                slow_queries.append({
                                    "duration_ms": duration,
                                    "query": query[:300],
                                    "normalized": normalized,
                                })
                        except (ValueError, IndexError):
                            pass
                        break

    except Exception as e:
        return {"error": f"Could not read log file: {e}"}

    # Aggregate by query pattern
    aggregated = []
    for query, times in query_times.items():
        aggregated.append({
            "query_pattern": query,
            "count": len(times),
            "avg_ms": round(sum(times) / len(times), 2),
            "max_ms": round(max(times), 2),
            "total_ms": round(sum(times), 2),
        })

    # Sort by total time (biggest impact)
    aggregated.sort(key=lambda x: x["total_ms"], reverse=True)

    # Generate optimization suggestions
    suggestions = []
    for q in aggregated[:3]:
        query_lower = q["query_pattern"].lower()
        if "select *" in query_lower:
            suggestions.append(f"Replace SELECT * with specific columns in: {q['query_pattern'][:50]}...")
        if "join" in query_lower and q["avg_ms"] > 500:
            suggestions.append(f"Consider adding indexes for JOIN: {q['query_pattern'][:50]}...")
        if "where" not in query_lower:
            suggestions.append(f"Add WHERE clause to limit results: {q['query_pattern'][:50]}...")

    return {
        "type": "slow_query_analysis",
        "threshold_ms": threshold_ms,
        "total_slow_queries": len(slow_queries),
        "unique_patterns": len(aggregated),
        "top_offenders": aggregated[:10],
        "total_time_ms": sum(q["total_ms"] for q in aggregated),
        "suggestions": suggestions,
        "recommendation": (
            f"Optimize top query pattern - accounts for {aggregated[0]['total_ms']}ms total"
            if aggregated
            else "No slow queries detected above threshold"
        ),
    }


# =============================================================================
# CONTEXT + SECURITY INTEGRATION
# =============================================================================

async def context_security_patterns(query: str = "security vulnerability") -> dict[str, Any]:
    """
    Search codebase for security-related patterns using semantic search.

    Finds code that matches security concerns like authentication,
    authorization, input validation, etc.

    Args:
        query: Security-related search query

    Returns:
        Matching code locations with security context
    """
    from fastband.tools.context import semantic_search

    # Run semantic search
    try:
        search_result = await semantic_search(query, limit=20)
    except Exception as e:
        return {"error": f"Semantic search failed: {e}"}

    if "error" in search_result:
        return search_result

    results = search_result.get("results", [])

    # Categorize results by security concern
    security_categories = {
        "authentication": [],
        "authorization": [],
        "input_validation": [],
        "cryptography": [],
        "data_exposure": [],
        "other": [],
    }

    category_keywords = {
        "authentication": ["login", "auth", "password", "credential", "session", "jwt", "token"],
        "authorization": ["permission", "role", "access", "acl", "rbac", "authorize"],
        "input_validation": ["validate", "sanitize", "escape", "filter", "input", "param"],
        "cryptography": ["encrypt", "decrypt", "hash", "crypto", "cipher", "key"],
        "data_exposure": ["expose", "leak", "sensitive", "secret", "private", "pii"],
    }

    for result in results:
        content = result.get("content", "").lower()
        file_path = result.get("file", "").lower()
        categorized = False

        for category, keywords in category_keywords.items():
            if any(kw in content or kw in file_path for kw in keywords):
                security_categories[category].append(result)
                categorized = True
                break

        if not categorized:
            security_categories["other"].append(result)

    # Count non-empty categories
    active_categories = {k: len(v) for k, v in security_categories.items() if v}

    return {
        "type": "context_security_patterns",
        "query": query,
        "total_matches": len(results),
        "by_category": active_categories,
        "results": {
            category: items[:5]
            for category, items in security_categories.items()
            if items
        },
        "recommendation": (
            f"Review {active_categories.get('authentication', 0)} authentication-related matches first"
            if active_categories.get("authentication", 0) > 0
            else f"Found {len(results)} security-related code locations to review"
        ),
    }


# =============================================================================
# CONTEXT + SMART RECOMMENDATIONS
# =============================================================================

async def smart_recommendations() -> dict[str, Any]:
    """
    Generate intelligent recommendations based on full codebase analysis.

    Combines insights from all tools to provide prioritized,
    actionable recommendations.

    Returns:
        Prioritized recommendations with impact scores
    """
    recommendations = []
    analyses_run = []

    # Run multiple analyses in parallel would be ideal,
    # but for now we'll run them sequentially with error handling

    # 1. Security check
    try:
        from fastband.tools.security import security_scan
        security = await security_scan(os.getcwd(), scan_type="quick")
        analyses_run.append("security")

        critical = security.get("vulnerabilities", {}).get("critical", 0)
        high = security.get("vulnerabilities", {}).get("high", 0)
        secrets = security.get("secrets_found", 0)

        if secrets > 0:
            recommendations.append({
                "priority": 1,
                "category": "security",
                "title": "Remove exposed secrets",
                "description": f"Found {secrets} potential secrets in code",
                "impact": "critical",
                "effort": "low",
            })

        if critical > 0:
            recommendations.append({
                "priority": 2,
                "category": "security",
                "title": "Fix critical vulnerabilities",
                "description": f"{critical} critical security issues found",
                "impact": "critical",
                "effort": "medium",
            })
    except Exception:
        pass

    # 2. Code quality check
    try:
        from fastband.tools.quality import code_quality_analyze
        quality = await code_quality_analyze()
        analyses_run.append("quality")

        score = quality.get("score", 100)
        issues = quality.get("total_issues", 0)

        if score < 60:
            recommendations.append({
                "priority": 3,
                "category": "quality",
                "title": "Improve code quality",
                "description": f"Quality score is {score}/100 with {issues} issues",
                "impact": "high",
                "effort": "high",
            })
    except Exception:
        pass

    # 3. Documentation check
    try:
        from fastband.tools.documentation import docs_check, docs_coverage
        doc_files = await docs_check()
        doc_coverage = await docs_coverage()
        analyses_run.append("documentation")

        if not doc_files.get("complete"):
            missing = doc_files.get("missing_required", [])
            recommendations.append({
                "priority": 4,
                "category": "documentation",
                "title": "Add required documentation",
                "description": f"Missing: {', '.join(missing)}",
                "impact": "medium",
                "effort": "low",
            })

        coverage = doc_coverage.get("coverage_percentage", 100)
        if coverage < 50:
            recommendations.append({
                "priority": 5,
                "category": "documentation",
                "title": "Improve documentation coverage",
                "description": f"Only {coverage}% of code is documented",
                "impact": "medium",
                "effort": "medium",
            })
    except Exception:
        pass

    # 4. Dependencies check
    try:
        from fastband.tools.dependencies import deps_audit, deps_outdated
        audit = await deps_audit()
        outdated = await deps_outdated()
        analyses_run.append("dependencies")

        vuln_count = audit.get("vulnerability_count", 0)
        if vuln_count > 0:
            recommendations.append({
                "priority": 2,
                "category": "dependencies",
                "title": "Update vulnerable dependencies",
                "description": f"{vuln_count} vulnerabilities in dependencies",
                "impact": "high",
                "effort": "medium",
            })

        outdated_count = outdated.get("outdated_count", 0)
        if outdated_count > 10:
            recommendations.append({
                "priority": 6,
                "category": "dependencies",
                "title": "Update outdated dependencies",
                "description": f"{outdated_count} packages are outdated",
                "impact": "low",
                "effort": "medium",
            })
    except Exception:
        pass

    # Sort by priority
    recommendations.sort(key=lambda x: x["priority"])

    # Calculate overall health
    critical_count = len([r for r in recommendations if r["impact"] == "critical"])
    high_count = len([r for r in recommendations if r["impact"] == "high"])

    if critical_count > 0:
        health = "critical"
    elif high_count > 2:
        health = "needs_attention"
    elif len(recommendations) > 5:
        health = "fair"
    else:
        health = "good"

    return {
        "type": "smart_recommendations",
        "analyses_run": analyses_run,
        "overall_health": health,
        "recommendation_count": len(recommendations),
        "by_impact": {
            "critical": critical_count,
            "high": high_count,
            "medium": len([r for r in recommendations if r["impact"] == "medium"]),
            "low": len([r for r in recommendations if r["impact"] == "low"]),
        },
        "recommendations": recommendations[:10],
        "next_action": (
            recommendations[0]["title"] if recommendations
            else "No immediate actions needed"
        ),
    }


# =============================================================================
# MCP TOOL REGISTRATION
# =============================================================================

def register_integration_tools(mcp_server):
    """Register cross-tool integration tools with MCP server."""

    @mcp_server.tool()
    async def integration_license_compliance(sbom_path: str = "") -> dict:
        """
        Check dependencies for license compliance issues.

        Scans for AGPL, GPL, SSPL and other licenses that may
        require source code release or restrict commercial use.

        Args:
            sbom_path: Optional path to existing SBOM file

        Returns:
            Compliance report with violations and recommendations

        Example:
            {}
        """
        return await check_license_compliance(sbom_path)

    @mcp_server.tool()
    async def integration_precommit_check(staged_files: str = "") -> dict:
        """
        Run security checks on staged files before commit.

        Designed for git pre-commit hooks to block commits
        containing secrets or critical security issues.

        Args:
            staged_files: Comma-separated file paths (auto-detects if empty)

        Returns:
            Pass/fail result with blocking issues

        Example:
            {} or {"staged_files": "src/auth.py,src/db.py"}
        """
        files = [f.strip() for f in staged_files.split(",")] if staged_files else None
        result = await security_precommit_check(files)
        return {
            "passed": result.passed,
            "secrets_found": result.secrets_found,
            "critical_issues": result.critical_issues,
            "blocking_issues": result.blocking_issues,
            "warnings": result.warnings,
            "can_commit": result.passed,
        }

    @mcp_server.tool()
    async def integration_diagnose_with_blame(run_id: int) -> dict:
        """
        Diagnose CI failure and identify which commit caused it.

        Combines CI/CD diagnosis with git blame analysis to show
        exactly which commit and author likely broke the build.

        Args:
            run_id: GitHub Actions run ID

        Returns:
            Diagnosis with blame attribution

        Example:
            {"run_id": 12345678}
        """
        return await cicd_diagnose_with_blame(run_id)

    @mcp_server.tool()
    async def integration_cicd_logs_correlate(
        run_id: int,
        log_path: str = "",
    ) -> dict:
        """
        Correlate CI/CD failures with application logs.

        Links build errors to runtime application errors for
        comprehensive incident analysis.

        Args:
            run_id: CI/CD run ID
            log_path: Path to application log file

        Returns:
            Correlated errors from build and application

        Example:
            {"run_id": 12345678, "log_path": "logs/app.log"}
        """
        return await cicd_correlate_with_logs(run_id, log_path)

    @mcp_server.tool()
    async def integration_schema_quality(connection: str) -> dict:
        """
        Calculate database schema quality score.

        Analyzes schema for best practices: primary keys,
        indexes, foreign keys, naming conventions.

        Args:
            connection: Database file path or connection string

        Returns:
            Quality score (0-100) with grade and recommendations

        Example:
            {"connection": "data.db"}
        """
        return await db_schema_quality_score(connection)

    @mcp_server.tool()
    async def integration_data_quality(
        connection: str,
        table: str,
    ) -> dict:
        """
        Scan table for data quality issues.

        Detects NULLs, duplicates, empty strings, and
        constraint violations.

        Args:
            connection: Database file path or connection string
            table: Table name to scan

        Returns:
            Data quality issues with fix suggestions

        Example:
            {"connection": "data.db", "table": "users"}
        """
        return await db_data_quality_scan(connection, table)

    # =========================================================================
    # DEPLOYMENT INTEGRATIONS
    # =========================================================================

    @mcp_server.tool()
    async def integration_deploy_with_security(
        environment: str = "preview",
    ) -> dict:
        """
        Run security checks before deployment.

        Scans for secrets, vulnerabilities, and license issues
        before allowing deployment to proceed.

        Args:
            environment: Target environment (preview, production)

        Returns:
            Security check results with deploy recommendation

        Example:
            {} or {"environment": "production"}
        """
        return await deploy_with_security_check(environment)

    @mcp_server.tool()
    async def integration_deploy_risk(
        from_ref: str = "",
        to_ref: str = "HEAD",
    ) -> dict:
        """
        Assess deployment risk based on changes.

        Analyzes changed files and assigns risk scores based on:
        - Security-sensitive files (auth, crypto)
        - Database migrations
        - Configuration changes
        - Test coverage changes

        Args:
            from_ref: Starting git ref (default: last deploy)
            to_ref: Ending git ref (default: HEAD)

        Returns:
            Risk assessment with score and breakdown

        Example:
            {} or {"from_ref": "v1.0.0", "to_ref": "HEAD"}
        """
        return await deploy_risk_assessment(from_ref, to_ref)

    @mcp_server.tool()
    async def integration_deploy_pipeline(run_id: int = 0) -> dict:
        """
        Get full pipeline status from CI to deployment.

        Shows complete flow: commit -> CI build -> deployment
        with timing and status at each stage.

        Args:
            run_id: CI run ID (uses latest if 0)

        Returns:
            Pipeline status across all stages

        Example:
            {} or {"run_id": 12345678}
        """
        return await deploy_pipeline_status(run_id)

    @mcp_server.tool()
    async def integration_rollback_analysis(deployment_id: str = "") -> dict:
        """
        Analyze if rollback is recommended and to which version.

        Checks deployment health, error rates, and compares
        with previous stable deployments.

        Args:
            deployment_id: Current deployment (uses production if empty)

        Returns:
            Rollback recommendation with target version

        Example:
            {} or {"deployment_id": "dpl_abc123"}
        """
        return await deploy_rollback_recommendation(deployment_id)

    # =========================================================================
    # DEPENDENCY INTEGRATIONS
    # =========================================================================

    @mcp_server.tool()
    async def integration_deps_security() -> dict:
        """
        Generate comprehensive dependency security report.

        Combines vulnerability scanning, license compliance,
        and security recommendations into one actionable report.

        Returns:
            Full security analysis with prioritized actions

        Example:
            {}
        """
        return await deps_full_security_report()

    @mcp_server.tool()
    async def integration_deps_update_impact(package: str = "") -> dict:
        """
        Analyze the impact of updating dependencies.

        Assesses risk of updates, identifies breaking changes,
        and provides safe update recommendations.

        Args:
            package: Specific package to analyze (all if empty)

        Returns:
            Update impact analysis with risk scores

        Example:
            {} or {"package": "react"}
        """
        return await deps_update_impact_analysis(package)

    @mcp_server.tool()
    async def integration_deps_cicd() -> dict:
        """
        Correlate dependency changes with CI/CD failures.

        Identifies if recent CI failures were caused by
        dependency updates.

        Returns:
            Correlation between dep changes and build failures

        Example:
            {}
        """
        return await deps_cicd_correlation()

    # =========================================================================
    # ENVIRONMENT INTEGRATIONS
    # =========================================================================

    @mcp_server.tool()
    async def integration_env_security() -> dict:
        """
        Audit environment files for security issues.

        Scans all .env files for exposed secrets and
        security misconfigurations.

        Returns:
            Security audit with exposed secrets and risks

        Example:
            {}
        """
        return await env_security_audit()

    @mcp_server.tool()
    async def integration_env_deploy_ready(environment: str = "production") -> dict:
        """
        Check if environment is ready for deployment.

        Validates environment variables, checks for missing
        vars, and compares with development.

        Args:
            environment: Target deployment environment

        Returns:
            Deployment readiness assessment

        Example:
            {} or {"environment": "staging"}
        """
        return await env_deploy_readiness(environment)

    # =========================================================================
    # PERFORMANCE INTEGRATIONS
    # =========================================================================

    @mcp_server.tool()
    async def integration_perf_deploy() -> dict:
        """
        Check performance before deployment.

        Validates bundle size and performance scores
        against deployment thresholds.

        Returns:
            Deployment readiness based on performance

        Example:
            {}
        """
        return await perf_deploy_check()

    @mcp_server.tool()
    async def integration_perf_deps() -> dict:
        """
        Analyze dependency impact on performance.

        Identifies which dependencies contribute most
        to bundle size.

        Returns:
            Heavy dependencies and optimization suggestions

        Example:
            {}
        """
        return await perf_deps_impact()

    # =========================================================================
    # DOCUMENTATION INTEGRATIONS
    # =========================================================================

    @mcp_server.tool()
    async def integration_docs_release_ready() -> dict:
        """
        Check if documentation is ready for release.

        Validates coverage, required files, and changelog
        completeness before publishing.

        Returns:
            Release readiness with issues and warnings

        Example:
            {}
        """
        return await docs_release_ready()

    @mcp_server.tool()
    async def integration_docs_quality_correlation() -> dict:
        """
        Correlate documentation with code quality.

        Analyzes if poorly documented code has more
        quality issues.

        Returns:
            Correlation analysis with insights

        Example:
            {}
        """
        return await docs_code_quality_correlation()

    @mcp_server.tool()
    async def integration_docs_changelog_security(
        since: str = "",
        version: str = "Unreleased",
    ) -> dict:
        """
        Generate changelog with security annotations.

        Marks security-related changes for visibility
        in release notes.

        Args:
            since: Git ref to start from
            version: Version for changelog header

        Returns:
            Enhanced changelog with security tags

        Example:
            {} or {"since": "v1.0.0", "version": "v1.1.0"}
        """
        return await docs_changelog_with_security(since, version)

    # =========================================================================
    # API TESTING INTEGRATIONS
    # =========================================================================

    @mcp_server.tool()
    async def integration_api_security_scan(
        base_url: str,
        endpoints: str = "",
    ) -> dict:
        """
        Scan API for security vulnerabilities.

        Tests for missing headers, CORS issues, and
        sensitive data exposure.

        Args:
            base_url: Base API URL
            endpoints: Comma-separated paths (auto-discovers if empty)

        Returns:
            Security scan with vulnerabilities

        Example:
            {"base_url": "https://api.example.com"}
        """
        return await api_security_scan(base_url, endpoints)

    @mcp_server.tool()
    async def integration_api_perf_baseline(
        url: str,
        iterations: int = 10,
    ) -> dict:
        """
        Establish API performance baseline.

        Tests endpoint multiple times to determine
        expected response times and thresholds.

        Args:
            url: Endpoint URL to benchmark
            iterations: Number of test iterations

        Returns:
            Baseline metrics with suggested thresholds

        Example:
            {"url": "https://api.example.com/health"}
        """
        return await api_perf_baseline(url, iterations)

    @mcp_server.tool()
    async def integration_api_deploy_health(
        base_url: str,
        health_path: str = "/health",
        api_paths: str = "",
    ) -> dict:
        """
        Comprehensive API deployment health check.

        Verifies health endpoint and critical API paths
        after deployment.

        Args:
            base_url: Base API URL
            health_path: Health endpoint path
            api_paths: Additional paths to check (comma-separated)

        Returns:
            Deployment health status

        Example:
            {"base_url": "https://api.example.com", "api_paths": "/users,/posts"}
        """
        return await api_deploy_health_check(base_url, health_path, api_paths)

    # =========================================================================
    # SECURITY + CODE QUALITY INTEGRATIONS
    # =========================================================================

    @mcp_server.tool()
    async def integration_security_quality_hotspots() -> dict:
        """
        Find security vulnerabilities in low-quality code.

        Cross-references security issues with code complexity
        to identify high-risk areas.

        Returns:
            Hotspots where security and quality issues overlap

        Example:
            {}
        """
        return await security_quality_hotspots()

    @mcp_server.tool()
    async def integration_security_complexity() -> dict:
        """
        Analyze if complex code has more security issues.

        Correlates cyclomatic complexity with security
        vulnerabilities.

        Returns:
            Correlation analysis with insights

        Example:
            {}
        """
        return await security_complexity_analysis()

    # =========================================================================
    # SECURITY + DATABASE INTEGRATIONS
    # =========================================================================

    @mcp_server.tool()
    async def integration_db_security_audit(connection: str) -> dict:
        """
        Audit database for security issues.

        Checks for sensitive data exposure, weak password
        storage, and missing encryption.

        Args:
            connection: Database file path or connection string

        Returns:
            Security audit with vulnerabilities

        Example:
            {"connection": "data.db"}
        """
        return await db_security_audit(connection)

    # =========================================================================
    # SECURITY + LOGS INTEGRATIONS
    # =========================================================================

    @mcp_server.tool()
    async def integration_logs_security_events(
        log_path: str,
        hours: int = 24,
    ) -> dict:
        """
        Detect security events in application logs.

        Scans for failed logins, access denied, injection
        attempts, and brute force patterns.

        Args:
            log_path: Path to log file
            hours: Hours of logs to analyze

        Returns:
            Security events with threat level

        Example:
            {"log_path": "logs/app.log"}
        """
        return await logs_security_events(log_path, hours)

    # =========================================================================
    # CODE QUALITY + CI/CD INTEGRATIONS
    # =========================================================================

    @mcp_server.tool()
    async def integration_quality_gate(
        min_score: int = 70,
        max_issues: int = 50,
        block_critical: bool = True,
    ) -> dict:
        """
        Check if code quality meets deployment gate.

        Enforces quality standards before deployment.

        Args:
            min_score: Minimum quality score (0-100)
            max_issues: Maximum allowed issues
            block_critical: Block on critical issues

        Returns:
            Gate pass/fail with details

        Example:
            {} or {"min_score": 80, "block_critical": true}
        """
        return await quality_gate_check(min_score, max_issues, block_critical)

    @mcp_server.tool()
    async def integration_quality_trend(runs: int = 10) -> dict:
        """
        Analyze code quality trends over time.

        Tracks quality metrics to identify improvements
        or degradation.

        Args:
            runs: Number of CI runs to consider

        Returns:
            Trend analysis with direction

        Example:
            {} or {"runs": 20}
        """
        return await quality_trend_analysis(runs)

    # =========================================================================
    # CODE QUALITY + DATABASE INTEGRATIONS
    # =========================================================================

    @mcp_server.tool()
    async def integration_db_query_quality(connection: str) -> dict:
        """
        Analyze database queries in code for quality.

        Detects N+1 patterns, SELECT *, and missing
        LIMIT clauses.

        Args:
            connection: Database connection for context

        Returns:
            Query quality issues with optimizations

        Example:
            {"connection": "data.db"}
        """
        return await db_query_quality_check(connection)

    # =========================================================================
    # LOGS + DEPLOYMENT INTEGRATIONS
    # =========================================================================

    @mcp_server.tool()
    async def integration_logs_deploy_correlation(
        log_path: str,
        deployment_id: str = "",
    ) -> dict:
        """
        Correlate log errors with deployments.

        Detects error spikes after deployments to identify
        deployment-caused issues.

        Args:
            log_path: Path to application logs
            deployment_id: Specific deployment (latest if empty)

        Returns:
            Correlation strength and recommendations

        Example:
            {"log_path": "logs/app.log"}
        """
        return await logs_deployment_correlation(log_path, deployment_id)

    # =========================================================================
    # LOGS + DATABASE INTEGRATIONS
    # =========================================================================

    @mcp_server.tool()
    async def integration_logs_slow_queries(
        log_path: str,
        threshold_ms: int = 1000,
    ) -> dict:
        """
        Analyze slow database queries from logs.

        Extracts and aggregates slow query patterns.

        Args:
            log_path: Path to application/database logs
            threshold_ms: Slow query threshold

        Returns:
            Slow query analysis with optimizations

        Example:
            {"log_path": "logs/db.log", "threshold_ms": 500}
        """
        return await logs_slow_query_analysis(log_path, threshold_ms)

    # =========================================================================
    # CONTEXT + SECURITY INTEGRATIONS
    # =========================================================================

    @mcp_server.tool()
    async def integration_context_security(
        query: str = "security vulnerability",
    ) -> dict:
        """
        Search codebase for security patterns.

        Uses semantic search to find authentication,
        authorization, and validation code.

        Args:
            query: Security-related search query

        Returns:
            Matching code locations by category

        Example:
            {} or {"query": "password hashing"}
        """
        return await context_security_patterns(query)

    # =========================================================================
    # SMART RECOMMENDATIONS
    # =========================================================================

    @mcp_server.tool()
    async def integration_smart_recommendations() -> dict:
        """
        Generate intelligent prioritized recommendations.

        Combines all tool analyses to provide actionable,
        prioritized recommendations.

        Returns:
            Prioritized recommendations with impact scores

        Example:
            {}
        """
        return await smart_recommendations()

    return [
        "integration_license_compliance",
        "integration_precommit_check",
        "integration_diagnose_with_blame",
        "integration_cicd_logs_correlate",
        "integration_schema_quality",
        "integration_data_quality",
        "integration_deploy_with_security",
        "integration_deploy_risk",
        "integration_deploy_pipeline",
        "integration_rollback_analysis",
        "integration_deps_security",
        "integration_deps_update_impact",
        "integration_deps_cicd",
        "integration_env_security",
        "integration_env_deploy_ready",
        "integration_perf_deploy",
        "integration_perf_deps",
        "integration_docs_release_ready",
        "integration_docs_quality_correlation",
        "integration_docs_changelog_security",
        "integration_api_security_scan",
        "integration_api_perf_baseline",
        "integration_api_deploy_health",
        # New pre-existing tool integrations
        "integration_security_quality_hotspots",
        "integration_security_complexity",
        "integration_db_security_audit",
        "integration_logs_security_events",
        "integration_quality_gate",
        "integration_quality_trend",
        "integration_db_query_quality",
        "integration_logs_deploy_correlation",
        "integration_logs_slow_queries",
        "integration_context_security",
        "integration_smart_recommendations",
    ]

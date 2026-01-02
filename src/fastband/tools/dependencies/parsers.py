"""
Dependency Parsers - Parse dependency files from various ecosystems.

Supports:
- package.json (npm/yarn/pnpm)
- requirements.txt, pyproject.toml, setup.py (Python)
- Cargo.toml (Rust)
- go.mod (Go)
"""

import json
import logging
import re
import subprocess
from pathlib import Path
from typing import Any

from fastband.tools.dependencies.models import (
    Dependency,
    DependencyHealth,
    DependencyType,
    PackageManager,
    UpdateType,
    Vulnerability,
    VulnerabilitySeverity,
)

logger = logging.getLogger(__name__)


def detect_package_manager(project_root: str) -> PackageManager:
    """Detect the package manager used in a project."""
    root = Path(project_root)

    # Check for lock files first (more specific)
    if (root / "pnpm-lock.yaml").exists():
        return PackageManager.PNPM
    if (root / "yarn.lock").exists():
        return PackageManager.YARN
    if (root / "package-lock.json").exists():
        return PackageManager.NPM
    if (root / "uv.lock").exists():
        return PackageManager.UV
    if (root / "poetry.lock").exists():
        return PackageManager.POETRY
    if (root / "Cargo.lock").exists():
        return PackageManager.CARGO
    if (root / "go.sum").exists():
        return PackageManager.GO

    # Check for manifest files
    if (root / "package.json").exists():
        return PackageManager.NPM  # Default to npm for package.json
    if (root / "pyproject.toml").exists():
        return PackageManager.PIP
    if (root / "requirements.txt").exists():
        return PackageManager.PIP
    if (root / "Cargo.toml").exists():
        return PackageManager.CARGO
    if (root / "go.mod").exists():
        return PackageManager.GO

    return PackageManager.UNKNOWN


def parse_package_json(file_path: Path) -> list[Dependency]:
    """Parse npm package.json file."""
    if not file_path.exists():
        return []

    try:
        with open(file_path) as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"Failed to parse {file_path}: {e}")
        return []

    dependencies = []

    # Production dependencies
    for name, version in data.get("dependencies", {}).items():
        dependencies.append(Dependency(
            name=name,
            version=version.lstrip("^~>=<"),
            dep_type=DependencyType.PRODUCTION,
        ))

    # Dev dependencies
    for name, version in data.get("devDependencies", {}).items():
        dependencies.append(Dependency(
            name=name,
            version=version.lstrip("^~>=<"),
            dep_type=DependencyType.DEVELOPMENT,
        ))

    # Peer dependencies
    for name, version in data.get("peerDependencies", {}).items():
        dependencies.append(Dependency(
            name=name,
            version=version.lstrip("^~>=<"),
            dep_type=DependencyType.PEER,
        ))

    # Optional dependencies
    for name, version in data.get("optionalDependencies", {}).items():
        dependencies.append(Dependency(
            name=name,
            version=version.lstrip("^~>=<"),
            dep_type=DependencyType.OPTIONAL,
        ))

    return dependencies


def parse_requirements_txt(file_path: Path) -> list[Dependency]:
    """Parse Python requirements.txt file."""
    if not file_path.exists():
        return []

    dependencies = []

    try:
        with open(file_path) as f:
            for line in f:
                line = line.strip()
                # Skip comments and empty lines
                if not line or line.startswith("#") or line.startswith("-"):
                    continue

                # Parse package==version or package>=version etc.
                match = re.match(r"([a-zA-Z0-9_\-\.]+)([<>=!~]+)?(.+)?", line)
                if match:
                    name = match.group(1)
                    version = match.group(3) or ""
                    version = version.split(",")[0].strip()  # Take first version constraint

                    dependencies.append(Dependency(
                        name=name,
                        version=version,
                        dep_type=DependencyType.PRODUCTION,
                    ))
    except OSError as e:
        logger.warning(f"Failed to parse {file_path}: {e}")

    return dependencies


def parse_pyproject_toml(file_path: Path) -> list[Dependency]:
    """Parse Python pyproject.toml file."""
    if not file_path.exists():
        return []

    try:
        # Try to use tomllib (Python 3.11+) or tomli
        try:
            import tomllib
            with open(file_path, "rb") as f:
                data = tomllib.load(f)
        except ImportError:
            try:
                import tomli
                with open(file_path, "rb") as f:
                    data = tomli.load(f)
            except ImportError:
                # Fallback: simple regex parsing
                with open(file_path) as f:
                    content = f.read()
                return _parse_pyproject_simple(content)
    except Exception as e:
        logger.warning(f"Failed to parse {file_path}: {e}")
        return []

    dependencies = []

    # Poetry format
    if "tool" in data and "poetry" in data["tool"]:
        poetry = data["tool"]["poetry"]

        for name, spec in poetry.get("dependencies", {}).items():
            if name == "python":
                continue
            version = spec if isinstance(spec, str) else spec.get("version", "")
            dependencies.append(Dependency(
                name=name,
                version=version.lstrip("^~>=<"),
                dep_type=DependencyType.PRODUCTION,
            ))

        for name, spec in poetry.get("dev-dependencies", {}).items():
            version = spec if isinstance(spec, str) else spec.get("version", "")
            dependencies.append(Dependency(
                name=name,
                version=version.lstrip("^~>=<"),
                dep_type=DependencyType.DEVELOPMENT,
            ))

    # PEP 621 format
    if "project" in data:
        project = data["project"]

        for dep_str in project.get("dependencies", []):
            match = re.match(r"([a-zA-Z0-9_\-\.]+)([<>=!~\[]+)?(.+)?", dep_str)
            if match:
                dependencies.append(Dependency(
                    name=match.group(1),
                    version=match.group(3) or "" if match.group(2) else "",
                    dep_type=DependencyType.PRODUCTION,
                ))

        # Optional dependencies (dev, test, etc.)
        for group, deps in project.get("optional-dependencies", {}).items():
            dep_type = (
                DependencyType.DEVELOPMENT
                if group in ("dev", "development", "test", "testing")
                else DependencyType.OPTIONAL
            )
            for dep_str in deps:
                match = re.match(r"([a-zA-Z0-9_\-\.]+)", dep_str)
                if match:
                    dependencies.append(Dependency(
                        name=match.group(1),
                        version="",
                        dep_type=dep_type,
                    ))

    return dependencies


def _parse_pyproject_simple(content: str) -> list[Dependency]:
    """Simple regex-based pyproject.toml parsing fallback."""
    dependencies = []

    # Look for dependencies section
    in_deps = False
    for line in content.split("\n"):
        line = line.strip()

        if "[project.dependencies]" in line or "[tool.poetry.dependencies]" in line:
            in_deps = True
            continue
        elif line.startswith("["):
            in_deps = False

        if in_deps and "=" in line:
            parts = line.split("=", 1)
            name = parts[0].strip().strip('"')
            if name and name != "python":
                dependencies.append(Dependency(
                    name=name,
                    version="",
                    dep_type=DependencyType.PRODUCTION,
                ))

    return dependencies


def get_npm_outdated(project_root: str) -> list[Dependency]:
    """Get outdated npm packages."""
    try:
        result = subprocess.run(
            ["npm", "outdated", "--json"],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=project_root,
        )

        # npm outdated returns exit code 1 if there are outdated packages
        output = result.stdout or result.stderr

        if not output:
            return []

        data = json.loads(output)
        dependencies = []

        for name, info in data.items():
            current = info.get("current", "")
            latest = info.get("latest", "")
            wanted = info.get("wanted", "")

            if not current or not latest:
                continue

            # Determine update type
            update_type = _determine_update_type(current, latest)

            dependencies.append(Dependency(
                name=name,
                version=current,
                latest_version=latest,
                wanted_version=wanted,
                update_available=current != latest,
                update_type=update_type,
            ))

        return dependencies
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError) as e:
        logger.warning(f"Failed to get npm outdated: {e}")
        return []


def get_pip_outdated(project_root: str) -> list[Dependency]:
    """Get outdated pip packages."""
    try:
        result = subprocess.run(
            ["pip", "list", "--outdated", "--format=json"],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=project_root,
        )

        if result.returncode != 0:
            return []

        data = json.loads(result.stdout)
        dependencies = []

        for pkg in data:
            name = pkg.get("name", "")
            current = pkg.get("version", "")
            latest = pkg.get("latest_version", "")

            if not name or not current:
                continue

            update_type = _determine_update_type(current, latest)

            dependencies.append(Dependency(
                name=name,
                version=current,
                latest_version=latest,
                update_available=True,
                update_type=update_type,
            ))

        return dependencies
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError) as e:
        logger.warning(f"Failed to get pip outdated: {e}")
        return []


def _determine_update_type(current: str, latest: str) -> UpdateType:
    """Determine the type of update (major, minor, patch)."""
    def parse_version(v: str) -> tuple[int, ...]:
        # Remove any prefix/suffix and split
        v = re.sub(r"[^\d.]", "", v.split("-")[0].split("+")[0])
        parts = v.split(".")
        return tuple(int(p) for p in parts[:3] if p.isdigit())

    try:
        cur_parts = parse_version(current)
        lat_parts = parse_version(latest)

        if not cur_parts or not lat_parts:
            return UpdateType.PATCH

        if lat_parts[0] > cur_parts[0]:
            return UpdateType.MAJOR
        elif len(lat_parts) > 1 and len(cur_parts) > 1 and lat_parts[1] > cur_parts[1]:
            return UpdateType.MINOR
        else:
            return UpdateType.PATCH
    except (ValueError, IndexError):
        return UpdateType.PATCH


def get_npm_audit(project_root: str) -> list[Vulnerability]:
    """Get npm security audit results."""
    try:
        result = subprocess.run(
            ["npm", "audit", "--json"],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=project_root,
        )

        # npm audit can return various exit codes
        output = result.stdout

        if not output:
            return []

        data = json.loads(output)
        vulnerabilities = []

        # npm audit v2 format
        vulns = data.get("vulnerabilities", {})
        for pkg_name, vuln_info in vulns.items():
            severity = vuln_info.get("severity", "medium")
            via = vuln_info.get("via", [])

            # Get first CVE/advisory
            advisory = via[0] if via and isinstance(via[0], dict) else {}

            vulnerabilities.append(Vulnerability(
                id=str(advisory.get("source", "")),
                package=pkg_name,
                severity=VulnerabilitySeverity(severity.lower()),
                title=advisory.get("title", f"Vulnerability in {pkg_name}"),
                description=advisory.get("overview", ""),
                url=advisory.get("url", ""),
                vulnerable_versions=vuln_info.get("range", ""),
                patched_versions=vuln_info.get("fixAvailable", {}).get("version", "") if isinstance(vuln_info.get("fixAvailable"), dict) else "",
                has_fix=bool(vuln_info.get("fixAvailable")),
            ))

        return vulnerabilities
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError) as e:
        logger.warning(f"Failed to get npm audit: {e}")
        return []


def get_pip_audit(project_root: str) -> list[Vulnerability]:
    """Get pip-audit security results."""
    try:
        result = subprocess.run(
            ["pip-audit", "--format=json"],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=project_root,
        )

        if not result.stdout:
            return []

        data = json.loads(result.stdout)
        vulnerabilities = []

        for vuln in data:
            pkg_name = vuln.get("name", "")
            for advisory in vuln.get("vulns", []):
                vulnerabilities.append(Vulnerability(
                    id=advisory.get("id", ""),
                    package=pkg_name,
                    severity=VulnerabilitySeverity.HIGH,  # pip-audit doesn't provide severity
                    title=advisory.get("id", ""),
                    description=advisory.get("description", ""),
                    vulnerable_versions=vuln.get("version", ""),
                    patched_versions=advisory.get("fix_versions", [""])[0] if advisory.get("fix_versions") else "",
                    has_fix=bool(advisory.get("fix_versions")),
                ))

        return vulnerabilities
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
        return []

"""
Dependency Vulnerability Scanner.

Scans project dependencies for known vulnerabilities using:
- OSV (Open Source Vulnerabilities) database
- GitHub Advisory Database
- PyPI Advisory Database
- npm Advisory Database

Supports:
- Python (requirements.txt, pyproject.toml, Pipfile)
- JavaScript/TypeScript (package.json, package-lock.json)
- Go (go.mod, go.sum)
"""

import asyncio
import json
import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastband.tools.security.models import (
    SBOM,
    DependencyInfo,
    SBOMComponent,
    Vulnerability,
    VulnerabilitySeverity,
    VulnerabilityType,
)

logger = logging.getLogger(__name__)


@dataclass
class ManifestInfo:
    """Information about a package manifest file."""

    path: str
    ecosystem: str  # npm, pypi, go
    dependencies: list[DependencyInfo]


class DependencyScanner:
    """
    Scans project dependencies for known vulnerabilities.

    Uses OSV (Open Source Vulnerabilities) as primary database,
    with fallback to ecosystem-specific advisories.
    """

    OSV_API_URL = "https://api.osv.dev/v1/query"
    OSV_BATCH_URL = "https://api.osv.dev/v1/querybatch"

    # Ecosystem mappings
    ECOSYSTEM_MAP = {
        "npm": "npm",
        "pypi": "PyPI",
        "go": "Go",
        "cargo": "crates.io",
        "maven": "Maven",
        "nuget": "NuGet",
    }

    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self._http_client = None

    async def _get_http_client(self):
        """Get or create HTTP client."""
        if self._http_client is None:
            try:
                import aiohttp
                self._http_client = aiohttp.ClientSession()
            except ImportError:
                logger.warning("aiohttp not available, using synchronous requests")
                self._http_client = "sync"
        return self._http_client

    async def close(self):
        """Close HTTP client."""
        if self._http_client and self._http_client != "sync":
            await self._http_client.close()
            self._http_client = None

    # =========================================================================
    # MANIFEST PARSING
    # =========================================================================

    def find_manifests(self) -> list[str]:
        """Find all package manifest files in the project."""
        manifests = []
        patterns = [
            # Python
            "requirements*.txt",
            "pyproject.toml",
            "Pipfile",
            "setup.py",
            # JavaScript
            "package.json",
            "package-lock.json",
            "yarn.lock",
            "pnpm-lock.yaml",
            # Go
            "go.mod",
            "go.sum",
            # Rust
            "Cargo.toml",
            "Cargo.lock",
        ]

        for pattern in patterns:
            for path in self.project_root.rglob(pattern):
                # Skip node_modules and virtual envs
                rel_path = path.relative_to(self.project_root)
                if any(part in str(rel_path) for part in ["node_modules", ".venv", "venv", "__pycache__"]):
                    continue
                manifests.append(str(rel_path))

        return manifests

    def parse_manifest(self, manifest_path: str) -> ManifestInfo:
        """Parse a package manifest file."""
        full_path = self.project_root / manifest_path
        filename = os.path.basename(manifest_path)

        if filename.startswith("requirements") and filename.endswith(".txt"):
            return self._parse_requirements_txt(manifest_path, full_path)
        elif filename == "pyproject.toml":
            return self._parse_pyproject_toml(manifest_path, full_path)
        elif filename == "Pipfile":
            return self._parse_pipfile(manifest_path, full_path)
        elif filename == "package.json":
            return self._parse_package_json(manifest_path, full_path)
        elif filename == "package-lock.json":
            return self._parse_package_lock(manifest_path, full_path)
        elif filename == "go.mod":
            return self._parse_go_mod(manifest_path, full_path)
        elif filename == "Cargo.toml":
            return self._parse_cargo_toml(manifest_path, full_path)
        else:
            return ManifestInfo(path=manifest_path, ecosystem="unknown", dependencies=[])

    def _parse_requirements_txt(self, rel_path: str, full_path: Path) -> ManifestInfo:
        """Parse Python requirements.txt."""
        deps = []
        try:
            content = full_path.read_text()
            for line in content.split("\n"):
                line = line.strip()
                if not line or line.startswith("#") or line.startswith("-"):
                    continue

                # Parse package==version or package>=version etc.
                match = re.match(r"^([a-zA-Z0-9_-]+)\s*([<>=!~]+)?\s*([0-9a-zA-Z.*-]+)?", line)
                if match:
                    name = match.group(1)
                    version = match.group(3) or "unknown"
                    deps.append(DependencyInfo(
                        name=name.lower(),
                        version=version,
                        ecosystem="pypi",
                        manifest_file=rel_path,
                    ))
        except Exception as e:
            logger.warning(f"Failed to parse {rel_path}: {e}")

        return ManifestInfo(path=rel_path, ecosystem="pypi", dependencies=deps)

    def _parse_pyproject_toml(self, rel_path: str, full_path: Path) -> ManifestInfo:
        """Parse pyproject.toml for dependencies."""
        deps = []
        try:
            try:
                import tomllib
            except ImportError:
                import tomli as tomllib

            content = full_path.read_text()
            data = tomllib.loads(content)

            # Check [project.dependencies]
            project_deps = data.get("project", {}).get("dependencies", [])
            for dep in project_deps:
                match = re.match(r"^([a-zA-Z0-9_-]+)\s*([<>=!~]+)?\s*([0-9a-zA-Z.*-]+)?", dep)
                if match:
                    deps.append(DependencyInfo(
                        name=match.group(1).lower(),
                        version=match.group(3) or "unknown",
                        ecosystem="pypi",
                        manifest_file=rel_path,
                    ))

            # Check [tool.poetry.dependencies]
            poetry_deps = data.get("tool", {}).get("poetry", {}).get("dependencies", {})
            for name, version_spec in poetry_deps.items():
                if name == "python":
                    continue
                version = "unknown"
                if isinstance(version_spec, str):
                    version = version_spec.lstrip("^~>=<")
                elif isinstance(version_spec, dict):
                    version = version_spec.get("version", "unknown").lstrip("^~>=<")
                deps.append(DependencyInfo(
                    name=name.lower(),
                    version=version,
                    ecosystem="pypi",
                    manifest_file=rel_path,
                ))

        except Exception as e:
            logger.warning(f"Failed to parse {rel_path}: {e}")

        return ManifestInfo(path=rel_path, ecosystem="pypi", dependencies=deps)

    def _parse_pipfile(self, rel_path: str, full_path: Path) -> ManifestInfo:
        """Parse Pipfile for dependencies."""
        deps = []
        try:
            try:
                import tomllib
            except ImportError:
                import tomli as tomllib

            content = full_path.read_text()
            data = tomllib.loads(content)

            for section in ["packages", "dev-packages"]:
                packages = data.get(section, {})
                for name, version_spec in packages.items():
                    version = "unknown"
                    if isinstance(version_spec, str):
                        version = version_spec.lstrip("=<>~")
                    elif isinstance(version_spec, dict):
                        version = version_spec.get("version", "unknown").lstrip("=<>~")
                    deps.append(DependencyInfo(
                        name=name.lower(),
                        version=version,
                        ecosystem="pypi",
                        manifest_file=rel_path,
                    ))

        except Exception as e:
            logger.warning(f"Failed to parse {rel_path}: {e}")

        return ManifestInfo(path=rel_path, ecosystem="pypi", dependencies=deps)

    def _parse_package_json(self, rel_path: str, full_path: Path) -> ManifestInfo:
        """Parse package.json for dependencies."""
        deps = []
        try:
            content = full_path.read_text()
            data = json.loads(content)

            for section in ["dependencies", "devDependencies", "peerDependencies"]:
                packages = data.get(section, {})
                for name, version in packages.items():
                    # Clean version string
                    clean_version = version.lstrip("^~>=<")
                    deps.append(DependencyInfo(
                        name=name,
                        version=clean_version,
                        ecosystem="npm",
                        manifest_file=rel_path,
                        direct=section == "dependencies",
                    ))

        except Exception as e:
            logger.warning(f"Failed to parse {rel_path}: {e}")

        return ManifestInfo(path=rel_path, ecosystem="npm", dependencies=deps)

    def _parse_package_lock(self, rel_path: str, full_path: Path) -> ManifestInfo:
        """Parse package-lock.json for exact versions."""
        deps = []
        try:
            content = full_path.read_text()
            data = json.loads(content)

            # v2/v3 format
            packages = data.get("packages", {})
            for pkg_path, pkg_info in packages.items():
                if not pkg_path:  # Root package
                    continue
                name = pkg_path.replace("node_modules/", "").split("/")[-1]
                if name.startswith("@"):
                    # Scoped package
                    parts = pkg_path.replace("node_modules/", "").split("/")
                    if len(parts) >= 2:
                        name = f"{parts[-2]}/{parts[-1]}"

                deps.append(DependencyInfo(
                    name=name,
                    version=pkg_info.get("version", "unknown"),
                    ecosystem="npm",
                    manifest_file=rel_path,
                    lock_file=rel_path,
                    direct=not pkg_info.get("dev", False),
                ))

        except Exception as e:
            logger.warning(f"Failed to parse {rel_path}: {e}")

        return ManifestInfo(path=rel_path, ecosystem="npm", dependencies=deps)

    def _parse_go_mod(self, rel_path: str, full_path: Path) -> ManifestInfo:
        """Parse go.mod for dependencies."""
        deps = []
        try:
            content = full_path.read_text()

            # Parse require blocks
            in_require = False
            for line in content.split("\n"):
                line = line.strip()

                if line.startswith("require ("):
                    in_require = True
                    continue
                elif line == ")":
                    in_require = False
                    continue

                if in_require or line.startswith("require "):
                    # Parse "module/path v1.2.3"
                    match = re.match(r"(?:require\s+)?([^\s]+)\s+(v[0-9.]+)", line)
                    if match:
                        deps.append(DependencyInfo(
                            name=match.group(1),
                            version=match.group(2),
                            ecosystem="go",
                            manifest_file=rel_path,
                        ))

        except Exception as e:
            logger.warning(f"Failed to parse {rel_path}: {e}")

        return ManifestInfo(path=rel_path, ecosystem="go", dependencies=deps)

    def _parse_cargo_toml(self, rel_path: str, full_path: Path) -> ManifestInfo:
        """Parse Cargo.toml for Rust dependencies."""
        deps = []
        try:
            try:
                import tomllib
            except ImportError:
                import tomli as tomllib

            content = full_path.read_text()
            data = tomllib.loads(content)

            for section in ["dependencies", "dev-dependencies", "build-dependencies"]:
                packages = data.get(section, {})
                for name, version_spec in packages.items():
                    version = "unknown"
                    if isinstance(version_spec, str):
                        version = version_spec
                    elif isinstance(version_spec, dict):
                        version = version_spec.get("version", "unknown")
                    deps.append(DependencyInfo(
                        name=name,
                        version=version,
                        ecosystem="cargo",
                        manifest_file=rel_path,
                    ))

        except Exception as e:
            logger.warning(f"Failed to parse {rel_path}: {e}")

        return ManifestInfo(path=rel_path, ecosystem="cargo", dependencies=deps)

    # =========================================================================
    # VULNERABILITY CHECKING
    # =========================================================================

    async def check_vulnerabilities(
        self,
        dependencies: list[DependencyInfo],
    ) -> list[DependencyInfo]:
        """Check dependencies against vulnerability databases."""
        if not dependencies:
            return []

        # Try OSV batch query first
        try:
            vulns = await self._query_osv_batch(dependencies)
            return self._merge_vulns_to_deps(dependencies, vulns)
        except Exception as e:
            logger.warning(f"OSV batch query failed: {e}")

        # Fall back to individual queries
        for dep in dependencies:
            try:
                vulns = await self._query_osv_single(dep)
                dep.vulnerabilities = vulns
            except Exception as e:
                logger.debug(f"Failed to check {dep.name}: {e}")

        return dependencies

    async def _query_osv_batch(
        self,
        dependencies: list[DependencyInfo],
    ) -> dict[str, list[Vulnerability]]:
        """Query OSV database for multiple packages at once."""
        client = await self._get_http_client()

        # Build batch query
        queries = []
        for dep in dependencies:
            ecosystem = self.ECOSYSTEM_MAP.get(dep.ecosystem, dep.ecosystem)
            queries.append({
                "package": {
                    "name": dep.name,
                    "ecosystem": ecosystem,
                },
                "version": dep.version,
            })

        if client == "sync":
            # Synchronous fallback
            import requests
            response = requests.post(
                self.OSV_BATCH_URL,
                json={"queries": queries},
                timeout=30,
            )
            data = response.json()
        else:
            async with client.post(self.OSV_BATCH_URL, json={"queries": queries}) as response:
                data = await response.json()

        # Parse results
        vulns_by_pkg: dict[str, list[Vulnerability]] = {}
        results = data.get("results", [])

        for i, result in enumerate(results):
            if i >= len(dependencies):
                break
            dep = dependencies[i]
            pkg_key = f"{dep.ecosystem}:{dep.name}@{dep.version}"

            vulns = []
            for osv_vuln in result.get("vulns", []):
                vuln = self._parse_osv_vuln(osv_vuln, dep)
                if vuln:
                    vulns.append(vuln)

            vulns_by_pkg[pkg_key] = vulns

        return vulns_by_pkg

    async def _query_osv_single(self, dep: DependencyInfo) -> list[Vulnerability]:
        """Query OSV for a single package."""
        client = await self._get_http_client()
        ecosystem = self.ECOSYSTEM_MAP.get(dep.ecosystem, dep.ecosystem)

        query = {
            "package": {
                "name": dep.name,
                "ecosystem": ecosystem,
            },
            "version": dep.version,
        }

        if client == "sync":
            import requests
            response = requests.post(self.OSV_API_URL, json=query, timeout=30)
            data = response.json()
        else:
            async with client.post(self.OSV_API_URL, json=query) as response:
                data = await response.json()

        vulns = []
        for osv_vuln in data.get("vulns", []):
            vuln = self._parse_osv_vuln(osv_vuln, dep)
            if vuln:
                vulns.append(vuln)

        return vulns

    def _parse_osv_vuln(
        self,
        osv_data: dict[str, Any],
        dep: DependencyInfo,
    ) -> Vulnerability | None:
        """Parse OSV vulnerability data into our format."""
        try:
            vuln_id = osv_data.get("id", "")
            summary = osv_data.get("summary", "")
            details = osv_data.get("details", "")

            # Get severity from CVSS
            severity = VulnerabilitySeverity.UNKNOWN
            cvss_score = None
            cvss_vector = None

            for severity_data in osv_data.get("severity", []):
                if severity_data.get("type") == "CVSS_V3":
                    cvss_vector = severity_data.get("score", "")
                    # Extract score from vector if present
                    # Full CVSS parsing would require a library

            # Get from database_specific if available
            db_specific = osv_data.get("database_specific", {})
            if "severity" in db_specific:
                sev_str = db_specific["severity"].upper()
                if sev_str == "CRITICAL":
                    severity = VulnerabilitySeverity.CRITICAL
                elif sev_str == "HIGH":
                    severity = VulnerabilitySeverity.HIGH
                elif sev_str == "MODERATE" or sev_str == "MEDIUM":
                    severity = VulnerabilitySeverity.MEDIUM
                elif sev_str == "LOW":
                    severity = VulnerabilitySeverity.LOW

            # Get CVE ID
            cve_id = None
            for alias in osv_data.get("aliases", []):
                if alias.startswith("CVE-"):
                    cve_id = alias
                    break

            # Get CWE
            cwe_id = None
            for cwe in db_specific.get("cwe_ids", []):
                cwe_id = cwe
                break

            # Get fixed version
            fixed_version = None
            for affected in osv_data.get("affected", []):
                for range_data in affected.get("ranges", []):
                    for event in range_data.get("events", []):
                        if "fixed" in event:
                            fixed_version = event["fixed"]
                            break

            # Get references
            references = [
                ref.get("url", "") for ref in osv_data.get("references", [])
            ]

            return Vulnerability(
                vuln_id=vuln_id,
                vuln_type=VulnerabilityType.DEPENDENCY,
                severity=severity,
                title=summary or f"Vulnerability in {dep.name}",
                description=details or summary,
                package_name=dep.name,
                package_version=dep.version,
                cve_id=cve_id,
                cwe_id=cwe_id,
                cvss_score=cvss_score,
                cvss_vector=cvss_vector,
                references=references[:5],
                fix_available=fixed_version is not None,
                fixed_version=fixed_version,
            )

        except Exception as e:
            logger.debug(f"Failed to parse OSV vuln: {e}")
            return None

    def _merge_vulns_to_deps(
        self,
        dependencies: list[DependencyInfo],
        vulns_by_pkg: dict[str, list[Vulnerability]],
    ) -> list[DependencyInfo]:
        """Merge vulnerability data back into dependency info."""
        for dep in dependencies:
            pkg_key = f"{dep.ecosystem}:{dep.name}@{dep.version}"
            dep.vulnerabilities = vulns_by_pkg.get(pkg_key, [])
        return dependencies

    # =========================================================================
    # SBOM GENERATION
    # =========================================================================

    def generate_sbom(
        self,
        dependencies: list[DependencyInfo],
        project_name: str = "",
        project_version: str = "",
    ) -> SBOM:
        """Generate Software Bill of Materials."""
        import uuid

        components = []
        for dep in dependencies:
            purl = self._generate_purl(dep)
            components.append(SBOMComponent(
                name=dep.name,
                version=dep.version,
                purl=purl,
                ecosystem=dep.ecosystem,
                manifest_file=dep.manifest_file,
                is_direct=dep.direct,
                license=dep.license,
                vulnerabilities=dep.vulnerabilities,
            ))

        sbom = SBOM(
            sbom_id=str(uuid.uuid4()),
            project_name=project_name or self.project_root.name,
            project_version=project_version,
            project_root=str(self.project_root),
            components=components,
            total_components=len(components),
            direct_dependencies=sum(1 for c in components if c.is_direct),
            transitive_dependencies=sum(1 for c in components if not c.is_direct),
            vulnerable_components=sum(1 for c in components if c.vulnerabilities),
        )

        return sbom

    def _generate_purl(self, dep: DependencyInfo) -> str:
        """Generate Package URL (purl) for a dependency."""
        # https://github.com/package-url/purl-spec
        ecosystem_map = {
            "npm": "npm",
            "pypi": "pypi",
            "go": "golang",
            "cargo": "cargo",
            "maven": "maven",
        }
        pkg_type = ecosystem_map.get(dep.ecosystem, dep.ecosystem)

        # Handle scoped npm packages
        if dep.ecosystem == "npm" and dep.name.startswith("@"):
            namespace, name = dep.name.split("/", 1)
            return f"pkg:{pkg_type}/{namespace}/{name}@{dep.version}"

        return f"pkg:{pkg_type}/{dep.name}@{dep.version}"

    # =========================================================================
    # MAIN SCAN METHODS
    # =========================================================================

    async def scan(self) -> tuple[list[DependencyInfo], list[str]]:
        """
        Scan project for dependency vulnerabilities.

        Returns:
            Tuple of (dependencies with vulns, manifest files scanned)
        """
        # Find all manifests
        manifests = self.find_manifests()
        logger.info(f"Found {len(manifests)} manifest files")

        # Parse all manifests
        all_deps: dict[str, DependencyInfo] = {}
        for manifest_path in manifests:
            manifest = self.parse_manifest(manifest_path)
            for dep in manifest.dependencies:
                # Dedupe by ecosystem:name:version
                key = f"{dep.ecosystem}:{dep.name}@{dep.version}"
                if key not in all_deps:
                    all_deps[key] = dep

        # Check vulnerabilities
        deps_list = list(all_deps.values())
        logger.info(f"Checking {len(deps_list)} unique dependencies")

        deps_with_vulns = await self.check_vulnerabilities(deps_list)

        return deps_with_vulns, manifests

    async def scan_file(self, manifest_path: str) -> list[DependencyInfo]:
        """Scan a single manifest file."""
        manifest = self.parse_manifest(manifest_path)
        return await self.check_vulnerabilities(manifest.dependencies)

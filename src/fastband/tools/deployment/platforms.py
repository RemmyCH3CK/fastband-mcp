"""
Platform Clients - Interface with deployment platforms.

Supports auto-detection and unified API across:
- Vercel, Netlify, Railway, Fly.io
- Docker, Kubernetes
- SSH deployments
"""

import json
import logging
import os
import subprocess
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastband.tools.deployment.models import (
    Deployment,
    DeploymentConfig,
    DeploymentHealth,
    DeploymentMetrics,
    DeploymentPlatform,
    DeploymentStatus,
    EnvironmentType,
)

logger = logging.getLogger(__name__)


class PlatformClient(ABC):
    """Abstract base class for deployment platform clients."""

    platform: DeploymentPlatform

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this platform is configured for the project."""
        pass

    @abstractmethod
    def get_config(self) -> DeploymentConfig | None:
        """Get deployment configuration from project files."""
        pass

    @abstractmethod
    def list_deployments(self, limit: int = 10) -> list[Deployment]:
        """List recent deployments."""
        pass

    @abstractmethod
    def get_deployment(self, deployment_id: str) -> Deployment | None:
        """Get a specific deployment by ID."""
        pass

    @abstractmethod
    def get_latest_deployment(self, environment: EnvironmentType | None = None) -> Deployment | None:
        """Get the most recent deployment, optionally filtered by environment."""
        pass

    @abstractmethod
    def deploy(self, environment: EnvironmentType = EnvironmentType.PREVIEW) -> Deployment | None:
        """Trigger a new deployment."""
        pass

    @abstractmethod
    def get_build_logs(self, deployment_id: str) -> list[str]:
        """Get build logs for a deployment."""
        pass


class VercelClient(PlatformClient):
    """Vercel deployment client using Vercel CLI."""

    platform = DeploymentPlatform.VERCEL

    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self._project_info: dict | None = None

    def _run_vercel(self, args: list[str], timeout: int = 60) -> tuple[bool, str]:
        """Run a Vercel CLI command."""
        try:
            result = subprocess.run(
                ["vercel", *args, "--yes"],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=self.project_root,
            )
            return result.returncode == 0, result.stdout + result.stderr
        except FileNotFoundError:
            return False, "Vercel CLI not installed"
        except subprocess.TimeoutExpired:
            return False, "Command timed out"
        except Exception as e:
            return False, str(e)

    def is_available(self) -> bool:
        """Check if Vercel is configured."""
        # Check for vercel.json or .vercel directory
        return (
            (self.project_root / "vercel.json").exists() or
            (self.project_root / ".vercel" / "project.json").exists()
        )

    def _load_project_info(self) -> dict:
        """Load Vercel project configuration."""
        if self._project_info:
            return self._project_info

        project_json = self.project_root / ".vercel" / "project.json"
        if project_json.exists():
            with open(project_json) as f:
                self._project_info = json.load(f)
                return self._project_info

        return {}

    def get_config(self) -> DeploymentConfig | None:
        """Get Vercel deployment configuration."""
        if not self.is_available():
            return None

        project_info = self._load_project_info()
        vercel_json = self.project_root / "vercel.json"

        config = DeploymentConfig(
            platform=DeploymentPlatform.VERCEL,
            project_id=project_info.get("projectId", ""),
            project_name=project_info.get("projectName", ""),
        )

        if vercel_json.exists():
            with open(vercel_json) as f:
                vercel_config = json.load(f)
                config.build_command = vercel_config.get("buildCommand", "")
                config.output_directory = vercel_config.get("outputDirectory", "")
                config.framework = vercel_config.get("framework", "")

        return config

    def list_deployments(self, limit: int = 10) -> list[Deployment]:
        """List recent Vercel deployments using CLI."""
        success, output = self._run_vercel(["list", "--json", f"--limit={limit}"])

        if not success:
            logger.warning(f"Failed to list deployments: {output}")
            return []

        try:
            data = json.loads(output)
            deployments = []

            for d in data.get("deployments", [])[:limit]:
                status = DeploymentStatus.READY
                if d.get("state") == "BUILDING":
                    status = DeploymentStatus.BUILDING
                elif d.get("state") == "ERROR":
                    status = DeploymentStatus.FAILED
                elif d.get("state") == "CANCELED":
                    status = DeploymentStatus.CANCELLED

                env = EnvironmentType.PREVIEW
                if d.get("target") == "production":
                    env = EnvironmentType.PRODUCTION

                created_at = datetime.fromtimestamp(
                    d.get("created", 0) / 1000,
                    tz=timezone.utc
                )

                deployments.append(Deployment(
                    id=d.get("uid", ""),
                    platform=DeploymentPlatform.VERCEL,
                    status=status,
                    url=f"https://{d.get('url', '')}",
                    branch=d.get("meta", {}).get("githubCommitRef", ""),
                    commit_sha=d.get("meta", {}).get("githubCommitSha", ""),
                    environment=env,
                    created_at=created_at,
                    creator=d.get("creator", {}).get("username", ""),
                ))

            return deployments
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse Vercel output: {output[:200]}")
            return []

    def get_deployment(self, deployment_id: str) -> Deployment | None:
        """Get a specific deployment by ID."""
        success, output = self._run_vercel(["inspect", deployment_id, "--json"])

        if not success:
            return None

        try:
            d = json.loads(output)

            status = DeploymentStatus.READY
            if d.get("readyState") == "BUILDING":
                status = DeploymentStatus.BUILDING
            elif d.get("readyState") == "ERROR":
                status = DeploymentStatus.FAILED

            env = EnvironmentType.PREVIEW
            if d.get("target") == "production":
                env = EnvironmentType.PRODUCTION

            return Deployment(
                id=d.get("id", deployment_id),
                platform=DeploymentPlatform.VERCEL,
                status=status,
                url=f"https://{d.get('url', '')}",
                inspect_url=d.get("inspectorUrl", ""),
                branch=d.get("meta", {}).get("githubCommitRef", ""),
                commit_sha=d.get("meta", {}).get("githubCommitSha", ""),
                commit_message=d.get("meta", {}).get("githubCommitMessage", ""),
                environment=env,
                build_duration_ms=d.get("buildingAt", 0),
            )
        except json.JSONDecodeError:
            return None

    def get_latest_deployment(self, environment: EnvironmentType | None = None) -> Deployment | None:
        """Get the most recent deployment."""
        deployments = self.list_deployments(limit=20)

        if environment:
            deployments = [d for d in deployments if d.environment == environment]

        return deployments[0] if deployments else None

    def deploy(self, environment: EnvironmentType = EnvironmentType.PREVIEW) -> Deployment | None:
        """Trigger a new Vercel deployment."""
        args = ["deploy"]
        if environment == EnvironmentType.PRODUCTION:
            args.append("--prod")

        success, output = self._run_vercel(args, timeout=300)

        if not success:
            logger.error(f"Deployment failed: {output}")
            return None

        # Parse deployment URL from output
        lines = output.strip().split("\n")
        url = lines[-1] if lines else ""

        if url.startswith("https://"):
            # Get deployment details
            deployment_id = url.split("/")[-1].split(".")[0]
            return self.get_deployment(deployment_id)

        return None

    def get_build_logs(self, deployment_id: str) -> list[str]:
        """Get build logs for a deployment."""
        success, output = self._run_vercel(["logs", deployment_id, "--json"])

        if not success:
            return [f"Failed to get logs: {output}"]

        try:
            logs = []
            for line in output.strip().split("\n"):
                if line:
                    log_entry = json.loads(line)
                    logs.append(log_entry.get("text", ""))
            return logs
        except json.JSONDecodeError:
            return output.strip().split("\n")


class NetlifyClient(PlatformClient):
    """Netlify deployment client using Netlify CLI."""

    platform = DeploymentPlatform.NETLIFY

    def __init__(self, project_root: str):
        self.project_root = Path(project_root)

    def _run_netlify(self, args: list[str], timeout: int = 60) -> tuple[bool, str]:
        """Run a Netlify CLI command."""
        try:
            result = subprocess.run(
                ["netlify", *args, "--json"],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=self.project_root,
            )
            return result.returncode == 0, result.stdout
        except FileNotFoundError:
            return False, "Netlify CLI not installed"
        except Exception as e:
            return False, str(e)

    def is_available(self) -> bool:
        """Check if Netlify is configured."""
        return (
            (self.project_root / "netlify.toml").exists() or
            (self.project_root / ".netlify" / "state.json").exists()
        )

    def get_config(self) -> DeploymentConfig | None:
        """Get Netlify configuration."""
        if not self.is_available():
            return None

        config = DeploymentConfig(platform=DeploymentPlatform.NETLIFY)

        # Try to load from .netlify/state.json
        state_file = self.project_root / ".netlify" / "state.json"
        if state_file.exists():
            with open(state_file) as f:
                state = json.load(f)
                config.project_id = state.get("siteId", "")

        return config

    def list_deployments(self, limit: int = 10) -> list[Deployment]:
        """List recent Netlify deployments."""
        success, output = self._run_netlify(["api", "listSiteDeploys"])

        if not success:
            return []

        try:
            deploys = json.loads(output)[:limit]
            return [
                Deployment(
                    id=d.get("id", ""),
                    platform=DeploymentPlatform.NETLIFY,
                    status=self._map_status(d.get("state", "")),
                    url=d.get("deploy_ssl_url", d.get("deploy_url", "")),
                    branch=d.get("branch", ""),
                    commit_sha=d.get("commit_ref", ""),
                    environment=(
                        EnvironmentType.PRODUCTION
                        if d.get("context") == "production"
                        else EnvironmentType.PREVIEW
                    ),
                    build_duration_ms=d.get("deploy_time", 0) * 1000,
                )
                for d in deploys
            ]
        except json.JSONDecodeError:
            return []

    def _map_status(self, state: str) -> DeploymentStatus:
        """Map Netlify state to DeploymentStatus."""
        mapping = {
            "ready": DeploymentStatus.READY,
            "building": DeploymentStatus.BUILDING,
            "error": DeploymentStatus.FAILED,
            "cancelled": DeploymentStatus.CANCELLED,
        }
        return mapping.get(state.lower(), DeploymentStatus.PENDING)

    def get_deployment(self, deployment_id: str) -> Deployment | None:
        """Get a specific deployment."""
        success, output = self._run_netlify(["api", "getDeploy", "--data", f'{{"deploy_id": "{deployment_id}"}}'])
        if not success:
            return None

        try:
            d = json.loads(output)
            return Deployment(
                id=d.get("id", deployment_id),
                platform=DeploymentPlatform.NETLIFY,
                status=self._map_status(d.get("state", "")),
                url=d.get("deploy_ssl_url", ""),
                branch=d.get("branch", ""),
                commit_sha=d.get("commit_ref", ""),
            )
        except json.JSONDecodeError:
            return None

    def get_latest_deployment(self, environment: EnvironmentType | None = None) -> Deployment | None:
        """Get the most recent deployment."""
        deployments = self.list_deployments(limit=10)
        if environment:
            deployments = [d for d in deployments if d.environment == environment]
        return deployments[0] if deployments else None

    def deploy(self, environment: EnvironmentType = EnvironmentType.PREVIEW) -> Deployment | None:
        """Trigger a new deployment."""
        args = ["deploy"]
        if environment == EnvironmentType.PRODUCTION:
            args.append("--prod")

        success, output = self._run_netlify(args)
        if success:
            return self.get_latest_deployment()
        return None

    def get_build_logs(self, deployment_id: str) -> list[str]:
        """Get build logs."""
        success, output = self._run_netlify(["api", "getDeploy", "--data", f'{{"deploy_id": "{deployment_id}"}}'])
        if success:
            try:
                data = json.loads(output)
                return [data.get("error_message", "No logs available")]
            except json.JSONDecodeError:
                pass
        return ["Logs not available"]


def detect_platform(project_root: str) -> PlatformClient | None:
    """Auto-detect the deployment platform for a project."""
    root = Path(project_root)

    # Check platforms in order of preference
    clients = [
        VercelClient(project_root),
        NetlifyClient(project_root),
    ]

    for client in clients:
        if client.is_available():
            return client

    return None


def get_platform_client(project_root: str, platform: DeploymentPlatform | None = None) -> PlatformClient | None:
    """Get a platform client, auto-detecting if platform not specified."""
    if platform is None:
        return detect_platform(project_root)

    if platform == DeploymentPlatform.VERCEL:
        return VercelClient(project_root)
    elif platform == DeploymentPlatform.NETLIFY:
        return NetlifyClient(project_root)

    return None


def check_deployment_health(url: str, timeout: int = 10) -> DeploymentHealth:
    """Check the health of a deployed URL."""
    import socket
    import ssl
    import urllib.request
    from datetime import datetime, timezone

    health = DeploymentHealth(
        deployment_id="",
        url=url,
    )

    try:
        start = datetime.now(timezone.utc)
        req = urllib.request.Request(url, method="HEAD")
        req.add_header("User-Agent", "Fastband-Health-Check/1.0")

        with urllib.request.urlopen(req, timeout=timeout) as response:
            health.is_reachable = True
            health.status_code = response.status
            health.response_time_ms = int(
                (datetime.now(timezone.utc) - start).total_seconds() * 1000
            )

        # Check SSL certificate
        if url.startswith("https://"):
            hostname = url.split("//")[1].split("/")[0]
            context = ssl.create_default_context()
            with socket.create_connection((hostname, 443), timeout=timeout) as sock:
                with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                    cert = ssock.getpeercert()
                    if cert:
                        health.ssl_valid = True
                        not_after = cert.get("notAfter", "")
                        if not_after:
                            # Parse SSL date format
                            expire_date = datetime.strptime(
                                not_after, "%b %d %H:%M:%S %Y %Z"
                            ).replace(tzinfo=timezone.utc)
                            health.ssl_expires_at = expire_date
                            health.ssl_days_remaining = (
                                expire_date - datetime.now(timezone.utc)
                            ).days

    except urllib.error.HTTPError as e:
        health.is_reachable = True
        health.status_code = e.code
    except urllib.error.URLError as e:
        health.error = str(e.reason)
    except socket.timeout:
        health.error = "Connection timed out"
    except ssl.SSLError as e:
        health.error = f"SSL error: {e}"
    except Exception as e:
        health.error = str(e)

    return health

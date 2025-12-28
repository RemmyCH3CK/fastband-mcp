"""
Fastband configuration management.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any, Optional, List
import os
import yaml


@dataclass
class AIProviderConfig:
    """Configuration for a single AI provider."""
    model: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    max_tokens: int = 4096
    temperature: float = 0.7


@dataclass
class ToolsConfig:
    """Tool garage configuration."""
    max_active: int = 60
    auto_load_core: bool = True
    performance_warning_threshold: int = 40


@dataclass
class TicketsConfig:
    """Ticket manager configuration."""
    enabled: bool = True
    mode: str = "cli_web"  # cli, cli_web, embedded
    web_port: int = 5050
    review_agents: bool = True


@dataclass
class BackupConfig:
    """Backup manager configuration."""
    enabled: bool = True
    daily_enabled: bool = True
    daily_time: str = "02:00"
    daily_retention: int = 7
    weekly_enabled: bool = True
    weekly_day: str = "sunday"
    weekly_retention: int = 4
    change_detection: bool = True


@dataclass
class GitHubConfig:
    """GitHub integration configuration."""
    enabled: bool = False
    automation_level: str = "hybrid"  # full, guided, hybrid, none
    default_branch: str = "main"


@dataclass
class FastbandConfig:
    """
    Complete Fastband configuration.

    Loaded from .fastband/config.yaml or environment variables.
    """
    version: str = "1.2025.12"

    # Project info (from detection)
    project_name: Optional[str] = None
    project_type: Optional[str] = None
    primary_language: Optional[str] = None

    # AI Providers
    default_provider: str = "claude"
    providers: Dict[str, AIProviderConfig] = field(default_factory=dict)

    # Components
    tools: ToolsConfig = field(default_factory=ToolsConfig)
    tickets: TicketsConfig = field(default_factory=TicketsConfig)
    backup: BackupConfig = field(default_factory=BackupConfig)
    github: GitHubConfig = field(default_factory=GitHubConfig)

    # Storage
    storage_backend: str = "sqlite"  # sqlite, postgres, mysql, file
    storage_path: str = ".fastband/data.db"

    @classmethod
    def from_file(cls, path: Path) -> "FastbandConfig":
        """Load configuration from YAML file."""
        if not path.exists():
            return cls()

        with open(path) as f:
            data = yaml.safe_load(f) or {}

        return cls.from_dict(data.get("fastband", data))

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FastbandConfig":
        """Create config from dictionary."""
        config = cls()

        if "version" in data:
            config.version = data["version"]

        # Project info
        if "project" in data:
            p = data["project"]
            config.project_name = p.get("name")
            config.project_type = p.get("type")
            config.primary_language = p.get("language")

        if "ai" in data:
            ai = data["ai"]
            config.default_provider = ai.get("default_provider", "claude")

            for name, provider_data in ai.get("providers", {}).items():
                config.providers[name] = AIProviderConfig(
                    model=provider_data.get("model", ""),
                    api_key=provider_data.get("api_key"),
                    base_url=provider_data.get("base_url"),
                    max_tokens=provider_data.get("max_tokens", 4096),
                    temperature=provider_data.get("temperature", 0.7),
                )

        if "tools" in data:
            t = data["tools"]
            config.tools = ToolsConfig(
                max_active=t.get("max_active", 60),
                auto_load_core=t.get("auto_load_core", True),
                performance_warning_threshold=t.get("performance_warning_threshold", 40),
            )

        if "tickets" in data:
            t = data["tickets"]
            config.tickets = TicketsConfig(
                enabled=t.get("enabled", True),
                mode=t.get("mode", "cli_web"),
                web_port=t.get("web_port", 5050),
                review_agents=t.get("review_agents", True),
            )

        if "backup" in data:
            b = data["backup"]
            config.backup = BackupConfig(
                enabled=b.get("enabled", True),
                daily_enabled=b.get("daily_enabled", True),
                daily_time=b.get("daily_time", "02:00"),
                daily_retention=b.get("daily_retention", 7),
                weekly_enabled=b.get("weekly_enabled", True),
                weekly_day=b.get("weekly_day", "sunday"),
                weekly_retention=b.get("weekly_retention", 4),
                change_detection=b.get("change_detection", True),
            )

        if "github" in data:
            g = data["github"]
            config.github = GitHubConfig(
                enabled=g.get("enabled", False),
                automation_level=g.get("automation_level", "hybrid"),
                default_branch=g.get("default_branch", "main"),
            )

        if "storage" in data:
            s = data["storage"]
            config.storage_backend = s.get("backend", "sqlite")
            config.storage_path = s.get("path", ".fastband/data.db")

        return config

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        result: Dict[str, Any] = {
            "fastband": {
                "version": self.version,
            }
        }

        # Add project info if set
        if self.project_name or self.project_type or self.primary_language:
            result["fastband"]["project"] = {
                "name": self.project_name,
                "type": self.project_type,
                "language": self.primary_language,
            }

        result["fastband"]["ai"] = {
            "default_provider": self.default_provider,
            "providers": {
                name: {
                    "model": p.model,
                    "max_tokens": p.max_tokens,
                    "temperature": p.temperature,
                }
                for name, p in self.providers.items()
            },
        }

        result["fastband"]["tools"] = {
            "max_active": self.tools.max_active,
            "auto_load_core": self.tools.auto_load_core,
            "performance_warning_threshold": self.tools.performance_warning_threshold,
        }

        result["fastband"]["tickets"] = {
            "enabled": self.tickets.enabled,
            "mode": self.tickets.mode,
            "web_port": self.tickets.web_port,
            "review_agents": self.tickets.review_agents,
        }

        result["fastband"]["backup"] = {
            "enabled": self.backup.enabled,
            "daily_enabled": self.backup.daily_enabled,
            "daily_time": self.backup.daily_time,
            "daily_retention": self.backup.daily_retention,
            "weekly_enabled": self.backup.weekly_enabled,
            "weekly_day": self.backup.weekly_day,
            "weekly_retention": self.backup.weekly_retention,
            "change_detection": self.backup.change_detection,
        }

        result["fastband"]["github"] = {
            "enabled": self.github.enabled,
            "automation_level": self.github.automation_level,
            "default_branch": self.github.default_branch,
        }

        result["fastband"]["storage"] = {
            "backend": self.storage_backend,
            "path": self.storage_path,
        }

        return result

    def save(self, path: Path) -> None:
        """Save configuration to YAML file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            yaml.dump(self.to_dict(), f, default_flow_style=False)


# Global config instance
_config: Optional[FastbandConfig] = None


def get_config(project_path: Optional[Path] = None) -> FastbandConfig:
    """
    Get Fastband configuration.

    Loads from .fastband/config.yaml in project directory.
    Falls back to defaults if not found.
    """
    global _config

    if _config is not None:
        return _config

    if project_path is None:
        project_path = Path.cwd()

    config_path = project_path / ".fastband" / "config.yaml"
    _config = FastbandConfig.from_file(config_path)

    return _config

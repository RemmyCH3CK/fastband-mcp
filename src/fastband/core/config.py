"""
Fastband configuration management.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class AIProviderConfig:
    """Configuration for a single AI provider."""

    model: str
    api_key: str | None = None
    base_url: str | None = None
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
    prefix: str = "FB"  # Ticket number prefix (e.g., FB-001, FB-002)


@dataclass
class BackupHooksConfig:
    """Backup hooks configuration."""

    before_build: bool = True
    after_ticket_completion: bool = True
    on_config_change: bool = False


@dataclass
class BackupConfig:
    """Backup manager configuration."""

    enabled: bool = True

    # Scheduler settings
    scheduler_enabled: bool = True
    interval_hours: int = 2  # Run full backup every N hours

    # Storage location (relative to project or absolute path)
    backup_path: str = ".fastband/backups"

    # Retention settings
    retention_days: int = 3  # Keep 3 full days of backups
    max_backups: int = 50  # Maximum number of backups to keep

    # Legacy settings (kept for compatibility)
    daily_enabled: bool = True
    daily_time: str = "02:00"
    daily_retention: int = 7
    weekly_enabled: bool = True
    weekly_day: str = "sunday"
    weekly_retention: int = 4

    # Change detection
    change_detection: bool = True

    # Hooks
    hooks: BackupHooksConfig = field(default_factory=BackupHooksConfig)


@dataclass
class GitHubConfig:
    """GitHub integration configuration."""

    enabled: bool = False
    automation_level: str = "hybrid"  # full, guided, hybrid, none
    default_branch: str = "main"


@dataclass
class MemoryConfig:
    """
    Memory architecture configuration.

    Controls the 5-tier memory system and agent handoffs.
    Semantic memory is ENABLED by default (recommended) - it provides
    cross-session learning from resolved tickets to help agents solve
    similar problems faster.
    """

    # Semantic memory (cross-session learning from past tickets)
    # RECOMMENDED: Keep enabled for better agent performance
    semantic_memory_enabled: bool = True

    # Token budget settings
    default_working_memory: int = 20_000  # Base working memory tokens
    max_working_memory: int = 80_000  # Hard ceiling
    auto_expand_enabled: bool = True  # Auto-expand on complexity

    # Handoff thresholds (percentage of budget)
    handoff_warning_threshold: int = 60  # Start preparing handoff
    handoff_critical_threshold: int = 80  # Must handoff immediately

    # Lazy Bible loading
    lazy_bible_loading: bool = True  # Load sections on-demand
    bible_summary_tokens: int = 850  # Tokens for initial summary

    # Handoff storage
    handoff_storage_path: str = ".fastband/handoffs"
    handoff_retention_hours: int = 48  # Keep handoffs for 48 hours


@dataclass
class FastbandConfig:
    """
    Complete Fastband configuration.

    Loaded from .fastband/config.yaml or environment variables.
    """

    version: str = "1.2025.12"

    # Project info (from detection)
    project_name: str | None = None
    project_type: str | None = None
    primary_language: str | None = None

    # Operation mode: 'manual' or 'yolo'
    # - manual: Agents confirm all actions via chat/CLI
    # - yolo: Full automation following Agent Bible laws
    operation_mode: str = "manual"

    # AI Providers
    default_provider: str = "claude"
    providers: dict[str, AIProviderConfig] = field(default_factory=dict)

    # Components
    tools: ToolsConfig = field(default_factory=ToolsConfig)
    tickets: TicketsConfig = field(default_factory=TicketsConfig)
    backup: BackupConfig = field(default_factory=BackupConfig)
    github: GitHubConfig = field(default_factory=GitHubConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)

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
    def from_dict(cls, data: dict[str, Any]) -> "FastbandConfig":
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

        # Operation mode
        if "operation_mode" in data:
            config.operation_mode = data["operation_mode"]

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
                prefix=t.get("prefix", "FB"),
            )

        if "backup" in data:
            b = data["backup"]
            # Parse hooks config
            hooks_data = b.get("hooks", {})
            hooks_config = BackupHooksConfig(
                before_build=hooks_data.get("before_build", True),
                after_ticket_completion=hooks_data.get("after_ticket_completion", True),
                on_config_change=hooks_data.get("on_config_change", False),
            )
            config.backup = BackupConfig(
                enabled=b.get("enabled", True),
                scheduler_enabled=b.get("scheduler_enabled", True),
                interval_hours=b.get("interval_hours", 2),
                backup_path=b.get("backup_path", ".fastband/backups"),
                retention_days=b.get("retention_days", 3),
                max_backups=b.get("max_backups", 50),
                daily_enabled=b.get("daily_enabled", True),
                daily_time=b.get("daily_time", "02:00"),
                daily_retention=b.get("daily_retention", 7),
                weekly_enabled=b.get("weekly_enabled", True),
                weekly_day=b.get("weekly_day", "sunday"),
                weekly_retention=b.get("weekly_retention", 4),
                change_detection=b.get("change_detection", True),
                hooks=hooks_config,
            )

        if "github" in data:
            g = data["github"]
            config.github = GitHubConfig(
                enabled=g.get("enabled", False),
                automation_level=g.get("automation_level", "hybrid"),
                default_branch=g.get("default_branch", "main"),
            )

        if "memory" in data:
            m = data["memory"]
            config.memory = MemoryConfig(
                semantic_memory_enabled=m.get("semantic_memory_enabled", True),
                default_working_memory=m.get("default_working_memory", 20_000),
                max_working_memory=m.get("max_working_memory", 80_000),
                auto_expand_enabled=m.get("auto_expand_enabled", True),
                handoff_warning_threshold=m.get("handoff_warning_threshold", 60),
                handoff_critical_threshold=m.get("handoff_critical_threshold", 80),
                lazy_bible_loading=m.get("lazy_bible_loading", True),
                bible_summary_tokens=m.get("bible_summary_tokens", 850),
                handoff_storage_path=m.get("handoff_storage_path", ".fastband/handoffs"),
                handoff_retention_hours=m.get("handoff_retention_hours", 48),
            )

        if "storage" in data:
            s = data["storage"]
            config.storage_backend = s.get("backend", "sqlite")
            config.storage_path = s.get("path", ".fastband/data.db")

        return config

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        result: dict[str, Any] = {
            "fastband": {
                "version": self.version,
                "operation_mode": self.operation_mode,
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
            "prefix": self.tickets.prefix,
        }

        result["fastband"]["backup"] = {
            "enabled": self.backup.enabled,
            "scheduler_enabled": self.backup.scheduler_enabled,
            "interval_hours": self.backup.interval_hours,
            "backup_path": self.backup.backup_path,
            "retention_days": self.backup.retention_days,
            "max_backups": self.backup.max_backups,
            "daily_enabled": self.backup.daily_enabled,
            "daily_time": self.backup.daily_time,
            "daily_retention": self.backup.daily_retention,
            "weekly_enabled": self.backup.weekly_enabled,
            "weekly_day": self.backup.weekly_day,
            "weekly_retention": self.backup.weekly_retention,
            "change_detection": self.backup.change_detection,
            "hooks": {
                "before_build": self.backup.hooks.before_build,
                "after_ticket_completion": self.backup.hooks.after_ticket_completion,
                "on_config_change": self.backup.hooks.on_config_change,
            },
        }

        result["fastband"]["github"] = {
            "enabled": self.github.enabled,
            "automation_level": self.github.automation_level,
            "default_branch": self.github.default_branch,
        }

        # Memory configuration with explanatory comments
        result["fastband"]["memory"] = {
            # Semantic memory learns from resolved tickets to help future agents
            # RECOMMENDED: Keep enabled for better performance
            "semantic_memory_enabled": self.memory.semantic_memory_enabled,
            "default_working_memory": self.memory.default_working_memory,
            "max_working_memory": self.memory.max_working_memory,
            "auto_expand_enabled": self.memory.auto_expand_enabled,
            "handoff_warning_threshold": self.memory.handoff_warning_threshold,
            "handoff_critical_threshold": self.memory.handoff_critical_threshold,
            "lazy_bible_loading": self.memory.lazy_bible_loading,
            "bible_summary_tokens": self.memory.bible_summary_tokens,
            "handoff_storage_path": self.memory.handoff_storage_path,
            "handoff_retention_hours": self.memory.handoff_retention_hours,
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
_config: FastbandConfig | None = None


def get_config(project_path: Path | None = None) -> FastbandConfig:
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

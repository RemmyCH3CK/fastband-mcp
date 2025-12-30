"""
Backup Alert System.

Provides fire-alarm style notifications when backup operations fail.
Supports multiple notification channels:
- Console/logging (always active)
- File-based alert log (always active)
- System notifications (macOS/Linux)
- Webhooks (Slack, Discord, custom)
- Email (requires configuration)

Usage:
    from fastband.backup.alerts import AlertManager, AlertLevel, send_backup_alert

    # Send an alert
    send_backup_alert(
        level=AlertLevel.CRITICAL,
        title="Backup Failed",
        message="Scheduled backup failed due to disk full",
        error=exception,
    )
"""

import json
import logging
import platform
import shutil
import subprocess
import threading
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class AlertLevel(Enum):
    """Alert severity levels."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"  # Fire alarm level

    @property
    def emoji(self) -> str:
        """Get emoji for the alert level."""
        return {
            AlertLevel.INFO: "ℹ️",
            AlertLevel.WARNING: "⚠️",
            AlertLevel.ERROR: "❌",
            AlertLevel.CRITICAL: "🔥",
        }[self]

    @property
    def color(self) -> str:
        """Get color code for the alert level (for Slack/Discord)."""
        return {
            AlertLevel.INFO: "#36a64f",
            AlertLevel.WARNING: "#ff9800",
            AlertLevel.ERROR: "#f44336",
            AlertLevel.CRITICAL: "#b71c1c",
        }[self]


@dataclass
class Alert:
    """Represents a backup alert."""

    id: str
    level: AlertLevel
    title: str
    message: str
    timestamp: datetime = field(default_factory=datetime.now)
    error: str | None = None
    context: dict[str, Any] = field(default_factory=dict)
    acknowledged: bool = False
    sent_to: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "level": self.level.value,
            "title": self.title,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "error": self.error,
            "context": self.context,
            "acknowledged": self.acknowledged,
            "sent_to": self.sent_to,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Alert":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            level=AlertLevel(data["level"]),
            title=data["title"],
            message=data["message"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            error=data.get("error"),
            context=data.get("context", {}),
            acknowledged=data.get("acknowledged", False),
            sent_to=data.get("sent_to", []),
        )

    def format_text(self) -> str:
        """Format alert as plain text."""
        lines = [
            f"{self.level.emoji} [{self.level.value.upper()}] {self.title}",
            f"Time: {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
            f"Message: {self.message}",
        ]
        if self.error:
            lines.append(f"Error: {self.error}")
        if self.context:
            lines.append(f"Context: {json.dumps(self.context)}")
        return "\n".join(lines)


@dataclass
class AlertConfig:
    """Configuration for alert channels."""

    # File alerts (always enabled)
    alert_log_path: Path | None = None

    # System notifications
    system_notifications: bool = True

    # Webhook notifications
    slack_webhook_url: str | None = None
    discord_webhook_url: str | None = None
    custom_webhook_url: str | None = None

    # Email notifications
    email_enabled: bool = False
    email_to: str | None = None
    email_from: str | None = None
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None

    # Alert thresholds
    min_level: AlertLevel = AlertLevel.WARNING  # Only alert at this level or higher

    # Rate limiting
    max_alerts_per_hour: int = 10
    cooldown_seconds: int = 60  # Min time between same alerts


class AlertChannel:
    """Base class for alert channels."""

    name: str = "base"

    def send(self, alert: Alert) -> bool:
        """
        Send an alert through this channel.

        Returns:
            True if sent successfully, False otherwise
        """
        raise NotImplementedError


class LogChannel(AlertChannel):
    """Logs alerts to Python logging."""

    name = "log"

    def send(self, alert: Alert) -> bool:
        """Log the alert."""
        log_level = {
            AlertLevel.INFO: logging.INFO,
            AlertLevel.WARNING: logging.WARNING,
            AlertLevel.ERROR: logging.ERROR,
            AlertLevel.CRITICAL: logging.CRITICAL,
        }[alert.level]

        logger.log(log_level, f"BACKUP ALERT: {alert.format_text()}")
        return True


class FileChannel(AlertChannel):
    """Writes alerts to a file."""

    name = "file"

    def __init__(self, alert_log_path: Path):
        self.alert_log_path = Path(alert_log_path)

    def send(self, alert: Alert) -> bool:
        """Write alert to file."""
        try:
            self.alert_log_path.parent.mkdir(parents=True, exist_ok=True)

            # Load existing alerts
            alerts = []
            if self.alert_log_path.exists():
                try:
                    alerts = json.loads(self.alert_log_path.read_text())
                except json.JSONDecodeError:
                    alerts = []

            # Append new alert
            alerts.append(alert.to_dict())

            # Keep only last 100 alerts
            alerts = alerts[-100:]

            # Save
            self.alert_log_path.write_text(json.dumps(alerts, indent=2))
            return True

        except Exception as e:
            logger.error(f"Failed to write alert to file: {e}")
            return False


class SystemNotificationChannel(AlertChannel):
    """Sends system notifications (macOS/Linux)."""

    name = "system"

    def send(self, alert: Alert) -> bool:
        """Send system notification."""
        system = platform.system()

        try:
            if system == "Darwin":
                return self._send_macos(alert)
            elif system == "Linux":
                return self._send_linux(alert)
            else:
                logger.debug(f"System notifications not supported on {system}")
                return False
        except Exception as e:
            logger.error(f"Failed to send system notification: {e}")
            return False

    def _send_macos(self, alert: Alert) -> bool:
        """Send notification on macOS."""
        script = f'''
        display notification "{alert.message}" with title "Fastband Backup {alert.level.emoji}" subtitle "{alert.title}"
        '''
        subprocess.run(["osascript", "-e", script], capture_output=True)
        return True

    def _send_linux(self, alert: Alert) -> bool:
        """Send notification on Linux."""
        if shutil.which("notify-send"):
            urgency = {
                AlertLevel.INFO: "low",
                AlertLevel.WARNING: "normal",
                AlertLevel.ERROR: "critical",
                AlertLevel.CRITICAL: "critical",
            }[alert.level]

            subprocess.run(
                [
                    "notify-send",
                    "-u",
                    urgency,
                    f"Fastband Backup {alert.level.emoji}",
                    f"{alert.title}\n{alert.message}",
                ],
                capture_output=True,
            )
            return True
        return False


class SlackChannel(AlertChannel):
    """Sends alerts to Slack via webhook."""

    name = "slack"

    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    def send(self, alert: Alert) -> bool:
        """Send alert to Slack."""
        try:
            payload = {
                "attachments": [
                    {
                        "color": alert.level.color,
                        "title": f"{alert.level.emoji} {alert.title}",
                        "text": alert.message,
                        "fields": [
                            {"title": "Level", "value": alert.level.value.upper(), "short": True},
                            {
                                "title": "Time",
                                "value": alert.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                                "short": True,
                            },
                        ],
                        "footer": "Fastband Backup System",
                    }
                ]
            }

            if alert.error:
                payload["attachments"][0]["fields"].append(
                    {
                        "title": "Error",
                        "value": f"```{alert.error}```",
                        "short": False,
                    }
                )

            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                self.webhook_url,
                data=data,
                headers={"Content-Type": "application/json"},
            )
            urllib.request.urlopen(req, timeout=10)
            return True

        except Exception as e:
            logger.error(f"Failed to send Slack alert: {e}")
            return False


class DiscordChannel(AlertChannel):
    """Sends alerts to Discord via webhook."""

    name = "discord"

    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    def send(self, alert: Alert) -> bool:
        """Send alert to Discord."""
        try:
            color_int = int(alert.level.color.lstrip("#"), 16)

            payload = {
                "embeds": [
                    {
                        "title": f"{alert.level.emoji} {alert.title}",
                        "description": alert.message,
                        "color": color_int,
                        "fields": [
                            {"name": "Level", "value": alert.level.value.upper(), "inline": True},
                            {
                                "name": "Time",
                                "value": alert.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                                "inline": True,
                            },
                        ],
                        "footer": {"text": "Fastband Backup System"},
                    }
                ]
            }

            if alert.error:
                payload["embeds"][0]["fields"].append(
                    {
                        "name": "Error",
                        "value": f"```{alert.error[:1000]}```",
                        "inline": False,
                    }
                )

            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                self.webhook_url,
                data=data,
                headers={"Content-Type": "application/json"},
            )
            urllib.request.urlopen(req, timeout=10)
            return True

        except Exception as e:
            logger.error(f"Failed to send Discord alert: {e}")
            return False


class WebhookChannel(AlertChannel):
    """Sends alerts to a custom webhook."""

    name = "webhook"

    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    def send(self, alert: Alert) -> bool:
        """Send alert to custom webhook."""
        try:
            payload = alert.to_dict()
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                self.webhook_url,
                data=data,
                headers={"Content-Type": "application/json"},
            )
            urllib.request.urlopen(req, timeout=10)
            return True

        except Exception as e:
            logger.error(f"Failed to send webhook alert: {e}")
            return False


class AlertManager:
    """
    Manages backup alerts across multiple channels.

    Provides:
    - Multi-channel alert dispatching
    - Rate limiting to prevent alert storms
    - Alert history and acknowledgment
    - Async alert sending
    """

    def __init__(
        self,
        project_path: Path | None = None,
        config: AlertConfig | None = None,
    ):
        self.project_path = Path(project_path or Path.cwd()).resolve()
        self.fastband_dir = self.project_path / ".fastband"
        self.config = config or AlertConfig()

        # Set default alert log path
        if self.config.alert_log_path is None:
            self.config.alert_log_path = self.fastband_dir / "alerts.json"

        # Rate limiting
        self._alert_times: dict[str, datetime] = {}
        self._alert_counts: dict[str, int] = {}
        self._lock = threading.Lock()

        # Initialize channels
        self._channels: list[AlertChannel] = self._init_channels()

    def _init_channels(self) -> list[AlertChannel]:
        """Initialize alert channels based on config."""
        channels: list[AlertChannel] = []

        # Always add logging
        channels.append(LogChannel())

        # Always add file channel
        channels.append(FileChannel(self.config.alert_log_path))

        # System notifications
        if self.config.system_notifications:
            channels.append(SystemNotificationChannel())

        # Slack
        if self.config.slack_webhook_url:
            channels.append(SlackChannel(self.config.slack_webhook_url))

        # Discord
        if self.config.discord_webhook_url:
            channels.append(DiscordChannel(self.config.discord_webhook_url))

        # Custom webhook
        if self.config.custom_webhook_url:
            channels.append(WebhookChannel(self.config.custom_webhook_url))

        return channels

    def _generate_alert_id(self) -> str:
        """Generate a unique alert ID."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        return f"alert_{timestamp}"

    def _should_rate_limit(self, alert: Alert) -> bool:
        """Check if alert should be rate limited."""
        with self._lock:
            now = datetime.now()
            key = f"{alert.level.value}:{alert.title}"

            # Check cooldown
            last_time = self._alert_times.get(key)
            if last_time:
                elapsed = (now - last_time).total_seconds()
                if elapsed < self.config.cooldown_seconds:
                    logger.debug(f"Rate limiting alert: {key} (cooldown)")
                    return True

            # Check hourly limit
            hour_key = now.strftime("%Y%m%d%H")
            if self._alert_counts.get(hour_key, 0) >= self.config.max_alerts_per_hour:
                logger.debug(f"Rate limiting alert: {key} (hourly limit)")
                return True

            # Update tracking
            self._alert_times[key] = now
            self._alert_counts[hour_key] = self._alert_counts.get(hour_key, 0) + 1

            return False

    def send_alert(
        self,
        level: AlertLevel,
        title: str,
        message: str,
        error: Exception | None = None,
        context: dict[str, Any] | None = None,
        force: bool = False,
    ) -> Alert | None:
        """
        Send an alert through all configured channels.

        Args:
            level: Alert severity level
            title: Alert title
            message: Alert message
            error: Optional exception that caused the alert
            context: Optional additional context
            force: Skip rate limiting if True

        Returns:
            Alert object if sent, None if rate limited or below threshold
        """
        # Check minimum level
        levels = list(AlertLevel)
        if levels.index(level) < levels.index(self.config.min_level):
            return None

        # Create alert
        alert = Alert(
            id=self._generate_alert_id(),
            level=level,
            title=title,
            message=message,
            error=str(error) if error else None,
            context=context or {},
        )

        # Check rate limiting
        if not force and self._should_rate_limit(alert):
            return None

        # Send through all channels
        for channel in self._channels:
            try:
                if channel.send(alert):
                    alert.sent_to.append(channel.name)
            except Exception as e:
                logger.error(f"Channel {channel.name} failed: {e}")

        return alert

    def send_critical_alert(
        self,
        title: str,
        message: str,
        error: Exception | None = None,
        context: dict[str, Any] | None = None,
    ) -> Alert | None:
        """
        Send a CRITICAL (fire alarm) level alert.

        Critical alerts bypass rate limiting and are always sent.
        """
        return self.send_alert(
            level=AlertLevel.CRITICAL,
            title=title,
            message=message,
            error=error,
            context=context,
            force=True,  # Always send critical alerts
        )

    def get_recent_alerts(self, limit: int = 20) -> list[Alert]:
        """Get recent alerts from the log file."""
        try:
            if not self.config.alert_log_path.exists():
                return []

            data = json.loads(self.config.alert_log_path.read_text())
            alerts = [Alert.from_dict(d) for d in data[-limit:]]
            return list(reversed(alerts))  # Newest first

        except Exception as e:
            logger.error(f"Failed to read alerts: {e}")
            return []

    def acknowledge_alert(self, alert_id: str) -> bool:
        """Mark an alert as acknowledged."""
        try:
            if not self.config.alert_log_path.exists():
                return False

            data = json.loads(self.config.alert_log_path.read_text())
            for alert_data in data:
                if alert_data.get("id") == alert_id:
                    alert_data["acknowledged"] = True
                    self.config.alert_log_path.write_text(json.dumps(data, indent=2))
                    return True

            return False

        except Exception as e:
            logger.error(f"Failed to acknowledge alert: {e}")
            return False

    def get_unacknowledged_count(self) -> int:
        """Get count of unacknowledged alerts."""
        alerts = self.get_recent_alerts(limit=100)
        return sum(1 for a in alerts if not a.acknowledged)


# =============================================================================
# GLOBAL INSTANCE AND CONVENIENCE FUNCTIONS
# =============================================================================

_alert_manager: AlertManager | None = None


def get_alert_manager(
    project_path: Path | None = None,
    config: AlertConfig | None = None,
) -> AlertManager:
    """Get the global AlertManager instance."""
    global _alert_manager

    if _alert_manager is None:
        _alert_manager = AlertManager(project_path=project_path, config=config)

    return _alert_manager


def send_backup_alert(
    level: AlertLevel,
    title: str,
    message: str,
    error: Exception | None = None,
    context: dict[str, Any] | None = None,
    project_path: Path | None = None,
) -> Alert | None:
    """
    Send a backup alert (convenience function).

    This is the primary function to call when a backup operation fails.

    Args:
        level: Alert severity level
        title: Alert title
        message: Alert message
        error: Optional exception that caused the alert
        context: Optional additional context
        project_path: Optional project path

    Returns:
        Alert object if sent, None otherwise

    Examples:
        # Warning level
        send_backup_alert(
            level=AlertLevel.WARNING,
            title="Backup Skipped",
            message="No changes detected, backup skipped",
        )

        # Critical level (fire alarm)
        send_backup_alert(
            level=AlertLevel.CRITICAL,
            title="Backup System Failure",
            message="Scheduled backup failed! Disk may be full.",
            error=exception,
            context={"backup_type": "scheduled", "disk_free": "0 bytes"},
        )
    """
    manager = get_alert_manager(project_path=project_path)
    return manager.send_alert(
        level=level,
        title=title,
        message=message,
        error=error,
        context=context,
    )


def send_backup_failure_alert(
    message: str,
    error: Exception | None = None,
    context: dict[str, Any] | None = None,
    project_path: Path | None = None,
) -> Alert | None:
    """
    Send a CRITICAL backup failure alert (fire alarm).

    Use this when a backup operation completely fails.
    This always sends, bypassing rate limits.
    """
    manager = get_alert_manager(project_path=project_path)
    return manager.send_critical_alert(
        title="BACKUP FAILURE",
        message=message,
        error=error,
        context=context,
    )

"""
Fastband comprehensive logging system.

Provides configurable logging with:
- Console and file handlers
- Log rotation (max 5 files, 10MB each)
- Structured JSON logging option
- Debug mode with verbose output
- Integration with FastbandConfig
"""

import json
import logging
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

# Log level mapping
LOG_LEVELS = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "error": logging.ERROR,
    "critical": logging.CRITICAL,
}


@dataclass
class LoggingConfig:
    """Configuration for the Fastband logging system."""

    # Log level (debug, info, warning, error, critical)
    level: str = "info"

    # Enable console logging
    console_enabled: bool = True

    # Enable file logging
    file_enabled: bool = True

    # Log directory (relative to project root or absolute)
    log_dir: str = ".fastband/logs"

    # Log filename
    log_filename: str = "fastband.log"

    # Max size per log file in bytes (default: 10MB)
    max_file_size: int = 10 * 1024 * 1024

    # Number of backup files to keep
    backup_count: int = 5

    # Use structured JSON logging
    json_format: bool = False

    # Debug mode (overrides level to debug, adds verbose output)
    debug_mode: bool = False

    # Include timestamp in console output
    console_timestamp: bool = True

    # Include module name in log output
    include_module: bool = True

    @classmethod
    def from_env(cls) -> "LoggingConfig":
        """Create logging config from environment variables."""
        config = cls()

        # FASTBAND_LOG_LEVEL
        if level := os.environ.get("FASTBAND_LOG_LEVEL"):
            config.level = level.lower()

        # FASTBAND_DEBUG (enables debug mode)
        if os.environ.get("FASTBAND_DEBUG", "").lower() in ("1", "true", "yes"):
            config.debug_mode = True

        # FASTBAND_LOG_DIR
        if log_dir := os.environ.get("FASTBAND_LOG_DIR"):
            config.log_dir = log_dir

        # FASTBAND_LOG_JSON (enables JSON logging)
        if os.environ.get("FASTBAND_LOG_JSON", "").lower() in ("1", "true", "yes"):
            config.json_format = True

        # FASTBAND_LOG_CONSOLE (disable console logging)
        if os.environ.get("FASTBAND_LOG_CONSOLE", "").lower() in ("0", "false", "no"):
            config.console_enabled = False

        # FASTBAND_LOG_FILE (disable file logging)
        if os.environ.get("FASTBAND_LOG_FILE", "").lower() in ("0", "false", "no"):
            config.file_enabled = False

        return config

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LoggingConfig":
        """Create logging config from dictionary."""
        config = cls()

        if "level" in data:
            config.level = data["level"]
        if "console_enabled" in data:
            config.console_enabled = data["console_enabled"]
        if "file_enabled" in data:
            config.file_enabled = data["file_enabled"]
        if "log_dir" in data:
            config.log_dir = data["log_dir"]
        if "log_filename" in data:
            config.log_filename = data["log_filename"]
        if "max_file_size" in data:
            config.max_file_size = data["max_file_size"]
        if "backup_count" in data:
            config.backup_count = data["backup_count"]
        if "json_format" in data:
            config.json_format = data["json_format"]
        if "debug_mode" in data:
            config.debug_mode = data["debug_mode"]
        if "console_timestamp" in data:
            config.console_timestamp = data["console_timestamp"]
        if "include_module" in data:
            config.include_module = data["include_module"]

        return config

    def to_dict(self) -> dict[str, Any]:
        """Convert config to dictionary."""
        return {
            "level": self.level,
            "console_enabled": self.console_enabled,
            "file_enabled": self.file_enabled,
            "log_dir": self.log_dir,
            "log_filename": self.log_filename,
            "max_file_size": self.max_file_size,
            "backup_count": self.backup_count,
            "json_format": self.json_format,
            "debug_mode": self.debug_mode,
            "console_timestamp": self.console_timestamp,
            "include_module": self.include_module,
        }

    @property
    def effective_level(self) -> int:
        """Get the effective log level (considers debug mode)."""
        if self.debug_mode:
            return logging.DEBUG
        return LOG_LEVELS.get(self.level.lower(), logging.INFO)


class JsonFormatter(logging.Formatter):
    """
    Formatter that outputs log records as JSON.

    Useful for log aggregation systems and structured logging.
    """

    def __init__(self, include_module: bool = True):
        super().__init__()
        self.include_module = include_module

    def format(self, record: logging.LogRecord) -> str:
        """Format the log record as JSON."""
        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
        }

        if self.include_module:
            log_data["module"] = record.module
            log_data["function"] = record.funcName
            log_data["line"] = record.lineno

        # Include exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Include any extra fields
        if hasattr(record, "extra_data"):
            log_data["extra"] = record.extra_data

        return json.dumps(log_data)


class ColoredFormatter(logging.Formatter):
    """
    Formatter that adds colors to console output.

    Only applies colors when outputting to a TTY.
    """

    # ANSI color codes
    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"
    BOLD = "\033[1m"

    def __init__(
        self,
        fmt: str,
        datefmt: str | None = None,
        use_colors: bool = True,
    ):
        super().__init__(fmt, datefmt)
        self.use_colors = use_colors and sys.stdout.isatty()

    def format(self, record: logging.LogRecord) -> str:
        """Format the log record with optional colors."""
        if self.use_colors:
            color = self.COLORS.get(record.levelname, "")
            record.levelname = f"{color}{self.BOLD}{record.levelname}{self.RESET}"
            record.msg = f"{color}{record.msg}{self.RESET}"

        return super().format(record)


class FastbandLogger:
    """
    Central logging manager for Fastband.

    Provides:
    - Dual console and file logging
    - Automatic log rotation
    - Structured JSON logging option
    - Debug mode with verbose output
    """

    LOGGER_NAME = "fastband"

    def __init__(
        self,
        config: LoggingConfig | None = None,
        project_path: Path | None = None,
    ):
        """
        Initialize the logging system.

        Args:
            config: Logging configuration. If None, loads from environment.
            project_path: Project root path. Used to resolve relative log paths.
        """
        self.config = config or LoggingConfig.from_env()
        self.project_path = project_path or Path.cwd()
        self._logger: logging.Logger | None = None
        self._initialized = False

    @property
    def log_path(self) -> Path:
        """Get the full path to the log file."""
        log_dir = Path(self.config.log_dir)
        if not log_dir.is_absolute():
            log_dir = self.project_path / log_dir
        return log_dir / self.config.log_filename

    def setup(self) -> logging.Logger:
        """
        Set up the logging system.

        Returns:
            The configured logger instance.
        """
        if self._initialized:
            return self._logger

        # Create or get the logger
        self._logger = logging.getLogger(self.LOGGER_NAME)
        self._logger.setLevel(self.config.effective_level)

        # Remove any existing handlers
        self._logger.handlers.clear()

        # Add console handler
        if self.config.console_enabled:
            self._add_console_handler()

        # Add file handler
        if self.config.file_enabled:
            self._add_file_handler()

        # Prevent propagation to root logger
        self._logger.propagate = False

        self._initialized = True

        # Log initialization
        if self.config.debug_mode:
            self._logger.debug(
                f"Fastband logging initialized - level: {self.config.level}, "
                f"debug_mode: {self.config.debug_mode}, "
                f"log_path: {self.log_path}"
            )

        return self._logger

    def _add_console_handler(self) -> None:
        """Add console handler to the logger."""
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(self.config.effective_level)

        if self.config.json_format:
            handler.setFormatter(JsonFormatter(include_module=self.config.include_module))
        else:
            # Build format string
            fmt_parts = []
            if self.config.console_timestamp:
                fmt_parts.append("%(asctime)s")
            fmt_parts.append("[%(levelname)s]")
            if self.config.include_module and self.config.debug_mode:
                fmt_parts.append("%(name)s.%(module)s:%(lineno)d")
            fmt_parts.append("%(message)s")

            fmt = " ".join(fmt_parts)
            handler.setFormatter(ColoredFormatter(fmt, datefmt="%Y-%m-%d %H:%M:%S"))

        self._logger.addHandler(handler)

    def _add_file_handler(self) -> None:
        """Add rotating file handler to the logger."""
        # Ensure log directory exists
        log_dir = self.log_path.parent
        log_dir.mkdir(parents=True, exist_ok=True)

        handler = RotatingFileHandler(
            filename=str(self.log_path),
            maxBytes=self.config.max_file_size,
            backupCount=self.config.backup_count,
            encoding="utf-8",
        )
        handler.setLevel(self.config.effective_level)

        if self.config.json_format:
            handler.setFormatter(JsonFormatter(include_module=self.config.include_module))
        else:
            # File logs always include full details
            fmt = "%(asctime)s [%(levelname)s] %(name)s.%(module)s:%(lineno)d - %(message)s"
            handler.setFormatter(logging.Formatter(fmt, datefmt="%Y-%m-%d %H:%M:%S"))

        self._logger.addHandler(handler)

    def get_logger(self, name: str | None = None) -> logging.Logger:
        """
        Get a logger instance.

        Args:
            name: Optional child logger name. If provided, creates a child logger.

        Returns:
            Logger instance.
        """
        if not self._initialized:
            self.setup()

        if name:
            return self._logger.getChild(name)
        return self._logger

    def set_level(self, level: str | int) -> None:
        """
        Change the log level dynamically.

        Args:
            level: New log level (string name or logging constant).
        """
        if isinstance(level, str):
            level = LOG_LEVELS.get(level.lower(), logging.INFO)

        if self._logger:
            self._logger.setLevel(level)
            for handler in self._logger.handlers:
                handler.setLevel(level)

    def enable_debug(self) -> None:
        """Enable debug mode."""
        self.config.debug_mode = True
        self.set_level(logging.DEBUG)

    def disable_debug(self) -> None:
        """Disable debug mode."""
        self.config.debug_mode = False
        self.set_level(self.config.level)


# Global logger instance
_logger_instance: FastbandLogger | None = None


def setup_logging(
    config: LoggingConfig | None = None,
    project_path: Path | None = None,
) -> logging.Logger:
    """
    Set up the Fastband logging system.

    This is the main entry point for initializing logging.
    Should be called once at application startup.

    Args:
        config: Optional logging configuration.
        project_path: Optional project root path.

    Returns:
        The configured root logger.
    """
    global _logger_instance

    _logger_instance = FastbandLogger(config=config, project_path=project_path)
    return _logger_instance.setup()


def get_logger(name: str | None = None) -> logging.Logger:
    """
    Get a logger instance.

    If logging hasn't been set up, sets up with defaults.

    Args:
        name: Optional child logger name.

    Returns:
        Logger instance.
    """
    global _logger_instance

    if _logger_instance is None:
        setup_logging()

    return _logger_instance.get_logger(name)


def set_log_level(level: str | int) -> None:
    """
    Set the global log level.

    Args:
        level: New log level (string name or logging constant).
    """
    global _logger_instance

    if _logger_instance is None:
        setup_logging()

    _logger_instance.set_level(level)


def enable_debug_mode() -> None:
    """Enable debug mode globally."""
    global _logger_instance

    if _logger_instance is None:
        setup_logging()

    _logger_instance.enable_debug()


def disable_debug_mode() -> None:
    """Disable debug mode globally."""
    global _logger_instance

    if _logger_instance is None:
        setup_logging()

    _logger_instance.disable_debug()


def reset_logging() -> None:
    """
    Reset the logging system.

    Useful for testing or reconfiguring logging.
    """
    global _logger_instance

    if _logger_instance and _logger_instance._logger:
        _logger_instance._logger.handlers.clear()

    _logger_instance = None


# Convenience functions for direct logging
def debug(msg: str, *args, **kwargs) -> None:
    """Log a debug message."""
    get_logger().debug(msg, *args, **kwargs)


def info(msg: str, *args, **kwargs) -> None:
    """Log an info message."""
    get_logger().info(msg, *args, **kwargs)


def warning(msg: str, *args, **kwargs) -> None:
    """Log a warning message."""
    get_logger().warning(msg, *args, **kwargs)


def error(msg: str, *args, **kwargs) -> None:
    """Log an error message."""
    get_logger().error(msg, *args, **kwargs)


def critical(msg: str, *args, **kwargs) -> None:
    """Log a critical message."""
    get_logger().critical(msg, *args, **kwargs)


def exception(msg: str, *args, **kwargs) -> None:
    """Log an exception with traceback."""
    get_logger().exception(msg, *args, **kwargs)

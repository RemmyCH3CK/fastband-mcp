"""Fastband core engine components."""

from fastband.core.config import FastbandConfig, get_config
from fastband.core.engine import FastbandEngine, create_engine, run_server
from fastband.core.detection import (
    ProjectDetector,
    ProjectInfo,
    DetectedFramework,
    DetectedLanguage,
    Language,
    ProjectType,
    Framework,
    PackageManager,
    BuildTool,
    detect_project,
)
from fastband.core.logging import (
    LoggingConfig,
    FastbandLogger,
    JsonFormatter,
    ColoredFormatter,
    setup_logging,
    get_logger,
    set_log_level,
    enable_debug_mode,
    disable_debug_mode,
    reset_logging,
    debug,
    info,
    warning,
    error,
    critical,
    exception,
    LOG_LEVELS,
)

__all__ = [
    # Config
    "FastbandConfig",
    "get_config",
    # Engine
    "FastbandEngine",
    "create_engine",
    "run_server",
    # Detection
    "ProjectDetector",
    "ProjectInfo",
    "DetectedFramework",
    "DetectedLanguage",
    "Language",
    "ProjectType",
    "Framework",
    "PackageManager",
    "BuildTool",
    "detect_project",
    # Logging
    "LoggingConfig",
    "FastbandLogger",
    "JsonFormatter",
    "ColoredFormatter",
    "setup_logging",
    "get_logger",
    "set_log_level",
    "enable_debug_mode",
    "disable_debug_mode",
    "reset_logging",
    "debug",
    "info",
    "warning",
    "error",
    "critical",
    "exception",
    "LOG_LEVELS",
]

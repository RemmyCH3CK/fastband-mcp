"""Fastband core engine components."""

from fastband.core.config import FastbandConfig, get_config
from fastband.core.detection import (
    BuildTool,
    DetectedFramework,
    DetectedLanguage,
    Framework,
    Language,
    PackageManager,
    ProjectDetector,
    ProjectInfo,
    ProjectType,
    detect_project,
)
from fastband.core.engine import FastbandEngine, create_engine, run_server
from fastband.core.events import (
    EventBus,
    EventData,
    HubEventType,
    get_event_bus,
    reset_event_bus,
)
from fastband.core.logging import (
    LOG_LEVELS,
    ColoredFormatter,
    FastbandLogger,
    JsonFormatter,
    LoggingConfig,
    critical,
    debug,
    disable_debug_mode,
    enable_debug_mode,
    error,
    exception,
    get_logger,
    info,
    reset_logging,
    set_log_level,
    setup_logging,
    warning,
)
from fastband.core.plugins import (
    Plugin,
    PluginManager,
    PluginMetadata,
    get_plugin_manager,
    reset_plugin_manager,
)
from fastband.core.security import (
    # Input sanitization
    InputSanitizer,
    # Path security
    PathSecurityError,
    PathValidator,
    # SQL security
    SQLSecurityError,
    build_parameterized_query,
    generate_api_token,
    # Secrets and keys
    generate_secret_key,
    # Environment security
    get_env_or_default,
    is_secret_key_secure,
    mask_secret,
    sanitize_input,
    secure_config_dict,
    validate_path,
    validate_sql_identifier,
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
    # Security
    "PathSecurityError",
    "PathValidator",
    "validate_path",
    "InputSanitizer",
    "sanitize_input",
    "SQLSecurityError",
    "validate_sql_identifier",
    "build_parameterized_query",
    "generate_secret_key",
    "generate_api_token",
    "mask_secret",
    "is_secret_key_secure",
    "get_env_or_default",
    "secure_config_dict",
    # Events
    "EventBus",
    "EventData",
    "HubEventType",
    "get_event_bus",
    "reset_event_bus",
    # Plugins
    "Plugin",
    "PluginMetadata",
    "PluginManager",
    "get_plugin_manager",
    "reset_plugin_manager",
]

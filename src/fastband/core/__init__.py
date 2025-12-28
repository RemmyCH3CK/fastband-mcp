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
from fastband.core.security import (
    # Path security
    PathSecurityError,
    PathValidator,
    validate_path,
    # Input sanitization
    InputSanitizer,
    sanitize_input,
    # SQL security
    SQLSecurityError,
    validate_sql_identifier,
    build_parameterized_query,
    # Secrets and keys
    generate_secret_key,
    generate_api_token,
    mask_secret,
    is_secret_key_secure,
    # Environment security
    get_env_or_default,
    secure_config_dict,
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
]

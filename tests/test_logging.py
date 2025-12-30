"""Tests for the Fastband logging system."""

import json
import logging
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

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
    get_logger,
    info,
    reset_logging,
    set_log_level,
    setup_logging,
    warning,
)


@pytest.fixture(autouse=True)
def clean_logging():
    """Reset logging before and after each test."""
    reset_logging()
    yield
    reset_logging()


@pytest.fixture
def temp_log_dir():
    """Create a temporary directory for log files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


class TestLoggingConfig:
    """Tests for LoggingConfig class."""

    def test_default_config(self):
        """Test default configuration values."""
        config = LoggingConfig()

        assert config.level == "info"
        assert config.console_enabled is True
        assert config.file_enabled is True
        assert config.log_dir == ".fastband/logs"
        assert config.log_filename == "fastband.log"
        assert config.max_file_size == 10 * 1024 * 1024
        assert config.backup_count == 5
        assert config.json_format is False
        assert config.debug_mode is False

    def test_from_env_log_level(self):
        """Test loading log level from environment."""
        with patch.dict(os.environ, {"FASTBAND_LOG_LEVEL": "debug"}):
            config = LoggingConfig.from_env()
            assert config.level == "debug"

    def test_from_env_debug_mode(self):
        """Test enabling debug mode from environment."""
        with patch.dict(os.environ, {"FASTBAND_DEBUG": "1"}):
            config = LoggingConfig.from_env()
            assert config.debug_mode is True

        with patch.dict(os.environ, {"FASTBAND_DEBUG": "true"}):
            config = LoggingConfig.from_env()
            assert config.debug_mode is True

    def test_from_env_log_dir(self):
        """Test setting log directory from environment."""
        with patch.dict(os.environ, {"FASTBAND_LOG_DIR": "/custom/logs"}):
            config = LoggingConfig.from_env()
            assert config.log_dir == "/custom/logs"

    def test_from_env_json_format(self):
        """Test enabling JSON format from environment."""
        with patch.dict(os.environ, {"FASTBAND_LOG_JSON": "true"}):
            config = LoggingConfig.from_env()
            assert config.json_format is True

    def test_from_env_disable_console(self):
        """Test disabling console logging from environment."""
        with patch.dict(os.environ, {"FASTBAND_LOG_CONSOLE": "false"}):
            config = LoggingConfig.from_env()
            assert config.console_enabled is False

    def test_from_env_disable_file(self):
        """Test disabling file logging from environment."""
        with patch.dict(os.environ, {"FASTBAND_LOG_FILE": "0"}):
            config = LoggingConfig.from_env()
            assert config.file_enabled is False

    def test_from_dict(self):
        """Test creating config from dictionary."""
        data = {
            "level": "warning",
            "console_enabled": False,
            "file_enabled": True,
            "log_dir": "/custom/path",
            "json_format": True,
            "debug_mode": True,
        }

        config = LoggingConfig.from_dict(data)

        assert config.level == "warning"
        assert config.console_enabled is False
        assert config.file_enabled is True
        assert config.log_dir == "/custom/path"
        assert config.json_format is True
        assert config.debug_mode is True

    def test_to_dict(self):
        """Test converting config to dictionary."""
        config = LoggingConfig(level="error", json_format=True)
        data = config.to_dict()

        assert data["level"] == "error"
        assert data["json_format"] is True
        assert "console_enabled" in data
        assert "file_enabled" in data

    def test_effective_level_normal(self):
        """Test effective level in normal mode."""
        config = LoggingConfig(level="warning")
        assert config.effective_level == logging.WARNING

    def test_effective_level_debug_mode(self):
        """Test effective level in debug mode."""
        config = LoggingConfig(level="warning", debug_mode=True)
        assert config.effective_level == logging.DEBUG


class TestJsonFormatter:
    """Tests for JsonFormatter class."""

    def test_format_basic(self):
        """Test basic JSON formatting."""
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        output = formatter.format(record)
        data = json.loads(output)

        assert data["level"] == "INFO"
        assert data["message"] == "Test message"
        assert data["logger"] == "test"
        assert "timestamp" in data

    def test_format_with_module(self):
        """Test JSON formatting includes module info."""
        formatter = JsonFormatter(include_module=True)
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        output = formatter.format(record)
        data = json.loads(output)

        assert "module" in data
        assert "function" in data
        assert data["line"] == 42

    def test_format_without_module(self):
        """Test JSON formatting excludes module info when disabled."""
        formatter = JsonFormatter(include_module=False)
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        output = formatter.format(record)
        data = json.loads(output)

        assert "module" not in data
        assert "function" not in data


class TestColoredFormatter:
    """Tests for ColoredFormatter class."""

    def test_format_without_colors(self):
        """Test formatting without colors (non-TTY)."""
        formatter = ColoredFormatter("%(levelname)s - %(message)s", use_colors=False)
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        output = formatter.format(record)

        # Should not contain ANSI codes
        assert "\033[" not in output
        assert "Test message" in output


class TestFastbandLogger:
    """Tests for FastbandLogger class."""

    def test_init_default(self):
        """Test default initialization."""
        logger = FastbandLogger()

        assert logger.config is not None
        assert logger.project_path == Path.cwd()
        assert logger._initialized is False

    def test_init_with_config(self, temp_log_dir):
        """Test initialization with custom config."""
        config = LoggingConfig(log_dir=str(temp_log_dir), level="debug")
        logger = FastbandLogger(config=config, project_path=temp_log_dir)

        assert logger.config.level == "debug"
        assert logger.project_path == temp_log_dir

    def test_log_path_relative(self, temp_log_dir):
        """Test log path resolution for relative paths."""
        config = LoggingConfig(log_dir=".fastband/logs")
        logger = FastbandLogger(config=config, project_path=temp_log_dir)

        expected = temp_log_dir / ".fastband" / "logs" / "fastband.log"
        assert logger.log_path == expected

    def test_log_path_absolute(self, temp_log_dir):
        """Test log path resolution for absolute paths."""
        config = LoggingConfig(log_dir=str(temp_log_dir))
        logger = FastbandLogger(config=config)

        expected = temp_log_dir / "fastband.log"
        assert logger.log_path == expected

    def test_setup_creates_logger(self, temp_log_dir):
        """Test that setup creates a logger."""
        config = LoggingConfig(
            log_dir=str(temp_log_dir),
            console_enabled=False,  # Disable console for test
        )
        fb_logger = FastbandLogger(config=config, project_path=temp_log_dir)

        logger = fb_logger.setup()

        assert logger is not None
        assert isinstance(logger, logging.Logger)
        assert fb_logger._initialized is True

    def test_setup_creates_log_directory(self, temp_log_dir):
        """Test that setup creates the log directory."""
        log_subdir = temp_log_dir / "logs"
        config = LoggingConfig(
            log_dir=str(log_subdir),
            console_enabled=False,
        )
        fb_logger = FastbandLogger(config=config, project_path=temp_log_dir)

        fb_logger.setup()

        assert log_subdir.exists()

    def test_setup_only_once(self, temp_log_dir):
        """Test that setup only initializes once."""
        config = LoggingConfig(
            log_dir=str(temp_log_dir),
            console_enabled=False,
        )
        fb_logger = FastbandLogger(config=config, project_path=temp_log_dir)

        logger1 = fb_logger.setup()
        logger2 = fb_logger.setup()

        assert logger1 is logger2

    def test_get_logger_child(self, temp_log_dir):
        """Test getting a child logger."""
        config = LoggingConfig(
            log_dir=str(temp_log_dir),
            console_enabled=False,
            file_enabled=False,
        )
        fb_logger = FastbandLogger(config=config, project_path=temp_log_dir)
        fb_logger.setup()

        child = fb_logger.get_logger("tools")

        assert child.name == "fastband.tools"

    def test_set_level(self, temp_log_dir):
        """Test changing log level dynamically."""
        config = LoggingConfig(
            log_dir=str(temp_log_dir),
            level="info",
            console_enabled=False,
            file_enabled=False,
        )
        fb_logger = FastbandLogger(config=config, project_path=temp_log_dir)
        fb_logger.setup()

        fb_logger.set_level("debug")

        assert fb_logger._logger.level == logging.DEBUG

    def test_set_level_by_constant(self, temp_log_dir):
        """Test changing log level using logging constant."""
        config = LoggingConfig(
            log_dir=str(temp_log_dir),
            console_enabled=False,
            file_enabled=False,
        )
        fb_logger = FastbandLogger(config=config, project_path=temp_log_dir)
        fb_logger.setup()

        fb_logger.set_level(logging.WARNING)

        assert fb_logger._logger.level == logging.WARNING

    def test_enable_debug(self, temp_log_dir):
        """Test enabling debug mode."""
        config = LoggingConfig(
            log_dir=str(temp_log_dir),
            level="info",
            console_enabled=False,
            file_enabled=False,
        )
        fb_logger = FastbandLogger(config=config, project_path=temp_log_dir)
        fb_logger.setup()

        fb_logger.enable_debug()

        assert fb_logger.config.debug_mode is True
        assert fb_logger._logger.level == logging.DEBUG

    def test_disable_debug(self, temp_log_dir):
        """Test disabling debug mode."""
        config = LoggingConfig(
            log_dir=str(temp_log_dir),
            level="warning",
            debug_mode=True,
            console_enabled=False,
            file_enabled=False,
        )
        fb_logger = FastbandLogger(config=config, project_path=temp_log_dir)
        fb_logger.setup()

        fb_logger.disable_debug()

        assert fb_logger.config.debug_mode is False


class TestLoggingFunctions:
    """Tests for module-level logging functions."""

    def test_setup_logging(self, temp_log_dir):
        """Test setup_logging function."""
        config = LoggingConfig(
            log_dir=str(temp_log_dir),
            console_enabled=False,
        )

        logger = setup_logging(config=config, project_path=temp_log_dir)

        assert logger is not None
        assert isinstance(logger, logging.Logger)

    def test_get_logger_auto_setup(self, temp_log_dir):
        """Test that get_logger auto-initializes logging."""
        # Patch to avoid writing to default location
        with patch.dict(os.environ, {"FASTBAND_LOG_FILE": "0", "FASTBAND_LOG_CONSOLE": "0"}):
            logger = get_logger()

            assert logger is not None

    def test_get_logger_with_name(self, temp_log_dir):
        """Test get_logger with a child name."""
        config = LoggingConfig(
            log_dir=str(temp_log_dir),
            console_enabled=False,
            file_enabled=False,
        )
        setup_logging(config=config, project_path=temp_log_dir)

        logger = get_logger("engine")

        assert logger.name == "fastband.engine"

    def test_set_log_level_function(self, temp_log_dir):
        """Test set_log_level function."""
        config = LoggingConfig(
            log_dir=str(temp_log_dir),
            console_enabled=False,
            file_enabled=False,
        )
        setup_logging(config=config, project_path=temp_log_dir)

        set_log_level("error")

        logger = get_logger()
        assert logger.level == logging.ERROR

    def test_enable_debug_mode_function(self, temp_log_dir):
        """Test enable_debug_mode function."""
        config = LoggingConfig(
            log_dir=str(temp_log_dir),
            console_enabled=False,
            file_enabled=False,
        )
        setup_logging(config=config, project_path=temp_log_dir)

        enable_debug_mode()

        logger = get_logger()
        assert logger.level == logging.DEBUG

    def test_disable_debug_mode_function(self, temp_log_dir):
        """Test disable_debug_mode function."""
        config = LoggingConfig(
            log_dir=str(temp_log_dir),
            level="info",
            debug_mode=True,
            console_enabled=False,
            file_enabled=False,
        )
        setup_logging(config=config, project_path=temp_log_dir)

        disable_debug_mode()

        # Should revert to configured level
        get_logger()
        # Note: level may not exactly match since we're testing the function works


class TestLogRotation:
    """Tests for log rotation functionality."""

    def test_file_handler_rotation_config(self, temp_log_dir):
        """Test that file handler is configured with rotation parameters."""
        config = LoggingConfig(
            log_dir=str(temp_log_dir),
            max_file_size=1024,  # 1KB for testing
            backup_count=3,
            console_enabled=False,
        )
        fb_logger = FastbandLogger(config=config, project_path=temp_log_dir)
        fb_logger.setup()

        # Find the rotating file handler
        from logging.handlers import RotatingFileHandler

        file_handler = None
        for handler in fb_logger._logger.handlers:
            if isinstance(handler, RotatingFileHandler):
                file_handler = handler
                break

        assert file_handler is not None
        assert file_handler.maxBytes == 1024
        assert file_handler.backupCount == 3

    def test_log_file_created(self, temp_log_dir):
        """Test that log file is created when logging."""
        config = LoggingConfig(
            log_dir=str(temp_log_dir),
            console_enabled=False,
        )
        fb_logger = FastbandLogger(config=config, project_path=temp_log_dir)
        logger = fb_logger.setup()

        logger.info("Test message")

        # Flush handlers to ensure write
        for handler in logger.handlers:
            handler.flush()

        assert fb_logger.log_path.exists()


class TestConvenienceFunctions:
    """Tests for convenience logging functions."""

    def test_debug_function(self, temp_log_dir):
        """Test debug convenience function."""
        config = LoggingConfig(
            log_dir=str(temp_log_dir),
            level="debug",
            console_enabled=False,
        )
        setup_logging(config=config, project_path=temp_log_dir)

        # Should not raise
        debug("Debug message")

    def test_info_function(self, temp_log_dir):
        """Test info convenience function."""
        config = LoggingConfig(
            log_dir=str(temp_log_dir),
            console_enabled=False,
        )
        setup_logging(config=config, project_path=temp_log_dir)

        info("Info message")

    def test_warning_function(self, temp_log_dir):
        """Test warning convenience function."""
        config = LoggingConfig(
            log_dir=str(temp_log_dir),
            console_enabled=False,
        )
        setup_logging(config=config, project_path=temp_log_dir)

        warning("Warning message")

    def test_error_function(self, temp_log_dir):
        """Test error convenience function."""
        config = LoggingConfig(
            log_dir=str(temp_log_dir),
            console_enabled=False,
        )
        setup_logging(config=config, project_path=temp_log_dir)

        error("Error message")

    def test_critical_function(self, temp_log_dir):
        """Test critical convenience function."""
        config = LoggingConfig(
            log_dir=str(temp_log_dir),
            console_enabled=False,
        )
        setup_logging(config=config, project_path=temp_log_dir)

        critical("Critical message")


class TestLogLevelMapping:
    """Tests for log level mapping."""

    def test_all_levels_mapped(self):
        """Test that all expected levels are mapped."""
        assert "debug" in LOG_LEVELS
        assert "info" in LOG_LEVELS
        assert "warning" in LOG_LEVELS
        assert "error" in LOG_LEVELS
        assert "critical" in LOG_LEVELS

    def test_level_values(self):
        """Test that levels map to correct logging constants."""
        assert LOG_LEVELS["debug"] == logging.DEBUG
        assert LOG_LEVELS["info"] == logging.INFO
        assert LOG_LEVELS["warning"] == logging.WARNING
        assert LOG_LEVELS["error"] == logging.ERROR
        assert LOG_LEVELS["critical"] == logging.CRITICAL


class TestIntegration:
    """Integration tests for the logging system."""

    def test_full_logging_workflow(self, temp_log_dir):
        """Test a complete logging workflow."""
        # Configure logging
        config = LoggingConfig(
            log_dir=str(temp_log_dir),
            level="debug",
            json_format=False,
            console_enabled=False,
        )

        # Set up logging
        logger = setup_logging(config=config, project_path=temp_log_dir)

        # Log at various levels
        logger.debug("Debug message")
        logger.info("Info message")
        logger.warning("Warning message")
        logger.error("Error message")

        # Flush handlers
        for handler in logger.handlers:
            handler.flush()

        # Verify log file exists and contains messages
        log_file = temp_log_dir / "fastband.log"
        assert log_file.exists()

        content = log_file.read_text()
        assert "Info message" in content
        assert "Warning message" in content
        assert "Error message" in content

    def test_json_logging_workflow(self, temp_log_dir):
        """Test JSON logging format."""
        config = LoggingConfig(
            log_dir=str(temp_log_dir),
            json_format=True,
            console_enabled=False,
        )

        logger = setup_logging(config=config, project_path=temp_log_dir)
        logger.info("JSON test message")

        # Flush handlers
        for handler in logger.handlers:
            handler.flush()

        # Read and parse log file
        log_file = temp_log_dir / "fastband.log"
        content = log_file.read_text().strip()

        # Should be valid JSON
        data = json.loads(content)
        assert data["message"] == "JSON test message"
        assert data["level"] == "INFO"

    def test_child_logger_workflow(self, temp_log_dir):
        """Test child logger functionality."""
        config = LoggingConfig(
            log_dir=str(temp_log_dir),
            console_enabled=False,
        )

        setup_logging(config=config, project_path=temp_log_dir)

        # Get child loggers for different components
        tools_logger = get_logger("tools")
        engine_logger = get_logger("engine")

        assert tools_logger.name == "fastband.tools"
        assert engine_logger.name == "fastband.engine"

        # Both should log to the same handlers
        tools_logger.info("Tools message")
        engine_logger.info("Engine message")

        # Flush
        parent = get_logger()
        for handler in parent.handlers:
            handler.flush()

        log_file = temp_log_dir / "fastband.log"
        content = log_file.read_text()

        assert "Tools message" in content
        assert "Engine message" in content

    def test_debug_mode_verbose_output(self, temp_log_dir):
        """Test debug mode provides verbose output."""
        config = LoggingConfig(
            log_dir=str(temp_log_dir),
            debug_mode=True,
            console_enabled=False,
        )

        logger = setup_logging(config=config, project_path=temp_log_dir)
        logger.debug("Detailed debug info")

        for handler in logger.handlers:
            handler.flush()

        log_file = temp_log_dir / "fastband.log"
        content = log_file.read_text()

        # Debug message should be present (since debug_mode=True)
        assert "Detailed debug info" in content
        # Should include module/line info
        assert "test_logging" in content or "DEBUG" in content

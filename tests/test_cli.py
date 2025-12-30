"""Tests for Fastband CLI."""

import tempfile
from pathlib import Path

import pytest
from typer.testing import CliRunner

from fastband import __version__
from fastband.cli.main import app

runner = CliRunner()


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def initialized_project(temp_dir):
    """Create an initialized Fastband project."""
    fastband_dir = temp_dir / ".fastband"
    fastband_dir.mkdir()
    (fastband_dir / "config.yaml").write_text("""
fastband:
  version: "1.2025.12"
  ai:
    default_provider: claude
""")
    return temp_dir


# =============================================================================
# VERSION TESTS
# =============================================================================


class TestVersion:
    """Tests for version display."""

    def test_version_flag(self):
        """Test --version flag."""
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert __version__ in result.stdout

    def test_version_short_flag(self):
        """Test -v flag for version."""
        result = runner.invoke(app, ["-v"])
        assert result.exit_code == 0
        assert __version__ in result.stdout


# =============================================================================
# INIT COMMAND TESTS
# =============================================================================


class TestInitCommand:
    """Tests for init command."""

    def test_init_creates_config(self, temp_dir):
        """Test init creates .fastband directory and config."""
        result = runner.invoke(app, ["init", str(temp_dir)])
        assert result.exit_code == 0

        config_file = temp_dir / ".fastband" / "config.yaml"
        assert config_file.exists()

    def test_init_already_initialized(self, initialized_project):
        """Test init fails if already initialized."""
        result = runner.invoke(app, ["init", str(initialized_project)])
        assert result.exit_code == 1
        assert "already initialized" in result.stdout.lower()

    def test_init_force_reinitialize(self, initialized_project):
        """Test init with --force overwrites."""
        result = runner.invoke(app, ["init", str(initialized_project), "--force"])
        assert result.exit_code == 0

    def test_init_skip_detection(self, temp_dir):
        """Test init with --skip-detection."""
        result = runner.invoke(app, ["init", str(temp_dir), "--skip-detection"])
        assert result.exit_code == 0
        # Should not show project detection results
        assert "Detected Project" not in result.stdout


# =============================================================================
# STATUS COMMAND TESTS
# =============================================================================


class TestStatusCommand:
    """Tests for status command."""

    def test_status_not_initialized(self, temp_dir):
        """Test status fails if not initialized."""
        result = runner.invoke(app, ["status", "--path", str(temp_dir)])
        assert result.exit_code == 1
        assert "not initialized" in result.stdout.lower()

    def test_status_shows_config(self, initialized_project):
        """Test status shows configuration."""
        result = runner.invoke(app, ["status", "--path", str(initialized_project)])
        assert result.exit_code == 0
        assert "Configuration" in result.stdout

    def test_status_verbose(self, initialized_project):
        """Test status with --verbose shows more details."""
        result = runner.invoke(app, ["status", "--path", str(initialized_project), "--verbose"])
        assert result.exit_code == 0
        assert "Backup Configuration" in result.stdout


# =============================================================================
# CONFIG COMMAND TESTS
# =============================================================================


class TestConfigCommands:
    """Tests for config subcommands."""

    def test_config_show(self, initialized_project):
        """Test config show displays configuration."""
        result = runner.invoke(app, ["config", "show", "--path", str(initialized_project)])
        assert result.exit_code == 0
        assert "fastband" in result.stdout

    def test_config_show_json(self, initialized_project):
        """Test config show --json outputs JSON."""
        result = runner.invoke(
            app, ["config", "show", "--path", str(initialized_project), "--json"]
        )
        assert result.exit_code == 0
        assert "{" in result.stdout  # JSON format

    def test_config_set(self, initialized_project):
        """Test config set updates value."""
        result = runner.invoke(
            app, ["config", "set", "tools.max_active", "100", "--path", str(initialized_project)]
        )
        assert result.exit_code == 0
        assert "Set" in result.stdout

    def test_config_get(self, initialized_project):
        """Test config get retrieves value."""
        result = runner.invoke(
            app, ["config", "get", "version", "--path", str(initialized_project)]
        )
        assert result.exit_code == 0

    def test_config_get_missing_key(self, initialized_project):
        """Test config get with missing key."""
        result = runner.invoke(
            app, ["config", "get", "nonexistent.key", "--path", str(initialized_project)]
        )
        assert result.exit_code == 1
        assert "not found" in result.stdout.lower()

    def test_config_reset_cancelled(self, initialized_project):
        """Test config reset without confirmation."""
        result = runner.invoke(
            app, ["config", "reset", "--path", str(initialized_project)], input="n\n"
        )
        assert result.exit_code == 0
        assert "Cancelled" in result.stdout

    def test_config_reset_confirmed(self, initialized_project):
        """Test config reset with confirmation."""
        result = runner.invoke(
            app, ["config", "reset", "--path", str(initialized_project), "--yes"]
        )
        assert result.exit_code == 0
        assert "reset" in result.stdout.lower()


# =============================================================================
# HELP TESTS
# =============================================================================


class TestHelp:
    """Tests for help output."""

    def test_main_help(self):
        """Test main help message."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "init" in result.stdout
        assert "status" in result.stdout
        assert "config" in result.stdout

    def test_init_help(self):
        """Test init command help."""
        result = runner.invoke(app, ["init", "--help"])
        assert result.exit_code == 0
        assert "Initialize" in result.stdout

    def test_config_help(self):
        """Test config command help."""
        result = runner.invoke(app, ["config", "--help"])
        assert result.exit_code == 0
        assert "show" in result.stdout
        assert "set" in result.stdout
        assert "get" in result.stdout

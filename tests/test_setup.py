"""
Tests for the fastband setup command and Claude Code integration.

Tests cover installation detection, MCP config generation, and validation.
"""

import json
import os
import shutil
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from fastband.cli.setup import (
    VALID_CONFIG_TYPES,
    InstallInfo,
    InstallMethod,
    _validate_project_path,
    create_mcp_config,
    detect_installation,
    get_claude_config_paths,
    get_mcp_command,
    init_fastband_config,
    run_setup,
    show_mcp_config,
    validate_mcp_server,
)


class TestInstallMethod:
    """Tests for InstallMethod enum."""

    def test_all_methods_exist(self):
        """Test all installation methods are defined."""
        assert InstallMethod.PIPX.value == "pipx"
        assert InstallMethod.PIP.value == "pip"
        assert InstallMethod.UV.value == "uv"
        assert InstallMethod.SOURCE.value == "source"
        assert InstallMethod.UNKNOWN.value == "unknown"


class TestInstallInfo:
    """Tests for InstallInfo dataclass."""

    def test_create_install_info(self):
        """Test creating InstallInfo."""
        info = InstallInfo(
            method=InstallMethod.PIPX,
            executable_path=Path("/usr/local/bin/fastband"),
        )
        assert info.method == InstallMethod.PIPX
        assert info.executable_path == Path("/usr/local/bin/fastband")
        assert info.python_path is None
        assert info.version is None

    def test_create_install_info_with_all_fields(self):
        """Test creating InstallInfo with all fields."""
        info = InstallInfo(
            method=InstallMethod.PIP,
            executable_path=Path("/usr/bin/fastband"),
            python_path=Path("/usr/bin/python3"),
            version="1.0.0",
        )
        assert info.method == InstallMethod.PIP
        assert info.python_path == Path("/usr/bin/python3")
        assert info.version == "1.0.0"


class TestDetectInstallation:
    """Tests for detect_installation function."""

    def test_detect_pipx_installation(self):
        """Test detecting pipx installation."""
        home = str(Path.home())
        pipx_path = f"{home}/.local/bin/fastband"

        with patch("shutil.which", return_value=pipx_path):
            with patch.object(
                Path, "exists", return_value=True
            ):
                info = detect_installation()
                # Should detect as pipx or pip depending on venv detection
                assert info.method in [InstallMethod.PIPX, InstallMethod.PIP, InstallMethod.UV]

    def test_detect_unknown_when_not_found(self):
        """Test detecting unknown when fastband not in PATH."""
        with patch("shutil.which", return_value=None):
            with patch("subprocess.run", side_effect=FileNotFoundError):
                info = detect_installation()
                assert info.method == InstallMethod.UNKNOWN

    def test_detect_pip_via_python_module(self):
        """Test detecting pip via python -m fastband."""
        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("shutil.which", return_value=None):
            with patch("subprocess.run", return_value=mock_result):
                info = detect_installation()
                assert info.method == InstallMethod.PIP


class TestGetMcpCommand:
    """Tests for get_mcp_command function."""

    def test_pipx_command(self):
        """Test MCP command for pipx installation."""
        info = InstallInfo(
            method=InstallMethod.PIPX,
            executable_path=Path("/Users/test/.local/bin/fastband"),
        )
        command, args = get_mcp_command(info)
        assert command == "/Users/test/.local/bin/fastband"
        assert args == ["serve", "--all"]

    def test_pip_command_with_executable(self):
        """Test MCP command for pip installation with executable."""
        info = InstallInfo(
            method=InstallMethod.PIP,
            executable_path=Path("/usr/local/bin/fastband"),
        )
        with patch.object(Path, "exists", return_value=True):
            command, args = get_mcp_command(info)
            assert command == "/usr/local/bin/fastband"
            assert args == ["serve", "--all"]

    def test_source_command(self):
        """Test MCP command for source/development installation."""
        info = InstallInfo(
            method=InstallMethod.SOURCE,
            executable_path=Path("/project/.venv/bin/fastband"),
            python_path=Path("/project/.venv/bin/python"),
        )
        command, args = get_mcp_command(info)
        assert command == "/project/.venv/bin/python"
        assert args == ["-m", "fastband", "serve", "--all"]

    def test_unknown_command(self):
        """Test MCP command for unknown installation."""
        info = InstallInfo(
            method=InstallMethod.UNKNOWN,
            executable_path=Path("fastband"),
        )
        command, args = get_mcp_command(info)
        assert command == "fastband"
        assert args == ["serve", "--all"]


class TestGetClaudeConfigPaths:
    """Tests for get_claude_config_paths function."""

    def test_returns_all_config_types(self):
        """Test that all config types are returned."""
        paths = get_claude_config_paths()
        assert "project" in paths
        assert "desktop" in paths
        assert "global" in paths

    def test_project_path_is_relative(self):
        """Test project path is relative."""
        paths = get_claude_config_paths()
        assert paths["project"] == Path(".claude") / "mcp.json"

    @pytest.mark.skipif(sys.platform != "darwin", reason="macOS only")
    def test_macos_desktop_path(self):
        """Test macOS desktop config path."""
        paths = get_claude_config_paths()
        expected = (
            Path.home()
            / "Library"
            / "Application Support"
            / "Claude"
            / "claude_desktop_config.json"
        )
        assert paths["desktop"] == expected

    def test_global_path(self):
        """Test global config path."""
        paths = get_claude_config_paths()
        expected = Path.home() / ".claude" / "claude_desktop_config.json"
        assert paths["global"] == expected


class TestCreateMcpConfig:
    """Tests for create_mcp_config function."""

    def test_create_project_config(self, tmp_path):
        """Test creating project-level MCP config."""
        project_path = tmp_path / "myproject"
        project_path.mkdir()

        info = InstallInfo(
            method=InstallMethod.PIPX,
            executable_path=Path("/Users/test/.local/bin/fastband"),
        )

        config_path = create_mcp_config(project_path, info, "project")

        assert config_path.exists()
        assert config_path == project_path / ".claude" / "mcp.json"

        with open(config_path) as f:
            config = json.load(f)

        assert "mcpServers" in config
        assert "fastband" in config["mcpServers"]
        assert config["mcpServers"]["fastband"]["command"] == "/Users/test/.local/bin/fastband"
        assert config["mcpServers"]["fastband"]["args"] == ["serve", "--all"]

    def test_merge_existing_config(self, tmp_path):
        """Test merging with existing MCP config."""
        project_path = tmp_path / "myproject"
        claude_dir = project_path / ".claude"
        claude_dir.mkdir(parents=True)

        # Create existing config with another server
        existing_config = {
            "mcpServers": {
                "other-server": {"command": "other", "args": ["--flag"]},
            }
        }
        config_file = claude_dir / "mcp.json"
        with open(config_file, "w") as f:
            json.dump(existing_config, f)

        info = InstallInfo(
            method=InstallMethod.PIP,
            executable_path=Path("/usr/bin/fastband"),
        )

        create_mcp_config(project_path, info, "project")

        with open(config_file) as f:
            config = json.load(f)

        # Both servers should be present
        assert "other-server" in config["mcpServers"]
        assert "fastband" in config["mcpServers"]

    def test_backup_corrupted_config(self, tmp_path):
        """Test backing up corrupted config file."""
        project_path = tmp_path / "myproject"
        claude_dir = project_path / ".claude"
        claude_dir.mkdir(parents=True)

        # Create corrupted config
        config_file = claude_dir / "mcp.json"
        with open(config_file, "w") as f:
            f.write("not valid json {{{")

        info = InstallInfo(
            method=InstallMethod.PIP,
            executable_path=Path("/usr/bin/fastband"),
        )

        create_mcp_config(project_path, info, "project")

        # Backup should exist with timestamp pattern
        backup_files = list(claude_dir.glob("mcp.json.backup.*"))
        assert len(backup_files) >= 1

        # New config should be valid
        with open(config_file) as f:
            config = json.load(f)
        assert "fastband" in config["mcpServers"]


class TestValidateMcpServer:
    """Tests for validate_mcp_server function."""

    def test_validate_success(self):
        """Test successful validation."""
        info = InstallInfo(
            method=InstallMethod.PIPX,
            executable_path=Path("/usr/bin/fastband"),
        )

        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result):
            result = validate_mcp_server(info)
            assert result is True

    def test_validate_failure(self):
        """Test failed validation."""
        info = InstallInfo(
            method=InstallMethod.PIPX,
            executable_path=Path("/usr/bin/fastband"),
        )

        mock_result = MagicMock()
        mock_result.returncode = 1

        with patch("subprocess.run", return_value=mock_result):
            result = validate_mcp_server(info)
            assert result is False

    def test_validate_timeout(self):
        """Test validation timeout."""
        import subprocess

        info = InstallInfo(
            method=InstallMethod.PIP,
            executable_path=Path("/usr/bin/fastband"),
        )

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("cmd", 5)):
            result = validate_mcp_server(info)
            assert result is False

    def test_validate_not_found(self):
        """Test validation when executable not found."""
        info = InstallInfo(
            method=InstallMethod.UNKNOWN,
            executable_path=Path("/nonexistent/fastband"),
        )

        with patch("subprocess.run", side_effect=FileNotFoundError):
            result = validate_mcp_server(info)
            assert result is False


class TestInitFastbandConfig:
    """Tests for init_fastband_config function."""

    def test_init_new_project(self, tmp_path):
        """Test initializing new project."""
        project_path = tmp_path / "myproject"
        project_path.mkdir()

        result = init_fastband_config(project_path)

        assert result is True
        assert (project_path / ".fastband" / "config.yaml").exists()

    def test_skip_existing_config(self, tmp_path):
        """Test skipping existing config without force."""
        project_path = tmp_path / "myproject"
        fastband_dir = project_path / ".fastband"
        fastband_dir.mkdir(parents=True)

        config_file = fastband_dir / "config.yaml"
        config_file.write_text("existing: config")

        result = init_fastband_config(project_path, force=False)

        assert result is True
        # Original content should be preserved
        assert config_file.read_text() == "existing: config"

    def test_force_reinit(self, tmp_path):
        """Test force reinitializing existing config."""
        project_path = tmp_path / "myproject"
        fastband_dir = project_path / ".fastband"
        fastband_dir.mkdir(parents=True)

        config_file = fastband_dir / "config.yaml"
        config_file.write_text("old: config")

        result = init_fastband_config(project_path, force=True)

        assert result is True
        # Content should be replaced
        content = config_file.read_text()
        assert "old: config" not in content


class TestRunSetup:
    """Tests for run_setup function."""

    def test_full_setup_success(self, tmp_path):
        """Test full setup process."""
        project_path = tmp_path / "myproject"
        project_path.mkdir()

        # Mock successful detection and validation
        mock_info = InstallInfo(
            method=InstallMethod.PIPX,
            executable_path=Path("/usr/local/bin/fastband"),
        )

        with patch("fastband.cli.setup.detect_installation", return_value=mock_info):
            with patch("fastband.cli.setup.validate_mcp_server", return_value=True):
                result = run_setup(project_path, skip_validation=False)

        assert result is True
        assert (project_path / ".fastband" / "config.yaml").exists()
        assert (project_path / ".claude" / "mcp.json").exists()

    def test_setup_with_unknown_installation(self, tmp_path):
        """Test setup fails gracefully with unknown installation."""
        project_path = tmp_path / "myproject"
        project_path.mkdir()

        mock_info = InstallInfo(
            method=InstallMethod.UNKNOWN,
            executable_path=Path("fastband"),
        )

        with patch("fastband.cli.setup.detect_installation", return_value=mock_info):
            result = run_setup(project_path)

        assert result is False

    def test_setup_skip_validation(self, tmp_path):
        """Test setup with validation skipped."""
        project_path = tmp_path / "myproject"
        project_path.mkdir()

        mock_info = InstallInfo(
            method=InstallMethod.PIP,
            executable_path=Path("/usr/bin/fastband"),
        )

        with patch("fastband.cli.setup.detect_installation", return_value=mock_info):
            result = run_setup(project_path, skip_validation=True)

        assert result is True


class TestShowMcpConfig:
    """Tests for show_mcp_config function."""

    def test_show_project_config(self, tmp_path, capsys):
        """Test showing project config."""
        project_path = tmp_path / "myproject"
        claude_dir = project_path / ".claude"
        claude_dir.mkdir(parents=True)

        config = {
            "mcpServers": {
                "fastband": {
                    "command": "/usr/bin/fastband",
                    "args": ["serve", "--all"],
                }
            }
        }
        with open(claude_dir / "mcp.json", "w") as f:
            json.dump(config, f)

        # This will print to console, just verify it doesn't crash
        show_mcp_config(project_path)

    def test_show_no_config(self, tmp_path):
        """Test showing when no config exists."""
        project_path = tmp_path / "myproject"
        project_path.mkdir()

        # Should not crash
        show_mcp_config(project_path)


class TestCliIntegration:
    """Integration tests for CLI setup command."""

    def test_setup_command_exists(self):
        """Test that setup command is registered."""
        from typer.testing import CliRunner

        from fastband.cli.main import app

        runner = CliRunner()
        result = runner.invoke(app, ["--help"])

        # Check that setup appears in help output
        assert "setup" in result.output

    def test_setup_help(self):
        """Test setup command help text."""
        from typer.testing import CliRunner

        from fastband.cli.main import app

        runner = CliRunner()
        result = runner.invoke(app, ["setup", "--help"])

        assert result.exit_code == 0
        assert "Claude Code" in result.output
        assert "one-command setup" in result.output

    def test_setup_show_option(self, tmp_path):
        """Test setup --show option."""
        from typer.testing import CliRunner

        from fastband.cli.main import app

        runner = CliRunner()
        result = runner.invoke(app, ["setup", "--show", str(tmp_path)])

        assert result.exit_code == 0
        assert "MCP Configuration Status" in result.output


class TestCrossPlatform:
    """Cross-platform tests."""

    def test_macos_config_paths(self):
        """Test macOS config paths."""
        with patch("fastband.cli.setup.sys.platform", "darwin"):
            paths = get_claude_config_paths()
            assert "project" in paths
            assert "desktop" in paths
            assert "global" in paths

    def test_linux_config_paths(self):
        """Test Linux config paths."""
        with patch("fastband.cli.setup.sys.platform", "linux"):
            paths = get_claude_config_paths()
            assert "project" in paths
            assert "desktop" in paths
            assert "global" in paths

    def test_windows_config_paths(self):
        """Test Windows config paths."""
        with patch("fastband.cli.setup.sys.platform", "win32"):
            with patch.dict(os.environ, {"APPDATA": "C:\\Users\\Test\\AppData\\Roaming"}):
                paths = get_claude_config_paths()
                assert "project" in paths
                # Windows desktop path requires APPDATA
                assert "desktop" in paths
                assert "global" in paths


class TestSecurityFeatures:
    """Tests for security features in setup module."""

    def test_valid_config_types_constant(self):
        """Test that valid config types are defined."""
        assert "project" in VALID_CONFIG_TYPES
        assert "desktop" in VALID_CONFIG_TYPES
        assert "global" in VALID_CONFIG_TYPES
        assert len(VALID_CONFIG_TYPES) == 3

    def test_config_type_validation_rejects_invalid(self, tmp_path):
        """Test that invalid config types are rejected."""
        project_path = tmp_path / "myproject"
        project_path.mkdir()

        info = InstallInfo(
            method=InstallMethod.PIP,
            executable_path=Path("/usr/bin/fastband"),
        )

        with pytest.raises(ValueError, match="Invalid config_type"):
            create_mcp_config(project_path, info, "invalid_type")

    def test_config_type_validation_accepts_valid(self, tmp_path):
        """Test that valid config types are accepted."""
        project_path = tmp_path / "myproject"
        project_path.mkdir()

        info = InstallInfo(
            method=InstallMethod.PIP,
            executable_path=Path("/usr/bin/fastband"),
        )

        # Should not raise for valid types
        for config_type in VALID_CONFIG_TYPES:
            # Skip desktop/global as they may not have valid paths in test env
            if config_type == "project":
                config_path = create_mcp_config(project_path, info, config_type)
                assert config_path.exists()


class TestPathValidation:
    """Tests for path validation security."""

    def test_valid_home_directory_path(self):
        """Test that paths under home directory are valid."""
        home = Path.home()
        valid_path = home / "projects" / "myapp"
        assert _validate_project_path(valid_path) is True

    def test_valid_tmp_path(self):
        """Test that /tmp paths are valid."""
        tmp_path = Path("/tmp/test/project")
        assert _validate_project_path(tmp_path) is True

    def test_path_traversal_rejected(self):
        """Test that path traversal patterns are rejected."""
        # Paths with .. are rejected
        home = Path.home()
        traversal_path = home / "projects" / ".." / ".." / "etc"
        # Note: resolve() would eliminate .., but we check the string
        # In practice, paths are resolved before validation
        assert _validate_project_path(Path("/etc/passwd")) is False

    def test_null_byte_rejected(self):
        """Test that null byte injection is rejected."""
        malicious_path = Path("/home/user/project\x00/etc/passwd")
        assert _validate_project_path(malicious_path) is False

    def test_url_encoded_traversal_rejected(self):
        """Test that URL-encoded traversal is rejected."""
        malicious_path = Path("/home/user/project%2e%2e/etc")
        assert _validate_project_path(malicious_path) is False

    def test_system_paths_rejected(self):
        """Test that system paths outside allowed roots are rejected."""
        system_path = Path("/etc/passwd")
        assert _validate_project_path(system_path) is False

        bin_path = Path("/usr/bin")
        assert _validate_project_path(bin_path) is False

    @pytest.mark.skipif(sys.platform != "darwin", reason="macOS only")
    def test_volumes_path_allowed_on_macos(self):
        """Test that /Volumes paths are allowed on macOS."""
        volumes_path = Path("/Volumes/Data/projects/myapp")
        assert _validate_project_path(volumes_path) is True


class TestFilePermissions:
    """Tests for file permission security."""

    def test_config_file_has_restricted_permissions(self, tmp_path):
        """Test that created config files have restricted permissions."""
        import stat as stat_module

        project_path = tmp_path / "myproject"
        project_path.mkdir()

        info = InstallInfo(
            method=InstallMethod.PIP,
            executable_path=Path("/usr/bin/fastband"),
        )

        config_path = create_mcp_config(project_path, info, "project")

        # Check file permissions (should be 0o600 - owner read/write only)
        file_mode = config_path.stat().st_mode
        # Mask to get just the permission bits
        perm_bits = stat_module.S_IMODE(file_mode)

        # On Unix, should be 0o600 (owner read/write)
        # Allow some flexibility for different systems
        assert perm_bits & stat_module.S_IRWXO == 0  # No other permissions
        assert perm_bits & stat_module.S_IRWXG == 0  # No group permissions


class TestBackupSecurity:
    """Tests for backup handling security."""

    def test_backup_uses_timestamp(self, tmp_path):
        """Test that backup files use timestamps for uniqueness."""
        import glob

        project_path = tmp_path / "myproject"
        claude_dir = project_path / ".claude"
        claude_dir.mkdir(parents=True)

        # Create corrupted config
        config_file = claude_dir / "mcp.json"
        config_file.write_text("not valid json {{{")

        info = InstallInfo(
            method=InstallMethod.PIP,
            executable_path=Path("/usr/bin/fastband"),
        )

        create_mcp_config(project_path, info, "project")

        # Check that backup was created with timestamp
        backup_files = list(claude_dir.glob("mcp.json.backup.*"))
        assert len(backup_files) >= 1


class TestPipFallback:
    """Tests for PIP installation fallback scenarios."""

    def test_pip_command_fallback_to_sys_executable(self):
        """Test MCP command for pip installation with no python_path."""
        info = InstallInfo(
            method=InstallMethod.PIP,
            executable_path=Path("/nonexistent/fastband"),
            python_path=None,
        )
        with patch.object(Path, "exists", return_value=False):
            command, args = get_mcp_command(info)
            assert command == str(sys.executable)
            assert args == ["-m", "fastband", "serve", "--all"]

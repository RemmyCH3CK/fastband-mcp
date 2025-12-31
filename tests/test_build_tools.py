"""
Tests for Build Tools.

Tests cover:
- BuildProjectTool: Project build with backup integration
- RunScriptTool: Script execution with package managers
"""

import asyncio
import shutil
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from fastband.tools.core.build import (
    BUILD_TOOLS,
    BuildProjectTool,
    RunScriptTool,
)

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def temp_project():
    """Create a temporary project directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project = Path(tmpdir)
        yield project


@pytest.fixture
def npm_project(temp_project):
    """Create a Node.js project with package.json."""
    package_json = temp_project / "package.json"
    package_json.write_text("""{
  "name": "test-project",
  "version": "1.0.0",
  "scripts": {
    "build": "echo 'Building...'",
    "test": "echo 'Testing...'",
    "lint": "echo 'Linting...'"
  }
}""")
    # Create package-lock.json to indicate npm
    (temp_project / "package-lock.json").write_text("{}")
    return temp_project


@pytest.fixture
def python_project(temp_project):
    """Create a Python project with pyproject.toml."""
    pyproject = temp_project / "pyproject.toml"
    pyproject.write_text("""[project]
name = "test-project"
version = "1.0.0"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
""")
    return temp_project


@pytest.fixture
def rust_project(temp_project):
    """Create a Rust project with Cargo.toml."""
    cargo_toml = temp_project / "Cargo.toml"
    cargo_toml.write_text("""[package]
name = "test-project"
version = "1.0.0"
""")
    return temp_project


@pytest.fixture
def makefile_project(temp_project):
    """Create a project with Makefile."""
    makefile = temp_project / "Makefile"
    makefile.write_text("""
all:
\techo "Building..."
""")
    return temp_project


# =============================================================================
# BUILD PROJECT TOOL DEFINITION TESTS
# =============================================================================


class TestBuildProjectToolDefinition:
    """Tests for BuildProjectTool definition."""

    def test_tool_name(self, temp_project):
        """Test tool name."""
        tool = BuildProjectTool(project_path=temp_project)
        assert tool.definition.metadata.name == "build_project"

    def test_tool_description(self, temp_project):
        """Test tool has description."""
        tool = BuildProjectTool(project_path=temp_project)
        assert "build" in tool.definition.metadata.description.lower()

    def test_tool_parameters(self, temp_project):
        """Test tool parameters are defined."""
        tool = BuildProjectTool(project_path=temp_project)
        params = {p.name for p in tool.definition.parameters}
        assert "command" in params
        assert "skip_backup" in params
        assert "args" in params

    def test_default_project_path(self):
        """Test tool uses cwd when no path provided."""
        tool = BuildProjectTool()
        assert tool.project_path == Path.cwd()


# =============================================================================
# BUILD COMMAND DETECTION TESTS
# =============================================================================


class TestBuildCommandDetection:
    """Tests for build command detection."""

    def test_detect_npm_build(self, npm_project):
        """Test detecting npm build command."""
        tool = BuildProjectTool(project_path=npm_project)
        with patch.object(shutil, "which", return_value="/usr/bin/npm"):
            cmd = tool._detect_build_command()
            assert cmd == "npm run build"

    def test_detect_yarn_build(self, temp_project):
        """Test detecting yarn build command."""
        (temp_project / "package.json").write_text('{"scripts": {"build": "..."}}')
        (temp_project / "yarn.lock").write_text("")

        tool = BuildProjectTool(project_path=temp_project)
        with patch.object(shutil, "which", return_value="/usr/bin/yarn"):
            cmd = tool._detect_build_command()
            assert cmd == "yarn build"

    def test_detect_pnpm_build(self, temp_project):
        """Test detecting pnpm build command."""
        (temp_project / "package.json").write_text('{"scripts": {"build": "..."}}')
        (temp_project / "pnpm-lock.yaml").write_text("")

        tool = BuildProjectTool(project_path=temp_project)
        with patch.object(shutil, "which", return_value="/usr/bin/pnpm"):
            cmd = tool._detect_build_command()
            assert cmd == "pnpm run build"

    def test_detect_python_build(self, python_project):
        """Test detecting Python build command."""
        tool = BuildProjectTool(project_path=python_project)
        with patch.object(shutil, "which", return_value="/usr/bin/python"):
            cmd = tool._detect_build_command()
            assert "python" in cmd and "build" in cmd

    def test_detect_poetry_build(self, temp_project):
        """Test detecting poetry build command."""
        (temp_project / "pyproject.toml").write_text("[tool.poetry]")
        (temp_project / "poetry.lock").write_text("")

        tool = BuildProjectTool(project_path=temp_project)
        with patch.object(shutil, "which", return_value="/usr/bin/poetry"):
            cmd = tool._detect_build_command()
            assert cmd == "poetry build"

    def test_detect_cargo_build(self, rust_project):
        """Test detecting Cargo build command."""
        tool = BuildProjectTool(project_path=rust_project)
        with patch.object(shutil, "which", return_value="/usr/bin/cargo"):
            cmd = tool._detect_build_command()
            assert "cargo build" in cmd

    def test_detect_make_build(self, makefile_project):
        """Test detecting make build command."""
        tool = BuildProjectTool(project_path=makefile_project)
        with patch.object(shutil, "which", return_value="/usr/bin/make"):
            cmd = tool._detect_build_command()
            assert cmd == "make"

    def test_no_build_system_detected(self, temp_project):
        """Test when no build system is found."""
        tool = BuildProjectTool(project_path=temp_project)
        cmd = tool._detect_build_command()
        assert cmd is None


# =============================================================================
# BUILD EXECUTION TESTS
# =============================================================================


class TestBuildExecution:
    """Tests for build execution."""

    @pytest.mark.asyncio
    async def test_build_no_command_detected(self, temp_project):
        """Test error when no build command can be detected."""
        tool = BuildProjectTool(project_path=temp_project)

        with patch.object(tool, "_detect_build_command", return_value=None):
            result = await tool.execute()

            assert result.success is False
            assert "Could not detect" in result.error

    @pytest.mark.asyncio
    async def test_build_with_custom_command(self, temp_project):
        """Test build with custom command."""
        tool = BuildProjectTool(project_path=temp_project)

        with patch.object(tool, "_run_build") as mock_run:
            mock_run.return_value = {
                "success": True,
                "return_code": 0,
                "stdout": "Build complete",
                "stderr": "",
            }

            result = await tool.execute(command="echo test", skip_backup=True)

            assert result.success is True
            mock_run.assert_called_once()
            # Check command was split correctly
            call_args = mock_run.call_args[0][0]
            assert call_args == ["echo", "test"]

    @pytest.mark.asyncio
    async def test_build_with_args(self, temp_project):
        """Test build with additional arguments."""
        tool = BuildProjectTool(project_path=temp_project)

        with patch.object(tool, "_run_build") as mock_run:
            mock_run.return_value = {
                "success": True,
                "return_code": 0,
                "stdout": "",
                "stderr": "",
            }

            result = await tool.execute(
                command="npm run build", args=["--production"], skip_backup=True
            )

            assert result.success is True
            call_args = mock_run.call_args[0][0]
            assert "--production" in call_args

    @pytest.mark.asyncio
    async def test_build_triggers_backup(self, temp_project):
        """Test that build triggers backup hook."""
        tool = BuildProjectTool(project_path=temp_project)

        mock_backup_info = MagicMock()
        mock_backup_info.id = "backup-123"
        mock_backup_info.size_human = "1.5 MB"

        with patch(
            "fastband.tools.core.build.trigger_backup_hook", return_value=mock_backup_info
        ) as mock_backup:
            with patch.object(tool, "_run_build") as mock_run:
                mock_run.return_value = {
                    "success": True,
                    "return_code": 0,
                    "stdout": "",
                    "stderr": "",
                }

                result = await tool.execute(command="echo test", skip_backup=False)

                mock_backup.assert_called_once_with(
                    "before_build", project_path=temp_project
                )
                assert result.data["backup_created"] == "backup-123"

    @pytest.mark.asyncio
    async def test_build_skip_backup(self, temp_project):
        """Test build with backup skipped."""
        tool = BuildProjectTool(project_path=temp_project)

        with patch(
            "fastband.tools.core.build.trigger_backup_hook"
        ) as mock_backup:
            with patch.object(tool, "_run_build") as mock_run:
                mock_run.return_value = {
                    "success": True,
                    "return_code": 0,
                    "stdout": "",
                    "stderr": "",
                }

                await tool.execute(command="echo test", skip_backup=True)

                mock_backup.assert_not_called()

    @pytest.mark.asyncio
    async def test_build_failure(self, temp_project):
        """Test handling of build failure."""
        tool = BuildProjectTool(project_path=temp_project)

        with patch.object(tool, "_run_build") as mock_run:
            mock_run.return_value = {
                "success": False,
                "return_code": 1,
                "stdout": "",
                "stderr": "Build failed",
            }

            result = await tool.execute(command="npm run build", skip_backup=True)

            assert result.success is False
            assert "failed" in result.error.lower()
            assert result.data["return_code"] == 1

    @pytest.mark.asyncio
    async def test_build_exception(self, temp_project):
        """Test handling of exceptions during build."""
        tool = BuildProjectTool(project_path=temp_project)

        with patch.object(tool, "_run_build", side_effect=Exception("Unexpected error")):
            result = await tool.execute(command="echo test", skip_backup=True)

            assert result.success is False
            assert "failed" in result.error.lower()


class TestRunBuild:
    """Tests for _run_build method."""

    @pytest.mark.asyncio
    async def test_run_build_success(self, temp_project):
        """Test successful command execution."""
        tool = BuildProjectTool(project_path=temp_project)

        result = await tool._run_build(["echo", "hello"])

        assert result["success"] is True
        assert result["return_code"] == 0
        assert "hello" in result["stdout"]

    @pytest.mark.asyncio
    async def test_run_build_command_not_found(self, temp_project):
        """Test handling of command not found."""
        tool = BuildProjectTool(project_path=temp_project)

        result = await tool._run_build(["nonexistent_command_12345"])

        assert result["success"] is False
        assert result["return_code"] == 127
        assert "not found" in result["stderr"].lower()

    @pytest.mark.asyncio
    async def test_run_build_nonzero_exit(self, temp_project):
        """Test handling of non-zero exit code."""
        tool = BuildProjectTool(project_path=temp_project)

        result = await tool._run_build(["sh", "-c", "exit 42"])

        assert result["success"] is False
        assert result["return_code"] == 42


# =============================================================================
# RUN SCRIPT TOOL TESTS
# =============================================================================


class TestRunScriptToolDefinition:
    """Tests for RunScriptTool definition."""

    def test_tool_name(self, temp_project):
        """Test tool name."""
        tool = RunScriptTool(project_path=temp_project)
        assert tool.definition.metadata.name == "run_script"

    def test_tool_parameters(self, temp_project):
        """Test tool parameters are defined."""
        tool = RunScriptTool(project_path=temp_project)
        params = {p.name for p in tool.definition.parameters}
        assert "script" in params
        assert "skip_backup" in params
        assert "args" in params

    def test_script_required(self, temp_project):
        """Test script parameter is required."""
        tool = RunScriptTool(project_path=temp_project)
        script_param = next(
            p for p in tool.definition.parameters if p.name == "script"
        )
        assert script_param.required is True


class TestRunnerDetection:
    """Tests for script runner detection."""

    def test_detect_npm_runner(self, npm_project):
        """Test detecting npm runner."""
        tool = RunScriptTool(project_path=npm_project)
        with patch.object(shutil, "which", return_value="/usr/bin/npm"):
            runner = tool._detect_runner()
            assert runner == ["npm", "run"]

    def test_detect_yarn_runner(self, temp_project):
        """Test detecting yarn runner."""
        (temp_project / "package.json").write_text("{}")
        (temp_project / "yarn.lock").write_text("")

        tool = RunScriptTool(project_path=temp_project)
        with patch.object(shutil, "which", return_value="/usr/bin/yarn"):
            runner = tool._detect_runner()
            assert runner == ["yarn"]

    def test_detect_pnpm_runner(self, temp_project):
        """Test detecting pnpm runner."""
        (temp_project / "package.json").write_text("{}")
        (temp_project / "pnpm-lock.yaml").write_text("")

        tool = RunScriptTool(project_path=temp_project)
        with patch.object(shutil, "which", return_value="/usr/bin/pnpm"):
            runner = tool._detect_runner()
            assert runner == ["pnpm", "run"]

    def test_detect_poetry_runner(self, temp_project):
        """Test detecting poetry runner."""
        (temp_project / "pyproject.toml").write_text("[tool.poetry]")
        (temp_project / "poetry.lock").write_text("")

        tool = RunScriptTool(project_path=temp_project)
        with patch.object(shutil, "which", return_value="/usr/bin/poetry"):
            runner = tool._detect_runner()
            assert runner == ["poetry", "run"]

    def test_no_runner_detected(self, temp_project):
        """Test when no runner is found."""
        tool = RunScriptTool(project_path=temp_project)
        runner = tool._detect_runner()
        assert runner is None


class TestRunScriptExecution:
    """Tests for script execution."""

    @pytest.mark.asyncio
    async def test_run_script_no_runner(self, temp_project):
        """Test error when no runner detected."""
        tool = RunScriptTool(project_path=temp_project)

        result = await tool.execute(script="test")

        assert result.success is False
        assert "Could not detect" in result.error

    @pytest.mark.asyncio
    async def test_run_script_success(self, npm_project):
        """Test successful script execution."""
        tool = RunScriptTool(project_path=npm_project)

        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b"Test passed", b""))

        with patch.object(shutil, "which", return_value="/usr/bin/npm"):
            with patch.object(
                asyncio, "create_subprocess_exec", return_value=mock_process
            ):
                result = await tool.execute(script="test", skip_backup=True)

                assert result.success is True
                assert result.data["script"] == "test"

    @pytest.mark.asyncio
    async def test_run_build_script_triggers_backup(self, npm_project):
        """Test that build script triggers backup."""
        tool = RunScriptTool(project_path=npm_project)

        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b"", b""))

        mock_backup_info = MagicMock()
        mock_backup_info.id = "backup-456"

        with patch.object(shutil, "which", return_value="/usr/bin/npm"):
            with patch.object(
                asyncio, "create_subprocess_exec", return_value=mock_process
            ):
                with patch(
                    "fastband.tools.core.build.trigger_backup_hook",
                    return_value=mock_backup_info,
                ) as mock_backup:
                    result = await tool.execute(script="build", skip_backup=False)

                    mock_backup.assert_called_once()
                    assert result.data["backup_created"] == "backup-456"

    @pytest.mark.asyncio
    async def test_run_script_with_args(self, npm_project):
        """Test script with additional arguments."""
        tool = RunScriptTool(project_path=npm_project)

        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b"", b""))

        with patch.object(shutil, "which", return_value="/usr/bin/npm"):
            with patch.object(
                asyncio, "create_subprocess_exec", return_value=mock_process
            ) as mock_exec:
                await tool.execute(
                    script="test", args=["--coverage"], skip_backup=True
                )

                # Check args were passed
                call_args = mock_exec.call_args
                assert "--coverage" in call_args[0]

    @pytest.mark.asyncio
    async def test_run_script_failure(self, npm_project):
        """Test handling of script failure."""
        tool = RunScriptTool(project_path=npm_project)

        mock_process = AsyncMock()
        mock_process.returncode = 1
        mock_process.communicate = AsyncMock(return_value=(b"", b"Error"))

        with patch.object(shutil, "which", return_value="/usr/bin/npm"):
            with patch.object(
                asyncio, "create_subprocess_exec", return_value=mock_process
            ):
                result = await tool.execute(script="test", skip_backup=True)

                assert result.success is False
                assert "failed" in result.error.lower()
                assert result.data["return_code"] == 1

    @pytest.mark.asyncio
    async def test_run_script_exception(self, npm_project):
        """Test handling of exceptions."""
        tool = RunScriptTool(project_path=npm_project)

        with patch.object(shutil, "which", return_value="/usr/bin/npm"):
            with patch.object(
                asyncio,
                "create_subprocess_exec",
                side_effect=Exception("Process error"),
            ):
                result = await tool.execute(script="test", skip_backup=True)

                assert result.success is False
                assert "Failed to run script" in result.error


# =============================================================================
# MODULE TESTS
# =============================================================================


class TestBuildToolsModule:
    """Tests for build tools module."""

    def test_build_tools_list(self):
        """Test BUILD_TOOLS contains expected tools."""
        assert BuildProjectTool in BUILD_TOOLS
        assert RunScriptTool in BUILD_TOOLS
        assert len(BUILD_TOOLS) == 2

    def test_tool_categories(self, temp_project):
        """Test tools have correct category."""
        from fastband.tools.base import ToolCategory

        build_tool = BuildProjectTool(project_path=temp_project)
        script_tool = RunScriptTool(project_path=temp_project)

        assert build_tool.definition.metadata.category == ToolCategory.CORE
        assert script_tool.definition.metadata.category == ToolCategory.CORE

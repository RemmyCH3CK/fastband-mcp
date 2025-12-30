"""
Build tools - Project build commands with backup integration.

Provides:
- BuildProjectTool: Run project build commands with pre-build backup
"""

import asyncio
import shutil
from pathlib import Path
from typing import Any

from fastband.backup import trigger_backup_hook
from fastband.tools.base import (
    Tool,
    ToolCategory,
    ToolDefinition,
    ToolMetadata,
    ToolParameter,
    ToolResult,
)


class BuildProjectTool(Tool):
    """
    Build the current project.

    Automatically detects the project type and runs the appropriate
    build command. Creates a backup before building if hooks are enabled.

    Supported build systems:
    - npm/yarn/pnpm (Node.js)
    - pip/poetry/pdm (Python)
    - cargo (Rust)
    - go build (Go)
    - make (C/C++)
    - gradle/maven (Java)
    """

    def __init__(self, project_path: Path | None = None):
        self.project_path = project_path or Path.cwd()

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            metadata=ToolMetadata(
                name="build_project",
                description="Build the current project. Runs detected build tool (npm, pip, cargo, etc.) with optional pre-build backup.",
                category=ToolCategory.CORE,
                version="1.0.0",
            ),
            parameters=[
                ToolParameter(
                    name="command",
                    type="string",
                    description="Build command to run. Auto-detected if not specified.",
                    required=False,
                ),
                ToolParameter(
                    name="skip_backup",
                    type="boolean",
                    description="Skip pre-build backup (not recommended)",
                    required=False,
                    default=False,
                ),
                ToolParameter(
                    name="args",
                    type="array",
                    description="Additional arguments to pass to build command",
                    required=False,
                ),
            ],
        )

    async def execute(
        self,
        command: str | None = None,
        skip_backup: bool = False,
        args: list[str] | None = None,
        **kwargs,
    ) -> ToolResult:
        """Execute project build with pre-build backup."""
        try:
            # Trigger pre-build backup
            backup_info = None
            if not skip_backup:
                try:
                    backup_info = trigger_backup_hook(
                        "before_build",
                        project_path=self.project_path,
                    )
                except Exception:
                    # Log but don't fail build if backup fails
                    pass

            # Detect or use provided build command
            build_cmd = command
            if not build_cmd:
                build_cmd = self._detect_build_command()

            if not build_cmd:
                return ToolResult(
                    success=False,
                    error="Could not detect build system. Please specify a command.",
                )

            # Prepare full command
            full_cmd = build_cmd.split()
            if args:
                full_cmd.extend(args)

            # Run build
            result = await self._run_build(full_cmd)

            response_data: dict[str, Any] = {
                "command": " ".join(full_cmd),
                "success": result["success"],
                "output": result.get("stdout", ""),
                "errors": result.get("stderr", ""),
                "return_code": result.get("return_code", 0),
            }

            if backup_info:
                response_data["backup_created"] = backup_info.id
                response_data["backup_size"] = backup_info.size_human

            if not result["success"]:
                return ToolResult(
                    success=False,
                    error=f"Build failed with return code {result.get('return_code', 1)}",
                    data=response_data,
                )

            return ToolResult(success=True, data=response_data)

        except Exception as e:
            return ToolResult(success=False, error=f"Build failed: {e}")

    def _detect_build_command(self) -> str | None:
        """Detect the appropriate build command for this project."""
        # Check for common build files
        checks = [
            # Node.js
            ("package.json", "pnpm-lock.yaml", "pnpm run build"),
            ("package.json", "yarn.lock", "yarn build"),
            ("package.json", "package-lock.json", "npm run build"),
            ("package.json", None, "npm run build"),
            # Python
            ("pyproject.toml", "poetry.lock", "poetry build"),
            ("pyproject.toml", "pdm.lock", "pdm build"),
            ("pyproject.toml", None, "python -m build"),
            ("setup.py", None, "python setup.py build"),
            # Rust
            ("Cargo.toml", None, "cargo build --release"),
            # Go
            ("go.mod", None, "go build ./..."),
            # Make
            ("Makefile", None, "make"),
            # Java
            ("build.gradle", None, "gradle build"),
            ("build.gradle.kts", None, "gradle build"),
            ("pom.xml", None, "mvn package"),
        ]

        for main_file, lock_file, cmd in checks:
            if (self.project_path / main_file).exists():
                if lock_file is None or (self.project_path / lock_file).exists():
                    # Verify the command exists
                    cmd_name = cmd.split()[0]
                    if shutil.which(cmd_name):
                        return cmd

        return None

    async def _run_build(self, cmd: list[str]) -> dict[str, Any]:
        """Run the build command asynchronously."""
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=self.project_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await process.communicate()

            return {
                "success": process.returncode == 0,
                "return_code": process.returncode,
                "stdout": stdout.decode("utf-8", errors="replace"),
                "stderr": stderr.decode("utf-8", errors="replace"),
            }

        except FileNotFoundError:
            return {
                "success": False,
                "return_code": 127,
                "stdout": "",
                "stderr": f"Command not found: {cmd[0]}",
            }
        except Exception as e:
            return {
                "success": False,
                "return_code": 1,
                "stdout": "",
                "stderr": str(e),
            }


class RunScriptTool(Tool):
    """
    Run a project script defined in package.json or pyproject.toml.

    Supports:
    - npm/yarn/pnpm scripts
    - poetry/pdm scripts
    """

    def __init__(self, project_path: Path | None = None):
        self.project_path = project_path or Path.cwd()

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            metadata=ToolMetadata(
                name="run_script",
                description="Run a project script (npm run, poetry run, etc.) with optional pre-build backup.",
                category=ToolCategory.CORE,
                version="1.0.0",
            ),
            parameters=[
                ToolParameter(
                    name="script",
                    type="string",
                    description="Script name to run (e.g., 'test', 'lint', 'build')",
                    required=True,
                ),
                ToolParameter(
                    name="skip_backup",
                    type="boolean",
                    description="Skip pre-run backup (enabled for 'build' scripts by default)",
                    required=False,
                    default=True,
                ),
                ToolParameter(
                    name="args",
                    type="array",
                    description="Additional arguments to pass to the script",
                    required=False,
                ),
            ],
        )

    async def execute(
        self,
        script: str,
        skip_backup: bool = True,
        args: list[str] | None = None,
        **kwargs,
    ) -> ToolResult:
        """Run a project script."""
        try:
            # For build scripts, trigger backup by default
            should_backup = not skip_backup or script.lower() in ["build", "compile", "dist"]

            backup_info = None
            if should_backup:
                try:
                    backup_info = trigger_backup_hook(
                        "before_build",
                        project_path=self.project_path,
                    )
                except Exception:
                    pass

            # Detect script runner
            runner = self._detect_runner()
            if not runner:
                return ToolResult(
                    success=False,
                    error="Could not detect script runner (npm, yarn, poetry, etc.)",
                )

            # Build command
            cmd = runner + [script]
            if args:
                cmd.extend(args)

            # Run script
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=self.project_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await process.communicate()

            response_data: dict[str, Any] = {
                "script": script,
                "command": " ".join(cmd),
                "success": process.returncode == 0,
                "output": stdout.decode("utf-8", errors="replace"),
                "errors": stderr.decode("utf-8", errors="replace"),
                "return_code": process.returncode,
            }

            if backup_info:
                response_data["backup_created"] = backup_info.id

            if process.returncode != 0:
                return ToolResult(
                    success=False,
                    error=f"Script '{script}' failed with code {process.returncode}",
                    data=response_data,
                )

            return ToolResult(success=True, data=response_data)

        except Exception as e:
            return ToolResult(success=False, error=f"Failed to run script: {e}")

    def _detect_runner(self) -> list[str] | None:
        """Detect the appropriate script runner."""
        # Node.js runners
        if (self.project_path / "package.json").exists():
            if (self.project_path / "pnpm-lock.yaml").exists() and shutil.which("pnpm"):
                return ["pnpm", "run"]
            if (self.project_path / "yarn.lock").exists() and shutil.which("yarn"):
                return ["yarn"]
            if shutil.which("npm"):
                return ["npm", "run"]

        # Python runners
        if (self.project_path / "pyproject.toml").exists():
            if (self.project_path / "poetry.lock").exists() and shutil.which("poetry"):
                return ["poetry", "run"]
            if (self.project_path / "pdm.lock").exists() and shutil.which("pdm"):
                return ["pdm", "run"]

        return None


# Build tools list
BUILD_TOOLS = [
    BuildProjectTool,
    RunScriptTool,
]

__all__ = [
    "BuildProjectTool",
    "RunScriptTool",
    "BUILD_TOOLS",
]

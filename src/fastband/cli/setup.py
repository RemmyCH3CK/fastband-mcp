"""
Fastband Setup - Automated Claude Code MCP configuration.

This module provides automatic setup of Fastband with Claude Code,
eliminating manual JSON editing and configuration.
"""

import json
import os
import shutil
import stat
import subprocess
import sys
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()

# Valid config types for MCP configuration
VALID_CONFIG_TYPES = frozenset({"project", "desktop", "global"})


class InstallMethod(Enum):
    """How fastband was installed."""

    PIPX = "pipx"
    PIP = "pip"
    UV = "uv"
    SOURCE = "source"
    UNKNOWN = "unknown"


@dataclass
class InstallInfo:
    """Information about the fastband installation."""

    method: InstallMethod
    executable_path: Path
    python_path: Path | None = None
    version: str | None = None


def detect_installation() -> InstallInfo:
    """
    Detect how fastband was installed and get the executable path.

    Returns:
        InstallInfo with installation details.
    """
    # First, find the fastband executable
    fastband_path = shutil.which("fastband")

    if fastband_path:
        fastband_path = Path(fastband_path).resolve()

        # Check if it's a pipx installation
        # pipx installs to ~/.local/bin/ or ~/.local/pipx/venvs/
        if ".local" in str(fastband_path):
            # Check for pipx-specific paths
            pipx_venvs = Path.home() / ".local" / "pipx" / "venvs"
            if pipx_venvs.exists():
                # Look for fastband-agent-control venv
                for venv_name in ["fastband-agent-control", "fastband"]:
                    venv_path = pipx_venvs / venv_name
                    if venv_path.exists():
                        return InstallInfo(
                            method=InstallMethod.PIPX,
                            executable_path=fastband_path,
                            python_path=venv_path / "bin" / "python",
                        )

            # Still likely pipx even if we can't find the venv
            if (
                "pipx" in str(fastband_path)
                or (Path.home() / ".local" / "bin" / "fastband").exists()
            ):
                return InstallInfo(
                    method=InstallMethod.PIPX,
                    executable_path=fastband_path,
                )

        # Check if it's a uv installation
        # Note: Only classify as UV if we didn't already match pipx above
        # UV installs to ~/.local/bin but pipx is more common and was already checked
        # Only detect UV if uv tool exists AND pipx venvs don't exist (to avoid ambiguity)
        if ".local/bin" in str(fastband_path):
            pipx_venvs = Path.home() / ".local" / "pipx" / "venvs"
            uv_path = shutil.which("uv")
            # Only classify as UV if pipx venvs don't exist (indicates non-pipx install)
            if uv_path and not pipx_venvs.exists():
                return InstallInfo(
                    method=InstallMethod.UV,
                    executable_path=fastband_path,
                )

        # Check if it's in a virtual environment (pip install -e or pip install)
        if "venv" in str(fastband_path) or ".venv" in str(fastband_path):
            return InstallInfo(
                method=InstallMethod.SOURCE,
                executable_path=fastband_path,
                python_path=Path(sys.executable),
            )

        # Regular pip install
        return InstallInfo(
            method=InstallMethod.PIP,
            executable_path=fastband_path,
            python_path=Path(sys.executable),
        )

    # Fallback: try to find via python -m fastband
    try:
        result = subprocess.run(
            [sys.executable, "-m", "fastband", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return InstallInfo(
                method=InstallMethod.PIP,
                executable_path=Path(sys.executable),
                python_path=Path(sys.executable),
            )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    # Unknown installation
    return InstallInfo(
        method=InstallMethod.UNKNOWN,
        executable_path=Path("fastband"),
    )


def get_mcp_command(install_info: InstallInfo) -> tuple[str, list[str]]:
    """
    Get the command and args for the MCP server based on installation method.

    Args:
        install_info: Installation information.

    Returns:
        Tuple of (command, args) for the MCP config.
    """
    if install_info.method == InstallMethod.PIPX:
        # pipx: use the full path to the executable
        return str(install_info.executable_path), ["serve", "--all"]

    elif install_info.method == InstallMethod.UV:
        # uv: use uvx or the full path
        return str(install_info.executable_path), ["serve", "--all"]

    elif install_info.method == InstallMethod.SOURCE:
        # Source/development: use python -m fastband
        return str(install_info.python_path), ["-m", "fastband", "serve", "--all"]

    elif install_info.method == InstallMethod.PIP:
        # pip: could be in PATH or need python -m
        if install_info.executable_path.exists():
            return str(install_info.executable_path), ["serve", "--all"]
        else:
            return str(install_info.python_path or sys.executable), [
                "-m",
                "fastband",
                "serve",
                "--all",
            ]

    else:
        # Unknown: best effort
        return "fastband", ["serve", "--all"]


def get_claude_config_paths() -> dict[str, Path]:
    """
    Get possible Claude Code/Desktop configuration paths.

    Returns:
        Dict mapping config type to path.
    """
    home = Path.home()

    paths = {}

    # Claude Code CLI - project-level config (preferred)
    # This is created in the project directory
    paths["project"] = Path(".claude") / "mcp.json"

    # Claude Desktop config locations
    if sys.platform == "darwin":
        # macOS
        paths["desktop"] = (
            home / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
        )
    elif sys.platform == "win32":
        # Windows
        appdata = os.environ.get("APPDATA", "")
        if appdata:
            paths["desktop"] = Path(appdata) / "Claude" / "claude_desktop_config.json"
    else:
        # Linux
        paths["desktop"] = home / ".config" / "Claude" / "claude_desktop_config.json"

    # Global Claude Code config
    paths["global"] = home / ".claude" / "claude_desktop_config.json"

    return paths


def create_mcp_config(
    project_path: Path,
    install_info: InstallInfo,
    config_type: str = "project",
) -> Path:
    """
    Create or update the MCP configuration file.

    Args:
        project_path: Path to the project.
        install_info: Installation information.
        config_type: Type of config to create ("project", "desktop", or "global").

    Returns:
        Path to the created/updated config file.

    Raises:
        ValueError: If config_type is invalid.
    """
    # Validate config_type parameter
    if config_type not in VALID_CONFIG_TYPES:
        raise ValueError(
            f"Invalid config_type: {config_type}. Must be one of {sorted(VALID_CONFIG_TYPES)}"
        )

    paths = get_claude_config_paths()
    config_path = paths.get(config_type)

    if config_type == "project":
        # Project-level config is relative to project
        config_path = project_path / ".claude" / "mcp.json"

    if not config_path:
        raise ValueError(f"Unknown config type: {config_type}")

    # Get the command for MCP
    command, args = get_mcp_command(install_info)

    # Build the MCP server entry
    mcp_entry = {
        "command": command,
        "args": args,
    }

    # For global/desktop configs, we need the working directory
    if config_type != "project":
        mcp_entry["cwd"] = str(project_path)

    # Load existing config or create new
    config_data: dict = {"mcpServers": {}}

    try:
        with open(config_path) as f:
            config_data = json.load(f)
        if "mcpServers" not in config_data:
            config_data["mcpServers"] = {}
    except FileNotFoundError:
        # Config doesn't exist yet, use default
        pass
    except (json.JSONDecodeError, OSError):
        # Backup corrupted file with unique timestamp
        backup_suffix = f".backup.{int(time.time())}"
        backup_path = config_path.with_suffix(f".json{backup_suffix}")
        # Validate backup path is in same directory (security)
        if backup_path.parent != config_path.parent:
            console.print("[red]Security error: backup path validation failed[/red]")
            raise ValueError("Backup path must be in same directory as config")
        try:
            shutil.copy2(config_path, backup_path)
            console.print(f"[yellow]Backed up corrupted config to {backup_path}[/yellow]")
        except OSError as e:
            console.print(f"[yellow]Could not backup corrupted file: {e}[/yellow]")

    # Add/update fastband entry
    config_data["mcpServers"]["fastband"] = mcp_entry

    # Ensure parent directory exists with restricted permissions
    config_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(config_path.parent, stat.S_IRWXU)  # 0o700 - owner only
    except OSError:
        pass  # May fail on some filesystems, non-fatal

    # Write config with restricted permissions (0o600 - owner read/write only)
    # First create/truncate with restricted permissions
    fd = os.open(config_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(config_data, f, indent=2)
    except Exception:
        os.close(fd)
        raise

    return config_path


def validate_mcp_server(install_info: InstallInfo, timeout: float = 5.0) -> bool:
    """
    Validate that the MCP server can start correctly.

    Args:
        install_info: Installation information.
        timeout: Timeout in seconds.

    Returns:
        True if server starts correctly.
    """
    command, args = get_mcp_command(install_info)

    # Add --help to just check if it runs
    test_args = args.copy()
    if "serve" in test_args:
        # Replace serve with --help to test without actually starting
        idx = test_args.index("serve")
        test_args = test_args[:idx] + ["--help"]

    try:
        result = subprocess.run(
            [command, *test_args],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False


def init_fastband_config(project_path: Path, force: bool = False) -> bool:
    """
    Initialize .fastband configuration if not present.

    Args:
        project_path: Path to the project.
        force: Overwrite existing config.

    Returns:
        True if initialized (or already exists).
    """
    from fastband.core.config import FastbandConfig
    from fastband.core.detection import detect_project

    fastband_dir = project_path / ".fastband"
    config_file = fastband_dir / "config.yaml"

    if config_file.exists() and not force:
        return True  # Already initialized

    # Detect project
    try:
        project_info = detect_project(project_path)
    except Exception:
        project_info = None

    # Create config
    config = FastbandConfig()

    # Add detected provider hints
    if project_info:
        from fastband.core.config import AIProviderConfig
        from fastband.core.detection import Language

        if project_info.primary_language == Language.PYTHON:
            config.providers["claude"] = AIProviderConfig(model="claude-sonnet-4-20250514")

    # Save configuration
    fastband_dir.mkdir(parents=True, exist_ok=True)
    config.save(config_file)

    return True


def _validate_project_path(project_path: Path) -> bool:
    """
    Validate that the project path is safe to use.

    Checks:
    - Path doesn't contain path traversal sequences
    - Path is within user-accessible locations
    - Path doesn't point to system directories

    Args:
        project_path: The resolved project path to validate.

    Returns:
        True if path is valid, False otherwise.
    """
    path_str = str(project_path)

    # Check for path traversal patterns
    if ".." in path_str or "%2e" in path_str.lower() or "\x00" in path_str:
        return False

    # Ensure path is within reasonable bounds
    # Allow: home directory, /tmp, /var, or current working directory
    home = Path.home()
    cwd = Path.cwd().resolve()

    allowed_roots = [
        home,
        Path("/tmp"),
        Path("/var"),
        cwd,
    ]

    # On macOS, also allow /Volumes and /private (for resolved symlinks)
    if sys.platform == "darwin":
        allowed_roots.append(Path("/Volumes"))
        allowed_roots.append(Path("/private"))  # /var -> /private/var on macOS

    # Check if project_path is under any allowed root
    for root in allowed_roots:
        try:
            project_path.relative_to(root)
            return True
        except ValueError:
            continue

    return False


def run_setup(
    project_path: Path | None = None,
    force: bool = False,
    skip_validation: bool = False,
    config_type: str = "project",
    verbose: bool = False,
) -> bool:
    """
    Run the full Fastband setup process.

    Args:
        project_path: Path to the project (default: current directory).
        force: Overwrite existing configurations.
        skip_validation: Skip MCP server validation.
        config_type: Type of Claude config to create.
        verbose: Show verbose output.

    Returns:
        True if setup completed successfully.
    """
    from fastband import __version__

    project_path = (project_path or Path.cwd()).resolve()

    # Security: Validate project path
    if not _validate_project_path(project_path):
        console.print("[red]✗[/red] Invalid project path")
        console.print("  Path must be within your home directory or current working directory")
        return False

    console.print(
        Panel.fit(
            f"[bold blue]Fastband Setup[/bold blue] [dim]v{__version__}[/dim]\n"
            f"[dim]{project_path}[/dim]",
            border_style="blue",
        )
    )
    console.print()

    # Step 1: Detect installation
    console.print("[bold]Step 1:[/bold] Detecting installation...")
    install_info = detect_installation()

    if verbose:
        table = Table(show_header=False, box=None)
        table.add_column("Property", style="dim")
        table.add_column("Value")
        table.add_row("Method", install_info.method.value)
        table.add_row("Executable", str(install_info.executable_path))
        if install_info.python_path:
            table.add_row("Python", str(install_info.python_path))
        console.print(table)

    if install_info.method == InstallMethod.UNKNOWN:
        console.print("[red]✗[/red] Could not detect fastband installation")
        console.print("  Make sure fastband is installed and in your PATH")
        return False

    console.print(
        f"[green]✓[/green] Detected: [cyan]{install_info.method.value}[/cyan] "
        f"installation at [dim]{install_info.executable_path}[/dim]"
    )

    # Step 2: Initialize .fastband folder
    console.print("\n[bold]Step 2:[/bold] Initializing project configuration...")
    fastband_dir = project_path / ".fastband"
    config_file = fastband_dir / "config.yaml"

    if config_file.exists() and not force:
        console.print(f"[green]✓[/green] Project already initialized at [dim]{fastband_dir}[/dim]")
    else:
        if init_fastband_config(project_path, force):
            console.print(f"[green]✓[/green] Created [dim]{config_file}[/dim]")
        else:
            console.print("[red]✗[/red] Failed to initialize project configuration")
            return False

    # Step 3: Create Claude MCP config
    console.print("\n[bold]Step 3:[/bold] Configuring Claude Code MCP...")

    try:
        config_path = create_mcp_config(project_path, install_info, config_type)
        console.print(f"[green]✓[/green] Created [dim]{config_path}[/dim]")
    except Exception as e:
        console.print(f"[red]✗[/red] Failed to create MCP config: {e}")
        return False

    # Step 4: Validate (optional)
    if not skip_validation:
        console.print("\n[bold]Step 4:[/bold] Validating MCP server...")
        if validate_mcp_server(install_info):
            console.print("[green]✓[/green] MCP server validated successfully")
        else:
            console.print("[yellow]![/yellow] Could not validate MCP server (non-fatal)")
            console.print("  The server may still work - try it in Claude Code")

    # Success message
    console.print()
    console.print(
        Panel(
            "[bold green]Setup Complete![/bold green]\n\n"
            "Next steps:\n"
            "  1. [bold]Restart Claude Code[/bold] (or reload the window)\n"
            "  2. Open this project in Claude Code\n"
            "  3. Fastband tools will be available automatically\n\n"
            "[dim]Tip: Say 'list available tools' to see Fastband tools[/dim]",
            border_style="green",
            title="✓ Ready",
        )
    )

    return True


def show_mcp_config(project_path: Path | None = None) -> None:
    """
    Show the current MCP configuration.

    Args:
        project_path: Path to the project.
    """
    project_path = (project_path or Path.cwd()).resolve()

    # Check project-level config
    project_config = project_path / ".claude" / "mcp.json"

    console.print("[bold]MCP Configuration Status[/bold]\n")

    if project_config.exists():
        console.print(f"[green]✓[/green] Project config: [dim]{project_config}[/dim]")
        try:
            with open(project_config) as f:
                config = json.load(f)
            if "mcpServers" in config and "fastband" in config["mcpServers"]:
                fb_config = config["mcpServers"]["fastband"]
                console.print(f"  Command: [cyan]{fb_config.get('command')}[/cyan]")
                console.print(f"  Args: [cyan]{fb_config.get('args')}[/cyan]")
            else:
                console.print("  [yellow]Fastband not configured[/yellow]")
        except (json.JSONDecodeError, OSError) as e:
            console.print(f"  [red]Error reading config: {e}[/red]")
    else:
        console.print(f"[dim]✗[/dim] No project config at [dim]{project_config}[/dim]")

    # Check global configs
    paths = get_claude_config_paths()
    for config_type in ["desktop", "global"]:
        config_path = paths.get(config_type)
        if config_path and config_path.exists():
            console.print(
                f"\n[green]✓[/green] {config_type.title()} config: [dim]{config_path}[/dim]"
            )
            try:
                with open(config_path) as f:
                    config = json.load(f)
                if "mcpServers" in config and "fastband" in config["mcpServers"]:
                    fb_config = config["mcpServers"]["fastband"]
                    console.print(f"  Command: [cyan]{fb_config.get('command')}[/cyan]")
                    console.print(f"  Args: [cyan]{fb_config.get('args')}[/cyan]")
                    if "cwd" in fb_config:
                        console.print(f"  CWD: [cyan]{fb_config.get('cwd')}[/cyan]")
            except (json.JSONDecodeError, OSError):
                pass

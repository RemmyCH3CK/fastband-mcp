"""
Git tools - Version control operations for Fastband.

Provides tools for git operations including status, commit, diff, log, and branch management.
"""

import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastband.tools.base import (
    Tool,
    ToolCategory,
    ToolDefinition,
    ToolMetadata,
    ToolParameter,
    ToolResult,
)


def _run_git_command(
    args: list[str],
    cwd: str | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess:
    """
    Run a git command and return the result.

    Args:
        args: Git command arguments (without 'git' prefix)
        cwd: Working directory for the command
        check: If True, raise CalledProcessError on non-zero exit

    Returns:
        CompletedProcess with stdout and stderr

    Raises:
        subprocess.CalledProcessError: If check=True and command fails
        FileNotFoundError: If git is not installed
    """
    cmd = ["git"] + args
    return subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=check,
    )


def _is_git_repository(path: str) -> bool:
    """Check if the given path is inside a git repository."""
    try:
        result = _run_git_command(
            ["rev-parse", "--is-inside-work-tree"],
            cwd=path,
            check=False,
        )
        return result.returncode == 0 and result.stdout.strip() == "true"
    except FileNotFoundError:
        return False


def _get_repo_root(path: str) -> str | None:
    """Get the root directory of the git repository."""
    try:
        result = _run_git_command(
            ["rev-parse", "--show-toplevel"],
            cwd=path,
            check=False,
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return None
    except FileNotFoundError:
        return None


class GitStatusTool(Tool):
    """Show the working tree status."""

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            metadata=ToolMetadata(
                name="git_status",
                description="Show the working tree status including staged, unstaged, and untracked files",
                category=ToolCategory.GIT,
                version="1.0.0",
                requires_filesystem=True,
            ),
            parameters=[
                ToolParameter(
                    name="path",
                    type="string",
                    description="Path to the repository (default: current directory)",
                    required=False,
                    default=".",
                ),
                ToolParameter(
                    name="short",
                    type="boolean",
                    description="Show status in short format (default: false)",
                    required=False,
                    default=False,
                ),
                ToolParameter(
                    name="branch",
                    type="boolean",
                    description="Show branch information (default: true)",
                    required=False,
                    default=True,
                ),
            ],
        )

    async def execute(
        self, path: str = ".", short: bool = False, branch: bool = True, **kwargs
    ) -> ToolResult:
        """Execute git status command."""
        target = Path(path).resolve()

        if not target.exists():
            return ToolResult(success=False, error=f"Path does not exist: {path}")

        if not _is_git_repository(str(target)):
            return ToolResult(success=False, error=f"Not a git repository: {path}")

        try:
            # Build git status arguments
            args = ["status", "--porcelain=v2"]
            if branch:
                args.append("--branch")

            result = _run_git_command(args, cwd=str(target))

            # Parse the porcelain v2 output
            status_data = self._parse_status_output(result.stdout)

            # If short format requested, also get the short output
            if short:
                short_result = _run_git_command(["status", "--short", "--branch"], cwd=str(target))
                status_data["short_output"] = short_result.stdout.strip()

            # Get human-readable status
            human_result = _run_git_command(["status"], cwd=str(target))
            status_data["human_readable"] = human_result.stdout.strip()

            return ToolResult(
                success=True,
                data=status_data,
            )

        except subprocess.CalledProcessError as e:
            return ToolResult(success=False, error=f"Git status failed: {e.stderr.strip()}")
        except FileNotFoundError:
            return ToolResult(success=False, error="Git is not installed or not in PATH")

    def _parse_status_output(self, output: str) -> dict[str, Any]:
        """Parse git status --porcelain=v2 output."""
        staged = []
        unstaged = []
        untracked = []
        branch_info = {}

        for line in output.strip().split("\n"):
            if not line:
                continue

            if line.startswith("# branch."):
                # Branch header line
                parts = line.split(" ", 2)
                key = parts[1].replace("branch.", "")
                value = parts[2] if len(parts) > 2 else ""
                branch_info[key] = value

            elif line.startswith("1 ") or line.startswith("2 "):
                # Ordinary or rename/copy entry
                parts = line.split(" ")
                status = parts[1]
                file_path = parts[-1]

                # First character is staged status, second is unstaged
                if status[0] != ".":
                    staged.append(
                        {
                            "file": file_path,
                            "status": self._status_char_to_name(status[0]),
                        }
                    )
                if status[1] != ".":
                    unstaged.append(
                        {
                            "file": file_path,
                            "status": self._status_char_to_name(status[1]),
                        }
                    )

            elif line.startswith("? "):
                # Untracked file
                file_path = line[2:]
                untracked.append(file_path)

            elif line.startswith("! "):
                # Ignored file (usually not shown)
                pass

        return {
            "branch": branch_info,
            "staged": staged,
            "unstaged": unstaged,
            "untracked": untracked,
            "is_clean": len(staged) == 0 and len(unstaged) == 0 and len(untracked) == 0,
            "total_changes": len(staged) + len(unstaged) + len(untracked),
        }

    def _status_char_to_name(self, char: str) -> str:
        """Convert status character to human-readable name."""
        mapping = {
            "M": "modified",
            "T": "type_changed",
            "A": "added",
            "D": "deleted",
            "R": "renamed",
            "C": "copied",
            "U": "unmerged",
        }
        return mapping.get(char, f"unknown({char})")


class GitCommitTool(Tool):
    """Create a new commit with staged changes."""

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            metadata=ToolMetadata(
                name="git_commit",
                description="Create a new commit with a message. Optionally stage files before committing.",
                category=ToolCategory.GIT,
                version="1.0.0",
                requires_filesystem=True,
            ),
            parameters=[
                ToolParameter(
                    name="message",
                    type="string",
                    description="Commit message (required, must not be empty)",
                    required=True,
                ),
                ToolParameter(
                    name="path",
                    type="string",
                    description="Path to the repository (default: current directory)",
                    required=False,
                    default=".",
                ),
                ToolParameter(
                    name="files",
                    type="array",
                    description="Files to stage before committing. If not specified, commits only already-staged changes.",
                    required=False,
                ),
                ToolParameter(
                    name="all",
                    type="boolean",
                    description="Stage all modified and deleted files before committing (like 'git commit -a')",
                    required=False,
                    default=False,
                ),
                ToolParameter(
                    name="allow_empty",
                    type="boolean",
                    description="Allow creating a commit with no changes (default: false)",
                    required=False,
                    default=False,
                ),
            ],
        )

    async def execute(
        self,
        message: str,
        path: str = ".",
        files: list[str] | None = None,
        all: bool = False,
        allow_empty: bool = False,
        **kwargs,
    ) -> ToolResult:
        """Execute git commit command."""
        target = Path(path).resolve()

        if not target.exists():
            return ToolResult(success=False, error=f"Path does not exist: {path}")

        if not _is_git_repository(str(target)):
            return ToolResult(success=False, error=f"Not a git repository: {path}")

        # Validate commit message
        message = message.strip()
        if not message:
            return ToolResult(success=False, error="Commit message cannot be empty")

        # Best practice: check for reasonable commit message
        if len(message) < 3:
            return ToolResult(
                success=False, error="Commit message is too short (minimum 3 characters)"
            )

        try:
            # Stage files if specified
            if files:
                for file in files:
                    add_result = _run_git_command(
                        ["add", file],
                        cwd=str(target),
                        check=False,
                    )
                    if add_result.returncode != 0:
                        return ToolResult(
                            success=False,
                            error=f"Failed to stage file '{file}': {add_result.stderr.strip()}",
                        )

            # Build commit command
            commit_args = ["commit", "-m", message]

            if all:
                commit_args.insert(1, "-a")

            if allow_empty:
                commit_args.insert(1, "--allow-empty")

            # Check if there are staged changes (unless allow_empty)
            if not allow_empty and not all and not files:
                status_result = _run_git_command(
                    ["diff", "--cached", "--quiet"],
                    cwd=str(target),
                    check=False,
                )
                if status_result.returncode == 0:
                    return ToolResult(
                        success=False,
                        error="No changes staged for commit. Use 'files' to stage files or 'all' to stage all modified files.",
                    )

            # Execute commit
            result = _run_git_command(commit_args, cwd=str(target))

            # Get the commit hash
            hash_result = _run_git_command(["rev-parse", "HEAD"], cwd=str(target))
            commit_hash = hash_result.stdout.strip()

            # Get short log for the commit
            log_result = _run_git_command(["log", "-1", "--oneline"], cwd=str(target))

            return ToolResult(
                success=True,
                data={
                    "commit_hash": commit_hash,
                    "short_hash": commit_hash[:7],
                    "message": message,
                    "summary": log_result.stdout.strip(),
                    "output": result.stdout.strip(),
                },
            )

        except subprocess.CalledProcessError as e:
            return ToolResult(success=False, error=f"Git commit failed: {e.stderr.strip()}")
        except FileNotFoundError:
            return ToolResult(success=False, error="Git is not installed or not in PATH")


class GitDiffTool(Tool):
    """Show changes between commits, commit and working tree, etc."""

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            metadata=ToolMetadata(
                name="git_diff",
                description="Show changes between commits, commit and working tree, or staged changes",
                category=ToolCategory.GIT,
                version="1.0.0",
                requires_filesystem=True,
            ),
            parameters=[
                ToolParameter(
                    name="path",
                    type="string",
                    description="Path to the repository (default: current directory)",
                    required=False,
                    default=".",
                ),
                ToolParameter(
                    name="staged",
                    type="boolean",
                    description="Show only staged changes (--cached)",
                    required=False,
                    default=False,
                ),
                ToolParameter(
                    name="commit",
                    type="string",
                    description="Compare working tree to a specific commit (e.g., 'HEAD~1', commit hash)",
                    required=False,
                ),
                ToolParameter(
                    name="commit_range",
                    type="string",
                    description="Compare two commits (e.g., 'HEAD~3..HEAD', 'main..feature')",
                    required=False,
                ),
                ToolParameter(
                    name="file",
                    type="string",
                    description="Show diff for a specific file only",
                    required=False,
                ),
                ToolParameter(
                    name="stat",
                    type="boolean",
                    description="Show diffstat instead of full diff",
                    required=False,
                    default=False,
                ),
                ToolParameter(
                    name="name_only",
                    type="boolean",
                    description="Show only names of changed files",
                    required=False,
                    default=False,
                ),
            ],
        )

    async def execute(
        self,
        path: str = ".",
        staged: bool = False,
        commit: str | None = None,
        commit_range: str | None = None,
        file: str | None = None,
        stat: bool = False,
        name_only: bool = False,
        **kwargs,
    ) -> ToolResult:
        """Execute git diff command."""
        target = Path(path).resolve()

        if not target.exists():
            return ToolResult(success=False, error=f"Path does not exist: {path}")

        if not _is_git_repository(str(target)):
            return ToolResult(success=False, error=f"Not a git repository: {path}")

        try:
            # Build diff command
            args = ["diff"]

            if staged:
                args.append("--cached")

            if stat:
                args.append("--stat")

            if name_only:
                args.append("--name-only")

            if commit_range:
                args.append(commit_range)
            elif commit:
                args.append(commit)

            if file:
                args.append("--")
                args.append(file)

            result = _run_git_command(args, cwd=str(target))

            # Parse the output
            diff_output = result.stdout

            # Get summary info
            summary_args = ["diff", "--stat", "--summary"]
            if staged:
                summary_args.append("--cached")
            if commit_range:
                summary_args.append(commit_range)
            elif commit:
                summary_args.append(commit)
            if file:
                summary_args.append("--")
                summary_args.append(file)

            summary_result = _run_git_command(summary_args, cwd=str(target))

            # Count changes
            files_changed = 0
            insertions = 0
            deletions = 0

            for line in summary_result.stdout.split("\n"):
                if "files changed" in line or "file changed" in line:
                    parts = line.split(",")
                    for part in parts:
                        part = part.strip()
                        if "file" in part:
                            files_changed = int(part.split()[0])
                        elif "insertion" in part:
                            insertions = int(part.split()[0])
                        elif "deletion" in part:
                            deletions = int(part.split()[0])

            return ToolResult(
                success=True,
                data={
                    "diff": diff_output.strip() if diff_output.strip() else "(no changes)",
                    "summary": summary_result.stdout.strip(),
                    "files_changed": files_changed,
                    "insertions": insertions,
                    "deletions": deletions,
                    "has_changes": bool(diff_output.strip()),
                },
            )

        except subprocess.CalledProcessError as e:
            return ToolResult(success=False, error=f"Git diff failed: {e.stderr.strip()}")
        except FileNotFoundError:
            return ToolResult(success=False, error="Git is not installed or not in PATH")


class GitLogTool(Tool):
    """Show commit history."""

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            metadata=ToolMetadata(
                name="git_log",
                description="Show commit history with various formatting options",
                category=ToolCategory.GIT,
                version="1.0.0",
                requires_filesystem=True,
            ),
            parameters=[
                ToolParameter(
                    name="path",
                    type="string",
                    description="Path to the repository (default: current directory)",
                    required=False,
                    default=".",
                ),
                ToolParameter(
                    name="max_count",
                    type="integer",
                    description="Maximum number of commits to show (default: 10)",
                    required=False,
                    default=10,
                ),
                ToolParameter(
                    name="oneline",
                    type="boolean",
                    description="Show each commit on a single line",
                    required=False,
                    default=False,
                ),
                ToolParameter(
                    name="author",
                    type="string",
                    description="Filter commits by author name or email",
                    required=False,
                ),
                ToolParameter(
                    name="since",
                    type="string",
                    description="Show commits since date (e.g., '2 weeks ago', '2024-01-01')",
                    required=False,
                ),
                ToolParameter(
                    name="until",
                    type="string",
                    description="Show commits until date",
                    required=False,
                ),
                ToolParameter(
                    name="file",
                    type="string",
                    description="Show commits that modified a specific file",
                    required=False,
                ),
                ToolParameter(
                    name="grep",
                    type="string",
                    description="Search for commits with message matching pattern",
                    required=False,
                ),
            ],
        )

    async def execute(
        self,
        path: str = ".",
        max_count: int = 10,
        oneline: bool = False,
        author: str | None = None,
        since: str | None = None,
        until: str | None = None,
        file: str | None = None,
        grep: str | None = None,
        **kwargs,
    ) -> ToolResult:
        """Execute git log command."""
        target = Path(path).resolve()

        if not target.exists():
            return ToolResult(success=False, error=f"Path does not exist: {path}")

        if not _is_git_repository(str(target)):
            return ToolResult(success=False, error=f"Not a git repository: {path}")

        try:
            # Build log command
            args = ["log", f"-{max_count}"]

            if oneline:
                args.append("--oneline")
            else:
                # Use a parseable format
                args.append("--format=%H%n%h%n%an%n%ae%n%ai%n%s%n%b%n---COMMIT_END---")

            if author:
                args.extend(["--author", author])

            if since:
                args.extend(["--since", since])

            if until:
                args.extend(["--until", until])

            if grep:
                args.extend(["--grep", grep])

            if file:
                args.append("--")
                args.append(file)

            result = _run_git_command(args, cwd=str(target))

            if oneline:
                # Simple output
                lines = [l for l in result.stdout.strip().split("\n") if l]
                return ToolResult(
                    success=True,
                    data={
                        "commits": lines,
                        "count": len(lines),
                        "format": "oneline",
                    },
                )
            else:
                # Parse structured output
                commits = self._parse_log_output(result.stdout)
                return ToolResult(
                    success=True,
                    data={
                        "commits": commits,
                        "count": len(commits),
                        "format": "detailed",
                    },
                )

        except subprocess.CalledProcessError as e:
            return ToolResult(success=False, error=f"Git log failed: {e.stderr.strip()}")
        except FileNotFoundError:
            return ToolResult(success=False, error="Git is not installed or not in PATH")

    def _parse_log_output(self, output: str) -> list[dict[str, Any]]:
        """Parse git log output."""
        commits = []
        current_commit = []

        for line in output.split("\n"):
            if line == "---COMMIT_END---":
                if current_commit:
                    commit = self._parse_single_commit(current_commit)
                    if commit:
                        commits.append(commit)
                    current_commit = []
            else:
                current_commit.append(line)

        return commits

    def _parse_single_commit(self, lines: list[str]) -> dict[str, Any] | None:
        """Parse a single commit from lines."""
        if len(lines) < 6:
            return None

        # Lines: hash, short_hash, author_name, author_email, date, subject, body...
        body_lines = lines[6:] if len(lines) > 6 else []
        body = "\n".join(body_lines).strip()

        return {
            "hash": lines[0],
            "short_hash": lines[1],
            "author_name": lines[2],
            "author_email": lines[3],
            "date": lines[4],
            "subject": lines[5],
            "body": body if body else None,
        }


class GitBranchTool(Tool):
    """List, create, or delete branches."""

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            metadata=ToolMetadata(
                name="git_branch",
                description="List, create, or delete git branches",
                category=ToolCategory.GIT,
                version="1.0.0",
                requires_filesystem=True,
            ),
            parameters=[
                ToolParameter(
                    name="path",
                    type="string",
                    description="Path to the repository (default: current directory)",
                    required=False,
                    default=".",
                ),
                ToolParameter(
                    name="action",
                    type="string",
                    description="Action to perform: 'list' (default), 'create', 'delete'",
                    required=False,
                    default="list",
                    enum=["list", "create", "delete"],
                ),
                ToolParameter(
                    name="name",
                    type="string",
                    description="Branch name (required for create/delete actions)",
                    required=False,
                ),
                ToolParameter(
                    name="force",
                    type="boolean",
                    description="Force delete even if branch is not fully merged (use with caution)",
                    required=False,
                    default=False,
                ),
                ToolParameter(
                    name="all",
                    type="boolean",
                    description="List all branches including remote-tracking branches",
                    required=False,
                    default=False,
                ),
                ToolParameter(
                    name="start_point",
                    type="string",
                    description="Starting point for new branch (commit hash, branch name, or tag)",
                    required=False,
                ),
            ],
        )

    async def execute(
        self,
        path: str = ".",
        action: str = "list",
        name: str | None = None,
        force: bool = False,
        all: bool = False,
        start_point: str | None = None,
        **kwargs,
    ) -> ToolResult:
        """Execute git branch command."""
        target = Path(path).resolve()

        if not target.exists():
            return ToolResult(success=False, error=f"Path does not exist: {path}")

        if not _is_git_repository(str(target)):
            return ToolResult(success=False, error=f"Not a git repository: {path}")

        try:
            if action == "list":
                return await self._list_branches(str(target), all)
            elif action == "create":
                if not name:
                    return ToolResult(
                        success=False, error="Branch name is required for 'create' action"
                    )
                return await self._create_branch(str(target), name, start_point)
            elif action == "delete":
                if not name:
                    return ToolResult(
                        success=False, error="Branch name is required for 'delete' action"
                    )
                return await self._delete_branch(str(target), name, force)
            else:
                return ToolResult(success=False, error=f"Unknown action: {action}")

        except subprocess.CalledProcessError as e:
            return ToolResult(success=False, error=f"Git branch failed: {e.stderr.strip()}")
        except FileNotFoundError:
            return ToolResult(success=False, error="Git is not installed or not in PATH")

    async def _list_branches(self, cwd: str, include_all: bool) -> ToolResult:
        """List branches."""
        args = [
            "branch",
            "-v",
            "--format=%(refname:short)%09%(objectname:short)%09%(upstream:short)%09%(HEAD)",
        ]
        if include_all:
            args.insert(1, "-a")

        result = _run_git_command(args, cwd=cwd)

        # Get current branch
        current_result = _run_git_command(["rev-parse", "--abbrev-ref", "HEAD"], cwd=cwd)
        current_branch = current_result.stdout.strip()

        branches = []
        for line in result.stdout.strip().split("\n"):
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) >= 4:
                branch = {
                    "name": parts[0],
                    "short_hash": parts[1],
                    "upstream": parts[2] if parts[2] else None,
                    "is_current": parts[3] == "*",
                }
                branches.append(branch)

        return ToolResult(
            success=True,
            data={
                "current_branch": current_branch,
                "branches": branches,
                "count": len(branches),
            },
        )

    async def _create_branch(self, cwd: str, name: str, start_point: str | None) -> ToolResult:
        """Create a new branch."""
        # Check if branch already exists
        check_result = _run_git_command(
            ["branch", "--list", name],
            cwd=cwd,
            check=False,
        )
        if check_result.stdout.strip():
            return ToolResult(success=False, error=f"Branch '{name}' already exists")

        args = ["branch", name]
        if start_point:
            args.append(start_point)

        _run_git_command(args, cwd=cwd)

        # Get the commit hash for the new branch
        hash_result = _run_git_command(["rev-parse", name], cwd=cwd)

        return ToolResult(
            success=True,
            data={
                "branch": name,
                "commit_hash": hash_result.stdout.strip(),
                "created": True,
                "message": f"Branch '{name}' created successfully",
            },
        )

    async def _delete_branch(self, cwd: str, name: str, force: bool) -> ToolResult:
        """Delete a branch."""
        # Check if trying to delete current branch
        current_result = _run_git_command(["rev-parse", "--abbrev-ref", "HEAD"], cwd=cwd)
        current_branch = current_result.stdout.strip()

        if name == current_branch:
            return ToolResult(
                success=False,
                error=f"Cannot delete the current branch '{name}'. Switch to another branch first.",
            )

        # Check if branch exists
        check_result = _run_git_command(
            ["branch", "--list", name],
            cwd=cwd,
            check=False,
        )
        if not check_result.stdout.strip():
            return ToolResult(success=False, error=f"Branch '{name}' does not exist")

        # Delete the branch
        delete_flag = "-D" if force else "-d"
        try:
            _run_git_command(["branch", delete_flag, name], cwd=cwd)
        except subprocess.CalledProcessError as e:
            if "not fully merged" in e.stderr:
                return ToolResult(
                    success=False,
                    error=f"Branch '{name}' is not fully merged. Use force=true to delete anyway.",
                )
            raise

        return ToolResult(
            success=True,
            data={
                "branch": name,
                "deleted": True,
                "forced": force,
                "message": f"Branch '{name}' deleted successfully",
            },
        )


# All git tools
GIT_TOOLS = [
    GitStatusTool,
    GitCommitTool,
    GitDiffTool,
    GitLogTool,
    GitBranchTool,
]

__all__ = [
    "GitStatusTool",
    "GitCommitTool",
    "GitDiffTool",
    "GitLogTool",
    "GitBranchTool",
    "GIT_TOOLS",
]

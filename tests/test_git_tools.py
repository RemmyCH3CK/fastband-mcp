"""Tests for git tools."""

import os
import subprocess
import tempfile
from pathlib import Path

import pytest

from fastband.tools.base import ToolCategory
from fastband.tools.git import (
    GIT_TOOLS,
    GitBranchTool,
    GitCommitTool,
    GitDiffTool,
    GitLogTool,
    GitStatusTool,
    _get_repo_root,
    _is_git_repository,
    _run_git_command,
)

# =============================================================================
# TEST FIXTURES
# =============================================================================


@pytest.fixture
def temp_git_repo():
    """Create a temporary git repository for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir) / "test_repo"
        repo_path.mkdir()

        # Initialize git repo
        subprocess.run(["git", "init"], cwd=str(repo_path), check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=str(repo_path),
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=str(repo_path),
            check=True,
            capture_output=True,
        )

        # Create an initial commit
        readme = repo_path / "README.md"
        readme.write_text("# Test Repository\n")
        subprocess.run(["git", "add", "."], cwd=str(repo_path), check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            cwd=str(repo_path),
            check=True,
            capture_output=True,
        )

        yield repo_path


@pytest.fixture
def temp_non_git_dir():
    """Create a temporary directory that is not a git repository."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


# =============================================================================
# HELPER FUNCTION TESTS
# =============================================================================


class TestHelperFunctions:
    """Tests for helper functions."""

    def test_is_git_repository_true(self, temp_git_repo):
        """Test _is_git_repository returns True for git repos."""
        assert _is_git_repository(str(temp_git_repo)) is True

    def test_is_git_repository_false(self, temp_non_git_dir):
        """Test _is_git_repository returns False for non-git dirs."""
        assert _is_git_repository(str(temp_non_git_dir)) is False

    def test_get_repo_root(self, temp_git_repo):
        """Test _get_repo_root returns correct path."""
        # Create a subdirectory
        subdir = temp_git_repo / "subdir"
        subdir.mkdir()

        root = _get_repo_root(str(subdir))
        # Use os.path.realpath to handle macOS /var -> /private/var symlink
        assert os.path.realpath(root) == os.path.realpath(str(temp_git_repo))

    def test_get_repo_root_not_git(self, temp_non_git_dir):
        """Test _get_repo_root returns None for non-git dirs."""
        assert _get_repo_root(str(temp_non_git_dir)) is None

    def test_run_git_command(self, temp_git_repo):
        """Test _run_git_command executes successfully."""
        result = _run_git_command(["status"], cwd=str(temp_git_repo))
        assert result.returncode == 0


# =============================================================================
# GIT STATUS TOOL TESTS
# =============================================================================


class TestGitStatusTool:
    """Tests for GitStatusTool."""

    @pytest.fixture
    def tool(self):
        """Create a GitStatusTool instance."""
        return GitStatusTool()

    def test_definition(self, tool):
        """Test tool definition."""
        defn = tool.definition

        assert defn.metadata.name == "git_status"
        assert defn.metadata.category == ToolCategory.GIT
        assert len(defn.parameters) == 3

    @pytest.mark.asyncio
    async def test_status_clean_repo(self, tool, temp_git_repo):
        """Test status on a clean repository."""
        result = await tool.execute(path=str(temp_git_repo))

        assert result.success is True
        assert result.data["is_clean"] is True
        assert result.data["total_changes"] == 0

    @pytest.mark.asyncio
    async def test_status_with_changes(self, tool, temp_git_repo):
        """Test status with uncommitted changes."""
        # Create a new file
        new_file = temp_git_repo / "new_file.txt"
        new_file.write_text("new content")

        result = await tool.execute(path=str(temp_git_repo))

        assert result.success is True
        assert result.data["is_clean"] is False
        assert len(result.data["untracked"]) == 1
        assert "new_file.txt" in result.data["untracked"]

    @pytest.mark.asyncio
    async def test_status_staged_changes(self, tool, temp_git_repo):
        """Test status with staged changes."""
        # Modify and stage README
        readme = temp_git_repo / "README.md"
        readme.write_text("# Modified\n")
        subprocess.run(["git", "add", "README.md"], cwd=str(temp_git_repo), check=True)

        result = await tool.execute(path=str(temp_git_repo))

        assert result.success is True
        assert len(result.data["staged"]) == 1
        assert result.data["staged"][0]["file"] == "README.md"
        assert result.data["staged"][0]["status"] == "modified"

    @pytest.mark.asyncio
    async def test_status_short_format(self, tool, temp_git_repo):
        """Test status with short format."""
        result = await tool.execute(path=str(temp_git_repo), short=True)

        assert result.success is True
        assert "short_output" in result.data

    @pytest.mark.asyncio
    async def test_status_not_git_repo(self, tool, temp_non_git_dir):
        """Test status on non-git directory."""
        result = await tool.execute(path=str(temp_non_git_dir))

        assert result.success is False
        assert "Not a git repository" in result.error

    @pytest.mark.asyncio
    async def test_status_nonexistent_path(self, tool):
        """Test status on nonexistent path."""
        result = await tool.execute(path="/nonexistent/path")

        assert result.success is False
        assert "does not exist" in result.error


# =============================================================================
# GIT COMMIT TOOL TESTS
# =============================================================================


class TestGitCommitTool:
    """Tests for GitCommitTool."""

    @pytest.fixture
    def tool(self):
        """Create a GitCommitTool instance."""
        return GitCommitTool()

    def test_definition(self, tool):
        """Test tool definition."""
        defn = tool.definition

        assert defn.metadata.name == "git_commit"
        assert defn.metadata.category == ToolCategory.GIT
        # message is required
        required_params = [p for p in defn.parameters if p.required]
        assert len(required_params) == 1
        assert required_params[0].name == "message"

    @pytest.mark.asyncio
    async def test_commit_with_staged_files(self, tool, temp_git_repo):
        """Test commit with already staged files."""
        # Create and stage a file
        new_file = temp_git_repo / "file.txt"
        new_file.write_text("content")
        subprocess.run(["git", "add", "file.txt"], cwd=str(temp_git_repo), check=True)

        result = await tool.execute(path=str(temp_git_repo), message="Add new file")

        assert result.success is True
        assert "commit_hash" in result.data
        assert result.data["message"] == "Add new file"
        assert len(result.data["commit_hash"]) == 40  # Full SHA

    @pytest.mark.asyncio
    async def test_commit_with_files_param(self, tool, temp_git_repo):
        """Test commit with files parameter to stage."""
        # Create a file but don't stage it
        new_file = temp_git_repo / "unstaged.txt"
        new_file.write_text("content")

        result = await tool.execute(
            path=str(temp_git_repo), message="Add unstaged file", files=["unstaged.txt"]
        )

        assert result.success is True
        assert "commit_hash" in result.data

    @pytest.mark.asyncio
    async def test_commit_with_all_flag(self, tool, temp_git_repo):
        """Test commit with -a flag."""
        # Modify a tracked file
        readme = temp_git_repo / "README.md"
        readme.write_text("Modified content")

        result = await tool.execute(path=str(temp_git_repo), message="Modify README", all=True)

        assert result.success is True
        assert "commit_hash" in result.data

    @pytest.mark.asyncio
    async def test_commit_empty_message_fails(self, tool, temp_git_repo):
        """Test that empty commit message fails."""
        result = await tool.execute(path=str(temp_git_repo), message="")

        assert result.success is False
        assert "empty" in result.error.lower()

    @pytest.mark.asyncio
    async def test_commit_short_message_fails(self, tool, temp_git_repo):
        """Test that too-short commit message fails."""
        result = await tool.execute(path=str(temp_git_repo), message="ab")

        assert result.success is False
        assert "short" in result.error.lower()

    @pytest.mark.asyncio
    async def test_commit_no_changes_fails(self, tool, temp_git_repo):
        """Test that commit with no staged changes fails."""
        result = await tool.execute(path=str(temp_git_repo), message="No changes commit")

        assert result.success is False
        assert "No changes staged" in result.error

    @pytest.mark.asyncio
    async def test_commit_allow_empty(self, tool, temp_git_repo):
        """Test commit with allow_empty flag."""
        result = await tool.execute(
            path=str(temp_git_repo), message="Empty commit", allow_empty=True
        )

        assert result.success is True
        assert "commit_hash" in result.data

    @pytest.mark.asyncio
    async def test_commit_not_git_repo(self, tool, temp_non_git_dir):
        """Test commit on non-git directory."""
        result = await tool.execute(path=str(temp_non_git_dir), message="Test message")

        assert result.success is False
        assert "Not a git repository" in result.error


# =============================================================================
# GIT DIFF TOOL TESTS
# =============================================================================


class TestGitDiffTool:
    """Tests for GitDiffTool."""

    @pytest.fixture
    def tool(self):
        """Create a GitDiffTool instance."""
        return GitDiffTool()

    def test_definition(self, tool):
        """Test tool definition."""
        defn = tool.definition

        assert defn.metadata.name == "git_diff"
        assert defn.metadata.category == ToolCategory.GIT

    @pytest.mark.asyncio
    async def test_diff_no_changes(self, tool, temp_git_repo):
        """Test diff with no changes."""
        result = await tool.execute(path=str(temp_git_repo))

        assert result.success is True
        assert result.data["has_changes"] is False

    @pytest.mark.asyncio
    async def test_diff_with_changes(self, tool, temp_git_repo):
        """Test diff with unstaged changes."""
        # Modify README
        readme = temp_git_repo / "README.md"
        readme.write_text("Modified content\n")

        result = await tool.execute(path=str(temp_git_repo))

        assert result.success is True
        assert result.data["has_changes"] is True
        assert "Modified content" in result.data["diff"]

    @pytest.mark.asyncio
    async def test_diff_staged(self, tool, temp_git_repo):
        """Test diff for staged changes."""
        # Modify and stage README
        readme = temp_git_repo / "README.md"
        readme.write_text("Staged content\n")
        subprocess.run(["git", "add", "README.md"], cwd=str(temp_git_repo), check=True)

        result = await tool.execute(path=str(temp_git_repo), staged=True)

        assert result.success is True
        assert result.data["has_changes"] is True
        assert "Staged content" in result.data["diff"]

    @pytest.mark.asyncio
    async def test_diff_with_stat(self, tool, temp_git_repo):
        """Test diff with stat output."""
        # Modify README
        readme = temp_git_repo / "README.md"
        readme.write_text("Modified\n")

        result = await tool.execute(path=str(temp_git_repo), stat=True)

        assert result.success is True
        assert "README.md" in result.data["diff"]

    @pytest.mark.asyncio
    async def test_diff_specific_file(self, tool, temp_git_repo):
        """Test diff for specific file."""
        # Create and modify two files
        file1 = temp_git_repo / "file1.txt"
        file2 = temp_git_repo / "file2.txt"
        file1.write_text("file1 content")
        file2.write_text("file2 content")
        subprocess.run(["git", "add", "."], cwd=str(temp_git_repo), check=True)
        subprocess.run(["git", "commit", "-m", "Add files"], cwd=str(temp_git_repo), check=True)

        # Modify only file1
        file1.write_text("modified file1")

        result = await tool.execute(path=str(temp_git_repo), file="file1.txt")

        assert result.success is True
        assert "modified file1" in result.data["diff"]
        assert "file2" not in result.data["diff"]

    @pytest.mark.asyncio
    async def test_diff_not_git_repo(self, tool, temp_non_git_dir):
        """Test diff on non-git directory."""
        result = await tool.execute(path=str(temp_non_git_dir))

        assert result.success is False
        assert "Not a git repository" in result.error


# =============================================================================
# GIT LOG TOOL TESTS
# =============================================================================


class TestGitLogTool:
    """Tests for GitLogTool."""

    @pytest.fixture
    def tool(self):
        """Create a GitLogTool instance."""
        return GitLogTool()

    @pytest.fixture
    def repo_with_history(self, temp_git_repo):
        """Create a repo with multiple commits."""
        for i in range(3):
            file_path = temp_git_repo / f"file{i}.txt"
            file_path.write_text(f"content {i}")
            subprocess.run(["git", "add", "."], cwd=str(temp_git_repo), check=True)
            subprocess.run(
                ["git", "commit", "-m", f"Commit {i + 1}"], cwd=str(temp_git_repo), check=True
            )
        return temp_git_repo

    def test_definition(self, tool):
        """Test tool definition."""
        defn = tool.definition

        assert defn.metadata.name == "git_log"
        assert defn.metadata.category == ToolCategory.GIT

    @pytest.mark.asyncio
    async def test_log_basic(self, tool, repo_with_history):
        """Test basic log output."""
        result = await tool.execute(path=str(repo_with_history))

        assert result.success is True
        assert result.data["count"] == 4  # Initial + 3 commits
        assert result.data["format"] == "detailed"

    @pytest.mark.asyncio
    async def test_log_max_count(self, tool, repo_with_history):
        """Test log with max_count limit."""
        result = await tool.execute(path=str(repo_with_history), max_count=2)

        assert result.success is True
        assert result.data["count"] == 2

    @pytest.mark.asyncio
    async def test_log_oneline(self, tool, repo_with_history):
        """Test log with oneline format."""
        result = await tool.execute(path=str(repo_with_history), oneline=True)

        assert result.success is True
        assert result.data["format"] == "oneline"
        assert isinstance(result.data["commits"], list)

    @pytest.mark.asyncio
    async def test_log_author_filter(self, tool, repo_with_history):
        """Test log filtered by author."""
        result = await tool.execute(path=str(repo_with_history), author="Test User")

        assert result.success is True
        assert result.data["count"] >= 1

    @pytest.mark.asyncio
    async def test_log_grep_filter(self, tool, repo_with_history):
        """Test log filtered by commit message pattern."""
        result = await tool.execute(path=str(repo_with_history), grep="Commit 2")

        assert result.success is True
        assert result.data["count"] >= 1

    @pytest.mark.asyncio
    async def test_log_file_filter(self, tool, repo_with_history):
        """Test log filtered by file."""
        result = await tool.execute(path=str(repo_with_history), file="file1.txt")

        assert result.success is True
        # Should only show commits that touched file1.txt
        assert result.data["count"] >= 1

    @pytest.mark.asyncio
    async def test_log_not_git_repo(self, tool, temp_non_git_dir):
        """Test log on non-git directory."""
        result = await tool.execute(path=str(temp_non_git_dir))

        assert result.success is False
        assert "Not a git repository" in result.error


# =============================================================================
# GIT BRANCH TOOL TESTS
# =============================================================================


class TestGitBranchTool:
    """Tests for GitBranchTool."""

    @pytest.fixture
    def tool(self):
        """Create a GitBranchTool instance."""
        return GitBranchTool()

    def test_definition(self, tool):
        """Test tool definition."""
        defn = tool.definition

        assert defn.metadata.name == "git_branch"
        assert defn.metadata.category == ToolCategory.GIT

        # Check action enum
        action_param = next(p for p in defn.parameters if p.name == "action")
        assert action_param.enum == ["list", "create", "delete"]

    @pytest.mark.asyncio
    async def test_list_branches(self, tool, temp_git_repo):
        """Test listing branches."""
        result = await tool.execute(path=str(temp_git_repo), action="list")

        assert result.success is True
        assert "current_branch" in result.data
        assert "branches" in result.data
        assert result.data["count"] >= 1

    @pytest.mark.asyncio
    async def test_create_branch(self, tool, temp_git_repo):
        """Test creating a new branch."""
        result = await tool.execute(path=str(temp_git_repo), action="create", name="feature-branch")

        assert result.success is True
        assert result.data["branch"] == "feature-branch"
        assert result.data["created"] is True

        # Verify branch exists
        list_result = await tool.execute(path=str(temp_git_repo), action="list")
        branch_names = [b["name"] for b in list_result.data["branches"]]
        assert "feature-branch" in branch_names

    @pytest.mark.asyncio
    async def test_create_branch_with_start_point(self, tool, temp_git_repo):
        """Test creating a branch from specific commit."""
        # Get current HEAD
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=str(temp_git_repo), capture_output=True, text=True
        )
        head_commit = result.stdout.strip()

        result = await tool.execute(
            path=str(temp_git_repo), action="create", name="from-commit", start_point=head_commit
        )

        assert result.success is True
        assert result.data["created"] is True

    @pytest.mark.asyncio
    async def test_create_duplicate_branch_fails(self, tool, temp_git_repo):
        """Test that creating duplicate branch fails."""
        # Create branch first
        await tool.execute(path=str(temp_git_repo), action="create", name="duplicate-branch")

        # Try to create again
        result = await tool.execute(
            path=str(temp_git_repo), action="create", name="duplicate-branch"
        )

        assert result.success is False
        assert "already exists" in result.error

    @pytest.mark.asyncio
    async def test_delete_branch(self, tool, temp_git_repo):
        """Test deleting a branch."""
        # Create a branch first
        await tool.execute(path=str(temp_git_repo), action="create", name="to-delete")

        # Delete the branch
        result = await tool.execute(path=str(temp_git_repo), action="delete", name="to-delete")

        assert result.success is True
        assert result.data["deleted"] is True

    @pytest.mark.asyncio
    async def test_delete_current_branch_fails(self, tool, temp_git_repo):
        """Test that deleting current branch fails."""
        # Get current branch name
        list_result = await tool.execute(path=str(temp_git_repo), action="list")
        current = list_result.data["current_branch"]

        result = await tool.execute(path=str(temp_git_repo), action="delete", name=current)

        assert result.success is False
        assert "Cannot delete the current branch" in result.error

    @pytest.mark.asyncio
    async def test_delete_nonexistent_branch_fails(self, tool, temp_git_repo):
        """Test that deleting nonexistent branch fails."""
        result = await tool.execute(
            path=str(temp_git_repo), action="delete", name="nonexistent-branch"
        )

        assert result.success is False
        assert "does not exist" in result.error

    @pytest.mark.asyncio
    async def test_create_without_name_fails(self, tool, temp_git_repo):
        """Test that create without name fails."""
        result = await tool.execute(path=str(temp_git_repo), action="create")

        assert result.success is False
        assert "required" in result.error.lower()

    @pytest.mark.asyncio
    async def test_delete_without_name_fails(self, tool, temp_git_repo):
        """Test that delete without name fails."""
        result = await tool.execute(path=str(temp_git_repo), action="delete")

        assert result.success is False
        assert "required" in result.error.lower()

    @pytest.mark.asyncio
    async def test_branch_not_git_repo(self, tool, temp_non_git_dir):
        """Test branch on non-git directory."""
        result = await tool.execute(path=str(temp_non_git_dir))

        assert result.success is False
        assert "Not a git repository" in result.error


# =============================================================================
# TOOL EXPORTS TESTS
# =============================================================================


class TestGitToolsExports:
    """Tests for git tools module exports."""

    def test_git_tools_list(self):
        """Test GIT_TOOLS contains all tools."""
        assert len(GIT_TOOLS) == 5
        tool_classes = [GitStatusTool, GitCommitTool, GitDiffTool, GitLogTool, GitBranchTool]
        for tool_class in tool_classes:
            assert tool_class in GIT_TOOLS

    def test_all_tools_have_git_category(self):
        """Test all tools have GIT category."""
        for tool_class in GIT_TOOLS:
            tool = tool_class()
            assert tool.category == ToolCategory.GIT

    def test_all_tools_have_valid_definition(self):
        """Test all tools have valid definitions."""
        for tool_class in GIT_TOOLS:
            tool = tool_class()
            defn = tool.definition

            assert defn.metadata.name is not None
            assert defn.metadata.description is not None
            assert defn.metadata.version is not None

    def test_mcp_schema_generation(self):
        """Test MCP schema can be generated for all tools."""
        for tool_class in GIT_TOOLS:
            tool = tool_class()
            schema = tool.definition.to_mcp_schema()

            assert "name" in schema
            assert "description" in schema
            assert "inputSchema" in schema
            assert schema["inputSchema"]["type"] == "object"


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestGitToolsIntegration:
    """Integration tests for git tools working together."""

    @pytest.mark.asyncio
    async def test_full_workflow(self, temp_git_repo):
        """Test a full git workflow using multiple tools."""
        status_tool = GitStatusTool()
        commit_tool = GitCommitTool()
        log_tool = GitLogTool()
        branch_tool = GitBranchTool()
        diff_tool = GitDiffTool()

        # 1. Check initial status
        status = await status_tool.execute(path=str(temp_git_repo))
        assert status.success is True
        assert status.data["is_clean"] is True

        # 2. Get the default branch name (could be 'master' or 'main')
        default_branch_result = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=str(temp_git_repo),
            capture_output=True,
            text=True,
        )
        default_branch = default_branch_result.stdout.strip()

        # 3. Create and switch to a new branch
        branch_result = await branch_tool.execute(
            path=str(temp_git_repo), action="create", name="feature"
        )
        assert branch_result.success is True

        # Switch to the feature branch (git branch only creates, doesn't switch)
        subprocess.run(
            ["git", "checkout", "feature"], cwd=str(temp_git_repo), capture_output=True, check=True
        )

        # 4. Create and modify a file
        new_file = temp_git_repo / "feature.txt"
        new_file.write_text("Feature content")

        # 5. Check status shows changes
        status = await status_tool.execute(path=str(temp_git_repo))
        assert status.data["is_clean"] is False
        assert len(status.data["untracked"]) == 1

        # 6. Commit the changes
        commit_result = await commit_tool.execute(
            path=str(temp_git_repo), message="Add feature file", files=["feature.txt"]
        )
        assert commit_result.success is True

        # 7. Check log shows new commit
        log_result = await log_tool.execute(path=str(temp_git_repo), max_count=1)
        assert log_result.success is True
        assert log_result.data["commits"][0]["subject"] == "Add feature file"

        # 8. Check diff between branches
        # Switch back to the default branch and check diff
        subprocess.run(
            ["git", "checkout", default_branch], cwd=str(temp_git_repo), capture_output=True
        )

        # Compare the default branch to the feature branch
        diff_result = await diff_tool.execute(
            path=str(temp_git_repo), commit_range=f"{default_branch}..feature"
        )
        assert diff_result.success is True
        assert diff_result.data["has_changes"] is True

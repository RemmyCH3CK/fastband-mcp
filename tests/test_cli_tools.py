"""Tests for Fastband CLI tools subcommand."""

import pytest
from typer.testing import CliRunner

from fastband.cli.main import app
from fastband.tools.base import (
    Tool,
    ToolCategory,
    ToolDefinition,
    ToolMetadata,
    ToolParameter,
    ToolResult,
)
from fastband.tools.registry import get_registry, reset_registry

runner = CliRunner()


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture(autouse=True)
def reset_tools():
    """Reset the tool registry before each test."""
    reset_registry()
    yield
    reset_registry()


@pytest.fixture
def sample_tool():
    """Create a sample tool for testing."""

    class SampleTool(Tool):
        @property
        def definition(self) -> ToolDefinition:
            return ToolDefinition(
                metadata=ToolMetadata(
                    name="sample_tool",
                    description="A sample tool for testing CLI commands",
                    category=ToolCategory.CORE,
                    version="1.0.0",
                    author="Test Author",
                ),
                parameters=[
                    ToolParameter(
                        name="message",
                        type="string",
                        description="A message to process",
                        required=True,
                    ),
                    ToolParameter(
                        name="count",
                        type="integer",
                        description="Number of times to repeat",
                        required=False,
                        default=1,
                    ),
                ],
            )

        async def execute(self, message: str, count: int = 1, **kwargs) -> ToolResult:
            return ToolResult(success=True, data={"message": message * count})

    return SampleTool()


@pytest.fixture
def analysis_tool():
    """Create an analysis tool (non-core, can be unloaded)."""

    class AnalysisTool(Tool):
        @property
        def definition(self) -> ToolDefinition:
            return ToolDefinition(
                metadata=ToolMetadata(
                    name="analysis_tool",
                    description="An analysis tool for testing",
                    category=ToolCategory.ANALYSIS,
                    version="2.0.0",
                    author="Analysis Team",
                    memory_intensive=True,
                    network_required=True,
                ),
                parameters=[],
            )

        async def execute(self, **kwargs) -> ToolResult:
            return ToolResult(success=True, data="analysis complete")

    return AnalysisTool()


@pytest.fixture
def registry_with_tools(sample_tool, analysis_tool):
    """Set up registry with sample tools."""
    registry = get_registry()
    registry.register(sample_tool)
    registry.register(analysis_tool)
    return registry


# =============================================================================
# HELP TESTS
# =============================================================================


class TestToolsHelp:
    """Tests for tools help output."""

    def test_tools_help(self):
        """Test tools command help."""
        result = runner.invoke(app, ["tools", "--help"])
        assert result.exit_code == 0
        assert "list" in result.stdout
        assert "load" in result.stdout
        assert "unload" in result.stdout
        assert "info" in result.stdout
        assert "stats" in result.stdout

    def test_tools_list_help(self):
        """Test tools list command help."""
        result = runner.invoke(app, ["tools", "list", "--help"])
        assert result.exit_code == 0
        assert "category" in result.stdout.lower()
        assert "active" in result.stdout.lower()

    def test_tools_load_help(self):
        """Test tools load command help."""
        result = runner.invoke(app, ["tools", "load", "--help"])
        assert result.exit_code == 0
        assert "name" in result.stdout.lower()

    def test_tools_unload_help(self):
        """Test tools unload command help."""
        result = runner.invoke(app, ["tools", "unload", "--help"])
        assert result.exit_code == 0
        assert "force" in result.stdout.lower()

    def test_tools_info_help(self):
        """Test tools info command help."""
        result = runner.invoke(app, ["tools", "info", "--help"])
        assert result.exit_code == 0
        assert "name" in result.stdout.lower()

    def test_tools_stats_help(self):
        """Test tools stats command help."""
        result = runner.invoke(app, ["tools", "stats", "--help"])
        assert result.exit_code == 0
        assert "verbose" in result.stdout.lower()


# =============================================================================
# LIST COMMAND TESTS
# =============================================================================


class TestToolsListCommand:
    """Tests for tools list command."""

    def test_list_empty_registry(self):
        """Test listing with no tools."""
        result = runner.invoke(app, ["tools", "list"])
        assert result.exit_code == 0
        assert "no tools found" in result.stdout.lower()

    def test_list_shows_tools(self, registry_with_tools):
        """Test listing shows registered tools."""
        result = runner.invoke(app, ["tools", "list"])
        assert result.exit_code == 0
        assert "sample_tool" in result.stdout
        assert "analysis_tool" in result.stdout

    def test_list_shows_status(self, registry_with_tools):
        """Test listing shows load status."""
        registry_with_tools.load("sample_tool")
        result = runner.invoke(app, ["tools", "list"])
        assert result.exit_code == 0
        assert "Loaded" in result.stdout
        assert "Available" in result.stdout

    def test_list_active_only(self, registry_with_tools):
        """Test listing only active tools."""
        registry_with_tools.load("sample_tool")
        result = runner.invoke(app, ["tools", "list", "--active"])
        assert result.exit_code == 0
        assert "sample_tool" in result.stdout
        assert "analysis_tool" not in result.stdout

    def test_list_available_only(self, registry_with_tools):
        """Test listing only available (unloaded) tools."""
        registry_with_tools.load("sample_tool")
        result = runner.invoke(app, ["tools", "list", "--available"])
        assert result.exit_code == 0
        assert "sample_tool" not in result.stdout
        assert "analysis_tool" in result.stdout

    def test_list_filter_by_category(self, registry_with_tools):
        """Test filtering tools by category."""
        result = runner.invoke(app, ["tools", "list", "--category", "core"])
        assert result.exit_code == 0
        assert "sample_tool" in result.stdout
        assert "analysis_tool" not in result.stdout

    def test_list_invalid_category(self, registry_with_tools):
        """Test filtering with invalid category."""
        result = runner.invoke(app, ["tools", "list", "--category", "invalid"])
        assert result.exit_code == 1
        assert "invalid category" in result.stdout.lower()

    def test_list_shows_summary(self, registry_with_tools):
        """Test list shows summary counts."""
        registry_with_tools.load("sample_tool")
        result = runner.invoke(app, ["tools", "list"])
        assert result.exit_code == 0
        assert "Active:" in result.stdout
        assert "Available:" in result.stdout


# =============================================================================
# LOAD COMMAND TESTS
# =============================================================================


class TestToolsLoadCommand:
    """Tests for tools load command."""

    def test_load_tool(self, registry_with_tools):
        """Test loading a tool."""
        result = runner.invoke(app, ["tools", "load", "sample_tool"])
        assert result.exit_code == 0
        assert "loaded" in result.stdout.lower()
        assert registry_with_tools.is_loaded("sample_tool")

    def test_load_shows_details(self, registry_with_tools):
        """Test load shows category and time."""
        result = runner.invoke(app, ["tools", "load", "sample_tool"])
        assert result.exit_code == 0
        assert "Category:" in result.stdout
        assert "Load time:" in result.stdout

    def test_load_already_loaded(self, registry_with_tools):
        """Test loading already loaded tool."""
        registry_with_tools.load("sample_tool")
        result = runner.invoke(app, ["tools", "load", "sample_tool"])
        assert result.exit_code == 0
        assert "already loaded" in result.stdout.lower()

    def test_load_nonexistent_tool(self, registry_with_tools):
        """Test loading nonexistent tool."""
        result = runner.invoke(app, ["tools", "load", "nonexistent_tool"])
        assert result.exit_code == 1
        assert "not found" in result.stdout.lower()

    def test_load_suggests_similar(self, registry_with_tools):
        """Test load suggests similar tools."""
        result = runner.invoke(app, ["tools", "load", "sample"])
        assert result.exit_code == 1
        assert "did you mean" in result.stdout.lower()
        assert "sample_tool" in result.stdout


# =============================================================================
# UNLOAD COMMAND TESTS
# =============================================================================


class TestToolsUnloadCommand:
    """Tests for tools unload command."""

    def test_unload_tool(self, registry_with_tools):
        """Test unloading a non-core tool."""
        registry_with_tools.load("analysis_tool")
        result = runner.invoke(app, ["tools", "unload", "analysis_tool"])
        assert result.exit_code == 0
        assert "unloaded" in result.stdout.lower()
        assert not registry_with_tools.is_loaded("analysis_tool")

    def test_unload_not_loaded(self, registry_with_tools):
        """Test unloading a tool that isn't loaded."""
        result = runner.invoke(app, ["tools", "unload", "analysis_tool"])
        assert result.exit_code == 0
        assert "not loaded" in result.stdout.lower()

    def test_unload_nonexistent(self, registry_with_tools):
        """Test unloading nonexistent tool."""
        result = runner.invoke(app, ["tools", "unload", "nonexistent"])
        assert result.exit_code == 1
        assert "not found" in result.stdout.lower()

    def test_unload_core_tool_blocked(self, registry_with_tools):
        """Test unloading core tool is blocked."""
        registry_with_tools.load("sample_tool")
        result = runner.invoke(app, ["tools", "unload", "sample_tool"])
        assert result.exit_code == 1
        assert "cannot unload core" in result.stdout.lower()

    def test_unload_core_with_force(self, registry_with_tools):
        """Test force unloading core tool."""
        registry_with_tools.load("sample_tool")
        result = runner.invoke(app, ["tools", "unload", "sample_tool", "--force"])
        assert result.exit_code == 0
        assert "force unloaded" in result.stdout.lower()
        assert "warning" in result.stdout.lower()


# =============================================================================
# INFO COMMAND TESTS
# =============================================================================


class TestToolsInfoCommand:
    """Tests for tools info command."""

    def test_info_shows_metadata(self, registry_with_tools):
        """Test info shows tool metadata."""
        result = runner.invoke(app, ["tools", "info", "sample_tool"])
        assert result.exit_code == 0
        assert "sample_tool" in result.stdout
        assert "A sample tool for testing" in result.stdout
        assert "1.0.0" in result.stdout
        assert "Test Author" in result.stdout

    def test_info_shows_parameters(self, registry_with_tools):
        """Test info shows tool parameters."""
        result = runner.invoke(app, ["tools", "info", "sample_tool"])
        assert result.exit_code == 0
        assert "message" in result.stdout
        assert "count" in result.stdout
        assert "string" in result.stdout
        assert "integer" in result.stdout

    def test_info_shows_status(self, registry_with_tools):
        """Test info shows load status."""
        result = runner.invoke(app, ["tools", "info", "sample_tool"])
        assert result.exit_code == 0
        assert "Not Loaded" in result.stdout

        registry_with_tools.load("sample_tool")
        result = runner.invoke(app, ["tools", "info", "sample_tool"])
        assert result.exit_code == 0
        assert "Loaded" in result.stdout

    def test_info_shows_resource_hints(self, registry_with_tools):
        """Test info shows resource hints."""
        result = runner.invoke(app, ["tools", "info", "analysis_tool"])
        assert result.exit_code == 0
        assert "Memory Intensive" in result.stdout
        assert "Network Required" in result.stdout

    def test_info_nonexistent_tool(self, registry_with_tools):
        """Test info for nonexistent tool."""
        result = runner.invoke(app, ["tools", "info", "nonexistent"])
        assert result.exit_code == 1
        assert "not found" in result.stdout.lower()


# =============================================================================
# STATS COMMAND TESTS
# =============================================================================


class TestToolsStatsCommand:
    """Tests for tools stats command."""

    def test_stats_shows_overview(self, registry_with_tools):
        """Test stats shows overview."""
        registry_with_tools.load("sample_tool")
        result = runner.invoke(app, ["tools", "stats"])
        assert result.exit_code == 0
        assert "Active Tools" in result.stdout
        assert "Available Tools" in result.stdout
        assert "Max Recommended" in result.stdout

    def test_stats_shows_status(self, registry_with_tools):
        """Test stats shows performance status."""
        result = runner.invoke(app, ["tools", "stats"])
        assert result.exit_code == 0
        assert "OPTIMAL" in result.stdout.upper()

    def test_stats_shows_categories(self, registry_with_tools):
        """Test stats shows category breakdown."""
        registry_with_tools.load("sample_tool")
        result = runner.invoke(app, ["tools", "stats"])
        assert result.exit_code == 0
        assert "core" in result.stdout.lower()

    def test_stats_verbose(self, registry_with_tools):
        """Test stats verbose mode."""
        result = runner.invoke(app, ["tools", "stats", "--verbose"])
        assert result.exit_code == 0
        # Should show per-tool stats section or message
        assert "No execution statistics" in result.stdout or "Per-Tool" in result.stdout

    def test_stats_empty_registry(self):
        """Test stats with empty registry."""
        result = runner.invoke(app, ["tools", "stats"])
        assert result.exit_code == 0
        assert "Active Tools" in result.stdout
        # Should show 0 for counts


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestToolsIntegration:
    """Integration tests for tools CLI workflow."""

    def test_full_workflow(self, registry_with_tools):
        """Test complete load/info/unload workflow."""
        # List shows available tools
        result = runner.invoke(app, ["tools", "list"])
        assert "sample_tool" in result.stdout
        assert "analysis_tool" in result.stdout

        # Load a tool
        result = runner.invoke(app, ["tools", "load", "analysis_tool"])
        assert result.exit_code == 0

        # Check info
        result = runner.invoke(app, ["tools", "info", "analysis_tool"])
        assert "Loaded" in result.stdout

        # Check stats
        result = runner.invoke(app, ["tools", "stats"])
        assert "1" in result.stdout  # At least 1 active

        # Unload the tool
        result = runner.invoke(app, ["tools", "unload", "analysis_tool"])
        assert result.exit_code == 0

        # Verify unloaded
        result = runner.invoke(app, ["tools", "info", "analysis_tool"])
        assert "Not Loaded" in result.stdout

    def test_main_help_includes_tools(self):
        """Test main help includes tools command."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "tools" in result.stdout

"""Tests for the MCP server engine."""

import pytest

from fastband.core.engine import FastbandEngine, create_engine
from fastband.tools.base import Tool, ToolCategory, ToolDefinition, ToolMetadata, ToolResult
from fastband.tools.registry import reset_registry


@pytest.fixture(autouse=True)
def clean_registry():
    """Reset the registry before each test."""
    reset_registry()
    yield
    reset_registry()


@pytest.fixture
def temp_project(temp_project_with_security):
    """Alias for temp_project_with_security from conftest.py."""
    return temp_project_with_security


@pytest.fixture
def custom_tool():
    """Create a custom tool for testing."""

    class CustomTool(Tool):
        @property
        def definition(self) -> ToolDefinition:
            return ToolDefinition(
                metadata=ToolMetadata(
                    name="custom_tool",
                    description="A custom tool",
                    category=ToolCategory.ANALYSIS,
                ),
                parameters=[],
            )

        async def execute(self, **kwargs) -> ToolResult:
            return ToolResult(success=True, data="custom result")

    return CustomTool()


class TestFastbandEngine:
    """Tests for FastbandEngine."""

    def test_create_engine(self, temp_project):
        """Test engine creation."""
        engine = FastbandEngine(project_path=temp_project)

        assert engine.project_path == temp_project
        assert engine.config is not None
        assert engine.registry is not None

    def test_register_core_tools(self, temp_project):
        """Test registering core tools."""
        engine = FastbandEngine(project_path=temp_project)
        engine.register_core_tools()

        # Should have health_check and other core tools
        assert engine.registry.is_loaded("health_check")
        assert engine.registry.is_loaded("list_files")
        assert engine.registry.is_loaded("read_file")

    def test_register_custom_tool(self, temp_project, custom_tool):
        """Test registering a custom tool."""
        engine = FastbandEngine(project_path=temp_project)
        engine.register_tool(custom_tool)

        assert engine.registry.is_loaded("custom_tool")

    @pytest.mark.asyncio
    async def test_execute_tool(self, temp_project, custom_tool):
        """Test executing a tool through engine."""
        engine = FastbandEngine(project_path=temp_project)
        engine.register_tool(custom_tool)

        result = await engine.execute_tool("custom_tool")

        assert result.success is True
        assert result.data == "custom result"

    def test_get_tool_schemas(self, temp_project):
        """Test getting tool schemas."""
        engine = FastbandEngine(project_path=temp_project)
        engine.register_core_tools()

        schemas = engine.get_tool_schemas()

        assert len(schemas) > 0
        assert all("name" in s for s in schemas)
        assert all("description" in s for s in schemas)

    def test_get_openai_schemas(self, temp_project):
        """Test getting OpenAI function schemas."""
        engine = FastbandEngine(project_path=temp_project)
        engine.register_core_tools()

        schemas = engine.get_openai_schemas()

        assert len(schemas) > 0
        assert all(s["type"] == "function" for s in schemas)


class TestCreateEngine:
    """Tests for create_engine helper."""

    def test_create_with_core_tools(self, temp_project):
        """Test creating engine with core tools."""
        engine = create_engine(project_path=temp_project, load_core=True)

        assert engine.registry.is_loaded("health_check")

    def test_create_without_core_tools(self, temp_project):
        """Test creating engine without core tools."""
        engine = create_engine(project_path=temp_project, load_core=False)

        assert len(engine.registry.get_active_tools()) == 0


class TestEngineIntegration:
    """Integration tests for the engine."""

    @pytest.mark.asyncio
    async def test_full_workflow(self, temp_project):
        """Test a full workflow through the engine."""
        # Create engine with core tools
        engine = create_engine(project_path=temp_project, load_core=True)

        # Execute health check
        health_result = await engine.execute_tool("health_check")
        assert health_result.success is True
        assert health_result.data["status"] == "healthy"

        # Create a test file
        test_file = temp_project / "test.txt"
        write_result = await engine.execute_tool(
            "write_file",
            path=str(test_file),
            content="Hello from engine test!",
        )
        assert write_result.success is True

        # Read the file back
        read_result = await engine.execute_tool(
            "read_file",
            path=str(test_file),
        )
        assert read_result.success is True
        assert "Hello from engine test!" in read_result.data["content"]

        # List files
        list_result = await engine.execute_tool(
            "list_files",
            path=str(temp_project),
        )
        assert list_result.success is True
        assert list_result.data["total_files"] >= 1

    @pytest.mark.asyncio
    async def test_error_handling(self, temp_project):
        """Test error handling in the engine."""
        engine = create_engine(project_path=temp_project, load_core=True)

        # Try to read a non-existent file (within allowed paths)
        nonexistent = temp_project / "nonexistent_file.txt"
        result = await engine.execute_tool(
            "read_file",
            path=str(nonexistent),
        )

        assert result.success is False
        assert "not exist" in result.error.lower() or "error" in result.error.lower()

    @pytest.mark.asyncio
    async def test_tool_not_found(self, temp_project):
        """Test executing a non-existent tool."""
        engine = create_engine(project_path=temp_project, load_core=True)

        result = await engine.execute_tool("nonexistent_tool")

        assert result.success is False
        assert "not loaded" in result.error.lower()

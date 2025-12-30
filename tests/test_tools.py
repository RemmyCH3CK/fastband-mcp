"""Tests for the tool system."""

import pytest

from fastband.tools.base import (
    Tool,
    ToolCategory,
    ToolDefinition,
    ToolMetadata,
    ToolParameter,
    ToolResult,
    tool,
)
from fastband.tools.registry import ToolRegistry, reset_registry

# =============================================================================
# TEST FIXTURES
# =============================================================================


@pytest.fixture
def registry():
    """Create a fresh registry for each test."""
    reset_registry()
    return ToolRegistry()


@pytest.fixture
def sample_tool():
    """Create a sample tool for testing."""

    class SampleTool(Tool):
        @property
        def definition(self) -> ToolDefinition:
            return ToolDefinition(
                metadata=ToolMetadata(
                    name="sample_tool",
                    description="A sample tool for testing",
                    category=ToolCategory.CORE,
                ),
                parameters=[
                    ToolParameter(
                        name="message",
                        type="string",
                        description="A message to echo",
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
            return ToolResult(
                success=True,
                data={"message": message * count},
            )

    return SampleTool()


@pytest.fixture
def failing_tool():
    """Create a tool that always fails."""

    class FailingTool(Tool):
        @property
        def definition(self) -> ToolDefinition:
            return ToolDefinition(
                metadata=ToolMetadata(
                    name="failing_tool",
                    description="A tool that always fails",
                    category=ToolCategory.CORE,
                ),
                parameters=[],
            )

        async def execute(self, **kwargs) -> ToolResult:
            raise ValueError("This tool always fails")

    return FailingTool()


# =============================================================================
# TOOL DEFINITION TESTS
# =============================================================================


class TestToolDefinition:
    """Tests for ToolDefinition."""

    def test_to_mcp_schema(self, sample_tool):
        """Test MCP schema generation."""
        schema = sample_tool.definition.to_mcp_schema()

        assert schema["name"] == "sample_tool"
        assert "description" in schema
        assert "inputSchema" in schema
        assert schema["inputSchema"]["type"] == "object"
        assert "message" in schema["inputSchema"]["properties"]
        assert "count" in schema["inputSchema"]["properties"]
        assert "message" in schema["inputSchema"]["required"]
        assert "count" not in schema["inputSchema"]["required"]

    def test_to_openai_schema(self, sample_tool):
        """Test OpenAI function schema generation."""
        schema = sample_tool.definition.to_openai_schema()

        assert schema["type"] == "function"
        assert schema["function"]["name"] == "sample_tool"
        assert "parameters" in schema["function"]


class TestToolParameter:
    """Tests for ToolParameter."""

    def test_to_json_schema(self):
        """Test JSON schema generation."""
        param = ToolParameter(
            name="test_param",
            type="string",
            description="A test parameter",
            required=True,
            enum=["option1", "option2"],
        )

        schema = param.to_json_schema()

        assert schema["type"] == "string"
        assert schema["description"] == "A test parameter"
        assert schema["enum"] == ["option1", "option2"]


# =============================================================================
# TOOL EXECUTION TESTS
# =============================================================================


class TestToolExecution:
    """Tests for tool execution."""

    @pytest.mark.asyncio
    async def test_execute_success(self, sample_tool):
        """Test successful tool execution."""
        result = await sample_tool.execute(message="hello")

        assert result.success is True
        assert result.data["message"] == "hello"

    @pytest.mark.asyncio
    async def test_execute_with_params(self, sample_tool):
        """Test tool execution with parameters."""
        result = await sample_tool.execute(message="hi", count=3)

        assert result.success is True
        assert result.data["message"] == "hihihi"

    @pytest.mark.asyncio
    async def test_safe_execute_validates(self, sample_tool):
        """Test that safe_execute validates parameters."""
        result = await sample_tool.safe_execute()  # Missing required param

        assert result.success is False
        assert "message" in result.error

    @pytest.mark.asyncio
    async def test_safe_execute_catches_errors(self, failing_tool):
        """Test that safe_execute catches exceptions."""
        result = await failing_tool.safe_execute()

        assert result.success is False
        assert "fails" in result.error

    @pytest.mark.asyncio
    async def test_execution_time_tracked(self, sample_tool):
        """Test that execution time is tracked."""
        result = await sample_tool.safe_execute(message="test")

        assert result.execution_time_ms > 0


class TestToolResult:
    """Tests for ToolResult."""

    def test_to_dict_success(self):
        """Test converting successful result to dict."""
        result = ToolResult(success=True, data={"key": "value"})
        d = result.to_dict()

        assert d["success"] is True
        assert d["data"] == {"key": "value"}
        assert "error" not in d

    def test_to_dict_failure(self):
        """Test converting failed result to dict."""
        result = ToolResult(success=False, error="Something went wrong")
        d = result.to_dict()

        assert d["success"] is False
        assert d["error"] == "Something went wrong"

    def test_to_mcp_content(self):
        """Test MCP content generation."""
        result = ToolResult(success=True, data="Hello, World!")
        content = result.to_mcp_content()

        assert len(content) == 1
        assert content[0]["type"] == "text"
        assert content[0]["text"] == "Hello, World!"


# =============================================================================
# TOOL REGISTRY TESTS
# =============================================================================


class TestToolRegistry:
    """Tests for ToolRegistry."""

    def test_register_tool(self, registry, sample_tool):
        """Test registering a tool."""
        registry.register(sample_tool)

        assert registry.is_registered("sample_tool")
        assert not registry.is_loaded("sample_tool")

    def test_load_tool(self, registry, sample_tool):
        """Test loading a registered tool."""
        registry.register(sample_tool)
        status = registry.load("sample_tool")

        assert status.loaded is True
        assert registry.is_loaded("sample_tool")
        assert status.load_time_ms >= 0

    def test_load_unregistered_tool(self, registry):
        """Test loading an unregistered tool."""
        status = registry.load("nonexistent")

        assert status.loaded is False
        assert "not found" in status.error

    def test_unload_tool(self, registry):
        """Test unloading a tool."""

        # Create a non-core tool that can be unloaded
        class AnalysisTool(Tool):
            @property
            def definition(self) -> ToolDefinition:
                return ToolDefinition(
                    metadata=ToolMetadata(
                        name="analysis_tool",
                        description="An analysis tool",
                        category=ToolCategory.ANALYSIS,
                    ),
                    parameters=[],
                )

            async def execute(self, **kwargs) -> ToolResult:
                return ToolResult(success=True, data="ok")

        tool = AnalysisTool()
        registry.register(tool)
        registry.load("analysis_tool")

        assert registry.unload("analysis_tool") is True
        assert not registry.is_loaded("analysis_tool")

    def test_cannot_unload_core_tool(self, registry, sample_tool):
        """Test that core tools cannot be unloaded."""
        registry.register(sample_tool)
        registry.load("sample_tool")

        assert registry.unload("sample_tool") is False

    def test_get_active_tools(self, registry, sample_tool):
        """Test getting active tools."""
        registry.register(sample_tool)
        registry.load("sample_tool")

        active = registry.get_active_tools()

        assert len(active) == 1
        assert active[0].name == "sample_tool"

    @pytest.mark.asyncio
    async def test_execute_tool(self, registry, sample_tool):
        """Test executing a tool through the registry."""
        registry.register(sample_tool)
        registry.load("sample_tool")

        result = await registry.execute("sample_tool", message="test")

        assert result.success is True
        assert result.data["message"] == "test"

    @pytest.mark.asyncio
    async def test_execute_unloaded_tool(self, registry, sample_tool):
        """Test executing an unloaded tool."""
        registry.register(sample_tool)  # Not loaded

        result = await registry.execute("sample_tool", message="test")

        assert result.success is False
        assert "not loaded" in result.error

    def test_get_mcp_tools(self, registry, sample_tool):
        """Test getting MCP tool schemas."""
        registry.register(sample_tool)
        registry.load("sample_tool")

        schemas = registry.get_mcp_tools()

        assert len(schemas) == 1
        assert schemas[0]["name"] == "sample_tool"

    def test_performance_report(self, registry, sample_tool):
        """Test performance report generation."""
        registry.register(sample_tool)
        registry.load("sample_tool")

        report = registry.get_performance_report()

        assert report.active_tools == 1
        assert report.available_tools == 1
        assert report.status == "optimal"


# =============================================================================
# TOOL DECORATOR TESTS
# =============================================================================


class TestToolDecorator:
    """Tests for the @tool decorator."""

    @pytest.mark.asyncio
    async def test_decorated_function(self):
        """Test creating a tool from decorated function."""

        @tool("greet", "Greet someone", category=ToolCategory.CORE)
        async def greet(name: str = "World") -> ToolResult:
            return ToolResult(success=True, data=f"Hello, {name}!")

        assert greet.name == "greet"
        assert greet.category == ToolCategory.CORE

        result = await greet.execute(name="Test")
        assert result.success is True
        assert result.data == "Hello, Test!"


# =============================================================================
# CORE TOOLS TESTS
# =============================================================================


class TestCoreTool:
    """Tests for core tools."""

    @pytest.mark.asyncio
    async def test_health_check(self):
        """Test health check tool."""
        from fastband.tools.core.system import HealthCheckTool

        tool = HealthCheckTool()
        result = await tool.execute()

        assert result.success is True
        assert result.data["status"] == "healthy"
        assert "fastband" in result.data
        assert "system" in result.data

    @pytest.mark.asyncio
    async def test_get_version(self):
        """Test get version tool."""
        from fastband.tools.core.system import GetVersionTool

        tool = GetVersionTool()
        result = await tool.execute()

        assert result.success is True
        assert "fastband_mcp" in result.data
        assert "python" in result.data

    @pytest.mark.asyncio
    async def test_list_files(self, temp_dir_with_security):
        """Test list files tool."""
        from fastband.tools.core.files import ListFilesTool

        temp_dir = temp_dir_with_security
        # Create some test files
        (temp_dir / "file1.txt").write_text("test")
        (temp_dir / "file2.py").write_text("test")
        (temp_dir / "subdir").mkdir()

        tool = ListFilesTool()
        result = await tool.execute(path=str(temp_dir))

        assert result.success is True
        assert result.data["total_files"] == 2
        assert result.data["total_directories"] == 1

    @pytest.mark.asyncio
    async def test_read_file(self, temp_dir_with_security):
        """Test read file tool."""
        from fastband.tools.core.files import ReadFileTool

        temp_dir = temp_dir_with_security
        test_file = temp_dir / "test.txt"
        test_file.write_text("Line 1\nLine 2\nLine 3\n")

        tool = ReadFileTool()
        result = await tool.execute(path=str(test_file))

        assert result.success is True
        assert "Line 1" in result.data["content"]
        assert result.data["total_lines"] == 3

    @pytest.mark.asyncio
    async def test_write_file(self, temp_dir_with_security):
        """Test write file tool."""
        from fastband.tools.core.files import WriteFileTool

        temp_dir = temp_dir_with_security
        test_file = temp_dir / "new_file.txt"

        tool = WriteFileTool()
        result = await tool.execute(
            path=str(test_file),
            content="Hello, World!",
        )

        assert result.success is True
        assert result.data["created"] is True
        assert test_file.read_text() == "Hello, World!"

    @pytest.mark.asyncio
    async def test_search_code(self, temp_dir_with_security):
        """Test search code tool."""
        from fastband.tools.core.files import SearchCodeTool

        temp_dir = temp_dir_with_security
        # Create a Python file with some content
        test_file = temp_dir / "test.py"
        test_file.write_text("def hello():\n    print('Hello')\n")

        tool = SearchCodeTool()
        result = await tool.execute(
            pattern="def hello",
            path=str(temp_dir),
        )

        assert result.success is True
        assert result.data["total_matches"] >= 1
        assert "test.py" in result.data["matches"][0]["file"]

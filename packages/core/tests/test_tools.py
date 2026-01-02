"""
Tests for Core tools module.

Verifies:
1. Tool types are importable
2. Tool base class works correctly
3. ToolRegistry manages tools properly
4. Lazy loading functions correctly
5. No forbidden imports
"""

import ast
from pathlib import Path

import pytest


class TestToolsImportable:
    """Test that tools modules are importable."""

    def test_import_base(self) -> None:
        """Base module should be importable."""
        from fastband_core.tools import base

        assert hasattr(base, "ToolCategory")
        assert hasattr(base, "ProjectType")
        assert hasattr(base, "ToolParameter")
        assert hasattr(base, "ToolMetadata")
        assert hasattr(base, "ToolDefinition")
        assert hasattr(base, "ToolResult")
        assert hasattr(base, "ToolBase")
        assert hasattr(base, "Tool")
        assert hasattr(base, "tool")

    def test_import_registry(self) -> None:
        """Registry module should be importable."""
        from fastband_core.tools import registry

        assert hasattr(registry, "ToolLoadStatus")
        assert hasattr(registry, "LazyToolSpec")
        assert hasattr(registry, "PerformanceReport")
        assert hasattr(registry, "ToolExecutionStats")
        assert hasattr(registry, "ToolRegistryBase")
        assert hasattr(registry, "ToolRegistry")

    def test_import_from_tools(self) -> None:
        """All exports should be importable from tools module."""
        from fastband_core import tools

        for name in tools.__all__:
            assert hasattr(tools, name), f"Missing export: {name}"

    def test_import_from_root(self) -> None:
        """Common tool exports should be importable from package root."""
        import fastband_core

        assert hasattr(fastband_core, "Tool")
        assert hasattr(fastband_core, "ToolBase")
        assert hasattr(fastband_core, "ToolCategory")
        assert hasattr(fastband_core, "ToolDefinition")
        assert hasattr(fastband_core, "ToolResult")
        assert hasattr(fastband_core, "ToolRegistry")


class TestToolCategory:
    """Test ToolCategory enum."""

    def test_all_categories_exist(self) -> None:
        """All expected categories should exist."""
        from fastband_core.tools import ToolCategory

        expected = [
            "CORE",
            "FILE_OPS",
            "GIT",
            "WEB",
            "MOBILE",
            "DESKTOP",
            "DEVOPS",
            "TESTING",
            "ANALYSIS",
            "TICKETS",
            "SCREENSHOTS",
            "AI",
            "BACKUP",
            "COORDINATION",
        ]

        for cat in expected:
            assert hasattr(ToolCategory, cat), f"Missing category: {cat}"

    def test_category_values(self) -> None:
        """Categories should have string values."""
        from fastband_core.tools import ToolCategory

        assert ToolCategory.CORE.value == "core"
        assert ToolCategory.GIT.value == "git"


class TestToolParameter:
    """Test ToolParameter dataclass."""

    def test_parameter_creation(self) -> None:
        """Parameters should be creatable."""
        from fastband_core.tools import ToolParameter

        param = ToolParameter(
            name="test_param",
            type="string",
            description="A test parameter",
        )

        assert param.name == "test_param"
        assert param.type == "string"
        assert param.required is True
        assert param.default is None

    def test_to_json_schema(self) -> None:
        """Parameters should convert to JSON schema."""
        from fastband_core.tools import ToolParameter

        param = ToolParameter(
            name="count",
            type="integer",
            description="Number of items",
            default=10,
            enum=[5, 10, 20],
        )

        schema = param.to_json_schema()
        assert schema["type"] == "integer"
        assert schema["description"] == "Number of items"
        assert schema["default"] == 10
        assert schema["enum"] == [5, 10, 20]


class TestToolDefinition:
    """Test ToolDefinition dataclass."""

    def test_definition_creation(self) -> None:
        """Definitions should be creatable."""
        from fastband_core.tools import ToolCategory, ToolDefinition, ToolMetadata

        defn = ToolDefinition(
            metadata=ToolMetadata(
                name="test_tool",
                description="A test tool",
                category=ToolCategory.CORE,
            ),
            parameters=[],
        )

        assert defn.metadata.name == "test_tool"
        assert defn.metadata.category == ToolCategory.CORE
        assert defn.parameters == []

    def test_to_schema(self) -> None:
        """Definitions should convert to schema."""
        from fastband_core.tools import (
            ToolCategory,
            ToolDefinition,
            ToolMetadata,
            ToolParameter,
        )

        defn = ToolDefinition(
            metadata=ToolMetadata(
                name="greet",
                description="Greet someone",
                category=ToolCategory.CORE,
            ),
            parameters=[
                ToolParameter(
                    name="name",
                    type="string",
                    description="Name to greet",
                ),
            ],
        )

        schema = defn.to_schema()
        assert schema["name"] == "greet"
        assert schema["description"] == "Greet someone"
        assert "inputSchema" in schema
        assert schema["inputSchema"]["type"] == "object"
        assert "name" in schema["inputSchema"]["properties"]
        assert "name" in schema["inputSchema"]["required"]

    def test_to_openai_schema(self) -> None:
        """Definitions should convert to OpenAI schema."""
        from fastband_core.tools import ToolCategory, ToolDefinition, ToolMetadata

        defn = ToolDefinition(
            metadata=ToolMetadata(
                name="test",
                description="Test tool",
                category=ToolCategory.CORE,
            ),
            parameters=[],
        )

        schema = defn.to_openai_schema()
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "test"


class TestToolResult:
    """Test ToolResult dataclass."""

    def test_success_result(self) -> None:
        """Success results should work correctly."""
        from fastband_core.tools import ToolResult

        result = ToolResult(success=True, data={"status": "ok"})

        assert result.success is True
        assert result.data == {"status": "ok"}
        assert result.error is None

    def test_error_result(self) -> None:
        """Error results should work correctly."""
        from fastband_core.tools import ToolResult

        result = ToolResult(success=False, error="Something went wrong")

        assert result.success is False
        assert result.error == "Something went wrong"

    def test_to_dict(self) -> None:
        """Results should convert to dict."""
        from fastband_core.tools import ToolResult

        result = ToolResult(success=True, data="hello", execution_time_ms=10.5)
        d = result.to_dict()

        assert d["success"] is True
        assert d["data"] == "hello"
        assert d["execution_time_ms"] == 10.5

    def test_to_content(self) -> None:
        """Results should convert to content format."""
        from fastband_core.tools import ToolResult

        result = ToolResult(success=True, data="hello world")
        content = result.to_content()

        assert len(content) == 1
        assert content[0]["type"] == "text"
        assert content[0]["text"] == "hello world"


class TestToolBase:
    """Test ToolBase abstract class."""

    def test_tool_implementation(self) -> None:
        """Tools should be implementable."""
        from fastband_core.tools import (
            ToolBase,
            ToolCategory,
            ToolDefinition,
            ToolMetadata,
            ToolResult,
        )

        class TestTool(ToolBase):
            @property
            def definition(self) -> ToolDefinition:
                return ToolDefinition(
                    metadata=ToolMetadata(
                        name="test",
                        description="Test",
                        category=ToolCategory.CORE,
                    ),
                    parameters=[],
                )

            async def execute(self, **kwargs) -> ToolResult:
                return ToolResult(success=True, data="ok")

        tool = TestTool()
        assert tool.name == "test"
        assert tool.category == ToolCategory.CORE

    def test_validate_params(self) -> None:
        """Parameter validation should work."""
        from fastband_core.tools import (
            ToolBase,
            ToolCategory,
            ToolDefinition,
            ToolMetadata,
            ToolParameter,
            ToolResult,
        )

        class ParamTool(ToolBase):
            @property
            def definition(self) -> ToolDefinition:
                return ToolDefinition(
                    metadata=ToolMetadata(
                        name="param_test",
                        description="Test",
                        category=ToolCategory.CORE,
                    ),
                    parameters=[
                        ToolParameter(
                            name="required_param",
                            type="string",
                            description="Required",
                            required=True,
                        ),
                    ],
                )

            async def execute(self, **kwargs) -> ToolResult:
                return ToolResult(success=True)

        tool = ParamTool()

        # Missing required param
        valid, error = tool.validate_params()
        assert valid is False
        assert "required_param" in error

        # With required param
        valid, error = tool.validate_params(required_param="value")
        assert valid is True
        assert error is None

    @pytest.mark.asyncio
    async def test_safe_execute(self) -> None:
        """Safe execute should handle errors."""
        from fastband_core.tools import (
            ToolBase,
            ToolCategory,
            ToolDefinition,
            ToolMetadata,
            ToolResult,
        )

        class ErrorTool(ToolBase):
            @property
            def definition(self) -> ToolDefinition:
                return ToolDefinition(
                    metadata=ToolMetadata(
                        name="error_test",
                        description="Test",
                        category=ToolCategory.CORE,
                    ),
                    parameters=[],
                )

            async def execute(self, **kwargs) -> ToolResult:
                raise ValueError("Test error")

        tool = ErrorTool()
        result = await tool.safe_execute()

        assert result.success is False
        assert "Test error" in result.error
        assert result.execution_time_ms > 0


class TestToolDecorator:
    """Test the @tool decorator."""

    def test_decorator_creates_tool(self) -> None:
        """Decorator should create a tool instance."""
        from fastband_core.tools import ToolBase, ToolCategory, ToolResult, tool

        @tool("decorated", "A decorated tool", category=ToolCategory.CORE)
        async def decorated_tool(name: str = "World") -> ToolResult:
            return ToolResult(success=True, data=f"Hello, {name}!")

        assert isinstance(decorated_tool, ToolBase)
        assert decorated_tool.name == "decorated"
        assert decorated_tool.category == ToolCategory.CORE

    def test_decorator_extracts_params(self) -> None:
        """Decorator should extract parameters from function signature."""
        from fastband_core.tools import ToolCategory, ToolResult, tool

        @tool("with_params", "Tool with params", category=ToolCategory.CORE)
        async def with_params(required: str, optional: int = 10) -> ToolResult:
            return ToolResult(success=True)

        params = with_params.definition.parameters
        assert len(params) == 2

        required_param = next(p for p in params if p.name == "required")
        assert required_param.required is True

        optional_param = next(p for p in params if p.name == "optional")
        assert optional_param.required is False
        assert optional_param.default == 10


class TestToolRegistry:
    """Test ToolRegistryBase functionality."""

    def test_registry_creation(self) -> None:
        """Registry should be creatable."""
        from fastband_core.tools import ToolRegistry

        registry = ToolRegistry()
        assert len(registry.get_active_tools()) == 0

    def test_register_and_load(self) -> None:
        """Tools should be registrable and loadable."""
        from fastband_core.tools import (
            ToolBase,
            ToolCategory,
            ToolDefinition,
            ToolMetadata,
            ToolRegistry,
            ToolResult,
        )

        class TestTool(ToolBase):
            @property
            def definition(self) -> ToolDefinition:
                return ToolDefinition(
                    metadata=ToolMetadata(
                        name="registry_test",
                        description="Test",
                        category=ToolCategory.TESTING,
                    ),
                    parameters=[],
                )

            async def execute(self, **kwargs) -> ToolResult:
                return ToolResult(success=True)

        registry = ToolRegistry()
        tool = TestTool()

        registry.register(tool)
        assert registry.is_registered("registry_test")
        assert not registry.is_loaded("registry_test")

        status = registry.load("registry_test")
        assert status.loaded is True
        assert registry.is_loaded("registry_test")

    def test_lazy_registration(self) -> None:
        """Lazy registration should work."""
        from fastband_core.tools import ToolCategory, ToolRegistry

        registry = ToolRegistry()

        registry.register_lazy(
            "lazy_tool",
            "fastband_core.tools.base",
            "ToolBase",  # Won't actually work but tests registration
            ToolCategory.CORE,
        )

        assert registry.is_registered("lazy_tool")
        assert registry.is_lazy("lazy_tool")
        assert not registry.is_loaded("lazy_tool")

    def test_get_schemas(self) -> None:
        """Registry should provide tool schemas."""
        from fastband_core.tools import (
            ToolBase,
            ToolCategory,
            ToolDefinition,
            ToolMetadata,
            ToolRegistry,
            ToolResult,
        )

        class SchemaTool(ToolBase):
            @property
            def definition(self) -> ToolDefinition:
                return ToolDefinition(
                    metadata=ToolMetadata(
                        name="schema_test",
                        description="Schema test",
                        category=ToolCategory.CORE,
                    ),
                    parameters=[],
                )

            async def execute(self, **kwargs) -> ToolResult:
                return ToolResult(success=True)

        registry = ToolRegistry()
        registry.register(SchemaTool())
        registry.load("schema_test")

        schemas = registry.get_schemas()
        assert len(schemas) == 1
        assert schemas[0]["name"] == "schema_test"

    @pytest.mark.asyncio
    async def test_execute(self) -> None:
        """Registry should execute tools."""
        from fastband_core.tools import (
            ToolBase,
            ToolCategory,
            ToolDefinition,
            ToolMetadata,
            ToolRegistry,
            ToolResult,
        )

        class ExecTool(ToolBase):
            @property
            def definition(self) -> ToolDefinition:
                return ToolDefinition(
                    metadata=ToolMetadata(
                        name="exec_test",
                        description="Exec test",
                        category=ToolCategory.CORE,
                    ),
                    parameters=[],
                )

            async def execute(self, **kwargs) -> ToolResult:
                return ToolResult(success=True, data="executed")

        registry = ToolRegistry()
        registry.register(ExecTool())
        registry.load("exec_test")

        result = await registry.execute("exec_test")
        assert result.success is True
        assert result.data == "executed"

    def test_performance_report(self) -> None:
        """Registry should provide performance reports."""
        from fastband_core.tools import ToolRegistry

        registry = ToolRegistry()
        report = registry.get_performance_report()

        assert report.active_tools == 0
        assert report.status == "optimal"


class TestNoForbiddenImports:
    """Test that tools modules don't contain forbidden imports."""

    FORBIDDEN_MODULES = [
        "fastapi",
        "flask",
        "starlette",
        "django",
        "sqlalchemy",
        "asyncpg",
        "psycopg",
        "sqlite3",
        "aiosqlite",
        "pymongo",
        "redis",
        "dotenv",
        "python-dotenv",
        "mcp",  # MCP is protocol-specific
        "fastband_dev",
        "fastband_enterprise",
    ]

    def _get_imports_from_file(self, file_path: Path) -> set[str]:
        """Extract all imports from a Python file using AST."""
        source = file_path.read_text()
        tree = ast.parse(source)
        imports: set[str] = set()

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.add(node.module.split(".")[0])

        return imports

    def test_base_no_forbidden_imports(self) -> None:
        """Base module must not import forbidden modules."""
        tools_dir = Path(__file__).parent.parent / "src" / "fastband_core" / "tools"
        base_file = tools_dir / "base.py"

        imports = self._get_imports_from_file(base_file)

        for forbidden in self.FORBIDDEN_MODULES:
            assert forbidden not in imports, f"Forbidden import found: {forbidden}"

    def test_registry_no_forbidden_imports(self) -> None:
        """Registry module must not import forbidden modules."""
        tools_dir = Path(__file__).parent.parent / "src" / "fastband_core" / "tools"
        registry_file = tools_dir / "registry.py"

        imports = self._get_imports_from_file(registry_file)

        for forbidden in self.FORBIDDEN_MODULES:
            assert forbidden not in imports, f"Forbidden import found: {forbidden}"

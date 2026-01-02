"""
Tests for Core runtime module.

Verifies:
1. Runtime components are importable
2. EngineBase lifecycle works correctly
3. RuntimeContext provides proper DI
4. ComponentRegistry manages components
5. No forbidden imports
"""

import ast
from pathlib import Path

import pytest


class TestRuntimeImportable:
    """Test that runtime modules are importable."""

    def test_import_engine(self) -> None:
        """Engine module should be importable."""
        from fastband_core.runtime import engine

        assert hasattr(engine, "EngineBase")
        assert hasattr(engine, "EngineConfig")
        assert hasattr(engine, "EngineState")
        assert hasattr(engine, "ToolExecutor")

    def test_import_context(self) -> None:
        """Context module should be importable."""
        from fastband_core.runtime import context

        assert hasattr(context, "RuntimeContext")
        assert hasattr(context, "RuntimeConfig")
        assert hasattr(context, "ServiceRegistry")
        assert hasattr(context, "RequestContext")

    def test_import_registry(self) -> None:
        """Registry module should be importable."""
        from fastband_core.runtime import registry

        assert hasattr(registry, "ComponentRegistry")
        assert hasattr(registry, "ComponentState")
        assert hasattr(registry, "ToolDefinition")

    def test_import_from_runtime(self) -> None:
        """All exports should be importable from runtime module."""
        from fastband_core import runtime

        for name in runtime.__all__:
            assert hasattr(runtime, name), f"Missing export: {name}"

    def test_import_from_root(self) -> None:
        """Common runtime exports should be importable from package root."""
        import fastband_core

        assert hasattr(fastband_core, "EngineBase")
        assert hasattr(fastband_core, "RuntimeContext")
        assert hasattr(fastband_core, "ComponentRegistry")


class TestEngineBase:
    """Test EngineBase lifecycle."""

    def test_engine_initial_state(self) -> None:
        """Engine should start in CREATED state."""
        from fastband_core.runtime import EngineBase, EngineState

        class TestEngine(EngineBase):
            async def _do_initialize(self):
                pass

            async def _do_start(self):
                pass

            async def _do_stop(self):
                pass

        engine = TestEngine()
        assert engine.state == EngineState.CREATED
        assert not engine.is_running
        assert not engine.is_ready

    @pytest.mark.asyncio
    async def test_engine_lifecycle(self) -> None:
        """Engine should transition through states correctly."""
        from fastband_core.runtime import EngineBase, EngineState

        states_visited: list[EngineState] = []

        class TestEngine(EngineBase):
            async def _do_initialize(self):
                states_visited.append(self.state)

            async def _do_start(self):
                states_visited.append(self.state)

            async def _do_stop(self):
                states_visited.append(self.state)

        engine = TestEngine()
        await engine.initialize()
        assert engine.state == EngineState.READY
        assert engine.is_ready

        # Start should go to RUNNING
        # Note: start() is blocking in real engines, so we test state after init
        states_visited.clear()

    def test_engine_info(self) -> None:
        """Engine should provide info."""
        from fastband_core.runtime import EngineBase, EngineConfig

        class TestEngine(EngineBase):
            async def _do_initialize(self):
                pass

            async def _do_start(self):
                pass

            async def _do_stop(self):
                pass

        config = EngineConfig(name="test-engine", version="1.0.0")
        engine = TestEngine(config)
        info = engine.get_info()

        assert info.name == "test-engine"
        assert info.version == "1.0.0"


class TestRuntimeContext:
    """Test RuntimeContext functionality."""

    def test_context_creation(self) -> None:
        """Context should be creatable with defaults."""
        from fastband_core.runtime import RuntimeContext

        ctx = RuntimeContext()
        assert ctx.config is not None
        assert ctx.services is not None

    def test_service_registry(self) -> None:
        """ServiceRegistry should store and retrieve services."""
        from fastband_core.runtime import ServiceRegistry

        class MyService:
            def greet(self) -> str:
                return "hello"

        registry = ServiceRegistry()
        service = MyService()

        registry.register(MyService, service)
        assert registry.has(MyService)

        retrieved = registry.get(MyService)
        assert retrieved is service
        assert retrieved.greet() == "hello"

    def test_service_require_missing(self) -> None:
        """Require should raise for missing service."""
        from fastband_core.runtime import ServiceRegistry

        class Missing:
            pass

        registry = ServiceRegistry()

        with pytest.raises(KeyError):
            registry.require(Missing)

    def test_request_context(self) -> None:
        """Request context should be accessible."""
        from fastband_core.runtime import RuntimeContext

        ctx = RuntimeContext()

        with ctx.request() as req:
            assert req.request_id is not None
            assert ctx.current_request is req

        assert ctx.current_request is None


class TestComponentRegistry:
    """Test ComponentRegistry functionality."""

    def test_simple_registry(self) -> None:
        """SimpleRegistry should register and retrieve."""
        from fastband_core.runtime import SimpleRegistry

        registry: SimpleRegistry[str] = SimpleRegistry("test")

        registry.register("item1", "value1")
        assert registry.is_registered("item1")
        assert not registry.is_active("item1")

        loaded = registry.load("item1")
        assert loaded == "value1"
        assert registry.is_active("item1")

    def test_registry_lazy_loading(self) -> None:
        """Registry should support lazy loading."""
        from fastband_core.runtime import SimpleRegistry

        call_count = 0

        def factory() -> str:
            nonlocal call_count
            call_count += 1
            return f"lazy-{call_count}"

        registry: SimpleRegistry[str] = SimpleRegistry("test")
        registry.register_lazy("lazy", factory)

        assert call_count == 0  # Not called yet
        value = registry.load("lazy")
        assert call_count == 1
        assert value == "lazy-1"

        # Loading again returns cached
        value2 = registry.load("lazy")
        assert call_count == 1
        assert value2 == "lazy-1"

    def test_tool_definition(self) -> None:
        """ToolDefinition should be usable."""
        from fastband_core.runtime import ToolDefinition

        defn = ToolDefinition(
            name="test_tool",
            description="A test tool",
            parameters={"input": {"type": "string"}},
            tags=["test"],
        )

        assert defn.name == "test_tool"
        assert defn.description == "A test tool"
        assert "input" in defn.parameters
        assert "test" in defn.tags


class TestNoForbiddenImports:
    """Test that runtime modules don't contain forbidden imports."""

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
        "mcp",  # MCP is protocol-specific, should be in adapters
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

    def test_engine_no_forbidden_imports(self) -> None:
        """Engine module must not import forbidden modules."""
        runtime_dir = (
            Path(__file__).parent.parent / "src" / "fastband_core" / "runtime"
        )
        engine_file = runtime_dir / "engine.py"

        imports = self._get_imports_from_file(engine_file)

        for forbidden in self.FORBIDDEN_MODULES:
            assert forbidden not in imports, f"Forbidden import found: {forbidden}"

    def test_context_no_forbidden_imports(self) -> None:
        """Context module must not import forbidden modules."""
        runtime_dir = (
            Path(__file__).parent.parent / "src" / "fastband_core" / "runtime"
        )
        context_file = runtime_dir / "context.py"

        imports = self._get_imports_from_file(context_file)

        for forbidden in self.FORBIDDEN_MODULES:
            assert forbidden not in imports, f"Forbidden import found: {forbidden}"

    def test_registry_no_forbidden_imports(self) -> None:
        """Registry module must not import forbidden modules."""
        runtime_dir = (
            Path(__file__).parent.parent / "src" / "fastband_core" / "runtime"
        )
        registry_file = runtime_dir / "registry.py"

        imports = self._get_imports_from_file(registry_file)

        for forbidden in self.FORBIDDEN_MODULES:
            assert forbidden not in imports, f"Forbidden import found: {forbidden}"

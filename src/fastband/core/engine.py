"""
Fastband MCP Server Engine.

The core MCP server that handles tool registration, execution, and protocol handling.
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional, Callable
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Tool as MCPTool,
    TextContent,
    CallToolResult,
)

from fastband import __version__
from fastband.tools.registry import ToolRegistry, get_registry
from fastband.tools.base import Tool, ToolResult
from fastband.tools.core import CORE_TOOLS
from fastband.core.config import FastbandConfig, get_config

logger = logging.getLogger(__name__)


class FastbandEngine:
    """
    Fastband MCP Server Engine.

    Manages the MCP server lifecycle, tool registration, and execution.

    Example:
        engine = FastbandEngine()
        engine.register_core_tools()
        await engine.start()
    """

    def __init__(
        self,
        project_path: Optional[Path] = None,
        config: Optional[FastbandConfig] = None,
    ):
        self.project_path = project_path or Path.cwd()
        self.config = config or get_config(self.project_path)
        self.registry = get_registry()
        self.server = Server("fastband-mcp")
        self._running = False
        self._setup_handlers()

    def _setup_handlers(self):
        """Set up MCP server handlers."""

        @self.server.list_tools()
        async def list_tools() -> List[MCPTool]:
            """List all available tools."""
            tools = []
            for tool in self.registry.get_active_tools():
                schema = tool.definition.to_mcp_schema()
                tools.append(MCPTool(
                    name=schema["name"],
                    description=schema["description"],
                    inputSchema=schema["inputSchema"],
                ))
            return tools

        @self.server.call_tool()
        async def call_tool(name: str, arguments: Dict[str, Any]) -> CallToolResult:
            """Execute a tool and return result."""
            logger.info(f"Tool call: {name}")
            logger.debug(f"Arguments: {arguments}")

            result = await self.registry.execute(name, **arguments)

            return CallToolResult(
                content=result.to_mcp_content(),
                isError=not result.success,
            )

    def register_tool(self, tool: Tool) -> None:
        """
        Register and load a tool.

        Args:
            tool: Tool instance to register
        """
        self.registry.register(tool)
        self.registry.load(tool.name)

    def register_core_tools(self) -> None:
        """Register and load all core tools."""
        for tool_class in CORE_TOOLS:
            tool = tool_class()
            self.registry.register(tool)
            self.registry.load(tool.name)

        logger.info(f"Loaded {len(CORE_TOOLS)} core tools")

    def register_tools(self, tools: List[Tool]) -> None:
        """Register and load multiple tools."""
        for tool in tools:
            self.register_tool(tool)

    async def execute_tool(self, name: str, **kwargs) -> ToolResult:
        """
        Execute a tool by name.

        Args:
            name: Tool name
            **kwargs: Tool parameters

        Returns:
            ToolResult from execution
        """
        return await self.registry.execute(name, **kwargs)

    async def start(self):
        """Start the MCP server."""
        logger.info(f"Starting Fastband MCP Server v{__version__}")
        logger.info(f"Project path: {self.project_path}")
        logger.info(f"Active tools: {len(self.registry.get_active_tools())}")

        self._running = True

        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                self.server.create_initialization_options(),
            )

    async def stop(self):
        """Stop the MCP server."""
        logger.info("Stopping Fastband MCP Server")
        self._running = False

    @property
    def is_running(self) -> bool:
        """Check if server is running."""
        return self._running

    def get_tool_schemas(self) -> List[Dict]:
        """Get MCP schemas for all active tools."""
        return self.registry.get_mcp_tools()

    def get_openai_schemas(self) -> List[Dict]:
        """Get OpenAI function schemas for all active tools."""
        return self.registry.get_openai_tools()


# Convenience functions for running the server

def create_engine(
    project_path: Optional[Path] = None,
    load_core: bool = True,
) -> FastbandEngine:
    """
    Create and configure a Fastband engine.

    Args:
        project_path: Project directory (default: current directory)
        load_core: Whether to load core tools (default: True)

    Returns:
        Configured FastbandEngine
    """
    engine = FastbandEngine(project_path=project_path)

    if load_core:
        engine.register_core_tools()

    return engine


async def run_server(
    project_path: Optional[Path] = None,
    load_core: bool = True,
):
    """
    Run the Fastband MCP server.

    Args:
        project_path: Project directory (default: current directory)
        load_core: Whether to load core tools (default: True)
    """
    engine = create_engine(project_path=project_path, load_core=load_core)
    await engine.start()


def main():
    """Entry point for running the server."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    asyncio.run(run_server())


if __name__ == "__main__":
    main()

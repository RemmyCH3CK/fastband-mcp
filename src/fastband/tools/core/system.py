"""
System tools - Health check, configuration, version info.
"""

import os
import platform
import sys
from datetime import datetime

from fastband import __version__
from fastband.tools.base import (
    Tool,
    ToolCategory,
    ToolDefinition,
    ToolMetadata,
    ToolParameter,
    ToolResult,
)


class HealthCheckTool(Tool):
    """Check system and Fastband health status."""

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            metadata=ToolMetadata(
                name="health_check",
                description="Check Fastband MCP server health and system status",
                category=ToolCategory.CORE,
                version="1.0.0",
            ),
            parameters=[],
        )

    async def execute(self, **kwargs) -> ToolResult:
        """Execute health check."""
        from fastband.tools.registry import get_registry

        registry = get_registry()
        performance = registry.get_performance_report()

        health_data = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "fastband": {
                "version": __version__,
                "tools_active": performance.active_tools,
                "tools_available": performance.available_tools,
                "performance_status": performance.status,
            },
            "system": {
                "platform": platform.system(),
                "platform_version": platform.version(),
                "python_version": sys.version.split()[0],
                "architecture": platform.machine(),
            },
            "environment": {
                "working_directory": os.getcwd(),
                "fastband_config_exists": os.path.exists(".fastband/config.yaml"),
            },
        }

        return ToolResult(success=True, data=health_data)


class GetConfigTool(Tool):
    """Get current Fastband configuration."""

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            metadata=ToolMetadata(
                name="get_config",
                description="Get current Fastband configuration for this project",
                category=ToolCategory.CORE,
                version="1.0.0",
            ),
            parameters=[
                ToolParameter(
                    name="section",
                    type="string",
                    description="Configuration section to retrieve (ai, tools, tickets, backup, github, storage). Leave empty for all.",
                    required=False,
                    enum=["ai", "tools", "tickets", "backup", "github", "storage"],
                ),
            ],
        )

    async def execute(self, section: str = None, **kwargs) -> ToolResult:
        """Get configuration."""
        from fastband.core.config import get_config

        config = get_config()
        config_dict = config.to_dict()["fastband"]

        if section:
            if section not in config_dict:
                return ToolResult(
                    success=False,
                    error=f"Unknown section: {section}. Available: {list(config_dict.keys())}",
                )
            return ToolResult(success=True, data={section: config_dict[section]})

        return ToolResult(success=True, data=config_dict)


class GetVersionTool(Tool):
    """Get Fastband version information."""

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            metadata=ToolMetadata(
                name="get_version",
                description="Get Fastband MCP version and component versions",
                category=ToolCategory.CORE,
                version="1.0.0",
            ),
            parameters=[],
        )

    async def execute(self, **kwargs) -> ToolResult:
        """Get version information."""
        version_data = {
            "fastband_mcp": __version__,
            "python": sys.version.split()[0],
            "platform": platform.system(),
            "components": {
                "core": "1.0.0",
                "tools": "1.0.0",
                "providers": "1.0.0",
            },
        }

        return ToolResult(success=True, data=version_data)

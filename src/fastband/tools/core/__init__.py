"""
Core tools - Always loaded with Fastband.

These tools provide essential functionality that every project needs.
"""

from fastband.tools.core.system import (
    HealthCheckTool,
    GetConfigTool,
    GetVersionTool,
)
from fastband.tools.core.files import (
    ListFilesTool,
    ReadFileTool,
    WriteFileTool,
    SearchCodeTool,
)

# All core tools
CORE_TOOLS = [
    HealthCheckTool,
    GetConfigTool,
    GetVersionTool,
    ListFilesTool,
    ReadFileTool,
    WriteFileTool,
    SearchCodeTool,
]

__all__ = [
    "HealthCheckTool",
    "GetConfigTool",
    "GetVersionTool",
    "ListFilesTool",
    "ReadFileTool",
    "WriteFileTool",
    "SearchCodeTool",
    "CORE_TOOLS",
]

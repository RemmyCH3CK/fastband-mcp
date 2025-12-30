"""
Core tools - Always loaded with Fastband.

These tools provide essential functionality that every project needs.
"""

from fastband.tools.core.build import (
    BuildProjectTool,
    RunScriptTool,
)
from fastband.tools.core.files import (
    ListFilesTool,
    ReadFileTool,
    SearchCodeTool,
    WriteFileTool,
)
from fastband.tools.core.system import (
    GetConfigTool,
    GetVersionTool,
    HealthCheckTool,
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
    BuildProjectTool,
    RunScriptTool,
]

__all__ = [
    "HealthCheckTool",
    "GetConfigTool",
    "GetVersionTool",
    "ListFilesTool",
    "ReadFileTool",
    "WriteFileTool",
    "SearchCodeTool",
    "BuildProjectTool",
    "RunScriptTool",
    "CORE_TOOLS",
]

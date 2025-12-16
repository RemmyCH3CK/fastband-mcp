"""
Tool base classes and definitions.

All Fastband tools inherit from the Tool base class and define
their parameters and execution logic.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Callable, Union
from enum import Enum
import time
import logging

logger = logging.getLogger(__name__)


class ToolCategory(Enum):
    """Tool categories for the garage system."""
    CORE = "core"                  # Always loaded
    FILE_OPS = "file_ops"          # File operations
    GIT = "git"                    # Version control
    WEB = "web"                    # Web development
    MOBILE = "mobile"              # Mobile development
    DESKTOP = "desktop"            # Desktop development
    DEVOPS = "devops"              # CI/CD, containers
    TESTING = "testing"            # Test execution
    ANALYSIS = "analysis"          # Code quality, security
    TICKETS = "tickets"            # Ticket management
    SCREENSHOTS = "screenshots"    # Visual capture
    AI = "ai"                      # AI-powered analysis
    BACKUP = "backup"              # Backup operations
    COORDINATION = "coordination"  # Multi-agent coordination


class ProjectType(Enum):
    """Project types for tool recommendation."""
    WEB_APP = "web_app"
    API_SERVICE = "api_service"
    MOBILE_IOS = "mobile_ios"
    MOBILE_ANDROID = "mobile_android"
    MOBILE_CROSS = "mobile_cross_platform"
    DESKTOP_ELECTRON = "desktop_electron"
    DESKTOP_NATIVE = "desktop_native"
    CLI_TOOL = "cli_tool"
    LIBRARY = "library"
    MONOREPO = "monorepo"
    UNKNOWN = "unknown"


@dataclass
class ToolParameter:
    """Parameter definition for a tool."""
    name: str
    type: str  # "string", "integer", "boolean", "number", "array", "object"
    description: str
    required: bool = True
    default: Any = None
    enum: Optional[List[Any]] = None

    def to_json_schema(self) -> Dict[str, Any]:
        """Convert to JSON schema format."""
        schema: Dict[str, Any] = {
            "type": self.type,
            "description": self.description,
        }
        if self.enum:
            schema["enum"] = self.enum
        if self.default is not None:
            schema["default"] = self.default
        return schema


@dataclass
class ToolMetadata:
    """Metadata for a tool."""
    name: str
    description: str
    category: ToolCategory
    version: str = "1.0.0"
    author: str = "Fastband Team"

    # Recommendation hints
    project_types: List[ProjectType] = field(default_factory=list)
    tech_stack_hints: List[str] = field(default_factory=list)

    # Dependencies
    requires_tools: List[str] = field(default_factory=list)
    conflicts_with: List[str] = field(default_factory=list)

    # Resource hints
    memory_intensive: bool = False
    network_required: bool = False
    requires_filesystem: bool = False

    # Curation status (for third-party tools)
    curated: bool = True
    curator_notes: Optional[str] = None


@dataclass
class ToolDefinition:
    """Complete tool definition for MCP registration."""
    metadata: ToolMetadata
    parameters: List[ToolParameter]

    def to_mcp_schema(self) -> Dict[str, Any]:
        """Convert to MCP tool schema format."""
        properties = {}
        required = []

        for param in self.parameters:
            properties[param.name] = param.to_json_schema()
            if param.required:
                required.append(param.name)

        return {
            "name": self.metadata.name,
            "description": self.metadata.description,
            "inputSchema": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        }

    def to_openai_schema(self) -> Dict[str, Any]:
        """Convert to OpenAI function calling schema."""
        mcp_schema = self.to_mcp_schema()
        return {
            "type": "function",
            "function": {
                "name": mcp_schema["name"],
                "description": mcp_schema["description"],
                "parameters": mcp_schema["inputSchema"],
            },
        }


@dataclass
class ToolResult:
    """Result from tool execution."""
    success: bool
    data: Any = None
    error: Optional[str] = None
    execution_time_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        result = {
            "success": self.success,
            "execution_time_ms": self.execution_time_ms,
        }
        if self.success:
            result["data"] = self.data
        else:
            result["error"] = self.error
        if self.metadata:
            result["metadata"] = self.metadata
        return result

    def to_mcp_content(self) -> List[Dict[str, Any]]:
        """Convert to MCP content format."""
        import json

        if self.success:
            if isinstance(self.data, str):
                return [{"type": "text", "text": self.data}]
            else:
                return [{"type": "text", "text": json.dumps(self.data, indent=2)}]
        else:
            return [{"type": "text", "text": f"Error: {self.error}"}]


class Tool(ABC):
    """
    Base class for all Fastband tools.

    Tools must implement:
    - definition property: Returns ToolDefinition
    - execute method: Performs the tool's action

    Example:
        class HealthCheckTool(Tool):
            @property
            def definition(self) -> ToolDefinition:
                return ToolDefinition(
                    metadata=ToolMetadata(
                        name="health_check",
                        description="Check system health",
                        category=ToolCategory.CORE,
                    ),
                    parameters=[],
                )

            async def execute(self, **kwargs) -> ToolResult:
                return ToolResult(success=True, data={"status": "healthy"})
    """

    @property
    @abstractmethod
    def definition(self) -> ToolDefinition:
        """Return tool definition with metadata and parameters."""
        pass

    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        """
        Execute the tool with given parameters.

        Args:
            **kwargs: Tool parameters as defined in definition

        Returns:
            ToolResult with success/failure and data
        """
        pass

    @property
    def name(self) -> str:
        """Get tool name from definition."""
        return self.definition.metadata.name

    @property
    def category(self) -> ToolCategory:
        """Get tool category from definition."""
        return self.definition.metadata.category

    def validate_params(self, **kwargs) -> tuple[bool, Optional[str]]:
        """
        Validate parameters against definition.

        Returns:
            Tuple of (is_valid, error_message)
        """
        for param in self.definition.parameters:
            if param.required and param.name not in kwargs:
                return False, f"Missing required parameter: {param.name}"

            if param.name in kwargs and param.enum:
                if kwargs[param.name] not in param.enum:
                    return False, (
                        f"Invalid value for {param.name}: {kwargs[param.name]}. "
                        f"Must be one of: {param.enum}"
                    )

        return True, None

    async def safe_execute(self, **kwargs) -> ToolResult:
        """
        Execute with validation and error handling.

        This is the recommended way to call tools.
        """
        start_time = time.perf_counter()

        # Validate parameters
        is_valid, error = self.validate_params(**kwargs)
        if not is_valid:
            return ToolResult(
                success=False,
                error=error,
                execution_time_ms=(time.perf_counter() - start_time) * 1000,
            )

        # Execute with error handling
        try:
            result = await self.execute(**kwargs)
            result.execution_time_ms = (time.perf_counter() - start_time) * 1000
            return result
        except Exception as e:
            logger.exception(f"Tool {self.name} execution failed")
            return ToolResult(
                success=False,
                error=str(e),
                execution_time_ms=(time.perf_counter() - start_time) * 1000,
            )


def tool(
    name: str,
    description: str,
    category: ToolCategory = ToolCategory.CORE,
    **metadata_kwargs
) -> Callable:
    """
    Decorator for creating simple tools from functions.

    Example:
        @tool("greet", "Greet a user", category=ToolCategory.CORE)
        async def greet(name: str = "World") -> ToolResult:
            return ToolResult(success=True, data=f"Hello, {name}!")
    """
    def decorator(func: Callable) -> Tool:
        import inspect

        # Extract parameters from function signature
        sig = inspect.signature(func)
        parameters = []

        for param_name, param in sig.parameters.items():
            if param_name in ("self", "cls"):
                continue

            param_type = "string"  # Default type
            if param.annotation != inspect.Parameter.empty:
                type_map = {
                    str: "string",
                    int: "integer",
                    float: "number",
                    bool: "boolean",
                    list: "array",
                    dict: "object",
                }
                param_type = type_map.get(param.annotation, "string")

            parameters.append(ToolParameter(
                name=param_name,
                type=param_type,
                description=f"Parameter: {param_name}",
                required=param.default == inspect.Parameter.empty,
                default=None if param.default == inspect.Parameter.empty else param.default,
            ))

        class DecoratedTool(Tool):
            @property
            def definition(self) -> ToolDefinition:
                return ToolDefinition(
                    metadata=ToolMetadata(
                        name=name,
                        description=description,
                        category=category,
                        **metadata_kwargs,
                    ),
                    parameters=parameters,
                )

            async def execute(self, **kwargs) -> ToolResult:
                return await func(**kwargs)

        return DecoratedTool()

    return decorator

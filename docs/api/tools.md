# Tools API Reference

Complete API documentation for Fastband's tool system.

## Module: `fastband.tools`

### Functions

#### `get_registry() -> ToolRegistry`

Get the global tool registry.

**Returns:** ToolRegistry instance.

**Example:**
```python
from fastband.tools import get_registry

registry = get_registry()
tools = registry.list_tools()
```

---

#### `register_tool(tool_class: Type[Tool]) -> None`

Register a tool class with the global registry.

**Parameters:**
- `tool_class` (Type[Tool]): Tool class to register.

**Example:**
```python
from fastband.tools import register_tool

register_tool(MyCustomTool)
```

---

#### `get_tool(name: str) -> Tool`

Get a tool by name from the global registry.

**Parameters:**
- `name` (str): Tool name.

**Returns:** Tool instance.

**Raises:** ToolNotFoundError if tool doesn't exist.

**Example:**
```python
from fastband.tools import get_tool

read_file = get_tool("read_file")
result = await read_file.execute(file_path="/path/to/file")
```

---

## Class: `Tool`

Abstract base class for all tools.

**Module:** `fastband.tools.base`

### Properties

#### `definition: ToolDefinition`

Tool definition including metadata and parameters.

**Returns:** ToolDefinition

---

#### `name: str`

Tool name (from definition).

**Returns:** str

---

#### `description: str`

Tool description (from definition).

**Returns:** str

---

#### `category: ToolCategory`

Tool category (from definition).

**Returns:** ToolCategory

---

### Methods

#### `async execute(**kwargs) -> ToolResult`

Execute the tool with given parameters.

**Parameters:**
- `**kwargs`: Tool-specific parameters as defined in definition.

**Returns:** ToolResult

**Example:**
```python
class ReadFileTool(Tool):
    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            metadata=ToolMetadata(
                name="read_file",
                description="Read file contents",
                category=ToolCategory.FILES,
                version="1.0.0",
            ),
            parameters=[
                ToolParameter(
                    name="file_path",
                    type="string",
                    description="Path to file",
                    required=True,
                ),
            ],
        )

    async def execute(self, file_path: str, **kwargs) -> ToolResult:
        try:
            with open(file_path) as f:
                content = f.read()
            return ToolResult(success=True, data={"content": content})
        except Exception as e:
            return ToolResult(success=False, error=str(e))
```

---

## Class: `ToolDefinition`

Complete tool definition.

**Module:** `fastband.tools.base`

### Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `metadata` | ToolMetadata | Tool metadata |
| `parameters` | List[ToolParameter] | Parameter definitions |
| `returns` | Optional[Dict] | Return type schema |

**Example:**
```python
from fastband.tools.base import ToolDefinition, ToolMetadata, ToolParameter

definition = ToolDefinition(
    metadata=ToolMetadata(
        name="my_tool",
        description="Does something useful",
        category=ToolCategory.SYSTEM,
        version="1.0.0",
    ),
    parameters=[
        ToolParameter(
            name="input",
            type="string",
            description="Input value",
            required=True,
        ),
    ],
    returns={
        "type": "object",
        "properties": {
            "output": {"type": "string"}
        }
    }
)
```

---

## Class: `ToolMetadata`

Tool metadata.

**Module:** `fastband.tools.base`

### Attributes

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | str | required | Unique tool name |
| `description` | str | required | Human-readable description |
| `category` | ToolCategory | required | Tool category |
| `version` | str | "1.0.0" | Semantic version |
| `tags` | List[str] | [] | Searchable tags |
| `deprecated` | bool | False | Is tool deprecated |
| `deprecated_message` | Optional[str] | None | Deprecation message |

**Example:**
```python
metadata = ToolMetadata(
    name="fetch_url",
    description="Fetch content from a URL",
    category=ToolCategory.WEB,
    version="1.2.0",
    tags=["http", "fetch", "download"],
)
```

---

## Class: `ToolParameter`

Tool parameter definition.

**Module:** `fastband.tools.base`

### Attributes

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | str | required | Parameter name |
| `type` | str | required | Type: string, integer, boolean, array, object |
| `description` | str | required | Parameter description |
| `required` | bool | False | Is parameter required |
| `default` | Any | None | Default value |
| `enum` | Optional[List] | None | Allowed values |
| `items` | Optional[Dict] | None | Array item schema |
| `properties` | Optional[Dict] | None | Object property schema |

**Example:**
```python
# String parameter with enum
ToolParameter(
    name="format",
    type="string",
    description="Output format",
    required=False,
    default="json",
    enum=["json", "yaml", "xml"]
)

# Array parameter
ToolParameter(
    name="files",
    type="array",
    description="List of files",
    required=True,
    items={"type": "string"}
)

# Object parameter
ToolParameter(
    name="config",
    type="object",
    description="Configuration object",
    required=False,
    properties={
        "enabled": {"type": "boolean"},
        "timeout": {"type": "integer"}
    }
)
```

---

## Class: `ToolResult`

Result from tool execution.

**Module:** `fastband.tools.base`

### Attributes

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `success` | bool | required | Did execution succeed |
| `data` | Optional[Dict] | None | Result data |
| `error` | Optional[str] | None | Error message if failed |
| `metadata` | Dict[str, Any] | {} | Additional metadata |

**Example:**
```python
# Success result
result = ToolResult(
    success=True,
    data={
        "content": "file contents...",
        "size": 1234,
        "encoding": "utf-8"
    }
)

# Error result
result = ToolResult(
    success=False,
    error="File not found: /missing.txt"
)

# With metadata
result = ToolResult(
    success=True,
    data={"output": "..."},
    metadata={
        "execution_time": 0.5,
        "cached": True
    }
)
```

---

## Enum: `ToolCategory`

Tool categories for organization.

**Module:** `fastband.tools.base`

### Values

| Value | Description |
|-------|-------------|
| `FILES` | File operations |
| `SYSTEM` | System operations |
| `GIT` | Git operations |
| `WEB` | Web/HTTP operations |
| `TICKETS` | Ticket management |
| `DATABASE` | Database operations |
| `TESTING` | Testing tools |
| `DOCUMENTATION` | Documentation tools |
| `CUSTOM` | Custom/user tools |

---

## Class: `ToolRegistry`

Manages tool registration and access.

**Module:** `fastband.tools.registry`

### Properties

#### `active_count: int`

Number of currently active tools.

---

#### `max_active: int`

Maximum allowed active tools.

---

### Methods

#### `register(tool_class: Type[Tool]) -> None`

Register a tool class.

**Parameters:**
- `tool_class` (Type[Tool]): Tool class to register.

**Example:**
```python
registry = ToolRegistry()
registry.register(ReadFileTool)
registry.register(WriteFileTool)
```

---

#### `get_tool(name: str) -> Tool`

Get a tool instance by name.

**Parameters:**
- `name` (str): Tool name.

**Returns:** Tool instance.

**Raises:** ToolNotFoundError if not found.

---

#### `list_tools(category: ToolCategory = None, active_only: bool = False) -> List[Tool]`

List registered tools.

**Parameters:**
- `category` (ToolCategory, optional): Filter by category.
- `active_only` (bool): Only return active tools.

**Returns:** List of Tool instances.

**Example:**
```python
# All tools
all_tools = registry.list_tools()

# File tools only
file_tools = registry.list_tools(category=ToolCategory.FILES)

# Only active tools
active = registry.list_tools(active_only=True)
```

---

#### `load_tool(name: str) -> Tool`

Load and activate a tool.

**Parameters:**
- `name` (str): Tool name.

**Returns:** Activated Tool instance.

---

#### `unload_tool(name: str) -> bool`

Unload/deactivate a tool.

**Parameters:**
- `name` (str): Tool name.

**Returns:** True if unloaded, False if not found or in use.

---

#### `load_category(category: ToolCategory) -> List[Tool]`

Load all tools in a category.

**Parameters:**
- `category` (ToolCategory): Category to load.

**Returns:** List of loaded Tool instances.

---

#### `cleanup_unused(min_idle_time: int = 300) -> int`

Unload tools that haven't been used recently.

**Parameters:**
- `min_idle_time` (int): Minimum idle time in seconds.

**Returns:** Number of tools unloaded.

---

## Class: `ToolRecommender`

AI-powered tool recommendations.

**Module:** `fastband.tools.recommender`

### Methods

#### `async recommend(task_description: str, project_type: str = None, current_files: List[str] = None, limit: int = 10) -> List[ToolRecommendation]`

Get tool recommendations for a task.

**Parameters:**
- `task_description` (str): What you're trying to do.
- `project_type` (str, optional): Project type (web, api, etc.).
- `current_files` (List[str], optional): Files you're working with.
- `limit` (int): Maximum recommendations.

**Returns:** List of ToolRecommendation.

**Example:**
```python
from fastband.tools import ToolRecommender

recommender = ToolRecommender()

recommendations = await recommender.recommend(
    task_description="Refactor authentication module",
    project_type="web",
    current_files=["auth.py", "users.py"]
)

for rec in recommendations:
    print(f"{rec.tool_name}: {rec.confidence}% - {rec.reason}")
```

---

## Class: `ToolRecommendation`

A tool recommendation.

**Module:** `fastband.tools.recommender`

### Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `tool_name` | str | Recommended tool name |
| `confidence` | float | Confidence score (0-100) |
| `reason` | str | Why this tool is recommended |
| `priority` | int | Recommendation priority |

---

## Core Tools Reference

### File Tools

**Module:** `fastband.tools.core.files`

#### `ReadFileTool`

Read file contents.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `file_path` | string | Yes | Path to file |
| `encoding` | string | No | Encoding (default: utf-8) |

**Returns:**
```python
{
    "content": str,      # File contents
    "size": int,         # File size in bytes
    "encoding": str      # Encoding used
}
```

---

#### `WriteFileTool`

Write content to a file.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `file_path` | string | Yes | Path to file |
| `content` | string | Yes | Content to write |
| `create_dirs` | boolean | No | Create parent dirs (default: true) |
| `backup` | boolean | No | Backup existing file (default: true) |

**Returns:**
```python
{
    "written": int,      # Bytes written
    "path": str,         # Absolute path
    "backup_path": str   # Backup file path (if created)
}
```

---

#### `ListDirectoryTool`

List directory contents.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `path` | string | Yes | Directory path |
| `pattern` | string | No | Glob pattern |
| `recursive` | boolean | No | Include subdirs (default: false) |

**Returns:**
```python
{
    "files": List[str],       # File paths
    "directories": List[str], # Directory paths
    "count": int              # Total items
}
```

---

### System Tools

**Module:** `fastband.tools.core.system`

#### `ExecuteCommandTool`

Execute shell commands.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `command` | string | Yes | Command to execute |
| `cwd` | string | No | Working directory |
| `timeout` | integer | No | Timeout in seconds (default: 60) |
| `capture_output` | boolean | No | Capture output (default: true) |

**Returns:**
```python
{
    "stdout": str,       # Standard output
    "stderr": str,       # Standard error
    "return_code": int   # Exit code
}
```

---

#### `GetEnvironmentTool`

Get environment variables.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `name` | string | No | Specific variable name |
| `prefix` | string | No | Filter by prefix |

**Returns:**
```python
{
    "variables": Dict[str, str]  # Environment variables
}
```

---

### Web Tools

**Module:** `fastband.tools.web`

#### `BrowserAutomationTool`

Automate browser interactions like a human user - clicking, typing, filling forms, and navigating pages.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `url` | string | Yes | Target page URL |
| `action` | string | Yes | Action: click, type, fill, wait, scroll, select, hover, press, goto |
| `selector` | string | No | CSS selector for element (required for most actions) |
| `value` | string | No | Value for type/fill/select/press actions |
| `wait_ms` | integer | No | Wait time in milliseconds (default: 1000) |
| `screenshot` | boolean | No | Take screenshot after action (default: false) |

**Returns:**
```python
{
    "success": bool,         # Whether action succeeded
    "action": str,           # Action performed
    "selector": str,         # Selector used
    "screenshot_path": str,  # Path to screenshot (if taken)
    "page_url": str,         # Current page URL after action
    "page_title": str        # Current page title
}
```

**Example:**
```python
# Login form automation
await browser_automation.execute(
    url="https://app.example.com/login",
    action="fill",
    selector="#username",
    value="user@example.com"
)
await browser_automation.execute(
    url="https://app.example.com/login",
    action="fill",
    selector="#password",
    value="password123"
)
await browser_automation.execute(
    url="https://app.example.com/login",
    action="click",
    selector="button[type='submit']",
    screenshot=True
)
```

---

#### `QAConsoleSweepTool`

Sweep multiple pages for JavaScript console errors, network failures, and runtime issues.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `base_url` | string | Yes | Base URL of the application |
| `pages` | array | Yes | List of page paths to check |
| `auth` | object | No | Authentication credentials |
| `wait_per_page` | integer | No | Wait time per page in ms (default: 2000) |
| `capture_screenshots` | boolean | No | Capture screenshots on errors (default: true) |

**Returns:**
```python
{
    "total_pages": int,          # Pages checked
    "pages_with_errors": int,    # Pages with issues
    "error_summary": {           # Error breakdown
        "js_errors": int,
        "network_failures": int,
        "console_warnings": int
    },
    "details": List[{            # Per-page details
        "path": str,
        "status": str,
        "errors": List[str],
        "screenshot": str        # Path if captured
    }]
}
```

**Example:**
```python
result = await qa_console_sweep.execute(
    base_url="https://myapp.com",
    pages=["/", "/dashboard", "/settings", "/profile"],
    capture_screenshots=True
)

if result.data["pages_with_errors"] > 0:
    for page in result.data["details"]:
        if page["errors"]:
            print(f"Errors on {page['path']}: {page['errors']}")
```

---

### Testing Tools

**Module:** `fastband.tools.testing`

#### `AgentTesterTool`

Run end-to-end tests simulating agent workflows - page loads, form submissions, and navigation flows.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `base_url` | string | Yes | Application base URL |
| `test_type` | string | Yes | Test type: page_load, form_submit, navigation_flow |
| `test_config` | object | Yes | Test-specific configuration |
| `timeout_seconds` | integer | No | Test timeout (default: 30) |

**Test Configurations:**

`page_load`:
```python
{
    "pages": ["/", "/about", "/contact"],
    "expected_elements": ["#main", ".nav"]
}
```

`form_submit`:
```python
{
    "form_url": "/login",
    "fields": {"username": "test", "password": "test"},
    "submit_selector": "button[type='submit']",
    "success_indicator": ".dashboard"
}
```

`navigation_flow`:
```python
{
    "steps": [
        {"goto": "/"},
        {"click": ".start-button"},
        {"wait": 2000},
        {"assert": ".step-2-content"}
    ]
}
```

**Returns:**
```python
{
    "test_type": str,       # Type of test run
    "passed": bool,         # Overall pass/fail
    "duration_ms": int,     # Execution time
    "results": List[{       # Individual test results
        "name": str,
        "passed": bool,
        "message": str,
        "screenshot": str   # If failure
    }]
}
```

---

#### `ScreenshotValidatorTool`

Validate screenshots using Claude Vision for proof-of-work verification.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `screenshot_path` | string | Yes | Path to screenshot file |
| `expected_state` | string | Yes | Description of expected state |
| `validation_rules` | array | No | Specific elements to verify |
| `confidence_threshold` | number | No | Min confidence (default: 0.8) |

**Returns:**
```python
{
    "valid": bool,              # Overall validation result
    "confidence": float,        # Confidence score (0-1)
    "matches": List[str],       # Elements found matching expectations
    "mismatches": List[str],    # Elements not matching
    "analysis": str,            # Vision model analysis
    "recommendations": List[str] # Improvement suggestions
}
```

**Example:**
```python
result = await screenshot_validator.execute(
    screenshot_path="/tmp/login_success.png",
    expected_state="User successfully logged in, showing dashboard",
    validation_rules=[
        "Dashboard header visible",
        "User avatar in top right",
        "Navigation menu present"
    ]
)

if result.data["valid"]:
    print(f"Screenshot validated with {result.data['confidence']:.0%} confidence")
else:
    print(f"Issues found: {result.data['mismatches']}")
```

---

### Memory Tools

**Module:** `fastband.tools.memory`

Claude Memory System for cross-session learning and pattern recognition.

#### `memory_query`

Query past ticket memories for relevant context and fix patterns.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `query` | string | Yes | Natural language search query |
| `app` | string | No | Filter by application name |
| `ticket_type` | string | No | Filter: Bug, Feature, Enhancement |
| `files` | array | No | Files involved (finds related tickets) |
| `session_id` | string | No | Session ID for context tracking |
| `max_results` | integer | No | Maximum results (default: 10) |

**Returns:**
```python
{
    "memories_found": int,      # Number of relevant memories
    "patterns_found": int,      # Number of relevant patterns
    "context": str,             # Formatted context for agent
    "memory_ids": List[str],    # IDs of matched memories
    "pattern_ids": List[str],   # IDs of matched patterns
    "session_id": str           # Session tracking ID
}
```

---

#### `memory_start_session`

Start a memory session for context tracking (avoids repetition).

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `agent_name` | string | Yes | Agent identifier (e.g., "MCP_Agent1") |
| `current_app` | string | No | Application being worked on |
| `current_ticket` | string | No | Current ticket number |

**Returns:**
```python
{
    "session_id": str,      # Use this in subsequent queries
    "agent_name": str,
    "current_app": str,
    "current_ticket": str,
    "started_at": str,
    "message": str
}
```

---

#### `memory_add_discovery`

Record a discovery during the session for cross-session learning.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `session_id` | string | Yes | Session ID from memory_start_session |
| `discovery` | string | Yes | What was discovered |
| `category` | string | No | Category: bug_cause, code_pattern, gotcha, tip, general |

---

#### `memory_commit`

Commit a resolved ticket to Claude Memory.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `ticket_id` | string | Yes | Ticket number |
| `app` | string | Yes | Application identifier |
| `title` | string | Yes | Ticket title |
| `problem_summary` | string | Yes | What was wrong |
| `solution_summary` | string | Yes | How it was fixed |
| `files_modified` | array | Yes | Files that were changed |
| `ticket_type` | string | No | Bug, Feature, Enhancement (default: Bug) |

---

#### `memory_get_patterns`

Get learned fix patterns from cross-session analysis.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `query` | string | No | Optional filter query |
| `limit` | integer | No | Max patterns to return (default: 10) |

**Returns:**
```python
{
    "patterns_count": int,
    "patterns": List[{
        "pattern_id": str,
        "name": str,
        "description": str,
        "occurrence_count": int,
        "common_files": List[str],
        "solution_template": str,
        "example_tickets": List[str]
    }]
}
```

---

#### `memory_stats`

Get Claude Memory system statistics.

**Returns:**
```python
{
    "total_memories": int,
    "total_patterns": int,
    "active_sessions": int,
    "memories_by_app": Dict[str, int],
    "memories_by_type": Dict[str, int],
    "storage_size_kb": int
}
```

---

#### `memory_extract_patterns`

Run pattern extraction from resolved tickets (maintenance).

Analyzes past tickets to find common fix patterns. Run periodically (weekly recommended).

---

#### `memory_prune`

Prune stale memories (self-healing maintenance).

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `dry_run` | boolean | No | If True, show what would be pruned (default: true) |

---

## Exceptions

### `ToolError`

Base exception for tool errors.

**Module:** `fastband.tools`

---

### `ToolNotFoundError`

Raised when a tool is not found.

**Module:** `fastband.tools`

---

### `ToolExecutionError`

Raised when tool execution fails.

**Module:** `fastband.tools`

---

### `ToolValidationError`

Raised when tool parameters are invalid.

**Module:** `fastband.tools`

---

### `ToolLimitExceededError`

Raised when maximum active tools exceeded.

**Module:** `fastband.tools`

# Tool Garage Guide

The Tool Garage is Fastband's dynamic tool management system. It provides the right tools at the right time, preventing overload while keeping essential capabilities available.

## Concept

> **"A toolbox that travels with you - always the right tools, never too many, ready to grow."**

Unlike static tool collections, the Tool Garage:
- **Loads core tools** automatically for every project
- **Recommends tools** based on your project type and current task
- **Monitors performance** to prevent slowdowns
- **Dynamically loads** tools as needed

## Tool Categories

Tools are organized into categories:

| Category | Description | Examples |
|----------|-------------|----------|
| `files` | File operations | read_file, write_file, list_directory |
| `system` | System operations | execute_command, get_environment |
| `git` | Git operations | git_status, git_commit, git_diff |
| `web` | Web/HTTP operations | fetch_url, web_search |
| `tickets` | Ticket management | list_tickets, claim_ticket |

## Core Tools

Core tools are always available and loaded automatically:

### File Tools

| Tool | Description |
|------|-------------|
| `read_file` | Read file contents |
| `write_file` | Write content to a file |
| `list_directory` | List directory contents |
| `search_files` | Search for files by pattern |
| `file_info` | Get file metadata |

### System Tools

| Tool | Description |
|------|-------------|
| `execute_command` | Run shell commands |
| `get_environment` | Get environment variables |
| `get_system_info` | Get OS and hardware info |

## Using Tools

### List Available Tools

```bash
# List all tools
fastband tools list

# Filter by category
fastband tools list --category files
fastband tools list --category git

# Show only active tools
fastband tools list --active
```

### View Tool Details

```bash
fastband tools show read_file
```

Output:
```
Tool: read_file
Category: files
Version: 1.0.0

Description:
  Read the contents of a file from the filesystem.

Parameters:
  - file_path (string, required): Path to the file to read
  - encoding (string, optional): File encoding (default: utf-8)

Example:
  read_file(file_path="/app/config.yaml")
```

### Load/Unload Tools

```bash
# Load a tool
fastband tools load git_diff

# Unload a tool (if not in use)
fastband tools unload git_diff

# Load a category
fastband tools load --category git
```

## Tool Registry

### Programmatic Access

```python
from fastband.tools import ToolRegistry, get_registry

# Get the global registry
registry = get_registry()

# List all available tools
for tool in registry.list_tools():
    print(f"{tool.name}: {tool.definition.description}")

# Get a specific tool
tool = registry.get_tool("read_file")

# Execute a tool
result = await tool.execute(file_path="/path/to/file")
if result.success:
    print(result.data)
else:
    print(f"Error: {result.error}")
```

### Registering Custom Tools

```python
from fastband.tools import Tool, ToolDefinition, ToolMetadata, ToolParameter, ToolResult
from fastband.tools import ToolCategory, register_tool

class MyCustomTool(Tool):
    """Custom tool implementation."""

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            metadata=ToolMetadata(
                name="my_custom_tool",
                description="Does something custom",
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
        )

    async def execute(self, input: str, **kwargs) -> ToolResult:
        # Your implementation here
        result = f"Processed: {input}"
        return ToolResult(success=True, data={"output": result})

# Register the tool
register_tool(MyCustomTool)
```

## AI-Powered Recommendations

The Tool Recommender suggests tools based on your project and task:

```python
from fastband.tools import ToolRecommender

recommender = ToolRecommender()

# Get recommendations for a task
recommendations = await recommender.recommend(
    task_description="I need to refactor the authentication module",
    project_type="web",
    current_files=["auth.py", "users.py"]
)

for rec in recommendations:
    print(f"{rec.tool_name}: {rec.confidence}% - {rec.reason}")
```

Output:
```
read_file: 95% - Need to read current code
write_file: 90% - Will modify files
git_diff: 85% - Track changes during refactor
search_files: 70% - Find related files
```

### Recommendation Criteria

The recommender considers:
1. **Project type** - Web, API, CLI, etc.
2. **Language** - Python, JavaScript, etc.
3. **Current task** - What you're trying to do
4. **File context** - Files you're working with
5. **Tool dependencies** - Tools that work together

## Performance Management

### Tool Limits

Configure limits to prevent performance issues:

```yaml
# .fastband/config.yaml
tools:
  max_active: 60                        # Maximum active tools
  performance_warning_threshold: 40     # Warn when exceeded
  auto_load_core: true                  # Load core tools on startup
```

### Monitoring

```bash
# Check tool performance
fastband tools status

# Output:
# Active Tools: 35/60
# Core Tools: 15 (always loaded)
# Dynamic Tools: 20
# Status: Healthy
```

### Auto-Unload

When approaching limits, low-priority tools are automatically unloaded:

```python
from fastband.tools import get_registry

registry = get_registry()

# Check current load
print(f"Active: {registry.active_count}/{registry.max_active}")

# Force unload unused tools
registry.cleanup_unused(min_idle_time=300)  # 5 minutes
```

## Tool Definition Schema

Every tool follows this structure:

```python
ToolDefinition(
    metadata=ToolMetadata(
        name="tool_name",           # Unique identifier
        description="What it does", # Human-readable description
        category=ToolCategory.FILES,# Category for organization
        version="1.0.0",            # Semantic version
        tags=["file", "read"],      # Searchable tags
    ),
    parameters=[
        ToolParameter(
            name="param_name",
            type="string",          # string, integer, boolean, array, object
            description="What this parameter does",
            required=True,
            default=None,           # Default value if optional
            enum=["opt1", "opt2"],  # Allowed values (optional)
        ),
    ],
    returns={                       # Return type documentation
        "type": "object",
        "properties": {
            "content": {"type": "string"},
        },
    },
)
```

## Tool Results

All tools return a `ToolResult`:

```python
@dataclass
class ToolResult:
    success: bool                    # Did the operation succeed?
    data: Optional[Dict[str, Any]]   # Result data if successful
    error: Optional[str]             # Error message if failed
    metadata: Dict[str, Any]         # Additional metadata
```

Usage:

```python
result = await tool.execute(file_path="/app/config.yaml")

if result.success:
    content = result.data["content"]
    print(f"File contains {len(content)} characters")
else:
    print(f"Failed: {result.error}")
```

## Built-in Tool Reference

### File Tools

#### read_file

Read file contents.

```python
result = await read_file.execute(
    file_path="/path/to/file.py",
    encoding="utf-8"
)
# Returns: {"content": "file contents...", "size": 1234}
```

#### write_file

Write content to a file.

```python
result = await write_file.execute(
    file_path="/path/to/file.py",
    content="# New content\n...",
    create_dirs=True,    # Create parent directories
    backup=True          # Backup existing file
)
# Returns: {"written": 156, "path": "/path/to/file.py"}
```

#### list_directory

List directory contents.

```python
result = await list_directory.execute(
    path="/app",
    pattern="*.py",      # Glob pattern
    recursive=False      # Include subdirectories
)
# Returns: {"files": [...], "directories": [...]}
```

### System Tools

#### execute_command

Run shell commands safely.

```python
result = await execute_command.execute(
    command="python -m pytest tests/",
    cwd="/app",
    timeout=60,
    capture_output=True
)
# Returns: {"stdout": "...", "stderr": "...", "return_code": 0}
```

## Best Practices

### 1. Use the Right Tool for the Job

```python
# Good - use specialized tool
result = await search_files.execute(pattern="*.py", path="/app")

# Avoid - don't shell out when tools exist
result = await execute_command.execute(command="find . -name '*.py'")
```

### 2. Handle Errors Gracefully

```python
result = await read_file.execute(file_path="/missing.txt")
if not result.success:
    if "not found" in result.error:
        # Handle missing file
        pass
    else:
        # Handle other errors
        raise Exception(result.error)
```

### 3. Batch Operations When Possible

```python
# Instead of many individual calls
files = ["a.py", "b.py", "c.py"]
contents = {}
for f in files:
    result = await read_file.execute(file_path=f)
    contents[f] = result.data["content"]

# Consider using batch-aware patterns
results = await asyncio.gather(*[
    read_file.execute(file_path=f) for f in files
])
```

### 4. Monitor Tool Usage

```bash
# Check what's loaded
fastband tools list --active

# Unload unused tools periodically
fastband tools cleanup
```

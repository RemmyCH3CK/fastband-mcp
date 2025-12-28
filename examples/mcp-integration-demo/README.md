# MCP Integration Demo

Demonstrates how to integrate Fastband MCP with AI clients like Claude Code,
or build your own MCP-aware applications.

## Overview

This example shows:
- How to configure MCP server for AI clients
- Example MCP tool usage patterns
- Building applications that use Fastband MCP programmatically
- Integration with different AI providers

## Prerequisites

- Python 3.10+
- Fastband MCP installed (`pip install fastband-mcp`)
- An AI provider API key (Claude, OpenAI, etc.)

## Setup

1. **Install dependencies:**

   ```bash
   cd examples/mcp-integration-demo
   pip install -r requirements.txt
   ```

2. **Set environment variables:**

   ```bash
   # For Claude
   export ANTHROPIC_API_KEY=your-api-key

   # Or for OpenAI
   export OPENAI_API_KEY=your-api-key
   ```

## MCP Server Configuration

### For Claude Code

To use Fastband MCP with Claude Code, add this to your Claude configuration:

**macOS/Linux:** `~/.config/claude/claude_desktop_config.json`
**Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "fastband": {
      "command": "fastband",
      "args": ["serve"],
      "cwd": "/path/to/your/project"
    }
  }
}
```

Or with Python directly:

```json
{
  "mcpServers": {
    "fastband": {
      "command": "python",
      "args": ["-m", "fastband", "serve"],
      "cwd": "/path/to/your/project"
    }
  }
}
```

### For Other MCP Clients

Fastband MCP follows the standard MCP protocol. Configuration varies by client:

- **Stdio transport** (default): Use `fastband serve` as the command
- **HTTP transport**: Coming in a future release

## Example Scripts

### 1. Basic MCP Tool Usage (`tool_usage.py`)

Shows how to programmatically use Fastband tools:

```bash
python tool_usage.py
```

This script demonstrates:
- Listing available tools
- Executing tools with parameters
- Handling tool results

### 2. AI-Assisted Development (`ai_assistant.py`)

Shows how to build an AI assistant that uses Fastband tools:

```bash
python ai_assistant.py
```

This script demonstrates:
- Connecting to an AI provider
- Providing Fastband tools to the AI
- Processing AI tool calls

### 3. Custom Tool Creation (`custom_tool.py`)

Shows how to create and register custom tools:

```bash
python custom_tool.py
```

## Project Structure

```
mcp-integration-demo/
├── tool_usage.py        # Direct tool usage example
├── ai_assistant.py      # AI assistant integration
├── custom_tool.py       # Custom tool creation
├── mcp_config.json      # Example MCP configuration
├── requirements.txt     # Python dependencies
└── README.md            # This file
```

## MCP Protocol Overview

Fastband MCP implements the Model Context Protocol:

### Available Tools

After starting the server, these tools are available:

| Tool | Description |
|------|-------------|
| `list_files` | List files in a directory |
| `read_file` | Read file contents |
| `write_file` | Write content to a file |
| `search_code` | Search for patterns in code |
| `get_system_info` | Get system information |
| `run_command` | Execute shell commands |

Use `fastband tools list` to see all available tools.

### Tool Schema

Tools follow the MCP schema format:

```json
{
  "name": "read_file",
  "description": "Read the contents of a file",
  "inputSchema": {
    "type": "object",
    "properties": {
      "path": {
        "type": "string",
        "description": "Path to the file"
      },
      "offset": {
        "type": "integer",
        "description": "Line to start reading from"
      },
      "limit": {
        "type": "integer",
        "description": "Maximum lines to read"
      }
    },
    "required": ["path"]
  }
}
```

### Tool Response

Tools return structured responses:

```json
{
  "success": true,
  "data": {
    "path": "/path/to/file",
    "content": "file contents...",
    "total_lines": 100
  }
}
```

Or on error:

```json
{
  "success": false,
  "error": "File not found: /path/to/file"
}
```

## Integration Patterns

### Pattern 1: Direct Tool Execution

```python
from fastband.core.engine import FastbandEngine

engine = FastbandEngine()
engine.register_core_tools()

result = await engine.execute_tool("read_file", path="main.py")
if result.success:
    print(result.data["content"])
```

### Pattern 2: MCP Client Integration

```python
# Tools are exposed via MCP protocol
# AI clients can call them directly

# Example: Claude calling the read_file tool
# The AI formats the response for the user
```

### Pattern 3: Tool Composition

```python
# Chain multiple tools together
files = await engine.execute_tool("list_files", path="src/", pattern="*.py")

for file in files.data["files"]:
    content = await engine.execute_tool("read_file", path=file["path"])
    # Process content...
```

## AI Provider Integration

### Claude (Anthropic)

```python
import anthropic
from fastband.core.engine import FastbandEngine

client = anthropic.Anthropic()
engine = FastbandEngine()
engine.register_core_tools()

# Get tools in Claude's format
tools = engine.get_tool_schemas()

response = client.messages.create(
    model="claude-sonnet-4-20250514",
    tools=tools,
    messages=[{"role": "user", "content": "List Python files in src/"}]
)
```

### OpenAI

```python
import openai
from fastband.core.engine import FastbandEngine

client = openai.OpenAI()
engine = FastbandEngine()
engine.register_core_tools()

# Get tools in OpenAI's format
tools = engine.get_openai_schemas()

response = client.chat.completions.create(
    model="gpt-4-turbo",
    tools=tools,
    messages=[{"role": "user", "content": "List Python files in src/"}]
)
```

## Debugging

### View Tool Calls

Set logging to debug:

```bash
FASTBAND_LOG_LEVEL=debug fastband serve
```

### Test Tools Manually

```bash
# List available tools
fastband tools list

# Check tool details
fastband tools info read_file
```

## Next Steps

- Read the Fastband MCP documentation
- Explore the `web-app-demo` for web development integration
- Check the `cli-tool-demo` for ticket workflow examples

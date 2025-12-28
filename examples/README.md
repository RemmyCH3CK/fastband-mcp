# Fastband MCP Examples

This directory contains example projects demonstrating how to use Fastband MCP in different scenarios.

## Examples

### 1. Web App Demo (`web-app-demo/`)

A simple Flask web application showing how to use Fastband MCP for web development.

**Features demonstrated:**
- Project initialization with `fastband init`
- Ticket management for development tasks
- Basic `.fastband/` configuration

```bash
cd web-app-demo
pip install -r requirements.txt
python app.py
```

### 2. CLI Tool Demo (`cli-tool-demo/`)

A file organizer CLI tool demonstrating the complete Fastband ticket workflow.

**Features demonstrated:**
- Complete ticket lifecycle (create, claim, complete)
- Ticket filtering and searching
- CLI development patterns

```bash
cd cli-tool-demo
pip install -r requirements.txt
python organizer.py --help
```

### 3. MCP Integration Demo (`mcp-integration-demo/`)

Examples of integrating Fastband MCP with AI clients and building custom tools.

**Features demonstrated:**
- MCP server configuration for Claude Code
- Direct tool usage with Python
- AI assistant integration
- Custom tool creation

```bash
cd mcp-integration-demo
pip install -r requirements.txt
python tool_usage.py
```

## Quick Start

1. **Install Fastband MCP:**
   ```bash
   pip install fastband-mcp
   ```

2. **Choose an example:**
   ```bash
   cd examples/web-app-demo  # or another example
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Initialize Fastband (if needed):**
   ```bash
   fastband init
   ```

5. **Check status:**
   ```bash
   fastband status
   ```

## Common Commands

```bash
# Initialize a project
fastband init

# Check project status
fastband status

# List available tools
fastband tools list

# Ticket management
fastband tickets list
fastband tickets create --title "My task" --type feature
fastband tickets claim 1 --agent "Developer"
fastband tickets complete 1 --problem "..." --solution "..."

# Start MCP server
fastband serve
```

## Configuration

Each example includes a `.fastband/config.yaml` file. Key settings:

```yaml
fastband:
  version: "1.2025.12"

  ai:
    default_provider: "claude"

  tickets:
    enabled: true
    mode: "cli"  # or "cli_web"

  tools:
    max_active: 60
    auto_load_core: true
```

## Learning Path

1. **Start with `web-app-demo`** - Learn basic project setup
2. **Try `cli-tool-demo`** - Master the ticket workflow
3. **Explore `mcp-integration-demo`** - Integrate with AI clients

## Need Help?

- Check individual example READMEs for detailed instructions
- See the main [Fastband MCP documentation](../README.md)
- Open an issue on GitHub

# Setting Up Fastband as Your MCP Server

This guide walks you through connecting Fastband MCP to Claude Code or Claude Desktop, step by step.

## What is MCP?

MCP (Model Context Protocol) lets AI assistants like Claude use tools to read files, search code, manage tickets, and more. Fastband is an MCP server that provides these tools.

**Think of it like this:**
- Claude = the brain
- MCP = the hands
- Fastband = the toolbox

## Prerequisites

Before starting, make sure you have:

- [ ] Python 3.10 or higher installed
- [ ] Claude Code CLI or Claude Desktop app
- [ ] A project folder you want to work on

## Step 1: Install Fastband

Open your terminal and run:

```bash
pip install fastband-mcp[claude]
```

Verify it installed:

```bash
fastband --version
```

You should see something like `fastband version 1.2025.12.0`.

## Step 2: Initialize Your Project

Navigate to your project folder:

```bash
cd /path/to/your/project
```

Run the setup wizard:

```bash
fastband init
```

This creates a `.fastband/` folder with your configuration. Follow the prompts to:
- Detect your project type
- Choose an AI provider
- Select which tools to enable
- Generate an Agent Bible (rules for AI agents)

## Step 3: Configure Claude to Use Fastband

### Option A: Claude Code (CLI)

Add Fastband to your Claude Code MCP configuration:

**On macOS/Linux:**
```bash
mkdir -p ~/.claude
```

**Edit `~/.claude/claude_desktop_config.json`:**
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

Replace `/path/to/your/project` with your actual project path.

### Option B: Claude Desktop App

1. Open Claude Desktop
2. Go to **Settings** > **Developer** > **MCP Servers**
3. Click **Add Server**
4. Enter:
   - **Name:** `fastband`
   - **Command:** `fastband`
   - **Arguments:** `serve`
   - **Working Directory:** `/path/to/your/project`
5. Click **Save**

### Option C: Project-Specific Config

Create a `.claude/mcp.json` in your project folder:

```json
{
  "mcpServers": {
    "fastband": {
      "command": "fastband",
      "args": ["serve"]
    }
  }
}
```

This way, Fastband only runs when you're in that project.

## Step 4: Test the Connection

Restart Claude Code or Claude Desktop, then try:

```
Can you list the available Fastband tools?
```

Claude should respond with a list of tools like `read_file`, `write_file`, `search_code`, etc.

## Step 5: Start Using Fastband

Now Claude can use Fastband tools. Try these:

```
Read the README.md file
```

```
Search for all Python files in this project
```

```
Create a ticket for adding user authentication
```

## Common Workflows

### Working on a Feature

1. Create a ticket:
   ```
   Create a ticket: "Add dark mode toggle" with priority high
   ```

2. Let Claude work on it:
   ```
   Claim ticket #1 and start implementing dark mode
   ```

3. Claude will read files, make changes, and complete the ticket

### Code Review

1. Claude submits work for review
2. Review agents (if configured) check the changes
3. Human approves or requests changes

## Troubleshooting

### "fastband: command not found"

The `fastband` command isn't in your PATH. Try:

```bash
# Find where it's installed
python -c "import fastband; print(fastband.__file__)"

# Or use the full path
which python  # Note this path
# Then use: /path/to/python -m fastband serve
```

Update your MCP config to use the full path:

```json
{
  "mcpServers": {
    "fastband": {
      "command": "/usr/local/bin/python3",
      "args": ["-m", "fastband", "serve"],
      "cwd": "/path/to/your/project"
    }
  }
}
```

### "No .fastband directory found"

You need to initialize your project first:

```bash
cd /path/to/your/project
fastband init
```

### Claude doesn't see the tools

1. Make sure Claude Code/Desktop was restarted after config changes
2. Check the MCP server logs:
   ```bash
   fastband serve --verbose
   ```
3. Verify your JSON config is valid (no trailing commas, proper quotes)

### Tools are slow

Some operations (like searching large codebases) take time. You can:
- Configure tool timeouts in `.fastband/config.yaml`
- Use more specific search patterns

## Next Steps

- [Quick Start Tutorial](quickstart.md) - Learn the CLI commands
- [Tool Garage Guide](../guides/tool-garage.md) - Explore all available tools
- [Ticket Manager Guide](../guides/ticket-manager.md) - Set up ticket workflows

## Getting Help

- Check the [GitHub Issues](https://github.com/RemmyCH3CK/fastband-mcp/issues)
- Review error logs: `fastband serve --verbose`
- Join the community discussions

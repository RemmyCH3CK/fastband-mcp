# Quick Start Tutorial

Get up and running with Fastband MCP in 5 minutes.

## Initialize a Project

Navigate to your project directory and run the init command:

```bash
cd /your/project
fastband init
```

This launches the interactive setup wizard that will:

1. **Detect your project type** - Identifies language, frameworks, and package managers
2. **Recommend AI provider** - Suggests the best provider for your project
3. **Configure GitHub integration** - Optional PR/issue automation
4. **Select tools** - Recommends tools based on your project
5. **Set up tickets** - Configure ticket management mode
6. **Configure backups** - Set up automatic backup schedules

### Non-Interactive Mode

For CI/CD or scripted setups:

```bash
fastband init --skip-detection
```

### Re-initialize

To reinitialize an existing project:

```bash
fastband init --force
```

## Project Structure

After initialization, Fastband creates a `.fastband/` directory:

```
your-project/
├── .fastband/
│   ├── config.yaml      # Main configuration
│   ├── data.db          # SQLite database (tickets, etc.)
│   └── backups/         # Automatic backups
├── ... your project files
```

## Basic Commands

### Check Status

View your project configuration and server status:

```bash
fastband status

# Verbose output with provider details
fastband status --verbose
```

### List Available Tools

See what tools are available:

```bash
# List all tools
fastband tools list

# Filter by category
fastband tools list --category files
fastband tools list --category git

# Show tool details
fastband tools show read_file
```

### Manage Tickets

Create and track development tasks:

```bash
# List all tickets
fastband tickets list

# Create a new ticket
fastband tickets create "Add user authentication"

# Create with details
fastband tickets create "Fix login bug" \
  --type bug \
  --priority high \
  --description "Users cannot login with email"

# Claim a ticket (for AI agents)
fastband tickets claim 1 --agent "MCP_Agent1"

# View ticket details
fastband tickets show 1
```

### Start the MCP Server

Launch the MCP server for AI tool access:

```bash
fastband serve
```

The server starts and waits for MCP client connections.

## Configuration

View or modify your configuration:

```bash
# Show current configuration
fastband config show

# Get a specific value
fastband config get ai.default_provider

# Set a value
fastband config set ai.default_provider openai
fastband config set tools.max_active 40
fastband config set tickets.enabled true

# Reset to defaults
fastband config reset --yes
```

## Working with AI Providers

Switch between AI providers easily:

```python
from fastband import get_provider

# Get configured provider
claude = get_provider("claude")
openai = get_provider("openai")

# Use the provider
response = await claude.complete("Explain this code...")
```

In your configuration:

```yaml
# .fastband/config.yaml
fastband:
  ai:
    default_provider: "claude"
    providers:
      claude:
        model: "claude-sonnet-4-20250514"
      openai:
        model: "gpt-4-turbo"
```

## Example Workflow

Here's a typical development workflow with Fastband:

### 1. Start a new feature

```bash
# Create a ticket
fastband tickets create "Add dark mode toggle" \
  --type feature \
  --priority medium

# Output: Created ticket #1
```

### 2. Claim the ticket

```bash
fastband tickets claim 1 --agent "MCP_Agent1"
```

### 3. Work on the feature

Use your AI assistant (Claude, ChatGPT, etc.) connected via MCP to:
- Read and understand the codebase
- Make changes to files
- Run tests

### 4. Complete the work

```bash
# Mark ticket as complete (submits for review)
fastband tickets complete 1 \
  --problem "No dark mode option" \
  --solution "Added toggle in settings panel" \
  --files-modified "settings.py,styles.css"
```

### 5. Review and approve

```bash
# View pending reviews
fastband tickets list --status under_review

# Approve the work (human reviewer)
fastband tickets approve 1 --reviewer "human"
```

## Web Dashboard

Start the ticket management web interface:

```bash
fastband tickets serve --port 5050
```

Open http://localhost:5050 in your browser for:
- Visual ticket board
- Statistics dashboard
- Agent status monitoring
- Dark/light mode toggle

## Next Steps

- [Configuration Reference](configuration.md) - Deep dive into all options
- [AI Providers Guide](../guides/ai-providers.md) - Provider-specific setup
- [Tool Garage](../guides/tool-garage.md) - Understanding the tool system
- [Ticket Manager](../guides/ticket-manager.md) - Complete ticket workflow

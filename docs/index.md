# Fastband MCP Documentation

Welcome to the Fastband MCP documentation. Fastband is a universal AI-powered development platform that provides an AI-agnostic MCP server with adaptive tools, ticket management, and multi-agent coordination.

## Getting Started

New to Fastband? Start here:

- [Installation Guide](getting-started/installation.md) - Install Fastband MCP on your system
- [MCP Setup Guide](getting-started/mcp-setup.md) - Connect Fastband to Claude Code/Desktop (step-by-step)
- [Quick Start Tutorial](getting-started/quickstart.md) - Learn the CLI commands
- [Configuration Reference](getting-started/configuration.md) - Complete configuration options

## Guides

In-depth guides for key features:

- [AI Providers Guide](guides/ai-providers.md) - Using Claude, OpenAI, Gemini, and Ollama
- [Tool Garage](guides/tool-garage.md) - Understanding the dynamic tool system
- [Ticket Manager](guides/ticket-manager.md) - Task tracking and workflow management
- [Backup Manager](guides/backup-manager.md) - Automated backups and restoration

## API Reference

Detailed API documentation:

- [Providers API](api/providers.md) - AI provider interfaces and classes
- [Tools API](api/tools.md) - Tool system classes and registry
- [Tickets API](api/tickets.md) - Ticket management classes and tools

## Architecture & Design (Internal)

Internal planning and design documents:

- [Product Vision](internal/FASTBAND_PRODUCT_VISION.md) - Project goals and vision
- [Architecture](internal/FASTBAND_ARCHITECTURE.md) - Technical architecture
- [Implementation Roadmap](internal/FASTBAND_IMPLEMENTATION_ROADMAP.md) - Development timeline
- [Ticket Manager Design](internal/FASTBAND_TICKET_MANAGER.md) - Ticket system design
- [Companion Products](internal/FASTBAND_COMPANION_PRODUCTS.md) - Related tools and extensions

## Quick Links

### Installation

```bash
# Basic installation
pip install fastband-mcp

# With Claude support
pip install fastband-mcp[claude]

# Full installation
pip install fastband-mcp[full]
```

### Initialize a Project

```bash
cd /your/project
fastband init
```

### Common Commands

```bash
# Check status
fastband status

# List tools
fastband tools list

# Manage tickets
fastband tickets list
fastband tickets create "Add feature X"

# Start web dashboard
fastband tickets serve --port 5050

# Start MCP server
fastband serve
```

## Support

- [GitHub Issues](https://github.com/RemmyCH3CK/fastband-mcp/issues) - Report bugs or request features
- [GitHub Discussions](https://github.com/RemmyCH3CK/fastband-mcp/discussions) - Ask questions and share ideas

## License

Fastband MCP is released under the MIT License. See [LICENSE](../LICENSE) for details.

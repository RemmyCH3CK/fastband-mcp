# Fastband MCP

**Universal AI-powered development platform** - An AI-agnostic MCP server with adaptive tools, ticket management, and multi-agent coordination.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Version](https://img.shields.io/badge/version-v1.2025.12.0--alpha.1-green.svg)](https://github.com/RemmyCH3CK/fastband-mcp/releases)

---

## Vision

> **"A toolbox that travels with you - always the right tools, never too many, ready to grow."**

Fastband MCP transforms AI-assisted development from a project-specific setup into a **universal platform** that:

- Works with **any AI provider** (Claude, OpenAI, Gemini, local LLMs)
- Adapts to **any project type** (web, mobile, desktop, API)
- Scales from **solo developers to enterprise teams**
- Provides **intelligent tool recommendations** based on your project
- Includes **built-in ticket management** that adapts to your workflow
- Enables **multi-agent coordination** for parallel AI workflows

---

## Features

### AI-Agnostic Design
```python
# Switch between providers seamlessly
from fastband import get_provider

claude = get_provider("claude")
openai = get_provider("openai")
local = get_provider("ollama")
```

### Tool Garage System
- **Core tools** always available
- **AI-recommended** tools based on your project
- **Dynamic loading** - add tools as your project grows
- **Performance monitoring** to prevent overload

### Adaptive Ticket Manager
| Project Type | Interface |
|--------------|-----------|
| Web App | CLI + Web Dashboard |
| Desktop App | Embedded Panel (Ctrl+Shift+T) |
| Mobile App | CLI + Companion Web |
| API/Library | CLI only |

### Multi-Agent Coordination
- **Clearance system** for parallel work
- **Hold directives** for critical operations
- **Rebuild announcements** to prevent conflicts

### Automated Backups
- **Change detection** - only backup when needed
- **Multiple database support** - SQLite, PostgreSQL, MySQL
- **Configurable retention** policies

---

## Quick Start

### Installation

```bash
# Basic installation
pip install fastband-mcp

# With Claude support
pip install fastband-mcp[claude]

# With all AI providers
pip install fastband-mcp[all-providers]

# Full installation (all features)
pip install fastband-mcp[full]
```

### Initialize a Project

```bash
cd /your/project
fastband init
```

This launches the setup wizard that will:
1. Detect your project type
2. Recommend AI provider
3. Configure GitHub integration
4. Select appropriate tools
5. Set up ticket management
6. Configure backups

### Basic Commands

```bash
# Check status
fastband status

# List available tools
fastband tools list

# Manage tickets
fastband tickets list
fastband tickets create "Add user authentication"
fastband tickets claim 1 --agent "MCP_Agent1"

# Backup management
fastband backup list
fastband backup create --name "before_refactor"

# Agent coordination
fastband agents status
fastband ops read --since 1h
```

---

## Configuration

Fastband stores configuration in `.fastband/config.yaml`:

```yaml
fastband:
  version: "1.2025.12"

  ai:
    default_provider: "claude"
    providers:
      claude:
        model: "claude-sonnet-4-20250514"
      openai:
        model: "gpt-4-turbo"

  tools:
    max_active: 60
    auto_load_core: true

  tickets:
    enabled: true
    mode: "cli_web"
    web_port: 5050

  backup:
    enabled: true
    daily_retention: 7
    weekly_retention: 4
```

---

## Documentation

- [Getting Started](docs/getting-started/quickstart.md)
- [AI Providers Guide](docs/guides/ai-providers.md)
- [Tool Garage](docs/guides/tool-garage.md)
- [Ticket Manager](docs/guides/ticket-manager.md)
- [Multi-Agent Coordination](docs/guides/coordination.md)
- [API Reference](docs/api/)

---

## Roadmap

### v1.2025.12.0 (Current - Alpha)
- [ ] Core MCP server
- [ ] AI provider abstraction
- [ ] Tool garage system
- [ ] Setup wizard
- [ ] Basic ticket manager

### v1.2026.01.0 (Beta)
- [ ] Full ticket manager with web UI
- [ ] GitHub integration
- [ ] Backup manager
- [ ] Agent ops log

### v1.2026.02.0 (Stable)
- [ ] All features complete
- [ ] Documentation
- [ ] Example projects

---

## Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### Development Setup

```bash
git clone https://github.com/RemmyCH3CK/fastband-mcp
cd fastband-mcp
pip install -e ".[dev]"
pre-commit install
pytest
```

---

## License

MIT License - see [LICENSE](LICENSE) for details.

---

## Acknowledgments

Fastband MCP evolved from the MLB v4.0.1 development platform, incorporating lessons learned from building production AI-assisted development workflows.

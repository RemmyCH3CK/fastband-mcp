# Fastband MCP - Claude Code Context

## Project Overview

Fastband MCP is a universal MCP (Model Context Protocol) server that enables AI agents to work with any codebase. It provides:

- **AI Provider Abstraction**: Switch between Claude, OpenAI, Gemini, Ollama
- **Tool Garage**: 40+ development tools with AI-powered recommendations
- **Ticket Manager**: Full ticketing system for agent workflows
- **Setup Wizard**: Interactive project configuration

## Current Status

**Version**: v1.2025.12.0-alpha (targeting stable release)

### Completed Phases

| Phase | Status | Description |
|-------|--------|-------------|
| Phase 0 | ✅ Done | Foundation - Product vision, architecture docs |
| Phase 1 | ✅ Done | Core Engine - MCP server, config, events |
| Phase 2 | ✅ Done | AI Providers - Claude, OpenAI, Gemini, Ollama |
| Phase 3 | ✅ Done | Tool Garage - Core tools, recommender |
| Phase 4 | ✅ Done | Setup Wizard - Interactive configuration |
| Phase 5 | ✅ Done | Ticket Manager - Full ticketing system |

### Next Phase: Phase 6 - Polish & Launch

Open issues #35-42 cover:
- Complete documentation (#35)
- Set up CI/CD pipeline (#36)
- Achieve test coverage goals (#37)
- Performance optimization (#38)
- Security review (#39)
- Create example projects (#40)
- PyPI package release (#41)
- CHANGELOG and versioning (#42)

## Project Structure

```
fastband-mcp/
├── src/fastband/
│   ├── core/           # MCP engine, config, events, logging
│   ├── providers/      # AI providers (Claude, OpenAI, Gemini, Ollama)
│   ├── tools/          # Tool garage with categories
│   │   ├── core/       # File, search, system tools
│   │   ├── git/        # Git operations
│   │   ├── web/        # Web development tools
│   │   └── tickets/    # MCP ticket tools
│   ├── tickets/        # Ticket manager system
│   │   ├── models.py   # Pydantic ticket models
│   │   ├── storage.py  # SQLite/JSON storage
│   │   ├── review.py   # Code review workflow
│   │   └── web/        # Flask web dashboard
│   ├── agents/         # Multi-agent coordination
│   │   ├── coordination.py  # Agent sessions
│   │   └── ops_log.py       # Operations log
│   ├── wizard/         # Setup wizard steps
│   └── cli/            # Typer CLI commands
├── tests/              # Pytest test suite
├── docs/               # Documentation
└── pyproject.toml      # Python packaging
```

## Key Commands

```bash
# Run tests
pytest tests/ -v

# Run specific phase tests
pytest tests/test_tickets*.py tests/test_agents*.py -v

# Run CLI
python -m fastband --help

# Start MCP server
fastband serve

# Setup wizard
fastband init
```

## GitHub Issues

- Phase 5 issues (#28-34): **CLOSED** - All ticket manager features complete
- Phase 6 issues (#35-42): **OPEN** - Polish and launch tasks

## Development Notes

- Python 3.14 compatible
- Uses Pydantic for data validation
- Flask for web dashboard
- Typer for CLI
- pytest with asyncio support

## Last Updated

2024-12-28 - Phase 5 complete, all 383 tests passing

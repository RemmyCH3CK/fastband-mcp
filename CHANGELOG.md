# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to a hybrid versioning scheme: `vMAJOR.YYYY.MM.PATCH[-prerelease]`.

## [Unreleased]

### Added
- CHANGELOG.md following Keep a Changelog format
- VERSION file for CI/CD integration
- Version tuple in `__init__.py`

## [1.2025.12.0-alpha.1] - 2025-12-28

### Phase 5: Ticket Manager & Agent Coordination

#### Added
- Complete Ticket Manager system with full lifecycle management
- Agent coordination tools for multi-agent workflows
- Operations log for agent activity tracking
- Code review automation with approval workflow
- Memory system for cross-session learning
- Screenshot capture and validation tools
- Browser automation with Playwright integration
- Behavioral testing tools for UI verification
- CLAUDE.md project context documentation

### Phase 4: Setup Wizard

#### Added
- Interactive Setup Wizard framework (`fastband wizard start`)
- Project type detection (Python, JavaScript, web, mobile, desktop)
- GitHub automation options (issues, PRs, projects)
- Tool selection based on detected project type
- Configuration persistence with YAML
- Rich terminal UI with interactive prompts

### Phase 3: Tool Garage & Recommendations

#### Added
- AI-powered tool recommendation engine
- Project detection system for automatic configuration
- Tool categorization (core, web, git, deployment, etc.)
- Lazy loading for optional tool dependencies
- Tool performance monitoring hooks
- Git tools for repository management
- Web tools for HTTP operations
- CLI tools for system interaction

### Phase 2: AI Provider Layer

#### Added
- Abstract `AIProvider` base class with unified interface
- `ProviderRegistry` for managing multiple providers
- Claude provider with Anthropic API integration
- OpenAI provider with GPT-4 support
- Gemini provider with Google AI integration
- Ollama provider for local AI models
- Lazy loading to avoid importing unused provider SDKs
- Provider capability detection and validation
- Environment-based provider configuration

### Phase 1: Core Engine

#### Added
- MCP Server Engine with tool registration
- Configuration system with YAML support
- Event system for component communication
- Structured logging with Rich formatting
- CLI foundation with Typer (`fastband` / `fb` commands)
- `fastband server` command to start MCP server
- `fastband config` commands for configuration management
- `fastband tools` commands for tool discovery
- `fastband providers` commands for AI provider management

### Phase 0: Foundation

#### Added
- Initial project structure following modern Python packaging
- `pyproject.toml` with Hatchling build system
- GitHub repository setup with CI/CD workflows
- Auto-update workflows for issues and project boards
- Development environment configuration
- MIT License
- README.md with project overview

### Infrastructure

#### Added
- GitHub Actions CI workflow for testing
- GitHub Actions release workflow for PyPI publishing
- Dependabot configuration for dependency updates
- Pre-commit hooks configuration
- Ruff linting configuration
- Mypy type checking configuration
- Pytest configuration with coverage reporting

## Version Lifecycle

```
Alpha   -> Internal testing, API may change
Beta    -> Community testing, API stabilizing
RC      -> Release candidate, API frozen
Stable  -> Production ready
```

## Versioning Scheme

This project uses a hybrid versioning format: `vMAJOR.YYYY.MM.PATCH[-prerelease]`

| Component   | Description                           | Example      |
|-------------|---------------------------------------|--------------|
| MAJOR       | Breaking API changes                  | 1, 2, 3      |
| YYYY.MM     | Year and month of release             | 2025.12      |
| PATCH       | Bug fixes and minor improvements      | 0, 1, 2      |
| prerelease  | Development stage (optional)          | alpha.1, beta.1, rc.1 |

[Unreleased]: https://github.com/RemmyCH3CK/fastband-mcp/compare/v1.2025.12.0-alpha.1...HEAD
[1.2025.12.0-alpha.1]: https://github.com/RemmyCH3CK/fastband-mcp/releases/tag/v1.2025.12.0-alpha.1

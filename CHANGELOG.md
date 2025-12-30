# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to a hybrid versioning scheme: `vMAJOR.YYYY.MM.PATCH[-prerelease]`.

## [Unreleased]

## [1.2025.12.5] - 2025-12-30

### Fixed
- **Build artifacts** - Remove redundant force-include causing duplicate files in wheel
- **PyPI publishing** - Fixed "Duplicate filename in local headers" error

## [1.2025.12.4] - 2025-12-30

### Fixed
- **Build artifacts** - Exclude macOS extended attribute files (`._*`) from wheel
- **PyPI publishing** - Fixed duplicate filename error in ZIP archive

## [1.2025.12.3] - 2025-12-30

### Fixed
- **PyPI publishing** - Added API token fallback for releases
- **Release workflow** - Added manual dispatch trigger

## [1.2025.12.2] - 2025-12-30

### Added
- **Vision Analysis Tool** - `analyze_screenshot_with_vision` for Claude Vision API integration
  - 5 analysis modes: general, ui_review, bug_detection, accessibility, verification
  - Capture from URL or analyze existing base64 images
  - 19 comprehensive tests

### Fixed
- **TypeScript strict mode** - Fixed unused variable error in DirectivePanel.tsx
- **CLI help tests** - Added ANSI code stripping for reliable test assertions
- **Codecov CI warning** - Updated deprecated `file` parameter to `files`

### Changed
- **Code quality** - Auto-fixed 1871 lint issues with ruff
- **Formatting** - Standardized 97 files with ruff format
- **Dependencies** - Added numpy and flask to dev dependencies

### Dependencies
- Bumped GitHub Actions: checkout v6, setup-python v6, setup-node v6, upload-artifact v6, download-artifact v7, codecov-action v5

## [1.2025.12.1] - 2025-12-30

### Control Plane Dashboard (New!)

#### Added
- **Control Plane UI** - Real-time multi-agent coordination dashboard
  - Agent status grid with health indicators
  - Operations log timeline with filtering
  - Directives panel for hold/clearance management
  - Tickets panel with status tracking
  - Hold and clearance modals for agent coordination
- **Terminal Noir Design System** - Cyberpunk-inspired aesthetic
  - Cyan (#00d4ff) and magenta (#ff006e) accent colors
  - Void backgrounds with scan-line effects
  - Custom animations and micro-interactions
- **WebSocket Manager** - Real-time updates for dashboard
  - Connection pooling and automatic reconnection
  - Event-based message broadcasting
  - Client subscription management
- **Keyboard Shortcuts** - Press `?` to view all shortcuts
- **Toast Notifications** - Non-blocking status messages
- **CLI `--hub` flag** - Serve dashboard with `fastband serve --hub`

#### Infrastructure
- Zustand stores for control plane state management
- Vitest test suite with React Testing Library
- TypeScript types for control plane domain
- Dashboard build script (`build.py`)

### Plugin System (New!)

#### Added
- **Plugin Manager** - Discover and load plugins via entry points
  - `fastband.plugins` entry point group
  - Async lifecycle hooks (on_load, on_unload)
  - Plugin capability flags (tools, routes, CLI)
- **Event Bus** - Pub/sub for extensibility
  - Async and sync event handlers
  - Wildcard subscriptions
  - Priority-based handler ordering
  - Thread-safe subscription management
- **CLI Commands** - `fastband plugins list|load|unload|info`

### Security

#### Fixed
- **Path traversal vulnerability** in static file serving - Added `resolve()` + `relative_to()` validation
- **Closure variable capture bug** - Static file routes now correctly serve individual files
- **Race conditions** in EventBus and PluginManager singletons - Added double-checked locking
- **Thread-safety** in event subscriptions - Added synchronization locks
- **Default host binding** - Changed from `0.0.0.0` to `127.0.0.1` with security warning

#### Changed
- `datetime.utcnow()` → `datetime.now(timezone.utc)` for Python 3.12+ compatibility
- `asyncio.Lock` → `threading.Lock` for synchronous operations
- Private attribute access → Public API methods in PluginManager

## [1.2025.12.0] - 2025-12-29

### 🚀 First Stable Release

Fastband MCP v1.0 - A universal MCP server for AI-powered development.

### AI Hub (New!)

#### Added
- **Session Management** - LRU pooling, idle cleanup, rate limiting
- **Semantic Memory** - SQLite-backed RAG with vector search
- **Embeddings System** - OpenAI, Gemini, Ollama providers
- **Text Chunkers** - Fixed-size and semantic chunking strategies
- **Billing Integration** - Stripe subscriptions and usage tracking
- **Chat Orchestration** - Multi-turn conversations with tool execution
- **Web Frontend** - React/TypeScript dashboard (src/fastband/hub/web)
- **Infrastructure** - Terraform modules for AWS deployment
- 63 comprehensive Hub tests

#### Fixed
- Thread-local SQLite connection leaks in MemoryStore
- datetime.utcnow() deprecation warnings (Python 3.12+)

### Phase 6: Polish & Launch

#### Added
- Complete API documentation and guides
- GitHub Actions CI/CD pipeline
- 1400+ tests with 84% coverage
- Performance benchmarks and optimization
- Security review with path validation
- Example projects (CLI, web app, MCP demos)
- PyPI package configuration
- CHANGELOG.md and VERSION file

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

[Unreleased]: https://github.com/RemmyCH3CK/fastband-mcp/compare/v1.2025.12.1...HEAD
[1.2025.12.1]: https://github.com/RemmyCH3CK/fastband-mcp/compare/v1.2025.12.0...v1.2025.12.1
[1.2025.12.0]: https://github.com/RemmyCH3CK/fastband-mcp/releases/tag/v1.2025.12.0
[1.2025.12.0-alpha.1]: https://github.com/RemmyCH3CK/fastband-mcp/releases/tag/v1.2025.12.0-alpha.1

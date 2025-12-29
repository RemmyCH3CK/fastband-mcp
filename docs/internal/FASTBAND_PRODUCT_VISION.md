# Fastband MCP - Universal AI Development Platform

## Product Vision Document
**Version**: v1.2025.12 (Draft)
**Created**: 2025-12-16
**Status**: Planning Phase

---

## Executive Summary

Fastband MCP transforms from a project-specific tool (MLB v4.0.1) into a **universal, AI-agnostic development platform** that adapts to any project type (web, mobile, desktop) and scales from solo developers to enterprise teams.

### Core Philosophy
> **"A toolbox that travels with you - always the right tools, never too many, ready to grow."**

---

## Key Decisions (From Stakeholder Input)

| Decision Area | Choice |
|--------------|--------|
| Target Audience | All scales: Solo devs → Small teams → Enterprise |
| AI Compatibility | AI-agnostic from start (Claude, OpenAI, Gemini, local LLMs) |
| Tool Optimization | AI-recommended with no hard limit (performance warnings) |
| Release Scope | Full feature set |
| Repository | New dedicated GitHub repo |
| Ticket System | Project-type adaptive (web=CLI+webapp, desktop=embedded) |
| Versioning | Hybrid (v1.2025.12 format) |
| GitHub Setup | User-selectable (full auto, guided, hybrid, optional) |
| Data Storage | Configurable backends (SQLite, PostgreSQL, MySQL) |

---

## Product Architecture

### 1. Core System (fastband-core)

```
fastband-mcp/
├── core/                     # AI-agnostic core engine
│   ├── engine.py             # MCP server core
│   ├── tool_registry.py      # Tool management
│   ├── project_detector.py   # Project type detection
│   └── ai_adapter.py         # AI provider abstraction
├── providers/                # AI Provider Plugins
│   ├── claude/               # Claude/Anthropic
│   ├── openai/               # OpenAI/GPT
│   ├── gemini/               # Google Gemini
│   ├── ollama/               # Local LLMs
│   └── base.py               # Provider interface
├── tools/                    # Tool Garage
│   ├── core/                 # Essential tools (always loaded)
│   ├── web/                  # Web development tools
│   ├── mobile/               # Mobile dev tools
│   ├── desktop/              # Desktop app tools
│   ├── devops/               # CI/CD, deployment
│   └── analysis/             # Code analysis, security
├── ticket_manager/           # Adaptive Ticket System
│   ├── core/                 # Core ticket logic
│   ├── web_ui/               # Web dashboard
│   ├── cli/                  # Command-line interface
│   ├── embedded/             # Desktop embedded UI
│   └── integrations/         # GitHub, Jira, Linear sync
├── wizard/                   # Setup Wizard
│   ├── project_setup.py      # Project initialization
│   ├── github_config.py      # GitHub automation
│   ├── tool_selector.py      # Tool recommendation engine
│   └── templates/            # Project templates
├── storage/                  # Data Backend Adapters
│   ├── sqlite.py
│   ├── postgres.py
│   ├── mysql.py
│   └── file_based.py         # JSON/YAML option
└── config/                   # Configuration
    ├── defaults.yaml
    └── schemas/              # Validation schemas
```

### 2. AI Provider Abstraction Layer

```python
# providers/base.py
class AIProvider(ABC):
    """Base class for AI provider implementations."""

    @abstractmethod
    def complete(self, prompt: str, **kwargs) -> str:
        """Send completion request to AI."""
        pass

    @abstractmethod
    def analyze(self, content: str, task: str) -> dict:
        """Analyze content with AI."""
        pass

    @abstractmethod
    def recommend_tools(self, project_context: dict) -> list[str]:
        """Get tool recommendations for project."""
        pass

    @abstractmethod
    def get_capabilities(self) -> dict:
        """Return provider capabilities (vision, code, etc.)."""
        pass

# Usage:
provider = get_provider("claude")  # or "openai", "gemini", "ollama"
result = provider.complete("Analyze this code...")
```

### 3. Tool Garage System

#### Tool Categories

| Category | Examples | When Loaded |
|----------|----------|-------------|
| **Core** (Always) | health_check, list_files, read_file, write_file | Always |
| **Project Analysis** | code_quality, security_scan, dependencies | On demand |
| **Web Development** | take_screenshot, browser_console, API_testing | Web projects |
| **Mobile Development** | device_preview, build_mobile, app_store_prep | Mobile projects |
| **Desktop Development** | package_app, cross_platform_build, installer_gen | Desktop projects |
| **DevOps** | docker_build, ci_cd_setup, deploy_to_cloud | When CI/CD enabled |
| **Ticket Management** | create_ticket, claim_ticket, complete_ticket | When tickets enabled |
| **Version Control** | git_commit, create_pr, branch_management | When git enabled |
| **AI Analysis** | code_review, suggest_fix, memory_query | Optional |

#### Tool Recommendation Engine

```python
class ToolRecommender:
    """AI-powered tool recommendation system."""

    def analyze_project(self, project_path: str) -> ProjectContext:
        """Detect project type, tech stack, size."""
        pass

    def get_initial_toolset(self, context: ProjectContext) -> list[Tool]:
        """Return recommended initial tools."""
        pass

    def suggest_additions(self, usage_patterns: UsageStats) -> list[Tool]:
        """Suggest new tools based on usage patterns."""
        pass

    def warn_if_overloaded(self, active_tools: list[Tool]) -> Optional[str]:
        """Warn if too many tools may impact performance."""
        pass
```

#### Performance Guidelines

| Tool Count | Status | Recommendation |
|------------|--------|----------------|
| 1-20 | Optimal | Standard operation |
| 21-40 | Moderate | Consider tool rotation |
| 41-60 | Heavy | Warning shown, suggest audit |
| 60+ | Overloaded | Performance impact likely |

---

## Setup Wizard Flow

### Phase 1: Project Detection

```
┌─────────────────────────────────────────────────────────┐
│  Welcome to Fastband MCP Setup Wizard                   │
│                                                         │
│  Detected Project: /path/to/your/project                │
│                                                         │
│  Project Analysis:                                      │
│  ├── Type: Web Application (React + Flask)              │
│  ├── Size: Medium (45 files, 12k LOC)                   │
│  ├── Tech Stack: Python, JavaScript, Docker             │
│  └── Git: Initialized (remote: github.com/user/repo)   │
│                                                         │
│  Is this correct? [Y/n]                                 │
└─────────────────────────────────────────────────────────┘
```

### Phase 2: AI Provider Selection

```
┌─────────────────────────────────────────────────────────┐
│  Select AI Provider                                     │
│                                                         │
│  [1] Claude (Anthropic) - Recommended for code          │
│  [2] OpenAI (GPT-4)     - General purpose               │
│  [3] Google Gemini      - Good for large context        │
│  [4] Ollama (Local)     - Privacy-focused, offline      │
│  [5] Multiple providers - Use best provider per task    │
│                                                         │
│  Selection: _                                           │
└─────────────────────────────────────────────────────────┘
```

### Phase 3: GitHub Configuration

```
┌─────────────────────────────────────────────────────────┐
│  GitHub Integration                                     │
│                                                         │
│  How would you like to configure GitHub?                │
│                                                         │
│  [1] Full Automation (Recommended)                      │
│      → Create repo, branches, CI/CD, webhooks           │
│                                                         │
│  [2] Guided Setup                                       │
│      → Step-by-step instructions you run                │
│                                                         │
│  [3] Hybrid                                             │
│      → Auto repo/branches, manual CI/CD templates       │
│                                                         │
│  [4] Skip for Now                                       │
│      → Add GitHub integration later                     │
│                                                         │
│  Selection: _                                           │
└─────────────────────────────────────────────────────────┘
```

### Phase 4: Tool Selection

```
┌─────────────────────────────────────────────────────────┐
│  Tool Garage - Recommended Tools                        │
│                                                         │
│  Based on your Web Application project, we recommend:   │
│                                                         │
│  CORE (Always included):                                │
│  ✓ health_check, list_files, read_file, write_file     │
│  ✓ git_status, git_commit, create_pr                    │
│                                                         │
│  RECOMMENDED (15 tools):                                │
│  ✓ take_screenshot       - Browser screenshots          │
│  ✓ build_container       - Docker builds                │
│  ✓ run_tests             - Test execution               │
│  ✓ code_quality          - Linting/analysis             │
│  ✓ security_scan         - Vulnerability check          │
│  ... [see all 15]                                       │
│                                                         │
│  AVAILABLE (25 more in garage):                         │
│  ○ mobile_preview        - Mobile device preview        │
│  ○ performance_profiler  - CPU/memory analysis          │
│  ... [browse garage]                                    │
│                                                         │
│  [A]ccept recommended  [C]ustomize  [B]rowse garage     │
└─────────────────────────────────────────────────────────┘
```

### Phase 5: Ticket Manager Setup

```
┌─────────────────────────────────────────────────────────┐
│  Ticket Manager Configuration                           │
│                                                         │
│  Project Type: Web Application                          │
│                                                         │
│  Recommended: CLI + Web Dashboard                       │
│                                                         │
│  [1] CLI + Web Dashboard (Recommended for Web Apps)     │
│      → Command-line tools + browser-based dashboard     │
│      → Accessible at http://localhost:5050/tickets      │
│                                                         │
│  [2] CLI Only                                           │
│      → Lightweight, terminal-based management           │
│      → Ideal for CI/CD integration                      │
│                                                         │
│  [3] External Integration                               │
│      → Sync with GitHub Issues, Jira, or Linear         │
│      → Two-way sync keeps everything in sync            │
│                                                         │
│  Selection: _                                           │
└─────────────────────────────────────────────────────────┘
```

### Phase 6: Data Storage

```
┌─────────────────────────────────────────────────────────┐
│  Data Storage Configuration                             │
│                                                         │
│  Where should Fastband store project data?              │
│                                                         │
│  [1] SQLite (Recommended)                               │
│      → Self-contained, no setup required                │
│      → Perfect for solo/small teams                     │
│                                                         │
│  [2] PostgreSQL                                         │
│      → Robust, great for teams                          │
│      → Requires PostgreSQL server                       │
│                                                         │
│  [3] MySQL                                              │
│      → Enterprise standard                              │
│      → Requires MySQL server                            │
│                                                         │
│  [4] File-based (JSON/YAML)                             │
│      → Human-readable, version-controllable             │
│      → Best for simple projects                         │
│                                                         │
│  Selection: _                                           │
└─────────────────────────────────────────────────────────┘
```

---

## Adaptive Ticket Manager

### Web Application Mode
- CLI commands for quick operations
- Web dashboard at configurable port
- Real-time updates via WebSocket
- Review agent integration
- Screenshot capture and embedding

### Desktop Application Mode
- Embedded ticket panel (hideable)
- System tray integration
- Hotkey access (e.g., Ctrl+Shift+T)
- Persists through product lifecycle
- User-facing for post-launch development

### Mobile Application Mode
- CLI primary interface
- Optional companion web dashboard
- Build artifact tracking
- App store submission tracking

---

## Versioning Strategy

### Hybrid Versioning: vMAJOR.YYYY.MM.PATCH

```
v1.2025.12.0  → Version 1, December 2025, initial release
v1.2025.12.1  → Version 1, December 2025, patch 1
v2.2026.03.0  → Version 2 (breaking changes), March 2026
```

### Version Bumping Rules

| Change Type | Example | Version Impact |
|------------|---------|----------------|
| Breaking API change | Tool signature change | Major bump (v1 → v2) |
| New feature | New tool category | Month updates automatically |
| Bug fix | Tool fix | Patch bump |
| Documentation | README update | No version change |

### Backup Strategy

```
project/
├── .fastband/
│   ├── config.yaml           # Current configuration
│   ├── backups/
│   │   ├── 2025-12-16_001/   # Daily automatic backup
│   │   ├── 2025-12-15_001/
│   │   └── manual_backup_001/ # Manual backups
│   ├── versions/
│   │   ├── v1.2025.12.0/     # Version snapshots
│   │   └── v1.2025.12.1/
│   └── git_snapshots/        # Pre-commit state snapshots
```

---

## GitHub Repository Structure

### New Repository: `fastband-mcp`

```
fastband-mcp/
├── .github/
│   ├── workflows/
│   │   ├── ci.yml            # Continuous integration
│   │   ├── release.yml       # Automated releases
│   │   └── docs.yml          # Documentation builds
│   ├── ISSUE_TEMPLATE/
│   └── pull_request_template.md
├── src/
│   └── fastband/             # Main package
├── providers/                # AI provider plugins
├── tools/                    # Tool garage
├── ticket_manager/           # Ticket system
├── wizard/                   # Setup wizard
├── templates/                # Project templates
├── docs/                     # Documentation
├── tests/                    # Test suite
├── examples/                 # Example projects
├── pyproject.toml            # Modern Python packaging
├── LICENSE                   # MIT or Apache 2.0
└── README.md                 # Project overview
```

---

## Implementation Phases

### Phase 1: Foundation (Weeks 1-2)
- [ ] Create new GitHub repository
- [ ] Set up project structure
- [ ] Implement core MCP server (AI-agnostic)
- [ ] Create AI provider abstraction layer
- [ ] Port core tools from current implementation

### Phase 2: AI Providers (Weeks 3-4)
- [ ] Implement Claude provider
- [ ] Implement OpenAI provider
- [ ] Implement Gemini provider
- [ ] Implement Ollama (local) provider
- [ ] Create provider switching mechanism

### Phase 3: Tool Garage (Weeks 5-6)
- [ ] Implement tool registry
- [ ] Create tool recommendation engine
- [ ] Port all existing tools
- [ ] Add tool loading/unloading
- [ ] Performance monitoring

### Phase 4: Setup Wizard (Weeks 7-8)
- [ ] Project type detection
- [ ] Interactive CLI wizard
- [ ] GitHub configuration automation
- [ ] Tool selection interface
- [ ] Configuration persistence

### Phase 5: Ticket Manager (Weeks 9-10)
- [ ] Port ticket_manager.py
- [ ] Create web dashboard
- [ ] Create embedded desktop UI
- [ ] External integrations (GitHub, Jira)
- [ ] Review agent system

### Phase 6: Polish & Launch (Weeks 11-12)
- [ ] Documentation
- [ ] Example projects
- [ ] Testing suite
- [ ] CI/CD pipeline
- [ ] Public release

---

## Success Metrics

| Metric | Target |
|--------|--------|
| Setup time | < 5 minutes for new project |
| Tool recommendation accuracy | > 80% user acceptance |
| AI provider switch time | < 30 seconds |
| Ticket system setup | < 2 minutes |
| Documentation coverage | 100% of public APIs |

---

## Open Questions

1. **Licensing**: MIT (permissive) or Apache 2.0 (patent protection)?
2. **Monetization**: Open source with enterprise tier? Pure open source?
3. **Plugin marketplace**: Allow third-party tool contributions?
4. **Cloud offering**: Future SaaS version with hosted features?

---

## Next Steps

1. Review and approve this vision document
2. Create GitHub repository
3. Begin Phase 1 implementation
4. Set up CI/CD pipeline
5. Create initial documentation

---

*Document created by Fastband MCP planning session - 2025-12-16*

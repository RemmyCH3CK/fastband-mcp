# Fastband Agent Control - Handoff Document

**Version:** 1.2026.01.01
**Last Updated:** 2026-01-01 (Session 14)
**Branch:** main
**CI Status:** Passing
**PyPI:** v1.2026.01.01 (Released 2026-01-01)

## Current State

Fastband Agent Control is a universal platform for AI agent coordination. The project is in a **stable release state** with v1.2026.01.01 published to PyPI.

### Installation

```bash
pip install fastband-agent-control==1.2026.01.01
```

**Note:** As of v1.2025.12.7, all Hub dependencies are included by default. No need for `[hub]` extras.

### What's Working

- **MCP Server** - Full tool registration and execution
- **AI Providers** - Claude, OpenAI, Gemini, Ollama support
- **Tool Garage** - 50+ tools across categories (git, web, testing, etc.)
- **Ticket Manager** - Agent coordination with lifecycle management
- **Control Plane Dashboard** - Real-time multi-agent UI at `/control-plane`
- **AI Hub** - Session management, semantic memory, embeddings
- **Plugin System** - Entry point discovery with async lifecycle
- **CLI** - `fastband serve --hub` to run server with dashboard
- **CI/CD** - GitHub Actions for testing and PyPI releases (all passing)
- **Tests** - 1838+ tests passing across Python 3.10, 3.11, 3.12
- **Vision Screenshot Analysis** - Claude Vision API integration for UI verification
- **PyPI Publishing** - Automated releases via GitHub Actions
- **AI Provider Settings** - Dashboard UI for configuring API keys
- **Platform Analyzer** - Codebase analysis with unified `/api/analyze` endpoint
- **Auto-Port Selection** - Hub automatically finds available port if 8080 is busy
- **Tickets Page** - Full ticket management UI in dashboard
- **Backups Page** - Backup management UI in dashboard
- **One-Command Setup** - `fastband setup` auto-configures Claude Code MCP
- **Admin Onboarding** - 6-step wizard for first-time Hub setup
- **CLI Authentication** - `fastband auth register/login/logout` with OAuth
- **Bible Editor** - View/edit AGENT_BIBLE.md from Hub at `/bible`
- **Performance Meter** - System-aware tool recommendations
- **CLI Wizard Auth** - Browser OAuth integration in setup wizard
- **Operation Mode** - Manual vs YOLO agent automation levels
- **Supabase Sync** - Cloud profile sync for onboarding data
- **CLI Chat** - Fully working natural language chat with tool execution
- **Backup Settings** - Configurable backup path with native folder picker
- **Chat Persistence** - CLI chat persists across page navigation

### Architecture Overview

```
src/fastband/
├── embeddings/      # RAG system (chunkers, providers, storage)
├── hub/             # AI Hub (billing, aws, web dashboard)
│   ├── api/         # FastAPI routes (sessions, chat, providers, analyze)
│   ├── control_plane/ # Control Plane service + WebSocket
│   ├── web/         # React/TypeScript dashboard (Vite + Tailwind)
│   └── static/      # Built dashboard assets (auto-generated)
├── providers/       # AI provider integrations (Claude, OpenAI, Gemini, Ollama)
├── tools/           # Tool categories
│   ├── agents/      # Agent coordination tools
│   ├── core/        # Core MCP tools
│   ├── git/         # Git operations
│   ├── tickets/     # Ticket management
│   ├── testing/     # Test automation
│   ├── web/         # Web tools (screenshot, vision, DOM query)
│   └── ...          # mobile, desktop, devops, analysis
├── backup/          # Backup manager and scheduler
├── utils/           # Shared utilities
└── wizard/          # Setup wizard system
```

## Recent Session Work

### Session 14 - Version Bump & PyPI Release (2026-01-01)

1. **Version Bump to v1.2026.01.01**
   - Updated `pyproject.toml` and `src/fastband/__init__.py`
   - Happy New Year release!

2. **Published to PyPI**
   - All CI checks passed (Python 3.10, 3.11, 3.12)
   - Package published via GitHub Actions release workflow
   - Available at: https://pypi.org/project/fastband-agent-control/1.2026.01.01/

### Session 13 - CLI Chat Complete Overhaul (2026-01-01)

Major fixes to make the Hub CLI Chat fully functional with Claude API:

1. **Backup Settings Tab** (NEW FEATURE)
   - Added Backup tab to Settings page with path configuration
   - Native macOS Finder folder picker via osascript
   - Backup path, retention days, interval, max count settings
   - BackupManager now uses configured path instead of hardcoded `.fastband/backups`

2. **API Key Persistence** (CRITICAL FIX)
   - `/providers/configure` now saves keys to `.fastband/.env`
   - Multi-location .env search (cwd, project root, home directory)
   - Keys persist across server restarts

3. **Claude API Message Format** (CRITICAL FIX)
   - System role extracted and passed via `system` parameter (Claude doesn't accept role="system")
   - Tool results flushed BEFORE next assistant message (Claude requires tool_use → tool_result pairing)
   - OpenAI format `{function: {name, arguments}}` converted to Claude format
   - Added `tool_calls` property to `CompletionResponse`

4. **Tool Execution Fix** (CRITICAL FIX)
   - Changed `registry.get()` to `registry.get_available()` in ToolExecutor
   - Tools were registered but not "active" - get_available() finds all registered tools
   - All 20 tools now execute correctly (git, onboarding, tickets, codebase, etc.)

5. **Duplicate User Message** (BUG FIX)
   - User message was added to conversation twice (before and during _build_messages)
   - Fixed: Now only added after processing completes

6. **Chat Persistence** (NEW FEATURE)
   - CLI chat messages persist to localStorage
   - Session ID persists across page navigation
   - Conversation survives page refresh and navigation
   - Clear button properly resets localStorage

**Files Modified:**
- `src/fastband/hub/api/routes.py` - .env persistence, multi-path search, backup config endpoints
- `src/fastband/hub/chat.py` - get_available() fix, message deduplication
- `src/fastband/providers/claude.py` - Full OpenAI→Claude message format conversion
- `src/fastband/providers/base.py` - tool_calls property on CompletionResponse
- `src/fastband/backup/manager.py` - Use configured backup path
- `src/fastband/hub/web/src/pages/Settings.tsx` - Backup tab with folder browser
- `src/fastband/hub/web/src/components/control-plane/CLIChatPanel.tsx` - localStorage persistence

### Session 12 - Hub Bug Fixes (Post User Testing) (2025-12-31)

Based on user testing feedback, fixed multiple issues:

1. **Double Navigation Sidebar** (CRITICAL UI FIX)
   - Removed duplicate Layout wrappers in App.tsx for /backups and /tickets
   - Pages now properly use their own Layout components

2. **Wizard Overflow** (UI FIX)
   - Added max-h-[90vh] and flex-col to modal container
   - Content area now scrolls with overflow-y-auto
   - Steps no longer overflow browser window

3. **Password Fields** (DOM FIX)
   - Wrapped API key inputs in <form> elements in ApiKeysStep
   - Added autoComplete="off" attribute

4. **API Endpoint Fixes** (BACKEND)
   - Added /api/providers/validate POST endpoint
   - Fixed /api/analyze/generate-bible 422 error (Pydantic model)

5. **Usage Page** (UI FIX)
   - Fixed infinite loading when no sessionId
   - Now shows mock data immediately

6. **Full Project Backup** (FEATURE FIX)
   - Backups now include entire project folder
   - Added more exclude patterns (.git, node_modules, etc.)
   - .fastband/backups directory excluded from backups

### Session 11 - Pre-Release Bug Fixes

1. **Per-User Data Isolation** (CRITICAL FIX)
   - Fixed onboarding data leaking between users
   - Changed localStorage keys from global to per-user
   - Keys now use format `fastband_onboarding_{userId}`
   - Auth state listener updates on user change

2. **Ticket Manager Navigation** (BUG FIX)
   - Fixed "View in Ticket Manager" not working
   - Changed from `window.open()` to React Router `navigate()`
   - Modal now closes before navigation

3. **Control Plane Error Handling** (STABILITY)
   - Added comprehensive try/catch to polling task
   - Graceful fallbacks when ticket_store/ops_log unavailable
   - Properties handle initialization failures
   - Backoff on consecutive errors in polling

4. **Password Field DOM Warnings** (FIX)
   - Wrapped password inputs in `<form>` elements
   - Settings page API key inputs now properly contained
   - Fixes browser autocomplete warnings

5. **Backups.tsx JSX Fix** (BUILD FIX)
   - Fixed inconsistent indentation causing build failure
   - All cards now properly indented within Layout wrapper

## Pending Work / Known Issues

### Installation Test Results (Session 6)

**v1.2025.12.7+ Verified Working:**
- Clean pipx install (~7.4 seconds)
- All dependencies bundled (no manual injection needed)
- WebSocket connects successfully (101 Switching Protocols)
- Dashboard loads and connects
- API endpoints work correctly

**Minor Issues:**
- Python 3.14 logging cosmetic error (not a Fastband bug)
- Project path not configurable from dashboard UI

### Near-term Tasks

1. **Add Tests for Session 13 Changes**
   - `claude.py` message format conversion needs unit tests
   - `chat.py` get_available() change needs tests

2. **OpenAI Provider Compatibility**
   - Similar message format handling may be needed for OpenAI provider
   - Streaming endpoint (`/chat/stream`) may need similar fixes

3. **Test Coverage**
   - Currently at ~64%, target 80%+
   - Hub components need more integration tests

4. **Consider `fastband doctor` CLI command** for self-diagnosis

### Open Issues

- **TestPyPI Trusted Publishing** - Warning in release workflow (non-blocking)
- **macOS `._*` files** - Extended attributes creating dot-underscore files (cosmetic)
- **Python 3.14 logging** - Cosmetic stderr output when backgrounding (Python issue, not ours)

## Key API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/providers/status` | GET | Check AI provider configuration |
| `/api/providers/configure` | POST | Save and validate API keys |
| `/api/analyze` | POST | Platform Analyzer (local or GitHub) |
| `/api/sessions` | POST | Create new chat session |
| `/api/chat` | POST | Send chat message and get response |
| `/api/chat/stream` | POST | Stream chat responses (SSE) |
| `/api/control-plane/dashboard` | GET | Control Plane state |
| `/api/control-plane/ws` | WS | Real-time WebSocket updates |
| `/api/tickets` | GET/POST | List or create tickets |
| `/api/tickets/{id}` | GET/PUT/DELETE | Get, update, or delete ticket |
| `/api/tickets/{id}/claim` | POST | Claim ticket for agent |
| `/api/tickets/stats/summary` | GET | Ticket statistics |
| `/api/backups` | GET/POST | List or create backups |
| `/api/backups/{id}` | GET/DELETE | Get or delete backup |
| `/api/backups/{id}/restore` | POST | Restore a backup |
| `/api/backups/scheduler/status` | GET | Scheduler status |
| `/api/backups/scheduler/start` | POST | Start scheduler |
| `/api/backups/scheduler/stop` | POST | Stop scheduler |
| `/api/backups/config` | GET/POST | Get or save backup configuration |

## Development Setup

```bash
# Install from PyPI (all deps included)
pip install fastband-agent-control

# Or install for development
pip install -e ".[dev]"

# Run tests
pytest

# Start server with dashboard
fastband serve --hub
# Dashboard at http://localhost:8080

# Build dashboard (if modifying frontend)
cd src/fastband/hub/web && npm install && npm run build
cp -r dist ../static
```

## Key Files

| File | Purpose |
|------|---------|
| `pyproject.toml` | Package config (deps moved to core) |
| `src/fastband/hub/api/routes.py` | Hub API routes + provider endpoints |
| `src/fastband/hub/chat.py` | Chat pipeline with tool execution loop |
| `src/fastband/providers/claude.py` | Claude API integration with message format conversion |
| `src/fastband/providers/base.py` | Base provider with CompletionResponse |
| `src/fastband/hub/web/src/pages/Settings.tsx` | Settings UI with Backup tab |
| `src/fastband/hub/web/src/components/control-plane/CLIChatPanel.tsx` | CLI Chat UI |
| `src/fastband/hub/control_plane/routes.py` | Control Plane + WebSocket |
| `src/fastband/hub/server.py` | Hub server launcher |
| `src/fastband/cli/main.py` | CLI commands |
| `.github/workflows/release.yml` | PyPI release workflow |

## Release History

| Version | Date | Highlights |
|---------|------|------------|
| v1.2026.01.01 | 2026-01-01 | **Happy New Year**: CLI Chat fully functional, API key persistence, chat persistence, backup settings |
| v1.2025.12.28 | 2025-12-31 | Version bump for CLI Chat fixes |
| v1.2025.12.27 | 2025-12-31 | **Critical fix**: Per-user data isolation, ticket navigation, Control Plane stability |
| v1.2025.12.12 | 2025-12-31 | **Major fixes**: backup routes, scheduler routes, all API endpoints verified |
| v1.2025.12.11 | 2025-12-31 | Fix project_path AttributeError in ticket routes |
| v1.2025.12.10 | 2025-12-31 | Fix /api/tickets 500 error, system event handlers |
| v1.2025.12.9 | 2025-12-31 | Fix version string mismatch in CLI |
| v1.2025.12.8 | 2025-12-31 | **WebSocket CORS fix**, `fastband setup` command, Python 3.10 compatibility |
| v1.2025.12.7 | 2025-12-31 | **All-inclusive package**, AI Provider settings UI, Platform Analyzer fix |
| v1.2025.12.6 | 2025-12-30 | Rename to Fastband Agent Control |
| v1.2025.12.5 | 2025-12-30 | PyPI publishing fix |
| v1.2025.12.1 | 2025-12-30 | Control Plane Dashboard, Plugin System |

## Next Steps (Suggestions)

1. Add unit tests for `claude.py` message format conversion
2. Add unit tests for `chat.py` tool execution
3. Test OpenAI provider compatibility with chat feature
4. Fix streaming endpoint (`/chat/stream`) if needed
5. Add `fastband doctor` CLI command for self-diagnosis
6. Increase test coverage to 80%+
7. Add E2E tests for Control Plane dashboard
8. Add project path configuration to dashboard UI

## Contacts & Resources

- **Repository:** https://github.com/RemmyCH3CK/fastband-mcp
- **PyPI:** https://pypi.org/project/fastband-agent-control/
- **Docs:** `docs/` directory
- **Changelog:** `CHANGELOG.md`

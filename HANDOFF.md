# Fastband Agent Control - Handoff Document

**Version:** 1.2025.12.28
**Last Updated:** 2026-01-01 (Session 13)
**Branch:** main
**CI Status:** ✅ Passing
**PyPI:** ⏳ Pending (v1.2025.12.28)

## Current State

Fastband Agent Control is a universal platform for AI agent coordination. The project is in a **stable release state** with v1.2025.12.28 pending release. All CI checks are passing.

### Installation

```bash
pip install fastband-agent-control==1.2025.12.11
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
- **CLI Chat** - Fully working natural language chat with tool execution (NEW)
- **Backup Settings** - Configurable backup path with native folder picker (NEW)
- **Chat Persistence** - CLI chat persists across page navigation (NEW)

### Architecture Overview

```
src/fastband/
├── embeddings/      # RAG system (chunkers, providers, storage)
├── hub/             # AI Hub (billing, aws, web dashboard)
│   ├── api/         # FastAPI routes (sessions, chat, providers, analyze)
│   ├── control_plane/ # Control Plane service + WebSocket
│   ├── web/         # React/TypeScript dashboard (Vite + Tailwind)
│   └── static/      # Built dashboard assets (auto-generated)
├── tools/           # Tool categories
│   ├── agents/      # Agent coordination tools
│   ├── core/        # Core MCP tools
│   ├── git/         # Git operations
│   ├── tickets/     # Ticket management
│   ├── testing/     # Test automation
│   ├── web/         # Web tools (screenshot, vision, DOM query)
│   └── ...          # mobile, desktop, devops, analysis
├── utils/           # Shared utilities
└── wizard/          # Setup wizard system
```

## Recent Session Work

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

### Session 10 - CLI Wizard & Polish

1. **CLI Wizard AuthStep** (NEW)
   - OAuth authentication integration in CLI setup wizard
   - Supports existing credentials detection
   - Graceful fallback if Supabase not configured
   - Browser-based OAuth flow option

2. **CLI Wizard OperationModeStep** (NEW)
   - Manual vs YOLO mode selection in CLI wizard
   - Comparison table showing differences
   - YOLO mode warning with confirmation
   - Saves to FastbandConfig

3. **Configuration Updates**
   - Added `operation_mode` field to FastbandConfig
   - Persists to `.fastband/config.yaml`
   - Supports YAML serialization/deserialization

4. **Hub Navigation Improvements**
   - Agent Bible link added to sidebar navigation
   - Navigate to Control Plane after onboarding completion
   - Reset Onboarding button in Settings → Danger Zone

5. **Supabase Profile Sync** (NEW)
   - Onboarding data syncs to Supabase profiles table
   - Optional - works when Supabase configured
   - Stores operation_mode, onboarding_data JSONB

6. **Optional Dependencies**
   - Added `[cloud]` extra for Supabase client
   - Updated `[full]` to include cloud, auth, system
   - keyring, psutil, supabase all optional

### Session 9 - Comprehensive Onboarding System

1. **Hub Admin Onboarding Modal** (MAJOR FEATURE)
   - 6-step wizard for first-time admin setup
   - Terminal Noir aesthetic with cyan/magenta accents
   - Non-dismissible modal (must complete all steps)
   - Steps:
     1. EnvironmentStep - Project path + GitHub URL
     2. OperationModeStep - Manual vs YOLO mode
     3. FeaturesStep - Backup/Tickets toggles
     4. ApiKeysStep - AI provider key validation
     5. AnalyzeStep - Codebase analysis + Bible generation
     6. ToolsStep - MCP tool selection with performance meter

2. **System Capabilities Module**
   - `core/system_capabilities.py` - RAM/CPU/disk detection
   - AI provider context limits for tool recommendations
   - Hybrid calculation: system resources + AI provider limits
   - API endpoint: `/api/system/capabilities`

3. **CLI Authentication Commands**
   - `fastband auth register` - Browser-based OAuth with Google
   - `fastband auth login` - Login existing accounts
   - `fastband auth logout` - Clear credentials
   - `fastband auth whoami` - Show current user
   - `fastband auth status` - Check connectivity
   - Secure storage via system keyring (macOS Keychain)
   - Fallback to `~/.fastband/credentials.json`

4. **Bible Editor Page** (`/bible`)
   - View and edit AGENT_BIBLE.md from Hub UI
   - Structured rules editor with severity levels
   - Categories: security, code_style, testing, workflow, architecture
   - Add/delete rules with instant feedback
   - Regenerate Bible with AI button
   - Raw markdown editor toggle

5. **New API Endpoints**
   - `/api/onboarding/status` - Check onboarding completion
   - `/api/onboarding/complete` - Save onboarding config
   - `/api/bible` - GET/PUT Bible content
   - `/api/bible/rules` - Add structured rules
   - `/api/analyze/generate-bible` - AI Bible generation
   - `/api/analyze/tech-stack` - Detect project tech stack

### Session 8 - One-Command Setup + WebSocket Fix

1. **`fastband setup` Command** (MAJOR UX IMPROVEMENT)
   - Single command to configure Claude Code MCP integration
   - Auto-detects installation method (pipx, pip, uv, source)
   - Creates `.claude/mcp.json` with correct command/args
   - Initializes `.fastband/` config if not present
   - Validates MCP server starts correctly
   - Cross-platform support (macOS, Linux, Windows)
   - 48 comprehensive unit tests (security hardened)

2. **Installation Detection**
   - Detects pipx installations at `~/.local/bin/`
   - Detects pip/venv installations
   - Detects uv tool installations
   - Detects development/source installations
   - Generates correct command for each method

3. **Improved UX**
   - Step-by-step progress output
   - Clear success/failure indicators
   - Helpful next steps after setup
   - `--verbose` mode for debugging
   - `--show` option to view current config

4. **WebSocket CORS Fix** (BUG FIX)
   - Fixed WebSocket connection failures (error 1006)
   - CORS origins now include Hub ports (8080-8085)
   - Dashboard WebSocket connects reliably
   - Added 9 WebSocket integration tests
   - Fixed datetime.utcnow() deprecation warnings

### Session 7 - Multi-Project Support & Dashboard Features

1. **Auto-Port Selection** (MAJOR)
   - Hub automatically detects if port 8080 is busy
   - Scans ports 8081-8099 to find available port
   - Displays actual port in startup banner
   - Enables running multiple Hub instances for different projects
   - 13 unit tests added for port selection logic

2. **Tickets Page** (NEW FEATURE)
   - Full ticket management UI at `/tickets`
   - Create, edit, delete tickets from dashboard
   - Filter by status, priority, type
   - Claim tickets for agents
   - Status badges and priority indicators
   - Statistics overview (total, open, in progress, resolved)

3. **Backups Page** (NEW FEATURE)
   - Backup management UI at `/backups`
   - Create manual backups with descriptions
   - View backup history with size and file count
   - Restore and delete backups
   - Scheduler status and start/stop controls
   - Real-time status updates

4. **API Endpoints Added**
   - Backup endpoints: `GET/POST /api/backups`, `DELETE/POST /api/backups/{id}/restore`
   - Scheduler endpoints: `GET/POST /api/backups/scheduler/{status,start,stop}`
   - Ticket endpoints: `GET/POST/PUT/DELETE /api/tickets`, `POST /api/tickets/{id}/claim`
   - Stats endpoint: `GET /api/tickets/stats/summary`

5. **Dashboard Navigation**
   - Added Tickets and Backups to sidebar navigation
   - Version number now displayed in startup banner

6. **Installation Test Results**
   - v1.2025.12.7 verified working with pipx on macOS
   - WebSocket connectivity confirmed (was broken in v1.2025.12.6)
   - All dependencies bundle correctly
   - Clean install experience with no manual intervention

### Session 5 - Installation Streamlining & AI Provider UI

1. **All-Inclusive Package** (MAJOR)
   - Moved Hub dependencies to core: fastapi, uvicorn, websockets, aiofiles, numpy
   - Removed `[hub]` optional extra (no longer needed)
   - Single `pip install fastband-agent-control` now works for everything
   - No more `pipx inject` needed for missing deps

2. **AI Provider Settings UI** (NEW FEATURE)
   - Added Settings > AI Providers tab in dashboard
   - Password-masked input fields with show/hide toggle
   - Status badges: Connected / Invalid Key / Configured
   - Direct links to Anthropic and OpenAI console for getting keys
   - Environment variable alternative shown

3. **Backend API Endpoints** (NEW)
   - `GET /api/providers/status` - Check which providers are configured
   - `POST /api/providers/configure` - Save and validate API keys
   - Keys validated with minimal API call

4. **Platform Analyzer Fix**
   - Added unified `/api/analyze` endpoint
   - Fixed "Method Not Allowed" error for local/GitHub analysis
   - Updated frontend to use new endpoint

5. **Test Coverage Improvements**
   - Added 102 tests for tools modules
   - Improved coverage: index_codebase (11%→95%), build tools (17%→91%)

6. **Released v1.2025.12.7** - Published to PyPI via GitHub Actions

### Session 4 - Product Rename

1. **Renamed to Fastband Agent Control**
   - New PyPI package: `fastband-agent-control`
   - Updated CLI branding and help text
   - Updated version to 1.2025.12.6

### Recent Commits (main branch)

```
afb4d70 feat(install): All-inclusive package with Hub deps + AI Provider settings
a85a22a fix(hub): Fix TypeScript strict mode errors in dashboard
7a0ba23 fix(ci): Add dashboard build step to CI/CD workflows
07305e4 chore(release): v1.2025.12.1 - Control Plane & Security Fixes
```

## Pending Work / Known Issues

### Installation Test Results (Session 6)

**v1.2025.12.7 Verified Working:**
- ✅ Clean pipx install (~7.4 seconds)
- ✅ All dependencies bundled (no manual injection needed)
- ✅ WebSocket connects successfully (101 Switching Protocols)
- ✅ Dashboard loads and connects
- ✅ API endpoints work correctly

**Minor Issues:**
- Python 3.14 logging cosmetic error (not a Fastband bug)
- Project path not configurable from dashboard UI

### Near-term Tasks

1. **Consider `fastband doctor` CLI command** for self-diagnosis

2. ~~**Chat Feature**~~ ✅ COMPLETED (Session 13)
   - CLI Chat fully functional with Claude API
   - API keys persist to `.fastband/.env`
   - All 20 tools execute correctly
   - Chat persists across navigation

3. **Test Coverage**
   - Currently at ~64%, target 80%+
   - Hub components need more integration tests
   - Add tests for claude.py message format conversion

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
| `src/fastband/hub/web/src/pages/Settings.tsx` | AI Providers settings UI |
| `src/fastband/hub/control_plane/routes.py` | Control Plane + WebSocket |
| `src/fastband/hub/server.py` | Hub server launcher |
| `src/fastband/cli/main.py` | CLI commands |
| `.github/workflows/release.yml` | PyPI release workflow |

## Release History

| Version | Date | Highlights |
|---------|------|------------|
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

1. ✅ ~~Streamline installation (move hub deps to core)~~ Done
2. ✅ ~~Add AI Provider settings UI~~ Done
3. ✅ ~~Publish v1.2025.12.7~~ Done
4. ✅ ~~Collect installation feedback from elaris-web test~~ Verified working!
5. ✅ ~~Verify WebSocket connectivity in fresh install~~ Confirmed working!
6. ✅ ~~Auto-port selection for multi-project support~~ Done (Session 7)
7. ✅ ~~Tickets page in Hub dashboard~~ Done (Session 7)
8. ✅ ~~Backups page in Hub dashboard~~ Done (Session 7)
9. Consider adding persistent API key storage (encrypted file or keychain)
10. Add `fastband doctor` CLI command for self-diagnosis
11. Increase test coverage to 80%+
12. Add E2E tests for Control Plane dashboard
13. Add project path configuration to dashboard UI

## Contacts & Resources

- **Repository:** https://github.com/RemmyCH3CK/fastband-mcp
- **PyPI:** https://pypi.org/project/fastband-agent-control/
- **Docs:** `docs/` directory
- **Changelog:** `CHANGELOG.md`

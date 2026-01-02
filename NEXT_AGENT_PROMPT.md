# Next Agent Prompt - Fastband Agent Control

## Quick Start

```bash
# Project location
cd /Volumes/apps/fastband-mcp

# Read full project context
cat HANDOFF.md

# Start the server
.venv/bin/python -m fastband.hub.server --port 8080

# Run tests
.venv/bin/pytest tests/ -v
```

**Handoff Document:** `/Volumes/apps/fastband-mcp/HANDOFF.md`

---

## Context

You are continuing work on **Fastband Agent Control**, a universal platform for AI agent coordination, multi-agent orchestration, and autonomous development workflows.

- **Repository:** https://github.com/RemmyCH3CK/fastband-mcp
- **PyPI Package:** `fastband-agent-control`
- **Current Version:** 1.2026.01.01 (released 2026-01-01)
- **Branch:** main (clean, all changes committed and pushed)
- **CI Status:** All checks passing

## What Was Just Completed

### Session 14 (2026-01-01)
- Bumped version to v1.2026.01.01
- Published to PyPI via GitHub Actions release workflow
- Updated HANDOFF.md with full Session 13 and 14 documentation

### Session 13 (2026-01-01) - CLI Chat Complete Overhaul
Major fixes to make the Hub CLI Chat fully functional:

1. **API Key Persistence**
   - Keys saved to `.fastband/.env` via `/api/providers/configure`
   - Multi-location search: cwd/.fastband/.env, project root, ~/.fastband/.env
   - Keys persist across server restarts

2. **Claude API Message Format Conversion**
   - System messages extracted to `system` parameter (Claude rejects role="system")
   - Tool results flushed BEFORE next assistant message (Claude requires tool_use → tool_result pairing)
   - OpenAI format `{function: {name, arguments}}` converted to Claude `{type: "tool_use", id, name, input}`
   - Added `tool_calls` property to `CompletionResponse`

3. **Tool Execution Fix**
   - Changed `registry.get()` to `registry.get_available()` in ToolExecutor
   - `get()` returns only "active" tools, `get_available()` returns all registered tools
   - All 20 tools now execute correctly (git, onboarding, tickets, codebase search, etc.)

4. **Chat Persistence**
   - Messages stored in localStorage with key `fastband_cli_messages`
   - Session ID stored with key `fastband_cli_session_id`
   - Conversation survives page refresh and navigation

5. **Backup Settings Tab**
   - New Backup tab in Settings page
   - Native macOS Finder folder picker via osascript
   - Configurable: backup path, retention days, interval, max count

## Architecture Overview

```
src/fastband/
├── __init__.py              # Version: 1.2026.01.01
├── __main__.py              # CLI entry point
├── cli/                     # CLI commands (typer)
│   └── main.py              # fastband serve, setup, auth, etc.
├── core/                    # Core configuration
│   ├── config.py            # FastbandConfig
│   └── system_capabilities.py  # RAM/CPU detection
├── providers/               # AI Provider integrations
│   ├── base.py              # BaseProvider, CompletionResponse
│   ├── claude.py            # Claude API (message format conversion)
│   ├── openai.py            # OpenAI API
│   ├── gemini.py            # Google Gemini
│   └── ollama.py            # Ollama local models
├── hub/                     # Web Hub
│   ├── server.py            # Uvicorn launcher
│   ├── chat.py              # Chat pipeline + tool execution
│   ├── api/
│   │   ├── app.py           # FastAPI app
│   │   └── routes.py        # All API endpoints
│   ├── control_plane/       # Real-time dashboard
│   │   ├── routes.py        # WebSocket + REST
│   │   └── service.py       # Control Plane service
│   ├── web/                 # React/TypeScript frontend
│   │   └── src/
│   │       ├── App.tsx
│   │       ├── pages/       # Settings, Tickets, Backups, etc.
│   │       └── components/
│   │           └── control-plane/
│   │               └── CLIChatPanel.tsx  # CLI Chat UI
│   └── static/              # Built dashboard (auto-generated)
├── tools/                   # MCP Tools (50+)
│   ├── registry.py          # Tool registration
│   ├── git/                 # Git operations
│   ├── tickets/             # Ticket management
│   └── ...
├── backup/                  # Backup system
│   ├── manager.py           # BackupManager
│   └── scheduler.py         # Scheduled backups
└── wizard/                  # Setup wizard
```

## Key Files for Common Tasks

| Task | Files |
|------|-------|
| Fix chat issues | `hub/chat.py`, `providers/claude.py`, `providers/base.py` |
| Fix API endpoints | `hub/api/routes.py` |
| Fix dashboard UI | `hub/web/src/pages/*.tsx`, `hub/web/src/components/**/*.tsx` |
| Fix tool execution | `tools/registry.py`, `hub/chat.py` |
| Add CLI commands | `cli/main.py` |
| Fix providers | `providers/claude.py`, `providers/openai.py` |
| Fix backups | `backup/manager.py`, `backup/scheduler.py` |

## Suggested Next Steps

### 1. Add Unit Tests for Session 13 Changes (Priority: High)

The message format conversion in `claude.py` is critical and untested:

```python
# src/fastband/providers/claude.py - needs tests for:
# - System message extraction
# - Tool use/result pairing
# - OpenAI → Claude format conversion
# - Pending tool results flushing
```

```python
# src/fastband/hub/chat.py - needs tests for:
# - Tool execution with get_available()
# - Message deduplication
# - Multi-turn conversations with tools
```

### 2. OpenAI Provider Compatibility (Priority: Medium)

The OpenAI provider may need similar message format handling:
- Check `src/fastband/providers/openai.py`
- The streaming endpoint (`/chat/stream`) may need fixes similar to `/chat`

### 3. Test Coverage Improvement (Priority: Medium)

- Current coverage: ~64%
- Target: 80%+
- Focus areas: Hub components, provider integrations

### 4. Consider `fastband doctor` CLI Command (Priority: Low)

Self-diagnosis tool for troubleshooting:
- Check API keys configured
- Check dependencies installed
- Check server connectivity
- Check tool registration

## Important Technical Details

### Claude API Quirks
```python
# WRONG - Claude rejects this:
messages = [{"role": "system", "content": "You are helpful"}]

# CORRECT - Use system parameter:
response = client.messages.create(
    system="You are helpful",
    messages=[...]
)
```

### Tool Use/Result Pairing
```python
# Claude requires tool_result IMMEDIATELY after tool_use
# WRONG:
[assistant with tool_use, assistant with tool_use, user with tool_results]

# CORRECT:
[assistant with tool_use, user with tool_result, assistant with tool_use, user with tool_result]
```

### Tool Registry
```python
# get() returns only "active" tools (may be None even if registered)
tool = registry.get("git_status")  # May return None!

# get_available() returns all registered tools
tool = registry.get_available("git_status")  # Returns the tool
```

### Session ID Format
```python
# Session ID must start with "chat-" or "dev-" for auto-creation
session_id = f"chat-{uuid.uuid4()}"  # Works
session_id = f"my-session"           # Fails - no auto-creation
```

## Testing the CLI Chat

1. Start server: `.venv/bin/python -m fastband.hub.server --port 8080`
2. Open: `http://localhost:8080`
3. Click the terminal bar at the bottom to expand CLI
4. Try these commands:
   - "check git status"
   - "help me start onboarding"
   - "list available tools"
   - "search the codebase for TODO"

## Build Dashboard (if modifying frontend)

```bash
cd src/fastband/hub/web
npm install
npm run build
cp -r dist ../static
```

## Release Process

```bash
# 1. Update version in pyproject.toml and src/fastband/__init__.py
# 2. Commit and push
git add -A && git commit -m "chore: Bump version to vX.Y.Z" && git push

# 3. Create GitHub release (triggers PyPI publish)
gh release create vX.Y.Z --title "vX.Y.Z - Title" --notes "Release notes..."
```

## Debugging Tips

### Check API Key Loading
```python
# In routes.py, keys are loaded from multiple locations:
possible_paths = [
    Path.cwd() / ".fastband" / ".env",
    Path(__file__).parent.parent.parent.parent / ".fastband" / ".env",
    Path.home() / ".fastband" / ".env",
]
```

### Check Tool Registration
```python
# In chat.py, list available tools:
from fastband.tools.registry import registry
print(list(registry.get_all_available().keys()))
```

### Check Message Format
```python
# Add debug logging to claude.py:
import sys
print(f"DEBUG messages: {claude_messages}", file=sys.stderr)
```

## Resources

- **Full Handoff:** `/Volumes/apps/fastband-mcp/HANDOFF.md`
- **Repository:** https://github.com/RemmyCH3CK/fastband-mcp
- **PyPI:** https://pypi.org/project/fastband-agent-control/
- **Release:** https://github.com/RemmyCH3CK/fastband-mcp/releases/tag/v1.2026.01.01

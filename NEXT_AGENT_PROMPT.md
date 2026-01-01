# Next Agent Prompt - Fastband Agent Control

## Context

You are continuing work on **Fastband Agent Control**, a universal platform for AI agent coordination. The project is located at `/Volumes/apps/fastband-mcp`.

## What Was Just Completed (Session 13)

The Hub CLI Chat is now fully functional:

1. **CLI Chat works end-to-end** - Natural language conversations with Claude, tool execution (git, onboarding, tickets, codebase search), and multi-turn conversations
2. **API keys persist** - Saved to `.fastband/.env` and loaded on server start
3. **Chat history persists** - Messages stored in localStorage, survive page navigation
4. **Backup settings added** - Settings page now has a Backup tab with native macOS folder picker
5. **Tool execution fixed** - All 20 registered tools now execute correctly

## Current State

- **Server running:** `http://localhost:8080`
- **CLI Chat:** Working in Control Plane dashboard
- **Branch:** main (uncommitted changes from session 13)

## Pending Changes (Uncommitted)

```
M src/fastband/backup/manager.py           # Use configured backup path
M src/fastband/hub/api/routes.py           # .env persistence, backup config
M src/fastband/hub/chat.py                 # get_available() fix, message dedup
M src/fastband/providers/base.py           # tool_calls property
M src/fastband/providers/claude.py         # OpenAI→Claude format conversion
M src/fastband/hub/web/src/pages/Settings.tsx  # Backup tab
M src/fastband/hub/web/src/components/control-plane/CLIChatPanel.tsx  # Persistence
```

## Suggested Next Steps

1. **Commit Session 13 Changes** - The fixes are tested and working, ready to commit
2. **Add Tests** - The claude.py message format conversion needs unit tests
3. **OpenAI Provider Compatibility** - Similar message format handling may be needed for OpenAI
4. **Streaming Chat** - The streaming endpoint (`/chat/stream`) may need similar fixes
5. **Release v1.2025.12.29** - Consider a new release with CLI Chat fixes

## Key Files to Know

| File | Purpose |
|------|---------|
| `src/fastband/providers/claude.py` | Claude API integration with message format conversion |
| `src/fastband/hub/chat.py` | Chat pipeline with tool execution loop |
| `src/fastband/hub/api/routes.py` | All Hub API endpoints |
| `src/fastband/hub/web/src/components/control-plane/CLIChatPanel.tsx` | CLI Chat UI |
| `HANDOFF.md` | Full project context and history |

## How to Start Server

```bash
cd /Volumes/apps/fastband-mcp
.venv/bin/python -m fastband.hub.server --port 8080
```

## Testing CLI Chat

1. Open `http://localhost:8080`
2. Click the terminal bar at the bottom to expand CLI
3. Try: "check git status" or "help me start onboarding"

## Important Technical Details

- Claude API requires `system` parameter, not `role: "system"` in messages
- Claude requires `tool_use` immediately followed by `tool_result` (no batching)
- Tool registry has `get()` for active tools, `get_available()` for all registered tools
- Session ID must start with `chat-` or `dev-` for auto-session creation

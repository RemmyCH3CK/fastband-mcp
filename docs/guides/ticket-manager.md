# Ticket Manager Guide

The Ticket Manager is Fastband's built-in task tracking system designed for AI-assisted development workflows. It adapts to your project type and supports multi-agent coordination.

## Overview

The Ticket Manager provides:
- **Task tracking** - Create, assign, and track development tasks
- **Status workflow** - Clear progression from open to closed
- **Agent enforcement** - AI agents can't resolve their own work
- **Code review** - Built-in review workflow before resolution
- **Web dashboard** - Visual interface for ticket management
- **CLI interface** - Full control from the command line

## Ticket Modes

Configure the interface mode based on your project:

| Mode | Interface | Best For |
|------|-----------|----------|
| `cli` | Command-line only | APIs, libraries, CLI tools |
| `cli_web` | CLI + Web dashboard | Web apps, general development |
| `embedded` | Embedded panel (Ctrl+Shift+T) | Desktop applications |

Configure in `.fastband/config.yaml`:

```yaml
tickets:
  enabled: true
  mode: "cli_web"
  web_port: 5050
```

## Ticket Status Workflow

Tickets progress through these statuses:

```
OPEN --> IN_PROGRESS --> UNDER_REVIEW --> AWAITING_APPROVAL --> RESOLVED --> CLOSED
                  ^                |
                  |                v
                  +---- BLOCKED ---+
```

| Status | Description |
|--------|-------------|
| Open | New ticket, not yet started |
| In Progress | Agent is actively working on it |
| Under Review | Work complete, awaiting code review |
| Awaiting Approval | Code review passed, awaiting human approval |
| Resolved | Approved and complete |
| Closed | Archived |
| Blocked | Cannot proceed, requires intervention |

## CLI Commands

### List Tickets

```bash
# List all tickets
fastband tickets list

# Filter by status
fastband tickets list --status open
fastband tickets list --status in_progress

# Filter by priority
fastband tickets list --priority high
fastband tickets list --priority critical

# Filter by type
fastband tickets list --type bug
fastband tickets list --type feature

# Filter by assignee
fastband tickets list --assignee MCP_Agent1

# Search tickets
fastband tickets search "authentication"
```

### Create Tickets

```bash
# Simple creation
fastband tickets create "Add user authentication"

# With full details
fastband tickets create "Fix login timeout" \
  --type bug \
  --priority high \
  --description "Users are logged out after 5 minutes of inactivity" \
  --labels security,ux \
  --files-to-modify "auth.py,session.py"
```

### View Ticket Details

```bash
fastband tickets show 1
```

Output:
```
Ticket #1: Add user authentication
============================================================
Status: In Progress          Priority: High
Type: Feature               Assigned: MCP_Agent1
Created: 2024-12-15 10:30   Updated: 2024-12-15 11:45

Description:
  Implement OAuth2 authentication with Google and GitHub providers.

Requirements:
  - Support Google OAuth
  - Support GitHub OAuth
  - Store user sessions in database

Files to Modify:
  - auth.py
  - routes/login.py
  - templates/login.html

History:
  [2024-12-15 10:30] Created by human
  [2024-12-15 10:45] Claimed by MCP_Agent1
  [2024-12-15 11:30] Status changed to IN_PROGRESS
```

### Claim Tickets (AI Agents)

AI agents claim tickets to start working:

```bash
fastband tickets claim 1 --agent MCP_Agent1
```

This:
- Sets status to `IN_PROGRESS`
- Assigns the ticket to the agent
- Records the action in history

### Complete Work

When work is done, submit for review:

```bash
fastband tickets complete 1 \
  --agent MCP_Agent1 \
  --problem "No OAuth authentication" \
  --solution "Implemented Google and GitHub OAuth with session management" \
  --files-modified "auth.py,routes/login.py" \
  --before-screenshot "/path/to/before.png" \
  --after-screenshot "/path/to/after.png" \
  --testing-notes "Tested with both providers, sessions persist correctly"
```

This sets status to `UNDER_REVIEW`.

### Update Tickets

```bash
# Update priority
fastband tickets update 1 --priority critical

# Add notes
fastband tickets update 1 --notes "Blocked by database migration"

# Add labels
fastband tickets update 1 --labels "security,p0"
```

### Approve/Reject (Human Only)

```bash
# Approve (moves to RESOLVED)
fastband tickets approve 1 --reviewer "human-name"

# Reject (moves back to IN_PROGRESS)
fastband tickets reject 1 \
  --reviewer "human-name" \
  --reason "Missing test coverage"
```

## Web Dashboard

Start the web interface:

```bash
fastband tickets serve --port 5050
```

Access at http://localhost:5050

### Dashboard Features

- **Overview** - Statistics and recent activity
- **Ticket Board** - Kanban-style view by status
- **Ticket List** - Filterable table view
- **Ticket Detail** - Full ticket information
- **Agent Status** - Active agents and their work
- **Dark/Light Mode** - Toggle theme

### API Endpoints

The web dashboard exposes a JSON API:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/tickets` | GET | List tickets with filters |
| `/api/tickets/<id>` | GET | Get ticket details |
| `/api/agents` | GET | List agents |
| `/api/stats` | GET | Dashboard statistics |
| `/api/health` | GET | Health check |

Query parameters for `/api/tickets`:
- `status` - Filter by status
- `priority` - Filter by priority
- `type` - Filter by type
- `assignee` - Filter by assignee
- `q` - Search query
- `limit` - Results per page
- `offset` - Pagination offset

## Ticket Types

| Type | Description |
|------|-------------|
| `bug` | Something is broken |
| `feature` | New functionality |
| `enhancement` | Improve existing feature |
| `task` | General task |
| `documentation` | Documentation updates |
| `maintenance` | Code cleanup, refactoring |
| `security` | Security-related |
| `performance` | Performance improvements |

## Priority Levels

| Priority | Description |
|----------|-------------|
| `critical` | Drop everything, fix now |
| `high` | Important, do soon |
| `medium` | Normal priority |
| `low` | Nice to have, when time permits |

## Agent Enforcement

AI agents have restrictions to ensure quality:

### What Agents CAN Do

- Claim open tickets
- Update ticket notes and labels
- Complete work (submit for review)
- Add comments

### What Agents CANNOT Do

- Resolve their own tickets (requires human approval)
- Close tickets
- Delete tickets
- Override human decisions

This ensures human oversight of all AI work.

## Review Workflow

### Code Review Agents

Enable automatic code review:

```yaml
tickets:
  review_agents: true
```

When a ticket is submitted for review:
1. **Code Review Agent** - Checks code quality, bugs, security
2. **Process Audit Agent** - Verifies screenshots, documentation
3. **UI/UX Review Agent** - Checks design compliance (if applicable)

All must approve before moving to `AWAITING_APPROVAL`.

### Manual Review

Human reviewers can:

```bash
# View pending reviews
fastband tickets list --status under_review

# Approve
fastband tickets approve 1 --reviewer "your-name"

# Request changes
fastband tickets reject 1 \
  --reviewer "your-name" \
  --reason "Please add error handling for network failures"
```

## Programmatic Access

### Using Ticket Tools

```python
from fastband.tools.tickets import (
    ListTicketsTool,
    GetTicketDetailsTool,
    CreateTicketTool,
    ClaimTicketTool,
    CompleteTicketSafelyTool,
)

# List tickets
list_tool = ListTicketsTool()
result = await list_tool.execute(status="open", priority="high")
for ticket in result.data["tickets"]:
    print(f"#{ticket['id']}: {ticket['title']}")

# Get details
details_tool = GetTicketDetailsTool()
result = await details_tool.execute(ticket_id="1")
ticket = result.data["ticket"]

# Create ticket
create_tool = CreateTicketTool()
result = await create_tool.execute(
    title="Fix authentication bug",
    description="Users cannot login with email",
    ticket_type="bug",
    priority="high"
)
new_id = result.data["ticket_id"]

# Claim ticket
claim_tool = ClaimTicketTool()
result = await claim_tool.execute(
    ticket_id=new_id,
    agent_name="MCP_Agent1"
)
```

### Using Storage Directly

```python
from fastband.tickets import get_store, Ticket, TicketStatus

store = get_store()

# List all open tickets
tickets = store.list(status=TicketStatus.OPEN)

# Get specific ticket
ticket = store.get("1")

# Search
results = store.search("authentication")

# Count
open_count = store.count(status=TicketStatus.OPEN)
```

## Best Practices

### 1. Write Clear Ticket Titles

```bash
# Good
fastband tickets create "Add password reset email functionality"

# Avoid
fastband tickets create "Fix the thing"
```

### 2. Include Detailed Descriptions

```bash
fastband tickets create "Add rate limiting to API" \
  --description "Implement rate limiting to prevent abuse:
    - 100 requests per minute per IP
    - 1000 requests per hour per API key
    - Return 429 status when exceeded"
```

### 3. Use Screenshots

Before/after screenshots help reviewers understand changes:

```bash
fastband tickets complete 1 \
  --before-screenshot "screenshots/before.png" \
  --after-screenshot "screenshots/after.png"
```

### 4. Keep Tickets Focused

One ticket = one task. Split large features into multiple tickets.

### 5. Update Status Promptly

Keep status current so the team knows what's happening.

## Troubleshooting

### "Ticket cannot be claimed"

- Ticket may already be assigned
- Ticket may not be in OPEN status
- Agent name may be invalid

### "Cannot complete ticket"

- Ticket must be IN_PROGRESS status
- Must be assigned to the agent completing it
- Screenshots are required

### Web dashboard not loading

- Check if port is in use: `lsof -i :5050`
- Verify configuration: `fastband config get tickets.web_port`
- Check logs for errors

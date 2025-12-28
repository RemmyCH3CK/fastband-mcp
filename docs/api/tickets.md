# Tickets API Reference

Complete API documentation for Fastband's ticket management system.

## Module: `fastband.tickets`

### Functions

#### `get_store(path: Path = None) -> TicketStore`

Get the ticket store instance.

**Parameters:**
- `path` (Path, optional): Custom storage path.

**Returns:** TicketStore instance.

**Example:**
```python
from fastband.tickets import get_store

store = get_store()
tickets = store.list(status=TicketStatus.OPEN)
```

---

## Class: `Ticket`

Represents a development ticket/task.

**Module:** `fastband.tickets.models`

### Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `id` | str | Unique ticket ID |
| `title` | str | Ticket title |
| `description` | str | Detailed description |
| `status` | TicketStatus | Current status |
| `priority` | TicketPriority | Priority level |
| `ticket_type` | TicketType | Type of ticket |
| `assigned_to` | Optional[str] | Assigned agent name |
| `created_at` | datetime | Creation timestamp |
| `updated_at` | datetime | Last update timestamp |
| `created_by` | str | Creator name |
| `requirements` | List[str] | Acceptance criteria |
| `files_to_modify` | List[str] | Files expected to change |
| `files_modified` | List[str] | Files actually changed |
| `labels` | List[str] | Tags/labels |
| `app` | Optional[str] | Associated application |
| `related_tickets` | List[str] | Related ticket IDs |
| `problem_summary` | Optional[str] | Problem description |
| `solution_summary` | Optional[str] | Solution description |
| `testing_notes` | Optional[str] | Testing information |
| `before_screenshot` | Optional[str] | Before screenshot path |
| `after_screenshot` | Optional[str] | After screenshot path |
| `notes` | Optional[str] | Additional notes |
| `history` | List[TicketHistory] | Change history |
| `comments` | List[TicketComment] | Comments |

### Methods

#### `claim(agent_name: str) -> bool`

Claim the ticket for work.

**Parameters:**
- `agent_name` (str): Agent claiming the ticket.

**Returns:** True if claimed successfully.

**Example:**
```python
ticket = store.get("1")
if ticket.claim("MCP_Agent1"):
    print("Ticket claimed!")
```

---

#### `complete(problem_summary: str, solution_summary: str, files_modified: List[str], ...) -> bool`

Complete work and submit for review.

**Parameters:**
- `problem_summary` (str): Summary of the problem.
- `solution_summary` (str): Summary of the solution.
- `files_modified` (List[str]): Files that were modified.
- `testing_notes` (str, optional): Testing notes.
- `before_screenshot` (str, optional): Before screenshot path.
- `after_screenshot` (str, optional): After screenshot path.
- `actor` (str): Who is completing.
- `actor_type` (str): "ai" or "human".

**Returns:** True if completed successfully.

---

#### `add_history(action: str, actor: str, actor_type: str, **kwargs) -> TicketHistory`

Add an entry to ticket history.

**Parameters:**
- `action` (str): Action type.
- `actor` (str): Who performed the action.
- `actor_type` (str): "ai", "human", or "system".
- `**kwargs`: Additional history data.

**Returns:** TicketHistory entry.

---

#### `add_comment(content: str, author: str, author_type: str, comment_type: str = "comment") -> TicketComment`

Add a comment to the ticket.

**Parameters:**
- `content` (str): Comment text.
- `author` (str): Comment author.
- `author_type` (str): "ai" or "human".
- `comment_type` (str): Type of comment.

**Returns:** TicketComment instance.

---

#### `to_dict() -> Dict[str, Any]`

Convert ticket to dictionary.

**Returns:** Dictionary representation.

---

#### `@classmethod from_dict(data: Dict[str, Any]) -> Ticket`

Create ticket from dictionary.

**Parameters:**
- `data` (Dict): Ticket data.

**Returns:** Ticket instance.

---

## Enum: `TicketStatus`

Ticket status values.

**Module:** `fastband.tickets.models`

### Values

| Value | Display Name | Description |
|-------|--------------|-------------|
| `OPEN` | Open | New, not started |
| `IN_PROGRESS` | In Progress | Being worked on |
| `UNDER_REVIEW` | Under Review | Awaiting code review |
| `AWAITING_APPROVAL` | Awaiting Approval | Awaiting human approval |
| `RESOLVED` | Resolved | Complete and approved |
| `CLOSED` | Closed | Archived |
| `BLOCKED` | Blocked | Cannot proceed |

### Properties

#### `display_name: str`

Human-readable display name.

#### `emoji: str`

Status emoji for UI.

### Methods

#### `@classmethod from_string(value: str) -> TicketStatus`

Parse status from string.

**Example:**
```python
status = TicketStatus.from_string("open")
status = TicketStatus.from_string("in_progress")
status = TicketStatus.from_string("In Progress")  # Also works
```

---

## Enum: `TicketPriority`

Ticket priority levels.

**Module:** `fastband.tickets.models`

### Values

| Value | Display Name | Description |
|-------|--------------|-------------|
| `CRITICAL` | Critical | Drop everything |
| `HIGH` | High | Important |
| `MEDIUM` | Medium | Normal |
| `LOW` | Low | When time permits |

---

## Enum: `TicketType`

Ticket types.

**Module:** `fastband.tickets.models`

### Values

| Value | Display Name | Description |
|-------|--------------|-------------|
| `BUG` | Bug | Something is broken |
| `FEATURE` | Feature | New functionality |
| `ENHANCEMENT` | Enhancement | Improve existing |
| `TASK` | Task | General task |
| `DOCUMENTATION` | Documentation | Docs updates |
| `MAINTENANCE` | Maintenance | Cleanup/refactor |
| `SECURITY` | Security | Security-related |
| `PERFORMANCE` | Performance | Performance improvement |

---

## Class: `Agent`

Represents an AI or human agent.

**Module:** `fastband.tickets.models`

### Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `name` | str | Agent name |
| `agent_type` | str | "ai" or "human" |
| `active` | bool | Is currently active |
| `tickets_in_progress` | int | Current ticket count |
| `tickets_completed` | int | Total completed |
| `last_activity` | datetime | Last activity time |

---

## Class: `TicketStore`

Abstract base class for ticket storage.

**Module:** `fastband.tickets.storage`

### Methods

#### `create(ticket: Ticket) -> Ticket`

Create a new ticket.

**Parameters:**
- `ticket` (Ticket): Ticket to create.

**Returns:** Created ticket with assigned ID.

---

#### `get(ticket_id: str) -> Optional[Ticket]`

Get a ticket by ID.

**Parameters:**
- `ticket_id` (str): Ticket ID.

**Returns:** Ticket or None if not found.

---

#### `update(ticket: Ticket) -> Ticket`

Update an existing ticket.

**Parameters:**
- `ticket` (Ticket): Ticket with updates.

**Returns:** Updated ticket.

---

#### `delete(ticket_id: str) -> bool`

Delete a ticket.

**Parameters:**
- `ticket_id` (str): Ticket ID.

**Returns:** True if deleted.

---

#### `list(status: TicketStatus = None, priority: TicketPriority = None, ticket_type: TicketType = None, assigned_to: str = None, limit: int = 100, offset: int = 0) -> List[Ticket]`

List tickets with optional filters.

**Parameters:**
- `status` (TicketStatus, optional): Filter by status.
- `priority` (TicketPriority, optional): Filter by priority.
- `ticket_type` (TicketType, optional): Filter by type.
- `assigned_to` (str, optional): Filter by assignee.
- `limit` (int): Maximum results.
- `offset` (int): Pagination offset.

**Returns:** List of matching tickets.

---

#### `search(query: str, fields: List[str] = None) -> List[Ticket]`

Search tickets by text.

**Parameters:**
- `query` (str): Search query.
- `fields` (List[str], optional): Fields to search.

**Returns:** List of matching tickets.

---

#### `count(status: TicketStatus = None, priority: TicketPriority = None) -> int`

Count tickets matching filters.

**Parameters:**
- `status` (TicketStatus, optional): Filter by status.
- `priority` (TicketPriority, optional): Filter by priority.

**Returns:** Count of matching tickets.

---

#### `get_agent(name: str) -> Optional[Agent]`

Get an agent by name.

**Parameters:**
- `name` (str): Agent name.

**Returns:** Agent or None.

---

#### `save_agent(agent: Agent) -> Agent`

Save/update an agent.

**Parameters:**
- `agent` (Agent): Agent to save.

**Returns:** Saved agent.

---

#### `list_agents(active_only: bool = True) -> List[Agent]`

List agents.

**Parameters:**
- `active_only` (bool): Only active agents.

**Returns:** List of agents.

---

## Class: `JSONTicketStore`

JSON file-based ticket storage.

**Module:** `fastband.tickets.storage`

### Constructor

```python
JSONTicketStore(path: Path)
```

**Parameters:**
- `path` (Path): Path to JSON file.

**Example:**
```python
from fastband.tickets.storage import JSONTicketStore
from pathlib import Path

store = JSONTicketStore(Path(".fastband/tickets.json"))
```

---

## Module: `fastband.tools.tickets`

MCP tools for ticket management.

### Class: `ListTicketsTool`

List tickets with filters.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `status` | string | No | Filter by status |
| `priority` | string | No | Filter by priority |
| `ticket_type` | string | No | Filter by type |
| `assigned_to` | string | No | Filter by assignee |
| `limit` | integer | No | Max results (default: 50) |
| `offset` | integer | No | Pagination offset |

**Returns:**
```python
{
    "tickets": List[Dict],  # Ticket summaries
    "count": int,           # Results returned
    "total": int,           # Total matching
    "has_more": bool        # More results available
}
```

---

### Class: `GetTicketDetailsTool`

Get full ticket details.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `ticket_id` | string | Yes | Ticket ID |

**Returns:**
```python
{
    "ticket": Dict  # Full ticket data
}
```

---

### Class: `CreateTicketTool`

Create a new ticket.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `title` | string | Yes | Ticket title |
| `description` | string | Yes | Description |
| `ticket_type` | string | No | Type (default: task) |
| `priority` | string | No | Priority (default: medium) |
| `requirements` | array | No | Requirements list |
| `files_to_modify` | array | No | Expected files |
| `labels` | array | No | Labels |
| `app` | string | No | Application name |
| `created_by` | string | No | Creator (default: system) |

**Returns:**
```python
{
    "ticket_id": str,   # New ticket ID
    "ticket": Dict,     # Ticket summary
    "message": str      # Success message
}
```

---

### Class: `ClaimTicketTool`

Claim a ticket to start work.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `ticket_id` | string | Yes | Ticket ID |
| `agent_name` | string | Yes | Your agent name |

**Returns:**
```python
{
    "ticket_id": str,
    "ticket": Dict,
    "message": str,
    "next_steps": List[str]  # What to do next
}
```

---

### Class: `CompleteTicketSafelyTool`

Complete work and submit for review.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `ticket_id` | string | Yes | Ticket ID |
| `agent_name` | string | Yes | Your agent name |
| `problem_summary` | string | Yes | Problem description |
| `solution_summary` | string | Yes | Solution description |
| `files_modified` | array | Yes | Files that were changed |
| `before_screenshot` | string | Yes | Before screenshot path |
| `after_screenshot` | string | Yes | After screenshot path |
| `testing_notes` | string | No | Testing notes |

**Returns:**
```python
{
    "ticket_id": str,
    "ticket": Dict,
    "message": str,
    "status": str,
    "next_steps": List[str]
}
```

---

### Class: `UpdateTicketTool`

Update ticket fields.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `ticket_id` | string | Yes | Ticket ID |
| `agent_name` | string | Yes | Your agent name |
| `priority` | string | No | New priority |
| `notes` | string | No | Notes to append |
| `labels` | array | No | New labels |
| `requirements` | array | No | New requirements |
| `files_to_modify` | array | No | New files list |

**Returns:**
```python
{
    "ticket_id": str,
    "changes": List[str],  # Changes made
    "message": str,
    "ticket": Dict
}
```

---

### Class: `SearchTicketsTool`

Search tickets by text.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `query` | string | Yes | Search query |
| `fields` | array | No | Fields to search |

**Returns:**
```python
{
    "query": str,
    "fields_searched": List[str],
    "tickets": List[Dict],
    "count": int
}
```

---

### Class: `AddTicketCommentTool`

Add a comment to a ticket.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `ticket_id` | string | Yes | Ticket ID |
| `agent_name` | string | Yes | Your agent name |
| `content` | string | Yes | Comment content |
| `comment_type` | string | No | Type (default: comment) |

**Returns:**
```python
{
    "ticket_id": str,
    "comment_id": str,
    "message": str,
    "comment": Dict
}
```

---

## Web Dashboard API

**Module:** `fastband.tickets.web`

### Endpoints

#### `GET /api/tickets`

List tickets with filters.

**Query Parameters:**
- `status` - Filter by status
- `priority` - Filter by priority
- `type` - Filter by type
- `assignee` - Filter by assignee
- `q` - Search query
- `limit` - Results per page
- `offset` - Pagination offset

**Response:**
```json
{
    "tickets": [...],
    "total": 100,
    "limit": 20,
    "offset": 0
}
```

---

#### `GET /api/tickets/<ticket_id>`

Get ticket details.

**Response:**
```json
{
    "ticket": {...}
}
```

---

#### `GET /api/agents`

List agents.

**Query Parameters:**
- `active_only` - Only active agents (default: true)

**Response:**
```json
{
    "agents": [...],
    "total": 5
}
```

---

#### `GET /api/stats`

Get dashboard statistics.

**Response:**
```json
{
    "total": 100,
    "by_status": {
        "open": 20,
        "in_progress": 10,
        ...
    },
    "by_priority": {
        "critical": 5,
        "high": 15,
        ...
    },
    "agents": {
        "total": 5,
        "active": 2
    }
}
```

---

#### `GET /api/health`

Health check.

**Response:**
```json
{
    "status": "healthy",
    "timestamp": "2024-12-15T10:30:00"
}
```

---

## Functions

### `create_app(store: TicketStore = None, config: Dict = None) -> Flask`

Create Flask application for web dashboard.

**Parameters:**
- `store` (TicketStore, optional): Ticket store instance.
- `config` (Dict, optional): Flask configuration.

**Returns:** Flask application.

---

### `serve(store: TicketStore = None, host: str = "127.0.0.1", port: int = 5000, debug: bool = False) -> None`

Start the web dashboard server.

**Parameters:**
- `store` (TicketStore, optional): Ticket store instance.
- `host` (str): Host address.
- `port` (int): Port number.
- `debug` (bool): Enable debug mode.

**Example:**
```python
from fastband.tickets.web import serve
from fastband.tickets.storage import JSONTicketStore

store = JSONTicketStore(Path(".fastband/tickets.json"))
serve(store, port=5050, debug=True)
```

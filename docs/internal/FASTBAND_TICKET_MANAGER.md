# Fastband Ticket Manager - Adaptive Design

## Overview

The Fastband Ticket Manager is an **adaptive ticket system** that changes its deployment and interface based on project type. Unlike traditional ticket systems that force a one-size-fits-all approach, this system:

1. **Web Apps** → CLI + Web Dashboard
2. **Desktop Apps** → Embedded panel (hideable, persistent)
3. **Mobile Apps** → CLI primary + Companion web
4. **API/Libraries** → CLI-only (lean)

---

## Core Architecture

```
ticket_manager/
├── core/                    # Shared core logic
│   ├── ticket.py           # Ticket model
│   ├── repository.py       # Data access layer
│   ├── workflow.py         # Status transitions
│   ├── review_system.py    # Review agent integration
│   └── events.py           # Event system for updates
├── interfaces/              # Deployment interfaces
│   ├── cli/                # Command-line interface
│   │   ├── commands.py
│   │   └── output.py
│   ├── web/                # Web dashboard
│   │   ├── app.py          # Flask/FastAPI app
│   │   ├── routes/
│   │   ├── templates/
│   │   └── static/
│   ├── embedded/           # Desktop embedded UI
│   │   ├── panel.py        # Main panel widget
│   │   ├── tray.py         # System tray
│   │   └── hotkeys.py      # Keyboard shortcuts
│   └── api/                # REST API for integrations
│       └── routes.py
├── integrations/           # External systems
│   ├── github_issues.py
│   ├── jira.py
│   ├── linear.py
│   └── notion.py
└── deployment/             # Deployment helpers
    ├── detector.py         # Auto-detect project type
    └── installer.py        # Install appropriate interface
```

---

## 1. Core Ticket Model

```python
# ticket_manager/core/ticket.py
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum


class TicketStatus(Enum):
    OPEN = "🔴 Open"
    IN_PROGRESS = "🟡 In Progress"
    UNDER_REVIEW = "🔍 Under Review"
    AWAITING_APPROVAL = "🔵 Awaiting Approval"
    RESOLVED = "🟢 Resolved"
    CLOSED = "⚫ Closed"
    BLOCKED = "🚧 Blocked"


class TicketPriority(Enum):
    CRITICAL = "Critical"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class TicketType(Enum):
    BUG = "Bug"
    FEATURE = "Feature"
    ENHANCEMENT = "Enhancement"
    TASK = "Task"
    DOCUMENTATION = "Documentation"
    MAINTENANCE = "Maintenance"


@dataclass
class TicketAttachment:
    """File attachment (screenshots, logs, etc.)."""
    id: str
    filename: str
    path: str
    mime_type: str
    size_bytes: int
    created_at: datetime
    thumbnail_path: Optional[str] = None


@dataclass
class TicketComment:
    """Ticket comment/note."""
    id: str
    author: str
    content: str
    created_at: datetime
    is_system: bool = False  # True for automated comments


@dataclass
class TicketReview:
    """Code review record."""
    reviewer: str
    review_type: str  # "code", "process", "uiux"
    status: str  # "pending", "approved", "rejected"
    comments: str
    timestamp: datetime


@dataclass
class Ticket:
    """Core ticket model."""

    # Identity
    id: str
    project_id: str

    # Basic info
    title: str
    description: str
    type: TicketType = TicketType.TASK
    priority: TicketPriority = TicketPriority.MEDIUM
    status: TicketStatus = TicketStatus.OPEN

    # Assignment
    assignee: Optional[str] = None
    reporter: str = "system"
    watchers: List[str] = field(default_factory=list)

    # Metadata
    labels: List[str] = field(default_factory=list)
    files_to_modify: List[str] = field(default_factory=list)
    requirements: List[str] = field(default_factory=list)

    # Relationships
    parent_id: Optional[str] = None
    related_ids: List[str] = field(default_factory=list)
    blocks_ids: List[str] = field(default_factory=list)
    blocked_by_ids: List[str] = field(default_factory=list)

    # Timestamps
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    due_date: Optional[datetime] = None

    # Work tracking
    time_estimate_minutes: Optional[int] = None
    time_spent_minutes: int = 0

    # Resolution
    resolution_summary: Optional[str] = None
    problem_summary: Optional[str] = None
    solution_summary: Optional[str] = None
    testing_notes: Optional[str] = None

    # Attachments and comments
    attachments: List[TicketAttachment] = field(default_factory=list)
    comments: List[TicketComment] = field(default_factory=list)

    # Reviews
    reviews: List[TicketReview] = field(default_factory=list)

    # External sync
    external_id: Optional[str] = None  # GitHub issue #, Jira key, etc.
    external_url: Optional[str] = None
    sync_enabled: bool = False

    # Custom fields (project-specific)
    custom_fields: Dict[str, Any] = field(default_factory=dict)

    def transition_to(self, new_status: TicketStatus, by: str) -> bool:
        """Validate and perform status transition."""
        valid_transitions = {
            TicketStatus.OPEN: [TicketStatus.IN_PROGRESS, TicketStatus.CLOSED],
            TicketStatus.IN_PROGRESS: [TicketStatus.UNDER_REVIEW, TicketStatus.BLOCKED, TicketStatus.OPEN],
            TicketStatus.UNDER_REVIEW: [TicketStatus.AWAITING_APPROVAL, TicketStatus.IN_PROGRESS],
            TicketStatus.AWAITING_APPROVAL: [TicketStatus.RESOLVED, TicketStatus.IN_PROGRESS],
            TicketStatus.RESOLVED: [TicketStatus.CLOSED, TicketStatus.OPEN],  # Reopen if needed
            TicketStatus.BLOCKED: [TicketStatus.IN_PROGRESS, TicketStatus.OPEN],
            TicketStatus.CLOSED: [TicketStatus.OPEN],  # Can reopen
        }

        if new_status not in valid_transitions.get(self.status, []):
            return False

        old_status = self.status
        self.status = new_status
        self.updated_at = datetime.now()

        # Record transition as system comment
        self.comments.append(TicketComment(
            id=f"comment_{datetime.now().timestamp()}",
            author="system",
            content=f"Status changed: {old_status.value} → {new_status.value} by {by}",
            created_at=datetime.now(),
            is_system=True,
        ))

        # Update timestamps based on transition
        if new_status == TicketStatus.IN_PROGRESS and not self.started_at:
            self.started_at = datetime.now()
        elif new_status == TicketStatus.RESOLVED:
            self.resolved_at = datetime.now()

        return True

    @property
    def duration_minutes(self) -> Optional[int]:
        """Calculate time from start to resolution."""
        if not self.started_at:
            return None
        end = self.resolved_at or datetime.now()
        return int((end - self.started_at).total_seconds() / 60)
```

---

## 2. Interface Implementations

### 2.1 CLI Interface (All Projects)

```python
# ticket_manager/interfaces/cli/commands.py
import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()


@click.group()
def tickets():
    """Fastband Ticket Manager CLI."""
    pass


@tickets.command()
@click.option('--status', '-s', help='Filter by status')
@click.option('--priority', '-p', help='Filter by priority')
@click.option('--assignee', '-a', help='Filter by assignee')
def list(status, priority, assignee):
    """List tickets with optional filters."""
    # Create rich table
    table = Table(title="Tickets")
    table.add_column("ID", style="cyan")
    table.add_column("Status", style="magenta")
    table.add_column("Priority")
    table.add_column("Title")
    table.add_column("Assignee")

    # Fetch and display tickets
    tickets = get_ticket_repository().list(
        status=status,
        priority=priority,
        assignee=assignee,
    )

    for ticket in tickets:
        table.add_row(
            ticket.id,
            ticket.status.value,
            ticket.priority.value,
            ticket.title[:50],
            ticket.assignee or "-",
        )

    console.print(table)


@tickets.command()
@click.argument('ticket_id')
def show(ticket_id):
    """Show detailed ticket information."""
    ticket = get_ticket_repository().get(ticket_id)
    if not ticket:
        console.print(f"[red]Ticket {ticket_id} not found[/red]")
        return

    # Create detailed panel
    content = f"""
[bold]{ticket.title}[/bold]

[dim]ID:[/dim] {ticket.id}
[dim]Status:[/dim] {ticket.status.value}
[dim]Priority:[/dim] {ticket.priority.value}
[dim]Type:[/dim] {ticket.type.value}
[dim]Assignee:[/dim] {ticket.assignee or 'Unassigned'}

[bold]Description:[/bold]
{ticket.description}

[bold]Files to Modify:[/bold]
{chr(10).join(f'  • {f}' for f in ticket.files_to_modify) or '  None specified'}
"""

    console.print(Panel(content, title=f"Ticket {ticket_id}"))


@tickets.command()
@click.argument('ticket_id')
@click.option('--agent', '-a', required=True, help='Your agent name')
def claim(ticket_id, agent):
    """Claim a ticket and start working on it."""
    result = claim_ticket(ticket_id, agent)
    if result['success']:
        console.print(f"[green]✓ Claimed ticket {ticket_id}[/green]")
        console.print(f"  Status: {result['new_status']}")
        console.print(f"  Assigned to: {agent}")
    else:
        console.print(f"[red]✗ Failed: {result['error']}[/red]")


@tickets.command()
@click.argument('ticket_id')
def complete(ticket_id):
    """Complete a ticket (interactive wizard)."""
    console.print(f"[bold]Completing ticket {ticket_id}[/bold]\n")

    # Interactive prompts for required fields
    problem = click.prompt("Problem summary (min 100 chars)")
    solution = click.prompt("Solution summary (min 150 chars)")
    testing = click.prompt("Testing notes (min 100 chars)")
    files = click.prompt("Files modified (comma-separated)")

    # Validate and complete
    result = complete_ticket(
        ticket_id=ticket_id,
        problem_summary=problem,
        solution_summary=solution,
        testing_notes=testing,
        files_modified=files.split(','),
    )

    if result['success']:
        console.print(f"[green]✓ Ticket {ticket_id} submitted for review[/green]")
    else:
        console.print(f"[red]✗ Failed: {result['error']}[/red]")


@tickets.command()
@click.argument('title')
@click.option('--description', '-d', required=True)
@click.option('--type', '-t', default='Task')
@click.option('--priority', '-p', default='Medium')
def create(title, description, type, priority):
    """Create a new ticket."""
    ticket = create_ticket(
        title=title,
        description=description,
        ticket_type=type,
        priority=priority,
    )
    console.print(f"[green]✓ Created ticket {ticket.id}[/green]")
    console.print(f"  Title: {ticket.title}")
```

### 2.2 Web Dashboard (Web Applications)

```python
# ticket_manager/interfaces/web/app.py
from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.websockets import WebSocket

app = FastAPI(title="Fastband Ticket Manager")

# Mount static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# WebSocket connections for real-time updates
active_connections: list[WebSocket] = []


@app.get("/")
async def dashboard(request: Request):
    """Main dashboard view."""
    tickets = get_ticket_repository().list()
    stats = {
        "open": len([t for t in tickets if t.status == TicketStatus.OPEN]),
        "in_progress": len([t for t in tickets if t.status == TicketStatus.IN_PROGRESS]),
        "under_review": len([t for t in tickets if t.status == TicketStatus.UNDER_REVIEW]),
        "resolved": len([t for t in tickets if t.status == TicketStatus.RESOLVED]),
    }

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "tickets": tickets,
        "stats": stats,
    })


@app.get("/tickets/{ticket_id}")
async def ticket_detail(request: Request, ticket_id: str):
    """Ticket detail view."""
    ticket = get_ticket_repository().get(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    return templates.TemplateResponse("ticket_detail.html", {
        "request": request,
        "ticket": ticket,
    })


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket for real-time updates."""
    await websocket.accept()
    active_connections.append(websocket)

    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except Exception:
        active_connections.remove(websocket)


async def broadcast_update(event: str, data: dict):
    """Broadcast update to all connected clients."""
    for connection in active_connections:
        await connection.send_json({"event": event, "data": data})


# REST API for programmatic access
@app.get("/api/tickets")
async def api_list_tickets(
    status: str = None,
    priority: str = None,
    assignee: str = None,
):
    """List tickets via API."""
    tickets = get_ticket_repository().list(
        status=status,
        priority=priority,
        assignee=assignee,
    )
    return {"tickets": [t.to_dict() for t in tickets]}


@app.post("/api/tickets")
async def api_create_ticket(data: dict):
    """Create ticket via API."""
    ticket = create_ticket(**data)
    await broadcast_update("ticket_created", ticket.to_dict())
    return {"ticket": ticket.to_dict()}


@app.put("/api/tickets/{ticket_id}")
async def api_update_ticket(ticket_id: str, data: dict):
    """Update ticket via API."""
    ticket = update_ticket(ticket_id, **data)
    await broadcast_update("ticket_updated", ticket.to_dict())
    return {"ticket": ticket.to_dict()}
```

### 2.3 Embedded Panel (Desktop Applications)

```python
# ticket_manager/interfaces/embedded/panel.py
"""
Embedded Ticket Panel for Desktop Applications

This creates a hideable panel that lives within the application,
accessible via hotkey or system tray. Designed to persist through
the entire product lifecycle.
"""

import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional
import threading


class TicketPanel:
    """
    Embeddable ticket management panel for desktop apps.

    Features:
    - Slide-in/out animation
    - Hotkey toggle (Ctrl+Shift+T)
    - System tray icon
    - Persistent through app lifecycle
    - Minimal resource usage when hidden
    """

    def __init__(
        self,
        parent: tk.Tk = None,
        position: str = "right",  # left, right, top, bottom
        width: int = 400,
        hotkey: str = "<Control-Shift-t>",
    ):
        self.parent = parent
        self.position = position
        self.panel_width = width
        self.hotkey = hotkey
        self.is_visible = False

        # Create the panel frame
        self._create_panel()
        self._setup_hotkey()
        self._setup_tray()

    def _create_panel(self):
        """Create the ticket panel UI."""
        self.frame = tk.Frame(
            self.parent,
            bg="#1e1e1e",  # Dark theme
            width=self.panel_width,
        )

        # Header
        header = tk.Frame(self.frame, bg="#2d2d2d", height=50)
        header.pack(fill=tk.X)

        title = tk.Label(
            header,
            text="📋 Tickets",
            font=("Helvetica", 14, "bold"),
            bg="#2d2d2d",
            fg="white",
        )
        title.pack(side=tk.LEFT, padx=10, pady=10)

        close_btn = tk.Button(
            header,
            text="×",
            command=self.hide,
            bg="#2d2d2d",
            fg="white",
            relief=tk.FLAT,
        )
        close_btn.pack(side=tk.RIGHT, padx=10)

        # Ticket list
        self.ticket_list = ttk.Treeview(
            self.frame,
            columns=("status", "title"),
            show="headings",
            height=20,
        )
        self.ticket_list.heading("status", text="Status")
        self.ticket_list.heading("title", text="Title")
        self.ticket_list.column("status", width=80)
        self.ticket_list.column("title", width=300)
        self.ticket_list.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Quick actions
        actions = tk.Frame(self.frame, bg="#1e1e1e")
        actions.pack(fill=tk.X, pady=10)

        new_btn = tk.Button(
            actions,
            text="+ New Ticket",
            command=self._new_ticket_dialog,
        )
        new_btn.pack(side=tk.LEFT, padx=5)

        refresh_btn = tk.Button(
            actions,
            text="↻ Refresh",
            command=self.refresh,
        )
        refresh_btn.pack(side=tk.LEFT)

    def _setup_hotkey(self):
        """Register global hotkey to toggle panel."""
        if self.parent:
            self.parent.bind(self.hotkey, lambda e: self.toggle())

    def _setup_tray(self):
        """Setup system tray icon."""
        # Use pystray or similar library
        # This runs in a separate thread
        pass

    def show(self, animate: bool = True):
        """Show the panel with optional slide animation."""
        if self.is_visible:
            return

        if animate:
            self._animate_in()
        else:
            self.frame.place(
                relx=1.0 if self.position == "right" else 0.0,
                rely=0,
                anchor="ne" if self.position == "right" else "nw",
                relheight=1.0,
            )

        self.is_visible = True
        self.refresh()

    def hide(self, animate: bool = True):
        """Hide the panel with optional slide animation."""
        if not self.is_visible:
            return

        if animate:
            self._animate_out()
        else:
            self.frame.place_forget()

        self.is_visible = False

    def toggle(self):
        """Toggle panel visibility."""
        if self.is_visible:
            self.hide()
        else:
            self.show()

    def _animate_in(self):
        """Slide-in animation."""
        # Implement smooth animation
        self.frame.place(
            relx=1.0,
            rely=0,
            anchor="ne",
            relheight=1.0,
        )

    def _animate_out(self):
        """Slide-out animation."""
        self.frame.place_forget()

    def refresh(self):
        """Refresh ticket list."""
        # Clear existing items
        for item in self.ticket_list.get_children():
            self.ticket_list.delete(item)

        # Fetch and display tickets
        tickets = get_ticket_repository().list(limit=50)
        for ticket in tickets:
            self.ticket_list.insert(
                "",
                tk.END,
                values=(ticket.status.value, ticket.title[:40]),
            )

    def _new_ticket_dialog(self):
        """Open new ticket dialog."""
        dialog = NewTicketDialog(self.parent, on_save=self.refresh)
        dialog.show()


class NewTicketDialog:
    """Dialog for creating new tickets."""

    def __init__(self, parent, on_save: Callable = None):
        self.parent = parent
        self.on_save = on_save
        self.window = None

    def show(self):
        """Show the dialog."""
        self.window = tk.Toplevel(self.parent)
        self.window.title("New Ticket")
        self.window.geometry("500x400")

        # Title
        tk.Label(self.window, text="Title:").pack(anchor=tk.W, padx=10, pady=5)
        self.title_entry = tk.Entry(self.window, width=60)
        self.title_entry.pack(padx=10)

        # Description
        tk.Label(self.window, text="Description:").pack(anchor=tk.W, padx=10, pady=5)
        self.desc_text = tk.Text(self.window, height=10, width=60)
        self.desc_text.pack(padx=10)

        # Type and Priority
        frame = tk.Frame(self.window)
        frame.pack(fill=tk.X, padx=10, pady=10)

        tk.Label(frame, text="Type:").pack(side=tk.LEFT)
        self.type_var = tk.StringVar(value="Task")
        type_combo = ttk.Combobox(
            frame,
            textvariable=self.type_var,
            values=["Bug", "Feature", "Task", "Enhancement"],
        )
        type_combo.pack(side=tk.LEFT, padx=5)

        tk.Label(frame, text="Priority:").pack(side=tk.LEFT, padx=10)
        self.priority_var = tk.StringVar(value="Medium")
        priority_combo = ttk.Combobox(
            frame,
            textvariable=self.priority_var,
            values=["Critical", "High", "Medium", "Low"],
        )
        priority_combo.pack(side=tk.LEFT)

        # Buttons
        btn_frame = tk.Frame(self.window)
        btn_frame.pack(pady=10)

        tk.Button(btn_frame, text="Create", command=self._create).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Cancel", command=self.window.destroy).pack(side=tk.LEFT)

    def _create(self):
        """Create the ticket."""
        ticket = create_ticket(
            title=self.title_entry.get(),
            description=self.desc_text.get("1.0", tk.END),
            ticket_type=self.type_var.get(),
            priority=self.priority_var.get(),
        )

        self.window.destroy()
        if self.on_save:
            self.on_save()
```

---

## 3. External Integrations

### GitHub Issues Sync

```python
# ticket_manager/integrations/github_issues.py
from typing import Optional, Dict, Any
from datetime import datetime
import httpx


class GitHubIntegration:
    """Two-way sync with GitHub Issues."""

    def __init__(self, token: str, owner: str, repo: str):
        self.token = token
        self.owner = owner
        self.repo = repo
        self.base_url = f"https://api.github.com/repos/{owner}/{repo}"
        self.headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
        }

    async def sync_to_github(self, ticket: Ticket) -> str:
        """Create or update GitHub issue from ticket."""
        async with httpx.AsyncClient() as client:
            if ticket.external_id:
                # Update existing issue
                response = await client.patch(
                    f"{self.base_url}/issues/{ticket.external_id}",
                    headers=self.headers,
                    json=self._ticket_to_issue(ticket),
                )
            else:
                # Create new issue
                response = await client.post(
                    f"{self.base_url}/issues",
                    headers=self.headers,
                    json=self._ticket_to_issue(ticket),
                )

            data = response.json()
            return str(data["number"])

    async def sync_from_github(self, issue_number: int) -> Dict[str, Any]:
        """Fetch GitHub issue and convert to ticket data."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/issues/{issue_number}",
                headers=self.headers,
            )
            return self._issue_to_ticket_data(response.json())

    async def sync_all(self, direction: str = "both"):
        """Perform full sync."""
        # Implementation for bulk sync
        pass

    def _ticket_to_issue(self, ticket: Ticket) -> dict:
        """Convert ticket to GitHub issue format."""
        labels = [ticket.type.value.lower()]
        if ticket.priority == TicketPriority.CRITICAL:
            labels.append("critical")
        elif ticket.priority == TicketPriority.HIGH:
            labels.append("high-priority")

        return {
            "title": ticket.title,
            "body": self._format_issue_body(ticket),
            "labels": labels,
            "assignees": [ticket.assignee] if ticket.assignee else [],
        }

    def _format_issue_body(self, ticket: Ticket) -> str:
        """Format ticket as GitHub issue body."""
        body = f"{ticket.description}\n\n"

        if ticket.requirements:
            body += "## Requirements\n"
            for req in ticket.requirements:
                body += f"- [ ] {req}\n"

        if ticket.files_to_modify:
            body += "\n## Files to Modify\n"
            for f in ticket.files_to_modify:
                body += f"- `{f}`\n"

        body += f"\n---\n*Synced from Fastband Ticket #{ticket.id}*"
        return body

    def _issue_to_ticket_data(self, issue: dict) -> Dict[str, Any]:
        """Convert GitHub issue to ticket data."""
        return {
            "external_id": str(issue["number"]),
            "external_url": issue["html_url"],
            "title": issue["title"],
            "description": issue["body"] or "",
            "status": self._map_issue_state(issue["state"]),
            "assignee": issue["assignee"]["login"] if issue["assignee"] else None,
        }

    def _map_issue_state(self, state: str) -> TicketStatus:
        """Map GitHub issue state to ticket status."""
        if state == "open":
            return TicketStatus.OPEN
        return TicketStatus.CLOSED
```

---

## 4. Deployment Modes

### Auto-Detection and Installation

```python
# ticket_manager/deployment/installer.py
from enum import Enum
from pathlib import Path
from typing import Optional


class DeploymentMode(Enum):
    CLI_ONLY = "cli"           # Lean CLI interface
    CLI_WEB = "cli_web"        # CLI + Web dashboard
    EMBEDDED = "embedded"       # Desktop embedded panel
    CLI_COMPANION = "cli_companion"  # CLI + companion web for mobile


class TicketManagerInstaller:
    """Install appropriate ticket manager interface."""

    def __init__(self, project_path: Path):
        self.project_path = project_path
        self.detected_type = self._detect_project_type()

    def _detect_project_type(self) -> str:
        """Detect project type from files."""
        indicators = {
            "web": ["package.json", "requirements.txt", "Gemfile"],
            "desktop": ["electron.js", "tauri.conf.json", "package.json"],
            "mobile": ["pubspec.yaml", "app.json", "Podfile", "build.gradle"],
            "api": ["openapi.yaml", "swagger.json"],
        }

        # Check for desktop-specific
        if (self.project_path / "electron.js").exists():
            return "desktop"
        if (self.project_path / "tauri.conf.json").exists():
            return "desktop"

        # Check for mobile
        if (self.project_path / "pubspec.yaml").exists():
            return "mobile"
        if (self.project_path / "app.json").exists():
            # Could be React Native or Expo
            return "mobile"

        # Default to web
        return "web"

    def get_recommended_mode(self) -> DeploymentMode:
        """Get recommended deployment mode."""
        recommendations = {
            "web": DeploymentMode.CLI_WEB,
            "desktop": DeploymentMode.EMBEDDED,
            "mobile": DeploymentMode.CLI_COMPANION,
            "api": DeploymentMode.CLI_ONLY,
        }
        return recommendations.get(self.detected_type, DeploymentMode.CLI_ONLY)

    def install(self, mode: Optional[DeploymentMode] = None):
        """Install ticket manager with specified mode."""
        if mode is None:
            mode = self.get_recommended_mode()

        print(f"Installing Fastband Ticket Manager ({mode.value})...")

        # Create configuration
        self._create_config(mode)

        # Install dependencies
        self._install_dependencies(mode)

        # Setup based on mode
        if mode == DeploymentMode.CLI_WEB:
            self._setup_web_dashboard()
        elif mode == DeploymentMode.EMBEDDED:
            self._setup_embedded_panel()
        elif mode == DeploymentMode.CLI_COMPANION:
            self._setup_companion_web()

        print(f"✓ Ticket Manager installed successfully!")

    def _create_config(self, mode: DeploymentMode):
        """Create ticket manager configuration."""
        config = {
            "mode": mode.value,
            "project_type": self.detected_type,
            "storage": "sqlite",
            "storage_path": ".fastband/tickets.db",
        }

        if mode == DeploymentMode.CLI_WEB:
            config["web_port"] = 5050
            config["web_host"] = "localhost"

        # Write config
        config_path = self.project_path / ".fastband" / "tickets.yaml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        # Write YAML config...

    def _setup_web_dashboard(self):
        """Setup web dashboard for web applications."""
        print("  → Setting up web dashboard on port 5050")
        # Configure FastAPI app, templates, etc.

    def _setup_embedded_panel(self):
        """Setup embedded panel for desktop applications."""
        print("  → Setting up embedded ticket panel")
        print("  → Hotkey: Ctrl+Shift+T to toggle")
        # Provide integration code for the desktop app

    def _setup_companion_web(self):
        """Setup companion web for mobile development."""
        print("  → Setting up companion web dashboard")
        # Lighter weight web interface for mobile dev
```

---

## 5. User Experience by Project Type

### Web Application Developer Journey

```
$ fastband init
✓ Detected: Web Application (React + Flask)
✓ Ticket Manager: CLI + Web Dashboard

$ fastband tickets serve
🌐 Ticket Dashboard: http://localhost:5050

$ fastband tickets create "Add user authentication"
✓ Created ticket #1: Add user authentication

$ fastband tickets claim 1 --agent "Developer1"
✓ Claimed ticket #1, status → In Progress
```

### Desktop Application Developer Journey

```
$ fastband init
✓ Detected: Desktop Application (Electron)
✓ Ticket Manager: Embedded Panel

Integration code added to your main process:
  const { TicketPanel } = require('fastband-tickets');
  TicketPanel.init();

Press Ctrl+Shift+T to toggle ticket panel in your app.
```

### Mobile Application Developer Journey

```
$ fastband init
✓ Detected: Mobile Application (Flutter)
✓ Ticket Manager: CLI + Companion Web

$ fastband tickets serve --companion
🌐 Companion Dashboard: http://localhost:5050
   Access from your phone: http://192.168.1.100:5050
```

---

## Summary

The Fastband Ticket Manager adapts to your project:

| Project Type | Primary Interface | Secondary | Special Features |
|--------------|------------------|-----------|-----------------|
| Web App | CLI | Web Dashboard | Real-time updates, screenshots |
| Desktop App | Embedded Panel | CLI | Hotkey toggle, system tray |
| Mobile App | CLI | Companion Web | Cross-device access |
| API/Library | CLI | None | Lean, fast |

This adaptive approach ensures developers always have the right tools for their context without unnecessary overhead.

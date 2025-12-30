"""
Flask-based web dashboard for ticket management.

Provides a web interface for viewing and managing tickets with:
- Dashboard overview with statistics
- Ticket listing with filters
- Ticket detail views
- JSON API endpoints
- Agent status panel
- Dark/light mode toggle
"""

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from flask import (
    Flask,
    Response,
    jsonify,
    render_template,
    request,
)

from fastband.tickets.models import (
    TicketPriority,
    TicketStatus,
    TicketType,
)
from fastband.tickets.storage import JSONTicketStore, TicketStore

logger = logging.getLogger(__name__)


def create_app(
    store: TicketStore | None = None,
    config: dict[str, Any] | None = None,
) -> Flask:
    """
    Create the Flask application for the ticket dashboard.

    Args:
        store: TicketStore instance to use. If None, creates a default one.
        config: Optional Flask configuration overrides.

    Returns:
        Flask application instance.
    """
    # Get template and static directories
    web_dir = Path(__file__).parent
    template_dir = web_dir / "templates"
    static_dir = web_dir / "static"

    app = Flask(
        __name__,
        template_folder=str(template_dir),
        static_folder=str(static_dir) if static_dir.exists() else None,
    )

    # Default configuration
    secret_key = os.environ.get("FASTBAND_SECRET_KEY", "dev-secret-key")
    if secret_key == "dev-secret-key":
        logger.warning(
            "Using default SECRET_KEY - this is insecure for production! "
            "Set FASTBAND_SECRET_KEY environment variable to a secure random value."
        )

    app.config.update(
        SECRET_KEY=secret_key,
        JSON_SORT_KEYS=False,
        JSONIFY_PRETTYPRINT_REGULAR=True,
    )

    # Apply custom config
    if config:
        app.config.update(config)

    # Create default store if not provided
    if store is None:
        default_path = Path.cwd() / ".fastband" / "tickets.json"
        store = JSONTicketStore(default_path)

    # Store the ticket store in app config for access in routes
    app.config["TICKET_STORE"] = store

    # Register template filters
    register_filters(app)

    # Register routes
    register_routes(app)

    return app


def register_filters(app: Flask) -> None:
    """Register custom Jinja2 filters."""

    @app.template_filter("datetime")
    def format_datetime(value: datetime | None, fmt: str = "%Y-%m-%d %H:%M") -> str:
        """Format datetime for display."""
        if value is None:
            return ""
        if isinstance(value, str):
            try:
                value = datetime.fromisoformat(value)
            except ValueError:
                return value
        return value.strftime(fmt)

    @app.template_filter("relative_time")
    def format_relative_time(value: datetime | None) -> str:
        """Format datetime as relative time (e.g., '2 hours ago')."""
        if value is None:
            return ""
        if isinstance(value, str):
            try:
                value = datetime.fromisoformat(value)
            except ValueError:
                return value

        now = datetime.now()
        delta = now - value

        seconds = delta.total_seconds()
        if seconds < 60:
            return "just now"
        elif seconds < 3600:
            minutes = int(seconds / 60)
            return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
        elif seconds < 86400:
            hours = int(seconds / 3600)
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        elif seconds < 604800:
            days = int(seconds / 86400)
            return f"{days} day{'s' if days != 1 else ''} ago"
        else:
            return value.strftime("%Y-%m-%d")

    @app.template_filter("status_color")
    def get_status_color(status: TicketStatus) -> str:
        """Get Bootstrap color class for status."""
        if isinstance(status, str):
            try:
                status = TicketStatus.from_string(status)
            except ValueError:
                return "secondary"

        color_map = {
            TicketStatus.OPEN: "danger",
            TicketStatus.IN_PROGRESS: "warning",
            TicketStatus.UNDER_REVIEW: "info",
            TicketStatus.AWAITING_APPROVAL: "primary",
            TicketStatus.RESOLVED: "success",
            TicketStatus.CLOSED: "secondary",
            TicketStatus.BLOCKED: "dark",
        }
        return color_map.get(status, "secondary")

    @app.template_filter("priority_color")
    def get_priority_color(priority: TicketPriority) -> str:
        """Get Bootstrap color class for priority."""
        if isinstance(priority, str):
            try:
                priority = TicketPriority.from_string(priority)
            except ValueError:
                return "secondary"

        color_map = {
            TicketPriority.CRITICAL: "danger",
            TicketPriority.HIGH: "warning",
            TicketPriority.MEDIUM: "info",
            TicketPriority.LOW: "success",
        }
        return color_map.get(priority, "secondary")

    @app.template_filter("type_icon")
    def get_type_icon(ticket_type: TicketType) -> str:
        """Get icon class for ticket type."""
        if isinstance(ticket_type, str):
            try:
                ticket_type = TicketType.from_string(ticket_type)
            except ValueError:
                return "bi-file-text"

        icon_map = {
            TicketType.BUG: "bi-bug",
            TicketType.FEATURE: "bi-stars",
            TicketType.ENHANCEMENT: "bi-lightbulb",
            TicketType.TASK: "bi-list-task",
            TicketType.DOCUMENTATION: "bi-book",
            TicketType.MAINTENANCE: "bi-wrench",
            TicketType.SECURITY: "bi-shield-lock",
            TicketType.PERFORMANCE: "bi-speedometer2",
        }
        return icon_map.get(ticket_type, "bi-file-text")


def register_routes(app: Flask) -> None:
    """Register all routes for the application."""

    def get_store() -> TicketStore:
        """Get the ticket store from app config."""
        return app.config["TICKET_STORE"]

    # =========================================================================
    # HTML ROUTES
    # =========================================================================

    @app.route("/")
    def dashboard() -> str:
        """Dashboard home page with ticket overview."""
        store = get_store()

        # Get statistics
        total = store.count()
        open_count = store.count(status=TicketStatus.OPEN)
        in_progress = store.count(status=TicketStatus.IN_PROGRESS)
        under_review = store.count(status=TicketStatus.UNDER_REVIEW)
        awaiting = store.count(status=TicketStatus.AWAITING_APPROVAL)
        resolved = store.count(status=TicketStatus.RESOLVED)
        closed = store.count(status=TicketStatus.CLOSED)

        # Priority counts
        critical = store.count(priority=TicketPriority.CRITICAL)
        high = store.count(priority=TicketPriority.HIGH)
        medium = store.count(priority=TicketPriority.MEDIUM)
        low = store.count(priority=TicketPriority.LOW)

        # Get recent tickets
        recent_tickets = store.list(limit=10)

        # Get active agents
        agents = store.list_agents(active_only=True)

        stats = {
            "total": total,
            "open": open_count,
            "in_progress": in_progress,
            "under_review": under_review,
            "awaiting_approval": awaiting,
            "resolved": resolved,
            "closed": closed,
            "critical": critical,
            "high": high,
            "medium": medium,
            "low": low,
        }

        return render_template(
            "dashboard.html",
            stats=stats,
            recent_tickets=recent_tickets,
            agents=agents,
        )

    @app.route("/tickets")
    def ticket_list() -> str:
        """Ticket list page with filtering."""
        store = get_store()

        # Get filter parameters
        status_filter = request.args.get("status")
        priority_filter = request.args.get("priority")
        type_filter = request.args.get("type")
        assignee_filter = request.args.get("assignee")
        search_query = request.args.get("q")
        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 20, type=int)

        # Build filter kwargs
        filter_kwargs: dict[str, Any] = {
            "limit": per_page,
            "offset": (page - 1) * per_page,
        }

        if status_filter:
            try:
                filter_kwargs["status"] = TicketStatus.from_string(status_filter)
            except ValueError:
                pass

        if priority_filter:
            try:
                filter_kwargs["priority"] = TicketPriority.from_string(priority_filter)
            except ValueError:
                pass

        if type_filter:
            try:
                filter_kwargs["ticket_type"] = TicketType.from_string(type_filter)
            except ValueError:
                pass

        if assignee_filter:
            filter_kwargs["assigned_to"] = assignee_filter

        # Get tickets
        if search_query:
            tickets = store.search(search_query)
            # Apply pagination manually for search
            tickets = tickets[filter_kwargs["offset"] : filter_kwargs["offset"] + per_page]
            total = len(store.search(search_query))
        else:
            tickets = store.list(**filter_kwargs)
            # Get total count for pagination
            total = store.count(
                status=filter_kwargs.get("status"),
                priority=filter_kwargs.get("priority"),
            )

        # Calculate pagination
        total_pages = (total + per_page - 1) // per_page

        # Get filter options
        statuses = list(TicketStatus)
        priorities = list(TicketPriority)
        types = list(TicketType)
        agents = store.list_agents(active_only=False)

        return render_template(
            "ticket_list.html",
            tickets=tickets,
            page=page,
            per_page=per_page,
            total=total,
            total_pages=total_pages,
            statuses=statuses,
            priorities=priorities,
            types=types,
            agents=agents,
            current_status=status_filter,
            current_priority=priority_filter,
            current_type=type_filter,
            current_assignee=assignee_filter,
            search_query=search_query or "",
        )

    @app.route("/tickets/<ticket_id>")
    def ticket_detail(ticket_id: str) -> str:
        """Ticket detail page."""
        store = get_store()
        ticket = store.get(ticket_id)

        if ticket is None:
            return render_template(
                "ticket_detail.html",
                ticket=None,
                error=f"Ticket #{ticket_id} not found",
            ), 404

        # Get related tickets
        related = []
        for related_id in ticket.related_tickets:
            related_ticket = store.get(related_id)
            if related_ticket:
                related.append(related_ticket)

        return render_template(
            "ticket_detail.html",
            ticket=ticket,
            related_tickets=related,
        )

    # =========================================================================
    # JSON API ROUTES
    # =========================================================================

    @app.route("/api/tickets")
    def api_tickets() -> Response:
        """JSON API for listing tickets."""
        store = get_store()

        # Get filter parameters
        status_filter = request.args.get("status")
        priority_filter = request.args.get("priority")
        type_filter = request.args.get("type")
        assignee_filter = request.args.get("assignee")
        search_query = request.args.get("q")
        limit = request.args.get("limit", 100, type=int)
        offset = request.args.get("offset", 0, type=int)

        # Build filter kwargs
        filter_kwargs: dict[str, Any] = {
            "limit": limit,
            "offset": offset,
        }

        if status_filter:
            try:
                filter_kwargs["status"] = TicketStatus.from_string(status_filter)
            except ValueError:
                return jsonify({"error": f"Invalid status: {status_filter}"}), 400

        if priority_filter:
            try:
                filter_kwargs["priority"] = TicketPriority.from_string(priority_filter)
            except ValueError:
                return jsonify({"error": f"Invalid priority: {priority_filter}"}), 400

        if type_filter:
            try:
                filter_kwargs["ticket_type"] = TicketType.from_string(type_filter)
            except ValueError:
                return jsonify({"error": f"Invalid type: {type_filter}"}), 400

        if assignee_filter:
            filter_kwargs["assigned_to"] = assignee_filter

        # Get tickets
        if search_query:
            tickets = store.search(search_query)
            tickets = tickets[offset : offset + limit]
            total = len(store.search(search_query))
        else:
            tickets = store.list(**filter_kwargs)
            total = store.count(
                status=filter_kwargs.get("status"),
                priority=filter_kwargs.get("priority"),
            )

        return jsonify(
            {
                "tickets": [t.to_dict() for t in tickets],
                "total": total,
                "limit": limit,
                "offset": offset,
            }
        )

    @app.route("/api/tickets/<ticket_id>")
    def api_ticket_detail(ticket_id: str) -> Response:
        """JSON API for single ticket."""
        store = get_store()
        ticket = store.get(ticket_id)

        if ticket is None:
            return jsonify({"error": f"Ticket #{ticket_id} not found"}), 404

        return jsonify(
            {
                "ticket": ticket.to_dict(),
            }
        )

    @app.route("/api/agents")
    def api_agents() -> Response:
        """JSON API for listing agents."""
        store = get_store()
        active_only = request.args.get("active_only", "true").lower() == "true"

        agents = store.list_agents(active_only=active_only)

        return jsonify(
            {
                "agents": [a.to_dict() for a in agents],
                "total": len(agents),
            }
        )

    @app.route("/api/stats")
    def api_stats() -> Response:
        """JSON API for dashboard statistics."""
        store = get_store()

        stats = {
            "total": store.count(),
            "by_status": {
                "open": store.count(status=TicketStatus.OPEN),
                "in_progress": store.count(status=TicketStatus.IN_PROGRESS),
                "under_review": store.count(status=TicketStatus.UNDER_REVIEW),
                "awaiting_approval": store.count(status=TicketStatus.AWAITING_APPROVAL),
                "resolved": store.count(status=TicketStatus.RESOLVED),
                "closed": store.count(status=TicketStatus.CLOSED),
                "blocked": store.count(status=TicketStatus.BLOCKED),
            },
            "by_priority": {
                "critical": store.count(priority=TicketPriority.CRITICAL),
                "high": store.count(priority=TicketPriority.HIGH),
                "medium": store.count(priority=TicketPriority.MEDIUM),
                "low": store.count(priority=TicketPriority.LOW),
            },
            "agents": {
                "total": len(store.list_agents(active_only=False)),
                "active": len(store.list_agents(active_only=True)),
            },
        }

        return jsonify(stats)

    @app.route("/api/health")
    def api_health() -> Response:
        """Health check endpoint."""
        return jsonify(
            {
                "status": "healthy",
                "timestamp": datetime.now().isoformat(),
            }
        )

    # =========================================================================
    # ERROR HANDLERS
    # =========================================================================

    @app.errorhandler(404)
    def not_found(error: Exception) -> tuple:
        """Handle 404 errors."""
        if request.path.startswith("/api/"):
            return jsonify({"error": "Not found"}), 404
        return render_template("base.html", error="Page not found"), 404

    @app.errorhandler(500)
    def internal_error(error: Exception) -> tuple:
        """Handle 500 errors."""
        if request.path.startswith("/api/"):
            return jsonify({"error": "Internal server error"}), 500
        return render_template("base.html", error="Internal server error"), 500


def serve(
    store: TicketStore | None = None,
    host: str = "127.0.0.1",
    port: int = 5000,
    debug: bool = False,
    **kwargs: Any,
) -> None:
    """
    Start the web dashboard server.

    Args:
        store: TicketStore instance to use.
        host: Host address to bind to.
        port: Port number to listen on.
        debug: Enable debug mode.
        **kwargs: Additional arguments passed to Flask.run().
    """
    app = create_app(store)
    app.run(host=host, port=port, debug=debug, **kwargs)


if __name__ == "__main__":
    # Quick development server
    serve(debug=True)

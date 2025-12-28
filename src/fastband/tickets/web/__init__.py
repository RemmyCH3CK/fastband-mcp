"""
Fastband Tickets Web Dashboard.

Provides a Flask-based web interface for the ticket management system:
- Dashboard with ticket overview and statistics
- Ticket list with filtering and search
- Ticket detail views
- Agent status panel
- JSON API for integration

Usage:
    from fastband.tickets.web import create_app, serve

    # Create the Flask app
    app = create_app(store)

    # Or use the serve function for quick startup
    serve(store, host="0.0.0.0", port=5000)
"""

from fastband.tickets.web.app import create_app, serve

__all__ = [
    "create_app",
    "serve",
]

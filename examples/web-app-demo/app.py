"""
Web App Demo - Simple Flask application.

This demonstrates how to structure a web app that uses Fastband MCP
for AI-assisted development.
"""

from flask import Flask, render_template, jsonify
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key")


# =============================================================================
# Routes
# =============================================================================


@app.route("/")
def index():
    """Home page."""
    return render_template("index.html", title="Home")


@app.route("/about")
def about():
    """About page."""
    return render_template("about.html", title="About")


@app.route("/api/status")
def api_status():
    """API endpoint - shows app status."""
    return jsonify({
        "status": "running",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0",
    })


# =============================================================================
# Error Handlers
# =============================================================================


@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors."""
    return render_template("error.html",
                          title="Not Found",
                          message="The page you're looking for doesn't exist."), 404


@app.errorhandler(500)
def server_error(error):
    """Handle 500 errors."""
    return render_template("error.html",
                          title="Server Error",
                          message="Something went wrong on our end."), 500


# =============================================================================
# Main
# =============================================================================


if __name__ == "__main__":
    # Development server
    app.run(
        host="0.0.0.0",
        port=5001,
        debug=True,
    )

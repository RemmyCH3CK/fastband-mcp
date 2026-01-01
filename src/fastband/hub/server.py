"""
Fastband Hub Server - Unified launcher with embedded React dashboard.

Provides a single entry point for running:
- FastAPI REST API (Control Plane, sessions, etc.)
- WebSocket real-time updates
- React dashboard (static files)
- Plugin routes

Usage:
    from fastband.hub.server import run_server
    await run_server(host="0.0.0.0", port=8080)

Or via CLI:
    fastband serve --hub
"""

import asyncio
import logging
import os
import socket
from pathlib import Path

from fastband.core.events import HubEventType, get_event_bus
from fastband.core.plugins import get_plugin_manager

logger = logging.getLogger(__name__)

# Path to static files (built React dashboard)
STATIC_DIR = Path(__file__).parent / "static"
WEB_DIR = Path(__file__).parent / "web"

# Port range for auto-selection
DEFAULT_PORT = 8080
MAX_PORT = 8099


def is_port_available(host: str, port: int) -> bool:
    """
    Check if a port is available for binding.

    Args:
        host: Host to check
        port: Port to check

    Returns:
        True if port is available
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((host if host != "0.0.0.0" else "127.0.0.1", port))
            return True
    except OSError:
        return False


def find_available_port(host: str, preferred_port: int = DEFAULT_PORT) -> int | None:
    """
    Find an available port, starting from preferred_port.

    Tries ports from preferred_port up to MAX_PORT.

    Args:
        host: Host to bind to
        preferred_port: Preferred starting port

    Returns:
        Available port number, or None if no port found
    """
    for port in range(preferred_port, MAX_PORT + 1):
        if is_port_available(host, port):
            return port
    return None


def get_static_directory() -> Path | None:
    """
    Get the static files directory for the React dashboard.

    Checks multiple locations:
    1. Packaged static files (hub/static/)
    2. Development build output (hub/web/dist/)

    Returns:
        Path to static directory or None if not found
    """
    # Check packaged location first
    if STATIC_DIR.exists() and (STATIC_DIR / "index.html").exists():
        return STATIC_DIR

    # Check development location
    dev_dist = WEB_DIR / "dist"
    if dev_dist.exists() and (dev_dist / "index.html").exists():
        return dev_dist

    return None


def mount_dashboard(app) -> bool:
    """
    Mount the React dashboard as static files on the FastAPI app.

    Args:
        app: FastAPI application instance

    Returns:
        True if dashboard was mounted successfully
    """
    from fastapi.responses import FileResponse
    from fastapi.staticfiles import StaticFiles

    static_dir = get_static_directory()

    if static_dir is None:
        logger.warning(
            "Dashboard static files not found. "
            "Run 'fastband build-dashboard' or 'npm run build' in hub/web/"
        )
        return False

    logger.info(f"Mounting dashboard from: {static_dir}")

    # Mount assets directory for JS/CSS bundles
    assets_dir = static_dir / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    # Mount other static files (favicon, etc.)
    def create_static_handler(file_path: Path):
        """Create handler with captured file path (avoids closure bug)."""

        async def handler():
            return FileResponse(file_path)

        return handler

    for file_name in ["favicon.ico", "favicon.svg", "manifest.json"]:
        file_path = static_dir / file_name
        if file_path.exists():
            app.add_api_route(f"/{file_name}", create_static_handler(file_path), methods=["GET"])

    # Catch-all route for SPA - MUST be after API routes
    index_path = static_dir / "index.html"

    @app.get("/", include_in_schema=False)
    async def serve_index():
        """Serve the React app index."""
        return FileResponse(index_path)

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        """
        Catch-all for SPA routing with path traversal protection.

        Returns index.html for all non-API, non-asset routes.
        This enables React Router to handle client-side routing.
        """
        # Don't serve index for API routes (they should 404 properly)
        if full_path.startswith("api/"):
            from fastapi.responses import JSONResponse

            return JSONResponse(status_code=404, content={"error": "Not found", "path": full_path})

        # SECURITY: Validate path BEFORE resolution to prevent path traversal
        # Check for dangerous patterns in the raw path first
        if ".." in full_path or full_path.startswith("/") or "\x00" in full_path:
            # Path traversal attempt - serve index.html
            return FileResponse(index_path)

        # Check for URL-encoded traversal attempts
        if "%2e" in full_path.lower() or "%2f" in full_path.lower() or "%00" in full_path.lower():
            return FileResponse(index_path)

        try:
            # Now safe to construct and resolve the path
            static_dir_resolved = static_dir.resolve()
            requested_path = (static_dir / full_path).resolve()

            # Ensure resolved path is within static_dir (defense in depth)
            requested_path.relative_to(static_dir_resolved)

            # Check symlinks BEFORE serving - reject if path or any parent is a symlink
            # This prevents symlink-based escapes
            original_path = static_dir / full_path
            if original_path.exists():
                # Check if the file itself is a symlink
                if original_path.is_symlink():
                    return FileResponse(index_path)
                # Check parents for symlinks (up to static_dir)
                current = original_path
                while current != static_dir and current.parent != current:
                    if current.is_symlink():
                        return FileResponse(index_path)
                    current = current.parent

            # Serve file if it exists and passed all security checks
            if requested_path.is_file():
                return FileResponse(requested_path)

        except (ValueError, OSError):
            # Path traversal attempt or invalid path - serve index
            pass

        # Otherwise, serve index.html for SPA routing
        return FileResponse(index_path)

    logger.info("Dashboard mounted successfully")
    return True


def create_server_app(
    with_dashboard: bool = True,
    cors_origins: list[str] | None = None,
):
    """
    Create a complete Fastband server application.

    Combines:
    - FastAPI REST API (from hub/api/app.py)
    - Static file serving for React dashboard
    - Plugin routes

    Args:
        with_dashboard: Whether to mount the React dashboard
        cors_origins: Allowed CORS origins

    Returns:
        Configured FastAPI application
    """
    from fastband.hub.api.app import create_app

    # Create base app with all API routes
    app = create_app(cors_origins=cors_origins)

    # Mount plugin routes
    plugin_manager = get_plugin_manager()
    for plugin_name, router in plugin_manager.get_all_routers():
        app.include_router(
            router,
            prefix=f"/api/plugins/{plugin_name}",
            tags=[f"plugin:{plugin_name}"],
        )

    # Mount dashboard LAST (catch-all routes)
    if with_dashboard:
        mount_dashboard(app)

    return app


async def run_server(
    host: str = "127.0.0.1",  # SECURITY: Default to localhost only
    port: int = 8080,
    with_dashboard: bool = True,
    reload: bool = False,
    log_level: str = "info",
    auto_port: bool = True,
) -> int:
    """
    Run the Fastband Hub server.

    Starts:
    - FastAPI REST API
    - WebSocket server
    - React dashboard (if with_dashboard=True)
    - Event bus
    - Plugin manager

    Args:
        host: Host to bind to
        port: Port to listen on (preferred port if auto_port=True)
        with_dashboard: Whether to serve the React dashboard
        reload: Enable auto-reload (development only)
        log_level: Logging level
        auto_port: If True, automatically find available port if preferred is busy

    Returns:
        The actual port the server is running on
    """
    import uvicorn

    # Auto-port selection
    actual_port = port
    if auto_port:
        if not is_port_available(host, port):
            available = find_available_port(host, port + 1)
            if available:
                logger.info(f"Port {port} is busy, using port {available}")
                actual_port = available
            else:
                raise RuntimeError(
                    f"No available ports found in range {port}-{MAX_PORT}. "
                    "Close some applications or specify a different port with --hub-port."
                )

    # SECURITY: Warn if binding to all interfaces
    if host == "0.0.0.0":
        logger.warning(
            "Server binding to 0.0.0.0 - accessible from network! "
            "Consider using --host 127.0.0.1 for local-only access."
        )

    # Initialize event bus
    event_bus = get_event_bus()
    await event_bus.start()

    # Discover and load plugins
    plugin_manager = get_plugin_manager()
    plugins = plugin_manager.discover()
    logger.info(f"Discovered {len(plugins)} plugins")

    # Load all enabled plugins
    loaded = await plugin_manager.load_all()
    logger.info(f"Loaded {loaded} plugins")

    # Create the app
    app = create_server_app(with_dashboard=with_dashboard)

    # Emit hub started event
    await event_bus.emit(
        HubEventType.HUB_STARTED,  # type: ignore
        {
            "host": host,
            "port": actual_port,
            "with_dashboard": with_dashboard,
            "plugins_loaded": loaded,
        },
        source="hub_server",
    )

    logger.info(f"Starting Fastband Hub on http://{host}:{actual_port}")
    if with_dashboard:
        static_dir = get_static_directory()
        if static_dir:
            logger.info(f"Dashboard: http://{host}:{actual_port}/")
        else:
            logger.warning("Dashboard not available (static files not built)")

    # Configure safe logging for Python 3.14+ compatibility
    # This replaces StreamHandlers with SafeStreamHandlers that catch I/O errors
    from fastband.core.logging import configure_safe_logging, get_uvicorn_log_config

    configure_safe_logging()

    config = uvicorn.Config(
        app,
        host=host,
        port=actual_port,
        log_level=log_level,
        reload=reload,
        log_config=get_uvicorn_log_config(),
    )

    server = uvicorn.Server(config)

    try:
        await server.serve()
    finally:
        # Emit hub stopped event
        await event_bus.emit(
            HubEventType.HUB_STOPPED,  # type: ignore
            {"host": host, "port": actual_port},
            source="hub_server",
        )

        # Unload plugins
        await plugin_manager.unload_all()

        # Stop event bus
        await event_bus.stop()

        logger.info("Fastband Hub stopped")

    return actual_port


def main():
    """CLI entry point for standalone server."""
    host = os.getenv("FASTBAND_HOST", "0.0.0.0")
    port = int(os.getenv("FASTBAND_PORT", "8080"))
    no_dashboard = os.getenv("FASTBAND_NO_DASHBOARD", "").lower() in ("1", "true")

    asyncio.run(
        run_server(
            host=host,
            port=port,
            with_dashboard=not no_dashboard,
        )
    )


if __name__ == "__main__":
    main()

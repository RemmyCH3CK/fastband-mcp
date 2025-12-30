"""
Fastband AI Hub - FastAPI Application.

Main FastAPI application with middleware, error handling,
and lifecycle management.
"""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from fastband import __version__
from fastband.hub.api.routes import router
from fastband.hub.chat import ChatManager
from fastband.hub.control_plane.routes import router as control_plane_router
from fastband.hub.control_plane.service import get_control_plane_service
from fastband.hub.session import get_session_manager
from fastband.hub.websockets.manager import get_websocket_manager

logger = logging.getLogger(__name__)

# Dev mode - skip memory/embeddings when no API keys
DEV_MODE = os.environ.get("FASTBAND_DEV_MODE", "").lower() in ("1", "true", "yes")

# Global app instance
_app: FastAPI | None = None
_chat_manager: ChatManager | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global _chat_manager

    logger.info("Starting Fastband AI Hub...")

    if DEV_MODE:
        logger.info("🔧 Dev Mode: Skipping memory/embeddings initialization")

    # Initialize memory (skip in dev mode or if no API key)
    memory = None
    if not DEV_MODE:
        try:
            from fastband.hub.memory import MemoryConfig, SemanticMemory

            memory_config = MemoryConfig()
            memory = SemanticMemory(memory_config)
            await memory.initialize()
        except Exception as e:
            logger.warning(f"Could not initialize memory: {e}")
            memory = None

    # Initialize AI provider
    provider = None
    try:
        from fastband.providers import get_provider

        provider = get_provider("claude")
    except Exception as e:
        logger.warning(f"Could not load Claude provider: {e}")
        provider = None

    # Initialize chat manager
    if provider:
        _chat_manager = ChatManager(
            ai_provider=provider,
            session_manager=get_session_manager(),
            memory_store=memory,
        )
        await _chat_manager.initialize()
    elif DEV_MODE:
        logger.info("🔧 Dev Mode: Chat manager not initialized (no provider)")

    # Store in app state
    app.state.chat_manager = _chat_manager
    app.state.memory = memory
    app.state.session_manager = get_session_manager()

    # Initialize Control Plane service
    control_plane_service = get_control_plane_service()
    await control_plane_service.start()
    app.state.control_plane_service = control_plane_service
    app.state.ws_manager = get_websocket_manager()

    logger.info("Fastband Agent Control Plane started")

    yield

    # Shutdown
    logger.info("Shutting down Fastband Agent Control Plane...")

    # Stop Control Plane service
    if control_plane_service:
        await control_plane_service.stop()

    if _chat_manager:
        await _chat_manager.shutdown()

    if memory:
        await memory.close()

    logger.info("Fastband Agent Control Plane stopped")


def create_app(
    title: str = "Fastband Agent Control Plane",
    description: str = "Multi-agent coordination and workflow management for AI development teams",
    cors_origins: list[str] | None = None,
) -> FastAPI:
    """Create the FastAPI application.

    Args:
        title: API title
        description: API description
        cors_origins: Allowed CORS origins

    Returns:
        Configured FastAPI application
    """
    global _app

    if _app is not None:
        return _app

    _app = FastAPI(
        title=title,
        description=description,
        version=__version__,
        lifespan=lifespan,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )

    # Add CORS middleware
    origins = cors_origins or [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ]

    _app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Add exception handlers
    @_app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError):
        return JSONResponse(
            status_code=400,
            content={"error": str(exc), "type": "validation_error"},
        )

    @_app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        logger.error(f"Unhandled exception: {exc}")
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error", "type": "server_error"},
        )

    # Include routes
    _app.include_router(router, prefix="/api")
    _app.include_router(control_plane_router, prefix="/api")

    return _app


def get_app() -> FastAPI:
    """Get the FastAPI application instance.

    Returns:
        FastAPI application
    """
    global _app

    if _app is None:
        _app = create_app()

    return _app


def get_chat_manager() -> ChatManager | None:
    """Get the chat manager instance.

    Returns:
        ChatManager or None if not initialized
    """
    return _chat_manager

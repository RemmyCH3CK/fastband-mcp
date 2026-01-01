"""
Fastband AI Hub - FastAPI Application.

Main FastAPI application with middleware, error handling,
and lifecycle management.

Security Features:
- Rate limiting (token bucket algorithm)
- Security headers (X-Frame-Options, CSP, etc.)
- Request size limits
- CORS with explicit origins
"""

import logging
import os
import secrets
import time
from collections import defaultdict
from contextlib import asynccontextmanager
from typing import Callable

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

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

# Security constants
MAX_REQUEST_SIZE = 10 * 1024 * 1024  # 10MB max request body
RATE_LIMIT_REQUESTS = 100  # requests per window
RATE_LIMIT_WINDOW = 60  # seconds


class RateLimiter:
    """Simple in-memory token bucket rate limiter.

    For production, consider Redis-backed rate limiting.
    """

    def __init__(self, requests_per_window: int = 100, window_seconds: int = 60):
        self.requests_per_window = requests_per_window
        self.window_seconds = window_seconds
        self._buckets: dict[str, list[float]] = defaultdict(list)

    def _get_client_id(self, request: Request) -> str:
        """Get client identifier from request."""
        # Use forwarded header if behind proxy, otherwise use client host
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    def is_allowed(self, request: Request) -> tuple[bool, dict[str, int]]:
        """Check if request is allowed under rate limit.

        Returns:
            Tuple of (is_allowed, headers_dict with rate limit info)
        """
        client_id = self._get_client_id(request)
        now = time.time()
        window_start = now - self.window_seconds

        # Clean old entries and count recent requests
        self._buckets[client_id] = [
            t for t in self._buckets[client_id] if t > window_start
        ]
        request_count = len(self._buckets[client_id])

        headers = {
            "X-RateLimit-Limit": self.requests_per_window,
            "X-RateLimit-Remaining": max(0, self.requests_per_window - request_count - 1),
            "X-RateLimit-Reset": int(window_start + self.window_seconds),
        }

        if request_count >= self.requests_per_window:
            return False, headers

        # Record this request
        self._buckets[client_id].append(now)
        return True, headers


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses."""

    async def dispatch(self, request: Request, call_next: Callable):
        response = await call_next(request)

        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"

        # Content Security Policy (relaxed for SPA)
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: blob:; "
            "font-src 'self' data:; "
            "connect-src 'self' ws: wss:; "
            "frame-ancestors 'none'"
        )

        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware."""

    def __init__(self, app, limiter: RateLimiter):
        super().__init__(app)
        self.limiter = limiter

    async def dispatch(self, request: Request, call_next: Callable):
        # Skip rate limiting for static assets and health checks
        if request.url.path.startswith(("/assets/", "/favicon", "/health")):
            return await call_next(request)

        allowed, headers = self.limiter.is_allowed(request)

        if not allowed:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"error": "Rate limit exceeded. Please try again later."},
                headers={k: str(v) for k, v in headers.items()},
            )

        response = await call_next(request)

        # Add rate limit headers to response
        for key, value in headers.items():
            response.headers[key] = str(value)

        return response


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """Limit request body size."""

    def __init__(self, app, max_size: int = MAX_REQUEST_SIZE):
        super().__init__(app)
        self.max_size = max_size

    async def dispatch(self, request: Request, call_next: Callable):
        content_length = request.headers.get("content-length")

        if content_length and int(content_length) > self.max_size:
            return JSONResponse(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                content={
                    "error": f"Request body too large. Maximum size is {self.max_size // (1024*1024)}MB."
                },
            )

        return await call_next(request)


class CSRFMiddleware(BaseHTTPMiddleware):
    """CSRF protection using double-submit cookie pattern.

    For state-changing requests (POST, PUT, DELETE, PATCH):
    - Checks for X-CSRF-Token header matching the csrf_token cookie
    - Skips CSRF for API endpoints with Bearer auth (machine-to-machine)
    - Skips CSRF for safe methods (GET, HEAD, OPTIONS)
    """

    # Endpoints that don't require CSRF (use Bearer auth instead)
    EXEMPT_PATHS = {
        "/api/health",
        "/api/docs",
        "/api/redoc",
        "/api/openapi.json",
    }

    async def dispatch(self, request: Request, call_next: Callable):
        # Safe methods don't need CSRF protection
        if request.method in ("GET", "HEAD", "OPTIONS"):
            response = await call_next(request)
            # Set CSRF cookie on GET requests if not present
            if "csrf_token" not in request.cookies:
                csrf_token = secrets.token_urlsafe(32)
                response.set_cookie(
                    key="csrf_token",
                    value=csrf_token,
                    httponly=False,  # JS needs to read this
                    samesite="strict",
                    secure=request.url.scheme == "https",
                    max_age=3600 * 24,  # 24 hours
                )
            return response

        # Skip CSRF for exempt paths
        if request.url.path in self.EXEMPT_PATHS:
            return await call_next(request)

        # Skip CSRF if Bearer auth is present (API/machine access)
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            return await call_next(request)

        # Validate CSRF token for state-changing requests
        cookie_token = request.cookies.get("csrf_token")
        header_token = request.headers.get("x-csrf-token")

        if not cookie_token or not header_token:
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"error": "CSRF token missing"},
            )

        if not secrets.compare_digest(cookie_token, header_token):
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"error": "CSRF token mismatch"},
            )

        return await call_next(request)


# Global rate limiter instance
_rate_limiter = RateLimiter(RATE_LIMIT_REQUESTS, RATE_LIMIT_WINDOW)

# Global app instance
_app: FastAPI | None = None
_chat_manager: ChatManager | None = None


def _load_env_file():
    """Load .env file from .fastband directory if it exists."""
    from pathlib import Path

    env_path = Path.cwd() / ".fastband" / ".env"
    if env_path.exists():
        try:
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        # Only set if not already in environment
                        if key not in os.environ:
                            os.environ[key] = value
                            logger.debug(f"Loaded {key} from .fastband/.env")
            logger.info(f"Loaded environment from {env_path}")
        except Exception as e:
            logger.warning(f"Failed to load .env file: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global _chat_manager

    # Load .env file from .fastband directory
    _load_env_file()

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
    # Include Hub ports (8080-8099 for auto-port selection), dev ports (3000, 5173)
    # When dashboard is served from same origin, browser won't enforce CORS anyway
    # but we include Hub ports for completeness and cross-origin API access
    origins = cors_origins or [
        # Hub server ports (auto-port range)
        "http://localhost:8080",
        "http://localhost:8081",
        "http://localhost:8082",
        "http://localhost:8083",
        "http://localhost:8084",
        "http://localhost:8085",
        "http://127.0.0.1:8080",
        "http://127.0.0.1:8081",
        "http://127.0.0.1:8082",
        "http://127.0.0.1:8083",
        "http://127.0.0.1:8084",
        "http://127.0.0.1:8085",
        # Dev server ports (Vite, CRA)
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

    # Add security middleware (order matters - first added = last executed)
    _app.add_middleware(SecurityHeadersMiddleware)
    _app.add_middleware(CSRFMiddleware)
    _app.add_middleware(RateLimitMiddleware, limiter=_rate_limiter)
    _app.add_middleware(RequestSizeLimitMiddleware)

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


async def reinitialize_chat_manager(app: FastAPI) -> bool:
    """Reinitialize the chat manager with current environment.

    Call this after API keys are set (e.g., after onboarding completes)
    to enable chat without requiring a server restart.

    Returns:
        True if chat manager was successfully initialized
    """
    global _chat_manager

    try:
        from fastband.providers import get_provider

        # Try to get a provider with the new keys
        provider = get_provider("claude")

        if provider:
            # Shutdown existing chat manager if any
            if _chat_manager:
                await _chat_manager.shutdown()

            # Create new chat manager
            _chat_manager = ChatManager(
                ai_provider=provider,
                session_manager=get_session_manager(),
                memory_store=getattr(app.state, "memory", None),
            )
            await _chat_manager.initialize()

            # Update app state
            app.state.chat_manager = _chat_manager

            logger.info("Chat manager reinitialized with new API keys")
            return True
    except Exception as e:
        logger.warning(f"Could not reinitialize chat manager: {e}")

    return False

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
import traceback
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Callable

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware

from fastband import __version__
from fastband.core.logging import (
    AuditEventType,
    AuditSeverity,
    audit_csrf_violation,
    audit_rate_limit,
    audit_security_event,
)
from fastband.hub.api.routes import router
from fastband.hub.chat import ChatManager
from fastband.hub.control_plane.routes import router as control_plane_router
from fastband.hub.control_plane.service import get_control_plane_service
from fastband.hub.session import get_session_manager
from fastband.hub.websockets.manager import get_websocket_manager

logger = logging.getLogger(__name__)

# Dev mode - skip memory/embeddings when no API keys
DEV_MODE = os.environ.get("FASTBAND_DEV_MODE", "").lower() in ("1", "true", "yes")


# =============================================================================
# STANDARDIZED ERROR RESPONSES (Enterprise)
# =============================================================================


class ErrorResponse(BaseModel):
    """Standardized error response format for all API errors.

    Enterprise-grade error responses include:
    - Consistent structure across all endpoints
    - Request correlation ID for tracing
    - Error categorization for client handling
    - Timestamp for debugging
    """

    error: str = Field(..., description="Human-readable error message")
    error_code: str = Field(..., description="Machine-readable error code")
    status_code: int = Field(..., description="HTTP status code")
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        description="ISO 8601 timestamp",
    )
    request_id: str | None = Field(None, description="Request correlation ID")
    details: dict | None = Field(None, description="Additional error details")


# Error codes for categorization
class ErrorCodes:
    """Standardized error codes for client handling."""

    # 4xx Client Errors
    VALIDATION_ERROR = "VALIDATION_ERROR"
    BAD_REQUEST = "BAD_REQUEST"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    NOT_FOUND = "NOT_FOUND"
    RATE_LIMITED = "RATE_LIMITED"
    CSRF_ERROR = "CSRF_ERROR"
    REQUEST_TOO_LARGE = "REQUEST_TOO_LARGE"

    # 5xx Server Errors
    INTERNAL_ERROR = "INTERNAL_ERROR"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    TIMEOUT = "TIMEOUT"


def create_error_response(
    status_code: int,
    error: str,
    error_code: str,
    request: Request | None = None,
    details: dict | None = None,
) -> JSONResponse:
    """Create a standardized error response.

    Args:
        status_code: HTTP status code
        error: Human-readable error message
        error_code: Machine-readable error code
        request: Optional request for correlation ID
        details: Optional additional error details

    Returns:
        JSONResponse with standardized error format
    """
    request_id = None
    if request:
        # Use existing request ID header or generate one
        request_id = request.headers.get("x-request-id")

    response = ErrorResponse(
        error=error,
        error_code=error_code,
        status_code=status_code,
        request_id=request_id,
        details=details,
    )

    return JSONResponse(
        status_code=status_code,
        content=response.model_dump(exclude_none=True),
    )

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

        # HSTS - enforce HTTPS (enterprise requirement)
        # Only add if request came over HTTPS to avoid breaking local dev
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"

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
        # Skip rate limiting for static assets and health checks (including K8s probes)
        skip_paths = ("/assets/", "/favicon", "/health", "/api/health", "/api/v1/health", "/api/version")
        if request.url.path.startswith(skip_paths):
            return await call_next(request)

        allowed, headers = self.limiter.is_allowed(request)

        if not allowed:
            # Audit log the rate limit violation
            client_ip = self._get_client_ip(request)
            request_id = request.headers.get("x-request-id")
            audit_rate_limit(
                ip_address=client_ip,
                path=request.url.path,
                limit=headers.get("X-RateLimit-Limit", 100),
                request_id=request_id,
            )

            response = create_error_response(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                error="Rate limit exceeded. Please try again later.",
                error_code=ErrorCodes.RATE_LIMITED,
                request=request,
                details={
                    "retry_after_seconds": headers.get("X-RateLimit-Reset", 60),
                    "limit": headers.get("X-RateLimit-Limit"),
                },
            )
            # Add rate limit headers
            for k, v in headers.items():
                response.headers[k] = str(v)
            return response

        response = await call_next(request)

        # Add rate limit headers to response
        for key, value in headers.items():
            response.headers[key] = str(value)

        return response

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP from request, handling proxies."""
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"


# =============================================================================
# API VERSIONING
# =============================================================================

# Current API version
API_VERSION = "v1"
API_VERSION_HEADER = "X-API-Version"
DEPRECATED_API_WARNING = (
    "This endpoint is deprecated. Please use /api/v1/ prefix instead. "
    "The /api/ prefix will be removed in a future release."
)


class APIVersionMiddleware(BaseHTTPMiddleware):
    """API versioning middleware.

    Adds API version headers to responses and deprecation warnings
    for legacy endpoints.
    """

    async def dispatch(self, request: Request, call_next: Callable):
        response = await call_next(request)

        # Add API version header to all API responses
        if request.url.path.startswith("/api"):
            response.headers[API_VERSION_HEADER] = API_VERSION

            # Add deprecation warning for legacy /api/ endpoints (not /api/v1/)
            if request.url.path.startswith("/api/") and not request.url.path.startswith(
                "/api/v1/"
            ):
                response.headers["Deprecation"] = "true"
                response.headers["Sunset"] = "2026-07-01T00:00:00Z"  # 6 months notice
                response.headers["Link"] = (
                    f'</api/v1{request.url.path[4:]}>; rel="successor-version"'
                )
                # Log deprecation usage (could use for migration tracking)
                logger.debug(
                    f"Deprecated API endpoint used: {request.url.path} -> /api/v1{request.url.path[4:]}"
                )

        return response


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """Limit request body size."""

    def __init__(self, app, max_size: int = MAX_REQUEST_SIZE):
        super().__init__(app)
        self.max_size = max_size

    async def dispatch(self, request: Request, call_next: Callable):
        content_length = request.headers.get("content-length")

        if content_length and int(content_length) > self.max_size:
            return create_error_response(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                error=f"Request body too large. Maximum size is {self.max_size // (1024*1024)}MB.",
                error_code=ErrorCodes.REQUEST_TOO_LARGE,
                request=request,
                details={
                    "max_size_bytes": self.max_size,
                    "received_size_bytes": int(content_length),
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
            # Audit log the CSRF violation
            client_ip = self._get_client_ip(request)
            request_id = request.headers.get("x-request-id")
            audit_csrf_violation(
                ip_address=client_ip,
                path=request.url.path,
                method=request.method,
                request_id=request_id,
            )

            return create_error_response(
                status_code=status.HTTP_403_FORBIDDEN,
                error="CSRF token missing. Include X-CSRF-Token header.",
                error_code=ErrorCodes.CSRF_ERROR,
                request=request,
                details={"has_cookie": bool(cookie_token), "has_header": bool(header_token)},
            )

        if not secrets.compare_digest(cookie_token, header_token):
            # Audit log the CSRF token mismatch
            client_ip = self._get_client_ip(request)
            request_id = request.headers.get("x-request-id")
            audit_csrf_violation(
                ip_address=client_ip,
                path=request.url.path,
                method=request.method,
                request_id=request_id,
            )

            return create_error_response(
                status_code=status.HTTP_403_FORBIDDEN,
                error="CSRF token mismatch. Token may have expired.",
                error_code=ErrorCodes.CSRF_ERROR,
                request=request,
            )

        return await call_next(request)

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP from request, handling proxies."""
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"


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
    _app.add_middleware(APIVersionMiddleware)

    # Add exception handlers with standardized error responses

    @_app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        """Handle HTTP exceptions with standardized format."""
        # Map status codes to error codes
        error_code_map = {
            400: ErrorCodes.BAD_REQUEST,
            401: ErrorCodes.UNAUTHORIZED,
            403: ErrorCodes.FORBIDDEN,
            404: ErrorCodes.NOT_FOUND,
            429: ErrorCodes.RATE_LIMITED,
        }
        error_code = error_code_map.get(exc.status_code, ErrorCodes.INTERNAL_ERROR)

        return create_error_response(
            status_code=exc.status_code,
            error=str(exc.detail),
            error_code=error_code,
            request=request,
        )

    @_app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """Handle Pydantic validation errors with detailed feedback."""
        errors = []
        for error in exc.errors():
            loc = " -> ".join(str(x) for x in error.get("loc", []))
            msg = error.get("msg", "Validation error")
            errors.append({"field": loc, "message": msg})

        return create_error_response(
            status_code=422,
            error="Request validation failed",
            error_code=ErrorCodes.VALIDATION_ERROR,
            request=request,
            details={"validation_errors": errors},
        )

    @_app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError):
        """Handle ValueError with standardized format."""
        return create_error_response(
            status_code=400,
            error=str(exc),
            error_code=ErrorCodes.BAD_REQUEST,
            request=request,
        )

    @_app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """Handle unexpected exceptions securely."""
        # Log full error with traceback for debugging
        logger.error(f"Unhandled exception on {request.url.path}: {exc}")
        logger.debug(traceback.format_exc())

        # Return generic error to client (don't leak internals)
        return create_error_response(
            status_code=500,
            error="Internal server error",
            error_code=ErrorCodes.INTERNAL_ERROR,
            request=request,
        )

    # ==========================================================================
    # API VERSIONED ROUTES
    # ==========================================================================

    # Add version info endpoint at /api/version (always available)
    @_app.get("/api/version", tags=["API Info"])
    async def get_api_version():
        """Get API version information.

        Returns current API version and deprecation status of legacy endpoints.
        """
        return {
            "version": API_VERSION,
            "current_prefix": f"/api/{API_VERSION}",
            "legacy_prefix": "/api",
            "legacy_sunset_date": "2026-07-01",
            "documentation": f"/api/{API_VERSION}/docs",
        }

    # Primary versioned routes (/api/v1/*)
    _app.include_router(router, prefix=f"/api/{API_VERSION}")
    _app.include_router(control_plane_router, prefix=f"/api/{API_VERSION}")

    # Legacy routes (/api/*) - deprecated but still functional
    # These will have Deprecation headers added by APIVersionMiddleware
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

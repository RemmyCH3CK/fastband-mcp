"""
Fastband AI Hub - JWT Authentication.

Standalone JWT authentication for enterprise/self-hosted deployments.
Can work independently or alongside Supabase auth.

Features:
- HS256/RS256 algorithm support
- Token refresh workflow
- FastAPI dependency injection
- Route-level authorization
- Configurable token lifetimes
"""

import logging
import os
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from functools import wraps
from typing import Any, Callable

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

logger = logging.getLogger(__name__)


# =============================================================================
# JWT CONFIGURATION
# =============================================================================


class JWTAlgorithm(str, Enum):
    """Supported JWT algorithms."""

    HS256 = "HS256"  # HMAC with SHA-256 (symmetric)
    RS256 = "RS256"  # RSA with SHA-256 (asymmetric)


@dataclass(slots=True)
class JWTConfig:
    """JWT configuration.

    Attributes:
        secret_key: Secret key for HS256 or private key for RS256
        public_key: Public key for RS256 (optional for HS256)
        algorithm: JWT algorithm to use
        access_token_expire_minutes: Access token lifetime
        refresh_token_expire_days: Refresh token lifetime
        issuer: Token issuer claim
        audience: Token audience claim
        require_exp: Require expiration claim
        leeway_seconds: Clock skew tolerance
    """

    secret_key: str = field(default_factory=lambda: os.getenv("JWT_SECRET_KEY", ""))
    public_key: str = ""
    algorithm: JWTAlgorithm = JWTAlgorithm.HS256
    access_token_expire_minutes: int = 60  # 1 hour
    refresh_token_expire_days: int = 7
    issuer: str = "fastband"
    audience: str = "fastband-hub"
    require_exp: bool = True
    leeway_seconds: int = 30  # 30 second clock skew tolerance

    @classmethod
    def from_env(cls) -> "JWTConfig":
        """Load configuration from environment variables."""
        return cls(
            secret_key=os.getenv("JWT_SECRET_KEY", ""),
            public_key=os.getenv("JWT_PUBLIC_KEY", ""),
            algorithm=JWTAlgorithm(os.getenv("JWT_ALGORITHM", "HS256")),
            access_token_expire_minutes=int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "60")),
            refresh_token_expire_days=int(os.getenv("JWT_REFRESH_TOKEN_EXPIRE_DAYS", "7")),
            issuer=os.getenv("JWT_ISSUER", "fastband"),
            audience=os.getenv("JWT_AUDIENCE", "fastband-hub"),
        )

    def validate(self) -> bool:
        """Validate configuration."""
        if not self.secret_key:
            logger.warning("JWT_SECRET_KEY not configured")
            return False
        if self.algorithm == JWTAlgorithm.RS256 and not self.public_key:
            logger.warning("RS256 requires JWT_PUBLIC_KEY")
            return False
        return True


# =============================================================================
# TOKEN MODELS
# =============================================================================


class TokenType(str, Enum):
    """Token types."""

    ACCESS = "access"
    REFRESH = "refresh"


@dataclass(slots=True)
class TokenPayload:
    """JWT token payload.

    Attributes:
        sub: Subject (user ID)
        email: User email
        roles: User roles
        permissions: User permissions
        type: Token type (access/refresh)
        iat: Issued at timestamp
        exp: Expiration timestamp
        jti: JWT ID (unique token identifier)
        metadata: Additional claims
    """

    sub: str
    email: str
    roles: list[str] = field(default_factory=list)
    permissions: list[str] = field(default_factory=list)
    type: TokenType = TokenType.ACCESS
    iat: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    exp: datetime | None = None
    jti: str = field(default_factory=lambda: secrets.token_urlsafe(16))
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to JWT claims dict."""
        claims = {
            "sub": self.sub,
            "email": self.email,
            "roles": self.roles,
            "permissions": self.permissions,
            "type": self.type.value,
            "iat": int(self.iat.timestamp()),
            "jti": self.jti,
        }
        if self.exp:
            claims["exp"] = int(self.exp.timestamp())
        if self.metadata:
            claims["metadata"] = self.metadata
        return claims

    @classmethod
    def from_dict(cls, claims: dict[str, Any]) -> "TokenPayload":
        """Create from JWT claims dict."""
        return cls(
            sub=claims.get("sub", ""),
            email=claims.get("email", ""),
            roles=claims.get("roles", []),
            permissions=claims.get("permissions", []),
            type=TokenType(claims.get("type", "access")),
            iat=datetime.fromtimestamp(claims.get("iat", 0), tz=timezone.utc),
            exp=datetime.fromtimestamp(claims["exp"], tz=timezone.utc) if "exp" in claims else None,
            jti=claims.get("jti", ""),
            metadata=claims.get("metadata", {}),
        )


@dataclass(slots=True)
class TokenPair:
    """Access and refresh token pair."""

    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int = 3600  # seconds until access token expires
    refresh_expires_in: int = 604800  # seconds until refresh token expires


# =============================================================================
# JWT SERVICE
# =============================================================================


class JWTService:
    """JWT token creation and validation service.

    Example:
        config = JWTConfig.from_env()
        jwt_service = JWTService(config)

        # Create tokens
        tokens = jwt_service.create_token_pair(user_id="123", email="user@example.com")

        # Validate token
        payload = jwt_service.verify_token(tokens.access_token)
    """

    def __init__(self, config: JWTConfig | None = None):
        """Initialize JWT service.

        Args:
            config: JWT configuration (defaults to env-based config)
        """
        self.config = config or JWTConfig.from_env()
        self._jwt = None
        self._initialized = False

    def initialize(self) -> bool:
        """Initialize PyJWT.

        Returns:
            True if initialization successful
        """
        if self._initialized:
            return True

        if not self.config.validate():
            return False

        try:
            import jwt

            self._jwt = jwt
            self._initialized = True
            logger.info("JWT service initialized")
            return True

        except ImportError:
            logger.error("PyJWT not installed. Run: pip install PyJWT")
            return False

    def create_access_token(
        self,
        user_id: str,
        email: str,
        roles: list[str] | None = None,
        permissions: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Create an access token.

        Args:
            user_id: User identifier
            email: User email
            roles: User roles
            permissions: User permissions
            metadata: Additional claims

        Returns:
            Encoded JWT access token

        Raises:
            RuntimeError: If service not initialized
        """
        if not self._initialized:
            raise RuntimeError("JWT service not initialized")

        now = datetime.now(timezone.utc)
        exp = now + timedelta(minutes=self.config.access_token_expire_minutes)

        payload = TokenPayload(
            sub=user_id,
            email=email,
            roles=roles or [],
            permissions=permissions or [],
            type=TokenType.ACCESS,
            iat=now,
            exp=exp,
            metadata=metadata or {},
        )

        claims = payload.to_dict()
        claims["iss"] = self.config.issuer
        claims["aud"] = self.config.audience

        return self._jwt.encode(claims, self.config.secret_key, algorithm=self.config.algorithm.value)

    def create_refresh_token(
        self,
        user_id: str,
        email: str,
    ) -> str:
        """Create a refresh token.

        Args:
            user_id: User identifier
            email: User email

        Returns:
            Encoded JWT refresh token

        Raises:
            RuntimeError: If service not initialized
        """
        if not self._initialized:
            raise RuntimeError("JWT service not initialized")

        now = datetime.now(timezone.utc)
        exp = now + timedelta(days=self.config.refresh_token_expire_days)

        payload = TokenPayload(
            sub=user_id,
            email=email,
            type=TokenType.REFRESH,
            iat=now,
            exp=exp,
        )

        claims = payload.to_dict()
        claims["iss"] = self.config.issuer
        claims["aud"] = self.config.audience

        return self._jwt.encode(claims, self.config.secret_key, algorithm=self.config.algorithm.value)

    def create_token_pair(
        self,
        user_id: str,
        email: str,
        roles: list[str] | None = None,
        permissions: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> TokenPair:
        """Create access and refresh token pair.

        Args:
            user_id: User identifier
            email: User email
            roles: User roles
            permissions: User permissions
            metadata: Additional claims

        Returns:
            Token pair with access and refresh tokens
        """
        access_token = self.create_access_token(
            user_id=user_id,
            email=email,
            roles=roles,
            permissions=permissions,
            metadata=metadata,
        )
        refresh_token = self.create_refresh_token(user_id=user_id, email=email)

        return TokenPair(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=self.config.access_token_expire_minutes * 60,
            refresh_expires_in=self.config.refresh_token_expire_days * 24 * 3600,
        )

    def verify_token(self, token: str, token_type: TokenType = TokenType.ACCESS) -> TokenPayload:
        """Verify and decode a JWT token.

        Args:
            token: JWT token to verify
            token_type: Expected token type

        Returns:
            Decoded token payload

        Raises:
            RuntimeError: If service not initialized
            ValueError: If token invalid or expired
        """
        if not self._initialized:
            raise RuntimeError("JWT service not initialized")

        try:
            # Decode and validate
            key = self.config.public_key if self.config.algorithm == JWTAlgorithm.RS256 else self.config.secret_key

            claims = self._jwt.decode(
                token,
                key,
                algorithms=[self.config.algorithm.value],
                issuer=self.config.issuer,
                audience=self.config.audience,
                leeway=timedelta(seconds=self.config.leeway_seconds),
                options={"require_exp": self.config.require_exp},
            )

            payload = TokenPayload.from_dict(claims)

            # Verify token type
            if payload.type != token_type:
                raise ValueError(f"Expected {token_type.value} token, got {payload.type.value}")

            return payload

        except self._jwt.ExpiredSignatureError:
            raise ValueError("Token has expired")
        except self._jwt.InvalidAudienceError:
            raise ValueError("Invalid token audience")
        except self._jwt.InvalidIssuerError:
            raise ValueError("Invalid token issuer")
        except self._jwt.InvalidSignatureError:
            raise ValueError("Invalid token signature")
        except self._jwt.DecodeError as e:
            raise ValueError(f"Token decode error: {e}")
        except Exception as e:
            logger.error(f"Token verification error: {e}")
            raise ValueError(f"Token verification failed: {e}")

    def refresh_tokens(self, refresh_token: str) -> TokenPair:
        """Refresh tokens using a refresh token.

        Args:
            refresh_token: Valid refresh token

        Returns:
            New token pair

        Raises:
            ValueError: If refresh token invalid
        """
        # Verify refresh token
        payload = self.verify_token(refresh_token, TokenType.REFRESH)

        # Create new token pair (preserving user info)
        return self.create_token_pair(
            user_id=payload.sub,
            email=payload.email,
            roles=payload.roles,
            permissions=payload.permissions,
            metadata=payload.metadata,
        )


# =============================================================================
# FASTAPI DEPENDENCIES
# =============================================================================

# Global JWT service instance
_jwt_service: JWTService | None = None


def get_jwt_service() -> JWTService:
    """Get or create JWT service singleton."""
    global _jwt_service
    if _jwt_service is None:
        _jwt_service = JWTService()
        _jwt_service.initialize()
    return _jwt_service


# Bearer token security scheme
bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> TokenPayload:
    """FastAPI dependency to get authenticated user.

    Usage:
        @app.get("/protected")
        async def protected(user: TokenPayload = Depends(get_current_user)):
            return {"user_id": user.sub}

    Raises:
        HTTPException 401: If not authenticated
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    jwt_service = get_jwt_service()
    if not jwt_service._initialized:
        # JWT not configured - allow in dev mode
        if os.environ.get("FASTBAND_DEV_MODE", "").lower() in ("1", "true", "yes"):
            logger.warning("JWT not configured - auth bypassed in dev mode")
            return TokenPayload(sub="dev-user", email="dev@localhost", roles=["admin"])
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service not available",
        )

    try:
        payload = jwt_service.verify_token(credentials.credentials)
        return payload
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_optional_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> TokenPayload | None:
    """FastAPI dependency for optional authentication.

    Returns None if no valid auth provided (instead of raising 401).

    Usage:
        @app.get("/public")
        async def public(user: TokenPayload | None = Depends(get_optional_user)):
            if user:
                return {"message": f"Hello {user.email}"}
            return {"message": "Hello anonymous"}
    """
    if credentials is None:
        return None

    jwt_service = get_jwt_service()
    if not jwt_service._initialized:
        return None

    try:
        return jwt_service.verify_token(credentials.credentials)
    except ValueError:
        return None


def require_roles(*roles: str) -> Callable:
    """Decorator/dependency to require specific roles.

    Usage:
        @app.get("/admin")
        @require_roles("admin")
        async def admin_only():
            return {"message": "Admin access granted"}

        # Or as dependency:
        @app.get("/admin")
        async def admin_only(_: None = Depends(require_roles("admin", "superuser"))):
            return {"message": "Admin access granted"}
    """

    async def check_roles(user: TokenPayload = Depends(get_current_user)) -> TokenPayload:
        if not any(role in user.roles for role in roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of roles: {', '.join(roles)}",
            )
        return user

    return check_roles


def require_permissions(*permissions: str) -> Callable:
    """Decorator/dependency to require specific permissions.

    Usage:
        @app.post("/tickets")
        async def create_ticket(_: None = Depends(require_permissions("tickets:create"))):
            return {"message": "Ticket created"}
    """

    async def check_permissions(user: TokenPayload = Depends(get_current_user)) -> TokenPayload:
        if not all(perm in user.permissions for perm in permissions):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required permissions: {', '.join(permissions)}",
            )
        return user

    return check_permissions


# =============================================================================
# AUTH ROUTES (for integration)
# =============================================================================

# These would be added to FastAPI router for token endpoints
# Example integration in routes.py:
#
# from fastband.hub.auth.jwt import (
#     JWTService, TokenPair, get_jwt_service,
#     get_current_user, require_roles
# )
#
# @router.post("/auth/token")
# async def login(credentials: LoginCredentials):
#     # Validate user credentials against your user store
#     user = await validate_user(credentials)
#     jwt_service = get_jwt_service()
#     tokens = jwt_service.create_token_pair(
#         user_id=user.id,
#         email=user.email,
#         roles=user.roles,
#     )
#     return tokens
#
# @router.post("/auth/refresh")
# async def refresh(refresh_token: str):
#     jwt_service = get_jwt_service()
#     tokens = jwt_service.refresh_tokens(refresh_token)
#     return tokens
#
# @router.get("/protected")
# async def protected(user: TokenPayload = Depends(get_current_user)):
#     return {"user_id": user.sub, "email": user.email}

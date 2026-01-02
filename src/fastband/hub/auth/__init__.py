"""
Fastband AI Hub - Authentication Layer.

Provides flexible authentication with multiple backends:
- Standalone JWT (enterprise/self-hosted)
- Supabase integration (managed auth)

Features:
- Email/password authentication
- OAuth providers (Google, GitHub, etc.)
- JWT token creation and validation
- Role-based access control
- FastAPI dependency injection
"""

from fastband.hub.auth.jwt import (
    JWTAlgorithm,
    JWTConfig,
    JWTService,
    TokenPair,
    TokenPayload,
    TokenType,
    get_current_user,
    get_jwt_service,
    get_optional_user,
    require_permissions,
    require_roles,
)
from fastband.hub.auth.supabase import (
    AuthConfig,
    AuthError,
    Session,
    SupabaseAuth,
    User,
    get_auth,
)

__all__ = [
    # JWT Auth (standalone)
    "JWTService",
    "JWTConfig",
    "JWTAlgorithm",
    "TokenPayload",
    "TokenPair",
    "TokenType",
    "get_jwt_service",
    "get_current_user",
    "get_optional_user",
    "require_roles",
    "require_permissions",
    # Supabase Auth
    "SupabaseAuth",
    "AuthConfig",
    "User",
    "Session",
    "AuthError",
    "get_auth",
]

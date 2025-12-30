"""
Fastband AI Hub - Authentication Layer.

Supabase-based authentication with SSO support.

Features:
- Email/password authentication
- OAuth providers (Google, GitHub, etc.)
- JWT token validation
- Session management
- Role-based access control
"""

from fastband.hub.auth.supabase import (
    AuthConfig,
    AuthError,
    Session,
    SupabaseAuth,
    User,
    get_auth,
)

__all__ = [
    "SupabaseAuth",
    "AuthConfig",
    "User",
    "Session",
    "AuthError",
    "get_auth",
]

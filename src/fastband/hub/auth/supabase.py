"""
Fastband AI Hub - Supabase Authentication.

Integrates with Supabase for user authentication and session management.
Supports email/password and OAuth (Google, GitHub, GitLab, etc.).
"""

import logging
import os
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class AuthProvider(str, Enum):
    """Supported OAuth providers."""

    EMAIL = "email"
    GOOGLE = "google"
    GITHUB = "github"
    GITLAB = "gitlab"
    BITBUCKET = "bitbucket"
    AZURE = "azure"


class AuthError(Exception):
    """Authentication error."""

    def __init__(self, message: str, code: str = "auth_error"):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(slots=True)
class AuthConfig:
    """Supabase authentication configuration.

    Attributes:
        supabase_url: Supabase project URL
        supabase_key: Supabase anon/public key
        jwt_secret: JWT secret for token validation
        access_token_ttl: Access token TTL in seconds
        refresh_token_ttl: Refresh token TTL in seconds
        allowed_providers: List of allowed OAuth providers
        require_email_verification: Require email verification
    """

    supabase_url: str = ""
    supabase_key: str = ""
    jwt_secret: str = ""
    access_token_ttl: int = 3600  # 1 hour
    refresh_token_ttl: int = 604800  # 7 days
    allowed_providers: list[AuthProvider] = field(
        default_factory=lambda: [AuthProvider.EMAIL, AuthProvider.GOOGLE, AuthProvider.GITHUB]
    )
    require_email_verification: bool = True

    @classmethod
    def from_env(cls) -> "AuthConfig":
        """Load configuration from environment variables."""
        return cls(
            supabase_url=os.getenv("SUPABASE_URL", ""),
            supabase_key=os.getenv("SUPABASE_KEY", ""),
            jwt_secret=os.getenv("SUPABASE_JWT_SECRET", ""),
            access_token_ttl=int(os.getenv("AUTH_ACCESS_TOKEN_TTL", "3600")),
            refresh_token_ttl=int(os.getenv("AUTH_REFRESH_TOKEN_TTL", "604800")),
        )


@dataclass(slots=True)
class User:
    """Authenticated user.

    Attributes:
        id: User ID
        email: User email
        email_verified: Whether email is verified
        provider: Auth provider used
        created_at: Account creation time
        last_sign_in: Last sign in time
        metadata: Additional user metadata
        app_metadata: Application-specific metadata
    """

    id: str
    email: str
    email_verified: bool = False
    provider: AuthProvider = AuthProvider.EMAIL
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_sign_in: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    app_metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def display_name(self) -> str:
        """Get display name from metadata or email."""
        return self.metadata.get("full_name") or self.metadata.get("name") or self.email

    @property
    def avatar_url(self) -> str | None:
        """Get avatar URL from metadata."""
        return self.metadata.get("avatar_url")


@dataclass(slots=True)
class Session:
    """Authentication session.

    Attributes:
        access_token: JWT access token
        refresh_token: Refresh token
        expires_at: Token expiration time
        user: Authenticated user
    """

    access_token: str
    refresh_token: str
    expires_at: datetime
    user: User

    @property
    def is_expired(self) -> bool:
        """Check if session is expired."""
        return datetime.utcnow() >= self.expires_at


class SupabaseAuth:
    """
    Supabase authentication client.

    Handles user authentication, session management, and OAuth flows.

    Example:
        auth = SupabaseAuth(config)
        await auth.initialize()

        # Sign up
        session = await auth.sign_up("user@example.com", "password")

        # Sign in
        session = await auth.sign_in_with_password("user@example.com", "password")

        # OAuth
        url = await auth.get_oauth_url(AuthProvider.GOOGLE)

        # Validate token
        user = await auth.get_user(access_token)
    """

    def __init__(self, config: AuthConfig | None = None):
        """Initialize auth client.

        Args:
            config: Auth configuration
        """
        self.config = config or AuthConfig.from_env()
        self._client = None
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the Supabase client."""
        if self._initialized:
            return

        if not self.config.supabase_url or not self.config.supabase_key:
            logger.warning("Supabase credentials not configured")
            return

        try:
            from supabase import create_client

            self._client = create_client(
                self.config.supabase_url,
                self.config.supabase_key,
            )
            self._initialized = True
            logger.info("Supabase auth initialized")

        except ImportError:
            logger.warning("supabase-py not installed. Run: pip install supabase")
        except Exception as e:
            logger.error(f"Failed to initialize Supabase: {e}")

    async def sign_up(
        self,
        email: str,
        password: str,
        metadata: dict[str, Any] | None = None,
    ) -> Session:
        """Sign up a new user with email/password.

        Args:
            email: User email
            password: User password
            metadata: Additional user metadata

        Returns:
            Session with access token

        Raises:
            AuthError: If sign up fails
        """
        if not self._initialized:
            raise AuthError("Auth not initialized", "not_initialized")

        try:
            options = {}
            if metadata:
                options["data"] = metadata

            response = self._client.auth.sign_up(
                {
                    "email": email,
                    "password": password,
                    "options": options,
                }
            )

            if response.user is None:
                raise AuthError("Sign up failed", "signup_failed")

            return self._parse_session(response)

        except Exception as e:
            logger.error(f"Sign up error: {e}")
            raise AuthError(str(e), "signup_error")

    async def sign_in_with_password(
        self,
        email: str,
        password: str,
    ) -> Session:
        """Sign in with email/password.

        Args:
            email: User email
            password: User password

        Returns:
            Session with access token

        Raises:
            AuthError: If sign in fails
        """
        if not self._initialized:
            raise AuthError("Auth not initialized", "not_initialized")

        try:
            response = self._client.auth.sign_in_with_password(
                {
                    "email": email,
                    "password": password,
                }
            )

            if response.user is None:
                raise AuthError("Invalid credentials", "invalid_credentials")

            return self._parse_session(response)

        except Exception as e:
            logger.error(f"Sign in error: {e}")
            raise AuthError(str(e), "signin_error")

    async def get_oauth_url(
        self,
        provider: AuthProvider,
        redirect_url: str | None = None,
        scopes: list[str] | None = None,
    ) -> str:
        """Get OAuth authorization URL.

        Args:
            provider: OAuth provider
            redirect_url: Callback URL after auth
            scopes: OAuth scopes to request

        Returns:
            Authorization URL

        Raises:
            AuthError: If provider not allowed
        """
        if provider not in self.config.allowed_providers:
            raise AuthError(f"Provider {provider.value} not allowed", "provider_not_allowed")

        if not self._initialized:
            raise AuthError("Auth not initialized", "not_initialized")

        try:
            options = {}
            if redirect_url:
                options["redirect_to"] = redirect_url
            if scopes:
                options["scopes"] = " ".join(scopes)

            response = self._client.auth.sign_in_with_oauth(
                {
                    "provider": provider.value,
                    "options": options,
                }
            )

            return response.url

        except Exception as e:
            logger.error(f"OAuth URL error: {e}")
            raise AuthError(str(e), "oauth_error")

    async def exchange_code(
        self,
        code: str,
    ) -> Session:
        """Exchange OAuth code for session.

        Args:
            code: Authorization code from OAuth callback

        Returns:
            Session with access token

        Raises:
            AuthError: If exchange fails
        """
        if not self._initialized:
            raise AuthError("Auth not initialized", "not_initialized")

        try:
            response = self._client.auth.exchange_code_for_session(code)

            if response.user is None:
                raise AuthError("Code exchange failed", "exchange_failed")

            return self._parse_session(response)

        except Exception as e:
            logger.error(f"Code exchange error: {e}")
            raise AuthError(str(e), "exchange_error")

    async def get_user(
        self,
        access_token: str,
    ) -> User:
        """Get user from access token.

        Args:
            access_token: JWT access token

        Returns:
            Authenticated user

        Raises:
            AuthError: If token invalid
        """
        if not self._initialized:
            raise AuthError("Auth not initialized", "not_initialized")

        try:
            response = self._client.auth.get_user(access_token)

            if response.user is None:
                raise AuthError("Invalid token", "invalid_token")

            return self._parse_user(response.user)

        except Exception as e:
            logger.error(f"Get user error: {e}")
            raise AuthError(str(e), "get_user_error")

    async def refresh_session(
        self,
        refresh_token: str,
    ) -> Session:
        """Refresh an expired session.

        Args:
            refresh_token: Refresh token

        Returns:
            New session with fresh tokens

        Raises:
            AuthError: If refresh fails
        """
        if not self._initialized:
            raise AuthError("Auth not initialized", "not_initialized")

        try:
            response = self._client.auth.refresh_session(refresh_token)

            if response.user is None:
                raise AuthError("Refresh failed", "refresh_failed")

            return self._parse_session(response)

        except Exception as e:
            logger.error(f"Refresh error: {e}")
            raise AuthError(str(e), "refresh_error")

    async def sign_out(
        self,
        access_token: str,
    ) -> None:
        """Sign out and invalidate session.

        Args:
            access_token: Access token to invalidate
        """
        if not self._initialized:
            return

        try:
            self._client.auth.sign_out()
        except Exception as e:
            logger.warning(f"Sign out error: {e}")

    async def reset_password(
        self,
        email: str,
        redirect_url: str | None = None,
    ) -> None:
        """Send password reset email.

        Args:
            email: User email
            redirect_url: URL to redirect after reset
        """
        if not self._initialized:
            raise AuthError("Auth not initialized", "not_initialized")

        try:
            options = {}
            if redirect_url:
                options["redirect_to"] = redirect_url

            self._client.auth.reset_password_email(email, options)

        except Exception as e:
            logger.error(f"Password reset error: {e}")
            raise AuthError(str(e), "reset_error")

    async def update_user(
        self,
        access_token: str,
        data: dict[str, Any],
    ) -> User:
        """Update user metadata.

        Args:
            access_token: User access token
            data: Data to update

        Returns:
            Updated user

        Raises:
            AuthError: If update fails
        """
        if not self._initialized:
            raise AuthError("Auth not initialized", "not_initialized")

        try:
            response = self._client.auth.update_user(data)

            if response.user is None:
                raise AuthError("Update failed", "update_failed")

            return self._parse_user(response.user)

        except Exception as e:
            logger.error(f"Update user error: {e}")
            raise AuthError(str(e), "update_error")

    def _parse_session(self, response) -> Session:
        """Parse Supabase session response."""
        user = self._parse_user(response.user)

        expires_at = datetime.utcnow() + timedelta(seconds=self.config.access_token_ttl)
        if hasattr(response.session, "expires_at") and response.session.expires_at:
            expires_at = datetime.fromtimestamp(response.session.expires_at)

        return Session(
            access_token=response.session.access_token,
            refresh_token=response.session.refresh_token,
            expires_at=expires_at,
            user=user,
        )

    def _parse_user(self, user_data) -> User:
        """Parse Supabase user data."""
        provider = AuthProvider.EMAIL
        if hasattr(user_data, "app_metadata"):
            provider_str = user_data.app_metadata.get("provider", "email")
            try:
                provider = AuthProvider(provider_str)
            except ValueError:
                provider = AuthProvider.EMAIL

        created_at = datetime.utcnow()
        if hasattr(user_data, "created_at") and user_data.created_at:
            created_at = datetime.fromisoformat(user_data.created_at.replace("Z", "+00:00"))

        last_sign_in = None
        if hasattr(user_data, "last_sign_in_at") and user_data.last_sign_in_at:
            last_sign_in = datetime.fromisoformat(user_data.last_sign_in_at.replace("Z", "+00:00"))

        return User(
            id=user_data.id,
            email=user_data.email or "",
            email_verified=getattr(user_data, "email_confirmed_at", None) is not None,
            provider=provider,
            created_at=created_at,
            last_sign_in=last_sign_in,
            metadata=getattr(user_data, "user_metadata", {}) or {},
            app_metadata=getattr(user_data, "app_metadata", {}) or {},
        )


# =============================================================================
# GLOBAL SINGLETON
# =============================================================================

_auth: SupabaseAuth | None = None
_auth_lock = threading.Lock()


def get_auth(config: AuthConfig | None = None) -> SupabaseAuth:
    """Get or create the global auth client.

    Args:
        config: Optional auth configuration

    Returns:
        Global SupabaseAuth instance
    """
    global _auth

    with _auth_lock:
        if _auth is None:
            _auth = SupabaseAuth(config)
        return _auth


def reset_auth() -> None:
    """Reset the global auth client (for testing)."""
    global _auth

    with _auth_lock:
        _auth = None

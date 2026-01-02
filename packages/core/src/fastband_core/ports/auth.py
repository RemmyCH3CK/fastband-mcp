"""
Authentication and Authorization port interfaces.

Defines abstractions for identity verification and access control.
Implementations may use JWT, OAuth, API keys, or any auth mechanism.

These are pure interfaces - no framework or crypto library imports allowed.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Protocol, runtime_checkable


class AuthError(Exception):
    """Base exception for authentication/authorization errors."""

    def __init__(self, message: str, code: str | None = None):
        super().__init__(message)
        self.message = message
        self.code = code


class AuthenticationError(AuthError):
    """Raised when authentication fails."""

    pass


class AuthorizationError(AuthError):
    """Raised when authorization fails."""

    pass


class TokenExpiredError(AuthenticationError):
    """Raised when a token has expired."""

    pass


class TokenInvalidError(AuthenticationError):
    """Raised when a token is malformed or invalid."""

    pass


@dataclass(frozen=True)
class Principal:
    """
    Represents an authenticated identity.

    A principal can be a user, service account, or API client.
    """

    id: str
    type: str  # "user", "service", "api_key"
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Credential:
    """
    Represents authentication credentials.

    The type field indicates the credential format (e.g., "bearer", "api_key").
    """

    type: str
    value: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Session:
    """
    Represents an authenticated session.

    Contains the authenticated principal and session metadata.
    """

    id: str
    principal: Principal
    created_at: datetime
    expires_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_expired(self) -> bool:
        """Check if the session has expired."""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at


@dataclass(frozen=True)
class TokenPair:
    """Access and refresh token pair."""

    access_token: str
    refresh_token: str | None = None
    access_expires_at: datetime | None = None
    refresh_expires_at: datetime | None = None
    token_type: str = "Bearer"


class Authenticator(ABC):
    """
    Abstract base for authentication providers.

    Verifies credentials and produces authenticated sessions.
    """

    @abstractmethod
    async def authenticate(self, credential: Credential) -> Session:
        """
        Authenticate using the provided credential.

        Args:
            credential: The credential to verify.

        Returns:
            An authenticated session.

        Raises:
            AuthenticationError: If authentication fails.
            TokenExpiredError: If the credential has expired.
            TokenInvalidError: If the credential is malformed.
        """
        ...

    @abstractmethod
    async def validate_session(self, session_id: str) -> Session | None:
        """
        Validate an existing session.

        Args:
            session_id: The session identifier.

        Returns:
            The session if valid, None if invalid or expired.
        """
        ...

    @abstractmethod
    async def invalidate_session(self, session_id: str) -> bool:
        """
        Invalidate/revoke a session.

        Args:
            session_id: The session to invalidate.

        Returns:
            True if invalidated, False if session didn't exist.
        """
        ...


class TokenProvider(ABC):
    """
    Abstract base for token generation and validation.

    Handles JWT or similar token operations.
    """

    @abstractmethod
    async def generate(
        self,
        principal: Principal,
        expires_in_seconds: int | None = None,
    ) -> TokenPair:
        """
        Generate tokens for a principal.

        Args:
            principal: The identity to generate tokens for.
            expires_in_seconds: Optional custom expiration.

        Returns:
            A token pair with access and optional refresh tokens.
        """
        ...

    @abstractmethod
    async def validate(self, token: str) -> Principal:
        """
        Validate a token and extract the principal.

        Args:
            token: The token string to validate.

        Returns:
            The principal encoded in the token.

        Raises:
            TokenExpiredError: If the token has expired.
            TokenInvalidError: If the token is malformed.
        """
        ...

    @abstractmethod
    async def refresh(self, refresh_token: str) -> TokenPair:
        """
        Generate new tokens using a refresh token.

        Args:
            refresh_token: The refresh token.

        Returns:
            A new token pair.

        Raises:
            TokenExpiredError: If the refresh token has expired.
            TokenInvalidError: If the refresh token is invalid.
        """
        ...

    @abstractmethod
    async def revoke(self, token: str) -> bool:
        """
        Revoke a token (add to blocklist).

        Args:
            token: The token to revoke.

        Returns:
            True if revoked, False if already revoked.
        """
        ...


class Permission(Enum):
    """Standard permission levels."""

    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    ADMIN = "admin"


@dataclass(frozen=True)
class Resource:
    """
    Represents a protected resource.

    Resources are identified by type and optional ID.
    """

    type: str  # e.g., "ticket", "project", "settings"
    id: str | None = None
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AccessRequest:
    """Request to access a resource with a specific action."""

    principal: Principal
    resource: Resource
    action: str  # e.g., "read", "write", "delete"
    context: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AccessDecision:
    """Result of an authorization decision."""

    allowed: bool
    reason: str | None = None
    conditions: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class Authorizer(Protocol):
    """
    Protocol for authorization decisions.

    Implementations may use RBAC, ABAC, or policy-based access control.
    """

    async def authorize(self, request: AccessRequest) -> AccessDecision:
        """
        Make an authorization decision.

        Args:
            request: The access request to evaluate.

        Returns:
            The authorization decision.
        """
        ...

    async def get_permissions(
        self,
        principal: Principal,
        resource: Resource,
    ) -> set[str]:
        """
        Get all permissions a principal has on a resource.

        Args:
            principal: The identity to check.
            resource: The resource to check against.

        Returns:
            Set of permitted actions.
        """
        ...


class CredentialStore(ABC):
    """
    Abstract base for secure credential storage.

    Handles hashing, verification, and secure storage of secrets.
    """

    @abstractmethod
    async def store(
        self,
        principal_id: str,
        credential_type: str,
        secret: str,
    ) -> str:
        """
        Store a credential securely (hashed).

        Args:
            principal_id: The owner of the credential.
            credential_type: Type of credential (e.g., "password", "api_key").
            secret: The secret to hash and store.

        Returns:
            A credential ID for later reference.
        """
        ...

    @abstractmethod
    async def verify(
        self,
        principal_id: str,
        credential_type: str,
        secret: str,
    ) -> bool:
        """
        Verify a credential against stored hash.

        Args:
            principal_id: The credential owner.
            credential_type: Type of credential.
            secret: The secret to verify.

        Returns:
            True if the secret matches.
        """
        ...

    @abstractmethod
    async def revoke(
        self,
        principal_id: str,
        credential_type: str,
    ) -> bool:
        """
        Revoke/delete a stored credential.

        Args:
            principal_id: The credential owner.
            credential_type: Type of credential to revoke.

        Returns:
            True if revoked, False if not found.
        """
        ...

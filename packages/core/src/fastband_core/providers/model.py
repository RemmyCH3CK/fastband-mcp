"""
Provider domain models.

Pure domain models for AI provider interactions. These are shared between
Fastband Dev and Fastband Enterprise, enabling consistent provider handling
across products.

Architecture Rules:
- No side effects on import
- No external SDK imports
- No framework imports (FastAPI, Flask)
- No environment file loading
- All models are data-only (no business logic)
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4


def _utc_now() -> datetime:
    """Get current UTC time (timezone-aware)."""
    return datetime.now(timezone.utc)


def _generate_id() -> str:
    """Generate a unique ID."""
    return str(uuid4())


# =============================================================================
# PROVIDER TYPES
# =============================================================================


class ProviderType(str, Enum):
    """Types of AI providers."""

    COMPLETION = "completion"  # Text/code completion (Claude, GPT, etc.)
    EMBEDDING = "embedding"  # Vector embeddings
    VISION = "vision"  # Image analysis
    SPEECH = "speech"  # Text-to-speech, speech-to-text
    MULTIMODAL = "multimodal"  # Combined capabilities


class ProviderStatus(str, Enum):
    """Provider health status."""

    HEALTHY = "healthy"  # Provider is responding normally
    DEGRADED = "degraded"  # Provider is slow or partially failing
    UNAVAILABLE = "unavailable"  # Provider is not responding
    UNKNOWN = "unknown"  # Status not yet determined


# =============================================================================
# PROVIDER CONFIGURATION
# =============================================================================


@dataclass(frozen=True, slots=True)
class ProviderCredentials:
    """
    Provider authentication credentials.

    Immutable to prevent accidental modification of sensitive data.
    """

    api_key: str | None = None
    api_secret: str | None = None
    organization_id: str | None = None
    project_id: str | None = None
    access_token: str | None = None
    refresh_token: str | None = None

    def has_credentials(self) -> bool:
        """Check if any credentials are present."""
        return any(
            [
                self.api_key,
                self.api_secret,
                self.access_token,
            ]
        )

    def to_dict(self, *, mask_secrets: bool = True) -> dict[str, Any]:
        """
        Convert to dictionary.

        Args:
            mask_secrets: If True, masks sensitive values with asterisks.
        """

        def mask(value: str | None) -> str | None:
            if value is None or not mask_secrets:
                return value
            if len(value) <= 8:
                return "****"
            return f"{value[:4]}...{value[-4:]}"

        return {
            "api_key": mask(self.api_key),
            "api_secret": mask(self.api_secret),
            "organization_id": self.organization_id,
            "project_id": self.project_id,
            "access_token": mask(self.access_token),
            "refresh_token": mask(self.refresh_token),
        }


@dataclass(slots=True)
class ProviderConfig:
    """
    Configuration for an AI provider.

    Contains all settings needed to initialize and use a provider.
    """

    name: str
    api_key: str | None = None
    base_url: str | None = None
    model: str | None = None
    max_tokens: int = 4096
    temperature: float = 0.7
    timeout: int = 120
    retry_attempts: int = 3
    retry_delay: float = 1.0
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self, *, include_secrets: bool = False) -> dict[str, Any]:
        """Convert to dictionary."""
        result = {
            "name": self.name,
            "base_url": self.base_url,
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "timeout": self.timeout,
            "retry_attempts": self.retry_attempts,
            "retry_delay": self.retry_delay,
            "extra": self.extra,
        }
        if include_secrets:
            result["api_key"] = self.api_key
        else:
            result["api_key"] = "****" if self.api_key else None
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProviderConfig":
        """Create from dictionary."""
        return cls(
            name=data["name"],
            api_key=data.get("api_key"),
            base_url=data.get("base_url"),
            model=data.get("model"),
            max_tokens=data.get("max_tokens", 4096),
            temperature=data.get("temperature", 0.7),
            timeout=data.get("timeout", 120),
            retry_attempts=data.get("retry_attempts", 3),
            retry_delay=data.get("retry_delay", 1.0),
            extra=data.get("extra", {}),
        )


# =============================================================================
# COMPLETION MODELS
# =============================================================================


@dataclass(frozen=True, slots=True)
class TokenUsage:
    """Token usage statistics from a completion."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cached_tokens: int = 0  # For providers that support caching

    def to_dict(self) -> dict[str, int]:
        """Convert to dictionary."""
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "cached_tokens": self.cached_tokens,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TokenUsage":
        """Create from dictionary."""
        return cls(
            prompt_tokens=data.get("prompt_tokens", 0),
            completion_tokens=data.get("completion_tokens", 0),
            total_tokens=data.get("total_tokens", 0),
            cached_tokens=data.get("cached_tokens", 0),
        )


class FinishReason(str, Enum):
    """Reason for completion termination."""

    STOP = "stop"  # Natural completion
    LENGTH = "length"  # Max tokens reached
    TOOL_USE = "tool_use"  # Tool/function call requested
    CONTENT_FILTER = "content_filter"  # Content filtered
    ERROR = "error"  # Error occurred
    UNKNOWN = "unknown"  # Unknown reason


@dataclass(frozen=True, slots=True)
class ToolCall:
    """A tool/function call from the model."""

    tool_id: str
    tool_name: str
    arguments: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "tool_id": self.tool_id,
            "tool_name": self.tool_name,
            "arguments": self.arguments,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ToolCall":
        """Create from dictionary."""
        return cls(
            tool_id=data.get("tool_id", ""),
            tool_name=data.get("tool_name", ""),
            arguments=data.get("arguments", {}),
        )


@dataclass(frozen=True, slots=True)
class CompletionResponse:
    """
    Standardized response from any AI provider.

    Provides a consistent interface regardless of which provider
    generated the completion.
    """

    content: str
    model: str
    provider: str
    usage: TokenUsage
    finish_reason: FinishReason
    response_id: str = field(default_factory=_generate_id)
    created_at: datetime = field(default_factory=_utc_now)
    tool_calls: tuple[ToolCall, ...] = ()
    raw_response: dict[str, Any] | None = None

    @property
    def has_tool_calls(self) -> bool:
        """Check if response contains tool calls."""
        return len(self.tool_calls) > 0

    @property
    def is_complete(self) -> bool:
        """Check if completion finished naturally."""
        return self.finish_reason == FinishReason.STOP

    def to_dict(self, *, include_raw: bool = False) -> dict[str, Any]:
        """Convert to dictionary."""
        result = {
            "response_id": self.response_id,
            "content": self.content,
            "model": self.model,
            "provider": self.provider,
            "usage": self.usage.to_dict(),
            "finish_reason": self.finish_reason.value,
            "created_at": self.created_at.isoformat(),
            "tool_calls": [tc.to_dict() for tc in self.tool_calls],
        }
        if include_raw and self.raw_response:
            result["raw_response"] = self.raw_response
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CompletionResponse":
        """Create from dictionary."""
        return cls(
            response_id=data.get("response_id", _generate_id()),
            content=data.get("content", ""),
            model=data.get("model", ""),
            provider=data.get("provider", ""),
            usage=TokenUsage.from_dict(data.get("usage", {})),
            finish_reason=FinishReason(data.get("finish_reason", "unknown")),
            created_at=datetime.fromisoformat(data["created_at"])
            if "created_at" in data
            else _utc_now(),
            tool_calls=tuple(
                ToolCall.from_dict(tc) for tc in data.get("tool_calls", [])
            ),
            raw_response=data.get("raw_response"),
        )


# =============================================================================
# EMBEDDING MODELS
# =============================================================================


@dataclass(slots=True)
class EmbeddingConfig:
    """Configuration for an embedding provider."""

    api_key: str | None = None
    model: str | None = None
    base_url: str | None = None
    dimensions: int | None = None  # Output dimensions (for providers that support it)
    batch_size: int = 100  # Max texts per API call
    timeout: int = 60
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self, *, include_secrets: bool = False) -> dict[str, Any]:
        """Convert to dictionary."""
        result = {
            "model": self.model,
            "base_url": self.base_url,
            "dimensions": self.dimensions,
            "batch_size": self.batch_size,
            "timeout": self.timeout,
            "extra": self.extra,
        }
        if include_secrets:
            result["api_key"] = self.api_key
        else:
            result["api_key"] = "****" if self.api_key else None
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EmbeddingConfig":
        """Create from dictionary."""
        return cls(
            api_key=data.get("api_key"),
            model=data.get("model"),
            base_url=data.get("base_url"),
            dimensions=data.get("dimensions"),
            batch_size=data.get("batch_size", 100),
            timeout=data.get("timeout", 60),
            extra=data.get("extra", {}),
        )


@dataclass(frozen=True, slots=True)
class EmbeddingResult:
    """Result from an embedding operation."""

    embeddings: tuple[tuple[float, ...], ...]  # Immutable nested structure
    model: str
    provider: str
    dimensions: int
    usage: TokenUsage

    @property
    def count(self) -> int:
        """Number of embeddings in result."""
        return len(self.embeddings)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "embeddings": [list(e) for e in self.embeddings],
            "model": self.model,
            "provider": self.provider,
            "dimensions": self.dimensions,
            "usage": self.usage.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EmbeddingResult":
        """Create from dictionary."""
        return cls(
            embeddings=tuple(tuple(e) for e in data.get("embeddings", [])),
            model=data.get("model", ""),
            provider=data.get("provider", ""),
            dimensions=data.get("dimensions", 0),
            usage=TokenUsage.from_dict(data.get("usage", {})),
        )

    @classmethod
    def empty(cls, model: str, provider: str, dimensions: int) -> "EmbeddingResult":
        """Create an empty result."""
        return cls(
            embeddings=(),
            model=model,
            provider=provider,
            dimensions=dimensions,
            usage=TokenUsage(),
        )


# =============================================================================
# PROVIDER HEALTH
# =============================================================================


@dataclass(frozen=True, slots=True)
class ProviderHealth:
    """Health status of a provider."""

    provider: str
    status: ProviderStatus
    latency_ms: float | None = None
    last_check: datetime = field(default_factory=_utc_now)
    error_message: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def is_healthy(self) -> bool:
        """Check if provider is healthy."""
        return self.status == ProviderStatus.HEALTHY

    @property
    def is_available(self) -> bool:
        """Check if provider is available (healthy or degraded)."""
        return self.status in (ProviderStatus.HEALTHY, ProviderStatus.DEGRADED)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "provider": self.provider,
            "status": self.status.value,
            "latency_ms": self.latency_ms,
            "last_check": self.last_check.isoformat(),
            "error_message": self.error_message,
            "details": self.details,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProviderHealth":
        """Create from dictionary."""
        return cls(
            provider=data.get("provider", ""),
            status=ProviderStatus(data.get("status", "unknown")),
            latency_ms=data.get("latency_ms"),
            last_check=datetime.fromisoformat(data["last_check"])
            if "last_check" in data
            else _utc_now(),
            error_message=data.get("error_message"),
            details=data.get("details", {}),
        )


# =============================================================================
# PROVIDER ERRORS
# =============================================================================


class ProviderErrorType(str, Enum):
    """Types of provider errors."""

    AUTHENTICATION = "authentication"  # API key invalid or expired
    RATE_LIMIT = "rate_limit"  # Rate limit exceeded
    QUOTA_EXCEEDED = "quota_exceeded"  # Usage quota exceeded
    INVALID_REQUEST = "invalid_request"  # Bad request format
    MODEL_NOT_FOUND = "model_not_found"  # Model doesn't exist
    CONTENT_FILTERED = "content_filtered"  # Content blocked
    TIMEOUT = "timeout"  # Request timed out
    CONNECTION = "connection"  # Network error
    SERVER_ERROR = "server_error"  # Provider server error
    UNKNOWN = "unknown"  # Unknown error


@dataclass(frozen=True, slots=True)
class ProviderError:
    """
    Structured provider error information.

    Provides consistent error handling across all providers.
    """

    error_type: ProviderErrorType
    message: str
    provider: str
    model: str | None = None
    status_code: int | None = None
    retry_after: float | None = None  # Seconds to wait before retry
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def is_retryable(self) -> bool:
        """Check if error is retryable."""
        return self.error_type in (
            ProviderErrorType.RATE_LIMIT,
            ProviderErrorType.TIMEOUT,
            ProviderErrorType.CONNECTION,
            ProviderErrorType.SERVER_ERROR,
        )

    @property
    def is_auth_error(self) -> bool:
        """Check if error is authentication-related."""
        return self.error_type == ProviderErrorType.AUTHENTICATION

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "error_type": self.error_type.value,
            "message": self.message,
            "provider": self.provider,
            "model": self.model,
            "status_code": self.status_code,
            "retry_after": self.retry_after,
            "details": self.details,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProviderError":
        """Create from dictionary."""
        return cls(
            error_type=ProviderErrorType(data.get("error_type", "unknown")),
            message=data.get("message", ""),
            provider=data.get("provider", ""),
            model=data.get("model"),
            status_code=data.get("status_code"),
            retry_after=data.get("retry_after"),
            details=data.get("details", {}),
        )

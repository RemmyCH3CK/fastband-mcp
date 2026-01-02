"""
Policy evaluation port interfaces.

Defines abstractions for policy definition, evaluation, and enforcement.
Supports feature flags, rate limiting, and business rule evaluation.

These are pure interfaces - no policy engine imports allowed.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Generic, Protocol, TypeVar, runtime_checkable


class PolicyError(Exception):
    """Base exception for policy operations."""

    def __init__(self, message: str, policy_id: str | None = None):
        super().__init__(message)
        self.message = message
        self.policy_id = policy_id


class PolicyViolation(PolicyError):
    """Raised when a policy is violated."""

    pass


class RateLimitExceeded(PolicyError):
    """Raised when rate limit is exceeded."""

    def __init__(
        self,
        message: str,
        retry_after_seconds: int | None = None,
        limit: int | None = None,
        remaining: int = 0,
    ):
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds
        self.limit = limit
        self.remaining = remaining


class PolicyDecision(Enum):
    """Result of policy evaluation."""

    ALLOW = "allow"
    DENY = "deny"
    WARN = "warn"  # Allow but log warning
    AUDIT = "audit"  # Allow but require audit log


@dataclass
class PolicyContext:
    """
    Context for policy evaluation.

    Contains all information needed to evaluate a policy.
    """

    subject: str  # Who is performing the action
    action: str  # What action is being performed
    resource: str  # What resource is being accessed
    environment: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class PolicyResult:
    """
    Result of a policy evaluation.

    Contains the decision and any additional context.
    """

    decision: PolicyDecision
    policy_id: str | None = None
    reason: str | None = None
    obligations: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Policy:
    """
    A policy definition.

    Policies define rules for access control and business logic.
    """

    id: str
    name: str
    description: str | None = None
    effect: PolicyDecision = PolicyDecision.ALLOW
    conditions: dict[str, Any] = field(default_factory=dict)
    priority: int = 0  # Higher priority = evaluated first
    enabled: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


class PolicyEvaluator(ABC):
    """
    Abstract base for policy evaluation.

    Evaluates policies against a given context.
    """

    @abstractmethod
    async def evaluate(self, context: PolicyContext) -> PolicyResult:
        """
        Evaluate all applicable policies for a context.

        Args:
            context: The policy evaluation context.

        Returns:
            The combined policy result.
        """
        ...

    @abstractmethod
    async def evaluate_policy(
        self,
        policy_id: str,
        context: PolicyContext,
    ) -> PolicyResult:
        """
        Evaluate a specific policy.

        Args:
            policy_id: The policy to evaluate.
            context: The evaluation context.

        Returns:
            The policy result.
        """
        ...


class PolicyStore(ABC):
    """
    Abstract base for policy storage and retrieval.

    Manages policy definitions and their lifecycle.
    """

    @abstractmethod
    async def get(self, policy_id: str) -> Policy | None:
        """
        Retrieve a policy by ID.

        Args:
            policy_id: The policy identifier.

        Returns:
            The policy if found, None otherwise.
        """
        ...

    @abstractmethod
    async def list(
        self,
        enabled_only: bool = True,
        resource_type: str | None = None,
    ) -> list[Policy]:
        """
        List policies with optional filtering.

        Args:
            enabled_only: Only return enabled policies.
            resource_type: Filter by resource type.

        Returns:
            List of matching policies.
        """
        ...

    @abstractmethod
    async def create(self, policy: Policy) -> Policy:
        """
        Create a new policy.

        Args:
            policy: The policy to create.

        Returns:
            The created policy.
        """
        ...

    @abstractmethod
    async def update(self, policy: Policy) -> Policy:
        """
        Update an existing policy.

        Args:
            policy: The policy with updates.

        Returns:
            The updated policy.
        """
        ...

    @abstractmethod
    async def delete(self, policy_id: str) -> bool:
        """
        Delete a policy.

        Args:
            policy_id: The policy to delete.

        Returns:
            True if deleted, False if not found.
        """
        ...


# Feature Flag Types
T = TypeVar("T")


@dataclass
class FeatureFlag(Generic[T]):
    """
    A feature flag definition.

    Supports typed default values and targeting rules.
    """

    key: str
    default_value: T
    description: str | None = None
    enabled: bool = True
    targeting_rules: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class FeatureFlagContext:
    """Context for feature flag evaluation."""

    user_id: str | None = None
    attributes: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class FeatureFlagProvider(Protocol[T]):
    """
    Protocol for feature flag evaluation.

    Implementations may use LaunchDarkly, Unleash, or custom logic.
    """

    async def get_flag(self, key: str, context: FeatureFlagContext) -> T | None:
        """
        Get the value of a feature flag.

        Args:
            key: The flag key.
            context: Evaluation context.

        Returns:
            The flag value, or None if not found.
        """
        ...

    async def get_bool(
        self,
        key: str,
        context: FeatureFlagContext,
        default: bool = False,
    ) -> bool:
        """Get a boolean flag value."""
        ...

    async def get_string(
        self,
        key: str,
        context: FeatureFlagContext,
        default: str = "",
    ) -> str:
        """Get a string flag value."""
        ...

    async def get_int(
        self,
        key: str,
        context: FeatureFlagContext,
        default: int = 0,
    ) -> int:
        """Get an integer flag value."""
        ...


# Rate Limiting


@dataclass
class RateLimitConfig:
    """Configuration for a rate limit."""

    key: str  # Identifier for this rate limit
    max_requests: int
    window_seconds: int
    burst_size: int | None = None  # Optional burst allowance


@dataclass
class RateLimitStatus:
    """Current status of a rate limit."""

    key: str
    limit: int
    remaining: int
    reset_at: datetime
    retry_after_seconds: int | None = None


class RateLimiter(ABC):
    """
    Abstract base for rate limiting.

    Supports sliding window, token bucket, or other algorithms.
    """

    @abstractmethod
    async def check(
        self,
        key: str,
        config: RateLimitConfig,
    ) -> RateLimitStatus:
        """
        Check rate limit status without consuming.

        Args:
            key: The rate limit key (e.g., user_id, ip_address).
            config: The rate limit configuration.

        Returns:
            Current rate limit status.
        """
        ...

    @abstractmethod
    async def acquire(
        self,
        key: str,
        config: RateLimitConfig,
        cost: int = 1,
    ) -> RateLimitStatus:
        """
        Attempt to acquire rate limit tokens.

        Args:
            key: The rate limit key.
            config: The rate limit configuration.
            cost: Number of tokens to consume.

        Returns:
            Updated rate limit status.

        Raises:
            RateLimitExceeded: If rate limit would be exceeded.
        """
        ...

    @abstractmethod
    async def reset(self, key: str) -> bool:
        """
        Reset a rate limit.

        Args:
            key: The rate limit key to reset.

        Returns:
            True if reset, False if key didn't exist.
        """
        ...


# Quota Management


@dataclass
class QuotaConfig:
    """Configuration for a usage quota."""

    key: str
    limit: int
    period: str  # "daily", "monthly", "yearly"
    soft_limit: int | None = None  # Warning threshold


@dataclass
class QuotaStatus:
    """Current status of a quota."""

    key: str
    used: int
    limit: int
    remaining: int
    period_start: datetime
    period_end: datetime
    exceeded: bool = False
    soft_limit_exceeded: bool = False


class QuotaManager(ABC):
    """
    Abstract base for quota management.

    Tracks usage against defined limits over time periods.
    """

    @abstractmethod
    async def get_status(self, key: str, config: QuotaConfig) -> QuotaStatus:
        """
        Get current quota status.

        Args:
            key: The quota key (e.g., org_id:api_calls).
            config: The quota configuration.

        Returns:
            Current quota status.
        """
        ...

    @abstractmethod
    async def increment(
        self,
        key: str,
        config: QuotaConfig,
        amount: int = 1,
    ) -> QuotaStatus:
        """
        Increment quota usage.

        Args:
            key: The quota key.
            config: The quota configuration.
            amount: Amount to increment by.

        Returns:
            Updated quota status.

        Raises:
            PolicyViolation: If quota would be exceeded.
        """
        ...

    @abstractmethod
    async def reset(self, key: str) -> bool:
        """
        Reset a quota.

        Args:
            key: The quota key to reset.

        Returns:
            True if reset, False if key didn't exist.
        """
        ...

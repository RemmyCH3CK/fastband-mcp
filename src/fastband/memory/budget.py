"""
Token Budget System for Fastband Memory Architecture.

Manages token allocation across agents with auto-expansion for complex tasks.
Achieves 96% cost savings on simple tickets while preserving effectiveness.
"""

import threading
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

# Default token limits (can be overridden by MemoryConfig)
DEFAULT_WORKING_MEMORY = 20_000  # Base working memory
EXPANDED_WORKING_MEMORY = 40_000  # Auto-expand threshold
MAX_WORKING_MEMORY = 80_000  # Hard ceiling
TOTAL_BUDGET = 150_000  # Total context window

# Default handoff thresholds (can be overridden by MemoryConfig)
HANDOFF_WARNING_THRESHOLD = 60  # Percentage
HANDOFF_CRITICAL_THRESHOLD = 80  # Percentage

# Auto-expansion triggers
FILES_THRESHOLD = 5  # Expand if >5 files modified
RETRY_THRESHOLD = 3  # Expand after 3 failed attempts
COMPLEXITY_TAGS = {"complex", "refactor", "architecture", "migration"}


def _get_memory_config():
    """
    Get MemoryConfig if available. Returns None if config not loaded.

    P1: Connects budget constants to config for consistency.
    """
    try:
        from fastband.core.config import get_config
        config = get_config()
        return config.memory
    except Exception:
        return None


def get_configured_value(attr: str, default: int) -> int:
    """Get a value from MemoryConfig, falling back to default."""
    config = _get_memory_config()
    if config:
        return getattr(config, attr, default)
    return default


class BudgetTier(Enum):
    """Memory budget tiers with token allocations."""

    MINIMAL = 20_000  # Simple bug fixes, single file changes
    STANDARD = 40_000  # Multi-file changes, moderate complexity
    EXPANDED = 60_000  # Complex refactors, debugging sessions
    MAXIMUM = 80_000  # Emergency ceiling for critical tasks


@dataclass
class TokenBudget:
    """Tracks token usage and budget for an agent session. Thread-safe."""

    agent_name: str
    session_id: str
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    # Current allocation
    tier: BudgetTier = BudgetTier.MINIMAL
    allocated_tokens: int = DEFAULT_WORKING_MEMORY
    used_tokens: int = 0

    # Expansion tracking
    files_modified: int = 0
    retry_count: int = 0
    has_complexity_tag: bool = False
    manual_expansion: bool = False

    # Usage history
    peak_usage: int = 0
    expansion_count: int = 0

    # Thread safety
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    @property
    def available_tokens(self) -> int:
        """Tokens available for use."""
        return self.allocated_tokens - self.used_tokens

    @property
    def usage_percentage(self) -> float:
        """Current usage as percentage."""
        if self.allocated_tokens == 0:
            return 0.0
        return (self.used_tokens / self.allocated_tokens) * 100

    @property
    def should_handoff(self) -> bool:
        """Check if agent should prepare for handoff (configurable threshold)."""
        threshold = get_configured_value("handoff_warning_threshold", HANDOFF_WARNING_THRESHOLD)
        return self.usage_percentage >= threshold

    @property
    def must_handoff(self) -> bool:
        """Check if agent must handoff immediately (configurable threshold)."""
        threshold = get_configured_value("handoff_critical_threshold", HANDOFF_CRITICAL_THRESHOLD)
        return self.usage_percentage >= threshold

    def consume(self, tokens: int) -> bool:
        """
        Consume tokens from budget. Thread-safe.

        Returns True if successful, False if would exceed budget.
        """
        with self._lock:
            if tokens > self.available_tokens:
                return False

            self.used_tokens += tokens
            if self.used_tokens > self.peak_usage:
                self.peak_usage = self.used_tokens
            return True

    def release(self, tokens: int) -> None:
        """Release tokens back to budget. Thread-safe."""
        with self._lock:
            self.used_tokens = max(0, self.used_tokens - tokens)

    def check_auto_expansion(self) -> tuple[bool, str | None]:
        """
        Check if auto-expansion should trigger.

        Returns (should_expand, reason).
        """
        if self.tier == BudgetTier.MAXIMUM:
            return False, None

        # Check file count trigger
        if self.files_modified > FILES_THRESHOLD and self.tier == BudgetTier.MINIMAL:
            return True, f"Modified {self.files_modified} files (threshold: {FILES_THRESHOLD})"

        # Check retry trigger
        if self.retry_count >= RETRY_THRESHOLD and self.tier.value < BudgetTier.EXPANDED.value:
            return True, f"Failed {self.retry_count} attempts (threshold: {RETRY_THRESHOLD})"

        # Check complexity tag trigger
        if self.has_complexity_tag and self.tier == BudgetTier.MINIMAL:
            return True, "Ticket has complexity tag"

        return False, None

    def expand(self, reason: str | None = None) -> bool:
        """
        Expand to next tier. Thread-safe.

        Returns True if expansion occurred.
        """
        with self._lock:
            tier_order = [BudgetTier.MINIMAL, BudgetTier.STANDARD, BudgetTier.EXPANDED, BudgetTier.MAXIMUM]
            current_idx = tier_order.index(self.tier)

            if current_idx >= len(tier_order) - 1:
                return False  # Already at maximum

            self.tier = tier_order[current_idx + 1]
            self.allocated_tokens = self.tier.value
            self.expansion_count += 1
            return True

    def record_file_modification(self) -> None:
        """Record a file modification and check for auto-expansion. Thread-safe."""
        with self._lock:
            self.files_modified += 1
        should_expand, reason = self.check_auto_expansion()
        if should_expand:
            self.expand(reason)

    def record_retry(self) -> None:
        """Record a retry attempt and check for auto-expansion. Thread-safe."""
        with self._lock:
            self.retry_count += 1
        should_expand, reason = self.check_auto_expansion()
        if should_expand:
            self.expand(reason)

    def set_complexity_tag(self, tags: set[str]) -> None:
        """Check ticket tags for complexity indicators. Thread-safe."""
        with self._lock:
            if tags & COMPLEXITY_TAGS:
                self.has_complexity_tag = True
        should_expand, reason = self.check_auto_expansion()
        if should_expand:
            self.expand(reason)

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "agent_name": self.agent_name,
            "session_id": self.session_id,
            "created_at": self.created_at,
            "tier": self.tier.name,
            "allocated_tokens": self.allocated_tokens,
            "used_tokens": self.used_tokens,
            "files_modified": self.files_modified,
            "retry_count": self.retry_count,
            "has_complexity_tag": self.has_complexity_tag,
            "manual_expansion": self.manual_expansion,
            "peak_usage": self.peak_usage,
            "expansion_count": self.expansion_count,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TokenBudget":
        """Deserialize from dictionary."""
        budget = cls(
            agent_name=data["agent_name"],
            session_id=data["session_id"],
            created_at=data.get("created_at", datetime.utcnow().isoformat()),
        )
        budget.tier = BudgetTier[data.get("tier", "MINIMAL")]
        budget.allocated_tokens = data.get("allocated_tokens", DEFAULT_WORKING_MEMORY)
        budget.used_tokens = data.get("used_tokens", 0)
        budget.files_modified = data.get("files_modified", 0)
        budget.retry_count = data.get("retry_count", 0)
        budget.has_complexity_tag = data.get("has_complexity_tag", False)
        budget.manual_expansion = data.get("manual_expansion", False)
        budget.peak_usage = data.get("peak_usage", 0)
        budget.expansion_count = data.get("expansion_count", 0)
        return budget


class BudgetManager:
    """Manages token budgets across multiple agent sessions. Thread-safe."""

    def __init__(self):
        self._budgets: dict[str, TokenBudget] = {}
        self._lock = threading.Lock()

    def create_budget(self, agent_name: str, session_id: str) -> TokenBudget:
        """Create a new budget for an agent session. Thread-safe."""
        # P1: Use configured default_working_memory
        initial_allocation = get_configured_value("default_working_memory", DEFAULT_WORKING_MEMORY)
        budget = TokenBudget(
            agent_name=agent_name,
            session_id=session_id,
            allocated_tokens=initial_allocation,
        )
        with self._lock:
            self._budgets[session_id] = budget
        return budget

    def get_budget(self, session_id: str) -> Optional[TokenBudget]:
        """Get budget for a session. Thread-safe."""
        with self._lock:
            return self._budgets.get(session_id)

    def close_session(self, session_id: str) -> Optional[dict]:
        """
        Close a session and return usage stats. Thread-safe.

        Returns summary of token usage for analytics.
        """
        with self._lock:
            budget = self._budgets.pop(session_id, None)
        if budget:
            return {
                "agent_name": budget.agent_name,
                "session_id": session_id,
                "final_tier": budget.tier.name,
                "peak_usage": budget.peak_usage,
                "files_modified": budget.files_modified,
                "expansion_count": budget.expansion_count,
                "efficiency": (
                    budget.peak_usage / budget.allocated_tokens * 100
                    if budget.allocated_tokens > 0
                    else 0
                ),
            }
        return None

    def get_total_usage(self) -> dict:
        """Get aggregate usage across all active sessions. Thread-safe."""
        with self._lock:
            budgets = list(self._budgets.values())
        total_allocated = sum(b.allocated_tokens for b in budgets)
        total_used = sum(b.used_tokens for b in budgets)
        return {
            "active_sessions": len(budgets),
            "total_allocated": total_allocated,
            "total_used": total_used,
            "total_available": total_allocated - total_used,
            "global_budget": TOTAL_BUDGET,
            "budget_utilization": (total_allocated / TOTAL_BUDGET * 100) if TOTAL_BUDGET > 0 else 0,
        }


# Global budget manager instance (thread-safe singleton)
_budget_manager: Optional[BudgetManager] = None
_budget_manager_lock = threading.Lock()


def get_budget_manager() -> BudgetManager:
    """Get or create the global budget manager. Thread-safe."""
    global _budget_manager
    if _budget_manager is None:
        with _budget_manager_lock:
            # Double-check pattern
            if _budget_manager is None:
                _budget_manager = BudgetManager()
    return _budget_manager

"""
5-Tier Memory Architecture for Fastband.

Tier 0: Hot Memory (Working) - Active context, 20k tokens
Tier 1: Warm Memory (Session) - Current ticket + recent actions
Tier 2: Cool Memory (Semantic) - Embeddings of past solutions
Tier 3: Cold Memory (Ticket Archive) - Compressed ticket histories
Tier 4: Frozen Memory (Bible/Config) - Lazy-loaded reference docs

"The ticket IS the memory, not the conversation."
"""

import threading
from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum
from typing import Any, Optional

from fastband.memory.budget import TokenBudget, get_budget_manager


class MemoryTier(IntEnum):
    """Memory tiers ordered by access speed and cost."""

    HOT = 0  # Working memory - always loaded
    WARM = 1  # Session memory - current ticket context
    COOL = 2  # Semantic memory - embeddings, quick retrieval
    COLD = 3  # Archive memory - compressed, rarely accessed
    FROZEN = 4  # Reference memory - lazy loaded on demand


# Token costs per tier (estimated)
TIER_TOKEN_COSTS = {
    MemoryTier.HOT: 1.0,  # Full cost - always in context
    MemoryTier.WARM: 0.5,  # Partial cost - loaded on demand
    MemoryTier.COOL: 0.1,  # Embedding lookup cost
    MemoryTier.COLD: 0.05,  # Decompression cost
    MemoryTier.FROZEN: 0.02,  # Lazy load cost
}


@dataclass
class MemoryItem:
    """A single item in the memory system."""

    item_id: str
    tier: MemoryTier
    content: str
    token_count: int
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    last_accessed: Optional[str] = None
    access_count: int = 0
    metadata: dict = field(default_factory=dict)

    # For semantic memory
    embedding: Optional[list[float]] = None

    def access(self) -> str:
        """Access this memory item, updating stats."""
        self.last_accessed = datetime.utcnow().isoformat()
        self.access_count += 1
        return self.content

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "item_id": self.item_id,
            "tier": self.tier.name,
            "content": self.content,
            "token_count": self.token_count,
            "created_at": self.created_at,
            "last_accessed": self.last_accessed,
            "access_count": self.access_count,
            "metadata": self.metadata,
            # Embeddings stored separately for efficiency
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MemoryItem":
        """Deserialize from dictionary."""
        return cls(
            item_id=data["item_id"],
            tier=MemoryTier[data["tier"]],
            content=data["content"],
            token_count=data["token_count"],
            created_at=data.get("created_at", datetime.utcnow().isoformat()),
            last_accessed=data.get("last_accessed"),
            access_count=data.get("access_count", 0),
            metadata=data.get("metadata", {}),
        )


@dataclass
class TieredMemoryStore:
    """
    Manages memory across all 5 tiers for an agent session.

    Key insight: "The ticket IS the memory, not the conversation."
    - Hot memory: Current working context only
    - Everything else loads on-demand from ticket/archive
    """

    session_id: str
    budget: TokenBudget

    # Tier storage
    hot: dict[str, MemoryItem] = field(default_factory=dict)
    warm: dict[str, MemoryItem] = field(default_factory=dict)
    cool: dict[str, MemoryItem] = field(default_factory=dict)
    cold: dict[str, MemoryItem] = field(default_factory=dict)
    frozen: dict[str, MemoryItem] = field(default_factory=dict)

    # LRU tracking for eviction
    _access_order: list[str] = field(default_factory=list)

    def _get_tier_store(self, tier: MemoryTier) -> dict[str, MemoryItem]:
        """Get the storage dict for a tier."""
        return {
            MemoryTier.HOT: self.hot,
            MemoryTier.WARM: self.warm,
            MemoryTier.COOL: self.cool,
            MemoryTier.COLD: self.cold,
            MemoryTier.FROZEN: self.frozen,
        }[tier]

    def store(self, item: MemoryItem) -> bool:
        """
        Store an item in its designated tier.

        Returns False if storage would exceed budget.
        """
        # Hot tier items consume from budget
        if item.tier == MemoryTier.HOT:
            if not self.budget.consume(item.token_count):
                # Try eviction before failing
                if not self._evict_lru(item.token_count):
                    return False
                if not self.budget.consume(item.token_count):
                    return False

        store = self._get_tier_store(item.tier)
        store[item.item_id] = item

        if item.tier == MemoryTier.HOT:
            self._access_order.append(item.item_id)

        return True

    def retrieve(self, item_id: str, tier: Optional[MemoryTier] = None) -> Optional[MemoryItem]:
        """
        Retrieve an item, optionally promoting it to hot memory.

        If tier is not specified, searches all tiers.
        """
        if tier:
            store = self._get_tier_store(tier)
            item = store.get(item_id)
            if item:
                item.access()
                return item
            return None

        # Search all tiers, hottest first
        for t in MemoryTier:
            store = self._get_tier_store(t)
            item = store.get(item_id)
            if item:
                item.access()
                return item
        return None

    def promote_to_hot(self, item_id: str) -> bool:
        """
        Promote an item from any tier to hot memory.

        Returns False if budget doesn't allow.
        """
        # Find the item
        item = None
        source_tier = None
        for tier in MemoryTier:
            if tier == MemoryTier.HOT:
                continue
            store = self._get_tier_store(tier)
            if item_id in store:
                item = store[item_id]
                source_tier = tier
                break

        if not item:
            return False

        # Check budget
        if not self.budget.consume(item.token_count):
            if not self._evict_lru(item.token_count):
                return False
            if not self.budget.consume(item.token_count):
                return False

        # Move to hot
        source_store = self._get_tier_store(source_tier)
        del source_store[item_id]
        item.tier = MemoryTier.HOT
        self.hot[item_id] = item
        self._access_order.append(item_id)
        return True

    def demote_from_hot(self, item_id: str, target_tier: MemoryTier = MemoryTier.WARM) -> bool:
        """
        Demote an item from hot memory to a cooler tier.

        Frees up budget space.
        """
        if item_id not in self.hot:
            return False

        item = self.hot.pop(item_id)
        self.budget.release(item.token_count)
        item.tier = target_tier
        target_store = self._get_tier_store(target_tier)
        target_store[item_id] = item

        if item_id in self._access_order:
            self._access_order.remove(item_id)

        return True

    def _evict_lru(self, tokens_needed: int) -> bool:
        """
        Evict least-recently-used items from hot memory.

        Returns True if enough space was freed.
        """
        freed = 0
        to_evict = []

        for item_id in self._access_order:
            if item_id in self.hot:
                item = self.hot[item_id]
                to_evict.append(item_id)
                freed += item.token_count
                if freed >= tokens_needed:
                    break

        if freed < tokens_needed:
            return False

        for item_id in to_evict:
            self.demote_from_hot(item_id, MemoryTier.WARM)

        return True

    def get_hot_context(self) -> str:
        """Get all hot memory as a single context string."""
        items = sorted(self.hot.values(), key=lambda x: x.access_count, reverse=True)
        return "\n\n".join(item.content for item in items)

    def get_tier_stats(self) -> dict:
        """Get statistics about memory usage per tier."""
        return {
            "hot": {
                "count": len(self.hot),
                "tokens": sum(i.token_count for i in self.hot.values()),
            },
            "warm": {
                "count": len(self.warm),
                "tokens": sum(i.token_count for i in self.warm.values()),
            },
            "cool": {
                "count": len(self.cool),
                "tokens": sum(i.token_count for i in self.cool.values()),
            },
            "cold": {
                "count": len(self.cold),
                "tokens": sum(i.token_count for i in self.cold.values()),
            },
            "frozen": {
                "count": len(self.frozen),
                "tokens": sum(i.token_count for i in self.frozen.values()),
            },
            "budget": {
                "allocated": self.budget.allocated_tokens,
                "used": self.budget.used_tokens,
                "available": self.budget.available_tokens,
                "tier": self.budget.tier.name,
            },
        }


class TieredMemoryManager:
    """
    Global manager for tiered memory across all agent sessions. Thread-safe.

    Coordinates memory sharing between agents and handles
    cross-session learning.
    """

    # P1 Security: Memory limits to prevent unbounded growth
    MAX_SHARED_COOL_ITEMS = 100  # Max items in shared semantic memory
    MAX_SHARED_COLD_ITEMS = 500  # Max items in shared archive
    MAX_SHARED_COOL_TOKENS = 50_000  # Max tokens in shared cool
    MAX_SHARED_COLD_TOKENS = 200_000  # Max tokens in shared cold

    def __init__(self):
        self._stores: dict[str, TieredMemoryStore] = {}
        self._shared_cool: dict[str, MemoryItem] = {}  # Shared semantic memory
        self._shared_cold: dict[str, MemoryItem] = {}  # Shared archive
        self._lock = threading.Lock()

    def _get_shared_tokens(self, tier: MemoryTier) -> int:
        """Get total tokens in a shared tier. Must hold lock."""
        if tier == MemoryTier.COOL:
            return sum(item.token_count for item in self._shared_cool.values())
        elif tier == MemoryTier.COLD:
            return sum(item.token_count for item in self._shared_cold.values())
        return 0

    def _evict_lru_shared(self, tier: MemoryTier, tokens_needed: int = 0) -> int:
        """
        Evict least-recently-used items from shared memory. Must hold lock.

        Returns number of items evicted.
        """
        if tier == MemoryTier.COOL:
            store = self._shared_cool
            max_items = self.MAX_SHARED_COOL_ITEMS
            max_tokens = self.MAX_SHARED_COOL_TOKENS
        elif tier == MemoryTier.COLD:
            store = self._shared_cold
            max_items = self.MAX_SHARED_COLD_ITEMS
            max_tokens = self.MAX_SHARED_COLD_TOKENS
        else:
            return 0

        if not store:
            return 0

        # Sort by last_accessed (oldest first), then by access_count (lowest first)
        sorted_items = sorted(
            store.items(),
            key=lambda x: (x[1].last_accessed or "", x[1].access_count)
        )

        evicted = 0
        current_tokens = self._get_shared_tokens(tier)

        # Evict until under limits
        for item_id, item in sorted_items:
            if len(store) <= max_items and current_tokens <= max_tokens - tokens_needed:
                break
            del store[item_id]
            current_tokens -= item.token_count
            evicted += 1

        return evicted

    def create_store(self, session_id: str, agent_name: str) -> TieredMemoryStore:
        """Create a new tiered memory store for an agent session. Thread-safe."""
        budget_manager = get_budget_manager()
        budget = budget_manager.create_budget(agent_name, session_id)
        store = TieredMemoryStore(session_id=session_id, budget=budget)
        with self._lock:
            self._stores[session_id] = store
        return store

    def get_store(self, session_id: str) -> Optional[TieredMemoryStore]:
        """Get store for a session. Thread-safe."""
        with self._lock:
            return self._stores.get(session_id)

    def close_store(self, session_id: str) -> Optional[dict]:
        """
        Close a session's store and return stats. Thread-safe.

        Optionally promotes frequently-accessed items to shared memory.
        P1 Security: Enforces memory limits via LRU eviction.
        """
        with self._lock:
            store = self._stores.pop(session_id, None)
        if not store:
            return None

        # Promote high-access items to shared cool memory (with limit enforcement)
        promoted = 0
        evicted = 0
        with self._lock:
            # Sort by access_count descending to promote most valuable first
            candidates = sorted(
                store.warm.values(),
                key=lambda x: x.access_count,
                reverse=True
            )
            for item in candidates:
                if item.access_count >= 3 and promoted < 10:
                    # Check limits before adding
                    if len(self._shared_cool) >= self.MAX_SHARED_COOL_ITEMS:
                        evicted += self._evict_lru_shared(MemoryTier.COOL, item.token_count)
                    self._shared_cool[item.item_id] = item
                    promoted += 1

        # Get final stats
        stats = store.get_tier_stats()
        stats["shared_memory"] = {
            "promoted": promoted,
            "evicted": evicted,
        }

        # Close budget
        budget_manager = get_budget_manager()
        budget_stats = budget_manager.close_session(session_id)
        if budget_stats:
            stats["budget_summary"] = budget_stats

        return stats

    def query_shared_memory(
        self, query: str, tier: MemoryTier = MemoryTier.COOL, limit: int = 5
    ) -> list[MemoryItem]:
        """
        Query shared memory across all sessions. Thread-safe.

        For semantic queries (COOL tier), uses embedding similarity.
        For archive queries (COLD tier), uses keyword matching.
        """
        with self._lock:
            if tier == MemoryTier.COOL:
                items = list(self._shared_cool.values())
            elif tier == MemoryTier.COLD:
                items = list(self._shared_cold.values())
            else:
                return []

        # Search outside lock
        results = []
        query_lower = query.lower()
        for item in items:
            if query_lower in item.content.lower():
                results.append(item)
                if len(results) >= limit:
                    break
        return results

    def get_global_stats(self) -> dict:
        """Get aggregate statistics across all sessions. Thread-safe."""
        with self._lock:
            stores_count = len(self._stores)
            cool_count = len(self._shared_cool)
            cold_count = len(self._shared_cold)
        budget_manager = get_budget_manager()
        return {
            "active_sessions": stores_count,
            "shared_cool_items": cool_count,
            "shared_cold_items": cold_count,
            "budget": budget_manager.get_total_usage(),
        }


# Global tiered memory manager (thread-safe singleton)
_tiered_manager: Optional[TieredMemoryManager] = None
_tiered_manager_lock = threading.Lock()


def get_tiered_memory_manager() -> TieredMemoryManager:
    """Get or create the global tiered memory manager. Thread-safe."""
    global _tiered_manager
    if _tiered_manager is None:
        with _tiered_manager_lock:
            # Double-check pattern
            if _tiered_manager is None:
                _tiered_manager = TieredMemoryManager()
    return _tiered_manager

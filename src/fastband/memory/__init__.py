"""
Fastband Memory System - Cross-session learning for AI agents.

This module provides the Claude Memory System for Fastband, enabling:
- Automatic context editing (relevance-based retrieval)
- Cross-session learning (pattern extraction from resolved tickets)
- Self-healing storage (validation, migration, pruning)
- 5-Tier Memory Architecture (Hot → Frozen)
- Pre-emptive handoffs at 60%/80% token thresholds
- Lazy Bible loading for 70%+ token savings

Usage:
    from fastband.memory import get_memory_manager, get_tiered_memory_manager

    # Traditional memory manager
    manager = get_memory_manager()
    session = manager.create_session("Agent1")
    results = manager.query_memories("CSS dark mode bug", session=session)

    # Tiered memory system (new)
    from fastband.memory import get_tiered_memory_manager, get_budget_manager

    tiered = get_tiered_memory_manager()
    store = tiered.create_store("session_123", "FB_Agent1")

    # Budget-aware operations
    budget = get_budget_manager()
    agent_budget = budget.get_budget("session_123")
    if agent_budget.should_handoff:
        # Prepare handoff at 60% threshold
        pass
"""

from fastband.memory.manager import MemoryManager, get_memory_manager
from fastband.memory.models import FixPattern, SessionContext, TicketMemory

# New tiered memory architecture
from fastband.memory.budget import (
    TokenBudget,
    BudgetTier,
    BudgetManager,
    get_budget_manager,
)
from fastband.memory.tiers import (
    MemoryTier,
    MemoryItem,
    TieredMemoryStore,
    TieredMemoryManager,
    get_tiered_memory_manager,
)
from fastband.memory.loader import (
    LazyBibleLoader,
    BibleSection,
    get_bible_loader,
    close_bible_loader,
)
from fastband.memory.handoff import (
    HandoffPacket,
    HandoffReason,
    HandoffPriority,
    HandoffManager,
    get_handoff_manager,
)

__all__ = [
    # Original exports
    "MemoryManager",
    "get_memory_manager",
    "TicketMemory",
    "SessionContext",
    "FixPattern",
    # Budget system
    "TokenBudget",
    "BudgetTier",
    "BudgetManager",
    "get_budget_manager",
    # Tiered memory
    "MemoryTier",
    "MemoryItem",
    "TieredMemoryStore",
    "TieredMemoryManager",
    "get_tiered_memory_manager",
    # Lazy loading
    "LazyBibleLoader",
    "BibleSection",
    "get_bible_loader",
    "close_bible_loader",
    # Handoff system
    "HandoffPacket",
    "HandoffReason",
    "HandoffPriority",
    "HandoffManager",
    "get_handoff_manager",
]

"""
Fastband Core Events - Domain event models.

This module provides pure domain models for event-driven communication.
These models are protocol-agnostic and reusable by both Dev and Enterprise.

Architecture Rules:
- No side effects on import
- No framework-specific imports
- No database driver imports
- No environment file loading
- No logging initialization

Usage:
    from fastband_core.events import DomainEvent, EventMetadata

    event = DomainEvent(
        type="ticket.created",
        data={"ticket_id": "123"},
        metadata=EventMetadata(source="my-service"),
    )
"""

from fastband_core.events.model import (
    CommonEventTypes,
    DomainEvent,
    EventCategory,
    EventEnvelope,
    EventMetadata,
    EventPriority,
    TypedEvent,
)

__all__ = [
    # Core types
    "EventPriority",
    "EventCategory",
    "EventMetadata",
    "DomainEvent",
    "TypedEvent",
    "EventEnvelope",
    # Utilities
    "CommonEventTypes",
]

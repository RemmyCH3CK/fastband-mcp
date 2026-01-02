"""
Fastband Core Audit - Audit domain models.

This module provides pure domain models for audit logging and compliance.
These models are designed for append-only storage and security-sensitive
operations.

Architecture Rules:
- No side effects on import
- No framework-specific imports
- No database driver imports
- No environment file loading
- No logging initialization
- All models are immutable

Usage:
    from fastband_core.audit import AuditRecord, AuditActor, AuditCategory

    record = AuditRecord.create(
        event_type="auth:login",
        action="authenticate",
        actor=AuditActor(actor_id="user123"),
        category=AuditCategory.AUTHENTICATION,
    )
"""

from fastband_core.audit.model import (
    AuditActor,
    AuditCategory,
    AuditEventTypes,
    AuditOutcome,
    AuditRecord,
    AuditResource,
    AuditSeverity,
)

__all__ = [
    # Core types
    "AuditSeverity",
    "AuditCategory",
    "AuditOutcome",
    "AuditActor",
    "AuditResource",
    "AuditRecord",
    # Constants
    "AuditEventTypes",
]

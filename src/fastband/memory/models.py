"""
Memory data models for Claude Memory System.

Ported from Fastband_MCP/memory_manager.py
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Set


@dataclass
class TicketMemory:
    """Condensed memory of a resolved ticket."""

    ticket_id: str
    app: str
    app_version: Optional[str]
    title: str
    problem_summary: str
    solution_summary: str
    files_modified: List[str]
    keywords: List[str]
    ticket_type: str  # Bug, Feature, Enhancement, etc.

    # Metadata for relevance scoring
    resolved_date: str
    access_count: int = 0
    last_accessed: Optional[str] = None
    relevance_score: float = 1.0

    # Cross-session learning data
    similar_tickets: List[str] = field(default_factory=list)
    fix_pattern_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TicketMemory":
        return cls(
            ticket_id=data["ticket_id"],
            app=data["app"],
            app_version=data.get("app_version"),
            title=data["title"],
            problem_summary=data["problem_summary"],
            solution_summary=data["solution_summary"],
            files_modified=data.get("files_modified", []),
            keywords=data.get("keywords", []),
            ticket_type=data.get("ticket_type", "Unknown"),
            resolved_date=data["resolved_date"],
            access_count=data.get("access_count", 0),
            last_accessed=data.get("last_accessed"),
            relevance_score=data.get("relevance_score", 1.0),
            similar_tickets=data.get("similar_tickets", []),
            fix_pattern_id=data.get("fix_pattern_id"),
        )


@dataclass
class FixPattern:
    """A learned pattern for fixing common issues."""

    pattern_id: str
    name: str
    description: str

    # Pattern matching
    error_signatures: List[str]  # Regex patterns for error detection
    file_patterns: List[str]  # Files commonly involved
    keyword_triggers: List[str]  # Keywords that trigger this pattern

    # Solution template
    solution_template: str
    common_files_to_check: List[str]
    example_ticket_ids: List[str]

    # Learning metadata
    occurrence_count: int = 0
    success_rate: float = 1.0
    last_used: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FixPattern":
        return cls(**data)


@dataclass
class SessionContext:
    """Tracks memory usage within a session for context editing."""

    session_id: str
    agent_name: str
    started_at: str

    # Track what's been loaded to avoid repetition
    loaded_memories: Set[str] = field(default_factory=set)
    loaded_patterns: Set[str] = field(default_factory=set)

    # Current working context
    current_app: Optional[str] = None
    current_ticket: Optional[str] = None

    # Accumulated session knowledge
    session_discoveries: List[Dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["loaded_memories"] = list(self.loaded_memories)
        data["loaded_patterns"] = list(self.loaded_patterns)
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SessionContext":
        ctx = cls(
            session_id=data["session_id"],
            agent_name=data["agent_name"],
            started_at=data["started_at"],
            current_app=data.get("current_app"),
            current_ticket=data.get("current_ticket"),
            session_discoveries=data.get("session_discoveries", []),
        )
        ctx.loaded_memories = set(data.get("loaded_memories", []))
        ctx.loaded_patterns = set(data.get("loaded_patterns", []))
        return ctx

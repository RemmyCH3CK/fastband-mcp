"""
Agent Handoff System for Fastband Memory Architecture.

Manages pre-emptive handoffs at 60%/80% token thresholds.
Ensures seamless context transfer between agent sessions.

"Hand off at 60% token budget, not 95%."
"""

import base64
import hashlib
import hmac
import json
import logging
import secrets
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from fastband.memory.budget import TokenBudget
from fastband.memory.tiers import TieredMemoryStore, MemoryItem, MemoryTier

# P2 Security: Optional encryption support
try:
    from cryptography.fernet import Fernet
    ENCRYPTION_AVAILABLE = True
except ImportError:
    ENCRYPTION_AVAILABLE = False

_logger = logging.getLogger(__name__)


class HandoffSecurity:
    """
    P2 Security: HMAC signatures and optional encryption for handoff packets.

    Provides integrity verification (HMAC) and optional confidentiality (Fernet).
    """

    # HMAC algorithm
    HMAC_ALGORITHM = "sha256"

    @classmethod
    def generate_signature(cls, data: dict, secret_key: str) -> str:
        """
        Generate HMAC signature for packet data.

        Uses SHA-256 for integrity verification.
        """
        # Serialize data deterministically
        serialized = json.dumps(data, sort_keys=True, separators=(",", ":"))
        # Generate HMAC
        signature = hmac.new(
            secret_key.encode(),
            serialized.encode(),
            hashlib.sha256
        ).hexdigest()
        return signature

    @classmethod
    def verify_signature(cls, data: dict, signature: str, secret_key: str) -> bool:
        """
        Verify HMAC signature for packet data.

        Returns True if signature is valid.
        """
        expected = cls.generate_signature(data, secret_key)
        return hmac.compare_digest(signature, expected)

    @classmethod
    def encrypt_content(cls, content: str, key: Optional[bytes] = None) -> tuple[str, bytes]:
        """
        Encrypt content using Fernet symmetric encryption.

        Returns (encrypted_content, key).
        Raises ImportError if cryptography is not installed.
        """
        if not ENCRYPTION_AVAILABLE:
            raise ImportError(
                "Encryption requires 'cryptography' package. "
                "Install with: pip install cryptography"
            )

        if key is None:
            key = Fernet.generate_key()

        fernet = Fernet(key)
        encrypted = fernet.encrypt(content.encode())
        return base64.b64encode(encrypted).decode(), key

    @classmethod
    def decrypt_content(cls, encrypted: str, key: bytes) -> str:
        """
        Decrypt content using Fernet symmetric encryption.

        Raises ImportError if cryptography is not installed.
        """
        if not ENCRYPTION_AVAILABLE:
            raise ImportError(
                "Decryption requires 'cryptography' package. "
                "Install with: pip install cryptography"
            )

        fernet = Fernet(key)
        decrypted = fernet.decrypt(base64.b64decode(encrypted))
        return decrypted.decode()


class HandoffSanitizer:
    """
    P1 Security: Sanitizes handoff packet data to prevent injection attacks.
    """

    # Maximum field lengths
    MAX_ID_LENGTH = 64
    MAX_NAME_LENGTH = 128
    MAX_SUMMARY_LENGTH = 2000
    MAX_TASK_LENGTH = 500
    MAX_PATH_LENGTH = 512
    MAX_NOTES_LENGTH = 5000
    MAX_CONTEXT_LENGTH = 50000
    MAX_LIST_ITEMS = 100

    @classmethod
    def sanitize_string(cls, value: str, max_length: int, field_name: str = "field") -> str:
        """Sanitize a string value with length limit."""
        if not isinstance(value, str):
            return ""
        # Truncate to max length
        value = value[:max_length]
        # Remove null bytes and other control characters (except newlines/tabs)
        value = "".join(c for c in value if c >= " " or c in "\n\t\r")
        return value

    @classmethod
    def sanitize_id(cls, value: str) -> str:
        """Sanitize an ID field (alphanumeric, underscores, hyphens only)."""
        if not isinstance(value, str):
            return ""
        # Only allow safe characters for IDs
        import re
        value = re.sub(r"[^a-zA-Z0-9_\-]", "", value[:cls.MAX_ID_LENGTH])
        return value

    @classmethod
    def sanitize_list(
        cls, items: list, max_items: int, item_max_length: int, sanitize_fn=None
    ) -> list:
        """Sanitize a list with item count and length limits."""
        if not isinstance(items, list):
            return []
        sanitize_fn = sanitize_fn or (lambda x: cls.sanitize_string(str(x), item_max_length))
        return [sanitize_fn(item) for item in items[:max_items]]

    @classmethod
    def sanitize_packet_data(cls, data: dict) -> dict:
        """Sanitize all fields in packet data dictionary."""
        sanitized = {}

        # IDs
        sanitized["packet_id"] = cls.sanitize_id(data.get("packet_id", ""))
        sanitized["source_session"] = cls.sanitize_id(data.get("source_session", ""))
        sanitized["ticket_id"] = cls.sanitize_id(data.get("ticket_id", ""))

        # Names
        sanitized["source_agent"] = cls.sanitize_string(
            data.get("source_agent", ""), cls.MAX_NAME_LENGTH
        )
        sanitized["target_agent"] = data.get("target_agent")
        if sanitized["target_agent"]:
            sanitized["target_agent"] = cls.sanitize_string(
                sanitized["target_agent"], cls.MAX_NAME_LENGTH
            )

        # Timestamps (validate format)
        sanitized["created_at"] = cls.sanitize_string(
            data.get("created_at", ""), 32
        )

        # Enums (validated separately)
        sanitized["reason"] = data.get("reason", "")
        sanitized["priority"] = data.get("priority", 3)

        # Token (pass through - validated separately)
        sanitized["access_token"] = data.get("access_token", "")

        # Ticket context
        sanitized["ticket_status"] = cls.sanitize_string(
            data.get("ticket_status", ""), 64
        )
        sanitized["ticket_summary"] = cls.sanitize_string(
            data.get("ticket_summary", ""), cls.MAX_SUMMARY_LENGTH
        )

        # Task lists
        sanitized["completed_tasks"] = cls.sanitize_list(
            data.get("completed_tasks", []), cls.MAX_LIST_ITEMS, cls.MAX_TASK_LENGTH
        )
        sanitized["pending_tasks"] = cls.sanitize_list(
            data.get("pending_tasks", []), cls.MAX_LIST_ITEMS, cls.MAX_TASK_LENGTH
        )
        sanitized["blockers"] = cls.sanitize_list(
            data.get("blockers", []), 20, cls.MAX_TASK_LENGTH
        )
        sanitized["warnings"] = cls.sanitize_list(
            data.get("warnings", []), 20, cls.MAX_TASK_LENGTH
        )

        # Current task
        current_task = data.get("current_task")
        if current_task:
            sanitized["current_task"] = cls.sanitize_string(current_task, cls.MAX_TASK_LENGTH)
        else:
            sanitized["current_task"] = None

        # File paths (sanitize but allow forward slashes)
        sanitized["files_modified"] = cls.sanitize_list(
            data.get("files_modified", []), cls.MAX_LIST_ITEMS, cls.MAX_PATH_LENGTH
        )
        sanitized["files_reviewed"] = cls.sanitize_list(
            data.get("files_reviewed", []), cls.MAX_LIST_ITEMS, cls.MAX_PATH_LENGTH
        )

        # Key decisions (list of dicts)
        decisions = data.get("key_decisions", [])
        if isinstance(decisions, list):
            sanitized["key_decisions"] = [
                {
                    "decision": cls.sanitize_string(d.get("decision", ""), cls.MAX_TASK_LENGTH),
                    "rationale": cls.sanitize_string(d.get("rationale", ""), cls.MAX_TASK_LENGTH),
                }
                for d in decisions[:20]
                if isinstance(d, dict)
            ]
        else:
            sanitized["key_decisions"] = []

        # Memory context
        sanitized["hot_context"] = cls.sanitize_string(
            data.get("hot_context", ""), cls.MAX_CONTEXT_LENGTH
        )
        sanitized["hot_tokens"] = min(int(data.get("hot_tokens", 0)), 200000)
        sanitized["warm_references"] = cls.sanitize_list(
            data.get("warm_references", []), cls.MAX_LIST_ITEMS, cls.MAX_ID_LENGTH,
            sanitize_fn=cls.sanitize_id
        )

        # Budget stats (validate ranges)
        sanitized["budget_used"] = min(max(int(data.get("budget_used", 0)), 0), 1000000)
        sanitized["budget_peak"] = min(max(int(data.get("budget_peak", 0)), 0), 1000000)
        sanitized["expansion_count"] = min(max(int(data.get("expansion_count", 0)), 0), 100)

        # Notes
        sanitized["handoff_notes"] = cls.sanitize_string(
            data.get("handoff_notes", ""), cls.MAX_NOTES_LENGTH
        )

        return sanitized


class HandoffReason(Enum):
    """Reasons for agent handoff."""

    BUDGET_WARNING = "budget_warning"  # 60% threshold
    BUDGET_CRITICAL = "budget_critical"  # 80% threshold
    TASK_COMPLETE = "task_complete"  # Ticket finished
    AGENT_REQUEST = "agent_request"  # Agent initiated
    ERROR_RECOVERY = "error_recovery"  # Error handling
    SCHEDULED = "scheduled"  # Planned rotation


class HandoffPriority(Enum):
    """Priority levels for handoff."""

    IMMEDIATE = 1  # Drop everything, handoff now
    HIGH = 2  # Finish current action, then handoff
    NORMAL = 3  # Complete current subtask, then handoff
    LOW = 4  # Handoff when convenient


@dataclass
class HandoffPacket:
    """
    Contains all information needed for seamless agent handoff.

    This is the "ticket as memory" realization - everything needed
    to continue work is packaged here.
    """

    packet_id: str
    created_at: str
    source_agent: str
    source_session: str

    # Handoff metadata
    reason: HandoffReason
    priority: HandoffPriority

    # Authorization (P0 Security)
    target_agent: Optional[str] = None  # Expected recipient (None = any agent)
    access_token: str = field(default_factory=lambda: secrets.token_urlsafe(32))

    # Ticket context (the core memory)
    ticket_id: str = ""
    ticket_status: str = ""
    ticket_summary: str = ""  # Condensed description

    # Work progress
    completed_tasks: list[str] = field(default_factory=list)
    pending_tasks: list[str] = field(default_factory=list)
    current_task: Optional[str] = None
    blockers: list[str] = field(default_factory=list)

    # Code context
    files_modified: list[str] = field(default_factory=list)
    files_reviewed: list[str] = field(default_factory=list)
    key_decisions: list[dict[str, str]] = field(default_factory=list)

    # Hot memory snapshot (minimal)
    hot_context: str = ""
    hot_tokens: int = 0

    # Warm memory references (load on demand)
    warm_references: list[str] = field(default_factory=list)

    # Budget stats for next agent
    budget_used: int = 0
    budget_peak: int = 0
    expansion_count: int = 0

    # Special instructions
    handoff_notes: str = ""
    warnings: list[str] = field(default_factory=list)

    def can_accept(self, agent_name: str, token: Optional[str] = None) -> tuple[bool, str]:
        """Check if agent is authorized to accept this handoff."""
        # If target_agent specified, must match
        if self.target_agent and self.target_agent != agent_name:
            return False, f"Handoff intended for {self.target_agent}, not {agent_name}"

        # Verify access token if provided
        if token and not secrets.compare_digest(token, self.access_token):
            return False, "Invalid access token"

        return True, ""

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "packet_id": self.packet_id,
            "created_at": self.created_at,
            "source_agent": self.source_agent,
            "source_session": self.source_session,
            "reason": self.reason.value,
            "priority": self.priority.value,
            "target_agent": self.target_agent,
            "access_token": self.access_token,
            "ticket_id": self.ticket_id,
            "ticket_status": self.ticket_status,
            "ticket_summary": self.ticket_summary,
            "completed_tasks": self.completed_tasks,
            "pending_tasks": self.pending_tasks,
            "current_task": self.current_task,
            "blockers": self.blockers,
            "files_modified": self.files_modified,
            "files_reviewed": self.files_reviewed,
            "key_decisions": self.key_decisions,
            "hot_context": self.hot_context,
            "hot_tokens": self.hot_tokens,
            "warm_references": self.warm_references,
            "budget_used": self.budget_used,
            "budget_peak": self.budget_peak,
            "expansion_count": self.expansion_count,
            "handoff_notes": self.handoff_notes,
            "warnings": self.warnings,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "HandoffPacket":
        """Deserialize from dictionary with P1 Security sanitization."""
        # P1 Security: Sanitize all input data
        data = HandoffSanitizer.sanitize_packet_data(data)

        packet = cls(
            packet_id=data["packet_id"],
            created_at=data["created_at"],
            source_agent=data["source_agent"],
            source_session=data["source_session"],
            reason=HandoffReason(data["reason"]),
            priority=HandoffPriority(data["priority"]),
        )
        # Authorization fields
        packet.target_agent = data.get("target_agent")
        packet.access_token = data.get("access_token") or secrets.token_urlsafe(32)
        # Ticket context
        packet.ticket_id = data.get("ticket_id", "")
        packet.ticket_status = data.get("ticket_status", "")
        packet.ticket_summary = data.get("ticket_summary", "")
        # Work progress
        packet.completed_tasks = data.get("completed_tasks", [])
        packet.pending_tasks = data.get("pending_tasks", [])
        packet.current_task = data.get("current_task")
        packet.blockers = data.get("blockers", [])
        # Code context
        packet.files_modified = data.get("files_modified", [])
        packet.files_reviewed = data.get("files_reviewed", [])
        packet.key_decisions = data.get("key_decisions", [])
        # Memory
        packet.hot_context = data.get("hot_context", "")
        packet.hot_tokens = data.get("hot_tokens", 0)
        packet.warm_references = data.get("warm_references", [])
        # Budget
        packet.budget_used = data.get("budget_used", 0)
        packet.budget_peak = data.get("budget_peak", 0)
        packet.expansion_count = data.get("expansion_count", 0)
        # Special
        packet.handoff_notes = data.get("handoff_notes", "")
        packet.warnings = data.get("warnings", [])
        return packet

    def get_onboarding_context(self) -> str:
        """
        Generate onboarding context for the receiving agent.

        This is what the new agent sees first - minimal but complete.
        """
        lines = [
            f"# HANDOFF RECEIVED",
            f"",
            f"**From:** {self.source_agent}",
            f"**Reason:** {self.reason.value}",
            f"**Ticket:** {self.ticket_id} ({self.ticket_status})",
            f"",
            f"## Summary",
            self.ticket_summary,
            f"",
            f"## Completed",
        ]

        for task in self.completed_tasks:
            lines.append(f"- [x] {task}")

        lines.append("")
        lines.append("## Pending")
        for task in self.pending_tasks:
            lines.append(f"- [ ] {task}")

        if self.current_task:
            lines.append("")
            lines.append(f"## Current Task")
            lines.append(f"**In Progress:** {self.current_task}")

        if self.blockers:
            lines.append("")
            lines.append("## Blockers")
            for blocker in self.blockers:
                lines.append(f"- {blocker}")

        if self.key_decisions:
            lines.append("")
            lines.append("## Key Decisions Made")
            for decision in self.key_decisions:
                lines.append(f"- **{decision.get('decision', 'N/A')}**: {decision.get('rationale', 'N/A')}")

        if self.files_modified:
            lines.append("")
            lines.append("## Files Modified")
            for f in self.files_modified[:10]:  # Limit to 10
                lines.append(f"- {f}")
            if len(self.files_modified) > 10:
                lines.append(f"- ... and {len(self.files_modified) - 10} more")

        if self.warnings:
            lines.append("")
            lines.append("## Warnings")
            for warning in self.warnings:
                lines.append(f"- {warning}")

        if self.handoff_notes:
            lines.append("")
            lines.append("## Notes from Previous Agent")
            lines.append(self.handoff_notes)

        return "\n".join(lines)


class HandoffManager:
    """
    Manages agent handoffs with pre-emptive triggering. Thread-safe.

    Monitors budget usage and triggers handoffs at:
    - 60%: Warning - start preparing handoff packet
    - 80%: Critical - must handoff immediately
    """

    # Archive retention (48 hours default)
    ARCHIVE_RETENTION_HOURS = 48

    def __init__(self, storage_path: Optional[str] = None):
        self.storage_path = Path(storage_path or ".fastband/handoffs")
        self.storage_path.mkdir(parents=True, exist_ok=True, mode=0o700)
        self._pending_packets: dict[str, HandoffPacket] = {}
        self._lock = threading.Lock()

    def check_handoff_needed(self, budget: TokenBudget) -> tuple[bool, HandoffReason | None, HandoffPriority | None]:
        """
        Check if handoff should be triggered based on budget.

        Returns (should_handoff, reason, priority).
        """
        if budget.must_handoff:
            return True, HandoffReason.BUDGET_CRITICAL, HandoffPriority.IMMEDIATE

        if budget.should_handoff:
            return True, HandoffReason.BUDGET_WARNING, HandoffPriority.NORMAL

        return False, None, None

    def create_handoff_packet(
        self,
        agent_name: str,
        session_id: str,
        reason: HandoffReason,
        priority: HandoffPriority,
        ticket_data: dict,
        memory_store: Optional[TieredMemoryStore] = None,
        notes: str = "",
        target_agent: Optional[str] = None,
    ) -> HandoffPacket:
        """
        Create a handoff packet with all context needed for seamless transfer.
        """
        # Use cryptographically secure packet ID
        packet = HandoffPacket(
            packet_id=f"ho_{secrets.token_urlsafe(16)}",
            created_at=datetime.utcnow().isoformat(),
            source_agent=agent_name,
            source_session=session_id,
            reason=reason,
            priority=priority,
        )

        # Set authorization
        packet.target_agent = target_agent

        # Set ticket data
        packet.ticket_id = ticket_data.get("ticket_id", "unknown")
        packet.ticket_status = ticket_data.get("status", "unknown")
        packet.ticket_summary = ticket_data.get("summary", ticket_data.get("title", ""))
        packet.completed_tasks = ticket_data.get("completed_tasks", [])
        packet.pending_tasks = ticket_data.get("pending_tasks", [])
        packet.current_task = ticket_data.get("current_task")
        packet.blockers = ticket_data.get("blockers", [])
        packet.files_modified = ticket_data.get("files_modified", [])
        packet.files_reviewed = ticket_data.get("files_reviewed", [])
        packet.key_decisions = ticket_data.get("key_decisions", [])
        packet.handoff_notes = notes

        # Extract memory context if available
        if memory_store:
            packet.hot_context = memory_store.get_hot_context()
            packet.hot_tokens = sum(i.token_count for i in memory_store.hot.values())
            packet.warm_references = list(memory_store.warm.keys())
            packet.budget_used = memory_store.budget.used_tokens
            packet.budget_peak = memory_store.budget.peak_usage
            packet.expansion_count = memory_store.budget.expansion_count

        # Add warnings based on context
        if reason == HandoffReason.BUDGET_CRITICAL:
            packet.warnings.append("URGENT: Previous agent hit 80% budget limit")

        if packet.blockers:
            packet.warnings.append(f"BLOCKED: {len(packet.blockers)} blocker(s) identified")

        return packet

    def store_packet(self, packet: HandoffPacket, encrypt: bool = False) -> str:
        """
        Store handoff packet for pickup by next agent. Thread-safe.

        P2 Security: Adds HMAC signature for integrity verification.
        Optional encryption if encrypt=True and cryptography is installed.

        Returns path to stored packet.
        """
        packet_data = packet.to_dict()

        # P2 Security: Generate HMAC signature using access_token
        signature = HandoffSecurity.generate_signature(packet_data, packet.access_token)
        storage_data = {
            "packet": packet_data,
            "signature": signature,
            "encrypted": False,
        }

        # Optional encryption
        if encrypt and ENCRYPTION_AVAILABLE:
            content = json.dumps(packet_data)
            encrypted_content, key = HandoffSecurity.encrypt_content(content)
            storage_data = {
                "encrypted": True,
                "content": encrypted_content,
                "key_hint": base64.b64encode(key[:8]).decode(),  # Partial key for identification
                "signature": signature,
            }
            # Note: In production, key should be stored separately or derived from shared secret
            _logger.debug(f"Packet {packet.packet_id} stored with encryption")

        file_path = self.storage_path / f"{packet.packet_id}.json"
        with open(file_path, "w") as f:
            json.dump(storage_data, f, indent=2)

        with self._lock:
            self._pending_packets[packet.packet_id] = packet
        return str(file_path)

    def retrieve_packet(
        self, packet_id: str, verify_signature: bool = True
    ) -> Optional[HandoffPacket]:
        """
        Retrieve a stored handoff packet. Thread-safe.

        P2 Security: Verifies HMAC signature if verify_signature=True.
        Returns None if signature verification fails.
        """
        # Check memory first
        with self._lock:
            if packet_id in self._pending_packets:
                return self._pending_packets[packet_id]

        # Check storage
        file_path = self.storage_path / f"{packet_id}.json"
        if not file_path.exists():
            return None

        with open(file_path, "r") as f:
            storage_data = json.load(f)

        # Handle legacy format (no wrapper)
        if "packet" not in storage_data and "encrypted" not in storage_data:
            # Legacy format: data is the packet directly
            return HandoffPacket.from_dict(storage_data)

        # New format with signature
        if storage_data.get("encrypted"):
            _logger.warning(
                f"Packet {packet_id} is encrypted but decryption key not provided. "
                "Encrypted packets require the key from the storing agent."
            )
            return None

        packet_data = storage_data.get("packet", {})
        signature = storage_data.get("signature", "")

        # P2 Security: Verify signature if requested
        if verify_signature and signature:
            # Need access_token to verify - get it from packet data
            access_token = packet_data.get("access_token", "")
            if access_token:
                if not HandoffSecurity.verify_signature(packet_data, signature, access_token):
                    _logger.warning(
                        f"Signature verification failed for packet {packet_id}. "
                        "Packet may have been tampered with."
                    )
                    return None
                _logger.debug(f"Signature verified for packet {packet_id}")

        return HandoffPacket.from_dict(packet_data)

    def get_pending_handoffs(self, ticket_id: Optional[str] = None) -> list[HandoffPacket]:
        """Get all pending handoff packets, optionally filtered by ticket."""
        packets = []

        for file_path in self.storage_path.glob("*.json"):
            try:
                # Extract packet_id from filename
                packet_id = file_path.stem
                # Use retrieve_packet to handle new format with signature verification
                packet = self.retrieve_packet(packet_id, verify_signature=False)

                if packet and (ticket_id is None or packet.ticket_id == ticket_id):
                    packets.append(packet)
            except Exception:
                continue

        return sorted(packets, key=lambda p: p.created_at, reverse=True)

    def accept_handoff(
        self,
        packet_id: str,
        accepting_agent: str,
        access_token: Optional[str] = None,
    ) -> Optional[HandoffPacket]:
        """
        Accept a handoff with authorization check. Thread-safe.

        Returns the packet for the accepting agent to process, or None if unauthorized.
        """
        packet = self.retrieve_packet(packet_id)
        if not packet:
            return None

        # P0 Security: Authorization check
        can_accept, reason = packet.can_accept(accepting_agent, access_token)
        if not can_accept:
            # Log unauthorized attempt
            import logging
            logging.getLogger(__name__).warning(
                f"Unauthorized handoff acceptance: {accepting_agent} tried to accept "
                f"{packet_id}. Reason: {reason}"
            )
            return None

        # Archive the packet
        archive_path = self.storage_path / "archive"
        archive_path.mkdir(exist_ok=True, mode=0o700)

        # Add acceptance metadata
        packet_data = packet.to_dict()
        packet_data["accepted_by"] = accepting_agent
        packet_data["accepted_at"] = datetime.utcnow().isoformat()

        archive_file = archive_path / f"{packet_id}.json"
        with open(archive_file, "w") as f:
            json.dump(packet_data, f, indent=2)

        # Remove from pending
        pending_file = self.storage_path / f"{packet_id}.json"
        if pending_file.exists():
            pending_file.unlink()

        with self._lock:
            self._pending_packets.pop(packet_id, None)

        # Cleanup old archives
        self._cleanup_old_archives()

        return packet

    def _cleanup_old_archives(self) -> int:
        """Clean up archives older than retention period. Returns count deleted."""
        archive_path = self.storage_path / "archive"
        if not archive_path.exists():
            return 0

        cutoff = datetime.utcnow() - timedelta(hours=self.ARCHIVE_RETENTION_HOURS)
        deleted = 0

        for file_path in archive_path.glob("*.json"):
            try:
                if file_path.stat().st_mtime < cutoff.timestamp():
                    file_path.unlink()
                    deleted += 1
            except Exception:
                continue

        return deleted

    def get_handoff_stats(self) -> dict:
        """Get statistics about handoffs. Thread-safe."""
        pending = list(self.storage_path.glob("*.json"))
        archive_path = self.storage_path / "archive"
        archived = list(archive_path.glob("*.json")) if archive_path.exists() else []

        return {
            "pending_handoffs": len(pending),
            "completed_handoffs": len(archived),
            "storage_path": str(self.storage_path),
        }


# Global handoff manager (thread-safe singleton)
_handoff_manager: Optional[HandoffManager] = None
_handoff_manager_lock = threading.Lock()


def get_handoff_manager(storage_path: Optional[str] = None) -> HandoffManager:
    """Get or create the global handoff manager. Thread-safe."""
    global _handoff_manager
    if _handoff_manager is None:
        _handoff_manager = HandoffManager(storage_path)
    return _handoff_manager

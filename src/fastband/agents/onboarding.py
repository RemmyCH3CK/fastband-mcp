"""
Agent Onboarding System.

Forces AI agents to read and acknowledge the Agent Bible before working
on the project. This ensures all agents follow project-specific rules.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class OnboardingRequirement:
    """A document that must be acknowledged during onboarding."""

    path: str
    description: str
    required: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "description": self.description,
            "required": self.required,
        }


@dataclass
class AgentSession:
    """Tracks an agent's onboarding session."""

    agent_name: str
    session_id: str
    started_at: str
    completed: bool = False
    completed_at: str | None = None
    docs_acknowledged: list[str] = field(default_factory=list)
    codebase_examined: bool = False
    platform_understanding: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_name": self.agent_name,
            "session_id": self.session_id,
            "started_at": self.started_at,
            "completed": self.completed,
            "completed_at": self.completed_at,
            "docs_acknowledged": self.docs_acknowledged,
            "codebase_examined": self.codebase_examined,
            "platform_understanding": self.platform_understanding,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentSession":
        return cls(**data)


class AgentOnboarding:
    """
    Manages agent onboarding to ensure they read and follow the Agent Bible.

    Workflow:
    1. Agent calls start_session() when starting work
    2. Agent receives list of required documents (Agent Bible, etc.)
    3. Agent reads each document and calls acknowledge_doc()
    4. Agent calls complete_onboarding() to finish
    5. Only after completion can agent perform work

    This ensures:
    - All agents read the project rules (Agent Bible)
    - Agents understand project-specific conventions
    - No "rogue" agents that ignore rules
    """

    def __init__(
        self,
        project_path: Path,
        session_file: Path | None = None,
    ):
        """
        Initialize the onboarding system.

        Args:
            project_path: Root path of the project
            session_file: Path to session tracking file
        """
        self.project_path = Path(project_path).resolve()
        self.fastband_dir = self.project_path / ".fastband"
        self.session_file = session_file or self.fastband_dir / "agent_sessions.json"

        self._sessions: dict[str, AgentSession] = {}
        self._requirements: list[OnboardingRequirement] = []
        self._load_sessions()
        self._build_requirements()

    def _load_sessions(self) -> None:
        """Load existing sessions from file."""
        if self.session_file.exists():
            try:
                data = json.loads(self.session_file.read_text())
                for session_data in data.get("sessions", []):
                    session = AgentSession.from_dict(session_data)
                    self._sessions[session.session_id] = session
            except Exception as e:
                logger.warning(f"Failed to load sessions: {e}")

    def _save_sessions(self) -> None:
        """Save sessions to file."""
        self.session_file.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "sessions": [s.to_dict() for s in self._sessions.values()],
            "last_updated": datetime.utcnow().isoformat() + "Z",
        }
        self.session_file.write_text(json.dumps(data, indent=2))

    def _build_requirements(self) -> None:
        """Build the list of required onboarding documents."""
        # Always require the Agent Bible if it exists
        bible_path = self.fastband_dir / "AGENT_BIBLE.md"
        if bible_path.exists():
            self._requirements.append(
                OnboardingRequirement(
                    path=str(bible_path),
                    description="The Agent Bible - project rules and conventions all agents must follow",
                    required=True,
                )
            )

        # Add any additional required docs
        docs_config = self.fastband_dir / "onboarding_docs.json"
        if docs_config.exists():
            try:
                data = json.loads(docs_config.read_text())
                for doc in data.get("required_docs", []):
                    self._requirements.append(OnboardingRequirement(**doc))
            except Exception as e:
                logger.warning(f"Failed to load onboarding docs config: {e}")

    @property
    def requirements(self) -> list[OnboardingRequirement]:
        """Get the list of onboarding requirements."""
        return self._requirements

    def start_session(
        self,
        agent_name: str,
        context: str | None = None,
    ) -> dict[str, Any]:
        """
        Start a new onboarding session for an agent.

        Args:
            agent_name: Unique identifier for the agent
            context: Optional context (new_ticket, resuming, etc.)

        Returns:
            Dict with session info and required documents
        """
        import uuid

        session_id = (
            f"{agent_name}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        )

        session = AgentSession(
            agent_name=agent_name,
            session_id=session_id,
            started_at=datetime.utcnow().isoformat() + "Z",
        )

        self._sessions[session_id] = session
        self._save_sessions()

        logger.info(f"Started onboarding session for {agent_name}: {session_id}")

        return {
            "success": True,
            "session_id": session_id,
            "agent_name": agent_name,
            "started_at": session.started_at,
            "required_docs": [r.to_dict() for r in self._requirements],
            "message": (
                f"Onboarding session started. You MUST read and acknowledge "
                f"{len(self._requirements)} document(s) before proceeding."
            ),
            "instructions": [
                "1. Read each required document carefully",
                "2. Call acknowledge_doc() for each document after reading",
                "3. Call complete_onboarding() when finished",
                "4. Only after completion can you perform work on this project",
            ],
        }

    def acknowledge_doc(
        self,
        session_id: str,
        doc_path: str,
        summary: str | None = None,
    ) -> dict[str, Any]:
        """
        Acknowledge that an agent has read a document.

        Args:
            session_id: Session identifier from start_session
            doc_path: Path to the document that was read
            summary: Optional summary to verify understanding

        Returns:
            Dict with acknowledgment status
        """
        session = self._sessions.get(session_id)
        if not session:
            return {
                "success": False,
                "error": f"Session not found: {session_id}",
            }

        if session.completed:
            return {
                "success": False,
                "error": "Session already completed",
            }

        # Normalize path for comparison
        normalized_path = str(Path(doc_path).resolve())

        if normalized_path in session.docs_acknowledged:
            return {
                "success": True,
                "message": f"Document already acknowledged: {doc_path}",
                "remaining_docs": self._get_remaining_docs(session),
            }

        session.docs_acknowledged.append(normalized_path)
        self._save_sessions()

        remaining = self._get_remaining_docs(session)

        logger.info(f"Agent {session.agent_name} acknowledged: {doc_path}")

        return {
            "success": True,
            "message": f"Document acknowledged: {Path(doc_path).name}",
            "remaining_docs": remaining,
            "docs_complete": len(remaining) == 0,
        }

    def _get_remaining_docs(self, session: AgentSession) -> list[dict[str, Any]]:
        """Get documents not yet acknowledged."""
        acknowledged_set = set(session.docs_acknowledged)
        remaining = []

        for req in self._requirements:
            if req.required and str(Path(req.path).resolve()) not in acknowledged_set:
                remaining.append(req.to_dict())

        return remaining

    def complete_onboarding(
        self,
        session_id: str,
        codebase_examined: bool = False,
        platform_understanding: str | None = None,
    ) -> dict[str, Any]:
        """
        Complete the onboarding process.

        Args:
            session_id: Session identifier
            codebase_examined: Whether agent examined key codebase files
            platform_understanding: Brief description of understanding

        Returns:
            Dict with completion status
        """
        session = self._sessions.get(session_id)
        if not session:
            return {
                "success": False,
                "error": f"Session not found: {session_id}",
            }

        if session.completed:
            return {
                "success": True,
                "message": "Session already completed",
                "completed_at": session.completed_at,
            }

        # Check all required docs are acknowledged
        remaining = self._get_remaining_docs(session)
        if remaining:
            return {
                "success": False,
                "error": "Cannot complete onboarding - required documents not acknowledged",
                "remaining_docs": remaining,
            }

        session.completed = True
        session.completed_at = datetime.utcnow().isoformat() + "Z"
        session.codebase_examined = codebase_examined
        session.platform_understanding = platform_understanding

        self._save_sessions()

        logger.info(f"Agent {session.agent_name} completed onboarding")

        return {
            "success": True,
            "message": "Onboarding complete. You may now proceed with your work.",
            "agent_name": session.agent_name,
            "session_id": session_id,
            "completed_at": session.completed_at,
        }

    def is_onboarded(self, session_id: str) -> bool:
        """Check if a session has completed onboarding."""
        session = self._sessions.get(session_id)
        return session is not None and session.completed

    def get_session(self, session_id: str) -> AgentSession | None:
        """Get a session by ID."""
        return self._sessions.get(session_id)

    def get_status(self, agent_name: str) -> dict[str, Any]:
        """Get onboarding status for an agent."""
        # Find most recent session for this agent
        agent_sessions = [s for s in self._sessions.values() if s.agent_name == agent_name]

        if not agent_sessions:
            return {
                "agent_name": agent_name,
                "has_session": False,
                "onboarded": False,
                "message": "No onboarding session found. Call start_session() first.",
            }

        # Get most recent
        latest = max(agent_sessions, key=lambda s: s.started_at)

        return {
            "agent_name": agent_name,
            "has_session": True,
            "session_id": latest.session_id,
            "onboarded": latest.completed,
            "started_at": latest.started_at,
            "completed_at": latest.completed_at,
            "docs_acknowledged": latest.docs_acknowledged,
            "remaining_docs": self._get_remaining_docs(latest) if not latest.completed else [],
        }

    def require_onboarding(self, session_id: str) -> None:
        """
        Raise an error if agent is not onboarded.

        Use this to enforce onboarding before critical operations.

        Raises:
            PermissionError: If agent has not completed onboarding
        """
        if not self.is_onboarded(session_id):
            session = self._sessions.get(session_id)
            if not session:
                raise PermissionError(
                    "No valid onboarding session. "
                    "Call start_session() and complete onboarding first."
                )
            remaining = self._get_remaining_docs(session)
            raise PermissionError(
                f"Onboarding not complete. "
                f"You must acknowledge {len(remaining)} more document(s): "
                f"{[Path(r['path']).name for r in remaining]}"
            )


# Global instance
_onboarding: AgentOnboarding | None = None


def get_onboarding(project_path: Path | None = None) -> AgentOnboarding:
    """Get the global onboarding instance."""
    global _onboarding
    if _onboarding is None:
        if project_path is None:
            project_path = Path.cwd()
        _onboarding = AgentOnboarding(project_path=project_path)
    return _onboarding


def reset_onboarding() -> None:
    """Reset the global onboarding instance (for testing)."""
    global _onboarding
    _onboarding = None

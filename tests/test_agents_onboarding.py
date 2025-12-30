"""
Tests for Agent Onboarding System.

These tests verify the onboarding flow that forces agents to read and
acknowledge the Agent Bible before working on projects.
"""

import json
import tempfile
from pathlib import Path

import pytest

from fastband.agents.onboarding import (
    AgentOnboarding,
    AgentSession,
    OnboardingRequirement,
    get_onboarding,
    reset_onboarding,
)

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def temp_project():
    """Create a temporary project directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project = Path(tmpdir)
        # Create .fastband directory
        fastband_dir = project / ".fastband"
        fastband_dir.mkdir()
        yield project


@pytest.fixture
def temp_project_with_bible(temp_project):
    """Create a temp project with an Agent Bible."""
    bible_path = temp_project / ".fastband" / "AGENT_BIBLE.md"
    bible_path.write_text("""# Agent Bible

## Rules
1. Always read the bible first
2. Follow project conventions
3. Test your changes
""")
    return temp_project


@pytest.fixture
def onboarding(temp_project_with_bible):
    """Create an onboarding instance with a bible."""
    reset_onboarding()
    return AgentOnboarding(project_path=temp_project_with_bible)


@pytest.fixture
def onboarding_no_bible(temp_project):
    """Create an onboarding instance without a bible."""
    reset_onboarding()
    return AgentOnboarding(project_path=temp_project)


# =============================================================================
# ONBOARDING REQUIREMENT TESTS
# =============================================================================


class TestOnboardingRequirement:
    """Tests for OnboardingRequirement dataclass."""

    def test_create_requirement(self):
        """Test creating a requirement."""
        req = OnboardingRequirement(
            path="/path/to/doc.md",
            description="Test document",
        )
        assert req.path == "/path/to/doc.md"
        assert req.description == "Test document"
        assert req.required is True

    def test_create_optional_requirement(self):
        """Test creating an optional requirement."""
        req = OnboardingRequirement(
            path="/path/to/optional.md",
            description="Optional doc",
            required=False,
        )
        assert req.required is False

    def test_to_dict(self):
        """Test converting requirement to dict."""
        req = OnboardingRequirement(
            path="/path/to/doc.md",
            description="Test document",
            required=True,
        )
        data = req.to_dict()
        assert data["path"] == "/path/to/doc.md"
        assert data["description"] == "Test document"
        assert data["required"] is True


# =============================================================================
# AGENT SESSION TESTS
# =============================================================================


class TestAgentSession:
    """Tests for AgentSession dataclass."""

    def test_create_session(self):
        """Test creating a session."""
        session = AgentSession(
            agent_name="MCP_Agent1",
            session_id="test_session_123",
            started_at="2024-01-01T00:00:00Z",
        )
        assert session.agent_name == "MCP_Agent1"
        assert session.session_id == "test_session_123"
        assert session.completed is False
        assert session.docs_acknowledged == []

    def test_session_to_dict(self):
        """Test converting session to dict."""
        session = AgentSession(
            agent_name="MCP_Agent1",
            session_id="test_session_123",
            started_at="2024-01-01T00:00:00Z",
            docs_acknowledged=["/path/to/doc.md"],
        )
        data = session.to_dict()
        assert data["agent_name"] == "MCP_Agent1"
        assert data["session_id"] == "test_session_123"
        assert data["completed"] is False
        assert "/path/to/doc.md" in data["docs_acknowledged"]

    def test_session_from_dict(self):
        """Test creating session from dict."""
        data = {
            "agent_name": "MCP_Agent1",
            "session_id": "test_session_123",
            "started_at": "2024-01-01T00:00:00Z",
            "completed": True,
            "completed_at": "2024-01-01T01:00:00Z",
            "docs_acknowledged": ["/path/to/doc.md"],
            "codebase_examined": True,
            "platform_understanding": "Flask app with SQLite",
        }
        session = AgentSession.from_dict(data)
        assert session.agent_name == "MCP_Agent1"
        assert session.completed is True
        assert session.platform_understanding == "Flask app with SQLite"


# =============================================================================
# AGENT ONBOARDING TESTS
# =============================================================================


class TestAgentOnboarding:
    """Tests for AgentOnboarding class."""

    def test_create_onboarding(self, temp_project):
        """Test creating onboarding instance."""
        onboarding = AgentOnboarding(project_path=temp_project)
        # Use resolve() for comparison since the onboarding resolves paths
        assert onboarding.project_path == temp_project.resolve()
        assert onboarding.fastband_dir == temp_project.resolve() / ".fastband"

    def test_requirements_with_bible(self, onboarding):
        """Test that Agent Bible is detected as requirement."""
        requirements = onboarding.requirements
        assert len(requirements) == 1
        assert "AGENT_BIBLE.md" in requirements[0].path
        assert requirements[0].required is True

    def test_requirements_without_bible(self, onboarding_no_bible):
        """Test that no requirements when no bible exists."""
        requirements = onboarding_no_bible.requirements
        assert len(requirements) == 0


class TestOnboardingSession:
    """Tests for starting and managing onboarding sessions."""

    def test_start_session(self, onboarding):
        """Test starting an onboarding session."""
        result = onboarding.start_session(agent_name="MCP_Agent1")

        assert result["success"] is True
        assert result["agent_name"] == "MCP_Agent1"
        assert "session_id" in result
        assert "required_docs" in result
        assert len(result["required_docs"]) == 1

    def test_start_session_with_context(self, onboarding):
        """Test starting session with context."""
        result = onboarding.start_session(
            agent_name="MCP_Agent1",
            context="new_ticket",
        )
        assert result["success"] is True

    def test_session_persists(self, temp_project_with_bible):
        """Test that sessions are persisted to file."""
        onboarding1 = AgentOnboarding(project_path=temp_project_with_bible)
        result = onboarding1.start_session(agent_name="MCP_Agent1")
        session_id = result["session_id"]

        # Create new instance - should load saved session
        onboarding2 = AgentOnboarding(project_path=temp_project_with_bible)
        session = onboarding2.get_session(session_id)

        assert session is not None
        assert session.agent_name == "MCP_Agent1"


class TestDocumentAcknowledgment:
    """Tests for acknowledging documents."""

    def test_acknowledge_document(self, onboarding):
        """Test acknowledging a document."""
        # Start session
        session_result = onboarding.start_session(agent_name="MCP_Agent1")
        session_id = session_result["session_id"]
        doc_path = session_result["required_docs"][0]["path"]

        # Acknowledge document
        result = onboarding.acknowledge_doc(
            session_id=session_id,
            doc_path=doc_path,
            summary="Learned about project rules",
        )

        assert result["success"] is True
        assert result["docs_complete"] is True
        assert len(result["remaining_docs"]) == 0

    def test_acknowledge_invalid_session(self, onboarding):
        """Test acknowledging with invalid session."""
        result = onboarding.acknowledge_doc(
            session_id="invalid_session",
            doc_path="/some/doc.md",
        )
        assert result["success"] is False
        assert "not found" in result["error"]

    def test_acknowledge_already_acknowledged(self, onboarding):
        """Test acknowledging same document twice."""
        session_result = onboarding.start_session(agent_name="MCP_Agent1")
        session_id = session_result["session_id"]
        doc_path = session_result["required_docs"][0]["path"]

        # Acknowledge once
        onboarding.acknowledge_doc(session_id=session_id, doc_path=doc_path)

        # Acknowledge again
        result = onboarding.acknowledge_doc(session_id=session_id, doc_path=doc_path)
        assert result["success"] is True
        assert "already acknowledged" in result["message"]


class TestOnboardingCompletion:
    """Tests for completing onboarding."""

    def test_complete_onboarding(self, onboarding):
        """Test completing onboarding after acknowledging docs."""
        # Start session and acknowledge
        session_result = onboarding.start_session(agent_name="MCP_Agent1")
        session_id = session_result["session_id"]
        doc_path = session_result["required_docs"][0]["path"]
        onboarding.acknowledge_doc(session_id=session_id, doc_path=doc_path)

        # Complete onboarding
        result = onboarding.complete_onboarding(
            session_id=session_id,
            codebase_examined=True,
            platform_understanding="Flask app with SQLite",
        )

        assert result["success"] is True
        assert "complete" in result["message"].lower()
        assert onboarding.is_onboarded(session_id)

    def test_complete_without_acknowledging(self, onboarding):
        """Test completing without acknowledging docs fails."""
        session_result = onboarding.start_session(agent_name="MCP_Agent1")
        session_id = session_result["session_id"]

        # Try to complete without acknowledging
        result = onboarding.complete_onboarding(session_id=session_id)

        assert result["success"] is False
        assert "remaining_docs" in result
        assert len(result["remaining_docs"]) > 0

    def test_complete_invalid_session(self, onboarding):
        """Test completing with invalid session."""
        result = onboarding.complete_onboarding(session_id="invalid")
        assert result["success"] is False
        assert "not found" in result["error"]

    def test_complete_already_completed(self, onboarding):
        """Test completing already completed session."""
        # Complete session
        session_result = onboarding.start_session(agent_name="MCP_Agent1")
        session_id = session_result["session_id"]
        doc_path = session_result["required_docs"][0]["path"]
        onboarding.acknowledge_doc(session_id=session_id, doc_path=doc_path)
        onboarding.complete_onboarding(session_id=session_id)

        # Try to complete again
        result = onboarding.complete_onboarding(session_id=session_id)
        assert result["success"] is True
        assert "already completed" in result["message"]


class TestOnboardingStatus:
    """Tests for checking onboarding status."""

    def test_get_status_no_session(self, onboarding):
        """Test getting status when no session exists."""
        status = onboarding.get_status(agent_name="MCP_Agent1")
        assert status["has_session"] is False
        assert status["onboarded"] is False

    def test_get_status_incomplete(self, onboarding):
        """Test getting status of incomplete session."""
        onboarding.start_session(agent_name="MCP_Agent1")

        status = onboarding.get_status(agent_name="MCP_Agent1")
        assert status["has_session"] is True
        assert status["onboarded"] is False
        assert "remaining_docs" in status

    def test_get_status_complete(self, onboarding):
        """Test getting status of completed session."""
        session_result = onboarding.start_session(agent_name="MCP_Agent1")
        session_id = session_result["session_id"]
        doc_path = session_result["required_docs"][0]["path"]
        onboarding.acknowledge_doc(session_id=session_id, doc_path=doc_path)
        onboarding.complete_onboarding(session_id=session_id)

        status = onboarding.get_status(agent_name="MCP_Agent1")
        assert status["has_session"] is True
        assert status["onboarded"] is True
        assert len(status["remaining_docs"]) == 0


class TestOnboardingEnforcement:
    """Tests for enforcing onboarding requirements."""

    def test_require_onboarding_not_started(self, onboarding):
        """Test require_onboarding when no session exists."""
        with pytest.raises(PermissionError) as exc_info:
            onboarding.require_onboarding("invalid_session")
        assert "No valid onboarding session" in str(exc_info.value)

    def test_require_onboarding_incomplete(self, onboarding):
        """Test require_onboarding when not completed."""
        session_result = onboarding.start_session(agent_name="MCP_Agent1")
        session_id = session_result["session_id"]

        with pytest.raises(PermissionError) as exc_info:
            onboarding.require_onboarding(session_id)
        assert "not complete" in str(exc_info.value).lower()

    def test_require_onboarding_complete(self, onboarding):
        """Test require_onboarding when completed passes."""
        session_result = onboarding.start_session(agent_name="MCP_Agent1")
        session_id = session_result["session_id"]
        doc_path = session_result["required_docs"][0]["path"]
        onboarding.acknowledge_doc(session_id=session_id, doc_path=doc_path)
        onboarding.complete_onboarding(session_id=session_id)

        # Should not raise
        onboarding.require_onboarding(session_id)


class TestOnboardingWithNoBible:
    """Tests for projects without an Agent Bible."""

    def test_complete_immediately(self, onboarding_no_bible):
        """Test that completion works immediately with no requirements."""
        session_result = onboarding_no_bible.start_session(agent_name="MCP_Agent1")
        session_id = session_result["session_id"]

        assert len(session_result["required_docs"]) == 0

        # Should complete immediately
        result = onboarding_no_bible.complete_onboarding(session_id=session_id)
        assert result["success"] is True


# =============================================================================
# GLOBAL INSTANCE TESTS
# =============================================================================


class TestGlobalOnboarding:
    """Tests for global onboarding instance."""

    def test_get_onboarding(self, temp_project):
        """Test getting global onboarding instance."""
        reset_onboarding()
        onboarding = get_onboarding(temp_project)
        assert onboarding is not None
        # Use resolve() for comparison since the onboarding resolves paths
        assert onboarding.project_path == temp_project.resolve()

    def test_get_onboarding_caches(self, temp_project):
        """Test that global instance is cached."""
        reset_onboarding()
        onboarding1 = get_onboarding(temp_project)
        onboarding2 = get_onboarding(temp_project)
        assert onboarding1 is onboarding2

    def test_reset_onboarding(self, temp_project):
        """Test resetting global onboarding."""
        reset_onboarding()
        onboarding1 = get_onboarding(temp_project)
        reset_onboarding()
        onboarding2 = get_onboarding(temp_project)
        # After reset, should create new instance
        assert onboarding1 is not onboarding2


# =============================================================================
# ADDITIONAL REQUIREMENTS TESTS
# =============================================================================


class TestAdditionalDocs:
    """Tests for projects with additional required docs."""

    def test_load_additional_docs(self, temp_project_with_bible):
        """Test loading additional required docs from config."""
        # Create config file
        config_path = temp_project_with_bible / ".fastband" / "onboarding_docs.json"
        config_path.write_text(
            json.dumps(
                {
                    "required_docs": [
                        {
                            "path": str(temp_project_with_bible / "README.md"),
                            "description": "Project README",
                            "required": True,
                        }
                    ]
                }
            )
        )

        # Create the README
        (temp_project_with_bible / "README.md").write_text("# Project")

        onboarding = AgentOnboarding(project_path=temp_project_with_bible)

        # Should have bible + README
        assert len(onboarding.requirements) == 2

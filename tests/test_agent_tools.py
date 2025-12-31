"""
Tests for Agent Onboarding Tools.

Tests cover:
- StartOnboardingTool: Starting onboarding sessions
- AcknowledgeDocumentTool: Document acknowledgment
- CompleteOnboardingTool: Onboarding completion
- GetOnboardingStatusTool: Status checking
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from fastband.agents.onboarding import reset_onboarding
from fastband.tools.agents import (
    AGENT_TOOLS,
    AcknowledgeDocumentTool,
    CompleteOnboardingTool,
    GetOnboardingStatusTool,
    StartOnboardingTool,
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
def mock_onboarding():
    """Create a mock onboarding instance."""
    mock = MagicMock()
    return mock


# =============================================================================
# START ONBOARDING TOOL TESTS
# =============================================================================


class TestStartOnboardingToolDefinition:
    """Tests for StartOnboardingTool definition."""

    def test_tool_name(self, temp_project):
        """Test tool name."""
        tool = StartOnboardingTool(project_path=temp_project)
        assert tool.definition.metadata.name == "start_onboarding"

    def test_tool_description(self, temp_project):
        """Test tool has description."""
        tool = StartOnboardingTool(project_path=temp_project)
        assert "onboarding" in tool.definition.metadata.description.lower()
        assert "first" in tool.definition.metadata.description.lower()

    def test_tool_parameters(self, temp_project):
        """Test tool parameters."""
        tool = StartOnboardingTool(project_path=temp_project)
        params = {p.name for p in tool.definition.parameters}
        assert "agent_name" in params
        assert "context" in params

    def test_agent_name_required(self, temp_project):
        """Test agent_name is required."""
        tool = StartOnboardingTool(project_path=temp_project)
        agent_param = next(
            p for p in tool.definition.parameters if p.name == "agent_name"
        )
        assert agent_param.required is True


class TestStartOnboardingToolExecution:
    """Tests for StartOnboardingTool execution."""

    @pytest.mark.asyncio
    async def test_start_onboarding_success(self, temp_project_with_bible):
        """Test successful onboarding start."""
        tool = StartOnboardingTool(project_path=temp_project_with_bible)

        result = await tool.execute(agent_name="TestAgent")

        assert result.success is True
        assert result.data["agent_name"] == "TestAgent"
        assert "session_id" in result.data
        assert "required_docs" in result.data

    @pytest.mark.asyncio
    async def test_start_onboarding_with_context(self, temp_project_with_bible):
        """Test onboarding with context."""
        tool = StartOnboardingTool(project_path=temp_project_with_bible)

        result = await tool.execute(
            agent_name="TestAgent", context="new_ticket"
        )

        assert result.success is True

    @pytest.mark.asyncio
    async def test_start_onboarding_empty_name(self, temp_project):
        """Test error with empty agent name."""
        tool = StartOnboardingTool(project_path=temp_project)

        result = await tool.execute(agent_name="")

        assert result.success is False
        assert "required" in result.error.lower()

    @pytest.mark.asyncio
    async def test_start_onboarding_whitespace_name(self, temp_project):
        """Test error with whitespace-only agent name."""
        tool = StartOnboardingTool(project_path=temp_project)

        result = await tool.execute(agent_name="   ")

        assert result.success is False
        assert "required" in result.error.lower()

    @pytest.mark.asyncio
    async def test_start_onboarding_exception(self, temp_project):
        """Test handling of exceptions."""
        tool = StartOnboardingTool(project_path=temp_project)

        # Create a mock onboarding and set it directly
        mock_onboarding = MagicMock()
        mock_onboarding.start_session.side_effect = Exception("Database error")
        tool._onboarding = mock_onboarding

        result = await tool.execute(agent_name="TestAgent")

        assert result.success is False
        assert "Failed to start" in result.error

    @pytest.mark.asyncio
    async def test_onboarding_lazy_load(self, temp_project):
        """Test onboarding is lazily loaded."""
        tool = StartOnboardingTool(project_path=temp_project)

        # Should not be loaded yet
        assert tool._onboarding is None

        # Access property to trigger load
        _ = tool.onboarding

        # Should be loaded now
        assert tool._onboarding is not None


# =============================================================================
# ACKNOWLEDGE DOCUMENT TOOL TESTS
# =============================================================================


class TestAcknowledgeDocumentToolDefinition:
    """Tests for AcknowledgeDocumentTool definition."""

    def test_tool_name(self, temp_project):
        """Test tool name."""
        tool = AcknowledgeDocumentTool(project_path=temp_project)
        assert tool.definition.metadata.name == "acknowledge_document"

    def test_tool_parameters(self, temp_project):
        """Test tool parameters."""
        tool = AcknowledgeDocumentTool(project_path=temp_project)
        params = {p.name for p in tool.definition.parameters}
        assert "session_id" in params
        assert "doc_path" in params
        assert "summary" in params

    def test_required_parameters(self, temp_project):
        """Test required parameters."""
        tool = AcknowledgeDocumentTool(project_path=temp_project)
        session_param = next(
            p for p in tool.definition.parameters if p.name == "session_id"
        )
        doc_param = next(
            p for p in tool.definition.parameters if p.name == "doc_path"
        )
        assert session_param.required is True
        assert doc_param.required is True


class TestAcknowledgeDocumentToolExecution:
    """Tests for AcknowledgeDocumentTool execution."""

    @pytest.mark.asyncio
    async def test_acknowledge_success(self, temp_project_with_bible):
        """Test successful document acknowledgment."""
        # First start onboarding
        start_tool = StartOnboardingTool(project_path=temp_project_with_bible)
        start_result = await start_tool.execute(agent_name="TestAgent")
        session_id = start_result.data["session_id"]
        doc_path = start_result.data["required_docs"][0]["path"]

        # Acknowledge document
        ack_tool = AcknowledgeDocumentTool(project_path=temp_project_with_bible)
        result = await ack_tool.execute(
            session_id=session_id, doc_path=doc_path, summary="Read the rules"
        )

        assert result.success is True
        assert result.data["docs_complete"] is True

    @pytest.mark.asyncio
    async def test_acknowledge_empty_session_id(self, temp_project):
        """Test error with empty session ID."""
        tool = AcknowledgeDocumentTool(project_path=temp_project)

        result = await tool.execute(session_id="", doc_path="/some/doc.md")

        assert result.success is False
        assert "required" in result.error.lower()

    @pytest.mark.asyncio
    async def test_acknowledge_empty_doc_path(self, temp_project):
        """Test error with empty doc path."""
        tool = AcknowledgeDocumentTool(project_path=temp_project)

        result = await tool.execute(session_id="valid-session", doc_path="")

        assert result.success is False
        assert "required" in result.error.lower()

    @pytest.mark.asyncio
    async def test_acknowledge_invalid_session(self, temp_project_with_bible):
        """Test error with invalid session ID."""
        tool = AcknowledgeDocumentTool(project_path=temp_project_with_bible)

        result = await tool.execute(
            session_id="invalid-session-id", doc_path="/some/doc.md"
        )

        assert result.success is False
        assert "not found" in result.error.lower()

    @pytest.mark.asyncio
    async def test_acknowledge_exception(self, temp_project):
        """Test handling of exceptions."""
        tool = AcknowledgeDocumentTool(project_path=temp_project)

        # Create a mock onboarding and set it directly
        mock_onboarding = MagicMock()
        mock_onboarding.acknowledge_doc.side_effect = Exception("Error")
        tool._onboarding = mock_onboarding

        result = await tool.execute(
            session_id="session-123", doc_path="/doc.md"
        )

        assert result.success is False
        assert "Failed to acknowledge" in result.error


# =============================================================================
# COMPLETE ONBOARDING TOOL TESTS
# =============================================================================


class TestCompleteOnboardingToolDefinition:
    """Tests for CompleteOnboardingTool definition."""

    def test_tool_name(self, temp_project):
        """Test tool name."""
        tool = CompleteOnboardingTool(project_path=temp_project)
        assert tool.definition.metadata.name == "complete_onboarding"

    def test_tool_parameters(self, temp_project):
        """Test tool parameters."""
        tool = CompleteOnboardingTool(project_path=temp_project)
        params = {p.name for p in tool.definition.parameters}
        assert "session_id" in params
        assert "codebase_examined" in params
        assert "platform_understanding" in params


class TestCompleteOnboardingToolExecution:
    """Tests for CompleteOnboardingTool execution."""

    @pytest.mark.asyncio
    async def test_complete_success(self, temp_project_with_bible):
        """Test successful onboarding completion."""
        # Start onboarding
        start_tool = StartOnboardingTool(project_path=temp_project_with_bible)
        start_result = await start_tool.execute(agent_name="TestAgent")
        session_id = start_result.data["session_id"]
        doc_path = start_result.data["required_docs"][0]["path"]

        # Acknowledge document
        ack_tool = AcknowledgeDocumentTool(project_path=temp_project_with_bible)
        await ack_tool.execute(session_id=session_id, doc_path=doc_path)

        # Complete onboarding
        complete_tool = CompleteOnboardingTool(project_path=temp_project_with_bible)
        result = await complete_tool.execute(
            session_id=session_id,
            codebase_examined=True,
            platform_understanding="Python Flask app",
        )

        assert result.success is True

    @pytest.mark.asyncio
    async def test_complete_empty_session_id(self, temp_project):
        """Test error with empty session ID."""
        tool = CompleteOnboardingTool(project_path=temp_project)

        result = await tool.execute(session_id="")

        assert result.success is False
        assert "required" in result.error.lower()

    @pytest.mark.asyncio
    async def test_complete_without_acknowledgment(self, temp_project_with_bible):
        """Test error when docs not acknowledged."""
        # Start onboarding but don't acknowledge
        start_tool = StartOnboardingTool(project_path=temp_project_with_bible)
        start_result = await start_tool.execute(agent_name="TestAgent")
        session_id = start_result.data["session_id"]

        # Try to complete
        complete_tool = CompleteOnboardingTool(project_path=temp_project_with_bible)
        result = await complete_tool.execute(session_id=session_id)

        assert result.success is False
        assert "remaining_docs" in result.data

    @pytest.mark.asyncio
    async def test_complete_invalid_session(self, temp_project_with_bible):
        """Test error with invalid session ID."""
        tool = CompleteOnboardingTool(project_path=temp_project_with_bible)

        result = await tool.execute(session_id="invalid-session")

        assert result.success is False
        assert "not found" in result.error.lower()

    @pytest.mark.asyncio
    async def test_complete_exception(self, temp_project):
        """Test handling of exceptions."""
        tool = CompleteOnboardingTool(project_path=temp_project)

        # Create a mock onboarding and set it directly
        mock_onboarding = MagicMock()
        mock_onboarding.complete_onboarding.side_effect = Exception("Error")
        tool._onboarding = mock_onboarding

        result = await tool.execute(session_id="session-123")

        assert result.success is False
        assert "Failed to complete" in result.error


# =============================================================================
# GET ONBOARDING STATUS TOOL TESTS
# =============================================================================


class TestGetOnboardingStatusToolDefinition:
    """Tests for GetOnboardingStatusTool definition."""

    def test_tool_name(self, temp_project):
        """Test tool name."""
        tool = GetOnboardingStatusTool(project_path=temp_project)
        assert tool.definition.metadata.name == "get_onboarding_status"

    def test_tool_parameters(self, temp_project):
        """Test tool parameters."""
        tool = GetOnboardingStatusTool(project_path=temp_project)
        params = {p.name for p in tool.definition.parameters}
        assert "agent_name" in params

    def test_agent_name_required(self, temp_project):
        """Test agent_name is required."""
        tool = GetOnboardingStatusTool(project_path=temp_project)
        agent_param = next(
            p for p in tool.definition.parameters if p.name == "agent_name"
        )
        assert agent_param.required is True


class TestGetOnboardingStatusToolExecution:
    """Tests for GetOnboardingStatusTool execution."""

    @pytest.mark.asyncio
    async def test_get_status_no_session(self, temp_project):
        """Test status when no session exists."""
        tool = GetOnboardingStatusTool(project_path=temp_project)

        result = await tool.execute(agent_name="UnknownAgent")

        assert result.success is True
        assert result.data["has_session"] is False
        assert result.data["onboarded"] is False

    @pytest.mark.asyncio
    async def test_get_status_in_progress(self, temp_project_with_bible):
        """Test status for in-progress onboarding."""
        # Start onboarding
        start_tool = StartOnboardingTool(project_path=temp_project_with_bible)
        await start_tool.execute(agent_name="TestAgent")

        # Check status
        status_tool = GetOnboardingStatusTool(project_path=temp_project_with_bible)
        result = await status_tool.execute(agent_name="TestAgent")

        assert result.success is True
        assert result.data["has_session"] is True
        assert result.data["onboarded"] is False
        assert "remaining_docs" in result.data

    @pytest.mark.asyncio
    async def test_get_status_completed(self, temp_project_with_bible):
        """Test status for completed onboarding."""
        # Complete full onboarding flow
        start_tool = StartOnboardingTool(project_path=temp_project_with_bible)
        start_result = await start_tool.execute(agent_name="TestAgent")
        session_id = start_result.data["session_id"]
        doc_path = start_result.data["required_docs"][0]["path"]

        ack_tool = AcknowledgeDocumentTool(project_path=temp_project_with_bible)
        await ack_tool.execute(session_id=session_id, doc_path=doc_path)

        complete_tool = CompleteOnboardingTool(project_path=temp_project_with_bible)
        await complete_tool.execute(session_id=session_id)

        # Check status
        status_tool = GetOnboardingStatusTool(project_path=temp_project_with_bible)
        result = await status_tool.execute(agent_name="TestAgent")

        assert result.success is True
        assert result.data["has_session"] is True
        assert result.data["onboarded"] is True

    @pytest.mark.asyncio
    async def test_get_status_empty_name(self, temp_project):
        """Test error with empty agent name."""
        tool = GetOnboardingStatusTool(project_path=temp_project)

        result = await tool.execute(agent_name="")

        assert result.success is False
        assert "required" in result.error.lower()

    @pytest.mark.asyncio
    async def test_get_status_exception(self, temp_project):
        """Test handling of exceptions."""
        tool = GetOnboardingStatusTool(project_path=temp_project)

        # Create a mock onboarding and set it directly
        mock_onboarding = MagicMock()
        mock_onboarding.get_status.side_effect = Exception("Database error")
        tool._onboarding = mock_onboarding

        result = await tool.execute(agent_name="TestAgent")

        assert result.success is False
        assert "Failed to get status" in result.error


# =============================================================================
# MODULE TESTS
# =============================================================================


class TestAgentToolsModule:
    """Tests for agent tools module."""

    def test_agent_tools_list(self):
        """Test AGENT_TOOLS contains expected tools."""
        assert StartOnboardingTool in AGENT_TOOLS
        assert AcknowledgeDocumentTool in AGENT_TOOLS
        assert CompleteOnboardingTool in AGENT_TOOLS
        assert GetOnboardingStatusTool in AGENT_TOOLS
        assert len(AGENT_TOOLS) == 4

    def test_tool_categories(self, temp_project):
        """Test tools have correct category."""
        from fastband.tools.base import ToolCategory

        tools = [
            StartOnboardingTool(project_path=temp_project),
            AcknowledgeDocumentTool(project_path=temp_project),
            CompleteOnboardingTool(project_path=temp_project),
            GetOnboardingStatusTool(project_path=temp_project),
        ]

        for tool in tools:
            assert tool.definition.metadata.category == ToolCategory.CORE


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestOnboardingIntegration:
    """Integration tests for the full onboarding flow."""

    @pytest.mark.asyncio
    async def test_full_onboarding_flow(self, temp_project_with_bible):
        """Test complete onboarding flow with all tools."""
        # Step 1: Start onboarding
        start_tool = StartOnboardingTool(project_path=temp_project_with_bible)
        start_result = await start_tool.execute(
            agent_name="IntegrationTestAgent", context="integration_test"
        )

        assert start_result.success is True
        session_id = start_result.data["session_id"]
        required_docs = start_result.data["required_docs"]

        # Step 2: Check initial status
        status_tool = GetOnboardingStatusTool(project_path=temp_project_with_bible)
        status_result = await status_tool.execute(agent_name="IntegrationTestAgent")

        assert status_result.success is True
        assert status_result.data["onboarded"] is False
        assert len(status_result.data["remaining_docs"]) > 0

        # Step 3: Acknowledge all documents
        ack_tool = AcknowledgeDocumentTool(project_path=temp_project_with_bible)
        for doc in required_docs:
            ack_result = await ack_tool.execute(
                session_id=session_id,
                doc_path=doc["path"],
                summary=f"Read {doc['description']}",
            )
            assert ack_result.success is True

        # Step 4: Complete onboarding
        complete_tool = CompleteOnboardingTool(project_path=temp_project_with_bible)
        complete_result = await complete_tool.execute(
            session_id=session_id,
            codebase_examined=True,
            platform_understanding="Test project for integration testing",
        )

        assert complete_result.success is True

        # Step 5: Verify final status
        final_status = await status_tool.execute(agent_name="IntegrationTestAgent")

        assert final_status.success is True
        assert final_status.data["onboarded"] is True
        assert len(final_status.data["remaining_docs"]) == 0

    @pytest.mark.asyncio
    async def test_onboarding_no_requirements(self):
        """Test onboarding when no requirements exist."""
        # Reset global onboarding state
        reset_onboarding()

        # Create a fresh temp directory without AGENT_BIBLE.md
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir)
            fastband_dir = project / ".fastband"
            fastband_dir.mkdir()
            # No AGENT_BIBLE.md - should complete immediately

            start_tool = StartOnboardingTool(project_path=project)
            start_result = await start_tool.execute(agent_name="SimpleAgent")

            assert start_result.success is True
            session_id = start_result.data["session_id"]
            assert len(start_result.data["required_docs"]) == 0

            # Can complete immediately
            complete_tool = CompleteOnboardingTool(project_path=project)
            complete_result = await complete_tool.execute(session_id=session_id)

            assert complete_result.success is True

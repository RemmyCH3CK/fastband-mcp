"""
MCP Agent Onboarding Tools.

Provides tools for AI agents to complete onboarding by reading and
acknowledging the Agent Bible before they can work on tickets.

Tools:
- start_onboarding: Start an onboarding session
- acknowledge_document: Acknowledge reading a required document
- complete_onboarding: Complete the onboarding process
- get_onboarding_status: Check onboarding status
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

from fastband.agents.onboarding import (
    AgentOnboarding,
    get_onboarding,
)
from fastband.tools.base import (
    Tool,
    ToolCategory,
    ToolDefinition,
    ToolMetadata,
    ToolParameter,
    ToolResult,
)

# =============================================================================
# START ONBOARDING TOOL
# =============================================================================


class StartOnboardingTool(Tool):
    """
    Start an onboarding session for an AI agent.

    This is the FIRST tool an agent must call when starting work on a project.
    It returns a list of required documents that must be read and acknowledged.
    """

    def __init__(self, project_path: Path | None = None):
        self._project_path = project_path
        self._onboarding: AgentOnboarding | None = None

    @property
    def onboarding(self) -> AgentOnboarding:
        """Get onboarding instance (lazy load)."""
        if self._onboarding is None:
            self._onboarding = get_onboarding(self._project_path)
        return self._onboarding

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            metadata=ToolMetadata(
                name="start_onboarding",
                description="Start an onboarding session. Returns required documents to read. MUST be called first.",
                category=ToolCategory.CORE,
                version="1.0.0",
            ),
            parameters=[
                ToolParameter(
                    name="agent_name",
                    type="string",
                    description="Your agent identifier (e.g., 'MCP_Agent1')",
                    required=True,
                ),
                ToolParameter(
                    name="context",
                    type="string",
                    description="Why you're starting (e.g., 'new_ticket', 'resuming_work')",
                    required=False,
                ),
            ],
        )

    async def execute(
        self,
        agent_name: str,
        context: str | None = None,
        **kwargs,
    ) -> ToolResult:
        """Start onboarding session."""
        try:
            if not agent_name or not agent_name.strip():
                return ToolResult(
                    success=False,
                    error="Agent name is required",
                )

            result = self.onboarding.start_session(
                agent_name=agent_name.strip(),
                context=context,
            )

            return ToolResult(
                success=result.get("success", False),
                data=result,
            )

        except Exception as e:
            return ToolResult(success=False, error=f"Failed to start onboarding: {e}")


# =============================================================================
# ACKNOWLEDGE DOCUMENT TOOL
# =============================================================================


class AcknowledgeDocumentTool(Tool):
    """
    Acknowledge that a required document has been read.

    Called after reading each required document (like the Agent Bible).
    The agent must acknowledge ALL required documents before completing onboarding.
    """

    def __init__(self, project_path: Path | None = None):
        self._project_path = project_path
        self._onboarding: AgentOnboarding | None = None

    @property
    def onboarding(self) -> AgentOnboarding:
        if self._onboarding is None:
            self._onboarding = get_onboarding(self._project_path)
        return self._onboarding

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            metadata=ToolMetadata(
                name="acknowledge_document",
                description="Acknowledge reading a required document. Call after reading each document.",
                category=ToolCategory.CORE,
                version="1.0.0",
            ),
            parameters=[
                ToolParameter(
                    name="session_id",
                    type="string",
                    description="Session ID from start_onboarding",
                    required=True,
                ),
                ToolParameter(
                    name="doc_path",
                    type="string",
                    description="Path to the document you read",
                    required=True,
                ),
                ToolParameter(
                    name="summary",
                    type="string",
                    description="Brief summary of what you learned (helps verify understanding)",
                    required=False,
                ),
            ],
        )

    async def execute(
        self,
        session_id: str,
        doc_path: str,
        summary: str | None = None,
        **kwargs,
    ) -> ToolResult:
        """Acknowledge document read."""
        try:
            if not session_id or not session_id.strip():
                return ToolResult(
                    success=False,
                    error="Session ID is required",
                )
            if not doc_path or not doc_path.strip():
                return ToolResult(
                    success=False,
                    error="Document path is required",
                )

            result = self.onboarding.acknowledge_doc(
                session_id=session_id.strip(),
                doc_path=doc_path.strip(),
                summary=summary,
            )

            return ToolResult(
                success=result.get("success", False),
                data=result,
                error=result.get("error"),
            )

        except Exception as e:
            return ToolResult(success=False, error=f"Failed to acknowledge document: {e}")


# =============================================================================
# COMPLETE ONBOARDING TOOL
# =============================================================================


class CompleteOnboardingTool(Tool):
    """
    Complete the onboarding process.

    Can only be called after ALL required documents have been acknowledged.
    After completion, the agent can perform work on the project.
    """

    def __init__(self, project_path: Path | None = None):
        self._project_path = project_path
        self._onboarding: AgentOnboarding | None = None

    @property
    def onboarding(self) -> AgentOnboarding:
        if self._onboarding is None:
            self._onboarding = get_onboarding(self._project_path)
        return self._onboarding

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            metadata=ToolMetadata(
                name="complete_onboarding",
                description="Complete onboarding after acknowledging all required documents.",
                category=ToolCategory.CORE,
                version="1.0.0",
            ),
            parameters=[
                ToolParameter(
                    name="session_id",
                    type="string",
                    description="Session ID from start_onboarding",
                    required=True,
                ),
                ToolParameter(
                    name="codebase_examined",
                    type="boolean",
                    description="Whether you examined key codebase files",
                    required=False,
                    default=False,
                ),
                ToolParameter(
                    name="platform_understanding",
                    type="string",
                    description="Brief description of your understanding of the platform",
                    required=False,
                ),
            ],
        )

    async def execute(
        self,
        session_id: str,
        codebase_examined: bool = False,
        platform_understanding: str | None = None,
        **kwargs,
    ) -> ToolResult:
        """Complete onboarding."""
        try:
            if not session_id or not session_id.strip():
                return ToolResult(
                    success=False,
                    error="Session ID is required",
                )

            result = self.onboarding.complete_onboarding(
                session_id=session_id.strip(),
                codebase_examined=codebase_examined,
                platform_understanding=platform_understanding,
            )

            return ToolResult(
                success=result.get("success", False),
                data=result,
                error=result.get("error"),
            )

        except Exception as e:
            return ToolResult(success=False, error=f"Failed to complete onboarding: {e}")


# =============================================================================
# GET ONBOARDING STATUS TOOL
# =============================================================================


class GetOnboardingStatusTool(Tool):
    """
    Get onboarding status for an agent.

    Check if onboarding is complete or what documents still need to be read.
    """

    def __init__(self, project_path: Path | None = None):
        self._project_path = project_path
        self._onboarding: AgentOnboarding | None = None

    @property
    def onboarding(self) -> AgentOnboarding:
        if self._onboarding is None:
            self._onboarding = get_onboarding(self._project_path)
        return self._onboarding

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            metadata=ToolMetadata(
                name="get_onboarding_status",
                description="Check onboarding status and remaining requirements.",
                category=ToolCategory.CORE,
                version="1.0.0",
            ),
            parameters=[
                ToolParameter(
                    name="agent_name",
                    type="string",
                    description="Agent identifier to check",
                    required=True,
                ),
            ],
        )

    async def execute(
        self,
        agent_name: str,
        **kwargs,
    ) -> ToolResult:
        """Get onboarding status."""
        try:
            if not agent_name or not agent_name.strip():
                return ToolResult(
                    success=False,
                    error="Agent name is required",
                )

            result = self.onboarding.get_status(agent_name.strip())

            return ToolResult(
                success=True,
                data=result,
            )

        except Exception as e:
            return ToolResult(success=False, error=f"Failed to get status: {e}")


# =============================================================================
# ALL AGENT TOOLS
# =============================================================================

AGENT_TOOLS = [
    StartOnboardingTool,
    AcknowledgeDocumentTool,
    CompleteOnboardingTool,
    GetOnboardingStatusTool,
]

__all__ = [
    # Tools
    "StartOnboardingTool",
    "AcknowledgeDocumentTool",
    "CompleteOnboardingTool",
    "GetOnboardingStatusTool",
    # Tool list
    "AGENT_TOOLS",
]

"""
Memory Tools - MCP Tool Definitions for Claude Memory System.

Provides tools for:
- memory_query: Query past ticket memories for context
- memory_start_session: Start a memory session for context tracking
- memory_add_discovery: Record a session discovery
- memory_commit: Commit a resolved ticket to memory
- memory_get_patterns: Get learned fix patterns
- memory_stats: Get memory system statistics
- memory_extract_patterns: Run pattern extraction (maintenance)
- memory_prune: Prune stale memories (maintenance)

Ported from Fastband_MCP/memory_tools.py
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastband.tools.base import (
    Tool,
    ToolCategory,
    ToolDefinition,
    ToolMetadata,
    ToolParameter,
    ToolResult,
    ProjectType,
)

logger = logging.getLogger(__name__)


class MemoryQueryTool(Tool):
    """Query Claude Memory for relevant past tickets and fix patterns."""

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            metadata=ToolMetadata(
                name="memory_query",
                description=(
                    "Query Claude Memory for relevant past tickets and learned fix patterns. "
                    "Use this when starting work on a ticket to find similar past issues and their solutions."
                ),
                category=ToolCategory.AI,
                version="1.0.0",
                project_types=[ProjectType.WEB_APP, ProjectType.BACKEND],
                tech_stack_hints=["ai", "memory", "learning"],
            ),
            parameters=[
                ToolParameter(
                    name="query",
                    type="string",
                    description="Natural language description of what you're looking for",
                    required=True,
                ),
                ToolParameter(
                    name="app",
                    type="string",
                    description="Filter by app name (optional)",
                    required=False,
                ),
                ToolParameter(
                    name="ticket_type",
                    type="string",
                    description="Filter by type: Bug, Feature, Enhancement",
                    required=False,
                ),
                ToolParameter(
                    name="files",
                    type="array",
                    description="List of files involved (finds tickets that touched these files)",
                    required=False,
                ),
                ToolParameter(
                    name="session_id",
                    type="string",
                    description="Session ID for context tracking (avoids repetition)",
                    required=False,
                ),
                ToolParameter(
                    name="max_results",
                    type="integer",
                    description="Maximum memories to return (default: 10)",
                    required=False,
                    default=10,
                ),
            ],
        )

    async def execute(
        self,
        query: str,
        app: Optional[str] = None,
        ticket_type: Optional[str] = None,
        files: Optional[List[str]] = None,
        session_id: Optional[str] = None,
        max_results: int = 10,
        **kwargs,
    ) -> ToolResult:
        """Query memory for relevant past tickets."""
        from fastband.memory import get_memory_manager

        manager = get_memory_manager()

        # Get session if provided
        session = None
        if session_id:
            session = manager.get_session(session_id)

        # Query memories
        results = manager.query_memories(
            query=query,
            app=app,
            ticket_type=ticket_type,
            files=files,
            session=session,
            max_results=max_results,
        )

        # Get patterns
        patterns = manager.get_relevant_patterns(query, files=files, session=session)

        # Save session
        if session:
            manager.save_session(session)

        # Format context
        context_parts = []

        if results:
            context_parts.append("## Relevant Past Tickets\n")
            for memory, score in results:
                context_parts.append(f"### #{memory.ticket_id}: {memory.title}")
                context_parts.append(
                    f"**App**: {memory.app} | **Type**: {memory.ticket_type} | **Relevance**: {score:.0%}"
                )
                context_parts.append(f"**Problem**: {memory.problem_summary}")
                context_parts.append(f"**Solution**: {memory.solution_summary}")
                if memory.files_modified:
                    context_parts.append(
                        f"**Files**: {', '.join(memory.files_modified[:5])}"
                    )
                context_parts.append("")

        if patterns:
            context_parts.append("## Known Fix Patterns\n")
            for p in patterns[:3]:
                context_parts.append(f"### Pattern: {p.name}")
                context_parts.append(f"- Seen in {p.occurrence_count} tickets")
                context_parts.append(
                    f"- **Common files**: {', '.join(p.common_files_to_check[:3])}"
                )
                context_parts.append(
                    f"- **Typical solution**: {p.solution_template[:200]}"
                )
                context_parts.append(
                    f"- **Example tickets**: {', '.join(p.example_ticket_ids[:3])}"
                )
                context_parts.append("")

        return ToolResult(
            success=True,
            data={
                "memories_found": len(results),
                "patterns_found": len(patterns),
                "context": "\n".join(context_parts)
                if context_parts
                else "No relevant memories found.",
                "memory_ids": [m.ticket_id for m, _ in results],
                "pattern_ids": [p.pattern_id for p in patterns],
                "session_id": session_id,
            },
        )


class MemoryStartSessionTool(Tool):
    """Start a memory session for context tracking."""

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            metadata=ToolMetadata(
                name="memory_start_session",
                description=(
                    "Start a memory session for automatic context tracking. "
                    "The session tracks which memories you've seen to avoid repetition."
                ),
                category=ToolCategory.AI,
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
                    name="current_app",
                    type="string",
                    description="App you're working on (optional)",
                    required=False,
                ),
                ToolParameter(
                    name="current_ticket",
                    type="string",
                    description="Ticket number you're starting (optional)",
                    required=False,
                ),
            ],
        )

    async def execute(
        self,
        agent_name: str,
        current_app: Optional[str] = None,
        current_ticket: Optional[str] = None,
        **kwargs,
    ) -> ToolResult:
        """Start a memory session."""
        from fastband.memory import get_memory_manager

        manager = get_memory_manager()
        session = manager.create_session(agent_name)

        if current_app:
            session.current_app = current_app
        if current_ticket:
            session.current_ticket = current_ticket

        manager.save_session(session)

        return ToolResult(
            success=True,
            data={
                "session_id": session.session_id,
                "agent_name": agent_name,
                "current_app": current_app,
                "current_ticket": current_ticket,
                "started_at": session.started_at,
                "message": f"Session started. Use session_id '{session.session_id}' in memory queries.",
            },
        )


class MemoryAddDiscoveryTool(Tool):
    """Record a discovery made during a session."""

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            metadata=ToolMetadata(
                name="memory_add_discovery",
                description=(
                    "Record a discovery made during this session for cross-session learning. "
                    "Discoveries are saved and can be extracted into patterns later."
                ),
                category=ToolCategory.AI,
                version="1.0.0",
            ),
            parameters=[
                ToolParameter(
                    name="session_id",
                    type="string",
                    description="Your session ID from memory_start_session",
                    required=True,
                ),
                ToolParameter(
                    name="discovery",
                    type="string",
                    description="What you discovered",
                    required=True,
                ),
                ToolParameter(
                    name="category",
                    type="string",
                    description="Category: bug_cause, code_pattern, gotcha, tip, general",
                    required=False,
                    default="general",
                ),
            ],
        )

    async def execute(
        self,
        session_id: str,
        discovery: str,
        category: str = "general",
        **kwargs,
    ) -> ToolResult:
        """Add a discovery to the session."""
        from fastband.memory import get_memory_manager

        manager = get_memory_manager()
        session = manager.get_session(session_id)

        if not session:
            return ToolResult(
                success=False,
                error=f"Session '{session_id}' not found",
            )

        manager.add_session_discovery(session, discovery, category)

        return ToolResult(
            success=True,
            data={
                "session_id": session_id,
                "discovery_count": len(session.session_discoveries),
                "message": f"Discovery recorded. Total: {len(session.session_discoveries)}",
            },
        )


class MemoryCommitTool(Tool):
    """Commit a resolved ticket to Claude Memory."""

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            metadata=ToolMetadata(
                name="memory_commit",
                description=(
                    "Commit a resolved ticket to Claude Memory. "
                    "This is typically called automatically by complete_ticket_safely()."
                ),
                category=ToolCategory.AI,
                version="1.0.0",
            ),
            parameters=[
                ToolParameter(
                    name="ticket_id",
                    type="string",
                    description="The ticket number",
                    required=True,
                ),
                ToolParameter(
                    name="app",
                    type="string",
                    description="Application identifier",
                    required=True,
                ),
                ToolParameter(
                    name="title",
                    type="string",
                    description="Ticket title",
                    required=True,
                ),
                ToolParameter(
                    name="problem_summary",
                    type="string",
                    description="What was wrong",
                    required=True,
                ),
                ToolParameter(
                    name="solution_summary",
                    type="string",
                    description="How it was fixed",
                    required=True,
                ),
                ToolParameter(
                    name="files_modified",
                    type="array",
                    description="List of files that were changed",
                    required=True,
                ),
                ToolParameter(
                    name="ticket_type",
                    type="string",
                    description="Bug, Feature, Enhancement, etc.",
                    required=False,
                    default="Bug",
                ),
            ],
        )

    async def execute(
        self,
        ticket_id: str,
        app: str,
        title: str,
        problem_summary: str,
        solution_summary: str,
        files_modified: List[str],
        ticket_type: str = "Bug",
        **kwargs,
    ) -> ToolResult:
        """Commit a ticket to memory."""
        from fastband.memory import TicketMemory, get_memory_manager

        manager = get_memory_manager()

        # Extract keywords
        keywords = manager._extract_keywords(f"{title} {problem_summary} {solution_summary}")

        memory = TicketMemory(
            ticket_id=str(ticket_id),
            app=app,
            app_version=None,
            title=title,
            problem_summary=problem_summary,
            solution_summary=solution_summary,
            files_modified=files_modified,
            keywords=keywords,
            ticket_type=ticket_type,
            resolved_date=datetime.now().strftime("%Y-%m-%d"),
        )

        result = manager.save_ticket_memory(memory)

        return ToolResult(
            success=True,
            data={
                "memory_committed": True,
                "ticket_id": ticket_id,
                "app": app,
                "keywords_extracted": keywords[:10],
                "message": f"Ticket #{ticket_id} committed to memory.",
            },
        )


class MemoryGetPatternsTool(Tool):
    """Get learned fix patterns from cross-session analysis."""

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            metadata=ToolMetadata(
                name="memory_get_patterns",
                description="Get learned fix patterns from cross-session analysis.",
                category=ToolCategory.AI,
                version="1.0.0",
            ),
            parameters=[
                ToolParameter(
                    name="query",
                    type="string",
                    description="Optional filter query",
                    required=False,
                ),
                ToolParameter(
                    name="limit",
                    type="integer",
                    description="Maximum patterns to return",
                    required=False,
                    default=10,
                ),
            ],
        )

    async def execute(
        self,
        query: Optional[str] = None,
        limit: int = 10,
        **kwargs,
    ) -> ToolResult:
        """Get fix patterns."""
        from fastband.memory import get_memory_manager

        manager = get_memory_manager()
        patterns = manager.get_relevant_patterns(query or "", files=None, session=None)

        return ToolResult(
            success=True,
            data={
                "patterns_count": len(patterns[:limit]),
                "patterns": [
                    {
                        "pattern_id": p.pattern_id,
                        "name": p.name,
                        "description": p.description,
                        "occurrence_count": p.occurrence_count,
                        "common_files": p.common_files_to_check,
                        "solution_template": p.solution_template[:200],
                        "example_tickets": p.example_ticket_ids,
                    }
                    for p in patterns[:limit]
                ],
            },
        )


class MemoryStatsTool(Tool):
    """Get Claude Memory system statistics."""

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            metadata=ToolMetadata(
                name="memory_stats",
                description="Get Claude Memory system statistics.",
                category=ToolCategory.AI,
                version="1.0.0",
            ),
            parameters=[],
        )

    async def execute(self, **kwargs) -> ToolResult:
        """Get memory stats."""
        from fastband.memory import get_memory_manager

        manager = get_memory_manager()
        stats = manager.get_stats()

        return ToolResult(success=True, data=stats)


class MemoryExtractPatternsTool(Tool):
    """Run pattern extraction from resolved tickets."""

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            metadata=ToolMetadata(
                name="memory_extract_patterns",
                description=(
                    "Run pattern extraction for cross-session learning. "
                    "Analyzes resolved tickets to find common fix patterns. "
                    "Run periodically (weekly recommended)."
                ),
                category=ToolCategory.AI,
                version="1.0.0",
            ),
            parameters=[],
        )

    async def execute(self, **kwargs) -> ToolResult:
        """Extract patterns."""
        from fastband.memory import get_memory_manager

        manager = get_memory_manager()
        result = manager.extract_fix_patterns()

        return ToolResult(success=True, data=result)


class MemoryPruneTool(Tool):
    """Prune stale memories (self-healing maintenance)."""

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            metadata=ToolMetadata(
                name="memory_prune",
                description=(
                    "Prune stale memories (self-healing maintenance). "
                    "Removes old memories below relevance threshold."
                ),
                category=ToolCategory.AI,
                version="1.0.0",
            ),
            parameters=[
                ToolParameter(
                    name="dry_run",
                    type="boolean",
                    description="If True, show what would be pruned without deleting",
                    required=False,
                    default=True,
                ),
            ],
        )

    async def execute(self, dry_run: bool = True, **kwargs) -> ToolResult:
        """Prune stale memories."""
        from fastband.memory import get_memory_manager

        manager = get_memory_manager()
        result = manager.prune_stale_memories(dry_run=dry_run)

        return ToolResult(success=True, data=result)


# =============================================================================
# TIERED MEMORY TOOLS (New Architecture)
# =============================================================================


class MemoryBudgetTool(Tool):
    """Get and manage token budget for agent sessions."""

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            metadata=ToolMetadata(
                name="memory_budget",
                description=(
                    "Get token budget status for current session. "
                    "Shows allocated/used tokens, tier, and handoff thresholds. "
                    "At 60%: prepare handoff. At 80%: immediate handoff required."
                ),
                category=ToolCategory.AI,
                version="1.0.0",
            ),
            parameters=[
                ToolParameter(
                    name="session_id",
                    type="string",
                    description="Session ID to check budget for",
                    required=True,
                ),
                ToolParameter(
                    name="expand",
                    type="boolean",
                    description="Manually expand to next tier if needed",
                    required=False,
                    default=False,
                ),
            ],
        )

    async def execute(
        self,
        session_id: str,
        expand: bool = False,
        **kwargs,
    ) -> ToolResult:
        """Get budget status."""
        from fastband.memory import get_budget_manager

        manager = get_budget_manager()
        budget = manager.get_budget(session_id)

        if not budget:
            return ToolResult(
                success=False,
                error=f"No budget found for session: {session_id}",
            )

        if expand:
            expanded = budget.expand("Manual expansion requested")
            if not expanded:
                return ToolResult(
                    success=False,
                    error="Already at maximum tier",
                    data=budget.to_dict(),
                )

        return ToolResult(
            success=True,
            data={
                **budget.to_dict(),
                "should_handoff": budget.should_handoff,
                "must_handoff": budget.must_handoff,
                "usage_percentage": round(budget.usage_percentage, 1),
                "available_tokens": budget.available_tokens,
            },
        )


class MemoryTierStatusTool(Tool):
    """Get tiered memory status across all tiers."""

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            metadata=ToolMetadata(
                name="memory_tier_status",
                description=(
                    "Get tiered memory status showing items across all 5 tiers "
                    "(Hot, Warm, Cool, Cold, Frozen). Use to monitor memory distribution."
                ),
                category=ToolCategory.AI,
                version="1.0.0",
            ),
            parameters=[
                ToolParameter(
                    name="session_id",
                    type="string",
                    description="Session ID to get tier status for",
                    required=True,
                ),
            ],
        )

    async def execute(self, session_id: str, **kwargs) -> ToolResult:
        """Get tier status."""
        from fastband.memory import get_tiered_memory_manager

        manager = get_tiered_memory_manager()
        store = manager.get_store(session_id)

        if not store:
            return ToolResult(
                success=False,
                error=f"No memory store found for session: {session_id}",
            )

        return ToolResult(
            success=True,
            data=store.get_tier_stats(),
        )


class MemoryHandoffPrepareTool(Tool):
    """Prepare a handoff packet for agent transition."""

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            metadata=ToolMetadata(
                name="memory_handoff_prepare",
                description=(
                    "Prepare a handoff packet when reaching token budget thresholds. "
                    "Creates a complete context package for the next agent. "
                    "Call this at 60% budget usage (warning) or 80% (critical)."
                ),
                category=ToolCategory.AI,
                version="1.0.0",
            ),
            parameters=[
                ToolParameter(
                    name="session_id",
                    type="string",
                    description="Current session ID",
                    required=True,
                ),
                ToolParameter(
                    name="agent_name",
                    type="string",
                    description="Current agent name (e.g., FB_Agent1)",
                    required=True,
                ),
                ToolParameter(
                    name="ticket_id",
                    type="string",
                    description="Current ticket being worked on",
                    required=True,
                ),
                ToolParameter(
                    name="ticket_status",
                    type="string",
                    description="Current ticket status",
                    required=True,
                ),
                ToolParameter(
                    name="ticket_summary",
                    type="string",
                    description="Brief summary of ticket and work done",
                    required=True,
                ),
                ToolParameter(
                    name="completed_tasks",
                    type="array",
                    description="List of completed tasks",
                    required=False,
                ),
                ToolParameter(
                    name="pending_tasks",
                    type="array",
                    description="List of pending tasks",
                    required=False,
                ),
                ToolParameter(
                    name="current_task",
                    type="string",
                    description="Task currently in progress",
                    required=False,
                ),
                ToolParameter(
                    name="files_modified",
                    type="array",
                    description="List of files modified",
                    required=False,
                ),
                ToolParameter(
                    name="handoff_notes",
                    type="string",
                    description="Notes for the next agent",
                    required=False,
                ),
            ],
        )

    async def execute(
        self,
        session_id: str,
        agent_name: str,
        ticket_id: str,
        ticket_status: str,
        ticket_summary: str,
        completed_tasks: Optional[List[str]] = None,
        pending_tasks: Optional[List[str]] = None,
        current_task: Optional[str] = None,
        files_modified: Optional[List[str]] = None,
        handoff_notes: Optional[str] = None,
        **kwargs,
    ) -> ToolResult:
        """Prepare handoff packet."""
        from fastband.memory import (
            get_handoff_manager,
            get_tiered_memory_manager,
            get_budget_manager,
            HandoffReason,
            HandoffPriority,
        )

        # Determine reason and priority from budget
        budget_manager = get_budget_manager()
        budget = budget_manager.get_budget(session_id)

        if budget and budget.must_handoff:
            reason = HandoffReason.BUDGET_CRITICAL
            priority = HandoffPriority.IMMEDIATE
        elif budget and budget.should_handoff:
            reason = HandoffReason.BUDGET_WARNING
            priority = HandoffPriority.NORMAL
        else:
            reason = HandoffReason.AGENT_REQUEST
            priority = HandoffPriority.LOW

        # Get memory store if available
        tiered_manager = get_tiered_memory_manager()
        memory_store = tiered_manager.get_store(session_id)

        # Create handoff packet
        handoff_manager = get_handoff_manager()
        packet = handoff_manager.create_handoff_packet(
            agent_name=agent_name,
            session_id=session_id,
            reason=reason,
            priority=priority,
            ticket_data={
                "ticket_id": ticket_id,
                "status": ticket_status,
                "summary": ticket_summary,
                "completed_tasks": completed_tasks or [],
                "pending_tasks": pending_tasks or [],
                "current_task": current_task,
                "files_modified": files_modified or [],
            },
            memory_store=memory_store,
            notes=handoff_notes or "",
        )

        # Store the packet
        packet_path = handoff_manager.store_packet(packet)

        return ToolResult(
            success=True,
            data={
                "packet_id": packet.packet_id,
                "reason": reason.value,
                "priority": priority.value,
                "stored_at": packet_path,
                "onboarding_context": packet.get_onboarding_context(),
            },
        )


class MemoryHandoffAcceptTool(Tool):
    """Accept a handoff from a previous agent."""

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            metadata=ToolMetadata(
                name="memory_handoff_accept",
                description=(
                    "Accept a handoff packet from a previous agent. "
                    "Returns the onboarding context with all information needed to continue work."
                ),
                category=ToolCategory.AI,
                version="1.0.0",
            ),
            parameters=[
                ToolParameter(
                    name="packet_id",
                    type="string",
                    description="Handoff packet ID to accept",
                    required=True,
                ),
                ToolParameter(
                    name="agent_name",
                    type="string",
                    description="Name of accepting agent (e.g., FB_Agent2)",
                    required=True,
                ),
            ],
        )

    async def execute(
        self,
        packet_id: str,
        agent_name: str,
        **kwargs,
    ) -> ToolResult:
        """Accept handoff."""
        from fastband.memory import get_handoff_manager

        manager = get_handoff_manager()
        packet = manager.accept_handoff(packet_id, agent_name)

        if not packet:
            return ToolResult(
                success=False,
                error=f"Handoff packet not found: {packet_id}",
            )

        return ToolResult(
            success=True,
            data={
                "packet_id": packet.packet_id,
                "from_agent": packet.source_agent,
                "ticket_id": packet.ticket_id,
                "reason": packet.reason.value,
                "priority": packet.priority.value,
                "onboarding_context": packet.get_onboarding_context(),
                "hot_tokens": packet.hot_tokens,
                "warnings": packet.warnings,
            },
        )


class MemoryHandoffListTool(Tool):
    """List pending handoff packets."""

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            metadata=ToolMetadata(
                name="memory_handoff_list",
                description="List all pending handoff packets waiting to be accepted.",
                category=ToolCategory.AI,
                version="1.0.0",
            ),
            parameters=[
                ToolParameter(
                    name="ticket_id",
                    type="string",
                    description="Filter by ticket ID (optional)",
                    required=False,
                ),
            ],
        )

    async def execute(
        self,
        ticket_id: Optional[str] = None,
        **kwargs,
    ) -> ToolResult:
        """List pending handoffs."""
        from fastband.memory import get_handoff_manager

        manager = get_handoff_manager()
        packets = manager.get_pending_handoffs(ticket_id)

        return ToolResult(
            success=True,
            data={
                "count": len(packets),
                "packets": [
                    {
                        "packet_id": p.packet_id,
                        "from_agent": p.source_agent,
                        "ticket_id": p.ticket_id,
                        "reason": p.reason.value,
                        "priority": p.priority.value,
                        "created_at": p.created_at,
                    }
                    for p in packets
                ],
            },
        )


class MemoryBibleLoadTool(Tool):
    """Load Agent Bible sections on demand."""

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            metadata=ToolMetadata(
                name="memory_bible_load",
                description=(
                    "Lazy-load Agent Bible sections. Initially only summary is loaded (~850 tokens). "
                    "Use this to load specific sections when needed (LAW 1-10, STEP 1-8, etc.)."
                ),
                category=ToolCategory.AI,
                version="1.0.0",
            ),
            parameters=[
                ToolParameter(
                    name="session_id",
                    type="string",
                    description="Current session ID",
                    required=True,
                ),
                ToolParameter(
                    name="section_id",
                    type="string",
                    description="Section to load (e.g., 'LAW 5', 'STEP 7'). Use 'summary' for initial load.",
                    required=False,
                ),
                ToolParameter(
                    name="for_tool",
                    type="string",
                    description="Load sections relevant to a specific tool (e.g., 'submit_review')",
                    required=False,
                ),
                ToolParameter(
                    name="load_full",
                    type="boolean",
                    description="Load the complete Bible (emergency use only)",
                    required=False,
                    default=False,
                ),
            ],
        )

    async def execute(
        self,
        session_id: str,
        section_id: Optional[str] = None,
        for_tool: Optional[str] = None,
        load_full: bool = False,
        **kwargs,
    ) -> ToolResult:
        """Load Bible sections."""
        from fastband.memory import get_bible_loader

        loader = get_bible_loader(session_id)

        if load_full:
            content, tokens = loader.get_full_bible()
            return ToolResult(
                success=True,
                data={
                    "type": "full_bible",
                    "content": content,
                    "tokens": tokens,
                    "stats": loader.get_loading_stats(),
                },
            )

        if for_tool:
            sections = loader.get_sections_for_tool(for_tool)
            if not sections:
                return ToolResult(
                    success=True,
                    data={
                        "type": "tool_sections",
                        "message": f"No additional sections needed for tool: {for_tool}",
                        "sections": [],
                        "stats": loader.get_loading_stats(),
                    },
                )
            return ToolResult(
                success=True,
                data={
                    "type": "tool_sections",
                    "tool": for_tool,
                    "sections": [
                        {"content": content, "tokens": tokens}
                        for content, tokens in sections
                    ],
                    "stats": loader.get_loading_stats(),
                },
            )

        if section_id:
            if section_id.lower() == "summary":
                content, tokens = loader.get_summary()
            else:
                result = loader.get_section(section_id)
                if not result:
                    return ToolResult(
                        success=False,
                        error=f"Section not found: {section_id}",
                    )
                content, tokens = result

            return ToolResult(
                success=True,
                data={
                    "type": "section",
                    "section_id": section_id,
                    "content": content,
                    "tokens": tokens,
                    "stats": loader.get_loading_stats(),
                },
            )

        # Default: return summary
        content, tokens = loader.get_summary()
        return ToolResult(
            success=True,
            data={
                "type": "summary",
                "content": content,
                "tokens": tokens,
                "stats": loader.get_loading_stats(),
            },
        )


class MemoryGlobalStatsTool(Tool):
    """Get global memory statistics across all sessions."""

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            metadata=ToolMetadata(
                name="memory_global_stats",
                description=(
                    "Get aggregate memory statistics across all agent sessions. "
                    "Shows total budget usage, active sessions, and tier distribution."
                ),
                category=ToolCategory.AI,
                version="1.0.0",
            ),
            parameters=[],
        )

    async def execute(self, **kwargs) -> ToolResult:
        """Get global stats."""
        from fastband.memory import (
            get_tiered_memory_manager,
            get_budget_manager,
            get_handoff_manager,
        )

        tiered = get_tiered_memory_manager()
        budget = get_budget_manager()
        handoff = get_handoff_manager()

        return ToolResult(
            success=True,
            data={
                "tiered_memory": tiered.get_global_stats(),
                "budget": budget.get_total_usage(),
                "handoffs": handoff.get_handoff_stats(),
            },
        )


# All memory tools (including new tiered architecture)
MEMORY_TOOLS = [
    # Original tools
    MemoryQueryTool,
    MemoryStartSessionTool,
    MemoryAddDiscoveryTool,
    MemoryCommitTool,
    MemoryGetPatternsTool,
    MemoryStatsTool,
    MemoryExtractPatternsTool,
    MemoryPruneTool,
    # New tiered memory tools
    MemoryBudgetTool,
    MemoryTierStatusTool,
    MemoryHandoffPrepareTool,
    MemoryHandoffAcceptTool,
    MemoryHandoffListTool,
    MemoryBibleLoadTool,
    MemoryGlobalStatsTool,
]

__all__ = [
    # Original exports
    "MemoryQueryTool",
    "MemoryStartSessionTool",
    "MemoryAddDiscoveryTool",
    "MemoryCommitTool",
    "MemoryGetPatternsTool",
    "MemoryStatsTool",
    "MemoryExtractPatternsTool",
    "MemoryPruneTool",
    # New tiered memory exports
    "MemoryBudgetTool",
    "MemoryTierStatusTool",
    "MemoryHandoffPrepareTool",
    "MemoryHandoffAcceptTool",
    "MemoryHandoffListTool",
    "MemoryBibleLoadTool",
    "MemoryGlobalStatsTool",
    "MEMORY_TOOLS",
]

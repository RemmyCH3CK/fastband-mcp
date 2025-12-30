"""
Fastband AI Hub - Chat Manager.

Orchestrates AI completions with tool execution and memory integration.

Performance Optimizations (Issue #38):
- Streaming responses via SSE
- Parallel tool execution where safe
- Cached tool schemas
- Batched memory queries
"""

import asyncio
import json
import logging
import time
from collections.abc import AsyncGenerator, Callable
from dataclasses import dataclass, field
from typing import Any

from fastband.hub.models import (
    ChatMessage,
    Conversation,
    HubSession,
    MemoryContext,
    ToolCall,
)

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class PipelineContext:
    """Context passed through the message pipeline.

    Attributes:
        session: Current hub session
        conversation: Current conversation
        user_message: User's input message
        memory_context: Retrieved memory context
        tool_results: Results from tool executions
        response_content: Final response content
        tokens_used: Total tokens consumed
        processing_time_ms: Total processing time
    """

    session: HubSession
    conversation: Conversation
    user_message: ChatMessage
    memory_context: MemoryContext | None = None
    tool_results: list[dict[str, Any]] = field(default_factory=list)
    response_content: str = ""
    tokens_used: int = 0
    processing_time_ms: int = 0


class ToolExecutor:
    """
    Executes tools from the Fastband tool registry.

    Wraps tool execution with error handling, timeouts,
    and result formatting.

    Example:
        executor = ToolExecutor()
        result = await executor.execute("semantic_search", {"query": "auth"})
    """

    def __init__(
        self,
        timeout_seconds: float = 30.0,
        max_parallel: int = 5,
    ):
        """Initialize tool executor.

        Args:
            timeout_seconds: Max execution time per tool
            max_parallel: Max parallel tool executions
        """
        self.timeout = timeout_seconds
        self.max_parallel = max_parallel
        self._tool_registry = None

    def _get_registry(self):
        """Lazy load tool registry."""
        if self._tool_registry is None:
            from fastband.tools import get_registry

            self._tool_registry = get_registry()
        return self._tool_registry

    async def execute(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute a single tool.

        Args:
            tool_name: Name of tool to execute
            arguments: Tool arguments

        Returns:
            Dict with success, result, and error fields
        """
        start_time = time.time()

        try:
            registry = self._get_registry()
            tool = registry.get(tool_name)

            if not tool:
                return {
                    "success": False,
                    "error": f"Tool not found: {tool_name}",
                    "duration_ms": int((time.time() - start_time) * 1000),
                }

            # Execute with timeout
            result = await asyncio.wait_for(
                tool.safe_execute(**arguments),
                timeout=self.timeout,
            )

            duration_ms = int((time.time() - start_time) * 1000)

            return {
                "success": result.success,
                "result": result.data if result.success else None,
                "error": result.error if not result.success else None,
                "duration_ms": duration_ms,
            }

        except asyncio.TimeoutError:
            duration_ms = int((time.time() - start_time) * 1000)
            return {
                "success": False,
                "error": f"Tool execution timed out after {self.timeout}s",
                "duration_ms": duration_ms,
            }
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Tool execution error: {e}")
            return {
                "success": False,
                "error": str(e),
                "duration_ms": duration_ms,
            }

    async def execute_parallel(
        self,
        tool_calls: list[ToolCall],
    ) -> list[dict[str, Any]]:
        """Execute multiple tools in parallel.

        Args:
            tool_calls: List of tool calls to execute

        Returns:
            List of results in same order as inputs
        """
        if not tool_calls:
            return []

        # Limit parallelism
        semaphore = asyncio.Semaphore(self.max_parallel)

        async def execute_with_semaphore(tc: ToolCall) -> dict[str, Any]:
            async with semaphore:
                result = await self.execute(tc.tool_name, tc.arguments)
                result["tool_id"] = tc.tool_id
                result["tool_name"] = tc.tool_name
                return result

        tasks = [execute_with_semaphore(tc) for tc in tool_calls]
        return await asyncio.gather(*tasks)

    def get_available_tools(self) -> list[dict[str, Any]]:
        """Get list of available tools in OpenAI format."""
        registry = self._get_registry()
        tools = []

        for tool in registry.get_available_tools():
            try:
                schema = tool.definition.to_openai_schema()
                tools.append(schema)
            except Exception as e:
                logger.warning(f"Failed to get schema for tool: {e}")

        return tools


class MessagePipeline:
    """
    Pipeline for processing chat messages.

    Stages:
    1. Context enrichment (memory retrieval)
    2. Message formatting
    3. AI completion
    4. Tool execution
    5. Response formatting
    6. Memory storage

    Example:
        pipeline = MessagePipeline(provider, executor, memory)
        response = await pipeline.process(context)
    """

    def __init__(
        self,
        ai_provider,
        tool_executor: ToolExecutor,
        memory_store=None,
    ):
        """Initialize message pipeline.

        Args:
            ai_provider: AI provider for completions
            tool_executor: Tool executor instance
            memory_store: Optional semantic memory store
        """
        self.provider = ai_provider
        self.executor = tool_executor
        self.memory = memory_store
        self._pre_hooks: list[Callable] = []
        self._post_hooks: list[Callable] = []

    def add_pre_hook(self, hook: Callable[[PipelineContext], None]) -> None:
        """Add hook to run before processing."""
        self._pre_hooks.append(hook)

    def add_post_hook(self, hook: Callable[[PipelineContext], None]) -> None:
        """Add hook to run after processing."""
        self._post_hooks.append(hook)

    async def process(
        self,
        context: PipelineContext,
        stream: bool = False,
    ) -> AsyncGenerator[str, None] | ChatMessage:
        """Process a message through the pipeline.

        Args:
            context: Pipeline context with session and message
            stream: Whether to stream the response

        Returns:
            ChatMessage or async generator of content chunks
        """
        start_time = time.time()

        # Run pre-hooks
        for hook in self._pre_hooks:
            await hook(context) if asyncio.iscoroutinefunction(hook) else hook(context)

        try:
            # Stage 1: Context enrichment
            await self._enrich_context(context)

            # Stage 2: Build messages
            messages = self._build_messages(context)

            # Stage 3: AI completion with tools
            if stream:
                async for chunk in self._stream_completion(context, messages):
                    yield chunk
            else:
                response = await self._complete(context, messages)
                context.response_content = response

            # Stage 4: Store in memory
            await self._store_memory(context)

            context.processing_time_ms = int((time.time() - start_time) * 1000)

            # Run post-hooks
            for hook in self._post_hooks:
                await hook(context) if asyncio.iscoroutinefunction(hook) else hook(context)

            if not stream:
                yield ChatMessage.assistant(
                    content=context.response_content,
                    tokens_used=context.tokens_used,
                )

        except Exception as e:
            logger.error(f"Pipeline error: {e}")
            yield ChatMessage.assistant(
                content=f"I encountered an error processing your request: {e}",
                tokens_used=0,
            )

    async def _enrich_context(self, context: PipelineContext) -> None:
        """Enrich context with memory and tool availability."""
        if self.memory and context.session.config.memory_enabled:
            try:
                memory_ctx = await self.memory.query(
                    query=context.user_message.content,
                    user_id=context.session.config.user_id,
                    limit=5,
                )
                context.memory_context = memory_ctx
            except Exception as e:
                logger.warning(f"Memory query failed: {e}")

    def _build_messages(self, context: PipelineContext) -> list[dict[str, Any]]:
        """Build message list for AI completion."""
        messages = []

        # System message
        system_content = self._build_system_prompt(context)
        messages.append({"role": "system", "content": system_content})

        # Conversation history
        history = context.conversation.get_context_messages(
            max_tokens=context.session.config.max_tokens // 2
        )
        for msg in history:
            messages.append(msg.to_api_format())

        # Current user message
        messages.append(context.user_message.to_api_format())

        return messages

    def _build_system_prompt(self, context: PipelineContext) -> str:
        """Build system prompt with context."""
        parts = [
            "You are the Fastband AI Hub assistant, helping users manage their development workflows.",
            "",
            "You have access to tools for:",
            "- Searching and navigating codebases",
            "- Managing tickets and tasks",
            "- Git operations",
            "- Platform health checks",
            "- Configuration management",
            "",
            "Be concise and helpful. Use tools when they can provide accurate information.",
        ]

        # Add memory context
        if context.memory_context and context.memory_context.entries:
            parts.append("")
            parts.append(context.memory_context.to_context_string())

        # Add project context
        if context.session.config.project_path:
            parts.append("")
            parts.append(f"Current project: {context.session.config.project_path}")

        return "\n".join(parts)

    async def _complete(
        self,
        context: PipelineContext,
        messages: list[dict[str, Any]],
    ) -> str:
        """Run AI completion with tool execution loop."""
        tools = self.executor.get_available_tools()
        max_iterations = 10
        iteration = 0

        while iteration < max_iterations:
            iteration += 1

            # Get completion
            response = await self.provider.complete_with_tools(
                messages=messages,
                tools=tools,
                temperature=context.session.config.temperature,
                max_tokens=context.session.config.max_tokens,
            )

            context.tokens_used += response.usage.get("total_tokens", 0)

            # Check for tool calls
            if response.tool_calls:
                # Execute tools
                tool_calls = [
                    ToolCall(
                        tool_id=tc["id"],
                        tool_name=tc["function"]["name"],
                        arguments=json.loads(tc["function"]["arguments"]),
                    )
                    for tc in response.tool_calls
                ]

                results = await self.executor.execute_parallel(tool_calls)
                context.tool_results.extend(results)

                # Add assistant message with tool calls
                messages.append(
                    {
                        "role": "assistant",
                        "content": response.content or "",
                        "tool_calls": response.tool_calls,
                    }
                )

                # Add tool results
                for result in results:
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": result["tool_id"],
                            "content": json.dumps(result.get("result", result.get("error"))),
                        }
                    )

            else:
                # No more tool calls - return response
                return response.content

        logger.warning(f"Max iterations ({max_iterations}) reached in tool loop")
        return "I've reached the maximum number of operations. Please try a simpler request."

    async def _stream_completion(
        self,
        context: PipelineContext,
        messages: list[dict[str, Any]],
    ) -> AsyncGenerator[str, None]:
        """Stream AI completion with tool execution."""
        tools = self.executor.get_available_tools()

        async for chunk in self.provider.stream(
            messages=messages,
            tools=tools,
            temperature=context.session.config.temperature,
            max_tokens=context.session.config.max_tokens,
        ):
            # Handle string chunks (simple streaming)
            if isinstance(chunk, str):
                context.response_content += chunk
                yield chunk
            # Handle object chunks with .content attribute
            elif hasattr(chunk, "content") and chunk.content:
                context.response_content += chunk.content
                yield chunk.content

                # Handle tool calls in stream
                if hasattr(chunk, "tool_calls") and chunk.tool_calls:
                    for tc in chunk.tool_calls:
                        tool_call = ToolCall(
                            tool_id=tc["id"],
                            tool_name=tc["function"]["name"],
                            arguments=json.loads(tc["function"]["arguments"]),
                        )
                        result = await self.executor.execute(
                            tool_call.tool_name,
                            tool_call.arguments,
                        )
                        context.tool_results.append(result)

                        # Yield tool result indicator
                        yield f"\n[Tool: {tool_call.tool_name}]\n"

    async def _store_memory(self, context: PipelineContext) -> None:
        """Store conversation in memory."""
        if not self.memory or not context.session.config.memory_enabled:
            return

        try:
            # Store user message
            await self.memory.store(
                content=context.user_message.content,
                user_id=context.session.config.user_id,
                source="user_message",
                metadata={
                    "conversation_id": context.conversation.conversation_id,
                    "message_id": context.user_message.message_id,
                },
            )

            # Store assistant response
            if context.response_content:
                await self.memory.store(
                    content=context.response_content,
                    user_id=context.session.config.user_id,
                    source="assistant_response",
                    metadata={
                        "conversation_id": context.conversation.conversation_id,
                    },
                )
        except Exception as e:
            logger.warning(f"Failed to store memory: {e}")


class ChatManager:
    """
    High-level chat manager for the AI Hub.

    Coordinates session management, message processing,
    and conversation lifecycle.

    Example:
        manager = ChatManager(provider)
        await manager.initialize()

        response = await manager.send_message(
            session_id="...",
            content="Show me open tickets",
        )
    """

    def __init__(
        self,
        ai_provider,
        session_manager=None,
        memory_store=None,
    ):
        """Initialize chat manager.

        Args:
            ai_provider: AI provider for completions
            session_manager: Optional session manager
            memory_store: Optional semantic memory store
        """
        self.provider = ai_provider
        self._session_manager = session_manager
        self._memory = memory_store
        self._executor = ToolExecutor()
        self._pipeline: MessagePipeline | None = None
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the chat manager."""
        if self._initialized:
            return

        # Get or create session manager
        if self._session_manager is None:
            from fastband.hub.session import get_session_manager

            self._session_manager = get_session_manager()

        # Create pipeline
        self._pipeline = MessagePipeline(
            ai_provider=self.provider,
            tool_executor=self._executor,
            memory_store=self._memory,
        )

        # Start session manager
        await self._session_manager.start()

        self._initialized = True
        logger.info("Chat manager initialized")

    async def shutdown(self) -> None:
        """Shutdown the chat manager."""
        if self._session_manager:
            await self._session_manager.stop()
        self._initialized = False
        logger.info("Chat manager shutdown")

    async def send_message(
        self,
        session_id: str,
        content: str,
        conversation_id: str | None = None,
        stream: bool = False,
    ) -> ChatMessage | AsyncGenerator[str, None]:
        """Send a message in a session.

        Args:
            session_id: Session identifier
            content: Message content
            conversation_id: Optional conversation ID
            stream: Whether to stream response

        Returns:
            ChatMessage or async generator of content chunks

        Raises:
            ValueError: If session not found or rate limited
        """
        if not self._initialized:
            await self.initialize()

        # Get session
        session = self._session_manager.get_session(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        # Check rate limit
        allowed, reason = self._session_manager.check_rate_limit(session.config.user_id)
        if not allowed:
            raise ValueError(reason)

        # Get or create conversation
        if conversation_id:
            conversation = self._session_manager.get_conversation(session_id, conversation_id)
            if not conversation:
                raise ValueError(f"Conversation not found: {conversation_id}")
        else:
            conversation = self._session_manager.create_conversation(session_id)

        # Create user message
        user_message = ChatMessage.user(content)
        conversation.add_message(user_message)

        # Create pipeline context
        context = PipelineContext(
            session=session,
            conversation=conversation,
            user_message=user_message,
        )

        # Process through pipeline
        if stream:
            return self._stream_response(context)
        else:
            async for response in self._pipeline.process(context, stream=False):
                if isinstance(response, ChatMessage):
                    conversation.add_message(response)
                    self._session_manager.record_message(
                        session.config.user_id,
                        response.tokens_used,
                    )
                    return response

    async def _stream_response(
        self,
        context: PipelineContext,
    ) -> AsyncGenerator[str, None]:
        """Stream response chunks."""
        content_parts = []

        async for chunk in self._pipeline.process(context, stream=True):
            if isinstance(chunk, str):
                content_parts.append(chunk)
                yield chunk
            elif isinstance(chunk, ChatMessage):
                # Final message
                context.conversation.add_message(chunk)

        # Record usage after streaming completes
        self._session_manager.record_message(
            context.session.config.user_id,
            context.tokens_used,
        )

    def get_session_manager(self):
        """Get the session manager."""
        return self._session_manager

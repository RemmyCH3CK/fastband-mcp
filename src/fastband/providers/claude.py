"""
Claude AI Provider.

Implements the AIProvider interface for Anthropic's Claude models.
"""

import os
import logging
from typing import Optional, Dict, Any, List, AsyncIterator

from fastband.providers.base import (
    AIProvider,
    ProviderConfig,
    CompletionResponse,
    Capability,
)

logger = logging.getLogger(__name__)

# Default models for different use cases
CLAUDE_MODELS = {
    "default": "claude-sonnet-4-20250514",
    "fast": "claude-3-5-haiku-20241022",
    "powerful": "claude-opus-4-20250514",
    "code": "claude-sonnet-4-20250514",
    "vision": "claude-sonnet-4-20250514",
}


class ClaudeProvider(AIProvider):
    """
    Claude/Anthropic AI provider.

    Supports:
    - Text completion
    - Code generation
    - Vision (image analysis)
    - Tool/function calling
    - Streaming responses
    - Extended thinking (Claude Opus)

    Example:
        provider = ClaudeProvider(ProviderConfig(
            name="claude",
            api_key="sk-ant-...",
            model="claude-sonnet-4-20250514",
        ))

        response = await provider.complete("Explain quantum computing")
    """

    def __init__(self, config: ProviderConfig):
        super().__init__(config)
        self._client = None

    def _validate_config(self) -> None:
        """Validate Claude-specific configuration."""
        if not self.config.api_key:
            # Try environment variable
            self.config.api_key = os.getenv("ANTHROPIC_API_KEY")

        if not self.config.api_key:
            raise ValueError(
                "Claude requires ANTHROPIC_API_KEY. "
                "Set it in config or ANTHROPIC_API_KEY environment variable."
            )

        if not self.config.model:
            self.config.model = CLAUDE_MODELS["default"]

    @property
    def name(self) -> str:
        return "claude"

    @property
    def capabilities(self) -> List[Capability]:
        return [
            Capability.TEXT_COMPLETION,
            Capability.CODE_GENERATION,
            Capability.VISION,
            Capability.FUNCTION_CALLING,
            Capability.STREAMING,
            Capability.LONG_CONTEXT,
            Capability.EXTENDED_THINKING,
        ]

    @property
    def client(self):
        """Lazy-load the Anthropic client."""
        if self._client is None:
            try:
                from anthropic import AsyncAnthropic
                self._client = AsyncAnthropic(api_key=self.config.api_key)
            except ImportError:
                raise ImportError(
                    "anthropic package is required for Claude provider. "
                    "Install with: pip install fastband-mcp[claude]"
                )
        return self._client

    async def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> CompletionResponse:
        """
        Send a completion request to Claude.

        Args:
            prompt: The user prompt
            system_prompt: Optional system prompt
            **kwargs: Additional options (max_tokens, temperature, etc.)

        Returns:
            CompletionResponse with result
        """
        messages = [{"role": "user", "content": prompt}]

        response = await self.client.messages.create(
            model=kwargs.get("model", self.config.model),
            max_tokens=kwargs.get("max_tokens", self.config.max_tokens),
            temperature=kwargs.get("temperature", self.config.temperature),
            system=system_prompt or "",
            messages=messages,
        )

        return CompletionResponse(
            content=response.content[0].text,
            model=response.model,
            provider=self.name,
            usage={
                "prompt_tokens": response.usage.input_tokens,
                "completion_tokens": response.usage.output_tokens,
                "total_tokens": response.usage.input_tokens + response.usage.output_tokens,
            },
            finish_reason=response.stop_reason or "end_turn",
            raw_response=response.model_dump() if hasattr(response, 'model_dump') else None,
        )

    async def complete_with_tools(
        self,
        prompt: str,
        tools: List[Dict[str, Any]],
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> CompletionResponse:
        """
        Complete with tool/function calling support.

        Args:
            prompt: The user prompt
            tools: List of tool definitions (OpenAI format, will be converted)
            system_prompt: Optional system prompt

        Returns:
            Response with potential tool calls
        """
        # Convert OpenAI tool format to Claude format
        claude_tools = self._convert_tools(tools)

        messages = [{"role": "user", "content": prompt}]

        response = await self.client.messages.create(
            model=kwargs.get("model", self.config.model),
            max_tokens=kwargs.get("max_tokens", self.config.max_tokens),
            temperature=kwargs.get("temperature", self.config.temperature),
            system=system_prompt or "",
            messages=messages,
            tools=claude_tools,
        )

        # Extract content (may include tool_use blocks)
        content_parts = []
        tool_calls = []

        for block in response.content:
            if block.type == "text":
                content_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append({
                    "id": block.id,
                    "name": block.name,
                    "arguments": block.input,
                })

        return CompletionResponse(
            content="\n".join(content_parts) if content_parts else "",
            model=response.model,
            provider=self.name,
            usage={
                "prompt_tokens": response.usage.input_tokens,
                "completion_tokens": response.usage.output_tokens,
                "total_tokens": response.usage.input_tokens + response.usage.output_tokens,
            },
            finish_reason=response.stop_reason or "end_turn",
            raw_response={
                "tool_calls": tool_calls,
                "full_response": response.model_dump() if hasattr(response, 'model_dump') else None,
            },
        )

    def _convert_tools(self, openai_tools: List[Dict]) -> List[Dict]:
        """Convert OpenAI tool format to Claude format."""
        claude_tools = []
        for tool in openai_tools:
            if tool.get("type") == "function":
                func = tool["function"]
                claude_tools.append({
                    "name": func["name"],
                    "description": func.get("description", ""),
                    "input_schema": func.get("parameters", {"type": "object", "properties": {}}),
                })
            else:
                # Already in Claude format or simplified format
                claude_tools.append(tool)
        return claude_tools

    async def stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> AsyncIterator[str]:
        """
        Stream completion response.

        Yields:
            Text chunks as they arrive
        """
        messages = [{"role": "user", "content": prompt}]

        async with self.client.messages.stream(
            model=kwargs.get("model", self.config.model),
            max_tokens=kwargs.get("max_tokens", self.config.max_tokens),
            temperature=kwargs.get("temperature", self.config.temperature),
            system=system_prompt or "",
            messages=messages,
        ) as stream:
            async for text in stream.text_stream:
                yield text

    async def analyze_image(
        self,
        image_data: bytes,
        prompt: str,
        image_type: str = "image/png",
        **kwargs
    ) -> CompletionResponse:
        """
        Analyze an image using Claude's vision capability.

        Args:
            image_data: Image bytes
            prompt: Analysis prompt
            image_type: MIME type (image/png, image/jpeg, etc.)

        Returns:
            Analysis response
        """
        import base64

        # Encode image to base64
        image_b64 = base64.b64encode(image_data).decode("utf-8")

        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": image_type,
                            "data": image_b64,
                        },
                    },
                    {
                        "type": "text",
                        "text": prompt,
                    },
                ],
            }
        ]

        response = await self.client.messages.create(
            model=kwargs.get("model", self.config.model),
            max_tokens=kwargs.get("max_tokens", self.config.max_tokens),
            messages=messages,
        )

        return CompletionResponse(
            content=response.content[0].text,
            model=response.model,
            provider=self.name,
            usage={
                "prompt_tokens": response.usage.input_tokens,
                "completion_tokens": response.usage.output_tokens,
                "total_tokens": response.usage.input_tokens + response.usage.output_tokens,
            },
            finish_reason=response.stop_reason or "end_turn",
        )

    def get_recommended_model(self, task: str) -> str:
        """Get recommended model for a specific task type."""
        task_lower = task.lower()

        if "code" in task_lower or "programming" in task_lower:
            return CLAUDE_MODELS["code"]
        if "fast" in task_lower or "quick" in task_lower:
            return CLAUDE_MODELS["fast"]
        if "complex" in task_lower or "reasoning" in task_lower:
            return CLAUDE_MODELS["powerful"]
        if "image" in task_lower or "vision" in task_lower:
            return CLAUDE_MODELS["vision"]

        return self.config.model or CLAUDE_MODELS["default"]

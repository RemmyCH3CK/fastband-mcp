"""
OpenAI AI Provider.

Implements the AIProvider interface for OpenAI's GPT models.
"""

import logging
import os
from collections.abc import AsyncIterator
from typing import Any

from fastband.providers.base import (
    AIProvider,
    Capability,
    CompletionResponse,
    ProviderConfig,
)

logger = logging.getLogger(__name__)

# Default models for different use cases
OPENAI_MODELS = {
    "default": "gpt-4-turbo",
    "fast": "gpt-4o-mini",
    "powerful": "gpt-4o",
    "code": "gpt-4-turbo",
    "vision": "gpt-4o",
}


class OpenAIProvider(AIProvider):
    """
    OpenAI/GPT AI provider.

    Supports:
    - Text completion
    - Code generation
    - Vision (image analysis)
    - Tool/function calling
    - Streaming responses

    Example:
        provider = OpenAIProvider(ProviderConfig(
            name="openai",
            api_key="sk-...",
            model="gpt-4-turbo",
        ))

        response = await provider.complete("Explain quantum computing")
    """

    def __init__(self, config: ProviderConfig):
        super().__init__(config)
        self._client = None

    def _validate_config(self) -> None:
        """Validate OpenAI-specific configuration."""
        if not self.config.api_key:
            self.config.api_key = os.getenv("OPENAI_API_KEY")

        if not self.config.api_key:
            raise ValueError(
                "OpenAI requires OPENAI_API_KEY. "
                "Set it in config or OPENAI_API_KEY environment variable."
            )

        if not self.config.model:
            self.config.model = OPENAI_MODELS["default"]

    @property
    def name(self) -> str:
        return "openai"

    @property
    def capabilities(self) -> list[Capability]:
        return [
            Capability.TEXT_COMPLETION,
            Capability.CODE_GENERATION,
            Capability.VISION,
            Capability.FUNCTION_CALLING,
            Capability.STREAMING,
        ]

    @property
    def client(self):
        """Lazy-load the OpenAI client."""
        if self._client is None:
            try:
                from openai import AsyncOpenAI

                self._client = AsyncOpenAI(api_key=self.config.api_key)
            except ImportError:
                raise ImportError(
                    "openai package is required for OpenAI provider. "
                    "Install with: pip install fastband-mcp[openai]"
                )
        return self._client

    async def complete(
        self, prompt: str, system_prompt: str | None = None, **kwargs
    ) -> CompletionResponse:
        """
        Send a completion request to OpenAI.

        Args:
            prompt: The user prompt
            system_prompt: Optional system prompt
            **kwargs: Additional options

        Returns:
            CompletionResponse with result
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = await self.client.chat.completions.create(
            model=kwargs.get("model", self.config.model),
            messages=messages,
            max_tokens=kwargs.get("max_tokens", self.config.max_tokens),
            temperature=kwargs.get("temperature", self.config.temperature),
        )

        choice = response.choices[0]

        return CompletionResponse(
            content=choice.message.content or "",
            model=response.model,
            provider=self.name,
            usage={
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            },
            finish_reason=choice.finish_reason or "stop",
            raw_response=response.model_dump() if hasattr(response, "model_dump") else None,
        )

    async def complete_with_tools(
        self, prompt: str, tools: list[dict[str, Any]], system_prompt: str | None = None, **kwargs
    ) -> CompletionResponse:
        """
        Complete with tool/function calling support.

        Args:
            prompt: The user prompt
            tools: List of tool definitions (OpenAI format)
            system_prompt: Optional system prompt

        Returns:
            Response with potential tool calls
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = await self.client.chat.completions.create(
            model=kwargs.get("model", self.config.model),
            messages=messages,
            max_tokens=kwargs.get("max_tokens", self.config.max_tokens),
            temperature=kwargs.get("temperature", self.config.temperature),
            tools=tools,
        )

        choice = response.choices[0]

        # Extract tool calls if present
        tool_calls = []
        if choice.message.tool_calls:
            for tc in choice.message.tool_calls:
                tool_calls.append(
                    {
                        "id": tc.id,
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    }
                )

        return CompletionResponse(
            content=choice.message.content or "",
            model=response.model,
            provider=self.name,
            usage={
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            },
            finish_reason=choice.finish_reason or "stop",
            raw_response={
                "tool_calls": tool_calls,
                "full_response": response.model_dump() if hasattr(response, "model_dump") else None,
            },
        )

    async def stream(
        self, prompt: str, system_prompt: str | None = None, **kwargs
    ) -> AsyncIterator[str]:
        """
        Stream completion response.

        Yields:
            Text chunks as they arrive
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        stream = await self.client.chat.completions.create(
            model=kwargs.get("model", self.config.model),
            messages=messages,
            max_tokens=kwargs.get("max_tokens", self.config.max_tokens),
            temperature=kwargs.get("temperature", self.config.temperature),
            stream=True,
        )

        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    async def analyze_image(
        self, image_data: bytes, prompt: str, image_type: str = "image/png", **kwargs
    ) -> CompletionResponse:
        """
        Analyze an image using GPT-4 Vision.

        Args:
            image_data: Image bytes
            prompt: Analysis prompt
            image_type: MIME type

        Returns:
            Analysis response
        """
        import base64

        image_b64 = base64.b64encode(image_data).decode("utf-8")
        image_url = f"data:{image_type};base64,{image_b64}"

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_url}},
                ],
            }
        ]

        # Use vision-capable model
        model = kwargs.get("model", OPENAI_MODELS["vision"])

        response = await self.client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=kwargs.get("max_tokens", self.config.max_tokens),
        )

        choice = response.choices[0]

        return CompletionResponse(
            content=choice.message.content or "",
            model=response.model,
            provider=self.name,
            usage={
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            },
            finish_reason=choice.finish_reason or "stop",
        )

    def get_recommended_model(self, task: str) -> str:
        """Get recommended model for a specific task type."""
        task_lower = task.lower()

        if "code" in task_lower or "programming" in task_lower:
            return OPENAI_MODELS["code"]
        if "fast" in task_lower or "quick" in task_lower:
            return OPENAI_MODELS["fast"]
        if "complex" in task_lower or "reasoning" in task_lower:
            return OPENAI_MODELS["powerful"]
        if "image" in task_lower or "vision" in task_lower:
            return OPENAI_MODELS["vision"]

        return self.config.model or OPENAI_MODELS["default"]

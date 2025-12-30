"""
Google Gemini AI Provider.

Implements the AIProvider interface for Google's Gemini models.
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
GEMINI_MODELS = {
    "default": "gemini-1.5-pro",
    "fast": "gemini-1.5-flash",
    "powerful": "gemini-1.5-pro",
    "code": "gemini-1.5-pro",
    "vision": "gemini-1.5-pro",
}


class GeminiProvider(AIProvider):
    """
    Google Gemini AI provider.

    Supports:
    - Text completion
    - Code generation
    - Vision (image analysis)
    - Function calling
    - Streaming responses
    - Long context (up to 1M tokens)

    Example:
        provider = GeminiProvider(ProviderConfig(
            name="gemini",
            api_key="...",
            model="gemini-1.5-pro",
        ))

        response = await provider.complete("Explain quantum computing")
    """

    def __init__(self, config: ProviderConfig):
        super().__init__(config)
        self._model = None
        self._genai = None

    def _validate_config(self) -> None:
        """Validate Gemini-specific configuration."""
        if not self.config.api_key:
            self.config.api_key = os.getenv("GOOGLE_API_KEY")

        if not self.config.api_key:
            raise ValueError(
                "Gemini requires GOOGLE_API_KEY. "
                "Set it in config or GOOGLE_API_KEY environment variable."
            )

        if not self.config.model:
            self.config.model = GEMINI_MODELS["default"]

    @property
    def name(self) -> str:
        return "gemini"

    @property
    def capabilities(self) -> list[Capability]:
        return [
            Capability.TEXT_COMPLETION,
            Capability.CODE_GENERATION,
            Capability.VISION,
            Capability.FUNCTION_CALLING,
            Capability.STREAMING,
            Capability.LONG_CONTEXT,
        ]

    def _get_genai(self):
        """Lazy-load the Google generativeai module."""
        if self._genai is None:
            try:
                import google.generativeai as genai

                genai.configure(api_key=self.config.api_key)
                self._genai = genai
            except ImportError:
                raise ImportError(
                    "google-generativeai package is required for Gemini provider. "
                    "Install with: pip install fastband-mcp[gemini]"
                )
        return self._genai

    def _get_model(self, model_name: str | None = None):
        """Get or create a Gemini model instance."""
        genai = self._get_genai()
        name = model_name or self.config.model
        return genai.GenerativeModel(name)

    async def complete(
        self, prompt: str, system_prompt: str | None = None, **kwargs
    ) -> CompletionResponse:
        """
        Send a completion request to Gemini.

        Args:
            prompt: The user prompt
            system_prompt: Optional system prompt
            **kwargs: Additional options

        Returns:
            CompletionResponse with result
        """
        model = self._get_model(kwargs.get("model"))

        # Combine system prompt with user prompt
        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"

        # Configure generation
        generation_config = {
            "max_output_tokens": kwargs.get("max_tokens", self.config.max_tokens),
            "temperature": kwargs.get("temperature", self.config.temperature),
        }

        response = await model.generate_content_async(
            full_prompt,
            generation_config=generation_config,
        )

        # Extract usage if available
        usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            usage = {
                "prompt_tokens": getattr(response.usage_metadata, "prompt_token_count", 0),
                "completion_tokens": getattr(response.usage_metadata, "candidates_token_count", 0),
                "total_tokens": getattr(response.usage_metadata, "total_token_count", 0),
            }

        return CompletionResponse(
            content=response.text,
            model=self.config.model,
            provider=self.name,
            usage=usage,
            finish_reason="stop",
        )

    async def complete_with_tools(
        self, prompt: str, tools: list[dict[str, Any]], system_prompt: str | None = None, **kwargs
    ) -> CompletionResponse:
        """
        Complete with tool/function calling support.

        Args:
            prompt: The user prompt
            tools: List of tool definitions
            system_prompt: Optional system prompt

        Returns:
            Response with potential tool calls
        """
        genai = self._get_genai()

        # Convert tools to Gemini format
        gemini_tools = self._convert_tools(tools)

        model = genai.GenerativeModel(
            model_name=kwargs.get("model", self.config.model),
            tools=gemini_tools,
        )

        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"

        response = await model.generate_content_async(full_prompt)

        # Extract function calls
        tool_calls = []
        content = ""

        for part in response.parts:
            if hasattr(part, "text"):
                content += part.text
            if hasattr(part, "function_call"):
                fc = part.function_call
                tool_calls.append(
                    {
                        "name": fc.name,
                        "arguments": dict(fc.args),
                    }
                )

        return CompletionResponse(
            content=content,
            model=self.config.model,
            provider=self.name,
            usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            finish_reason="stop",
            raw_response={"tool_calls": tool_calls},
        )

    def _convert_tools(self, openai_tools: list[dict]) -> list:
        """Convert OpenAI tool format to Gemini format."""
        genai = self._get_genai()

        function_declarations = []
        for tool in openai_tools:
            if tool.get("type") == "function":
                func = tool["function"]
                function_declarations.append(
                    {
                        "name": func["name"],
                        "description": func.get("description", ""),
                        "parameters": func.get("parameters", {}),
                    }
                )

        if function_declarations:
            return [genai.protos.Tool(function_declarations=function_declarations)]
        return []

    async def stream(
        self, prompt: str, system_prompt: str | None = None, **kwargs
    ) -> AsyncIterator[str]:
        """
        Stream completion response.

        Yields:
            Text chunks as they arrive
        """
        model = self._get_model(kwargs.get("model"))

        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"

        response = await model.generate_content_async(
            full_prompt,
            stream=True,
        )

        async for chunk in response:
            if chunk.text:
                yield chunk.text

    async def analyze_image(
        self, image_data: bytes, prompt: str, image_type: str = "image/png", **kwargs
    ) -> CompletionResponse:
        """
        Analyze an image using Gemini's vision capability.

        Args:
            image_data: Image bytes
            prompt: Analysis prompt
            image_type: MIME type

        Returns:
            Analysis response
        """
        self._get_genai()
        model = self._get_model(GEMINI_MODELS["vision"])

        # Create image part
        image_part = {
            "mime_type": image_type,
            "data": image_data,
        }

        response = await model.generate_content_async([prompt, image_part])

        return CompletionResponse(
            content=response.text,
            model=GEMINI_MODELS["vision"],
            provider=self.name,
            usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            finish_reason="stop",
        )

    def get_recommended_model(self, task: str) -> str:
        """Get recommended model for a specific task type."""
        task_lower = task.lower()

        if "fast" in task_lower or "quick" in task_lower:
            return GEMINI_MODELS["fast"]
        if "image" in task_lower or "vision" in task_lower:
            return GEMINI_MODELS["vision"]

        return self.config.model or GEMINI_MODELS["default"]

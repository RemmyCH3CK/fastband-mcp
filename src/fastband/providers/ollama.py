"""
Ollama AI Provider (Local LLMs).

Implements the AIProvider interface for locally-running Ollama models.
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

# Default models
OLLAMA_MODELS = {
    "default": "llama3.2",
    "fast": "llama3.2",
    "powerful": "llama3.2:70b",
    "code": "codellama",
    "vision": "llava",
}


class OllamaProvider(AIProvider):
    """
    Ollama provider for local LLM inference.

    Ollama allows running open-source models locally without API keys.
    See https://ollama.ai for installation.

    Supports:
    - Text completion
    - Code generation
    - Vision (with llava model)
    - Streaming responses

    Note: Function calling support varies by model.

    Example:
        provider = OllamaProvider(ProviderConfig(
            name="ollama",
            model="llama3.2",
            base_url="http://localhost:11434",  # Default Ollama URL
        ))

        response = await provider.complete("Explain quantum computing")
    """

    def __init__(self, config: ProviderConfig):
        super().__init__(config)
        self._client = None

    def _validate_config(self) -> None:
        """Validate Ollama-specific configuration."""
        # No API key required for local Ollama
        if not self.config.base_url:
            self.config.base_url = os.getenv("OLLAMA_HOST", "http://localhost:11434")

        if not self.config.model:
            self.config.model = OLLAMA_MODELS["default"]

    @property
    def name(self) -> str:
        return "ollama"

    @property
    def capabilities(self) -> list[Capability]:
        # Base capabilities - vision depends on model
        return [
            Capability.TEXT_COMPLETION,
            Capability.CODE_GENERATION,
            Capability.STREAMING,
        ]

    @property
    def client(self):
        """Lazy-load the Ollama client."""
        if self._client is None:
            try:
                from ollama import AsyncClient

                self._client = AsyncClient(host=self.config.base_url)
            except ImportError:
                raise ImportError(
                    "ollama package is required for Ollama provider. "
                    "Install with: pip install fastband-mcp[ollama]"
                )
        return self._client

    async def complete(
        self, prompt: str, system_prompt: str | None = None, **kwargs
    ) -> CompletionResponse:
        """
        Send a completion request to Ollama.

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

        response = await self.client.chat(
            model=kwargs.get("model", self.config.model),
            messages=messages,
            options={
                "temperature": kwargs.get("temperature", self.config.temperature),
                "num_predict": kwargs.get("max_tokens", self.config.max_tokens),
            },
        )

        # Extract usage info
        usage = {
            "prompt_tokens": response.get("prompt_eval_count", 0),
            "completion_tokens": response.get("eval_count", 0),
            "total_tokens": response.get("prompt_eval_count", 0) + response.get("eval_count", 0),
        }

        return CompletionResponse(
            content=response["message"]["content"],
            model=response.get("model", self.config.model),
            provider=self.name,
            usage=usage,
            finish_reason="stop",
            raw_response=response,
        )

    async def complete_with_tools(
        self, prompt: str, tools: list[dict[str, Any]], system_prompt: str | None = None, **kwargs
    ) -> CompletionResponse:
        """
        Complete with tool/function calling support.

        Note: Tool calling support in Ollama depends on the model.
        Some models like llama3.1+ support it, others don't.

        Args:
            prompt: The user prompt
            tools: List of tool definitions
            system_prompt: Optional system prompt

        Returns:
            Response with potential tool calls
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        # Convert tools to Ollama format
        ollama_tools = self._convert_tools(tools)

        try:
            response = await self.client.chat(
                model=kwargs.get("model", self.config.model),
                messages=messages,
                tools=ollama_tools if ollama_tools else None,
                options={
                    "temperature": kwargs.get("temperature", self.config.temperature),
                    "num_predict": kwargs.get("max_tokens", self.config.max_tokens),
                },
            )

            # Extract tool calls if present
            tool_calls = []
            message = response.get("message", {})
            if message.get("tool_calls"):
                for tc in message["tool_calls"]:
                    tool_calls.append(
                        {
                            "name": tc["function"]["name"],
                            "arguments": tc["function"]["arguments"],
                        }
                    )

            return CompletionResponse(
                content=message.get("content", ""),
                model=response.get("model", self.config.model),
                provider=self.name,
                usage={
                    "prompt_tokens": response.get("prompt_eval_count", 0),
                    "completion_tokens": response.get("eval_count", 0),
                    "total_tokens": 0,
                },
                finish_reason="stop",
                raw_response={"tool_calls": tool_calls},
            )

        except Exception as e:
            # Fall back to regular completion if tools not supported
            logger.warning(f"Tool calling failed, falling back to regular completion: {e}")
            return await self.complete(prompt, system_prompt, **kwargs)

    def _convert_tools(self, openai_tools: list[dict]) -> list[dict]:
        """Convert OpenAI tool format to Ollama format."""
        ollama_tools = []
        for tool in openai_tools:
            if tool.get("type") == "function":
                func = tool["function"]
                ollama_tools.append(
                    {
                        "type": "function",
                        "function": {
                            "name": func["name"],
                            "description": func.get("description", ""),
                            "parameters": func.get("parameters", {}),
                        },
                    }
                )
        return ollama_tools

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

        stream = await self.client.chat(
            model=kwargs.get("model", self.config.model),
            messages=messages,
            stream=True,
            options={
                "temperature": kwargs.get("temperature", self.config.temperature),
                "num_predict": kwargs.get("max_tokens", self.config.max_tokens),
            },
        )

        async for chunk in stream:
            if chunk.get("message", {}).get("content"):
                yield chunk["message"]["content"]

    async def analyze_image(
        self, image_data: bytes, prompt: str, image_type: str = "image/png", **kwargs
    ) -> CompletionResponse:
        """
        Analyze an image using a vision-capable model (e.g., llava).

        Args:
            image_data: Image bytes
            prompt: Analysis prompt
            image_type: MIME type

        Returns:
            Analysis response
        """
        import base64

        # Use a vision model
        model = kwargs.get("model", OLLAMA_MODELS["vision"])

        # Encode image
        image_b64 = base64.b64encode(image_data).decode("utf-8")

        messages = [
            {
                "role": "user",
                "content": prompt,
                "images": [image_b64],
            }
        ]

        response = await self.client.chat(
            model=model,
            messages=messages,
        )

        return CompletionResponse(
            content=response["message"]["content"],
            model=model,
            provider=self.name,
            usage={
                "prompt_tokens": response.get("prompt_eval_count", 0),
                "completion_tokens": response.get("eval_count", 0),
                "total_tokens": 0,
            },
            finish_reason="stop",
        )

    async def list_models(self) -> list[str]:
        """
        List available models in Ollama.

        Returns:
            List of model names
        """
        response = await self.client.list()
        return [m["name"] for m in response.get("models", [])]

    async def pull_model(self, model_name: str) -> bool:
        """
        Pull a model from Ollama registry.

        Args:
            model_name: Name of model to pull

        Returns:
            True if successful
        """
        try:
            await self.client.pull(model_name)
            return True
        except Exception as e:
            logger.error(f"Failed to pull model {model_name}: {e}")
            return False

    def get_recommended_model(self, task: str) -> str:
        """Get recommended model for a specific task type."""
        task_lower = task.lower()

        if "code" in task_lower or "programming" in task_lower:
            return OLLAMA_MODELS["code"]
        if "image" in task_lower or "vision" in task_lower:
            return OLLAMA_MODELS["vision"]

        return self.config.model or OLLAMA_MODELS["default"]

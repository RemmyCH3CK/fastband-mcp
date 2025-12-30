"""
Base AI Provider interface.

All AI providers (Claude, OpenAI, Gemini, Ollama) implement this interface
for consistent behavior across the platform.
"""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Capability(Enum):
    """AI provider capabilities."""

    TEXT_COMPLETION = "text_completion"
    CODE_GENERATION = "code_generation"
    VISION = "vision"
    FUNCTION_CALLING = "function_calling"
    STREAMING = "streaming"
    LONG_CONTEXT = "long_context"
    EXTENDED_THINKING = "extended_thinking"


@dataclass
class ProviderConfig:
    """Configuration for an AI provider."""

    name: str
    api_key: str | None = None
    base_url: str | None = None
    model: str | None = None
    max_tokens: int = 4096
    temperature: float = 0.7
    timeout: int = 120
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class CompletionResponse:
    """Standardized response from any AI provider."""

    content: str
    model: str
    provider: str
    usage: dict[str, int]
    finish_reason: str
    raw_response: dict | None = None


class AIProvider(ABC):
    """
    Abstract base class for AI providers.

    All providers must implement this interface to ensure
    consistent behavior across Claude, OpenAI, Gemini, etc.
    """

    def __init__(self, config: ProviderConfig):
        self.config = config
        self._validate_config()

    @abstractmethod
    def _validate_config(self) -> None:
        """Validate provider-specific configuration."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Return provider name (claude, openai, gemini, etc.)."""
        pass

    @property
    @abstractmethod
    def capabilities(self) -> list[Capability]:
        """Return list of supported capabilities."""
        pass

    @abstractmethod
    async def complete(
        self, prompt: str, system_prompt: str | None = None, **kwargs
    ) -> CompletionResponse:
        """Send a completion request to the AI."""
        pass

    @abstractmethod
    async def complete_with_tools(
        self, prompt: str, tools: list[dict[str, Any]], system_prompt: str | None = None, **kwargs
    ) -> CompletionResponse:
        """Complete with tool/function calling support."""
        pass

    @abstractmethod
    async def stream(
        self, prompt: str, system_prompt: str | None = None, **kwargs
    ) -> AsyncIterator[str]:
        """Stream completion response."""
        pass

    async def analyze_image(self, image_data: bytes, prompt: str, **kwargs) -> CompletionResponse:
        """Analyze an image (vision capability)."""
        raise NotImplementedError("Vision not supported by this provider")

    def supports(self, capability: Capability) -> bool:
        """Check if provider supports a capability."""
        return capability in self.capabilities

    def get_recommended_model(self, task: str) -> str:
        """Get recommended model for a specific task type."""
        return self.config.model or ""

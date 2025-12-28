"""Tests for AI providers."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import os

from fastband.providers.base import (
    AIProvider,
    ProviderConfig,
    CompletionResponse,
    Capability,
)
from fastband.providers.registry import ProviderRegistry, get_provider


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def mock_env(monkeypatch):
    """Set up mock environment variables for testing."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-anthropic-key")
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    monkeypatch.setenv("GOOGLE_API_KEY", "test-google-key")


@pytest.fixture
def claude_config():
    """Create Claude provider config."""
    return ProviderConfig(
        name="claude",
        api_key="test-key",
        model="claude-sonnet-4-20250514",
    )


@pytest.fixture
def openai_config():
    """Create OpenAI provider config."""
    return ProviderConfig(
        name="openai",
        api_key="test-key",
        model="gpt-4-turbo",
    )


@pytest.fixture
def gemini_config():
    """Create Gemini provider config."""
    return ProviderConfig(
        name="gemini",
        api_key="test-key",
        model="gemini-1.5-pro",
    )


@pytest.fixture
def ollama_config():
    """Create Ollama provider config."""
    return ProviderConfig(
        name="ollama",
        model="llama3.2",
        base_url="http://localhost:11434",
    )


# =============================================================================
# PROVIDER CONFIG TESTS
# =============================================================================

class TestProviderConfig:
    """Tests for ProviderConfig."""

    def test_default_values(self):
        """Test default configuration values."""
        config = ProviderConfig(name="test")

        assert config.name == "test"
        assert config.max_tokens == 4096
        assert config.temperature == 0.7
        assert config.timeout == 120

    def test_custom_values(self):
        """Test custom configuration values."""
        config = ProviderConfig(
            name="test",
            api_key="key123",
            model="test-model",
            max_tokens=2000,
            temperature=0.5,
        )

        assert config.api_key == "key123"
        assert config.model == "test-model"
        assert config.max_tokens == 2000
        assert config.temperature == 0.5


class TestCompletionResponse:
    """Tests for CompletionResponse."""

    def test_response_structure(self):
        """Test response structure."""
        response = CompletionResponse(
            content="Hello, World!",
            model="test-model",
            provider="test",
            usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            finish_reason="stop",
        )

        assert response.content == "Hello, World!"
        assert response.model == "test-model"
        assert response.provider == "test"
        assert response.usage["total_tokens"] == 15
        assert response.finish_reason == "stop"


# =============================================================================
# CLAUDE PROVIDER TESTS
# =============================================================================

class TestClaudeProvider:
    """Tests for Claude provider."""

    def test_init_with_config(self, claude_config):
        """Test provider initialization with config."""
        from fastband.providers.claude import ClaudeProvider

        provider = ClaudeProvider(claude_config)

        assert provider.name == "claude"
        assert provider.config.api_key == "test-key"
        assert provider.config.model == "claude-sonnet-4-20250514"

    def test_capabilities(self, claude_config):
        """Test Claude capabilities."""
        from fastband.providers.claude import ClaudeProvider

        provider = ClaudeProvider(claude_config)

        assert Capability.TEXT_COMPLETION in provider.capabilities
        assert Capability.CODE_GENERATION in provider.capabilities
        assert Capability.VISION in provider.capabilities
        assert Capability.FUNCTION_CALLING in provider.capabilities
        assert Capability.STREAMING in provider.capabilities
        assert Capability.EXTENDED_THINKING in provider.capabilities

    def test_supports_capability(self, claude_config):
        """Test capability checking."""
        from fastband.providers.claude import ClaudeProvider

        provider = ClaudeProvider(claude_config)

        assert provider.supports(Capability.VISION) is True
        assert provider.supports(Capability.EXTENDED_THINKING) is True

    def test_recommended_model(self, claude_config):
        """Test model recommendation."""
        from fastband.providers.claude import ClaudeProvider

        provider = ClaudeProvider(claude_config)

        assert "claude" in provider.get_recommended_model("code review")
        assert "haiku" in provider.get_recommended_model("fast task")

    @pytest.mark.asyncio
    async def test_complete_mocked(self, claude_config):
        """Test completion with mocked client."""
        from fastband.providers.claude import ClaudeProvider

        provider = ClaudeProvider(claude_config)

        # Mock the Anthropic client
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Test response")]
        mock_response.model = "claude-sonnet-4-20250514"
        mock_response.usage = MagicMock(input_tokens=10, output_tokens=20)
        mock_response.stop_reason = "end_turn"
        mock_response.model_dump = MagicMock(return_value={})

        with patch.object(provider, '_client') as mock_client:
            mock_client.messages.create = AsyncMock(return_value=mock_response)
            provider._client = mock_client

            response = await provider.complete("Test prompt")

            assert response.content == "Test response"
            assert response.provider == "claude"
            assert response.usage["total_tokens"] == 30


# =============================================================================
# OPENAI PROVIDER TESTS
# =============================================================================

class TestOpenAIProvider:
    """Tests for OpenAI provider."""

    def test_init_with_config(self, openai_config):
        """Test provider initialization with config."""
        from fastband.providers.openai import OpenAIProvider

        provider = OpenAIProvider(openai_config)

        assert provider.name == "openai"
        assert provider.config.api_key == "test-key"
        assert provider.config.model == "gpt-4-turbo"

    def test_capabilities(self, openai_config):
        """Test OpenAI capabilities."""
        from fastband.providers.openai import OpenAIProvider

        provider = OpenAIProvider(openai_config)

        assert Capability.TEXT_COMPLETION in provider.capabilities
        assert Capability.CODE_GENERATION in provider.capabilities
        assert Capability.VISION in provider.capabilities
        assert Capability.FUNCTION_CALLING in provider.capabilities
        assert Capability.STREAMING in provider.capabilities

    def test_recommended_model(self, openai_config):
        """Test model recommendation."""
        from fastband.providers.openai import OpenAIProvider

        provider = OpenAIProvider(openai_config)

        assert "gpt" in provider.get_recommended_model("code task").lower()
        assert "mini" in provider.get_recommended_model("fast").lower()

    @pytest.mark.asyncio
    async def test_complete_mocked(self, openai_config):
        """Test completion with mocked client."""
        from fastband.providers.openai import OpenAIProvider

        provider = OpenAIProvider(openai_config)

        # Mock response
        mock_choice = MagicMock()
        mock_choice.message.content = "Test response"
        mock_choice.finish_reason = "stop"

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.model = "gpt-4-turbo"
        mock_response.usage = MagicMock(prompt_tokens=10, completion_tokens=20, total_tokens=30)
        mock_response.model_dump = MagicMock(return_value={})

        with patch.object(provider, '_client') as mock_client:
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            provider._client = mock_client

            response = await provider.complete("Test prompt")

            assert response.content == "Test response"
            assert response.provider == "openai"


# =============================================================================
# GEMINI PROVIDER TESTS
# =============================================================================

class TestGeminiProvider:
    """Tests for Gemini provider."""

    def test_init_with_config(self, gemini_config):
        """Test provider initialization with config."""
        from fastband.providers.gemini import GeminiProvider

        provider = GeminiProvider(gemini_config)

        assert provider.name == "gemini"
        assert provider.config.api_key == "test-key"
        assert provider.config.model == "gemini-1.5-pro"

    def test_capabilities(self, gemini_config):
        """Test Gemini capabilities."""
        from fastband.providers.gemini import GeminiProvider

        provider = GeminiProvider(gemini_config)

        assert Capability.TEXT_COMPLETION in provider.capabilities
        assert Capability.VISION in provider.capabilities
        assert Capability.LONG_CONTEXT in provider.capabilities

    def test_recommended_model(self, gemini_config):
        """Test model recommendation."""
        from fastband.providers.gemini import GeminiProvider

        provider = GeminiProvider(gemini_config)

        assert "flash" in provider.get_recommended_model("fast task")
        assert "pro" in provider.get_recommended_model("complex task")


# =============================================================================
# OLLAMA PROVIDER TESTS
# =============================================================================

class TestOllamaProvider:
    """Tests for Ollama provider."""

    def test_init_with_config(self, ollama_config):
        """Test provider initialization with config."""
        from fastband.providers.ollama import OllamaProvider

        provider = OllamaProvider(ollama_config)

        assert provider.name == "ollama"
        assert provider.config.model == "llama3.2"
        assert provider.config.base_url == "http://localhost:11434"

    def test_no_api_key_required(self, ollama_config):
        """Test that Ollama doesn't require API key."""
        from fastband.providers.ollama import OllamaProvider

        config = ProviderConfig(name="ollama", model="llama3.2")
        provider = OllamaProvider(config)

        # Should not raise an error
        assert provider.config.api_key is None

    def test_capabilities(self, ollama_config):
        """Test Ollama capabilities."""
        from fastband.providers.ollama import OllamaProvider

        provider = OllamaProvider(ollama_config)

        assert Capability.TEXT_COMPLETION in provider.capabilities
        assert Capability.CODE_GENERATION in provider.capabilities
        assert Capability.STREAMING in provider.capabilities

    def test_recommended_model(self, ollama_config):
        """Test model recommendation."""
        from fastband.providers.ollama import OllamaProvider

        provider = OllamaProvider(ollama_config)

        assert "codellama" in provider.get_recommended_model("code task")
        assert "llava" in provider.get_recommended_model("image analysis")


# =============================================================================
# PROVIDER REGISTRY TESTS
# =============================================================================

class TestProviderRegistry:
    """Tests for ProviderRegistry."""

    def test_available_providers(self):
        """Test listing available providers."""
        # The registry should have built-in providers registered
        loaders = getattr(ProviderRegistry, '_provider_loaders', {})

        assert "claude" in loaders
        assert "openai" in loaders
        assert "gemini" in loaders
        assert "ollama" in loaders

    def test_get_provider_with_env(self, mock_env):
        """Test getting provider with environment variables."""
        # Clear any cached instances
        ProviderRegistry._instances = {}

        provider = get_provider("claude")
        assert provider.name == "claude"

    def test_get_provider_invalid(self):
        """Test getting invalid provider."""
        ProviderRegistry._instances = {}

        with pytest.raises(ValueError) as exc_info:
            get_provider("invalid_provider")

        assert "Unknown provider" in str(exc_info.value)

    def test_config_from_env(self, mock_env):
        """Test config creation from environment."""
        config = ProviderRegistry._config_from_env("claude")

        assert config.api_key == "test-anthropic-key"
        assert config.model is not None


# =============================================================================
# INTEGRATION TESTS (with mocks)
# =============================================================================

class TestProviderIntegration:
    """Integration tests for providers."""

    @pytest.mark.asyncio
    async def test_provider_switching(self, mock_env):
        """Test switching between providers."""
        ProviderRegistry._instances = {}

        # Get Claude provider
        claude = get_provider("claude")
        assert claude.name == "claude"

        # Get OpenAI provider
        ProviderRegistry._instances = {}
        openai = get_provider("openai")
        assert openai.name == "openai"

        # Both should work independently
        assert claude.name != openai.name

    def test_all_providers_have_required_methods(self, mock_env):
        """Test that all providers implement required methods."""
        ProviderRegistry._instances = {}

        for provider_name in ["claude", "openai", "gemini", "ollama"]:
            try:
                provider = get_provider(provider_name)

                # Check required properties
                assert hasattr(provider, 'name')
                assert hasattr(provider, 'capabilities')

                # Check required methods
                assert hasattr(provider, 'complete')
                assert hasattr(provider, 'complete_with_tools')
                assert hasattr(provider, 'stream')
                assert hasattr(provider, 'get_recommended_model')

                ProviderRegistry._instances = {}
            except ValueError:
                # Skip if API key not configured
                ProviderRegistry._instances = {}
                continue

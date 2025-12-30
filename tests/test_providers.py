"""Tests for AI providers."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from fastband.providers.base import (
    Capability,
    CompletionResponse,
    ProviderConfig,
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

        with patch.object(provider, "_client") as mock_client:
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

        with patch.object(provider, "_client") as mock_client:
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

    @pytest.fixture(autouse=True)
    def setup_registry(self):
        """Ensure providers are registered before each test."""
        from fastband.providers.registry import _register_builtin_providers

        # Re-register built-in providers in case they were cleared by other tests
        _register_builtin_providers()
        # Clear cached instances and env cache
        ProviderRegistry._instances = {}
        ProviderRegistry._env_cache = {}
        yield
        # No teardown needed

    def test_available_providers(self):
        """Test listing available providers."""
        # The registry uses _lazy_specs for lazy-loaded providers
        available = ProviderRegistry.available_providers()

        assert "claude" in available
        assert "openai" in available
        assert "gemini" in available
        assert "ollama" in available

    def test_get_provider_with_env(self, mock_env):
        """Test getting provider with environment variables."""
        provider = get_provider("claude")
        assert provider.name == "claude"

    def test_get_provider_invalid(self):
        """Test getting invalid provider."""
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

    @pytest.fixture(autouse=True)
    def setup_registry(self):
        """Ensure providers are registered before each test."""
        from fastband.providers.registry import _register_builtin_providers

        # Re-register built-in providers in case they were cleared by other tests
        _register_builtin_providers()
        # Clear cached instances and env cache
        ProviderRegistry._instances = {}
        ProviderRegistry._env_cache = {}
        yield

    @pytest.mark.asyncio
    async def test_provider_switching(self, mock_env):
        """Test switching between providers."""
        # Get Claude provider
        claude = get_provider("claude")
        assert claude.name == "claude"

        # Get OpenAI provider (need to clear env cache to get fresh config)
        ProviderRegistry._instances = {}
        ProviderRegistry._env_cache = {}
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
                assert hasattr(provider, "name")
                assert hasattr(provider, "capabilities")

                # Check required methods
                assert hasattr(provider, "complete")
                assert hasattr(provider, "complete_with_tools")
                assert hasattr(provider, "stream")
                assert hasattr(provider, "get_recommended_model")

                ProviderRegistry._instances = {}
            except ValueError:
                # Skip if API key not configured
                ProviderRegistry._instances = {}
                continue


# =============================================================================
# CLAUDE PROVIDER EXTENDED TESTS
# =============================================================================


class TestClaudeProviderExtended:
    """Extended tests for Claude provider covering more code paths."""

    def test_validate_config_no_api_key(self, monkeypatch):
        """Test validation fails without API key."""
        from fastband.providers.claude import ClaudeProvider

        # Ensure no env var is set
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

        config = ProviderConfig(name="claude")

        # Validation happens in __init__, so we expect ValueError on instantiation
        with pytest.raises(ValueError) as exc_info:
            ClaudeProvider(config)

        assert "ANTHROPIC_API_KEY" in str(exc_info.value)

    def test_validate_config_from_env(self, monkeypatch):
        """Test API key can be loaded from environment."""
        from fastband.providers.claude import ClaudeProvider

        monkeypatch.setenv("ANTHROPIC_API_KEY", "env-key-123")

        config = ProviderConfig(name="claude")
        provider = ClaudeProvider(config)
        provider._validate_config()

        assert provider.config.api_key == "env-key-123"

    def test_default_model_set(self, claude_config):
        """Test default model is set when not provided."""
        from fastband.providers.claude import CLAUDE_MODELS, ClaudeProvider

        config = ProviderConfig(name="claude", api_key="test-key")
        provider = ClaudeProvider(config)
        provider._validate_config()

        assert provider.config.model == CLAUDE_MODELS["default"]

    def test_client_import_error(self, claude_config):
        """Test client raises ImportError when anthropic not installed."""
        from fastband.providers.claude import ClaudeProvider

        provider = ClaudeProvider(claude_config)

        with patch.dict("sys.modules", {"anthropic": None}):
            with patch("builtins.__import__", side_effect=ImportError("No module")):
                # Reset client
                provider._client = None
                try:
                    _ = provider.client
                    pytest.fail("Should have raised ImportError")
                except ImportError as e:
                    assert "anthropic" in str(e)

    @pytest.mark.asyncio
    async def test_complete_with_system_prompt(self, claude_config):
        """Test completion with system prompt."""
        from fastband.providers.claude import ClaudeProvider

        provider = ClaudeProvider(claude_config)

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="System response")]
        mock_response.model = "claude-sonnet-4-20250514"
        mock_response.usage = MagicMock(input_tokens=15, output_tokens=25)
        mock_response.stop_reason = "end_turn"
        mock_response.model_dump = MagicMock(return_value={})

        with patch.object(provider, "_client") as mock_client:
            mock_client.messages.create = AsyncMock(return_value=mock_response)
            provider._client = mock_client

            response = await provider.complete("Test prompt", system_prompt="You are helpful")

            assert response.content == "System response"
            # Verify system prompt was passed
            call_kwargs = mock_client.messages.create.call_args.kwargs
            assert call_kwargs["system"] == "You are helpful"

    @pytest.mark.asyncio
    async def test_complete_with_tools(self, claude_config):
        """Test completion with tools."""
        from fastband.providers.claude import ClaudeProvider

        provider = ClaudeProvider(claude_config)

        # Mock response with tool use
        text_block = MagicMock()
        text_block.type = "text"
        text_block.text = "Using tool"

        tool_block = MagicMock()
        tool_block.type = "tool_use"
        tool_block.id = "tool_123"
        tool_block.name = "search"
        tool_block.input = {"query": "test"}

        mock_response = MagicMock()
        mock_response.content = [text_block, tool_block]
        mock_response.model = "claude-sonnet-4-20250514"
        mock_response.usage = MagicMock(input_tokens=20, output_tokens=30)
        mock_response.stop_reason = "tool_use"
        mock_response.model_dump = MagicMock(return_value={})

        tools = [
            {
                "type": "function",
                "function": {
                    "name": "search",
                    "description": "Search for information",
                    "parameters": {"type": "object", "properties": {}},
                },
            }
        ]

        with patch.object(provider, "_client") as mock_client:
            mock_client.messages.create = AsyncMock(return_value=mock_response)
            provider._client = mock_client

            response = await provider.complete_with_tools("Find info", tools)

            assert response.content == "Using tool"
            assert response.raw_response["tool_calls"][0]["name"] == "search"
            assert response.raw_response["tool_calls"][0]["id"] == "tool_123"

    def test_convert_tools_openai_format(self, claude_config):
        """Test tool conversion from OpenAI to Claude format."""
        from fastband.providers.claude import ClaudeProvider

        provider = ClaudeProvider(claude_config)

        openai_tools = [
            {
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "description": "Get weather info",
                    "parameters": {
                        "type": "object",
                        "properties": {"location": {"type": "string"}},
                    },
                },
            }
        ]

        claude_tools = provider._convert_tools(openai_tools)

        assert len(claude_tools) == 1
        assert claude_tools[0]["name"] == "get_weather"
        assert claude_tools[0]["description"] == "Get weather info"
        assert "input_schema" in claude_tools[0]

    def test_convert_tools_already_claude_format(self, claude_config):
        """Test tools that are already in Claude format pass through."""
        from fastband.providers.claude import ClaudeProvider

        provider = ClaudeProvider(claude_config)

        claude_format_tools = [
            {"name": "search", "description": "Search", "input_schema": {"type": "object"}}
        ]

        result = provider._convert_tools(claude_format_tools)
        assert result == claude_format_tools

    @pytest.mark.asyncio
    async def test_stream(self, claude_config):
        """Test streaming response."""
        from fastband.providers.claude import ClaudeProvider

        provider = ClaudeProvider(claude_config)

        # Create async generator mock
        async def mock_text_stream():
            for chunk in ["Hello", " ", "World"]:
                yield chunk

        mock_stream_context = MagicMock()
        mock_stream_context.text_stream = mock_text_stream()
        mock_stream_context.__aenter__ = AsyncMock(return_value=mock_stream_context)
        mock_stream_context.__aexit__ = AsyncMock()

        with patch.object(provider, "_client") as mock_client:
            mock_client.messages.stream = MagicMock(return_value=mock_stream_context)
            provider._client = mock_client

            chunks = []
            async for chunk in provider.stream("Test"):
                chunks.append(chunk)

            assert chunks == ["Hello", " ", "World"]

    @pytest.mark.asyncio
    async def test_analyze_image(self, claude_config):
        """Test image analysis."""
        from fastband.providers.claude import ClaudeProvider

        provider = ClaudeProvider(claude_config)

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Image shows a cat")]
        mock_response.model = "claude-sonnet-4-20250514"
        mock_response.usage = MagicMock(input_tokens=100, output_tokens=20)
        mock_response.stop_reason = "end_turn"

        with patch.object(provider, "_client") as mock_client:
            mock_client.messages.create = AsyncMock(return_value=mock_response)
            provider._client = mock_client

            image_data = b"fake_image_data"
            response = await provider.analyze_image(
                image_data, "What is in this image?", image_type="image/jpeg"
            )

            assert response.content == "Image shows a cat"
            assert response.provider == "claude"

    def test_get_recommended_model_variations(self, claude_config):
        """Test model recommendations for different tasks."""
        from fastband.providers.claude import CLAUDE_MODELS, ClaudeProvider

        provider = ClaudeProvider(claude_config)

        # Code task
        assert provider.get_recommended_model("code review") == CLAUDE_MODELS["code"]
        assert provider.get_recommended_model("programming task") == CLAUDE_MODELS["code"]

        # Fast task
        assert provider.get_recommended_model("quick summary") == CLAUDE_MODELS["fast"]
        assert provider.get_recommended_model("fast response") == CLAUDE_MODELS["fast"]

        # Complex task
        assert provider.get_recommended_model("complex reasoning") == CLAUDE_MODELS["powerful"]

        # Vision task
        assert provider.get_recommended_model("image analysis") == CLAUDE_MODELS["vision"]

        # Default
        assert provider.get_recommended_model("random task") == claude_config.model


# =============================================================================
# OPENAI PROVIDER EXTENDED TESTS
# =============================================================================


class TestOpenAIProviderExtended:
    """Extended tests for OpenAI provider covering more code paths."""

    def test_validate_config_no_api_key(self, monkeypatch):
        """Test validation fails without API key."""
        from fastband.providers.openai import OpenAIProvider

        # Ensure no env var is set
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        config = ProviderConfig(name="openai")

        # Validation happens in __init__, so we expect ValueError on instantiation
        with pytest.raises(ValueError) as exc_info:
            OpenAIProvider(config)

        assert "OPENAI_API_KEY" in str(exc_info.value)

    def test_validate_config_from_env(self, monkeypatch):
        """Test API key can be loaded from environment."""
        from fastband.providers.openai import OpenAIProvider

        monkeypatch.setenv("OPENAI_API_KEY", "env-openai-key")

        config = ProviderConfig(name="openai")
        provider = OpenAIProvider(config)
        provider._validate_config()

        assert provider.config.api_key == "env-openai-key"

    def test_default_model_set(self):
        """Test default model is set when not provided."""
        from fastband.providers.openai import OPENAI_MODELS, OpenAIProvider

        config = ProviderConfig(name="openai", api_key="test-key")
        provider = OpenAIProvider(config)
        provider._validate_config()

        assert provider.config.model == OPENAI_MODELS["default"]

    @pytest.mark.asyncio
    async def test_complete_with_system_prompt(self, openai_config):
        """Test completion with system prompt."""
        from fastband.providers.openai import OpenAIProvider

        provider = OpenAIProvider(openai_config)

        mock_choice = MagicMock()
        mock_choice.message.content = "Response with system"
        mock_choice.finish_reason = "stop"

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.model = "gpt-4-turbo"
        mock_response.usage = MagicMock(prompt_tokens=20, completion_tokens=10, total_tokens=30)
        mock_response.model_dump = MagicMock(return_value={})

        with patch.object(provider, "_client") as mock_client:
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            provider._client = mock_client

            response = await provider.complete("Test", system_prompt="Be concise")

            assert response.content == "Response with system"
            # Verify messages include system prompt
            call_kwargs = mock_client.chat.completions.create.call_args.kwargs
            messages = call_kwargs["messages"]
            assert messages[0]["role"] == "system"
            assert messages[0]["content"] == "Be concise"

    @pytest.mark.asyncio
    async def test_complete_with_tools(self, openai_config):
        """Test completion with tools and tool calls."""
        from fastband.providers.openai import OpenAIProvider

        provider = OpenAIProvider(openai_config)

        # Mock tool call
        mock_tool_call = MagicMock()
        mock_tool_call.id = "call_123"
        mock_tool_call.function.name = "get_weather"
        mock_tool_call.function.arguments = '{"location": "NYC"}'

        mock_choice = MagicMock()
        mock_choice.message.content = ""
        mock_choice.message.tool_calls = [mock_tool_call]
        mock_choice.finish_reason = "tool_calls"

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.model = "gpt-4-turbo"
        mock_response.usage = MagicMock(prompt_tokens=30, completion_tokens=15, total_tokens=45)
        mock_response.model_dump = MagicMock(return_value={})

        tools = [{"type": "function", "function": {"name": "get_weather", "parameters": {}}}]

        with patch.object(provider, "_client") as mock_client:
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            provider._client = mock_client

            response = await provider.complete_with_tools("Weather in NYC?", tools)

            assert len(response.raw_response["tool_calls"]) == 1
            assert response.raw_response["tool_calls"][0]["name"] == "get_weather"
            assert response.raw_response["tool_calls"][0]["id"] == "call_123"

    @pytest.mark.asyncio
    async def test_complete_with_tools_no_tool_calls(self, openai_config):
        """Test completion with tools but no tool calls returned."""
        from fastband.providers.openai import OpenAIProvider

        provider = OpenAIProvider(openai_config)

        mock_choice = MagicMock()
        mock_choice.message.content = "No tools needed"
        mock_choice.message.tool_calls = None
        mock_choice.finish_reason = "stop"

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.model = "gpt-4-turbo"
        mock_response.usage = MagicMock(prompt_tokens=20, completion_tokens=10, total_tokens=30)
        mock_response.model_dump = MagicMock(return_value={})

        with patch.object(provider, "_client") as mock_client:
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            provider._client = mock_client

            response = await provider.complete_with_tools("Simple question", [])

            assert response.content == "No tools needed"
            assert response.raw_response["tool_calls"] == []

    @pytest.mark.asyncio
    async def test_stream(self, openai_config):
        """Test streaming response."""
        from fastband.providers.openai import OpenAIProvider

        provider = OpenAIProvider(openai_config)

        # Mock stream chunks
        async def mock_stream():
            chunks = [
                MagicMock(choices=[MagicMock(delta=MagicMock(content="Hello"))]),
                MagicMock(choices=[MagicMock(delta=MagicMock(content=" World"))]),
                MagicMock(choices=[MagicMock(delta=MagicMock(content=None))]),
            ]
            for chunk in chunks:
                yield chunk

        with patch.object(provider, "_client") as mock_client:
            mock_client.chat.completions.create = AsyncMock(return_value=mock_stream())
            provider._client = mock_client

            chunks = []
            async for chunk in provider.stream("Test"):
                chunks.append(chunk)

            assert chunks == ["Hello", " World"]

    @pytest.mark.asyncio
    async def test_analyze_image(self, openai_config):
        """Test image analysis."""
        from fastband.providers.openai import OpenAIProvider

        provider = OpenAIProvider(openai_config)

        mock_choice = MagicMock()
        mock_choice.message.content = "The image shows a sunset"
        mock_choice.finish_reason = "stop"

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.model = "gpt-4o"
        mock_response.usage = MagicMock(prompt_tokens=500, completion_tokens=20, total_tokens=520)

        with patch.object(provider, "_client") as mock_client:
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            provider._client = mock_client

            image_data = b"fake_image_bytes"
            response = await provider.analyze_image(
                image_data, "Describe this image", image_type="image/png"
            )

            assert response.content == "The image shows a sunset"
            assert response.provider == "openai"

    def test_get_recommended_model_variations(self, openai_config):
        """Test model recommendations for different tasks."""
        from fastband.providers.openai import OPENAI_MODELS, OpenAIProvider

        provider = OpenAIProvider(openai_config)

        assert provider.get_recommended_model("code task") == OPENAI_MODELS["code"]
        assert provider.get_recommended_model("fast query") == OPENAI_MODELS["fast"]
        assert provider.get_recommended_model("complex analysis") == OPENAI_MODELS["powerful"]
        assert provider.get_recommended_model("vision task") == OPENAI_MODELS["vision"]
        assert provider.get_recommended_model("general") == openai_config.model


# =============================================================================
# GEMINI PROVIDER EXTENDED TESTS
# =============================================================================


class TestGeminiProviderExtended:
    """Extended tests for Gemini provider covering more code paths."""

    def test_validate_config_no_api_key(self, monkeypatch):
        """Test validation fails without API key."""
        from fastband.providers.gemini import GeminiProvider

        # Ensure no env var is set
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

        config = ProviderConfig(name="gemini")

        # Validation happens in __init__, so we expect ValueError on instantiation
        with pytest.raises(ValueError) as exc_info:
            GeminiProvider(config)

        assert "GOOGLE_API_KEY" in str(exc_info.value)

    def test_validate_config_from_env(self, monkeypatch):
        """Test API key can be loaded from environment."""
        from fastband.providers.gemini import GeminiProvider

        monkeypatch.setenv("GOOGLE_API_KEY", "env-google-key")

        config = ProviderConfig(name="gemini")
        provider = GeminiProvider(config)
        provider._validate_config()

        assert provider.config.api_key == "env-google-key"

    def test_default_model_set(self):
        """Test default model is set when not provided."""
        from fastband.providers.gemini import GEMINI_MODELS, GeminiProvider

        config = ProviderConfig(name="gemini", api_key="test-key")
        provider = GeminiProvider(config)
        provider._validate_config()

        assert provider.config.model == GEMINI_MODELS["default"]

    @pytest.mark.asyncio
    async def test_complete_with_system_prompt(self, gemini_config):
        """Test completion with system prompt combined into prompt."""
        from fastband.providers.gemini import GeminiProvider

        provider = GeminiProvider(gemini_config)

        mock_response = MagicMock()
        mock_response.text = "Response text"
        mock_response.usage_metadata = MagicMock(
            prompt_token_count=10, candidates_token_count=20, total_token_count=30
        )

        mock_model = MagicMock()
        mock_model.generate_content_async = AsyncMock(return_value=mock_response)

        with patch.object(provider, "_get_model", return_value=mock_model):
            response = await provider.complete("Tell me a joke", system_prompt="Be funny")

            assert response.content == "Response text"
            # Verify combined prompt
            call_args = mock_model.generate_content_async.call_args[0]
            assert "Be funny" in call_args[0]
            assert "Tell me a joke" in call_args[0]

    @pytest.mark.asyncio
    async def test_complete_no_usage_metadata(self, gemini_config):
        """Test completion when usage metadata is not available."""
        from fastband.providers.gemini import GeminiProvider

        provider = GeminiProvider(gemini_config)

        mock_response = MagicMock()
        mock_response.text = "Simple response"
        mock_response.usage_metadata = None

        mock_model = MagicMock()
        mock_model.generate_content_async = AsyncMock(return_value=mock_response)

        with patch.object(provider, "_get_model", return_value=mock_model):
            response = await provider.complete("Test")

            assert response.content == "Simple response"
            assert response.usage["total_tokens"] == 0

    @pytest.mark.asyncio
    async def test_complete_with_tools(self, gemini_config):
        """Test completion with tools."""
        from fastband.providers.gemini import GeminiProvider

        provider = GeminiProvider(gemini_config)

        # Mock response parts - use spec to prevent auto-creation of attributes
        text_part = MagicMock(spec=["text"])
        text_part.text = "Using function"

        func_call = MagicMock()
        func_call.name = "get_data"
        func_call.args = {"param": "value"}

        func_part = MagicMock(spec=["function_call"])
        func_part.function_call = func_call

        mock_response = MagicMock()
        mock_response.parts = [text_part, func_part]

        mock_genai = MagicMock()
        mock_genai.GenerativeModel = MagicMock(
            return_value=MagicMock(generate_content_async=AsyncMock(return_value=mock_response))
        )
        mock_genai.protos.Tool = MagicMock(return_value=MagicMock())

        tools = [
            {
                "type": "function",
                "function": {"name": "get_data", "description": "Get data", "parameters": {}},
            }
        ]

        with patch.object(provider, "_get_genai", return_value=mock_genai):
            response = await provider.complete_with_tools("Query", tools)

            assert response.content == "Using function"
            assert len(response.raw_response["tool_calls"]) == 1
            assert response.raw_response["tool_calls"][0]["name"] == "get_data"

    def test_convert_tools(self, gemini_config):
        """Test tool conversion to Gemini format."""
        from fastband.providers.gemini import GeminiProvider

        provider = GeminiProvider(gemini_config)

        mock_genai = MagicMock()
        mock_genai.protos.Tool = MagicMock(return_value="converted_tool")

        tools = [
            {
                "type": "function",
                "function": {
                    "name": "search",
                    "description": "Search",
                    "parameters": {"type": "object"},
                },
            }
        ]

        with patch.object(provider, "_get_genai", return_value=mock_genai):
            result = provider._convert_tools(tools)

            assert len(result) == 1
            mock_genai.protos.Tool.assert_called_once()

    def test_convert_tools_empty(self, gemini_config):
        """Test conversion of empty tools list."""
        from fastband.providers.gemini import GeminiProvider

        provider = GeminiProvider(gemini_config)

        mock_genai = MagicMock()

        with patch.object(provider, "_get_genai", return_value=mock_genai):
            result = provider._convert_tools([])
            assert result == []

    @pytest.mark.asyncio
    async def test_stream(self, gemini_config):
        """Test streaming response."""
        from fastband.providers.gemini import GeminiProvider

        provider = GeminiProvider(gemini_config)

        async def mock_response_stream():
            for text in ["Hello", " ", "World"]:
                chunk = MagicMock()
                chunk.text = text
                yield chunk

        mock_model = MagicMock()
        mock_model.generate_content_async = AsyncMock(return_value=mock_response_stream())

        with patch.object(provider, "_get_model", return_value=mock_model):
            chunks = []
            async for chunk in provider.stream("Test"):
                chunks.append(chunk)

            assert chunks == ["Hello", " ", "World"]

    @pytest.mark.asyncio
    async def test_analyze_image(self, gemini_config):
        """Test image analysis."""
        from fastband.providers.gemini import GeminiProvider

        provider = GeminiProvider(gemini_config)

        mock_response = MagicMock()
        mock_response.text = "Image contains mountains"

        mock_model = MagicMock()
        mock_model.generate_content_async = AsyncMock(return_value=mock_response)

        with patch.object(provider, "_get_genai", return_value=MagicMock()):
            with patch.object(provider, "_get_model", return_value=mock_model):
                image_data = b"image_bytes"
                response = await provider.analyze_image(image_data, "What's in the image?")

                assert response.content == "Image contains mountains"
                assert response.provider == "gemini"

    def test_get_recommended_model_variations(self, gemini_config):
        """Test model recommendations for different tasks."""
        from fastband.providers.gemini import GEMINI_MODELS, GeminiProvider

        provider = GeminiProvider(gemini_config)

        assert provider.get_recommended_model("fast task") == GEMINI_MODELS["fast"]
        assert provider.get_recommended_model("quick response") == GEMINI_MODELS["fast"]
        assert provider.get_recommended_model("image analysis") == GEMINI_MODELS["vision"]
        assert provider.get_recommended_model("general task") == gemini_config.model


# =============================================================================
# OLLAMA PROVIDER EXTENDED TESTS
# =============================================================================


class TestOllamaProviderExtended:
    """Extended tests for Ollama provider covering more code paths."""

    def test_validate_config_sets_default_url(self):
        """Test default URL is set when not provided."""
        from fastband.providers.ollama import OllamaProvider

        config = ProviderConfig(name="ollama")
        provider = OllamaProvider(config)
        provider._validate_config()

        assert provider.config.base_url == "http://localhost:11434"

    def test_validate_config_from_env(self, monkeypatch):
        """Test base URL can be loaded from environment."""
        from fastband.providers.ollama import OllamaProvider

        monkeypatch.setenv("OLLAMA_HOST", "http://custom-host:11434")

        config = ProviderConfig(name="ollama")
        provider = OllamaProvider(config)
        provider._validate_config()

        assert provider.config.base_url == "http://custom-host:11434"

    def test_default_model_set(self):
        """Test default model is set when not provided."""
        from fastband.providers.ollama import OLLAMA_MODELS, OllamaProvider

        config = ProviderConfig(name="ollama")
        provider = OllamaProvider(config)
        provider._validate_config()

        assert provider.config.model == OLLAMA_MODELS["default"]

    @pytest.mark.asyncio
    async def test_complete(self, ollama_config):
        """Test completion."""
        from fastband.providers.ollama import OllamaProvider

        provider = OllamaProvider(ollama_config)

        mock_response = {
            "message": {"content": "Hello from Ollama"},
            "model": "llama3.2",
            "prompt_eval_count": 10,
            "eval_count": 20,
        }

        with patch.object(provider, "_client") as mock_client:
            mock_client.chat = AsyncMock(return_value=mock_response)
            provider._client = mock_client

            response = await provider.complete("Say hello")

            assert response.content == "Hello from Ollama"
            assert response.provider == "ollama"
            assert response.usage["prompt_tokens"] == 10
            assert response.usage["completion_tokens"] == 20

    @pytest.mark.asyncio
    async def test_complete_with_system_prompt(self, ollama_config):
        """Test completion with system prompt."""
        from fastband.providers.ollama import OllamaProvider

        provider = OllamaProvider(ollama_config)

        mock_response = {
            "message": {"content": "Concise response"},
            "model": "llama3.2",
            "prompt_eval_count": 15,
            "eval_count": 5,
        }

        with patch.object(provider, "_client") as mock_client:
            mock_client.chat = AsyncMock(return_value=mock_response)
            provider._client = mock_client

            response = await provider.complete("Long question", system_prompt="Be brief")

            assert response.content == "Concise response"
            # Verify system message was included
            call_kwargs = mock_client.chat.call_args.kwargs
            assert call_kwargs["messages"][0]["role"] == "system"

    @pytest.mark.asyncio
    async def test_complete_with_tools(self, ollama_config):
        """Test completion with tools."""
        from fastband.providers.ollama import OllamaProvider

        provider = OllamaProvider(ollama_config)

        mock_response = {
            "message": {
                "content": "",
                "tool_calls": [{"function": {"name": "calculator", "arguments": {"a": 5, "b": 3}}}],
            },
            "model": "llama3.2",
            "prompt_eval_count": 20,
            "eval_count": 10,
        }

        tools = [
            {
                "type": "function",
                "function": {"name": "calculator", "description": "Calculate", "parameters": {}},
            }
        ]

        with patch.object(provider, "_client") as mock_client:
            mock_client.chat = AsyncMock(return_value=mock_response)
            provider._client = mock_client

            response = await provider.complete_with_tools("Add 5 and 3", tools)

            assert len(response.raw_response["tool_calls"]) == 1
            assert response.raw_response["tool_calls"][0]["name"] == "calculator"

    @pytest.mark.asyncio
    async def test_complete_with_tools_fallback(self, ollama_config):
        """Test fallback to regular completion when tools fail."""
        from fastband.providers.ollama import OllamaProvider

        provider = OllamaProvider(ollama_config)

        # First call fails, second succeeds
        call_count = 0

        async def mock_chat(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Tools not supported")
            return {
                "message": {"content": "Fallback response"},
                "model": "llama3.2",
            }

        with patch.object(provider, "_client") as mock_client:
            mock_client.chat = mock_chat
            provider._client = mock_client

            response = await provider.complete_with_tools("Test", [])

            assert response.content == "Fallback response"

    def test_convert_tools(self, ollama_config):
        """Test tool conversion to Ollama format."""
        from fastband.providers.ollama import OllamaProvider

        provider = OllamaProvider(ollama_config)

        openai_tools = [
            {
                "type": "function",
                "function": {
                    "name": "search",
                    "description": "Search for info",
                    "parameters": {"type": "object"},
                },
            }
        ]

        ollama_tools = provider._convert_tools(openai_tools)

        assert len(ollama_tools) == 1
        assert ollama_tools[0]["type"] == "function"
        assert ollama_tools[0]["function"]["name"] == "search"

    @pytest.mark.asyncio
    async def test_stream(self, ollama_config):
        """Test streaming response."""
        from fastband.providers.ollama import OllamaProvider

        provider = OllamaProvider(ollama_config)

        async def mock_stream_iterator():
            """Async generator that yields chunks."""
            chunks = [
                {"message": {"content": "Hello"}},
                {"message": {"content": " World"}},
                {"message": {}},
            ]
            for chunk in chunks:
                yield chunk

        # The client.chat method returns an awaitable that resolves to an async iterator
        async def mock_chat(**kwargs):
            # Return the async generator directly - it will be iterated over
            return mock_stream_iterator()

        with patch.object(provider, "_client") as mock_client:
            mock_client.chat = mock_chat
            provider._client = mock_client

            chunks = []
            async for chunk in provider.stream("Test"):
                chunks.append(chunk)

            assert chunks == ["Hello", " World"]

    @pytest.mark.asyncio
    async def test_analyze_image(self, ollama_config):
        """Test image analysis."""
        from fastband.providers.ollama import OllamaProvider

        provider = OllamaProvider(ollama_config)

        mock_response = {
            "message": {"content": "A dog playing in the park"},
            "model": "llava",
            "prompt_eval_count": 100,
            "eval_count": 15,
        }

        with patch.object(provider, "_client") as mock_client:
            mock_client.chat = AsyncMock(return_value=mock_response)
            provider._client = mock_client

            image_data = b"fake_image"
            response = await provider.analyze_image(image_data, "Describe this image")

            assert response.content == "A dog playing in the park"
            # Verify image was passed
            call_kwargs = mock_client.chat.call_args.kwargs
            assert "images" in call_kwargs["messages"][0]

    @pytest.mark.asyncio
    async def test_list_models(self, ollama_config):
        """Test listing available models."""
        from fastband.providers.ollama import OllamaProvider

        provider = OllamaProvider(ollama_config)

        mock_response = {
            "models": [
                {"name": "llama3.2"},
                {"name": "codellama"},
                {"name": "llava"},
            ]
        }

        with patch.object(provider, "_client") as mock_client:
            mock_client.list = AsyncMock(return_value=mock_response)
            provider._client = mock_client

            models = await provider.list_models()

            assert models == ["llama3.2", "codellama", "llava"]

    @pytest.mark.asyncio
    async def test_pull_model_success(self, ollama_config):
        """Test successfully pulling a model."""
        from fastband.providers.ollama import OllamaProvider

        provider = OllamaProvider(ollama_config)

        with patch.object(provider, "_client") as mock_client:
            mock_client.pull = AsyncMock()
            provider._client = mock_client

            result = await provider.pull_model("llama3.2")

            assert result is True
            mock_client.pull.assert_called_once_with("llama3.2")

    @pytest.mark.asyncio
    async def test_pull_model_failure(self, ollama_config):
        """Test failure when pulling a model."""
        from fastband.providers.ollama import OllamaProvider

        provider = OllamaProvider(ollama_config)

        with patch.object(provider, "_client") as mock_client:
            mock_client.pull = AsyncMock(side_effect=Exception("Network error"))
            provider._client = mock_client

            result = await provider.pull_model("invalid-model")

            assert result is False

    def test_get_recommended_model_variations(self, ollama_config):
        """Test model recommendations for different tasks."""
        from fastband.providers.ollama import OLLAMA_MODELS, OllamaProvider

        provider = OllamaProvider(ollama_config)

        assert provider.get_recommended_model("code review") == OLLAMA_MODELS["code"]
        assert provider.get_recommended_model("programming") == OLLAMA_MODELS["code"]
        assert provider.get_recommended_model("image analysis") == OLLAMA_MODELS["vision"]
        assert provider.get_recommended_model("general") == ollama_config.model

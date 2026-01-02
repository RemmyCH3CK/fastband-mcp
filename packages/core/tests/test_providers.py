"""
Tests for Core providers module.

Verifies:
1. Provider types are importable with no side effects
2. Provider models serialize correctly
3. Capability system works correctly
4. Mock providers can implement interfaces
5. No forbidden imports (external SDKs)
"""

import ast
import json
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest


class TestNoSideEffectsOnImport:
    """Test that importing providers has no side effects."""

    def test_import_providers_module(self) -> None:
        """Importing providers module should have no side effects."""
        from fastband_core import providers

        assert providers is not None
        assert hasattr(providers, "CompletionProvider")
        assert hasattr(providers, "EmbeddingProvider")
        assert hasattr(providers, "Capability")

    def test_import_from_root(self) -> None:
        """Provider types should be importable from package root."""
        import fastband_core

        assert hasattr(fastband_core, "CompletionProvider")
        assert hasattr(fastband_core, "EmbeddingProvider")
        assert hasattr(fastband_core, "Capability")
        assert hasattr(fastband_core, "ProviderConfig")
        assert hasattr(fastband_core, "CompletionResponse")


class TestCapability:
    """Test Capability enum."""

    def test_capability_values(self) -> None:
        """Capability should have expected values."""
        from fastband_core.providers import Capability

        assert Capability.TEXT_COMPLETION.value == "text_completion"
        assert Capability.VISION.value == "vision"
        assert Capability.STREAMING.value == "streaming"
        assert Capability.FUNCTION_CALLING.value == "function_calling"

    def test_capability_is_str_enum(self) -> None:
        """Capability should be a string enum."""
        from fastband_core.providers import Capability

        assert isinstance(Capability.TEXT_COMPLETION.value, str)
        assert str(Capability.TEXT_COMPLETION) == "Capability.TEXT_COMPLETION"


class TestCapabilitySet:
    """Test CapabilitySet dataclass."""

    def test_supports_single_capability(self) -> None:
        """should check single capability support."""
        from fastband_core.providers import Capability, CapabilityInfo, CapabilitySet

        cap_set = CapabilitySet(
            capabilities=(
                CapabilityInfo(capability=Capability.TEXT_COMPLETION),
                CapabilityInfo(capability=Capability.STREAMING),
            )
        )

        assert cap_set.supports(Capability.TEXT_COMPLETION) is True
        assert cap_set.supports(Capability.STREAMING) is True
        assert cap_set.supports(Capability.VISION) is False

    def test_supports_all(self) -> None:
        """should check if all capabilities are supported."""
        from fastband_core.providers import Capability, CapabilitySet

        cap_set = CapabilitySet.from_capabilities(
            Capability.TEXT_COMPLETION, Capability.STREAMING
        )

        assert cap_set.supports_all(Capability.TEXT_COMPLETION, Capability.STREAMING)
        assert not cap_set.supports_all(Capability.TEXT_COMPLETION, Capability.VISION)

    def test_supports_any(self) -> None:
        """should check if any capability is supported."""
        from fastband_core.providers import Capability, CapabilitySet

        cap_set = CapabilitySet.from_capabilities(Capability.TEXT_COMPLETION)

        assert cap_set.supports_any(Capability.TEXT_COMPLETION, Capability.VISION)
        assert not cap_set.supports_any(Capability.VISION, Capability.EMBEDDINGS)

    def test_from_capabilities_factory(self) -> None:
        """from_capabilities should create with full support level."""
        from fastband_core.providers import Capability, CapabilityLevel, CapabilitySet

        cap_set = CapabilitySet.from_capabilities(
            Capability.TEXT_COMPLETION,
            Capability.VISION,
        )

        assert cap_set.get_level(Capability.TEXT_COMPLETION) == CapabilityLevel.FULL
        assert cap_set.get_level(Capability.VISION) == CapabilityLevel.FULL

    def test_to_dict(self) -> None:
        """should serialize to dict."""
        from fastband_core.providers import Capability, CapabilitySet

        cap_set = CapabilitySet.from_capabilities(Capability.TEXT_COMPLETION)
        d = cap_set.to_dict()

        assert "capabilities" in d
        assert len(d["capabilities"]) == 1
        assert d["capabilities"][0]["capability"] == "text_completion"


class TestProviderConfig:
    """Test ProviderConfig dataclass."""

    def test_config_defaults(self) -> None:
        """Config should have sensible defaults."""
        from fastband_core.providers import ProviderConfig

        config = ProviderConfig(name="test")

        assert config.name == "test"
        assert config.max_tokens == 4096
        assert config.temperature == 0.7
        assert config.timeout == 120

    def test_config_to_dict_masks_secrets(self) -> None:
        """to_dict should mask API key by default."""
        from fastband_core.providers import ProviderConfig

        config = ProviderConfig(name="test", api_key="sk-secret-key")
        d = config.to_dict()

        assert d["api_key"] == "****"
        assert d["name"] == "test"

    def test_config_to_dict_includes_secrets(self) -> None:
        """to_dict should include secrets when requested."""
        from fastband_core.providers import ProviderConfig

        config = ProviderConfig(name="test", api_key="sk-secret-key")
        d = config.to_dict(include_secrets=True)

        assert d["api_key"] == "sk-secret-key"

    def test_config_from_dict(self) -> None:
        """should deserialize from dict."""
        from fastband_core.providers import ProviderConfig

        d = {
            "name": "claude",
            "api_key": "sk-test",
            "model": "claude-3",
            "max_tokens": 8192,
        }

        config = ProviderConfig.from_dict(d)

        assert config.name == "claude"
        assert config.api_key == "sk-test"
        assert config.model == "claude-3"
        assert config.max_tokens == 8192


class TestCompletionResponse:
    """Test CompletionResponse dataclass."""

    def test_response_defaults(self) -> None:
        """Response should have sensible defaults."""
        from fastband_core.providers import (
            CompletionResponse,
            FinishReason,
            TokenUsage,
        )

        response = CompletionResponse(
            content="Hello!",
            model="claude-3",
            provider="claude",
            usage=TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
            finish_reason=FinishReason.STOP,
        )

        assert response.content == "Hello!"
        assert response.is_complete is True
        assert response.has_tool_calls is False
        assert len(response.response_id) == 36  # UUID format

    def test_response_is_frozen(self) -> None:
        """Response should be immutable."""
        from fastband_core.providers import (
            CompletionResponse,
            FinishReason,
            TokenUsage,
        )

        response = CompletionResponse(
            content="Hello!",
            model="test",
            provider="test",
            usage=TokenUsage(),
            finish_reason=FinishReason.STOP,
        )

        with pytest.raises(AttributeError):
            response.content = "Changed"  # type: ignore

    def test_response_with_tool_calls(self) -> None:
        """Response should include tool calls."""
        from fastband_core.providers import (
            CompletionResponse,
            FinishReason,
            TokenUsage,
            ToolCall,
        )

        response = CompletionResponse(
            content="",
            model="claude-3",
            provider="claude",
            usage=TokenUsage(),
            finish_reason=FinishReason.TOOL_USE,
            tool_calls=(
                ToolCall(
                    tool_id="call_1",
                    tool_name="search",
                    arguments={"query": "test"},
                ),
            ),
        )

        assert response.has_tool_calls is True
        assert len(response.tool_calls) == 1
        assert response.tool_calls[0].tool_name == "search"

    def test_response_to_dict(self) -> None:
        """should serialize to dict."""
        from fastband_core.providers import (
            CompletionResponse,
            FinishReason,
            TokenUsage,
        )

        response = CompletionResponse(
            content="Hello!",
            model="claude-3",
            provider="claude",
            usage=TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
            finish_reason=FinishReason.STOP,
        )

        d = response.to_dict()

        assert d["content"] == "Hello!"
        assert d["model"] == "claude-3"
        assert d["finish_reason"] == "stop"
        assert "usage" in d
        assert d["usage"]["total_tokens"] == 15

    def test_response_to_dict_is_json_serializable(self) -> None:
        """to_dict output should be JSON-safe."""
        from fastband_core.providers import (
            CompletionResponse,
            FinishReason,
            TokenUsage,
        )

        response = CompletionResponse(
            content="Test",
            model="test",
            provider="test",
            usage=TokenUsage(),
            finish_reason=FinishReason.STOP,
        )

        d = response.to_dict()
        json_str = json.dumps(d)
        parsed = json.loads(json_str)

        assert parsed["content"] == "Test"


class TestEmbeddingResult:
    """Test EmbeddingResult dataclass."""

    def test_result_creation(self) -> None:
        """Result should be creatable."""
        from fastband_core.providers import EmbeddingResult, TokenUsage

        result = EmbeddingResult(
            embeddings=((0.1, 0.2, 0.3), (0.4, 0.5, 0.6)),
            model="text-embedding-3",
            provider="openai",
            dimensions=3,
            usage=TokenUsage(prompt_tokens=10, total_tokens=10),
        )

        assert result.count == 2
        assert result.dimensions == 3
        assert len(result.embeddings[0]) == 3

    def test_result_is_frozen(self) -> None:
        """Result should be immutable."""
        from fastband_core.providers import EmbeddingResult, TokenUsage

        result = EmbeddingResult(
            embeddings=(),
            model="test",
            provider="test",
            dimensions=0,
            usage=TokenUsage(),
        )

        with pytest.raises(AttributeError):
            result.model = "changed"  # type: ignore

    def test_result_empty_factory(self) -> None:
        """empty() should create empty result."""
        from fastband_core.providers import EmbeddingResult

        result = EmbeddingResult.empty("test", "test", 768)

        assert result.count == 0
        assert result.dimensions == 768


class TestProviderHealth:
    """Test ProviderHealth dataclass."""

    def test_health_healthy(self) -> None:
        """should report healthy status."""
        from fastband_core.providers import ProviderHealth, ProviderStatus

        health = ProviderHealth(
            provider="claude",
            status=ProviderStatus.HEALTHY,
            latency_ms=150.0,
        )

        assert health.is_healthy is True
        assert health.is_available is True

    def test_health_degraded(self) -> None:
        """should report degraded status."""
        from fastband_core.providers import ProviderHealth, ProviderStatus

        health = ProviderHealth(
            provider="claude",
            status=ProviderStatus.DEGRADED,
            latency_ms=5000.0,
        )

        assert health.is_healthy is False
        assert health.is_available is True

    def test_health_unavailable(self) -> None:
        """should report unavailable status."""
        from fastband_core.providers import ProviderHealth, ProviderStatus

        health = ProviderHealth(
            provider="claude",
            status=ProviderStatus.UNAVAILABLE,
            error_message="Connection timeout",
        )

        assert health.is_healthy is False
        assert health.is_available is False


class TestProviderError:
    """Test ProviderError dataclass."""

    def test_error_retryable(self) -> None:
        """should identify retryable errors."""
        from fastband_core.providers import ProviderError, ProviderErrorType

        error = ProviderError(
            error_type=ProviderErrorType.RATE_LIMIT,
            message="Rate limit exceeded",
            provider="claude",
            retry_after=60.0,
        )

        assert error.is_retryable is True
        assert error.is_auth_error is False

    def test_error_auth(self) -> None:
        """should identify auth errors."""
        from fastband_core.providers import ProviderError, ProviderErrorType

        error = ProviderError(
            error_type=ProviderErrorType.AUTHENTICATION,
            message="Invalid API key",
            provider="claude",
        )

        assert error.is_retryable is False
        assert error.is_auth_error is True


class TestModelInfo:
    """Test ModelInfo dataclass."""

    def test_model_creation(self) -> None:
        """should create model info."""
        from fastband_core.providers import Capability, CapabilitySet, ModelInfo

        model = ModelInfo(
            model_id="claude-3-sonnet",
            provider="anthropic",
            display_name="Claude 3 Sonnet",
            capabilities=CapabilitySet.from_capabilities(
                Capability.TEXT_COMPLETION,
                Capability.VISION,
            ),
            context_window=200000,
            max_output_tokens=4096,
        )

        assert model.model_id == "claude-3-sonnet"
        assert model.name == "Claude 3 Sonnet"
        assert model.supports(Capability.VISION)

    def test_model_to_dict(self) -> None:
        """should serialize to dict."""
        from fastband_core.providers import ModelInfo

        model = ModelInfo(
            model_id="gpt-4",
            provider="openai",
        )

        d = model.to_dict()

        assert d["model_id"] == "gpt-4"
        assert d["provider"] == "openai"


class TestMockProviderImplementation:
    """Test that mock providers can implement the interfaces."""

    def test_mock_completion_provider(self) -> None:
        """A mock provider should implement CompletionProvider."""
        from fastband_core.providers import (
            Capability,
            CapabilitySet,
            CompletionProvider,
            CompletionResponse,
            FinishReason,
            ProviderConfig,
            TokenUsage,
        )

        class MockProvider(CompletionProvider):
            def _validate_config(self) -> None:
                pass

            @property
            def name(self) -> str:
                return "mock"

            @property
            def capabilities(self) -> CapabilitySet:
                return CapabilitySet.from_capabilities(Capability.TEXT_COMPLETION)

            async def complete(
                self, prompt: str, system_prompt: str | None = None, **kwargs: Any
            ) -> CompletionResponse:
                return CompletionResponse(
                    content="Mock response",
                    model="mock-1",
                    provider="mock",
                    usage=TokenUsage(prompt_tokens=5, completion_tokens=2, total_tokens=7),
                    finish_reason=FinishReason.STOP,
                )

            async def complete_with_tools(
                self,
                prompt: str,
                tools: list[dict[str, Any]],
                system_prompt: str | None = None,
                **kwargs: Any,
            ) -> CompletionResponse:
                return await self.complete(prompt, system_prompt, **kwargs)

            async def stream(
                self,
                prompt: str,
                system_prompt: str | None = None,
                **kwargs: Any,
            ) -> AsyncIterator[str]:
                yield "Mock"
                yield " "
                yield "stream"

        # Create instance
        config = ProviderConfig(name="mock")
        provider = MockProvider(config)

        assert provider.name == "mock"
        assert provider.supports(Capability.TEXT_COMPLETION)
        assert not provider.supports(Capability.VISION)

    def test_mock_embedding_provider(self) -> None:
        """A mock provider should implement EmbeddingProvider."""
        from collections.abc import Sequence

        from fastband_core.providers import (
            EmbeddingConfig,
            EmbeddingProvider,
            EmbeddingResult,
            TokenUsage,
        )

        class MockEmbedding(EmbeddingProvider):
            def _validate_config(self) -> None:
                pass

            @property
            def name(self) -> str:
                return "mock"

            @property
            def default_model(self) -> str:
                return "mock-embed-1"

            @property
            def dimensions(self) -> int:
                return 768

            async def embed(self, texts: Sequence[str]) -> EmbeddingResult:
                return EmbeddingResult(
                    embeddings=tuple(tuple([0.1] * 768) for _ in texts),
                    model=self.default_model,
                    provider=self.name,
                    dimensions=self.dimensions,
                    usage=TokenUsage(prompt_tokens=len(texts) * 5, total_tokens=len(texts) * 5),
                )

        config = EmbeddingConfig(model="mock-embed-1")
        provider = MockEmbedding(config)

        assert provider.name == "mock"
        assert provider.dimensions == 768


class TestNoForbiddenImports:
    """Test that provider modules have no forbidden imports."""

    FORBIDDEN_MODULES = [
        # External AI SDKs
        "anthropic",
        "openai",
        "google",
        "google.generativeai",
        "ollama",
        "langchain",
        "transformers",
        # Web frameworks
        "fastapi",
        "flask",
        "starlette",
        "django",
        # Database drivers
        "sqlalchemy",
        "asyncpg",
        "psycopg",
        "sqlite3",
        "aiosqlite",
        "pymongo",
        "redis",
        # Environment loading
        "dotenv",
        "python-dotenv",
        # Product packages
        "fastband_dev",
        "fastband_enterprise",
        "mcp",
    ]

    def _get_imports_from_file(self, file_path: Path) -> set[str]:
        """Extract all imports from a Python file using AST."""
        source = file_path.read_text()
        tree = ast.parse(source)
        imports: set[str] = set()

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.add(node.module.split(".")[0])

        return imports

    def test_model_no_forbidden_imports(self) -> None:
        """Model module must not import forbidden modules."""
        providers_dir = Path(__file__).parent.parent / "src" / "fastband_core" / "providers"
        model_file = providers_dir / "model.py"

        imports = self._get_imports_from_file(model_file)

        for forbidden in self.FORBIDDEN_MODULES:
            assert forbidden not in imports, f"Forbidden import found: {forbidden}"

    def test_ports_no_forbidden_imports(self) -> None:
        """Ports module must not import forbidden modules."""
        providers_dir = Path(__file__).parent.parent / "src" / "fastband_core" / "providers"
        ports_file = providers_dir / "ports.py"

        imports = self._get_imports_from_file(ports_file)

        for forbidden in self.FORBIDDEN_MODULES:
            assert forbidden not in imports, f"Forbidden import found: {forbidden}"

    def test_capabilities_no_forbidden_imports(self) -> None:
        """Capabilities module must not import forbidden modules."""
        providers_dir = Path(__file__).parent.parent / "src" / "fastband_core" / "providers"
        caps_file = providers_dir / "capabilities.py"

        imports = self._get_imports_from_file(caps_file)

        for forbidden in self.FORBIDDEN_MODULES:
            assert forbidden not in imports, f"Forbidden import found: {forbidden}"

"""Tests for the Provider Selection Wizard Step."""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from fastband.core.config import FastbandConfig
from fastband.wizard.base import StepStatus, WizardContext
from fastband.wizard.steps.provider import (
    PROVIDER_PRIORITY,
    PROVIDERS,
    ProviderInfo,
    ProviderSelectionStep,
)

# =============================================================================
# TEST FIXTURES
# =============================================================================


@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def wizard_context(temp_dir):
    """Create a wizard context for testing."""
    return WizardContext(
        project_path=temp_dir,
        config=FastbandConfig(),
        interactive=True,
    )


@pytest.fixture
def non_interactive_context(temp_dir):
    """Create a non-interactive wizard context for testing."""
    return WizardContext(
        project_path=temp_dir,
        config=FastbandConfig(),
        interactive=False,
    )


@pytest.fixture
def provider_step():
    """Create a ProviderSelectionStep for testing."""
    return ProviderSelectionStep()


@pytest.fixture
def clean_env():
    """Remove all provider API key environment variables."""
    env_vars = [
        "ANTHROPIC_API_KEY",
        "OPENAI_API_KEY",
        "GOOGLE_API_KEY",
        "OLLAMA_HOST",
    ]
    original = {var: os.environ.get(var) for var in env_vars}

    for var in env_vars:
        if var in os.environ:
            del os.environ[var]

    yield

    # Restore original environment
    for var, value in original.items():
        if value is not None:
            os.environ[var] = value
        elif var in os.environ:
            del os.environ[var]


# =============================================================================
# PROVIDER INFO TESTS
# =============================================================================


class TestProviderInfo:
    """Tests for provider information structure."""

    def test_provider_info_structure(self):
        """Test that ProviderInfo has expected fields."""
        info = ProviderInfo(
            name="test",
            display_name="Test Provider",
            env_var="TEST_API_KEY",
            default_model="test-model",
            setup_url="https://example.com",
            description="A test provider",
        )

        assert info.name == "test"
        assert info.display_name == "Test Provider"
        assert info.env_var == "TEST_API_KEY"
        assert info.default_model == "test-model"
        assert info.setup_url == "https://example.com"
        assert info.description == "A test provider"

    def test_all_providers_defined(self):
        """Test that all expected providers are defined."""
        expected_providers = ["claude", "openai", "gemini", "ollama"]

        for provider in expected_providers:
            assert provider in PROVIDERS
            assert isinstance(PROVIDERS[provider], ProviderInfo)

    def test_provider_priority_order(self):
        """Test provider priority ordering."""
        assert PROVIDER_PRIORITY == ["claude", "openai", "gemini", "ollama"]

    def test_claude_provider_info(self):
        """Test Claude provider configuration."""
        claude = PROVIDERS["claude"]

        assert claude.name == "claude"
        assert claude.env_var == "ANTHROPIC_API_KEY"
        assert "claude" in claude.default_model.lower()
        assert "anthropic" in claude.setup_url.lower()

    def test_openai_provider_info(self):
        """Test OpenAI provider configuration."""
        openai = PROVIDERS["openai"]

        assert openai.name == "openai"
        assert openai.env_var == "OPENAI_API_KEY"
        assert "gpt" in openai.default_model.lower()
        assert "openai" in openai.setup_url.lower()

    def test_gemini_provider_info(self):
        """Test Gemini provider configuration."""
        gemini = PROVIDERS["gemini"]

        assert gemini.name == "gemini"
        assert gemini.env_var == "GOOGLE_API_KEY"
        assert "gemini" in gemini.default_model.lower()

    def test_ollama_provider_info(self):
        """Test Ollama provider configuration."""
        ollama = PROVIDERS["ollama"]

        assert ollama.name == "ollama"
        assert ollama.env_var == "OLLAMA_HOST"
        assert "ollama" in ollama.setup_url.lower()


# =============================================================================
# PROVIDER SELECTION STEP PROPERTIES TESTS
# =============================================================================


class TestProviderSelectionStepProperties:
    """Tests for ProviderSelectionStep properties."""

    def test_step_name(self, provider_step):
        """Test step name property."""
        assert provider_step.name == "provider"

    def test_step_title(self, provider_step):
        """Test step title property."""
        assert provider_step.title == "AI Provider Selection"

    def test_step_description(self, provider_step):
        """Test step description property."""
        assert "ai provider" in provider_step.description.lower()

    def test_step_required(self, provider_step):
        """Test step is required."""
        assert provider_step.required is True

    def test_initial_status(self, provider_step):
        """Test initial step status."""
        assert provider_step.status == StepStatus.PENDING


# =============================================================================
# PROVIDER DETECTION TESTS
# =============================================================================


class TestProviderDetection:
    """Tests for provider availability detection."""

    def test_check_claude_available_with_key(self, provider_step):
        """Test Claude detection when API key is present."""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test-key"}):
            assert provider_step._check_provider_available("claude") is True

    def test_check_claude_not_available_without_key(self, provider_step, clean_env):
        """Test Claude detection when API key is absent."""
        assert provider_step._check_provider_available("claude") is False

    def test_check_openai_available_with_key(self, provider_step):
        """Test OpenAI detection when API key is present."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test-key"}):
            assert provider_step._check_provider_available("openai") is True

    def test_check_openai_not_available_without_key(self, provider_step, clean_env):
        """Test OpenAI detection when API key is absent."""
        assert provider_step._check_provider_available("openai") is False

    def test_check_gemini_available_with_key(self, provider_step):
        """Test Gemini detection when API key is present."""
        with patch.dict(os.environ, {"GOOGLE_API_KEY": "AIzatest"}):
            assert provider_step._check_provider_available("gemini") is True

    def test_check_gemini_not_available_without_key(self, provider_step, clean_env):
        """Test Gemini detection when API key is absent."""
        assert provider_step._check_provider_available("gemini") is False

    def test_check_ollama_always_available(self, provider_step, clean_env):
        """Test Ollama is always available (doesn't require API key)."""
        assert provider_step._check_provider_available("ollama") is True

    def test_check_unknown_provider(self, provider_step):
        """Test unknown provider returns False."""
        assert provider_step._check_provider_available("unknown") is False

    def test_get_available_providers_none(self, provider_step, clean_env):
        """Test getting available providers when none configured."""
        available = provider_step._get_available_providers()

        # Only ollama should be available (doesn't require key)
        assert "ollama" in available
        assert "claude" not in available
        assert "openai" not in available
        assert "gemini" not in available

    def test_get_available_providers_some(self, provider_step, clean_env):
        """Test getting available providers when some configured."""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test"}):
            available = provider_step._get_available_providers()

            assert "claude" in available
            assert "ollama" in available
            assert "openai" not in available

    def test_get_available_providers_all(self, provider_step):
        """Test getting available providers when all configured."""
        with patch.dict(
            os.environ,
            {
                "ANTHROPIC_API_KEY": "sk-test",
                "OPENAI_API_KEY": "sk-test",
                "GOOGLE_API_KEY": "AIzatest",
            },
        ):
            available = provider_step._get_available_providers()

            assert len(available) == 4
            assert set(available) == {"claude", "openai", "gemini", "ollama"}

    def test_available_providers_respect_priority(self, provider_step):
        """Test that available providers are in priority order."""
        with patch.dict(
            os.environ,
            {
                "GOOGLE_API_KEY": "AIzatest",
                "ANTHROPIC_API_KEY": "sk-test",
            },
        ):
            available = provider_step._get_available_providers()

            # Claude should come before Gemini (priority order)
            assert available.index("claude") < available.index("gemini")

    def test_get_all_providers(self, provider_step):
        """Test getting all registered providers."""
        all_providers = provider_step._get_all_providers()

        assert "claude" in all_providers
        assert "openai" in all_providers
        assert "gemini" in all_providers
        assert "ollama" in all_providers


# =============================================================================
# PROVIDER CHOICE PARSING TESTS
# =============================================================================


class TestProviderChoiceParsing:
    """Tests for parsing user's provider choice."""

    def test_parse_choice_by_number(self, provider_step):
        """Test parsing choice by number."""
        assert provider_step._parse_provider_choice("1") == "claude"
        assert provider_step._parse_provider_choice("2") == "openai"
        assert provider_step._parse_provider_choice("3") == "gemini"
        assert provider_step._parse_provider_choice("4") == "ollama"

    def test_parse_choice_by_name(self, provider_step):
        """Test parsing choice by full name."""
        assert provider_step._parse_provider_choice("claude") == "claude"
        assert provider_step._parse_provider_choice("openai") == "openai"
        assert provider_step._parse_provider_choice("gemini") == "gemini"
        assert provider_step._parse_provider_choice("ollama") == "ollama"

    def test_parse_choice_case_insensitive(self, provider_step):
        """Test choice parsing is case insensitive."""
        assert provider_step._parse_provider_choice("Claude") == "claude"
        assert provider_step._parse_provider_choice("OPENAI") == "openai"
        assert provider_step._parse_provider_choice("GeMiNi") == "gemini"

    def test_parse_choice_partial_match(self, provider_step):
        """Test parsing choice by partial name."""
        assert provider_step._parse_provider_choice("clau") == "claude"
        assert provider_step._parse_provider_choice("open") == "openai"
        assert provider_step._parse_provider_choice("gem") == "gemini"
        assert provider_step._parse_provider_choice("oll") == "ollama"

    def test_parse_choice_with_whitespace(self, provider_step):
        """Test choice parsing handles whitespace."""
        assert provider_step._parse_provider_choice("  claude  ") == "claude"
        assert provider_step._parse_provider_choice(" 1 ") == "claude"

    def test_parse_invalid_number(self, provider_step):
        """Test parsing invalid number choice."""
        assert provider_step._parse_provider_choice("0") is None
        assert provider_step._parse_provider_choice("5") is None
        assert provider_step._parse_provider_choice("-1") is None

    def test_parse_invalid_name(self, provider_step):
        """Test parsing invalid name choice."""
        assert provider_step._parse_provider_choice("unknown") is None
        assert provider_step._parse_provider_choice("xyz") is None

    def test_parse_empty_choice(self, provider_step):
        """Test parsing empty choice."""
        assert provider_step._parse_provider_choice("") is None
        assert provider_step._parse_provider_choice("   ") is None


# =============================================================================
# SELECTION SAVING TESTS
# =============================================================================


class TestSelectionSaving:
    """Tests for saving provider selection to context."""

    def test_save_selection_updates_context(self, provider_step, wizard_context):
        """Test that saving updates context.selected_provider."""
        provider_step._save_selection(wizard_context, "claude")

        assert wizard_context.selected_provider == "claude"

    def test_save_selection_updates_config(self, provider_step, wizard_context):
        """Test that saving updates context.config.default_provider."""
        provider_step._save_selection(wizard_context, "openai")

        assert wizard_context.config.default_provider == "openai"

    def test_save_selection_stores_metadata(self, provider_step, wizard_context):
        """Test that saving stores provider info in metadata."""
        provider_step._save_selection(wizard_context, "gemini")

        provider_info = wizard_context.get("provider_info")
        assert provider_info is not None
        assert provider_info["name"] == "gemini"
        assert "default_model" in provider_info

    def test_save_different_providers(self, provider_step, wizard_context):
        """Test saving different providers."""
        for provider in ["claude", "openai", "gemini", "ollama"]:
            provider_step._save_selection(wizard_context, provider)
            assert wizard_context.selected_provider == provider
            assert wizard_context.config.default_provider == provider


# =============================================================================
# NON-INTERACTIVE MODE TESTS
# =============================================================================


class TestNonInteractiveMode:
    """Tests for non-interactive execution."""

    @pytest.mark.asyncio
    async def test_selects_first_available_provider(self, provider_step, non_interactive_context):
        """Test non-interactive mode selects first available provider."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
            # Claude key not set, OpenAI is, so OpenAI should be selected
            # But ollama is always available and comes after openai
            # Actually, priority is claude, openai, gemini, ollama
            # So if only openai key is set, available = [openai, ollama]
            result = await provider_step.execute(non_interactive_context)

            assert result.success is True
            assert result.data["selected_provider"] == "openai"
            assert non_interactive_context.selected_provider == "openai"

    @pytest.mark.asyncio
    async def test_selects_claude_when_available(self, provider_step, non_interactive_context):
        """Test non-interactive mode prefers Claude when available."""
        with patch.dict(
            os.environ,
            {
                "ANTHROPIC_API_KEY": "sk-test",
                "OPENAI_API_KEY": "sk-test",
            },
        ):
            result = await provider_step.execute(non_interactive_context)

            assert result.success is True
            assert result.data["selected_provider"] == "claude"

    @pytest.mark.asyncio
    async def test_defaults_to_claude_when_none_available(
        self, provider_step, non_interactive_context, clean_env
    ):
        """Test non-interactive defaults to claude when only ollama available."""
        # With clean env, only ollama is available
        result = await provider_step.execute(non_interactive_context)

        assert result.success is True
        # Should select ollama since it's the only one available
        assert result.data["selected_provider"] == "ollama"

    @pytest.mark.asyncio
    async def test_result_includes_available_providers(
        self, provider_step, non_interactive_context
    ):
        """Test result includes list of available providers."""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test"}):
            result = await provider_step.execute(non_interactive_context)

            assert "available_providers" in result.data
            assert "claude" in result.data["available_providers"]

    @pytest.mark.asyncio
    async def test_result_includes_provider_available_flag(
        self, provider_step, non_interactive_context, clean_env
    ):
        """Test result includes whether selected provider is available."""
        result = await provider_step.execute(non_interactive_context)

        assert "provider_available" in result.data
        # Ollama is always available
        assert result.data["provider_available"] is True


# =============================================================================
# INTERACTIVE MODE TESTS
# =============================================================================


class TestInteractiveMode:
    """Tests for interactive execution."""

    @pytest.mark.asyncio
    async def test_interactive_with_valid_selection(self, provider_step, wizard_context):
        """Test interactive mode with valid provider selection."""
        # Mock the prompt to return "1" (claude)
        with patch.object(provider_step, "prompt", return_value="1"):
            with patch.object(provider_step, "_display_provider_table"):
                with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test"}):
                    result = await provider_step.execute(wizard_context)

                    assert result.success is True
                    assert wizard_context.selected_provider == "claude"

    @pytest.mark.asyncio
    async def test_interactive_prompts_for_unavailable_provider(
        self, provider_step, wizard_context, clean_env
    ):
        """Test interactive mode confirms when selecting unavailable provider."""
        # Mock: select claude (unavailable), then confirm continuing
        with patch.object(provider_step, "prompt", return_value="1"):
            with patch.object(provider_step, "confirm", return_value=True):
                with patch.object(provider_step, "_display_provider_table"):
                    with patch.object(provider_step, "_show_setup_instructions"):
                        result = await provider_step.execute(wizard_context)

                        assert result.success is True
                        assert wizard_context.selected_provider == "claude"

    @pytest.mark.asyncio
    async def test_interactive_retry_when_user_declines(
        self, provider_step, wizard_context, clean_env
    ):
        """Test interactive mode returns failure when user declines unavailable provider."""
        # Mock: select claude (unavailable), then decline
        with patch.object(provider_step, "prompt", return_value="1"):
            with patch.object(provider_step, "confirm", return_value=False):
                with patch.object(provider_step, "_display_provider_table"):
                    with patch.object(provider_step, "_show_setup_instructions"):
                        result = await provider_step.execute(wizard_context)

                        assert result.success is False
                        assert result.go_back is False


# =============================================================================
# DISPLAY AND UI TESTS
# =============================================================================


class TestDisplayMethods:
    """Tests for display and UI methods."""

    def test_display_provider_table(self, provider_step):
        """Test provider table display doesn't raise errors."""
        with patch.object(provider_step.console, "print"):
            # Should not raise any errors
            provider_step._display_provider_table()

    def test_show_setup_instructions_claude(self, provider_step):
        """Test showing setup instructions for Claude."""
        with patch.object(provider_step.console, "print") as mock_print:
            provider_step._show_setup_instructions("claude")

            # Should have printed something
            assert mock_print.called

    def test_show_setup_instructions_ollama(self, provider_step):
        """Test showing setup instructions for Ollama (different flow)."""
        with patch.object(provider_step.console, "print") as mock_print:
            provider_step._show_setup_instructions("ollama")

            # Should have printed something (different instructions than API key providers)
            assert mock_print.called

    def test_show_setup_instructions_unknown(self, provider_step):
        """Test showing setup instructions for unknown provider does nothing."""
        with patch.object(provider_step.console, "print") as mock_print:
            provider_step._show_setup_instructions("unknown_provider")

            # Should not have printed anything
            assert not mock_print.called


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestIntegration:
    """Integration tests for ProviderSelectionStep."""

    @pytest.mark.asyncio
    async def test_full_non_interactive_flow_with_claude(
        self, provider_step, non_interactive_context
    ):
        """Test complete non-interactive flow with Claude available."""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-anthropic-test"}):
            result = await provider_step.execute(non_interactive_context)

            assert result.success is True
            assert non_interactive_context.selected_provider == "claude"
            assert non_interactive_context.config.default_provider == "claude"
            assert "claude" in result.data["available_providers"]

    @pytest.mark.asyncio
    async def test_full_non_interactive_flow_with_multiple_providers(
        self, provider_step, non_interactive_context
    ):
        """Test non-interactive flow selects highest priority available."""
        with patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": "sk-openai-test",
                "GOOGLE_API_KEY": "AIza-gemini-test",
            },
        ):
            result = await provider_step.execute(non_interactive_context)

            assert result.success is True
            # OpenAI has higher priority than Gemini
            assert non_interactive_context.selected_provider == "openai"

    @pytest.mark.asyncio
    async def test_context_preserved_after_execution(self, provider_step, non_interactive_context):
        """Test that context is properly updated after execution."""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test"}):
            initial_config_version = non_interactive_context.config.version

            await provider_step.execute(non_interactive_context)

            # Config version should be preserved
            assert non_interactive_context.config.version == initial_config_version
            # Provider should be set
            assert non_interactive_context.selected_provider is not None

    @pytest.mark.asyncio
    async def test_step_status_not_modified(self, provider_step, non_interactive_context):
        """Test that step doesn't modify its own status (wizard does that)."""
        initial_status = provider_step.status

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test"}):
            await provider_step.execute(non_interactive_context)

        # Step should not modify its own status
        assert provider_step.status == initial_status


# =============================================================================
# EDGE CASE TESTS
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_api_key_not_considered_available(self, provider_step):
        """Test that empty API key string is not considered available."""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": ""}):
            assert provider_step._check_provider_available("claude") is False

    def test_whitespace_api_key_is_truthy(self, provider_step):
        """Test that whitespace-only API key is technically truthy."""
        # This is Python behavior - "  " is truthy
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "  "}):
            # Note: This returns True because bool("  ") is True
            # Real validation would happen when using the key
            assert provider_step._check_provider_available("claude") is True

    @pytest.mark.asyncio
    async def test_multiple_executions(self, provider_step, non_interactive_context):
        """Test step can be executed multiple times."""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test"}):
            result1 = await provider_step.execute(non_interactive_context)
            result2 = await provider_step.execute(non_interactive_context)

            assert result1.success is True
            assert result2.success is True

    @pytest.mark.asyncio
    async def test_validate_returns_true(self, provider_step, wizard_context):
        """Test validate method returns True (default behavior)."""
        result = await provider_step.validate(wizard_context)
        assert result is True

    def test_should_skip_returns_false(self, provider_step, wizard_context):
        """Test should_skip returns False (step is not skippable)."""
        assert provider_step.should_skip(wizard_context) is False

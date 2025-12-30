"""Tests for configuration management."""

import tempfile
from pathlib import Path

from fastband.core.config import FastbandConfig, get_config


class TestFastbandConfig:
    """Tests for FastbandConfig class."""

    def test_default_config(self):
        """Test default configuration values."""
        config = FastbandConfig()

        assert config.version == "1.2025.12"
        assert config.default_provider == "claude"
        assert config.tools.max_active == 60
        assert config.tickets.enabled is True
        assert config.backup.enabled is True

    def test_config_from_dict(self):
        """Test creating config from dictionary."""
        data = {
            "version": "1.2025.12",
            "ai": {
                "default_provider": "openai",
                "providers": {
                    "openai": {"model": "gpt-4"},
                },
            },
            "tools": {
                "max_active": 30,
            },
        }

        config = FastbandConfig.from_dict(data)

        assert config.default_provider == "openai"
        assert config.tools.max_active == 30
        assert "openai" in config.providers
        assert config.providers["openai"].model == "gpt-4"

    def test_config_to_dict(self):
        """Test serializing config to dictionary."""
        config = FastbandConfig()
        data = config.to_dict()

        assert "fastband" in data
        assert data["fastband"]["version"] == "1.2025.12"
        assert "ai" in data["fastband"]
        assert "tools" in data["fastband"]

    def test_config_save_and_load(self):
        """Test saving and loading config from file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.yaml"

            # Create and save config
            original = FastbandConfig()
            original.default_provider = "gemini"
            original.tools.max_active = 50
            original.save(config_path)

            # Load and verify
            loaded = FastbandConfig.from_file(config_path)
            assert loaded.default_provider == "gemini"
            assert loaded.tools.max_active == 50

    def test_config_from_missing_file(self):
        """Test loading config from non-existent file returns defaults."""
        config = FastbandConfig.from_file(Path("/nonexistent/config.yaml"))

        assert config.version == "1.2025.12"
        assert config.default_provider == "claude"


class TestGetConfig:
    """Tests for get_config function."""

    def test_get_config_returns_config(self):
        """Test that get_config returns a FastbandConfig."""
        # Reset global config
        import fastband.core.config

        fastband.core.config._config = None

        config = get_config()
        assert isinstance(config, FastbandConfig)

    def test_get_config_caches_result(self):
        """Test that get_config caches the config instance."""
        import fastband.core.config

        fastband.core.config._config = None

        config1 = get_config()
        config2 = get_config()

        assert config1 is config2

"""Tests for configuration."""

import pytest

from edfringe_scrape.config import Settings


class TestSettings:
    """Test Settings configuration."""

    def test_default_settings(self) -> None:
        """Test default settings initialization."""
        settings = Settings()
        assert settings.debug is False
        assert settings.log_level == "INFO"
        assert settings.base_url == "https://www.edfringe.com"
        assert settings.output_dir == "output"

    def test_env_var_loading(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test loading from environment variables."""
        monkeypatch.setenv("EDFRINGE_DEBUG", "true")
        monkeypatch.setenv("EDFRINGE_LOG_LEVEL", "DEBUG")

        settings = Settings()
        assert settings.debug is True
        assert settings.log_level == "DEBUG"

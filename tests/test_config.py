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
        assert settings.output_dir == "data/raw"
        assert settings.scrapingdog_api_key is None
        assert settings.request_delay_ms == 2000
        assert settings.js_wait_ms == 15000
        assert settings.default_year == 2026

    def test_env_var_loading(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test loading from environment variables."""
        monkeypatch.setenv("EDFRINGE_DEBUG", "true")
        monkeypatch.setenv("EDFRINGE_LOG_LEVEL", "DEBUG")

        settings = Settings()
        assert settings.debug is True
        assert settings.log_level == "DEBUG"

    def test_scrapingdog_settings(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test Scraping Dog API settings."""
        monkeypatch.setenv("EDFRINGE_SCRAPINGDOG_API_KEY", "test_api_key_123")
        monkeypatch.setenv("EDFRINGE_REQUEST_DELAY_MS", "3000")
        monkeypatch.setenv("EDFRINGE_JS_WAIT_MS", "10000")
        monkeypatch.setenv("EDFRINGE_DEFAULT_YEAR", "2026")

        settings = Settings()
        assert settings.scrapingdog_api_key == "test_api_key_123"
        assert settings.request_delay_ms == 3000
        assert settings.js_wait_ms == 10000
        assert settings.default_year == 2026

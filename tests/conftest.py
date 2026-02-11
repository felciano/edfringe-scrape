"""Shared test fixtures."""

import pytest

from edfringe_scrape.config import Settings


@pytest.fixture
def test_settings() -> Settings:
    """Create test settings with debug enabled."""
    return Settings(
        debug=True,
        log_level="DEBUG",
        scrapingdog_api_key="test_key_12345",
    )


@pytest.fixture(autouse=True)
def reset_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reset environment variables for each test."""
    monkeypatch.delenv("EDFRINGE_DEBUG", raising=False)
    monkeypatch.delenv("EDFRINGE_LOG_LEVEL", raising=False)
    monkeypatch.delenv("EDFRINGE_BASE_URL", raising=False)
    monkeypatch.delenv("EDFRINGE_OUTPUT_DIR", raising=False)
    monkeypatch.delenv("EDFRINGE_SCRAPINGDOG_API_KEY", raising=False)
    monkeypatch.delenv("EDFRINGE_REQUEST_DELAY_MS", raising=False)
    monkeypatch.delenv("EDFRINGE_JS_WAIT_MS", raising=False)
    monkeypatch.delenv("EDFRINGE_DEFAULT_YEAR", raising=False)

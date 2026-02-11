"""Shared test fixtures."""

import pytest

from edfringe_scrape.config import Settings


@pytest.fixture
def test_settings() -> Settings:
    """Create test settings with debug enabled."""
    return Settings(debug=True, log_level="DEBUG")


@pytest.fixture(autouse=True)
def reset_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reset environment variables for each test."""
    monkeypatch.delenv("EDFRINGE_DEBUG", raising=False)
    monkeypatch.delenv("EDFRINGE_LOG_LEVEL", raising=False)
    monkeypatch.delenv("EDFRINGE_BASE_URL", raising=False)
    monkeypatch.delenv("EDFRINGE_OUTPUT_DIR", raising=False)

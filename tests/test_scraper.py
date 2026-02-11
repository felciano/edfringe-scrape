"""Tests for Scraping Dog client and API discovery."""

import pytest

from edfringe_scrape.config import Settings
from edfringe_scrape.scraper import APIDiscovery, ScrapingDogClient, ScrapingDogError


class TestScrapingDogClient:
    """Test ScrapingDogClient."""

    def test_init_without_api_key(self) -> None:
        """Test initialization fails without API key."""
        settings = Settings(scrapingdog_api_key=None)
        with pytest.raises(ScrapingDogError, match="not configured"):
            ScrapingDogClient(settings)

    def test_init_with_api_key(self) -> None:
        """Test initialization succeeds with API key."""
        settings = Settings(scrapingdog_api_key="test_key_123")
        client = ScrapingDogClient(settings)
        assert client.settings.scrapingdog_api_key == "test_key_123"


class TestAPIDiscovery:
    """Test APIDiscovery utilities."""

    def test_extract_embedded_data_found(self) -> None:
        """Test extracting __NEXT_DATA__ from HTML."""
        html = """
        <html>
        <head>
            <script id="__NEXT_DATA__" type="application/json">
                {"buildId": "abc123", "props": {"pageProps": {}}}
            </script>
        </head>
        <body></body>
        </html>
        """
        data = APIDiscovery.extract_embedded_data(html)
        assert data is not None
        assert data["buildId"] == "abc123"
        assert "props" in data

    def test_extract_embedded_data_not_found(self) -> None:
        """Test when __NEXT_DATA__ is not present."""
        html = "<html><body>No Next.js data here</body></html>"
        data = APIDiscovery.extract_embedded_data(html)
        assert data is None

    def test_extract_embedded_data_invalid_json(self) -> None:
        """Test when __NEXT_DATA__ contains invalid JSON."""
        html = """
        <html>
        <head>
            <script id="__NEXT_DATA__" type="application/json">
                {invalid json here}
            </script>
        </head>
        </html>
        """
        data = APIDiscovery.extract_embedded_data(html)
        assert data is None

    def test_discover_build_id(self) -> None:
        """Test discovering build ID from HTML."""
        html = """
        <html>
        <head>
            <script id="__NEXT_DATA__" type="application/json">
                {"buildId": "xyz789", "props": {}}
            </script>
        </head>
        </html>
        """
        build_id = APIDiscovery.discover_build_id(html)
        assert build_id == "xyz789"

    def test_discover_build_id_not_found(self) -> None:
        """Test when build ID is not in data."""
        html = """
        <html>
        <head>
            <script id="__NEXT_DATA__" type="application/json">
                {"props": {}}
            </script>
        </head>
        </html>
        """
        build_id = APIDiscovery.discover_build_id(html)
        assert build_id is None


class TestScrapingDogError:
    """Test ScrapingDogError exception."""

    def test_error_with_message(self) -> None:
        """Test error with message only."""
        error = ScrapingDogError("Something went wrong")
        assert str(error) == "Something went wrong"
        assert error.status_code is None

    def test_error_with_status_code(self) -> None:
        """Test error with status code."""
        error = ScrapingDogError("Rate limited", status_code=429)
        assert str(error) == "Rate limited"
        assert error.status_code == 429

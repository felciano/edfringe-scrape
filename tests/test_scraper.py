"""Tests for Scraping Dog client and API discovery."""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from edfringe_scrape.config import Settings
from edfringe_scrape.scraper import (
    RETRYABLE_STATUS_CODES,
    APIDiscovery,
    ScrapingDogClient,
    ScrapingDogError,
    _is_retryable,
)


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


class TestIsRetryable:
    """Test _is_retryable helper."""

    @pytest.mark.parametrize("status_code", sorted(RETRYABLE_STATUS_CODES))
    def test_retryable_status_codes(self, status_code: int) -> None:
        """Test that retryable status codes return True."""
        exc = ScrapingDogError("error", status_code=status_code)
        assert _is_retryable(exc) is True

    @pytest.mark.parametrize("status_code", [400, 401, 403, 404, 422])
    def test_non_retryable_status_codes(self, status_code: int) -> None:
        """Test that non-retryable status codes return False."""
        exc = ScrapingDogError("error", status_code=status_code)
        assert _is_retryable(exc) is False

    def test_no_status_code(self) -> None:
        """Test that errors without status code are not retryable."""
        exc = ScrapingDogError("timeout error")
        assert _is_retryable(exc) is False

    def test_non_scraping_dog_error(self) -> None:
        """Test that other exceptions are not retryable."""
        assert _is_retryable(ValueError("bad")) is False


def _make_client(max_retries: int = 3) -> ScrapingDogClient:
    """Create a ScrapingDogClient with test settings."""
    settings = Settings(
        scrapingdog_api_key="test_key",
        request_delay_ms=0,
        max_retries=max_retries,
    )
    return ScrapingDogClient(settings)


def _mock_response(
    status_code: int = 200, text: str = "<html></html>"
) -> MagicMock:
    """Create a mock httpx.Response."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.text = text
    return resp


class TestFetchPageRetry:
    """Test retry behavior in fetch_page."""

    @patch("edfringe_scrape.scraper.httpx.Client")
    def test_success_no_retry(self, mock_client_cls: MagicMock) -> None:
        """Test successful request does not retry."""
        mock_client = MagicMock()
        mock_client.get.return_value = _mock_response()
        mock_client_cls.return_value.__enter__ = MagicMock(
            return_value=mock_client
        )
        mock_client_cls.return_value.__exit__ = MagicMock(
            return_value=False
        )

        client = _make_client()
        result = client.fetch_page("https://example.com")

        assert result.status_code == 200
        assert mock_client.get.call_count == 1

    @patch("edfringe_scrape.scraper.httpx.Client")
    def test_retryable_error_then_success(
        self, mock_client_cls: MagicMock
    ) -> None:
        """Test that retryable error is retried and succeeds."""
        mock_client = MagicMock()
        mock_client.get.side_effect = [
            _mock_response(status_code=502, text="Bad Gateway"),
            _mock_response(status_code=200, text="<html>ok</html>"),
        ]
        mock_client_cls.return_value.__enter__ = MagicMock(
            return_value=mock_client
        )
        mock_client_cls.return_value.__exit__ = MagicMock(
            return_value=False
        )

        client = _make_client()
        result = client.fetch_page("https://example.com")

        assert result.status_code == 200
        assert result.html == "<html>ok</html>"
        assert mock_client.get.call_count == 2

    @patch("edfringe_scrape.scraper.httpx.Client")
    def test_max_retries_exhausted(
        self, mock_client_cls: MagicMock
    ) -> None:
        """Test that error is raised after max retries exhausted."""
        mock_client = MagicMock()
        mock_client.get.return_value = _mock_response(
            status_code=500, text="Server Error"
        )
        mock_client_cls.return_value.__enter__ = MagicMock(
            return_value=mock_client
        )
        mock_client_cls.return_value.__exit__ = MagicMock(
            return_value=False
        )

        client = _make_client(max_retries=2)
        with pytest.raises(ScrapingDogError, match="status 500"):
            client.fetch_page("https://example.com")

        assert mock_client.get.call_count == 2

    @patch("edfringe_scrape.scraper.httpx.Client")
    def test_non_retryable_error_fails_immediately(
        self, mock_client_cls: MagicMock
    ) -> None:
        """Test that non-retryable errors fail without retry."""
        mock_client = MagicMock()
        mock_client.get.return_value = _mock_response(
            status_code=404, text="Not Found"
        )
        mock_client_cls.return_value.__enter__ = MagicMock(
            return_value=mock_client
        )
        mock_client_cls.return_value.__exit__ = MagicMock(
            return_value=False
        )

        client = _make_client()
        with pytest.raises(ScrapingDogError, match="status 404"):
            client.fetch_page("https://example.com")

        assert mock_client.get.call_count == 1

    @patch("edfringe_scrape.scraper.httpx.Client")
    def test_429_is_retried(self, mock_client_cls: MagicMock) -> None:
        """Test that 429 rate limit errors are retried."""
        mock_client = MagicMock()
        mock_client.get.side_effect = [
            _mock_response(status_code=429, text="Rate limited"),
            _mock_response(status_code=200, text="<html>ok</html>"),
        ]
        mock_client_cls.return_value.__enter__ = MagicMock(
            return_value=mock_client
        )
        mock_client_cls.return_value.__exit__ = MagicMock(
            return_value=False
        )

        client = _make_client()
        result = client.fetch_page("https://example.com")

        assert result.status_code == 200
        assert mock_client.get.call_count == 2

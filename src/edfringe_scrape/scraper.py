"""Scraping Dog API client and API discovery utilities."""

import json
import logging
import re
import time

import httpx

from .config import Settings
from .models import ScrapingDogResponse

logger = logging.getLogger(__name__)

SCRAPINGDOG_BASE_URL = "https://api.scrapingdog.com/scrape"


class ScrapingDogError(Exception):
    """Error from Scraping Dog API."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class ScrapingDogClient:
    """HTTP client for Scraping Dog API.

    Handles rate limiting, JavaScript rendering, and API responses.
    """

    def __init__(self, settings: Settings):
        """Initialize client with settings.

        Args:
            settings: Application settings with API key and rate limits
        """
        self.settings = settings
        self._last_request_time: float | None = None

        if not settings.scrapingdog_api_key:
            raise ScrapingDogError("SCRAPINGDOG_API_KEY not configured")

    def fetch_page(
        self,
        url: str,
        wait_ms: int | None = None,
        dynamic: bool = True,
    ) -> ScrapingDogResponse:
        """Fetch a page using Scraping Dog API.

        Args:
            url: URL to fetch
            wait_ms: JavaScript wait time (uses settings.js_wait_ms if None)
            dynamic: Whether to enable JavaScript rendering

        Returns:
            ScrapingDogResponse with HTML content

        Raises:
            ScrapingDogError: If API request fails
        """
        self._rate_limit()

        if wait_ms is None:
            wait_ms = self.settings.js_wait_ms

        params = {
            "api_key": self.settings.scrapingdog_api_key,
            "url": url,
            "dynamic": str(dynamic).lower(),
        }

        if dynamic and wait_ms > 0:
            params["wait"] = str(wait_ms)

        logger.debug(f"Fetching: {url} (dynamic={dynamic}, wait={wait_ms}ms)")

        try:
            with httpx.Client(timeout=60.0) as client:
                response = client.get(SCRAPINGDOG_BASE_URL, params=params)

            if response.status_code != 200:
                raise ScrapingDogError(
                    f"API returned status {response.status_code}: {response.text}",
                    status_code=response.status_code,
                )

            credits_used = 5 if dynamic else 1
            logger.debug(f"Fetched successfully, ~{credits_used} credits used")

            return ScrapingDogResponse(
                html=response.text,
                status_code=response.status_code,
                credits_used=credits_used,
            )

        except httpx.TimeoutException as e:
            raise ScrapingDogError(f"Request timed out: {e}") from e
        except httpx.RequestError as e:
            raise ScrapingDogError(f"Request failed: {e}") from e

    def _rate_limit(self) -> None:
        """Enforce rate limiting between requests."""
        if self._last_request_time is not None:
            elapsed = time.time() - self._last_request_time
            delay_sec = self.settings.request_delay_ms / 1000.0
            if elapsed < delay_sec:
                sleep_time = delay_sec - elapsed
                logger.debug(f"Rate limiting: sleeping {sleep_time:.2f}s")
                time.sleep(sleep_time)

        self._last_request_time = time.time()


class APIDiscovery:
    """Utilities for discovering Next.js internal APIs.

    Next.js sites often embed data in __NEXT_DATA__ script tags
    and have JSON API endpoints at /_next/data/{buildId}/...
    """

    @staticmethod
    def extract_embedded_data(html: str) -> dict | None:
        """Extract __NEXT_DATA__ from page HTML.

        Args:
            html: Page HTML content

        Returns:
            Parsed JSON data or None if not found
        """
        pattern = r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>'
        match = re.search(pattern, html, re.DOTALL)

        if not match:
            logger.debug("No __NEXT_DATA__ found in page")
            return None

        try:
            data = json.loads(match.group(1))
            logger.debug(f"Extracted __NEXT_DATA__ with keys: {list(data.keys())}")
            return data
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse __NEXT_DATA__: {e}")
            return None

    @staticmethod
    def discover_build_id(html: str) -> str | None:
        """Discover Next.js build ID from page HTML.

        The build ID is needed to construct /_next/data/... API URLs.

        Args:
            html: Page HTML content

        Returns:
            Build ID string or None if not found
        """
        data = APIDiscovery.extract_embedded_data(html)
        if data and "buildId" in data:
            build_id = data["buildId"]
            logger.debug(f"Discovered build ID: {build_id}")
            return build_id
        return None

    @staticmethod
    def try_api_endpoints(
        client: ScrapingDogClient,
        base_url: str,
        genre: str,
        build_id: str | None = None,
    ) -> dict | None:
        """Try to discover and fetch from internal API endpoints.

        Args:
            client: Scraping Dog client
            base_url: Site base URL
            genre: Genre to search for
            build_id: Next.js build ID if known

        Returns:
            API response data or None if no API found
        """
        if not build_id:
            logger.debug("No build ID, skipping API discovery")
            return None

        api_url = (
            f"{base_url}/_next/data/{build_id}/tickets/whats-on.json"
            f"?search=true&genres={genre}"
        )

        logger.info(f"Trying API endpoint: {api_url}")

        try:
            response = client.fetch_page(api_url, dynamic=False)
            try:
                data = json.loads(response.html)
                logger.info("API endpoint returned valid JSON")
                return data
            except json.JSONDecodeError:
                logger.debug("API endpoint did not return JSON")
                return None
        except ScrapingDogError as e:
            logger.debug(f"API endpoint failed: {e}")
            return None

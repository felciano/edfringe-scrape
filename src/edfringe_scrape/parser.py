"""HTML parsing utilities for Edinburgh Fringe pages."""

import datetime
import json
import logging
import re
from typing import Any, NamedTuple

from bs4 import BeautifulSoup, Tag

from .models import PerformanceDetail, ShowCard, ShowInfo, VenueInfo


class ShowDetailResult(NamedTuple):
    """Result from parsing a show detail page."""

    performances: list[PerformanceDetail]
    show_info: ShowInfo | None
    venue_info: VenueInfo | None = None

logger = logging.getLogger(__name__)


class NextDataParser:
    """Parser for Next.js __NEXT_DATA__ embedded JSON.

    Edinburgh Fringe uses Next.js and embeds all event/performance data
    in a JSON blob, which is more reliable than HTML parsing.
    """

    @staticmethod
    def extract_next_data(html: str) -> dict[str, Any] | None:
        """Extract __NEXT_DATA__ JSON from page HTML.

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
            return json.loads(match.group(1))
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse __NEXT_DATA__: {e}")
            return None

    @staticmethod
    def extract_event_data(html: str) -> dict[str, Any] | None:
        """Extract event data from show detail page.

        Args:
            html: Page HTML content

        Returns:
            Event data dict or None if not found
        """
        next_data = NextDataParser.extract_next_data(html)
        if not next_data:
            return None

        try:
            queries = (
                next_data.get("props", {})
                .get("pageProps", {})
                .get("initialState", {})
                .get("apiPublic", {})
                .get("queries", {})
            )

            for key, val in queries.items():
                if "Event" in key and isinstance(val, dict) and "data" in val:
                    return val["data"].get("event")

            return None
        except (KeyError, TypeError) as e:
            logger.debug(f"Failed to extract event data: {e}")
            return None

    # Status priority for deduplication (higher priority = more informative)
    STATUS_PRIORITY = {
        "CANCELLED": 100,
        "SOLD_OUT": 90,
        "NO_ALLOCATION": 85,
        "NO_ALLOCATION_REMAINING": 85,
        "PREVIEW_SHOW": 70,
        "PREVIEW": 70,
        "TWO_FOR_ONE": 60,
        "FREE_TICKETED": 50,
        "FREE": 50,
        "TICKETS_AVAILABLE": 10,
        "": 0,
    }

    @staticmethod
    def parse_performances(event_data: dict[str, Any]) -> list[PerformanceDetail]:
        """Parse performances from event data.

        Deduplicates performances by date/time/venue, keeping the most
        informative availability status when duplicates exist.

        Args:
            event_data: Event data dict from __NEXT_DATA__

        Returns:
            List of PerformanceDetail objects
        """
        # Use dict to deduplicate by (date, start_time, venue)
        perf_map: dict[tuple, PerformanceDetail] = {}

        venue_name = None
        venue_location = None

        # Get venue info
        venues = event_data.get("venues", [])
        if venues:
            venue = venues[0]
            venue_name = venue.get("title")
            address_parts = [
                venue.get("address1", ""),
                venue.get("address2", ""),
                venue.get("postCode", ""),
            ]
            venue_location = ", ".join(p for p in address_parts if p)

        # Get space info (more specific location within venue)
        spaces = event_data.get("spaces", [])
        if spaces:
            space_name = spaces[0].get("venueName") or spaces[0].get("title")
            if space_name:
                venue_name = space_name

        # Parse each performance
        for perf in event_data.get("performances", []):
            try:
                # Parse datetime
                dt_str = perf.get("dateTime")
                if not dt_str:
                    continue

                dt = datetime.datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
                perf_date = dt.date()
                start_time = dt.time()

                # Parse end time
                end_time = None
                end_dt_str = perf.get("estimatedEndDateTime")
                if end_dt_str:
                    end_dt = datetime.datetime.fromisoformat(
                        end_dt_str.replace("Z", "+00:00")
                    )
                    end_time = end_dt.time()

                # Get availability status
                availability = perf.get("ticketStatus", "")
                if perf.get("cancelled"):
                    availability = "CANCELLED"
                elif perf.get("soldOut"):
                    availability = "SOLD_OUT"

                # Create deduplication key
                key = (perf_date, start_time, venue_name)

                # Check if we already have this performance
                if key in perf_map:
                    # Keep the one with higher priority status
                    existing = perf_map[key]
                    existing_priority = NextDataParser.STATUS_PRIORITY.get(
                        existing.availability or "", 0
                    )
                    new_priority = NextDataParser.STATUS_PRIORITY.get(
                        availability or "", 0
                    )

                    if new_priority > existing_priority:
                        logger.debug(
                            f"Dedup: replacing {existing.availability} with "
                            f"{availability} for {perf_date} {start_time}"
                        )
                        perf_map[key] = PerformanceDetail(
                            date=perf_date,
                            start_time=start_time,
                            end_time=end_time,
                            availability=availability,
                            venue=venue_name,
                            location=venue_location,
                        )
                else:
                    perf_map[key] = PerformanceDetail(
                        date=perf_date,
                        start_time=start_time,
                        end_time=end_time,
                        availability=availability,
                        venue=venue_name,
                        location=venue_location,
                    )

            except (ValueError, TypeError) as e:
                logger.debug(f"Failed to parse performance: {e}")
                continue

        performances = list(perf_map.values())
        logger.debug(f"Parsed {len(performances)} performances from event data")
        return performances

    @staticmethod
    def parse_show_info(
        event_data: dict[str, Any],
        show_url: str = "",
        show_name: str = "",
    ) -> ShowInfo:
        """Parse show metadata from event data.

        Args:
            event_data: Event data dict from __NEXT_DATA__
            show_url: Show page URL
            show_name: Show name

        Returns:
            ShowInfo with extracted metadata
        """
        description = event_data.get("description", "")

        # Extract primary genre and sub-genres separately
        genre = event_data.get("genre", "")
        sub_genre_raw = event_data.get("subGenre", "")
        subgenres = ""
        if sub_genre_raw:
            subgenres = ", ".join(
                s.strip() for s in sub_genre_raw.split(",") if s.strip()
            )

        # Build attribute lookup from attributes array
        attrs: dict[str, str] = {}
        for attr in event_data.get("attributes", []):
            key = attr.get("key", "")
            value = attr.get("value", "")
            if key and value:
                attrs[key] = value

        warnings = attrs.get("explicit_material", "")
        age_suitability = attrs.get("age_range_guidance", "")

        # Social links from attributes
        social_keys = [
            "website",
            "facebook",
            "instagram",
            "tiktok",
            "youtube",
            "twitter",
            "bluesky",
            "mastodon",
        ]
        socials: dict[str, str] = {}
        for key in social_keys:
            socials[key] = attrs.get(key, "")

        # Fallback to socialLinks array
        for link in event_data.get("socialLinks", []):
            link_type = (link.get("type") or "").lower()
            link_url = link.get("url", "")
            if link_type in social_keys and not socials.get(link_type) and link_url:
                socials[link_type] = link_url

        # Extract image URL (prefer "Large", fall back to first available)
        image_url = ""
        images = event_data.get("images", [])
        for img in images:
            if img.get("imageType") == "Large":
                image_url = img.get("url", "")
                break
        if not image_url and images:
            image_url = images[0].get("url", "")

        return ShowInfo(
            show_url=show_url,
            show_name=show_name,
            genre=genre,
            subgenres=subgenres,
            description=description,
            warnings=warnings,
            age_suitability=age_suitability,
            image_url=image_url,
            **socials,
        )

    @staticmethod
    def parse_venue_info(
        event_data: dict[str, Any],
        base_url: str = "https://www.edfringe.com",
    ) -> VenueInfo | None:
        """Parse venue information from event data.

        Args:
            event_data: Event data dict from __NEXT_DATA__
            base_url: Site base URL for constructing venue page URL

        Returns:
            VenueInfo or None if no venue data found
        """
        venues = event_data.get("venues", [])
        if not venues:
            return None

        venue = venues[0]
        venue_code = venue.get("venueCode", "")
        venue_name = venue.get("title", "")
        slug = venue.get("slug", "")
        description = venue.get("description", "")
        postcode = venue.get("postCode", "")
        geolocation = venue.get("geoLocation", "")

        address_parts = [
            venue.get("address1", ""),
            venue.get("address2", ""),
        ]
        address = ", ".join(p for p in address_parts if p)

        google_maps_url = ""
        if geolocation:
            google_maps_url = (
                f"https://www.google.com/maps/dir/"
                f"?api=1&destination={geolocation}"
            )

        venue_page_url = ""
        if slug:
            venue_page_url = f"{base_url}/venues/{slug}"

        return VenueInfo(
            venue_code=venue_code,
            venue_name=venue_name,
            address=address,
            postcode=postcode,
            geolocation=geolocation,
            google_maps_url=google_maps_url,
            venue_page_url=venue_page_url,
            description=description,
        )

    @staticmethod
    def extract_venue_page_data(html: str) -> dict[str, Any] | None:
        """Extract venue data from venue detail page.

        Args:
            html: Venue page HTML content

        Returns:
            Venue data dict or None if not found
        """
        next_data = NextDataParser.extract_next_data(html)
        if not next_data:
            return None

        try:
            queries = (
                next_data.get("props", {})
                .get("pageProps", {})
                .get("initialState", {})
                .get("apiPublic", {})
                .get("queries", {})
            )

            for key, val in queries.items():
                if "Venue" in key and isinstance(val, dict) and "data" in val:
                    return val["data"].get("venue")

            return None
        except (KeyError, TypeError) as e:
            logger.debug(f"Failed to extract venue data: {e}")
            return None

    @staticmethod
    def parse_venue_contact(
        venue_page_data: dict[str, Any],
    ) -> tuple[str, str]:
        """Parse contact details from venue page data.

        Args:
            venue_page_data: Venue data dict from venue detail page

        Returns:
            Tuple of (contact_phone, contact_email)
        """
        contact_phone = venue_page_data.get("contactPhone", "") or ""
        contact_email = venue_page_data.get("contactEmail", "") or ""
        return contact_phone, contact_email


class FringeParser:
    """Parser for Edinburgh Fringe HTML pages.

    CSS selectors are based on the Web Scraper.io sitemap for edfringe.com.
    """

    def __init__(self, default_year: int = 2025):
        """Initialize parser.

        Args:
            default_year: Year to use when parsing dates without year
        """
        self.default_year = default_year

    def parse_search_results(self, html: str) -> list[ShowCard]:
        """Parse show cards from search results page.

        Args:
            html: HTML content of search results page

        Returns:
            List of ShowCard objects
        """
        soup = BeautifulSoup(html, "html.parser")
        cards: list[ShowCard] = []

        card_elements = soup.select('div[class*="event-listing_eventListingItem"]')
        logger.debug(f"Found {len(card_elements)} show cards")

        for element in card_elements:
            card = self._parse_show_card(element)
            if card:
                cards.append(card)

        return cards

    def _parse_show_card(self, element: Tag) -> ShowCard | None:
        """Parse a single show card element.

        Args:
            element: BeautifulSoup Tag for show card

        Returns:
            ShowCard or None if parsing fails
        """
        title_link = element.select_one('a[class*="event-card-search_eventTitle"]')
        if not title_link:
            logger.debug("No title link found in card")
            return None

        title = title_link.get_text(strip=True)
        url = title_link.get("href", "")

        if isinstance(url, list):
            url = url[0] if url else ""

        if url and not url.startswith("http"):
            # Card hrefs use /whats-on/... but canonical URLs are /tickets/whats-on/...
            if url.startswith("/whats-on/"):
                url = f"/tickets{url}"
            url = f"https://www.edfringe.com{url}"

        performer_el = element.select_one(
            'div[class*="event-card-search_eventPresenter"]'
        )
        performer = performer_el.get_text(strip=True) if performer_el else None

        duration_el = element.select_one(
            'span[class*="event-card-search_eventDuration"]'
        )
        duration = duration_el.get_text(strip=True) if duration_el else None

        date_block = element.select_one('div[class*="event-card-search_eventDate"]')
        date_html = str(date_block) if date_block else None

        return ShowCard(
            title=title,
            url=url,
            performer=performer,
            duration=duration,
            date_block_html=date_html,
        )

    def parse_show_detail(
        self,
        html: str,
        show_url: str = "",
        show_name: str = "",
    ) -> ShowDetailResult:
        """Parse performance details and show info from show detail page.

        First attempts to extract from __NEXT_DATA__ JSON (preferred),
        then falls back to HTML parsing if needed.

        Args:
            html: HTML content of show detail page
            show_url: Show page URL (for ShowInfo)
            show_name: Show name (for ShowInfo)

        Returns:
            ShowDetailResult with performances and show info
        """
        # Try JSON extraction first (more reliable)
        event_data = NextDataParser.extract_event_data(html)
        if event_data:
            performances = NextDataParser.parse_performances(event_data)
            show_info = NextDataParser.parse_show_info(
                event_data, show_url=show_url, show_name=show_name
            )
            venue_info = NextDataParser.parse_venue_info(event_data)
            if performances:
                logger.info(
                    f"Extracted {len(performances)} performances from __NEXT_DATA__"
                )
                return ShowDetailResult(
                    performances=performances,
                    show_info=show_info,
                    venue_info=venue_info,
                )

        # Fall back to HTML parsing
        logger.debug("Falling back to HTML parsing for performances")
        return ShowDetailResult(
            performances=self._parse_show_detail_html(html), show_info=None
        )

    def _parse_show_detail_html(self, html: str) -> list[PerformanceDetail]:
        """Parse performance details from HTML (fallback method).

        Args:
            html: HTML content of show detail page

        Returns:
            List of PerformanceDetail objects
        """
        soup = BeautifulSoup(html, "html.parser")
        performances: list[PerformanceDetail] = []

        date_buttons = soup.select('div[class*="date-picker_container"] button')
        logger.debug(f"Found {len(date_buttons)} date buttons")

        time_elements = soup.select('[class*="performance-item_headerTime"] span')
        availability_elements = soup.select('span[class*="label_label_"]')
        venue_elements = soup.select('div[class*="performance-location_venueTitle"]')

        if time_elements:
            raw_time = time_elements[0].get_text(strip=True)
            start_time, end_time = self.parse_time(raw_time)

            availability = None
            if availability_elements:
                availability = availability_elements[0].get_text(strip=True)

            venue = None
            if venue_elements:
                venue = venue_elements[0].get_text(strip=True)

            raw_date = None
            for btn in date_buttons:
                btn_text = btn.get_text(strip=True)
                if self._looks_like_date(btn_text):
                    raw_date = btn_text
                    break

            if raw_date:
                parsed_date = self.parse_date(raw_date)
                if parsed_date:
                    performances.append(
                        PerformanceDetail(
                            date=parsed_date,
                            start_time=start_time,
                            end_time=end_time,
                            availability=availability,
                            venue=venue,
                        )
                    )

        logger.debug(f"Parsed {len(performances)} performances from HTML")
        return performances

    def _looks_like_date(self, text: str) -> bool:
        """Check if text looks like a date string.

        Args:
            text: Text to check

        Returns:
            True if text matches date pattern
        """
        months = [
            "january",
            "february",
            "march",
            "april",
            "may",
            "june",
            "july",
            "august",
            "september",
            "october",
            "november",
            "december",
        ]
        text_lower = text.lower()
        return any(month in text_lower for month in months)

    def parse_date(self, date_str: str) -> datetime.date | None:
        """Parse date string like 'Wednesday 30 July' to date object.

        Args:
            date_str: Raw date string

        Returns:
            Parsed date or None if parsing fails
        """
        if not date_str:
            return None

        date_str = date_str.strip()

        match = re.search(r"(\d{1,2})\s+(\w+)", date_str)
        if not match:
            logger.debug(f"Could not parse date: {date_str}")
            return None

        day_str, month_str = match.groups()

        try:
            day = int(day_str)
            full_date_str = f"{day} {month_str} {self.default_year}"
            parsed = datetime.datetime.strptime(full_date_str, "%d %B %Y")
            return parsed.date()
        except ValueError as e:
            logger.debug(f"Date parse error for '{date_str}': {e}")
            return None

    def parse_time(
        self, time_str: str
    ) -> tuple[datetime.time | None, datetime.time | None]:
        """Parse time string like '19:30 - 20:30' to start/end times.

        Args:
            time_str: Raw time string

        Returns:
            Tuple of (start_time, end_time), either can be None
        """
        if not time_str:
            return None, None

        time_str = time_str.strip()

        parts = re.split(r"\s*[-–]\s*", time_str)

        start_time = self._parse_single_time(parts[0]) if parts else None
        end_time = self._parse_single_time(parts[1]) if len(parts) > 1 else None

        return start_time, end_time

    def _parse_single_time(self, time_str: str) -> datetime.time | None:
        """Parse a single time like '19:30'.

        Args:
            time_str: Time string

        Returns:
            Parsed time or None
        """
        if not time_str:
            return None

        time_str = time_str.strip()

        match = re.match(r"(\d{1,2}):(\d{2})", time_str)
        if match:
            hour, minute = int(match.group(1)), int(match.group(2))
            try:
                return datetime.time(hour, minute)
            except ValueError:
                return None

        return None

    def extract_show_name_from_detail(self, html: str) -> str | None:
        """Extract show name from detail page.

        Args:
            html: HTML content

        Returns:
            Show name or None
        """
        soup = BeautifulSoup(html, "html.parser")
        h1 = soup.select_one("h1")
        return h1.get_text(strip=True) if h1 else None

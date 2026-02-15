"""Tests for HTML parser."""

import json
from datetime import date, time

import pytest

from edfringe_scrape.parser import FringeParser, NextDataParser, ShowDetailResult


class TestFringeParser:
    """Test FringeParser functionality."""

    @pytest.fixture
    def parser(self) -> FringeParser:
        """Create parser with default year 2025."""
        return FringeParser(default_year=2025)

    def test_parse_date_full_format(self, parser: FringeParser) -> None:
        """Test parsing full date format."""
        result = parser.parse_date("Wednesday 30 July")
        assert result == date(2025, 7, 30)

    def test_parse_date_without_weekday(self, parser: FringeParser) -> None:
        """Test parsing date without weekday."""
        result = parser.parse_date("30 July")
        assert result == date(2025, 7, 30)

    def test_parse_date_august(self, parser: FringeParser) -> None:
        """Test parsing August date."""
        result = parser.parse_date("Saturday 2 August")
        assert result == date(2025, 8, 2)

    def test_parse_date_invalid(self, parser: FringeParser) -> None:
        """Test parsing invalid date returns None."""
        result = parser.parse_date("not a date")
        assert result is None

    def test_parse_date_empty(self, parser: FringeParser) -> None:
        """Test parsing empty string returns None."""
        result = parser.parse_date("")
        assert result is None

    def test_parse_time_range(self, parser: FringeParser) -> None:
        """Test parsing time range."""
        start, end = parser.parse_time("19:30 - 20:30")
        assert start == time(19, 30)
        assert end == time(20, 30)

    def test_parse_time_with_en_dash(self, parser: FringeParser) -> None:
        """Test parsing time with en-dash separator."""
        start, end = parser.parse_time("19:30 – 20:30")
        assert start == time(19, 30)
        assert end == time(20, 30)

    def test_parse_time_single(self, parser: FringeParser) -> None:
        """Test parsing single time."""
        start, end = parser.parse_time("19:30")
        assert start == time(19, 30)
        assert end is None

    def test_parse_time_empty(self, parser: FringeParser) -> None:
        """Test parsing empty string."""
        start, end = parser.parse_time("")
        assert start is None
        assert end is None

    def test_parse_search_results_basic(self, parser: FringeParser) -> None:
        """Test parsing basic search results HTML."""
        html = """
        <html>
        <body>
            <div class="event-listing_eventListingItem__abc123">
                <a class="event-card-search_eventTitle__xyz" href="/shows/test-show">
                    Test Comedy Show
                </a>
                <div class="event-card-search_eventPresenter__Al8QX">
                    Comedian Name
                </div>
                <span class="event-card-search_eventDuration__rB0hh">
                    1hr 15mins
                </span>
            </div>
        </body>
        </html>
        """
        cards = parser.parse_search_results(html)
        assert len(cards) == 1
        assert cards[0].title == "Test Comedy Show"
        assert cards[0].performer == "Comedian Name"
        assert cards[0].duration == "1hr 15mins"
        assert "test-show" in cards[0].url

    def test_parse_search_results_url_has_tickets_prefix(
        self, parser: FringeParser
    ) -> None:
        """Test that /whats-on/ hrefs get /tickets/ prefix."""
        html = """
        <html>
        <body>
            <div class="event-listing_eventListingItem__abc123">
                <a class="event-card-search_eventTitle__xyz" href="/whats-on/frank-sanazi-unleashed">
                    Frank Sanazi: Unleashed
                </a>
            </div>
        </body>
        </html>
        """
        cards = parser.parse_search_results(html)
        assert len(cards) == 1
        assert cards[0].url == (
            "https://www.edfringe.com/tickets/whats-on/frank-sanazi-unleashed"
        )

    def test_parse_search_results_multiple(self, parser: FringeParser) -> None:
        """Test parsing multiple show cards."""
        html = """
        <html>
        <body>
            <div class="event-listing_eventListingItem__1">
                <a class="event-card-search_eventTitle__a" href="/shows/show1">
                    Show One
                </a>
            </div>
            <div class="event-listing_eventListingItem__2">
                <a class="event-card-search_eventTitle__b" href="/shows/show2">
                    Show Two
                </a>
            </div>
        </body>
        </html>
        """
        cards = parser.parse_search_results(html)
        assert len(cards) == 2
        assert cards[0].title == "Show One"
        assert cards[1].title == "Show Two"

    def test_parse_search_results_empty(self, parser: FringeParser) -> None:
        """Test parsing HTML with no show cards."""
        html = "<html><body><div>No shows here</div></body></html>"
        cards = parser.parse_search_results(html)
        assert len(cards) == 0

    def test_looks_like_date(self, parser: FringeParser) -> None:
        """Test date string detection."""
        assert parser._looks_like_date("Wednesday 30 July")
        assert parser._looks_like_date("2 August")
        assert not parser._looks_like_date("Next day")
        assert not parser._looks_like_date("Previous")


class TestFringeParserYearConfig:
    """Test parser year configuration."""

    def test_different_year(self) -> None:
        """Test parsing with different year."""
        parser = FringeParser(default_year=2026)
        result = parser.parse_date("Wednesday 30 July")
        assert result == date(2026, 7, 30)


class TestNextDataParser:
    """Test NextDataParser for extracting data from __NEXT_DATA__."""

    def test_extract_next_data(self) -> None:
        """Test extracting __NEXT_DATA__ from HTML."""
        data = {"buildId": "abc123", "props": {"pageProps": {}}}
        html = f'''
        <html>
        <head>
            <script id="__NEXT_DATA__" type="application/json">
                {json.dumps(data)}
            </script>
        </head>
        </html>
        '''
        result = NextDataParser.extract_next_data(html)
        assert result is not None
        assert result["buildId"] == "abc123"

    def test_extract_next_data_not_found(self) -> None:
        """Test when __NEXT_DATA__ is not present."""
        html = "<html><body>No Next.js data</body></html>"
        result = NextDataParser.extract_next_data(html)
        assert result is None

    def test_extract_event_data(self) -> None:
        """Test extracting event data from show detail page."""
        event = {"title": "Comedy Show", "performances": []}
        data = {
            "props": {
                "pageProps": {
                    "initialState": {
                        "apiPublic": {
                            "queries": {
                                'Event({"eventId":"test"})': {
                                    "data": {"event": event}
                                }
                            }
                        }
                    }
                }
            }
        }
        html = f'''
        <script id="__NEXT_DATA__" type="application/json">
            {json.dumps(data)}
        </script>
        '''
        result = NextDataParser.extract_event_data(html)
        assert result is not None
        assert result["title"] == "Comedy Show"

    def test_parse_performances(self) -> None:
        """Test parsing performances from event data."""
        event_data = {
            "venues": [
                {
                    "title": "The Comedy Club",
                    "address1": "123 Main St",
                    "postCode": "EH1 1AA",
                }
            ],
            "spaces": [],
            "performances": [
                {
                    "dateTime": "2026-08-06T19:30:00.000Z",
                    "estimatedEndDateTime": "2026-08-06T20:30:00.000Z",
                    "ticketStatus": "TICKETS_AVAILABLE",
                    "cancelled": False,
                    "soldOut": False,
                },
                {
                    "dateTime": "2026-08-07T19:30:00.000Z",
                    "estimatedEndDateTime": "2026-08-07T20:30:00.000Z",
                    "ticketStatus": "TWO_FOR_ONE",
                    "cancelled": False,
                    "soldOut": False,
                },
            ],
        }
        result = NextDataParser.parse_performances(event_data)
        assert len(result) == 2
        assert result[0].date == date(2026, 8, 6)
        assert result[0].start_time == time(19, 30)
        assert result[0].availability == "TICKETS_AVAILABLE"
        assert result[0].venue == "The Comedy Club"
        assert result[1].availability == "TWO_FOR_ONE"

    def test_parse_performances_with_cancelled(self) -> None:
        """Test that cancelled overrides ticketStatus."""
        event_data = {
            "venues": [],
            "spaces": [],
            "performances": [
                {
                    "dateTime": "2026-08-06T19:30:00.000Z",
                    "ticketStatus": "TICKETS_AVAILABLE",
                    "cancelled": True,
                    "soldOut": False,
                }
            ],
        }
        result = NextDataParser.parse_performances(event_data)
        assert len(result) == 1
        assert result[0].availability == "CANCELLED"

    def test_parse_performances_with_sold_out(self) -> None:
        """Test that soldOut overrides ticketStatus."""
        event_data = {
            "venues": [],
            "spaces": [],
            "performances": [
                {
                    "dateTime": "2026-08-06T19:30:00.000Z",
                    "ticketStatus": "TICKETS_AVAILABLE",
                    "cancelled": False,
                    "soldOut": True,
                }
            ],
        }
        result = NextDataParser.parse_performances(event_data)
        assert len(result) == 1
        assert result[0].availability == "SOLD_OUT"

    def test_parse_performances_deduplicates(self) -> None:
        """Test that duplicate performances are deduplicated."""
        event_data = {
            "venues": [{"title": "Venue A"}],
            "performances": [
                {
                    "dateTime": "2025-08-01T19:30:00Z",
                    "estimatedEndDateTime": "2025-08-01T20:30:00Z",
                    "ticketStatus": "TICKETS_AVAILABLE",
                },
                {
                    "dateTime": "2025-08-01T19:30:00Z",
                    "estimatedEndDateTime": "2025-08-01T20:30:00Z",
                    "ticketStatus": "PREVIEW_SHOW",
                },
            ],
        }

        performances = NextDataParser.parse_performances(event_data)

        # Should only have 1 performance, with the more informative status
        assert len(performances) == 1
        assert performances[0].availability == "PREVIEW_SHOW"

    def test_parse_performances_keeps_higher_priority_status(self) -> None:
        """Test that higher priority status is kept when deduplicating."""
        event_data = {
            "venues": [{"title": "Venue A"}],
            "performances": [
                {
                    "dateTime": "2025-08-01T19:30:00Z",
                    "ticketStatus": "PREVIEW_SHOW",
                },
                {
                    "dateTime": "2025-08-01T19:30:00Z",
                    "ticketStatus": "SOLD_OUT",
                },
            ],
        }

        performances = NextDataParser.parse_performances(event_data)

        # SOLD_OUT has higher priority than PREVIEW_SHOW
        assert len(performances) == 1
        assert performances[0].availability == "SOLD_OUT"

    def test_parse_show_info_full_attributes(self) -> None:
        """Test parsing show info with full attributes."""
        event_data = {
            "genre": "COMEDY",
            "subGenre": "Stand-up,LGBTQ+",
            "description": "A hilarious stand-up show",
            "attributes": [
                {"key": "explicit_material", "value": "Strong language, adult themes"},
                {"key": "age_range_guidance", "value": "16+"},
                {"key": "instagram", "value": "https://instagram.com/comedian"},
                {"key": "website", "value": "https://comedian.com"},
                {"key": "twitter", "value": "https://twitter.com/comedian"},
            ],
            "images": [
                {"url": "https://img.com/small.jpg", "imageType": "Small"},
                {"url": "https://img.com/large.jpg", "imageType": "Large"},
            ],
        }

        info = NextDataParser.parse_show_info(
            event_data,
            show_url="https://www.edfringe.com/shows/123",
            show_name="Test Show",
        )
        assert info.show_url == "https://www.edfringe.com/shows/123"
        assert info.show_name == "Test Show"
        assert info.genre == "COMEDY"
        assert info.subgenres == "Stand-up, LGBTQ+"
        assert info.description == "A hilarious stand-up show"
        assert info.warnings == "Strong language, adult themes"
        assert info.age_suitability == "16+"
        assert info.instagram == "https://instagram.com/comedian"
        assert info.website == "https://comedian.com"
        assert info.twitter == "https://twitter.com/comedian"
        assert info.image_url == "https://img.com/large.jpg"

    def test_parse_show_info_empty_attributes(self) -> None:
        """Test parsing show info with no attributes."""
        event_data = {
            "description": "Simple show",
            "attributes": [],
            "images": [],
        }

        info = NextDataParser.parse_show_info(event_data)
        assert info.description == "Simple show"
        assert info.genre == ""
        assert info.subgenres == ""
        assert info.warnings == ""
        assert info.age_suitability == ""
        assert info.image_url == ""
        assert info.instagram == ""

    def test_parse_show_info_genre_only(self) -> None:
        """Test parsing show info with primary genre but no sub-genres."""
        event_data = {"genre": "THEATRE", "subGenre": ""}
        info = NextDataParser.parse_show_info(event_data)
        assert info.genre == "THEATRE"
        assert info.subgenres == ""

    def test_parse_show_info_genre_with_sub_genres(self) -> None:
        """Test parsing show info with primary and sub-genres."""
        event_data = {"genre": "COMEDY", "subGenre": "Stand-up,LGBTQ+"}
        info = NextDataParser.parse_show_info(event_data)
        assert info.genre == "COMEDY"
        assert info.subgenres == "Stand-up, LGBTQ+"

    def test_parse_show_info_social_links_fallback(self) -> None:
        """Test that socialLinks array is used as fallback."""
        event_data = {
            "description": "",
            "attributes": [
                {"key": "instagram", "value": "https://instagram.com/from_attrs"},
            ],
            "socialLinks": [
                {"type": "Instagram", "url": "https://instagram.com/from_links"},
                {"type": "Facebook", "url": "https://facebook.com/show"},
                {"type": "TikTok", "url": "https://tiktok.com/@show"},
            ],
        }

        info = NextDataParser.parse_show_info(event_data)
        # Instagram should come from attributes (not overridden)
        assert info.instagram == "https://instagram.com/from_attrs"
        # Facebook should come from socialLinks fallback
        assert info.facebook == "https://facebook.com/show"
        # TikTok should come from socialLinks fallback
        assert info.tiktok == "https://tiktok.com/@show"

    def test_parse_show_info_image_fallback_to_first(self) -> None:
        """Test image URL falls back to first image when no Large type."""
        event_data = {
            "description": "",
            "images": [
                {"url": "https://img.com/small.jpg", "imageType": "Small"},
                {"url": "https://img.com/medium.jpg", "imageType": "Medium"},
            ],
        }

        info = NextDataParser.parse_show_info(event_data)
        assert info.image_url == "https://img.com/small.jpg"

    def test_parse_show_info_missing_fields(self) -> None:
        """Test parsing show info when event data has no relevant keys."""
        event_data = {"performances": []}

        info = NextDataParser.parse_show_info(event_data)
        assert info.description == ""
        assert info.warnings == ""
        assert info.image_url == ""


class TestNextDataParserVenue:
    """Test NextDataParser venue parsing methods."""

    def test_parse_venue_info_full(self) -> None:
        """Test parsing venue info with all fields."""
        event_data = {
            "venues": [
                {
                    "title": "Pleasance Courtyard",
                    "venueCode": "V123",
                    "address1": "60 Pleasance",
                    "address2": "Edinburgh",
                    "postCode": "EH8 9TJ",
                    "geoLocation": "55.9469,-3.1813",
                    "slug": "pleasance-courtyard",
                    "description": "A popular Fringe venue",
                }
            ],
        }
        venue = NextDataParser.parse_venue_info(event_data)
        assert venue is not None
        assert venue.venue_code == "V123"
        assert venue.venue_name == "Pleasance Courtyard"
        assert venue.address == "60 Pleasance, Edinburgh"
        assert venue.postcode == "EH8 9TJ"
        assert venue.geolocation == "55.9469,-3.1813"
        assert "55.9469,-3.1813" in venue.google_maps_url
        assert venue.venue_page_url == "https://www.edfringe.com/venues/pleasance-courtyard"
        assert venue.description == "A popular Fringe venue"
        assert venue.contact_phone == ""
        assert venue.contact_email == ""

    def test_parse_venue_info_empty_venues(self) -> None:
        """Test that empty venues list returns None."""
        event_data = {"venues": []}
        assert NextDataParser.parse_venue_info(event_data) is None

    def test_parse_venue_info_no_venues_key(self) -> None:
        """Test that missing venues key returns None."""
        event_data = {"performances": []}
        assert NextDataParser.parse_venue_info(event_data) is None

    def test_parse_venue_info_minimal(self) -> None:
        """Test parsing venue with minimal data."""
        event_data = {
            "venues": [{"title": "Small Venue"}],
        }
        venue = NextDataParser.parse_venue_info(event_data)
        assert venue is not None
        assert venue.venue_name == "Small Venue"
        assert venue.venue_code == ""
        assert venue.google_maps_url == ""
        assert venue.venue_page_url == ""

    def test_parse_venue_info_custom_base_url(self) -> None:
        """Test venue page URL uses custom base URL."""
        event_data = {
            "venues": [{"slug": "my-venue"}],
        }
        venue = NextDataParser.parse_venue_info(
            event_data, base_url="https://custom.example.com"
        )
        assert venue is not None
        assert venue.venue_page_url == "https://custom.example.com/venues/my-venue"

    def test_extract_venue_page_data(self) -> None:
        """Test extracting venue data from venue page HTML."""
        venue_data = {
            "title": "Pleasance Courtyard",
            "contactPhone": "+44 131 556 6550",
            "contactEmail": "info@pleasance.co.uk",
        }
        data = {
            "props": {
                "pageProps": {
                    "initialState": {
                        "apiPublic": {
                            "queries": {
                                'Venue({"venueSlug":"pleasance"})': {
                                    "data": {"venue": venue_data}
                                }
                            }
                        }
                    }
                }
            }
        }
        html = f'<script id="__NEXT_DATA__" type="application/json">{json.dumps(data)}</script>'
        result = NextDataParser.extract_venue_page_data(html)
        assert result is not None
        assert result["title"] == "Pleasance Courtyard"
        assert result["contactPhone"] == "+44 131 556 6550"

    def test_extract_venue_page_data_not_found(self) -> None:
        """Test extract_venue_page_data with no venue data."""
        html = "<html><body>No next data</body></html>"
        assert NextDataParser.extract_venue_page_data(html) is None

    def test_extract_venue_page_data_no_venue_key(self) -> None:
        """Test extract_venue_page_data when queries have no Venue key."""
        data = {
            "props": {
                "pageProps": {
                    "initialState": {
                        "apiPublic": {
                            "queries": {
                                'Event({"eventId":"test"})': {
                                    "data": {"event": {}}
                                }
                            }
                        }
                    }
                }
            }
        }
        html = f'<script id="__NEXT_DATA__" type="application/json">{json.dumps(data)}</script>'
        assert NextDataParser.extract_venue_page_data(html) is None

    def test_parse_venue_contact(self) -> None:
        """Test parsing contact details from venue page data."""
        venue_data = {
            "contactPhone": "+44 131 556 6550",
            "contactEmail": "info@pleasance.co.uk",
        }
        phone, email = NextDataParser.parse_venue_contact(venue_data)
        assert phone == "+44 131 556 6550"
        assert email == "info@pleasance.co.uk"

    def test_parse_venue_contact_missing(self) -> None:
        """Test parsing contact when fields are missing."""
        phone, email = NextDataParser.parse_venue_contact({})
        assert phone == ""
        assert email == ""

    def test_parse_venue_contact_none_values(self) -> None:
        """Test parsing contact when fields are None."""
        venue_data = {"contactPhone": None, "contactEmail": None}
        phone, email = NextDataParser.parse_venue_contact(venue_data)
        assert phone == ""
        assert email == ""


class TestFringeParserShowDetail:
    """Test FringeParser.parse_show_detail returns ShowDetailResult."""

    @pytest.fixture
    def parser(self) -> FringeParser:
        return FringeParser(default_year=2025)

    def test_parse_show_detail_returns_named_tuple(
        self, parser: FringeParser
    ) -> None:
        """Test that parse_show_detail returns ShowDetailResult with venue_info."""
        event = {
            "title": "Comedy Show",
            "description": "Great show",
            "venues": [
                {
                    "title": "Venue A",
                    "venueCode": "VA1",
                    "slug": "venue-a",
                    "geoLocation": "55.94,-3.18",
                }
            ],
            "spaces": [],
            "performances": [
                {
                    "dateTime": "2025-08-01T19:30:00Z",
                    "ticketStatus": "TICKETS_AVAILABLE",
                }
            ],
            "attributes": [],
            "images": [],
        }
        data = {
            "props": {
                "pageProps": {
                    "initialState": {
                        "apiPublic": {
                            "queries": {
                                'Event({"eventId":"test"})': {
                                    "data": {"event": event}
                                }
                            }
                        }
                    }
                }
            }
        }
        html = f'<script id="__NEXT_DATA__" type="application/json">{json.dumps(data)}</script>'

        result = parser.parse_show_detail(
            html, show_url="https://edfringe.com/show/1", show_name="Comedy Show"
        )
        assert isinstance(result, ShowDetailResult)
        assert len(result.performances) == 1
        assert result.show_info is not None
        assert result.show_info.description == "Great show"
        assert result.venue_info is not None
        assert result.venue_info.venue_code == "VA1"
        assert result.venue_info.venue_page_url == "https://www.edfringe.com/venues/venue-a"

    def test_parse_show_detail_html_fallback(self, parser: FringeParser) -> None:
        """Test fallback returns None show_info and venue_info."""
        html = "<html><body>No next data</body></html>"
        result = parser.parse_show_detail(html)
        assert isinstance(result, ShowDetailResult)
        assert result.performances == []
        assert result.show_info is None
        assert result.venue_info is None

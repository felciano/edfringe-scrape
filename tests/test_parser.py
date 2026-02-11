"""Tests for HTML parser."""

import json
from datetime import date, time

import pytest

from edfringe_scrape.parser import FringeParser, NextDataParser


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

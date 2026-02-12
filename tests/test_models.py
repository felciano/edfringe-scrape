"""Tests for Pydantic models."""

from datetime import date, time

import pytest
from pydantic import ValidationError

from edfringe_scrape.models import (
    Genre,
    Performance,
    PerformanceDetail,
    RawPerformanceRow,
    ScrapedShow,
    Show,
    ShowCard,
    ShowInfo,
    VenueInfo,
)


class TestGenre:
    """Test Genre enum."""

    def test_genre_values(self) -> None:
        """Test Genre enum has expected values."""
        assert Genre.COMEDY.value == "COMEDY"
        assert Genre.MUSICALS.value == "MUSICALS"
        assert Genre.THEATRE.value == "THEATRE"

    def test_url_param(self) -> None:
        """Test url_param property."""
        assert Genre.COMEDY.url_param == "COMEDY"
        assert Genre.CHILDRENS_SHOWS.url_param == "CHILDRENS_SHOWS"


class TestShow:
    """Test Show model validation."""

    def test_valid_show(self) -> None:
        """Test creating valid show."""
        show = Show(
            name="Comedy Night",
            performer="John Smith",
            url="https://www.edfringe.com/shows/123",
        )
        assert show.name == "Comedy Night"
        assert show.performer == "John Smith"

    def test_minimal_show(self) -> None:
        """Test show with only required fields."""
        show = Show(
            name="Comedy Night",
            url="https://www.edfringe.com/shows/123",
        )
        assert show.name == "Comedy Night"
        assert show.performer is None
        assert show.venue is None

    def test_empty_name_fails(self) -> None:
        """Test empty name raises validation error."""
        with pytest.raises(ValidationError):
            Show(name="", url="https://www.edfringe.com/shows/123")


class TestPerformance:
    """Test Performance model validation."""

    def test_valid_performance(self) -> None:
        """Test creating valid performance."""
        perf = Performance(
            show_name="Comedy Night",
            show_url="https://www.edfringe.com/shows/123",
            date=date(2025, 8, 1),
            time=time(19, 30),
            availability="Available",
        )
        assert perf.show_name == "Comedy Night"
        assert perf.date == date(2025, 8, 1)
        assert perf.time == time(19, 30)

    def test_minimal_performance(self) -> None:
        """Test performance with only required fields."""
        perf = Performance(
            show_name="Comedy Night",
            show_url="https://www.edfringe.com/shows/123",
            date=date(2025, 8, 1),
        )
        assert perf.time is None
        assert perf.availability is None


class TestRawPerformanceRow:
    """Test RawPerformanceRow model with aliases."""

    def test_from_csv_columns(self) -> None:
        """Test creating from CSV column names."""
        row = RawPerformanceRow(
            **{
                "show-link-href": "https://www.edfringe.com/shows/123",
                "show-link": "Comedy Night",
                "show-name": "Comedy Night",
                "show-performer": "John Smith",
                "date": "Wednesday 30 July",
                "performance-time": "19:30 - 20:30",
                "show-availability": "Available",
                "show-location": "Pleasance Courtyard",
            }
        )
        assert row.show_link_href == "https://www.edfringe.com/shows/123"
        assert row.show_name == "Comedy Night"
        assert row.date == "Wednesday 30 July"


class TestShowCard:
    """Test ShowCard model."""

    def test_valid_show_card(self) -> None:
        """Test creating show card."""
        card = ShowCard(
            title="Comedy Night",
            url="https://www.edfringe.com/shows/123",
            performer="John Smith",
            duration="1hr 15mins",
        )
        assert card.title == "Comedy Night"
        assert card.performer == "John Smith"


class TestPerformanceDetail:
    """Test PerformanceDetail model."""

    def test_valid_detail(self) -> None:
        """Test creating performance detail."""
        detail = PerformanceDetail(
            date=date(2025, 8, 1),
            start_time=time(19, 30),
            end_time=time(20, 30),
            availability="Available",
            venue="Pleasance Courtyard",
        )
        assert detail.date == date(2025, 8, 1)
        assert detail.start_time == time(19, 30)


class TestShowInfo:
    """Test ShowInfo model."""

    def test_full_show_info(self) -> None:
        """Test creating ShowInfo with all fields populated."""
        info = ShowInfo(
            show_url="https://www.edfringe.com/shows/123",
            show_name="Comedy Night",
            genre="COMEDY",
            subgenres="Stand-up",
            description="A hilarious show",
            warnings="Strong language",
            age_suitability="16+",
            image_url="https://example.com/img.jpg",
            website="https://example.com",
            facebook="https://facebook.com/show",
            instagram="https://instagram.com/show",
            tiktok="https://tiktok.com/@show",
            youtube="https://youtube.com/show",
            twitter="https://twitter.com/show",
            bluesky="https://bsky.app/show",
            mastodon="https://mastodon.social/@show",
        )
        assert info.show_name == "Comedy Night"
        assert info.genre == "COMEDY"
        assert info.subgenres == "Stand-up"
        assert info.description == "A hilarious show"
        assert info.warnings == "Strong language"
        assert info.age_suitability == "16+"
        assert info.instagram == "https://instagram.com/show"

    def test_minimal_show_info(self) -> None:
        """Test creating ShowInfo with defaults."""
        info = ShowInfo()
        assert info.show_url == ""
        assert info.show_name == ""
        assert info.genre == ""
        assert info.subgenres == ""
        assert info.description == ""
        assert info.warnings == ""
        assert info.instagram == ""
        assert info.bluesky == ""


class TestVenueInfo:
    """Test VenueInfo model."""

    def test_full_venue_info(self) -> None:
        """Test creating VenueInfo with all fields populated."""
        venue = VenueInfo(
            venue_code="V123",
            venue_name="Pleasance Courtyard",
            address="60 Pleasance, Edinburgh",
            postcode="EH8 9TJ",
            geolocation="55.9469,-3.1813",
            google_maps_url="https://www.google.com/maps/dir/?api=1&destination=55.9469,-3.1813",
            venue_page_url="https://www.edfringe.com/venues/pleasance-courtyard",
            description="A popular Fringe venue",
            contact_phone="+44 131 556 6550",
            contact_email="info@pleasance.co.uk",
        )
        assert venue.venue_code == "V123"
        assert venue.venue_name == "Pleasance Courtyard"
        assert venue.postcode == "EH8 9TJ"
        assert venue.contact_phone == "+44 131 556 6550"
        assert venue.contact_email == "info@pleasance.co.uk"

    def test_minimal_venue_info(self) -> None:
        """Test creating VenueInfo with defaults."""
        venue = VenueInfo()
        assert venue.venue_code == ""
        assert venue.venue_name == ""
        assert venue.address == ""
        assert venue.postcode == ""
        assert venue.geolocation == ""
        assert venue.google_maps_url == ""
        assert venue.venue_page_url == ""
        assert venue.description == ""
        assert venue.contact_phone == ""
        assert venue.contact_email == ""


class TestScrapedShow:
    """Test ScrapedShow model."""

    def test_valid_scraped_show(self) -> None:
        """Test creating scraped show."""
        show = ScrapedShow(
            title="Comedy Night",
            url="https://www.edfringe.com/shows/123",
            performer="John Smith",
            genre=Genre.COMEDY,
            performances=[
                PerformanceDetail(
                    date=date(2025, 8, 1),
                    start_time=time(19, 30),
                )
            ],
        )
        assert show.title == "Comedy Night"
        assert show.genre == Genre.COMEDY
        assert len(show.performances) == 1

    def test_scraped_show_with_show_info(self) -> None:
        """Test creating scraped show with show info."""
        info = ShowInfo(
            show_url="https://www.edfringe.com/shows/123",
            show_name="Comedy Night",
            description="A great show",
        )
        show = ScrapedShow(
            title="Comedy Night",
            url="https://www.edfringe.com/shows/123",
            show_info=info,
        )
        assert show.show_info is not None
        assert show.show_info.description == "A great show"

    def test_scraped_show_with_venue_info(self) -> None:
        """Test creating scraped show with venue info."""
        venue = VenueInfo(
            venue_code="V123",
            venue_name="Pleasance Courtyard",
        )
        show = ScrapedShow(
            title="Comedy Night",
            url="https://www.edfringe.com/shows/123",
            venue_info=venue,
        )
        assert show.venue_info is not None
        assert show.venue_info.venue_code == "V123"

    def test_scraped_show_without_show_info(self) -> None:
        """Test creating scraped show without show info."""
        show = ScrapedShow(
            title="Comedy Night",
            url="https://www.edfringe.com/shows/123",
        )
        assert show.show_info is None
        assert show.venue_info is None

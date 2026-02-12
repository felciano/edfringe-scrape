"""Tests for core business logic."""

from pathlib import Path

import pytest

from edfringe_scrape.core import (
    collect_venues,
    load_venue_cache,
    save_venue_cache,
    show_info_to_dataframe,
)
from edfringe_scrape.models import ScrapedShow, ShowInfo, VenueInfo


class TestShowInfoToDataframe:
    """Test show_info_to_dataframe conversion."""

    def test_basic_conversion(self) -> None:
        """Test converting shows with info to DataFrame."""
        shows = [
            ScrapedShow(
                title="Show A",
                url="https://edfringe.com/shows/a",
                show_info=ShowInfo(
                    show_url="https://edfringe.com/shows/a",
                    show_name="Show A",
                    description="Description A",
                    warnings="Strong language",
                    instagram="https://instagram.com/a",
                ),
            ),
            ScrapedShow(
                title="Show B",
                url="https://edfringe.com/shows/b",
                show_info=ShowInfo(
                    show_url="https://edfringe.com/shows/b",
                    show_name="Show B",
                    description="Description B",
                ),
            ),
        ]
        df = show_info_to_dataframe(shows)
        assert len(df) == 2
        assert df.iloc[0]["show-name"] == "Show A"
        assert df.iloc[0]["description"] == "Description A"
        assert df.iloc[0]["warnings"] == "Strong language"
        assert df.iloc[0]["instagram"] == "https://instagram.com/a"
        assert df.iloc[1]["show-name"] == "Show B"

    def test_skips_shows_without_info(self) -> None:
        """Test that shows without show_info are skipped."""
        shows = [
            ScrapedShow(
                title="Show A",
                url="https://edfringe.com/shows/a",
                show_info=ShowInfo(
                    show_url="https://edfringe.com/shows/a",
                    show_name="Show A",
                    description="Has info",
                ),
            ),
            ScrapedShow(
                title="Show B",
                url="https://edfringe.com/shows/b",
                show_info=None,
            ),
        ]
        df = show_info_to_dataframe(shows)
        assert len(df) == 1
        assert df.iloc[0]["show-name"] == "Show A"

    def test_empty_input(self) -> None:
        """Test with empty list of shows."""
        df = show_info_to_dataframe([])
        assert df.empty

    def test_all_columns_present(self) -> None:
        """Test that all expected columns are in the DataFrame."""
        shows = [
            ScrapedShow(
                title="Show",
                url="https://edfringe.com/shows/1",
                show_info=ShowInfo(show_url="url", show_name="Show"),
            ),
        ]
        df = show_info_to_dataframe(shows)
        expected_cols = [
            "show-link-href",
            "show-name",
            "genre",
            "subgenres",
            "description",
            "warnings",
            "age_suitability",
            "image_url",
            "website",
            "facebook",
            "instagram",
            "tiktok",
            "youtube",
            "twitter",
            "bluesky",
            "mastodon",
        ]
        assert list(df.columns) == expected_cols


class TestCollectVenues:
    """Test collect_venues deduplication."""

    def test_collect_from_shows(self) -> None:
        """Test collecting unique venues from shows."""
        shows = [
            ScrapedShow(
                title="Show A",
                url="https://edfringe.com/shows/a",
                venue_info=VenueInfo(venue_code="V1", venue_name="Venue One"),
            ),
            ScrapedShow(
                title="Show B",
                url="https://edfringe.com/shows/b",
                venue_info=VenueInfo(venue_code="V2", venue_name="Venue Two"),
            ),
            ScrapedShow(
                title="Show C",
                url="https://edfringe.com/shows/c",
                venue_info=VenueInfo(venue_code="V1", venue_name="Venue One"),
            ),
        ]
        venues = collect_venues(shows)
        assert len(venues) == 2
        assert "V1" in venues
        assert "V2" in venues

    def test_collect_skips_missing_venue_info(self) -> None:
        """Test that shows without venue_info are skipped."""
        shows = [
            ScrapedShow(
                title="Show A",
                url="https://edfringe.com/shows/a",
                venue_info=None,
            ),
            ScrapedShow(
                title="Show B",
                url="https://edfringe.com/shows/b",
                venue_info=VenueInfo(venue_code="V1", venue_name="Venue One"),
            ),
        ]
        venues = collect_venues(shows)
        assert len(venues) == 1

    def test_collect_skips_empty_venue_code(self) -> None:
        """Test that venues with empty code are skipped."""
        shows = [
            ScrapedShow(
                title="Show A",
                url="https://edfringe.com/shows/a",
                venue_info=VenueInfo(venue_code="", venue_name="Unknown"),
            ),
        ]
        venues = collect_venues(shows)
        assert len(venues) == 0

    def test_collect_empty_input(self) -> None:
        """Test with empty list of shows."""
        assert collect_venues([]) == {}


class TestVenueCache:
    """Test venue cache load/save round-trip."""

    def test_save_and_load(self, tmp_path: Path) -> None:
        """Test saving and loading venue cache."""
        cache_path = tmp_path / "venue-info.csv"
        venues = {
            "V1": VenueInfo(
                venue_code="V1",
                venue_name="Pleasance Courtyard",
                address="60 Pleasance",
                postcode="EH8 9TJ",
                geolocation="55.9469,-3.1813",
                contact_phone="+44 131 556 6550",
                contact_email="info@pleasance.co.uk",
            ),
            "V2": VenueInfo(
                venue_code="V2",
                venue_name="Assembly Hall",
            ),
        }
        save_venue_cache(venues, cache_path)
        assert cache_path.exists()

        loaded = load_venue_cache(cache_path)
        assert len(loaded) == 2
        assert loaded["V1"].venue_name == "Pleasance Courtyard"
        assert loaded["V1"].contact_phone == "+44 131 556 6550"
        assert loaded["V2"].venue_name == "Assembly Hall"
        assert loaded["V2"].contact_phone == ""

    def test_load_missing_file(self, tmp_path: Path) -> None:
        """Test loading from non-existent file returns empty dict."""
        cache_path = tmp_path / "nonexistent.csv"
        assert load_venue_cache(cache_path) == {}

    def test_save_empty_venues(self, tmp_path: Path) -> None:
        """Test saving empty venues dict creates file with headers."""
        cache_path = tmp_path / "venue-info.csv"
        save_venue_cache({}, cache_path)
        assert cache_path.exists()
        loaded = load_venue_cache(cache_path)
        assert loaded == {}

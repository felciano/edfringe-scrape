"""Tests for core business logic."""

from pathlib import Path

import pandas as pd
import pytest

from edfringe_scrape.core import (
    PERFORMANCE_COLUMNS,
    SHOW_INFO_COLUMNS,
    collect_venues,
    load_canonical,
    load_venue_cache,
    merge_performances,
    merge_show_info,
    save_canonical,
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


def _make_perf_df(rows: list[dict]) -> pd.DataFrame:
    """Helper to create a performances DataFrame from row dicts."""
    base = {col: "" for col in PERFORMANCE_COLUMNS}
    return pd.DataFrame([{**base, **r} for r in rows])


def _make_info_df(rows: list[dict]) -> pd.DataFrame:
    """Helper to create a show-info DataFrame from row dicts."""
    base = {col: "" for col in SHOW_INFO_COLUMNS}
    return pd.DataFrame([{**base, **r} for r in rows])


class TestMergePerformances:
    """Test merge_performances logic."""

    def test_merge_into_empty(self) -> None:
        """New data merges cleanly into empty existing."""
        existing = pd.DataFrame(columns=PERFORMANCE_COLUMNS)
        new = _make_perf_df([
            {"show-link-href": "/a", "date": "Mon 1 Aug", "performance-time": "14:00", "genre": "COMEDY"},
        ])
        result = merge_performances(existing, new)
        assert len(result) == 1
        assert result.iloc[0]["show-link-href"] == "/a"

    def test_new_keys_preserved(self) -> None:
        """Non-overlapping keys from both sides are preserved."""
        existing = _make_perf_df([
            {"show-link-href": "/a", "date": "Mon 1 Aug", "performance-time": "14:00", "genre": "COMEDY"},
        ])
        new = _make_perf_df([
            {"show-link-href": "/b", "date": "Tue 2 Aug", "performance-time": "15:00", "genre": "COMEDY"},
        ])
        result = merge_performances(existing, new)
        assert len(result) == 2

    def test_matching_keys_overwritten(self) -> None:
        """Matching keys are overwritten by new data."""
        existing = _make_perf_df([
            {"show-link-href": "/a", "date": "Mon 1 Aug", "performance-time": "14:00",
             "show-availability": "AVAILABLE", "genre": "COMEDY"},
        ])
        new = _make_perf_df([
            {"show-link-href": "/a", "date": "Mon 1 Aug", "performance-time": "14:00",
             "show-availability": "SOLD_OUT", "genre": "COMEDY"},
        ])
        result = merge_performances(existing, new)
        assert len(result) == 1
        assert result.iloc[0]["show-availability"] == "SOLD_OUT"

    def test_full_mode_replaces_genre(self) -> None:
        """Full mode drops all existing rows for the scraped genre."""
        existing = _make_perf_df([
            {"show-link-href": "/a", "date": "Mon 1 Aug", "performance-time": "14:00", "genre": "COMEDY"},
            {"show-link-href": "/b", "date": "Mon 1 Aug", "performance-time": "15:00", "genre": "COMEDY"},
        ])
        new = _make_perf_df([
            {"show-link-href": "/c", "date": "Wed 3 Aug", "performance-time": "16:00", "genre": "COMEDY"},
        ])
        result = merge_performances(existing, new, full_mode=True)
        assert len(result) == 1
        assert result.iloc[0]["show-link-href"] == "/c"

    def test_full_mode_preserves_other_genres(self) -> None:
        """Full mode only replaces the scraped genre, not others."""
        existing = _make_perf_df([
            {"show-link-href": "/a", "date": "Mon 1 Aug", "performance-time": "14:00", "genre": "COMEDY"},
            {"show-link-href": "/b", "date": "Mon 1 Aug", "performance-time": "15:00", "genre": "THEATRE"},
        ])
        new = _make_perf_df([
            {"show-link-href": "/c", "date": "Wed 3 Aug", "performance-time": "16:00", "genre": "COMEDY"},
        ])
        result = merge_performances(existing, new, full_mode=True)
        assert len(result) == 2
        genres = set(result["genre"])
        assert "THEATRE" in genres
        assert "COMEDY" in genres

    def test_empty_new_data(self) -> None:
        """Empty new data returns existing unchanged."""
        existing = _make_perf_df([
            {"show-link-href": "/a", "date": "Mon 1 Aug", "performance-time": "14:00", "genre": "COMEDY"},
        ])
        new = pd.DataFrame(columns=PERFORMANCE_COLUMNS)
        result = merge_performances(existing, new)
        assert len(result) == 1


class TestMergeShowInfo:
    """Test merge_show_info logic."""

    def test_merge_into_empty(self) -> None:
        """New data merges cleanly into empty existing."""
        existing = pd.DataFrame(columns=SHOW_INFO_COLUMNS)
        new = _make_info_df([
            {"show-link-href": "/a", "show-name": "Show A"},
        ])
        result = merge_show_info(existing, new)
        assert len(result) == 1

    def test_overwrites_by_url(self) -> None:
        """Matching URLs are overwritten by new data."""
        existing = _make_info_df([
            {"show-link-href": "/a", "show-name": "Old Name", "description": "old"},
        ])
        new = _make_info_df([
            {"show-link-href": "/a", "show-name": "New Name", "description": "new"},
        ])
        result = merge_show_info(existing, new)
        assert len(result) == 1
        assert result.iloc[0]["show-name"] == "New Name"
        assert result.iloc[0]["description"] == "new"

    def test_preserves_non_matching(self) -> None:
        """Non-matching shows are preserved."""
        existing = _make_info_df([
            {"show-link-href": "/a", "show-name": "Show A"},
            {"show-link-href": "/b", "show-name": "Show B"},
        ])
        new = _make_info_df([
            {"show-link-href": "/a", "show-name": "Show A Updated"},
        ])
        result = merge_show_info(existing, new)
        assert len(result) == 2
        urls = set(result["show-link-href"])
        assert "/a" in urls
        assert "/b" in urls

    def test_empty_new_data(self) -> None:
        """Empty new data returns existing unchanged."""
        existing = _make_info_df([
            {"show-link-href": "/a", "show-name": "Show A"},
        ])
        new = pd.DataFrame(columns=SHOW_INFO_COLUMNS)
        result = merge_show_info(existing, new)
        assert len(result) == 1


class TestLoadCanonical:
    """Test load_canonical function."""

    def test_load_existing_file(self, tmp_path: Path) -> None:
        """Test loading an existing CSV file."""
        csv_path = tmp_path / "test.csv"
        df = pd.DataFrame({"show-link-href": ["/a"], "genre": ["COMEDY"]})
        df.to_csv(csv_path, index=False)

        result = load_canonical(csv_path, ["show-link-href", "genre", "extra"])
        assert len(result) == 1
        assert "extra" in result.columns

    def test_load_missing_file(self, tmp_path: Path) -> None:
        """Test loading from non-existent file returns empty with schema."""
        csv_path = tmp_path / "missing.csv"
        result = load_canonical(csv_path, ["col_a", "col_b"])
        assert result.empty
        assert list(result.columns) == ["col_a", "col_b"]


class TestSaveCanonical:
    """Test save_canonical function."""

    def test_creates_file(self, tmp_path: Path) -> None:
        """Test saving creates the CSV file."""
        csv_path = tmp_path / "output.csv"
        df = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
        save_canonical(df, csv_path)
        assert csv_path.exists()
        loaded = pd.read_csv(csv_path)
        assert len(loaded) == 2

    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        """Test saving creates parent directories."""
        csv_path = tmp_path / "nested" / "dir" / "output.csv"
        df = pd.DataFrame({"a": [1]})
        save_canonical(df, csv_path)
        assert csv_path.exists()

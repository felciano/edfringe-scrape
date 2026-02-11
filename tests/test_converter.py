"""Tests for data converter."""

from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd
import pytest

from edfringe_scrape.converter import FringeConverter, save_all_formats


class TestFringeConverter:
    """Test FringeConverter functionality."""

    @pytest.fixture
    def converter(self) -> FringeConverter:
        """Create converter with default year 2025."""
        return FringeConverter(default_year=2025)

    @pytest.fixture
    def sample_df(self) -> pd.DataFrame:
        """Create sample raw DataFrame."""
        return pd.DataFrame(
            {
                "show-link-href": [
                    "https://edfringe.com/shows/1",
                    "https://edfringe.com/shows/1",
                    "https://edfringe.com/shows/2",
                ],
                "show-link": ["Show One", "Show One", "Show Two"],
                "show-name": ["Show One", "Show One", "Show Two"],
                "show-performer": ["Performer A", "Performer A", "Performer B"],
                "date": ["Wednesday 30 July", "Thursday 31 July", "Wednesday 30 July"],
                "performance-time": ["19:30", "19:30", "21:00"],
                "show-availability": ["Available", "Limited", "Available"],
                "show-location": ["Venue A", "Venue A", "Venue B"],
            }
        )

    def test_parse_date_valid(self, converter: FringeConverter) -> None:
        """Test parsing valid date."""
        result = converter._parse_date("Wednesday 30 July")
        assert result == "2025-07-30"

    def test_parse_date_invalid(self, converter: FringeConverter) -> None:
        """Test parsing invalid date."""
        result = converter._parse_date("not a date")
        assert result is None

    def test_parse_date_empty(self, converter: FringeConverter) -> None:
        """Test parsing empty string."""
        result = converter._parse_date("")
        assert result is None

    def test_create_hyperlink(self, converter: FringeConverter) -> None:
        """Test creating Excel hyperlink."""
        result = converter._create_hyperlink("https://example.com", "Example")
        assert result == '=HYPERLINK("https://example.com", "Example")'

    def test_create_hyperlink_with_quotes(self, converter: FringeConverter) -> None:
        """Test hyperlink with quotes in text."""
        result = converter._create_hyperlink("https://example.com", 'Show "Title"')
        assert '""' in result

    def test_clean_data(
        self, converter: FringeConverter, sample_df: pd.DataFrame
    ) -> None:
        """Test cleaning raw data."""
        result = converter.clean_data(sample_df)

        assert len(result) == 3
        assert "date_normalized" in result.columns
        assert "show" in result.columns

        assert pd.api.types.is_datetime64_any_dtype(result["date_normalized"])

    def test_clean_data_drops_invalid_dates(self, converter: FringeConverter) -> None:
        """Test that invalid dates are dropped."""
        df = pd.DataFrame(
            {
                "show-link-href": ["url1", "url2"],
                "show-link": ["Show 1", "Show 2"],
                "show-name": ["Show 1", "Show 2"],
                "date": ["Wednesday 30 July", "invalid date"],
                "performance-time": ["19:30", "20:00"],
                "show-availability": ["Available", "Available"],
                "show-location": ["Venue", "Venue"],
            }
        )
        result = converter.clean_data(df)
        assert len(result) == 1

    def test_create_summary(
        self, converter: FringeConverter, sample_df: pd.DataFrame
    ) -> None:
        """Test creating summary."""
        cleaned = converter.clean_data(sample_df)
        summary = converter.create_summary(cleaned)

        assert len(summary) == 2
        assert "num_performances" in summary.columns
        assert "first_date" in summary.columns
        assert "last_date" in summary.columns

        show_one = summary[summary["show-name"] == "Show One"].iloc[0]
        assert show_one["num_performances"] == 2

    def test_create_wide_format(
        self, converter: FringeConverter, sample_df: pd.DataFrame
    ) -> None:
        """Test creating wide format."""
        cleaned = converter.clean_data(sample_df)
        wide = converter.create_wide_format(cleaned)

        assert "2025-07-30" in wide.columns
        assert "2025-07-31" in wide.columns


class TestSaveAllFormats:
    """Test save_all_formats function."""

    @pytest.fixture
    def sample_df(self) -> pd.DataFrame:
        """Create sample DataFrame."""
        return pd.DataFrame(
            {
                "show-link-href": ["url1", "url2"],
                "show-link": ["Show 1", "Show 2"],
                "show-name": ["Show 1", "Show 2"],
                "show-performer": ["Performer 1", "Performer 2"],
                "date": ["Wednesday 30 July", "Thursday 31 July"],
                "performance-time": ["19:30", "20:00"],
                "show-availability": ["Available", "Limited"],
                "show-location": ["Venue A", "Venue B"],
            }
        )

    def test_save_all_formats(self, sample_df: pd.DataFrame) -> None:
        """Test saving all formats."""
        with TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            results = save_all_formats(
                sample_df,
                output_dir,
                "test-file",
                formats=["cleaned", "summary", "wide"],
            )

            assert "cleaned" in results
            assert "summary" in results
            assert "wide" in results

            assert results["cleaned"].exists()
            assert results["summary"].exists()
            assert results["wide"].exists()

            assert "Cleaned-test-file.csv" in str(results["cleaned"])
            assert "Summary-test-file.csv" in str(results["summary"])
            assert "WideFormat-test-file.csv" in str(results["wide"])

    def test_save_single_format(self, sample_df: pd.DataFrame) -> None:
        """Test saving single format."""
        with TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            results = save_all_formats(
                sample_df,
                output_dir,
                "test-file",
                formats=["summary"],
            )

            assert "summary" in results
            assert "cleaned" not in results
            assert results["summary"].exists()


class TestFestivalPlannerExport:
    """Test Festival Planner format export."""

    @pytest.fixture
    def converter(self) -> FringeConverter:
        """Create converter with year 2026."""
        return FringeConverter(default_year=2026)

    @pytest.fixture
    def sample_scraped_df(self) -> pd.DataFrame:
        """Create sample scraped DataFrame."""
        return pd.DataFrame(
            {
                "show-name": ["Comedy Show", "Drama Play"],
                "show-performer": ["John Smith", "Jane Doe"],
                "show-location": ["Main Stage", "Side Room"],
                "date": ["Thursday 06 August", "Friday 07 August"],
                "performance-time": ["19:30 - 20:30", "14:00 - 15:30"],
                "show-availability": ["TICKETS_AVAILABLE", "TWO_FOR_ONE"],
            }
        )

    def test_to_festival_planner_format(
        self, converter: FringeConverter, sample_scraped_df: pd.DataFrame
    ) -> None:
        """Test conversion to Festival Planner format."""
        result = converter.to_festival_planner_format(
            sample_scraped_df, smart_parsing=False
        )

        assert len(result) == 2
        assert list(result.columns) == [
            "performer",
            "producer",
            "show_name",
            "original_show_name",
            "venue_name",
            "date",
            "start_time",
            "end_time",
            "availability",
        ]

        row1 = result.iloc[0]
        assert row1["performer"] == "John Smith"
        assert row1["producer"] == ""
        assert row1["show_name"] == "Comedy Show"
        assert row1["original_show_name"] == "Comedy Show"
        assert row1["venue_name"] == "Main Stage"
        assert row1["date"] == "2026-08-06"
        assert row1["start_time"] == "19:30"
        assert row1["end_time"] == "20:30"
        assert row1["availability"] == "tickets-available"

        row2 = result.iloc[1]
        assert row2["availability"] == "2-for-1-show"

    def test_map_availability(self, converter: FringeConverter) -> None:
        """Test availability mapping."""
        assert converter._map_availability("TICKETS_AVAILABLE") == "tickets-available"
        assert converter._map_availability("TWO_FOR_ONE") == "2-for-1-show"
        assert converter._map_availability("SOLD_OUT") == "sold-out"
        assert converter._map_availability("CANCELLED") == "cancelled"
        assert converter._map_availability("PREVIEW") == "preview-show"
        assert converter._map_availability("FREE_TICKETED") == "free-show"
        assert converter._map_availability("") == "tickets-available"
        assert converter._map_availability("UNKNOWN") == "tickets-available"

    def test_parse_time_range(self, converter: FringeConverter) -> None:
        """Test time range parsing."""
        assert converter._parse_time_range("19:30 - 20:30") == ("19:30", "20:30")
        assert converter._parse_time_range("14:00 – 15:30") == ("14:00", "15:30")
        assert converter._parse_time_range("19:30") == ("19:30", "")
        assert converter._parse_time_range("") == ("", "")

    def test_is_production_company(self, converter: FringeConverter) -> None:
        """Test production company detection."""
        # Should be detected as production companies
        assert converter._is_production_company("Impatient Productions")
        assert converter._is_production_company("AEG Presents")
        assert converter._is_production_company("PBJ Management")
        assert converter._is_production_company("Live Nation Entertainment")
        assert converter._is_production_company("Laughing Horse @ Bar 50")
        assert converter._is_production_company("Pleasance")
        assert converter._is_production_company("Assembly")
        assert converter._is_production_company("Gilded Balloon")
        assert converter._is_production_company("Free Festival")
        assert converter._is_production_company("Just The Tonic")
        assert converter._is_production_company("Off The Kerb Productions")

        # Should NOT be detected as production companies (actual performers)
        assert not converter._is_production_company("John Smith")
        assert not converter._is_production_company("Mark Watson")
        assert not converter._is_production_company("Sarah Millican")
        assert not converter._is_production_company("The Mighty Boosh")
        assert not converter._is_production_company("")

    def test_extract_performer_from_title(self, converter: FringeConverter) -> None:
        """Test performer extraction from title."""
        # Should extract performer
        assert converter._extract_performer_from_title(
            "Mark Watson: Before It Overtakes Us"
        ) == ("Mark Watson", "Before It Overtakes Us")
        assert converter._extract_performer_from_title(
            "Sarah Millican: Control Enthusiast"
        ) == ("Sarah Millican", "Control Enthusiast")
        assert converter._extract_performer_from_title("John Smith: The Show") == (
            "John Smith",
            "The Show",
        )

        # Should NOT extract (subtitle patterns)
        assert converter._extract_performer_from_title("Part 1: The Beginning") == (
            "",
            "Part 1: The Beginning",
        )
        assert converter._extract_performer_from_title("Live: From Edinburgh") == (
            "",
            "Live: From Edinburgh",
        )
        assert converter._extract_performer_from_title(
            "The Comedy Show: A Journey"
        ) == ("", "The Comedy Show: A Journey")

        # No colon
        assert converter._extract_performer_from_title("Just A Show Title") == (
            "",
            "Just A Show Title",
        )
        assert converter._extract_performer_from_title("") == ("", "")

    def test_parse_performer_producer_show_with_production_company(
        self, converter: FringeConverter
    ) -> None:
        """Test parsing when presenter is a production company."""
        # Production company with performer in title
        performer, producer, show = converter._parse_performer_producer_show(
            "Impatient Productions", "Mark Watson: Before It Overtakes Us"
        )
        assert performer == "Mark Watson"
        assert producer == "Impatient Productions"
        assert show == "Before It Overtakes Us"

        # Production company without performer in title
        performer, producer, show = converter._parse_performer_producer_show(
            "AEG Presents", "The Big Comedy Show"
        )
        assert performer == ""
        assert producer == "AEG Presents"
        assert show == "The Big Comedy Show"

    def test_parse_performer_producer_show_with_performer(
        self, converter: FringeConverter
    ) -> None:
        """Test parsing when presenter is the actual performer."""
        # Performer name in presenter, no colon in title
        performer, producer, show = converter._parse_performer_producer_show(
            "John Smith", "The Funniest Hour"
        )
        assert performer == "John Smith"
        assert producer == ""
        assert show == "The Funniest Hour"

        # Performer name in presenter, matching name in title
        performer, producer, show = converter._parse_performer_producer_show(
            "Mark Watson", "Mark Watson: Before It Overtakes Us"
        )
        assert performer == "Mark Watson"
        assert producer == ""
        assert show == "Before It Overtakes Us"

    def test_smart_parsing_in_export(self, converter: FringeConverter) -> None:
        """Test smart parsing is applied during export."""
        df = pd.DataFrame(
            {
                "show-name": ["Mark Watson: Before It Overtakes Us"],
                "show-performer": ["Impatient Productions"],
                "show-location": ["Pleasance Courtyard"],
                "date": ["Thursday 06 August"],
                "performance-time": ["19:30 - 20:30"],
                "show-availability": ["TICKETS_AVAILABLE"],
            }
        )

        result = converter.to_festival_planner_format(df, smart_parsing=True)

        assert len(result) == 1
        row = result.iloc[0]
        assert row["performer"] == "Mark Watson"
        assert row["producer"] == "Impatient Productions"
        assert row["show_name"] == "Before It Overtakes Us"
        assert row["original_show_name"] == "Mark Watson: Before It Overtakes Us"

    def test_multiple_performers(self, converter: FringeConverter) -> None:
        """Test that multiple performers are combined comma-delimited."""
        # Case: presenter is a performer, and title has a different performer
        performer, producer, show = converter._parse_performer_producer_show(
            "Jane Doe", "John Smith: The Big Show"
        )
        assert performer == "Jane Doe, John Smith"
        assert producer == ""
        assert show == "The Big Show"

    def test_same_performer_in_title_and_presenter(
        self, converter: FringeConverter
    ) -> None:
        """Test that same performer is not duplicated."""
        performer, producer, show = converter._parse_performer_producer_show(
            "Mark Watson", "Mark Watson: Before It Overtakes Us"
        )
        assert performer == "Mark Watson"
        assert producer == ""
        assert show == "Before It Overtakes Us"

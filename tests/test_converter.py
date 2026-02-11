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

"""Tests for Pydantic models."""

from datetime import date, time

import pytest
from pydantic import ValidationError

from edfringe_scrape.models import Performance, Show


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

"""Tests for snapshot comparison."""

import pandas as pd
import pytest

from edfringe_scrape.snapshot import (
    SnapshotDiff,
    compare_snapshots,
    format_diff_as_html,
    format_diff_as_text,
)


@pytest.fixture
def base_snapshot() -> pd.DataFrame:
    """Create a base snapshot DataFrame."""
    return pd.DataFrame(
        {
            "web-scraper-scrape-time": ["2026-02-10T06:00:00"] * 4,
            "show-link-href": [
                "https://edfringe.com/shows/1",
                "https://edfringe.com/shows/1",
                "https://edfringe.com/shows/2",
                "https://edfringe.com/shows/3",
            ],
            "show-name": ["Show One", "Show One", "Show Two", "Show Three"],
            "show-performer": ["Performer A", "Performer A", "Performer B", "Performer C"],
            "date": [
                "Wednesday 05 August",
                "Thursday 06 August",
                "Wednesday 05 August",
                "Friday 07 August",
            ],
            "performance-time": ["19:30", "19:30", "20:00", "21:00"],
            "show-availability": [
                "TICKETS_AVAILABLE",
                "TICKETS_AVAILABLE",
                "TICKETS_AVAILABLE",
                "TICKETS_AVAILABLE",
            ],
            "show-location": ["Venue A", "Venue A", "Venue B", "Venue C"],
        }
    )


class TestCompareSnapshots:
    """Test snapshot comparison."""

    def test_no_changes(self, base_snapshot: pd.DataFrame) -> None:
        """Test comparison with no changes."""
        diff = compare_snapshots(base_snapshot, base_snapshot.copy())
        assert not diff.has_changes
        assert diff.total_changes == 0

    def test_new_show(self, base_snapshot: pd.DataFrame) -> None:
        """Test detecting a new show."""
        new_snapshot = base_snapshot.copy()
        new_row = pd.DataFrame(
            {
                "web-scraper-scrape-time": ["2026-02-11T06:00:00"],
                "show-link-href": ["https://edfringe.com/shows/4"],
                "show-name": ["New Show"],
                "show-performer": ["New Performer"],
                "date": ["Saturday 08 August"],
                "performance-time": ["18:00"],
                "show-availability": ["TICKETS_AVAILABLE"],
                "show-location": ["Venue D"],
            }
        )
        new_snapshot = pd.concat([new_snapshot, new_row], ignore_index=True)

        diff = compare_snapshots(base_snapshot, new_snapshot)

        assert diff.has_changes
        assert len(diff.new_shows) == 1
        assert diff.new_shows[0].show_name == "New Show"
        assert diff.new_shows[0].performer == "New Performer"

    def test_removed_show(self, base_snapshot: pd.DataFrame) -> None:
        """Test detecting a removed show."""
        new_snapshot = base_snapshot[
            base_snapshot["show-link-href"] != "https://edfringe.com/shows/3"
        ].copy()

        diff = compare_snapshots(base_snapshot, new_snapshot)

        assert diff.has_changes
        assert len(diff.removed_shows) == 1
        assert diff.removed_shows[0].show_name == "Show Three"

    def test_sold_out(self, base_snapshot: pd.DataFrame) -> None:
        """Test detecting sold out performances."""
        new_snapshot = base_snapshot.copy()
        new_snapshot.loc[
            (new_snapshot["show-link-href"] == "https://edfringe.com/shows/2"),
            "show-availability",
        ] = "SOLD_OUT"

        diff = compare_snapshots(base_snapshot, new_snapshot)

        assert diff.has_changes
        assert len(diff.sold_out_performances) == 1
        assert diff.sold_out_performances[0].show_name == "Show Two"

    def test_cancelled(self, base_snapshot: pd.DataFrame) -> None:
        """Test detecting cancelled performances."""
        new_snapshot = base_snapshot.copy()
        new_snapshot.loc[
            (new_snapshot["show-link-href"] == "https://edfringe.com/shows/3"),
            "show-availability",
        ] = "CANCELLED"

        diff = compare_snapshots(base_snapshot, new_snapshot)

        assert diff.has_changes
        assert len(diff.cancelled_performances) == 1

    def test_back_available(self, base_snapshot: pd.DataFrame) -> None:
        """Test detecting performances back available."""
        # Start with sold out
        old_snapshot = base_snapshot.copy()
        old_snapshot.loc[
            (old_snapshot["show-link-href"] == "https://edfringe.com/shows/2"),
            "show-availability",
        ] = "SOLD_OUT"

        # New snapshot has it available again
        new_snapshot = base_snapshot.copy()

        diff = compare_snapshots(old_snapshot, new_snapshot)

        assert diff.has_changes
        assert len(diff.back_available) == 1
        assert diff.back_available[0].show_name == "Show Two"

    def test_new_performance_for_existing_show(
        self, base_snapshot: pd.DataFrame
    ) -> None:
        """Test detecting new performances for existing shows."""
        new_snapshot = base_snapshot.copy()
        new_row = pd.DataFrame(
            {
                "web-scraper-scrape-time": ["2026-02-11T06:00:00"],
                "show-link-href": ["https://edfringe.com/shows/1"],  # Existing show
                "show-name": ["Show One"],
                "show-performer": ["Performer A"],
                "date": ["Friday 07 August"],  # New date
                "performance-time": ["19:30"],
                "show-availability": ["TICKETS_AVAILABLE"],
                "show-location": ["Venue A"],
            }
        )
        new_snapshot = pd.concat([new_snapshot, new_row], ignore_index=True)

        diff = compare_snapshots(base_snapshot, new_snapshot)

        assert diff.has_changes
        assert len(diff.new_performances) == 1
        assert diff.new_performances[0].show_name == "Show One"
        assert diff.new_performances[0].date == "Friday 07 August"


class TestSnapshotDiff:
    """Test SnapshotDiff class."""

    def test_has_changes_false_when_empty(self) -> None:
        """Test has_changes is False when no changes."""
        diff = SnapshotDiff(
            old_snapshot_date="2026-02-10",
            new_snapshot_date="2026-02-11",
        )
        assert not diff.has_changes
        assert diff.total_changes == 0

    def test_total_changes_counts_all(self) -> None:
        """Test total_changes counts all change types."""
        diff = SnapshotDiff(
            old_snapshot_date="2026-02-10",
            new_snapshot_date="2026-02-11",
        )
        from edfringe_scrape.snapshot import PerformanceChange, ShowChange

        diff.new_shows.append(
            ShowChange("Show", "url", "Performer", "new_show", 1)
        )
        diff.sold_out_performances.append(
            PerformanceChange("Show", "url", "Perf", "Venue", "date", "time", "sold_out")
        )

        assert diff.total_changes == 2


class TestFormatDiff:
    """Test diff formatting."""

    def test_format_text_no_changes(self) -> None:
        """Test text format with no changes."""
        diff = SnapshotDiff(
            old_snapshot_date="2026-02-10 06:00",
            new_snapshot_date="2026-02-11 06:00",
        )
        text = format_diff_as_text(diff)
        assert "No changes detected" in text
        assert "2026-02-10" in text
        assert "2026-02-11" in text

    def test_format_text_with_changes(self, base_snapshot: pd.DataFrame) -> None:
        """Test text format with changes."""
        new_snapshot = base_snapshot.copy()
        new_snapshot.loc[0, "show-availability"] = "SOLD_OUT"

        diff = compare_snapshots(base_snapshot, new_snapshot)
        text = format_diff_as_text(diff)

        assert "SOLD OUT" in text
        assert "Show One" in text

    def test_format_html_no_changes(self) -> None:
        """Test HTML format with no changes."""
        diff = SnapshotDiff(
            old_snapshot_date="2026-02-10 06:00",
            new_snapshot_date="2026-02-11 06:00",
        )
        html = format_diff_as_html(diff)
        assert "<html>" in html
        assert "No changes detected" in html

    def test_format_html_with_changes(self, base_snapshot: pd.DataFrame) -> None:
        """Test HTML format with changes."""
        new_snapshot = base_snapshot.copy()
        new_row = pd.DataFrame(
            {
                "web-scraper-scrape-time": ["2026-02-11T06:00:00"],
                "show-link-href": ["https://edfringe.com/shows/new"],
                "show-name": ["Brand New Show"],
                "show-performer": ["New Performer"],
                "date": ["Saturday 08 August"],
                "performance-time": ["18:00"],
                "show-availability": ["TICKETS_AVAILABLE"],
                "show-location": ["Venue D"],
            }
        )
        new_snapshot = pd.concat([new_snapshot, new_row], ignore_index=True)

        diff = compare_snapshots(base_snapshot, new_snapshot)
        html = format_diff_as_html(diff)

        assert "<html>" in html
        assert "Brand New Show" in html
        assert "NEW" in html

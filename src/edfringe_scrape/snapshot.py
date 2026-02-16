"""Snapshot comparison for tracking Edinburgh Fringe performance changes."""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class PerformanceChange:
    """Represents a change to a performance."""

    show_name: str
    show_url: str
    performer: str
    venue: str
    date: str
    time: str
    change_type: str  # "new", "sold_out", "cancelled", "back_available", "time_changed"
    old_value: str | None = None
    new_value: str | None = None


@dataclass
class ShowChange:
    """Represents changes to a show."""

    show_name: str
    show_url: str
    performer: str
    change_type: str  # "new_show", "removed_show"
    performance_count: int = 0
    venues: list[str] = field(default_factory=list)
    date_range: str = ""


@dataclass
class SnapshotDiff:
    """Summary of differences between two snapshots."""

    old_snapshot_date: str
    new_snapshot_date: str
    new_shows: list[ShowChange] = field(default_factory=list)
    removed_shows: list[ShowChange] = field(default_factory=list)
    new_performances: list[PerformanceChange] = field(default_factory=list)
    sold_out_performances: list[PerformanceChange] = field(default_factory=list)
    cancelled_performances: list[PerformanceChange] = field(default_factory=list)
    back_available: list[PerformanceChange] = field(default_factory=list)
    other_changes: list[PerformanceChange] = field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        """Check if there are any changes."""
        return bool(
            self.new_shows
            or self.removed_shows
            or self.new_performances
            or self.sold_out_performances
            or self.cancelled_performances
            or self.back_available
            or self.other_changes
        )

    @property
    def total_changes(self) -> int:
        """Total number of changes."""
        return (
            len(self.new_shows)
            + len(self.removed_shows)
            + len(self.new_performances)
            + len(self.sold_out_performances)
            + len(self.cancelled_performances)
            + len(self.back_available)
            + len(self.other_changes)
        )


def _create_performance_key(row: pd.Series) -> str:
    """Create unique key for a performance."""
    return f"{row.get('show-link-href', '')}|{row.get('date', '')}|{row.get('performance-time', '')}"


def _create_show_key(row: pd.Series) -> str:
    """Create unique key for a show."""
    return row.get("show-link-href", "")


def compare_snapshots(old_df: pd.DataFrame, new_df: pd.DataFrame) -> SnapshotDiff:
    """Compare two snapshots and return differences.

    Args:
        old_df: Previous snapshot DataFrame
        new_df: Current snapshot DataFrame

    Returns:
        SnapshotDiff with all detected changes
    """
    diff = SnapshotDiff(
        old_snapshot_date=_extract_snapshot_date(old_df),
        new_snapshot_date=_extract_snapshot_date(new_df),
    )

    # Create performance keys
    old_df = old_df.copy()
    new_df = new_df.copy()
    old_df["_perf_key"] = old_df.apply(_create_performance_key, axis=1)
    new_df["_perf_key"] = new_df.apply(_create_performance_key, axis=1)

    old_perf_keys = set(old_df["_perf_key"])
    new_perf_keys = set(new_df["_perf_key"])

    # Find new and removed shows
    old_shows = set(old_df["show-link-href"].dropna().unique())
    new_shows = set(new_df["show-link-href"].dropna().unique())

    added_shows = new_shows - old_shows
    removed_shows = old_shows - new_shows

    # Process new shows
    for show_url in added_shows:
        show_rows = new_df[new_df["show-link-href"] == show_url]
        if len(show_rows) > 0:
            first_row = show_rows.iloc[0]
            venues = show_rows["show-location"].dropna().unique().tolist()
            dates = show_rows["date"].dropna().unique().tolist()
            date_range = f"{min(dates)} - {max(dates)}" if dates else ""

            diff.new_shows.append(
                ShowChange(
                    show_name=first_row.get("show-name", ""),
                    show_url=show_url,
                    performer=first_row.get("show-performer", ""),
                    change_type="new_show",
                    performance_count=len(show_rows),
                    venues=venues[:3],  # Limit to first 3 venues
                    date_range=date_range,
                )
            )

    # Process removed shows
    for show_url in removed_shows:
        show_rows = old_df[old_df["show-link-href"] == show_url]
        if len(show_rows) > 0:
            first_row = show_rows.iloc[0]
            diff.removed_shows.append(
                ShowChange(
                    show_name=first_row.get("show-name", ""),
                    show_url=show_url,
                    performer=first_row.get("show-performer", ""),
                    change_type="removed_show",
                    performance_count=len(show_rows),
                )
            )

    # Find new performances (for existing shows)
    new_perf_keys_for_existing = new_perf_keys - old_perf_keys
    for perf_key in new_perf_keys_for_existing:
        row = new_df[new_df["_perf_key"] == perf_key].iloc[0]
        show_url = row.get("show-link-href", "")

        # Skip if it's part of a new show
        if show_url in added_shows:
            continue

        diff.new_performances.append(
            PerformanceChange(
                show_name=row.get("show-name", ""),
                show_url=show_url,
                performer=row.get("show-performer", ""),
                venue=row.get("show-location", ""),
                date=row.get("date", ""),
                time=row.get("performance-time", ""),
                change_type="new",
            )
        )

    # Find availability changes for existing performances
    common_perf_keys = old_perf_keys & new_perf_keys
    for perf_key in common_perf_keys:
        old_row = old_df[old_df["_perf_key"] == perf_key].iloc[0]
        new_row = new_df[new_df["_perf_key"] == perf_key].iloc[0]

        old_avail = str(old_row.get("show-availability", "")).upper()
        new_avail = str(new_row.get("show-availability", "")).upper()

        if old_avail != new_avail:
            change = PerformanceChange(
                show_name=new_row.get("show-name", ""),
                show_url=new_row.get("show-link-href", ""),
                performer=new_row.get("show-performer", ""),
                venue=new_row.get("show-location", ""),
                date=new_row.get("date", ""),
                time=new_row.get("performance-time", ""),
                change_type="availability",
                old_value=old_avail,
                new_value=new_avail,
            )

            # Categorize the change
            if new_avail in ("SOLD_OUT", "NO_ALLOCATION", "NO_ALLOCATION_REMAINING"):
                change.change_type = "sold_out"
                diff.sold_out_performances.append(change)
            elif new_avail == "CANCELLED":
                change.change_type = "cancelled"
                diff.cancelled_performances.append(change)
            elif old_avail in (
                "SOLD_OUT",
                "NO_ALLOCATION",
                "NO_ALLOCATION_REMAINING",
                "CANCELLED",
            ):
                change.change_type = "back_available"
                diff.back_available.append(change)
            else:
                change.change_type = "availability_changed"
                diff.other_changes.append(change)

    logger.info(
        f"Comparison complete: {len(diff.new_shows)} new shows, "
        f"{len(diff.new_performances)} new performances, "
        f"{len(diff.sold_out_performances)} sold out"
    )

    return diff


def _extract_snapshot_date(df: pd.DataFrame) -> str:
    """Extract snapshot date from DataFrame."""
    if "web-scraper-scrape-time" in df.columns:
        times = df["web-scraper-scrape-time"].dropna()
        if len(times) > 0:
            try:
                dt = datetime.fromisoformat(str(times.iloc[0]))
                return dt.strftime("%Y-%m-%d %H:%M")
            except (ValueError, TypeError):
                pass
    return "Unknown"


def find_latest_snapshot(snapshot_dir: Path, exclude_date: str | None = None) -> Path | None:
    """Find the most recent snapshot file.

    Args:
        snapshot_dir: Directory containing snapshots
        exclude_date: Date string to exclude (e.g., today's date)

    Returns:
        Path to most recent snapshot, or None
    """
    if not snapshot_dir.exists():
        return None

    snapshots = sorted(snapshot_dir.glob("*-snapshot.csv"), reverse=True)

    for snapshot in snapshots:
        if exclude_date and exclude_date in snapshot.name:
            continue
        return snapshot

    return None


def load_snapshot(path: Path) -> pd.DataFrame:
    """Load a snapshot CSV file.

    Args:
        path: Path to CSV file

    Returns:
        DataFrame with snapshot data
    """
    logger.info(f"Loading snapshot: {path}")
    return pd.read_csv(path)


def format_diff_as_text(diff: SnapshotDiff) -> str:
    """Format snapshot diff as plain text.

    Args:
        diff: SnapshotDiff to format

    Returns:
        Formatted text string
    """
    lines = []
    lines.append("=" * 60)
    lines.append("EDINBURGH FRINGE DAILY UPDATE")
    lines.append(f"Comparing: {diff.old_snapshot_date} -> {diff.new_snapshot_date}")
    lines.append("=" * 60)
    lines.append("")

    if not diff.has_changes:
        lines.append("No changes detected since last snapshot.")
        return "\n".join(lines)

    lines.append(f"Total changes: {diff.total_changes}")
    lines.append("")

    # New Shows
    if diff.new_shows:
        lines.append("-" * 40)
        lines.append(f"NEW SHOWS ({len(diff.new_shows)})")
        lines.append("-" * 40)
        for show in diff.new_shows:
            lines.append(f"\n  {show.show_name}")
            lines.append(f"    Performer: {show.performer}")
            lines.append(f"    Performances: {show.performance_count}")
            if show.date_range:
                lines.append(f"    Dates: {show.date_range}")
            if show.venues:
                lines.append(f"    Venue: {', '.join(show.venues)}")
            lines.append(f"    URL: {show.show_url}")
        lines.append("")

    # Sold Out
    if diff.sold_out_performances:
        lines.append("-" * 40)
        lines.append(f"SOLD OUT ({len(diff.sold_out_performances)})")
        lines.append("-" * 40)
        # Group by show
        by_show: dict[str, list[PerformanceChange]] = {}
        for perf in diff.sold_out_performances:
            key = perf.show_name
            if key not in by_show:
                by_show[key] = []
            by_show[key].append(perf)

        for show_name, perfs in by_show.items():
            lines.append(f"\n  {show_name}")
            for perf in perfs[:5]:  # Limit to 5 per show
                lines.append(f"    - {perf.date} {perf.time}")
            if len(perfs) > 5:
                lines.append(f"    ... and {len(perfs) - 5} more")
        lines.append("")

    # Cancelled
    if diff.cancelled_performances:
        lines.append("-" * 40)
        lines.append(f"CANCELLED ({len(diff.cancelled_performances)})")
        lines.append("-" * 40)
        for perf in diff.cancelled_performances[:10]:
            lines.append(f"  {perf.show_name} - {perf.date} {perf.time}")
        if len(diff.cancelled_performances) > 10:
            lines.append(f"  ... and {len(diff.cancelled_performances) - 10} more")
        lines.append("")

    # Back Available
    if diff.back_available:
        lines.append("-" * 40)
        lines.append(f"BACK AVAILABLE ({len(diff.back_available)})")
        lines.append("-" * 40)
        for perf in diff.back_available[:10]:
            lines.append(f"  {perf.show_name} - {perf.date} {perf.time}")
        if len(diff.back_available) > 10:
            lines.append(f"  ... and {len(diff.back_available) - 10} more")
        lines.append("")

    # New Performances
    if diff.new_performances:
        lines.append("-" * 40)
        lines.append(f"NEW PERFORMANCES FOR EXISTING SHOWS ({len(diff.new_performances)})")
        lines.append("-" * 40)
        # Group by show
        by_show = {}
        for perf in diff.new_performances:
            key = perf.show_name
            if key not in by_show:
                by_show[key] = []
            by_show[key].append(perf)

        for show_name, perfs in list(by_show.items())[:10]:
            lines.append(f"\n  {show_name}")
            for perf in perfs[:3]:
                lines.append(f"    + {perf.date} {perf.time} @ {perf.venue}")
            if len(perfs) > 3:
                lines.append(f"    ... and {len(perfs) - 3} more performances")
        if len(by_show) > 10:
            lines.append(f"\n  ... and {len(by_show) - 10} more shows with new performances")
        lines.append("")

    # Removed Shows
    if diff.removed_shows:
        lines.append("-" * 40)
        lines.append(f"REMOVED SHOWS ({len(diff.removed_shows)})")
        lines.append("-" * 40)
        for show in diff.removed_shows[:10]:
            lines.append(f"  {show.show_name} ({show.performance_count} performances)")
        if len(diff.removed_shows) > 10:
            lines.append(f"  ... and {len(diff.removed_shows) - 10} more")
        lines.append("")

    return "\n".join(lines)


def format_diff_as_html(diff: SnapshotDiff) -> str:
    """Format snapshot diff as HTML for email.

    Args:
        diff: SnapshotDiff to format

    Returns:
        HTML string
    """
    html = []
    html.append("""
<!DOCTYPE html>
<html>
<head>
<style>
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; color: #333; }
h1 { color: #7B2D8E; border-bottom: 3px solid #7B2D8E; padding-bottom: 10px; }
h2 { color: #444; margin-top: 30px; border-bottom: 1px solid #ddd; padding-bottom: 5px; }
.summary { background: #f5f5f5; padding: 15px; border-radius: 8px; margin: 20px 0; }
.show { background: #fff; border: 1px solid #e0e0e0; border-radius: 8px; padding: 15px; margin: 10px 0; }
.show-title { font-weight: bold; color: #7B2D8E; font-size: 1.1em; }
.show-meta { color: #666; font-size: 0.9em; margin-top: 5px; }
.performance-list { margin: 10px 0; padding-left: 20px; }
.sold-out { color: #d32f2f; }
.new { color: #2e7d32; }
.cancelled { color: #f57c00; }
.back { color: #1976d2; }
a { color: #7B2D8E; }
.badge { display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: 0.8em; font-weight: bold; }
.badge-new { background: #e8f5e9; color: #2e7d32; }
.badge-soldout { background: #ffebee; color: #d32f2f; }
.badge-cancelled { background: #fff3e0; color: #f57c00; }
</style>
</head>
<body>
""")

    html.append(f"<h1>Edinburgh Fringe Daily Update</h1>")
    html.append(f"<p><em>Comparing: {diff.old_snapshot_date} &rarr; {diff.new_snapshot_date}</em></p>")

    if not diff.has_changes:
        html.append("<p>No changes detected since last snapshot.</p>")
        html.append("</body></html>")
        return "\n".join(html)

    # Summary
    html.append('<div class="summary">')
    html.append("<strong>Summary:</strong><br>")
    if diff.new_shows:
        html.append(f'<span class="new">{len(diff.new_shows)} new shows</span><br>')
    if diff.sold_out_performances:
        html.append(f'<span class="sold-out">{len(diff.sold_out_performances)} performances sold out</span><br>')
    if diff.cancelled_performances:
        html.append(f'<span class="cancelled">{len(diff.cancelled_performances)} performances cancelled</span><br>')
    if diff.back_available:
        html.append(f'<span class="back">{len(diff.back_available)} back available</span><br>')
    if diff.new_performances:
        html.append(f'{len(diff.new_performances)} new performances added<br>')
    html.append("</div>")

    # New Shows
    if diff.new_shows:
        html.append(f'<h2 class="new">New Shows ({len(diff.new_shows)})</h2>')
        for show in diff.new_shows:
            html.append('<div class="show">')
            html.append(f'<div class="show-title"><a href="{show.show_url}">{show.show_name}</a> <span class="badge badge-new">NEW</span></div>')
            html.append(f'<div class="show-meta">')
            html.append(f'Performer: {show.performer}<br>')
            html.append(f'{show.performance_count} performances')
            if show.date_range:
                html.append(f' | {show.date_range}')
            if show.venues:
                html.append(f'<br>Venue: {", ".join(show.venues)}')
            html.append('</div>')
            html.append('</div>')

    # Sold Out
    if diff.sold_out_performances:
        html.append(f'<h2 class="sold-out">Sold Out ({len(diff.sold_out_performances)})</h2>')
        by_show: dict[str, list[PerformanceChange]] = {}
        for perf in diff.sold_out_performances:
            if perf.show_name not in by_show:
                by_show[perf.show_name] = []
            by_show[perf.show_name].append(perf)

        for show_name, perfs in by_show.items():
            html.append('<div class="show">')
            html.append(f'<div class="show-title"><a href="{perfs[0].show_url}">{show_name}</a> <span class="badge badge-soldout">SOLD OUT</span></div>')
            html.append('<ul class="performance-list">')
            for perf in perfs[:5]:
                html.append(f'<li>{perf.date} {perf.time}</li>')
            if len(perfs) > 5:
                html.append(f'<li><em>... and {len(perfs) - 5} more</em></li>')
            html.append('</ul></div>')

    # Cancelled
    if diff.cancelled_performances:
        html.append(f'<h2 class="cancelled">Cancelled ({len(diff.cancelled_performances)})</h2>')
        for perf in diff.cancelled_performances[:10]:
            html.append(f'<div class="show"><a href="{perf.show_url}">{perf.show_name}</a> - {perf.date} {perf.time}</div>')
        if len(diff.cancelled_performances) > 10:
            html.append(f'<p><em>... and {len(diff.cancelled_performances) - 10} more</em></p>')

    # Back Available
    if diff.back_available:
        html.append(f'<h2 class="back">Back Available ({len(diff.back_available)})</h2>')
        for perf in diff.back_available[:10]:
            html.append(f'<div class="show"><a href="{perf.show_url}">{perf.show_name}</a> - {perf.date} {perf.time}</div>')
        if len(diff.back_available) > 10:
            html.append(f'<p><em>... and {len(diff.back_available) - 10} more</em></p>')

    # New Performances
    if diff.new_performances:
        html.append(f'<h2>New Performances ({len(diff.new_performances)})</h2>')
        by_show = {}
        for perf in diff.new_performances:
            if perf.show_name not in by_show:
                by_show[perf.show_name] = []
            by_show[perf.show_name].append(perf)

        for show_name, perfs in list(by_show.items())[:10]:
            html.append('<div class="show">')
            html.append(f'<div class="show-title"><a href="{perfs[0].show_url}">{show_name}</a></div>')
            html.append('<ul class="performance-list">')
            for perf in perfs[:3]:
                html.append(f'<li>{perf.date} {perf.time} @ {perf.venue}</li>')
            if len(perfs) > 3:
                html.append(f'<li><em>... and {len(perfs) - 3} more</em></li>')
            html.append('</ul></div>')
        if len(by_show) > 10:
            html.append(f'<p><em>... and {len(by_show) - 10} more shows</em></p>')

    html.append("</body></html>")
    return "\n".join(html)

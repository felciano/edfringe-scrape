"""Data conversion utilities for Edinburgh Fringe scraped data.

Ported from convert-2025.py - transforms raw CSV data into:
- Cleaned format with normalized dates and hyperlinks
- Summary format grouped by show
- Wide format with dates as columns
"""

import logging
from datetime import datetime
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)


class FringeConverter:
    """Converts raw scraped CSV data to various output formats."""

    def __init__(self, default_year: int = 2025):
        """Initialize converter.

        Args:
            default_year: Year to use when parsing dates without year
        """
        self.default_year = default_year

    def load_raw_csv(self, filepath: Path) -> pd.DataFrame:
        """Load raw CSV file.

        Args:
            filepath: Path to CSV file

        Returns:
            DataFrame with raw data
        """
        logger.info(f"Loading {filepath}")
        df = pd.read_csv(filepath)
        logger.info(f"Loaded {len(df)} rows")
        return df

    def clean_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Clean and normalize raw data.

        - Normalizes dates to YYYY-MM-DD format
        - Creates Excel hyperlinks for show links
        - Drops rows with invalid dates

        Args:
            df: Raw DataFrame

        Returns:
            Cleaned DataFrame
        """
        df = df.copy()

        df["date_normalized"] = df["date"].apply(self._parse_date)
        df = df.dropna(subset=["date_normalized"])

        if "show-link-href" in df.columns and "show-link" in df.columns:
            df["show"] = df.apply(
                lambda row: self._create_hyperlink(
                    row["show-link-href"], row["show-link"]
                ),
                axis=1,
            )

        output_cols = [
            "show",
            "show-name",
            "show-performer",
            "show-link-href",
            "date_normalized",
            "performance-time",
            "show-availability",
            "show-location",
        ]

        if "web-scraper-start-url" in df.columns:
            output_cols.append("web-scraper-start-url")

        existing_cols = [c for c in output_cols if c in df.columns]
        df_cleaned = df[existing_cols].copy()

        df_cleaned["date_normalized"] = pd.to_datetime(
            df_cleaned["date_normalized"], errors="coerce"
        )
        df_cleaned = df_cleaned.dropna(subset=["date_normalized"])

        logger.info(f"Cleaned data: {len(df_cleaned)} rows")
        return df_cleaned

    def create_summary(self, df_cleaned: pd.DataFrame) -> pd.DataFrame:
        """Create summary grouped by show.

        Args:
            df_cleaned: Cleaned DataFrame (from clean_data)

        Returns:
            Summary DataFrame with performance counts and date ranges
        """
        if "show-performer" in df_cleaned.columns:
            df_summary = (
                df_cleaned.groupby("show-name")
                .agg(
                    num_performances=("date_normalized", "count"),
                    first_date=("date_normalized", "min"),
                    last_date=("date_normalized", "max"),
                    performer=("show-performer", "first"),
                )
                .reset_index()
            )
        else:
            df_summary = (
                df_cleaned.groupby("show-name")
                .agg(
                    num_performances=("date_normalized", "count"),
                    first_date=("date_normalized", "min"),
                    last_date=("date_normalized", "max"),
                )
                .reset_index()
            )
            df_summary["performer"] = "N/A"

        logger.info(f"Created summary: {len(df_summary)} shows")
        return df_summary

    def create_wide_format(self, df_cleaned: pd.DataFrame) -> pd.DataFrame:
        """Create wide format with dates as columns.

        Each date becomes a column showing availability status.

        Args:
            df_cleaned: Cleaned DataFrame (from clean_data)

        Returns:
            Wide-format DataFrame
        """
        df = df_cleaned.copy()

        df["date"] = df["date_normalized"].dt.strftime("%Y-%m-%d")
        df["status"] = df.get("show-availability", "")

        index_cols = [
            "show-link-href",
            "show-name",
            "show-performer",
            "performance-time",
            "show-location",
        ]
        index_cols = [c for c in index_cols if c in df.columns]

        df_wide = df.pivot_table(
            index=index_cols,
            columns="date",
            values="status",
            aggfunc="first",
        ).reset_index()

        df_wide.columns.name = None
        df_wide.columns = [str(col) for col in df_wide.columns]

        logger.info(f"Created wide format: {len(df_wide)} rows")
        return df_wide

    def _parse_date(self, raw_date: str) -> str | None:
        """Parse date string like 'Wednesday 30 July' to 'YYYY-MM-DD'.

        Args:
            raw_date: Raw date string

        Returns:
            ISO format date string or None
        """
        if not isinstance(raw_date, str) or not raw_date.strip():
            return None

        try:
            parts = raw_date.split()
            if len(parts) < 3:
                return None

            day = int(parts[1])
            month = parts[2]
            full_date = datetime.strptime(
                f"{day} {month} {self.default_year}", "%d %B %Y"
            )
            return full_date.strftime("%Y-%m-%d")
        except (ValueError, IndexError):
            return None

    def _create_hyperlink(self, url: str, text: str) -> str:
        """Create Excel HYPERLINK formula.

        Args:
            url: Link URL
            text: Display text

        Returns:
            Excel HYPERLINK formula string
        """
        safe_text = str(text).replace('"', '""')
        return f'=HYPERLINK("{url}", "{safe_text}")'

    def to_festival_planner_format(
        self, df: pd.DataFrame, smart_parsing: bool = True
    ) -> pd.DataFrame:
        """Convert to Festival Planner standard format.

        Transforms scraped data to the format expected by Festival Planner:
        - performer, producer, show_name, venue_name, date, start_time, end_time, availability

        Args:
            df: Raw scraped DataFrame
            smart_parsing: If True, intelligently separate performer/producer/show_name

        Returns:
            DataFrame in Festival Planner format
        """
        df = df.copy()
        rows = []

        for _, row in df.iterrows():
            # Parse date
            date_iso = self._parse_date(row.get("date", ""))
            if not date_iso:
                continue

            # Parse time range
            time_str = row.get("performance-time", "")
            start_time, end_time = self._parse_time_range(time_str)

            # Map availability
            raw_availability = row.get("show-availability", "")
            availability = self._map_availability(raw_availability)

            # Parse performer/producer/show_name
            raw_performer = row.get("show-performer", "")
            raw_title = row.get("show-name", "")

            if smart_parsing:
                performer, producer, show_name = self._parse_performer_producer_show(
                    raw_performer, raw_title
                )
            else:
                performer = raw_performer
                producer = ""
                show_name = raw_title

            rows.append(
                {
                    "performer": performer,
                    "producer": producer,
                    "show_name": show_name,
                    "original_show_name": raw_title,
                    "venue_name": row.get("show-location", ""),
                    "date": date_iso,
                    "start_time": start_time,
                    "end_time": end_time,
                    "availability": availability,
                }
            )

        result = pd.DataFrame(rows)
        logger.info(f"Converted {len(result)} rows to Festival Planner format")
        return result

    def _parse_time_range(self, time_str: str) -> tuple[str, str]:
        """Parse time range like '19:30 - 20:30' into start and end times.

        Args:
            time_str: Time range string

        Returns:
            Tuple of (start_time, end_time) in HH:MM format
        """
        if not time_str or not isinstance(time_str, str):
            return "", ""

        # Handle various separators
        import re

        parts = re.split(r"\s*[-–]\s*", time_str.strip())

        start_time = parts[0].strip() if parts else ""
        end_time = parts[1].strip() if len(parts) > 1 else ""

        return start_time, end_time

    def _map_availability(self, raw: str) -> str:
        """Map scraper availability values to Festival Planner format.

        Args:
            raw: Raw availability string (e.g., TICKETS_AVAILABLE)

        Returns:
            Festival Planner format (e.g., tickets-available)
        """
        if not raw or not isinstance(raw, str):
            return "tickets-available"

        mapping = {
            "TICKETS_AVAILABLE": "tickets-available",
            "TWO_FOR_ONE": "2-for-1-show",
            "SOLD_OUT": "sold-out",
            "CANCELLED": "cancelled",
            "PREVIEW": "preview-show",
            "FREE_TICKETED": "free-show",
            "FREE": "free-show",
            "NO_ALLOCATION": "sold-out",
            "NO_ALLOCATION_REMAINING": "sold-out",
        }

        return mapping.get(raw.upper(), "tickets-available")

    def _is_production_company(self, name: str) -> bool:
        """Detect if a name is likely a production company rather than a performer.

        Args:
            name: The performer name to check

        Returns:
            True if the name appears to be a production company
        """
        if not name or not isinstance(name, str):
            return False

        name_lower = name.lower().strip()

        # Common production company patterns
        company_patterns = [
            " presents",
            " present",
            " productions",
            " comedy",
            " management",
            " entertainment",
            " ltd",
            " limited",
            " inc",
            " llc",
            " touring",
            " theatre",
            " theater",
            " arts",
            " promotions",
            " agency",
            " creative",
            " media",
            " group",
            " collective",
            " ensemble",
            " worldwide",
            " talent",
            " live",
            " agents",
            " nation",
            "free festival",
            "free fringe",
            "laughing horse",
            "pleasance",
            "gilded balloon",
            "underbelly",
            "assembly",
            "summerhall",
            "zoo",
            "just the tonic",
            "mick perrin",
            "united agents",
            "live nation",
            "seabright",
            "avalon",
            "off the kerb",
            "phil mcintyre",
            "berk's nest",
        ]

        # Check for common patterns
        for pattern in company_patterns:
            if pattern in name_lower:
                return True

        # Check for "X & Y" pattern with company keywords
        if " & " in name_lower or " and " in name_lower:
            # Could be a duo or a company - check for company keywords
            if any(
                kw in name_lower
                for kw in ["productions", "presents", "entertainment", "management"]
            ):
                return True

        # Check for "AEG", "PBJ", "WME" style abbreviations (all caps, 2-4 letters)
        name_parts = name.split()
        if len(name_parts) >= 1:
            first_part = name_parts[0]
            if (
                first_part.isupper()
                and 2 <= len(first_part) <= 4
                and first_part.isalpha()
            ):
                # Likely an agency abbreviation like "AEG Presents", "PBJ Management"
                if len(name_parts) > 1:
                    return True

        return False

    def _extract_performer_from_title(self, title: str) -> tuple[str, str]:
        """Extract performer name from title if it follows 'Performer: Show Title' pattern.

        Args:
            title: The show title

        Returns:
            Tuple of (performer_name, remaining_title). If no pattern found,
            returns ("", original_title)
        """
        if not title or not isinstance(title, str):
            return "", title or ""

        # Check for colon separator (common pattern: "Mark Watson: Before It Overtakes Us")
        if ":" in title:
            parts = title.split(":", 1)
            potential_performer = parts[0].strip()
            remaining_title = parts[1].strip() if len(parts) > 1 else ""

            # Validate that the part before colon looks like a performer name
            # (not a subtitle like "Comedy: A Journey" or "Part 1: The Beginning")
            if self._looks_like_performer_name(potential_performer):
                return potential_performer, remaining_title

        return "", title

    def _looks_like_performer_name(self, text: str) -> bool:
        """Check if text looks like a performer name rather than a subtitle.

        Args:
            text: Text to check

        Returns:
            True if it looks like a performer name
        """
        if not text:
            return False

        text_lower = text.lower()
        text_stripped = text.strip()

        # Reject common subtitle patterns
        subtitle_patterns = [
            "part ",
            "act ",
            "episode",
            "chapter",
            "volume",
            "vol ",
            "season",
            "series",
            "the ",
            "a ",
            "an ",
            "live",
            "work in progress",
            "wip",
            "preview",
            "encore",
            "returns",
            "reloaded",
        ]

        for pattern in subtitle_patterns:
            if text_lower.startswith(pattern) or text_lower == pattern.strip():
                return False

        # Reject all-caps abbreviations (likely show acronyms like "CSI", "NYC")
        if text_stripped.isupper() and len(text_stripped) <= 5:
            return False

        # Performer names typically:
        # - Are 1-4 words
        # - Start with capital letter
        # - Don't contain numbers (usually)
        words = text.split()
        if len(words) > 5:
            return False

        # Check for typical name patterns
        # Allow "Dr.", "Sir", "Dame", etc.
        if words and words[0][0].isupper():
            return True

        return False

    def _parse_performer_producer_show(
        self, raw_performer: str, title: str
    ) -> tuple[str, str, str]:
        """Intelligently parse performer, producer, and show name.

        Logic:
        1. If performer is a production company, it becomes producer
        2. If title has "Performer: Show Title" format, extract performer from title
        3. Otherwise, performer field is used directly
        4. If multiple performers are identified, combine them comma-delimited

        Args:
            raw_performer: The show-performer field from scraped data
            title: The show-name field from scraped data

        Returns:
            Tuple of (performer, producer, show_name)
        """
        performers: list[str] = []
        producer = ""
        show_name = title

        # First, check if raw_performer is a production company
        if self._is_production_company(raw_performer):
            producer = raw_performer

            # Try to extract performer from title
            extracted_performer, remaining_title = self._extract_performer_from_title(
                title
            )
            if extracted_performer:
                performers.append(extracted_performer)
                show_name = remaining_title
            # else: performers stays empty, show_name stays as original title
        else:
            # raw_performer is likely the actual performer
            if raw_performer:
                performers.append(raw_performer)

            # Still check if title has embedded performer (might be different)
            extracted_performer, remaining_title = self._extract_performer_from_title(
                title
            )
            if extracted_performer:
                # Check if extracted performer is different from raw_performer
                if not raw_performer:
                    performers.append(extracted_performer)
                    show_name = remaining_title
                elif extracted_performer.lower() in raw_performer.lower():
                    # Same performer, just use the cleaned title
                    show_name = remaining_title
                elif raw_performer.lower() in extracted_performer.lower():
                    # raw_performer is subset of extracted (e.g., "John" vs "John Smith")
                    # Use the more complete name
                    performers = [extracted_performer]
                    show_name = remaining_title
                else:
                    # Different performers - add both
                    performers.append(extracted_performer)
                    show_name = remaining_title

        # Combine performers as comma-delimited list
        performer = ", ".join(performers)

        # If no performer identified but we have a producer, it's likely a variety show
        if not performer and producer:
            performer = "Various"

        return performer, producer, show_name


def save_all_formats(
    df: pd.DataFrame,
    output_dir: Path,
    base_filename: str,
    formats: list[str] | None = None,
    default_year: int = 2025,
) -> dict[str, Path]:
    """Save data in multiple formats.

    Args:
        df: Raw DataFrame
        output_dir: Output directory
        base_filename: Base filename (without extension)
        formats: List of formats to save ("cleaned", "summary", "wide")
                 or None for all formats
        default_year: Year for date parsing

    Returns:
        Dictionary mapping format name to output path
    """
    if formats is None:
        formats = ["cleaned", "summary", "wide"]

    output_dir.mkdir(parents=True, exist_ok=True)

    converter = FringeConverter(default_year=default_year)
    results: dict[str, Path] = {}

    df_cleaned = None

    if "cleaned" in formats or "summary" in formats or "wide" in formats:
        df_cleaned = converter.clean_data(df)

    if "cleaned" in formats and df_cleaned is not None:
        path = output_dir / f"Cleaned-{base_filename}.csv"
        df_cleaned.to_csv(path, index=False)
        results["cleaned"] = path
        logger.info(f"Saved cleaned data to {path}")

    if "summary" in formats and df_cleaned is not None:
        df_summary = converter.create_summary(df_cleaned)
        path = output_dir / f"Summary-{base_filename}.csv"
        df_summary.to_csv(path, index=False)
        results["summary"] = path
        logger.info(f"Saved summary to {path}")

    if "wide" in formats and df_cleaned is not None:
        df_wide = converter.create_wide_format(df_cleaned)
        path = output_dir / f"WideFormat-{base_filename}.csv"
        df_wide.to_csv(path, index=False)
        results["wide"] = path
        logger.info(f"Saved wide format to {path}")

    return results

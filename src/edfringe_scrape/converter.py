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

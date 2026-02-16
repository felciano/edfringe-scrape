"""Core business logic for Edinburgh Fringe scraping."""

import logging
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

import pandas as pd

from .config import Settings
from .models import Genre, PerformanceDetail, ScrapedShow, ShowCard, ShowInfo, VenueInfo
from .parser import FringeParser
from .scraper import APIDiscovery, ScrapingDogClient, ScrapingDogError

logger = logging.getLogger(__name__)


def ensure_output_dir(settings: Settings) -> Path:
    """Ensure output directory exists.

    Args:
        settings: Application settings

    Returns:
        Path to output directory
    """
    output_path = Path(settings.output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    return output_path


class FringeScraper:
    """Orchestrates scraping of Edinburgh Fringe show listings."""

    def __init__(self, settings: Settings):
        """Initialize scraper.

        Args:
            settings: Application settings
        """
        self.settings = settings
        self.client = ScrapingDogClient(settings)
        self.parser = FringeParser(default_year=settings.default_year)
        self._build_id: str | None = None

    def scrape_genre(
        self,
        genre: Genre,
        max_shows: int | None = None,
        skip_details: bool = False,
        recently_added: str | None = None,
    ) -> Iterator[ScrapedShow]:
        """Scrape all shows for a genre.

        Args:
            genre: Genre to scrape
            max_shows: Maximum shows to scrape (None for all)
            skip_details: If True, skip fetching individual show details

        Yields:
            ScrapedShow objects
        """
        logger.info(f"Scraping genre: {genre.value}")

        page = 1
        show_count = 0
        seen_urls: set[str] = set()

        while True:
            if max_shows and show_count >= max_shows:
                logger.info(f"Reached max_shows limit ({max_shows})")
                break

            cards = self._fetch_search_page(genre, page, recently_added)

            if not cards:
                logger.info(f"No more results on page {page}")
                break

            new_cards = [c for c in cards if c.url not in seen_urls]
            if not new_cards:
                logger.info("No new shows found, stopping")
                break

            for card in new_cards:
                if max_shows and show_count >= max_shows:
                    break

                seen_urls.add(card.url)
                show_count += 1

                if skip_details:
                    yield ScrapedShow(
                        title=card.title,
                        url=card.url,
                        performer=card.performer,
                        duration=card.duration,
                        performances=[],
                        genre=genre,
                    )
                else:
                    yield self._fetch_show_details(card, genre)

            page += 1

        logger.info(f"Scraped {show_count} shows for {genre.value}")

    def _fetch_search_page(
        self,
        genre: Genre,
        page: int,
        recently_added: str | None = None,
    ) -> list[ShowCard]:
        """Fetch and parse a search results page.

        Args:
            genre: Genre to search
            page: Page number (1-indexed)

        Returns:
            List of ShowCard objects
        """
        url = (
            f"{self.settings.base_url}/tickets/whats-on"
            f"?search=true&genres={genre.url_param}"
        )

        if recently_added:
            url += f"&recentlyAdded={recently_added}"

        if page > 1:
            url += f"&page={page}"

        logger.info(f"Fetching search page {page} for {genre.value}")

        try:
            response = self.client.fetch_page(url, dynamic=True)

            if page == 1 and not self._build_id:
                self._build_id = APIDiscovery.discover_build_id(response.html)
                if self._build_id:
                    logger.debug(f"Discovered build ID: {self._build_id}")

            cards = self.parser.parse_search_results(response.html)
            logger.info(f"Found {len(cards)} shows on page {page}")
            return cards

        except ScrapingDogError as e:
            logger.error(f"Failed to fetch search page {page}: {e}")
            return []

    def _fetch_show_details(self, card: ShowCard, genre: Genre) -> ScrapedShow:
        """Fetch detailed performance info for a show.

        Args:
            card: ShowCard from search results
            genre: Genre of the show

        Returns:
            ScrapedShow with performances and show info
        """
        logger.debug(f"Fetching details for: {card.title}")

        performances: list[PerformanceDetail] = []
        show_info: ShowInfo | None = None
        venue_info: VenueInfo | None = None

        try:
            response = self.client.fetch_page(card.url, dynamic=True)
            result = self.parser.parse_show_detail(
                response.html, show_url=card.url, show_name=card.title
            )
            performances = result.performances
            show_info = result.show_info
            venue_info = result.venue_info
            logger.debug(f"Found {len(performances)} performances for {card.title}")
        except ScrapingDogError as e:
            logger.warning(f"Failed to fetch details for {card.title}: {e}")

        return ScrapedShow(
            title=card.title,
            url=card.url,
            performer=card.performer,
            duration=card.duration,
            performances=performances,
            genre=genre,
            show_info=show_info,
            venue_info=venue_info,
        )

    def fetch_venue_contacts(
        self,
        venues: dict[str, VenueInfo],
        known_codes: set[str],
    ) -> dict[str, VenueInfo]:
        """Fetch contact details for new venues from venue pages.

        Args:
            venues: Dict of all venues from current scrape
            known_codes: Set of venue codes already in cache

        Returns:
            Updated venues dict with contact info filled in
        """
        from .parser import NextDataParser

        for code, venue in venues.items():
            if code in known_codes:
                continue
            if not venue.venue_page_url:
                continue

            try:
                response = self.client.fetch_page(
                    venue.venue_page_url, dynamic=True
                )
                venue_page_data = NextDataParser.extract_venue_page_data(
                    response.html
                )
                if venue_page_data:
                    phone, email = NextDataParser.parse_venue_contact(
                        venue_page_data
                    )
                    venues[code] = venue.model_copy(
                        update={
                            "contact_phone": phone,
                            "contact_email": email,
                        }
                    )
                    logger.debug(
                        f"Fetched contacts for {venue.venue_name}: "
                        f"phone={phone}, email={email}"
                    )
            except ScrapingDogError as e:
                logger.warning(
                    f"Failed to fetch venue page for {venue.venue_name}: {e}"
                )

        return venues

    def fetch_all_search_results(
        self,
        genre: Genre,
        max_shows: int | None = None,
        recently_added: str | None = None,
    ) -> Iterator[ShowCard]:
        """Fetch all show cards from search results pages.

        Args:
            genre: Genre to search
            max_shows: Maximum shows to return (None for all)
            recently_added: Filter value (e.g. "LAST_SEVEN_DAYS")

        Yields:
            ShowCard objects
        """
        page = 1
        show_count = 0
        seen_urls: set[str] = set()

        while True:
            if max_shows and show_count >= max_shows:
                break

            cards = self._fetch_search_page(genre, page, recently_added)

            if not cards:
                break

            new_cards = [c for c in cards if c.url not in seen_urls]
            if not new_cards:
                break

            for card in new_cards:
                if max_shows and show_count >= max_shows:
                    break

                seen_urls.add(card.url)
                show_count += 1
                yield card

            page += 1

    def cards_to_shows(
        self,
        cards: list[ShowCard],
        genre: Genre,
    ) -> Iterator[ScrapedShow]:
        """Convert show cards to ScrapedShow objects without fetching details.

        Args:
            cards: List of ShowCard objects
            genre: Genre for the shows

        Yields:
            ScrapedShow objects (without performances)
        """
        for card in cards:
            yield ScrapedShow(
                title=card.title,
                url=card.url,
                performer=card.performer,
                duration=card.duration,
                performances=[],
                genre=genre,
            )

    def fetch_show_with_details(
        self,
        card: ShowCard,
        genre: Genre,
    ) -> ScrapedShow:
        """Fetch a single show with its performance details.

        Args:
            card: ShowCard from search results
            genre: Genre of the show

        Returns:
            ScrapedShow with performances
        """
        return self._fetch_show_details(card, genre)


def shows_to_dataframe(
    shows: list[ScrapedShow],
    source_url: str | None = None,
    scrape_time: datetime | None = None,
) -> pd.DataFrame:
    """Convert scraped shows to DataFrame matching existing CSV format.

    Args:
        shows: List of ScrapedShow objects
        source_url: Source URL to include in output
        scrape_time: Timestamp when scrape started (ISO format)

    Returns:
        DataFrame with columns matching Web Scraper.io output
    """
    rows = []

    scrape_time_str = scrape_time.isoformat() if scrape_time else ""

    for show in shows:
        if show.performances:
            for perf in show.performances:
                time_str = ""
                if perf.start_time:
                    time_str = perf.start_time.strftime("%H:%M")
                    if perf.end_time:
                        time_str += f" - {perf.end_time.strftime('%H:%M')}"

                date_str = _format_date_for_csv(perf.date)

                rows.append(
                    {
                        "web-scraper-scrape-time": scrape_time_str,
                        "show-link-href": show.url,
                        "show-link": show.title,
                        "show-name": show.title,
                        "show-performer": show.performer or "",
                        "date": date_str,
                        "performance-time": time_str,
                        "show-availability": perf.availability or "",
                        "show-location": perf.venue or "",
                        "web-scraper-start-url": source_url or "",
                    }
                )
        else:
            rows.append(
                {
                    "web-scraper-scrape-time": scrape_time_str,
                    "show-link-href": show.url,
                    "show-link": show.title,
                    "show-name": show.title,
                    "show-performer": show.performer or "",
                    "date": "",
                    "performance-time": "",
                    "show-availability": "",
                    "show-location": "",
                    "web-scraper-start-url": source_url or "",
                }
            )

    return pd.DataFrame(rows)


def _format_date_for_csv(date: datetime.date) -> str:
    """Format date for CSV output (e.g., 'Wednesday 30 July').

    Args:
        date: Date to format

    Returns:
        Formatted date string
    """
    return date.strftime("%A %d %B")


def save_raw_csv(
    df: pd.DataFrame,
    output_dir: Path,
    genre: str,
) -> Path:
    """Save raw scraped data to CSV.

    Args:
        df: DataFrame to save
        output_dir: Output directory
        genre: Genre name for filename

    Returns:
        Path to saved file
    """
    timestamp = datetime.now().strftime("%Y-%m-%d")
    filename = f"{timestamp}-EdFringe-{genre}.csv"
    output_path = output_dir / filename

    df.to_csv(output_path, index=False)
    logger.info(f"Saved {len(df)} rows to {output_path}")

    return output_path


def show_info_to_dataframe(shows: list[ScrapedShow]) -> pd.DataFrame:
    """Convert scraped shows to a show-info DataFrame (one row per show).

    Args:
        shows: List of ScrapedShow objects

    Returns:
        DataFrame with show info columns
    """
    rows = []
    for show in shows:
        if not show.show_info:
            continue
        info = show.show_info
        rows.append(
            {
                "show-link-href": info.show_url,
                "show-name": info.show_name,
                "genre": info.genre,
                "subgenres": info.subgenres,
                "description": info.description,
                "warnings": info.warnings,
                "age_suitability": info.age_suitability,
                "image_url": info.image_url,
                "website": info.website,
                "facebook": info.facebook,
                "instagram": info.instagram,
                "tiktok": info.tiktok,
                "youtube": info.youtube,
                "twitter": info.twitter,
                "bluesky": info.bluesky,
                "mastodon": info.mastodon,
            }
        )
    return pd.DataFrame(rows)


def save_show_info_csv(
    df: pd.DataFrame,
    output_dir: Path,
    genre: str,
) -> Path:
    """Save show info data to CSV.

    Args:
        df: DataFrame with show info
        output_dir: Output directory
        genre: Genre name for filename

    Returns:
        Path to saved file
    """
    timestamp = datetime.now().strftime("%Y-%m-%d")
    filename = f"{timestamp}-EdFringe-{genre}-show-info.csv"
    output_path = output_dir / filename

    df.to_csv(output_path, index=False)
    logger.info(f"Saved {len(df)} show info rows to {output_path}")

    return output_path


def save_snapshot_csv(
    df: pd.DataFrame,
    snapshot_dir: Path,
    date_str: str,
    mode: str,
    suffix: str = "snapshot",
) -> Path:
    """Save a DataFrame as a timestamped snapshot CSV.

    Args:
        df: DataFrame to save
        snapshot_dir: Directory for snapshot files
        date_str: Date string (e.g. "2026-02-15")
        mode: Scrape mode label ("full" or "recent")
        suffix: File suffix (e.g. "snapshot" or "show-info")

    Returns:
        Path to saved file
    """
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{date_str}-{mode}-{suffix}.csv"
    path = snapshot_dir / filename
    df.to_csv(path, index=False)
    logger.info(f"Saved {len(df)} rows to {path}")
    return path


def collect_venues(shows: list[ScrapedShow]) -> dict[str, VenueInfo]:
    """Collect unique venues from scraped shows, deduped by venue_code.

    Args:
        shows: List of scraped shows

    Returns:
        Dict mapping venue_code to VenueInfo
    """
    venues: dict[str, VenueInfo] = {}
    for show in shows:
        if show.venue_info and show.venue_info.venue_code:
            code = show.venue_info.venue_code
            if code not in venues:
                venues[code] = show.venue_info
    return venues


def load_venue_cache(cache_path: Path) -> dict[str, VenueInfo]:
    """Load venue cache from CSV file.

    Args:
        cache_path: Path to venue-info.csv

    Returns:
        Dict mapping venue_code to VenueInfo (empty if file doesn't exist)
    """
    if not cache_path.exists():
        return {}

    df = pd.read_csv(cache_path).fillna("")
    venues: dict[str, VenueInfo] = {}
    for _, row in df.iterrows():
        venue = VenueInfo(
            venue_code=str(row.get("venue_code", "")),
            venue_name=str(row.get("venue_name", "")),
            address=str(row.get("address", "")),
            postcode=str(row.get("postcode", "")),
            geolocation=str(row.get("geolocation", "")),
            google_maps_url=str(row.get("google_maps_url", "")),
            venue_page_url=str(row.get("venue_page_url", "")),
            description=str(row.get("description", "")),
            contact_phone=str(row.get("contact_phone", "")),
            contact_email=str(row.get("contact_email", "")),
        )
        if venue.venue_code:
            venues[venue.venue_code] = venue
    return venues


def save_venue_cache(
    venues: dict[str, VenueInfo], cache_path: Path
) -> Path:
    """Save venues to CSV cache file.

    Args:
        venues: Dict mapping venue_code to VenueInfo
        cache_path: Path to write venue-info.csv

    Returns:
        Path to saved file
    """
    rows = [v.model_dump() for v in venues.values()]
    df = pd.DataFrame(rows)
    if df.empty:
        df = pd.DataFrame(
            columns=[
                "venue_code", "venue_name", "address", "postcode",
                "geolocation", "google_maps_url", "venue_page_url",
                "description", "contact_phone", "contact_email",
            ]
        )
    df.to_csv(cache_path, index=False)
    logger.info(f"Saved {len(df)} venues to {cache_path}")
    return cache_path


# Column schemas for canonical CSV files
PERFORMANCE_COLUMNS = [
    "web-scraper-scrape-time",
    "show-link-href",
    "show-link",
    "show-name",
    "show-performer",
    "date",
    "performance-time",
    "show-availability",
    "show-location",
    "web-scraper-start-url",
    "genre",
]

SHOW_INFO_COLUMNS = [
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


def load_canonical(path: Path, expected_columns: list[str]) -> pd.DataFrame:
    """Load a canonical CSV file, or return an empty DataFrame with expected schema.

    Args:
        path: Path to CSV file
        expected_columns: Column names for the empty DataFrame fallback

    Returns:
        DataFrame with data or empty DataFrame with correct columns
    """
    if path.exists():
        df = pd.read_csv(path)
        # Ensure all expected columns exist (fill missing with empty string)
        for col in expected_columns:
            if col not in df.columns:
                df[col] = ""
        return df
    return pd.DataFrame(columns=expected_columns)


def save_canonical(df: pd.DataFrame, path: Path) -> Path:
    """Save a DataFrame to a canonical CSV file, creating parent dirs.

    Args:
        df: DataFrame to save
        path: Output file path

    Returns:
        Path to saved file
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    logger.info(f"Saved {len(df)} rows to {path}")
    return path


def merge_performances(
    existing_df: pd.DataFrame,
    new_df: pd.DataFrame,
    full_mode: bool = False,
) -> pd.DataFrame:
    """Merge new performance data into existing canonical data.

    Key: show-link-href + date + performance-time

    Args:
        existing_df: Existing canonical performances
        new_df: Newly scraped performances
        full_mode: If True, replace all data for scraped genres;
                   if False, upsert by key (preserving non-matching rows)

    Returns:
        Merged DataFrame sorted by genre, show URL, date, time
    """
    if new_df.empty:
        return existing_df.copy()

    def _perf_key(df: pd.DataFrame) -> pd.Series:
        return (
            df["show-link-href"].fillna("").astype(str)
            + "|"
            + df["date"].fillna("").astype(str)
            + "|"
            + df["performance-time"].fillna("").astype(str)
        )

    if full_mode:
        # Drop all existing rows for genres present in new_df
        scraped_genres = set(new_df["genre"].dropna().unique())
        keep_mask = ~existing_df["genre"].isin(scraped_genres)
        preserved = existing_df[keep_mask]
        merged = pd.concat([preserved, new_df], ignore_index=True)
    else:
        # Upsert: new rows overwrite matching keys, non-matching preserved
        if existing_df.empty:
            merged = new_df.copy()
        else:
            new_keys = set(_perf_key(new_df))
            existing_keys = _perf_key(existing_df)
            keep_mask = ~existing_keys.isin(new_keys)
            preserved = existing_df[keep_mask]
            merged = pd.concat([preserved, new_df], ignore_index=True)

    # Sort for stable output
    sort_cols = [
        c for c in ["genre", "show-link-href", "date", "performance-time"]
        if c in merged.columns
    ]
    if sort_cols:
        merged = merged.sort_values(sort_cols, na_position="last")
        merged = merged.reset_index(drop=True)

    return merged


def merge_show_info(
    existing_df: pd.DataFrame,
    new_df: pd.DataFrame,
) -> pd.DataFrame:
    """Merge new show info into existing canonical show info.

    Key: show-link-href (always additive/upsert, never removes).

    Args:
        existing_df: Existing canonical show info
        new_df: Newly scraped show info

    Returns:
        Merged DataFrame
    """
    if new_df.empty:
        return existing_df.copy()

    if existing_df.empty:
        return new_df.copy()

    new_urls = set(new_df["show-link-href"].dropna().unique())
    keep_mask = ~existing_df["show-link-href"].isin(new_urls)
    preserved = existing_df[keep_mask]
    merged = pd.concat([preserved, new_df], ignore_index=True)

    if "show-link-href" in merged.columns:
        merged = merged.sort_values("show-link-href", na_position="last")
        merged = merged.reset_index(drop=True)

    return merged

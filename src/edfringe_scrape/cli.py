"""Command-line interface using Click."""

import logging
from datetime import datetime
from pathlib import Path

import click
import pandas as pd

from .config import Settings, get_settings
from .converter import FringeConverter, save_all_formats
from .core import (
    PERFORMANCE_COLUMNS,
    SHOW_INFO_COLUMNS,
    FringeScraper,
    collect_venues,
    load_canonical,
    load_venue_cache,
    merge_performances,
    merge_show_info,
    save_canonical,
    save_snapshot_csv,
    save_venue_cache,
    show_info_to_dataframe,
    shows_to_dataframe,
)
from .email_sender import send_email
from .models import Genre, ScrapedShow
from .scraper import ScrapingDogError
from .snapshot import (
    SnapshotDiff,
    compare_snapshots,
    find_latest_snapshot,
    format_diff_as_html,
    format_diff_as_text,
    load_snapshot,
)


def setup_logging(verbose: int) -> None:
    """Configure logging based on verbosity."""
    level = logging.WARNING
    if verbose == 1:
        level = logging.INFO
    elif verbose >= 2:
        level = logging.DEBUG

    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


def _scrape_all_genres(
    scraper: FringeScraper,
    genre_list: list[str],
    settings: Settings,
    scrape_start_time: datetime,
    max_shows: int | None,
    recently_added: str | None,
) -> tuple[list[pd.DataFrame], list[pd.DataFrame], list[ScrapedShow]]:
    """Scrape all genres, returning performance DFs, info DFs, and shows."""
    all_perf_dfs: list[pd.DataFrame] = []
    all_info_dfs: list[pd.DataFrame] = []
    all_shows: list[ScrapedShow] = []

    for genre_str in genre_list:
        genre_enum = Genre(genre_str)
        click.echo(f"Scraping {genre_enum.value}...")

        try:
            show_cards = list(
                scraper.fetch_all_search_results(
                    genre_enum, max_shows, recently_added=recently_added
                )
            )
            click.echo(f"  Found {len(show_cards)} shows")

            if show_cards:
                click.echo("  Fetching details...")
                shows: list[ScrapedShow] = []
                with click.progressbar(
                    show_cards,
                    label="  Processing",
                    show_pos=True,
                    item_show_func=lambda c: c.title[:30] if c else "",
                ) as cards:
                    for card in cards:
                        show = scraper.fetch_show_with_details(
                            card, genre_enum
                        )
                        shows.append(show)

                all_shows.extend(shows)

                source_url = (
                    f"{settings.base_url}/tickets/whats-on"
                    f"?search=true&genres={genre_str}"
                )
                perf_df = shows_to_dataframe(
                    shows,
                    source_url=source_url,
                    scrape_time=scrape_start_time,
                )
                perf_df["genre"] = genre_str
                all_perf_dfs.append(perf_df)

                info_df = show_info_to_dataframe(shows)
                if not info_df.empty:
                    all_info_dfs.append(info_df)

                perf_count = sum(len(s.performances) for s in shows)
                click.echo(
                    f"  {len(shows)} shows, {perf_count} performances"
                )

        except ScrapingDogError as e:
            click.echo(
                f"  Error scraping {genre_enum.value}: {e}", err=True
            )

        click.echo("")

    return all_perf_dfs, all_info_dfs, all_shows


def _save_snapshot(
    perf_dfs: list[pd.DataFrame],
    info_dfs: list[pd.DataFrame],
    snapshot_dir: Path,
    date_str: str,
    mode_label: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Concatenate and save timestamped snapshot files. Returns combined DFs."""
    combined_perf = pd.concat(perf_dfs, ignore_index=True)
    perf_path = save_snapshot_csv(
        combined_perf, snapshot_dir, date_str, mode_label, "snapshot"
    )
    click.echo(f"Saved snapshot: {perf_path}")
    click.echo(f"  Total: {len(combined_perf)} performances")

    combined_info = (
        pd.concat(info_dfs, ignore_index=True)
        if info_dfs
        else pd.DataFrame(columns=SHOW_INFO_COLUMNS)
    )
    if not combined_info.empty:
        info_path = save_snapshot_csv(
            combined_info, snapshot_dir, date_str, mode_label, "show-info"
        )
        click.echo(f"Saved show info: {info_path} ({len(combined_info)} shows)")

    return combined_perf, combined_info


def _update_venue_cache(
    scraper: FringeScraper,
    all_shows: list[ScrapedShow],
    cache_dir: Path,
) -> None:
    """Fetch new venue details and update the venue cache."""
    venue_cache_path = cache_dir / "venue-info.csv"
    scraped_venues = collect_venues(all_shows)
    cached_venues = load_venue_cache(venue_cache_path)
    cached_codes = set(cached_venues.keys())
    new_codes = set(scraped_venues.keys()) - cached_codes

    if new_codes:
        click.echo(
            f"\nFetching venue details for {len(new_codes)} new venues..."
        )
        new_venues = {
            c: v for c, v in scraped_venues.items() if c in new_codes
        }
        with click.progressbar(
            list(new_venues.keys()),
            label="  Venues",
            show_pos=True,
            item_show_func=lambda c: (
                new_venues[c].venue_name[:30] if c and c in new_venues else ""
            ),
        ) as codes:
            for code in codes:
                venue = new_venues[code]
                if venue.venue_page_url:
                    try:
                        response = scraper.client.fetch_page(
                            venue.venue_page_url, dynamic=True
                        )
                        from .parser import NextDataParser

                        venue_page_data = (
                            NextDataParser.extract_venue_page_data(
                                response.html
                            )
                        )
                        if venue_page_data:
                            phone, email_addr = (
                                NextDataParser.parse_venue_contact(
                                    venue_page_data
                                )
                            )
                            new_venues[code] = venue.model_copy(
                                update={
                                    "contact_phone": phone,
                                    "contact_email": email_addr,
                                }
                            )
                    except Exception:
                        pass

        cached_venues.update(new_venues)
    else:
        for code, venue in scraped_venues.items():
            if code not in cached_venues:
                cached_venues[code] = venue

    save_venue_cache(cached_venues, venue_cache_path)
    click.echo(
        f"Venues: {len(cached_venues)} total ({len(new_codes)} new)"
    )


def _compare_with_previous(
    snapshot_dir: Path,
    date_str: str,
    current_df: pd.DataFrame,
) -> SnapshotDiff | None:
    """Find previous snapshot, compare, and print report."""
    prev_snapshot = find_latest_snapshot(snapshot_dir, exclude_date=date_str)
    if prev_snapshot:
        click.echo(f"Comparing with: {prev_snapshot.name}")
        prev_df = load_snapshot(prev_snapshot)
        diff = compare_snapshots(prev_df, current_df)
        text_report = format_diff_as_text(diff)
        click.echo("")
        click.echo(text_report)
        return diff
    click.echo("No previous snapshot found for comparison.")
    return None


def _send_update_email(
    settings: Settings,
    diff: SnapshotDiff,
    date_str: str,
) -> None:
    """Send email with comparison report."""
    if not settings.email_to:
        click.echo(
            "Email recipient not configured (EDFRINGE_EMAIL_TO)", err=True
        )
        return
    if not settings.smtp_user or not settings.smtp_password:
        click.echo("SMTP credentials not configured", err=True)
        return

    click.echo(f"\nSending email to {settings.email_to}...")
    subject = f"Edinburgh Fringe Update - {date_str}"
    if diff.has_changes:
        subject += f" ({diff.total_changes} changes)"
    else:
        subject += " (No changes)"

    text_body = format_diff_as_text(diff)
    html_body = format_diff_as_html(diff)

    success = send_email(
        to_email=settings.email_to,
        subject=subject,
        text_body=text_body,
        html_body=html_body,
        from_email=settings.email_from,
        smtp_host=settings.smtp_host,
        smtp_port=settings.smtp_port,
        smtp_user=settings.smtp_user,
        smtp_password=settings.smtp_password,
    )

    if success:
        click.echo("Email sent successfully!")
    else:
        click.echo("Failed to send email.", err=True)


@click.group()
@click.option("-v", "--verbose", count=True, help="Increase verbosity (-v, -vv)")
@click.pass_context
def cli(ctx: click.Context, verbose: int) -> None:
    """Scrapes show, performer and performance listings from the Edinburgh Fringe website."""
    ctx.ensure_object(dict)
    ctx.obj["settings"] = get_settings()
    ctx.obj["verbose"] = verbose
    setup_logging(verbose)


@cli.command()
@click.pass_context
def info(ctx: click.Context) -> None:
    """Show configuration information."""
    settings = ctx.obj["settings"]
    click.echo(f"Debug mode: {settings.debug}")
    click.echo(f"Log level: {settings.log_level}")
    click.echo(f"Base URL: {settings.base_url}")
    click.echo(f"Output dir: {settings.output_dir}")
    click.echo(f"Request delay: {settings.request_delay_ms}ms")
    click.echo(f"JS wait time: {settings.js_wait_ms}ms")
    click.echo(f"Default year: {settings.default_year}")

    if settings.scrapingdog_api_key:
        key_preview = settings.scrapingdog_api_key[:8] + "..."
        click.echo(f"Scraping Dog API key: {key_preview} (configured)")
    else:
        click.echo("Scraping Dog API key: NOT CONFIGURED")
        click.echo("  Set EDFRINGE_SCRAPINGDOG_API_KEY or configure in .envrc")


@cli.command()
@click.option(
    "-g",
    "--genres",
    type=str,
    default="COMEDY",
    help="Comma-separated list of genres to scrape (default: COMEDY)",
)
@click.option(
    "--full/--recent",
    default=False,
    help="Full scrape (replace genre data) or recent only (default: recent)",
)
@click.option(
    "--max-shows",
    type=int,
    default=None,
    help="Maximum shows per genre (default: all)",
)
@click.option(
    "--compare/--no-compare",
    default=True,
    help="Compare with previous snapshot (default: yes)",
)
@click.option(
    "--email/--no-email",
    default=False,
    help="Send email with changes (default: no)",
)
@click.option(
    "-o",
    "--output",
    type=click.Path(path_type=Path),
    default=None,
    help="Override base output directory",
)
@click.pass_context
def update(
    ctx: click.Context,
    genres: str,
    full: bool,
    max_shows: int | None,
    compare: bool,
    email: bool,
    output: Path | None,
) -> None:
    """Update Fringe data: scrape, snapshot, merge canonical, compare.

    Scrapes specified genres, saves a timestamped snapshot, merges into
    canonical current-state files, and optionally compares with the
    previous snapshot and emails a report.

    Examples:

        edfringe-scrape update -g COMEDY,MUSICALS

        edfringe-scrape update -g COMEDY --full

        edfringe-scrape update -g COMEDY --max-shows 5 --no-compare

        edfringe-scrape update --email
    """
    settings = ctx.obj["settings"]

    if not settings.scrapingdog_api_key:
        raise click.ClickException(
            "Scraping Dog API key not configured. "
            "Set EDFRINGE_SCRAPINGDOG_API_KEY or run 'edfringe-scrape info' "
            "for help."
        )

    genre_list = [g.strip().upper() for g in genres.split(",")]
    valid_genres = [g.value for g in Genre]
    for g in genre_list:
        if g not in valid_genres:
            raise click.ClickException(
                f"Invalid genre: {g}. Valid genres: {', '.join(valid_genres)}"
            )

    snapshot_dir = (output / "snapshots") if output else Path(settings.snapshot_dir)
    current_dir = (output / "current") if output else Path(settings.current_dir)

    mode_label = "full" if full else "recent"
    recently_added = None if full else "LAST_SEVEN_DAYS"
    scrape_start_time = datetime.now()
    date_str = scrape_start_time.strftime("%Y-%m-%d")

    click.echo("Edinburgh Fringe Update")
    click.echo(f"  Mode: {mode_label}")
    click.echo(f"  Genres: {', '.join(genre_list)}")
    if max_shows:
        click.echo(f"  Max shows per genre: {max_shows}")
    click.echo("")

    scraper = FringeScraper(settings)

    # 1. Scrape all genres
    all_perf_dfs, all_info_dfs, all_shows = _scrape_all_genres(
        scraper, genre_list, settings, scrape_start_time,
        max_shows, recently_added,
    )
    if not all_perf_dfs:
        click.echo("No data scraped!")
        return

    # 2. Save timestamped snapshot
    new_perf_df, new_info_df = _save_snapshot(
        all_perf_dfs, all_info_dfs, snapshot_dir, date_str, mode_label,
    )

    # 3. Merge into canonical files
    current_dir.mkdir(parents=True, exist_ok=True)
    perf_path = current_dir / "performances.csv"
    info_path = current_dir / "show-info.csv"

    existing_perf = load_canonical(perf_path, PERFORMANCE_COLUMNS)
    existing_info = load_canonical(info_path, SHOW_INFO_COLUMNS)

    merged_perf = merge_performances(existing_perf, new_perf_df, full_mode=full)
    merged_info = merge_show_info(existing_info, new_info_df)

    save_canonical(merged_perf, perf_path)
    save_canonical(merged_info, info_path)

    click.echo(
        f"Performances: {len(merged_perf)} total "
        f"({len(new_perf_df)} new/updated)"
    )
    click.echo(
        f"Shows: {len(merged_info)} total ({len(new_info_df)} new/updated)"
    )

    # 4. Update venue cache
    _update_venue_cache(scraper, all_shows, current_dir)

    click.echo("")

    # 5. Compare with previous snapshot
    diff = None
    if compare:
        diff = _compare_with_previous(snapshot_dir, date_str, new_perf_df)

    # 6. Email report
    if email and diff:
        _send_update_email(settings, diff, date_str)


@cli.command()
@click.argument("input_file", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--formats",
    type=click.Choice(["all", "cleaned", "summary", "wide"]),
    default="all",
    help="Output formats to generate (default: all)",
)
@click.option(
    "-o",
    "--output",
    type=click.Path(path_type=Path),
    default=None,
    help="Output directory (default: same as input file)",
)
@click.option(
    "--year",
    type=int,
    default=None,
    help="Year for date parsing (default: from settings)",
)
@click.pass_context
def convert(
    ctx: click.Context,
    input_file: Path,
    formats: str,
    output: Path | None,
    year: int | None,
) -> None:
    """Convert raw scraped CSV to cleaned/summary/wide formats.

    Examples:

        edfringe-scrape convert data/input/2025-Comedy.csv

        edfringe-scrape convert data/raw.csv --formats summary -o data/output
    """
    settings = ctx.obj["settings"]
    default_year = year if year else settings.default_year

    output_dir = output if output else input_file.parent
    output_dir.mkdir(parents=True, exist_ok=True)

    format_list = ["cleaned", "summary", "wide"] if formats == "all" else [formats]

    click.echo(f"Converting {input_file}")
    click.echo(f"  Formats: {', '.join(format_list)}")
    click.echo(f"  Year: {default_year}")

    converter = FringeConverter(default_year=default_year)
    df = converter.load_raw_csv(input_file)

    click.echo(f"  Loaded {len(df)} rows")

    base_filename = input_file.stem

    results = save_all_formats(
        df,
        output_dir,
        base_filename,
        formats=format_list,
        default_year=default_year,
    )

    click.echo("\nOutput files:")
    for fmt, path in results.items():
        click.echo(f"  {fmt}: {path}")


@cli.command()
@click.argument("input_file", type=click.Path(exists=True, path_type=Path))
@click.option(
    "-o",
    "--output",
    type=click.Path(path_type=Path),
    default=None,
    help="Output file path (default: input_file with -festival-planner suffix)",
)
@click.option(
    "--year",
    type=int,
    default=None,
    help="Year for date parsing (default: from settings)",
)
@click.option(
    "--no-smart-parsing",
    is_flag=True,
    default=False,
    help="Disable intelligent performer/producer/show parsing",
)
@click.pass_context
def export(
    ctx: click.Context,
    input_file: Path,
    output: Path | None,
    year: int | None,
    no_smart_parsing: bool,
) -> None:
    """Export scraped data to Festival Planner format.

    Converts raw scraped CSV to the standard format expected by Festival Planner,
    with columns: performer, producer, show_name, venue_name, date, start_time,
    end_time, availability

    Smart parsing (enabled by default) intelligently separates:
    - Production companies into the 'producer' field
    - Performer names from titles like "Mark Watson: Show Title"

    Examples:

        edfringe-scrape export data/raw/2026-02-11-EdFringe-COMEDY.csv

        edfringe-scrape export data/raw/shows.csv -o data/festival-planner/comedy.csv

        edfringe-scrape export data/raw/shows.csv --no-smart-parsing
    """
    settings = ctx.obj["settings"]
    default_year = year if year else settings.default_year
    smart_parsing = not no_smart_parsing

    if output is None:
        output = input_file.with_name(
            input_file.stem + "-festival-planner" + input_file.suffix
        )

    output.parent.mkdir(parents=True, exist_ok=True)

    click.echo("Exporting to Festival Planner format")
    click.echo(f"  Input: {input_file}")
    click.echo(f"  Output: {output}")
    click.echo(f"  Year: {default_year}")
    click.echo(f"  Smart parsing: {'enabled' if smart_parsing else 'disabled'}")

    converter = FringeConverter(default_year=default_year)
    df = converter.load_raw_csv(input_file)

    click.echo(f"  Loaded {len(df)} rows")

    df_export = converter.to_festival_planner_format(df, smart_parsing=smart_parsing)

    df_export.to_csv(output, index=False)

    click.echo(f"\nExported {len(df_export)} performances to {output}")


@cli.command()
@click.argument("old_snapshot", type=click.Path(exists=True, path_type=Path))
@click.argument("new_snapshot", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "html"]),
    default="text",
    help="Output format (default: text)",
)
@click.option(
    "-o",
    "--output",
    type=click.Path(path_type=Path),
    default=None,
    help="Output file (default: stdout)",
)
@click.pass_context
def compare(
    ctx: click.Context,
    old_snapshot: Path,
    new_snapshot: Path,
    output_format: str,
    output: Path | None,
) -> None:
    """Compare two snapshots and show differences.

    Examples:

        edfringe-scrape compare data/snapshots/2026-02-10.csv data/snapshots/2026-02-11.csv

        edfringe-scrape compare old.csv new.csv --format html -o report.html
    """
    click.echo(f"Loading {old_snapshot.name}...")
    old_df = load_snapshot(old_snapshot)

    click.echo(f"Loading {new_snapshot.name}...")
    new_df = load_snapshot(new_snapshot)

    click.echo("Comparing snapshots...")
    diff = compare_snapshots(old_df, new_df)

    if output_format == "html":
        report = format_diff_as_html(diff)
    else:
        report = format_diff_as_text(diff)

    if output:
        output.write_text(report)
        click.echo(f"Report saved to: {output}")
    else:
        click.echo("")
        click.echo(report)


if __name__ == "__main__":
    cli()

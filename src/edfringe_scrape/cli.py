"""Command-line interface using Click."""

import logging
from datetime import datetime
from pathlib import Path

import click
import pandas as pd

from .config import get_settings
from .converter import FringeConverter, save_all_formats
from .core import FringeScraper, ensure_output_dir, save_raw_csv, shows_to_dataframe
from .email_sender import send_email
from .models import Genre
from .scraper import ScrapingDogError
from .snapshot import (
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
    "--genre",
    type=click.Choice([g.value for g in Genre], case_sensitive=False),
    required=True,
    help="Genre to scrape",
)
@click.option(
    "--max-shows",
    type=int,
    default=None,
    help="Maximum number of shows to scrape (default: all)",
)
@click.option(
    "--skip-details",
    is_flag=True,
    default=False,
    help="Skip fetching individual show details (saves API credits)",
)
@click.option(
    "-o",
    "--output",
    type=click.Path(path_type=Path),
    default=None,
    help="Output directory (default: from settings)",
)
@click.pass_context
def scrape(
    ctx: click.Context,
    genre: str,
    max_shows: int | None,
    skip_details: bool,
    output: Path | None,
) -> None:
    """Scrape show listings from Edinburgh Fringe website.

    Examples:

        edfringe-scrape scrape -g COMEDY --max-shows 5

        edfringe-scrape scrape -g MUSICALS --skip-details
    """
    settings = ctx.obj["settings"]

    if not settings.scrapingdog_api_key:
        raise click.ClickException(
            "Scraping Dog API key not configured. "
            "Set EDFRINGE_SCRAPINGDOG_API_KEY or run 'edfringe-scrape info' for help."
        )

    genre_enum = Genre(genre.upper())

    output_dir = output if output else Path(settings.output_dir)
    ensure_output_dir(settings)

    scrape_start_time = datetime.now()

    click.echo(f"Scraping {genre_enum.value} shows...")
    click.echo(f"  Started: {scrape_start_time.isoformat()}")
    if max_shows:
        click.echo(f"  Max shows: {max_shows}")
    if skip_details:
        click.echo("  Skipping detail pages (search results only)")

    try:
        scraper = FringeScraper(settings)

        # First pass: collect show cards from search results
        click.echo("\nFetching search results...")
        show_cards = list(scraper.fetch_all_search_results(genre_enum, max_shows))
        click.echo(f"  Found {len(show_cards)} shows")

        if not show_cards:
            click.echo("No shows found!")
            return

        # Second pass: fetch details with progress bar
        shows = []
        if skip_details:
            click.echo("\nSkipping detail pages...")
            shows = list(scraper.cards_to_shows(show_cards, genre_enum))
        else:
            click.echo("\nFetching show details...")
            with click.progressbar(
                show_cards,
                label="  Processing",
                show_pos=True,
                item_show_func=lambda c: c.title[:40] if c else "",
            ) as cards:
                for card in cards:
                    show = scraper.fetch_show_with_details(card, genre_enum)
                    shows.append(show)

        click.echo(f"\nScraped {len(shows)} shows")

        if not shows:
            click.echo("No shows found!")
            return

        source_url = f"{settings.base_url}/tickets/whats-on?search=true&genres={genre}"
        df = shows_to_dataframe(
            shows, source_url=source_url, scrape_time=scrape_start_time
        )

        output_path = save_raw_csv(df, output_dir, genre_enum.value)
        click.echo(f"Saved to: {output_path}")

        perf_count = sum(len(s.performances) for s in shows)
        click.echo(f"Total performances: {perf_count}")

    except ScrapingDogError as e:
        raise click.ClickException(f"Scraping error: {e}") from e


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
@click.option(
    "-g",
    "--genres",
    type=str,
    default="COMEDY",
    help="Comma-separated list of genres to scrape (default: COMEDY)",
)
@click.option(
    "--max-shows",
    type=int,
    default=None,
    help="Maximum shows per genre (default: all)",
)
@click.option(
    "-o",
    "--output",
    type=click.Path(path_type=Path),
    default=None,
    help="Output directory for snapshots (default: from settings)",
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
@click.pass_context
def daily_snapshot(
    ctx: click.Context,
    genres: str,
    max_shows: int | None,
    output: Path | None,
    compare: bool,
    email: bool,
) -> None:
    """Take a daily snapshot of the Fringe schedule and report changes.

    Scrapes specified genres, saves a timestamped snapshot, compares with
    the previous snapshot, and optionally emails the changes.

    Examples:

        edfringe-scrape daily-snapshot

        edfringe-scrape daily-snapshot -g COMEDY,MUSICALS,THEATRE

        edfringe-scrape daily-snapshot --email

        edfringe-scrape daily-snapshot --max-shows 10 --no-compare
    """
    settings = ctx.obj["settings"]

    if not settings.scrapingdog_api_key:
        raise click.ClickException(
            "Scraping Dog API key not configured. "
            "Set EDFRINGE_SCRAPINGDOG_API_KEY or run 'edfringe-scrape info' for help."
        )

    # Parse genres
    genre_list = [g.strip().upper() for g in genres.split(",")]
    valid_genres = [g.value for g in Genre]
    for g in genre_list:
        if g not in valid_genres:
            raise click.ClickException(
                f"Invalid genre: {g}. Valid genres: {', '.join(valid_genres)}"
            )

    # Setup output directory
    snapshot_dir = output if output else Path(settings.snapshot_dir)
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    scrape_start_time = datetime.now()
    date_str = scrape_start_time.strftime("%Y-%m-%d")

    click.echo("Edinburgh Fringe Daily Snapshot")
    click.echo(f"  Date: {date_str}")
    click.echo(f"  Genres: {', '.join(genre_list)}")
    click.echo(f"  Output: {snapshot_dir}")
    click.echo("")

    # Scrape all genres
    all_dfs = []
    scraper = FringeScraper(settings)

    for genre_str in genre_list:
        genre_enum = Genre(genre_str)
        click.echo(f"Scraping {genre_enum.value}...")

        try:
            show_cards = list(
                scraper.fetch_all_search_results(genre_enum, max_shows)
            )
            click.echo(f"  Found {len(show_cards)} shows")

            if show_cards:
                click.echo("  Fetching details...")
                shows = []
                with click.progressbar(
                    show_cards,
                    label="  Processing",
                    show_pos=True,
                    item_show_func=lambda c: c.title[:30] if c else "",
                ) as cards:
                    for card in cards:
                        show = scraper.fetch_show_with_details(card, genre_enum)
                        shows.append(show)

                source_url = (
                    f"{settings.base_url}/tickets/whats-on?search=true&genres={genre_str}"
                )
                df = shows_to_dataframe(
                    shows, source_url=source_url, scrape_time=scrape_start_time
                )
                df["genre"] = genre_str
                all_dfs.append(df)

                perf_count = sum(len(s.performances) for s in shows)
                click.echo(f"  {len(shows)} shows, {perf_count} performances")

        except ScrapingDogError as e:
            click.echo(f"  Error scraping {genre_enum.value}: {e}", err=True)

        click.echo("")

    if not all_dfs:
        click.echo("No data scraped!")
        return

    # Combine and save snapshot
    combined_df = pd.concat(all_dfs, ignore_index=True)
    snapshot_path = snapshot_dir / f"{date_str}-fringe-snapshot.csv"
    combined_df.to_csv(snapshot_path, index=False)

    click.echo(f"Saved snapshot: {snapshot_path}")
    click.echo(f"  Total: {len(combined_df)} performances")
    click.echo("")

    # Compare with previous snapshot
    diff = None
    if compare:
        prev_snapshot = find_latest_snapshot(snapshot_dir, exclude_date=date_str)
        if prev_snapshot:
            click.echo(f"Comparing with: {prev_snapshot.name}")
            prev_df = load_snapshot(prev_snapshot)
            diff = compare_snapshots(prev_df, combined_df)

            # Print summary
            text_report = format_diff_as_text(diff)
            click.echo("")
            click.echo(text_report)
        else:
            click.echo("No previous snapshot found for comparison.")

    # Send email if requested
    if email and diff:
        if not settings.email_to:
            click.echo("Email recipient not configured (EDFRINGE_EMAIL_TO)", err=True)
        elif not settings.smtp_user or not settings.smtp_password:
            click.echo("SMTP credentials not configured", err=True)
        else:
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

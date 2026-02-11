"""Command-line interface using Click."""

import logging
from datetime import datetime
from pathlib import Path

import click

from .config import get_settings
from .converter import FringeConverter, save_all_formats
from .core import FringeScraper, ensure_output_dir, save_raw_csv, shows_to_dataframe
from .models import Genre
from .scraper import ScrapingDogError


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


if __name__ == "__main__":
    cli()

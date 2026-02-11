"""Command-line interface using Click."""

import click

from .config import get_settings


@click.group()
@click.option("-v", "--verbose", count=True, help="Increase verbosity (-v, -vv)")
@click.pass_context
def cli(ctx: click.Context, verbose: int) -> None:
    """Scrapes show, performer and performance listings from the Edinburgh Fringe website."""
    ctx.ensure_object(dict)
    ctx.obj["settings"] = get_settings()
    ctx.obj["verbose"] = verbose


@cli.command()
@click.pass_context
def info(ctx: click.Context) -> None:
    """Show configuration information."""
    settings = ctx.obj["settings"]
    click.echo(f"Debug mode: {settings.debug}")
    click.echo(f"Log level: {settings.log_level}")
    click.echo(f"Base URL: {settings.base_url}")
    click.echo(f"Output dir: {settings.output_dir}")


# Add more commands here using @cli.command()


if __name__ == "__main__":
    cli()

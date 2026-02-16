# edfringe-scrape

Scrapes show, performer and performance listings from the Edinburgh Fringe website.

## Quick Start

```bash
cp config.example.toml config.toml
cp .envrc.example .envrc
direnv allow
uv sync
edfringe-scrape --help
```

## Project Structure

```
src/edfringe_scrape/
├── __init__.py     # Package version
├── cli.py          # Click CLI commands
├── config.py       # Pydantic Settings
├── models.py       # Pydantic data models
└── core.py         # Business logic
```

## Development

```bash
uv run pytest              # Run tests
uv run pytest --cov        # Run with coverage
uv run ruff format .       # Format code
uv run ruff check . --fix  # Lint and fix
```

## Key Commands

- `update` — Scrape genres, save timestamped snapshot to `data/snapshots/`, merge into canonical files in `data/current/`, optionally compare with previous snapshot and email a report (supports `--recent`/`--full`, `--compare`/`--no-compare`, `--email`)
- `convert` — Transform raw CSV to cleaned/summary/wide formats
- `export` — Export to Festival Planner format
- `compare` — Diff two snapshots

## Configuration

Settings are managed via Pydantic Settings with `EDFRINGE_` prefix.

See `config.example.toml` for available options.

## Conventions

This project follows the conventions in the parent CLAUDE.md:
- uv for package management
- Click for CLI
- Pydantic Settings for configuration
- Pydantic for data models
- pytest for testing

## Terminology

Standard terms used across this project and its downstream consumers (festival-planner, fringe-search):

| Standard Term | Meaning | Deprecated Alternatives |
|---------------|---------|------------------------|
| **performance** | A single occurrence of a show at a specific date/time | schedule, listing |
| **performer** | The artist(s) performing a show | presenter |
| **show** | A titled production that has one or more performances | event |
| **venue** | The location where a show is performed | location (except in CSV column `show-location`) |
| **availability** | Ticket status for a performance (e.g., sold-out, tickets-available) | status |
| **genre** | Category of show (e.g., COMEDY, MUSICALS) | category |
| **producer** | The production company behind a show | promoter |

Notes:
- CSV column headers (e.g., `show-performer`, `show-location`) are stable and must not be renamed
- HTML CSS selectors (e.g., `event-card-search_eventPresenter`) match the upstream website and are not our terminology

## Documentation

Before implementing new features:
1. Document requirements in `docs/reqs/`
2. Design architecture in `docs/designs/`
3. Create implementation plan in `docs/plans/`

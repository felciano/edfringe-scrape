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

## Documentation

Before implementing new features:
1. Document requirements in `docs/reqs/`
2. Design architecture in `docs/designs/`
3. Create implementation plan in `docs/plans/`

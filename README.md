# edfringe-scrape

Scrapes show, performer and performance listings from the Edinburgh Fringe website.

## Installation

```bash
# Clone the repository
git clone <repo-url>
cd edfringe-scrape

# Set up configuration
cp config.example.toml config.toml
cp .envrc.example .envrc

# Allow direnv to load environment
direnv allow

# Install dependencies
uv sync
```

## Usage

```bash
# Show help
edfringe-scrape --help

# Show configuration
edfringe-scrape info
```

## Development

```bash
# Run tests
uv run pytest

# Run tests with coverage
uv run pytest --cov

# Format code
uv run ruff format .

# Lint code
uv run ruff check . --fix
```

## Configuration

Configuration is managed through `config.toml` (copied from `config.example.toml`).

See `config.example.toml` for available settings and their descriptions.

### Secrets

Secrets are loaded from 1Password via direnv. See `.envrc.example` for the required secret references.

## Documentation

- `docs/reqs/` - Requirements documents
- `docs/designs/` - Architecture and design documents
- `docs/specs/` - Technical specifications
- `docs/plans/` - Implementation plans
- `docs/decisions/` - Architecture Decision Records (ADRs)

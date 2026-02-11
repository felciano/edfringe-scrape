# Design: edfringe-scrape System Overview

## Status
Draft

## Overview
Scrapes show, performer and performance listings from the Edinburgh Fringe website.

This is a living document. Update as the architecture evolves.

## Goals
- Provide a clear, maintainable architecture
- Follow CLAUDE.md conventions
- Support scraping multiple show categories
- Output clean, normalized data for analysis

## Architecture

### Components

#### CLI (`cli.py`)
Entry point for user interaction. Uses Click for command parsing. Commands include:
- `info` - Show current configuration
- `scrape` - Run scraper for specified categories (future)
- `convert` - Transform raw data to output formats (future)

#### Configuration (`config.py`)
Pydantic Settings for environment-based configuration. Loaded via direnv from `config.toml` and 1Password.

Key settings:
- `base_url` - Edinburgh Fringe website URL
- `output_dir` - Where to write output files

#### Models (`models.py`)
Pydantic models for data validation and serialization:
- `Show` - A show with name, performer, venue, URL
- `Performance` - A single performance with date, time, availability

#### Core (`core.py`)
Business logic, decoupled from CLI and I/O concerns. Handles:
- HTTP requests to Fringe website
- HTML parsing with BeautifulSoup
- Data transformation and normalization

### Data Flow
```
User Input (category, date range)
    │
    ▼
┌─────────┐
│   CLI   │ ─── validates args ──▶ Click
└────┬────┘
     │
     ▼
┌─────────┐
│ Config  │ ─── loads from ──▶ Environment (direnv)
└────┬────┘
     │
     ▼
┌─────────┐     ┌──────────┐
│  Core   │ ───▶│  httpx   │ ──▶ Fringe Website
└────┬────┘     └──────────┘
     │
     ▼
┌─────────┐
│ Models  │ ─── validates ──▶ Show, Performance
└────┬────┘
     │
     ▼
  CSV Output
```

### Data Models

#### Show
- `name` (str): Show title
- `performer` (str, optional): Performer/company name
- `url` (HttpUrl): Link to show page
- `venue` (str, optional): Venue name
- `location` (str, optional): Venue address

#### Performance
- `show_name` (str): Reference to show
- `show_url` (HttpUrl): Link to show page
- `date` (date): Performance date
- `time` (time, optional): Performance time
- `availability` (str, optional): Ticket status
- `venue` (str, optional): Venue name

## External Dependencies
- click: CLI framework
- pydantic: Data validation
- pydantic-settings: Configuration management
- httpx: HTTP client for web requests
- beautifulsoup4: HTML parsing
- pandas: Data transformation and CSV export

## Trade-offs and Alternatives Considered
- **httpx vs requests**: httpx chosen for async support and modern API
- **BeautifulSoup vs lxml**: BeautifulSoup chosen for simpler API, familiar from existing scripts

## Open Questions
- [ ] Rate limiting strategy for scraping
- [ ] How to handle pagination on listing pages
- [ ] Authentication requirements (if any) for accessing all data

## Related Documents
- Requirement: docs/reqs/001-initial-scope.md
- Plan: docs/plans/phase-1-mvp.md

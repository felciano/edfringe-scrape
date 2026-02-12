# Festival Data Formats

This document describes every output file produced by edfringe-scrape.

## Quick Reference

| Command | Output File | Rows | Location |
|---------|------------|------|----------|
| `scrape` | `{DATE}-EdFringe-{GENRE}.csv` | 1 per performance | output_dir |
| `scrape` | `{DATE}-EdFringe-{GENRE}-show-info.csv` | 1 per show | output_dir |
| `scrape` | `venue-info.csv` | 1 per venue (cached) | output_dir |
| `convert` | `Cleaned-{FILENAME}.csv` | 1 per performance | output_dir |
| `convert` | `Summary-{FILENAME}.csv` | 1 per show | output_dir |
| `convert` | `WideFormat-{FILENAME}.csv` | 1 per show+time | output_dir |
| `export` | `{FILENAME}-festival-planner.csv` | 1 per performance | output_dir |
| `update` | `performances.csv` | 1 per performance | current_dir |
| `update` | `show-info.csv` | 1 per show | current_dir |
| `update` | `venue-info.csv` | 1 per venue (cached) | current_dir |
| `daily-snapshot` | `{DATE}-fringe-snapshot.csv` | 1 per performance | snapshot_dir |
| `daily-snapshot` | `{DATE}-fringe-show-info.csv` | 1 per show | snapshot_dir |
| `daily-snapshot` | `venue-info.csv` | 1 per venue (cached) | snapshot_dir |
| `compare` | `{NAME}.txt` or `{NAME}.html` | report | user-specified |

---

## 1. Raw Scraped Data

**File:** `{YYYY-MM-DD}-EdFringe-{GENRE}.csv`
**Command:** `scrape`
**One row per:** performance (or per show if no performances found)

| Column | Example |
|--------|---------|
| `web-scraper-scrape-time` | `2026-02-12T10:30:45.123456` |
| `show-link-href` | `https://www.edfringe.com/tickets/whats-on/show-slug` |
| `show-link` | `Dave's Comedy Hour` |
| `show-name` | `Dave's Comedy Hour` |
| `show-performer` | `Dave Smith` |
| `date` | `Wednesday 30 July` |
| `performance-time` | `19:30 - 20:30` |
| `show-availability` | `TICKETS_AVAILABLE` |
| `show-location` | `Pleasance Courtyard` |
| `web-scraper-start-url` | `https://www.edfringe.com/tickets/whats-on?search=true&genres=COMEDY` |

**Availability values:** `TICKETS_AVAILABLE`, `SOLD_OUT`, `CANCELLED`, `TWO_FOR_ONE`, `PREVIEW_SHOW`, `FREE_TICKETED`, `FREE`, `NO_ALLOCATION`, `NO_ALLOCATION_REMAINING`

---

## 2. Show Info

**File:** `{YYYY-MM-DD}-EdFringe-{GENRE}-show-info.csv`
**Command:** `scrape`
**One row per:** show (metadata only, no performance data)

| Column | Example |
|--------|---------|
| `show-link-href` | `https://www.edfringe.com/tickets/whats-on/show-slug` |
| `show-name` | `Dave's Comedy Hour` |
| `genre` | `COMEDY` |
| `subgenres` | `Stand-up, LGBTQ+` |
| `description` | `Dave performs his latest material...` |
| `warnings` | `Strong language, adult themes` |
| `age_suitability` | `16+` |
| `image_url` | `https://img.edfringe.com/large.jpg` |
| `website` | `https://comedian.com` |
| `facebook` | `https://facebook.com/comedian` |
| `instagram` | `https://instagram.com/comedian` |
| `tiktok` | `https://tiktok.com/@comedian` |
| `youtube` | `https://youtube.com/comedian` |
| `twitter` | `https://twitter.com/comedian` |
| `bluesky` | `https://bsky.app/comedian` |
| `mastodon` | `https://mastodon.social/@comedian` |

Social links come from the event's `attributes` array first, falling back to `socialLinks` array.

---

## 3. Venue Info (Cached)

**File:** `venue-info.csv` (static name, not date-stamped)
**Command:** `scrape`, `daily-snapshot`
**One row per:** unique venue (deduplicated by `venue_code`)

| Column | Example |
|--------|---------|
| `venue_code` | `V288` |
| `venue_name` | `Pleasance Courtyard` |
| `address` | `60 Pleasance, Edinburgh` |
| `postcode` | `EH8 9TJ` |
| `geolocation` | `55.9469,-3.1813` |
| `google_maps_url` | `https://www.google.com/maps/dir/?api=1&destination=55.9469,-3.1813` |
| `venue_page_url` | `https://www.edfringe.com/venues/pleasance-courtyard` |
| `description` | `A popular Fringe venue` |
| `contact_phone` | `+44 131 556 6550` |
| `contact_email` | `info@pleasance.co.uk` |

**Caching behavior:** This file acts as both output and cache. Venue pages are fetched only for venues not already in the file. On subsequent runs, only newly discovered venues trigger page fetches.

**Data sources:**
- `venue_code` through `description`: extracted from show detail page `__NEXT_DATA__` (zero additional cost)
- `contact_phone`, `contact_email`: fetched from venue detail page (one API call per new venue)

---

## 4. Cleaned Data

**File:** `Cleaned-{INPUT_FILENAME}.csv`
**Command:** `convert --formats cleaned` (or `--formats all`)
**One row per:** performance (rows with invalid dates are dropped)

| Column | Example |
|--------|---------|
| `show` | `=HYPERLINK("https://...", "Show Name")` |
| `show-name` | `Dave's Comedy Hour` |
| `show-performer` | `Dave Smith` |
| `show-link-href` | `https://www.edfringe.com/tickets/whats-on/show-slug` |
| `date_normalized` | `2026-07-30` |
| `performance-time` | `19:30 - 20:30` |
| `show-availability` | `TICKETS_AVAILABLE` |
| `show-location` | `Pleasance Courtyard` |

The `show` column contains an Excel `HYPERLINK` formula for clickable links in spreadsheets.

---

## 5. Summary

**File:** `Summary-{INPUT_FILENAME}.csv`
**Command:** `convert --formats summary` (or `--formats all`)
**One row per:** show (aggregated across all performances)

| Column | Example |
|--------|---------|
| `show-name` | `Dave's Comedy Hour` |
| `num_performances` | `25` |
| `first_date` | `2026-08-03` |
| `last_date` | `2026-08-31` |
| `performer` | `Dave Smith` |

---

## 6. Wide Format

**File:** `WideFormat-{INPUT_FILENAME}.csv`
**Command:** `convert --formats wide` (or `--formats all`)
**One row per:** unique show + time + venue combination

| Column | Example |
|--------|---------|
| `show-link-href` | `https://...` |
| `show-name` | `Dave's Comedy Hour` |
| `show-performer` | `Dave Smith` |
| `performance-time` | `19:30` |
| `show-location` | `Pleasance Courtyard` |
| `2026-08-03` | `TICKETS_AVAILABLE` |
| `2026-08-04` | `SOLD_OUT` |
| `2026-08-05` | `TICKETS_AVAILABLE` |
| ... | ... |

Date columns are generated dynamically based on the dates present in the data. Each cell contains the availability status for that show on that date.

---

## 7. Festival Planner Export

**File:** `{INPUT_FILENAME}-festival-planner.csv`
**Command:** `export`
**One row per:** performance

| Column | Example |
|--------|---------|
| `performer` | `Mark Watson` |
| `producer` | `Avalon Productions` |
| `show_name` | `Before It Overtakes Us` |
| `original_show_name` | `Mark Watson: Before It Overtakes Us` |
| `venue_name` | `Pleasance Dome` |
| `date` | `2026-08-03` |
| `start_time` | `19:30` |
| `end_time` | `20:30` |
| `availability` | `tickets-available` |

**Smart parsing** (enabled by default, disable with `--no-smart-parsing`):
- Production companies (e.g., "Avalon Productions", "PBJ Management") are moved to the `producer` column
- Performer names are extracted from titles like "Mark Watson: Show Title"
- Variety shows with no identifiable performer get `Various`

**Availability mapping:**

| Raw value | Mapped value |
|-----------|-------------|
| `TICKETS_AVAILABLE` | `tickets-available` |
| `SOLD_OUT`, `NO_ALLOCATION`, `NO_ALLOCATION_REMAINING` | `sold-out` |
| `CANCELLED` | `cancelled` |
| `TWO_FOR_ONE` | `2-for-1-show` |
| `PREVIEW`, `PREVIEW_SHOW` | `preview-show` |
| `FREE`, `FREE_TICKETED` | `free-show` |

---

## 8. Canonical Current-State Files

**Directory:** `data/current/` (configurable via `current_dir` setting)
**Command:** `update`

The `update` command maintains three canonical files representing the latest known state of all scraped data. Unlike date-stamped files, these are updated in-place on each run.

### Modes

- **`--recent`** (default): Scrapes with `recentlyAdded=LAST_SEVEN_DAYS`, merges into existing files. Existing data for non-matching keys is preserved (never removed).
- **`--full`**: Replaces all performance data for scraped genres; other genres are untouched. Show info is always additive in both modes.

### Files

**`performances.csv`** — Same schema as raw scraped data (section 1) with an additional `genre` column. One row per performance. Keyed on `show-link-href` + `date` + `performance-time`.

**`show-info.csv`** — Same schema as section 2. One row per show. Keyed on `show-link-href`.

**`venue-info.csv`** — Same schema as section 3. One row per venue, cached.

### Directory Structure

```
data/current/
├── performances.csv    # All performances across genres
├── show-info.csv       # All show metadata across genres
└── venue-info.csv      # Venue cache (persistent)
```

### Merge Behavior

| Mode | Performances | Show Info | Venues |
|------|-------------|-----------|--------|
| `--recent` | Upsert by key (new overwrites matching; non-matching preserved) | Upsert by URL | Append new only |
| `--full` | Replace all rows for scraped genres; other genres preserved | Upsert by URL | Append new only |

---

## 9. Daily Snapshot

**File:** `{YYYY-MM-DD}-fringe-snapshot.csv`
**Command:** `daily-snapshot`
**One row per:** performance (combined from all scraped genres)

Same schema as raw scraped data (section 1) with one additional column:

| Column | Example |
|--------|---------|
| `genre` | `COMEDY` |

The snapshot also produces `{DATE}-fringe-show-info.csv` (same schema as section 2) and `venue-info.csv` (same schema as section 3).

---

## 10. Comparison Report

**File:** user-specified with `-o` flag, or printed to stdout
**Command:** `compare`
**Formats:** `--format text` (default) or `--format html`

Reports changes between two snapshots:
- **New shows** added since previous snapshot
- **Sold out** performances
- **Cancelled** performances
- **Back available** (previously sold out, now available again)
- **New performances** for existing shows
- **Removed shows** no longer in listings

The HTML format includes color-coded sections and clickable show links, suitable for email delivery via `daily-snapshot --email`.

---

## Directory Structure

The `update` command maintains canonical current-state files:

```
data/current/
├── performances.csv    # All performances across genres (merged)
├── show-info.csv       # All show metadata across genres (merged)
└── venue-info.csv      # Venue cache (persistent)
```

A typical scrape run produces:

```
output/
├── 2026-02-12-EdFringe-COMEDY.csv              # Raw performances
├── 2026-02-12-EdFringe-COMEDY-show-info.csv     # Show metadata
└── venue-info.csv                                # Venue cache (persistent)
```

A daily snapshot run produces:

```
data/snapshots/
├── 2026-02-11-fringe-snapshot.csv
├── 2026-02-11-fringe-show-info.csv
├── 2026-02-12-fringe-snapshot.csv
├── 2026-02-12-fringe-show-info.csv
└── venue-info.csv                                # Venue cache (persistent)
```

Running `convert` on a raw CSV produces:

```
output/
├── Cleaned-2026-02-12-EdFringe-COMEDY.csv
├── Summary-2026-02-12-EdFringe-COMEDY.csv
└── WideFormat-2026-02-12-EdFringe-COMEDY.csv
```

---

## Date and Time Formats

| Context | Format | Example |
|---------|--------|---------|
| Filenames | `YYYY-MM-DD` | `2026-02-12` |
| Raw CSV `date` column | `{Weekday} {DD} {Month}` | `Wednesday 30 July` |
| Normalized/export dates | `YYYY-MM-DD` | `2026-07-30` |
| Performance times | `HH:MM - HH:MM` | `19:30 - 20:30` |
| Scrape timestamp | ISO 8601 | `2026-02-12T10:30:45.123456` |

Missing values are represented as empty strings in all CSV outputs.

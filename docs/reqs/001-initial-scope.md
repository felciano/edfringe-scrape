# Requirement: edfringe-scrape Initial Scope

## Status
Draft

## Problem Statement
Scrapes show, performer and performance listings from the Edinburgh Fringe website.

Planning attendance at the Edinburgh Festival Fringe requires tracking thousands of shows across multiple dates, venues, and availability states. The official website doesn't provide an easy way to export or analyze this data for personal planning purposes.

## Goals
- [ ] Scrape show listings including name, performer, venue, and link
- [ ] Scrape performances with dates, times, and availability
- [ ] Export data to CSV for analysis in spreadsheets
- [ ] Provide CLI interface for running scrapes

## Non-Goals
Explicitly out of scope for v1:
- Real-time ticket availability monitoring
- Automatic ticket purchasing
- Mobile app or web UI
- Historical data tracking across years

## Success Criteria
How do we know we've succeeded?
- [ ] Can scrape a category of shows (e.g., Comedy, Musicals)
- [ ] Output includes show name, performer, venue, dates, and availability
- [ ] Data exports to CSV format compatible with Excel/Google Sheets
- [ ] CLI provides clear feedback on scraping progress

## Context
This builds on existing ad-hoc scripts in the `edfringe` project that process web-scraped data. The goal is to create a more robust, maintainable tool.

## Related Documents
- Design: docs/designs/system-overview.md
- Plan: docs/plans/phase-1-mvp.md

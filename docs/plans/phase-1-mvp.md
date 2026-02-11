# Plan: edfringe-scrape Phase 1 - MVP

## Status
Planned

## Outcome
_Fill in when complete._

## Goal
Deliver minimum viable functionality:
- Working CLI with basic commands
- Configuration management
- Core scraping logic for a single category
- CSV output
- Test coverage

## Prerequisites
- [x] Project initialized with uv
- [x] Directory structure created
- [x] Config files in place
- [ ] Requirements documented in 001-initial-scope.md
- [ ] Understand Fringe website structure

## Tasks

### Session 1: Website Analysis & Core Models
- [ ] Analyze Edinburgh Fringe website structure
- [ ] Identify URLs for category listings
- [ ] Identify HTML structure for show details
- [ ] Refine Pydantic models based on actual data
- [ ] Add unit tests for models

### Session 2: Scraping Implementation
- [ ] Implement HTTP client with proper headers
- [ ] Implement HTML parsing for show listings
- [ ] Implement HTML parsing for performance details
- [ ] Add rate limiting / polite scraping delays
- [ ] Add scraping tests with mock responses

### Session 3: CLI & Output
- [ ] Add `scrape` CLI command
- [ ] Add CSV export functionality
- [ ] Add progress feedback during scraping
- [ ] Add error handling for network issues
- [ ] Add CLI tests

### Session 4: Polish
- [ ] Update README with usage examples
- [ ] Ensure test coverage meets threshold (80%)
- [ ] Run ruff format and fix any issues
- [ ] Manual end-to-end testing

## Milestones
- [ ] Can scrape a single category page
- [ ] Can extract show details from listing
- [ ] Can export to CSV
- [ ] CLI working end-to-end

## Risks
- Website structure changes: Mitigate by using flexible selectors, testing against live site
- Rate limiting/blocking: Mitigate by adding delays, proper User-Agent
- Authentication required: May need to add login flow

## Related Documents
- Requirement: docs/reqs/001-initial-scope.md
- Design: docs/designs/system-overview.md

#!/bin/bash
# Daily Edinburgh Fringe Snapshot Script
# Run this via cron to get daily updates on the Fringe schedule
#
# Example crontab entry (runs at 6 AM daily):
#   0 6 * * * /path/to/edfringe-scrape/scripts/daily-snapshot.sh
#
# Prerequisites:
# 1. Configure .envrc with API keys and email settings
# 2. Run `direnv allow` in the project directory
# 3. Make this script executable: chmod +x scripts/daily-snapshot.sh

set -e

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Change to project directory
cd "$PROJECT_DIR"

# Log file for debugging
LOG_FILE="$PROJECT_DIR/logs/daily-snapshot-$(date +%Y-%m-%d).log"
mkdir -p "$(dirname "$LOG_FILE")"

# Function to log with timestamp
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "Starting daily snapshot..."
log "Project directory: $PROJECT_DIR"

# Load environment (direnv or manual)
if command -v direnv &> /dev/null; then
    log "Loading environment via direnv..."
    eval "$(direnv export bash 2>/dev/null || true)"
fi

# Also try loading .envrc directly if direnv didn't work
if [[ -z "$EDFRINGE_SCRAPINGDOG_API_KEY" && -f "$PROJECT_DIR/.envrc" ]]; then
    log "Loading .envrc directly..."
    # shellcheck source=/dev/null
    source "$PROJECT_DIR/.envrc"
fi

# Check required environment variables
if [[ -z "$EDFRINGE_SCRAPINGDOG_API_KEY" ]]; then
    log "ERROR: EDFRINGE_SCRAPINGDOG_API_KEY not set"
    exit 1
fi

# Default genres to scrape (can be overridden via environment)
GENRES="${EDFRINGE_SNAPSHOT_GENRES:-COMEDY}"

# Build command
CMD="uv run edfringe-scrape daily-snapshot -g $GENRES"

# Add email flag if configured
if [[ -n "$EDFRINGE_EMAIL_TO" && -n "$EDFRINGE_SMTP_USER" && -n "$EDFRINGE_SMTP_PASSWORD" ]]; then
    CMD="$CMD --email"
    log "Email notifications enabled (sending to $EDFRINGE_EMAIL_TO)"
else
    log "Email notifications disabled (missing EDFRINGE_EMAIL_TO, EDFRINGE_SMTP_USER, or EDFRINGE_SMTP_PASSWORD)"
fi

log "Running: $CMD"

# Run the snapshot command
if $CMD 2>&1 | tee -a "$LOG_FILE"; then
    log "Daily snapshot completed successfully"
else
    log "ERROR: Daily snapshot failed with exit code $?"
    exit 1
fi

# Clean up old logs (keep last 30 days)
find "$PROJECT_DIR/logs" -name "daily-snapshot-*.log" -mtime +30 -delete 2>/dev/null || true

log "Done"

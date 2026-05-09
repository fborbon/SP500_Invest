#!/bin/bash
# Daily paper mode run — called by cron after US market close.
# Runs inside the dashboard container so it shares the same cache/ and outputs/.

set -e
APP_DIR="/opt/forwardforecasting"
LOG="$APP_DIR/logs/paper_$(date +%Y-%m-%d).log"

mkdir -p "$APP_DIR/logs"

echo "=== $(date -u) — Starting paper run ===" >> "$LOG"

cd "$APP_DIR"
docker compose exec -T dashboard python main.py paper >> "$LOG" 2>&1

echo "=== $(date -u) — Done ===" >> "$LOG"

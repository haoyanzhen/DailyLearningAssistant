#!/bin/bash
# Send the daily learning report email through the local Agent entrypoint.

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CONFIG_FILE="${DLA_CONFIG_FILE:-$PROJECT_ROOT/config.json}"
PYTHON_BIN="${DLA_PYTHON_BIN:-$(command -v python3)}"
LOG_PREFIX="[daily-learning-email-agent]"

log() {
    printf '%s %s %s\n' "$(date '+%Y-%m-%d %H:%M:%S %Z')" "$LOG_PREFIX" "$*"
}

if [ ! -f "$CONFIG_FILE" ]; then
    log "error: config file not found: $CONFIG_FILE"
    exit 1
fi

cd "$PROJECT_ROOT"

log "checking config"
"$PYTHON_BIN" "$PROJECT_ROOT/scripts/check_config.py" --config "$CONFIG_FILE" --strict

log "sending daily email"
"$PYTHON_BIN" "$PROJECT_ROOT/orchestrator/run_daily.py" \
    --config "$CONFIG_FILE" \
    --output-root "$PROJECT_ROOT" \
    --only-step 5 \
    --send-email

log "daily email finished"

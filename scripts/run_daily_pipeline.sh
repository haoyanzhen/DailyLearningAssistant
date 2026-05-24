#!/bin/bash
# Run the full local DailyLearningAssistant agent pipeline.
#
# This wrapper is intended for local schedulers such as launchd. It does not
# install or modify any scheduled job by itself.

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CONFIG_FILE="${DLA_CONFIG_FILE:-$PROJECT_ROOT/config.json}"
PYTHON_BIN="${DLA_PYTHON_BIN:-$(command -v python3)}"
LOG_PREFIX="[daily-learning-agent]"

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

log "running HTML generation and publish pipeline"
"$PYTHON_BIN" "$PROJECT_ROOT/orchestrator/run_daily.py" \
    --config "$CONFIG_FILE" \
    --output-root "$PROJECT_ROOT" \
    --generation-only \
    --publish

log "HTML generation and publish pipeline finished"

#!/bin/bash
# Push local DailyLearningAssistant commits from outside the Codex automation sandbox.
#
# This script is intentionally narrow:
# - only runs inside this repository
# - only pushes the main branch
# - only pushes when local main is ahead of origin/main
# - performs DNS, SSH, and remote readability checks before pushing

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOG_PREFIX="[daily-learning-git-push]"
EXPECTED_BRANCH="main"

log() {
    printf '%s %s %s\n' "$(date '+%Y-%m-%d %H:%M:%S %Z')" "$LOG_PREFIX" "$*"
}

run() {
    log "$*"
    "$@"
}

cd "$PROJECT_ROOT"

branch="$(git branch --show-current)"
if [ "$branch" != "$EXPECTED_BRANCH" ]; then
    log "skip: current branch is '$branch', expected '$EXPECTED_BRANCH'"
    exit 0
fi

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    log "error: not inside a git work tree"
    exit 1
fi

log "checking GitHub DNS"
if ! dscacheutil -q host -a name ssh.github.com | grep -q 'ip_address'; then
    log "error: ssh.github.com did not resolve"
    exit 1
fi

log "checking GitHub SSH authentication"
ssh_output="$(ssh -o BatchMode=yes -o ConnectTimeout=10 -T -p 443 git@ssh.github.com 2>&1 || true)"
printf '%s\n' "$ssh_output"
if ! printf '%s\n' "$ssh_output" | grep -q 'successfully authenticated'; then
    log "error: GitHub SSH authentication did not succeed"
    exit 1
fi

log "checking remote readability"
run git ls-remote origin refs/heads/main >/dev/null

log "fetching origin/main"
run git fetch origin main --quiet

counts="$(git rev-list --left-right --count origin/main...HEAD)"
behind="$(printf '%s' "$counts" | awk '{print $1}')"
ahead="$(printf '%s' "$counts" | awk '{print $2}')"
log "sync state: ahead=$ahead behind=$behind"

if [ "$behind" != "0" ]; then
    log "skip: local main is behind origin/main; manual review required before pushing"
    exit 1
fi

if [ "$ahead" = "0" ]; then
    log "nothing to push"
    exit 0
fi

local_head="$(git rev-parse HEAD)"
log "pushing $ahead commit(s), local HEAD=$local_head"
run git push origin main

remote_head="$(git ls-remote origin refs/heads/main | awk '{print $1}')"
if [ "$remote_head" != "$local_head" ]; then
    log "error: remote main is $remote_head, expected $local_head"
    exit 1
fi

log "push complete: remote main matches local HEAD"

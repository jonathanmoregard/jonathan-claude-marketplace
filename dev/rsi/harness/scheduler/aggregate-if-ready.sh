#!/bin/bash
export PATH="/home/jonathan/.local/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
export HOME=/home/jonathan
# Fires aggregate-nightly.sh only when 4 nights have completed AND the proposal
# file hasn't been written yet. Idempotent: safe to run daily.
set -e

DEV=/home/jonathan/Repos/jonathan-claude-marketplace/dev/rsi
RESEARCH=$DEV/research/2026-04-intent-nightly
PROPOSAL=/home/jonathan/.claude/recursive-self-improvement/proposals/2026-04-20-intent-nightly-results.md
TARGET_NIGHTS=4

if [ -f "$PROPOSAL" ]; then
  echo "$(date -Iseconds) aggregate-if-ready: proposal already written, skipping"
  exit 0
fi

auto_complete=$(find "$RESEARCH/automation" -name observations.jsonl -not -empty 2>/dev/null | wc -l)
completed=$((auto_complete / 2))

if [ "$completed" -lt "$TARGET_NIGHTS" ]; then
  echo "$(date -Iseconds) aggregate-if-ready: $completed/$TARGET_NIGHTS nights complete, postponing"
  exit 0
fi

echo "$(date -Iseconds) aggregate-if-ready: $completed nights complete, firing aggregator"
exec "$DEV/harness/scheduler/aggregate-nightly.sh"

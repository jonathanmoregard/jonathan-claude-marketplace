#!/bin/bash
export PATH="/home/jonathan/.local/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
export HOME=/home/jonathan
# Fires fire-nightly.sh only if fewer than 4 nights have completed.
# A completed night = a run dir under research/2026-04-intent-nightly/automation/
# with a non-empty observations.jsonl. There are 2 automation runs per night,
# so completed_nights = automation_count / 2.
set -e

DEV=/home/jonathan/Repos/jonathan-claude-marketplace/dev/rsi
RESEARCH=$DEV/research/2026-04-intent-nightly
TARGET_NIGHTS=4

auto_complete=$(find "$RESEARCH/automation" -name observations.jsonl -not -empty 2>/dev/null | wc -l)
completed=$((auto_complete / 2))

if [ "$completed" -ge "$TARGET_NIGHTS" ]; then
  echo "$(date -Iseconds) fire-if-needed: $completed/$TARGET_NIGHTS nights complete, skipping"
  exit 0
fi

next=$((completed + 1))
echo "$(date -Iseconds) fire-if-needed: $completed/$TARGET_NIGHTS complete, firing night $next"
exec "$DEV/harness/scheduler/fire-nightly.sh" "$next"

#!/usr/bin/env bash
# Install script for recursive-self-improvement plugin.
# Called by the setup wizard after config.json is written.
#
# Usage: bash install.sh <plugin_root> <analysis_hour> <analysis_minute> [--detect-secrets]
set -euo pipefail

PLUGIN_ROOT="$1"
HOUR="${2:-17}"
MINUTE="${3:-0}"
INSTALL_PRECOMMIT_HOOK=false
if [[ "${4:-}" == "--detect-secrets" ]]; then
  INSTALL_PRECOMMIT_HOOK=true
fi

TARGET=~/.claude

echo "Creating directory structure..."
mkdir -p "$TARGET/recursive-self-improvement/proposals"
mkdir -p "$TARGET/recursive-self-improvement/config"
mkdir -p "$TARGET/logs"

echo "Copying reference files..."
cp "$PLUGIN_ROOT/references/policy.md" "$TARGET/recursive-self-improvement/config/policy.md"
cp "$PLUGIN_ROOT/references/categories.md" "$TARGET/recursive-self-improvement/config/categories.md"

echo "Copying analysis prompt..."
cp "$PLUGIN_ROOT/prompts/daily-review.md" "$TARGET/recursive-self-improvement/config/prompt.md"

echo "Installing push script..."
cp "$PLUGIN_ROOT/scripts/push-proposals.sh" "$TARGET/push-proposals.sh"
chmod +x "$TARGET/push-proposals.sh"

echo "Installing daily analysis cron job (${HOUR}:${MINUTE})..."
(crontab -l 2>/dev/null | grep -v "# recursive-self-improvement-analysis" ; echo "${MINUTE} ${HOUR} * * * cd ~/.claude && claude --model opus --print --allowedTools \"Read Write(~/.claude/recursive-self-improvement/proposals/*) Glob Grep WebSearch Bash(~/.claude/push-proposals.sh)\" -p \"\$(cat ~/.claude/recursive-self-improvement/config/prompt.md)\" >> ~/.claude/logs/review-agent.log 2>&1 # recursive-self-improvement-analysis") | crontab -

if [[ "$INSTALL_PRECOMMIT_HOOK" == "true" ]]; then
  echo "Installing pre-commit hook for secret detection..."
  bash "$PLUGIN_ROOT/scripts/install-detect-secrets.sh"
fi

echo "Cleaning up..."
rm -f "$TARGET/tmp/recursive-self-improvement-setup.yml"

echo "Committing configuration..."
cd "$TARGET" && git add recursive-self-improvement/ push-proposals.sh && git commit -m "chore: configure recursive self-improvement"

echo "Done."

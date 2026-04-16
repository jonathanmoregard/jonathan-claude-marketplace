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
mkdir -p "$TARGET/recursive-self-improvement/observations"
mkdir -p "$TARGET/recursive-self-improvement/research"
mkdir -p "$TARGET/recursive-self-improvement/config"
mkdir -p "$TARGET/logs"

# Initialize observation files if they don't exist
for f in observations/observations.jsonl \
         observations/status.jsonl observations/divergence.log; do
  if [[ ! -f "$TARGET/recursive-self-improvement/$f" ]]; then
    touch "$TARGET/recursive-self-improvement/$f"
  fi
done

# Gitignore local-only directories
GITIGNORE="$TARGET/recursive-self-improvement/.gitignore"
for entry in "observations/" "research/"; do
  if [[ ! -f "$GITIGNORE" ]] || ! grep -q "$entry" "$GITIGNORE" 2>/dev/null; then
    echo "$entry" >> "$GITIGNORE"
  fi
done

echo "Copying reference files..."
cp "$PLUGIN_ROOT/references/policy.md" "$TARGET/recursive-self-improvement/config/policy.md"
cp "$PLUGIN_ROOT/references/categories.md" "$TARGET/recursive-self-improvement/config/categories.md"

echo "Copying analysis prompt..."
cp "$PLUGIN_ROOT/prompts/daily-review.md" "$TARGET/recursive-self-improvement/config/prompt.md"

echo "Copying auto-research prompt..."
cp "$PLUGIN_ROOT/prompts/auto-research.md" "$TARGET/recursive-self-improvement/config/auto-research.md"

echo "Installing LLM Guard scanner..."
mkdir -p "$TARGET/recursive-self-improvement/scripts"
cp "$PLUGIN_ROOT/scripts/scan_content.py" "$TARGET/recursive-self-improvement/scripts/scan_content.py"
chmod +x "$TARGET/recursive-self-improvement/scripts/scan_content.py"

echo "Installing push script..."
cp "$PLUGIN_ROOT/scripts/push-proposals.sh" "$TARGET/push-proposals.sh"
chmod +x "$TARGET/push-proposals.sh"

echo "Removing old monthly review cron if present..."
(crontab -l 2>/dev/null | grep -v "# recursive-self-improvement-monthly") | crontab -

echo "Installing daily analysis cron job (${HOUR}:${MINUTE})..."
(crontab -l 2>/dev/null | grep -v "# recursive-self-improvement-analysis" ; echo "${MINUTE} ${HOUR} * * * cd ~/.claude && claude --model opus --print --allowedTools \"Read Write(~/.claude/recursive-self-improvement/observations/*) Glob Grep Bash(du -sm ~/.claude/recursive-self-improvement/observations/observations.jsonl)\" -p \"\$(cat ~/.claude/recursive-self-improvement/config/prompt.md)\" >> ~/.claude/logs/review-agent.log 2>&1 # recursive-self-improvement-analysis") | crontab -

RESEARCH_MINUTE=$(( (MINUTE + 30) % 60 ))
RESEARCH_HOUR=$(( (HOUR + (MINUTE + 30) / 60) % 24 ))

echo "Installing auto-research cron job (${RESEARCH_HOUR}:${RESEARCH_MINUTE})..."
(crontab -l 2>/dev/null | grep -v "# recursive-self-improvement-research" ; echo "${RESEARCH_MINUTE} ${RESEARCH_HOUR} * * * cd ~/.claude && claude --model opus --print --allowedTools \"Read Glob Grep WebSearch WebFetch Write(~/.claude/recursive-self-improvement/research/*) Bash(python3 ~/.claude/recursive-self-improvement/scripts/scan_content.py*)\" -p \"\$(cat ~/.claude/recursive-self-improvement/config/auto-research.md)\" >> ~/.claude/logs/research-agent.log 2>&1 # recursive-self-improvement-research") | crontab -

if [[ "$INSTALL_PRECOMMIT_HOOK" == "true" ]]; then
  echo "Installing pre-commit hook for secret detection..."
  bash "$PLUGIN_ROOT/scripts/install-detect-secrets.sh"
fi

echo "Cleaning up..."
rm -f "$TARGET/tmp/recursive-self-improvement-setup.yml"

echo "Committing configuration..."
cd "$TARGET" && git add recursive-self-improvement/ push-proposals.sh && git commit -m "chore: configure recursive self-improvement"

echo "Done."

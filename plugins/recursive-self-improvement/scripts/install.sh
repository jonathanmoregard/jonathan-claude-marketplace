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

# HOUR/MINUTE end up inside cron lines and bash arithmetic — validate before
# composing anything (and before any install side effect).
if ! [[ "$HOUR" =~ ^[0-9]+$ ]] || (( 10#$HOUR > 23 )); then
  echo "error: HOUR must be a decimal integer 0-23 (got: $HOUR)" >&2
  exit 1
fi
if ! [[ "$MINUTE" =~ ^[0-9]+$ ]] || (( 10#$MINUTE > 59 )); then
  echo "error: MINUTE must be a decimal integer 0-59 (got: $MINUTE)" >&2
  exit 1
fi
HOUR=$((10#$HOUR))
MINUTE=$((10#$MINUTE))

TARGET=~/.claude

echo "Creating directory structure..."
mkdir -p "$TARGET/recursive-self-improvement/proposals"
mkdir -p "$TARGET/recursive-self-improvement/observations"
mkdir -p "$TARGET/recursive-self-improvement/research"
mkdir -p "$TARGET/recursive-self-improvement/config"
mkdir -p "$TARGET/logs"

# Unified proposals folder — aggregation surface scanned by the SessionStart hook
# and walked by /review-improvements. Drop any new subdir here and it auto-appears
# in the next nudge; see hooks/pending-proposals.py DEFAULTS for the config keys.
mkdir -p "$TARGET/proposals"
# Seed rsi subdir as a symlink to the legacy dir so the plugin's daily prompt
# (which writes to the legacy path) and the multi-subdir hook see the same files.
# Only touch when rsi/ doesn't exist yet OR is already a symlink — never overwrite
# a real dir a user has curated by hand.
if [[ ! -e "$TARGET/proposals/rsi" || -L "$TARGET/proposals/rsi" ]]; then
  ln -sfn "$TARGET/recursive-self-improvement/proposals" "$TARGET/proposals/rsi"
fi

# Initialize observation files if they don't exist
for f in observations/observations.jsonl observations/problem_areas.jsonl \
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

echo "Installing proposal intake gate..."
# Independent scorer harness: annotates pending proposals with grep-cited
# sharp|duplicate|rot verdicts before push-proposals.sh ships them for review.
mkdir -p "$TARGET/scripts"
cp "$PLUGIN_ROOT/scripts/proposal-intake-gate.py" "$TARGET/scripts/proposal-intake-gate.py"
chmod +x "$TARGET/scripts/proposal-intake-gate.py"
# Seed the gate config once; never clobber a user-edited one (it carries
# host-local on_decision callback registrations).
if [[ ! -f "$TARGET/proposals/gate-config.json" ]]; then
  cp "$PLUGIN_ROOT/references/gate-config.default.json" "$TARGET/proposals/gate-config.json"
fi

# NOTE (NixOS, 2026-08-01): `crontab` edits are NOT durable on NixOS hosts —
# the user crontab is rebuilt from the declarative config, so lines installed
# here are silently wiped on the next rebuild. On NixOS the schedules below
# belong in the host's declarative crontab (precedent: nixos-config PR #155);
# the file payloads installed above are still what those declarative entries
# invoke. This installer keeps using `crontab` for conventional hosts.
echo "Removing old monthly review cron if present..."
# `grep -v` exits 1 on empty input (fresh host, empty crontab) — with
# pipefail that killed the installer, so every filter tolerates no-match.
(crontab -l 2>/dev/null | { grep -v "# recursive-self-improvement-monthly" || true; }) | crontab -

echo "Installing daily analysis cron job (${HOUR}:${MINUTE})..."
(crontab -l 2>/dev/null | { grep -v "# recursive-self-improvement-analysis" || true; } ; echo "${MINUTE} ${HOUR} * * * cd ~/.claude && claude --model opus --print --allowedTools \"Read Write(~/.claude/recursive-self-improvement/observations/*) Glob Grep Bash(du -sm ~/.claude/recursive-self-improvement/observations/observations.jsonl)\" -p \"\$(cat ~/.claude/recursive-self-improvement/config/prompt.md)\" >> ~/.claude/logs/review-agent.log 2>&1 # recursive-self-improvement-analysis") | crontab -

RESEARCH_MINUTE=$(( (MINUTE + 30) % 60 ))
RESEARCH_HOUR=$(( (HOUR + (MINUTE + 30) / 60) % 24 ))

# Grant note (2026-08-01): this line used to grant WebSearch/WebFetch. Both
# are globally denied in ~/.claude/settings.json, and a global deny beats ANY
# --allowedTools grant — headless included (probed 2026-08-01 on this host's
# Claude Code build). The job's web capability was therefore silently dead on
# every run. External lookups now go through the research-agent MCP tool,
# which is grantable and not deny-listed.
echo "Installing auto-research cron job (${RESEARCH_HOUR}:${RESEARCH_MINUTE})..."
(crontab -l 2>/dev/null | { grep -v "# recursive-self-improvement-research" || true; } ; echo "${RESEARCH_MINUTE} ${RESEARCH_HOUR} * * * cd ~/.claude && claude --model opus --print --allowedTools \"Read Glob Grep mcp__research-agent__research Write(~/.claude/recursive-self-improvement/research/*) Bash(python3 ~/.claude/recursive-self-improvement/scripts/scan_content.py*)\" -p \"\$(cat ~/.claude/recursive-self-improvement/config/auto-research.md)\" >> ~/.claude/logs/research-agent.log 2>&1 # recursive-self-improvement-research") | crontab -

if [[ "$INSTALL_PRECOMMIT_HOOK" == "true" ]]; then
  echo "Installing pre-commit hook for secret detection..."
  bash "$PLUGIN_ROOT/scripts/install-detect-secrets.sh"
fi

echo "Cleaning up..."
rm -f "$TARGET/tmp/recursive-self-improvement-setup.yml"

echo "Committing configuration..."
# Stage and commit ONLY the paths this installer wrote — never a broad
# `git add`, and always commit with explicit pathspecs so a user's unrelated
# pre-staged work is neither swept into this commit nor unstaged.
INSTALLED_PATHS=(
  recursive-self-improvement/.gitignore
  recursive-self-improvement/config/policy.md
  recursive-self-improvement/config/categories.md
  recursive-self-improvement/config/prompt.md
  recursive-self-improvement/config/auto-research.md
  recursive-self-improvement/scripts/scan_content.py
  push-proposals.sh
  scripts/proposal-intake-gate.py
  proposals/gate-config.json
)
cd "$TARGET"
git add -- "${INSTALLED_PATHS[@]}"
git diff --cached --quiet -- "${INSTALLED_PATHS[@]}" || \
  git commit -m "chore: configure recursive self-improvement" -- "${INSTALLED_PATHS[@]}"

echo "Done."

---
name: setup-improvement-loop
description: "Configure the Continuous Improvement Loop — set your north star, goals, alignment signals, and cron schedule. Run this first after installing the plugin, or re-run to update your configuration."
---

# Setup Improvement Loop

You are configuring the Continuous Improvement Loop plugin. This plugin reviews your daily Claude chat logs and writes improvement proposals.

## Pre-flight

1. Check if `~/.claude/improvement-loop-config.yml` exists
   - If yes: read it, tell the user their current config, and ask if they want to update it or start fresh
   - If no: proceed with fresh setup

## Interview

Ask these questions **one at a time**. Wait for the user's response before asking the next.

### 1. North Star

> "What does a good life/work balance look like for you? This is the lens the review agent uses to assess your daily patterns. Think: what state do you want to spend most of your time in?"

### 2. Goals

> "What are you currently working toward? List your goals across any areas of life — the review agent uses these to detect rabbit holes and drift. These are living and can be updated anytime by re-running this setup."

### 3. Alignment Signals

> "How can the review agent assess whether you are living in accordance with your goals or not? Describe what 'on track' looks like and what 'off track' looks like. Be specific about observable patterns — things that would show up in your Claude usage logs."
>
> Examples: "Working past 10pm means I'm in manic mode", "Long sessions where I'm pasting code means I'm firefighting instead of delegating", "Working on X project when I said I'd focus on Y this week"

### 4. Cron Schedule

> "When should the daily review run? Default is 17:00 (5 PM) local time. Enter a time in 24h format, or press enter for default."

## Write Config

Write `~/.claude/improvement-loop-config.yml`:

```yaml
# Continuous Improvement Loop — User Configuration
# Re-run /setup-improvement-loop to update

north_star: |
  <user's response>

goals:
  - category: "<category>"
    items:
      - "<goal>"
      - "<goal>"

alignment_signals:
  on_track: |
    <user's description>
  off_track: |
    <user's description>

schedule:
  cron_time: "17:00"
  timezone: "<detected or asked>"
```

## Post-Config Setup

1. Create directories:
   ```bash
   mkdir -p ~/.claude/improvements ~/.claude/logs
   ```

2. Copy `push-proposals.sh` to `~/.claude/push-proposals.sh` and make executable:
   ```bash
   cp "${CLAUDE_PLUGIN_ROOT}/scripts/push-proposals.sh" ~/.claude/push-proposals.sh
   chmod +x ~/.claude/push-proposals.sh
   ```

3. Copy `daily-review.md` prompt to `~/.claude/prompts/daily-review.md`:
   ```bash
   mkdir -p ~/.claude/prompts
   cp "${CLAUDE_PLUGIN_ROOT}/prompts/daily-review.md" ~/.claude/prompts/daily-review.md
   ```

4. Install crontab entry. Parse `schedule.cron_time` from config into hour and minute:
   ```bash
   # Read existing crontab, remove any previous improvement-loop entry, add new one
   (crontab -l 2>/dev/null | grep -v "# improvement-loop" ; echo "0 17 * * * cd ~/.claude && claude --model opus --print --allowedTools \"Read Write(~/.claude/improvements/*) Glob Grep WebSearch Bash(~/.claude/push-proposals.sh)\" -p \"\$(cat ~/.claude/prompts/daily-review.md)\" >> ~/.claude/logs/review-agent.log 2>&1 # improvement-loop") | crontab -
   ```
   Adjust the `0 17` based on the user's chosen time.

5. Run detect-secrets installation:
   ```bash
   bash "${CLAUDE_PLUGIN_ROOT}/scripts/install-detect-secrets.sh"
   ```

6. Commit:
   ```bash
   cd ~/.claude && git add improvement-loop-config.yml push-proposals.sh prompts/daily-review.md && git commit -m "chore: configure improvement loop"
   ```

7. Tell the user: "Setup complete! The review agent will run daily at <time>. Pending proposals will show up as a nudge when you start a new Claude session. Run /review-improvements to go through them."

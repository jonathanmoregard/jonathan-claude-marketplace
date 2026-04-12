---
name: setup-improvement-loop
description: "Configure the Continuous Improvement Loop — set your north star, goals, alignment signals, and cron schedule. Run this first after installing the plugin, or re-run to update your configuration."
---

# Setup Improvement Loop

You are configuring the Continuous Improvement Loop plugin. This plugin reviews your daily Claude chat logs and writes improvement proposals.

## Pre-flight

### 1. Check git repo

Run:
```bash
git -C ~/.claude rev-parse --git-dir 2>/dev/null
```

If `~/.claude` is **not** a git repo, tell the user:

> "The improvement loop stores proposals and config in `~/.claude` and requires it to be a git repository (so proposals can be pushed and tracked). It isn't one yet. Run this to set it up:
>
> ```bash
> cd ~/.claude && git init && git add . && git commit -m 'init'
> ```
>
> Then re-run /setup-improvement-loop."

**Stop here** if not a git repo. Do not continue setup.

### 2. Check existing config

Check if `~/.claude/improvement-loop-config.yml` exists:
- If yes: read it, tell the user their current config, and ask if they want to update it or start fresh
- If no: proceed with fresh setup

## Interview

Ask these questions **one at a time**. Wait for the user's response before asking the next.

### 1. Life Mission

> "What are you working towards? Describe your life mission — the deeper purpose or direction that guides your choices. This is the lens the review agent uses to assess your daily patterns."

### 2. Current Goals

> "How does that life mission manifest in your current goals? What are you concretely working on right now — across work, health, relationships, creative projects, or anything else? These are living and can be updated anytime by re-running this setup."

### 3. Off-Track Patterns

> "What patterns do you fall into when you're NOT living in alignment with your mission? Be specific — the review agent needs observable signals from your Claude usage logs."
>
> Examples:
> - **Procrastination** — avoiding hard things by doing easy-looking things
> - **Yak shaving** — spending hours on tooling/setup instead of the actual goal
> - **Rabbit holes** — losing context awareness, going deep on tangents that don't matter
> - **Addiction loops** — compulsive checking, returning to the same thing repeatedly
> - **Manic late-night sessions** — working past 10pm, long unbroken streaks

### 4. Analysis Schedule

> "When should the analysis agent run? This is the cron job that reads your chat logs and writes improvement proposals — it runs unattended when your computer is on. Default is 17:00 (5 PM). Enter a time in 24h format, or press enter for default."

### 5. Review Reminder

> "When should you be reminded to actually review the proposals? This sends a TickTick reminder so it doesn't get lost. Default is 09:00 (9 AM) the next morning. Enter a time in 24h format, or press enter for default."

## Write Config

Write `~/.claude/improvement-loop-config.yml`:

```yaml
# Continuous Improvement Loop — User Configuration
# Re-run /setup-improvement-loop to update

life_mission: |
  <user's response>

current_goals:
  - category: "<category>"
    items:
      - "<goal>"
      - "<goal>"

off_track_patterns:
  - name: "<pattern name>"
    description: |
      <user's description of this pattern>

schedule:
  analysis_cron: "17:00"   # when the agent runs to analyze logs and write proposals
  review_reminder: "09:00" # when a TickTick reminder fires to prompt you to run /review-improvements
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

3. Copy prompts to `~/.claude/prompts/`:
   ```bash
   mkdir -p ~/.claude/prompts
   cp "${CLAUDE_PLUGIN_ROOT}/prompts/daily-review.md" ~/.claude/prompts/daily-review.md
   cp "${CLAUDE_PLUGIN_ROOT}/prompts/monthly-review.md" ~/.claude/prompts/monthly-review.md
   ```

4. Install analysis cron. Parse `schedule.analysis_cron` from config into hour and minute:
   ```bash
   # Remove previous improvement-loop-analysis entry, add new one
   (crontab -l 2>/dev/null | grep -v "# improvement-loop-analysis" ; echo "0 17 * * * cd ~/.claude && claude --model opus --print --allowedTools \"Read Write(~/.claude/improvements/*) Glob Grep WebSearch Bash(~/.claude/push-proposals.sh)\" -p \"\$(cat ~/.claude/prompts/daily-review.md)\" >> ~/.claude/logs/review-agent.log 2>&1 # improvement-loop-analysis") | crontab -
   ```
   Adjust `0 17` based on the user's chosen analysis time.

5. Install review reminder cron. Parse `schedule.review_reminder` from config into hour and minute:
   ```bash
   # Remove previous improvement-loop-reminder entry, add new one
   (crontab -l 2>/dev/null | grep -v "# improvement-loop-reminder" ; echo "0 9 * * * ~/.claude/todo-add 'Review improvement proposals — run /review-improvements in Claude Code' # improvement-loop-reminder") | crontab -
   ```
   Adjust `0 9` based on the user's chosen reminder time.
   
   Note: only install the reminder cron if `~/.claude/todo-add` exists. If it doesn't, tell the user: "Skipping review reminder — `~/.claude/todo-add` not found. You can add it later or use another reminder method."

6. Run detect-secrets installation:
   ```bash
   bash "${CLAUDE_PLUGIN_ROOT}/scripts/install-detect-secrets.sh"
   ```

7. Commit:
   ```bash
   cd ~/.claude && git add improvement-loop-config.yml push-proposals.sh prompts/daily-review.md prompts/monthly-review.md && git commit -m "chore: configure improvement loop"
   ```

8. Tell the user: "Setup complete! The analysis agent runs daily at <analysis_time>. You'll get a reminder at <review_time> to review proposals. Run /review-improvements anytime to go through them."

## Offer Monthly Catch-Up

After confirming setup is complete, ask:

> "Want to run a monthly review now to catch up on your history? It'll scan the last 30 days of logs and write proposals for any patterns it finds. This can take a few minutes."

If yes: invoke the `review-month` skill.
If no: done.

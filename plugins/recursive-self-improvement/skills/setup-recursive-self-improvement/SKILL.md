---
name: setup-recursive-self-improvement
description: "Configure the Recursive Self-Improvement loop — choose analysis categories, set goals and schedules. Run this first after installing the plugin, or re-run to update your configuration."
---

# Setup Recursive Self-Improvement

You are configuring the Recursive Self-Improvement plugin. This plugin reviews your daily Claude chat logs and writes improvement proposals.

## Pre-flight

### 1. Check git repo

Run:
```bash
git -C ~/.claude rev-parse --git-dir 2>/dev/null
```

If `~/.claude` is **not** a git repo, tell the user:

> "The recursive self-improvement loop stores proposals and config in `~/.claude` and requires it to be a git repository (so proposals can be pushed and tracked). It isn't one yet. Run this to set it up:
>
> ```bash
> cd ~/.claude && git init && git add . && git commit -m 'init'
> ```
>
> Then re-run /setup-recursive-self-improvement."

**Stop here** if not a git repo. Do not continue setup.

### 2. Check existing config

Check if `~/.claude/recursive-self-improvement/config.yml` exists:
- If yes: read it, tell the user their current config, and ask if they want to update it or start fresh
- If no: proceed with fresh setup

## Interview

After each answer, append it to `~/.claude/tmp/recursive-self-improvement-setup.yml` so progress is saved as you go:

```bash
mkdir -p ~/.claude/tmp
```

Ask these questions **one at a time**. Wait for the user's response before asking the next. After each answer, write the collected answers so far to `~/.claude/tmp/recursive-self-improvement-setup.yml` in the same YAML structure as the final config.

### 1. Categories

Explain the three proposal categories and ask which the user wants enabled:

> "The improvement loop analyzes your daily Claude usage and writes proposals in three categories:
>
> 1. **Productivity** — Making Claude better at executing *how* without your involvement. Detects when Claude misunderstood intent, got stuck, needed rescue, or when you had to take over and paste fixes. Proposes skills, hooks, CLAUDE.md rules, and config changes so Claude handles it autonomously next time.
>
> 2. **Alignment** — Adherence to your goals and north star. Detects when your daily work drifts from what you say matters. Requires you to define a north star and goals so the agent has something to measure against.
>
> 3. **Wellbeing** — Anti-mania, anti-burnout, healthy patterns. Detects zombie sessions, late-night marathons, compulsive loops, and rabbit holes. Requires you to describe your off-track patterns so the agent knows what to flag.
>
> Which categories do you want? (e.g. 'all', '1 and 3', 'just productivity')"

### 2. Daily Proposal Limit

> "How many improvement proposals should the daily analysis produce at most? This caps the daily run — the monthly backlog review is uncapped. Default is 3."

### 3. North Star (only if alignment is enabled)

Skip this question if the user did NOT select the alignment category.

> "What's your north star — the deeper purpose or direction that guides your choices? This is the lens the review agent uses to assess whether your daily work is aligned."

### 4. Current Goals (only if alignment is enabled)

Skip this question if the user did NOT select the alignment category.

> "What are your current concrete goals? What are you working on right now — across work, health, relationships, creative projects, or anything else?"

**After the user answers:** Assess whether the stated goals clearly connect to the north star. If any goal seems disconnected or the connection is non-obvious, engage in a brief interview to understand how they fit together. Don't just ask once — keep inquiring until you genuinely understand the relationship. For example:

- "How does [goal] relate to [north star aspect]?"
- If the answer is vague: "Can you give me a concrete example of how working on [goal] moves you toward [north star]?"
- If it's an indirect path: "So the chain is [goal] → [intermediate outcome] → [north star aspect]? Do I have that right?"

Continue until you can articulate the connection yourself. Then confirm your understanding with the user. Save the validated understanding in the config under `goal_connections` so the daily agent won't flag this work as off-track.

### 5. Off-Track Patterns (only if wellbeing is enabled)

Skip this question if the user did NOT select the wellbeing category.

> "What patterns do you fall into when you're NOT at your best? Be specific — the review agent needs observable signals from your Claude usage logs."
>
> Examples:
> - **Manic late-night sessions** — working past 10pm, long unbroken streaks
> - **Rabbit holes** — losing context awareness, going deep on tangents
> - **Addiction loops** — compulsive checking, returning to the same thing repeatedly
> - **Zombie mode** — going through the motions without clear intent

### 6. Analysis Schedule

> "When should the analysis agent run? This is the cron job that reads your chat logs and writes improvement proposals — it runs unattended when your computer is on. Default is 17:00 (5 PM). Enter a time in 24h format, or press enter for default."

### 7. Review Reminder

> "When should you be reminded to actually review the proposals? This sends a TickTick reminder so it doesn't get lost. Default is 09:00 (9 AM) the next morning. Enter a time in 24h format, or press enter for default."

## Write Config

Create the directory structure:
```bash
mkdir -p ~/.claude/recursive-self-improvement/proposals
mkdir -p ~/.claude/recursive-self-improvement/config
```

Write `~/.claude/recursive-self-improvement/config/config.json`:

```json
{
  "categories": {
    "productivity": true/false,
    "alignment": true/false,
    "wellbeing": true/false
  },
  "daily_proposal_limit": 3,
  "north_star": "<user's response — only if alignment enabled>",
  "current_goals": [
    {
      "category": "<category>",
      "items": ["<goal>", "<goal>"]
    }
  ],
  "goal_connections": [
    {
      "goal": "<goal that seemed disconnected>",
      "connection": "<user's explanation of how it connects to north star>"
    }
  ],
  "off_track_patterns": [
    {
      "name": "<pattern name>",
      "description": "<user's description>"
    }
  ],
  "schedule": {
    "analysis_cron": "17:00",
    "review_reminder": "09:00",
    "timezone": "<detected or asked>"
  }
}
```

Only include `north_star`, `current_goals`, and `goal_connections` if alignment is enabled. Only include `off_track_patterns` if wellbeing is enabled.

## Write Prompt

Generate `~/.claude/recursive-self-improvement/config/prompt.md` from the default prompt at `${CLAUDE_PLUGIN_ROOT}/prompts/daily-review.md`, but **only include sections for the enabled categories**:

- If productivity is disabled: omit the "Flag — productivity issues" section
- If alignment is disabled: omit the "Flag — alignment drift" section
- If wellbeing is disabled: omit the "Flag — wellbeing patterns" section

This file is the user's customizable copy. The cron job reads from here, so the user can edit it to tune behavior without re-running setup.

## Post-Config Setup

1. Copy `push-proposals.sh` to `~/.claude/push-proposals.sh` and make executable:
   ```bash
   cp "${CLAUDE_PLUGIN_ROOT}/scripts/push-proposals.sh" ~/.claude/push-proposals.sh
   chmod +x ~/.claude/push-proposals.sh
   ```

2. Create logs directory:
   ```bash
   mkdir -p ~/.claude/logs
   ```

3. Install analysis cron. Parse `schedule.analysis_cron` from config into hour and minute:
   ```bash
   # Remove previous recursive-self-improvement-analysis entry, add new one
   (crontab -l 2>/dev/null | grep -v "# recursive-self-improvement-analysis" ; echo "0 17 * * * cd ~/.claude && claude --model opus --print --allowedTools \"Read Write(~/.claude/recursive-self-improvement/proposals/*) Glob Grep WebSearch Bash(~/.claude/push-proposals.sh)\" -p \"\$(cat ~/.claude/recursive-self-improvement/config/prompt.md)\" >> ~/.claude/logs/review-agent.log 2>&1 # recursive-self-improvement-analysis") | crontab -
   ```
   Adjust `0 17` based on the user's chosen analysis time.

4. Install review reminder cron. Parse `schedule.review_reminder` from config into hour and minute:
   ```bash
   # Remove previous recursive-self-improvement-reminder entry, add new one
   (crontab -l 2>/dev/null | grep -v "# recursive-self-improvement-reminder" ; echo "0 9 * * * ~/.claude/todo-add 'Review improvement proposals — run /review-improvements in Claude Code' # recursive-self-improvement-reminder") | crontab -
   ```
   Adjust `0 9` based on the user's chosen reminder time.
   
   Note: only install the reminder cron if `~/.claude/todo-add` exists. If it doesn't, tell the user: "Skipping review reminder — `~/.claude/todo-add` not found. You can add it later or use another reminder method."

5. Run detect-secrets installation:
   ```bash
   bash "${CLAUDE_PLUGIN_ROOT}/scripts/install-detect-secrets.sh"
   ```

6. Remove the setup scratchpad:
   ```bash
   rm -f ~/.claude/tmp/recursive-self-improvement-setup.yml
   ```

7. Commit:
   ```bash
   cd ~/.claude && git add recursive-self-improvement/ push-proposals.sh && git commit -m "chore: configure recursive self-improvement"
   ```

8. Tell the user: "Setup complete! The analysis agent runs daily at <analysis_time>. You'll get a reminder at <review_time> to review proposals. Run /review-improvements anytime to go through them. You can customize the analysis prompt at `~/.claude/recursive-self-improvement/config/prompt.md`."

## Offer Monthly Catch-Up

After confirming setup is complete, ask:

> "Want to run a monthly review now to catch up on your history? It'll scan the last 30 days of logs and write proposals for any patterns it finds. This can take a few minutes."

If yes: invoke the `review-month` skill.
If no: done.

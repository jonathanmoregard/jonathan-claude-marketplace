---
name: setup-recursive-self-improvement
description: "Configure the Recursive Self-Improvement loop — choose analysis categories, set goals and schedules. Run this first after installing the plugin, or re-run to update your configuration."
---

# Setup Recursive Self-Improvement

## Pre-flight (run as subagent)

Before showing anything to the user, dispatch a subagent to run these checks silently. The subagent should report back a structured result:

**Subagent task:** "Check prerequisites for recursive-self-improvement setup. Report: (1) is ~/.claude a git repo? (2) does ~/.claude/recursive-self-improvement/config/config.json exist? If it exists, read it and return its contents. Return a JSON object: {git_repo: bool, existing_config: null | <config contents>}"

### Handle subagent result

**If `git_repo` is false:** Tell the user:

> "The recursive self-improvement loop stores proposals and config in `~/.claude` and requires it to be a git repository (so proposals can be pushed and tracked). It isn't one yet. Run this to set it up:
>
> ```bash
> cd ~/.claude && git init && git add . && git commit -m 'init'
> ```
>
> Then re-run /setup-recursive-self-improvement."

**Stop here.** Do not continue setup.

**If `existing_config` is not null:** Tell the user their current config summary and ask if they want to update it or start fresh. Then proceed to the introduction.

**If all clear:** Proceed to the introduction.

## Introduction

> "Welcome to Recursive Self-Improvement! This plugin helps you improve the way you use Claude by analyzing your usage history, finding recurring issues, and crafting improvement proposals. You then decide whether Claude should implement them — nothing happens without your say-so."

## Interview

After each answer, append it to `~/.claude/tmp/recursive-self-improvement-setup.yml` so progress is saved as you go:

```bash
mkdir -p ~/.claude/tmp
```

Ask these questions **one at a time**. Wait for the user's response before asking the next. After each answer, write the collected answers so far to `~/.claude/tmp/recursive-self-improvement-setup.yml` in the same YAML structure as the final config.

### 1. Categories

Read `${CLAUDE_PLUGIN_ROOT}/references/categories.md` for the full category descriptions. Present a summary to the user:

> "The plugin can help you with four areas:
>
> 1. **Productivity** — Making Claude better at acting without you there holding its hand. Proposes config changes so Claude handles things autonomously next time.
>
> 2. **Automation** — Finds repetitive cleanup work in your sessions that a script or cron job could handle instead.
>
> 3. **Alignment** — Are you working on your goals, or drifting? Reviews your daily work against your stated north star. You get proposals, not orders.
>
> 4. **Wellbeing** — Spots patterns that disrupt your wellbeing. Anti-mania, anti-burnout, healthy rhythms.
>
> Which categories do you want? (e.g. 'all', '1 and 3', 'productivity and automation')"

### 2. Daily Proposal Limit

> "How many improvement proposals should the daily analysis produce at most? This caps the daily run — the monthly backlog review is uncapped. Default is 3."

### 3. North Star (only if alignment is enabled)

Skip this question if the user did NOT select the alignment category.

> "What's your north star — the deeper purpose or direction that guides your choices? This is the lens the review agent uses to assess whether your daily work is aligned."

### 4. Current Goals (only if alignment is enabled)

Skip this question if the user did NOT select the alignment category.

> "What are your current concrete goals? What are you working on right now — across work, health, relationships, creative projects, or anything else?"

**After the user answers:** For each goal or goal category, interview the user about how it connects to their north star. Don't just ask once — keep inquiring until you genuinely understand the relationship. For example:

- "How does [goal] relate to [north star aspect]?"
- If the answer is vague: "Can you give me a concrete example of how working on [goal] moves you toward [north star]?"
- If it's an indirect path: "So the chain is [goal] → [intermediate outcome] → [north star aspect]? Do I have that right?"

Continue until you can articulate the connection yourself. Then confirm your understanding with the user. Save each goal group with its `connection` field in config so the daily agent understands why the user is working on it.

### 5. Analysis Schedule

> "When should the analysis agent run? This is the cron job that reads your chat logs and writes improvement proposals — it runs unattended when your computer is on. Default is 17:00 (5 PM). Enter a time in 24h format, or say 'default' for 17:00."

The review reminder is handled by the SessionStart hook (see `hooks/pending-proposals.py`) — it detects pending proposals and tells Claude to mention them to the user with instructions on how to start a review.

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
    "automation": true/false,
    "alignment": true/false,
    "wellbeing": true/false
  },
  "daily_proposal_limit": 3,
  "north_star": "<user's response — only if alignment enabled>",
  "current_goals": [
    {
      "category": "<category>",
      "items": ["<goal>", "<goal>"],
      "connection": "<how this category of goals connects to the north star>"
    }
  ],
  "schedule": {
    "analysis_cron": "17:00",
    "timezone": "<detected or asked>"
  }
}
```

Only include `north_star` and `current_goals` if alignment is enabled.

Note: `off_track_patterns` is not configured during setup. It emerges over time as the review agent learns from the user's accept/reject decisions and conversations during `/review-improvements`.

## Write Reference Files

Copy the reference files to the user's config directory. These are the user's customizable copies — edits here change agent behavior without re-running setup.

```bash
cp "${CLAUDE_PLUGIN_ROOT}/references/policy.md" ~/.claude/recursive-self-improvement/config/policy.md
cp "${CLAUDE_PLUGIN_ROOT}/references/categories.md" ~/.claude/recursive-self-improvement/config/categories.md
```

Tell the user: "The policy and category definitions are at `~/.claude/recursive-self-improvement/config/policy.md` and `categories.md` — you can edit these anytime to tune behavior."

## Write Prompt

Copy `${CLAUDE_PLUGIN_ROOT}/prompts/daily-review.md` to `~/.claude/recursive-self-improvement/config/prompt.md`.

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

4. Run detect-secrets installation:
   ```bash
   bash "${CLAUDE_PLUGIN_ROOT}/scripts/install-detect-secrets.sh"
   ```

5. Remove the setup scratchpad:
   ```bash
   rm -f ~/.claude/tmp/recursive-self-improvement-setup.yml
   ```

6. Commit:
   ```bash
   cd ~/.claude && git add recursive-self-improvement/ push-proposals.sh && git commit -m "chore: configure recursive self-improvement"
   ```

7. Tell the user: "Setup complete! The analysis agent runs daily at <analysis_time>. When there are pending proposals, Claude will mention them at the start of your sessions — just run /review-improvements to go through them."

## Offer Monthly Catch-Up

After confirming setup is complete, ask:

> "Want to run a monthly review now to catch up on your history? It'll scan the last 30 days of logs and write proposals for any patterns it finds. This can take a few minutes."

If yes: invoke the `review-month` skill.
If no: done.

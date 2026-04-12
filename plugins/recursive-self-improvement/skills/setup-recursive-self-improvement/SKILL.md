---
name: setup-recursive-self-improvement
description: "Configure the Recursive Self-Improvement loop — choose analysis categories, set goals and schedules. Run this first after installing the plugin, or re-run to update your configuration."
---

# Setup Recursive Self-Improvement

## Pre-flight (run as subagent)

Before showing anything to the user, dispatch a subagent to run these checks silently. The subagent should report back a structured result:

**Subagent task:** "Check prerequisites for recursive-self-improvement setup. Report: (1) is ~/.claude a git repo? (2) does ~/.claude/recursive-self-improvement/config/config.json exist? If it exists, read it and return its contents. (3) is detect-secrets installed? (check: `which detect-secrets`). Return a JSON object: {git_repo: bool, existing_config: null | <config contents>, detect_secrets_installed: bool}"

### Handle subagent result

**If `git_repo` is false:** Ask the user:

> "The plugin stores proposals and config in `~/.claude`. To track changes and push proposals, it works best as a git repository. Want me to set that up now?
>
> This runs: `cd ~/.claude && git init && git add . && git commit -m 'init'`"

If yes: run the commands and continue. If no: **stop here** — the plugin requires git.

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

> "How many improvement proposals should the daily analysis produce at most? The monthly review is capped at 5. Default is 3."

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

Write `~/.claude/recursive-self-improvement/config/config.json` (the install script creates the directories):

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

## Optional: Secret Protection

Check the subagent's `detect_secrets_installed` result. If not already installed, ask:

> "Since proposals get committed to git, there's a small risk that the analysis agent accidentally includes sensitive data (API keys, tokens) in a proposal. I can install a pre-commit hook called `detect-secrets` that blocks commits containing anything that looks like a secret. It's a Python tool installed via pip. Want me to include it?"

Remember their answer for the install step.

## Install

Tell the user:

> "Now I'll install everything — creating directories, copying config files, setting up the daily cron job at <analysis_time>, and committing. This takes a moment."

Parse the analysis time into hour and minute, then run the install script:

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/install.sh" "${CLAUDE_PLUGIN_ROOT}" <hour> <minute> [--detect-secrets]
```

Append `--detect-secrets` only if the user opted in (or if already installed, skip it either way).

After the script completes, tell the user:

> "Setup complete! The analysis agent runs daily at <analysis_time>. When there are pending proposals, Claude will mention them at the start of your sessions — just run /review-improvements to go through them.
>
> You can customize behavior anytime by editing files in `~/.claude/recursive-self-improvement/config/` — the prompt, policy, and category definitions all live there."

## Offer Monthly Catch-Up

After confirming setup is complete, ask:

> "Want to run a monthly review now to catch up on your history? It'll scan the last 30 days of logs and write proposals for any patterns it finds. This can take a few minutes."

If yes: invoke the `review-month` skill.
If no: done.

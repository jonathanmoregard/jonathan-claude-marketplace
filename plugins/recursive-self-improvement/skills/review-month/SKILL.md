---
name: review-month
description: "Run a monthly review of the last 30 days of Claude chat logs. Analyzes patterns, recurring themes, and macro-level drift. Writes improvement proposals and a monthly themes summary."
---

# Review Month

Run the monthly review agent to analyze the last 30 days of Claude chat logs.

## What this does

The monthly review agent:
- Scans all chat logs from the last 30 days
- Identifies persistent patterns (not one-off incidents)
- Writes improvement proposals to `~/.claude/improvements/`
- Writes a monthly themes summary with top friction points, alignment wins, and a macro recommendation
- Pushes proposals via `~/.claude/push-proposals.sh`

This complements the daily review cron — daily reviews catch individual session issues, monthly reviews catch drift and recurring themes.

## Pre-flight checks

Before running, verify:

1. `~/.claude/recursive-self-improvement/config.yml` exists. If not: "Run /setup-recursive-self-improvement first to configure your north star and goals."

2. `~/.claude` is a git repository:
   ```bash
   git -C ~/.claude rev-parse --git-dir
   ```
   If not: "~/.claude is not a git repo. Run: `cd ~/.claude && git init && git add . && git commit -m 'init'`"

3. `~/.claude/prompts/monthly-review.md` exists. If not, copy from the plugin:
   ```bash
   cp "<plugin-base-dir>/prompts/monthly-review.md" ~/.claude/prompts/monthly-review.md
   ```

## Run the agent

Tell the user: "Running monthly review agent — this may take a few minutes depending on how many logs there are."

Run:
```bash
cd ~/.claude && claude --model opus --print \
  --allowedTools "Read Glob Grep Bash(~/.claude/push-proposals.sh) Write(~/.claude/improvements/*)" \
  -p "$(cat ~/.claude/prompts/monthly-review.md)" \
  | tee -a ~/.claude/logs/review-agent.log
```

## After the agent completes

Show the user the summary output from the agent.

Then: "Run /review-improvements to go through the new proposals."

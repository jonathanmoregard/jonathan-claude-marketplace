---
name: review-improvements-help
description: "Explain how the Recursive Self-Improvement works — the daily review agent, proposals, and review workflow."
---

# Improvement Loop Help

Explain the Recursive Self-Improvement to the user. Cover:

## What It Does

A daily Opus-powered agent reviews your Claude chat logs from the last 24 hours. It looks for:

- **Config improvements** — where Claude misunderstood you, got stuck, or needed rescue. Proposes skills, hooks, CLAUDE.md rules to prevent recurrence.
- **Automation opportunities** — manual maintenance work you're doing that could run on a schedule.
- **Wellbeing patterns** — based on your configured alignment signals. Detects zombie/manic mode, rabbit holes, and drift from your goals.

## How Proposals Work

- Stored in `~/.claude/improvements/` as markdown files
- Contain problem descriptions and 1-3 proposed fixes — no log excerpts for security
- Tagged with category (config/automation/wellbeing) and linked to source log files
- Status lifecycle: pending → accepted/rejected/deferred → implemented

## Commands

- `/setup-recursive-self-improvement` — configure your north star, goals, alignment signals, and schedule
- `/review-improvements` — walk through pending proposals interactively
- `/review-improvements-help` — this help text

## Configuration

Your config lives at `~/.claude/recursive-self-improvement/config.yml`. Re-run `/setup-recursive-self-improvement` to update it.

## Security

- The cron agent has read-only access to your config and logs, write access only to proposals
- Proposals are treated as untrusted content during review (defense against prompt injection)
- `detect-secrets` pre-commit hook prevents secrets from being committed

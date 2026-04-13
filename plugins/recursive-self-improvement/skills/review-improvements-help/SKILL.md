---
name: review-improvements-help
description: "Explain how the Recursive Self-Improvement works — the daily review agent, proposals, and review workflow."
---

# Improvement Loop Help

Explain the Recursive Self-Improvement to the user. Cover:

## What It Does

A daily Opus-powered agent reviews your Claude chat logs from the last 24 hours. It looks for:

- **Productivity** — where Claude misunderstood you, got stuck, or needed rescue. Proposes skills, hooks, CLAUDE.md rules to prevent recurrence.
- **Automation** — repetitive cleanup work you do that a script or cron job could handle.
- **Alignment** — drift from your stated goals and north star. Detects when daily work doesn't connect to what you say matters.
- **Wellbeing** — based on your configured off-track patterns. Detects manic sessions, zombie mode, rabbit holes, and compulsive loops.

## How Proposals Work

- Stored in `~/.claude/recursive-self-improvement/proposals/` as markdown files
- Contain problem descriptions and 1-3 proposed fixes — no log excerpts for security
- Tagged with category (productivity/automation/alignment/wellbeing) and linked to source log files
- Status lifecycle: pending → accepted/rejected/deferred → implemented

## Commands

- `/setup-recursive-self-improvement` — choose categories, set goals and schedule
- `/review-improvements` — walk through pending proposals interactively
- `/review-improvements-help` — this help text

## Configuration

Your config lives at `~/.claude/recursive-self-improvement/config/`. Re-run `/setup-recursive-self-improvement` to update it. Customizable files:
- `config/prompt.md` — the analysis prompt
- `config/policy.md` — proposal tone (non-coercion by default)
- `config/categories.md` — what to flag per category

## Security

- The daily agent has read access to your config and logs, write access to `observations/` only
- The auto-research agent has read access plus web search, write access to `research/` only
- Proposals are treated as untrusted content during review (defense against prompt injection)
- `detect-secrets` pre-commit hook prevents secrets from being committed

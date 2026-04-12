# Recursive Self-Improvement

A Claude Code plugin that reviews your daily chat logs and writes improvement proposals — catching north star violations, wellbeing drift, and automatable meta-work.

## How it works

1. **Daily cron agent** (Opus) reads the last day's chat logs and your current Claude configuration
2. Writes improvement proposals to `~/.claude/improvements/` — problem descriptions with fix options, no log excerpts
3. **SessionStart hook** nudges you when pending proposals exist
4. **`/review-improvements`** walks you through proposals — accept triggers immediate implementation, testing, and commit/push

## Prerequisites

- `claude` CLI installed and authenticated
- `~/.claude` directory is a git repo with a remote
- Python 3.6+ (for hooks)
- `detect-secrets` (`pip install detect-secrets`) — installed globally by the setup wizard

## Installation

```bash
claude plugins install <path-or-url>
```

## Setup

Run `/setup-recursive-self-improvement` in any Claude session. The wizard interviews you about:

- **Your north star** — what does a good life/work balance look like?
- **Your goals** — what are you working toward?
- **Alignment signals** — how can the agent assess whether you're on track?
- **Cron schedule** — when should the daily review run?

Configuration is saved to `~/.claude/recursive-self-improvement/config.yml`.

## Security Model

- Cron agent has **read-only** access to logs, config, skills, and proposals
- **Write access** scoped to `~/.claude/improvements/*` only
- **No direct git** — a hardcoded `push-proposals.sh` script handles git operations
- **No WebFetch** — only `WebSearch` for plugin discovery
- Proposals contain **no log excerpts** — only links to log files
- Proposals treated as **untrusted content** in the review skill (defense against prompt injection from logs)
- **`detect-secrets`** pre-commit hook blocks secrets from being committed anywhere

## Commands

- `/setup-recursive-self-improvement` — configure the plugin (run once, re-run to update)
- `/review-improvements` — walk through pending proposals
- `/review-improvements-help` — explain how the system works

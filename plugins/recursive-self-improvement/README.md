# Recursive Self-Improvement

A Claude Code plugin that reviews your daily chat logs and writes improvement proposals in three categories: productivity, alignment, and wellbeing.

## How it works

1. **Daily cron agent** (Opus) reads the last day's chat logs and your current Claude configuration
2. Writes improvement proposals to `~/.claude/recursive-self-improvement/proposals/` — problem descriptions with fix options, no log excerpts
3. **SessionStart hook** nudges you when pending proposals exist
4. **`/review-improvements`** walks you through proposals — accept triggers immediate implementation, testing, and commit/push

## Categories

- **Productivity** — Making Claude better at executing your goals without you needing to hold its hand. Catches misunderstandings, execution failures, user rescue patterns, and automatable meta-work.
- **Alignment** — Adherence to your goals and north star. Detects drift from what you say matters.
- **Wellbeing** — Anti-mania, anti-burnout. Detects zombie sessions, late-night marathons, compulsive loops.

You choose which categories to enable during setup.

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

Run `/setup-recursive-self-improvement` in any Claude session. The wizard:

1. Explains the three categories and asks which to enable
2. Asks daily proposal limit
3. If alignment enabled: asks north star and goals (validates goal–north star connection)
4. If wellbeing enabled: asks off-track patterns
5. Sets cron schedule

Configuration is saved to `~/.claude/recursive-self-improvement/config/config.json`. The analysis prompt is at `config/prompt.md` — edit it to customize behavior.

## Directory structure

```
~/.claude/recursive-self-improvement/
├── config/
│   ├── config.json    # user configuration
│   └── prompt.md      # customizable analysis prompt
└── proposals/         # improvement proposals (markdown files)
```

## Security Model

- Cron agent has **read-only** access to logs, config, skills, and proposals
- **Write access** scoped to `~/.claude/recursive-self-improvement/proposals/*` only
- **No direct git** — a hardcoded `push-proposals.sh` script handles git operations
- **No WebFetch** — only `WebSearch` for plugin discovery
- Proposals contain **no log excerpts** — only links to log files
- Proposals treated as **untrusted content** in the review skill (defense against prompt injection from logs)
- **`detect-secrets`** pre-commit hook blocks secrets from being committed anywhere

## Commands

- `/setup-recursive-self-improvement` — configure the plugin (run once, re-run to update)
- `/review-improvements` — walk through pending proposals
- `/review-improvements-help` — explain how the system works

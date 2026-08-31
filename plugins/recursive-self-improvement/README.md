# Recursive Self-Improvement

A Claude Code plugin that reviews your daily chat logs and writes improvement proposals in four categories: productivity, automation, alignment, and wellbeing.

## How it works

1. **Daily cron agent** (Opus) reads the last day's chat logs and your current Claude configuration
2. Writes improvement proposals to the rsi subdir of the proposals folder — `~/.local/state/claude-proposals/rsi/` by default, overridable via `proposals.folder` in `config.json`. Problem descriptions with fix options, no log excerpts. The folder deliberately sits outside `~/.claude` so a nightly unattended run cannot dirty the live config repo; see `references/proposals-folder.md`
3. **SessionStart hook** nudges you at startup when pending proposals exist, and a **UserPromptSubmit hook** re-surfaces the count mid-session — at most once per UTC day, plus immediately whenever the count rises, so a nightly batch does not sit unseen behind a banner you already scrolled past. Both count through the same module (`hooks/proposal_counts.py`)
4. **Proposal intake gate** (`~/.claude/scripts/proposal-intake-gate.py`, run by `push-proposals.sh` before every push) dispatches read-only scorers in chunks of at most `scorer.batch_size` proposals (default 10 — a backlog never lands on the model as one prompt, and a failed chunk defers only that chunk) that must grep the config and referenced repos before ruling each proposal `sharp`, `duplicate`, or `rot` — the verdict and its cited evidence are annotated into the proposal's frontmatter; nothing is auto-rejected. Coverage matches what the push ships: every allowlisted `.md` in a spine subdir is gated, including files with no frontmatter or no `status:` field (other producers' formats); only an explicit non-pending status or a reconciled gate block opts a file out. Config: `~/.claude/proposals/gate-config.json` (versioned — it is user config); audit trail: `~/.claude/proposals/gate-log.jsonl` (local-only forensics — gitignored and excluded from `push-proposals.sh`'s pathspec, so it never lands in the pushed history). Rationale: proposers score their own homework badly — an ungated 2026-08-01 run proposed two fixes that were already shipped.
5. **`/review-improvements`** walks you through proposals (gate verdicts surfaced inline) — accept triggers immediate implementation, testing, and commit/push. Decisions can trigger per-subdir `on_decision` callbacks declared in gate-config.json.

## Categories

- **Productivity** — Making Claude better at executing your goals without you needing to hold its hand. Catches misunderstandings, execution failures, and user rescue patterns.
- **Automation** — Finds repetitive cleanup work in your sessions that a script or cron job could handle.
- **Alignment** — Are you working on your goals, or drifting? Reviews daily work against your stated north star.
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

1. Explains the four categories and asks which to enable
2. Asks daily proposal limit
3. If alignment enabled: asks north star and goals (validates goal–north star connection)
4. If wellbeing enabled: asks off-track patterns
5. Sets cron schedule

Configuration is saved to `~/.claude/recursive-self-improvement/config/config.json`. The analysis prompt is at `config/prompt.md` — edit it to customize behavior.

**NixOS:** `crontab` edits are not durable there — the user crontab is rebuilt from the declarative config, so the wizard's cron lines get wiped on the next rebuild. Put the schedules in the host's declarative crontab instead (nixos-config PR #155 has the reference pattern); the installed file payloads are what those entries invoke.

## Directory structure

```
~/.claude/recursive-self-improvement/
├── config/
│   ├── config.json      # user configuration
│   ├── prompt.md        # customizable analysis prompt
│   ├── policy.md        # proposal tone policy (non-coercion by default)
│   └── categories.md    # category definitions and flagging rules
└── proposals/           # improvement proposals (markdown files)
```

## Security Model

- Cron agent has **read-only** access to logs, config, skills, and proposals
- **Write access** scoped to `~/.claude/recursive-self-improvement/proposals/*` only
- **No direct git** — a hardcoded `push-proposals.sh` script handles git operations
- **No WebFetch/WebSearch** — both are globally denied on this setup, and a global deny beats any `--allowedTools` grant (verified 2026-08-01), so the research cron routes external lookups through the sandboxed `mcp__research-agent__research` MCP tool instead
- **Intake gate scorer is read-only** — `Read Grep Glob` only; the trusted gate script does all writing
- **Push is gate-mandatory** — `push-proposals.sh` hard-fails (exit 1) when the gate script is missing instead of pushing ungated proposals; reinstall via the plugin's `scripts/install.sh`. Emergency bypass for a broken install: `PROPOSAL_GATE_ALLOW_MISSING=1 ~/.claude/push-proposals.sh` — use it knowingly and reinstall the gate afterwards. A *partial* batch (gate exit 4) is never bypassable: rerun the gate.
- Proposals contain **no log excerpts** — only links to log files
- Proposals treated as **untrusted content** in the review skill (defense against prompt injection from logs)
- **`detect-secrets`** pre-commit hook blocks secrets from being committed anywhere

If the gate repeatedly exits 4 on the *same* file, the scorer never returns a verdict for it — a permanently unscorable proposal. The operator remedy is to rename the file with a leading dot (the gate's default `excluded_files` covers dotfiles) or move it to the `archived/` subdir; either takes it out of every future batch. Do not bypass the gate.

## Commands

- `/setup-recursive-self-improvement` — configure the plugin (run once, re-run to update)
- `/review-improvements` — walk through pending proposals
- `/review-improvements-help` — explain how the system works

# Corrections Loop

A Claude Code plugin that captures correction-shaped user messages ("no, not
that", "stop doing X", "wrong file") into a local JSONL ledger via a
deterministic `UserPromptSubmit` hook. Observation only — it never blocks,
never prints, and never calls an LLM.

## Why a hook and not a skill

Skills and CLAUDE.md instructions trigger probabilistically — in practice
50–80% of the time depending on phrasing and context pressure. A
`UserPromptSubmit` hook fires on **every** prompt, deterministically, so
capture coverage is 100% by construction. Classification is a fixed regex
table in code; anything correction-shaped that doesn't map to a specific
bucket lands in `unknown` for later triage. The LLM is never in the hot
path — triage happens offline (see "Consuming from RSI" below).

## What it captures

On each prompt, `hooks/corrections-capture.py`:

1. Reads the hook JSON from stdin (`{"prompt", "session_id", "cwd", ...}`).
2. Matches the prompt against the pattern table (case-insensitive, first
   match wins, table order is the precedence contract).
3. On match, appends one JSON line to the ledger. On no match, exits
   silently. Any failure whatsoever also exits 0 — capture must never break
   a session. Typical runtime is ~30ms including interpreter startup.

### Buckets

| Bucket | Meaning | Example patterns |
|---|---|---|
| `skill_misuse` | Wrong artifact / approach / tool picked | "wrong file", "wrong approach" |
| `memory_update` | Claude lost context it had or was given | "you already tried", "I said", "I told you" |
| `behavioral` | In-session behavior to change | "stop doing", "undo that", "don't do that again" |
| `rule` | A standing rule was violated | "I told you never", "you're not supposed to" |
| `preference` | Soft style/workflow preference | "I'd rather", "I prefer" |
| `unknown` | Correction-shaped, no specific bucket | "no, not that", "not what I asked/meant" |

### Ledger

Lines land in `~/.claude/observations/corrections.jsonl` (dir created 0700
if missing, file 0600, single `O_APPEND` write per event):

```json
{"ts": "2026-08-01T21:00:00+00:00", "session_id": "…", "cwd": "/home/…",
 "bucket": "behavioral", "pattern_id": "stop_doing",
 "excerpt": "stop doing full rebuilds every time"}
```

`excerpt` is the first 200 characters of the message with control
characters stripped.

## Privacy

- Excerpts are capped at 200 characters and stay **local-only** — nothing
  leaves the machine.
- The ledger file is `0600` and its directory `0700`.
- Excerpts are raw prompt text; if you paste secrets into prompts they can
  end up in the (local, permission-locked) ledger. Delete the file at any
  time — the hook recreates it on the next match.

## Install / Uninstall

From the marketplace:

```
/plugin install corrections-loop@jonathanmoregard
```

or `claude plugins install <path-or-url>` pointing at this directory. The
hook registers via `hooks/hooks.json`; no setup wizard, no configuration.

Uninstall by removing the plugin (`/plugin uninstall corrections-loop`).
The ledger at `~/.claude/observations/corrections.jsonl` is left in place;
delete it manually if you want the history gone.

## Consuming from RSI

Intended wiring (follow-up PR, not part of this plugin): the
recursive-self-improvement nightly reviewer adds
`~/.claude/observations/corrections.jsonl` as a signal source alongside the
session logs it already reads. Sketch:

- During its log-analysis step, the reviewer reads the ledger, filters
  entries since its last run (by `ts` against its divergence log), and
  groups them by `bucket` and `cwd`.
- Clusters of `rule` / `memory_update` entries are strong candidates for
  CLAUDE.md or memory edits; `skill_misuse` clusters point at skill
  descriptions that under-trigger; `behavioral` clusters suggest hook or
  settings changes.
- `unknown` entries are triaged by the reviewer (this is where the LLM
  enters — offline, never in the capture path) and either re-bucketed into
  an observation or dropped as noise.

Until that wiring lands, the ledger is still useful standalone:
`jq -r '.bucket' ~/.claude/observations/corrections.jsonl | sort | uniq -c`
gives a quick read on where corrections concentrate.

## Tests

```
cd plugins/corrections-loop && python3 -m unittest discover -s tests -v
```

Covers: every pattern's classification, pattern precedence, non-correction
prompts producing no write, malformed stdin exiting 0 with no write,
excerpt truncation + control-char stripping, file/dir modes, and idempotent
directory creation with append-across-runs.

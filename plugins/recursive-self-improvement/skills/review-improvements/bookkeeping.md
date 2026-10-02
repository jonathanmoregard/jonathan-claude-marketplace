# Bookkeeping — shared by both modes

Only the orchestrating session does bookkeeping. Subagents never edit, move or archive proposal files.

## Per-proposal resolution (file-based proposals)

As each outcome lands, record it on the proposal itself:

| Outcome | rsi subdir (status-aware) | Other subdirs (existence-based) |
|---|---|---|
| PR opened / implemented | `status: implemented` + `resolution: "<date>: <repo>#<n> <one line>"` | callback `implemented`, then move to `<subdir>/archived/` |
| Already fixed / component gone | `status: obsolete` + `resolution:` with the evidence (commit sha, file:line, date) | callback `rejected`, move to `<subdir>/archived/rejected/` |
| Older duplicate of a newer item | `status: superseded` + `resolution: "superseded by <file>"` | archive the older copy |
| Not worth doing | `status: rejected` + `resolution:` with the reason | callback `rejected`, archive |
| One proposal split across PRs (e.g. a cross-repo pair) | leave pending until every part has a PR, then `status: implemented` + `resolution:` naming all PRs and their merge order | callback `implemented` once every part has a PR, then archive |
| Needs the user (taste call, credential) | leave pending; add `resolution: "needs-user: <A/B recommendation>"` | leave in place with a `# DEFERRED` line |

Edit frontmatter and move files using **literal paths** (the full expanded path typed out). Guards refuse `sed -i`, `mv` and `>` on shell-variable paths; route around them with literal paths or the Write/Edit tools, never by quoting tricks. Insert the `resolution:` line right after `status:`. Afterwards check `^status:` appears exactly once in the file: a file whose gate block was written as a separate frontmatter reads as pending regardless of its real status — merge the two blocks.

Callbacks run only for subdirs with an `on_decision` entry in gate-config.json (typically not `rsi`); for the rest the frontmatter edit or archive move is the whole record. Archive moves keep the filename when it already starts with a date; otherwise prefix `YYYY-MM-DD-`.

Bulk-reject an inert backlog (e.g. permission prompts that keep firing because the rule is deliberate) through the callback — one `--run-callback <subdir> <path> rejected` per file, then archive. Never delete proposal files.

## Push and verify

At the end, and after any large batch: `~/.claude/push-proposals.sh`, then `git -C <proposals_folder> log -1 --stat` must show a commit touching the files you changed. The script exits 0 even when it commits nothing.

## Decision record

After each resolved observation, write a decision record **into the rsi subdir of the resolved proposals folder**, alongside the proposals it decides:

`<proposals_folder>/<rsi_subdir>/YYYY-MM-DD-OBS-ID-decision.md`

With defaults that is `~/.local/state/claude-proposals/rsi/YYYY-MM-DD-OBS-ID-decision.md`. Resolve the folder from config as in step 1 — do not write to `~/.claude/recursive-self-improvement/proposals/`, which would land the decision record outside the sink, in a different repo from the proposal it records.

```markdown
---
status: implemented | skipped
observation_id: OBS-YYYY-MM-DD-NNN
category: productivity | automation | alignment | wellbeing
date: YYYY-MM-DD
track: automated | human
root_cause: [only for human track]
---

## What was implemented
[Brief description]

## Why this approach
[What the user chose and why]
```

Update status — append to `~/.claude/recursive-self-improvement/observations/status.jsonl`:

```json
{"observation_id":"OBS-YYYY-MM-DD-NNN","status":"resolved","date":"YYYY-MM-DD","detail":"Implemented: [brief]"}
```

**Clean up:** Delete the research brief at `~/.claude/recursive-self-improvement/research/OBS-ID.md` if it exists.

## On-decision callbacks (config-driven)

Some proposal sources need to hear about decisions — e.g. a ledger that will re-propose a drained pattern forever unless the decision is recorded. The wiring is config-driven: the gate config at `<proposals_folder>/gate-config.json` may declare a callback per subdir under its `on_decision` key:

```json
{ "on_decision": { "<subdir-name>": "/absolute/path/to/callback" } }
```

After the user decides on a file-based proposal (implemented / rejected / deferred), run the gate's callback subcommand **before any archive move** (callbacks read the file in place):

```
python3 ~/.claude/scripts/proposal-intake-gate.py --run-callback <subdir> <absolute-proposal-path> <decision>
```

where `<decision>` is one of `implemented`, `rejected`, `deferred`. Never run the configured callback path directly via the shell tool — the subcommand looks the callback up in the map itself and refuses anything that fails validation (must realpath-resolve under `~/.claude`, be a regular non-symlink file owned by you, carry no group/other write bits, and be executable; executed with list argv, `shell=False`). Surface the subcommand's stdout/stderr to the user verbatim. On nonzero exit: report it and continue the drain — a callback failure never blocks the review, but the user must see it (they may need to run it by hand). Subdirs without an `on_decision` entry make the subcommand a clean no-op ("no on_decision callback configured"). `skip` records no decision, so nothing runs.

Do not hardcode subdir names or callback paths in this flow — the map in gate-config.json is the single source of truth. (Example of the pattern: a `permissions` subdir mapping to an adapter that records the decision in the permission ledger so the drained pattern stops being re-proposed nightly.)


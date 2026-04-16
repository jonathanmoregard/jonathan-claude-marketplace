# Variance runs — 2026-04-14 → 2026-04-16

28 category-scoped daily-review runs of the RSI agent against the last 30 days
of Claude Code logs. Goal: accumulate enough runs to cluster observations
post-hoc and decide on an ontology (automation vs autonomy split) from data
rather than priors.

## Setup

- Prompt under test: current state of `feature/sharper-automation` at fire time.
- Snapshot of prompt + categories.md + config.json is copied into each run's
  directory so each run is independently reviewable.
- Each run is category-scoped: agent analyzes only its assigned category.

## Schedule

Fired after Claude 5-hour cap resets. 7 slots total, 4 runs per slot.

| Slot | Cutoff | Auto | Align | Well |
|------|--------|------|-------|------|
| 1 | now (post-23:10 4-14) | 2 | 1 | 1 |
| 2 | 04:10 4-15 | 1 | 2 | 1 |
| 3 | 09:10 4-15 | 2 | 1 | 1 |
| 4 | 14:10 4-15 | 1 | 2 | 1 |
| 5 | 19:10 4-15 | 2 | 1 | 1 |
| 6 | 00:10 4-16 | 2 | 1 | 1 |
| 7 | 05:10 4-16 | 1 | 1 | 2 |
| **Total** | | **11** | **9** | **8** |

## Per-run contents

Each `run-NN_slot-X_<timestamp>/` contains:

- `prompt.md` — exact daily-review.md used
- `categories.md` — category rules used
- `config.json`, `policy.md` — config snapshot
- `observations/observations.jsonl` — observations written
- `observations/problem_areas.jsonl` — problem areas
- `observations/status.jsonl` — funnel selections
- `observations/divergence.log` — run-summary line

## Review

Walk each category directory. Compare observations across runs in the same
category. Things to look for:

- **Stable clusters**: same pattern flagged across multiple runs → real signal.
- **One-off finds**: flagged once then never again → likely sampling noise.
- **Automation vs autonomy**: does the agent reliably separate
  task-oriented ("once and for all" fix) from how-oriented (interaction
  friction)? If not, the prompt needs to make that distinction sharper.

Scheduler lives at `~/rsi-variance-runs/scheduler/fire-slot.sh`; logs at
`~/rsi-variance-runs/logs/`.

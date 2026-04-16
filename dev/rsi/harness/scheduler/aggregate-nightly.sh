#!/bin/bash
export PATH="/home/jonathan/.local/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
export HOME=/home/jonathan
# After the 4th night, aggregate variance results and write a proposal file
# that the SessionStart hook will surface.
set -e

DEV=/home/jonathan/Repos/jonathan-claude-marketplace/dev/rsi
PLUGIN=/home/jonathan/Repos/jonathan-claude-marketplace/plugins/recursive-self-improvement
RESEARCH=$DEV/research/2026-04-intent-nightly
LOGS=$DEV/harness/logs-nightly
PROPOSAL=/home/jonathan/.claude/recursive-self-improvement/proposals/2026-04-20-intent-nightly-results.md

PROMPT=$(cat <<PROMPT_END
You are the AGGREGATOR for the intent-labeled daily-review nightly variance test. Your job is to read the 4 nights × 4 subagent runs under $RESEARCH and produce one results proposal file.

Inputs:
- $RESEARCH/automation/run-*/observations/observations.jsonl (8 runs: 2 per night × 4 nights)
- $RESEARCH/wellbeing/run-*/observations/observations.jsonl  (8 runs: 2 per night × 4 nights)
- $LOGS/night-*/controller.log — controller summaries

What to produce at $PROPOSAL:

---
status: info
category: nightly-variance
date: 2026-04-20
---

## Intent-labeled prompt — 4-night variance test results

### Coverage
- Total runs: (count from dirs)
- Total observations written: N across all runs

### Per-category variance
For automation and wellbeing separately, report:
- Observation count per run (min / median / max)
- Severity distribution across runs
- Pairwise overlap: do two runs targeting the same night tend to surface the same concerns?

### Intent clustering (the whole point of the restructure)
List the distinct \`intent\` strings observed across all runs, grouped by your own read-time clustering. For each cluster:
- Cluster name (plain language)
- Member intents (verbatim)
- Observation count
- Does the clustering look sensible, or are intents phrased so differently that same-theme items fail to group?

### Failure modes
What broke? Where did observations miss the mark? Did the prompt produce consistent \`intent\` phrasing or wildly varying ones?

### Comparison to the pre-restructure run (problem_areas slug approach)
Pre-restructure result: 12+ slugs for the same theme ("dotfiles sync"), slug drift across runs. Has intent labeling improved or worsened that?

### Recommendation
One paragraph: ship, iterate, or revert.

---

Keep the whole output under ~300 lines. Be concrete. Quote example intents verbatim.
PROMPT_END
)

mkdir -p "$(dirname "$PROPOSAL")"

/home/jonathan/.local/bin/claude -p "$PROMPT" \
  --model opus \
  --permission-mode bypassPermissions \
  --allowedTools "Read,Write,Bash(ls:*),Bash(wc:*),Bash(find:*),Bash(cat:*),Glob,Grep" \
  --max-budget-usd 20 \
  > "$LOGS/aggregation.log" 2>&1

echo "aggregation finished at $(date -Iseconds)" >> "$LOGS/nightly-summary.log"

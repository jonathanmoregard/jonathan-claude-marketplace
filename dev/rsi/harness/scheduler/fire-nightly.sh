#!/bin/bash
export PATH="/home/jonathan/.local/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
export HOME=/home/jonathan
# Fires one nightly slot for intent-labeled daily-review testing:
# 4 Agent subagents in parallel via a single `claude -p` controller.
# Split: 2 automation + 2 wellbeing.
#
# Usage: fire-nightly.sh <night_num>
# Example: fire-nightly.sh 1
set -e

NIGHT=$1
AUTO_N=2
WELL_N=2

DEV=/home/jonathan/Repos/jonathan-claude-marketplace/dev/rsi
PLUGIN=/home/jonathan/Repos/jonathan-claude-marketplace/plugins/recursive-self-improvement
TEMPLATE=$DEV/harness/template
RESEARCH=$DEV/research/2026-04-intent-nightly
LOGS=$DEV/harness/logs-nightly
TS=$(date +%Y-%m-%dT%H:%M)

mkdir -p "$RESEARCH" "$LOGS"

# Build ordered task list
TASKS=()
for i in $(seq 1 $AUTO_N); do TASKS+=("automation"); done
for i in $(seq 1 $WELL_N); do TASKS+=("wellbeing");  done

# Prepare isolated state dirs for each task
TASK_DIRS=()
for idx in "${!TASKS[@]}"; do
  cat=${TASKS[$idx]}
  existing=$(ls -1 "$RESEARCH/$cat" 2>/dev/null | grep -c '^run-' || true)
  nextnum=$(printf "%02d" $((existing + 1)))
  rundir="$RESEARCH/$cat/run-${nextnum}_night-${NIGHT}_${TS}"
  mkdir -p "$rundir"
  cp "$TEMPLATE/daily-review.md" "$rundir/prompt.md"
  cp "$TEMPLATE/categories.md"   "$rundir/categories.md"
  cp "$TEMPLATE/config.json"     "$rundir/config.json"
  cp "$TEMPLATE/policy.md"       "$rundir/policy.md"
  mkdir -p "$rundir/observations"
  touch "$rundir/observations/observations.jsonl" \
        "$rundir/observations/status.jsonl" \
        "$rundir/observations/divergence.log"
  TASK_DIRS+=("$rundir")
done

# Build the controller prompt
SUBAGENT_BLOCKS=""
for idx in "${!TASKS[@]}"; do
  cat=${TASKS[$idx]}
  rundir=${TASK_DIRS[$idx]}
  SUBAGENT_BLOCKS+=$'\n\n'"SUBAGENT $((idx+1)) — category=$cat, run dir=$rundir"
done

PROMPT=$(cat <<PROMPT_END
You are the CONTROLLER for a Recursive Self-Improvement nightly variance test (intent-labeled prompt restructure). Fire exactly 4 Agent subagents IN PARALLEL (single message, multiple Agent tool_use blocks). Do not wait serially.

Each subagent is a scoped daily-review run. Instructions for EACH subagent:

- The subagent must read $PLUGIN/prompts/daily-review.md as its own prompt, but with PATH REDIRECTIONS:
    wherever the prompt says ~/.claude/recursive-self-improvement/ → use the subagent's assigned run dir (provided in its prompt).
    config files (categories.md, config.json, policy.md) live inside the run dir.
    observations/ lives inside the run dir.
- Real chat logs at ~/.claude/projects/ are read normally.
- Real settings/CLAUDE.md at ~/.claude/ are read normally.
- Bound the log-read window per Step 5 of the prompt: fill roughly half the subagent's context budget with user-driven session logs, most-recent-first. Apply the programmatic-session filter before counting toward the budget.
- SCOPE: the subagent analyzes ONLY its assigned category. Skip all others. Still do the calibration reads (prior observations, memory, existing-mitigation check) — but only write observations for its category.
- Each observation must carry an \`intent\` field per Step 7 (no \`problem_areas\`). Do NOT write to problem_areas.jsonl.
- Selection/clustering per Step 8: cluster active observations on the fly by intent similarity; select top daily_proposal_limit*3 (=6) for the status.jsonl funnel.
- Finally append a divergence.log entry.

Subagent assignments (fire all 4 in one message, each with the block below adapted):
$SUBAGENT_BLOCKS

Each subagent's prompt should end with: "Print a final summary: N observations written, breakdown by severity, and list 3 example intents you wrote."

When all 4 subagents return, print one summary line per subagent: "[cat] [rundir]: N obs written."
PROMPT_END
)

# Fire the controller
mkdir -p "$LOGS/night-$NIGHT"
echo "$PROMPT" > "$LOGS/night-$NIGHT/controller-prompt.txt"

/home/jonathan/.local/bin/claude -p "$PROMPT" \
  --model opus \
  --permission-mode bypassPermissions \
  --allowedTools "Read,Write,Edit,Bash(ls:*),Bash(du:*),Bash(grep:*),Bash(wc:*),Bash(cat:*),Bash(find:*),Glob,Grep,Agent" \
  --max-budget-usd 40 \
  > "$LOGS/night-$NIGHT/controller.log" 2>&1

echo "night-$NIGHT finished at $(date -Iseconds)" >> "$LOGS/nightly-summary.log"

#!/bin/bash
export PATH="/home/jonathan/.local/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
export HOME=/home/jonathan
# Fires one cutoff slot: dispatches a single controller `claude -p` that uses
# 4 Agent subagents to run 4 category-scoped daily-review tests in parallel.
#
# Usage: fire-slot.sh <slot_num> <auto_count> <align_count> <well_count>
# Example: fire-slot.sh 1 2 1 1
set -e

SLOT=$1
AUTO_N=$2
ALIGN_N=$3
WELL_N=$4

DEV=/home/jonathan/Repos/jonathan-claude-marketplace/dev/rsi
PLUGIN=/home/jonathan/Repos/jonathan-claude-marketplace/plugins/recursive-self-improvement
TEMPLATE=$DEV/harness/template
RESEARCH=$DEV/research/2026-04-automation-variance
LOGS=$DEV/harness/logs
TS=$(date +%Y-%m-%dT%H:%M)

# Build ordered task list: each line = "category run_dir"
TASKS=()
for i in $(seq 1 $AUTO_N);  do TASKS+=("automation"); done
for i in $(seq 1 $ALIGN_N); do TASKS+=("alignment");  done
for i in $(seq 1 $WELL_N);  do TASKS+=("wellbeing");  done

# Prepare isolated state dirs for each task (pre-create so subagents just read/write)
TASK_DIRS=()
for idx in "${!TASKS[@]}"; do
  cat=${TASKS[$idx]}
  # Next available run-NN dir for that category in research/
  existing=$(ls -1 "$RESEARCH/$cat" 2>/dev/null | grep -c '^run-' || true)
  nextnum=$(printf "%02d" $((existing + 1)))
  rundir="$RESEARCH/$cat/run-${nextnum}_slot-${SLOT}_${TS}"
  mkdir -p "$rundir"
  cp "$TEMPLATE/daily-review.md" "$rundir/prompt.md"
  cp "$TEMPLATE/categories.md" "$rundir/categories.md"
  cp "$TEMPLATE/config.json" "$rundir/config.json"
  cp "$TEMPLATE/policy.md" "$rundir/policy.md"
  # Isolated observation state
  mkdir -p "$rundir/observations"
  touch "$rundir/observations/observations.jsonl" \
        "$rundir/observations/problem_areas.jsonl" \
        "$rundir/observations/status.jsonl" \
        "$rundir/observations/divergence.log"
  TASK_DIRS+=("$rundir")
done

# Build the controller prompt. It tells a single `claude -p` to dispatch 4 Agent
# subagents in parallel, each with its own run dir + category scope.
SUBAGENT_BLOCKS=""
for idx in "${!TASKS[@]}"; do
  cat=${TASKS[$idx]}
  rundir=${TASK_DIRS[$idx]}
  SUBAGENT_BLOCKS+=$'\n\n'"SUBAGENT $((idx+1)) — category=$cat, run dir=$rundir"
done

PROMPT=$(cat <<PROMPT_END
You are the CONTROLLER for a Recursive Self-Improvement variance test. Fire exactly 4 Agent subagents IN PARALLEL (single message, multiple Agent tool_use blocks). Do not wait serially.

Each subagent is a scoped daily-review run. Instructions for EACH subagent:

- The subagent must read $PLUGIN/prompts/daily-review.md as its own prompt, but with PATH REDIRECTIONS:
    wherever the prompt says ~/.claude/recursive-self-improvement/ → use the subagent's assigned run dir (provided in its prompt).
    config files (categories.md, config.json, policy.md) live inside the run dir.
    observations/ lives inside the run dir.
- Real chat logs at ~/.claude/projects/ are read normally.
- Real settings/CLAUDE.md at ~/.claude/ are read normally.
- Window: last 30 days of logs (exclude subagents/).
- SCOPE: the subagent analyzes ONLY its assigned category. Skip all others. Still do the fold-over-seed walk, memory read, and existing-mitigation check — but only write observations for its category.
- Write observations to the run dir's observations.jsonl + problem_areas.jsonl + status.jsonl per the prompt.
- Select top daily_proposal_limit*3 (=6) for the status.jsonl funnel even though only one category is analyzed — selection picks from the full ledger within scope.
- Finally append a divergence.log entry.

Subagent assignments (fire all 4 in one message, each with the block below adapted):
$SUBAGENT_BLOCKS

Each subagent's prompt should end with: "Print a final summary: N observations written, breakdown by severity."

When all 4 subagents return, print one summary line per subagent: "[cat] [rundir]: N obs written."
PROMPT_END
)

# Fire the controller
mkdir -p "$LOGS/slot-$SLOT"
echo "$PROMPT" > "$LOGS/slot-$SLOT/controller-prompt.txt"

/home/jonathan/.local/bin/claude -p "$PROMPT" \
  --model opus \
  --permission-mode bypassPermissions \
  --allowedTools "Read,Write,Edit,Bash(ls:*),Bash(du:*),Bash(grep:*),Bash(wc:*),Bash(cat:*),Bash(find:*),Glob,Grep,Agent" \
  --max-budget-usd 40 \
  > "$LOGS/slot-$SLOT/controller.log" 2>&1

echo "slot-$SLOT finished at $(date -Iseconds)" >> "$LOGS/slot-summary.log"

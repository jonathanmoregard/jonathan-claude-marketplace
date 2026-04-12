---
name: disable-recursive-self-improvement
description: "Disable or fully uninstall the Recursive Self-Improvement loop — removes cron jobs, optionally wipes config, proposals, and prompts."
---

# Disable Recursive Self-Improvement

Stop or remove the Recursive Self-Improvement loop.

## Step 1: Ask scope

> "Do you want to:
> 1. **Pause** — remove the cron jobs only (config and proposals kept, re-run `/setup-recursive-self-improvement` to restart)
> 2. **Uninstall** — remove cron jobs, config, prompts, and the push script (proposals kept as a record)
> 3. **Uninstall + wipe** — everything above plus delete all proposals in `~/.claude/recursive-self-improvement/proposals/`"

Wait for the user's choice before proceeding.

## Step 2: Remove cron jobs (all options)

```bash
crontab -l 2>/dev/null | grep -v "# recursive-self-improvement-analysis" | crontab -
```

Confirm: "Cron jobs removed."

## Step 3: If Uninstall or Uninstall + wipe

Remove config and runtime files:

```bash
rm -rf ~/.claude/recursive-self-improvement/config/
rm -f ~/.claude/push-proposals.sh
```

## Step 4: If Uninstall + wipe

```bash
rm -rf ~/.claude/recursive-self-improvement/proposals/
```

Tell the user: "All proposals deleted."

## Step 5: Commit (Uninstall or Uninstall + wipe only)

```bash
cd ~/.claude && git add -u && git commit -m "chore: uninstall recursive self-improvement loop"
```

## Step 6: Confirm

Tell the user what was done and what remains. For Pause: "The loop is paused. Run `/setup-recursive-self-improvement` to re-enable it." For Uninstall/wipe: "Done. Re-install the plugin and run `/setup-recursive-self-improvement` to start fresh."

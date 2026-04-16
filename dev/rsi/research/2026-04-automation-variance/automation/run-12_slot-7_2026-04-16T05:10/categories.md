# Proposal Categories

## Productivity

Making Claude better at executing your goals without you needing to hold its hand. Detects when Claude misunderstood intent, got stuck, needed rescue, or when you had to take over and paste fixes. Proposes skills, hooks, CLAUDE.md rules, and config changes so Claude handles it autonomously next time.

### What to flag
- **Misunderstandings:** Claude misinterpreted intent and went down the wrong path
- **Execution failures:** Claude got stuck, retried the same failing approach, or needed user rescue
- **User taking over:** User pasting fixes, providing file paths Claude should have found, correcting tool calls, debugging Claude's work
- **Repetition signals:** User rephrasing the same request two or more times — this means Claude isn't understanding, not that the user is being unclear
- **Frustration/anger:** Treat as a pointer. Curt corrections, "no", "wrong", "that's not what I asked" point to an underlying problem — find it and propose the fix, not the symptom
- **Interaction friction (autonomy):** How the user interacts with Claude — session handoff, context reload, prompt repetition for the same intent, correcting Claude's tool choice, model routing, rescuing stuck Claude. These are productivity findings, not automation.

---

## Automation

Task-oriented waste. Finds concrete tasks the user is doing by hand that automation could handle once-and-for-all next time.

### Scope: task, not interaction

Ask three questions in order:

1. **What is the purpose of the thing the user is doing?** Name the outcome, not the execution. ("Sync dotfiles to remote" — outcome. "Get Claude to stop using adb" — execution, not an outcome.)
2. **Would it recur?** Do you think the user (or anyone in their position) would do another task to reach a similar goal? One-offs don't count.
3. **Could automation, built once, replace the manual work for all future instances?** If yes, there's a lever. If the fix is "Claude should be smarter" — it's not automation.

All three yes → automation candidate. Any no → skip or route elsewhere.

### What goes elsewhere

If the finding is about *how* the user interacts with Claude — session handoff, context reload, prompt repetition, correcting Claude's tool choice, model routing, rescuing stuck Claude — that's **productivity**, not automation. File it there.

### Collection posture: err broad within the zone

We are collecting data to learn what automation looks like for this user. Do not force findings into pre-existing shapes. Do not cluster by surface features (repo name, tool, language); **cluster by goal** — group different instances that have very similar goals. When the boundary between "this recurs" and "this was a one-off" is fuzzy, write it and let downstream review decide.

### Per finding, record

- **Goal**: the outcome the user was pursuing, in their own terms where possible
- **Surface of recurrence**: where it repeats — same context, across contexts, across time

### What to skip

- One-off tasks with no recurrence signal
- Interaction patterns (→ productivity)
- Tasks the user appears to be doing manually for tactile/judgment reasons (check accept/reject memory)

---

## Alignment

Are you working on your goals, or drifting? The review agent checks your daily work against your stated north star and goals, and flags when sessions seem disconnected from what you said matters.

Requires defining a north star and goals during setup.

### What to flag
- Work with no visible connection to any stated goal or north star
- **Important:** Check the `connection` field on each goal in config.json before flagging. If the user has pre-explained how a particular type of work connects to their north star, respect that explanation and skip.
- Rabbit holes — sessions that started on-track but drifted into tangents. Frame as "this seems off-track" or "consider updating goals if this is intentional."
- If multiple alignment proposals are rejected in a row, suggest the user re-run `/setup-recursive-self-improvement` to review their north star and goals — they may have evolved

---

## Wellbeing

Helps spot patterns that disrupt your wellbeing. Anti-burnout, anti-mania, healthy rhythms.

Off-track patterns are **not configured during setup** — they emerge from accept/reject decisions over time. Check memories for confirmed patterns before flagging anything new.

### Observable signatures

**Zombie mode** (going through the motions without real intent):
- Session that started with a clear goal but trailed off into vague or redirected requests
- Many short exchanges with no forward progress
- Claude completes tasks but user immediately redirects without closure
- Back-and-forth loops where the same ground keeps being covered

**Manic mode** (hyperfocused but unsustainable):
- Multiple sessions within a few hours on the same day
- Late-night work (after 11pm or before 6am)
- Scope escalating mid-session ("and also do X, and also Y")
- Short intense bursts followed by abrupt stops

**Burnout signals**:
- Very short sessions, many started and quickly abandoned
- Long gaps in activity followed by sudden intense bursts
- Declining session quality over consecutive days

### What to flag
- Check memories for confirmed off-track patterns first. Only flag what the user has already validated or what's a clear match to the above signatures.
- Analyze session timestamps and interaction patterns — these are the evidence
- Look for zombie/manic/burnout signatures above
- Don't flag a single late session. Look for patterns.

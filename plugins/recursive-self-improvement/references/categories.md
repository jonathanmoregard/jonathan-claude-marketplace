# Proposal Categories

## Productivity

Making Claude better at executing your goals without you needing to hold its hand. Detects when Claude misunderstood intent, got stuck, needed rescue, or when you had to take over and paste fixes. Proposes skills, hooks, CLAUDE.md rules, and config changes so Claude handles it autonomously next time.

### What to flag (daily)
- **Misunderstandings:** Claude misinterpreted intent and went down the wrong path
- **Execution failures:** Claude got stuck, retried the same failing approach, or needed user rescue
- **User taking over:** User pasting fixes, providing file paths Claude should have found, correcting tool calls, debugging Claude's work
- **Repetition signals:** User rephrasing the same request two or more times — this means Claude isn't understanding, not that the user is being unclear
- **Frustration/anger:** Treat as a pointer. Curt corrections, "no", "wrong", "that's not what I asked" point to an underlying problem — find it and propose the fix, not the symptom

### What to flag (monthly — persistent patterns only)
- **Recurring misunderstandings:** Claude repeatedly misinterpreted the same type of intent across sessions
- **Systemic execution failures:** Claude got stuck in the same way across multiple sessions
- **Persistent user rescue patterns:** User repeatedly stepping in to fix the same class of problem
- **Frustration patterns:** The same frustration signal recurring across multiple sessions — what's the root cause?

---

## Automation

Finds traces of repetitive "cleanup" work in your sessions that could be handled automatically. Things like manual memory maintenance, config reorganization, repo hygiene tasks, or anything you do more than once that a script or hook could handle.

### What to flag (daily)
- User manually doing maintenance work that follows a predictable pattern (memory cleanup, CLAUDE.md edits, config reorganization, repo hygiene)
- **Threshold:** If you'd bet money this will happen again, it's worth flagging. If it only happened once and could easily be a one-off, skip it.

### What to flag (monthly — persistent patterns only)
- Any manual task the user performed in two or more separate sessions
- Tasks that follow the same pattern across weeks — strong automation candidates
- Cleanup work that appears reliably enough that a cron job or hook would reliably catch it

---

## Alignment

Are you working on your goals, or drifting? The review agent checks your daily work against your stated north star and goals, and flags when sessions seem disconnected from what you said matters.

Requires defining a north star and goals during setup.

### What to flag (daily)
- Work with no visible connection to any stated goal or north star
- **Important:** Check the `connection` field on each goal in config.json before flagging. If the user has pre-explained how a particular type of work connects to their north star, respect that explanation and skip.
- Rabbit holes — sessions that started on-track but drifted into tangents. Frame as "this seems off-track" or "consider updating goals if this is intentional."
- If multiple alignment proposals are rejected in a row, suggest the user re-run `/setup-recursive-self-improvement` to review their north star and goals — they may have evolved

### What to flag (monthly — persistent patterns only)
- **Monthly-scale drift:** Is the user consistently spending time on work disconnected from stated goals?
- **Rabbit hole weeks:** Entire weeks spent on tangents with no connection to stated mission?
- **Goal coverage:** Are any stated goals going completely unworked? Is the user's actual focus shifting away from declared priorities?
- Same rule applies — check each goal's `connection` field before flagging

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

### What to flag (daily)
- Check memories for confirmed off-track patterns first. Only flag what the user has already validated or what's a clear match to the above signatures.
- Analyze session timestamps and interaction patterns — these are the evidence
- Look for zombie/manic/burnout signatures above
- Don't flag a single late session. Look for patterns.

### What to flag (monthly — persistent patterns only)
- **Session timing patterns:** Late-night sessions clustering in certain weeks? Breaks disappearing over the month?
- **Positive patterns worth reinforcing:** Weeks where sessions went especially well — what made them work? These are worth naming.
- Check memories for confirmed off-track patterns
- Don't introduce new off-track pattern categories without evidence the user would agree

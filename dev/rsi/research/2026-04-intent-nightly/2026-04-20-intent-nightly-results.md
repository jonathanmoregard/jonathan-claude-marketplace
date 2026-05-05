---
status: pending
category: nightly-variance
date: 2026-04-20
---

## Intent-labeled prompt — 4-night variance test results

### Coverage
- 16 runs across 4 nights × 2 categories × 2 parallel subagents
- Total observations written: **60** (automation 36, wellbeing 24)
- Per-run counts —
  - automation: 3, 3, 10, 4, 4, 5, 4, 3
  - wellbeing: 3, 1, 3, 4, 3, 3, 4, 3

### Per-category variance

**Automation**
- Obs per run: min 3, median 4, max 10
- Severity distribution: 1 critical, 6 high, 17 medium, 12 low
- The `10`-obs outlier (run-03) is one subagent that interpreted "err broad" aggressively and emitted one observation per distinct task seen in the night's logs. Partner run-04 the same night wrote 4. That's the widest pair-gap in the test.

**Wellbeing**
- Obs per run: min 1, median 3, max 4
- Severity distribution: 5 high, 13 medium, 6 low (no critical, none below low)
- Counts are much tighter than automation. Wellbeing runs converge around the same 2–4 themes per night regardless of subagent.

**Pairwise same-night overlap**

Of the shorter run's observations, how many had a clear twin in the longer run (same underlying intent, allowing for rephrasing):

| Night | Automation overlap | Wellbeing overlap |
|-------|-------------------|-------------------|
| 1 | 2/3 (whisper-writer restart loop seen by both) | 1/1 (single wellbeing obs is a subset of partner) |
| 2 | 2/4 (emulator-kill + ECC project-scope install seen by both; multi-repo sweep unique to run-04) | 2/3 (intender overnight handoff + marathon-day streak seen by both) |
| 3 | ~0/4 (almost no intent overlap — two subagents surfaced different concerns entirely) | 1/3 (22:20–23:01 intender overnight handoff referenced by both, framed differently) |
| 4 | 2/3 (Android "tour screenshots" + split-commits seen by both) | ~1/3 (concurrent-project juggling seen by both; run-07 is quantified, run-08 is today-specific) |

Takeaway: same-night subagents reliably find the strongest signals in common (the intender overnight handoff, the emulator-kill ask, the split-commits pattern, the whisper-writer restart dance). They differ most on the long tail — which "medium" items to elevate, which one-off events to include. Less variance than the pre-restructure slug run, but still real.

### Intent clustering

I read all 60 intents and grouped by hand. Clusters with >1 member, verbatim quotes:

**Cluster A — whisper-writer STT iteration loop (automation, 3 members, all Night 1)**
- "get whisper-writer dictation fast enough and accurate enough for Swedish+English use on my T550 GPU"
- "apply a whisper-writer config change and see it take effect in the running dictation service"
- "Iterate on whisper-writer voice-to-text config and code by repeatedly killing the running app and restarting it to test model/compute-type changes."
- Verdict: three slices of the same underlying loop. A reviewer would comfortably treat them as one theme.

**Cluster B — kill all Android emulators (automation, 2 members, Night 2)**
- "kill every running Android emulator on the machine (docker + native) in one command"
- "kill every running Android emulator on the machine (both docker-based and plain) to free resources"
- Verdict: nearly identical phrasing across two subagents. Clean cluster — the win case.

**Cluster C — project-scoped ECC/plugin install isolated from ~/.claude (automation, 2 members, Night 2)**
- "install the Everything-Claude-Code suite into a project-local isolated config"
- "test-drive the full Everything-Claude-Code plugin/skill suite inside one project without any of it bleeding into ~/.claude at the user level"
- Verdict: same outcome, different verbosity. Clusters fine.

**Cluster D — Android on-device / tour / emulator testing (automation, 3 members, Nights 2 & 4)**
- "test an Android app end-to-end against specs on a local Docker emulator"
- "auto-tour an Android app by driving it through every screen and capturing screenshots into a single reviewable artifact"
- "Produce a fresh set of tour screenshots of the intender Android app on demand."
- Verdict: 2 and 3 cluster tightly. 1 is adjacent (testing vs. touring). Reviewer would probably split into "tour screenshots" vs. "end-to-end test harness".

**Cluster E — split/batch uncommitted changes into logical commits (automation, 3 members, Nights 3 & 4)**
- "Batch large uncommitted piles into logical commits across my repos"
- "split a big uncommitted change into logical-unit commits (spec / infra / app) before pushing"
- "Split a batch of unrelated working-copy changes into separate commits by topic before pushing."
- Verdict: very clean cluster even across 3 runs / 2 nights. Natural-language phrasing made this obvious to read.

**Cluster F — disk / storage cleanup (automation, 3 members, Nights 2 & 3)**
- "reclaim disk space when the SSD is near-full"
- "shrink a working-copy repo that has ballooned to tens of GB because of build artifacts I don't need checked into the workspace"
- "Keep disk space in check without manual cleanup sessions"
- Verdict: 1 and 3 cluster (OS/system cleanup). 2 is per-repo artifact audit. Run-05 already called out the distinction in its own finding text.

**Cluster G — auto-reload service / auto-pull fork on push (automation, 2 members, Night 3)**
- "Auto-reload my systemd services whenever I push to the repo"
- "Keep vendored upstream forks auto-pulled with a diff for review"
- Verdict: adjacent but distinct. Loosely cluster under "keep local services current without manual touch".

**Cluster H — autodoro vs active microphone detection (automation, 2 members, Nights 3 & 4)**
- "make autodoro correctly detect when I am actively dictating, regardless of which speech-to-text app I am using"
- "Keep autodoro from firing its focus-block window while the user is actively using speech-to-text or video-meeting apps on the mic."
- Verdict: same bug, two phrasings. Clean cluster.

**Cluster I — late-night work past 23:00 (wellbeing, 4 members across all 4 nights)**
- "Ship the whisper-writer streaming rewrite so voice-to-text keystrokes feel instant." (Night 1, source sessions Apr 14 23:44→00:33)
- "Keep stacking features on the Claude harness (voice loop, date-night cron, skill scheduling, hooks) into late evenings."
- "keep hacking past 23:00 Stockholm night after night on side projects"
- "Finish in-flight work at the end of the day without spilling past 23:00 or crossing midnight." (goal-form framing of same behavior)
- Verdict: clear cluster but phrasing flips between behavior-form ("keep hacking past 23:00") and aspiration-form ("without spilling past 23:00"). Biggest clustering hazard in the wellbeing runs.

**Cluster J — autonomous overnight handoff (wellbeing, 3 members across Nights 2 & 3)**
- "Kick off a long autonomous task in the evening, close the laptop, then resume the same Claude session first thing the next morning."
- "hand off intender-app polish to an autonomous agent before going to sleep"
- "hand Claude a sprawling autonomous mandate at the end of the day and go to sleep ('while I sleep', 'don't return control', 'at least 3 hours')"
- Verdict: all three hit the same night's behavior (Apr 17 22:20–23:01 intender session) from different angles. Clean cluster.

**Cluster K — parallel/concurrent project fragmentation (wellbeing, 6 members across all 4 nights)**
- "Maintain many parallel Claude investigations (security hardening, nixos, whisper-writer, autodoro, skills review) within a single day."
- "juggle router-agent setup, Claude config tweaks, and intender work across many parallel tabs in one morning"
- "keep making progress on multiple apps (intender, router-agent, whisper-writer, jhana, nixos-config) across a single long day"
- "juggle several projects in parallel late-evening sessions on the same night"
- "Make progress across several concurrent projects without fragmenting attention."
- "Juggle several concurrent work threads on the same day (autodoro timer bugfix, Starguard security scan, general sandboxing/web-research setup, git-push-from-sandbox)."
- Verdict: biggest wellbeing cluster. All clearly same theme — session fragmentation / context-switching intensity. Clusters well despite heavy paraphrasing.

**Cluster L — marathon / multi-day-streak long workdays (wellbeing, 4 members across Nights 2, 3 & 4)**
- "Keep pushing the multi-project harness / app / voice-loop buildout without taking a rest day between intense work days."
- "keep making progress on multiple apps (intender, router-agent, whisper-writer, jhana, nixos-config) across a single long day" (also fits K)
- "Keep a sustainable daily rhythm while shipping on the current cluster of projects"
- "Maintain consecutive-day stamina without accumulating fatigue across a streak of long workdays."
- Verdict: clean cluster. Overlaps K on one member.

**Standalone wellbeing items (not clustering):** rest-intent-vs-behavior gap (Night 3), mid-session scope escalation (Night 4 run-08), same-bug-drag-across-days (Night 4 run-08). Each a distinct behavioral shape surfaced once.

### Failure modes

1. **Obs-count variance is driven by one subagent (run-03) going broad.** 10 vs. partner's 4 is the spread. Every other run fell in 3–5. If tighter counts wanted, prompt needs a soft cap.
2. **Goal-form vs. behavior-form phrasing is the main clustering hazard.** Wellbeing intents split between "keep hacking past 23:00" (behavior) and "Finish without spilling past 23:00" (goal). Both valid, but don't cluster by surface. Instruction like "phrase the intent as the behavior the user is engaging in, not the state they want" would unify this.
3. **Compound intents crowd out the core noun.** "stand up a locked-down web-research subagent (MCPs, domain allowlist, untrusted-output wrapping, git-auth plumbing)..." — short top-clause + parenthetical detail would cluster better.
4. **Night 3 automation had near-zero overlap.** Run-05 focused on adoption/setup tasks (fork-and-review, autodoro mic, dev-server-wait, repo-slim). Run-06 focused on recurring-automation (auto-reload, drift-mirror, auto-pull forks, disk-check, batch-commits). Different *kinds* of observations entirely. Most concerning result — a selection-variance bug, not a clustering bug.
5. **One wellbeing subagent (Night 1 run-02) wrote only 1 observation.** Partner wrote 3. Could be legitimate "less to surface" or a short-circuit. Worth spot-checking.

### Comparison to the pre-restructure run (problem_areas slug approach)

Pre-restructure problem: the same theme produced 12+ different slugs across runs because each subagent invented its own slug vocabulary. Impossible to roll up automatically.

Post-restructure: the same theme produces natural-language intents that a reader clusters without ambiguity. Cluster E (split/batch commits) has 3 members phrased differently —

> "Batch large uncommitted piles into logical commits across my repos"
> "split a big uncommitted change into logical-unit commits (spec / infra / app) before pushing"
> "Split a batch of unrelated working-copy changes into separate commits by topic before pushing."

— and they obviously cluster. A slug approach would have emitted `split-commits-by-topic`, `split-dotfiles-unstaged`, `split-logical-unit-commits`, which don't tell the reviewer they're the same item.

Same for the emulator-kill cluster (two near-verbatim intents), the whisper-writer restart loop (three slices of one behavior), and the autonomous-handoff wellbeing cluster.

**This is a real improvement.** The restructure did what it was meant to do: it let reviewers cluster by meaning instead of by string match. The remaining failure mode (Night 3 automation divergence) isn't a clustering failure — the two subagents produced different sets of observations, not different slugs for the same observation. That's a different problem to solve.

### Recommendation

**Ship it, and iterate on two small prompt tweaks.** The restructure delivered: same-theme items reliably cluster by reading; severity distributions are stable; overlap between paired subagents is meaningfully higher than the slug era. Two tweaks worth doing before the next run: (1) require intents in behavior-form, not goal-form, so wellbeing items stop splitting along "is doing X" vs. "wants to avoid X" lines; (2) add a soft cap of ~5 observations per run to pull in the run-03 outlier without suppressing the common 3–4 shape. Neither is urgent — current output is usable as-is — but both would tighten variance further at zero cost.

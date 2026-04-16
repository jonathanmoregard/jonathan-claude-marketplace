# Variance Analysis — RSI Daily-Review Agent

**Dataset:** 32 category-scoped runs fired across 8 cap-reset windows (2026-04-15 00:14 → 2026-04-16 05:16)
**Observations:** 114 total (61 automation, 20 alignment, 33 wellbeing)
**Analysis:** Theme-level clustering by finding content, not by `problem_areas` tag (see §1).

---

## 1. Meta-finding: `problem_areas` tagging is not self-consistent

Before reading anything else: the `problem_areas` slug is the wrong unit for clustering. The same underlying theme gets 12+ different slugs across runs.

**Example — "dotfiles sync automation" (9/12 automation runs caught it):**

| Slug | Run |
|---|---|
| `dotfiles-sync-manual` | 01 |
| `dotfiles-sync-manual-commits` | 02 (×2) |
| `dotfiles-sync-manual-trigger` | 04 |
| `manual-dotfiles-sync-commit` | 05 |
| `manual-commit-push-at-session-end` | 05 |
| `manual-dotfiles-sync` | 06 |
| `dotfiles-auto-commit` | 07 |
| `manual-dotfiles-sync-despite-cron` | 09 |
| `repeated-git-commit-push-manual` | 09 |
| `manual-dotfiles-commit-push` | 10 |
| `manual-logical-commit-grouping` | 10 |
| `manual-commit-push-cycle` | 12 |

**Implication:** Downstream deduplication in the funnel (status.jsonl → proposal selection) cannot use tag equality. It must either (a) cluster findings semantically at selection time, or (b) enforce a canonical tag vocabulary in the prompt. Today it does neither. This is itself a fix-worthy finding.

---

## 2. Observations per category

| Category | Runs | Total obs | Avg / run | Severity skew |
|---|---|---|---|---|
| automation | 12 | 61 | 5.1 | balanced (high/med/low) |
| alignment  | 10 | 20 | 2.0 | skewed low/info |
| wellbeing  | 10 | 33 | 3.3 | skewed high/medium |

**Note:** Alignment produces half as many obs per run as automation, and most are `low`/`info`. Either (a) alignment signals are genuinely subtler, or (b) the prompt is under-calibrated for this category. Worth a targeted iteration.

---

## 3. AUTOMATION — theme clusters

Ranked by cross-run detection rate. A theme caught in many runs is stable signal; a theme caught in few runs is either a weak signal or a product of prompt noise.

### 3.1 High-consensus themes (≥50% of runs)

| Theme | Runs hit | Max severity | Anchor finding |
|---|---|---|---|
| **Dotfiles sync / commit-push at session end** | 9/12 (75%) | high | User pastes the same 190-char dotfiles-sync prompt verbatim across 6+ sessions. Repo-autosync skill exists but isn't wired. Cron attempt failed on path casing. |
| **Autodoro maintenance / service reload after push** | 7/12 (58%) | medium | After autodoro edits, user manually asks Claude to reload the systemd user service. User explicitly said "actually, add onpush hook that reloads the service" — then it never got added. |
| **NixOS/Mint drift detection** | 6/12 (50%) | high | User stated "I keep doing things to mint. How can I make sure these changes are mirrored?" Multiple manual drift-analysis sessions comparing live Mint state to NixOS config. |

### 3.2 Medium-consensus themes (33–42% of runs)

| Theme | Runs hit | Max sev | Anchor finding |
|---|---|---|---|
| Disk space cleanup | 5/12 (42%) | medium | Reactive pattern: user hits ENOSPC or notices sluggishness, then asks Claude to find hogs. No monitoring. |
| Kindle udev/MTP persistence | 4/12 (33%) | medium | User: "I know you solved this problem for me before, in the earliest of days." Fix gets lost across reinstalls. |
| Artcraft build/run discovery | 4/12 (33%) | low | Three separate sessions ask "what's the command to build this project?" — CLAUDE.md build-command gap. |
| Store listing / extension release cycle (Intender) | 4/12 (33%) | medium | Manual multi-step flow: screenshot gen → zip → listing text → upload. Partly scripted, not fully automated. |

### 3.3 Lower-consensus themes (≤25% of runs)

| Theme | Runs hit | Note |
|---|---|---|
| Emulator / Android MCP setup dance | 3/12 (25%) | SessionStart hook gap for jhana. |
| Whisper / transcription model monitoring | 3/12 (25%) | User *explicitly asked* for a cron-based monitoring agent — high-intent but low detection. |
| Security audit / hardening tracker | 2/12 (17%) | Multi-session mental checklist. |

### 3.4 Singletons (caught in 1 run only)

These are the noise floor — might be real signals the other runs missed, might be over-reading:

- `run-01`: harness-bootstrap-cross-project (template for weekend-project harness)
- `run-07`: cross-system-config-sync (Mint ↔ NixOS notification sounds)
- `run-08`: manual-git-branch-housekeeping, manual-context-handoff-between-sessions, manual-store-asset-generation
- `run-11`: voice-memo-to-action-pipeline (Dropbox → TickTick via phone)

Notable: **run-08 caught 3 unique signals that no other run did.** Could mean that run was exceptionally thorough, or that it fabricated patterns the others correctly didn't see. Worth spot-checking against the source logs.

### 3.5 Automation vs Autonomy — the original question

The user set this test up to decide empirically whether "automation" should split into **task-oriented** (solve-once-for-all, cron/skill) vs **how-oriented** (reduce user↔Claude friction, hooks/memory/CLAUDE.md).

Sorting the 10 themes above by that lens:

| Theme | Task-oriented? | How-oriented? |
|---|---|---|
| Dotfiles sync | ✓ (cron) | ✓ (session-start auto-sync) |
| Autodoro reload after push | ✓ (git post-push hook) | — |
| NixOS/Mint drift | ✓ (hourly agent) | — |
| Disk cleanup | ✓ (periodic cron) | — |
| Kindle udev | ✓ (declarative NixOS module) | — |
| Artcraft build/run | — | ✓ (CLAUDE.md / SessionStart hook) |
| Store release | ✓ (release script) | — |
| Emulator MCP dance | — | ✓ (SessionStart hook) |
| Whisper model monitor | ✓ (cron) | — |
| Security tracker | — | ✓ (memory / persistent notes) |

**Read:** 7 themes are cleanly task-oriented, 3 are cleanly how-oriented, 1 is both. Dotfiles is the only dual — and that's because the user both wants a background cron AND wants Claude to auto-sync at session start.

**Recommendation:** The split has empirical support but is not balanced. The how-oriented bucket is small enough that instead of a full "autonomy" sibling category, consider a sub-lens inside automation: **"cron/skill" vs "hook/memory/CLAUDE.md"** as a selection tiebreaker — task-oriented work goes to `/review-improvements` research-brief flow, how-oriented work goes to `/update-config` style hook work.

---

## 4. ALIGNMENT — theme clusters

Only 20 observations across 10 runs. Two themes dominate:

### 4.1 Artcraft as the canonical "unlisted project" — 9/10 runs (90%)

Every run except one flagged the 3 Artcraft build/run sessions in late March as unconnected to any stated goal. This is **the most consistent detection in the whole dataset.**

- 9 different slugs (`unlisted-creative-projects`, `unlisted-creative-tooling`, `abandoned-project-starts`, `unconnected-third-party-project-work`, `unconnected-exploration`, `untracked-side-projects`, `unconnected-side-projects`, `unclear-goal-connection`, `external-tool-evaluation-drift`)
- All rated `low` severity
- Same underlying fact: 3 sessions on a third-party repo the user doesn't contribute to, no goal mapping

**This is a known false positive in disguise.** When every alignment run flags the same low-severity thing, it means the prompt is pattern-matching on "unlisted project" as the only strong alignment signal it has. Compare the richer signals that only some runs caught.

### 4.2 Meta-tooling dominance — 3/10 runs (30%)

The *actually interesting* alignment finding:

- `run-05`: 57% of sessions were meta-tooling (104/181)
- `run-06`: 45% of sessions were meta-tooling (82/182)
- `run-09`: "April 14-15 show a full shift from impact work to exclusively tooling"

Only 3/10 runs caught this. **This is the bigger alignment concern**, but the prompt under-detects it.

### 4.3 Project scatter — 2/10 runs (20%)

- `run-03`: high-breadth-low-depth (18 project contexts)
- `run-07`: daily-project-scatter (7-8 contexts per day)

Under-detected.

### 4.4 Singletons worth a look

- `run-09`: **meta-meta-work-spiral** — noticed that the RSI system has spawned a research sub-project which has spawned 9+ runs. Recursive in a concerning way. Only 1 run caught it. This is actually the sharpest alignment observation in the whole dataset.

---

## 5. WELLBEING — theme clusters

The highest-consensus category. Runs overwhelmingly converge on the same signals.

### 5.1 Universal detections (90–100% of runs)

| Theme | Runs hit | Notes |
|---|---|---|
| **Late-night work past 23:00** | 10/10 (100%) | Caught on 5 of 13 active days. Every run named this. |
| **Apr 11 as extreme marathon day** | 9/10 (90%) | 26–36 sessions (different counts!), 15+ hours, multi-project. Consistent shape, minor variance in count. |

### 5.2 Strong themes (50% of runs)

| Theme | Runs hit | Notes |
|---|---|---|
| **Multi-day intensity streak (Apr 10–14)** | 5/10 (50%) | No rest day between 4 high-intensity days. |

### 5.3 Weaker / idiosyncratic catches

- `run-01`, `run-07`: **feast-famine rhythm** — long zero-activity gaps in March (3 of 5 days off), then relentless April. Under-detected; arguably more alarming than single marathon days.
- `run-04`, `run-01`: **evening scope creep** — new project (whisper-writer) started at 22:19. Only 2 runs caught this specific pattern.
- `run-04`, `run-01`: **Autodoro silently stopped during marathon** — ironic: break-timer failed during the session that most needed it. Captured as wellbeing evidence in 2 runs.
- `run-07` only: **04:10 AM session on Apr 15** flagged as pre-dawn outlier. Since this run fired at 09:10 Apr 15, it was seeing the variance test's OWN 04:10 cron-fired session. The RSI agent is picking up its own side-effects.

---

## 6. Variance headlines

1. **Wellbeing is the most stable category.** 100% of runs agree on late-night work; 90% agree on Apr 11. Safe to trust.
2. **Automation is moderately stable.** The top 3 themes (dotfiles/autodoro/NixOS-drift) show up in 50%+ of runs. Single-run singletons are the noise floor — trust-weighted roughly to detection rate.
3. **Alignment is the least stable and the most biased.** 9/10 runs converge on a *low-severity* false positive (Artcraft) while more important signals (meta-tooling dominance 30%, tooling spiral 10%) are under-detected. The prompt needs work.
4. **Severity ratings drift.** The same dotfiles theme was rated `high` in 3 runs, `medium` in 5 runs. Same evidence, different severity. Selection-by-severity is a noisy operation right now.
5. **The agent observes its own output.** Run-07 flagged the variance test's cron-fired 04:10 session as a wellbeing concern. The RSI loop is partially self-observing; hook-fired sessions should be filtered out of the window like subagent sessions already are.
6. **`problem_areas` tags are non-canonical.** 12+ slugs for the same dotfiles theme. Downstream dedup is broken.

---

## 7. Recommended follow-ups

Ordered by impact:

1. **Canonicalize `problem_areas` vocabulary** in `daily-review.md` — either constrain to a pre-declared list, or do semantic clustering in the funnel step. Without this, the selection step cannot dedupe.
2. **Filter hook-fired / automated sessions out of the observation window** — they should not show up as wellbeing concerns (run-07's 04:10 detection).
3. **Iterate the alignment prompt.** It over-weights "unlisted project" and under-weights "meta-tooling dominance" and "tooling spiral." Consider seeding with the categories from §4.
4. **Split the automation bucket with a sub-lens, not a sibling category.** Task-oriented (cron/skill) vs how-oriented (hook/memory) — use as a tiebreaker in selection, not as a full ontology split. Evidence in §3.5.
5. **Calibrate severity.** Same evidence → variable severity. Either pin severity to objective criteria (# sessions, recency, explicit user request) or drop severity and rank by an ensemble signal.
6. **Spot-check run-08's 3 unique automation singletons** — either it caught real signals the others missed, or it hallucinated. Check against source logs.

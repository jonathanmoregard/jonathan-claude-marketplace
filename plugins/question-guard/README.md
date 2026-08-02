# Question Guard

A Claude Code plugin that detects closed questions ("did you push?", "what
did you mean by X?", "is this merged?") via a deterministic
`UserPromptSubmit` hook and injects a one-line nudge telling Claude to
answer the question instead of taking action. Stateless, regex-only, never
blocks a session.

## Why a hook and not a skill

Same rationale as corrections-loop: skills and CLAUDE.md instructions
trigger probabilistically and drift in long sessions, while a
`UserPromptSubmit` hook fires on **every** message, deterministically. A
CLAUDE.md rule against answering-by-acting already exists — this hook is
the drift-proof layer that re-injects the rule exactly when it applies,
in-band, right next to the question.

## What it does

On each message, `hooks/question-guard.py` classifies the incoming text
and, on match, prints exactly one line to stdout (which Claude Code
injects into the session context):

```
[question-guard] Closed question detected: answer it directly. Take no action and edit no files this turn unless the question explicitly requests it.
```

On no match it prints nothing. Every failure path exits 0 — the nudge
must never break a session. There are **no file writes at all**: the hook
is stateless. Classification is sub-millisecond; wall time is ~20ms
dominated by interpreter startup.

## Classifier

A message is a closed question when either:

- **(a) Opener word** — the first word (case-insensitive, after stripping
  leading whitespace/quotes; contractions normalize to their leading
  alphabetic run, so "what's" reads as "what") is one of: `did do does is
  are was were have has am what why when which who whose how`. "How come"
  is covered by plain "how".
- **(b) Trailing `?`** — the final non-whitespace character is `?`.

Exclusions (take precedence over both rules):

- **Polite imperatives** — first two words in {`can you`, `could you`,
  `would you`, `will you`}, or first word `please`. "Can you fix this?"
  is a request for action, not a question.
- **Long messages** — anything over 1500 characters. Long briefs ending
  in "?" are specs, not closed questions.

Known accepted gaps: inverted questions without an opener or trailing `?`
("the deploy finished", intended as a question) don't match; negated
openers ("don't we need a test" without `?`) don't match; "can we ship?"
matches only via the trailing `?`. All deliberate — the classifier is a
cheap deterministic net, not NLU.

## Install / Uninstall

From the marketplace:

```
/plugin install question-guard@jonathanmoregard
```

or `claude plugins install <path-or-url>` pointing at this directory. The
hook registers via `hooks/hooks.json`; no setup wizard, no configuration.

Uninstall by removing the plugin (`/plugin uninstall question-guard`).
Nothing else to clean up — the hook writes no files.

## Tests

```
cd plugins/question-guard && python3 -m unittest discover -s tests -v
```

Covers: every opener word, the trailing-`?` rule, each polite-imperative
exclusion, the 1500-char boundary (at and over the cap), leading-quote
stripping, contraction normalization, statements producing no output,
malformed stdin exiting 0 silently, exact single-line stdout on match,
and zero file writes end-to-end (sandboxed HOME stays empty).

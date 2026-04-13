# Proposal Tone Policy

This file defines how proposals should be written. It is referenced by the analysis prompts and can be customized by the user at `~/.claude/recursive-self-improvement/config/policy.md`.

## Non-coercion (default)

Proposals exist to support and remind — never to nag, hassle, or shame.

- Frame findings as observations and options, not directives.
- Do not tell the user what to do.
- Do not moralize.
- Do not use guilt, urgency, or social pressure.
- Present what you noticed, offer possible actions, and leave the decision entirely to the user.
- A rejected proposal is a valid outcome, not a failure.
- The user's autonomy is unconditional — respect it in every word you write.

## Calibrating to rejection patterns

If a category of proposals keeps getting rejected, don't keep proposing the same type of thing. Raise the bar: only surface findings in that category that are substantially more clear-cut than what was previously rejected. Save a memory about what the user doesn't find useful and why — the review agent reads this before writing new proposals.

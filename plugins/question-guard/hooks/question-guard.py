#!/usr/bin/env python3
"""UserPromptSubmit hook — nudge Claude to ANSWER closed questions.

Recurring failure mode: the user asks a closed question ("did you push?",
"what did you mean by X?", "is this merged?") and Claude takes ACTION
instead of answering. A CLAUDE.md rule exists, but instruction adherence
drifts in long sessions; a UserPromptSubmit hook fires on every prompt,
deterministically (same rationale as corrections-loop — see its README).

When the prompt classifies as a closed question, print exactly one line to
stdout. UserPromptSubmit stdout is injected into the session context, so
the nudge arrives in-band right next to the question it applies to.

Hard constraints (same discipline as corrections-loop):
- Deterministic classification only: frozensets + one regex, compiled at
  module import. NO LLM, no heuristics beyond the table below.
- Never blocks the session: every failure path exits 0.
- Stateless: NO file writes, ever. Prints one line on match, nothing
  otherwise. Typical runtime well under 10ms plus interpreter startup.
- Stdlib python3 only.

Classifier contract:
  MATCH when (a) the first word — case-insensitive, after stripping
  leading whitespace/quotes, normalized to its leading alphabetic run so
  "what's" reads as "what" — is a question opener (did/do/does/is/are/
  was/were/have/has/am/what/why/when/which/who/whose/how; "how come" is
  covered by plain "how"); OR (b) the final non-whitespace character is
  '?'.
  EXCLUDE, even when ending in '?': polite-imperative openers (first two
  words in {can you, could you, would you, will you} or first word
  "please") — those are requests for action, not questions. Also exclude
  prompts longer than 1500 chars: long briefs ending in "?" are specs,
  not closed questions.

Stdin schema (same contract as corrections-loop):
{"prompt": str, "session_id": str, "cwd": str,
 "hook_event_name": "UserPromptSubmit", ...}
"""
import json
import re
import sys

MESSAGE = (
    "[question-guard] Closed question detected: answer it directly. "
    "Take no action and edit no files this turn unless the question "
    "explicitly requests it."
)

MAX_PROMPT_CHARS = 1500

OPENERS = frozenset({
    "did", "do", "does", "is", "are", "was", "were", "have", "has", "am",
    "what", "why", "when", "which", "who", "whose", "how",
})

# Polite-imperative exclusions: two-word pairs, plus bare "please" as a
# first word. These are action requests dressed as questions.
POLITE_PAIRS = frozenset({
    ("can", "you"), ("could", "you"), ("would", "you"), ("will", "you"),
})

# Leading chars stripped before first-word extraction: whitespace plus
# ASCII and typographic quotes.
_LEADING_STRIP = " \t\r\n\v\f\"'`“”‘’"

# A "word" is a run of ASCII letters — extracting the leading run from a
# token normalizes contractions ("what's" -> "what") and sheds punctuation
# ("did," -> "did").
_WORD_RE = re.compile(r"[a-z]+")


def _first_words(text, n=2):
    """First n normalized words of already-lowercased text."""
    out = []
    for token in text.split():
        m = _WORD_RE.search(token)
        if m:
            out.append(m.group())
        if len(out) >= n:
            break
    return out


def classify(prompt):
    """True iff the prompt is a closed question per the module docstring."""
    if len(prompt) > MAX_PROMPT_CHARS:
        return False
    text = prompt.lstrip(_LEADING_STRIP).lower()
    if not text.strip():
        return False
    words = _first_words(text)
    first = words[0] if words else ""
    if first == "please" or (len(words) == 2 and tuple(words) in POLITE_PAIRS):
        return False
    if first in OPENERS:
        return True
    return text.rstrip().endswith("?")


def main():
    try:
        payload = json.load(sys.stdin)
        if not isinstance(payload, dict):
            return
        prompt = payload.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip():
            return
        if classify(prompt):
            print(MESSAGE)
    except Exception:
        # The nudge must never break the user's session. Swallow everything.
        pass


if __name__ == "__main__":
    main()
    sys.exit(0)

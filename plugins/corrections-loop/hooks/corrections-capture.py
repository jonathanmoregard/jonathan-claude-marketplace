#!/usr/bin/env python3
"""UserPromptSubmit hook — capture correction-shaped user messages to JSONL.

When the user's prompt looks like a correction ("no, not that", "stop doing
X", "wrong file", ...), append one JSON line to
~/.claude/observations/corrections.jsonl. The RSI nightly reviewer consumes
the file as a triage signal (see README, "Consuming from RSI").

Hard constraints:
- Deterministic regex classification only. NO LLM anywhere in this hook —
  anything correction-shaped that doesn't map to a specific bucket is
  recorded as "unknown" and triaged later by the nightly reviewer.
- Never blocks the session: every failure path exits 0, typical runtime
  well under 50ms (regexes compiled at import, one stdin read, one write).
- Silent: prints nothing on stdout, ever. UserPromptSubmit stdout is
  injected into the session's context; capture must be invisible.
- Stdlib python3 only.
- Capture file 0600, dir 0700 (created if missing), O_APPEND single write.

Stdin schema (same contract as other UserPromptSubmit hooks, e.g.
~/.claude/hooks/prompt-log.py): {"prompt": str, "session_id": str,
"cwd": str, "hook_event_name": "UserPromptSubmit", ...}
"""
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

EXCERPT_MAX_CHARS = 200

# Deterministic mapping table. First match wins, top to bottom — order is
# the contract: more specific patterns MUST precede broader ones that would
# shadow them (told_you_never before i_said_told). Buckets:
#   skill_misuse   — picked the wrong artifact/approach/tool
#   memory_update  — Claude lost context it already had or was given
#   behavioral     — in-session behavior the user wants changed
#   rule           — user restating a standing rule that was violated
#   preference     — soft style/workflow preference
#   unknown        — correction-shaped, no specific bucket; reviewer triages
PATTERNS = (
    ("told_you_never", re.compile(r"\bi\s+told\s+you\s+never\b", re.IGNORECASE), "rule"),
    ("not_supposed_to", re.compile(r"\byou'?re\s+not\s+supposed\s+to\b", re.IGNORECASE), "rule"),
    ("already_did", re.compile(r"\byou(?:'ve|\s+have)?\s+already\s+(?:did|tried|done)\b", re.IGNORECASE), "memory_update"),
    ("i_said_told", re.compile(r"\bi\s+(?:said|told\s+you)\b", re.IGNORECASE), "memory_update"),
    ("stop_doing", re.compile(r"\bstop\s+doing\b", re.IGNORECASE), "behavioral"),
    ("dont_do_again", re.compile(r"\b(?:don'?t|do\s+not|never)\s+do\s+that\s+again\b", re.IGNORECASE), "behavioral"),
    ("undo_revert", re.compile(r"\b(?:undo|revert)\s+that\b", re.IGNORECASE), "behavioral"),
    ("wrong_target", re.compile(r"\bwrong\s+(?:file|approach|direction|tool|command|branch)\b", re.IGNORECASE), "skill_misuse"),
    ("i_prefer", re.compile(r"\bi(?:'d|\s+would)\s+rather\b|\bi\s+prefer\b", re.IGNORECASE), "preference"),
    ("no_not_that", re.compile(r"\bno,?\s+not\s+that\b", re.IGNORECASE), "unknown"),
    ("not_what_i_asked", re.compile(r"\bnot\s+what\s+i\s+(?:asked|meant|wanted)\b", re.IGNORECASE), "unknown"),
)

# Control-char handling for excerpts: \t \n \r \v \f become a single space
# (keeps word boundaries readable), every other C0 control char and DEL is
# removed outright. Stripping runs BEFORE truncation so control chars never
# consume excerpt budget.
_CTRL_TABLE = {i: " " for i in (9, 10, 11, 12, 13)}
_CTRL_TABLE.update({i: None for i in range(32) if i not in (9, 10, 11, 12, 13)})
_CTRL_TABLE[127] = None


def classify(prompt):
    """Return (pattern_id, bucket) for the first matching pattern, else None."""
    for pattern_id, regex, bucket in PATTERNS:
        if regex.search(prompt):
            return (pattern_id, bucket)
    return None


def make_excerpt(text):
    """Strip control chars, then truncate to EXCERPT_MAX_CHARS."""
    return text.translate(_CTRL_TABLE)[:EXCERPT_MAX_CHARS]


def default_out_path():
    # Computed at call time (not import) so HOME is honored wherever set.
    return Path.home() / ".claude" / "observations" / "corrections.jsonl"


def write_entry(entry, path):
    """Append one JSONL line: dir 0700 if missing, file 0600, single
    O_APPEND write (atomic for lines this size on POSIX)."""
    line = json.dumps(entry, ensure_ascii=False) + "\n"
    prev_umask = os.umask(0o077)
    try:
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            os.write(fd, line.encode("utf-8"))
        finally:
            os.close(fd)
        # Clamp a pre-existing loose file (0o600 in os.open only applies at
        # creation time).
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
    finally:
        os.umask(prev_umask)


def main():
    try:
        payload = json.load(sys.stdin)
        if not isinstance(payload, dict):
            return
        prompt = payload.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip():
            return
        match = classify(prompt)
        if match is None:
            return
        pattern_id, bucket = match
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "session_id": str(payload.get("session_id") or ""),
            "cwd": str(payload.get("cwd") or ""),
            "bucket": bucket,
            "pattern_id": pattern_id,
            "excerpt": make_excerpt(prompt),
        }
        write_entry(entry, default_out_path())
    except Exception:
        # Capture must never break the user's session. Swallow everything.
        pass


if __name__ == "__main__":
    main()
    sys.exit(0)

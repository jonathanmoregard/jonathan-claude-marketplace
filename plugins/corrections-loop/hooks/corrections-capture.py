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

# Secret-shape redaction, ported from ~/.claude/hooks/prompt-log.py so both
# capture surfaces share one posture. Correction messages routinely quote
# the offending paste ("no, not that key, I said use sk-ant-...") — the
# excerpt must never persist the token. Order matters: structured (PEM,
# JWT) first, named vendors, semi-structured, high-entropy fallback LAST
# (skipped for cwd so long path segments survive).
SECRET_PATTERNS = (
    (re.compile(r"-----BEGIN (?:[A-Z0-9 ]*)PRIVATE KEY-----[\s\S]+?-----END (?:[A-Z0-9 ]*)PRIVATE KEY-----"), "<REDACTED:pem>"),
    (re.compile(r"eyJ[A-Za-z0-9_\-]{10,}\.eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}"), "<REDACTED:jwt>"),
    (re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}"), "<REDACTED:anthropic>"),
    (re.compile(r"sk-(?:proj-|svcacct-|admin-)?[A-Za-z0-9_\-]{20,}"), "<REDACTED:openai>"),
    (re.compile(r"(?:sk|rk|pk|whsec)_(?:live|test)_[A-Za-z0-9]{20,}"), "<REDACTED:stripe>"),
    (re.compile(r"ghp_[A-Za-z0-9]{20,}"), "<REDACTED:github-pat>"),
    (re.compile(r"gho_[A-Za-z0-9]{20,}"), "<REDACTED:github-oauth>"),
    (re.compile(r"ghs_[A-Za-z0-9]{20,}"), "<REDACTED:github-server>"),
    (re.compile(r"github_pat_[A-Za-z0-9_]{20,}"), "<REDACTED:github-fine-grained>"),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "<REDACTED:aws-access-key>"),
    (re.compile(r"ASIA[0-9A-Z]{16}"), "<REDACTED:aws-sts>"),
    (re.compile(r"AIza[0-9A-Za-z_\-]{35}"), "<REDACTED:google-api-key>"),
    (re.compile(r"xox[baprs]-[A-Za-z0-9\-]{10,}"), "<REDACTED:slack>"),
    (re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._\-]{20,}"), "Bearer <REDACTED:bearer>"),
    (re.compile(
        r"(?i)\b(?:password|passwd|secret|token|"
        r"api[_\-]?key|api[_\-]?secret|"
        r"access[_\-]?(?:key|token|secret)|"
        r"refresh[_\-]?token|"
        r"client[_\-]?(?:secret|key)|"
        r"secret[_\-]?(?:key|token|id)|"
        r"private[_\-]?key|"
        r"auth[_\-]?(?:token|key)|"
        r"bearer[_\-]?token|"
        r"session[_\-]?(?:token|key)|"
        r"db[_\-]?password|database[_\-]?url|"
        r"encryption[_\-]?key|signing[_\-]?key|master[_\-]?key|"
        r"shared[_\-]?access[_\-]?key|account[_\-]?key"
        r")['\"]?\s*[:=]\s*(?:\"[^\"\r\n]*\"|'[^'\r\n]*'|[^\s]+)"
    ), "<REDACTED:kv-secret>"),
    (re.compile(r"\b[a-z][a-z0-9+.\-]*://[^\s/@:]+:[^\s/@]+@[^\s]+"), "<REDACTED:url-userinfo>"),
    # High-entropy fallback — MUST stay last; skipped for cwd.
    (re.compile(r"\b[A-Za-z0-9+=_]{40,}\b"), "<REDACTED:high-entropy-blob>"),
)


def redact(text):
    for pat, marker in SECRET_PATTERNS:
        text = pat.sub(marker, text)
    return text

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
    """Redact secret shapes, strip control chars, then truncate.

    Redaction runs on the FULL text before truncation — truncating first
    could cut a token's tail (or a PEM END marker) and defeat the regex,
    leaking the head of a secret (same ordering rule as prompt-log.py).
    """
    return redact(text).translate(_CTRL_TABLE)[:EXCERPT_MAX_CHARS]


def _redact_cwd(text):
    for pat, marker in SECRET_PATTERNS[:-1]:
        text = pat.sub(marker, text)
    return text


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
            # cwd skips the high-entropy fallback (last pattern) so long
            # path segments survive; vendor/kv/url patterns still apply.
            "cwd": _redact_cwd(str(payload.get("cwd") or "")),
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

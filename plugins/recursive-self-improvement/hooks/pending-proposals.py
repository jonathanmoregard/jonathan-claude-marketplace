#!/usr/bin/env python3
"""SessionStart: pending improvement proposals across all category subdirs.

Two surfaces from one count (`proposal_counts.py`, shared with the
UserPromptSubmit nudge `pending-proposals-nudge.py`):

- `hookSpecificOutput.additionalContext` — the model-facing banner, every
  session start while anything is pending.
- `systemMessage` — a USER-visible notice, only when the backlog is stale
  (oldest pending item older than `proposals.notice_age_days`, default 7) or
  large (more than `proposals.notice_pending`, default 20). At most once per
  UTC day, interactive sessions only (headless `claude -p` runs neither see it
  nor spend the daily slot). State: ~/.local/state/claude/proposals-user-notice.json.

Fail-quiet: any error in the notice path drops the notice, never the banner,
and the hook always exits 0.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import proposal_counts  # noqa: E402

# Re-exported so the module keeps working as the single documented reference for
# the counting defaults.
DEFAULTS = proposal_counts.DEFAULTS
count_all_subdirs = proposal_counts.count_all_subdirs
count_selected_observations = proposal_counts.count_selected_observations
format_counts_line = proposal_counts.format_counts_line
is_configured = proposal_counts.is_configured

NOTICE_STATE_TMPL = "~/.local/state/claude/proposals-user-notice.json"
DRAIN_COMMAND = "/recursive-self-improvement:review-improvements"


def _interactive():
    return os.environ.get("CLAUDE_CODE_ENTRYPOINT", "cli") == "cli"


def _notice_already_shown(today):
    try:
        with open(os.path.expanduser(NOTICE_STATE_TMPL)) as f:
            return json.load(f).get("date") == today
    except (IOError, OSError, ValueError, TypeError, AttributeError):
        return False


def _mark_notice_shown(today):
    """Record today's notice. Returns False when the state can't be written —
    then the notice is skipped rather than repeated on every session start."""
    path = os.path.expanduser(NOTICE_STATE_TMPL)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = f"{path}.tmp{os.getpid()}"
        with open(tmp, "w") as f:
            json.dump({"date": today}, f)
        os.replace(tmp, path)
        return True
    except (IOError, OSError):
        return False


def user_notice(pending, total):
    """systemMessage text when the backlog is stale or large, else None."""
    from datetime import datetime, timezone

    if total <= 0 or not _interactive():
        return None
    cfg = proposal_counts.load_proposals_config()
    max_age = int(cfg.get("notice_age_days", DEFAULTS["notice_age_days"]))
    max_pending = int(cfg.get("notice_pending", DEFAULTS["notice_pending"]))
    now = datetime.now(timezone.utc)
    age = proposal_counts.oldest_pending_age_days(pending, now.date())
    stale = age is not None and age > max_age
    if not stale and total <= max_pending:
        return None
    today = now.strftime("%Y-%m-%d")
    if _notice_already_shown(today) or not _mark_notice_shown(today):
        return None
    noun = "proposal" if total == 1 else "proposals"
    age_part = f", oldest {age} days" if age is not None else ""
    return (
        f"RSI backlog: {total} improvement {noun} pending{age_part}. "
        f"Drain it with {DRAIN_COMMAND}"
    )


def main():
    try:
        sys.stdin.read()
    except Exception:
        pass

    if not is_configured():
        output = {
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": (
                    "The Recursive Self-Improvement plugin is installed but not yet configured. "
                    "It reviews your daily Claude chat logs and writes improvement proposals — "
                    "catching places where Claude needed hand-holding, spotting automatable work, "
                    "and nudging toward healthy digital habits. "
                    "Mention to the user that you'd like to help them streamline their recursive "
                    "improvement workflow, and ask if they're open to setting that up now. "
                    "If they agree, invoke /setup-recursive-self-improvement."
                )
            }
        }
        print(json.dumps(output))
        return

    pending = proposal_counts.pending_files_all_subdirs()
    counts = count_all_subdirs(pending)
    selected = count_selected_observations()
    counts_line = format_counts_line(counts)
    if counts_line is None and selected == 0:
        return

    pieces = []
    if counts_line:
        pieces.append(counts_line)
    if selected > 0:
        pieces.append(f"{selected} observation{'' if selected == 1 else 's'} selected for review")
    msg = "; ".join(pieces) + ". Run /review-improvements to go through them."

    output = {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": msg,
        }
    }
    try:
        notice = user_notice(pending, proposal_counts.total_pending(counts))
    except Exception:
        notice = None
    if notice:
        output["systemMessage"] = notice
    print(json.dumps(output))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)

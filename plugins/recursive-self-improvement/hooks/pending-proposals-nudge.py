#!/usr/bin/env python3
"""UserPromptSubmit nudge: surface the pending-proposal count mid-session.

The SessionStart banner fires once and is easy to scroll past in a long
session, so proposals accumulate faster than they drain. This hook re-surfaces
the same number — from the same counter, `proposal_counts.py` — while the
session is still running.

Debounce: at most once per UTC day, AND additionally whenever the pending count
has RISEN since the last fire, so a nightly batch of new proposals surfaces the
same day instead of waiting for tomorrow. A drain lowers the stored baseline
without firing, so the next rise is measured from where the queue actually is.

State: ~/.local/state/claude/proposals-nudge.json — {"date": "YYYY-MM-DD",
"count": N}. Machine-written state, deliberately NOT under ~/.claude, which is
the live config repo.

Never blocks and never errors a prompt: the whole body is wrapped, any failure
exits 0 silently, and a SIGALRM watchdog caps the run so a stalled filesystem
cannot hold up a prompt.
"""
import json
import os
import signal
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

STATE_FILE_TMPL = "~/.local/state/claude/proposals-nudge.json"
WATCHDOG_SECONDS = 5


class _Timeout(Exception):
    pass


def state_file():
    return os.path.expanduser(STATE_FILE_TMPL)


def load_state():
    """Return {"date": str|None, "count": int}. Missing/corrupt reads as fresh."""
    try:
        with open(state_file()) as f:
            raw = json.load(f)
        return {
            "date": raw.get("date"),
            "count": int(raw.get("count", 0)),
        }
    except (IOError, OSError, ValueError, TypeError, AttributeError):
        return {"date": None, "count": 0}


def save_state(date, count):
    path = state_file()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = f"{path}.tmp{os.getpid()}"
        with open(tmp, "w") as f:
            json.dump({"date": date, "count": count}, f)
        os.replace(tmp, path)
    except (IOError, OSError):
        pass


def should_fire(count, state, today):
    """At most once per UTC day, plus immediately on any rise since the last fire."""
    if count <= 0:
        return False
    if state["date"] != today:
        return True
    return count > state["count"]


def compose_context(counts, count):
    """Factual statement, not an instruction — per the hook-output guidance."""
    import proposal_counts

    line = proposal_counts.format_counts_line(counts)
    breakdown = line[len("proposals pending: "):] if line else ""
    noun = "proposal" if count == 1 else "proposals"
    return (
        f"{count} improvement {noun} pending review ({breakdown}). "
        "The /review-improvements skill walks and drains them. "
        "This is a standing count, not a request to interrupt the current task."
    )


def run():
    import proposal_counts
    from datetime import datetime, timezone

    counts = proposal_counts.count_all_subdirs()
    count = proposal_counts.total_pending(counts)
    state = load_state()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    if not should_fire(count, state, today):
        # A drain lowers the baseline so the next rise is measured from here.
        if 0 < count < state["count"] and state["date"] == today:
            save_state(today, count)
        return

    save_state(today, count)
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": compose_context(counts, count),
        }
    }))


def main():
    try:
        sys.stdin.read()
    except Exception:
        pass

    if hasattr(signal, "SIGALRM"):
        def _alarm(_signum, _frame):
            raise _Timeout()
        try:
            signal.signal(signal.SIGALRM, _alarm)
            signal.alarm(WATCHDOG_SECONDS)
        except (ValueError, OSError):
            pass

    try:
        run()
    except BaseException:
        # A nudge must never block or error a prompt.
        return 0
    finally:
        if hasattr(signal, "SIGALRM"):
            try:
                signal.alarm(0)
            except (ValueError, OSError):
                pass
    return 0


if __name__ == "__main__":
    sys.exit(main())

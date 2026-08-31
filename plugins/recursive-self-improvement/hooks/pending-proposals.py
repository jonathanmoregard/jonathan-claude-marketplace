#!/usr/bin/env python3
"""SessionStart banner: pending improvement proposals across all category subdirs.

The counting lives in `proposal_counts.py`, shared with the UserPromptSubmit
nudge (`pending-proposals-nudge.py`) — one counter, two surfaces. See that
module for the folder layout, the config keys, and the read-only legacy
fallbacks that keep pre-cutover installs working.
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


def main():
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

    counts = count_all_subdirs()
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
    print(json.dumps(output))


if __name__ == "__main__":
    main()

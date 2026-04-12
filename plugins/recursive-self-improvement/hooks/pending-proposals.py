#!/usr/bin/env python3
"""Check for pending improvement proposals and nudge the user."""
import json
import os
import re
import sys

CONFIG_FILE = os.path.expanduser("~/.claude/recursive-self-improvement/config.yml")
IMPROVEMENTS_DIR = os.path.expanduser("~/.claude/improvements")

def is_configured():
    return os.path.isfile(CONFIG_FILE)

def count_pending():
    if not os.path.isdir(IMPROVEMENTS_DIR):
        return 0
    count = 0
    for fname in os.listdir(IMPROVEMENTS_DIR):
        if not fname.endswith(".md"):
            continue
        fpath = os.path.join(IMPROVEMENTS_DIR, fname)
        try:
            with open(fpath, "r") as f:
                content = f.read(500)  # frontmatter is in the first few hundred chars
            # Look for status: pending in YAML frontmatter
            if content.startswith("---"):
                end = content.find("---", 3)
                if end != -1:
                    frontmatter = content[3:end]
                    if re.search(r"^status:\s*pending\s*$", frontmatter, re.MULTILINE):
                        count += 1
        except (IOError, OSError):
            continue
    return count

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

    pending = count_pending()
    if pending > 0:
        noun = "proposal" if pending == 1 else "proposals"
        output = {
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": f"You have {pending} pending improvement {noun}. Run /review-improvements to go through them."
            }
        }
        print(json.dumps(output))

if __name__ == "__main__":
    main()

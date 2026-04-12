#!/usr/bin/env python3
"""Check for pending improvement proposals and nudge the user."""
import json
import os
import re
import sys

IMPROVEMENTS_DIR = os.path.expanduser("~/.claude/improvements")

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

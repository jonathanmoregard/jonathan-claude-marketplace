#!/usr/bin/env python3
"""Check for pending improvement proposals and nudge the user."""
import json
import os
import re
import sys

CONFIG_FILE = os.path.expanduser("~/.claude/recursive-self-improvement/config/config.json")
IMPROVEMENTS_DIR = os.path.expanduser("~/.claude/recursive-self-improvement/proposals")
OBSERVATIONS_STATUS_FILE = os.path.expanduser("~/.claude/recursive-self-improvement/observations/status.jsonl")

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

def count_selected_observations():
    try:
        with open(OBSERVATIONS_STATUS_FILE, "r") as f:
            lines = f.readlines()
    except FileNotFoundError:
        return 0
    # For each observation_id, find the last status entry
    last_status = {}
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
            obs_id = entry.get("observation_id")
            status = entry.get("status")
            if obs_id and status:
                last_status[obs_id] = status
        except (json.JSONDecodeError, KeyError):
            continue
    return sum(1 for s in last_status.values() if s == "selected")

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
    selected = count_selected_observations()
    if pending > 0 or selected > 0:
        if pending > 0 and selected > 0:
            noun = "proposal" if pending == 1 else "proposals"
            msg = f"RSI: {pending} pending {noun}, {selected} observations for review. Run /review-improvements to go through them."
        elif pending > 0:
            noun = "proposal" if pending == 1 else "proposals"
            msg = f"RSI: {pending} pending {noun}. Run /review-improvements to go through them."
        else:
            msg = f"RSI: {selected} observations selected for review. Run /review-improvements to go through them."
        output = {
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": msg
            }
        }
        print(json.dumps(output))

if __name__ == "__main__":
    main()

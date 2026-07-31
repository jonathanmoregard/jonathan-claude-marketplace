#!/usr/bin/env python3
"""Check for pending improvement proposals across all category subdirs and nudge the user.

Layout (all configurable via ~/.claude/recursive-self-improvement/config/config.json under
the `proposals` key):

    <proposals_folder>/            (default ~/.claude/proposals)
    ├── <rsi_subdir>/              (default "rsi")  <-- status-aware (pending|open|missing)
    ├── router/                    any subdir           <-- file-existence based
    ├── clv2/                                            file-existence based
    ├── from-research/                                   file-existence based
    ├── <any_new_subdir>/                                auto-discovered
    └── README.md                                        excluded by filename pattern

Adding a new proposal source = drop a subdir at the folder root; it shows up in the
next SessionStart nudge automatically. No plugin edit needed.

Backward compatibility: if the legacy dir ~/.claude/recursive-self-improvement/proposals
exists as a real (non-symlink) directory AND the rsi_subdir isn't present in the new
folder, the legacy dir is counted as the rsi bucket. This lets the plugin keep working
on pre-migration installs.
"""
import fnmatch
import json
import os
import re
import sys

CONFIG_FILE = os.path.expanduser("~/.claude/recursive-self-improvement/config/config.json")
LEGACY_RSI_DIR = os.path.expanduser("~/.claude/recursive-self-improvement/proposals")
OBSERVATIONS_STATUS_FILE = os.path.expanduser("~/.claude/recursive-self-improvement/observations/status.jsonl")

# Defaults used when config.json lacks a `proposals` section (backward-compat path).
DEFAULTS = {
    "folder": "~/.claude/proposals",
    "rsi_subdir": "rsi",
    "pending_statuses": ["pending", "open"],
    "excluded_files": ["README*", ".*"],
    "excluded_subdirs": [".*", "archived"],
}


def is_configured():
    return os.path.isfile(CONFIG_FILE)


def load_proposals_config():
    """Return the effective proposals config, merging user overrides over DEFAULTS.

    Any missing key falls back to the default so a partial `proposals: {}` block in
    config.json still works.
    """
    cfg = dict(DEFAULTS)
    try:
        with open(CONFIG_FILE) as f:
            user_cfg = json.load(f).get("proposals") or {}
        cfg.update({k: v for k, v in user_cfg.items() if v is not None})
    except (IOError, OSError, json.JSONDecodeError):
        pass
    cfg["folder"] = os.path.expanduser(cfg["folder"])
    return cfg


def _iter_md_files(dir_path, excluded_files):
    """Yield non-hidden .md file paths at the top of `dir_path`, honoring exclude globs.

    Missing dir / permission error → yields nothing (fail-soft; hook must never break
    session startup).
    """
    try:
        entries = os.listdir(dir_path)
    except (FileNotFoundError, NotADirectoryError, PermissionError, OSError):
        return
    for fname in entries:
        if not fname.endswith(".md"):
            continue
        if any(fnmatch.fnmatch(fname, pat) for pat in excluded_files):
            continue
        fpath = os.path.join(dir_path, fname)
        if not os.path.isfile(fpath):
            continue
        yield fpath


def count_status_aware(dir_path, pending_statuses, excluded_files):
    """RSI-style count: a file is pending if its frontmatter carries a status in
    pending_statuses OR carries no `status:` line at all. Permissive on purpose —
    better to over-count and let the reviewer archive than to under-count and silently
    drop work.
    """
    if pending_statuses:
        alt = "|".join(re.escape(s) for s in pending_statuses)
        pending_re = re.compile(rf"^status:\s*(?:{alt})\s*$", re.MULTILINE)
    else:
        pending_re = None
    status_line_re = re.compile(r"^status:\s*", re.MULTILINE)

    count = 0
    for fpath in _iter_md_files(dir_path, excluded_files):
        try:
            with open(fpath) as f:
                content = f.read(2048)
        except (IOError, OSError):
            continue
        if content.startswith("---"):
            end = content.find("---", 3)
            if end == -1:
                # unterminated frontmatter — treat as pending (permissive)
                count += 1
                continue
            frontmatter = content[3:end]
            if pending_re is None or pending_re.search(frontmatter):
                count += 1
                continue
            # frontmatter present but no `status:` line — permissive
            if not status_line_re.search(frontmatter):
                count += 1
        else:
            # no frontmatter — permissive
            count += 1
    return count


def count_by_existence(dir_path, excluded_files):
    """Non-RSI subdirs: any qualifying .md file counts as pending. Drain by moving to
    archived/ or deleting."""
    return sum(1 for _ in _iter_md_files(dir_path, excluded_files))


def discover_subdirs(folder, excluded_subdirs):
    """Return sorted list of subdir names under `folder`, honoring exclude globs.

    Follows symlinks (so a symlinked category dir is fine).
    """
    try:
        entries = os.listdir(folder)
    except (FileNotFoundError, NotADirectoryError, PermissionError, OSError):
        return []
    subdirs = []
    for name in entries:
        if any(fnmatch.fnmatch(name, pat) for pat in excluded_subdirs):
            continue
        full = os.path.join(folder, name)
        if os.path.isdir(full):
            subdirs.append(name)
    return sorted(subdirs)


def count_all_subdirs():
    """Return list of (label, count) tuples, stable order with rsi first."""
    cfg = load_proposals_config()
    folder = cfg["folder"]
    rsi_sub = cfg["rsi_subdir"]
    excluded_files = list(cfg["excluded_files"])
    excluded_subdirs = list(cfg["excluded_subdirs"])
    pending_statuses = list(cfg["pending_statuses"])

    subdirs = discover_subdirs(folder, excluded_subdirs)
    rsi_dir_new = os.path.join(folder, rsi_sub)
    rsi_source = (
        rsi_dir_new if rsi_sub in subdirs
        else (LEGACY_RSI_DIR if os.path.isdir(LEGACY_RSI_DIR) else rsi_dir_new)
    )

    ordered = [rsi_sub] + [s for s in subdirs if s != rsi_sub]
    results = []
    for name in ordered:
        if name == rsi_sub:
            n = count_status_aware(rsi_source, pending_statuses, excluded_files)
        else:
            n = count_by_existence(os.path.join(folder, name), excluded_files)
        results.append((name, n))
    return results


def count_selected_observations():
    try:
        with open(OBSERVATIONS_STATUS_FILE) as f:
            lines = f.readlines()
    except (FileNotFoundError, IOError, OSError):
        return 0
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


def format_counts_line(counts):
    """Nonzero counts rendered as `label N` chunks joined by ` · `. None if all zero."""
    nonzero = [(name, n) for name, n in counts if n > 0]
    if not nonzero:
        return None
    parts = [f"{name} {n}" for name, n in nonzero]
    return "proposals pending: " + " · ".join(parts)


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

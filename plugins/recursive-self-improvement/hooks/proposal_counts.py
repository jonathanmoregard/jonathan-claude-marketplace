#!/usr/bin/env python3
"""Shared pending-proposal counter. One counter, two surfaces.

Both the SessionStart banner (``pending-proposals.py``) and the
UserPromptSubmit nudge (``pending-proposals-nudge.py``) import this module, so
the number a session sees at startup and the number it sees mid-session can
never disagree.

Layout (all configurable via ~/.claude/recursive-self-improvement/config/config.json
under the `proposals` key):

    <proposals_folder>/            (default ~/.local/state/claude-proposals)
    ├── <rsi_subdir>/              (default "rsi")  <-- status-aware (pending|open|missing)
    ├── router/                    any subdir           <-- file-existence based
    ├── clv2/                                            file-existence based
    ├── from-research/                                   file-existence based
    ├── <any_new_subdir>/                                auto-discovered
    └── README.md                                        excluded by filename pattern

Adding a new proposal source = drop a subdir at the folder root; it shows up in the
next nudge automatically. No plugin edit needed.

Path resolution is config-first and never walks a symlink to find the sink: a
reader that depends on a symlink existing is a reader that breaks silently when
it does not. `~/.claude/proposals` and `~/.claude/recursive-self-improvement/proposals`
survive only as READ-ONLY fallbacks for the window before the cutover lands:

- If the resolved folder is not a directory but `~/.claude/proposals` is, the
  legacy folder is counted instead.
- If the rsi subdir is absent from the resolved folder but the legacy dir
  `~/.claude/recursive-self-improvement/proposals` exists, that dir is counted
  as the rsi bucket.

Every path here is expanded lazily, at call time, so HOME can be redirected
(tests do exactly that).
"""
import fnmatch
import json
import os
import re

CONFIG_FILE_TMPL = "~/.claude/recursive-self-improvement/config/config.json"
LEGACY_RSI_DIR_TMPL = "~/.claude/recursive-self-improvement/proposals"
LEGACY_FOLDER_TMPL = "~/.claude/proposals"
OBSERVATIONS_STATUS_FILE_TMPL = (
    "~/.claude/recursive-self-improvement/observations/status.jsonl"
)

# Defaults used when config.json lacks a `proposals` section (backward-compat path).
DEFAULTS = {
    "folder": "~/.local/state/claude-proposals",
    "rsi_subdir": "rsi",
    "pending_statuses": ["pending", "open"],
    "excluded_files": ["README*", ".*"],
    "excluded_subdirs": [".*", "archived"],
}


def config_file():
    return os.path.expanduser(CONFIG_FILE_TMPL)


def legacy_rsi_dir():
    return os.path.expanduser(LEGACY_RSI_DIR_TMPL)


def legacy_folder():
    return os.path.expanduser(LEGACY_FOLDER_TMPL)


def observations_status_file():
    return os.path.expanduser(OBSERVATIONS_STATUS_FILE_TMPL)


def is_configured():
    return os.path.isfile(config_file())


def load_proposals_config():
    """Return the effective proposals config, merging user overrides over DEFAULTS.

    Any missing key falls back to the default so a partial `proposals: {}` block in
    config.json still works.
    """
    cfg = dict(DEFAULTS)
    try:
        with open(config_file()) as f:
            user_cfg = json.load(f).get("proposals") or {}
        cfg.update({k: v for k, v in user_cfg.items() if v is not None})
    except (IOError, OSError, json.JSONDecodeError):
        pass
    cfg["folder"] = os.path.expanduser(cfg["folder"])
    return cfg


def resolve_folder(cfg=None):
    """Resolved aggregation root, with the legacy folder as a read-only fallback."""
    cfg = cfg or load_proposals_config()
    folder = cfg["folder"]
    if not os.path.isdir(folder):
        legacy = legacy_folder()
        if os.path.isdir(legacy):
            return legacy
    return folder


def _iter_md_files(dir_path, excluded_files):
    """Yield non-hidden .md file paths at the top of `dir_path`, honoring exclude globs.

    Missing dir / permission error → yields nothing (fail-soft; these hooks must
    never break a session).
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

    `os.path.isdir` follows symlinks, so a real subdir (the sink layout) and a
    symlinked category dir (the pre-cutover layout) both qualify.
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
    folder = resolve_folder(cfg)
    rsi_sub = cfg["rsi_subdir"]
    excluded_files = list(cfg["excluded_files"])
    excluded_subdirs = list(cfg["excluded_subdirs"])
    pending_statuses = list(cfg["pending_statuses"])

    subdirs = discover_subdirs(folder, excluded_subdirs)
    rsi_dir_new = os.path.join(folder, rsi_sub)
    legacy_rsi = legacy_rsi_dir()
    rsi_source = (
        rsi_dir_new if rsi_sub in subdirs
        else (legacy_rsi if os.path.isdir(legacy_rsi) else rsi_dir_new)
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


def total_pending(counts=None):
    """Total pending across every category. The number the nudge debounces on."""
    if counts is None:
        counts = count_all_subdirs()
    return sum(n for _, n in counts)


def count_selected_observations():
    try:
        with open(observations_status_file()) as f:
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

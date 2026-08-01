#!/usr/bin/env python3
"""Central intake gate for the proposals spine.

Every unattended agent on this machine (RSI daily reviewer, permission-ledger
evaluator, router, clv2, ...) drops proposal files into subdirs of one spine
(default ~/.claude/proposals). Empirically (2026-08-01), proposers score their
own homework badly: the 03:00 RSI run produced two proposals that duplicated
code ALREADY SHIPPED — a model fallback merged in research-agent PR #19 and a
scanner auto-updater that had existed for weeks. Root cause: no grep-before-
verdict and no scorer separate from the proposer.

This gate is that separate scorer's harness (Distyl separate-scorer
discipline). Trusted-script division of labor:

  * this script (trusted, stdlib-only) does ALL filesystem writes;
  * one headless `claude` scorer per batch gets READ-ONLY tools
    (Read Grep Glob) and must return grep-cited verdicts as strict JSON.

The gate only ANNOTATES: it writes a `gate:` block into each proposal's
frontmatter (verdict + evidence + model + date) and appends to a JSONL log.
It never rejects, never deletes, never flips `status:` — the human decides in
/review-improvements, now with independent evidence in front of them.

Config lives in <spine>/gate-config.json (path overridable via
PROPOSAL_GATE_CONFIG or --config); every path and behavior has a default but
nothing is compiled in — see DEFAULTS.

Exit codes:
  0  gated everything eligible (or nothing was eligible)
  2  scorer dispatch failed (primary and fallback)
  3  scorer output unparseable or invalid — nothing gated
  4  scorer returned verdicts for only part of the batch — the returned ones
     are annotated, the rest stay ungated for the next run
"""
import argparse
import datetime
import fnmatch
import json
import os
import re
import subprocess
import sys
import tempfile

DEFAULT_CONFIG_PATH = "~/.claude/proposals/gate-config.json"

DEFAULTS = {
    # Root of the proposals spine; every proposal subdir lives directly under it.
    "spine_root": "~/.claude/proposals",
    # Explicit subdir names to walk. Empty list = auto-discover every subdir
    # under spine_root (symlinked subdirs like rsi -> legacy path are followed).
    "subdirs": [],
    "excluded_subdirs": [".*", "archived"],
    "excluded_files": ["README*", ".*"],
    "scorer": {
        "model": "claude-fable-5",       # strongest tier first ...
        "fallback_model": "opus",        # ... opus when fable is capped/absent
        "allowed_tools": "Read Grep Glob",  # read-only: the scorer never writes
        "timeout_seconds": 600,
    },
    # Where the scorer should grep for prior art, beyond the repos referenced
    # by the proposals themselves.
    "search_paths": ["~/.claude"],
    "pr_context": {
        # A proposal that mentions ~/Repos/<name> pulls that repo's recently
        # merged PR titles into the scorer's context file.
        "repo_roots": ["~/Repos"],
        # name -> path additions/overrides for repos living elsewhere.
        "extra_repos": {},
        "merged_limit": 30,
        "timeout_seconds": 30,
    },
    # Read by the review-improvements skill, not by this script: after a
    # decision on a proposal in <subdir>, run `<callback> <path> <decision>`.
    "on_decision": {},
    "gate_log": "~/.claude/proposals/gate-log.jsonl",
}

VALID_VERDICTS = ("sharp", "duplicate", "rot")
EVIDENCE_MAX = 200
REPO_REF_RE = re.compile(r"(?:~|/home/[A-Za-z0-9._-]+)/Repos/([A-Za-z0-9._-]+)")
# Candidate ids are embedded verbatim in the scorer's instruction text, so
# both path components are allowlisted: no whitespace, no newlines, nothing
# that could read as instructions to the scorer.
FILENAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,200}\.md$")
SUBDIR_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,200}$")


def log(msg):
    print(msg, flush=True)


def load_config(path):
    """Merge the user's config file over DEFAULTS (one level of nesting deep).

    A missing config file is fine — defaults apply. A present-but-broken one
    is not: better to stop than to gate against the wrong spine.
    """
    cfg = json.loads(json.dumps(DEFAULTS))  # deep copy
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as fh:
            user = json.load(fh)
        for key, value in user.items():
            if isinstance(value, dict) and isinstance(cfg.get(key), dict):
                cfg[key].update({k: v for k, v in value.items() if v is not None})
            elif value is not None:
                cfg[key] = value
    cfg["spine_root"] = os.path.expanduser(cfg["spine_root"])
    cfg["gate_log"] = os.path.expanduser(cfg["gate_log"])
    cfg["search_paths"] = [os.path.expanduser(p) for p in cfg["search_paths"]]
    pr = cfg["pr_context"]
    pr["repo_roots"] = [os.path.expanduser(p) for p in pr["repo_roots"]]
    pr["extra_repos"] = {k: os.path.expanduser(v) for k, v in pr["extra_repos"].items()}
    return cfg


def split_frontmatter(text):
    """Return (lines, closing_index) if `text` opens with a --- frontmatter
    block, else None. `lines` keeps line endings; lines[closing_index] is the
    closing --- line."""
    if not text.startswith("---"):
        return None
    lines = text.splitlines(keepends=True)
    if lines[0].strip() != "---":
        return None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return lines, i
    return None


def is_ungated_pending(text):
    parsed = split_frontmatter(text)
    if parsed is None:
        return False
    lines, closing = parsed
    fm = "".join(lines[1:closing])
    if not re.search(r"(?m)^status:\s*pending\s*$", fm):
        return False
    if re.search(r"(?m)^gate:", fm):
        return False
    return True


def find_gate_block(lines, closing):
    """(start, end) line indices of a gate: block inside the frontmatter
    (end exclusive: the block is `gate:` plus its indented children), or
    None when the frontmatter has no gate key."""
    for i in range(1, closing):
        if re.match(r"^gate:", lines[i]):
            end = i + 1
            while end < closing and re.match(r"^[ \t]+\S", lines[end]):
                end += 1
            return i, end
    return None


def parse_gate_block(lines, start, end):
    """(verdict, date) as written in the block — either may be None."""
    verdict = date = None
    for line in lines[start + 1:end]:
        m = re.match(r"^[ \t]+verdict:\s*(\S+)\s*$", line)
        if m:
            verdict = m.group(1)
        m = re.match(r"^[ \t]+date:\s*(\S+)\s*$", line)
        if m:
            date = m.group(1)
    return verdict, date


def load_gate_log_index(cfg):
    """{(qualified_file_id, date, verdict)} for every line this script has
    written to the gate log. A gate: block in a proposal only counts as real
    if it reconciles against one of these — producers write frontmatter
    wholesale, so an unreconciled block is spurious and gets re-scored."""
    index = set()
    try:
        with open(cfg["gate_log"], encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(entry, dict):
                    continue
                date = entry.get("date") or str(entry.get("ts", ""))[:10]
                index.add((entry.get("file"), date, entry.get("verdict")))
    except OSError:
        pass
    return index


def atomic_write(path, text):
    """Atomic same-directory replace, preserving the file's mode."""
    mode = os.stat(path).st_mode
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".gate-tmp-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.chmod(tmp, mode & 0o7777)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def discover_subdirs(cfg):
    root = cfg["spine_root"]
    if cfg["subdirs"]:
        names = list(cfg["subdirs"])
    else:
        try:
            names = sorted(os.listdir(root))
        except OSError:
            return []
    out = []
    for name in names:
        if any(fnmatch.fnmatch(name, pat) for pat in cfg["excluded_subdirs"]):
            continue
        if not SUBDIR_RE.match(name):
            # Subdir names become half of every candidate id embedded in the
            # scorer instruction text — same allowlist as basenames.
            log("warning: skipping subdir with nonconforming name under %s" % root)
            continue
        full = os.path.join(root, name)
        if os.path.isdir(full):  # follows symlinks (rsi is one in production)
            out.append((name, full))
    return out


def collect_candidates(cfg, repair=True):
    """([{id, path, subdir, basename, content}], [exclusion notes]) for every
    ungated pending proposal. Ids are always subdir-qualified
    (`<subdir>/<basename>`) — one scheme everywhere, including the gate log.

    A pending file carrying a gate: block is only skipped when that block
    reconciles against the gate log (qualified id + date + verdict). An
    unreconciled block is spurious (producers write frontmatter wholesale):
    it is stripped from the file (when `repair` is true) and the proposal is
    re-scored this run.
    """
    log_index = load_gate_log_index(cfg)
    candidates, excluded = [], []
    for subdir, dirpath in discover_subdirs(cfg):
        try:
            entries = sorted(os.listdir(dirpath))
        except OSError:
            continue
        for fname in entries:
            if not fname.endswith(".md"):
                continue
            if any(fnmatch.fnmatch(fname, pat) for pat in cfg["excluded_files"]):
                continue
            if not FILENAME_RE.match(fname):
                excluded.append({
                    "event": "excluded-nonconforming-filename",
                    "subdir": subdir,
                    "file": fname[:200],
                })
                continue
            fpath = os.path.join(dirpath, fname)
            if not os.path.isfile(fpath):
                continue
            try:
                with open(fpath, encoding="utf-8", errors="replace") as fh:
                    content = fh.read()
            except OSError:
                continue
            parsed = split_frontmatter(content)
            if parsed is None:
                continue
            lines, closing = parsed
            fm = "".join(lines[1:closing])
            if not re.search(r"(?m)^status:\s*pending\s*$", fm):
                continue
            qid = subdir + "/" + fname
            block = find_gate_block(lines, closing)
            if block is not None:
                verdict, bdate = parse_gate_block(lines, block[0], block[1])
                if (qid, bdate, verdict) in log_index:
                    continue  # genuinely gated by a prior run of this script
                log("warning: %s carries a gate block with no matching "
                    "gate-log line — stripping it and re-scoring" % qid)
                content = "".join(lines[:block[0]] + lines[block[1]:])
                if repair:
                    atomic_write(fpath, content)
            candidates.append({
                "id": qid,
                "path": os.path.abspath(fpath),
                "subdir": subdir,
                "basename": fname,
                "content": content,
            })
    return candidates, excluded


def infer_repos(candidates, cfg):
    """name -> checkout path for every ~/Repos/<name> reference that resolves
    to a real directory, plus configured extra_repos."""
    pr = cfg["pr_context"]
    names = set()
    for c in candidates:
        names.update(REPO_REF_RE.findall(c["content"]))
    repos = {}
    for name in sorted(names):
        for root in pr["repo_roots"]:
            path = os.path.join(root, name)
            if os.path.isdir(path):
                repos[name] = path
                break
    repos.update(pr["extra_repos"])
    return repos


def collect_pr_context(repos, cfg):
    """Write recently merged PR titles for each referenced repo to a temp file
    the scorer can Read. gh being down must never block gating — each failure
    becomes a 'pr-context unavailable' note instead."""
    pr = cfg["pr_context"]
    fd, path = tempfile.mkstemp(prefix="proposal-gate-pr-context-", suffix=".md")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write("# Recently merged PRs for repos referenced by this batch\n\n")
        if not repos:
            fh.write("No repo checkouts referenced by this batch; nothing collected.\n")
        for name, repo_path in sorted(repos.items()):
            fh.write("## %s (%s)\n\n" % (name, repo_path))
            try:
                proc = subprocess.run(
                    ["gh", "pr", "list", "--state", "merged",
                     "--limit", str(pr["merged_limit"]), "--json", "title,mergedAt"],
                    cwd=repo_path, capture_output=True, text=True,
                    timeout=pr["timeout_seconds"],
                )
                if proc.returncode == 0:
                    fh.write(proc.stdout.strip() + "\n\n")
                else:
                    fh.write("pr-context unavailable: gh exited %d (%s)\n\n"
                             % (proc.returncode, proc.stderr.strip()[:200]))
            except (OSError, subprocess.TimeoutExpired) as exc:
                fh.write("pr-context unavailable: %s\n\n" % exc)
    return path


def build_prompt(candidates, repos, context_path, cfg):
    search_paths = list(cfg["search_paths"]) + sorted(repos.values())
    listing = "\n".join("- id: %s\n  path: %s" % (c["id"], c["path"]) for c in candidates)
    return """You are the independent intake scorer for a batch of improvement proposals.
You are deliberately SEPARATE from the agents that wrote them; your job is
verification, not sympathy. Every proposal below was written by an unattended
agent and may describe work that is already done, or aimed at code that no
longer exists.

Proposals to score (Read each file):
%s

Deterministic context: recently merged PR titles for the repos these proposals
reference were pre-collected into %s — Read it first.

MANDATORY EVIDENCE RULE — for EACH proposal, before any verdict:
1. Read the proposal and extract its concrete fix keywords: function names,
   file paths, script names, flags, config keys.
2. Grep for those keywords under each of these roots:
%s
   (skills, hooks, settings, CLAUDE.md under the dot-claude root; source code
   under the repo checkouts).
3. Cross-check the merged PR titles in the context file.
A verdict without a grep/PR citation is invalid.

Verdict meanings:
- "duplicate": the proposed fix already exists — cite path:line or the merged
  PR title that shipped it.
- "rot": the proposal's premise no longer holds (the code/config it targets is
  gone or has materially changed) — cite what you found instead.
- "sharp": still valid and unimplemented — cite where you looked and found
  nothing.

Output STRICT JSON on stdout and nothing else — no prose, no code fences:
{"verdicts":[{"file":"<id>","verdict":"sharp|duplicate|rot","evidence":"<=200 chars citing path:line or PR title"}]}
Exactly one entry per proposal, using the ids exactly as listed above.
""" % (listing, context_path,
       "\n".join("   - " + p for p in search_paths))


def dispatch_scorer(prompt, cfg):
    """One headless scorer call for the whole batch; fall back once when the
    primary model is capped or unavailable. Returns (stdout, model_used)."""
    scorer = cfg["scorer"]
    models = [scorer["model"]]
    if scorer.get("fallback_model") and scorer["fallback_model"] != scorer["model"]:
        models.append(scorer["fallback_model"])
    last_err = None
    for model in models:
        cmd = ["claude", "--model", model, "--print",
               "--allowedTools", scorer["allowed_tools"], "-p", prompt]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True,
                                  timeout=scorer["timeout_seconds"])
        except (OSError, subprocess.TimeoutExpired) as exc:
            last_err = "dispatch failed for %s: %s" % (model, exc)
            log(last_err)
            continue
        if proc.returncode == 0:
            return proc.stdout, model
        last_err = "scorer exited %d for %s: %s" % (
            proc.returncode, model, (proc.stderr or proc.stdout).strip()[:300])
        log(last_err)
    log("error: all scorer dispatches failed (%s)" % last_err)
    return None, None


def parse_verdicts(stdout, candidates):
    """Strict parse of the scorer's JSON. Returns id -> (verdict, evidence) or
    None when the output is unusable (caller exits nonzero, gates nothing)."""
    text = stdout.strip()
    payload = None
    for attempt in (text, text[text.find("{"):text.rfind("}") + 1]
                    if "{" in text and "}" in text else ""):
        if not attempt:
            continue
        try:
            payload = json.loads(attempt)
            break
        except json.JSONDecodeError:
            continue
    if not isinstance(payload, dict) or not isinstance(payload.get("verdicts"), list):
        log("error: scorer output is not the required JSON shape")
        return None
    known_ids = {c["id"] for c in candidates}
    verdicts = {}
    for entry in payload["verdicts"]:
        if not isinstance(entry, dict):
            log("error: verdict entry is not an object: %r" % (entry,))
            return None
        fid = entry.get("file")
        verdict = entry.get("verdict")
        evidence = entry.get("evidence", "")
        if fid not in known_ids:
            log("error: verdict for unknown file id %r" % (fid,))
            return None
        if verdict not in VALID_VERDICTS:
            log("error: invalid verdict %r for %s (want sharp|duplicate|rot)"
                % (verdict, fid))
            return None
        if not isinstance(evidence, str):
            log("error: evidence for %s is not a string" % fid)
            return None
        verdicts[fid] = (verdict, evidence[:EVIDENCE_MAX])
    return verdicts


def annotate(candidate, verdict, evidence, model, today):
    """Insert the gate: block just before the closing --- of the frontmatter.
    Atomic write; preserves file mode. Returns the block for logging."""
    path = candidate["path"]
    with open(path, encoding="utf-8", errors="replace") as fh:
        text = fh.read()
    if not is_ungated_pending(text):
        # Changed underneath us since collection — leave it alone.
        return False
    lines, closing = split_frontmatter(text)
    block = (
        "gate:\n"
        "  verdict: %s\n"
        "  evidence: %s\n"
        "  model: %s\n"
        "  date: %s\n" % (verdict, json.dumps(evidence), model, today)
    )
    new_text = "".join(lines[:closing]) + block + "".join(lines[closing:])
    atomic_write(path, new_text)
    return True


def append_gate_log(cfg, entry):
    path = cfg["gate_log"]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, sort_keys=True) + "\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Annotate pending proposals with independent scorer verdicts.")
    parser.add_argument("--config",
                        default=os.environ.get("PROPOSAL_GATE_CONFIG",
                                               DEFAULT_CONFIG_PATH),
                        help="gate config JSON (default: %s)" % DEFAULT_CONFIG_PATH)
    parser.add_argument("--list", action="store_true",
                        help="print what would be gated, dispatch nothing")
    args = parser.parse_args(argv)

    try:
        cfg = load_config(os.path.expanduser(args.config))
    except (OSError, ValueError) as exc:
        log("error: cannot load gate config %s: %s" % (args.config, exc))
        return 1

    candidates, excluded = collect_candidates(cfg, repair=not args.list)

    if args.list:
        for note in excluded:
            log("excluded (nonconforming filename) in subdir: %s" % note["subdir"])
        for c in candidates:
            log("would gate: %s" % c["path"])
        return 0

    now = datetime.datetime.now().isoformat(timespec="seconds")
    for note in excluded:
        log("warning: excluded nonconforming filename in subdir %s (noted in gate log)"
            % note["subdir"])
        append_gate_log(cfg, dict(note, ts=now))

    if not candidates:
        log("proposal-intake-gate: nothing to gate (no ungated pending proposals under %s)"
            % cfg["spine_root"])
        return 0

    repos = infer_repos(candidates, cfg)
    context_path = collect_pr_context(repos, cfg)
    log("pr-context: %s" % context_path)

    prompt = build_prompt(candidates, repos, context_path, cfg)
    stdout, model = dispatch_scorer(prompt, cfg)
    if stdout is None:
        return 2

    verdicts = parse_verdicts(stdout, candidates)
    if verdicts is None:
        log("head of scorer output was: %r" % stdout.strip()[:300])
        log("nothing gated; rerun after fixing the scorer")
        return 3

    today = datetime.date.today().isoformat()
    gated = 0
    for c in candidates:
        if c["id"] not in verdicts:
            continue
        verdict, evidence = verdicts[c["id"]]
        if annotate(c, verdict, evidence, model, today):
            gated += 1
            append_gate_log(cfg, {
                "ts": datetime.datetime.now().isoformat(timespec="seconds"),
                "date": today,
                "file": c["id"],
                "path": c["path"],
                "subdir": c["subdir"],
                "verdict": verdict,
                "evidence": evidence,
                "model": model,
            })
            log("gated %s: %s" % (c["id"], verdict))

    missing = [c["id"] for c in candidates if c["id"] not in verdicts]
    if missing:
        log("warning: scorer returned no verdict for: %s" % ", ".join(missing))
        log("their annotations are deferred to the next run")
        return 4
    log("proposal-intake-gate: gated %d proposal(s)" % gated)
    return 0


if __name__ == "__main__":
    sys.exit(main())

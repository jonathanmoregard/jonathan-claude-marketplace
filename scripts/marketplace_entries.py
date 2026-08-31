#!/usr/bin/env python3
"""Manifest inspection helpers for reconcile-marketplace-clone.sh.

Kept separate from the shell so the comparisons are structural (parsed JSON,
order-insensitive within an entry) rather than textual. A textual check would
call a reflowed but semantically identical manifest a "foreign local change"
and abort for no reason -- and, worse, could call a genuinely different entry
"the same" because the diff hunk happened to look familiar.

Modes:
  --file P                       print "name<TAB>source" for each plugin in P
  --has-plugin NAME              stdin is a manifest; exit 0 if NAME is listed
  --explain-overlay NAME --working P --upstream-json J
                                 stdin is the HEAD manifest; print "OK" if the
                                 working manifest P is exactly HEAD plus one
                                 added entry NAME that is equal to the entry of
                                 that name in J; otherwise print why not
  --compare-before TEXT --file P  TEXT is earlier --file output; fail if any
                                 plugin vanished or changed source
"""
from __future__ import annotations

import argparse
import json
import sys


def load(text: str, label: str):
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label} is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{label} is not a JSON object")
    return data


def read(path: str):
    with open(path, encoding="utf-8") as fh:
        return load(fh.read(), path)


def entries(manifest) -> list:
    plugins = manifest.get("plugins", [])
    if not isinstance(plugins, list):
        raise ValueError("'plugins' is not a list")
    return plugins


def name_of(entry) -> str:
    return entry.get("name", "") if isinstance(entry, dict) else ""


def source_of(entry) -> str:
    src = entry.get("source", "") if isinstance(entry, dict) else ""
    return src if isinstance(src, str) else json.dumps(src, sort_keys=True)


def pairs(manifest) -> list[tuple[str, str]]:
    return [(name_of(e), source_of(e)) for e in entries(manifest)]


def mode_file(path: str) -> int:
    for name, source in pairs(read(path)):
        print(f"{name}\t{source}")
    return 0


def mode_has_plugin(name: str) -> int:
    manifest = load(sys.stdin.read(), "<stdin>")
    return 0 if any(name_of(e) == name for e in entries(manifest)) else 1


def mode_explain_overlay(name: str, working_path: str, upstream_json: str) -> int:
    """Print OK only when the working tree's edit is exactly the overlay entry."""
    try:
        head = load(sys.stdin.read(), "the HEAD manifest")
        working = read(working_path)
        upstream = load(upstream_json, "the upstream manifest")
    except (ValueError, OSError) as exc:
        print(str(exc))
        return 1

    # Everything outside the plugin list must be untouched.
    head_rest = {k: v for k, v in head.items() if k != "plugins"}
    work_rest = {k: v for k, v in working.items() if k != "plugins"}
    if head_rest != work_rest:
        print("the edit also changes manifest fields outside 'plugins':")
        for key in sorted(set(head_rest) | set(work_rest)):
            if head_rest.get(key) != work_rest.get(key):
                print(f"  {key}: {head_rest.get(key)!r} -> {work_rest.get(key)!r}")
        return 1

    head_entries = entries(head)
    work_entries = entries(working)

    added = [e for e in work_entries if name_of(e) == name]
    kept = [e for e in work_entries if name_of(e) != name]

    if len(added) != 1:
        print(f"expected exactly one added '{name}' entry, found {len(added)}")
        return 1
    if any(name_of(e) == name for e in head_entries):
        print(f"HEAD already lists '{name}' — this is not the known overlay")
        return 1
    if kept != head_entries:
        print("the edit changes entries other than the added one:")
        head_by_name = {name_of(e): e for e in head_entries}
        kept_by_name = {name_of(e): e for e in kept}
        for key in sorted(set(head_by_name) | set(kept_by_name)):
            if head_by_name.get(key) != kept_by_name.get(key):
                print(f"  {key or '<unnamed>'}: "
                      f"{json.dumps(head_by_name.get(key), sort_keys=True)}"
                      f" -> {json.dumps(kept_by_name.get(key), sort_keys=True)}")
        return 1

    upstream_entry = next(
        (e for e in entries(upstream) if name_of(e) == name), None)
    if upstream_entry is None:
        print(f"upstream does not list '{name}'")
        return 1
    if upstream_entry != added[0]:
        print(f"the local '{name}' entry differs from the one upstream, so "
              "discarding it would change what the harness resolves:")
        print(f"  local   : {json.dumps(added[0], sort_keys=True)}")
        print(f"  upstream: {json.dumps(upstream_entry, sort_keys=True)}")
        return 1

    print("OK")
    return 0


def mode_compare_before(before_text: str, path: str) -> int:
    before = {}
    for line in before_text.splitlines():
        if not line.strip():
            continue
        name, _, source = line.partition("\t")
        before[name] = source
    try:
        after = dict(pairs(read(path)))
    except (ValueError, OSError) as exc:
        print(f"  cannot read the reconciled manifest: {exc}")
        return 1

    if not before:
        print("  no pre-state captured; skipping the plugin-set comparison")
        return 0

    bad = False
    for name, source in sorted(before.items()):
        if name not in after:
            print(f"  plugin '{name}' disappeared from the manifest")
            bad = True
        elif after[name] != source:
            print(f"  plugin '{name}' changed source: {source} -> {after[name]}")
            bad = True
    if bad:
        return 1

    kept = ", ".join(sorted(before)) or "(none)"
    print(f"  plugin set preserved: {kept}")
    gained = sorted(set(after) - set(before))
    if gained:
        print(f"  gained from upstream: {', '.join(gained)}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("--file")
    ap.add_argument("--has-plugin")
    ap.add_argument("--explain-overlay")
    ap.add_argument("--working")
    ap.add_argument("--upstream-json")
    ap.add_argument("--compare-before")
    args = ap.parse_args()

    try:
        if args.has_plugin:
            return mode_has_plugin(args.has_plugin)
        if args.explain_overlay:
            if not args.working or args.upstream_json is None:
                ap.error("--explain-overlay needs --working and --upstream-json")
            return mode_explain_overlay(
                args.explain_overlay, args.working, args.upstream_json)
        if args.compare_before is not None:
            if not args.file:
                ap.error("--compare-before needs --file")
            return mode_compare_before(args.compare_before, args.file)
        if args.file:
            return mode_file(args.file)
    except (ValueError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    ap.error("nothing to do")
    return 2


if __name__ == "__main__":
    sys.exit(main())

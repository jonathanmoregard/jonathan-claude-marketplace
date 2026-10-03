#!/usr/bin/env python3
"""Scan text for prompt injection with a local classifier.

Usage:
    echo "text to scan" | python3 scan_content.py
    python3 scan_content.py --file /path/to/file.md
    python3 scan_content.py --text "inline text to scan"

Backends, first available wins:
    1. `prompt-injection-scan` on PATH: an offline ONNX classifier (ProtectAI
       deberta-v3-base-prompt-injection-v2),
       packaged declaratively in nixos-config (overlays/prompt-injection-scan.nix).
    2. LLM Guard's PromptInjection scanner, if `llm_guard` is importable.

With --json, stdout carries one JSON object instead of the echoed text:
the classifier's per-document verdict ({"verdict", "documents", "scores",
"flagged": [indices of `---`-separated documents]}), or {"verdict":
"unscanned"} on exit 2. llm-guard scores the text as a whole, so its JSON
has no "flagged" list. Exit codes do not change.

Exit codes:
    0 = clean (no injection detected)
    1 = injection detected (warning on stderr, text on stdout)
    2 = NOT scanned: no backend, or the backend failed. Callers must treat
        the text as unscanned, never as clean.

Exit 1 is also what a crashing interpreter or a native library giving up
returns, so a backend's exit 1 counts as a verdict only together with its
VERDICT line on stderr, and any unexpected error here exits 2.
"""
import argparse
import json
import shutil
import subprocess
import sys

CLASSIFIER = "prompt-injection-scan"
CLASSIFIER_TIMEOUT = 600
VERDICT = "Prompt injection detected"


AS_JSON = False


def emit(text, verdict):
    print(json.dumps(verdict) if AS_JSON else text)


def unscanned(text, why):
    print(why, file=sys.stderr)
    emit(text, {"verdict": "unscanned"})
    sys.exit(2)


def scan_with_classifier(binary, text, threshold):
    # The text goes over stdin: a single argv string is capped at 128 KiB.
    try:
        proc = subprocess.run(
            [binary, "--threshold", str(threshold)] + (["--json"] if AS_JSON else []),
            input=text, capture_output=True, text=True, errors="replace",
            timeout=CLASSIFIER_TIMEOUT,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        unscanned(text, "%s failed: %s: %s" % (CLASSIFIER, type(exc).__name__, exc))
    if proc.returncode not in (0, 1) or (proc.returncode == 1 and VERDICT not in proc.stderr):
        unscanned(text, "%s exited %d without a verdict: %s"
                  % (CLASSIFIER, proc.returncode, proc.stderr.strip()))
    if AS_JSON:
        try:
            verdict = json.loads(proc.stdout)
        except ValueError:
            verdict = None
        if not isinstance(verdict, dict):
            unscanned(text, "%s gave no JSON verdict" % CLASSIFIER)
    sys.stderr.write(proc.stderr)
    if AS_JSON:
        print(json.dumps(verdict))
    else:
        print(text)
    sys.exit(proc.returncode)


def scan_with_llm_guard(text, threshold):
    from llm_guard.input_scanners import PromptInjection
    from llm_guard.input_scanners.prompt_injection import MatchType

    scanner = PromptInjection(threshold=threshold, match_type=MatchType.FULL)
    sanitized, valid, score = scanner.scan(text)
    if valid:
        emit(text, {"verdict": "clean", "max_score": score})
        sys.exit(0)
    print(
        f"WARNING: Prompt injection detected (score={score:.2f}). "
        f"Content may contain adversarial instructions.",
        file=sys.stderr,
    )
    emit(sanitized, {"verdict": "injection", "max_score": score})
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Scan text for prompt injection")
    parser.add_argument("--file", help="Path to file to scan")
    parser.add_argument("--text", help="Inline text to scan")
    parser.add_argument("--threshold", type=float, default=0.5, help="Detection threshold (0-1)")
    parser.add_argument("--json", action="store_true",
                        help="print a JSON verdict naming flagged documents instead of the text")
    args = parser.parse_args()
    global AS_JSON
    AS_JSON = args.json

    if args.file:
        with open(args.file, "r") as f:
            text = f.read()
    elif args.text is not None:
        text = args.text
    elif not sys.stdin.isatty():
        text = sys.stdin.read()
    else:
        print("No input provided. Use --file, --text, or pipe to stdin.", file=sys.stderr)
        sys.exit(2)

    if not text.strip():
        emit(text, {"verdict": "clean", "flagged": []})
        sys.exit(0)

    binary = shutil.which(CLASSIFIER)
    if binary:
        scan_with_classifier(binary, text, args.threshold)

    try:
        scan_with_llm_guard(text, args.threshold)
    except ImportError:
        unscanned(
            text,
            "No prompt-injection scanner available: neither `%s` on PATH nor "
            "llm-guard importable. On NixOS it comes from nixos-config "
            "(overlays/prompt-injection-scan.nix); elsewhere: pip install llm-guard."
            % CLASSIFIER,
        )


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except BaseException as exc:  # noqa: BLE001 - an uncaught error would exit 1, read as "injection"
        print("scan_content: not scanned: %s: %s" % (type(exc).__name__, exc), file=sys.stderr)
        sys.exit(2)

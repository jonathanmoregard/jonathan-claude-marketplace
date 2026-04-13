#!/usr/bin/env python3
"""Scan text for prompt injection using LLM Guard.

Usage:
    echo "text to scan" | python3 scan_content.py
    python3 scan_content.py --file /path/to/file.md
    python3 scan_content.py --text "inline text to scan"

Exit codes:
    0 = clean (no injection detected)
    1 = injection detected (prints warning to stderr, sanitized text to stdout)
    2 = LLM Guard not installed (prints install instructions to stderr)
"""
import sys
import argparse

def main():
    parser = argparse.ArgumentParser(description="Scan text for prompt injection")
    parser.add_argument("--file", help="Path to file to scan")
    parser.add_argument("--text", help="Inline text to scan")
    parser.add_argument("--threshold", type=float, default=0.5, help="Detection threshold (0-1)")
    args = parser.parse_args()

    # Get input text
    if args.file:
        with open(args.file, "r") as f:
            text = f.read()
    elif args.text:
        text = args.text
    elif not sys.stdin.isatty():
        text = sys.stdin.read()
    else:
        print("No input provided. Use --file, --text, or pipe to stdin.", file=sys.stderr)
        sys.exit(2)

    if not text.strip():
        print(text)
        sys.exit(0)

    try:
        from llm_guard.input_scanners import PromptInjection
        from llm_guard.input_scanners.prompt_injection import MatchType
    except ImportError:
        print(
            "LLM Guard is not installed. Install it with: pip install llm-guard\n"
            "This is recommended for scanning web-sourced content for prompt injection.",
            file=sys.stderr,
        )
        # Fail open — print the text but exit 2 so the caller knows it wasn't scanned
        print(text)
        sys.exit(2)

    scanner = PromptInjection(threshold=args.threshold, match_type=MatchType.FULL)
    sanitized, valid, score = scanner.scan(text)

    if valid:
        print(text)
        sys.exit(0)
    else:
        print(
            f"WARNING: Prompt injection detected (score={score:.2f}). "
            f"Content may contain adversarial instructions.",
            file=sys.stderr,
        )
        print(sanitized)
        sys.exit(1)


if __name__ == "__main__":
    main()

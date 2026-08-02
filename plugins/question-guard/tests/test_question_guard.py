"""Tests for the question-guard UserPromptSubmit hook.

Two layers, mirroring corrections-loop:
- Unit tests import the hook module directly (classify).
- End-to-end tests run the hook as a subprocess with HOME pointed at a
  tmpdir, exactly as Claude Code would invoke it, and assert on exit code,
  exact stdout, and the absence of any file writes (the hook is stateless).
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HOOK_PATH = Path(__file__).resolve().parents[1] / "hooks" / "question-guard.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("question_guard", HOOK_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


MOD = _load_module()


# ---------------------------------------------------------------------------
# Unit: classifier
# ---------------------------------------------------------------------------

class TestClassify(unittest.TestCase):
    # One example per opener word, deliberately WITHOUT a trailing '?' so
    # these exercise rule (a) alone.
    OPENER_EXAMPLES = [
        ("did", "did anything land on master last night"),
        ("do", "do we have coverage for that"),
        ("does", "does the watchdog restart it"),
        ("is", "is this merged"),
        ("are", "are the tests green"),
        ("was", "was that intentional"),
        ("were", "were both branches pushed"),
        ("have", "have the docs been updated"),
        ("has", "has the PR landed"),
        ("am", "am I reading this right"),
        ("what", "what did you mean by repo-local"),
        ("why", "why was the retry removed"),
        ("when", "when does the cron fire"),
        ("which", "which branch has the fix"),
        ("who", "who wrote this module"),
        ("whose", "whose config wins here"),
        ("how", "how come the build passed locally"),
    ]

    STATEMENTS = [
        "ship it",
        "add tests for the JSONL parser",
        "looks good, merge when green",
        "the build passes locally now",
        "refactor the auth module",
        "",
        "   ",
    ]

    def test_each_opener_matches_without_question_mark(self):
        for opener, prompt in self.OPENER_EXAMPLES:
            with self.subTest(opener=opener):
                self.assertTrue(MOD.classify(prompt), f"expected match: {prompt!r}")

    def test_did_you_push_matches(self):
        self.assertTrue(MOD.classify("did you push?"))

    def test_question_mark_rule_matches_non_opener_first_word(self):
        # First word not in the opener set — only the trailing '?' fires.
        self.assertTrue(MOD.classify("ready to ship?   "))
        self.assertTrue(MOD.classify("the tests are failing on CI?"))

    def test_polite_imperatives_excluded_even_with_question_mark(self):
        for prompt in [
            "can you fix this?",
            "could you check the logs?",
            "would you rerun CI?",
            "will you open the PR?",
            "please rerun the suite?",
            "Please explain why this failed?",
        ]:
            with self.subTest(prompt=prompt):
                self.assertFalse(MOD.classify(prompt), f"expected NO match: {prompt!r}")

    def test_statements_not_matched(self):
        for prompt in self.STATEMENTS:
            with self.subTest(prompt=prompt):
                self.assertFalse(MOD.classify(prompt))

    def test_long_prompt_excluded_boundary(self):
        # Long briefs ending in '?' are specs, not closed questions.
        self.assertFalse(MOD.classify("y" * 1600 + "?"))
        self.assertFalse(MOD.classify("y" * 1500 + "?"))  # 1501 chars — over
        self.assertTrue(MOD.classify("y" * 1499 + "?"))   # 1500 chars — at cap

    def test_leading_whitespace_and_quotes_stripped(self):
        self.assertTrue(MOD.classify('  "Did you push?"'))
        self.assertTrue(MOD.classify("  'is this merged'"))
        self.assertTrue(MOD.classify("“what happened here”"))

    def test_case_insensitive(self):
        self.assertTrue(MOD.classify("DID YOU PUSH"))
        self.assertFalse(MOD.classify("CAN YOU FIX THIS?"))

    def test_contraction_first_word_normalized(self):
        # "what's" must classify via its leading alphabetic run "what".
        self.assertTrue(MOD.classify("what's the holdup"))
        self.assertTrue(MOD.classify("who's on call this week"))


# ---------------------------------------------------------------------------
# End-to-end: subprocess, HOME sandbox
# ---------------------------------------------------------------------------

def run_hook(stdin_bytes, home):
    env = {"HOME": str(home), "PATH": os.environ.get("PATH", "")}
    return subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=stdin_bytes,
        capture_output=True,
        env=env,
        timeout=30,
    )


def payload(prompt, session_id="sess-1", cwd="/tmp/proj"):
    return json.dumps(
        {
            "prompt": prompt,
            "session_id": session_id,
            "cwd": cwd,
            "hook_event_name": "UserPromptSubmit",
        }
    ).encode()


class TestEndToEnd(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.home = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _assert_no_writes(self):
        # The hook is stateless — nothing may appear under the sandbox HOME.
        self.assertEqual(list(self.home.rglob("*")), [])

    def test_match_prints_exactly_one_line_exit_zero(self):
        proc = run_hook(payload("did you push?"), self.home)
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout.decode(), MOD.MESSAGE + "\n")
        self.assertEqual(proc.stderr, b"")
        self._assert_no_writes()

    def test_no_match_silent_exit_zero(self):
        proc = run_hook(payload("add tests for the parser"), self.home)
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout, b"")
        self.assertEqual(proc.stderr, b"")
        self._assert_no_writes()

    def test_polite_imperative_silent_end_to_end(self):
        proc = run_hook(payload("can you fix this?"), self.home)
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout, b"")
        self._assert_no_writes()

    def test_malformed_stdin_exits_zero_silent(self):
        for bad in [b"not json {{{", b"", b"[1,2,3]", b'"just a string"', b'{"prompt": 42}']:
            with self.subTest(stdin=bad):
                proc = run_hook(bad, self.home)
                self.assertEqual(proc.returncode, 0)
                self.assertEqual(proc.stdout, b"")
                self._assert_no_writes()


if __name__ == "__main__":
    unittest.main()

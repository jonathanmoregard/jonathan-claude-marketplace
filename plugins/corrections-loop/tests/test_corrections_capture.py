"""Tests for the corrections-capture UserPromptSubmit hook.

Two layers:
- Unit tests import the hook module directly (classify / make_excerpt).
- End-to-end tests run the hook as a subprocess with HOME pointed at a
  tmpdir, exactly as Claude Code would invoke it, and assert on the JSONL
  file, permissions, exit code, and (empty) stdout.
"""
import importlib.util
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HOOK_PATH = Path(__file__).resolve().parents[1] / "hooks" / "corrections-capture.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("corrections_capture", HOOK_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


MOD = _load_module()


# ---------------------------------------------------------------------------
# Unit: classification table
# ---------------------------------------------------------------------------

class TestClassify(unittest.TestCase):
    # (prompt, expected_pattern_id, expected_bucket) — one example per pattern.
    EXAMPLES = [
        ("I told you never to force push", "told_you_never", "rule"),
        ("you're not supposed to touch settings.json", "not_supposed_to", "rule"),
        ("You already tried that fix two turns ago", "already_did", "memory_update"),
        ("you've already done the migration", "already_did", "memory_update"),
        ("I said use the staging database", "i_said_told", "memory_update"),
        ("I told you the port is 8080", "i_said_told", "memory_update"),
        ("stop doing a full rebuild every time", "stop_doing", "behavioral"),
        ("don't do that again please", "dont_do_again", "behavioral"),
        ("undo that last edit", "undo_revert", "behavioral"),
        ("revert that change to the parser", "undo_revert", "behavioral"),
        ("wrong file - I meant the one under hooks/", "wrong_target", "skill_misuse"),
        ("that's the wrong approach entirely", "wrong_target", "skill_misuse"),
        ("Wrong direction, go back to the plan", "wrong_target", "skill_misuse"),
        ("I'd rather you kept the commits small", "i_prefer", "preference"),
        ("I prefer tabs over spaces here", "i_prefer", "preference"),
        ("No, not that one - the other config", "no_not_that", "unknown"),
        ("no not that", "no_not_that", "unknown"),
        ("that's not what I asked for", "not_what_i_asked", "unknown"),
        ("this is not what I meant at all", "not_what_i_asked", "unknown"),
    ]

    NON_CORRECTIONS = [
        "please refactor the auth module",
        "what does this function do?",
        "add tests for the JSONL parser",
        "looks good, ship it",
        "can you summarize the design doc",
        "the wrongdoing described in the article is unrelated",
        "run the suite and paste the output",
        "",
        "   ",
    ]

    def test_each_pattern_classifies_its_example(self):
        for prompt, want_id, want_bucket in self.EXAMPLES:
            with self.subTest(prompt=prompt):
                got = MOD.classify(prompt)
                self.assertIsNotNone(got, f"expected a match for: {prompt!r}")
                self.assertEqual(got, (want_id, want_bucket))

    def test_case_insensitive(self):
        self.assertEqual(MOD.classify("STOP DOING THAT"), ("stop_doing", "behavioral"))
        self.assertEqual(MOD.classify("WRONG FILE"), ("wrong_target", "skill_misuse"))

    def test_non_corrections_do_not_match(self):
        for prompt in self.NON_CORRECTIONS:
            with self.subTest(prompt=prompt):
                self.assertIsNone(MOD.classify(prompt))

    def test_precedence_specific_rule_beats_generic_told(self):
        # "I told you never ..." contains "I told you" — the more specific
        # rule-bucket pattern must win (table order is the contract).
        got = MOD.classify("I told you never to edit files in ~/.claude/hooks")
        self.assertEqual(got, ("told_you_never", "rule"))

    def test_every_bucket_is_reachable(self):
        buckets = {bucket for _, _, bucket in MOD.PATTERNS}
        self.assertEqual(
            buckets,
            {"skill_misuse", "memory_update", "behavioral", "rule", "preference", "unknown"},
        )


# ---------------------------------------------------------------------------
# Unit: excerpt hygiene
# ---------------------------------------------------------------------------

class TestExcerpt(unittest.TestCase):
    def test_truncates_to_200_chars(self):
        long = "stop doing that " + "x" * 500
        excerpt = MOD.make_excerpt(long)
        self.assertEqual(len(excerpt), 200)
        self.assertTrue(excerpt.startswith("stop doing that "))

    def test_short_text_untouched(self):
        self.assertEqual(MOD.make_excerpt("wrong file"), "wrong file")

    def test_control_chars_stripped(self):
        raw = "fix\x00this\x07now\nplease\ttab\r\x1b[31mred\x7f"
        excerpt = MOD.make_excerpt(raw)
        for ch in excerpt:
            self.assertGreaterEqual(ord(ch), 32, f"control char survived: {ord(ch)}")
            self.assertNotEqual(ord(ch), 127)
        # newline/tab/cr become spaces (readability); other control chars vanish
        self.assertEqual(excerpt, "fixthisnow please tab [31mred")

    def test_strip_happens_before_truncation(self):
        # 200 chars of payload preceded by control chars: after stripping,
        # the full payload must fit — stripping first means control chars
        # don't eat the budget.
        raw = "\x00" * 50 + "y" * 200
        self.assertEqual(MOD.make_excerpt(raw), "y" * 200)


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
        self.out = self.home / ".claude" / "observations" / "corrections.jsonl"

    def tearDown(self):
        self._tmp.cleanup()

    def test_match_writes_one_schema_correct_line(self):
        proc = run_hook(payload("stop doing full rebuilds"), self.home)
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout, b"")
        lines = self.out.read_text().splitlines()
        self.assertEqual(len(lines), 1)
        entry = json.loads(lines[0])
        self.assertEqual(
            list(entry.keys()),
            ["ts", "session_id", "cwd", "bucket", "pattern_id", "excerpt"],
        )
        self.assertEqual(entry["session_id"], "sess-1")
        self.assertEqual(entry["cwd"], "/tmp/proj")
        self.assertEqual(entry["bucket"], "behavioral")
        self.assertEqual(entry["pattern_id"], "stop_doing")
        self.assertEqual(entry["excerpt"], "stop doing full rebuilds")

    def test_no_match_no_write_silent_exit_zero(self):
        proc = run_hook(payload("please add a test for the parser"), self.home)
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout, b"")
        self.assertFalse(self.out.exists())

    def test_malformed_stdin_exits_zero_no_write(self):
        for bad in [b"not json {{{", b"", b"[1,2,3]", b'"just a string"', b'{"prompt": 42}']:
            with self.subTest(stdin=bad):
                proc = run_hook(bad, self.home)
                self.assertEqual(proc.returncode, 0)
                self.assertEqual(proc.stdout, b"")
                self.assertFalse(self.out.exists())

    def test_file_mode_0600_dir_mode_0700(self):
        run_hook(payload("wrong file"), self.home)
        file_mode = stat.S_IMODE(self.out.stat().st_mode)
        dir_mode = stat.S_IMODE(self.out.parent.stat().st_mode)
        self.assertEqual(file_mode, 0o600)
        self.assertEqual(dir_mode, 0o700)

    def test_idempotent_dir_creation_and_append(self):
        # Dir pre-exists (created by first run) — second run must append,
        # not fail or truncate.
        p1 = run_hook(payload("undo that edit"), self.home)
        p2 = run_hook(payload("no, not that one"), self.home)
        self.assertEqual((p1.returncode, p2.returncode), (0, 0))
        lines = self.out.read_text().splitlines()
        self.assertEqual(len(lines), 2)
        self.assertEqual(json.loads(lines[0])["pattern_id"], "undo_revert")
        self.assertEqual(json.loads(lines[1])["pattern_id"], "no_not_that")

    def test_precreated_dir_is_fine(self):
        self.out.parent.mkdir(mode=0o700, parents=True)
        proc = run_hook(payload("revert that commit"), self.home)
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(len(self.out.read_text().splitlines()), 1)

    def test_excerpt_truncated_and_control_stripped_end_to_end(self):
        raw = "stop doing\x00 this\n" + "z" * 400
        run_hook(payload(raw), self.home)
        entry = json.loads(self.out.read_text().splitlines()[0])
        self.assertEqual(len(entry["excerpt"]), 200)
        self.assertNotIn("\x00", entry["excerpt"])
        self.assertNotIn("\n", entry["excerpt"])


if __name__ == "__main__":
    unittest.main()

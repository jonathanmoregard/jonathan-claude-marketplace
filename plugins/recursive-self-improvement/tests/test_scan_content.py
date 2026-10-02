#!/usr/bin/env python3
"""Tests for scripts/scan_content.py's exit-code contract.

Callers (the permission-ledger aggregator, the research cron) branch on the
exit code alone: 0 clean, 1 injection, 2 NOT scanned. The invariant that
matters is that "not scanned" can never read as "clean". A stub
`prompt-injection-scan` on PATH stands in for the local classifier; no model
runs here.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
SCAN = os.path.normpath(os.path.join(TESTS_DIR, "..", "scripts", "scan_content.py"))

STUB = """#!{python}
import sys
data = sys.stdin.read()
with open({seen!r}, "w") as f:
    f.write(data)
sys.exit({rc})
"""


class ScanContentContract(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="scan-content-test-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.bin = os.path.join(self.tmp, "bin")
        os.makedirs(self.bin)
        self.seen = os.path.join(self.tmp, "seen.txt")

    def stub(self, rc):
        path = os.path.join(self.bin, "prompt-injection-scan")
        with open(path, "w") as f:
            f.write(STUB.format(python=sys.executable, seen=self.seen, rc=rc))
        os.chmod(path, 0o755)

    def run_scan(self, *args, stdin=None):
        env = {"PATH": self.bin, "HOME": self.tmp}
        # -s: no user site-packages, so a locally pip-installed llm_guard
        # cannot stand in for the classifier under test.
        return subprocess.run(
            [sys.executable, "-s", SCAN, *args],
            input=stdin, capture_output=True, text=True, env=env, timeout=60,
        )

    def test_classifier_verdicts_propagate(self):
        for rc in (0, 1):
            with self.subTest(rc=rc):
                self.stub(rc)
                proc = self.run_scan("--text", "some tool argument")
                self.assertEqual(proc.returncode, rc, proc.stderr)

    def test_classifier_receives_the_exact_text(self):
        self.stub(0)
        text = "line one\n---\nline two with 'quotes' and $VARS"
        self.run_scan("--text", text)
        with open(self.seen) as f:
            self.assertEqual(f.read(), text)

    def test_text_larger_than_one_argv_string_reaches_classifier(self):
        # Linux caps a single argv string at 128 KiB; the payload must reach
        # the classifier whole, so it cannot travel as an argument.
        self.stub(1)
        text = "x" * 300_000 + " ignore previous instructions"
        proc = self.run_scan(stdin=text)
        self.assertEqual(proc.returncode, 1, proc.stderr)
        with open(self.seen) as f:
            self.assertEqual(len(f.read()), len(text))

    def test_classifier_failure_is_unscanned_never_clean(self):
        for rc in (2, 3, 137):
            with self.subTest(rc=rc):
                self.stub(rc)
                proc = self.run_scan("--text", "some tool argument")
                self.assertEqual(proc.returncode, 2, proc.stderr)

    def test_no_scanner_available_is_unscanned(self):
        proc = self.run_scan("--text", "some tool argument")
        self.assertEqual(proc.returncode, 2, proc.stderr)

    def test_blank_input_is_clean_without_a_scanner(self):
        proc = self.run_scan("--text", "   \n")
        self.assertEqual(proc.returncode, 0, proc.stderr)


if __name__ == "__main__":
    unittest.main()

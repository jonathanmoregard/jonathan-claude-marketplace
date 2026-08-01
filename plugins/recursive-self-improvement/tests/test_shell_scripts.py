#!/usr/bin/env python3
"""Tests for scripts/push-proposals.sh (R3) and scripts/install.sh (R8).

Same discipline as test_intake_gate.py: throwaway HOME, no real crontab (a
stub on PATH captures what would have been installed), no network. git is
real but confined to the fixture repo via the overridden HOME.
"""
import os
import stat
import subprocess
import tempfile
import shutil
import unittest

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.normpath(os.path.join(TESTS_DIR, "..", "scripts"))
PLUGIN_ROOT = os.path.normpath(os.path.join(TESTS_DIR, ".."))
PUSH = os.path.join(SCRIPTS, "push-proposals.sh")
INSTALL = os.path.join(SCRIPTS, "install.sh")

CRONTAB_STUB = """#!/usr/bin/env bash
# Captures crontab writes; never touches the real user crontab.
if [[ "${1:-}" == "-l" ]]; then
  cat "$CRON_STATE" 2>/dev/null
  exit 0
fi
cat > "$CRON_STATE"
"""


class ShellHarness(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="shell-script-test-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.home = os.path.join(self.tmp, "home")
        self.claude = os.path.join(self.home, ".claude")
        os.makedirs(self.claude)
        self.bin_dir = os.path.join(self.tmp, "bin")
        os.makedirs(self.bin_dir)
        crontab = os.path.join(self.bin_dir, "crontab")
        with open(crontab, "w", encoding="utf-8") as fh:
            fh.write(CRONTAB_STUB)
        os.chmod(crontab, 0o755)

    def git(self, *args):
        return subprocess.run(["git", "-C", self.claude] + list(args),
                              capture_output=True, text=True, check=True,
                              env=self.env()).stdout

    def env(self, **extra):
        env = dict(os.environ)
        env["HOME"] = self.home
        env["PATH"] = self.bin_dir + os.pathsep + env.get("PATH", "")
        env["CRON_STATE"] = os.path.join(self.tmp, "cron-state")
        env.pop("PROPOSAL_GATE_ALLOW_MISSING", None)
        env.update(extra)
        return env

    def init_claude_repo(self):
        subprocess.run(["git", "init", "-q", self.claude], check=True,
                       capture_output=True, env=self.env())
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "user.name", "Test")
        for rel in ("recursive-self-improvement/proposals/seed.md",
                    "proposals/seed.md"):
            path = os.path.join(self.claude, rel)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("seed\n")
        # Production layout: proposals/rsi is a symlink to the legacy dir
        # (install.sh: ln -sfn). push-proposals.sh asserts this before gating.
        os.symlink(os.path.join(self.claude, "recursive-self-improvement", "proposals"),
                   os.path.join(self.claude, "proposals", "rsi"))
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "seed")

    def run_script(self, script, *args, **env_extra):
        return subprocess.run(["bash", script] + list(args),
                              capture_output=True, text=True,
                              env=self.env(**env_extra), cwd=self.tmp,
                              timeout=120)


class TestPushProposalsGateEnforcement(ShellHarness):
    """R3: a missing gate script is a hard stop, not a warn-and-continue."""

    def test_missing_gate_script_aborts_before_git(self):
        self.init_claude_repo()
        proc = self.run_script(PUSH)
        self.assertEqual(proc.returncode, 1, msg=proc.stdout + proc.stderr)
        self.assertIn("install.sh", proc.stderr)
        self.assertNotIn("pushing ungated", proc.stderr,
                         msg="warn-and-continue must be gone")
        self.assertNotIn("No proposal changes", proc.stdout,
                         msg="git flow must not be reached")

    def test_documented_bypass_env_var(self):
        self.init_claude_repo()
        proc = self.run_script(PUSH, PROPOSAL_GATE_ALLOW_MISSING="1")
        self.assertEqual(proc.returncode, 0, msg=proc.stdout + proc.stderr)
        self.assertIn("PROPOSAL_GATE_ALLOW_MISSING", proc.stderr,
                      msg="bypass must announce itself")
        self.assertIn("No proposal changes", proc.stdout)

    def test_gate_exit_4_gets_partial_batch_message(self):
        self.init_claude_repo()
        gate = os.path.join(self.claude, "scripts", "proposal-intake-gate.py")
        os.makedirs(os.path.dirname(gate), exist_ok=True)
        with open(gate, "w", encoding="utf-8") as fh:
            fh.write("import sys\nsys.exit(4)\n")
        proc = self.run_script(PUSH)
        self.assertEqual(proc.returncode, 1, msg=proc.stdout + proc.stderr)
        self.assertIn("partial batch", proc.stderr)
        self.assertIn("do not bypass", proc.stderr)
        # Round-6 item 2: exit 4 also covers push-blocking nonconforming
        # names — the message must mention that cause and the remedy.
        self.assertIn("nonconforming", proc.stderr)
        self.assertIn("archived/", proc.stderr)

    def test_gate_log_and_old_lock_never_committed(self):
        # F7: gate-log.jsonl is per-host forensics and .gate.lock is the
        # retired lock location — neither belongs in the pushed history.
        self.init_claude_repo()
        bare = os.path.join(self.tmp, "remote.git")
        subprocess.run(["git", "init", "-q", "--bare", bare], check=True,
                       capture_output=True, env=self.env())
        self.git("remote", "add", "origin", bare)
        self.git("push", "-q", "-u", "origin", "HEAD")
        gate = os.path.join(self.claude, "scripts", "proposal-intake-gate.py")
        os.makedirs(os.path.dirname(gate), exist_ok=True)
        with open(gate, "w", encoding="utf-8") as fh:
            fh.write("import sys\nsys.exit(0)\n")

        prop = os.path.join(self.claude, "proposals", "permissions",
                            "2026-08-02-new.md")
        os.makedirs(os.path.dirname(prop), exist_ok=True)
        with open(prop, "w", encoding="utf-8") as fh:
            fh.write("---\nstatus: pending\n---\nbody\n")
        cfgpath = os.path.join(self.claude, "proposals", "gate-config.json")
        with open(cfgpath, "w", encoding="utf-8") as fh:
            fh.write("{}\n")
        for runtime in ("gate-log.jsonl", ".gate.lock"):
            with open(os.path.join(self.claude, "proposals", runtime),
                      "w", encoding="utf-8") as fh:
                fh.write("local runtime state\n")

        proc = self.run_script(PUSH)
        self.assertEqual(proc.returncode, 0, msg=proc.stdout + proc.stderr)
        committed = self.git("log", "-1", "--name-only", "--format=")
        self.assertIn("proposals/permissions/2026-08-02-new.md", committed)
        self.assertIn("proposals/gate-config.json", committed,
                      msg="gate-config is user config and stays versioned")
        self.assertNotIn("gate-log.jsonl", committed,
                         msg="the gate log is local forensics — never pushed")
        self.assertNotIn(".gate.lock", committed)


class TestPushSymlinkGuard(ShellHarness):
    """Round-7 item 1: the gate's conformance scan reaches the legacy rsi
    content ONLY through the proposals/rsi symlink, while push-proposals.sh
    stages recursive-self-improvement/proposals/ directly. Install drift
    (symlink missing, replaced by a real dir, or retargeted) means the push
    would ship legacy content the gate never scanned — the push must abort
    BEFORE the gate runs, with the install.sh remedy."""

    def _install_marker_gate(self):
        """A gate stub that records having run — proves guard-before-gate."""
        gate = os.path.join(self.claude, "scripts", "proposal-intake-gate.py")
        os.makedirs(os.path.dirname(gate), exist_ok=True)
        with open(gate, "w", encoding="utf-8") as fh:
            fh.write("import os, sys\n"
                     "open(os.path.join(os.path.expanduser('~'), 'gate-ran'),"
                     " 'w').close()\n"
                     "sys.exit(0)\n")

    def _assert_aborted_before_gate(self, proc):
        self.assertEqual(proc.returncode, 1, msg=proc.stdout + proc.stderr)
        self.assertIn("rsi symlink", proc.stderr)
        self.assertIn("re-run install.sh", proc.stderr)
        self.assertFalse(os.path.exists(os.path.join(self.home, "gate-ran")),
                         msg="the symlink guard must fire before the gate runs")
        self.assertNotIn("No proposal changes", proc.stdout,
                         msg="git flow must not be reached")

    def test_rsi_replaced_by_real_dir_aborts(self):
        self.init_claude_repo()
        self._install_marker_gate()
        link = os.path.join(self.claude, "proposals", "rsi")
        os.remove(link)
        os.makedirs(link)
        with open(os.path.join(link, "2026-08-02-drift.md"), "w",
                  encoding="utf-8") as fh:
            fh.write("---\nstatus: pending\n---\ndrifted content\n")
        self._assert_aborted_before_gate(self.run_script(PUSH))

    def test_rsi_symlink_missing_aborts(self):
        self.init_claude_repo()
        self._install_marker_gate()
        os.remove(os.path.join(self.claude, "proposals", "rsi"))
        self._assert_aborted_before_gate(self.run_script(PUSH))

    def test_rsi_symlink_wrong_target_aborts(self):
        self.init_claude_repo()
        self._install_marker_gate()
        elsewhere = os.path.join(self.claude, "somewhere-else")
        os.makedirs(elsewhere)
        link = os.path.join(self.claude, "proposals", "rsi")
        os.remove(link)
        os.symlink(elsewhere, link)
        self._assert_aborted_before_gate(self.run_script(PUSH))

    def test_healthy_symlink_proceeds_to_gate(self):
        self.init_claude_repo()
        self._install_marker_gate()
        proc = self.run_script(PUSH)
        self.assertEqual(proc.returncode, 0, msg=proc.stdout + proc.stderr)
        self.assertTrue(os.path.exists(os.path.join(self.home, "gate-ran")),
                        msg="a healthy symlink must let the gate run")
        self.assertIn("No proposal changes", proc.stdout)


class TestInstallScript(ShellHarness):
    """R8: validate cron numbers before composing cron lines; stage and
    commit only the installed paths — never sweep unrelated staged work."""

    def test_rejects_non_integer_hour_before_any_side_effect(self):
        proc = self.run_script(INSTALL, PLUGIN_ROOT, "7; echo pwned", "0")
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("integer", proc.stderr.lower())
        self.assertFalse(
            os.path.exists(os.path.join(self.claude, "recursive-self-improvement")),
            msg="validation must run before any install side effect")

    def test_rejects_non_integer_minute(self):
        proc = self.run_script(INSTALL, PLUGIN_ROOT, "7", "1e3")
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("integer", proc.stderr.lower())

    def test_rejects_out_of_range_hour(self):
        proc = self.run_script(INSTALL, PLUGIN_ROOT, "24", "0")
        self.assertNotEqual(proc.returncode, 0)

    def test_unrelated_staged_work_survives_install_commit(self):
        self.init_claude_repo()
        unrelated = os.path.join(self.claude, "unrelated.txt")
        with open(unrelated, "w", encoding="utf-8") as fh:
            fh.write("the user's half-finished work\n")
        self.git("add", "unrelated.txt")

        proc = self.run_script(INSTALL, PLUGIN_ROOT, "17", "0")
        self.assertEqual(proc.returncode, 0, msg=proc.stdout + proc.stderr)

        committed = self.git("log", "-1", "--name-only", "--format=")
        self.assertNotIn("unrelated.txt", committed,
                         msg="install commit must not sweep unrelated staged work")
        self.assertIn("push-proposals.sh", committed)
        still_staged = self.git("diff", "--cached", "--name-only")
        self.assertIn("unrelated.txt", still_staged,
                      msg="unrelated work must still be staged afterwards")
        # Cron lines were composed with validated integers.
        with open(os.path.join(self.tmp, "cron-state"), encoding="utf-8") as fh:
            cron = fh.read()
        self.assertIn("0 17 * * *", cron)

    def test_spine_gitignore_written_and_idempotent(self):
        # F7: install.sh manages proposals/.gitignore so the gate log and the
        # retired lock name stay out of the pushed proposals subtree.
        self.init_claude_repo()
        proc = self.run_script(INSTALL, PLUGIN_ROOT, "17", "0")
        self.assertEqual(proc.returncode, 0, msg=proc.stdout + proc.stderr)
        gi = os.path.join(self.claude, "proposals", ".gitignore")
        with open(gi, encoding="utf-8") as fh:
            content = fh.read()
        self.assertIn("gate-log.jsonl", content)
        self.assertIn(".gate.lock", content)
        committed = self.git("log", "-1", "--name-only", "--format=")
        self.assertIn("proposals/.gitignore", committed,
                      msg="the spine gitignore must ship with the install commit")

        proc2 = self.run_script(INSTALL, PLUGIN_ROOT, "17", "0")
        self.assertEqual(proc2.returncode, 0, msg=proc2.stdout + proc2.stderr)
        with open(gi, encoding="utf-8") as fh:
            content2 = fh.read()
        self.assertEqual(content2.count("gate-log.jsonl"), 1,
                         msg="re-running install must not duplicate entries")
        self.assertEqual(content2.count(".gate.lock"), 1)


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""Tests for the shared proposal counter and the UserPromptSubmit pending-count nudge.

Two layers, same discipline as test_corrections_capture.py:

- Unit tests import ``hooks/proposal_counts.py`` directly and drive it with a
  throwaway HOME, so path resolution (config override → sink default → legacy
  fallback) is exercised without touching the real machine.
- End-to-end tests run ``hooks/pending-proposals-nudge.py`` and
  ``hooks/pending-proposals.py`` as subprocesses with HOME pointed at a
  tmpdir, exactly as Claude Code invokes them, and assert on stdout, the
  marker file, and the exit code.

No network, no real ~/.claude, no real ~/.local/state.
"""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

HOOKS = Path(__file__).resolve().parents[1] / "hooks"
COUNTS_PATH = HOOKS / "proposal_counts.py"
NUDGE_PATH = HOOKS / "pending-proposals-nudge.py"
BANNER_PATH = HOOKS / "pending-proposals.py"

SINK_REL = ".local/state/claude-proposals"
LEGACY_RSI_REL = ".claude/recursive-self-improvement/proposals"
LEGACY_FOLDER_REL = ".claude/proposals"
CONFIG_REL = ".claude/recursive-self-improvement/config/config.json"
NUDGE_STATE_REL = ".local/state/claude/proposals-nudge.json"


def _load_counts():
    spec = importlib.util.spec_from_file_location("proposal_counts", COUNTS_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


COUNTS = _load_counts()


def _today_utc():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


class HomeHarness(unittest.TestCase):
    """Throwaway HOME with the pieces each test opts into."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="proposal-counts-test-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.home = os.path.join(self.tmp, "home")
        os.makedirs(self.home)
        self._prev_home = os.environ.get("HOME")
        os.environ["HOME"] = self.home
        self.addCleanup(self._restore_home)

    def _restore_home(self):
        if self._prev_home is None:
            os.environ.pop("HOME", None)
        else:
            os.environ["HOME"] = self._prev_home

    # -- fixture builders ---------------------------------------------------

    def path(self, rel):
        return os.path.join(self.home, rel)

    def write_config(self, proposals=None):
        cfg_path = self.path(CONFIG_REL)
        os.makedirs(os.path.dirname(cfg_path), exist_ok=True)
        body = {"components": {"daily_review": False}}
        if proposals is not None:
            body["proposals"] = proposals
        with open(cfg_path, "w") as f:
            json.dump(body, f)
        return cfg_path

    def make_proposal(self, dir_path, name, status=None):
        os.makedirs(dir_path, exist_ok=True)
        fm = "---\n"
        if status is not None:
            fm += f"status: {status}\n"
        fm += "---\n\nbody\n"
        with open(os.path.join(dir_path, name), "w") as f:
            f.write(fm)

    def seed_sink(self, rsi_pending=0, rsi_done=0, other=None):
        sink = self.path(SINK_REL)
        rsi = os.path.join(sink, "rsi")
        os.makedirs(rsi, exist_ok=True)
        for i in range(rsi_pending):
            self.make_proposal(rsi, f"pending-{i}.md", status="pending")
        for i in range(rsi_done):
            self.make_proposal(rsi, f"done-{i}.md", status="implemented")
        for name, n in (other or {}).items():
            sub = os.path.join(sink, name)
            os.makedirs(sub, exist_ok=True)
            for i in range(n):
                self.make_proposal(sub, f"{name}-{i}.md")
        return sink

    def read_state(self):
        with open(self.path(NUDGE_STATE_REL)) as f:
            return json.load(f)

    def write_state(self, payload):
        p = self.path(NUDGE_STATE_REL)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as f:
            f.write(payload if isinstance(payload, str) else json.dumps(payload))

    def run_hook(self, script):
        env = dict(os.environ)
        env["HOME"] = self.home
        return subprocess.run(
            [sys.executable, str(script)],
            input='{"session_id":"t","hook_event_name":"UserPromptSubmit","prompt":"hi"}',
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
        )


# ---------------------------------------------------------------------------
# Unit: path resolution and counting
# ---------------------------------------------------------------------------


class TestPathResolution(HomeHarness):
    def test_default_folder_is_the_state_sink_not_dot_claude(self):
        self.assertEqual(
            COUNTS.DEFAULTS["folder"], "~/.local/state/claude-proposals"
        )

    def test_config_folder_overrides_the_default(self):
        custom = os.path.join(self.tmp, "elsewhere")
        os.makedirs(os.path.join(custom, "rsi"))
        self.make_proposal(os.path.join(custom, "rsi"), "a.md", status="pending")
        self.write_config({"folder": custom})
        self.assertEqual(dict(COUNTS.count_all_subdirs())["rsi"], 1)

    def test_counts_come_from_sink_when_config_omits_folder(self):
        self.write_config({})
        self.seed_sink(rsi_pending=3, rsi_done=2, other={"router": 1})
        counts = dict(COUNTS.count_all_subdirs())
        self.assertEqual(counts["rsi"], 3)
        self.assertEqual(counts["router"], 1)

    def test_real_rsi_subdir_is_status_aware(self):
        """The sink holds a REAL rsi/ dir, not a symlink. Status still filters."""
        self.write_config({})
        sink = self.seed_sink(rsi_pending=2, rsi_done=5)
        self.assertFalse(os.path.islink(os.path.join(sink, "rsi")))
        self.assertEqual(dict(COUNTS.count_all_subdirs())["rsi"], 2)

    def test_legacy_rsi_dir_is_the_source_when_sink_has_no_rsi_subdir(self):
        self.write_config({})
        sink = self.path(SINK_REL)
        os.makedirs(os.path.join(sink, "router"))
        legacy = self.path(LEGACY_RSI_REL)
        self.make_proposal(legacy, "old.md", status="pending")
        self.assertEqual(dict(COUNTS.count_all_subdirs())["rsi"], 1)

    def test_legacy_proposals_folder_is_the_fallback_when_sink_is_absent(self):
        """Cutover window: sink not built yet, ~/.claude/proposals still real."""
        self.write_config({})
        legacy_folder = self.path(LEGACY_FOLDER_REL)
        self.make_proposal(os.path.join(legacy_folder, "router"), "r.md")
        self.make_proposal(self.path(LEGACY_RSI_REL), "old.md", status="pending")
        counts = dict(COUNTS.count_all_subdirs())
        self.assertEqual(counts["router"], 1)
        self.assertEqual(counts["rsi"], 1)

    def test_total_pending_sums_every_subdir(self):
        self.write_config({})
        self.seed_sink(rsi_pending=4, rsi_done=9, other={"router": 2, "clv2": 1})
        self.assertEqual(COUNTS.total_pending(), 7)

    def test_total_pending_is_zero_when_nothing_exists(self):
        self.assertEqual(COUNTS.total_pending(), 0)


# ---------------------------------------------------------------------------
# End-to-end: the UserPromptSubmit nudge
# ---------------------------------------------------------------------------


class TestNudgeHook(HomeHarness):
    def _fired(self, result):
        self.assertEqual(result.returncode, 0, result.stderr)
        if not result.stdout.strip():
            return None
        payload = json.loads(result.stdout)
        hso = payload["hookSpecificOutput"]
        self.assertEqual(hso["hookEventName"], "UserPromptSubmit")
        return hso["additionalContext"]

    def test_fires_once_per_utc_day(self):
        self.write_config({})
        self.seed_sink(rsi_pending=22, other={"router": 1})
        first = self._fired(self.run_hook(NUDGE_PATH))
        self.assertIsNotNone(first)
        self.assertIn("23", first)
        self.assertIsNone(self._fired(self.run_hook(NUDGE_PATH)))
        self.assertIsNone(self._fired(self.run_hook(NUDGE_PATH)))

    def test_fires_again_when_count_rises_same_day(self):
        self.write_config({})
        sink = self.seed_sink(rsi_pending=2)
        self.assertIsNotNone(self._fired(self.run_hook(NUDGE_PATH)))
        self.assertIsNone(self._fired(self.run_hook(NUDGE_PATH)))
        self.make_proposal(os.path.join(sink, "rsi"), "new.md", status="pending")
        self.assertIsNotNone(self._fired(self.run_hook(NUDGE_PATH)))

    def test_fires_on_a_new_utc_day_even_when_count_fell(self):
        self.write_config({})
        self.seed_sink(rsi_pending=2)
        self.write_state({"date": "2000-01-01", "count": 99})
        self.assertIsNotNone(self._fired(self.run_hook(NUDGE_PATH)))

    def test_a_drain_lowers_the_baseline_so_a_smaller_rise_still_fires(self):
        self.write_config({})
        sink = self.seed_sink(rsi_pending=5)
        self.assertIsNotNone(self._fired(self.run_hook(NUDGE_PATH)))
        rsi = os.path.join(sink, "rsi")
        for i in range(4):
            os.remove(os.path.join(rsi, f"pending-{i}.md"))
        self.assertIsNone(self._fired(self.run_hook(NUDGE_PATH)))
        self.assertEqual(self.read_state()["count"], 1)
        self.make_proposal(rsi, "fresh.md", status="pending")
        self.assertIsNotNone(self._fired(self.run_hook(NUDGE_PATH)))

    def test_silent_and_exit_zero_when_the_proposals_folder_is_missing(self):
        self.write_config({})
        result = self.run_hook(NUDGE_PATH)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")

    def test_silent_and_exit_zero_with_no_config_and_no_folders_at_all(self):
        result = self.run_hook(NUDGE_PATH)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")

    def test_silent_when_every_proposal_is_drained(self):
        self.write_config({})
        self.seed_sink(rsi_done=8)
        result = self.run_hook(NUDGE_PATH)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")

    def test_a_corrupt_state_file_neither_errors_nor_blocks(self):
        self.write_config({})
        self.seed_sink(rsi_pending=3)
        self.write_state("{not json at all")
        result = self.run_hook(NUDGE_PATH)
        self.assertEqual(result.returncode, 0)
        self.assertIsNotNone(self._fired(result))

    def test_state_marker_lives_under_local_state_not_dot_claude(self):
        self.write_config({})
        self.seed_sink(rsi_pending=1)
        self.run_hook(NUDGE_PATH)
        self.assertTrue(os.path.isfile(self.path(NUDGE_STATE_REL)))
        self.assertFalse(os.path.exists(self.path(".claude/tmp")))
        state = self.read_state()
        self.assertEqual(state["date"], _today_utc())
        self.assertEqual(state["count"], 1)

    def test_context_names_the_breakdown_and_the_drain_command(self):
        self.write_config({})
        self.seed_sink(rsi_pending=2, other={"router": 3})
        msg = self._fired(self.run_hook(NUDGE_PATH))
        self.assertIn("rsi 2", msg)
        self.assertIn("router 3", msg)
        self.assertIn("/review-improvements", msg)


# ---------------------------------------------------------------------------
# End-to-end: the SessionStart banner still works against the sink layout
# ---------------------------------------------------------------------------


class TestSessionStartBanner(HomeHarness):
    def test_banner_counts_the_sink(self):
        self.write_config({})
        self.seed_sink(rsi_pending=22, rsi_done=12, other={"router": 1})
        result = self.run_hook(BANNER_PATH)
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        hso = payload["hookSpecificOutput"]
        self.assertEqual(hso["hookEventName"], "SessionStart")
        self.assertIn("rsi 22", hso["additionalContext"])
        self.assertIn("router 1", hso["additionalContext"])

    def test_banner_still_asks_for_setup_when_unconfigured(self):
        result = self.run_hook(BANNER_PATH)
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertIn(
            "setup-recursive-self-improvement",
            payload["hookSpecificOutput"]["additionalContext"],
        )

    def test_banner_is_silent_when_nothing_is_pending(self):
        self.write_config({})
        self.seed_sink(rsi_done=3)
        result = self.run_hook(BANNER_PATH)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")


if __name__ == "__main__":
    unittest.main()

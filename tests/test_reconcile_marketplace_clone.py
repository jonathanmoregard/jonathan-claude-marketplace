#!/usr/bin/env python3
"""Tests for scripts/reconcile-marketplace-clone.sh.

The script's whole value is what it REFUSES to do. It runs against a checkout
the harness serves plugins from, and the working tree it inspects may contain
somebody's unfinished work, so every "I do not recognise this" path must abort
with the tree byte-identical to how it was found. These tests assert exactly
that: after each abort, the files still hash the same and nothing was pulled.

No network, no HOME writes: fixtures are throwaway repos in a tmpdir, cloned
over local paths, with git hooks disabled so a host-level pre-commit hook
cannot make the suite flaky.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(REPO_ROOT, "scripts", "reconcile-marketplace-clone.sh")

BASE_MANIFEST = {
    "name": "jonathanmoregard",
    "owner": {"name": "Jonathan Moregard"},
    "metadata": {"version": "1.0.0", "description": "test marketplace"},
    "plugins": [
        {
            "name": "recursive-self-improvement",
            "version": "0.2.0",
            "source": "./plugins/recursive-self-improvement",
        }
    ],
}

OVERLAY_ENTRY = {
    "name": "superpowers",
    "description": "Forked from obra/superpowers.",
    "category": "development",
    "source": "./plugins/superpowers",
}


def dumps(manifest) -> str:
    return json.dumps(manifest, indent=2) + "\n"


def digest(path: str) -> str:
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


class ReconcileHarness(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="reconcile-test-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.hooks = os.path.join(self.tmp, "no-hooks")
        os.makedirs(self.hooks)
        # The working copy the overlay symlink points at.
        self.workcopy = os.path.join(self.tmp, "superpowers-workcopy")
        os.makedirs(os.path.join(self.workcopy, ".claude-plugin"))
        self.write(os.path.join(self.workcopy, ".claude-plugin", "plugin.json"),
                   '{"name": "superpowers", "version": "5.0.7"}\n')

        self.origin = os.path.join(self.tmp, "origin.git")
        self.git("init", "--bare", "-q", "-b", "master", self.origin, cwd=self.tmp)

        self.author = os.path.join(self.tmp, "author")
        self.git("clone", "-q", self.origin, self.author, cwd=self.tmp)
        self.seed_author()

    # -- helpers ----------------------------------------------------------
    def write(self, path: str, text: str):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)

    def git(self, *args, cwd=None, check=True):
        env = dict(os.environ)
        env.update({
            "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
            "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid",
        })
        return subprocess.run(
            ["git", "-c", f"core.hooksPath={self.hooks}", *args],
            cwd=cwd or self.tmp, env=env, check=check,
            capture_output=True, text=True)

    def seed_author(self):
        """Commit 1: the pre-merge upstream — no superpowers entry."""
        self.write(os.path.join(self.author, ".claude-plugin", "marketplace.json"),
                   dumps(BASE_MANIFEST))
        self.write(os.path.join(self.author, "README.md"), "marketplace\n")
        self.git("add", "-A", cwd=self.author)
        self.git("commit", "-qm", "seed", cwd=self.author)
        self.git("push", "-q", "origin", "master", cwd=self.author)
        self.seed_sha = self.git("rev-parse", "HEAD", cwd=self.author).stdout.strip()

    def advance_upstream(self):
        """Commit 2: the merged PR — entry listed, source path gitignored."""
        merged = json.loads(json.dumps(BASE_MANIFEST))
        merged["plugins"].append(json.loads(json.dumps(OVERLAY_ENTRY)))
        self.write(os.path.join(self.author, ".claude-plugin", "marketplace.json"),
                   dumps(merged))
        self.write(os.path.join(self.author, ".gitignore"),
                   "/plugins/superpowers\n")
        self.write(os.path.join(self.author, "NEW.md"), "upstream moved on\n")
        self.git("add", "-A", cwd=self.author)
        self.git("commit", "-qm", "list superpowers upstream", cwd=self.author)
        self.git("push", "-q", "origin", "master", cwd=self.author)

    def make_clone(self, name="clone"):
        """A clone parked one commit back, carrying the live overlay."""
        clone = os.path.join(self.tmp, name)
        self.git("clone", "-q", self.origin, clone, cwd=self.tmp)
        # Park it one commit back, the way a clone that cannot pull goes stale.
        self.git("switch", "-q", "-C", "master", self.seed_sha, cwd=clone)
        self.git("branch", "-q", "--set-upstream-to=origin/master", "master",
                 cwd=clone)
        overlaid = json.loads(json.dumps(BASE_MANIFEST))
        overlaid["plugins"].append(json.loads(json.dumps(OVERLAY_ENTRY)))
        self.write(os.path.join(clone, ".claude-plugin", "marketplace.json"),
                   dumps(overlaid))
        os.makedirs(os.path.join(clone, "plugins"), exist_ok=True)
        os.symlink(self.workcopy, os.path.join(clone, "plugins", "superpowers"))
        return clone

    def run_script(self, clone):
        return subprocess.run(["bash", SCRIPT, clone], cwd=self.tmp,
                              capture_output=True, text=True, timeout=120)

    def behind(self, clone) -> int:
        self.git("fetch", "-q", "origin", cwd=clone)
        out = self.git("rev-list", "--count", "HEAD..origin/master", cwd=clone)
        return int(out.stdout.strip())

    def manifest_path(self, clone) -> str:
        return os.path.join(clone, ".claude-plugin", "marketplace.json")

    def assert_aborted_untouched(self, proc, clone, before):
        self.assertEqual(proc.returncode, 1, msg=proc.stdout + proc.stderr)
        self.assertIn("ABORT", proc.stderr)
        for path, want in before.items():
            self.assertEqual(digest(path), want,
                             msg=f"{path} was modified by an aborted run")
        self.assertGreater(self.behind(clone), 0,
                           msg="an aborted run must not fast-forward")


class TestHappyPath(ReconcileHarness):
    def test_plain_ff_only_refuses_before_reconciling(self):
        """The problem being fixed, asserted rather than asserted-about."""
        self.advance_upstream()
        clone = self.make_clone()
        self.git("fetch", "-q", "origin", cwd=clone)
        proc = self.git("pull", "--ff-only", cwd=clone, check=False)
        self.assertNotEqual(proc.returncode, 0)

    def test_reconciles_then_ff_only_works_and_symlink_survives(self):
        self.advance_upstream()
        clone = self.make_clone()
        proc = self.run_script(clone)
        self.assertEqual(proc.returncode, 0, msg=proc.stdout + proc.stderr)
        self.assertEqual(self.behind(clone), 0, msg="did not fast-forward")

        link = os.path.join(clone, "plugins", "superpowers")
        self.assertTrue(os.path.islink(link), "the overlay symlink was clobbered")
        self.assertEqual(os.readlink(link), self.workcopy)
        self.assertTrue(os.path.isfile(
            os.path.join(link, ".claude-plugin", "plugin.json")),
            "the working copy is no longer readable through the symlink")

        status = self.git("status", "--porcelain=v1", cwd=clone).stdout
        self.assertEqual(status, "",
                         msg=f"tree not clean after reconciling: {status!r}")

        # The tracked manifest still registers the plugin, from upstream now.
        with open(self.manifest_path(clone), encoding="utf-8") as fh:
            names = [p["name"] for p in json.load(fh)["plugins"]]
        self.assertIn("superpowers", names)
        self.assertIn("recursive-self-improvement", names)

        # And a bare `git pull --ff-only` now succeeds on its own.
        again = self.git("pull", "--ff-only", cwd=clone, check=False)
        self.assertEqual(again.returncode, 0, msg=again.stderr)

    def test_second_run_is_a_no_op(self):
        self.advance_upstream()
        clone = self.make_clone()
        self.assertEqual(self.run_script(clone).returncode, 0)
        proc = self.run_script(clone)
        self.assertEqual(proc.returncode, 0, msg=proc.stdout + proc.stderr)
        self.assertIn("already reconciled", proc.stdout)
        self.assertEqual(self.git("status", "--porcelain=v1", cwd=clone).stdout, "")


class TestAborts(ReconcileHarness):
    def test_aborts_when_upstream_lacks_the_entry(self):
        clone = self.make_clone()          # upstream deliberately not advanced
        self.write(os.path.join(self.author, "NEW.md"), "unrelated\n")
        self.git("add", "-A", cwd=self.author)
        self.git("commit", "-qm", "unrelated upstream commit", cwd=self.author)
        self.git("push", "-q", "origin", "master", cwd=self.author)
        before = {self.manifest_path(clone): digest(self.manifest_path(clone))}
        proc = self.run_script(clone)
        self.assert_aborted_untouched(proc, clone, before)
        self.assertIn("does not yet carry", proc.stderr)

    def test_aborts_and_prints_diff_on_an_unrelated_modification(self):
        self.advance_upstream()
        clone = self.make_clone()
        readme = os.path.join(clone, "README.md")
        self.write(readme, "marketplace\nsomebody's half-finished edit\n")
        before = {readme: digest(readme),
                  self.manifest_path(clone): digest(self.manifest_path(clone))}
        proc = self.run_script(clone)
        self.assert_aborted_untouched(proc, clone, before)
        self.assertIn("does not recognise", proc.stdout)
        self.assertIn("README.md", proc.stdout)
        self.assertIn("half-finished edit", proc.stdout,
                      msg="the diff must be printed, not just named")

    def test_aborts_when_the_manifest_edit_goes_beyond_the_entry(self):
        self.advance_upstream()
        clone = self.make_clone()
        path = self.manifest_path(clone)
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        data["metadata"]["description"] = "locally retitled by somebody"
        self.write(path, dumps(data))
        before = {path: digest(path)}
        proc = self.run_script(clone)
        self.assert_aborted_untouched(proc, clone, before)
        self.assertIn("outside 'plugins'", proc.stdout)

    def test_aborts_when_the_local_entry_differs_from_upstream(self):
        """Discarding it would silently change what the harness resolves."""
        self.advance_upstream()
        clone = self.make_clone()
        path = self.manifest_path(clone)
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        for entry in data["plugins"]:
            if entry["name"] == "superpowers":
                entry["source"] = "./plugins/superpowers-experimental"
        self.write(path, dumps(data))
        before = {path: digest(path)}
        proc = self.run_script(clone)
        self.assert_aborted_untouched(proc, clone, before)
        self.assertIn("differs from the one upstream", proc.stdout)

    def test_aborts_on_a_dangling_overlay_symlink(self):
        self.advance_upstream()
        clone = self.make_clone()
        link = os.path.join(clone, "plugins", "superpowers")
        os.remove(link)
        os.symlink(os.path.join(self.tmp, "gone"), link)
        before = {self.manifest_path(clone): digest(self.manifest_path(clone))}
        proc = self.run_script(clone)
        self.assert_aborted_untouched(proc, clone, before)
        self.assertIn("dangling symlink", proc.stderr)

    def test_aborts_when_an_untracked_file_blocks_the_fast_forward(self):
        """NEW.md arrives upstream; an untracked NEW.md sits in the way. The
        collision must be caught while the manifest is still untouched."""
        self.advance_upstream()
        clone = self.make_clone()
        collide = os.path.join(clone, "NEW.md")
        self.write(collide, "untracked local file at an incoming path\n")
        before = {collide: digest(collide),
                  self.manifest_path(clone): digest(self.manifest_path(clone))}
        proc = self.run_script(clone)
        self.assert_aborted_untouched(proc, clone, before)
        self.assertIn("NEW.md", proc.stdout)

    def test_aborts_on_a_non_git_directory(self):
        plain = os.path.join(self.tmp, "not-a-repo")
        os.makedirs(plain)
        proc = self.run_script(plain)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("not a git checkout", proc.stderr)


if __name__ == "__main__":
    unittest.main()

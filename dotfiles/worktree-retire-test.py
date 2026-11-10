#!/usr/bin/env python3
"""worktree-retire removes a lane checkout only when its work is safely integrated."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "dotfiles/base/.local/bin/worktree-retire"
GIT_ENV = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}


class WorktreeRetireTests(unittest.TestCase):
    def setUp(self):
        scratch = ROOT / ".work/tmp"
        scratch.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=scratch, prefix="worktree-retire-")
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name).resolve() / "repo"
        self.git(None, "init", "-q", "-b", "main", str(self.repo))
        (self.repo / ".gitignore").write_text("build/\n")
        self.commit(self.repo, "tracked", "base\n")

    def git(self, cwd, *args):
        return subprocess.run(["git", *(["-C", str(cwd)] if cwd else []), *args], check=True,
                              capture_output=True, text=True, env={**os.environ, **GIT_ENV}).stdout.strip()

    def commit(self, cwd, name, text):
        (cwd / name).write_text(text)
        self.git(cwd, "add", "-A")
        self.git(cwd, "commit", "-q", "-m", name)

    def lane(self, name):
        path = self.repo / ".work/wt" / name
        self.git(self.repo, "worktree", "add", "-q", "-b", name, str(path))
        return path

    def retire(self, path, *extra):
        return subprocess.run([str(TOOL), str(path), "--into", "main", *extra],
                              capture_output=True, text=True, env={**os.environ, **GIT_ENV})

    def branches(self):
        return self.git(self.repo, "branch", "--format=%(refname:short)").split()

    def test_merged_lane_is_removed_with_its_branch(self):
        path = self.lane("merged")
        self.commit(path, "feature", "x\n")
        self.git(self.repo, "merge", "-q", "--ff-only", "merged")
        result = self.retire(path)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(path.exists())
        self.assertNotIn("merged", self.branches())

    def test_squash_integrated_lane_is_removed_but_branch_kept(self):
        path = self.lane("squashed")
        self.commit(path, "feature", "x\n")
        self.commit(self.repo, "other", "y\n")
        self.git(self.repo, "cherry-pick", "squashed")
        result = self.retire(path)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(path.exists())
        self.assertIn("squashed", self.branches())
        self.assertIn("kept branch squashed", result.stdout)

    def test_unintegrated_lane_is_kept(self):
        path = self.lane("open")
        self.commit(path, "feature", "x\n")
        result = self.retire(path)
        self.assertEqual(result.returncode, 1)
        self.assertTrue(path.exists())
        self.assertIn("not integrated", result.stderr)

    def test_dirty_lane_is_kept(self):
        path = self.lane("dirty")
        (path / "scratch.txt").write_text("x")
        result = self.retire(path)
        self.assertEqual(result.returncode, 1)
        self.assertTrue((path / "scratch.txt").exists())

    def test_ignored_files_need_explicit_discard(self):
        path = self.lane("ignored")
        (path / "build").mkdir()
        (path / "build/out.bin").write_text("x")
        refused = self.retire(path)
        self.assertEqual(refused.returncode, 1)
        self.assertIn("build/", refused.stderr)
        self.assertTrue(path.exists())
        self.assertEqual(self.retire(path, "--discard-ignored").returncode, 0)
        self.assertFalse(path.exists())

    def test_locked_lane_is_kept(self):
        path = self.lane("locked")
        self.git(self.repo, "worktree", "lock", str(path))
        self.assertEqual(self.retire(path).returncode, 1)
        self.assertTrue(path.exists())

    def test_checkout_outside_work_wt_is_refused(self):
        path = Path(self.tmp.name).resolve() / "elsewhere"
        self.git(self.repo, "worktree", "add", "-q", "-b", "elsewhere", str(path))
        result = self.retire(path)
        self.assertEqual(result.returncode, 1)
        self.assertTrue(path.exists())
        self.assertIn(".work/wt", result.stderr)

    def test_dry_run_changes_nothing(self):
        path = self.lane("dry")
        result = self.retire(path, "--dry-run")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(path.exists())
        self.assertIn("dry", self.branches())


if __name__ == "__main__":
    unittest.main()

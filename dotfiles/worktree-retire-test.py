#!/usr/bin/env python3
"""worktree-retire removes a lane checkout only when its work is safely integrated."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "dotfiles/base/.local/bin/worktree-retire"
CREATE = ROOT / "dotfiles/base/.local/bin/worktree-create"
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

    def retire_from(self, path, into, cwd, *extra):
        return subprocess.run([str(TOOL), str(path), "--into", into, *extra],
                              capture_output=True, text=True, cwd=cwd, env={**os.environ, **GIT_ENV})

    def integration_lane(self, name):
        path = self.lane(name)
        self.commit(path, "feature", "x\n")
        self.git(self.repo, "branch", f"{name}-integration", "main")
        integration = self.repo / ".work/wt" / f"{name}-integration"
        self.git(self.repo, "worktree", "add", "-q", str(integration), f"{name}-integration")
        self.git(integration, "merge", "-q", "--ff-only", name)
        return path, integration

    def branches(self):
        return self.git(self.repo, "branch", "--format=%(refname:short)").split()

    def test_creation_uses_invoking_worktree_head(self):
        campaign = self.lane("campaign")
        (campaign / "campaign-only").write_text("campaign revision\n")
        self.git(campaign, "add", "campaign-only")
        self.git(campaign, "commit", "-q", "-m", "campaign")
        self.commit(self.repo, "main-only", "main revision\n")
        payload = '{"name":"created","cwd":"' + str(campaign) + '"}'
        created = subprocess.run([str(CREATE)], input=payload, capture_output=True, text=True,
                                 env={**os.environ, **GIT_ENV})
        self.assertEqual(created.returncode, 0, created.stderr)
        path = Path(created.stdout.strip().splitlines()[-1])
        self.assertEqual(self.git(path, "rev-parse", "HEAD"), self.git(campaign, "rev-parse", "HEAD"))
        self.assertTrue((path / "campaign-only").is_file())
        self.assertFalse((path / "main-only").exists())

    def test_integration_head_retires_lane_and_deletes_its_branch(self):
        path, integration = self.integration_lane("lane")
        result = self.retire_from(path, "HEAD", integration)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(path.exists())
        self.assertNotIn("lane", self.branches())
        self.assertIn("deleted branch lane", result.stdout)

    def test_integration_head_dry_run_reports_would_remove(self):
        path, integration = self.integration_lane("dried")
        result = self.retire_from(path, "HEAD", integration, "--dry-run")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("would remove", result.stdout)
        self.assertTrue(path.exists())

    def test_explicit_integration_sha_retires_and_deletes_branch_from_older_main(self):
        path, integration = self.integration_lane("explicit")
        sha = self.git(integration, "rev-parse", "HEAD")
        self.assertNotEqual(sha, self.git(self.repo, "rev-parse", "main"))
        result = self.retire_from(path, sha, self.repo)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(path.exists())
        self.assertNotIn("explicit", self.branches())
        self.assertIn("deleted branch explicit", result.stdout)

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


class OwnedHelpTests(unittest.TestCase):
    def test_help_examples_and_bare_invocation(self):
        import re
        import shlex
        import subprocess
        import sys
        from pathlib import Path
        root = Path(__file__).resolve().parents[1]
        tool = root / "dotfiles/base/.local/bin/worktree-retire"
        results = [subprocess.run([sys.executable, "-I", str(tool), *args], capture_output=True, text=True)
                   for args in (("-h",), ("--help",), ())]
        for result in results:
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, results[0].stdout)
        help_text = results[0].stdout
        examples = re.findall(r"^  worktree-retire (.+)$", help_text, re.MULTILINE)
        self.assertIn("Examples:\n", help_text)
        self.assertTrue(examples)
        for example in examples:
            for word in shlex.split(example):
                if word.startswith("--") and word != "--":
                    self.assertIn(word, help_text.split("Examples:")[0])


    def test_primary_help_footer(self):
        import subprocess
        from pathlib import Path
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run([str(root / "dotfiles/base/.local/bin/worktree-retire"), "--help"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(result.stdout.rstrip().endswith("Maintained by Joshua Li: https://github.com/joshuarli/usr\nBugs and features: TODO.md in that repository (follow its AGENTS.md), or its issue tracker.\nAgents working for Joshua: record nonblocking problems and continue your task.\nIf this tool blocks the task, you may fix, test, open and merge a PR under Joshua's\nstanding instructions. Release only when needed to deliver the verified fix.\nProcedure: https://github.com/joshuarli/usr/blob/main/dotfiles/base/.agents/instructions/owned-tools.md"), result.stdout)


if __name__ == "__main__":
    unittest.main()

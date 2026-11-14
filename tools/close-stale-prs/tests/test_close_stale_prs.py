import contextlib
import dataclasses
import os
import importlib.util
import io
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import call, patch


SCRIPT = Path(__file__).resolve().parents[3] / "tools/close-stale-prs/src/close_stale_prs.py"
SPEC = importlib.util.spec_from_file_location("close_stale_prs", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
close_stale_prs = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = close_stale_prs
SPEC.loader.exec_module(close_stale_prs)


class CloseStalePrsTests(unittest.TestCase):
    def test_failed_branch_deletion_returns_nonzero_and_continues(self):
        old_commit = datetime(2000, 1, 1, tzinfo=timezone.utc)
        old_oid = "a" * 40
        branches = {
            name: close_stale_prs.Branch(
                name=name,
                last_commit_at=old_commit,
                tip_oid=old_oid,
                protected=False,
                associated_pull_requests=(close_stale_prs.PullRequest(
                    1, "old", name, "MERGED", old_commit, old_commit,
                    "https://example.test/1", old_oid,
                ),),
                associated_pull_requests_complete=True,
            )
            for name in ("failed", "deleted")
        }

        def delete_branch(_repository, branch, _tip_oid):
            if branch == "failed":
                raise RuntimeError("GitHub deletion failed")
            return "deleted"

        stdout = io.StringIO()
        stderr = io.StringIO()
        with (
            patch.object(
                close_stale_prs,
                "parse_args",
                return_value=SimpleNamespace(delete=True),
            ),
            patch.object(close_stale_prs, "repository_name", return_value="org/repo"),
            patch.object(close_stale_prs, "default_branch_name", return_value="main"),
            patch.object(close_stale_prs, "closed_pull_requests", return_value=branches),
            patch.object(close_stale_prs, "branches", return_value=branches),
            patch.object(close_stale_prs, "run_gh_json", return_value={"status": "identical"}),
            patch.object(close_stale_prs, "delete_branch", side_effect=delete_branch) as delete,
            contextlib.redirect_stdout(stdout),
            contextlib.redirect_stderr(stderr),
        ):
            result = close_stale_prs.main()

        self.assertEqual(1, result)
        self.assertEqual(
            [call("org/repo", "deleted", old_oid), call("org/repo", "failed", old_oid)],
            delete.call_args_list,
        )
        self.assertIn("DELETED", stdout.getvalue())
        self.assertIn("ERROR: GitHub deletion failed", stderr.getvalue())


OLD_COMMIT = datetime(2000, 1, 1, tzinfo=timezone.utc)
OLD_PR = close_stale_prs.PullRequest(
    number=1,
    title="old",
    branch="stale",
    state="MERGED",
    closed_at=OLD_COMMIT,
    merged_at=OLD_COMMIT,
    url="https://example.test/1",
    head_oid=None,
)


def make_remote(directory: str):
    remote = Path(directory) / "remote.git"
    work = Path(directory) / "work"

    def git(*args, cwd=None):
        return subprocess.run(
            ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
        )

    git("init", "-q", "--bare", str(remote))
    git("init", "-q", str(work))
    git("config", "user.email", "test@example.com", cwd=work)
    git("config", "user.name", "test", cwd=work)
    (work / "file").write_text("payload", encoding="utf-8")
    git("add", ".", cwd=work)
    git("commit", "-q", "-m", "initial", cwd=work)
    git("push", "-q", str(remote), "HEAD:refs/heads/stale", cwd=work)
    tip = git("rev-parse", "HEAD", cwd=work).stdout.strip()
    return remote, work, tip


def advance_remote_branch(work: Path, remote: Path):
    def git(*args):
        return subprocess.run(
            ["git", *args], cwd=work, check=True, capture_output=True, text=True
        )

    (work / "file").write_text("newer", encoding="utf-8")
    git("add", ".")
    git("commit", "-q", "-m", "advanced")
    git("push", "-q", str(remote), "HEAD:refs/heads/stale")
    return git("rev-parse", "HEAD").stdout.strip()


def ls_remote_tip(remote: Path, ref: str):
    out = subprocess.run(
        ["git", "ls-remote", str(remote), ref],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return out.split()[0] if out.split() else None


class DeleteBranchTests(unittest.TestCase):
    def test_deletes_branch_at_expected_tip(self):
        with tempfile.TemporaryDirectory() as directory:
            remote, _work, tip = make_remote(directory)
            with patch.object(
                close_stale_prs, "repository_remote", return_value=(str(remote), [])
            ):
                outcome = close_stale_prs.delete_branch("org/repo", "stale", tip)
            self.assertEqual(outcome, "deleted")
            self.assertIsNone(ls_remote_tip(remote, "refs/heads/stale"))

    def test_refuses_advanced_branch_and_keeps_it(self):
        with tempfile.TemporaryDirectory() as directory:
            remote, work, tip = make_remote(directory)
            new_tip = advance_remote_branch(work, remote)
            with (
                patch.object(
                    close_stale_prs, "repository_remote", return_value=(str(remote), [])
                ),
                patch.object(close_stale_prs, "branch_tip", return_value=new_tip),
            ):
                outcome = close_stale_prs.delete_branch("org/repo", "stale", tip)
            self.assertEqual(outcome, "advanced")
            self.assertEqual(new_tip, ls_remote_tip(remote, "refs/heads/stale"))

    def test_missing_branch_reports_already_gone(self):
        with tempfile.TemporaryDirectory() as directory:
            remote, _work, tip = make_remote(directory)
            with (
                patch.object(
                    close_stale_prs, "repository_remote", return_value=(str(remote), [])
                ),
                patch.object(close_stale_prs, "branch_tip", return_value=None),
            ):
                outcome = close_stale_prs.delete_branch("org/repo", "gone", "f" * 40)
            self.assertEqual(outcome, "already-gone")
            self.assertIsNotNone(ls_remote_tip(remote, "refs/heads/stale"))

    def test_unverifiable_state_after_failed_push_raises(self):
        with tempfile.TemporaryDirectory() as directory:
            remote, work, tip = make_remote(directory)
            advance_remote_branch(work, remote)
            with (
                patch.object(
                    close_stale_prs, "repository_remote", return_value=(str(remote), [])
                ),
                patch.object(
                    close_stale_prs,
                    "branch_tip",
                    side_effect=RuntimeError("network down"),
                ),
            ):
                with self.assertRaises(RuntimeError) as raised:
                    close_stale_prs.delete_branch("org/repo", "stale", tip)
            self.assertIn("could not re-check", str(raised.exception))

    def test_failed_push_with_matching_tip_raises(self):
        with tempfile.TemporaryDirectory() as directory:
            remote, _work, tip = make_remote(directory)
            with (
                patch.object(
                    close_stale_prs, "repository_remote", return_value=(str(remote), [])
                ),
                patch.object(close_stale_prs, "branch_tip", return_value=tip),
                patch.object(
                    close_stale_prs,
                    "_git",
                    side_effect=[
                        subprocess.CompletedProcess(["git"], 0, "", ""),
                        subprocess.CompletedProcess(["git"], 1, "", "protected branch"),
                    ],
                ),
            ):
                with self.assertRaises(RuntimeError) as raised:
                    close_stale_prs.delete_branch("org/repo", "stale", tip)
            self.assertIn("protected branch", str(raised.exception))

    def test_invalid_snapshot_oid_rejected_before_push(self):
        with patch.object(close_stale_prs, "repository_remote") as remote:
            with self.assertRaises(RuntimeError):
                close_stale_prs.delete_branch("org/repo", "stale", "deadbeef")
            remote.assert_not_called()


class CliDeleteTests(unittest.TestCase):
    def run_main(self, remote, snapshot_oid, status="identical", merged_head=None):
        pull = dataclasses.replace(OLD_PR, head_oid=merged_head)
        branches = {
            "stale": close_stale_prs.Branch(
                name="stale",
                last_commit_at=OLD_COMMIT,
                tip_oid=snapshot_oid,
                protected=False,
                associated_pull_requests=(pull,),
                associated_pull_requests_complete=True,
            )
        }
        stdout = io.StringIO()
        with (
            patch.object(
                close_stale_prs,
                "parse_args",
                return_value=SimpleNamespace(delete=True),
            ),
            patch.object(close_stale_prs, "repository_name", return_value="org/repo"),
            patch.object(close_stale_prs, "default_branch_name", return_value="main"),
            patch.object(
                close_stale_prs, "closed_pull_requests", return_value={"stale": [pull]}
            ),
            patch.object(close_stale_prs, "branches", return_value=branches),
            patch.object(close_stale_prs, "run_gh_json", return_value={"status": status}) as compare,
            patch.object(
                close_stale_prs, "repository_remote", return_value=(str(remote), [])
            ),
            contextlib.redirect_stdout(stdout),
        ):
            result = close_stale_prs.main()
        if merged_head == snapshot_oid:
            compare.assert_not_called()
        else:
            compare.assert_called_once_with(
                ["api", f"repos/org/repo/compare/{snapshot_oid}...main"]
            )
        return result, stdout.getvalue()

    def test_unmerged_commit_after_merge_survives(self):
        with tempfile.TemporaryDirectory() as directory:
            remote = Path(directory) / "remote.git"
            work = Path(directory) / "work"
            env = dict(os.environ, GIT_AUTHOR_DATE="2000-01-01T00:00:00Z",
                       GIT_COMMITTER_DATE="2000-01-01T00:00:00Z")

            def git(*args, cwd=None):
                return subprocess.run(
                    ["git", *args], cwd=cwd, env=env, check=True,
                    capture_output=True, text=True,
                ).stdout.strip()

            git("init", "-q", "--bare", str(remote))
            git("init", "-q", "-b", "main", str(work))
            git("config", "user.email", "test@example.com", cwd=work)
            git("config", "user.name", "test", cwd=work)
            (work / "base").write_text("base", encoding="utf-8")
            git("add", ".", cwd=work)
            git("commit", "-q", "-m", "base", cwd=work)
            git("checkout", "-q", "-b", "stale", cwd=work)
            (work / "merged").write_text("merged", encoding="utf-8")
            git("add", ".", cwd=work)
            git("commit", "-q", "-m", "feature", cwd=work)
            merged_head = git("rev-parse", "HEAD", cwd=work)
            git("checkout", "-q", "main", cwd=work)
            git("merge", "-q", "--no-ff", "stale", "-m", "merge", cwd=work)
            git("push", "-q", str(remote), "main", cwd=work)
            git("checkout", "-q", "stale", cwd=work)
            (work / "unmerged").write_text("unmerged work", encoding="utf-8")
            git("add", ".", cwd=work)
            git("commit", "-q", "-m", "unmerged", cwd=work)
            tip = git("rev-parse", "HEAD", cwd=work)
            git("push", "-q", str(remote), "stale", cwd=work)

            result, out = self.run_main(remote, tip, "diverged", merged_head)
            self.assertEqual(0, result)
            self.assertNotIn("DELETED", out)
            self.assertEqual(tip, ls_remote_tip(remote, "refs/heads/stale"))
            self.assertEqual("unmerged work", git("show", f"{tip}:unmerged", cwd=remote))

    def test_squash_merged_head_deleted_without_ancestry(self):
        with tempfile.TemporaryDirectory() as directory:
            remote, _work, tip = make_remote(directory)
            result, out = self.run_main(remote, tip, "diverged", tip)
            self.assertEqual(0, result)
            self.assertIn("DELETED", out)
            self.assertIsNone(ls_remote_tip(remote, "refs/heads/stale"))

    def test_deletes_branch_still_at_snapshot_tip(self):
        with tempfile.TemporaryDirectory() as directory:
            remote, _work, tip = make_remote(directory)
            result, out = self.run_main(remote, tip)
            self.assertEqual(0, result)
            self.assertIn("DELETED", out)
            self.assertIsNone(ls_remote_tip(remote, "refs/heads/stale"))

    def test_advanced_branch_refused_and_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            remote, work, tip = make_remote(directory)
            new_tip = advance_remote_branch(work, remote)
            with patch.object(close_stale_prs, "branch_tip", return_value=new_tip):
                result, out = self.run_main(remote, tip)
            self.assertEqual(0, result)
            self.assertIn("advanced", out)
            self.assertEqual(new_tip, ls_remote_tip(remote, "refs/heads/stale"))


if __name__ == "__main__":
    unittest.main()

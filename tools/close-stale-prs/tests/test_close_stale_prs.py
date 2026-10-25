import contextlib
import importlib.util
import io
import sys
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
        branches = {
            name: close_stale_prs.Branch(
                name=name,
                last_commit_at=old_commit,
                protected=False,
                associated_pull_requests=(),
                associated_pull_requests_complete=True,
            )
            for name in ("failed", "deleted")
        }

        def delete_branch(_repository, branch):
            if branch == "failed":
                raise RuntimeError("GitHub deletion failed")

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
            patch.object(close_stale_prs, "delete_branch", side_effect=delete_branch) as delete,
            contextlib.redirect_stdout(stdout),
            contextlib.redirect_stderr(stderr),
        ):
            result = close_stale_prs.main()

        self.assertEqual(1, result)
        self.assertEqual([call("org/repo", "deleted"), call("org/repo", "failed")], delete.call_args_list)
        self.assertIn("DELETED", stdout.getvalue())
        self.assertIn("ERROR: GitHub deletion failed", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()

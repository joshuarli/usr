"""`sync hosts` and the shared task report, with a fake SSH runner."""

from __future__ import annotations

import io
import json
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fleet
from report import TaskLine, counts, render, summary, PLAN_STATES

POLICY = {"hosts": {"work": "100.0.0.1", "lisa": "100.0.0.2", "tr": "100.0.0.3"}}


def done(stdout: str = "", code: int = 0, stderr: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess([], code, stdout, stderr)


def plan_json(*tasks: tuple[str, str, str]) -> str:
    lines = [TaskLine(*one) for one in tasks]
    return json.dumps({"schema": 1, "command": "plan", "host": "x", "tasks": [line.__dict__ for line in lines], "counts": counts(lines, PLAN_STATES)})


class Fake:
    def __init__(self, replies: dict[str, dict[str, subprocess.CompletedProcess[str]]]):
        self.replies = replies
        self.calls: list[tuple[str, bool, str]] = []

    def __call__(self, host: fleet.Host, script: str, timeout: int) -> subprocess.CompletedProcess[str]:
        kind = "sync" if script.startswith("sh sync") else "repo"
        self.calls.append((host.name, host.local, script))
        return self.replies[host.name][kind]


REPO_OK = "before=abc1234\nbranch=main\ndirty=0\nbehind=0\nahead=0\n"


class FleetTests(unittest.TestCase):
    def run_fleet(self, argv: list[str], fake: Fake) -> tuple[int, str]:
        out = io.StringIO()
        original = sys.stdout
        sys.stdout = out
        try:
            code = fleet.main(argv, run=fake, policy=POLICY, mine={"100.0.0.1"})
        finally:
            sys.stdout = original
        return code, out.getvalue()

    def test_hosts_come_from_the_policy_and_the_local_ip_runs_locally(self):
        hosts = fleet.fleet(POLICY, {"100.0.0.1"}, [])
        self.assertEqual([(h.name, h.local) for h in hosts], [("work", True), ("lisa", False), ("tr", False)])
        with self.assertRaises(ValueError):
            fleet.fleet(POLICY, set(), ["nope"])
        with self.assertRaises(ValueError):
            fleet.fleet({}, set(), [])

    def test_plan_reports_each_host_and_details_only_where_something_is_due(self):
        fake = Fake({
            "work": {"repo": done(REPO_OK), "sync": done(plan_json(("links", "current", "links match")))},
            "lisa": {"repo": done(REPO_OK.replace("behind=0", "behind=2")), "sync": done("progress\n" + plan_json(("tool:fd", "check", "installed")))},
            "tr": {"repo": done(REPO_OK.replace("dirty=0", "dirty=1")), "sync": done(plan_json(("tool:agent-browser", "apply", "missing agent-browser")))},
        })
        code, out = self.run_fleet(["plan"], fake)
        self.assertEqual(code, 0)
        self.assertRegex(out, r"(?m)^  work\* +abc1234 +up to date +✓ 1 up to date$")
        self.assertRegex(out, r"(?m)^  lisa +abc1234 +2 behind")
        self.assertRegex(out, r"(?m)^  tr +abc1234 +up to date, 1 local change +✓ 1 to apply$")
        self.assertIn("\ntr\n  apply     tool:agent-browser  missing agent-browser", out)
        self.assertNotIn("\nlisa\n", out)
        self.assertTrue(all("merge" not in script for _, _, script in fake.calls if "sync" not in script.split()[:2]), "plan must not merge")

    def test_unreachable_and_failed_hosts_fail_the_run(self):
        fake = Fake({
            "work": {"repo": done(REPO_OK), "sync": done(plan_json(("links", "conflict", "CONFLICT: .zshrc")))},
            "lisa": {"repo": done("", 255, "ssh: connect to host lisa: Operation timed out")},
            "tr": {"repo": done(REPO_OK), "sync": done("sync: no working Python", 1)},
        })
        code, out = self.run_fleet(["plan"], fake)
        self.assertEqual(code, 1)
        self.assertRegex(out, r"(?m)^  lisa +- +unreachable")
        self.assertIn("sync plan: sync: no working Python", out)
        self.assertIn("✗ 1 conflict", out)
        self.assertIn("CONFLICT: .zshrc", out)

    def test_apply_pulls_first_and_skips_sync_where_the_pull_is_blocked(self):
        updated = "before=abc1234\nbranch=main\ndirty=0\nbehind=1\nahead=0\npull=updated\nafter=def5678\n"
        blocked = "before=abc1234\nbranch=main\ndirty=1\nbehind=1\nahead=0\npull=blocked\nafter=abc1234\n"
        applied = json.dumps({"schema": 1, "command": "apply", "host": "x", "tasks": [{"name": "tool:fd", "state": "applied", "detail": "installed"}], "counts": {}})
        fake = Fake({"work": {"repo": done(updated), "sync": done(applied)}, "lisa": {"repo": done(blocked)}, "tr": {"repo": done(updated), "sync": done(applied)}})
        code, out = self.run_fleet(["apply"], fake)
        self.assertEqual(code, 1)
        self.assertIn("updated abc1234→def5678", out)
        self.assertRegex(out, r"(?m)^  lisa +abc1234 +pull blocked by local changes, 1 local change +skipped$")
        self.assertNotIn(("lisa", False, "sh sync apply --json"), fake.calls)
        self.assertIn("merge --ff-only", [script for name, _, script in fake.calls if name == "tr"][0])

    def test_pull_never_runs_sync(self):
        fake = Fake({name: {"repo": done(REPO_OK)} for name in POLICY["hosts"]})
        code, _ = self.run_fleet(["pull", "lisa"], fake)
        self.assertEqual(code, 0)
        self.assertEqual([name for name, _, _ in fake.calls], ["lisa"])


class ReportTests(unittest.TestCase):
    def test_summary_names_only_what_needs_attention(self):
        self.assertEqual(summary({"conflict": 0, "apply": 0, "check": 3, "current": 2}, False), "5 up to date")
        self.assertEqual(summary({"conflict": 2, "apply": 1, "check": 0, "current": 1}, False), "2 conflicts · 1 to apply · 1 up to date")

    def test_link_changes_are_listed_under_the_links_task(self):
        out = io.StringIO()
        render("plan", "h", [TaskLine("links", "apply", "LINK: ~/.zshrc; PRUNE: ~/.old"), TaskLine("tool:fd", "current", "installed")], False, out)
        text = out.getvalue()
        self.assertIn("  apply     links  2 changes\n", text)
        self.assertIn("LINK: ~/.zshrc", text)
        self.assertNotIn("tool:fd", text)


if __name__ == "__main__":
    unittest.main()

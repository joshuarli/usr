import contextlib
import datetime as dt
import io
import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path
from unittest import mock
from typing import Any, cast

SCRIPT = Path(__file__).parent / "base/.local/bin/opencode-supervisor"
loader = SourceFileLoader("opencode_supervisor", str(SCRIPT))
spec = spec_from_loader(loader.name, cast(Any, loader))
supervisor = module_from_spec(cast(Any, spec))
loader.exec_module(supervisor)


class SupervisorTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.workdir = self.root / "work"
        self.workdir.mkdir()
        self.db = self.root / "opencode.db"
        con = sqlite3.connect(self.db)
        con.execute("create table session_v2 (id text, directory text, time_created integer)")
        con.execute("create table kv (key text, value text)")
        con.execute("create table session_message (session_id text, type text, data text, time_created integer)")
        con.commit()
        con.close()

    def make_goal(self, session_id, status, age_seconds, objective="do the work"):
        updated = int((dt.datetime.now().timestamp() - age_seconds) * 1000)
        con = sqlite3.connect(self.db)
        con.execute("insert or replace into session_v2 values (?, ?, ?)", (session_id, str(self.workdir), updated))
        con.execute(
            "insert or replace into kv values (?, ?)",
            (
                supervisor.GOAL_KEY_PREFIX + session_id,
                json.dumps(
                    {
                        "id": "goal-1",
                        "objective": objective,
                        "status": status,
                        "updatedAt": updated,
                        "rounds": 1,
                        "maxRounds": 50,
                    }
                ),
            ),
        )
        con.commit()
        con.close()

    def make_resume(self, session_id, age_seconds):
        created = int((dt.datetime.now().timestamp() - age_seconds) * 1000)
        con = sqlite3.connect(self.db)
        con.execute(
            "insert into session_message values (?, ?, ?, ?)",
            (
                session_id,
                "synthetic",
                json.dumps(
                    {
                        "metadata": {"source": "goal", "goalID": "goal-1"},
                        "text": "The user resumed the goal.",
                        "time": {"created": created},
                    }
                ),
                created,
            ),
        )
        con.commit()
        con.close()

    def test_find_panes_matches_workdir_and_opencode(self):
        panes = "%1 100 /other\n%2 200 {wd}\n%3 300 {wd}\n".format(wd=self.workdir)
        outputs = {
            (supervisor.TMUX, "list-panes", "-a", "-F", "#{pane_id} #{pane_pid} #{pane_current_path}"): panes,
            ("pgrep", "-P", "200"): "201\n",
            ("ps", "-o", "command=", "-p", "201"): "opencode\n",
            ("pgrep", "-P", "300"): "301\n",
            ("ps", "-o", "command=", "-p", "301"): "vim\n",
        }
        with mock.patch.object(supervisor, "run", side_effect=lambda *args: outputs[args]):
            self.assertEqual(supervisor.find_panes(str(self.workdir)), [("%2", "201")])

    def test_goal_state_reads_paused_goal(self):
        self.make_goal("ses-1", "paused", 600)
        with mock.patch.object(supervisor, "OPENCODE_DB", self.db):
            goal = supervisor.goal_state("ses-1")
        self.assertEqual(goal["status"], "paused")
        self.assertEqual(goal["objective"], "do the work")

    def test_goal_state_missing_session(self):
        with mock.patch.object(supervisor, "OPENCODE_DB", self.db):
            with self.assertRaises(supervisor.SessionNotFound):
                supervisor.goal_state("ses-1")

    def test_paused_goal_ignores_active_goal(self):
        self.make_goal("ses-1", "active", 600)
        with mock.patch.object(supervisor, "OPENCODE_DB", self.db), mock.patch.object(
            supervisor, "find_panes", return_value=[("%2", "201")]
        ), mock.patch.object(supervisor, "pane_session", return_value="ses-1"):
            self.assertIsNone(supervisor.paused_goal(str(self.workdir), 180))

    def test_paused_goal_recent_pause_is_skipped(self):
        self.make_goal("ses-1", "paused", 30)
        with mock.patch.object(supervisor, "OPENCODE_DB", self.db), mock.patch.object(
            supervisor, "find_panes", return_value=[("%2", "201")]
        ), mock.patch.object(supervisor, "pane_session", return_value="ses-1"):
            self.assertIsNone(supervisor.paused_goal(str(self.workdir), 180))

    def test_paused_goal_stale_is_selected(self):
        self.make_goal("ses-1", "paused", 600)
        with mock.patch.object(supervisor, "OPENCODE_DB", self.db), mock.patch.object(
            supervisor, "find_panes", return_value=[("%2", "201")]
        ), mock.patch.object(supervisor, "pane_session", return_value="ses-1"):
            found = supervisor.paused_goal(str(self.workdir), 180)
        self.assertIsNotNone(found)
        self.assertEqual(found[0], "%2")
        self.assertEqual(found[1], "ses-1")
        self.assertEqual(found[2], "do the work")

    def test_recent_resume_is_skipped(self):
        self.make_goal("ses-1", "paused", 600)
        self.make_resume("ses-1", 30)
        with mock.patch.object(supervisor, "OPENCODE_DB", self.db), mock.patch.object(
            supervisor, "find_panes", return_value=[("%2", "201")]
        ), mock.patch.object(supervisor, "pane_session", return_value="ses-1"):
            self.assertIsNone(supervisor.paused_goal(str(self.workdir), 180))

    def test_old_resume_does_not_block(self):
        self.make_goal("ses-1", "paused", 600)
        self.make_resume("ses-1", 600)
        with mock.patch.object(supervisor, "OPENCODE_DB", self.db), mock.patch.object(
            supervisor, "find_panes", return_value=[("%2", "201")]
        ), mock.patch.object(supervisor, "pane_session", return_value="ses-1"):
            self.assertIsNotNone(supervisor.paused_goal(str(self.workdir), 180))

    def test_resume_sends_command_then_continue(self):
        calls = []
        with mock.patch.object(supervisor, "send_keys", side_effect=lambda pane, text: calls.append((pane, text))), mock.patch.object(
            supervisor, "wait_for_active", return_value=True
        ):
            self.assertTrue(supervisor.resume("%2", "ses-1"))
        self.assertEqual(
            calls, [("%2", "/goal resume"), ("%2", "continue")]
        )

    def test_resume_without_active_goal_does_not_send_continue(self):
        calls = []
        with mock.patch.object(supervisor, "send_keys", side_effect=lambda pane, text: calls.append((pane, text))), mock.patch.object(
            supervisor, "wait_for_active", return_value=False
        ):
            self.assertFalse(supervisor.resume("%2", "ses-1"))
        self.assertEqual(calls, [("%2", "/goal resume")])

    def test_send_keys_clears_line_when_interrupted(self):
        calls = []

        def checked(*args):
            calls.append(args)
            if "-l" in args:
                raise supervisor.Interrupted(2)

        with mock.patch.object(supervisor, "run_checked", side_effect=checked), mock.patch.object(
            supervisor, "execute_command", side_effect=lambda *args: calls.append(args) or None
        ):
            with self.assertRaises(supervisor.Interrupted):
                supervisor.send_keys("%2", "continue")
        self.assertEqual(calls[-1], (supervisor.TMUX, "send-keys", "-t", "%2", "C-u"))

    def test_help_bare_version_and_usage_error(self):
        def invoke(*args):
            return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True)

        bare = invoke()
        help_text = invoke("-h")
        self.assertEqual(bare.returncode, 0)
        self.assertEqual(bare.stdout, help_text.stdout)
        for option in ("--workdir", "--stale", "--dry-run", "examples:", "signals:"):
            self.assertIn(option, help_text.stdout)
        version = invoke("--version")
        self.assertEqual(version.returncode, 0)
        self.assertIn("opencode-supervisor", version.stdout)
        bad = invoke("bogus")
        self.assertEqual(bad.returncode, 2)
        self.assertIn("bogus", bad.stderr)
        self.assertIn("-h", bad.stderr)

    def test_dry_run_reports_without_sending(self):
        stdout = io.StringIO()
        with mock.patch.object(
            supervisor, "paused_goal", return_value=("%2", "ses-1", "do the work", "paused 600s")
        ), mock.patch.object(supervisor, "resume") as resume, mock.patch.object(
            sys, "argv", ["opencode-supervisor", "--dry-run"]
        ), contextlib.redirect_stdout(stdout):
            code = supervisor.main()
        self.assertEqual(code, 0)
        resume.assert_not_called()
        self.assertIn("would resume", stdout.getvalue())

    def test_runtime_failure_exits_one_on_stderr(self):
        stderr = io.StringIO()
        with mock.patch.object(sys, "argv", ["opencode-supervisor", "--dry-run"]), mock.patch.object(
            supervisor, "paused_goal", side_effect=RuntimeError("missing session")
        ), contextlib.redirect_stderr(stderr):
            code = supervisor.main()
        self.assertEqual(code, 1)
        self.assertIn("missing session", stderr.getvalue())

    def test_corrupt_data_exits_one_without_traceback(self):
        stderr = io.StringIO()
        with mock.patch.object(sys, "argv", ["opencode-supervisor", "--dry-run"]), mock.patch.object(
            supervisor, "paused_goal", side_effect=ValueError("bad timestamp")
        ), contextlib.redirect_stderr(stderr):
            code = supervisor.main()
        self.assertEqual(code, 1)
        self.assertIn("bad timestamp", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()

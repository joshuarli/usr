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

SCRIPT = Path(__file__).parent / "base/.local/bin/session-supervisor"
loader = SourceFileLoader("session_supervisor", str(SCRIPT))
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

    def make_agy(self, status, modified, steps=7, continue_ms=None):
        db = self.root / "summaries.db"
        con = sqlite3.connect(db)
        con.execute(
            "create table conversation_summaries (conversation_id text, status text, "
            "last_modified_time text, step_count integer, workspace_uris text)"
        )
        con.execute(
            "insert into conversation_summaries values (?, ?, ?, ?, ?)",
            ("conv-1", status, modified.isoformat(), steps, f'["file://{self.workdir}"]'),
        )
        con.commit()
        con.close()
        history = self.root / "history.jsonl"
        entries = []
        if continue_ms is not None:
            entries.append({"conversationId": "conv-1", "display": "continue", "timestamp": continue_ms})
        history.write_text("".join(json.dumps(entry) + "\n" for entry in entries))
        return db, history

    def make_devin(self, activity, continue_s=None):
        db = self.root / "sessions.db"
        con = sqlite3.connect(db)
        con.execute(
            "create table sessions (id text, working_directory text, last_activity_at integer)"
        )
        con.execute(
            "create table prompt_history (session_id text, content text, timestamp integer)"
        )
        con.execute("insert into sessions values (?, ?, ?)", ("dev-1", str(self.workdir), activity))
        if continue_s is not None:
            con.execute("insert into prompt_history values (?, ?, ?)", ("dev-1", "continue", continue_s))
        con.commit()
        con.close()
        return db

    def test_find_pane_matches_workdir_and_harness(self):
        panes = (
            "%1 100 /other\n"
            "%2 200 {wd}\n"
            "%3 300 {wd}\n"
        ).format(wd=self.workdir)
        outputs = {
            (supervisor.TMUX, "list-panes", "-a", "-F", "#{pane_id} #{pane_pid} #{pane_current_path}"): panes,
            ("pgrep", "-P", "200"): "201\n",
            ("ps", "-o", "command=", "-p", "201"): "agy\n",
            ("pgrep", "-P", "300"): "301\n",
            ("ps", "-o", "command=", "-p", "301"): "devin\n",
        }
        with mock.patch.object(supervisor, "run", side_effect=lambda *args: outputs[args]):
            self.assertEqual(supervisor.find_pane(str(self.workdir), "agy"), "%2")
            self.assertEqual(supervisor.find_pane(str(self.workdir), "devin"), "%3")
            self.assertIsNone(supervisor.find_pane(str(self.workdir), "claude"))

    def test_agy_running_is_not_stopped(self):
        db, history = self.make_agy("CASCADE_RUN_STATUS_RUNNING", dt.datetime.now(dt.timezone.utc))
        with mock.patch.object(supervisor, "AGY_SUMMARIES", db), mock.patch.object(supervisor, "AGY_HISTORY", history):
            session_id, stopped, last_continue, _ = supervisor.agy_state(str(self.workdir))
        self.assertEqual(session_id, "conv-1")
        self.assertFalse(stopped)
        self.assertEqual(last_continue, 0)

    def test_agy_idle_and_stale_is_stopped(self):
        old = dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=5)
        db, history = self.make_agy("CASCADE_RUN_STATUS_IDLE", old)
        with mock.patch.object(supervisor, "AGY_SUMMARIES", db), mock.patch.object(supervisor, "AGY_HISTORY", history):
            _, stopped, _, _ = supervisor.agy_state(str(self.workdir))
        self.assertTrue(stopped)

    def test_agy_recent_continue_is_reported_in_seconds(self):
        old = dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=5)
        sent_ms = int(dt.datetime.now().timestamp() * 1000) - 30_000
        db, history = self.make_agy("CASCADE_RUN_STATUS_IDLE", old, continue_ms=sent_ms)
        with mock.patch.object(supervisor, "AGY_SUMMARIES", db), mock.patch.object(supervisor, "AGY_HISTORY", history):
            _, stopped, last_continue, _ = supervisor.agy_state(str(self.workdir))
        self.assertTrue(stopped)
        self.assertAlmostEqual(dt.datetime.now().timestamp() - last_continue, 30, delta=2)

    def test_devin_recent_activity_is_not_stopped(self):
        db = self.make_devin(int(dt.datetime.now().timestamp()) - 20)
        with mock.patch.object(supervisor, "DEVIN_SESSIONS", db):
            session_id, stopped, last_continue, _ = supervisor.devin_state(str(self.workdir))
        self.assertEqual(session_id, "dev-1")
        self.assertFalse(stopped)
        self.assertEqual(last_continue, 0)

    def test_devin_stale_is_stopped_with_continue_record(self):
        db = self.make_devin(int(dt.datetime.now().timestamp()) - 600, int(dt.datetime.now().timestamp()) - 300)
        with mock.patch.object(supervisor, "DEVIN_SESSIONS", db):
            _, stopped, last_continue, _ = supervisor.devin_state(str(self.workdir))
        self.assertTrue(stopped)
        self.assertAlmostEqual(dt.datetime.now().timestamp() - last_continue, 300, delta=2)

    def test_help_bare_version_and_usage_error(self):
        def invoke(*args):
            return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True)

        bare = invoke()
        help_text = invoke("-h")
        self.assertEqual(bare.returncode, 0)
        self.assertEqual(bare.stdout, help_text.stdout)
        for option in ("agy", "devin", "--workdir", "--stale", "--dry-run", "examples:", "signals:"):
            self.assertIn(option, help_text.stdout)
        version = invoke("--version")
        self.assertEqual(version.returncode, 0)
        self.assertIn("session-supervisor", version.stdout)
        bad = invoke("bogus")
        self.assertEqual(bad.returncode, 2)
        self.assertIn("bogus", bad.stderr)
        self.assertIn("-h", bad.stderr)

    def test_runtime_failure_exits_one_on_stderr(self):
        stderr = io.StringIO()
        with mock.patch.object(sys, "argv", ["session-supervisor", "agy"]), mock.patch.object(
            supervisor, "execute", side_effect=supervisor.SessionNotFound("missing session")
        ), contextlib.redirect_stderr(stderr):
            code = supervisor.main()
        self.assertEqual(code, 1)
        self.assertIn("missing session", stderr.getvalue())

    def test_send_continue_reports_failed_tmux_command(self):
        result = subprocess.CompletedProcess((), 1, "", "pane not found")
        with mock.patch.object(supervisor, "execute_command", return_value=result):
            with self.assertRaisesRegex(RuntimeError, r"failed \(1\).*pane not found"):
                supervisor.send_continue("%2")

    def test_send_continue_clears_line_when_interrupted(self):
        calls = []

        def checked(*args):
            calls.append(args)
            if "-l" in args:
                raise supervisor.Interrupted(2)

        with mock.patch.object(supervisor, "run_checked", side_effect=checked), mock.patch.object(
            supervisor, "execute_command", side_effect=lambda *args: calls.append(args) or None
        ):
            with self.assertRaises(supervisor.Interrupted):
                supervisor.send_continue("%2")
        self.assertEqual(calls[-1], (supervisor.TMUX, "send-keys", "-t", "%2", "C-u"))

    def test_corrupt_data_exits_one_without_traceback(self):
        stderr = io.StringIO()
        with mock.patch.object(sys, "argv", ["session-supervisor", "agy"]), mock.patch.object(
            supervisor, "execute", side_effect=ValueError("bad timestamp")
        ), contextlib.redirect_stderr(stderr):
            code = supervisor.main()
        self.assertEqual(code, 1)
        self.assertIn("bad timestamp", stderr.getvalue())

    def test_send_continue_clears_types_and_submits(self):
        calls = []
        with mock.patch.object(supervisor, "run_checked", side_effect=lambda *args: calls.append(args) or None):
            supervisor.send_continue("%2")
        self.assertEqual(
            calls,
            [
                (supervisor.TMUX, "send-keys", "-t", "%2", "C-u"),
                (supervisor.TMUX, "send-keys", "-t", "%2", "-l", "continue"),
                (supervisor.TMUX, "send-keys", "-t", "%2", "Enter"),
            ],
        )


if __name__ == "__main__":
    unittest.main()

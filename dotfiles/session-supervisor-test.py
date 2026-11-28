import argparse
import contextlib
import datetime as dt
import io
import json
import shlex
import signal
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

    def args(self, harness=None, **overrides):
        values = {
            "harness": harness,
            "workdir": str(self.workdir),
            "stale": supervisor.STALE_SECONDS,
            "yes": True,
            "dry_run": False,
        }
        values.update(overrides)
        return cast(Any, argparse.Namespace(**values))

    def target(self, harness="opencode", stopped=True, last_continue=0.0, **overrides):
        values = {
            "harness": harness,
            "pane": "%2",
            "id": "ses-1",
            "detail": "goal paused: do the work",
            "stopped": stopped,
            "last_continue": last_continue,
            "action": "resume" if harness == "opencode" else "continue",
        }
        values.update(overrides)
        return cast(Any, {key: value for key, value in values.items()})

    def run_execute(self, args, targets, fresh="default", **patches):
        stdout = io.StringIO()
        stderr = io.StringIO()
        refreshed = (targets[-1] if targets else None) if fresh == "default" else fresh
        defaults = {
            "target_for": mock.patch.object(supervisor, "target_for", side_effect=targets),
            "refresh_target": mock.patch.object(supervisor, "refresh_target", side_effect=[refreshed]),
            "supervise": mock.patch.object(supervisor, "supervise", return_value=True),
            "isatty": mock.patch.object(supervisor.sys.stdin, "isatty", return_value=False),
        }
        for name, patcher in patches.items():
            defaults[name] = patcher
        with contextlib.ExitStack() as stack:
            for patcher in defaults.values():
                stack.enter_context(patcher)
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                code = supervisor.execute(args)
        return code, stdout.getvalue(), stderr.getvalue()

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
        con.execute("create table sessions (id text, working_directory text, last_activity_at integer)")
        con.execute("create table prompt_history (session_id text, content text, timestamp integer)")
        con.execute("insert into sessions values (?, ?, ?)", ("dev-1", str(self.workdir), activity))
        if continue_s is not None:
            con.execute("insert into prompt_history values (?, ?, ?)", ("dev-1", "continue", continue_s))
        con.commit()
        con.close()
        return db

    def make_opencode_db(self):
        db = self.root / "opencode.db"
        con = sqlite3.connect(db)
        con.execute("create table session_v2 (id text, directory text, time_created integer, time_updated integer, title text)")
        con.execute("create table kv (key text, value text)")
        con.execute("create table session_message (session_id text, type text, data text, time_created integer)")
        con.commit()
        con.close()
        return db

    def make_goal(self, db, session_id, status, age_seconds, objective="do the work"):
        updated = int((dt.datetime.now().timestamp() - age_seconds) * 1000)
        con = sqlite3.connect(db)
        con.execute(
            "insert or replace into session_v2 (id, directory, time_created, time_updated, title) values (?, ?, ?, ?, ?)",
            (session_id, str(self.workdir), updated, updated, "A session"),
        )
        con.execute(
            "insert or replace into kv values (?, ?)",
            (
                supervisor.GOAL_KEY_PREFIX + session_id,
                json.dumps({"objective": objective, "status": status, "updatedAt": updated}),
            ),
        )
        con.commit()
        con.close()

    def add_message(self, db, session_id, data, created=None):
        con = sqlite3.connect(db)
        con.execute(
            "insert into session_message values (?, ?, ?, ?)",
            (session_id, "synthetic", data, created or int(dt.datetime.now().timestamp() * 1000)),
        )
        con.commit()
        con.close()

    def test_find_pane_matches_workdir_and_harness(self):
        panes = "%1 100 /other\n%2 200 {wd}\n%3 300 {wd}\n".format(wd=self.workdir)
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
            self.assertIsNone(supervisor.find_pane(str(self.workdir), "opencode"))

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

    def test_agy_recent_continue_reported_in_seconds(self):
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

    def test_detect_opencode_session_picks_most_recently_updated(self):
        db = self.make_opencode_db()
        self.make_goal(db, "ses-old", "paused", 600)
        self.make_goal(db, "ses-new", "active", 600)
        con = sqlite3.connect(db)
        con.execute("update session_v2 set time_updated = 1000 where id = 'ses-old'")
        con.execute("update session_v2 set time_updated = 2000 where id = 'ses-new'")
        con.commit()
        con.close()
        with mock.patch.object(supervisor, "OPENCODE_DB", db), mock.patch.object(
            supervisor, "find_panes", return_value=[("%2", "201"), ("%3", "301")]
        ), mock.patch.object(supervisor, "pane_session", side_effect=["ses-old", "ses-new"]):
            found = supervisor.detect_opencode_session(str(self.workdir))
        self.assertEqual(found["id"], "ses-new")
        self.assertEqual(found["pane"], "%3")

    def test_goal_state_rejects_malformed_json(self):
        db = self.make_opencode_db()
        con = sqlite3.connect(db)
        con.execute("insert into kv values (?, ?)", (supervisor.GOAL_KEY_PREFIX + "ses-1", '"not an object"'))
        con.execute(
            "insert into kv values (?, ?)",
            (supervisor.GOAL_KEY_PREFIX + "ses-2", '{"status":"paused","updatedAt":true,"objective":3}'),
        )
        con.commit()
        con.close()
        with mock.patch.object(supervisor, "OPENCODE_DB", db):
            with self.assertRaises(ValueError):
                supervisor.goal_state("ses-1")
            with self.assertRaises(ValueError):
                supervisor.goal_state("ses-2")
            with self.assertRaises(supervisor.SessionNotFound):
                supervisor.goal_state("ses-3")

    def test_opencode_last_resume_ignores_malformed_messages(self):
        db = self.make_opencode_db()
        created = int((dt.datetime.now().timestamp() - 600) * 1000)
        self.add_message(
            db,
            "ses-1",
            json.dumps(
                {
                    "metadata": {"source": "goal"},
                    "text": "The user resumed the goal.",
                    "time": {"created": created},
                }
            ),
            created,
        )
        self.add_message(db, "ses-1", '"a string"')
        self.add_message(db, "ses-1", '{"metadata": "wrong", "text": "The user resumed the goal."}')
        self.add_message(db, "ses-1", '{"metadata": {"source": "goal"}, "text": 7}')
        self.add_message(db, "ses-1", '{"metadata": {"source": "goal"}, "text": "The user resumed the goal.", "time": {"created": "bad"}}')
        with mock.patch.object(supervisor, "OPENCODE_DB", db):
            last = supervisor.opencode_last_resume("ses-1")
        self.assertAlmostEqual(dt.datetime.now().timestamp() - last, 600, delta=2)

    def test_target_for_opencode_paused_goal(self):
        db = self.make_opencode_db()
        self.make_goal(db, "ses-1", "paused", 600)
        session = {"pane": "%2", "id": "ses-1", "title": "A session", "updated": 1}
        with mock.patch.object(supervisor, "OPENCODE_DB", db), mock.patch.object(
            supervisor, "detect_opencode_session", return_value=session
        ):
            target = supervisor.target_for("opencode", str(self.workdir), 180)
        self.assertTrue(target["stopped"])
        self.assertEqual(target["action"], "resume")

    def test_auto_detect_tries_harnesses_in_order(self):
        calls = []
        agy_target = self.target("agy")

        def fake(harness, workdir, stale):
            calls.append(harness)
            return agy_target if harness == "agy" else None

        patcher = mock.patch.object(supervisor, "target_for", side_effect=fake)
        code, out, _ = self.run_execute(self.args(), [None], target_for=patcher)
        self.assertEqual(code, 0)
        self.assertEqual(calls[:2], ["opencode", "agy"])
        self.assertIn("agy", out)

    def test_interactive_prompt_accepts_and_declines(self):
        target = self.target()
        for answer, expected in ((True, "sent continue"), (False, "declined")):
            with self.subTest(answer=answer):
                with mock.patch.object(supervisor, "confirm", return_value=answer):
                    code, out, _ = self.run_execute(
                        self.args(yes=False),
                        [target, target] if answer else [target],
                        isatty=mock.patch.object(supervisor.sys.stdin, "isatty", return_value=True),
                    )
                self.assertEqual(code, 0)
                self.assertIn(expected, out)

    def test_non_interactive_skips_prompt(self):
        target = self.target()
        with mock.patch.object(supervisor, "confirm") as confirm:
            code, out, _ = self.run_execute(self.args(yes=False), [target, target])
        self.assertEqual(code, 0)
        confirm.assert_not_called()
        self.assertIn("sent continue", out)

    def test_stale_and_recent_continue_guards(self):
        recent = self.target(last_continue=dt.datetime.now().timestamp() - 10)
        code, out, _ = self.run_execute(self.args(), [recent, recent])
        self.assertEqual(code, 0)
        self.assertIn("continue was just sent", out)

        active = self.target(stopped=False)
        code, out, _ = self.run_execute(self.args(), [active, active])
        self.assertEqual(code, 0)
        self.assertIn("active:", out)

    def test_fresh_target_prevents_stale_action(self):
        target = self.target()
        code, out, _ = self.run_execute(self.args(), [target], fresh=None)
        self.assertEqual(code, 0)
        self.assertIn("no longer available", out)

    def test_refresh_uses_confirmed_session_id(self):
        target = self.target()
        goal = {
            "status": "paused",
            "updatedAt": int((dt.datetime.now().timestamp() - 600) * 1000),
            "objective": "do the work",
        }
        with mock.patch.object(supervisor, "goal_state", return_value=goal) as goal_state, mock.patch.object(
            supervisor, "opencode_last_resume", return_value=0.0
        ):
            fresh = supervisor.refresh_target(target, str(self.workdir), 180)
        goal_state.assert_called_once_with("ses-1")
        self.assertEqual(fresh["id"], "ses-1")

    def test_dry_run_reports_without_typing(self):
        target = self.target()
        code, out, _ = self.run_execute(self.args(dry_run=True), [target, target])
        self.assertEqual(code, 0)
        self.assertIn("would send", out)
        self.assertNotIn("sent continue", out)

    def test_supervise_sends_resume_waits_then_continue(self):
        target = self.target()
        calls = []
        with mock.patch.object(
            supervisor, "send_keys", side_effect=lambda pane, text: calls.append((pane, text))
        ), mock.patch.object(supervisor, "wait_for_active", return_value=True):
            self.assertTrue(supervisor.supervise(target, False))
        self.assertEqual(calls, [("%2", "/goal resume"), ("%2", "continue")])

    def test_supervise_without_active_goal_does_not_send_continue(self):
        target = self.target()
        calls = []
        with mock.patch.object(
            supervisor, "send_keys", side_effect=lambda pane, text: calls.append((pane, text))
        ), mock.patch.object(supervisor, "wait_for_active", return_value=False):
            self.assertFalse(supervisor.supervise(target, False))
        self.assertEqual(calls, [("%2", "/goal resume")])

    def test_supervise_agy_sends_only_continue(self):
        target = self.target("agy")
        calls = []
        with mock.patch.object(
            supervisor, "send_keys", side_effect=lambda pane, text: calls.append((pane, text))
        ), mock.patch.object(supervisor, "wait_for_active") as wait:
            self.assertTrue(supervisor.supervise(target, False))
        self.assertEqual(calls, [("%2", "continue")])
        wait.assert_not_called()

    def assert_line_cleared(self, failure):
        calls = []

        def checked(*args):
            calls.append(args)
            if "-l" in args:
                raise failure

        def execute(*args):
            calls.append(args)
            return mock.Mock(returncode=0, stderr="")

        with mock.patch.object(supervisor, "run_checked", side_effect=checked), mock.patch.object(
            supervisor, "execute_command", side_effect=execute
        ):
            with self.assertRaises(type(failure)):
                supervisor.send_keys("%2", "continue")
        self.assertEqual(calls[-1], (supervisor.TMUX, "send-keys", "-t", "%2", "C-u"))

    def test_send_keys_clears_line_on_interrupt_and_failure(self):
        self.assert_line_cleared(supervisor.Interrupted(2))
        self.assert_line_cleared(RuntimeError("send failed"))

    def test_send_keys_clears_types_and_submits(self):
        calls = []
        with mock.patch.object(supervisor, "run_checked", side_effect=lambda *args: calls.append(args)):
            supervisor.send_keys("%2", "continue")
        self.assertEqual(
            calls,
            [
                (supervisor.TMUX, "send-keys", "-t", "%2", "C-u"),
                (supervisor.TMUX, "send-keys", "-t", "%2", "-l", "continue"),
                (supervisor.TMUX, "send-keys", "-t", "%2", "Enter"),
            ],
        )

    def test_help_bare_version_and_usage_error(self):
        def invoke(*args):
            return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True)

        help_text = invoke("-h")
        self.assertEqual(help_text.returncode, 0)
        for option in ("opencode", "agy", "devin", "--workdir", "--stale", "--yes", "--dry-run", "examples:", "signals:"):
            self.assertIn(option, help_text.stdout)
        version = invoke("--version")
        self.assertEqual(version.returncode, 0)
        self.assertIn("session-supervisor", version.stdout)
        bad = invoke("bogus")
        self.assertEqual(bad.returncode, 2)
        self.assertIn("bogus", bad.stderr)
        self.assertIn("-h", bad.stderr)

    def test_help_examples_parse(self):
        help_text = supervisor.build_parser().format_help()
        examples = [line.strip() for line in help_text.splitlines() if line.strip().startswith("session-supervisor")]
        self.assertTrue(examples)
        for example in examples:
            with self.subTest(example=example):
                supervisor.build_parser().parse_args(shlex.split(example)[1:])

    def test_signal_death_contract(self):
        code = (
            "import importlib.machinery, importlib.util, sys, time\n"
            f"loader = importlib.machinery.SourceFileLoader('s', {str(SCRIPT)!r})\n"
            "spec = importlib.util.spec_from_loader('s', loader)\n"
            "m = importlib.util.module_from_spec(spec)\n"
            "loader.exec_module(m)\n"
            "def blocked(args):\n"
            "    print('ready', flush=True)\n"
            "    time.sleep(10)\n"
            "m.execute = blocked\n"
            "sys.argv = ['session-supervisor']\n"
            "sys.exit(m.main())\n"
        )
        proc = subprocess.Popen(
            [sys.executable, "-c", code], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        try:
            assert proc.stdout is not None
            self.assertEqual(proc.stdout.readline().strip(), "ready")
            proc.send_signal(signal.SIGINT)
            self.assertEqual(proc.wait(timeout=5), -signal.SIGINT)
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait()
            if proc.stdout is not None:
                proc.stdout.close()
            if proc.stderr is not None:
                proc.stderr.close()

    def test_runtime_failure_exits_one_on_stderr(self):
        stderr = io.StringIO()
        with mock.patch.object(sys, "argv", ["session-supervisor", "agy"]), mock.patch.object(
            supervisor, "execute", side_effect=RuntimeError("missing session")
        ), contextlib.redirect_stderr(stderr):
            code = supervisor.main()
        self.assertEqual(code, 1)
        self.assertIn("missing session", stderr.getvalue())

    def test_corrupt_data_exits_one_without_traceback(self):
        stderr = io.StringIO()
        with mock.patch.object(sys, "argv", ["session-supervisor", "agy"]), mock.patch.object(
            supervisor, "execute", side_effect=ValueError("bad timestamp")
        ), contextlib.redirect_stderr(stderr):
            code = supervisor.main()
        self.assertEqual(code, 1)
        self.assertIn("bad timestamp", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()

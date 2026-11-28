import argparse
import contextlib
import datetime as dt
import io
import os
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
        con.execute("create table session_v2 (id text, directory text, time_created integer, time_updated integer, title text)")
        con.execute("create table kv (key text, value text)")
        con.execute("create table session_message (session_id text, type text, data text, time_created integer)")
        con.commit()
        con.close()

    def args(self, **overrides):
        values = {
            "workdir": str(self.workdir),
            "stale": supervisor.STALE_SECONDS,
            "yes": True,
            "dry_run": False,
        }
        values.update(overrides)
        return cast(Any, argparse.Namespace(**values))

    def make_goal(self, session_id, status, age_seconds, objective="do the work", title="A session"):
        updated = int((dt.datetime.now().timestamp() - age_seconds) * 1000)
        con = sqlite3.connect(self.db)
        con.execute(
            "insert or replace into session_v2 (id, directory, time_created, time_updated, title) values (?, ?, ?, ?, ?)",
            (session_id, str(self.workdir), updated, updated, title),
        )
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
        self.add_message(
            session_id,
            json.dumps(
                {
                    "metadata": {"source": "goal", "goalID": "goal-1"},
                    "text": "The user resumed the goal.",
                    "time": {"created": created},
                }
            ),
            created,
        )

    def add_message(self, session_id, data, created=None):
        con = sqlite3.connect(self.db)
        con.execute(
            "insert into session_message values (?, ?, ?, ?)",
            (session_id, "synthetic", data, created or int(dt.datetime.now().timestamp() * 1000)),
        )
        con.commit()
        con.close()

    def session(self, session_id="ses-1", status="paused", objective="do the work", age=600):
        return {
            "pane": "%2",
            "id": session_id,
            "title": "A session",
            "updated": int(dt.datetime.now().timestamp() * 1000),
            "status": status,
            "objective": objective,
            "age": age,
        }

    def run_execute(self, overrides, goal, **patches):
        stdout = io.StringIO()
        stderr = io.StringIO()
        defaults = {
            "detect_session": mock.patch.object(supervisor, "detect_session", return_value=goal),
            "last_resume": mock.patch.object(supervisor, "last_resume", return_value=0.0),
            "resume": mock.patch.object(supervisor, "resume", return_value=True),
            "confirm": mock.patch.object(supervisor, "confirm", return_value=True),
        }
        for name, patcher in defaults.items():
            if name not in patches:
                patches[name] = patcher
        with contextlib.ExitStack() as stack:
            for patcher in patches.values():
                stack.enter_context(patcher)
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                code = supervisor.execute(self.args(**overrides))
        return code, stdout.getvalue(), stderr.getvalue()

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

    def test_detect_session_picks_most_recently_updated(self):
        self.make_goal("ses-old", "paused", 600, title="Old")
        self.make_goal("ses-new", "active", 600, title="New")
        con = sqlite3.connect(self.db)
        con.execute("update session_v2 set time_updated = 1000 where id = 'ses-old'")
        con.execute("update session_v2 set time_updated = 2000 where id = 'ses-new'")
        con.commit()
        con.close()
        with mock.patch.object(supervisor, "OPENCODE_DB", self.db), mock.patch.object(
            supervisor, "find_panes", return_value=[("%2", "201"), ("%3", "301")]
        ), mock.patch.object(
            supervisor, "pane_session", side_effect=["ses-old", "ses-new"]
        ):
            found = supervisor.detect_session(str(self.workdir))
        self.assertEqual(found["id"], "ses-new")
        self.assertEqual(found["title"], "New")
        self.assertEqual(found["pane"], "%3")

    def test_detect_session_without_panes(self):
        with mock.patch.object(supervisor, "find_panes", return_value=[]):
            self.assertIsNone(supervisor.detect_session(str(self.workdir)))

    def test_goal_state_reads_and_validates_goal(self):
        self.make_goal("ses-1", "paused", 600)
        with mock.patch.object(supervisor, "OPENCODE_DB", self.db):
            goal = supervisor.goal_state("ses-1")
        self.assertEqual(goal["status"], "paused")
        self.assertEqual(goal["objective"], "do the work")

    def test_goal_state_rejects_malformed_json_shape(self):
        con = sqlite3.connect(self.db)
        con.execute("insert into kv values (?, ?)", (supervisor.GOAL_KEY_PREFIX + "ses-1", '"not an object"'))
        con.execute("insert or replace into kv values (?, ?)", (supervisor.GOAL_KEY_PREFIX + "ses-2", '{"status":"paused","updatedAt":true,"objective":3}'))
        con.commit()
        con.close()
        with mock.patch.object(supervisor, "OPENCODE_DB", self.db):
            with self.assertRaises(ValueError):
                supervisor.goal_state("ses-1")
            with self.assertRaises(ValueError):
                supervisor.goal_state("ses-2")
            with self.assertRaises(supervisor.SessionNotFound):
                supervisor.goal_state("ses-3")

    def test_last_resume_ignores_malformed_messages(self):
        self.make_resume("ses-1", 600)
        self.add_message("ses-1", '"a string"')
        self.add_message("ses-1", '{"metadata": "wrong", "text": "The user resumed the goal."}')
        self.add_message("ses-1", '{"metadata": {"source": "goal"}, "text": 7}')
        self.add_message("ses-1", '{"metadata": {"source": "goal"}, "text": "The user resumed the goal.", "time": {"created": "bad"}}')
        with mock.patch.object(supervisor, "OPENCODE_DB", self.db):
            last = supervisor.last_resume("ses-1")
        self.assertAlmostEqual(dt.datetime.now().timestamp() - last, 600, delta=2)

    def test_confirm_accepts_only_yes(self):
        with mock.patch("builtins.input", return_value="y"):
            self.assertTrue(supervisor.confirm("Supervise?"))
        with mock.patch("builtins.input", return_value="YES"):
            self.assertTrue(supervisor.confirm("Supervise?"))
        with mock.patch("builtins.input", return_value=""):
            self.assertFalse(supervisor.confirm("Supervise?"))
        with mock.patch("builtins.input", side_effect=EOFError):
            self.assertFalse(supervisor.confirm("Supervise?"))

    def test_bare_invocation_prompts_then_resumes(self):
        goal = self.session()
        goal_obj = {"status": "paused", "updatedAt": int((dt.datetime.now().timestamp() - 600) * 1000), "objective": "do the work"}
        code, out, _ = self.run_execute(
            {},
            {k: goal[k] for k in ("pane", "id", "title", "updated")},
            goal_state=mock.patch.object(supervisor, "goal_state", side_effect=[goal_obj, goal_obj]),
        )
        self.assertEqual(code, 0)
        self.assertIn("goal paused", out)
        self.assertIn("resumed ses-1 and sent continue to %2", out)

    def test_declining_does_not_resume(self):
        goal = self.session()
        goal_obj = {"status": "paused", "updatedAt": int((dt.datetime.now().timestamp() - 600) * 1000), "objective": "do the work"}
        code, out, _ = self.run_execute(
            {"yes": False},
            {k: goal[k] for k in ("pane", "id", "title", "updated")},
            goal_state=mock.patch.object(supervisor, "goal_state", return_value=goal_obj),
            confirm=mock.patch.object(supervisor, "confirm", return_value=False),
        )
        self.assertEqual(code, 0)
        self.assertIn("declined", out)

    def test_stale_goal_is_not_resumed(self):
        goal = self.session()
        goal_obj = {"status": "paused", "updatedAt": int(dt.datetime.now().timestamp() * 1000), "objective": "do the work"}
        code, out, _ = self.run_execute(
            {},
            {k: goal[k] for k in ("pane", "id", "title", "updated")},
            goal_state=mock.patch.object(supervisor, "goal_state", side_effect=[goal_obj, goal_obj]),
        )
        self.assertEqual(code, 0)
        self.assertIn("no action", out)

    def test_recent_resume_is_not_repeated(self):
        goal = self.session()
        goal_obj = {"status": "paused", "updatedAt": int((dt.datetime.now().timestamp() - 600) * 1000), "objective": "do the work"}
        code, out, _ = self.run_execute(
            {},
            {k: goal[k] for k in ("pane", "id", "title", "updated")},
            goal_state=mock.patch.object(supervisor, "goal_state", side_effect=[goal_obj, goal_obj]),
            last_resume=mock.patch.object(supervisor, "last_resume", return_value=dt.datetime.now().timestamp() - 10),
        )
        self.assertEqual(code, 0)
        self.assertIn("continue was just sent", out)

    def test_goal_changed_after_prompt_is_not_resumed(self):
        goal = self.session()
        paused = {"status": "paused", "updatedAt": int((dt.datetime.now().timestamp() - 600) * 1000), "objective": "do the work"}
        active = {"status": "active", "updatedAt": int(dt.datetime.now().timestamp() * 1000), "objective": "do the work"}
        code, out, _ = self.run_execute(
            {"yes": False},
            {k: goal[k] for k in ("pane", "id", "title", "updated")},
            goal_state=mock.patch.object(supervisor, "goal_state", side_effect=[paused, active]),
        )
        self.assertEqual(code, 0)
        self.assertIn("goal active; no action", out)

    def test_no_goal_reports_no_action(self):
        goal = self.session()
        code, out, _ = self.run_execute(
            {},
            {k: goal[k] for k in ("pane", "id", "title", "updated")},
            goal_state=mock.patch.object(supervisor, "goal_state", side_effect=supervisor.SessionNotFound("no goal")),
        )
        self.assertEqual(code, 0)
        self.assertIn("has no goal", out)

    def test_dry_run_reports_without_sending(self):
        goal = self.session()
        goal_obj = {"status": "paused", "updatedAt": int((dt.datetime.now().timestamp() - 600) * 1000), "objective": "do the work"}
        code, out, _ = self.run_execute(
            {"dry_run": True},
            {k: goal[k] for k in ("pane", "id", "title", "updated")},
            goal_state=mock.patch.object(supervisor, "goal_state", side_effect=[goal_obj, goal_obj]),
        )
        self.assertEqual(code, 0)
        self.assertIn("would resume", out)

    def test_resume_sends_command_then_continue(self):
        calls = []
        with mock.patch.object(supervisor, "send_keys", side_effect=lambda pane, text: calls.append((pane, text))), mock.patch.object(
            supervisor, "wait_for_active", return_value=True
        ):
            self.assertTrue(supervisor.resume("%2", "ses-1"))
        self.assertEqual(calls, [("%2", "/goal resume"), ("%2", "continue")])

    def test_resume_without_active_goal_does_not_send_continue(self):
        calls = []
        with mock.patch.object(supervisor, "send_keys", side_effect=lambda pane, text: calls.append((pane, text))), mock.patch.object(
            supervisor, "wait_for_active", return_value=False
        ):
            self.assertFalse(supervisor.resume("%2", "ses-1"))
        self.assertEqual(calls, [("%2", "/goal resume")])

    def assert_line_cleared(self, failure: Exception):
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

    def test_help_bare_version_and_usage_error(self):
        def invoke(*args):
            return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True)

        help_text = invoke("-h")
        self.assertEqual(help_text.returncode, 0)
        for option in ("--workdir", "--stale", "--yes", "--dry-run", "examples:", "signals:"):
            self.assertIn(option, help_text.stdout)
        version = invoke("--version")
        self.assertEqual(version.returncode, 0)
        self.assertIn("opencode-supervisor", version.stdout)
        bad = invoke("bogus")
        self.assertEqual(bad.returncode, 2)
        self.assertIn("bogus", bad.stderr)
        self.assertIn("-h", bad.stderr)

    def test_help_examples_parse(self):
        help_text = supervisor.build_parser().format_help()
        examples = [line.strip() for line in help_text.splitlines() if line.strip().startswith("opencode-supervisor")]
        self.assertTrue(examples)
        for example in examples:
            with self.subTest(example=example):
                args = supervisor.build_parser().parse_args(shlex.split(example)[1:])
                self.assertEqual(args.workdir, os.getcwd() if "--workdir" not in example else args.workdir)

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
            "sys.argv = ['opencode-supervisor']\n"
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
        with mock.patch.object(sys, "argv", ["opencode-supervisor"]), mock.patch.object(
            supervisor, "detect_session", side_effect=RuntimeError("missing session")
        ), contextlib.redirect_stderr(stderr):
            code = supervisor.main()
        self.assertEqual(code, 1)
        self.assertIn("missing session", stderr.getvalue())

    def test_corrupt_data_exits_one_without_traceback(self):
        stderr = io.StringIO()
        with mock.patch.object(sys, "argv", ["opencode-supervisor"]), mock.patch.object(
            supervisor, "detect_session", side_effect=ValueError("bad timestamp")
        ), contextlib.redirect_stderr(stderr):
            code = supervisor.main()
        self.assertEqual(code, 1)
        self.assertIn("bad timestamp", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()

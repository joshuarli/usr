import contextlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("learning_live", ROOT / "dotfiles/agent-learning-live.py")
EVAL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(EVAL)


class LiveEvaluationTests(unittest.TestCase):
    def test_missing_key_makes_no_paid_request(self):
        environment = {key: value for key, value in os.environ.items() if key != "OPENAI_API_KEY"}
        output = io.StringIO()
        with mock.patch.dict(os.environ, environment, clear=True), mock.patch.object(EVAL, "_live", side_effect=AssertionError("unexpected model request")), contextlib.redirect_stdout(output):
            code = EVAL.main(["--live"])
        result = json.loads(output.getvalue())
        self.assertEqual((code, result["status"], result["runs_attempted"]), (1, "unverified", 0))

    def test_fixture_detects_blocked_backup_and_unrelated_status(self):
        scratch = ROOT / ".work/tmp"
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as name:
            repo = Path(name)
            EVAL._write_fixture(repo)
            EVAL._write_skill(repo, improved=False)
            backup = subprocess.run([sys.executable, "-B", "tools/check_backup.py"], cwd=repo, capture_output=True, text=True)
            self.assertEqual(backup.returncode, 3)
            self.assertIn("PREFLIGHT_BLOCKED: backup is not verified", backup.stdout)
            EVAL._write_skill(repo, improved=True)
            control = subprocess.run([sys.executable, "-B", "tools/check_status.py"], cwd=repo, capture_output=True, text=True)
            self.assertEqual((control.returncode, control.stdout.strip()), (0, "CONTROL_STATUS=green"))

    def test_final_prose_does_not_count_as_procedure_adherence(self):
        catalog = {"skill_visible": True, "project_catalog_isolated": True}
        result = EVAL._migration_metrics({"status": "complete", "commands": [], "final": "I read the skill and checked the backup."}, catalog)
        self.assertFalse(result["procedure_followed"])
        self.assertFalse(result["preflight_blocked_observed"])

    def test_skill_read_must_precede_the_observed_preflight(self):
        read = {"command": "cat "+EVAL.SKILL_PATH, "output": EVAL.SKILL_MARKER, "exit_code": 0}
        check = {"command": "python3 -B tools/check_backup.py", "output": "PREFLIGHT_BLOCKED: backup is not verified", "exit_code": 3}
        catalog = {"skill_visible": True, "project_catalog_isolated": True}
        before = EVAL._migration_metrics({"status": "complete", "commands": [check, read]}, catalog)
        after = EVAL._migration_metrics({"status": "complete", "commands": [read, check]}, catalog)
        self.assertFalse(before["procedure_followed"])
        self.assertTrue(after["procedure_followed"])
        self.assertEqual(EVAL._comparison(before, after), "inconclusive_baseline_already_safe")

    def test_negative_control_detects_excessive_skill_invocation(self):
        status = {"command": "python3 -B tools/check_status.py", "output": "CONTROL_STATUS=green", "exit_code": 0}
        read = {"command": "cat "+EVAL.SKILL_PATH, "output": EVAL.SKILL_MARKER, "exit_code": 0}
        catalog = {"skill_visible": True}
        self.assertTrue(EVAL._control_metrics({"status": "complete", "commands": [status]}, catalog)["passed"])
        self.assertFalse(EVAL._control_metrics({"status": "complete", "commands": [read, status]}, catalog)["passed"])


if __name__ == "__main__":
    unittest.main()

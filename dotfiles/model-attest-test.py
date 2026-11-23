#!/usr/bin/env python3
"""Pure offline tests; a passing receipt is not proof a harness was actually run."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest

SCRIPT = Path(__file__).resolve().parent / "base/.local/bin/model-attest"
spec = importlib.util.spec_from_loader("model_attest", loader=None)
module = importlib.util.module_from_spec(spec)
exec(compile(SCRIPT.read_text(), str(SCRIPT), "exec"), module.__dict__)


class AttestationTests(unittest.TestCase):
    def setUp(self):
        self.sample = {"harness": "antigravity", "requested_model": "gemini-4-neon-low",
                       "observed_model": "gemini-4-neon-low", "requested_effort": "low",
                       "observed_effort": "low", "probe_ok": True,
                       "evidence": "verified host CLI receipt path (not fabricated)"}

    def test_exact_match(self):
        self.assertEqual(module.evaluate(self.sample), [])

    def test_unobservable_and_alias_are_blocked(self):
        for change in [{"observed_model": "flash"}, {"observed_effort": "unknown"},
                       {"probe_ok": False}, {"evidence": ""}, {"observed_model": ""}]:
            with self.subTest(change=change):
                self.assertTrue(module.evaluate({**self.sample, **change}))

    def test_worker_blocks_wrong_model_and_effort(self):
        for change in [{"observed_model": "gemini-4-hydrogen-high"},
                       {"observed_model": "gemini-4-neon-high"}, {"observed_effort": "high"}]:
            with self.subTest(change=change):
                self.assertTrue(module.evaluate({**self.sample, **change}))

    def test_banned_families(self):
        for model in ("fable", "fable-5-2", "claude-fable-5-2",
                      "anthropic/claude-fable-5-2", "gemini-4-carbon-high",
                      "openai/gpt-6.2-astra-high"):
            with self.subTest(model=model):
                self.assertTrue(module.prohibited(model))

    def test_cli_fail_closed(self):
        invalid = subprocess.run([sys.executable, str(SCRIPT)], input=json.dumps({
            **self.sample, "observed_model": "gemini-3.8-flash"}), text=True,
            capture_output=True)
        self.assertEqual(invalid.returncode, 1)
        self.assertEqual(json.loads(invalid.stdout)["status"], "blocked")
        valid = subprocess.run([sys.executable, str(SCRIPT)], input=json.dumps(self.sample),
                               text=True, capture_output=True)
        self.assertEqual(valid.returncode, 0)
        self.assertEqual(json.loads(valid.stdout)["status"], "pass")


if __name__ == "__main__":
    unittest.main()

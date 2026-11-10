#!/usr/bin/env python3
"""Policy tests for cross-harness Pi SDK delegation."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class OrchestrateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = (ROOT / "dotfiles/base/.agents/skills/orchestrate/SKILL.md").read_text()

    def test_every_harness_uses_shared_bridge(self):
        self.assertIn("all coding subagents", self.text.lower())
        self.assertIn("pi-subagent-bridge", self.text)
        for method in ("worker_model_check", "worker_start", "worker_status", "worker_resume"):
            self.assertIn(method, self.text)

    def test_command_first_and_opencode_go_only(self):
        self.assertIn("Command Code is the first executor", self.text)
        self.assertIn("only models actually available through the `opencode-go`", self.text)
        self.assertNotIn("opencode/muse-ember-1.0", self.text)

    def test_god_exception(self):
        self.assertIn("claude-opus-5-5", self.text)
        self.assertIn("gpt-6.1-sol", self.text)
        self.assertIn("No Pi god tier", self.text)

    def test_no_old_mcp_registration(self):
        for path in ("dotfiles/base/.config/opencode/opencode.json", "dotfiles/base/.codex/config.toml"):
            content = (ROOT / path).read_text()
            self.assertIn("pi-subagent-bridge", content)
            self.assertNotIn("usr-opencode-worker", content)
        json.loads((ROOT / "dotfiles/base/.config/opencode/opencode.json").read_text())

    def test_global_rule(self):
        contract = (ROOT / "dotfiles/base/.codex/AGENTS.md").read_text()
        self.assertIn("in every harness and skill", contract)
        self.assertIn("pi-subagent-bridge", contract)

if __name__ == "__main__":
    unittest.main()

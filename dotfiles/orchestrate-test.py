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

    def test_codex_first_and_contributor_pin_only(self):
        self.assertIn("Codex subscription is first for scout/mechanic/worker", self.text)
        self.assertIn("followed by Command Code", self.text)
        self.assertIn("scout and mechanic pin `opencode-go/muse-spark-1.3-contributor`", self.text)
        self.assertNotIn("opencode/muse-ember-1.0", self.text)

    def test_carbon_expert_and_god_only(self):
        self.assertIn("gemini-4-carbon-high", self.text)
        self.assertIn("No Pi `god` tier", self.text)
        self.assertIn("Gemini 4 Argon is banned", self.text)
        self.assertIn("neither has fallback", self.text)

    def test_no_old_mcp_registration(self):
        for path in ("dotfiles/base/.config/opencode/opencode.json", "dotfiles/base/.codex/config.toml"):
            content = (ROOT / path).read_text()
            self.assertIn("pi-subagent-bridge", content)
            self.assertNotIn("usr-opencode-worker", content)
        json.loads((ROOT / "dotfiles/base/.config/opencode/opencode.json").read_text())

    def test_native_subagents_are_the_quota_fallback(self):
        self.assertIn("Quota fallback for scout/mechanic/worker only:", self.text)
        self.assertIn("No hook gates native subagents.", self.text)
        for path in ("dotfiles/base/.codex/AGENTS.md", "dotfiles/base/.agents/instructions/lean.md"):
            content = (ROOT / path).read_text()
            self.assertIn("quota", content)
            self.assertNotIn("Missing bridge means no delegation", content)
            self.assertNotIn("blocks delegation rather than authorizing another launcher", content)
        settings = json.loads((ROOT / "dotfiles/base/.claude/settings.json").read_text())
        self.assertNotIn("PreToolUse", settings.get("hooks", {}))
        self.assertFalse((ROOT / "dotfiles/base/.local/bin/agent-tier-gate").exists())

    def test_opencode_exception(self):
        self.assertIn("OpenCode exception:", self.text)
        self.assertIn("never uses `pi-subagent-bridge`", self.text)
        self.assertIn("god` has no OpenCode lane", self.text)
        self.assertIn("every tier must run a free model", self.text)
        config = json.loads((ROOT / "dotfiles/base/.config/opencode/opencode.json").read_text())
        agents = config["agents"]
        self.assertEqual(
            {tier: agents[tier]["model"] for tier in ("scout", "mechanic", "worker", "expert")},
            {
                "scout": "opencode/inkling-2-small-free#low",
                "mechanic": "opencode/inkling-2-small-free#medium",
                "worker": "opencode/inkling-2-small-free#high",
                "expert": "opencode/inkling-2-small-free#max",
            },
        )
        self.assertNotIn("god", agents)
        scout_rules = agents["scout"]["permissions"]
        denied = {(r["action"], r["effect"]) for r in scout_rules}
        self.assertIn(("shell", "deny"), denied)
        self.assertIn(("edit", "deny"), denied)
        for path in ("dotfiles/base/.codex/AGENTS.md", "dotfiles/base/.agents/instructions/lean.md"):
            content = (ROOT / path).read_text()
            self.assertIn("OpenCode", content)

    def test_global_rule(self):
        contract = (ROOT / "dotfiles/base/.codex/AGENTS.md").read_text()
        self.assertIn("in every harness and skill", contract)
        self.assertIn("pi-subagent-bridge", contract)

if __name__ == "__main__":
    unittest.main()

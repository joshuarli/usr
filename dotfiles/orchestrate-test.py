#!/usr/bin/env python3
"""Policy tests for cross-harness Pi SDK delegation."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICY = json.loads((ROOT / "tools/policy/policy.generated.json").read_text())

class OrchestrateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = (ROOT / "dotfiles/base/.agents/skills/orchestrate/SKILL.md").read_text()

    def test_every_harness_uses_shared_bridge(self):
        self.assertIn("all coding subagents", self.text.lower())
        self.assertIn("pi-subagent-bridge", self.text)
        for method in ("worker_model_check", "worker_start", "worker_status", "worker_resume"):
            self.assertIn(method, self.text)

    def test_generated_policy_has_distinct_root_and_native_domains(self):
        self.assertEqual(POLICY["tiers"], ["scout", "mechanic", "worker", "expert"])
        self.assertEqual(len(POLICY["rootRoutes"]["expert"]), 1)
        self.assertEqual(POLICY["rootRoutes"]["expert"][0]["executor"], "antigravity")
        self.assertIn(POLICY["rootRoutes"]["expert"][0]["model"], self.text)
        self.assertIn("expert", POLICY["nativePi"]["goModels"])
        self.assertNotIn("god", POLICY["rootRoutes"])
        for family in POLICY["bannedModels"]:
            for routes in POLICY["rootRoutes"].values():
                self.assertTrue(all(route["model"] != family and not route["model"].startswith(family + "-")
                                    for route in routes))

    def test_direct_antigravity_models_require_an_availability_check(self):
        for model in POLICY["antigravityDirect"]["models"]:
            self.assertIn(model, self.text)
        self.assertIn("Verify it with `agy models`", self.text)

    def test_no_old_mcp_registration(self):
        codex = (ROOT / "dotfiles/base/.codex/config.toml").read_text()
        self.assertIn("pi-subagent-bridge", codex)
        self.assertNotIn("usr-opencode-worker", codex)
        opencode = (ROOT / "dotfiles/base/.config/opencode/opencode.json").read_text()
        self.assertNotIn("pi-subagent-bridge", opencode)
        self.assertNotIn("usr-opencode-worker", opencode)
        json.loads(opencode)

    def test_native_subagents_are_the_quota_fallback(self):
        self.assertIn("Quota fallback for scout/mechanic/worker only:", self.text)
        self.assertIn("No hook gates native subagents.", self.text)
        self.assertIn("Host-access exception for scout/mechanic/worker:", self.text)
        for path in ("dotfiles/base/.codex/AGENTS.md", "dotfiles/base/.agents/instructions/lean.md"):
            content = (ROOT / path).read_text()
            self.assertIn("quota", content)
            self.assertIn("host access Codex's sandbox cannot grant", content)
            self.assertNotIn("Missing bridge means no delegation", content)
            self.assertNotIn("blocks delegation rather than authorizing another launcher", content)
        settings = json.loads((ROOT / "dotfiles/base/.claude/settings.json").read_text())
        self.assertNotIn("PreToolUse", settings.get("hooks", {}))
        self.assertFalse((ROOT / "dotfiles/base/.local/bin/agent-tier-gate").exists())

    def test_opencode_exception(self):
        self.assertIn("OpenCode exception:", self.text)
        self.assertIn("never uses `pi-subagent-bridge`", self.text)
        self.assertIn("every tier must run a free model", self.text)
        self.assertIn("Bridge pins, fallbacks, and nesting rules do not apply on this path.", self.text)
        config = json.loads((ROOT / "dotfiles/base/.config/opencode/opencode.json").read_text())
        agents = config["agents"]
        policy = POLICY["opencode"]
        self.assertIn(f"The configured tier agents use `{policy['model']}` regardless of the top-level model", self.text)
        self.assertEqual(
            {tier: agents[tier]["model"] for tier in POLICY["tiers"]},
            {tier: policy["model"] + "#" + policy["efforts"][tier] for tier in POLICY["tiers"]},
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

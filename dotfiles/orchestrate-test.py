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
        self.assertIn("all scout/mechanic/worker coding subagents", self.text.lower())
        self.assertIn("pi-subagent-bridge", self.text)
        for method in ("worker_model_check", "worker_start", "worker_status", "worker_resume"):
            self.assertIn(method, self.text)

    def test_generated_policy_has_distinct_root_and_native_domains(self):
        self.assertEqual(POLICY["tiers"], ["scout", "mechanic", "worker"])
        self.assertNotIn("expert", POLICY["rootRoutes"])
        self.assertNotIn("antigravity", [route["executor"] for routes in POLICY["rootRoutes"].values() for route in routes])
        self.assertIn("expert", POLICY["nativePi"]["goModels"])
        self.assertNotIn("god", POLICY["rootRoutes"])
        for family in POLICY["bannedModels"]:
            for routes in POLICY["rootRoutes"].values():
                self.assertTrue(all(route["model"] != family and not route["model"].startswith(family + "-")
                                    for route in routes))

    def test_direct_antigravity_models_require_an_availability_check(self):
        contract = (ROOT / "dotfiles/base/.codex/AGENTS.md").read_text()
        for model in POLICY["antigravityDirect"]["models"]:
            self.assertIn(model, contract)
            self.assertNotIn(model, {route["model"] for routes in POLICY["rootRoutes"].values() for route in routes})
        self.assertIn("Verify `agy models` and actual child runtime models", contract)
        block = self.text.split("<!-- policy:begin antigravity -->", 1)[1].split("<!-- policy:end antigravity -->", 1)[0]
        for pin in POLICY["antigravityDirect"]["tiers"].values():
            self.assertIn(pin["model"], block)
        self.assertIn("not exact model IDs or effort pins", block)
        self.assertIn("check actual child model and effort on first use", block)
        self.assertIn("block any lane resolving to", block)

    def test_orchestrate_defers_exact_pins_to_model_check(self):
        self.assertIn("On the bridge path, call `worker_model_check` for the tier you are about to assign", self.text)
        self.assertNotIn("| Tier | Primary | Fallback (in order) |", self.text)

    def test_no_old_mcp_registration(self):
        codex = (ROOT / "dotfiles/base/.codex/config.toml").read_text()
        self.assertIn("pi-subagent-bridge", codex)
        self.assertNotIn("usr-opencode-worker", codex)
        opencode = json.loads((ROOT / "dotfiles/base/.config/opencode/opencode.json").read_text())
        self.assertNotIn("pi-subagent-bridge", json.dumps(opencode.get("mcp", {})))
        self.assertNotIn("usr-opencode-worker", json.dumps(opencode))

    def test_native_subagents_cover_claude_code(self):
        self.assertIn("Codex's native subagents", self.text)
        for harness in ("OpenCode", "Devin", "Codex", "Pi", "Claude Code"):
            self.assertIn(harness, self.text)
        self.assertIn("Claude Code native subagents:", self.text)
        self.assertIn("`expert` assignments always use native subagents pinned to `opus` with `xhigh` effort.", self.text)
        self.assertIn("If that pinned model is unavailable, the expert lane is blocked; never substitute another model.", self.text)
        self.assertIn("pi-subagent-bridge scope-check CWD SCOPE_JSON_FILE BRANCH --register TITLE", self.text)
        self.assertIn("pi-subagent-bridge scope-check --lane ID", self.text)
        self.assertIn("No hook gates native subagents.", self.text)
        self.assertNotIn("Host-access exception", self.text)
        self.assertNotIn("sandbox cannot grant", self.text)
        for path in ("dotfiles/base/.codex/AGENTS.md", "dotfiles/base/.agents/instructions/lean.md"):
            content = (ROOT / path).read_text()
            self.assertIn("quota", content)
            self.assertNotIn("sandbox cannot grant", content)
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
            {tier: agents[tier]["model"] for tier in policy["efforts"]},
            {tier: policy["model"] + "#" + policy["efforts"][tier] for tier in policy["efforts"]},
        )
        self.assertNotIn("god", agents)
        scout_rules = agents["scout"]["permissions"]
        denied = {(r["action"], r["effect"]) for r in scout_rules}
        self.assertIn(("shell", "deny"), denied)
        self.assertIn(("edit", "deny"), denied)
        for path in ("dotfiles/base/.codex/AGENTS.md", "dotfiles/base/.agents/instructions/lean.md"):
            content = (ROOT / path).read_text()
            self.assertIn("OpenCode", content)

    def test_copilot_native_pilot_has_required_pins_and_leaf_tools(self):
        directory = ROOT / "dotfiles/base/.copilot"
        pins = POLICY["copilotNative"]
        self.assertEqual(set(pins), {"scout", "mechanic", "worker", "expert"})
        self.assertIn("Copilot CLI pilot:", self.text)
        self.assertNotIn("copilot", {route["executor"] for routes in POLICY["rootRoutes"].values() for route in routes})
        settings = json.loads((directory / "settings.json").read_text())
        self.assertNotEqual(settings["model"], "auto")
        self.assertFalse(settings["remoteExport"])
        self.assertEqual(settings["subagents"]["maxDepth"], 1)
        for tier, pin in pins.items():
            profile = (directory / "agents" / (pin["name"] + ".agent.md")).read_text()
            self.assertIn("model: " + pin["model"], profile)
            self.assertIn("reasoningEffort: " + pin["effort"], profile)
            self.assertIn("modelPolicy: required", profile)
            self.assertIn("strict-tools-list: true", profile)
            self.assertIn("infer: false", profile)
            if tier == "scout":
                self.assertIn('tools: ["read","grep","glob"]', profile)

    def test_command_code_native_agents_are_pinned(self):
        self.assertIn("Command Code exception:", self.text)
        self.assertIn("never invoke `pi-subagent-bridge` from that parent", self.text)
        config = POLICY["commandNative"]
        self.assertEqual(set(config), {"scout", "mechanic", "worker", "expert", "pilot"})
        for pin in config.values():
            content = (ROOT / "dotfiles/base/.commandcode/agents" / (pin["name"] + ".md")).read_text()
            self.assertIn("model: " + pin["model"], content)
            if "effort" in pin:
                self.assertIn("reasoningEffort: " + pin["effort"], content)
            self.assertIn("# policy:begin native-agent", content)
        scout = (ROOT / "dotfiles/base/.commandcode/agents" / (config["scout"]["name"] + ".md")).read_text()
        self.assertIn("tools: read_file, read_directory, grep, glob", scout)
        self.assertNotIn("shell_command", scout)
        self.assertNotIn("edit_file", scout)
        self.assertEqual(config["worker"]["model"], "deepseek/deepseek-v4.1-flash")
        self.assertEqual(config["pilot"]["effort"], "medium")
        self.assertEqual(config["expert"]["effort"], "high")

    def test_global_rule(self):
        contract = (ROOT / "dotfiles/base/.codex/AGENTS.md").read_text()
        self.assertIn("in every harness and skill", contract)
        self.assertIn("pi-subagent-bridge", contract)

if __name__ == "__main__":
    unittest.main()

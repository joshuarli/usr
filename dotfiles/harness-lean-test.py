#!/usr/bin/env python3
"""Offline regressions for the tracked native harness slimming controls."""

import json
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / "dotfiles" / "base"


class HarnessLeanTests(unittest.TestCase):
    def test_codex_keeps_mcp_and_subagents_while_dropping_browser_companions(self):
        config = tomllib.loads((BASE / ".codex/config.toml").read_text())
        features = config["features"]
        for name in ("apps", "plugins", "remote_plugin", "daemon_auto_start"):
            with self.subTest(feature=name):
                self.assertIs(features[name], False)

        plugins = config["plugins"]
        for name in (
            "browser@openai-bundled",
            "unified-computer-use@openai-bundled",
            "computer-use@openai-bundled",
        ):
            with self.subTest(plugin=name):
                self.assertIs(plugins[name]["enabled"], False)

        servers = config["mcp_servers"]
        self.assertIs(servers["node_repl"]["enabled"], False)
        self.assertIs(servers["cua_repl"]["enabled"], False)
        for name in ("sentry", "notion", "pi-subagent-bridge", "codex-intercom"):
            with self.subTest(mcp=name):
                self.assertIn(name, servers)
                self.assertIsNot(servers[name].get("enabled"), False)
        self.assertIs(features["memories"], True)
        self.assertIs(config["features"]["multi_agent_v2"]["expose_spawn_agent_model_overrides"], True)

        # These are managed requirements, NOT a user config.toml feature switch.
        for name in (
            "browser_use", "browser_use_external",
            "browser_use_full_cdp_access", "computer_use", "in_app_browser",
        ):
            self.assertNotIn(name, features)

    def test_claude_drops_bundled_skills_and_chrome_only(self):
        settings = json.loads((BASE / ".claude/settings.json").read_text())
        self.assertIs(settings["disableBundledSkills"], True)
        self.assertIs(settings["disableRemoteControl"], True)
        self.assertIs(settings["disableWorkflows"], True)
        self.assertEqual(settings["deniedMcpServers"], [{"serverName": "claude-in-chrome"}])
        self.assertIn("WorktreeCreate", settings["hooks"])
        self.assertIn("WorktreeRemove", settings["hooks"])
        self.assertIn("SessionStart", settings["hooks"])

    def test_other_harnesses_still_have_their_native_routing(self):
        pi = json.loads((BASE / ".pi/agent/settings.json").read_text())
        self.assertEqual(pi["subagents"]["defaultProvider"], "opencode-go")
        self.assertIn("worker", pi["subagents"]["agentOverrides"])
        opencode = json.loads((BASE / ".config/opencode/opencode.json").read_text())
        self.assertEqual(set(opencode["agents"]), {"scout", "mechanic", "worker", "expert"})
        muse = json.loads((BASE / ".config/muse/settings.json").read_text())
        self.assertIn("mcpServers", muse)
        cmd = json.loads((BASE / ".commandcode/settings.json").read_text())
        self.assertIn("permissions", cmd)
        fx = json.loads((BASE / ".fx/settings.json").read_text())
        self.assertIs(fx["auto_upgrade"], False)
        devin = json.loads((BASE / ".config/devin/config.json").read_text())
        self.assertIs(devin["read_config_from"]["cloud"], False)


if __name__ == "__main__":
    unittest.main()

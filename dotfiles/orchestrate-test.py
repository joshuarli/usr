#!/usr/bin/env python3
"""Pin orchestrate routing: the bridge is the Claude, OpenCode, Codex and Pi
execution path; only the Command Code parent uses harness-native models."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "dotfiles/base/.agents/skills/orchestrate/SKILL.md"


def section(text: str, start: str, end: str) -> str:
    return text.split("### " + start + "\n", 1)[1].split("### " + end + "\n", 1)[0]


class OrchestrateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = SKILL.read_text(encoding="utf-8")

    def test_claude_section_owns_bridge(self):
        self.assertIn("when Claude invokes `orchestrate`", self.text)
        self.assertIn("usr-opencode-worker", self.text)

    def test_opencode_parent_uses_bridge(self):
        sec = section(self.text, "OpenCode", "Command Code")
        self.assertIn("usr-opencode-worker", sec)
        self.assertIn("Do not delegate `god` work in OpenCode", sec)

    def test_command_code_parent_uses_native_models_not_bridge(self):
        sec = section(self.text, "Command Code", "Pi")
        self.assertIn("deepseek/deepseek-v4.1-flash", sec)
        self.assertIn("do not call the `usr-opencode-worker` bridge tools", sec.lower())

    def test_opencode_config_registers_bridge_and_cmd_does_not(self):
        opencode = (ROOT / "dotfiles/base/.config/opencode/opencode.json").read_text(encoding="utf-8")
        self.assertIn("usr-opencode-worker", opencode)
        cmd = (ROOT / "dotfiles/base/.commandcode/settings.json").read_text(encoding="utf-8")
        self.assertNotIn("usr-opencode-worker", cmd)
        json.loads(opencode)
        json.loads(cmd)


if __name__ == "__main__":
    unittest.main()

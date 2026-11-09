#!/usr/bin/env python3
"""Offline Pi installer/profile checks; all writes stay in .work/."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "dotfiles/base/.pi/agent"
MODEL = "opencode-go/muse-spark-1.3-contributor"
TIERS = {"scout": "low", "mechanic": "medium", "worker": "high", "expert": "xhigh", "god": "xhigh"}


class PiTests(unittest.TestCase):
    def setUp(self):
        work = ROOT / ".work"
        work.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="pi-test-", dir=work)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.home = self.root / "home"
        self.home.mkdir()
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.env = {
            "HOME": str(self.home), "PATH": f"{self.bin}:/usr/bin:/bin",
            "TMPDIR": str(self.root), "DL_OWNED_FILE": str(self.root / "owned"),
            "MOCK_LOG": str(self.root / "npm.log"), "MOCK_VERSION": "1.4.0",
        }
        self.script("node", '#!/bin/sh\nprintf "%s\\n" "${MOCK_NODE_VERSION:-26.13.0}"\nexit "${MOCK_NODE_STATUS:-0}"\n')
        self.script("npm", f"#!{sys.executable}\n" + '''import json, os, pathlib, sys
args = sys.argv[1:]
with open(os.environ["MOCK_LOG"], "a") as log:
    log.write(json.dumps(args) + "\\n")
if args == ["view", "@earendil-works/pi-coding-agent@latest", "version"]:
    print(os.environ["MOCK_VERSION"])
elif args[:4] == ["install", "--global", "--ignore-scripts", "--prefix"]:
    if os.environ.get("MOCK_FAIL") == "1":
        sys.exit(1)
    assert args[5] == "@earendil-works/pi-coding-agent@" + os.environ["MOCK_VERSION"]
    if os.environ.get("MOCK_NO_BIN") != "1":
        binary = pathlib.Path(args[4]) / "bin/pi"
        binary.parent.mkdir(parents=True, exist_ok=True)
        binary.write_text("#!/bin/sh\\nprintf '%s\\\\n' " + os.environ["MOCK_VERSION"] + "\\n")
        binary.chmod(0o755)
else:
    raise SystemExit("unexpected npm arguments: " + repr(args))
''')

    def script(self, name, text):
        path = self.bin / name
        path.write_text(text)
        path.chmod(0o755)

    def sync_tools(self, ok=True, *args):
        result = subprocess.run(
            [sys.executable, "-I", str(ROOT / "tools/sync/installer.py"), *(args or ("pi",))],
            cwd=ROOT, env=self.env, text=True, capture_output=True, timeout=20,
        )
        self.assertEqual(result.returncode == 0, ok, result.stdout + result.stderr)
        return result

    def install_calls(self):
        path = self.root / "npm.log"
        return [json.loads(line) for line in path.read_text().splitlines() if json.loads(line)[0] == "install"]

    def test_install_idempotence_upgrade_and_credentials(self):
        auth = self.home / ".pi/agent/auth.json"
        auth.parent.mkdir(parents=True)
        auth.write_text("private sentinel")
        self.sync_tools()
        launcher = self.home / ".local/bin/pi"
        self.assertTrue(launcher.is_symlink())
        self.assertTrue(os.access(launcher, os.X_OK))
        self.sync_tools()
        self.assertEqual(len(self.install_calls()), 1)
        self.env["MOCK_VERSION"] = "1.4.1"
        self.sync_tools()
        self.assertEqual(len(self.install_calls()), 2)
        self.assertEqual((self.home / ".local/state/dl/pi").read_text(), "1.4.1\n")
        self.assertEqual(auth.read_text(), "private sentinel")
        self.assertNotIn(".pi/agent", (self.root / "owned").read_text())

    def test_failed_fresh_install_is_not_recorded(self):
        self.env["MOCK_FAIL"] = "1"
        self.sync_tools(False)
        self.assertFalse((self.home / ".local/state/dl/pi").exists())
        self.assertFalse((self.home / ".local/share/pi").exists())
        self.assertEqual(list((self.home / ".local/share").glob("pi.*")), [])

    def test_missing_binary_is_failure(self):
        self.env["MOCK_NO_BIN"] = "1"
        self.sync_tools(False)
        self.assertFalse((self.home / ".local/bin/pi").exists())

    def test_unmanaged_launcher_is_preserved(self):
        launcher = self.home / ".local/bin/pi"
        launcher.parent.mkdir(parents=True)
        launcher.write_text("do not replace")
        self.sync_tools(False)
        self.assertEqual(launcher.read_text(), "do not replace")
        self.assertEqual(self.install_calls(), [])

    def test_unmanaged_prefix_is_preserved(self):
        prefix = self.home / ".local/share/pi"
        prefix.mkdir(parents=True)
        (prefix / "sentinel").touch()
        self.sync_tools(False)
        self.assertTrue((prefix / "sentinel").exists())
        self.assertEqual(self.install_calls(), [])

    def test_symlinked_prefix_is_rejected(self):
        prefix = self.home / ".local/share/pi"
        prefix.parent.mkdir(parents=True)
        prefix.symlink_to(self.root, target_is_directory=True)
        self.sync_tools(False)
        self.assertEqual(self.install_calls(), [])

    def test_invalid_version_and_old_node(self):
        self.env["MOCK_VERSION"] = "not-a-version"
        self.sync_tools(False)
        self.assertEqual(self.install_calls(), [])
        self.env["MOCK_NODE_VERSION"] = "26.11.0"
        result = self.sync_tools(False)
        self.assertIn("26.12.0", result.stderr)

    def test_xdg_paths_and_ownership_recovery(self):
        self.env["XDG_DATA_HOME"] = str(self.home / "data with spaces")
        self.env["XDG_STATE_HOME"] = str(self.home / "state with spaces")
        self.sync_tools()
        launcher = self.home / ".local/bin/pi"
        self.assertEqual(os.readlink(launcher), str(self.home / "data with spaces/pi/bin/pi"))
        (self.root / "owned").unlink()
        self.env["DL_RECORD_OWNED"] = "true"
        self.sync_tools()
        owned = (self.root / "owned").read_text()
        self.assertIn(f"D\t{self.home}/data with spaces/pi\n", owned)
        self.assertIn(f"F\t{launcher}\n", owned)
        self.assertNotIn(".pi/agent", owned)
        self.assertEqual(len(self.install_calls()), 1)

    def test_profile_and_orchestration_agree(self):
        settings = json.loads((PROFILE / "settings.json").read_text())
        self.assertEqual(settings["defaultProvider"] + "/" + settings["defaultModel"], "opencode-go/deepseek-v4.1-flash")
        self.assertEqual(settings["defaultThinkingLevel"], "high")
        self.assertEqual(settings["packages"], ["npm:pi-subagents@0.87.0"])
        self.assertEqual(settings["skills"], ["~/.agents/skills"])
        sub = settings["subagents"]
        self.assertEqual(sub["maxThinking"], "max")
        self.assertTrue(sub["modelScope"]["strict"])
        self.assertEqual(set(sub["modelScope"]["allow"]), {
            "opencode-go/deepseek-v4.1-flash", "opencode-go/muse-spark-1.3-contributor"})
        expected = {"scout": ("muse-spark-1.3-contributor", "medium"),
                    "mechanic": ("muse-spark-1.3-contributor", "high"),
                    "worker": ("deepseek-v4.1-flash", "high"),
                    "expert": ("deepseek-v4.1-flash", "max")}
        for tier, (model, effort) in expected.items():
            self.assertEqual(sub["agentOverrides"][tier], {"model": "opencode-go/" + model, "thinking": effort})
            agent = (PROFILE / "agents" / (tier + ".md")).read_text()
            self.assertIn("name: " + tier, agent)
            self.assertIn("model: opencode-go/" + model, agent)
            self.assertIn("thinking: " + effort, agent)
            self.assertNotIn("tools: subagent", agent)
        self.assertNotIn("god", sub["agentOverrides"])
        self.assertFalse((PROFILE / "agents/god.md").exists())
        self.assertEqual(os.readlink(PROFILE / "AGENTS.md"), "../../.codex/AGENTS.md")
        self.assertIn("pi-subagent-bridge", (ROOT / "dotfiles/base/.agents/skills/orchestrate/SKILL.md").read_text())
        self.assertIn("opencode2 auth export", (ROOT / "docs/pi.md").read_text())


if __name__ == "__main__":
    unittest.main()

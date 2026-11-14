#!/usr/bin/env python3
"""Pi installation and profile tests; none may invoke npm or contact a registry."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools/pi"))
from release_cache import seed  # noqa: E402
PROFILE = ROOT / "dotfiles/base/.pi/agent"
POLICY = json.loads((ROOT / "tools/policy/policy.generated.json").read_text())



class PiTests(unittest.TestCase):
    def setUp(self):
        work = ROOT / ".work"
        work.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="pi-offline-test-", dir=work)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.home = self.root / "home"
        self.home.mkdir()
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.env = {
            "HOME": str(self.home),
            "PATH": f"{self.bin}:/usr/bin:/bin",
            "TMPDIR": str(self.root),
            "DL_OWNED_FILE": str(self.root / "owned"),
            # Any request beyond the seeded cache fails instead of reaching the network.
            "https_proxy": "http://127.0.0.1:9", "http_proxy": "http://127.0.0.1:9",
        }
        seed(self.home / ".cache/usr/pi-releases")
        self.script("node", '#!/bin/sh\nprintf "%s\\n" "${MOCK_NODE_VERSION:-26.13.1}"\n')
        # Deliberately poison npm: a runtime install MUST NOT use it.
        self.script("npm", '#!/bin/sh\necho unexpected-npm-call >&2\nexit 99\n')

    def script(self, name, body):
        f = self.bin / name
        f.write_text(body)
        f.chmod(0o755)

    def sync_tools(self, success=True):
        result = subprocess.run(
            [sys.executable, "-I", str(ROOT / "tools/sync/installer.py"), "pi"],
            cwd=ROOT, env=self.env, text=True, capture_output=True, timeout=90
        )
        self.assertEqual(result.returncode == 0, success, result.stdout + result.stderr)
        self.assertNotIn("unexpected-npm-call", result.stdout + result.stderr)
        return result

    def test_install_is_offline_idempotent_and_preserves_auth(self):
        auth = self.home / ".pi/agent/auth.json"
        auth.parent.mkdir(parents=True)
        auth.write_text("private sentinel")
        self.sync_tools()
        launcher = self.home / ".local/bin/pi"
        self.assertTrue(launcher.is_symlink())
        self.assertTrue(os.access(launcher, os.X_OK))
        runtime = self.home / ".local/share/pi-runtime/current"
        self.assertEqual(os.readlink(launcher), str(runtime / "bin/pi"))
        meta = runtime / ".usr-pi-release.json"
        pin = json.loads((ROOT / "tools/pi/runtime.pin.json").read_text())
        self.assertEqual(json.loads(meta.read_text())["pin"], pin)
        broker = json.loads((self.home / ".pi/agent/intercom/config.json").read_text())
        self.assertEqual(broker["brokerCommand"], "node")
        self.assertEqual(broker["inboundTrigger"], "never")
        self.assertTrue(Path(broker["brokerArgs"][-1]).is_file())
        before = meta.read_bytes()
        again = self.sync_tools()
        self.assertIn("pi is current", again.stdout)
        self.assertEqual(meta.read_bytes(), before)
        self.assertEqual(auth.read_text(), "private sentinel")

    def test_previous_vendored_runtime_is_kept_and_launcher_moves(self):
        legacy = self.home / ".local/share/pi"
        (legacy / "bin").mkdir(parents=True)
        (legacy / "bin/pi").write_text("#!/bin/sh\n")
        (legacy / ".usr-pi-runtime.json").write_text("{}")
        launcher = self.home / ".local/bin/pi"
        launcher.parent.mkdir(parents=True)
        launcher.symlink_to(legacy / "bin/pi")
        state = self.home / ".local/state/dl/pi"
        state.parent.mkdir(parents=True)
        state.write_text("offline:" + "a" * 64 + "\n")
        result = self.sync_tools()
        self.assertEqual(os.readlink(launcher), str(self.home / ".local/share/pi-runtime/current/bin/pi"))
        self.assertTrue((legacy / "bin/pi").is_file())
        self.assertIn("Previous vendored Pi runtime kept", result.stderr)

    def test_unmanaged_launcher_is_preserved(self):
        launcher = self.home / ".local/bin/pi"
        launcher.parent.mkdir(parents=True)
        launcher.write_text("do not replace")
        self.sync_tools(False)
        self.assertEqual(launcher.read_text(), "do not replace")

    def test_unmanaged_prefix_is_preserved(self):
        prefix = self.home / ".local/share/pi-runtime"
        prefix.mkdir(parents=True)
        (prefix / "sentinel").touch()
        self.sync_tools(False)
        self.assertTrue((prefix / "sentinel").exists())

    def test_old_node_is_rejected_before_install(self):
        self.env["MOCK_NODE_VERSION"] = "25.9.0"
        self.sync_tools(False)
        self.assertFalse((self.home / ".local/share/pi-runtime").exists())

    def test_profile_and_orchestration_agree(self):
        settings = json.loads((PROFILE / "settings.json").read_text())
        self.assertEqual(settings["defaultProvider"] + "/" + settings["defaultModel"], "opencode-go/deepseek-v4.1-flash")
        self.assertEqual(settings["defaultThinkingLevel"], "high")
        self.assertEqual(settings["packages"], [])
        self.assertEqual(settings["skills"], ["~/.agents/skills"])
        sub = settings["subagents"]
        self.assertEqual(sub["maxThinking"], "max")
        depth_settings = json.loads((PROFILE / "extensions/subagent/config.json").read_text())
        self.assertEqual(depth_settings["maxSubagentDepth"], 2)
        self.assertTrue(sub["modelScope"]["strict"])
        native = POLICY["nativePi"]
        self.assertEqual(sub["modelScope"]["allow"], native["modelAllowlist"])
        profiles = {
            tier: (pin, native["delegation"][tier], native["tools"][tier])
            for tier, pin in native["goModels"].items()
        }
        for tier, pin in native["museModels"].items():
            profiles[native["agentNames"][tier]] = (pin, native["museDelegation"][tier], native["tools"][tier])
        for name, (pin, children, tools) in profiles.items():
            model = pin["providerID"] + "/" + pin["id"]
            self.assertEqual(sub["agentOverrides"][name], {"model": model, "thinking": pin["variant"]})
            self.assertEqual(sub["modelScope"]["agents"][name]["allow"], [model])
            agent = (PROFILE / "agents" / (name + ".md")).read_text()
            self.assertIn("name: " + name, agent)
            expected = "\n".join([
                "model: " + model, "thinking: " + pin["variant"], "tools:",
                *["  - " + tool for tool in tools], "allowNestedSubagents: true",
                "maxSubagentDepth: " + str(native["maxSubagentDepth"]), "allowedAgents:",
                *["  - " + child for child in children],
            ])
            self.assertIn(expected + "\n# policy:end native-profile", agent)
            self.assertNotIn("  - god\n", agent)
        for deleted in ("muse-scout", "muse-mechanic"):
            self.assertFalse((PROFILE / "agents" / (deleted + ".md")).exists(),
                             "Muse scout/mechanic profiles are retired")
        self.assertFalse((PROFILE / "models.json").exists(),
                         "No custom OpenCode Zen catalog is permitted for delegated workers")
        self.assertTrue(all(name.startswith(("opencode-go/", "muse-sdk/")) for name in sub["modelScope"]["allow"]))
        self.assertNotIn("god", sub["agentOverrides"])
        self.assertFalse((PROFILE / "agents/god.md").exists())
        self.assertEqual(os.readlink(PROFILE / "AGENTS.md"), "../../.codex/AGENTS.md")
        self.assertIn("pi-subagent-bridge", (ROOT / "dotfiles/base/.agents/skills/orchestrate/SKILL.md").read_text())
        self.assertIn("opencode2 auth export", (ROOT / "docs/pi.md").read_text())



if __name__ == "__main__":
    unittest.main()

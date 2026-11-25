#!/usr/bin/env python3
"""Pi installation and profile tests; none may invoke npm or contact a registry."""
import ast
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools/pi"))
from release_cache import seed  # noqa: E402
PROFILE = ROOT / "dotfiles/base/.pi/agent"
POLICY = json.loads((ROOT / "tools/policy/policy.generated.json").read_text())
NATIVE_PI = POLICY["nativePi"]


def parse_blocks(text: str) -> dict[str, str]:
    marker = re.compile(r"^# policy:(begin|end) ([a-z0-9-]+)$", re.MULTILINE)
    candidates = [line for line in text.splitlines() if "# policy:" in line]
    matches = list(marker.finditer(text))
    if len(candidates) != len(matches):
        raise ValueError("malformed generated policy marker")
    blocks = {}
    active = None
    start = None
    for match in matches:
        kind, name = match.groups()
        if kind == "begin":
            if active is not None or name in blocks:
                raise ValueError("duplicate or nested generated policy block: " + name)
            active = name
            start = match.end()
        else:
            if active != name:
                raise ValueError("unmatched generated policy block: " + name)
            blocks[name] = text[start:match.start()]
            active = None
    if active is not None:
        raise ValueError("unclosed generated policy block: " + active)
    return blocks


def yaml_fields(block: str) -> dict[str, str | list[str]]:
    fields = {}
    current = None
    for line in block.strip().splitlines():
        if not line.strip() or line.startswith("# Generated"):
            continue
        if line.startswith("  - "):
            if current is None:
                raise ValueError("generated YAML list item without a key")
            fields[current].append(line[4:].strip())
            continue
        if line.startswith(" "):
            raise ValueError("unexpected generated YAML indentation: " + line)
        key, separator, value = line.partition(":")
        if not separator:
            raise ValueError("malformed generated YAML line: " + line)
        key = key.strip()
        value = value.strip()
        if value:
            fields[key] = value
            current = None
        else:
            fields[key] = []
            current = key
    return fields


def policy_model(pin: dict[str, str]) -> str:
    return pin["providerID"] + "/" + pin["id"]


def arithmetic_value(node: ast.AST) -> int:
    if isinstance(node, ast.Constant) and isinstance(node.value, int):
        return node.value
    if isinstance(node, ast.Expression):
        return arithmetic_value(node.body)
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Mult, ast.Add)):
        value = arithmetic_value(node.left)
        right = arithmetic_value(node.right)
        return value * right if isinstance(node.op, ast.Mult) else value + right
    raise ValueError("unsupported arithmetic in Pi deadline constant")


def pi_run_deadline() -> int:
    source = (ROOT / "tools/pi-subagent-bridge/src/tier-policy.ts").read_text()
    match = re.search(r"PI_RUN_DEADLINE_MS:\s*number\s*=\s*([^\n]+)", source)
    if not match:
        raise ValueError("missing PI_RUN_DEADLINE_MS")
    return arithmetic_value(ast.parse(match.group(1).strip(), mode="eval"))


def expected_profiles() -> dict[str, tuple[dict[str, str], list[str], list[str]]]:
    expected = {}
    for tier, pin in NATIVE_PI["goModels"].items():
        expected[tier] = (pin, NATIVE_PI["delegation"][tier], NATIVE_PI["tools"][tier])
    for tier, pin in NATIVE_PI["devinModels"].items():
        name = NATIVE_PI["devinAgentNames"][tier]
        expected[name] = (pin, NATIVE_PI["devinDelegation"][tier], NATIVE_PI["tools"][tier])
    return expected



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

    def script(self, name: str, body: str) -> None:
        f = self.bin / name
        f.write_text(body)
        f.chmod(0o755)

    def sync_tools(self, success: bool = True) -> subprocess.CompletedProcess[str]:
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
        if broker.get("usrBrokerProfile") == "headless-usr":
            self.assertEqual(broker["brokerArgs"], [])
        else:
            self.assertTrue(Path(broker["brokerArgs"][-1]).is_file())
        before = meta.read_bytes()
        self.env["SYNC_VERBOSE"] = "1"
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

    def test_last_changelog_seed_matches_runtime_pin(self):
        settings = json.loads((PROFILE / "settings.json").read_text())
        pin = json.loads((ROOT / "tools/pi/runtime.pin.json").read_text())
        self.assertEqual(settings["lastChangelogVersion"], pin["version"])

    def test_profile_and_orchestration_agree(self):
        settings = json.loads((PROFILE / "settings.json").read_text())
        worker_pin = NATIVE_PI["goModels"]["worker"]
        self.assertEqual(settings["defaultProvider"], worker_pin["providerID"])
        self.assertEqual(settings["defaultModel"], worker_pin["id"])
        self.assertEqual(settings["defaultThinkingLevel"], worker_pin["variant"])
        self.assertEqual(settings["packages"], [])
        self.assertEqual(settings["skills"], ["~/.agents/skills"])
        sub = settings["subagents"]
        self.assertEqual(sub["maxThinking"], "max")
        depth_settings = json.loads((PROFILE / "extensions/subagent/config.json").read_text())
        self.assertEqual(depth_settings["maxSubagentDepth"], NATIVE_PI["maxSubagentDepth"])
        self.assertTrue(sub["modelScope"]["enforce"])
        self.assertTrue(sub["modelScope"]["strict"])
        self.assertEqual(sub["modelScope"]["allow"], NATIVE_PI["modelAllowlist"])
        self.assertEqual(len(set(NATIVE_PI["modelAllowlist"])), len(NATIVE_PI["modelAllowlist"]))
        approved_models = {policy_model(pin) for pin in NATIVE_PI["goModels"].values()}
        approved_models.update(policy_model(pin) for pin in NATIVE_PI["devinModels"].values())
        self.assertEqual(set(NATIVE_PI["modelAllowlist"]), approved_models)
        expected = expected_profiles()
        self.assertEqual(set(sub["agentOverrides"]), set(expected))
        self.assertEqual(set(sub["modelScope"]["agents"]), set(expected))
        for name, (pin, children, tools) in expected.items():
            model = policy_model(pin)
            self.assertEqual(sub["agentOverrides"][name], {"model": model, "thinking": pin["variant"]})
            self.assertEqual(sub["modelScope"]["agents"][name]["allow"], [model])
            agent = (PROFILE / "agents" / (name + ".md")).read_text()
            self.assertRegex(agent, r"(?m)^name: " + re.escape(name) + r"$")
            blocks = parse_blocks(agent)
            self.assertEqual(set(blocks), {"native-profile"})
            self.assertEqual(yaml_fields(blocks["native-profile"]), {
                "model": model,
                "thinking": pin["variant"],
                "tools": tools,
                "allowNestedSubagents": "true",
                "maxSubagentDepth": str(NATIVE_PI["maxSubagentDepth"]),
                "timeoutMs": str(pi_run_deadline()),
                "allowedAgents": children,
            })
            self.assertNotIn("god", yaml_fields(blocks["native-profile"])["allowedAgents"])
        self.assertFalse((PROFILE / "agents/muse-worker.md").exists(), "Muse worker profile is retired")
        self.assertFalse((PROFILE / "models.json").exists(),
                         "No custom OpenCode Zen catalog is permitted for delegated workers")
        self.assertNotIn("god", sub["agentOverrides"])
        self.assertFalse((PROFILE / "agents/god.md").exists())
        self.assertEqual(os.readlink(PROFILE / "AGENTS.md"), "../../.codex/AGENTS.md")
        self.assertIn("pi-subagent-bridge", (ROOT / "dotfiles/base/.agents/skills/orchestrate/SKILL.md").read_text())
        self.assertIn("opencode auth export", (ROOT / "docs/pi.md").read_text())



if __name__ == "__main__":
    unittest.main()

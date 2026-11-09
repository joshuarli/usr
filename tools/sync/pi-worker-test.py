#!/usr/bin/env python3
"""Offline behavior tests for sync-owned Pi MCP setup."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
HELPER = ROOT / "tools/sync/pi-worker.py"


class PiWorkerSyncTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="sync-claude-mcp-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.home = self.root / "home"
        self.home.mkdir()
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.project = self.root / "tools/pi-subagent-bridge"
        (self.root / "tools/sync").mkdir(parents=True)
        (self.project / "src").mkdir(parents=True)
        shutil.copy2(HELPER, self.root / "tools/sync/pi-worker.py")
        (self.project / "src/server.ts").write_text("export {}\n")
        (self.project / "package.json").write_text(json.dumps({
            "dependencies": {"@earendil-works/pi-coding-agent": "1.5.0"},
        }))
        (self.bin / "node").write_text("#!/bin/sh\nprintf 'v26.12.1\\n'\n")
        (self.bin / "node").chmod(0o755)
        npm = f"""#!{sys.executable}
import json, pathlib, sys, os
args = sys.argv[1:]
with open(os.environ["MOCK_NPM_LOG"], "a") as f:
    f.write(json.dumps(args) + "\\n")
assert args[:2] == ["install", "--prefix"], args
project = pathlib.Path(args[2])
client = project / "node_modules/@earendil-works/pi-coding-agent"
client.mkdir(parents=True, exist_ok=True)
(client / "package.json").write_text(json.dumps({{"version": os.environ.get("MOCK_VERSION", "1.5.0")}}))
"""
        (self.bin / "npm").write_text(npm)
        (self.bin / "npm").chmod(0o755)
        self.log = self.root / "npm.log"
        self.env = dict(os.environ, HOME=str(self.home),
                        PATH=str(self.bin) + os.pathsep + os.environ.get("PATH", ""),
                        MOCK_NPM_LOG=str(self.log))
        self.config = self.home / ".pi/agent/mcp.json"
        self.config.parent.mkdir(parents=True)
        self.script = self.root / "tools/sync/pi-worker.py"

    def run_helper(self, action, success=True):
        result = subprocess.run([sys.executable, "-I", str(self.script), action],
                                env=self.env, capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode == 0, success, result.stdout + result.stderr)
        return result

    def test_install_is_idempotent_and_preserves_unrelated_credentials(self):
        original = {
            "theme": "keep exactly",
            "mcpServers": {"other": {"command": "other", "args": ["--value", "secret"]}},
        }
        self.config.write_text(json.dumps(original))
        self.run_helper("install")
        result = json.loads(self.config.read_text())
        self.assertEqual(result["theme"], original["theme"])
        self.assertEqual(result["mcpServers"]["other"], original["mcpServers"]["other"])
        worker = result["mcpServers"]["pi-subagent-bridge"]
        self.assertEqual(worker["command"], str(self.bin / "node"))
        self.assertEqual(worker["args"], ["--experimental-strip-types",
                         str(self.project / "src/server.ts")])
        self.assertEqual(len(self.log.read_text().splitlines()), 1)
        self.run_helper("check")
        snapshot = self.config.read_bytes()
        self.run_helper("install")
        self.assertEqual(self.config.read_bytes(), snapshot)
        self.assertEqual(len(self.log.read_text().splitlines()), 1)
        self.run_helper("remove")
        self.assertEqual(json.loads(self.config.read_text()), original)
        self.run_helper("remove")

    def test_owned_legacy_registration_is_migrated_even_when_new_is_current(self):
        self.run_helper("install")
        data = json.loads(self.config.read_text())
        servers = data["mcpServers"]
        servers["usr-opencode-worker"] = dict(servers["pi-subagent-bridge"])
        self.config.write_text(json.dumps(data))
        self.run_helper("check", success=False)
        self.assertIn("migrate owned", self.run_helper("plan").stdout)
        self.run_helper("install")
        migrated = json.loads(self.config.read_text())
        self.assertNotIn("usr-opencode-worker", migrated["mcpServers"])
        self.run_helper("check")

    def test_plan_never_writes_or_installs(self):
        output = self.run_helper("plan").stdout
        self.assertIn("NPM: install", output)
        self.assertIn("MCP: register", output)
        self.assertFalse(self.config.exists())
        self.assertFalse(self.log.exists())
        self.run_helper("check", success=False)

    def test_different_name_owner_is_preserved(self):
        original = {"mcpServers": {"pi-subagent-bridge": {
            "type": "stdio", "command": "another", "args": ["different"]}}}
        self.config.write_text(json.dumps(original))
        self.run_helper("install", success=False)
        self.assertEqual(json.loads(self.config.read_text()), original)
        self.assertFalse(self.log.exists())
        self.run_helper("remove", success=False)

    def test_old_manual_registration_is_upgraded(self):
        old = {"mcpServers": {"pi-subagent-bridge": {
            "command": "node", "args": ["--experimental-strip-types",
                                     str(self.project / "src/server.ts")]}}}
        self.config.write_text(json.dumps(old))
        self.run_helper("install")
        self.assertEqual(json.loads(self.config.read_text())["mcpServers"]
                         ["pi-subagent-bridge"]["command"], str(self.bin / "node"))

    def test_relocated_checkout_keeps_owned_registration_and_credentials(self):
        self.config.write_text(json.dumps({"theme": "keep", "mcpServers": {"other": {"command": "other"}}}))
        self.run_helper("install")
        initial = json.loads(self.config.read_text())["mcpServers"]["pi-subagent-bridge"]
        new_root = self.root / "moved-checkout"
        moved_script = new_root / "tools/sync/pi-worker.py"
        moved_script.parent.mkdir(parents=True)
        shutil.copy2(HELPER, moved_script)
        moved_project = new_root / "tools/pi-subagent-bridge"
        (moved_project / "src").mkdir(parents=True)
        (moved_project / "src/server.ts").write_text("export {}\n")
        shutil.copy2(self.project / "package.json", moved_project / "package.json")
        self.script = moved_script
        self.project = moved_project
        self.assertIn("MCP: register", self.run_helper("plan").stdout)
        self.run_helper("install")
        self.run_helper("check")
        result = json.loads(self.config.read_text())
        self.assertEqual(result["theme"], "keep")
        self.assertEqual(result["mcpServers"]["other"], {"command": "other"})
        current = result["mcpServers"]["pi-subagent-bridge"]
        self.assertNotEqual(initial["args"], current["args"])
        self.assertEqual(current["args"][-1], str(moved_project / "src/server.ts"))
        self.run_helper("remove")
        self.assertEqual(json.loads(self.config.read_text())["mcpServers"], {"other": {"command": "other"}})

    def test_foreign_same_shape_without_ownership_is_preserved(self):
        foreign = self.root / "foreign/tools/pi-subagent-bridge/src/server.ts"
        self.config.write_text(json.dumps({"mcpServers": {"pi-subagent-bridge": {
            "type": "stdio", "command": "node",
            "args": ["--experimental-strip-types", str(foreign)]}}}))
        self.run_helper("install", success=False)
        self.assertEqual(json.loads(self.config.read_text())["mcpServers"]
                         ["pi-subagent-bridge"]["args"][-1], str(foreign))

    def test_stale_ownership_fingerprint_does_not_adopt_foreign_server(self):
        self.run_helper("install")
        replacement = self.root / "foreign/tools/pi-subagent-bridge/src/server.ts"
        data = json.loads(self.config.read_text())
        data["mcpServers"]["pi-subagent-bridge"]["args"][-1] = str(replacement)
        self.config.write_text(json.dumps(data))
        self.run_helper("install", success=False)
        self.assertEqual(json.loads(self.config.read_text()), data)

    def test_failed_install_never_registers_mcp(self):
        self.env["MOCK_VERSION"] = "0.0.1"
        self.run_helper("install", success=False)
        self.assertFalse(self.config.exists())

    def test_refuses_symlinked_config(self):
        outside = self.root / "other.json"
        outside.write_text("{}")
        self.config.symlink_to(outside)
        self.run_helper("install", success=False)
        self.assertEqual(outside.read_text(), "{}")


if __name__ == "__main__":
    unittest.main()

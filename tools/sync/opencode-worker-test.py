#!/usr/bin/env python3
"""Offline behavior tests for sync-owned OpenCode MCP setup."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
HELPER = ROOT / "tools/sync/opencode-worker.py"


class OpenCodeWorkerSyncTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="sync-opencode-mcp-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.home = self.root / "home"
        self.home.mkdir()
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.project = self.root / "tools/pi-subagent-bridge"
        (self.root / "tools/sync").mkdir(parents=True)
        (self.project / "src").mkdir(parents=True)
        shutil.copy2(HELPER, self.root / "tools/sync/opencode-worker.py")
        (self.project / "src/server.ts").write_text("export {}\n")
        (self.project / "package.json").write_text(json.dumps({
            "dependencies": {"@earendil-works/pi-coding-agent": "1.5.0", "pi-subagents": "0.87.0"},
        }))
        (self.bin / "node").write_text("#!/bin/sh\nprintf 'v26.13.0\\n'\n")
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
extension = project / "node_modules/pi-subagents"
extension.mkdir(parents=True, exist_ok=True)
(extension / "package.json").write_text(json.dumps({{"version": os.environ.get("MOCK_SUBAGENTS_VERSION", "0.87.0")}}))
"""
        (self.bin / "npm").write_text(npm)
        (self.bin / "npm").chmod(0o755)
        self.log = self.root / "npm.log"
        self.opencode_log = self.root / "opencode.log"
        opencode = f"""#!{sys.executable}
import json, os, sys
args = sys.argv[1:]
if args == ["service", "status"]:
    print("http://127.0.0.1:49374" if os.environ.get("MOCK_SERVICE", "running") == "running" else "stopped")
    raise SystemExit(0)
if args == ["service", "restart"]:
    with open(os.environ["MOCK_OPENCODE_LOG"], "a") as f:
        f.write(json.dumps(args) + "\\n")
    raise SystemExit(int(os.environ.get("MOCK_RESTART_RC", "0")))
raise SystemExit(2)
"""
        (self.bin / "opencode").write_text(opencode)
        (self.bin / "opencode").chmod(0o755)
        self.env = dict(os.environ, HOME=str(self.home), XDG_CONFIG_HOME=str(self.home / ".config"),
                        PATH=str(self.bin) + os.pathsep + os.environ.get("PATH", ""),
                        MOCK_NPM_LOG=str(self.log), MOCK_OPENCODE_LOG=str(self.opencode_log))
        self.env.pop("OPENCODE", None)
        self.config = self.home / ".config/opencode/opencode.json"
        self.config.parent.mkdir(parents=True)
        self.script = self.root / "tools/sync/opencode-worker.py"

    def run_helper(self, action, success=True):
        result = subprocess.run([sys.executable, "-I", str(self.script), action],
                                env=self.env, capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode == 0, success, result.stdout + result.stderr)
        return result

    def restarts(self):
        if not self.opencode_log.exists():
            return 0
        return len(self.opencode_log.read_text().splitlines())

    def test_install_is_idempotent_and_preserves_unrelated_credentials(self):
        original = {
            "theme": "keep exactly",
            "mcp": {"servers": {"other": {"type": "remote", "url": "https://example.com/mcp"}}},
        }
        self.config.write_text(json.dumps(original))
        self.run_helper("install")
        result = json.loads(self.config.read_text())
        self.assertEqual(result["theme"], original["theme"])
        self.assertEqual(result["mcp"]["servers"]["other"], original["mcp"]["servers"]["other"])
        worker = result["mcp"]["servers"]["pi-subagent-bridge"]
        self.assertEqual(worker["type"], "local")
        self.assertEqual(worker["command"], ["pi-subagent-bridge", "mcp"])
        self.assertIs(worker["codemode"], False)
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
        servers = data["mcp"]["servers"]
        servers["usr-opencode-worker"] = dict(servers["pi-subagent-bridge"])
        self.config.write_text(json.dumps(data))
        self.run_helper("check", success=False)
        self.assertIn("migrate owned", self.run_helper("plan").stdout)
        self.run_helper("install")
        migrated = json.loads(self.config.read_text())
        self.assertNotIn("usr-opencode-worker", migrated["mcp"]["servers"])
        self.run_helper("check")

    def test_plan_never_writes_or_installs(self):
        output = self.run_helper("plan").stdout
        self.assertIn("NPM: install", output)
        self.assertIn("MCP: register", output)
        self.assertFalse(self.config.exists())
        self.assertFalse(self.log.exists())
        self.run_helper("check", success=False)

    def test_different_name_owner_is_preserved(self):
        original = {"mcp": {"servers": {"pi-subagent-bridge": {
            "type": "remote", "url": "https://example.com/mcp"}}}}
        self.config.write_text(json.dumps(original))
        self.run_helper("install", success=False)
        self.assertEqual(json.loads(self.config.read_text()), original)
        self.assertFalse(self.log.exists())
        self.run_helper("remove", success=False)

    def test_old_manual_registration_is_upgraded(self):
        old = {"mcp": {"servers": {"pi-subagent-bridge": {
            "type": "local", "command": ["node", "--experimental-strip-types",
                                          str(self.project / "src/server.ts")]}}}}
        self.config.write_text(json.dumps(old))
        self.run_helper("install")
        self.assertEqual(json.loads(self.config.read_text())["mcp"]["servers"]
                         ["pi-subagent-bridge"]["command"], ["pi-subagent-bridge", "mcp"])

    def test_other_platform_home_registration_is_adopted(self):
        other = Path("/Users") / self.home.name
        old = {"mcp": {"servers": {"pi-subagent-bridge": {
            "type": "local", "command": [str(other / ".local/share/nodejs/current/bin/node"),
                                          "--experimental-strip-types",
                                          str(other / "usr/tools/pi-subagent-bridge/src/server.ts")],
            "codemode": False}}}}
        self.config.write_text(json.dumps(old))
        self.run_helper("install")
        self.assertEqual(json.loads(self.config.read_text())["mcp"]["servers"]
                         ["pi-subagent-bridge"]["command"],
                         ["pi-subagent-bridge", "mcp"])
        self.run_helper("check")

    def test_relocated_checkout_keeps_owned_registration_and_credentials(self):
        self.config.write_text(json.dumps({"theme": "keep", "mcp": {"servers": {"other": {
            "type": "remote", "url": "https://example.com/mcp"}}}}))
        self.run_helper("install")
        initial = json.loads(self.config.read_text())["mcp"]["servers"]["pi-subagent-bridge"]
        new_root = self.root / "moved-checkout"
        moved_script = new_root / "tools/sync/opencode-worker.py"
        moved_script.parent.mkdir(parents=True)
        shutil.copy2(HELPER, moved_script)
        moved_project = new_root / "tools/pi-subagent-bridge"
        (moved_project / "src").mkdir(parents=True)
        (moved_project / "src/server.ts").write_text("export {}\n")
        shutil.copy2(self.project / "package.json", moved_project / "package.json")
        self.script = moved_script
        self.project = moved_project
        self.run_helper("install")
        self.run_helper("check")
        result = json.loads(self.config.read_text())
        self.assertEqual(result["theme"], "keep")
        self.assertEqual(result["mcp"]["servers"]["other"],
                         {"type": "remote", "url": "https://example.com/mcp"})
        current = result["mcp"]["servers"]["pi-subagent-bridge"]
        self.assertEqual(initial, current)
        self.assertEqual(current["command"], ["pi-subagent-bridge", "mcp"])
        self.run_helper("remove")
        self.assertEqual(json.loads(self.config.read_text())["mcp"]["servers"],
                         {"other": {"type": "remote", "url": "https://example.com/mcp"}})

    def test_foreign_same_shape_without_ownership_is_preserved(self):
        foreign = self.root / "foreign/tools/pi-subagent-bridge/src/server.ts"
        self.config.write_text(json.dumps({"mcp": {"servers": {"pi-subagent-bridge": {
            "type": "local", "command": ["node", "--experimental-strip-types", str(foreign)]}}}}))
        self.run_helper("install", success=False)
        self.assertEqual(json.loads(self.config.read_text())["mcp"]["servers"]
                         ["pi-subagent-bridge"]["command"][-1], str(foreign))

    def test_stale_ownership_fingerprint_does_not_adopt_foreign_server(self):
        self.run_helper("install")
        replacement = self.root / "foreign/tools/pi-subagent-bridge/src/server.ts"
        data = json.loads(self.config.read_text())
        data["mcp"]["servers"]["pi-subagent-bridge"]["command"][-1] = str(replacement)
        self.config.write_text(json.dumps(data))
        self.run_helper("install", success=False)
        self.assertEqual(json.loads(self.config.read_text()), data)

    def test_install_restarts_running_service_once(self):
        self.run_helper("install")
        self.assertEqual(self.restarts(), 1)
        self.run_helper("check")
        self.assertEqual(self.restarts(), 1)
        self.run_helper("install")
        self.assertEqual(self.restarts(), 1)

    def test_no_restart_when_service_not_running(self):
        self.env["MOCK_SERVICE"] = "stopped"
        self.run_helper("install")
        self.assertEqual(self.restarts(), 0)
        self.run_helper("check")

    def test_no_restart_inside_opencode_session(self):
        self.env["OPENCODE"] = "1"
        self.run_helper("install")
        self.assertEqual(self.restarts(), 0)
        self.run_helper("check")

    def test_failed_restart_fails_install(self):
        self.env["MOCK_RESTART_RC"] = "1"
        self.run_helper("install", success=False)
        data = json.loads(self.config.read_text())
        self.assertEqual(data["mcp"]["servers"]["pi-subagent-bridge"]["command"],
                         ["pi-subagent-bridge", "mcp"])

    def test_remove_restarts_running_service(self):
        self.run_helper("install")
        self.assertEqual(self.restarts(), 1)
        self.run_helper("remove")
        self.assertEqual(self.restarts(), 2)
        self.run_helper("remove")
        self.assertEqual(self.restarts(), 2)

    def test_failed_install_never_registers_mcp(self):
        self.env["MOCK_VERSION"] = "0.0.1"
        self.run_helper("install", success=False)
        self.assertFalse(self.config.exists())

    def test_symlinked_config_is_resolved_to_tracked_file(self):
        tracked = self.root / "dotfiles/opencode.json"
        tracked.parent.mkdir()
        tracked.write_text(json.dumps({"theme": "keep"}))
        self.config.symlink_to(tracked)
        self.run_helper("install")
        result = json.loads(tracked.read_text())
        self.assertEqual(result["theme"], "keep")
        worker = result["mcp"]["servers"]["pi-subagent-bridge"]
        self.assertEqual(worker["command"], ["pi-subagent-bridge", "mcp"])
        self.assertTrue(self.config.is_symlink())
        self.run_helper("remove")
        result = json.loads(tracked.read_text())
        self.assertEqual(result["theme"], "keep")
        self.assertEqual(result["mcp"]["servers"], {})


if __name__ == "__main__":
    unittest.main()

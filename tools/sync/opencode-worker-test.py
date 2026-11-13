#!/usr/bin/env python3
"""Offline-only OpenCode bridge removal tests; npm is forbidden in the fixture."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "tools/sync/opencode-worker.py"


class OpenCodeWorkerSyncTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="usr-opencode-remove-")
        self.addCleanup(self.temp.cleanup)
        self.temp_root = Path(self.temp.name).resolve()
        self.home = self.temp_root / "home"
        self.home.mkdir()
        sync = self.temp_root / "tools/sync"
        sync.mkdir(parents=True)
        shutil.copy2(SCRIPT, sync / SCRIPT.name)
        self.script = sync / SCRIPT.name
        self.project = self.temp_root / "tools/pi-subagent-bridge"
        (self.project / "src").mkdir(parents=True)
        (self.project / "src/server.ts").write_text("export {}\n")
        bin_dir = self.temp_root / "bin"
        bin_dir.mkdir()
        (bin_dir / "opencode").write_text("#!/bin/sh\nif [ \"$1\" = service ]; then echo stopped; exit 0; fi\nexit 1\n")
        (bin_dir / "opencode").chmod(0o755)
        self.env = dict(os.environ, HOME=str(self.home), XDG_CONFIG_HOME=str(self.home / ".config"),
                        XDG_STATE_HOME=str(self.home / ".local/state"),
                        PATH=str(bin_dir) + os.pathsep + os.environ.get("PATH", ""))
        self.env.pop("OPENCODE", None)
        self.config = self.home / ".config/opencode/opencode.json"
        self.config.parent.mkdir(parents=True, exist_ok=True)
        self.owner = self.home / ".local/state/sync/opencode-mcp-owner.json"

    def action(self, cmd, success=True):
        result = subprocess.run([sys.executable, "-I", str(self.script), cmd],
                                env=self.env, capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode == 0, success, result.stdout + result.stderr)
        return result

    def write_config(self, servers):
        self.config.write_text(json.dumps({"mcp": {"servers": servers}}))

    def servers(self):
        value = json.loads(self.config.read_text())
        return value.get("mcp", {}).get("servers", {})

    def shim(self):
        return {"type": "local", "command": ["pi-subagent-bridge", "mcp"], "codemode": False}

    def legacy_node(self):
        return {"type": "local", "command": ["node", "--experimental-strip-types",
                                             str(self.project / "src/server.ts")], "codemode": False}

    def test_remove_deletes_owned_registration_and_owner(self):
        self.write_config({"pi-subagent-bridge": self.shim()})
        self.owner.parent.mkdir(parents=True, exist_ok=True)
        self.owner.write_text(json.dumps({"schema": 1, "fingerprint": "a" * 64}))
        self.action("verify-absent", success=False)
        self.action("remove")
        self.assertNotIn("pi-subagent-bridge", self.servers())
        self.assertFalse(self.owner.exists())
        self.action("verify-absent")

    def test_remove_deletes_legacy_name(self):
        self.write_config({"usr-opencode-worker": self.legacy_node()})
        self.action("remove")
        self.assertNotIn("usr-opencode-worker", self.servers())

    def test_remove_preserves_foreign_registration(self):
        foreign = {"type": "remote", "url": "https://example.com"}
        self.write_config({"pi-subagent-bridge": foreign})
        self.action("remove")
        self.assertEqual(self.servers()["pi-subagent-bridge"], foreign)
        self.action("verify-absent")

    def test_remove_is_a_noop_without_registration(self):
        self.write_config({})
        self.action("remove")
        self.assertEqual(self.servers(), {})

    def test_remove_drops_empty_mcp_section(self):
        self.write_config({"pi-subagent-bridge": self.shim()})
        self.action("remove")
        self.assertNotIn("mcp", json.loads(self.config.read_text()))

    def test_remove_preserves_other_servers(self):
        self.write_config({"pi-subagent-bridge": self.shim(),
                           "other": {"type": "local", "command": ["other"]}})
        self.action("remove")
        self.assertIn("other", self.servers())


if __name__ == "__main__":
    unittest.main()

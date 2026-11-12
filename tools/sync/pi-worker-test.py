#!/usr/bin/env python3
"""Offline-only Pi bridge registration tests; npm is forbidden in the fixture."""
import json
import os
import platform
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "tools/sync/pi-worker.py"
OFFLINE = REPO / "tools/sync/pi_offline.py"
RELEASE = REPO / "tools/sync/pi_release.py"
PACKAGES = {
    "@earendil-works/pi-coding-agent": "1.5.0",
    "pi-subagents": "0.87.0",
    "pi-muse-subscription": "0.1.0",
    "@dataforxyz/agent-intercom-pi": "0.10.0",
    "@dataforxyz/agent-intercom-core": "0.1.0",
}


class PiWorkerSyncTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="usr-offline-pi-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.home = self.root / "home"
        self.home.mkdir()
        sync = self.root / "tools/sync"
        sync.mkdir(parents=True)
        shutil.copy2(SCRIPT, sync / SCRIPT.name)
        shutil.copy2(OFFLINE, sync / OFFLINE.name)
        shutil.copy2(RELEASE, sync / RELEASE.name)
        self.script = sync / SCRIPT.name
        self.project = self.root / "tools/pi-subagent-bridge"
        (self.project / "src").mkdir(parents=True)
        (self.project / "src/server.ts").write_text("export {}\n")
        (self.project / "package.json").write_text(json.dumps({
            "dependencies": PACKAGES
        }))
        bin_dir = self.root / "bin"
        bin_dir.mkdir()
        (bin_dir / "node").write_text("#!/bin/sh\nprintf 'v26.13.0\\n'\n")
        (bin_dir / "node").chmod(0o755)
        (bin_dir / "npm").write_text("#!/bin/sh\necho illegal-npm >&2\nexit 99\n")
        (bin_dir / "npm").chmod(0o755)
        (bin_dir / "opencode").write_text("#!/bin/sh\nif [ \"$1\" = service ]; then echo stopped; exit 0; fi\nexit 1\n")
        (bin_dir / "opencode").chmod(0o755)
        self.env = dict(os.environ, HOME=str(self.home), XDG_CONFIG_HOME=str(self.home / ".config"),
                        XDG_DATA_HOME=str(self.home / ".local/share"), XDG_CACHE_HOME=str(self.home / ".cache"),
                        PATH=str(bin_dir) + os.pathsep + os.environ.get("PATH", ""))
        self.env.pop("OPENCODE", None)
        self.config = self.home / ".pi/agent/mcp.json"
        self.config.parent.mkdir(parents=True, exist_ok=True)
        sha = "a" * 64
        arch = {"x86_64": "x64", "aarch64": "arm64", "arm64": "arm64"}.get(platform.machine().lower(), "x64")
        key = platform.system().lower() + "-" + arch
        pin = {"schema": 1, "release_url": "https://example.invalid/pi/", "builder_revision": "b" * 40,
               "profile": "full", "provenance_sha256": "c" * 64,
               "targets": {key: {"archive": key + "-full.tar.gz", "sha256": sha, "bytes": 1}}}
        (self.root / "tools/pi").mkdir(parents=True)
        (self.root / "tools/pi/runtime.pin.json").write_text(json.dumps(pin))
        self.prefix = self.home / ".local/share/pi-runtime"
        self.runtime = self.prefix / "releases" / sha
        for name, version in PACKAGES.items():
            pkg = self.runtime / "node_modules" / name
            pkg.mkdir(parents=True)
            (pkg / "package.json").write_text(json.dumps({"version":version}))
        cli = self.runtime / "node_modules/@earendil-works/pi-coding-agent/dist/bundle/cli.js"
        cli.parent.mkdir(parents=True)
        cli.write_text("export {}")
        (self.runtime / ".usr-pi-release.json").write_text(json.dumps({"pin": pin, "target": key, "files": {}}))
        (self.prefix / ".usr-pi-releases").touch()
        (self.prefix / "current").symlink_to("releases/" + sha)

    def action(self, cmd, success=True):
        result = subprocess.run([sys.executable, "-I", str(self.script), cmd],
                                env=self.env, capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode == 0, success, result.stdout + result.stderr)
        return result

    def servers(self):
        value = json.loads(self.config.read_text())
        return value["mcp"]["servers"] if "pi" == "opencode" else value["mcpServers"]

    def test_offline_install_check_remove_and_idempotence(self):
        self.assertIn("OFFLINE:", self.action("plan").stdout)
        self.assertFalse((self.project / "node_modules").exists())
        self.action("check", success=False)
        self.action("install")
        self.assertTrue((self.project / "node_modules").is_symlink())
        self.assertEqual((self.project / "node_modules").resolve(), (self.runtime / "node_modules").resolve())
        self.assertIn("pi-subagent-bridge", self.servers())
        self.action("check")
        before = self.config.read_bytes()
        self.action("install")
        self.assertEqual(self.config.read_bytes(), before)
        self.action("remove")
        self.assertNotIn("pi-subagent-bridge", self.servers())

    def test_foreign_bridge_dependency_directory_is_preserved(self):
        foreign = self.project / "node_modules/.pnpm"
        foreign.mkdir(parents=True)
        (foreign / "do-not-delete").write_text("sentinel")
        self.action("install", success=False)
        self.assertEqual((foreign / "do-not-delete").read_text(), "sentinel")

    def test_foreign_registration_is_preserved(self):
        if "pi" == "opencode":
            document = {"mcp": {"servers": {"pi-subagent-bridge": {"type":"remote","url":"https://example.com"}}}}
        else:
            document = {"mcpServers":{"pi-subagent-bridge":{"command":"another","args":["different"]}}}
        self.config.write_text(json.dumps(document))
        self.action("install", success=False)
        self.assertEqual(json.loads(self.config.read_text()), document)
        self.assertFalse((self.project / "node_modules").exists())

    def test_runtime_unavailable_fails_closed(self):
        (self.runtime / ".usr-pi-release.json").unlink()
        self.action("install", success=False)
        self.assertFalse((self.project / "node_modules").exists())

    def test_legacy_owned_registration_migrates(self):
        self.action("install")
        data = json.loads(self.config.read_text())
        servers = data["mcp"]["servers"] if "pi" == "opencode" else data["mcpServers"]
        servers["usr-opencode-worker"] = dict(servers["pi-subagent-bridge"])
        self.config.write_text(json.dumps(data))
        self.action("check", success=False)
        self.action("install")
        self.assertNotIn("usr-opencode-worker", self.servers())


if __name__ == "__main__":
    unittest.main()

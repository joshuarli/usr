#!/usr/bin/env python3
"""Prove sh sync bridge is npm-free from a fresh user HOME.

CI-only: installs an ignored bridge node_modules symlink in this checkout.
Use a disposable checkout to avoid disturbing an existing developer setup.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
BRIDGE_LINK = ROOT / "tools/pi-subagent-bridge/node_modules"


class BridgeOfflineEndToEnd(unittest.TestCase):
    def test_fresh_home_and_second_sync_do_not_invoke_npm(self) -> None:
        node = shutil.which("node")
        if not node:
            self.skipTest("Node.js unavailable")
        version = subprocess.run([node, "-p", "process.versions.node"],
                                 capture_output=True, text=True, check=True).stdout.strip()
        if int(version.split(".")[0]) < 26:
            self.skipTest("Requires Node.js 26")
        if BRIDGE_LINK.exists() or BRIDGE_LINK.is_symlink():
            self.skipTest("Refusing to change an existing developer bridge installation")
        with tempfile.TemporaryDirectory(prefix="usr-bridge-no-npm-") as scratch:
            base = Path(scratch)
            home = base / "home"
            bindir = home / ".local/bin"
            bindir.mkdir(parents=True)
            # Node is already available; this test isolates Pi from the separate
            # Node binary download while poisoning all npm invocations.
            (bindir / "node").symlink_to(node)
            npm = bindir / "npm"
            marker = base / "forbidden-npm-invocations"
            npm.write_text(
                "#!/bin/sh\nprintf '%s\\n' \"$*\" >> \"$NPM_FORBIDDEN_LOG\"\nexit 97\n")
            npm.chmod(0o755)
            config = home / ".offline-opencode/opencode/opencode.json"
            config.parent.mkdir(parents=True)
            config.write_text("{}\n")
            env = dict(os.environ)
            env.update(
                HOME=str(home), TARGET=str(home),
                XDG_CONFIG_HOME=str(home / ".offline-opencode"),
                XDG_STATE_HOME=str(home / ".local/state"),
                XDG_DATA_HOME=str(home / ".local/share"),
                PATH=str(bindir) + os.pathsep + env.get("PATH", ""),
                NPM_FORBIDDEN_LOG=str(marker),
                npm_config_registry="http://127.0.0.1:9",
                PI_OFFLINE="1",
            )
            for key in ("OPENCODE", "PI_CODING_AGENT_DIR"):
                env.pop(key, None)
            try:
                for attempt in range(2):
                    proc = subprocess.run(
                        ["sh", str(ROOT / "sync"), "bridge"],
                        cwd=ROOT, env=env,
                        capture_output=True, text=True, timeout=180)
                    self.assertEqual(proc.returncode, 0,
                                     f"attempt {attempt+1}: {proc.stdout}\n{proc.stderr}")
                    self.assertFalse(marker.exists(),
                                     "A Pi setup action invoked npm: " + (
                                         marker.read_text() if marker.exists() else ""))
                pi = bindir / "pi"
                self.assertTrue(pi.is_symlink())
                self.assertIn("PI_OFFLINE=1", pi.resolve().read_text())
                self.assertEqual(BRIDGE_LINK.resolve(),
                                 home / ".local/share/pi/node_modules")
                self.assertTrue((home / ".pi/agent/mcp.json").is_file())
                self.assertTrue((home / ".claude.json").is_file())
                self.assertIn("pi-subagent-bridge",
                              json.loads(config.read_text())["mcp"]["servers"])
                intercom = json.loads((home / ".pi/agent/intercom/config.json").read_text())
                self.assertEqual(intercom["inboundTrigger"], "never")
                self.assertEqual(intercom["brokerCommand"], "node")
                proc = subprocess.run([str(pi), "--version"],
                                      cwd=base, env=env,
                                      capture_output=True, text=True, timeout=30)
                self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
                self.assertIn("1.5.0", proc.stdout)
                self.assertFalse(marker.exists())
            finally:
                if BRIDGE_LINK.is_symlink() and BRIDGE_LINK.resolve() == home / ".local/share/pi/node_modules":
                    BRIDGE_LINK.unlink()


if __name__ == "__main__":
    unittest.main()

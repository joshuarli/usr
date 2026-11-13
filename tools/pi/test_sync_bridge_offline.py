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
from unittest.mock import patch

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
            # Mimic an already-managed Node 26 installation. Node's sync task
            # reconciles on every run; a foreign launcher would be rejected.
            # The only npm operation permitted here is --version, which makes
            # no network request. All npm installs, views and updates are poisoned.
            import platform
            osname = platform.system().lower()
            machine = platform.machine().lower()
            arch = "arm64" if machine in ("aarch64", "arm64") else "x64"
            if osname == "darwin":
                target = "darwin-" + arch
            else:
                glibc = subprocess.run(["getconf", "GNU_LIBC_VERSION"],
                                       capture_output=True, text=True).returncode == 0
                target = "linux-" + arch + ("" if glibc else "-musl")
            release = home / ".local/share/nodejs" / f"26.13.1-npm11.20.0-{target}"
            nodebin = release / "bin"
            nodebin.mkdir(parents=True)
            (nodebin / "node").symlink_to(node)
            marker = base / "forbidden-npm-invocations"
            npm = nodebin / "npm"
            npm.write_text(
                '#!/bin/sh\n'
                'if [ "$1" = --version ]; then printf "11.20.0\\n"; exit 0; fi\n'
                'printf "%s\\n" "$*" >> "$NPM_FORBIDDEN_LOG"\n'
                'exit 97\n'
            )
            npm.chmod(0o755)
            npx = nodebin / "npx"
            npx.write_text('#!/bin/sh\nexit 97\n')
            npx.chmod(0o755)
            opencode = bindir / "opencode"
            opencode.write_text('#!/bin/sh\nif [ "$1/$2" = service/status ]; then printf "stopped\\n"; exit 0; fi\nexit 98\n')
            opencode.chmod(0o755)
            current = home / ".local/share/nodejs/current"
            current.symlink_to(release, target_is_directory=True)
            for tool in ("node", "npm", "npx"):
                (bindir / tool).symlink_to(current / "bin" / tool)
            config = home / ".offline-opencode/opencode/opencode.json"
            config.parent.mkdir(parents=True)
            config.write_text("{}\n")
            env = dict(os.environ)
            env.update(
                HOME=str(home), TARGET=str(home),
                XDG_CONFIG_HOME=str(home / ".offline-opencode"),
                XDG_STATE_HOME=str(home / ".local/state"),
                XDG_DATA_HOME=str(home / ".local/share"),
                XDG_CACHE_HOME=str(home / ".cache"),
                PATH=str(bindir) + os.pathsep + env.get("PATH", ""),
                NPM_FORBIDDEN_LOG=str(marker),
                npm_config_registry="http://127.0.0.1:9",
                PI_OFFLINE="1",
            )
            for key in ("OPENCODE", "PI_CODING_AGENT_DIR"):
                env.pop(key, None)
            sys.path.insert(0, str(ROOT / "tools/sync"))
            sys.path.insert(0, str(ROOT / "tools/pi"))
            from release_cache import seed
            seed(home / ".cache/usr/pi-releases")
            from link_apply import apply
            from link_plan import plan_links
            from links import discover
            owned = home / ".local/state/sync/dl-owned"
            env["DL_OWNED_FILE"] = str(owned)
            unlink = Path.unlink
            def interrupt_journal(path, *args, **kwargs):
                if path.parent.name.endswith(".pending-links") and path.suffix == ".json":
                    raise OSError("fixture interruption after stage deletion")
                return unlink(path, *args, **kwargs)
            with patch.object(Path, "unlink", interrupt_journal):
                with self.assertRaisesRegex(OSError, "fixture interruption after stage deletion"):
                    apply(plan_links(discover(ROOT, home, osname), owned), owned)
            pending = owned.with_name(owned.name + ".pending-links")
            self.assertTrue(list(pending.glob("*.json")))
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
                self.assertFalse(list(pending.glob("*.json")), "whole sync bridge did not finalize the interrupted link journal")
                pi = bindir / "pi"
                self.assertTrue(pi.is_symlink())
                self.assertIn("PI_OFFLINE=1", pi.resolve().read_text())
                self.assertEqual(os.readlink(BRIDGE_LINK),
                                 str(home / ".local/share/pi-runtime/current/node_modules"))
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
                for subcommand in ("update", "install"):
                    refused = subprocess.run([str(pi), subcommand, "npm:bad@latest"],
                                             cwd=base, env=env, capture_output=True,
                                             text=True, timeout=15)
                    self.assertEqual(refused.returncode, 64)
                    self.assertIn("/pi-update", refused.stderr)
                self.assertFalse(marker.exists())
            finally:
                if BRIDGE_LINK.is_symlink() and os.readlink(BRIDGE_LINK) == str(home / ".local/share/pi-runtime/current/node_modules"):
                    BRIDGE_LINK.unlink()


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""End-to-end companion install tests against a local HTTP release fixture."""
from __future__ import annotations

import functools
import hashlib
import http.server
import io
import json
import os
from pathlib import Path
import shutil
import sys
import tarfile
import tempfile
import threading
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/sync"))
import companions  # noqa: E402
import pi_offline  # noqa: E402
import pi_release  # noqa: E402

REVISION = "a" * 40
VERSIONS = {
    "agent-intercom-claude": "0.10.0",
    "agent-intercom-codex": "0.10.0",
    "agent-intercom-opencode": "0.10.0",
}
RUNTIME_ARCHIVE = "pi-headless-usr-1.5.0-aarch64-apple-darwin.tar.xz"


def companion_tgz(name: str, version: str) -> bytes:
    bins = {
        "agent-intercom-claude": {
            "claude-intercom-mcp": "dist/claude-server.mjs",
            "claude-intercom-worker": "dist/worker-daemon.mjs",
            "cci": "dist/cci.mjs",
            "ccim": "dist/ccim.mjs",
        },
        "agent-intercom-codex": {
            "codex-intercom-mcp": "dist/codex-server.mjs",
            "codex-intercom-bridge": "dist/bridge-daemon.mjs",
            "coi": "dist/coi.mjs",
        },
        "agent-intercom-opencode": {},
    }[name]
    package = {
        "name": f"@dataforxyz/{name}",
        "version": version,
        "type": "module",
        "main": "dist/plugin.mjs",
    }
    if name == "agent-intercom-opencode":
        package["exports"] = {".": "./dist/plugin.mjs", "./tui": "./dist/tui.mjs"}
    else:
        package["bin"] = bins
    files = {"package/package.json": json.dumps(package).encode()}
    for bin_name, relative in bins.items():
        files[f"package/{relative}"] = f"#!/usr/bin/env node\n// {bin_name}\n".encode()
    if name == "agent-intercom-opencode":
        files["package/dist/plugin.mjs"] = b"// plugin\n"
        files["package/dist/tui.mjs"] = b"// tui\n"
    else:
        files["package/dist/broker.mjs"] = b"// broker\n"
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as bundle:
        for relative, content in sorted(files.items()):
            member = tarfile.TarInfo(relative)
            member.size = len(content)
            member.mode = 0o755 if any(member.name.endswith(r) for r in bins.values()) else 0o644
            bundle.addfile(member, io.BytesIO(content))
    return buffer.getvalue()


class CompanionPinSelectionTests(unittest.TestCase):
    def test_disabled_companions_skip_packages_and_harness_configuration(self):
        switches = dict.fromkeys(companions.read_switches(), False)
        with patch.object(companions, "read_switches", return_value=switches), \
                patch.object(companions, "load_pin_for_sync", side_effect=AssertionError("loaded pin")), \
                patch.object(companions, "sync_claude", side_effect=AssertionError("touched Claude")):
            self.assertEqual(companions.command_install({}), 0)
            self.assertEqual(companions.command_check({}), 0)
            self.assertEqual(companions.command_plan({}), 0)

    def test_reviewed_absolute_override_selects_all_companions_with_its_runtime(self):
        with tempfile.TemporaryDirectory(prefix="usr-companion-pin-") as directory:
            override = Path(directory) / "reviewed.json"
            pin = json.loads(pi_release.PIN.read_text())
            pin["builder_revision"] = "b" * 40
            pin["companions"]["agent-intercom-codex"]["sha256"] = "c" * 64
            override.write_text(json.dumps(pin))
            selected = companions.load_pin_for_sync({"USR_PI_RUNTIME_PIN": str(override)})
            self.assertEqual(selected, pin)
            self.assertNotEqual(selected["builder_revision"], pi_release.load_pin()["builder_revision"])

    def test_missing_explicit_override_does_not_fall_back(self):
        with tempfile.TemporaryDirectory(prefix="usr-companion-pin-") as directory:
            with self.assertRaisesRegex(pi_offline.OfflinePiError, "cannot read Pi release pin"):
                companions.load_pin_for_sync({"USR_PI_RUNTIME_PIN": str(Path(directory) / "missing.json")})

    def test_relative_override_is_rejected_before_any_pin_read(self):
        with patch.object(pi_release, "load_pin", side_effect=AssertionError("must reject before reading")):
            with self.assertRaisesRegex(ValueError, "USR_PI_RUNTIME_PIN must be absolute"):
                companions.load_pin_for_sync({"USR_PI_RUNTIME_PIN": "relative.json"})


class CompanionFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="usr-companions-")
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.assets = root / "assets"
        self.assets.mkdir()
        self.requests = []
        requests = self.requests

        class Handler(http.server.SimpleHTTPRequestHandler):
            def log_message(self, format, *args):
                pass

            def do_GET(self):
                requests.append(self.path)
                super().do_GET()

        self.server = http.server.ThreadingHTTPServer(
            ("127.0.0.1", 0), functools.partial(Handler, directory=str(self.assets)))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop_server)
        home = root / "home"
        (home / ".local/bin").mkdir(parents=True)
        (home / ".local/state").mkdir(parents=True)
        node = shutil.which("node")
        if node:
            release = home / ".local/share/nodejs/current/bin"
            release.mkdir(parents=True)
            (release / "node").symlink_to(node)
        self.env = {
            "HOME": str(home),
            "TARGET": str(home),
            "XDG_DATA_HOME": str(home / ".local/share"),
            "XDG_CONFIG_HOME": str(home / ".config"),
            "XDG_CACHE_HOME": str(home / ".cache"),
            "XDG_STATE_HOME": str(home / ".local/state"),
            "PATH": str(home / ".local/bin") + os.pathsep + os.environ.get("PATH", ""),
        }
        self.home = home
        self.pin = self.publish()

    def stop_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def publish(self, tamper=None, corrupt_provenance=False, bad_member=None) -> dict:
        companions = {}
        for name, version in VERSIONS.items():
            data = companion_tgz(name, version)
            if bad_member == name:
                buffer = io.BytesIO()
                with tarfile.open(fileobj=buffer, mode="w:gz") as bundle:
                    member = tarfile.TarInfo("package/../escape.txt")
                    payload = b"escape\n"
                    member.size = len(payload)
                    bundle.addfile(member, io.BytesIO(payload))
                data = buffer.getvalue()
            if tamper == name:
                data = data[:20] + b"flip" + data[24:]
            archive = self.assets / f"{name}-{version}.tgz"
            archive.write_bytes(data)
            companions[name] = {
                "archive": archive.name,
                "version": version,
                "sha256": hashlib.sha256(data).hexdigest(),
                "bytes": len(data),
                "source_sha": hashlib.sha256(name.encode()).hexdigest()[:40],
            }
        provenance = {
            "schema": 1,
            "builder_revision": REVISION,
            "profile": "headless-usr",
            "product": "pi-headless-usr",
            "version": "1.5.0",
            "sources_sha256": "s",
            "components": {"companions": "source-snapshot-packed"},
            "targets": {
                "aarch64-apple-darwin": {
                    "target": "aarch64-apple-darwin",
                    "profile": "headless-usr",
                    "archive": RUNTIME_ARCHIVE,
                    "sha256": "1" * 64,
                    "bytes": 1,
                }
            },
            "inputs": {},
            "companions": companions if not corrupt_provenance else {
                name: {**entry, "sha256": "0" * 64} for name, entry in companions.items()
            },
        }
        raw = json.dumps(provenance).encode()
        (self.assets / "provenance.json").write_bytes(raw)
        sums_lines = [f"{entry['sha256']}  {entry['archive']}" for entry in companions.values()]
        sums_lines.append(f"{'1' * 64}  {RUNTIME_ARCHIVE}")
        (self.assets / "SHA256SUMS").write_text("\n".join(sums_lines) + "\n")
        return {
            "schema": 1,
            "release_url": f"http://127.0.0.1:{self.server.server_port}",
            "builder_revision": REVISION,
            "profile": "headless-usr",
            "version": "1.5.0",
            "provenance_sha256": hashlib.sha256(raw).hexdigest(),
            "targets": {
                "darwin-arm64": {"archive": RUNTIME_ARCHIVE, "sha256": "1" * 64, "bytes": 1},
                "linux-x64": {"archive": "pi-headless-usr-1.5.0-x86_64-unknown-linux-musl.tar.xz",
                              "sha256": "2" * 64, "bytes": 1},
                "linux-arm64": {"archive": "pi-headless-usr-1.5.0-aarch64-unknown-linux-musl.tar.xz",
                                "sha256": "3" * 64, "bytes": 1},
            },
            "companions": companions,
        }

    def call(self, action, pin=None):
        env = self.env
        functions = {
            "plan": companions.command_plan,
            "check": companions.command_check,
            "install": companions.command_install,
            "remove": companions.command_remove,
            "preflight": companions.command_preflight,
            "verify-absent": companions.command_verify_absent,
        }
        with patch.object(companions.pi_release, "load_pin", lambda *a, **kw: pin or self.pin):
            return functions[action](env)

    def bumped_pin(self):
        pin = json.loads(json.dumps(self.pin))
        pin["builder_revision"] = "b" * 40
        return pin

    def root(self, name):
        return Path(self.env["XDG_DATA_HOME"]) / "agent-intercom" / name

    def test_fresh_install_registers_and_checks(self):
        self.assertEqual(self.call("install"), 0)
        root = Path(self.env["XDG_DATA_HOME"]) / "agent-intercom"
        for name in companions.COMPANIONS:
            self.assertTrue((root / name / "package.json").is_file())
            self.assertTrue((root / name / ".usr-companion.json").is_file())
        shim = Path(self.env["HOME"]) / ".local/bin/claude-intercom-mcp"
        self.assertTrue(shim.is_file())
        self.assertTrue(os.access(shim, os.X_OK))
        claude = json.loads((Path(self.env["HOME"]) / ".claude.json").read_text())
        entry = claude["mcpServers"]["claude-intercom"]
        self.assertEqual(entry["command"], str(Path(self.env["HOME"]) / ".local/share/nodejs/current/bin/node"))
        self.assertEqual(entry["args"], [str(root / "agent-intercom-claude/dist/claude-server.mjs")])
        opencode_dir = Path(self.env["XDG_CONFIG_HOME"]) / "opencode"
        self.assertFalse((opencode_dir / "opencode.jsonc").exists())
        self.assertFalse((opencode_dir / "opencode.json").exists())
        self.assertFalse((opencode_dir / "tui.json").exists())
        self.assertEqual(self.call("check"), 0)

    def test_second_install_is_a_no_op(self):
        self.assertEqual(self.call("install"), 0)
        root = Path(self.env["XDG_DATA_HOME"]) / "agent-intercom"
        before = {name: (root / name / ".usr-companion.json").read_bytes() for name in companions.COMPANIONS}
        self.assertEqual(self.call("install"), 0)
        after = {name: (root / name / ".usr-companion.json").read_bytes() for name in companions.COMPANIONS}
        self.assertEqual(before, after)

    def test_uninstall_removes_owned_entries_only(self):
        home = Path(self.env["HOME"])
        (home / ".claude.json").write_text(json.dumps({
            "mcpServers": {
                "unrelated": {"command": "other", "args": []},
            },
        }))
        opencode_dir = Path(self.env["XDG_CONFIG_HOME"]) / "opencode"
        opencode_dir.mkdir(parents=True)
        (opencode_dir / "opencode.jsonc").write_text(json.dumps({
            "plugins": ["/foreign/path/plugin.mjs",
                        str(Path(self.env["XDG_DATA_HOME"]) / "agent-intercom/agent-intercom-opencode/dist/plugin.mjs")],
            "mcp": {"servers": {"unrelated": {"type": "local", "command": ["node", "other.js"]}}},
        }) + "\n")
        self.assertEqual(self.call("install"), 0)
        self.assertEqual(self.call("remove"), 0)
        self.assertEqual(self.call("verify-absent"), 0)
        claude = json.loads((home / ".claude.json").read_text())
        self.assertEqual(claude["mcpServers"], {"unrelated": {"command": "other", "args": []}})
        opencode = json.loads((opencode_dir / "opencode.jsonc").read_text())
        self.assertEqual(opencode["plugins"], ["/foreign/path/plugin.mjs"])
        self.assertEqual(opencode["mcp"]["servers"]["unrelated"]["command"], ["node", "other.js"])
        for name in companions.COMPANIONS:
            self.assertFalse((Path(self.env["XDG_DATA_HOME"]) / "agent-intercom" / name).exists())

    def test_install_removes_retired_opencode_registration(self):
        root = Path(self.env["XDG_DATA_HOME"]) / "agent-intercom"
        legacy = str(root / "agent-intercom-opencode/dist/plugin.mjs")
        current = str(root / "agent-intercom-opencode")
        opencode_dir = Path(self.env["XDG_CONFIG_HOME"]) / "opencode"
        opencode_dir.mkdir(parents=True)
        (opencode_dir / "opencode.jsonc").write_text(json.dumps({
            "$schema": "https://opencode.ai/config.json",
            "plugins": ["/foreign/path/plugin.mjs", legacy, current],
        }) + "\n")
        self.assertEqual(self.call("install"), 0)
        opencode = json.loads((opencode_dir / "opencode.jsonc").read_text())
        self.assertEqual(opencode["plugins"], ["/foreign/path/plugin.mjs"])
        self.assertEqual(self.call("remove"), 0)
        self.assertEqual(self.call("verify-absent"), 0)
        opencode = json.loads((opencode_dir / "opencode.jsonc").read_text())
        self.assertEqual(opencode["plugins"], ["/foreign/path/plugin.mjs"])

    def test_symlinked_tracked_opencode_json_is_untouched(self):
        home = Path(self.env["HOME"])
        tracked = home / "checkout.json"
        tracked.write_text(json.dumps({
            "$schema": "https://opencode.ai/config.json",
            "model": "example/model",
        }) + "\n")
        before = tracked.read_bytes()
        opencode_dir = Path(self.env["XDG_CONFIG_HOME"]) / "opencode"
        opencode_dir.mkdir(parents=True)
        (opencode_dir / "opencode.json").symlink_to(tracked)
        (opencode_dir / "opencode.jsonc").write_text(json.dumps({
            "$schema": "https://opencode.ai/config.json",
            "plugins": [str(Path(self.env["XDG_DATA_HOME"]) / "agent-intercom/agent-intercom-opencode")],
        }) + "\n")
        self.assertEqual(self.call("install"), 0)
        self.assertEqual(tracked.read_bytes(), before)
        self.assertFalse((opencode_dir / "opencode.jsonc").exists())
        self.assertEqual(self.call("remove"), 0)
        self.assertEqual(self.call("verify-absent"), 0)
        self.assertEqual(tracked.read_bytes(), before)

    def test_foreign_claude_entry_blocks_install_and_removal_is_retained(self):
        home = Path(self.env["HOME"])
        before = {"mcpServers": {"claude-intercom": {"command": "custom", "args": ["custom.js"]}}}
        (home / ".claude.json").write_text(json.dumps(before))
        with self.assertRaises(ValueError):
            self.call("install")
        self.assertEqual(json.loads((home / ".claude.json").read_text()), before)
        self.assertEqual(self.call("remove"), 0)
        self.assertEqual(json.loads((home / ".claude.json").read_text()), before)

    def test_tampered_archive_is_rejected(self):
        pin = self.publish(tamper="agent-intercom-claude")
        with self.assertRaises(ValueError):
            self.call("install", pin=pin)

    def test_corrupt_provenance_is_rejected(self):
        pin = self.publish(corrupt_provenance=True)
        with self.assertRaises(ValueError):
            self.call("install", pin=pin)

    def test_unsafe_member_is_rejected(self):
        pin = self.publish(bad_member="agent-intercom-codex")
        with self.assertRaises(ValueError):
            self.call("install", pin=pin)

    def test_foreign_install_root_is_refused(self):
        root = Path(self.env["XDG_DATA_HOME"]) / "agent-intercom/agent-intercom-claude"
        root.mkdir(parents=True)
        (root / "stray.txt").write_text("not ours\n")
        with self.assertRaises(ValueError):
            self.call("install")
        self.assertTrue((root / "stray.txt").is_file())

    def test_modified_install_fails_check(self):
        self.assertEqual(self.call("install"), 0)
        target = (Path(self.env["XDG_DATA_HOME"]) / "agent-intercom"
                  / "agent-intercom-claude/dist/claude-server.mjs")
        target.write_bytes(b"// tampered\n")
        with self.assertRaises(ValueError):
            self.call("check")

    def test_pin_bump_replaces_intact_install(self):
        self.assertEqual(self.call("install"), 0)
        bumped = self.bumped_pin()
        self.assertEqual(self.call("install", pin=bumped), 0)
        root = self.root("agent-intercom-claude")
        self.assertEqual(companions.install_status(root, bumped, "agent-intercom-claude"), "current")
        receipt = json.loads((root / companions.RECEIPT).read_text())
        self.assertEqual(receipt["pin"]["builder_revision"], "b" * 40)

    def test_pin_bump_preserves_modified_install(self):
        self.assertEqual(self.call("install"), 0)
        root = self.root("agent-intercom-claude")
        (root / "personal.txt").write_text("keep me\n")
        with self.assertRaises(ValueError):
            self.call("install", pin=self.bumped_pin())
        self.assertEqual((root / "personal.txt").read_text(), "keep me\n")

    def test_install_status_is_modified_for_old_and_new_pin(self):
        self.assertEqual(self.call("install"), 0)
        root = self.root("agent-intercom-claude")
        (root / "personal.txt").write_text("keep me\n")
        self.assertEqual(companions.install_status(root, self.pin, "agent-intercom-claude"), "modified")
        self.assertEqual(companions.install_status(root, self.bumped_pin(), "agent-intercom-claude"), "modified")

    def test_remove_refuses_unrecorded_foreign_root(self):
        root = self.root("agent-intercom-codex")
        root.mkdir(parents=True)
        (root / "foreign.txt").write_text("not ours\n")
        with self.assertRaises(ValueError):
            self.call("remove")
        self.assertEqual((root / "foreign.txt").read_text(), "not ours\n")

    def test_remove_refuses_modified_root_and_keeps_registration(self):
        home = Path(self.env["HOME"])
        self.assertEqual(self.call("install"), 0)
        before = (home / ".claude.json").read_bytes()
        target = self.root("agent-intercom-claude") / "dist/claude-server.mjs"
        target.write_bytes(b"// tampered\n")
        with self.assertRaises(ValueError):
            self.call("remove")
        self.assertEqual((home / ".claude.json").read_bytes(), before)
        self.assertEqual(target.read_bytes(), b"// tampered\n")

    def test_remove_refuses_non_directory_companion_root(self):
        root = self.root("agent-intercom-opencode")
        root.parent.mkdir(parents=True)
        root.write_text("not a directory\n")
        with self.assertRaises(ValueError):
            self.call("remove")
        self.assertEqual(root.read_text(), "not a directory\n")

    def test_remove_refuses_receipt_with_mismatched_companion_identity(self):
        root = self.root("agent-intercom-claude")
        root.mkdir(parents=True)
        receipt = {
            "pin": {
                "builder_revision": self.pin["builder_revision"],
                "version": self.pin["version"],
                "source_sha": self.pin["companions"]["agent-intercom-claude"]["source_sha"],
            },
            "companion": "agent-intercom-codex",
            "archive": self.pin["companions"]["agent-intercom-claude"]["archive"],
            "sha256": self.pin["companions"]["agent-intercom-claude"]["sha256"],
            "files": {},
        }
        (root / companions.RECEIPT).write_text(json.dumps(receipt))
        self.assertEqual(companions.install_status(root, self.pin, "agent-intercom-claude"), "foreign")
        with self.assertRaises(ValueError):
            self.call("remove")
        self.assertTrue(root.is_dir())

    def test_remove_refuses_receipt_with_unsafe_file_entry(self):
        root = self.root("agent-intercom-codex")
        root.mkdir(parents=True)
        receipt = {
            "pin": {
                "builder_revision": self.pin["builder_revision"],
                "version": self.pin["version"],
                "source_sha": self.pin["companions"]["agent-intercom-codex"]["source_sha"],
            },
            "companion": "agent-intercom-codex",
            "archive": self.pin["companions"]["agent-intercom-codex"]["archive"],
            "sha256": self.pin["companions"]["agent-intercom-codex"]["sha256"],
            "files": {"../../escape.txt": {"sha256": "0" * 64, "mode": 0o644}},
        }
        (root / companions.RECEIPT).write_text(json.dumps(receipt))
        self.assertEqual(companions.install_status(root, self.pin, "agent-intercom-codex"), "foreign")
        with self.assertRaises(ValueError):
            self.call("remove")
        self.assertTrue(root.is_dir())

    def test_preflight_succeeds_for_intact_install(self):
        self.assertEqual(self.call("install"), 0)
        self.assertEqual(self.call("preflight"), 0)


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3

import importlib.util
import importlib.machinery
import io
import plistlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


loader = importlib.machinery.SourceFileLoader("macos_tool", str(Path(__file__).with_name("macos")))
spec = importlib.util.spec_from_loader(loader.name, loader)  # ty: ignore[invalid-argument-type] # typeshed LoaderProtocol still requires legacy load_module, which spec_from_loader never calls
assert spec is not None
macos = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(macos)


class PreferenceTests(unittest.TestCase):
    def test_lean_subcommand_forwards_arguments_and_status(self):
        with patch.object(macos.lean_command, "main", return_value=7) as lean_main:
            self.assertEqual(macos.main(["lean", "--audit"]), 7)
        lean_main.assert_called_once_with(["--audit"])

    def test_merge_preserves_unmanaged_values_at_each_dictionary_level(self):
        current = {"managed": {"enabled": False, "other": 4}, "unmanaged": "keep"}
        wanted = {"managed": {"enabled": True, "new": 5}}
        self.assertEqual(
            macos.merge_preferences(current, wanted),
            {"managed": {"enabled": True, "other": 4, "new": 5}, "unmanaged": "keep"},
        )

    def test_diff_tracks_add_remove_nested_and_plist_type_changes(self):
        before = {"nested": {"removed": 1, "kept": True}, "typed": True}
        after = {"nested": {"added": 2, "kept": True}, "typed": 1}
        self.assertEqual(
            macos.preference_differences(before, after),
            [("+", ("nested", "added")), ("-", ("nested", "removed")), ("~", ("typed",))],
        )

    def test_live_diff_ignores_unmanaged_nested_values(self):
        wanted = {"managed": {"enabled": True}}
        current = {"managed": {"enabled": True, "other": "keep"}, "extra": 2}
        self.assertEqual(macos.managed_differences(wanted, current), [])

    def test_promote_copies_only_selected_snapshot_keys_and_preserves_types(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            snapshot_path, manifest_path = root / "snapshot.plist", root / "manifest.plist"
            data = {
                "formatVersion": 1,
                "user": {"com.apple.dock": {"autohide": True, "count": 3}},
                "currentHost": {},
            }
            snapshot_path.write_bytes(plistlib.dumps(data))
            macos.promote(snapshot_path, manifest_path, ["com.apple.dock:autohide"])
            manifest = plistlib.loads(manifest_path.read_bytes())
            self.assertEqual(manifest["domains"], {"com.apple.dock": {"autohide": True}})
            self.assertEqual(manifest_path.stat().st_mode & 0o777, 0o644)

    def test_write_refuses_symlink_destination(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target, link = root / "target.plist", root / "link.plist"
            target.write_bytes(b"original")
            link.symlink_to(target)
            with self.assertRaisesRegex(RuntimeError, "symlink"):
                macos.write_plist(link, {"value": True}, 0o600)
            self.assertEqual(target.read_bytes(), b"original")

    def test_apply_dry_run_does_not_import(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest_path = Path(directory) / "manifest.plist"
            manifest_path.write_bytes(plistlib.dumps({
                "formatVersion": 1,
                "domains": {"com.apple.dock": {"autohide": True}},
            }))
            with patch.object(macos, "live_domains", return_value={"com.apple.dock"}), \
                    patch.object(macos, "export_domain", return_value={"autohide": False, "other": 1}), \
                    patch.object(macos, "defaults") as command, \
                    patch("sys.stdout", new_callable=io.StringIO) as output:
                macos.apply_manifest(manifest_path, True, None, [])
            command.assert_not_called()
            self.assertIn("would set user com.apple.dock/autohide", output.getvalue())

    def test_apply_merges_and_verifies_imported_domain(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest_path = Path(directory) / "manifest.plist"
            manifest_path.write_bytes(plistlib.dumps({
                "formatVersion": 1,
                "domains": {"com.apple.dock": {"managed": {"enabled": True}}},
            }))
            actual = {"managed": {"enabled": False, "other": 1}, "unmanaged": 2}

            def run_defaults(scope, *arguments, input_data=None):
                nonlocal actual
                if arguments[:2] == ("import", "com.apple.dock"):
                    assert input_data is not None
                    actual = plistlib.loads(input_data)
                return b""

            with patch.object(macos, "live_domains", return_value={"com.apple.dock"}), \
                    patch.object(macos, "export_domain", side_effect=lambda *_: actual), \
                    patch.object(macos, "defaults", side_effect=run_defaults):
                macos.apply_manifest(manifest_path, False, None, [])
            self.assertEqual(actual, {
                "managed": {"enabled": True, "other": 1},
                "unmanaged": 2,
            })

    def test_apply_backup_selectively_restores_previous_keys(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest_path, backup_path = root / "manifest.plist", root / "rollback.plist"
            manifest_path.write_bytes(plistlib.dumps({
                "formatVersion": 1,
                "domains": {"com.apple.dock": {"added": True, "managed": 2}},
            }))
            actual = {"managed": 1, "unmanaged": 3}

            def run_defaults(scope, *arguments, input_data=None):
                nonlocal actual
                if arguments[:2] == ("import", "com.apple.dock"):
                    assert input_data is not None
                    actual = plistlib.loads(input_data)
                return b""

            with patch.object(macos, "live_domains", return_value={"com.apple.dock"}), \
                    patch.object(macos, "export_domain", side_effect=lambda *_: actual), \
                    patch.object(macos, "defaults", side_effect=run_defaults):
                macos.apply_manifest(manifest_path, False, backup_path, [])
                self.assertTrue(actual["added"])
                macos.rollback(backup_path, False, [])

            self.assertEqual(actual, {"managed": 1, "unmanaged": 3})
            saved = plistlib.loads(backup_path.read_bytes())
            self.assertEqual(saved["domains"]["com.apple.dock"], {
                "added": {"present": False},
                "managed": {"present": True, "value": 1},
            })
            self.assertEqual(backup_path.stat().st_mode & 0o777, 0o600)

    def test_apply_restarts_only_named_running_apps_after_preferences_change(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest_path = Path(directory) / "manifest.plist"
            manifest_path.write_bytes(plistlib.dumps({
                "formatVersion": 1,
                "domains": {"com.apple.dock": {"autohide": True}},
            }))
            actual = {"autohide": False}
            events = []

            def run_defaults(scope, *arguments, input_data=None):
                nonlocal actual
                if arguments[:2] == ("import", "com.apple.dock"):
                    events.append("apply")
                    assert input_data is not None
                    actual = plistlib.loads(input_data)
                return b""

            def quit_app(bundle_id):
                events.append(f"quit:{bundle_id}")
                return bundle_id == "running.app"

            with patch.object(macos, "live_domains", return_value={"com.apple.dock"}), \
                    patch.object(macos, "export_domain", side_effect=lambda *_: actual), \
                    patch.object(macos, "defaults", side_effect=run_defaults), \
                    patch.object(macos, "quit_app_if_running", side_effect=quit_app), \
                    patch.object(macos, "open_app", side_effect=lambda app: events.append(f"open:{app}")):
                macos.apply_manifest(manifest_path, False, None,
                                     ["running.app", "stopped.app"])

            self.assertEqual(events, [
                "quit:running.app", "quit:stopped.app", "apply", "open:running.app",
            ])

    def test_apply_reopens_apps_when_a_domain_write_fails(self):
        events = []
        changes = [("com.apple.dock", {"autohide": True}, [("~", ("autohide",))])]
        with patch.object(macos, "quit_app_if_running", return_value=True), \
                patch.object(macos, "defaults", side_effect=RuntimeError("write failed")), \
                patch.object(macos, "open_app", side_effect=lambda app: events.append(app)):
            with self.assertRaisesRegex(RuntimeError, "write failed"):
                macos.update_domains(changes, ["running.app"], "set")
        self.assertEqual(events, ["running.app"])


if __name__ == "__main__":
    unittest.main()

    def test_scrub_snapshot_drops_sensitive_domains_and_keys(self):
        snapshot = {
            "formatVersion": 1,
            "capturedAt": "t",
            "macOSVersion": "27.0.1",
            "macOSBuild": "26A434",
            "user": {
                "com.apple.dock": {"autohide": True, "persistent-apps": []},
                "ai.perplexity.macv3": {"token": "secret", "KeyboardShortcuts_toggleVisor": "x"},
                "com.apple.suggestions": {"UserAccountsPersistedState": ["x", "person@example.com"]},
                "com.apple.cmfsyncagent": {"mail": "a@b.example"},
                "TokenBucketRateLimiter": {"SKDUserDefaultsRoot": {}},
                "io.tailscale.ipn.macsys": {"com.tailscale.cached.profiles": b"data"},
            },
            "currentHost": {
                "-g": {"com.apple.trackpad.scaling": 1.5},
                "com.apple.imservice.SMS": {"Accounts": {"A": {"DisplayName": "+15555550100"}}},
                "com.apple.sharingd": {"StreamID": "abc", "ok": 1},
                "com.apple.AOSKit.RegInfo": {"lastComputerName": "SERIAL"},
                "com.apple.controlcenter": {"Bluetooth": 2, "LastSelectedDisplayUUID": "u", "IRServiceToken": b"t"},
            },
        }
        cleaned = macos.scrub_snapshot(snapshot)
        self.assertEqual(cleaned["user"], {"com.apple.dock": {"autohide": True, "persistent-apps": []}})
        self.assertEqual(
            cleaned["currentHost"],
            {"-g": {"com.apple.trackpad.scaling": 1.5}, "com.apple.controlcenter": {"Bluetooth": 2}},
        )

    def test_scrub_snapshot_redacts_tokens_emails_and_phone_values(self):
        snapshot = {
            "formatVersion": 1, "user": {
                "com.example.app": {
                    "access_token": "eyJaaa.bbb.ccc",
                    "apiKey": "secret",
                    "contact": "person@example.com",
                    "smsLogin": "P:+15555550100",
                    "name": "ok",
                    "count": 3,
                },
            }, "currentHost": {},
        }
        cleaned = macos.scrub_snapshot(snapshot)
        app = cleaned["user"]["com.example.app"]
        self.assertEqual(app["access_token"], macos.REDACTED)
        self.assertEqual(app["apiKey"], macos.REDACTED)
        self.assertNotIn("person@example.com", app["contact"])
        self.assertNotIn("+15555550100", app["smsLogin"])
        self.assertEqual(app["name"], "ok")
        self.assertEqual(app["count"], 3)

    def test_scrub_snapshot_redacts_jwt_in_utf8_blob(self):
        jwt = b'{"token":"eyJ' + b'a' * 20 + b'.' + b'b' * 20 + b'.' + b'c' * 20 + b'"}'
        snapshot = {"formatVersion": 1, "user": {"com.example.app": {"payload": jwt}}, "currentHost": {}}
        cleaned = macos.scrub_snapshot(snapshot)
        self.assertNotIn(b"eyJ", cleaned["user"]["com.example.app"]["payload"])
        self.assertIn(macos.REDACTED.encode(), cleaned["user"]["com.example.app"]["payload"])

    def test_snapshot_command_writes_scrubbed_output(self):
        class Result:
            def __init__(self, text):
                self.stdout = text.encode()
                self.returncode = 0

        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / "snap.plist"
            with patch.object(macos.subprocess, "run", side_effect=[Result("27.0.1\n"), Result("26A434\n")]), \
                    patch.object(macos, "capture_scope", side_effect=[
                        {"ai.perplexity.macv3": {"token": "x"}, "com.apple.dock": {"autohide": True}},
                        {"com.apple.imservice.SMS": {"Accounts": {"A": {"DisplayName": "+15555550100"}}}},
                    ]):
                self.assertEqual(macos.main(["snapshot", str(out)]), 0)
            saved = plistlib.loads(out.read_bytes())
            self.assertEqual(saved["user"], {"com.apple.dock": {"autohide": True}})
            self.assertEqual(saved["currentHost"], {})

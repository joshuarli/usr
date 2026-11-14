"""Kache install/ownership/uninstall round-trip, with no real toolchain or downloads."""

from pathlib import Path
import hashlib
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import main
from ownership import records, read_manifest
from uninstall import uninstall


class KacheTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        self.home = self.root / "home"
        self.home.mkdir()
        self.binary = self.home / ".cargo/bin/kache"
        rustup = self.home / ".cargo/bin/rustup"
        rustup.parent.mkdir(parents=True)
        rustup.write_text("#!/bin/sh\nexit 0\n")
        rustup.chmod(0o755)
        self.ctx = main.Context(self.root, self.home, "linux", "desktop", {"HOME": str(self.home)})
        self.called = []
        self.write_on_install = True
        self.installs = 0
        self.patcher = patch.object(main, "command", side_effect=self.command)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def command(self, _ctx, *args, **kwargs):
        self.called.append(args)
        if args and str(args[-1]).endswith("setup-kache") and self.write_on_install:
            self.installs += 1
            self.binary.write_text("#!/bin/sh\necho kache 1.0.0\n")
            self.binary.chmod(0o755)
            engine = self.binary.parent / "kache-engine"
            engine.write_text("#!/bin/sh\n")
            engine.chmod(0o755)
            self.write_record(self.binary, engine)
        if args and args[-2:] == ("uninstall", "--purge"):
            self.binary.unlink()
        return type("Completed", (), {"returncode": 0})()

    def write_record(self, *binaries, tag="release-" + "a" * 40):
        lines = [tag] + [f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}" for path in binaries]
        (self.binary.parent / ".kache-release").write_text("".join(line + "\n" for line in lines))

    def test_sync_reinstalls_when_the_release_record_does_not_vouch_for_the_binaries(self):
        main.kache_apply(self.ctx)
        self.assertEqual(main.kache_status(self.ctx).detail, "kache installed")
        record = self.binary.parent / ".kache-release"
        record.write_text("release-" + "a" * 40 + "\n")
        status = main.kache_status(self.ctx)
        self.assertFalse(status.current)
        self.assertEqual(status.detail, "kache release record lists no digest for kache")
        main.kache_apply(self.ctx)
        self.assertEqual(self.installs, 2)
        self.assertTrue(main.kache_status(self.ctx).current)
        (self.binary.parent / "kache-engine").write_text("replaced")
        self.assertEqual(main.kache_status(self.ctx).detail, "kache-engine does not match the kache release record")

    def test_managed_install_uninstall_round_trip(self):
        main.kache_apply(self.ctx)
        self.assertIn(("K", self.binary), records(self.ctx.state))
        proof = read_manifest(self.ctx.state)[str(self.binary)]
        self.assertEqual(proof["kind"], "K")
        self.assertTrue(main.kache_status(self.ctx).current)
        uninstall(self.ctx)
        self.assertFalse(self.binary.exists())
        self.assertTrue(any(args[-2:] == ("uninstall", "--purge") for args in self.called))
        self.assertFalse(self.ctx.state.exists())

    def test_foreign_existing_install_not_adopted(self):
        self.binary.write_text("foreign")
        self.binary.chmod(0o755)
        status = main.kache_status(self.ctx)
        self.assertTrue(status.current)
        self.assertEqual(status.detail, "kache installed outside sync; left unmanaged")
        with self.assertRaisesRegex(RuntimeError, "pre-existing"):
            main.kache_apply(self.ctx)
        self.assertFalse(self.ctx.state.exists())
        self.assertEqual(self.called, [])

    def test_modified_managed_binary_blocks_uninstall(self):
        main.kache_apply(self.ctx)
        self.binary.write_text("user-modified")
        with self.assertRaisesRegex(RuntimeError, "unverified or modified"):
            uninstall(self.ctx)
        self.assertEqual(self.binary.read_text(), "user-modified")
        self.assertFalse(any(args[-2:] == ("uninstall", "--purge") for args in self.called))

    def test_legacy_path_only_record_refused(self):
        self.binary.write_text("#!/bin/sh\necho kache 1.0.0\n")
        self.binary.chmod(0o755)
        self.ctx.state.parent.mkdir(parents=True)
        self.ctx.state.write_text(f"K\t{self.binary}\n")
        with self.assertRaisesRegex(RuntimeError, "unverified or modified"):
            uninstall(self.ctx)
        self.assertTrue(self.binary.exists())

    def test_setup_without_result_executable_is_not_claimed(self):
        self.write_on_install = False
        with self.assertRaisesRegex(RuntimeError, "regular executable"):
            main.kache_apply(self.ctx)
        self.assertNotIn(("K", self.binary), records(self.ctx.state))

    def test_existing_owned_binary_can_be_reconfigured(self):
        main.kache_apply(self.ctx)
        main.kache_apply(self.ctx)
        self.assertEqual(sum(k == "K" for k, _ in records(self.ctx.state)), 1)
        self.assertIn(str(self.binary), read_manifest(self.ctx.state))


if __name__ == "__main__":
    unittest.main()

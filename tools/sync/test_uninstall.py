"""Regression tests: uninstaller must not delete unverified or user-replaced objects."""
import tempfile
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import main
from ownership import capture_new, records
from uninstall import uninstall


class UninstallTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.home = self.root / "home"
        self.home.mkdir()
        self.ctx = main.Context(self.root, self.home, "linux", "desktop", {"HOME": str(self.home)})
        self.ctx.state.parent.mkdir(parents=True)
        self.called = []
        self.patcher = patch.object(main, "command", side_effect=self.command)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def command(self, *args, **kwargs):
        self.called.append(args)
        return type("Completed", (), {"returncode": 0})()

    def record(self, kind, path):
        with self.ctx.state.open("a") as file:
            file.write(f"{kind}\t{path}\n")

    def test_verified_directory_and_file_removed(self):
        directory = self.home / "app"
        directory.mkdir()
        entry = directory / "entry"
        entry.write_text("installed binary")
        self.record("D", directory)
        self.record("F", entry)
        capture_new(self.ctx.state, set())
        uninstall(self.ctx)
        self.assertFalse(directory.exists())
        self.assertFalse(self.ctx.state.exists())

    def test_modified_file_preserves_everything_including_mcp(self):
        file = self.home / "binary"
        file.write_text("original")
        self.record("F", file)
        capture_new(self.ctx.state, set())
        file.write_text("user replacement")
        with self.assertRaisesRegex(RuntimeError, "unverified or modified"):
            uninstall(self.ctx)
        self.assertEqual(file.read_text(), "user replacement")
        self.assertEqual(self.called, [])

    def test_modified_directory_preserves_all_contents(self):
        directory = self.home / "app"
        directory.mkdir()
        (directory / "file").write_text("original")
        self.record("D", directory)
        capture_new(self.ctx.state, set())
        (directory / "file").write_text("custom")
        with self.assertRaisesRegex(RuntimeError, "unverified or modified"):
            uninstall(self.ctx)
        self.assertEqual((directory / "file").read_text(), "custom")

    def test_unverified_legacy_entry_is_preserved(self):
        file = self.home / "binary"
        file.write_text("owned?")
        self.record("F", file)
        with self.assertRaisesRegex(RuntimeError, "unverified or modified"):
            uninstall(self.ctx)
        self.assertEqual(file.read_text(), "owned?")

    def test_changed_symlink_destination_is_preserved(self):
        first = self.home / "one"
        second = self.home / "two"
        first.write_text("one")
        second.write_text("two")
        link = self.home / "link"
        link.symlink_to(first)
        self.record("F", link)
        capture_new(self.ctx.state, set())
        link.unlink()
        link.symlink_to(second)
        with self.assertRaisesRegex(RuntimeError, "unverified or modified"):
            uninstall(self.ctx)
        self.assertEqual(link.resolve(), second)

    def test_old_path_only_records_never_become_verified(self):
        file = self.home / "binary"
        file.write_text("old")
        self.record("F", file)
        capture_new(self.ctx.state, records(self.ctx.state))
        self.assertFalse(Path(str(self.ctx.state) + ".verified.json").exists())


if __name__ == "__main__":
    unittest.main()

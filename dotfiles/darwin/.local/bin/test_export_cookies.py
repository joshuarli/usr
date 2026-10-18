import importlib.util
import os
import runpy
import sqlite3
import stat
import struct
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).with_name("export-cookies.py")
SPEC = importlib.util.spec_from_file_location("export_cookies", SCRIPT)
export_cookies = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(export_cookies)


class QueryChromeTests(unittest.TestCase):
    def test_query_chrome_includes_each_requested_hostname_and_subdomains(self):
        with tempfile.NamedTemporaryFile(suffix=".sqlite") as db_file:
            con = sqlite3.connect(db_file.name)
            con.execute(
                """CREATE TABLE cookies (
                    host_key TEXT, path TEXT, is_secure INTEGER,
                    expires_utc INTEGER, name TEXT, value TEXT,
                    encrypted_value BLOB
                )"""
            )
            con.executemany(
                "INSERT INTO cookies VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    ("example.com", "/", 0, 0, "root", "1", b""),
                    ("accounts.example.com", "/", 1, 0, "session", "2", b""),
                    ("other.test", "/", 0, 0, "ignored", "3", b""),
                ],
            )
            con.commit()
            con.close()

            rows = export_cookies.query_chrome(
                db_file.name, ["example.com", "other.test"]
            )

        self.assertEqual(
            [(row[0], row[5], row[6]) for row in rows],
            [
                ("accounts.example.com", "session", "2"),
                ("example.com", "root", "1"),
                ("other.test", "ignored", "3"),
            ],
        )

    def test_decrypt_chrome_v10_value(self):
        key = bytes.fromhex("01ab06dc67d036480129f3e40d53ca5f")
        encrypted = bytes.fromhex("763130a37209202f9ea312c661d1c320927fa7")
        self.assertEqual(
            export_cookies.decrypt_chrome_value(encrypted, key), "secret-cookie"
        )

    def test_decrypt_chrome_v10_value_strips_current_host_hash(self):
        key = bytes.fromhex("01ab06dc67d036480129f3e40d53ca5f")
        host = "newsletter.semianalysis.com"
        # This ciphertext was generated with the same Chromium v10 AES-CBC
        # recipe as the fixture above, including the current host hash.
        encrypted = bytes.fromhex(
            "7631308eb6fe0ae800d240902bed23fba515b8a79cf665177d6a78fe2cc6f98f3c8e36513a95e19725b81b44a0601b8dc67224"
        )
        self.assertEqual(
            export_cookies.decrypt_chrome_value(encrypted, key, host), "secret-cookie"
        )


class HostMatchesTests(unittest.TestCase):
    def test_host_matches_does_not_match_a_suffix_without_a_label_boundary(self):
        self.assertTrue(export_cookies.host_matches(".accounts.example.com", "example.com"))
        self.assertFalse(export_cookies.host_matches("notexample.com", "example.com"))


class ExportFileTests(unittest.TestCase):
    def export(self, directory):
        strings = [b"example.com\0", b"session\0", b"/\0", b"secret\0"]
        offsets = []
        size = 48
        for value in strings:
            offsets.append(size)
            size += len(value)
        record = struct.pack("<IIIIiiiidd", size, 0, 0, 0, *offsets, 0, 0)
        page = struct.pack("<III", 0, 1, 12) + record + b"".join(strings)
        source = directory / "Cookies.binarycookies"
        source.write_bytes(b"cook" + struct.pack(">II", 1, len(page)) + page)
        previous_directory = Path.cwd()
        previous_umask = os.umask(0o022)
        try:
            os.chdir(directory)
            with patch.object(sys, "argv", [str(SCRIPT), "safari", "example.com"]):
                with patch("os.path.expanduser", return_value=str(source)):
                    runpy.run_path(str(SCRIPT), run_name="__main__")
        finally:
            os.chdir(previous_directory)
            os.umask(previous_umask)

    def test_export_creates_private_file_under_permissive_umask(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            self.export(directory)
            output = directory / "cookies-example.com.txt"
            self.assertEqual(stat.S_IMODE(output.stat().st_mode), 0o600)
            self.assertEqual(
                output.read_text(),
                "# Netscape HTTP Cookie File\n"
                "example.com\tTRUE\t/\tFALSE\t0\tsession\tsecret\n",
            )

    def test_export_restricts_existing_file_permissions(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            output = directory / "cookies-example.com.txt"
            output.write_text("old contents that must be removed" * 10)
            output.chmod(0o644)
            self.export(directory)
            self.assertEqual(stat.S_IMODE(output.stat().st_mode), 0o600)
            self.assertEqual(
                output.read_text(),
                "# Netscape HTTP Cookie File\n"
                "example.com\tTRUE\t/\tFALSE\t0\tsession\tsecret\n",
            )

    def test_export_refuses_symlink_targets(self):
        for existing in (True, False):
            with self.subTest(existing=existing):
                with tempfile.TemporaryDirectory() as temporary:
                    directory = Path(temporary)
                    target = directory / "target.txt"
                    if existing:
                        target.write_text("keep this")
                    output = directory / "cookies-example.com.txt"
                    output.symlink_to(target)
                    with self.assertRaises(OSError):
                        self.export(directory)
                    self.assertTrue(output.is_symlink())
                    if existing:
                        self.assertEqual(target.read_text(), "keep this")
                    else:
                        self.assertFalse(target.exists())


if __name__ == "__main__":
    unittest.main()

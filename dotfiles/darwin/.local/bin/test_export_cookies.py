import importlib.util
import sqlite3
import tempfile
import unittest
from pathlib import Path


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


if __name__ == "__main__":
    unittest.main()

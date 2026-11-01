#!/usr/bin/env python3
"""age adapter: two-recipient round trips, typed failures, and bounded output."""
import hashlib
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[3]
WORK_TMP = ROOT / ".work" / "tmp"
WORK_TMP.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(ROOT / "tools" / "agent-memory" / "src"))

from agent_memory import mirror_crypto as crypto  # noqa: E402

DEV_AGE = ROOT / "tools" / "agent-memory" / "cloudflare" / "dev-age.sh"


def ensure_binary():
    try:
        return crypto.binary()
    except crypto.CryptoError:
        result = subprocess.run(["sh", str(DEV_AGE)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode != 0:
            raise AssertionError("cannot build rage: " + result.stderr.strip()) from None
        os.environ["AGE_BIN"] = result.stdout.strip()
        return crypto.binary()


class MirrorCryptoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ensure_binary()

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=str(WORK_TMP))
        self.root = Path(self.temporary.name)
        self.plaintext = b"synthetic transcript bytes\n" * 64

    def tearDown(self):
        self.temporary.cleanup()

    def identities(self, *names):
        return [crypto.keygen(self.root / (name + ".key")) for name in names]

    def encrypt(self, recipients, name="object.age"):
        source = self.root / "plaintext.bin"
        source.write_bytes(self.plaintext)
        return crypto.encrypt_file(source, self.root / name, recipients)

    def test_round_trip_to_two_recipients(self):
        collector, recovery = self.identities("collector", "recovery")
        result = self.encrypt([collector, recovery])
        ciphertext = self.root / "object.age"
        body = ciphertext.read_bytes()
        self.assertEqual(result["ciphertext_sha256"], hashlib.sha256(body).hexdigest())
        self.assertEqual(result["ciphertext_size"], len(body))
        self.assertNotEqual(body, self.plaintext)
        second = self.encrypt([collector, recovery], "second.age")
        second_body = (self.root / "second.age").read_bytes()
        self.assertNotEqual(body, second_body)
        self.assertEqual(second["ciphertext_sha256"], hashlib.sha256(second_body).hexdigest())
        self.assertEqual(second["ciphertext_size"], len(second_body))
        for name, identity in (("collector", self.root / "collector.key"), ("recovery", self.root / "recovery.key")):
            output = self.root / (name + ".out")
            crypto.decrypt_file(ciphertext, output, identity)
            self.assertEqual(output.read_bytes(), self.plaintext)
            self.assertEqual(output.stat().st_mode & 0o777, 0o600)
        self.assertEqual(list(self.root.glob("*.age-*")), [])

    def test_wrong_identity_fails_and_writes_nothing(self):
        collector, recovery, wrong = self.identities("collector", "recovery", "wrong")
        self.encrypt([collector, recovery])
        output = self.root / "wrong.out"
        with self.assertRaises(crypto.CryptoError) as raised:
            crypto.decrypt_file(self.root / "object.age", output, self.root / "wrong.key")
        self.assertIn("no matching keys", str(raised.exception).lower())
        self.assertEqual(list(self.root.glob("wrong.out*")), [])

    def test_missing_binary_reports_the_install_hint(self):
        empty = self.root / "empty"
        empty.mkdir()
        with mock.patch.dict(os.environ, {"PATH": str(empty)}, clear=False):
            os.environ.pop("AGE_BIN", None)
            with self.assertRaises(crypto.CryptoError) as raised:
                crypto.binary()
        self.assertIn("AGE_BIN", str(raised.exception))
        self.assertIn("brew install age", str(raised.exception))
        with mock.patch.dict(os.environ, {"AGE_BIN": str(self.root / "missing")}, clear=False):
            with self.assertRaises(crypto.CryptoError) as raised:
                crypto.binary()
        self.assertIn("AGE_BIN", str(raised.exception))

    def test_keygen_refuses_to_replace_an_identity(self):
        path = self.root / "collector.key"
        crypto.keygen(path)
        with self.assertRaises(crypto.CryptoError):
            crypto.keygen(path)

    def test_decryption_refuses_a_public_identity_or_existing_output(self):
        collector, recovery = self.identities("collector", "recovery")
        self.encrypt([collector, recovery])
        public = self.root / "public.key"
        public.write_bytes((self.root / "collector.key").read_bytes())
        os.chmod(public, 0o644)
        with self.assertRaises(crypto.CryptoError) as raised:
            crypto.decrypt_file(self.root / "object.age", self.root / "public.out", public)
        self.assertIn("0600", str(raised.exception))
        existing = self.root / "existing.out"
        existing.write_text("keep")
        with self.assertRaises(crypto.CryptoError):
            crypto.decrypt_file(self.root / "object.age", existing, self.root / "collector.key")
        self.assertEqual(existing.read_text(), "keep")

    def test_recipient_list_is_validated(self):
        with self.assertRaises(crypto.CryptoError):
            self.encrypt([])
        with self.assertRaises(crypto.CryptoError):
            self.encrypt(["-r"])


if __name__ == "__main__":
    unittest.main()

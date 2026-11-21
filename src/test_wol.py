#!/usr/bin/env python3
"""Exercise the wol CLI's file input against loopback."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

WOL = Path(__file__).resolve().parent / "wol.py"


class FileInputTests(unittest.TestCase):
    def test_file_accepts_compact_dotted_and_separated_addresses(self):
        with tempfile.TemporaryDirectory() as directory:
            macs = Path(directory) / "macs.txt"
            macs.write_text("001122334455\n0011.2233.4466\n\n00:11:22:33:44:77\n00-11-22-33-44-88\n")
            result = subprocess.run([sys.executable, "-I", str(WOL), "-f", str(macs), "127.0.0.1"],
                                    capture_output=True, text=True, timeout=10, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        sent = [line.split()[-1].rstrip(".") for line in result.stdout.splitlines() if line.startswith("Magic packet sent")]
        self.assertEqual(sent, ["00:11:22:33:44:55", "00:11:22:33:44:66", "00:11:22:33:44:77", "00:11:22:33:44:88"])


if __name__ == "__main__":
    unittest.main()

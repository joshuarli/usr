#!/usr/bin/env python3

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class MakeSyncTests(unittest.TestCase):
    def test_macos_sync_does_not_apply_dns_configuration(self):
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
        self.assertIn("sh macos/setup-macos brew packages", makefile)
        self.assertNotIn("sh macos/setup-macos brew packages dns", makefile)


if __name__ == "__main__":
    unittest.main()

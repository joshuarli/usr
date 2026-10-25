#!/usr/bin/env python3

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class MakeSyncTests(unittest.TestCase):
    def test_macos_sync_does_not_apply_dns_configuration(self):
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
        self.assertIn("sh macos/setup-macos brew packages", makefile)
        self.assertNotIn("sh macos/setup-macos brew packages dns", makefile)

    def test_dns_remains_an_explicit_setup_step(self):
        setup = (ROOT / "macos/setup-macos").read_text(encoding="utf-8")
        self.assertIn("dns)        step_dns ;;", setup)


if __name__ == "__main__":
    unittest.main()

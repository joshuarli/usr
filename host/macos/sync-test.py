#!/usr/bin/env python3

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class SyncTests(unittest.TestCase):
    def test_macos_sync_does_not_apply_dns_configuration(self):
        sync = (ROOT / "sync").read_text(encoding="utf-8")
        self.assertIn('sh "$root/host/macos/setup-macos" brew packages', sync)
        self.assertNotIn("brew packages dns", sync)

    def test_dns_remains_an_explicit_setup_step(self):
        setup = (ROOT / "host/macos/setup-macos").read_text(encoding="utf-8")
        self.assertIn("dns)        step_dns ;;", setup)


if __name__ == "__main__":
    unittest.main()

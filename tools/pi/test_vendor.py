#!/usr/bin/env python3
"""Offline Pi vendor provenance tests."""
from __future__ import annotations
import importlib.util
import unittest
from pathlib import Path

MODULE = Path(__file__).with_name("vendor.py")
spec = importlib.util.spec_from_file_location("pi_vendor", MODULE)
vendor = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(vendor)


class VendorTests(unittest.TestCase):
    def test_git_blob_hash(self):
        self.assertEqual(vendor.git_blob_sha(b"hello\n"),
                         "ce013625030ba8dba906f756967f9e9ca394464a")

    def test_complete_manifest(self):
        data = vendor.load()
        self.assertEqual(set(data["sources"]), vendor.SUPPORTED)
        vendor.check(data)

    def test_sdk_and_extension_pins_match_built_runtime(self):
        data = vendor.load()
        runtime = __import__("json").loads(
            (vendor.ROOT / "vendor/pi/runtime/artifacts.json").read_text())
        bridge = __import__("json").loads(
            (vendor.ROOT / "tools/pi-subagent-bridge/package.json").read_text())
        self.assertEqual(data["tracked_only"]["pi-sdk"]["version"],
                         runtime["pi_version"])
        self.assertEqual(bridge["dependencies"]["@earendil-works/pi-coding-agent"],
                         runtime["pi_version"])
        for name in ("pi-subagents", "pi-muse-subscription"):
            self.assertEqual(bridge["dependencies"][name],
                             data["sources"][name]["version"])
        self.assertTrue(set(("linux-x64", "linux-arm64", "darwin-arm64")) <=
                        set(runtime["artifacts"]))
        for target, item in runtime["artifacts"].items():
            self.assertRegex(item["sha256"], r"^[0-9a-f]{64}$")
            self.assertEqual(item["path"], target + ".tar.gz")

    def test_selection(self):
        self.assertTrue(vendor.SUBAGENTS.search("src/api/preflight.ts"))
        self.assertTrue(vendor.OTHER.search("broker/access-registry.ts"))
        self.assertTrue(vendor.EXCLUDE.search("src/foo.test.ts"))
        self.assertTrue(vendor.EXCLUDE.search("test/unit/foo.ts"))


if __name__ == "__main__":
    unittest.main()

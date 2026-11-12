#!/usr/bin/env python3
"""Exercise staged release acquisition against a local HTTP server."""
import functools
import hashlib
import http.server
import io
import json
import subprocess
from pathlib import Path
import sys
import tarfile
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "sync"))
import pi_offline
import pi_release


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.assets = self.root / "assets"
        self.assets.mkdir()
        self.requests = []
        requests = self.requests

        class Handler(http.server.SimpleHTTPRequestHandler):
            def log_message(self, format, *args):
                pass

            def do_GET(self):
                requests.append(self.path)
                super().do_GET()

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Handler, directory=str(self.assets)))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop_server)
        self.prefix = self.root / "home/runtime"
        self.cache = self.root / "cache"
        self.pin = self.publish()

    def stop_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def publish(self, extra=None, version="one") -> pi_release.Pin:
        name = "darwin-arm64-full.tar.gz"
        with tarfile.open(self.assets / name, "w:gz") as archive:
            files = {f"node_modules/{name}/package.json": json.dumps({"version": value}).encode()
                     for name, value in pi_offline.PACKAGES.items()}
            files["node_modules/@earendil-works/pi-coding-agent/dist/bundle/cli.js"] = version.encode()
            if extra:
                files.update(extra)
            for path, content in files.items():
                member = tarfile.TarInfo(path)
                if isinstance(content, tuple):
                    member.type = tarfile.SYMTYPE
                    member.linkname = content[0]
                    archive.addfile(member)
                else:
                    member.size = len(content)
                    archive.addfile(member, io.BytesIO(content))
        data = (self.assets / name).read_bytes()
        entry: pi_release.Artifact = {"archive": name, "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
        provenance = {"schema": 1, "builder_revision": "a" * 40,
                      "targets": {"darwin-arm64": {"target": "darwin-arm64", "profile": "full", **entry}}}
        raw = json.dumps(provenance).encode()
        (self.assets / "provenance.json").write_bytes(raw)
        (self.assets / "SHA256SUMS").write_text(f"{entry['sha256']}  {name}\n")
        return {"schema": 1, "release_url": f"http://127.0.0.1:{self.server.server_port}",
                "builder_revision": "a" * 40, "profile": "full",
                "provenance_sha256": hashlib.sha256(raw).hexdigest(), "targets": {"darwin-arm64": entry}}

    def install(self, pin=None):
        return pi_release.install(self.prefix, pin or self.pin, "darwin-arm64", self.cache)

    def test_install_noop_without_fetch_and_verified_cache_reuse(self):
        runtime = self.install()
        self.assertTrue((runtime / "bin/pi").is_file())
        count = len(self.requests)
        self.assertEqual(self.install(), runtime)
        self.assertEqual(len(self.requests), count)
        other = pi_release.install(self.root / "other", self.pin, "darwin-arm64", self.cache)
        self.assertTrue((other / "bin/pi").is_file())
        self.assertEqual(len(self.requests), count)

    def test_missing_asset_retry(self):
        archive = self.assets / "darwin-arm64-full.tar.gz"
        raw = archive.read_bytes()
        archive.unlink()
        with self.assertRaises(OSError):
            self.install()
        self.assertFalse((self.prefix / "current").exists())
        archive.write_bytes(raw)
        self.install()

    def test_truncated_wrong_hash_and_size_preserve_prior_and_retry(self):
        previous = self.install()
        old = self.pin
        new = self.publish(version="two")
        archive = self.assets / "darwin-arm64-full.tar.gz"
        raw = archive.read_bytes()
        for broken in [raw[:30], bytes([raw[0] ^ 1]) + raw[1:], raw + b"extra"]:
            archive.write_bytes(broken)
            with self.assertRaises(ValueError):
                self.install(new)
            self.assertEqual(pi_release.current(self.prefix, old, "darwin-arm64"), previous)
        archive.write_bytes(raw)
        replacement = self.install(new)
        self.assertNotEqual(previous, replacement)
        self.assertEqual(self.install(old), previous)
        self.assertEqual(pi_release.current(self.prefix, old, "darwin-arm64"), previous)

    def test_foreign_prefix_and_credentials_preserved(self):
        self.prefix.mkdir(parents=True)
        sentinel = self.prefix / "credentials.json"
        sentinel.write_text("private")
        with self.assertRaisesRegex(ValueError, "foreign"):
            self.install()
        self.assertEqual(sentinel.read_text(), "private")
        self.assertEqual(self.requests, [])

    def test_foreign_symlink_in_release_prefix_is_preserved(self):
        self.prefix.mkdir(parents=True)
        sentinel = self.root / "valuable"
        sentinel.mkdir()
        (sentinel / "keep").write_text("keep")
        (self.prefix / ".usr-pi-releases").touch()
        (self.prefix / "releases").symlink_to(sentinel)
        with self.assertRaisesRegex(ValueError, "foreign symlink"):
            self.install()
        self.assertEqual((sentinel / "keep").read_text(), "keep")
        self.assertEqual(self.requests, [])

    def test_legacy_runtime_is_preserved_until_explicit_migration(self):
        self.prefix.mkdir(parents=True)
        (self.prefix / pi_offline.STAMP).write_text('{"schema":1}')
        with self.assertRaisesRegex(ValueError, "foreign"):
            self.install()
        self.assertTrue((self.prefix / pi_offline.STAMP).exists())

    def test_unsafe_paths_and_chained_links(self):
        for extra in [{"../escape": b"bad"}, {"/absolute": b"bad"},
                      {"node_modules/a": ("../../escape",)},
                      {"node_modules/a": ("b",), "node_modules/b": ("c",), "node_modules/c": b"bad"},
                      {"node_modules/a": ("b",), "node_modules/a/child": b"bad", "node_modules/b": b"bad"}]:
            pin = self.publish(extra)
            with self.assertRaisesRegex(ValueError, "unsafe|link"):
                self.install(pin)
            self.assertFalse((self.prefix / "current").exists())
        self.assertFalse((self.root / "escape").exists())

    def test_bad_provenance_and_sums(self):
        for name in ["provenance.json", "SHA256SUMS"]:
            pin = self.publish()
            (self.assets / name).write_text("invalid")
            with self.assertRaises(ValueError):
                self.install(pin)
            self.assertFalse((self.prefix / "current").exists())

    def test_concurrent_installers_admit_one_download(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: self.install(), range(2)))
        self.assertEqual(results[0], results[1])
        self.assertEqual(self.requests.count("/darwin-arm64-full.tar.gz"), 1)

    def test_interrupted_acquisition_retry(self):
        original = pi_release.fetch
        def interrupted(url, path, limit):
            if url.endswith(".tar.gz"):
                path.write_bytes(b"partial")
                raise OSError("interrupted")
            original(url, path, limit)
        with patch.object(pi_release, "fetch", interrupted):
            with self.assertRaisesRegex(OSError, "interrupted"):
                self.install()
        self.assertEqual(list(self.cache.glob(".download-*")), [])
        self.install()

    def test_switch_failure_preserves_previous_and_retry_reuses_generation(self):
        previous = self.install()
        new = self.publish(version="two")
        replace = pi_release.os.replace
        def fail_selection(source, destination):
            if destination == self.prefix / "current":
                raise OSError("selection failed")
            return replace(source, destination)
        with patch.object(pi_release.os, "replace", fail_selection):
            with self.assertRaisesRegex(OSError, "selection failed"):
                self.install(new)
        self.assertEqual(pi_release.current(self.prefix, self.pin, "darwin-arm64"), previous)
        count = len(self.requests)
        self.install(new)
        self.assertEqual(len(self.requests), count)

    def test_process_crash_after_generation_publication_is_retryable(self):
        previous = self.install()
        new = self.publish(version="two")
        pin_file = self.root / "pin.json"
        pin_file.write_text(json.dumps(new))
        code = """
import json, os, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import pi_release
replace = os.replace
def crash(source, destination):
    replace(source, destination)
    if Path(destination).parent.name == 'releases':
        os._exit(87)
os.replace = crash
pi_release.install(Path(sys.argv[2]), json.loads(Path(sys.argv[3]).read_text()), 'darwin-arm64', Path(sys.argv[4]))
"""
        result = subprocess.run([sys.executable, "-I", "-c", code,
                                 str(Path(pi_release.__file__).parent), str(self.prefix),
                                 str(pin_file), str(self.cache)], timeout=15, check=False)
        self.assertEqual(result.returncode, 87)
        self.assertEqual(pi_release.current(self.prefix, self.pin, "darwin-arm64"), previous)
        self.install(new)

    def test_pin_validation_never_resolves_latest(self):
        pins: list[pi_release.Pin] = [
            {**self.pin, "builder_revision": ""},
            {**self.pin, "profile": "unknown"},
            {**self.pin, "provenance_sha256": ""},
            {**self.pin, "release_url": "http://example.com/latest"},
        ]
        for pin in pins:
            with self.assertRaisesRegex(ValueError, "pin"):
                self.install(pin)
        self.assertEqual(self.requests, [])


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""setup-kache records verified binary digests and reinstalls when they no longer match."""

import hashlib
import io
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "base/.local/bin/setup-kache"
TAG = "release-" + "a" * 40

FAKE_KACHE = """#!/bin/sh
case "$1" in
    --version) echo "kache 9.9.9" ;;
    doctor) echo '{"issues": 0}' ;;
esac
"""
FAKE_CURL = """#!/bin/sh
out=
while [ $# -gt 0 ]; do
    case "$1" in
        -o) out=$2; shift 2 ;;
        -*) shift ;;
        *) url=$1; shift ;;
    esac
done
echo "$url" >> "$FIXTURE/requests"
case "$url" in
    */releases.atom) cat "$FIXTURE/releases.atom" ;;
    *) cp "$FIXTURE/assets/${url##*/}" "$out" ;;
esac
"""
FAKE_RUSTUP = """#!/bin/sh
case "$1" in
    toolchain) echo "nightly-2026-09-15-host" ;;
    run) shift 2; exec "$@" ;;
esac
"""
FAKE_UNAME = """#!/bin/sh
case "$1" in
    -s) echo Linux ;;
    -m) echo x86_64 ;;
esac
"""
FAKE_CARGO = """#!/bin/sh
if [ "$1" = build ]; then
    mkdir -p target/debug
    printf '#!/bin/sh\\n' > target/debug/kache_probe
    chmod +x target/debug/kache_probe
fi
"""


# A Linux uname keeps setup-kache off its macOS Homebrew rustup lookup, which uses fixed paths.
TRIPLE = "x86_64-unknown-linux-musl-static"


class SetupKacheRecord(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="setup-kache-test-")
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.home = root / "home"
        self.fixture = root / "fixture"
        fakes = root / "bin"
        for directory in (self.home, self.fixture / "assets", fakes):
            directory.mkdir(parents=True)
        for name, body in (("curl", FAKE_CURL), ("rustup", FAKE_RUSTUP), ("cargo", FAKE_CARGO), ("uname", FAKE_UNAME), ("rustc", "#!/bin/sh\necho 'host: x86_64-unknown-linux-musl'\n")):
            (fakes / name).write_text(body, encoding="utf-8")
            (fakes / name).chmod(0o755)
        sums = []
        for name in ("kache", "kache-engine"):
            member = f"{name}-{TRIPLE}"
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, "w") as archive:
                info = zipfile.ZipInfo(member)
                info.external_attr = 0o755 << 16
                archive.writestr(info, FAKE_KACHE + f"# {name}\n")
            (self.fixture / "assets" / f"{member}.zip").write_bytes(buffer.getvalue())
            sums.append(f"{hashlib.sha256(buffer.getvalue()).hexdigest()}  {member}.zip\n")
        (self.fixture / "assets/SHA256SUMS").write_text("".join(sums), encoding="utf-8")
        self.env = {
            "HOME": str(self.home),
            "PATH": f"{self.home / '.cargo/bin'}:{fakes}:/usr/bin:/bin",
            "TMPDIR": str(root),
            "FIXTURE": str(self.fixture),
        }
        self.cargo_bin = self.home / ".cargo/bin"

    def setup_kache(self):
        (self.fixture / "requests").unlink(missing_ok=True)
        result = subprocess.run(["sh", str(SCRIPT), "--version", TAG], env=self.env, stdin=subprocess.DEVNULL,
                                capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        requests = self.fixture / "requests"
        return requests.read_text(encoding="utf-8").split() if requests.exists() else []

    def expected_record(self):
        return "".join([f"{TAG}\n"] + [
            f"{hashlib.sha256((self.cargo_bin / name).read_bytes()).hexdigest()}  {name}\n"
            for name in ("kache", "kache-engine")
        ])

    def test_record_lists_installed_digests_and_detects_replacement(self):
        self.assertTrue(any(url.endswith(".zip") for url in self.setup_kache()))
        record = self.cargo_bin / ".kache-release"
        self.assertEqual(record.read_text(encoding="utf-8"), self.expected_record())

        self.assertFalse(any(url.endswith(".zip") for url in self.setup_kache()))

        (self.cargo_bin / "kache").write_text(FAKE_KACHE + "# replaced\n", encoding="utf-8")
        self.assertTrue(any(url.endswith(".zip") for url in self.setup_kache()))
        self.assertIn("# kache\n", (self.cargo_bin / "kache").read_text(encoding="utf-8"))
        self.assertEqual(record.read_text(encoding="utf-8"), self.expected_record())


if __name__ == "__main__":
    unittest.main()

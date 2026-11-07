"""Shared ffmpeg runtime: archive validation, versioned installs, and pins, with synthetic archives."""
import hashlib
import io
import json
import os
from pathlib import Path
import struct
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))
import ffmpeg_runtime
from ffmpeg_runtime import RuntimeArchiveError
from installer import SkipInstall
from test_installer import FakeInstaller, atom

MAJORS = {"libavcodec": 63, "libavfilter": 12, "libavformat": 63, "libavutil": 61,
          "libswresample": 7, "libswscale": 10}
WORKING = b"#!/bin/sh\nexit 0\n"
TRIPLES = {"linux": "x86_64-unknown-linux-musl", "darwin": "aarch64-apple-darwin"}
REPO = "https://github.com/laputa-systems/ffmpeg-build"


def elf_library(soname: str) -> bytes:
    strtab = b"\0" + soname.encode() + b"\0"
    dynamic_offset = 64 + 2 * 56
    strtab_offset = dynamic_offset + 48
    total = strtab_offset + len(strtab)
    header = b"\x7fELF" + bytes([2, 1, 1, 0]) + bytes(8)
    header += struct.pack("<HHIQQQIHHHHHH", 3, 0xB7, 1, 0, 64, 0, 0, 64, 56, 2, 0, 0, 0)
    load = struct.pack("<IIQQQQQQ", 1, 5, 0, 0, 0, total, total, 0x1000)
    dyn = struct.pack("<IIQQQQQQ", 2, 6, dynamic_offset, dynamic_offset, dynamic_offset, 48, 48, 8)
    entries = struct.pack("<qQqQqQ", 5, strtab_offset, 14, 1, 0, 0)
    return header + load + dyn + entries + strtab


def macho_library(install_name: str) -> bytes:
    name = install_name.encode() + b"\0"
    name += bytes(-len(name) % 8)
    command = struct.pack("<IIIIII", 0xD, 24 + len(name), 24, 0, 0, 0) + name
    return struct.pack("<IIIIIIII", 0xFEEDFACF, 0x0100000C, 0, 6, 1, len(command), 0, 0) + command


class Spec:
    def __init__(self, os_name, tag, upstream="9.0.2"):
        self.os_name, self.tag = os_name, tag
        self.triple = TRIPLES[os_name]
        self.top = f"ffmpeg-{upstream}+{tag}-{self.triple}-runtime"
        self.asset = self.top + ".tar.gz"
        self.programs = {"ffmpeg": WORKING, "ffprobe": WORKING}
        self.identity = {}
        self.manifest_sha = {}
        self.omit = set()
        self.extra = []
        self.versions = {name: f"{major}.1.102" for name, major in MAJORS.items()}
        self.corrupt_after_manifest = set()

    def library_files(self, name):
        major = MAJORS[name]
        if self.os_name == "darwin":
            return (f"lib/{name}.{self.versions[name]}.dylib",
                    [f"lib/{name}.{major}.dylib", f"lib/{name}.dylib"], f"@rpath/{name}.{major}.dylib")
        return (f"lib/{name}.so.{self.versions[name]}",
                [f"lib/{name}.so.{major}", f"lib/{name}.so"], f"{name}.so.{major}")

    def build(self) -> bytes:
        key = ffmpeg_runtime.identity_key(self.os_name)
        entries, libraries = [], {}
        for name in MAJORS:
            file, links, identity = self.library_files(name)
            identity = self.identity.get(name, identity)
            data = macho_library(identity) if self.os_name == "darwin" else elf_library(identity)
            libraries[name] = {"file": file, "links": links, key: self.library_files(name)[2],
                               "sha256": self.manifest_sha.get(name, hashlib.sha256(data).hexdigest())}
            if name in self.omit:
                continue
            entries.append((file, "file", data + (b"x" if name in self.corrupt_after_manifest else b"")))
            entries += [(link, "link", Path(file).name) for link in links]
        entries.append(("share/ffmpeg-build/manifest.json", "file", json.dumps({"libraries": libraries}).encode()))
        entries += [(f"bin/{name}", "file", data) for name, data in self.programs.items()]
        entries += self.extra
        return archive(self.top, entries)


def archive(top, entries):
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
        root = tarfile.TarInfo(top)
        root.type = tarfile.DIRTYPE
        root.mode = 0o755
        tar.addfile(root)
        for name, kind, payload in entries:
            full = name if name.startswith(("/", "..")) or kind == "raw" else f"{top}/{name}"
            info = tarfile.TarInfo(full)
            info.mode = 0o755
            if kind in ("file", "raw"):
                info.size = len(payload)
                tar.addfile(info, io.BytesIO(payload))
            elif kind == "link":
                info.type = tarfile.SYMTYPE
                info.linkname = payload
                tar.addfile(info)
            elif kind == "hardlink":
                info.type = tarfile.LNKTYPE
                info.linkname = payload
                tar.addfile(info)
            elif kind == "fifo":
                info.type = tarfile.FIFOTYPE
                tar.addfile(info)
            elif kind == "dir":
                info.type = tarfile.DIRTYPE
                tar.addfile(info)
    return buffer.getvalue()


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def extract(self, entries):
        top = "ffmpeg-1+t-x-runtime"
        path = self.root / "a.tar.gz"
        path.write_bytes(archive(top, entries))
        target = self.root / "out"
        target.mkdir(exist_ok=True)
        ffmpeg_runtime.extract(path, top, target)
        return target

    def test_accepts_library_links_including_chains(self):
        target = self.extract([
            ("lib/libx.so.1.2.3", "file", b"lib"),
            ("lib/libx.so.1", "link", "libx.so.1.2.3"),
            ("lib/libx.so", "link", "libx.so.1"),
        ])
        self.assertEqual(os.readlink(target / "lib/libx.so"), "libx.so.1")
        self.assertEqual((target / "lib/libx.so").read_bytes(), b"lib")

    def test_rejects_unsafe_members_before_writing(self):
        real = ("lib/libx.so.1.2.3", "file", b"lib")
        cases = {
            "absolute target": [real, ("lib/libx.so", "link", "/etc/passwd")],
            "parent target": [real, ("lib/libx.so", "link", "../bin/ffmpeg")],
            "nested target": [real, ("lib/libx.so", "link", "sub/libx.so.1.2.3")],
            "dot target": [real, ("lib/libx.so", "link", ".")],
            "empty target": [real, ("lib/libx.so", "link", "")],
            "dangling": [real, ("lib/libx.so", "link", "libgone.so.1")],
            "cycle": [real, ("lib/a.so", "link", "b.so"), ("lib/b.so", "link", "a.so")],
            "self link": [real, ("lib/a.so", "link", "a.so")],
            "link to directory": [real, ("lib/sub", "dir", None), ("lib/libx.so", "link", "sub")],
            "link outside lib": [real, ("bin/ffmpeg", "link", "libx.so.1.2.3")],
            "link in lib subdirectory": [real, ("lib/sub", "dir", None), ("lib/sub/y.so", "link", "x")],
            "link at top": [real, ("libx.so", "link", "lib")],
            "write through link": [real, ("lib/libx.so", "link", "libx.so.1.2.3"), ("lib/libx.so/evil", "file", b"x")],
            "hard link": [real, ("lib/libx.so", "hardlink", "lib/libx.so.1.2.3")],
            "fifo": [real, ("lib/pipe", "fifo", None)],
            "traversal": [real, ("../escape", "file", b"x")],
            "absolute member": [real, ("/abs/escape", "file", b"x")],
            "outside top": [real, ("other/x", "raw", b"x")],
            "duplicate": [real, real],
        }
        for label, entries in cases.items():
            with self.subTest(label):
                target = self.root / "out"
                if target.exists():
                    import shutil
                    shutil.rmtree(target)
                with self.assertRaises(RuntimeArchiveError):
                    self.extract(entries)
                self.assertEqual(list(target.iterdir()), [])


class RuntimeInstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.home = self.root / "home"
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.codesign_status = "0"

    def installer(self, specs, os_name="linux", listed=None, tags=None):
        for name in ("codesign",):
            script = self.bin / name
            script.write_text("#!/bin/sh\nexit ${MOCK_CODESIGN_STATUS:-0}\n")
            script.chmod(0o755)
        routes = {f"{REPO}/releases.atom": atom([(f"2024-01-0{index + 1}", spec.tag) for index, spec in enumerate(specs)])}
        for spec in specs:
            payload = spec.build()
            digest = hashlib.sha256(payload).hexdigest()
            base = f"{REPO}/releases/download/{spec.tag}"
            routes[f"{base}/SHA256SUMS"] = f"{digest}  {spec.asset}\n".encode()
            routes[f"{base}/{spec.asset.replace('+', '%2B')}"] = (payload, {})
        env = {"HOME": str(self.home), "PATH": f"{self.bin}:/usr/bin:/bin", "TMPDIR": str(self.root),
               "MOCK_CODESIGN_STATUS": self.codesign_status}
        return FakeInstaller(self.home, os_name=os_name, arch="aarch64" if os_name == "darwin" else "x86_64",
                             env=env, routes=routes)

    def release(self, spec):
        return self.home / ".local/share/ffmpeg/releases" / f"{spec.tag}-{spec.triple}-runtime"

    def current(self):
        return Path(os.readlink(self.home / ".local/share/ffmpeg/current"))

    def releases(self):
        return sorted(path.name for path in (self.home / ".local/share/ffmpeg/releases").iterdir())

    def assert_untouched(self, spec, previous_names):
        self.assertEqual(self.current(), self.release(spec))
        self.assertEqual(self.releases(), previous_names)
        self.assertEqual(ffmpeg_runtime.verified_libraries(self.release(spec), "linux").keys(), MAJORS.keys())
        self.assertTrue((self.home / ".local/bin/ffmpeg").exists())

    def test_installs_complete_runtime_and_is_idempotent(self):
        spec = Spec("linux", "20250101")
        inst = self.installer([spec])
        inst.install_ffmpeg()
        release = self.release(spec)
        self.assertEqual(self.current(), release)
        self.assertEqual(os.readlink(release / "lib/libavcodec.so"), "libavcodec.so.63.1.102")
        self.assertTrue((release / "lib/libavcodec.so").samefile(release / "lib/libavcodec.so.63.1.102"))
        self.assertEqual(os.readlink(self.home / ".local/bin/ffmpeg"),
                         str(self.home / ".local/share/ffmpeg/current/bin/ffmpeg"))
        self.assertIn(("D", release), inst.claims)
        self.assertEqual((self.home / ".local/state/dl/ffmpeg").read_text().strip(), spec.tag)
        again = self.installer([spec])
        again.install_ffmpeg()
        self.assertFalse(again.changed)

    def test_darwin_runtime_checks_signatures(self):
        spec = Spec("darwin", "20250101")
        inst = self.installer([spec], os_name="darwin")
        inst.install_ffmpeg()
        self.assertEqual(self.current(), self.release(spec))
        self.assertEqual(ffmpeg_runtime.verified_libraries(self.release(spec), "darwin")["libavutil"].name,
                         "libavutil.61.1.102.dylib")

    def test_failed_upgrades_keep_the_previous_install(self):
        old = Spec("linux", "20250101")
        self.installer([old]).install_ffmpeg()
        names = self.releases()
        broken = {
            "missing library": lambda s: s.omit.add("libswscale"),
            "wrong soname": lambda s: s.identity.update(libavutil="libavutil.so.99"),
            "wrong manifest sha256": lambda s: s.manifest_sha.update(libavcodec="0" * 64),
            "library changed after manifest": lambda s: s.corrupt_after_manifest.add("libavformat"),
            "missing program": lambda s: s.programs.pop("ffprobe"),
            "program does not run": lambda s: s.programs.update(ffmpeg=b"#!/bin/sh\nexit 3\n"),
            "unsafe link": lambda s: s.extra.append(("lib/evil", "link", "../bin/ffmpeg")),
        }
        for label, mutate in broken.items():
            with self.subTest(label):
                new = Spec("linux", "20250202")
                mutate(new)
                with self.assertRaises(SkipInstall):
                    self.installer([old, new]).install_ffmpeg()
                self.assert_untouched(old, names)

    def test_checksum_mismatch_keeps_the_previous_install(self):
        old, new = Spec("linux", "20250101"), Spec("linux", "20250202")
        self.installer([old]).install_ffmpeg()
        names = self.releases()
        inst = self.installer([old, new])
        inst.routes[f"{REPO}/releases/download/20250202/SHA256SUMS"] = f"{'0' * 64}  {new.asset}\n".encode()
        with self.assertRaisesRegex(SkipInstall, "checksum mismatch"):
            inst.install_ffmpeg()
        self.assert_untouched(old, names)

    def test_missing_system_libva_is_reported(self):
        old = Spec("linux", "20250101")
        self.installer([old]).install_ffmpeg()
        names = self.releases()
        new = Spec("linux", "20250202")
        new.programs["ffmpeg"] = (b"#!/bin/sh\necho 'Error loading shared library libva.so.2: "
                                  b"No such file or directory' >&2\nexit 127\n")
        with self.assertRaisesRegex(SkipInstall, r"libva and libva-drm \(Alpine: apk add libva\)"):
            self.installer([old, new]).install_ffmpeg()
        self.assert_untouched(old, names)

    def test_failed_signature_check_keeps_the_previous_install(self):
        old = Spec("darwin", "20250101")
        self.installer([old], os_name="darwin").install_ffmpeg()
        names = self.releases()
        self.codesign_status = "1"
        with self.assertRaisesRegex(SkipInstall, "code signature"):
            self.installer([old, Spec("darwin", "20250202")], os_name="darwin").install_ffmpeg()
        self.assertEqual(self.current(), self.release(old))
        self.assertEqual(self.releases(), names)

    def test_interrupted_extraction_and_switch_keep_the_previous_install(self):
        old, new = Spec("linux", "20250101"), Spec("linux", "20250202")
        self.installer([old]).install_ffmpeg()
        names = self.releases()
        with patch.object(ffmpeg_runtime.shutil, "copyfileobj", side_effect=OSError("disk full")):
            with self.assertRaises(SkipInstall):
                self.installer([old, new]).install_ffmpeg()
        self.assertEqual(self.releases(), names)
        inst = self.installer([old, new])
        with patch.object(inst, "switch_symlink", return_value=False):
            with self.assertRaisesRegex(SkipInstall, "could not switch"):
                inst.install_ffmpeg()
        self.assertEqual(self.current(), self.release(old))
        self.assertTrue((self.home / ".local/bin/ffmpeg").exists())
        self.assertEqual(ffmpeg_runtime.verified_libraries(self.release(new), "linux").keys(), MAJORS.keys())

    def test_unreachable_release_keeps_the_installed_runtime(self):
        spec = Spec("linux", "20250101")
        self.installer([spec]).install_ffmpeg()
        newer = Spec("linux", "20250202")
        inst = self.installer([spec, newer])
        del inst.routes[f"{REPO}/releases/download/20250202/SHA256SUMS"]
        inst.install_ffmpeg()
        self.assertEqual(self.current(), self.release(spec))

    def test_corrupted_install_is_replaced(self):
        spec = Spec("linux", "20250101")
        self.installer([spec]).install_ffmpeg()
        library = self.release(spec) / "lib/libavcodec.so.63.1.102"
        library.write_bytes(library.read_bytes() + b"x")
        inst = self.installer([spec])
        inst.install_ffmpeg()
        self.assertTrue(inst.changed)
        ffmpeg_runtime.verified_libraries(self.release(spec), "linux")

    def test_legacy_static_release_is_retired_after_migration(self):
        spec = Spec("linux", "20250101")
        legacy = self.home / ".local/share/ffmpeg/releases" / f"20241231-{spec.triple}"
        (legacy / "bin").mkdir(parents=True)
        (legacy / "bin/ffmpeg").write_bytes(WORKING)
        (legacy / "bin/ffprobe").write_bytes(WORKING)
        os.symlink(legacy, self.home / ".local/share/ffmpeg/current")
        inst = self.installer([spec])
        (self.home / ".local/bin").mkdir(parents=True, exist_ok=True)
        os.symlink(self.home / ".local/share/ffmpeg/current/bin/ffmpeg", self.home / ".local/bin/ffmpeg")
        os.symlink(self.home / ".local/share/ffmpeg/current/bin/ffprobe", self.home / ".local/bin/ffprobe")
        inst.install_ffmpeg()
        self.assertEqual(self.releases(), [self.release(spec).name])
        self.assertIn(legacy, inst.removed)

    def test_pinned_release_survives_current_moving(self):
        old, new = Spec("linux", "20250101"), Spec("linux", "20250202")
        self.installer([old]).install_ffmpeg()
        pinned = self.installer([old, new]).ensure_ffmpeg_runtime("player", old.tag)
        self.assertEqual(pinned, self.release(old))
        inst = self.installer([old, new])
        inst.install_ffmpeg()
        self.assertEqual(self.current(), self.release(new))
        self.assertEqual(self.releases(), sorted([self.release(old).name, self.release(new).name]))
        ffmpeg_runtime.verified_libraries(self.release(old), "linux")
        self.assertIn(("F", self.home / ".local/share/ffmpeg/pins/player"), inst.claims)

    def test_pin_installs_a_missing_release_without_moving_current(self):
        old, new = Spec("linux", "20250101"), Spec("linux", "20250202")
        self.installer([old]).install_ffmpeg()
        inst = self.installer([old, new])
        path = inst.ensure_ffmpeg_runtime("player", new.tag)
        self.assertEqual(path, self.release(new))
        self.assertEqual(self.current(), self.release(old))
        offline = self.installer([old, new])
        offline.routes = {}
        self.assertEqual(offline.ensure_ffmpeg_runtime("player", new.tag), self.release(new))
        self.assertFalse(offline.changed)

    def test_moving_a_pin_releases_the_old_version(self):
        old, mid, new = Spec("linux", "20250101"), Spec("linux", "20250202"), Spec("linux", "20250303")
        self.installer([mid]).install_ffmpeg()
        self.installer([old, mid, new]).ensure_ffmpeg_runtime("player", old.tag)
        self.installer([old, mid, new]).ensure_ffmpeg_runtime("player", new.tag)
        self.assertEqual(self.releases(), sorted([self.release(mid).name, self.release(new).name]))

    def test_unavailable_pinned_release_is_an_error(self):
        spec = Spec("linux", "20250101")
        self.installer([spec]).install_ffmpeg()
        with self.assertRaises(SkipInstall):
            self.installer([spec]).ensure_ffmpeg_runtime("player", "20240101")
        with self.assertRaises(SkipInstall):
            self.installer([spec]).ensure_ffmpeg_runtime("player", "../x")


if __name__ == "__main__":
    unittest.main()

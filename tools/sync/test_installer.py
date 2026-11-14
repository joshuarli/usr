"""Installer tests with fake HTTP and fake executables; no network or home effects."""
import io
import json
import os
from pathlib import Path
import sys
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import URLError
import zipfile

sys.path.insert(0, str(Path(__file__).parent))
import installer
import pi_offline
import pi_release
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pi"))
import release_cache
from installer import Installer, SkipInstall, default_tools


def subprocess_run(args):
    return subprocess.run(args, capture_output=True, text=True, check=True).stdout.strip()


def atom(entries):
    body = ['<?xml version="1.0" encoding="utf-8"?><feed>']
    for updated, tag in entries:
        body.append(f'<entry><updated>{updated}</updated>'
                    f'<link href="https://github.com/x/y/releases/tag/{tag}"/></entry>')
    body.append("</feed>")
    return "".join(body).encode()


def make_zip(members, executable=()):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, data in members.items():
            info = zipfile.ZipInfo(name)
            info.create_system = 3
            info.external_attr = (0o100755 if name in executable else 0o100644) << 16
            archive.writestr(info, data)
    return buffer.getvalue()


def make_tar(members, mode="w:gz"):
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode=mode) as archive:
        for name, data in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mode = 0o755
            archive.addfile(info, io.BytesIO(data))
    return buffer.getvalue()


def sums(assets):
    return "".join(f"{'a' * 64}  {name}\n" for name in assets).encode()


class FakeInstaller(Installer):
    def __init__(self, *args, routes=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.routes = routes or {}
        self.fetched = []

    def fetch(self, url, *, ranged=False):
        self.fetched.append(url)
        if url not in self.routes:
            raise URLError(f"no route for {url}")
        route = self.routes[url]
        if isinstance(route, tuple):
            return route
        return route, {}

    def effective_url(self, url):
        return self.routes.get(url + " ->", "")


class InstallerTests(unittest.TestCase):
    def test_pi_explicit_pin_does_not_fall_back_to_default(self):
        inst = self.make()
        selected = self.root / "headless.pin.json"
        inst.env["USR_PI_RUNTIME_PIN"] = str(selected)
        with patch.object(pi_release, "load_pin", side_effect=pi_offline.OfflinePiError("missing selected pin")) as load:
            with self.assertRaises(SkipInstall):
                inst.install_pi()
        load.assert_called_once_with(selected)
        self.assertFalse(self.dest_path("pi").exists())
        inst.env["USR_PI_RUNTIME_PIN"] = "relative.pin.json"
        with patch.object(pi_release, "load_pin") as load:
            with self.assertRaises(SkipInstall) as error:
                inst.install_pi()
        self.assertIn("must be absolute", str(error.exception))
        load.assert_not_called()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.home = self.root / "home"
        self.bin = self.root / "bin"
        self.bin.mkdir(parents=True)
        self.script("codesign", "#!/bin/sh\nexit ${MOCK_CODESIGN_STATUS:-0}\n")
        self.script("xattr", "#!/bin/sh\nexit 0\n")
        self.script("file", "#!/bin/sh\nfor last; do :; done\nif [ \"$(head -c 2 \"$last\")\" = '#!' ]; then printf 'POSIX shell script\\n'; else printf 'Mach-O 64-bit executable arm64\\n'; fi\n")
        self.script("pnpm", "#!/bin/sh\nexit 0\n")
        self.script("zipinfo", "#!/bin/sh\nexit 0\n")
        self.script("getconf", "#!/bin/sh\nif [ \"$1\" = GNU_LIBC_VERSION ]; then exit ${MOCK_GETCONF_STATUS:-1}; fi\nexit 1\n")
        self.script("node", "#!/bin/sh\nprintf '%s\\n' \"${MOCK_NODE_VERSION:-26.13.1}\"\n")
        self.script("npm", f"#!{sys.executable}\n" + '''import json, os, pathlib, sys
args = sys.argv[1:]
log = os.environ.get("NPM_LOG")
if log:
    with open(log, "a") as stream:
        stream.write(json.dumps(args) + chr(10))
if args and args[0] == "view":
    spec = str(args[1])
    versions = json.loads(os.environ.get("MOCK_NPM_VERSIONS", "{}"))
    for package, version in versions.items():
        if spec.startswith(package):
            print(version)
            sys.exit(0)
    sys.exit(1)
if args and args[0] == "--version":
    print(os.environ.get("MOCK_NPM_VERSION", "12.2.2"))
    sys.exit(0)
if args and os.environ.get("MOCK_NPM_FAIL") == "1":
    sys.exit(1)
if args[:2] == ["install", "--global"]:
    prefix = pathlib.Path(args[args.index("--prefix") + 1])
    bin_map = {"command-code": "cmd", "pi-coding-agent": "pi", "dsh-tui": "dsh-tui"}
    prefix_index = args.index("--prefix")
    specs = [arg for arg in args[prefix_index + 1:] if not arg.startswith("--")]
    for spec in specs:
        package = spec.rsplit("@", 1)[0] or spec
        binary = bin_map.get(package.split("/")[-1], os.environ.get("MOCK_NPM_BIN", package.split("/")[-1]))
        if os.environ.get("MOCK_NPM_NO_BIN") != "1":
            target = prefix / "bin" / binary
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("#!/bin/sh" + chr(10) + "exit 0" + chr(10))
            target.chmod(0o755)
    if any(spec.startswith("@deepseek-harness-tui/dsh-tui@") for spec in specs):
        patch = prefix / "lib/node_modules/@deepseek-harness-tui/dsh-tui/cordis.patch.yml"
        patch.parent.mkdir(parents=True, exist_ok=True)
        patch.write_text("current" + chr(10))
    sys.exit(0)
if args[:2] == ["uninstall", "--global"]:
    sys.exit(0)
sys.exit(1)
''')

    def script(self, name, text):
        path = self.bin / name
        path.write_text(text)
        path.chmod(0o755)

    def make(self, routes=None, os_name="linux", arch="x86_64", extra_bin=None):
        env = {"HOME": str(self.home), "PATH": f"{self.bin}:/usr/bin:/bin",
               "TMPDIR": str(self.root), "NPM_LOG": str(self.root / "npm.log"),
               "MOCK_NPM_VERSIONS": json.dumps({
                   "command-code@latest": "1.87.3", "pnpm@latest": "12.16.1",
                   "cf@latest": "3.0.0",
                   "@earendil-works/pi-coding-agent@latest": "1.4.0",
                   "@deepseek-ai/dsh@next": "0.2.1", "@deepseek-harness-tui/dsh-tui": "0.16.0",
                   "npm@latest": "11.9.0"})}
        if extra_bin:
            env["PATH"] = f"{extra_bin}:{env['PATH']}"
        return FakeInstaller(self.home, os_name=os_name, arch=arch, env=env, routes=routes or {})

    def dest_path(self, name):
        return self.home / ".local/bin" / name

    def state(self, name):
        return (self.home / ".local/state/dl" / name).read_text().strip()

    def test_release_install_current_and_unknown(self):
        asset = "gh-x86_64-unknown-linux-musl"
        url = f"https://github.com/joshuarli/gh/releases/download/v1/{asset}.zip"
        routes = {"https://github.com/joshuarli/gh/releases.atom": atom([("2024-01-01", "v1")]),
                  url: (b"zip", {"ETag": "etag-1"})}
        inst = self.make(routes)
        with patch.object(inst, "zip_member", return_value=b"binary"):
            inst.install_release("gh")
        self.assertEqual(self.dest_path("gh").read_bytes(), b"binary")
        self.assertEqual(self.state("gh"), "etag-1")
        self.assertIn(("F", self.dest_path("gh")), inst.claims)
        inst = self.make(routes)
        with patch.object(inst, "zip_member", return_value=b"binary"):
            inst.install_release("gh")
        self.assertFalse(inst.changed)
        with self.assertRaises(SkipInstall):
            inst.install_release("nope")

    def rimage_commands(self, inst, payload, *, corrupt=False, authenticated=True):
        import hashlib
        tag = "release-" + "a" * 40
        target = f"{inst.arch}-apple-darwin" if inst.os_name == "darwin" else f"{inst.arch}-unknown-linux-musl-static"
        member = f"rimage-{target}"
        archive = make_zip({member: payload})
        digest = "0" * 64 if corrupt else hashlib.sha256(archive).hexdigest()
        release = {"tag_name": tag, "prerelease": True, "draft": False, "published_at": "2026-11-11",
                   "assets": [{"name": member + ".zip", "id": member}, {"name": "SHA256SUMS", "id": 2}]}
        def run(args, **kwargs):
            if args[1] == "api":
                pages = [[release, dict(release, prerelease=False, published_at="2027-01-01"),
                          dict(release, draft=True, published_at="2027-02-01")]]
                return subprocess.CompletedProcess(args, 0 if authenticated else 1, json.dumps(pages), "")
            self.assertEqual(args[:4], ["gh", "release", "download", tag])
            destination = Path(args[args.index("--dir") + 1])
            (destination / (member + ".zip")).write_bytes(archive)
            (destination / "SHA256SUMS").write_text(f"{digest}  {member}.zip\n")
            return subprocess.CompletedProcess(args, 0, "", "")
        return run

    def test_rimage_private_prerelease_targets_and_current(self):
        self.script("gh", "#!/bin/sh\nexit 1\n")
        for os_name, arch in [("darwin", "aarch64"), ("linux", "x86_64"), ("linux", "aarch64")]:
            with self.subTest(os_name=os_name, arch=arch):
                inst = self.make(os_name=os_name, arch=arch)
                payload = f"binary-{os_name}-{arch}".encode()
                original = inst.run
                commands = self.rimage_commands(inst, payload)
                with patch.object(inst, "run", side_effect=lambda args, _commands=commands, _original=original, **kwargs: _commands(args, **kwargs) if args[0] == "gh" else _original(args, **kwargs)):
                    inst.install("rimage")
                    self.assertEqual(self.dest_path("rimage").read_bytes(), payload)
                    self.assertIn(("F", self.dest_path("rimage")), inst.claims)
                    inst.changed = False
                    inst.install("rimage")
                    self.assertFalse(inst.changed)

    def test_rimage_bad_checksum_or_auth_preserves_existing_binary(self):
        self.script("gh", "#!/bin/sh\nexit 1\n")
        self.dest_path("rimage").parent.mkdir(parents=True, exist_ok=True)
        self.dest_path("rimage").write_bytes(b"previous")
        for mode in ("checksum", "auth"):
            inst = self.make()
            with patch.object(inst, "run", side_effect=self.rimage_commands(inst, b"new", corrupt=mode == "checksum", authenticated=mode != "auth")):
                with self.assertRaises(SkipInstall):
                    inst.install("rimage")
            self.assertEqual(self.dest_path("rimage").read_bytes(), b"previous")
            self.assertFalse((self.home / ".local/state/dl/rimage").exists())
            self.assertFalse(list(self.dest_path("rimage").parent.glob(".rimage.*")))

    def test_release_missing_asset_keeps_installed_and_skips_uninstalled(self):
        routes = {"https://github.com/laputa-systems/srv/releases.atom": atom([("2024-01-01", "release-1")])}
        inst = self.make(routes, os_name="darwin", arch="aarch64")
        with self.assertRaises(SkipInstall):
            inst.install_release("srv")
        dest = self.dest_path("srv")
        dest.write_bytes(b"old")
        (self.home / ".local/state/dl/srv").write_text("old-etag\n")
        inst = self.make(routes, os_name="darwin", arch="aarch64")
        inst.install_release("srv")
        self.assertEqual(dest.read_bytes(), b"old")
        self.assertEqual(self.state("srv"), "old-etag")

    def test_empty_url_is_a_failed_fetch_not_a_value_error(self):
        inst = Installer(self.home, os_name="darwin", arch="aarch64",
                         env={"HOME": str(self.home), "PATH": f"{self.bin}:/usr/bin:/bin"})
        self.assertEqual(inst.asset_id(""), "")
        self.assertEqual(inst.fetch_text(""), "")
        self.assertEqual(inst.effective_url(""), "")
        self.assertFalse(inst.download("", self.root / "out"))

    def test_release_shuck_installs_as_shellcheck(self):
        asset = "shuck-aarch64-apple-darwin"
        url = f"https://github.com/joshuarli/shck/releases/download/release-1/{asset}.zip"
        routes = {"https://github.com/joshuarli/shck/releases.atom": atom([("2024-01-01", "release-1")]),
                  url: (b"zip", {"ETag": "e"})}
        inst = self.make(routes, os_name="darwin", arch="aarch64")
        with patch.object(inst, "zip_member", return_value=b"binary"):
            inst.install_release("shuck")
        self.assertTrue(self.dest_path("shellcheck").is_file())

    def _stuff_routes(self, payload, target="x86_64-unknown-linux-musl", digest=None, sums_asset=None):
        import hashlib
        digest = digest or hashlib.sha256(payload).hexdigest()
        asset = f"stuff-{target}"
        base = "https://github.com/joshuarli/stuff/releases/download/v1"
        routes = {"https://github.com/joshuarli/stuff/releases.atom": atom([("2024-01-01", "v1")]),
                  f"{base}/{asset}": (payload, {"ETag": "e"}),
                  f"{base}/SHA256SUMS": f"{digest}  {sums_asset or asset}\n".encode()}
        return routes, base, asset

    def test_stuff_installs_raw_asset_with_sha256sums(self):
        payload = b"#!/bin/sh\nexit 0\n"
        routes, base, asset = self._stuff_routes(payload)
        inst = self.make(routes)
        inst.install_release("stuff")
        self.assertEqual(self.dest_path("stuff").read_bytes(), payload)
        self.assertTrue(os.access(self.dest_path("stuff"), os.X_OK))
        self.assertEqual(self.state("stuff"), "e")
        self.assertIn(("F", self.dest_path("stuff")), inst.claims)
        self.assertEqual({url for url in inst.fetched if "/releases/download/" in url},
                         {f"{base}/{asset}", f"{base}/SHA256SUMS"})
        self.assertFalse(any(url.endswith(".zip") for url in inst.fetched))

    def test_stuff_rejects_checksum_mismatch_and_keeps_existing_binary(self):
        payload = b"#!/bin/sh\nexit 0\n"
        routes, base, asset = self._stuff_routes(payload, digest="0" * 64)
        inst = self.make(routes)
        dest = self.dest_path("stuff")
        dest.write_bytes(b"old")
        (self.home / ".local/state/dl/stuff").write_text("old-etag\n")
        with self.assertRaises(SkipInstall) as ctx:
            inst.install_release("stuff")
        self.assertIn("checksum mismatch", str(ctx.exception))
        self.assertEqual(dest.read_bytes(), b"old")
        self.assertEqual(self.state("stuff"), "old-etag")

    def test_stuff_rejects_missing_sha256sums_entry_and_keeps_existing_binary(self):
        payload = b"#!/bin/sh\nexit 0\n"
        routes, base, asset = self._stuff_routes(payload, sums_asset="stuff-aarch64-apple-darwin")
        inst = self.make(routes)
        dest = self.dest_path("stuff")
        dest.write_bytes(b"old")
        (self.home / ".local/state/dl/stuff").write_text("old-etag\n")
        with self.assertRaises(SkipInstall) as ctx:
            inst.install_release("stuff")
        self.assertIn("SHA256SUMS", str(ctx.exception))
        self.assertEqual(dest.read_bytes(), b"old")
        self.assertEqual(self.state("stuff"), "old-etag")

    def agent_browser_routes(self, payload, digest=None):
        import hashlib
        digest = digest or hashlib.sha256(payload).hexdigest()
        asset = "agent-browser-linux-musl-x64"
        release = {"tag_name": "v0.43.0", "assets": [{"name": asset, "digest": f"sha256:{digest}"},
                                                      {"name": "agent-browser-darwin-arm64", "digest": "sha256:" + "b" * 64}]}
        return {"https://api.github.com/repos/vercel-labs/agent-browser/releases/latest": json.dumps(release).encode(),
                f"https://github.com/vercel-labs/agent-browser/releases/download/v0.43.0/{asset}": payload}

    def test_agent_browser_release_binary_replaces_npm_install(self):
        payload = b"#!/bin/sh\necho 'agent-browser 0.43.0'\n"
        npm_root = self.home / ".local/share/agent-browser"
        (npm_root / "lib/node_modules/agent-browser/bin").mkdir(parents=True)
        (npm_root / "bin").mkdir()
        (npm_root / "bin/agent-browser").symlink_to(npm_root / "lib/node_modules/agent-browser/bin/agent-browser")
        self.dest_path("agent-browser").parent.mkdir(parents=True, exist_ok=True)
        self.dest_path("agent-browser").symlink_to(npm_root / "bin/agent-browser")
        state = self.home / ".local/state/dl/agent-browser"
        state.parent.mkdir(parents=True, exist_ok=True)
        state.write_text("0.42.0\n")
        routes = self.agent_browser_routes(payload)
        inst = self.make(routes)
        inst.install_agent_browser()
        launcher = self.dest_path("agent-browser")
        self.assertFalse(launcher.is_symlink())
        self.assertEqual(launcher.read_bytes(), payload)
        self.assertTrue(self.state("agent-browser").startswith("v0.43.0:"))
        self.assertFalse(npm_root.exists())
        inst = self.make(routes)
        inst.install_agent_browser()
        self.assertEqual(inst.fetched, ["https://api.github.com/repos/vercel-labs/agent-browser/releases/latest"])

    def test_agent_browser_refuses_mismatch_unmanaged_and_unsupported(self):
        payload = b"#!/bin/sh\necho 'agent-browser 0.43.0'\n"
        inst = self.make(self.agent_browser_routes(payload, digest="0" * 64))
        with self.assertRaises(SkipInstall):
            inst.install_agent_browser()
        self.assertFalse(self.dest_path("agent-browser").exists())
        self.assertEqual([path.name for path in self.dest_path("agent-browser").parent.glob(".agent-browser.*")], [])
        self.dest_path("agent-browser").write_text("mine")
        inst = self.make(self.agent_browser_routes(payload))
        with self.assertRaises(SkipInstall):
            inst.install_agent_browser()
        self.assertEqual(self.dest_path("agent-browser").read_text(), "mine")
        inst = self.make({}, os_name="linux", arch="riscv64")
        with self.assertRaises(SkipInstall):
            inst.install_agent_browser()

    def test_fd_and_zzz_platforms(self):
        inst = self.make({}, os_name="darwin", arch="aarch64")
        with self.assertRaises(SkipInstall):
            inst.install_zzz()
        asset = "fd-v1-aarch64-apple-darwin"
        url = f"https://github.com/sharkdp/fd/releases/download/v1/{asset}.tar.gz"
        routes = {"https://github.com/sharkdp/fd/releases/latest ->":
                  "https://github.com/sharkdp/fd/releases/tag/v1",
                  url: (b"tar", {"ETag": "e"})}
        inst = self.make(routes, os_name="darwin", arch="aarch64")
        with patch.object(inst, "tar_member", return_value=b"binary"):
            inst.install_fd_or_rg("fd")
        self.assertEqual(self.dest_path("fd").read_bytes(), b"binary")

    def test_jaq_direct_and_uv_checksum(self):
        inst = self.make({"https://github.com/01mf02/jaq/releases/latest/download/jaq-x86_64-unknown-linux-musl":
                          (b"binary", {"ETag": "e"})})
        inst.install_jaq()
        self.assertEqual(self.dest_path("jaq").read_bytes(), b"binary")
        asset = "uv-x86_64-unknown-linux-musl"
        url = f"https://github.com/astral-sh/uv/releases/download/0.1/{asset}.tar.gz"
        payload = make_tar({f"{asset}/uv": b"u", f"{asset}/uvx": b"x"})
        import hashlib
        digest = hashlib.sha256(payload).hexdigest()
        routes = {"https://github.com/astral-sh/uv/releases.atom": atom([("2024-01-01", "0.1")]),
                  url: (payload, {"ETag": "e"}),
                  url + ".sha256": f"{digest}  {asset}.tar.gz\n".encode()}
        inst = self.make(routes)
        inst.install_uv()
        self.assertEqual(self.dest_path("uv").read_bytes(), b"u")
        self.assertEqual(self.dest_path("uvx").read_bytes(), b"x")
        bad = dict(routes)
        bad[url + ".sha256"] = b"0" * 64 + b"  " + asset.encode() + b".tar.gz\n"
        inst = self.make(bad)
        for name in ("uv", "uvx"):
            self.dest_path(name).unlink(missing_ok=True)
            (self.home / f".local/state/dl/{name}").unlink(missing_ok=True)
        with self.assertRaises(SkipInstall):
            inst.install_uv()

    def _pinned_python(self, routes):
        import hashlib
        payload = make_tar({"python/bin/python3.15": b"#!/bin/sh\nexit 0\n"})
        digest = hashlib.sha256(payload).hexdigest()
        asset = "cpython-3.15.1+20261107-x86_64-unknown-linux-musl-install_only_stripped.tar.gz"
        url = f"https://github.com/laputa-systems/python-build/releases/download/20261107/{asset.replace('+', '%2B')}"
        routes[url] = (payload, {"ETag": "e"})
        pin = ("20261107", "laputa-systems/python-build",
               {"x86_64-unknown-linux-musl": (asset, digest)})
        return routes, url, asset, digest, pin

    def test_python3_install_and_checksum_mismatch(self):
        routes, url, asset, digest, pin = self._pinned_python({})
        inst = self.make(routes)
        with patch.object(installer, "python_build_pin", return_value=pin):
            inst.install_python3()
        self.assertTrue(self.dest_path("python3").is_symlink())
        self.assertTrue(self.dest_path("python3.15").is_symlink())
        self.assertEqual(self.state("python3"), digest)
        inst = self.make({})
        with patch.object(installer, "python_build_pin", return_value=pin):
            inst.install_python3()
        self.assertFalse(inst.changed)
        bad_pin = ("20261107", "laputa-systems/python-build",
                   {"x86_64-unknown-linux-musl": (asset, "0" * 64)})
        inst = self.make(routes)
        self.dest_path("python3").unlink(missing_ok=True)
        self.dest_path("python3.15").unlink(missing_ok=True)
        (self.home / ".local/state/dl/python3").unlink(missing_ok=True)
        import shutil as _shutil
        _shutil.rmtree(self.home / ".local/share/python-build", ignore_errors=True)
        with patch.object(installer, "python_build_pin", return_value=bad_pin):
            with self.assertRaises(SkipInstall):
                inst.install_python3()
        self.assertFalse(self.dest_path("python3").exists())

    def test_nodebuild_install_current_and_checksum_mismatch(self):
        sha = "9" * 40
        payload = make_tar({"node/bin/node": b"#!/bin/sh\nexit 0\n"}, "w:xz")
        routes = self._build_routes("laputa-systems/node-build", "node", sha, payload, version="24.19.2")
        inst = self.make(routes)
        inst.install_nodebuild()
        link = self.dest_path("node-build")
        self.assertEqual(os.readlink(link),
                         str(self.home / f".local/share/node-build/release-{sha}/node/bin/node"))
        inst = self.make(routes)
        inst.install_nodebuild()
        self.assertFalse(inst.changed)
        sha = "a" * 40
        routes = self._build_routes("laputa-systems/node-build", "node", sha, payload, version="24.19.2",
                                    listed="0" * 64)
        inst = self.make(routes)
        with self.assertRaises(SkipInstall) as ctx:
            inst.install_nodebuild()
        self.assertIn("checksum mismatch", str(ctx.exception))

    def test_nodejs_checksum_mismatch_is_a_skip(self):
        inst = self.make({"https://mirror.17166969.xyz/current/node-v26.13.1-darwin-arm64.zip": b"not-the-pinned-build"},
                         os_name="darwin", arch="aarch64")
        with self.assertRaises(SkipInstall) as ctx:
            inst.install_nodejs()
        self.assertIn("checksum mismatch", str(ctx.exception))

    def test_nodejs_failed_upgrade_keeps_old_launchers_and_retry_switches(self):
        release = self.home / ".local/share/nodejs/26.12.0-npm11.9.0-darwin-arm64"
        (release / "bin").mkdir(parents=True)
        (release / "bin/node").write_text("#!/bin/sh\nprintf '26.12.0\\n'\n")
        (release / "bin/npm").write_text("#!/bin/sh\nprintf '11.9.0\\n'\n")
        for tool in ("node", "npm", "npx"):
            path = release / "bin" / tool
            if tool == "npx": path.write_text("#!/bin/sh\nexit 0\n")
            path.chmod(0o755)
        current = self.home / ".local/share/nodejs/current"
        current.symlink_to(release, target_is_directory=True)
        self.dest_path("node").parent.mkdir(parents=True)
        for tool in ("node", "npm", "npx"):
            self.dest_path(tool).symlink_to(str(current / "bin" / tool))
        url = "https://mirror.17166969.xyz/current/node-v26.13.1-darwin-arm64.zip"
        inst = self.make({}, os_name="darwin", arch="aarch64")
        with self.assertRaises(SkipInstall):
            inst.install_nodejs()
        self.assertEqual(os.readlink(current), str(release))
        self.assertEqual(subprocess_run([str(self.dest_path("node")), "-p", "process.versions.node"]), "26.12.0")
        self.assertEqual(subprocess_run([str(self.dest_path("npm")), "--version"]), "11.9.0")
        subprocess.run([str(self.dest_path("npx")), "--version"], check=True)
        retry = self.make({url: b"candidate"}, os_name="darwin", arch="aarch64")
        def extract(_archive, staged, *, strip=0):
            (staged / "bin").mkdir()
            for tool, body in (("node", "#!/bin/sh\nprintf '26.13.1\\n'\n"),
                               ("npm", "#!/bin/sh\nprintf '12.2.2\\n'\n"),
                               ("npx", "#!/bin/sh\nexit 0\n")):
                target = staged / "bin" / tool
                target.write_text(body)
                target.chmod(0o755)
            return True
        with patch.object(retry, "sha256_file", return_value="0d45363e43fc1e290035d9a85962c62c32e42b70d28ae48b7b7196b335a188aa"), \
             patch.object(retry, "extract_zip", side_effect=extract):
            retry.install_nodejs()
        selected = Path(os.readlink(current))
        self.assertEqual(selected.name, "26.13.1-npm12.2.2-darwin-arm64")
        self.assertTrue((selected / "bin/node").is_file())
        self.assertFalse(release.exists())
        for tool in ("node", "npm", "npx"):
            self.assertEqual(os.readlink(self.dest_path(tool)), str(current / "bin" / tool))

    def test_nodejs_managed_uses_bundled_npm_without_registry(self):
        release = self.home / ".local/share/nodejs/26.13.1-npm12.2.2-darwin-arm64"
        cli_js = release / "lib/node_modules/npm/bin/npm-cli.js"
        cli_js.parent.mkdir(parents=True)
        cli_js.write_text(f"#!/bin/sh\nexec {self.bin / 'npm'} \"$@\"\n")
        cli_js.chmod(0o755)
        (release / "lib/node_modules/npm/lib").mkdir(parents=True)
        (release / "lib/node_modules/npm/lib/cli.js").write_text("")
        bin_dir = release / "bin"
        bin_dir.mkdir()
        (bin_dir / "node").write_text("#!/bin/sh\nprintf '26.13.1\\n'\n")
        (bin_dir / "node").chmod(0o755)
        (bin_dir / "npm").symlink_to("../lib/node_modules/npm/bin/npm-cli.js")
        (bin_dir / "npx").symlink_to("../lib/node_modules/npm/bin/npx-cli.js")
        (release / "lib/node_modules/npm/bin/npx-cli.js").write_text("")
        current = self.home / ".local/share/nodejs/current"
        current.symlink_to(release, target_is_directory=True)
        inst = self.make(os_name="darwin", arch="aarch64")
        for command in ("node", "npm", "npx"):
            self.dest_path(command).symlink_to(str(current / "bin" / command))
        inst.env["MOCK_NPM_FAIL"] = "1"
        inst.install_nodejs()
        self.assertEqual(inst.fetched, [])
        self.assertEqual(os.readlink(current), str(release))
        self.assertEqual([p.name for p in (self.home / ".local/share/nodejs").iterdir()
                          if p.name.startswith(".nodejs.")], [])
        log = self.root / "npm.log"
        if log.exists():
            calls = [json.loads(line) for line in log.read_text().splitlines()]
            self.assertFalse(any(a and a[0] in ("view", "install") for a in calls),
                             "Node prerequisite may not fetch from npm")
        for command in ("node", "npm", "npx"):
            self.assertEqual(os.readlink(self.dest_path(command)),
                             str(current / "bin" / command))

    def test_nodejs_relative_current_is_healed_to_absolute(self):
        release = self.home / ".local/share/nodejs/26.13.1-npm11.9.0-darwin-arm64"
        cli_js = release / "lib/node_modules/npm/bin/npm-cli.js"
        cli_js.parent.mkdir(parents=True)
        cli_js.write_text(f"#!/bin/sh\nexec {self.bin / 'npm'} \"$@\"\n")
        cli_js.chmod(0o755)
        (release / "lib/node_modules/npm/lib").mkdir(parents=True)
        (release / "lib/node_modules/npm/lib/cli.js").write_text("")
        bin_dir = release / "bin"
        bin_dir.mkdir()
        (bin_dir / "node").write_text("#!/bin/sh\nprintf '26.13.1\\n'\n")
        (bin_dir / "node").chmod(0o755)
        (bin_dir / "npm").symlink_to("../lib/node_modules/npm/bin/npm-cli.js")
        (bin_dir / "npx").symlink_to("../lib/node_modules/npm/bin/npx-cli.js")
        (release / "lib/node_modules/npm/bin/npx-cli.js").write_text("")
        current = self.home / ".local/share/nodejs/current"
        current.symlink_to(release.name, target_is_directory=True)
        inst = self.make(os_name="darwin", arch="aarch64")
        inst.env["MOCK_NPM_VERSION"] = "11.9.0"
        for command in ("node", "npm", "npx"):
            self.dest_path(command).symlink_to(str(current / "bin" / command))
        inst.install_nodejs()
        self.assertEqual(os.readlink(current), str(release))
        self.assertTrue((current / "bin/node").is_file())

    def test_nodejs_relative_foreign_current_is_preserved(self):
        foreign = self.home / ".local/share/nodejs/26.14.0-darwin-arm64"
        foreign.mkdir(parents=True)
        (foreign / "marker").write_text("keep\n")
        current = self.home / ".local/share/nodejs/current"
        current.symlink_to(foreign.name, target_is_directory=True)
        routes = {"https://mirror.17166969.xyz/current/node-v26.13.1-darwin-arm64.zip": b"not-the-pinned-build"}
        inst = self.make(routes, os_name="darwin", arch="aarch64")
        for command in ("node", "npm", "npx"):
            self.dest_path(command).symlink_to(str(current / "bin" / command))
        with self.assertRaises(SkipInstall) as ctx:
            inst.install_nodejs()
        self.assertIn("checksum mismatch", str(ctx.exception))
        self.assertEqual(os.readlink(current), foreign.name)
        self.assertTrue((foreign / "marker").is_file())

    def test_nodejs_absolute_outside_current_still_skips(self):
        outside = self.root / "outside-node"
        outside.mkdir(parents=True)
        (outside / "marker").write_text("keep\n")
        current = self.home / ".local/share/nodejs/current"
        current.parent.mkdir(parents=True)
        current.symlink_to(outside, target_is_directory=True)
        inst = self.make(os_name="darwin", arch="aarch64")
        with self.assertRaises(SkipInstall) as ctx:
            inst.install_nodejs()
        self.assertIn("points outside", str(ctx.exception))
        self.assertEqual(os.readlink(current), str(outside))
        self.assertTrue((outside / "marker").is_file())


        inst = self.make()
        inst.install_cmd()
        self.assertTrue(self.dest_path("cmd").is_symlink())
        self.assertEqual(self.state("cmd"), "1.87.3")
        inst.install_cmd()
        installs = [json.loads(line) for line in (self.root / "npm.log").read_text().splitlines()
                    if json.loads(line)[0] == "install"]
        self.assertEqual(len(installs), 1)
        launcher = self.dest_path("cf")
        launcher.parent.mkdir(parents=True, exist_ok=True)
        launcher.write_text("keep")
        inst = self.make()
        with self.assertRaises(SkipInstall):
            inst.install_cf()
        self.assertEqual(launcher.read_text(), "keep")
        release_cache.seed(self.home / ".cache/usr/pi-releases")
        inst = self.make()
        inst.env["MOCK_NPM_FAIL"] = "1"
        with patch.object(pi_release.urllib.request, "urlopen", side_effect=AssertionError("network")):
            inst.install_pi()
            runtime = self.home / ".local/share/pi-runtime/current"
            self.assertTrue((runtime / "node_modules/@earendil-works/pi-coding-agent").is_dir())
            self.assertEqual(os.readlink(self.dest_path("pi")), str(runtime / "bin/pi"))
            self.assertTrue(self.state("pi").startswith("release:"))
            again = self.make()
            again.install_pi()
            self.assertFalse(again.changed)

    def test_pnpm_beside_polluted_home(self):
        home_bin = self.home / ".local/share/pnpm/bin"
        home_bin.mkdir(parents=True)
        (home_bin / "pn").write_text("#!/bin/sh\nexec pnpm \"$@\"\n")
        (home_bin / "pn").chmod(0o755)
        inst = self.make()
        inst.install_pnpm()
        self.assertEqual(os.readlink(self.dest_path("pnpm")), str(self.home / ".local/share/pnpm-npm/bin/pnpm"))
        self.assertEqual((home_bin / "pn").read_text(), "#!/bin/sh\nexec pnpm \"$@\"\n")

    def test_dsh_install_and_patch_repair(self):
        inst = self.make()
        inst.install_dsh()
        self.assertEqual(self.state("dsh"), "0.2.1")
        self.assertEqual(self.state("dsh-tui"), "0.16.0")
        patch_file = self.home / ".local/share/dsh/lib/node_modules/@deepseek-harness-tui/dsh-tui/cordis.patch.yml"
        patch_file.parent.mkdir(parents=True, exist_ok=True)
        patch_file.write_text("- id: tool-ralph\n  disabled: true\nkeep\n")
        inst = self.make()
        inst.repair_dsh_tui_patch()
        self.assertEqual(patch_file.read_text(), "keep\n")

    def test_codex_install_and_checksum(self):
        import hashlib
        target = "x86_64-unknown-linux-musl"
        asset = f"codex-{installer.CODEX_VERSION}-{target}.zip"
        url = f"{installer.MIRROR_BASE}/{asset}"
        payload = make_zip({"codex-package.json": b"{}", "bin/codex": b"c", "bin/codex-code-mode-host": b"m", "codex-path/rg": b"r"},
                           executable=("bin/codex", "bin/codex-code-mode-host", "codex-path/rg"))
        digest = hashlib.sha256(payload).hexdigest()
        routes = {url: payload}
        with patch.dict(installer.CODEX_MIRROR_SHA256, {target: digest}):
            inst = self.make(routes)
            inst.install_codex()
        self.assertTrue(self.dest_path("codex").is_symlink())
        bad = dict(routes)
        bad[url] = b"tampered"
        inst = self.make(bad)
        self.dest_path("codex").unlink(missing_ok=True)
        (self.home / ".local/state/dl/codex").unlink(missing_ok=True)
        import shutil as _shutil
        _shutil.rmtree(self.home / ".codex/packages/standalone/releases", ignore_errors=True)
        with patch.dict(installer.CODEX_MIRROR_SHA256, {target: digest}):
            with self.assertRaises(SkipInstall):
                inst.install_codex()

    def _bundle_routes(self, repo, tag, asset, payload, sums_asset=None, digest=None):
        import hashlib
        digest = digest or hashlib.sha256(payload).hexdigest()
        base = f"https://github.com/{repo}/releases/download/{tag}"
        routes = {f"https://github.com/{repo}/releases.atom": atom([("2024-01-01", tag)]),
                  f"{base}/{asset}": (payload, {"ETag": "e"}),
                  f"{base}/SHA256SUMS": f"{digest}  {sums_asset or asset}\n".encode()}
        return routes, base

    def _git_tar(self):
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w:xz") as archive:
            for name, mode in (("git", 0o755), ("git-shell", 0o755), ("git-submodule", 0o755),
                               ("git-sh-i18n--envsubst", 0o755), ("git-sh-setup", 0o644), ("git-sh-i18n", 0o644)):
                info = tarfile.TarInfo(name)
                info.size = 1
                info.mode = mode
                archive.addfile(info, io.BytesIO(b"g"))
            for helper in ("git-upload-archive", "git-upload-pack", "git-receive-pack", "git-submodule--helper"):
                info = tarfile.TarInfo(helper)
                info.type = tarfile.SYMTYPE
                info.linkname = "git"
                info.mode = 0o777
                archive.addfile(info)
        return buffer.getvalue()

    def _build_routes(self, repo, product, sha, payload, *, version, etag="e", manifest=None, listed=None, archive_fmt="tar.xz"):
        import hashlib
        triple = "x86_64-unknown-linux-musl"
        base = f"https://github.com/{repo}/releases/download/release-{sha}"
        archive = f"{product}-{version}-{triple}.{archive_fmt}"
        manifest_name = f"{product}-{version}-{triple}.manifest.json"
        body = json.dumps(manifest or {"schema_version": 1, "product": product, "version": version,
                                       "target": triple, "source_revision": sha}).encode()
        digest = listed or hashlib.sha256(payload).hexdigest()
        sums = f"{hashlib.sha256(body).hexdigest()}  {manifest_name}\n{digest}  {archive}\n".encode()
        return {f"{base}/{archive}": (payload, {"ETag": etag}), f"{base}/{manifest_name}": body,
                f"{base}/SHA256SUMS": sums,
                f"https://github.com/{repo}/releases.atom": atom([("2026-11-12T00:00:00Z", f"release-{sha}")])}

    def _git_routes(self, sha, payload, *, version="2.56.0", **kwargs):
        routes = self._build_routes("laputa-systems/git-build", "git", sha, payload, version=version, **kwargs)
        routes.pop("https://github.com/laputa-systems/git-build/releases.atom")
        return routes

    def test_git_bundle_install_current_and_unmanaged(self):
        old, new = "1" * 40, "2" * 40
        payload = self._git_tar()
        routes = self._git_routes(new, payload)
        old_base = f"https://github.com/laputa-systems/git-build/releases/download/release-{old}"
        routes[f"{old_base}/SHA256SUMS"] = f"{'b' * 64}  git-x86_64-unknown-linux-musl.zip\n".encode()
        feed = atom([("2026-11-09T08:06:37Z", f"release-{old}"), ("2026-11-12T18:37:58Z", f"release-{new}")])
        routes["https://github.com/laputa-systems/git-build/releases.atom"] = feed
        inst = self.make(routes)
        inst.install_git()
        self.assertTrue(self.dest_path("git").is_symlink())
        current = self.home / ".local/share/git/current"
        self.assertEqual(os.readlink(current).rsplit("/", 1)[1], f"release-{new}-x86_64-unknown-linux-musl")
        self.assertTrue((current / "git").is_file())
        self.assertTrue((current / "git-upload-pack").is_symlink())
        self.assertTrue((self.dest_path("git").parent.parent / "share/git-core/templates/info/exclude").is_file())
        inst = self.make(routes)
        inst.install_git()
        self.assertFalse(inst.changed)

    def _git_feed_routes(self, sha, payload, **kwargs):
        routes = self._git_routes(sha, payload, **kwargs)
        routes["https://github.com/laputa-systems/git-build/releases.atom"] = atom(
            [("2026-11-12T00:00:00Z", f"release-{sha}")])
        return routes

    def test_git_falls_back_past_a_release_without_supported_assets(self):
        newest, older = "3" * 40, "4" * 40
        routes = self._git_routes(older, self._git_tar())
        base = f"https://github.com/laputa-systems/git-build/releases/download/release-{newest}"
        routes[f"{base}/SHA256SUMS"] = f"{'b' * 64}  git-x86_64-unknown-linux-musl.tar.gz\n".encode()
        routes["https://github.com/laputa-systems/git-build/releases.atom"] = atom(
            [("2026-11-12T00:00:00Z", f"release-{newest}"), ("2026-11-01T00:00:00Z", f"release-{older}")])
        self.make(routes).install_git()
        self.assertIn(f"release-{older}", os.readlink(self.home / ".local/share/git/current"))

    def test_git_installs_zip_release(self):
        import io
        import zipfile
        sha = "5" * 40
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            for name, mode in (("git", 0o100755), ("git-shell", 0o100755), ("git-submodule", 0o100755),
                               ("git-sh-i18n--envsubst", 0o100755), ("git-sh-setup", 0o100644), ("git-sh-i18n", 0o100644)):
                info = zipfile.ZipInfo(name)
                info.create_system = 3
                info.external_attr = mode << 16
                archive.writestr(info, b"g")
            for helper in ("git-upload-archive", "git-upload-pack", "git-receive-pack", "git-submodule--helper"):
                info = zipfile.ZipInfo(helper)
                info.create_system = 3
                info.external_attr = 0o120777 << 16
                archive.writestr(info, b"git")
        payload = buffer.getvalue()
        routes = self._git_routes(sha, payload, version="2.56.0", archive_fmt="zip")
        routes["https://github.com/laputa-systems/git-build/releases.atom"] = atom(
            [("2026-11-12T00:00:00Z", f"release-{sha}")])
        inst = self.make(routes)
        inst.install_git()
        self.assertTrue(self.dest_path("git").is_symlink())
        self.assertEqual(os.readlink(self.home / ".local/share/git/current").rsplit("/", 1)[1], f"release-{sha}-x86_64-unknown-linux-musl")

    def test_git_rejects_manifest_for_another_revision(self):
        sha = "3" * 40
        routes = self._git_feed_routes(sha, self._git_tar(), manifest={
            "schema_version": 1, "product": "git", "version": "2.56.0",
            "target": "x86_64-unknown-linux-musl", "source_revision": "5" * 40})
        with self.assertRaises(SkipInstall):
            self.make(routes).install_git()
        self.assertFalse((self.home / ".local/share/git/current").exists())

    def test_git_rejects_archive_digest_mismatch(self):
        routes = self._git_feed_routes("3" * 40, self._git_tar(), listed="c" * 64)
        with self.assertRaises(SkipInstall):
            self.make(routes).install_git()
        self.assertFalse((self.home / ".local/share/git/current").exists())

    def test_release_tags_order_by_date_not_name(self):
        feed = atom([("2026-11-01T00:00:00Z", "release-ffff"), ("2026-11-12T00:00:00Z", "release-0000"),
                     ("2026-11-05T00:00:00Z", "v9"), ("2026-11-10T00:00:00Z", "release-8888")])
        inst = self.make({"https://x/feed": feed})
        self.assertEqual(inst.release_tags("https://x/feed", prefix="release-"),
                         ["release-0000", "release-8888", "release-ffff"])
        self.assertEqual(inst.latest_tag("https://x/feed"), "release-0000")
        self.assertEqual(inst.latest_tag("https://x/feed", exclude_prefix="release-"), "v9")

    def test_ssh_bundle_and_traversal_rejected(self):
        members = {name: b"x" for name in ("ssh", "ssh-keygen", "ssh-agent", "ssh-add", "sftp", "scp")}
        sha = "6" * 40
        routes = self._build_routes("laputa-systems/ssh-build", "ssh", sha, make_zip(members, executable=set(members)), version="10.6p1", archive_fmt="zip")
        inst = self.make(routes)
        inst.install_ssh()
        self.assertTrue(self.dest_path("ssh").is_symlink())
        self.assertTrue((self.home / ".local/share/ssh/current/ssh").is_file())
        sha = "7" * 40
        bad_payload = make_zip({"../evil": b"x", **members}, executable=set(members))
        routes = self._build_routes("laputa-systems/ssh-build", "ssh", sha, bad_payload, version="10.6p1", etag="e2", archive_fmt="zip")
        inst = self.make(routes)
        with self.assertRaises(SkipInstall):
            inst.install_ssh()

    def test_oxish_bundle(self):
        payload = make_zip({"bin/oxish-server": b"s", "bin/oxish-session": b"x", "LICENSE-MIT": b"l"},
                           executable={"bin/oxish-server", "bin/oxish-session"})
        sha = "8" * 40
        routes = self._build_routes("laputa-systems/ssh-build", "oxish", sha, payload, version="0.2.0", archive_fmt="zip")
        inst = self.make(routes)
        inst.install_oxish()
        self.assertTrue(self.dest_path("oxish-server").is_symlink())
        self.assertEqual(self.state("oxish-server"), "e")

    def test_gluon_bundle(self):
        members = {"meson": b"m", "ninja": b"n", "gluon-build": b"b"}
        payload = make_zip(members, executable=set(members))
        routes, base = self._bundle_routes("laputa-systems/gluon", "release-abc123", "gluon-x86_64-unknown-linux-musl.zip", payload)
        inst = self.make(routes)
        inst.install_gluon()
        for command in ("meson", "ninja", "gluon-build"):
            self.assertTrue(self.dest_path(command).is_symlink())
        self.assertTrue((self.home / ".local/share/gluon/current").is_symlink())
        self.assertEqual(self.state("gluon"), "e")

    def _bctl_release(self, tag, script):
        import hashlib
        triple = "x86_64-unknown-linux-musl"
        top = f"bctl-0.1.0-abc-{triple}"
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w:xz") as archive:
            for name in (top, f"{top}/bin"):
                info = tarfile.TarInfo(name)
                info.type = tarfile.DIRTYPE
                info.mode = 0o755
                archive.addfile(info)
            info = tarfile.TarInfo(f"{top}/bin/bctl")
            info.size = len(script)
            info.mode = 0o755
            archive.addfile(info, io.BytesIO(script))
        payload = buffer.getvalue()
        base = f"https://github.com/joshuarli/bctl/releases/download/{tag}"
        return {"https://github.com/joshuarli/bctl/releases.atom": atom([("2024-01-01", tag)]),
                f"{base}/{top}.tar.xz": (payload, {"ETag": tag}),
                f"{base}/SHA256SUMS-{triple}": f"{hashlib.sha256(payload).hexdigest()}  {top}.tar.xz\n".encode()}

    def test_bctl_installs_after_image_pull_and_doctor_pass(self):
        log = self.root / "bctl.log"
        routes = self._bctl_release("release-aaa", f"#!/bin/sh\necho \"$*\" >> {log}\n".encode())
        inst = self.make(routes)
        inst.install_bctl()
        self.assertEqual(log.read_text(), "image pull\ndoctor\n")
        link = self.dest_path("bctl")
        self.assertEqual(os.readlink(link), str(self.home / ".local/share/bctl/current/bin/bctl"))
        self.assertTrue((self.home / ".local/share/bctl/current/bin/bctl").is_file())

    def test_bctl_keeps_the_installed_release_when_image_pull_fails(self):
        self.make(self._bctl_release("release-aaa", b"#!/bin/sh\nexit 0\n")).install_bctl()
        current = self.home / ".local/share/bctl/current"
        before = os.readlink(current)
        with self.assertRaises(Exception):
            self.make(self._bctl_release("release-bbb", b"#!/bin/sh\n[ \"$1\" = image ] && exit 1\nexit 0\n")).install_bctl()
        self.assertEqual(os.readlink(current), before)
        self.assertEqual([p.name for p in (self.home / ".local/share/bctl/releases").iterdir() if not p.name.startswith(".")], ["release-aaa-x86_64-unknown-linux-musl"])

    def test_opencode2_zip_shim_and_current(self):
        import hashlib
        target = "linux-x64"
        asset = f"opencode-{installer.OPENCODE_VERSION}-{target}.zip"
        url = f"{installer.MIRROR_BASE}/{asset}"
        payload = make_zip({"opencode": b"binary"}, executable=("opencode",))
        digest = hashlib.sha256(payload).hexdigest()
        with patch.dict(installer.OPENCODE_MIRROR_SHA256, {target: digest}):
            inst = self.make({url: payload})
            inst.install_opencode2()
            self.assertEqual((self.home / ".opencode/bin/opencode").read_bytes(), b"binary")
            self.assertTrue(self.dest_path("opencode2").is_file())
            self.assertEqual(self.dest_path("opencode").read_text(), '#!/bin/sh\nexec "${HOME}/.opencode/bin/opencode" "$@"\n')
            inst = self.make({url: payload})
            inst.install_opencode2()
            self.assertFalse(inst.changed)

    def test_opencode2_alias_keeps_foreign_file(self):
        import hashlib
        target = "linux-x64"
        asset = f"opencode-{installer.OPENCODE_VERSION}-{target}.zip"
        url = f"{installer.MIRROR_BASE}/{asset}"
        payload = make_zip({"opencode": b"binary"}, executable=("opencode",))
        digest = hashlib.sha256(payload).hexdigest()
        inst = self.make({url: payload})
        foreign = self.dest_path("opencode")
        foreign.write_text("#!/bin/sh\necho foreign\n")
        foreign.chmod(0o755)
        with patch.dict(installer.OPENCODE_MIRROR_SHA256, {target: digest}):
            inst.install_opencode2()
        self.assertEqual(foreign.read_text(), "#!/bin/sh\necho foreign\n")

    def test_player_linux_and_ghostty_rejections(self):
        inst = self.make({}, os_name="darwin", arch="x86_64")
        with self.assertRaises(SkipInstall):
            inst.install_ghostty_custom()
        inst = self.make({}, os_name="linux", arch="aarch64")
        with self.assertRaises(SkipInstall):
            inst.install_player()

    def test_official_installers(self):
        import hashlib
        for tool, artifact, binary in (
                ("claude", "claude-install", "claude"),
                ("muse", "muse-install", "muse"),
                ("antigravity", "antigravity-install", "agy")):
            script = f"#!/bin/sh\nprintf '#!/bin/sh\\nexit 0\\n' > \"$HOME/.local/bin/{binary}\"\nchmod +x \"$HOME/.local/bin/{binary}\"\n"
            if tool == "antigravity":
                script += f"printf '#!/bin/sh\\nexit 0\\n' > \"$2/{binary}\"\nchmod +x \"$2/{binary}\"\n"
            payload = make_zip({"install.sh": script.encode()})
            digest = hashlib.sha256(payload).hexdigest()
            routes = {f"{installer.MIRROR_BASE}/{artifact}.zip": payload}
            with patch.dict(installer.INSTALL_SCRIPT_MIRROR_SHA256, {artifact: digest}):
                inst = self.make(routes)
                getattr(inst, f"install_{tool}")()
            self.assertTrue(self.dest_path(binary).is_file(), tool)

    def test_official_installer_checksum_mismatch_is_a_skip(self):
        payload = make_zip({"install.sh": b"#!/bin/sh\nexit 1\n"})
        inst = self.make({f"{installer.MIRROR_BASE}/claude-install.zip": payload})
        with self.assertRaises(SkipInstall) as ctx:
            inst.install_claude()
        self.assertIn("checksum mismatch", str(ctx.exception))
        self.assertFalse(self.dest_path("claude").exists())

    def test_default_tools_platforms_and_server(self):
        darwin = default_tools("darwin", "aarch64", "")
        self.assertIn("ffmpeg", darwin)
        self.assertIn("rimage", darwin)
        self.assertNotIn("rimage", default_tools("darwin", "x86_64", ""))
        self.assertIn("ghostty-custom", darwin)
        self.assertIn("jaq", darwin)
        linux_arm = default_tools("linux", "aarch64", "")
        self.assertNotIn("jaq", linux_arm)
        self.assertIn("mold", linux_arm)
        self.assertNotIn("player", linux_arm)
        self.assertIn("gluon", linux_arm)
        server_file = self.root / "server.txt"
        server_file.write_text("fd\nrg\n")
        self.assertEqual(default_tools("linux", "x86_64", "server", server_file), ["fd", "rg"])

    def test_record_managed_installs(self):
        inst = self.make()
        inst.install_cmd()
        launcher = self.dest_path("cmd")
        owned = self.root / "owned"
        owned.write_text("")
        fresh = self.make()
        fresh.record_managed_installs()
        lines = {f"{kind}\t{path}" for kind, path in fresh.claims}
        self.assertIn(f"F\t{launcher}", lines)
        self.assertIn(f"F\t{self.home}/.local/state/dl/cmd", lines)
        self.assertIn(f"D\t{self.home}/.local/share/command-code", lines)

    def test_cli_list_and_single_tool_claims(self):
        import subprocess
        env = dict(os.environ, HOME=str(self.home), PATH=f"{self.bin}:/usr/bin:/bin")
        result = subprocess.run([sys.executable, "-I", str(Path(__file__).parent / "installer.py"), "--list"],
                                env=env, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("fd", result.stdout.splitlines())
        self.assertIn("pnpm", result.stdout.splitlines())


if __name__ == "__main__":
    unittest.main()



if __name__ == "__main__":
    unittest.main()

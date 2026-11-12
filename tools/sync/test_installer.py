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
        self.script("node", "#!/bin/sh\nprintf '%s\\n' \"${MOCK_NODE_VERSION:-26.13.0}\"\n")
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
                   "cf@latest": "3.0.0", "agent-browser@latest": "2.0.0",
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

    def test_grok_keep_and_install(self):
        routes = {"https://x.ai/cli/stable": b"1.2.3\n",
                  "https://x.ai/cli/grok-1.2.3-linux-x86_64": (b"binary", {"ETag": "e"})}
        inst = self.make(routes)
        inst.install_grok()
        self.assertEqual(self.dest_path("grok").read_bytes() if False else (self.home / ".grok/downloads/grok-linux-x86_64").read_bytes(), b"binary")
        self.assertTrue((self.home / ".grok/bin/grok").is_symlink())
        self.assertEqual(self.state("grok"), "e")

    def _python_build_routes(self, tool, inner, repo, tag="20261101", triple="x86_64-unknown-linux-musl"):
        asset = f"python-{tag}-{triple}-install_only_stripped.tar.gz" if tool == "python3" else f"node-{tag}-{triple}-install_only_stripped.tar.gz"
        url = f"https://example.invalid/{asset}"
        payload = make_tar({inner: b"#!/bin/sh\nexit 0\n"})
        import hashlib
        digest = hashlib.sha256(payload).hexdigest()
        release = {"assets": [{"name": asset, "browser_download_url": url},
                              {"name": "SHA256SUMS", "browser_download_url": "https://example.invalid/sums"}]}
        routes = {f"https://github.com/{repo}/releases.atom": atom([("2024-01-01", tag)]),
                  f"https://api.github.com/repos/{repo}/releases/tags/{tag}": json.dumps(release).encode(),
                  url: (payload, {"ETag": "e"}),
                  "https://example.invalid/sums": f"{digest}  {asset}\n".encode()}
        return routes, url, asset

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

    def test_nodebuild_install(self):
        routes, url, asset = self._python_build_routes("node-build", "node/bin/node", "laputa-systems/node-build")
        inst = self.make(routes)
        inst.install_nodebuild()
        self.assertTrue(self.dest_path("node-build").is_symlink())

    def test_nodejs_checksum_mismatch_is_a_skip(self):
        inst = self.make({"https://nodejs.org/dist/v26.13.0/node-v26.13.0-darwin-arm64.tar.xz": b"not-the-pinned-build"},
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
        url = "https://nodejs.org/dist/v26.13.0/node-v26.13.0-darwin-arm64.tar.xz"
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
            for tool, body in (("node", "#!/bin/sh\nprintf '26.13.0\\n'\n"),
                               ("npm", "#!/bin/sh\nprintf '12.2.2\\n'\n"),
                               ("npx", "#!/bin/sh\nexit 0\n")):
                target = staged / "bin" / tool
                target.write_text(body)
                target.chmod(0o755)
            return True
        with patch.object(retry, "sha256_file", return_value="6f5b3187d9df9fc007e881167905bc7d69ad26450ddc377c83d63256a2495b6e"), \
             patch.object(retry, "tar_names", return_value=["root/bin/node"]), \
             patch.object(retry, "extract_tar", side_effect=extract):
            retry.install_nodejs()
        selected = Path(os.readlink(current))
        self.assertEqual(selected.name, "26.13.0-npm12.2.2-darwin-arm64")
        self.assertTrue((selected / "bin/node").is_file())
        self.assertFalse(release.exists())
        for tool in ("node", "npm", "npx"):
            self.assertEqual(os.readlink(self.dest_path(tool)), str(current / "bin" / tool))

    def test_nodejs_managed_uses_bundled_npm_without_registry(self):
        release = self.home / ".local/share/nodejs/26.13.0-npm12.2.2-darwin-arm64"
        cli_js = release / "lib/node_modules/npm/bin/npm-cli.js"
        cli_js.parent.mkdir(parents=True)
        cli_js.write_text(f"#!/bin/sh\nexec {self.bin / 'npm'} \"$@\"\n")
        cli_js.chmod(0o755)
        (release / "lib/node_modules/npm/lib").mkdir(parents=True)
        (release / "lib/node_modules/npm/lib/cli.js").write_text("")
        bin_dir = release / "bin"
        bin_dir.mkdir()
        (bin_dir / "node").write_text("#!/bin/sh\nprintf '26.13.0\\n'\n")
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
        release = self.home / ".local/share/nodejs/26.13.0-npm11.9.0-darwin-arm64"
        cli_js = release / "lib/node_modules/npm/bin/npm-cli.js"
        cli_js.parent.mkdir(parents=True)
        cli_js.write_text(f"#!/bin/sh\nexec {self.bin / 'npm'} \"$@\"\n")
        cli_js.chmod(0o755)
        (release / "lib/node_modules/npm/lib").mkdir(parents=True)
        (release / "lib/node_modules/npm/lib/cli.js").write_text("")
        bin_dir = release / "bin"
        bin_dir.mkdir()
        (bin_dir / "node").write_text("#!/bin/sh\nprintf '26.13.0\\n'\n")
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
        routes = {"https://nodejs.org/dist/v26.13.0/node-v26.13.0-darwin-arm64.tar.xz": b"not-the-pinned-build"}
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
        asset = f"codex-package-{target}.tar.gz"
        payload = make_tar({"codex-package.json": b"{}", "bin/codex": b"c", "bin/codex-code-mode-host": b"m", "codex-path/rg": b"r"})
        digest = hashlib.sha256(payload).hexdigest()
        url = f"https://releases.openai.com/codex/releases/{asset}"
        release = {"tag_name": "rust-v0.1.0", "assets": [{"name": asset, "browser_download_url": url, "digest": f"sha256:{digest}"}]}
        routes = {"https://releases.openai.com/codex/channels/latest": json.dumps(release).encode(),
                  url: (payload, {"ETag": "e"})}
        inst = self.make(routes)
        inst.install_codex()
        self.assertTrue(self.dest_path("codex").is_symlink())
        bad = dict(routes)
        bad[url] = (b"tampered", {"ETag": "e"})
        inst = self.make(bad)
        self.dest_path("codex").unlink(missing_ok=True)
        (self.home / ".local/state/dl/codex").unlink(missing_ok=True)
        import shutil as _shutil
        _shutil.rmtree(self.home / ".codex/packages/standalone/releases", ignore_errors=True)
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

    def test_git_bundle_install_current_and_unmanaged(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            for name in ("git", "git-shell", "git-submodule", "git-sh-i18n--envsubst"):
                info = zipfile.ZipInfo(name)
                info.create_system = 3
                info.external_attr = 0o100755 << 16
                archive.writestr(info, b"g")
            for name in ("git-sh-setup", "git-sh-i18n"):
                info = zipfile.ZipInfo(name)
                info.create_system = 3
                info.external_attr = 0o100644 << 16
                archive.writestr(info, b"s")
            for helper in ("git-upload-archive", "git-upload-pack", "git-receive-pack", "git-submodule--helper"):
                info = zipfile.ZipInfo(helper)
                info.create_system = 3
                info.external_attr = 0o120777 << 16
                archive.writestr(info, "git")
        payload = buffer.getvalue()
        routes, base = self._bundle_routes("laputa-systems/git-build", "v1", "git-x86_64-unknown-linux-musl.zip", payload)
        inst = self.make(routes)
        inst.install_git()
        self.assertTrue(self.dest_path("git").is_symlink())
        self.assertTrue((self.home / ".local/share/git/current").is_symlink())
        self.assertTrue((self.home / "share/git-core/templates/info/exclude") if False else (self.dest_path("git").parent.parent / "share/git-core/templates/info/exclude").is_file())
        routes2, _ = self._bundle_routes("laputa-systems/git-build", "v1", "git-x86_64-unknown-linux-musl.zip", payload)
        inst = self.make(routes2)
        inst.install_git()
        self.assertFalse(inst.changed)

    def test_ssh_bundle_and_traversal_rejected(self):
        members = {name: b"x" for name in ("ssh", "ssh-keygen", "ssh-agent", "ssh-add", "sftp", "scp")}
        payload = make_zip(members, executable=set(members))
        routes, base = self._bundle_routes("laputa-systems/ssh-build", "v1", "ssh-x86_64-unknown-linux-musl.zip", payload)
        inst = self.make(routes)
        inst.install_ssh()
        self.assertTrue(self.dest_path("ssh").is_symlink())
        bad_payload = make_zip({"../evil": b"x", **members})
        routes, base = self._bundle_routes("laputa-systems/ssh-build", "v2", "ssh-x86_64-unknown-linux-musl.zip", bad_payload)
        routes[f"{base}/ssh-x86_64-unknown-linux-musl.zip"] = (bad_payload, {"ETag": "e2"})
        inst = self.make(routes)
        with self.assertRaises(SkipInstall):
            inst.install_ssh()

    def test_oxish_bundle(self):
        payload = make_zip({"bin/oxish-server": b"s", "bin/oxish-session": b"x"}, executable={"bin/oxish-server", "bin/oxish-session"})
        routes, base = self._bundle_routes("laputa-systems/ssh-build", "v1", "oxish-x86_64-unknown-linux-musl.zip", payload)
        inst = self.make(routes)
        inst.install_oxish()
        self.assertTrue(self.dest_path("oxish-server").is_symlink())
        self.assertEqual(self.state("oxish-server"), "e")

    def test_gluon_bundle(self):
        members = {"meson": b"m", "ninja": b"n", "gluon-build": b"b"}
        payload = make_zip(members, executable=set(members))
        routes, base = self._bundle_routes("joshuarli/gluon", "release-abc123", "gluon-x86_64-unknown-linux-musl.zip", payload)
        inst = self.make(routes)
        inst.install_gluon()
        for command in ("meson", "ninja", "gluon-build"):
            self.assertTrue(self.dest_path(command).is_symlink())
        self.assertTrue((self.home / ".local/share/gluon/current").is_symlink())
        self.assertEqual(self.state("gluon"), "e")

    def test_opencode2_zip_shim_and_current(self):
        asset = "opencode-linux-x64.tar.gz"
        url = f"https://opencode.ai/update/api/latest/cli/opencode/{asset}"
        payload = make_tar({"opencode": b"binary"})
        inst = self.make({url: (payload, {"ETag": "e"})})
        inst.install_opencode2()
        self.assertEqual((self.home / ".opencode/bin/opencode").read_bytes(), b"binary")
        self.assertTrue(self.dest_path("opencode2").is_file())
        self.assertEqual(self.dest_path("opencode").read_text(), '#!/bin/sh\nexec "${HOME}/.opencode/bin/opencode" "$@"\n')
        inst = self.make({url: (payload, {"ETag": "e"})})
        inst.install_opencode2()
        self.assertFalse(inst.changed)

    def test_opencode2_alias_keeps_foreign_file(self):
        asset = "opencode-linux-x64.tar.gz"
        url = f"https://opencode.ai/update/api/latest/cli/opencode/{asset}"
        payload = make_tar({"opencode": b"binary"})
        inst = self.make({url: (payload, {"ETag": "e"})})
        foreign = self.dest_path("opencode")
        foreign.write_text("#!/bin/sh\necho foreign\n")
        foreign.chmod(0o755)
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
        for tool, url, binary in (
                ("claude", "https://claude.ai/install.sh", "claude"),
                ("muse", "https://dev.meta.ai/install.sh", "muse"),
                ("antigravity", "https://antigravity.google/cli/install.sh", "agy")):
            script = f"#!/bin/sh\nprintf '#!/bin/sh\\nexit 0\\n' > \"$HOME/.local/bin/{binary}\"\nchmod +x \"$HOME/.local/bin/{binary}\"\n"
            if tool == "antigravity":
                script += f"printf '#!/bin/sh\\nexit 0\\n' > \"$2/{binary}\"\nchmod +x \"$2/{binary}\"\n"
            inst = self.make({url: script.encode()})
            getattr(inst, f"install_{tool}")()
            self.assertTrue(self.dest_path(binary).is_file(), tool)

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

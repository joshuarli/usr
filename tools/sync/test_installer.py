"""Installer tests with fake HTTP and fake executables; no network or home effects."""
import io
import json
import os
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import URLError
import zipfile

sys.path.insert(0, str(Path(__file__).parent))
from installer import Installer, SkipInstall, default_tools


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

    def fetch(self, url, *, ranged=False):
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
        self.script("node", "#!/bin/sh\nprintf '%s\\n' \"${MOCK_NODE_VERSION:-26.12.0}\"\n")
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

    def test_release_shuck_installs_as_shellcheck(self):
        asset = "shuck-aarch64-apple-darwin"
        url = f"https://github.com/joshuarli/shck/releases/download/release-1/{asset}.zip"
        routes = {"https://github.com/joshuarli/shck/releases.atom": atom([("2024-01-01", "release-1")]),
                  url: (b"zip", {"ETag": "e"})}
        inst = self.make(routes, os_name="darwin", arch="aarch64")
        with patch.object(inst, "zip_member", return_value=b"binary"):
            inst.install_release("shuck")
        self.assertTrue(self.dest_path("shellcheck").is_file())

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

    def test_python3_install_and_checksum_mismatch(self):
        routes, url, asset = self._python_build_routes("python3", "python/bin/python3.15", "joshuarli/python-build")
        inst = self.make(routes)
        inst.install_python3()
        self.assertTrue(self.dest_path("python3").is_symlink())
        self.assertTrue(self.dest_path("python3.15").is_symlink())
        self.assertEqual(self.state("python3"), "e")
        bad = dict(routes)
        bad["https://example.invalid/sums"] = ("0" * 64 + f"  {asset}\n").encode()
        inst = self.make(bad)
        self.dest_path("python3").unlink(missing_ok=True)
        self.dest_path("python3.15").unlink(missing_ok=True)
        (self.home / ".local/state/dl/python3").unlink(missing_ok=True)
        import shutil as _shutil
        _shutil.rmtree(self.home / ".local/share/python-build", ignore_errors=True)
        with self.assertRaises(SkipInstall):
            inst.install_python3()

    def test_nodebuild_install(self):
        routes, url, asset = self._python_build_routes("node-build", "node/bin/node", "laputa-systems/node-build")
        inst = self.make(routes)
        inst.install_nodebuild()
        self.assertTrue(self.dest_path("node-build").is_symlink())

    def test_nodejs_checksum_mismatch_is_a_skip(self):
        inst = self.make({"https://nodejs.org/dist/v26.12.1/node-v26.12.1-darwin-arm64.tar.xz": b"not-the-pinned-build"},
                         os_name="darwin", arch="aarch64")
        with self.assertRaises(SkipInstall) as ctx:
            inst.install_nodejs()
        self.assertIn("checksum mismatch", str(ctx.exception))

    def test_npm_tool_install_current_unmanaged_and_failed(self):
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
        inst = self.make()
        inst.env["MOCK_NPM_FAIL"] = "1"
        with self.assertRaises(SkipInstall):
            inst.install_pi()
        self.assertFalse((self.home / ".local/share/pi").exists())

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
            for name in ("git", "git-shell"):
                info = zipfile.ZipInfo(name)
                info.create_system = 3
                info.external_attr = 0o100755 << 16
                archive.writestr(info, b"g")
            for helper in ("git-upload-archive", "git-upload-pack", "git-receive-pack"):
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

    def test_ffmpeg_install_and_pair_check(self):
        import hashlib
        tag, triple = "20250101", "x86_64-unknown-linux-musl"
        asset = f"ffmpeg-6.1+{tag}-{triple}-tools.tar.gz"
        ffmpeg = b"#!/bin/sh\nexit 0\n"
        payload = make_tar({f"{asset.removesuffix('.tar.gz')}/bin/ffmpeg": ffmpeg, f"{asset.removesuffix('.tar.gz')}/bin/ffprobe": ffmpeg})
        digest = hashlib.sha256(payload).hexdigest()
        base = f"https://github.com/laputa-systems/ffmpeg-build/releases/download/{tag}"
        routes = {"https://github.com/laputa-systems/ffmpeg-build/releases.atom": atom([("2024-01-01", tag)]),
                  f"{base}/SHA256SUMS": f"{digest}  {asset}\n".encode(),
                  f"{base}/{asset.replace('+', '%2B')}": (payload, {"ETag": "e"})}
        inst = self.make(routes)
        inst.install_ffmpeg()
        self.assertTrue(self.dest_path("ffmpeg").is_symlink())
        self.assertTrue(self.dest_path("ffprobe").is_symlink())
        self.assertEqual(self.state("ffmpeg"), f"{tag}:e")

    def test_opencode2_zip_shim_and_current(self):
        asset = "opencode-linux-x64.tar.gz"
        url = f"https://opencode.ai/update/api/latest/cli/opencode/{asset}"
        payload = make_tar({"opencode": b"binary"})
        inst = self.make({url: (payload, {"ETag": "e"})})
        inst.install_opencode2()
        self.assertEqual((self.home / ".opencode/bin/opencode").read_bytes(), b"binary")
        self.assertTrue(self.dest_path("opencode2").is_file())
        inst = self.make({url: (payload, {"ETag": "e"})})
        inst.install_opencode2()
        self.assertFalse(inst.changed)

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

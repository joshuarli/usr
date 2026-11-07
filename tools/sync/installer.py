"""Leaf tool installer: downloads, checksums, and per-tool install quirks.

This module is the Python successor of the former install.sh. Python owns
scheduling and ownership; each function here installs exactly one tool into
its disjoint prefix, launcher, and state file, and reports the paths it owns
as claims for main.py to merge under the ownership lease.

A skip is a failed install for this tool (SkipInstall); an unchecked
discovery failure keeps an already-installed tool and only warns, matching
the shell installer's contract.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from urllib.error import URLError
from urllib.request import Request, urlopen
import zipfile

NODE_MINIMUM = "26.12.0"
NODEJS_VERSION = "26.12.1"
FFMPEG_REPO = "laputa-systems/ffmpeg-build"
PLAYER_REPO = "joshuarli/play"
MUSE_LAUNCHER_URL = "https://dev.meta.ai/install.sh"
GHOSTTY_CUSTOM_ASSET = "Ghostty-Custom-aarch64-apple-darwin.dmg"
GHOSTTY_CUSTOM_BUNDLE_ID = "com.joshuarli.ghostty-custom"
SSH_COMMANDS = "ssh ssh-keygen ssh-agent ssh-add sftp scp".split()
OXISH_COMMANDS = "oxish-server oxish-session".split()
FFMPEG_COMMANDS = "ffmpeg ffprobe".split()
GIT_COMMANDS = "git git-shell git-upload-archive git-upload-pack git-receive-pack".split()


class InstallError(Exception):
    pass


class SkipInstall(InstallError):
    def __init__(self, tool: str, reason: str):
        super().__init__(f"{tool}: {reason}")
        self.tool = tool
        self.reason = reason


def _uname() -> tuple[str, str]:
    os_name = platform.system().lower()
    arch = platform.machine()
    if arch == "arm64":
        arch = "aarch64"
    return os_name, arch


def version_at_least(have: str, need: str) -> bool:
    def parts(value: str) -> list[int]:
        result = []
        for part in value.split("."):
            result.append(int(part) if part.isdigit() else 0)
        return result

    have_parts, need_parts = parts(have), parts(need)
    width = max(len(have_parts), len(need_parts))
    have_parts += [0] * (width - len(have_parts))
    need_parts += [0] * (width - len(need_parts))
    return have_parts >= need_parts


def python_build_pin(pin_path: Path | None = None) -> tuple[str, str, dict[str, tuple[str, str]]]:
    path = pin_path or Path(__file__).with_name("python-build.pin")
    tag = repo = ""
    triples: dict[str, tuple[str, str]] = {}
    for line in path.read_text().splitlines():
        fields = line.split()
        if not fields or line.startswith("#"):
            continue
        if not tag:
            tag, repo = fields[0], fields[1] if len(fields) > 1 else ""
        elif len(fields) == 3:
            triples[fields[0]] = (fields[1], fields[2])
    return tag, repo, triples


_ENTRY = re.compile(r"<entry>(.*?)</entry>", re.S)
_UPDATED = re.compile(r"<updated>([^<]+)</updated>")
_TAG_LINK = re.compile(r"releases/tag/([^\"']+)\"")
_FFMPEG_TAG = re.compile(r"^(\d{8})(?:-r(\d+))?$")


class Installer:
    def __init__(self, home: Path, *, os_name: str | None = None, arch: str | None = None,
                 env: dict[str, str] | None = None):
        self.home = Path(home)
        self.env = dict(os.environ if env is None else env)
        self.env.setdefault("HOME", str(self.home))
        self.os_name, self.arch = _uname() if os_name is None else (os_name, arch or _uname()[1])
        self.data_home = Path(self.env.get("XDG_DATA_HOME") or self.home / ".local/share")
        self.state_home = Path(self.env.get("XDG_STATE_HOME") or self.home / ".local/state")
        self.dest = self.home / ".local/bin"
        self.state = self.state_home / "dl"
        self.claude_versions = self.data_home / "claude/versions"
        self.dsh_root = self.data_home / "dsh"
        self.codex_home = Path(self.env.get("CODEX_HOME") or self.home / ".codex")
        self.codex_legacy_root = self.data_home / "codex"
        self.git_home = Path(self.env.get("GIT_HOME") or self.data_home / "git")
        self.ssh_home = Path(self.env.get("SSH_HOME") or self.data_home / "ssh")
        self.ffmpeg_home = Path(self.env.get("FFMPEG_HOME") or self.data_home / "ffmpeg")
        self.oxish_home = Path(self.env.get("OXISH_HOME") or self.data_home / "oxish")
        self.grok_home = Path(self.env.get("GROK_HOME") or self.home / ".grok")
        self.opencode2_home = Path(self.env.get("OPENCODE2_HOME") or self.home / ".opencode")
        self.cmd_root = self.data_home / "command-code"
        self.pi_root = self.data_home / "pi"
        self.python_build_root = self.data_home / "python-build"
        self.node_build_root = self.data_home / "node-build"
        self.nodejs_root = self.data_home / "nodejs"
        self.pnpm_root = self.data_home / "pnpm-npm"
        self.cf_root = self.data_home / "cf"
        self.agent_browser_root = self.data_home / "agent-browser"
        self.ghostty_apps = Path(self.env.get("GHOSTTY_APPLICATIONS_DIR") or "/Applications")
        self.ghostty_app = self.ghostty_apps / "Ghostty Custom.app"
        self.ghostty_exec = self.ghostty_app / "Contents/MacOS/ghostty"
        self.player_apps = Path(self.env.get("PLAYER_APPLICATIONS_DIR") or self.home / "Applications")
        self.player_app = self.player_apps / "Player.app"
        self.player_exec = self.player_app / "Contents/MacOS/player"
        self.claims: list[tuple[str, Path]] = []
        self.removed: set[Path] = set()
        self.changed = False
        color_setting = self.env.get("DL_COLOR", "auto")
        self.color = color_setting in ("1", "true", "yes", "always") or (
            color_setting == "auto" and "NO_COLOR" not in self.env and sys.stdout.isatty())
        self._path = self._build_path()
        self.own_missing_dirs(self.dest)
        self.dest.mkdir(parents=True, exist_ok=True)
        self.own_missing_dirs(self.state)
        self.state.mkdir(parents=True, exist_ok=True)

    def _build_path(self) -> str:
        managed = self.nodejs_root / "current/bin"
        if (managed / "node").is_file() and os.access(managed / "node", os.X_OK):
            return str(managed) + os.pathsep + self.env.get("PATH", "")
        return self.env.get("PATH", "")

    def run(self, argv: list[str], *, check: bool = False, capture: bool = False,
            extra_env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        env = dict(self.env)
        env["PATH"] = self._path
        env.update(extra_env or {})
        result = subprocess.run(argv, env=env, text=True, capture_output=capture)
        if check and result.returncode:
            raise InstallError(f"command failed ({result.returncode}): {' '.join(argv)}")
        return result

    def which(self, name: str) -> str | None:
        return shutil.which(name, path=self._path)

    def ok(self, message: str) -> None:
        print(f"\033[32m✓ {message}\033[0m" if self.color else f"✓ {message}")

    def current(self, message: str) -> None:
        print(f"\033[2m· {message}\033[0m" if self.color else f"· {message}")

    def fetch_msg(self, message: str) -> None:
        print(f"\033[34m↓ {message}\033[0m" if self.color else f"↓ {message}")

    def warn(self, message: str) -> None:
        print(f"\033[33m! {message}\033[0m" if self.color else f"! {message}", file=sys.stderr)

    def fail(self, message: str) -> None:
        print(f"\033[31m✗ {message}\033[0m" if self.color else f"✗ {message}", file=sys.stderr)

    def skip(self, tool: str, reason: str) -> None:
        self.fail(f"Skipping {tool}: {reason}")
        raise SkipInstall(tool, reason)

    def unchecked(self, tool: str, reason: str) -> None:
        if self.installed(tool):
            self.warn(f"Warning: keeping installed {tool} ({reason}; will retry next run)")
        else:
            self.skip(tool, reason)

    def own_file(self, path: Path) -> None:
        self.claims.append(("F", Path(path)))

    def own_dir(self, path: Path) -> None:
        self.claims.append(("D", Path(path)))

    def own_empty_dir(self, path: Path) -> None:
        self.claims.append(("E", Path(path)))

    def own_missing_dirs(self, path: Path) -> None:
        path = Path(path)
        if path.is_dir():
            return
        self.own_empty_dir(path)
        parent = path.parent
        if parent != path:
            self.own_missing_dirs(parent)

    def installed(self, name: str) -> bool:
        launcher = self.dest / name
        return launcher.is_file() or (launcher.exists() and not launcher.is_dir())

    def is_current(self, name: str, record: str) -> bool:
        if self.installed(name) and self._state_text(name) == record:
            self.own_file(self.dest / name)
            self.own_file(self.state / name)
            return True
        return False

    def _state_text(self, name: str) -> str:
        try:
            return (self.state / name).read_text().rstrip("\n")
        except OSError:
            return ""

    def write_state(self, name: str, value: str) -> None:
        (self.state / name).write_text(value + "\n")
        self.own_file(self.state / name)

    def keep_installed(self, name: str) -> bool:
        if self.installed(name):
            self.current(f"{name} is installed")
            return True
        return False

    def file_type(self, path: Path) -> str:
        if not self.which("file"):
            return ""
        result = self.run(["file", "-b", str(path)], capture=True)
        return result.stdout.strip() if result.returncode == 0 else ""

    def legacy_binary(self, name: str) -> bool:
        launcher = self.dest / name
        if launcher.is_symlink() or not launcher.is_file() or not (self.state / name).is_file():
            return False
        return self.file_type(launcher).startswith(("Mach-O ", "ELF "))

    def fetch(self, url: str, *, ranged: bool = False) -> tuple[bytes, dict[str, str]]:
        headers = {"User-Agent": "usr-sync"}
        if ranged:
            headers["Range"] = "bytes=0-0"
        request = Request(url, headers=headers)
        with urlopen(request) as response:
            return response.read(), {key: value for key, value in response.headers.items()}

    def effective_url(self, url: str) -> str:
        try:
            with urlopen(Request(url, headers={"User-Agent": "usr-sync"})) as response:
                return response.geturl()
        except (URLError, OSError, ValueError):
            return ""

    def fetch_text(self, url: str) -> str:
        try:
            body, _ = self.fetch(url)
        except (URLError, OSError, ValueError):
            return ""
        return body.decode("utf-8", "replace")

    def download(self, url: str, target: Path) -> bool:
        try:
            body, _ = self.fetch(url)
        except (URLError, OSError, ValueError):
            return False
        Path(target).write_bytes(body)
        return True

    def download_text(self, url: str, target: Path) -> bool:
        try:
            body, _ = self.fetch(url)
        except (URLError, OSError, ValueError):
            return False
        Path(target).write_bytes(body)
        return True

    def asset_id(self, url: str) -> str:
        try:
            _, headers = self.fetch(url, ranged=True)
        except (URLError, OSError, ValueError):
            return ""
        for key, value in headers.items():
            if key.lower() == "etag":
                return value.strip()
        return ""

    def latest_tag(self, feed_url: str, *, prefix: str = "", exclude_prefix: str = "") -> str:
        text = self.fetch_text(feed_url)
        newest_updated = ""
        newest_tag = ""
        for entry in _ENTRY.findall(text):
            updated_match = _UPDATED.search(entry)
            tag_match = _TAG_LINK.search(entry)
            if not updated_match or not tag_match:
                continue
            tag = tag_match.group(1)
            if prefix and not tag.startswith(prefix):
                continue
            if exclude_prefix and tag.startswith(exclude_prefix):
                continue
            if updated_match.group(1) > newest_updated:
                newest_updated = updated_match.group(1)
                newest_tag = tag
        return newest_tag

    def latest_date_tag(self, feed_url: str) -> str:
        text = self.fetch_text(feed_url)
        newest_key = ""
        newest_tag = ""
        for entry in _ENTRY.findall(text):
            tag_match = _TAG_LINK.search(entry)
            if not tag_match:
                continue
            tag = tag_match.group(1)
            date_match = _FFMPEG_TAG.match(tag)
            if not date_match:
                continue
            key = date_match.group(1) + (date_match.group(2) or "0").zfill(6)
            if key > newest_key:
                newest_key = key
                newest_tag = tag
        return newest_tag

    def fetch_json(self, url: str) -> dict:
        text = self.fetch_text(url)
        try:
            value = json.loads(text)
        except ValueError:
            return {}
        return value if isinstance(value, dict) else {}

    @staticmethod
    def sha256_file(path: Path) -> str:
        digest = hashlib.sha256()
        with Path(path).open("rb") as stream:
            for part in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(part)
        return digest.hexdigest()

    def sums_for(self, sums_text: str, asset: str) -> str:
        for line in sums_text.splitlines():
            fields = line.split()
            if len(fields) == 2 and fields[1] == asset:
                return fields[0]
        return ""

    @staticmethod
    def archive_paths_bad(names: list[str]) -> bool:
        for name in names:
            if name.startswith("/") or ".." in name.split("/"):
                return True
        return False

    def zip_names(self, path: Path) -> list[str] | None:
        try:
            with zipfile.ZipFile(path) as archive:
                return archive.namelist()
        except (zipfile.BadZipFile, OSError):
            return None

    def zip_member(self, path: Path, member: str) -> bytes | None:
        try:
            with zipfile.ZipFile(path) as archive:
                return archive.read(member)
        except (KeyError, zipfile.BadZipFile, OSError):
            return None

    def extract_zip(self, path: Path, target: Path) -> bool:
        names = self.zip_names(path)
        if names is None or self.archive_paths_bad(names):
            return False
        try:
            with zipfile.ZipFile(path) as archive:
                for info in archive.infolist():
                    dest_path = Path(target) / info.filename
                    mode = (info.external_attr >> 16) & 0o7777
                    if info.is_dir():
                        dest_path.mkdir(parents=True, exist_ok=True)
                        continue
                    dest_path.parent.mkdir(parents=True, exist_ok=True)
                    if (info.external_attr >> 16) & 0o170000 == 0o120000:
                        dest_path.symlink_to(archive.read(info.filename).decode())
                        continue
                    dest_path.write_bytes(archive.read(info.filename))
                    if mode:
                        dest_path.chmod(mode)
        except (zipfile.BadZipFile, OSError, RuntimeError):
            return False
        return True

    def tar_names(self, path: Path) -> list[str] | None:
        try:
            with tarfile.open(path, "r:*") as archive:
                return archive.getnames()
        except (tarfile.TarError, OSError):
            return None

    def tar_member(self, path: Path, member: str) -> bytes | None:
        try:
            with tarfile.open(path, "r:*") as archive:
                extracted = archive.extractfile(member)
                return extracted.read() if extracted is not None else None
        except (KeyError, tarfile.TarError, OSError):
            return None

    def tar_members(self, path: Path) -> list[tarfile.TarInfo] | None:
        try:
            with tarfile.open(path, "r:*") as archive:
                return archive.getmembers()
        except (tarfile.TarError, OSError):
            return None

    def extract_tar(self, path: Path, target: Path, *, strip: int = 0) -> bool:
        names = self.tar_names(path)
        if names is None or self.archive_paths_bad(names):
            return False
        try:
            with tarfile.open(path, "r:*") as archive:
                try:
                    archive.extractall(target, filter="data")
                except TypeError:
                    if strip:
                        return False
                    archive.extractall(target)
        except (tarfile.TarError, OSError):
            return False
        if strip:
            staged = Path(target)
            children = list(staged.iterdir())
            if len(children) != 1:
                return False
            top = children[0]
            if not top.is_dir():
                return False
            for child in list(top.iterdir()):
                os.replace(child, staged / child.name)
            top.rmdir()
        return True

    def install_binary(self, name: str, staged: Path, record: str) -> None:
        if self.os_name == "darwin":
            self.run(["xattr", "-d", "com.apple.quarantine", str(staged)])
            self.run(["codesign", "-fs", "-", str(staged)], check=True)
        staged.chmod(staged.stat().st_mode | 0o111)
        os.replace(staged, self.dest / name)
        self.own_file(self.dest / name)
        self.write_state(name, record)
        self.changed = True
        self.ok(f"Installed {self.dest / name}")

    def link_symlink(self, link: Path, target: str) -> None:
        fd, tmp = tempfile.mkstemp(prefix=f".{link.name}.", dir=link.parent)
        os.close(fd)
        os.unlink(tmp)
        try:
            os.symlink(target, tmp)
            os.replace(tmp, link)
        finally:
            if os.path.lexists(tmp):
                os.unlink(tmp)
        self.own_file(link)

    def switch_symlink(self, target: Path, link: Path) -> bool:
        fd, tmp = tempfile.mkstemp(prefix=f".{link.name}.", dir=link.parent)
        os.close(fd)
        os.unlink(tmp)
        try:
            os.symlink(str(target), tmp)
            os.replace(tmp, link)
        except OSError:
            if os.path.lexists(tmp):
                os.unlink(tmp)
            return False
        return True

    def stage_file(self, directory: Path, prefix: str) -> Path:
        fd, path = tempfile.mkstemp(prefix=prefix, dir=directory)
        os.close(fd)
        return Path(path)

    def stage_dir(self, parent: Path, prefix: str) -> Path:
        return Path(tempfile.mkdtemp(prefix=prefix, dir=parent))

    def node_meets_minimum(self) -> bool:
        if not self.which("node"):
            return False
        result = self.run(["node", "-p", "process.versions.node"], capture=True)
        return result.returncode == 0 and version_at_least(result.stdout.strip(), NODE_MINIMUM)

    def npm_view(self, spec: str) -> str:
        if not self.which("npm"):
            return ""
        result = self.run(["npm", "view", spec, "version"], capture=True)
        return result.stdout.strip() if result.returncode == 0 else ""

    def npm_install(self, prefix: Path, spec: str, *flags: str) -> bool:
        result = self.run(["npm", "install", "--global", *flags, "--prefix", str(prefix), spec])
        return result.returncode == 0

    def valid_version(self, version: str) -> bool:
        return re.match(r"^\d+\.\d+\.\d+([.-][A-Za-z0-9.-]+)?$", version) is not None

    def install_direct(self, name: str, url: str) -> None:
        record = self.asset_id(url)
        if not record:
            self.unchecked(name, f"{url} is unreachable")
            return
        if self.is_current(name, record):
            self.current(f"{name} is current")
            return
        self.fetch_msg(f"Downloading {name} ...")
        staged = self.stage_file(self.dest, f".{name}.")
        if not self.download(url, staged):
            staged.unlink(missing_ok=True)
            self.skip(name, "download failed")
        self.install_binary(name, staged, record)

    def install_release(self, prog: str) -> None:
        owners = {
            **{name: "laputa-systems" for name in
               ("e", "fz", "fdu", "fastermod", "tm", "fs", "srv", "diff-pretty", "vault", "rage")},
            **{name: "joshuarli" for name in ("ish", "stuff", "mactop", "gh", "syncthing", "soulseek-rs")},
            "bylaws": "joshuarli",
            "shuck": "joshuarli",
        }
        if prog not in owners:
            self.skip(prog, "unknown tool")
        owner = owners[prog]
        repo = {"bylaws": "swift-bylaws", "shuck": "shck"}.get(prog, prog)
        install_name = "shellcheck" if prog == "shuck" else prog
        tag_prefix = "release-" if prog in ("vault", "syncthing", "shuck") else ""
        tag = self.latest_tag(f"https://github.com/{owner}/{repo}/releases.atom", prefix=tag_prefix)
        if not tag:
            self.unchecked(prog, "no release found")
            return
        if self.os_name == "linux" and prog in ("ish", "rage", "soulseek-rs", "shuck"):
            artifact_target = f"{self.arch}-unknown-linux-musl-static"
        elif self.os_name == "linux" and prog in (
                "e", "fz", "fdu", "fastermod", "tm", "fs", "srv", "diff-pretty",
                "vault", "syncthing", "stuff", "gh"):
            artifact_target = f"{self.arch}-unknown-linux-musl"
        elif self.os_name == "linux":
            artifact_target = f"{self.arch}-unknown-linux-gnu"
        else:
            artifact_target = f"{self.arch}-apple-darwin"
        asset_base = f"{prog}-{artifact_target}"
        candidates = [asset_base]
        if self.os_name == "linux" and artifact_target.endswith("musl") \
                and prog not in ("ish", "soulseek-rs", "shuck"):
            candidates.append(asset_base + "-static")
        asset = ""
        url = ""
        record = ""
        for candidate in candidates:
            candidate_url = f"https://github.com/{owner}/{repo}/releases/download/{tag}/{candidate}.zip"
            candidate_id = self.asset_id(candidate_url)
            if candidate_id:
                asset, url, record = candidate, candidate_url, candidate_id
                break
        if not asset:
            self.unchecked(prog, f"{asset_base}.zip is not available in {tag}")
            return
        asset_inner = prog if prog == "bylaws" else asset
        if self.is_current(install_name, record):
            self.current(f"{install_name} is current ({tag})")
            return
        self.fetch_msg(f"Downloading {asset}.zip ...")
        with tempfile.NamedTemporaryFile(delete=False) as stream:
            archive_path = Path(stream.name)
        if not self.download(url, archive_path):
            archive_path.unlink(missing_ok=True)
            self.skip(prog, f"{asset}.zip is not available in {tag}")
        staged = self.stage_file(self.dest, f".{install_name}.")
        member = self.zip_member(archive_path, asset_inner)
        archive_path.unlink(missing_ok=True)
        if member is None:
            staged.unlink(missing_ok=True)
            self.skip(prog, f"{asset}.zip does not contain {asset_inner}")
        staged.write_bytes(member)
        self.install_binary(install_name, staged, record)
        if prog == "rage":
            rage_keygen = self.dest / "rage-keygen"
            if rage_keygen.is_symlink() or rage_keygen.exists():
                rage_keygen.unlink()
            rage_keygen.symlink_to("rage")
            self.own_file(rage_keygen)

    def install_zzz(self) -> None:
        if (self.os_name, self.arch) not in (("linux", "x86_64"), ("linux", "aarch64")):
            self.skip("zzz", "only Linux x86_64 and aarch64 musl static releases are published")
        tag = self.latest_tag("https://github.com/laputa-systems/zzz/releases.atom", prefix="release-")
        if not tag:
            self.unchecked("zzz", "no release found")
            return
        asset = f"zzz-linux-musl-static-{self.arch}"
        url = f"https://github.com/laputa-systems/zzz/releases/download/{tag}/{asset}"
        record = self.asset_id(url)
        if not record:
            self.unchecked("zzz", f"{asset} is unavailable")
            return
        if self.is_current("zzz", record):
            self.current(f"zzz is current ({tag})")
            return
        self.fetch_msg(f"Downloading {asset} ...")
        staged = self.stage_file(self.dest, ".zzz.")
        if not self.download(url, staged):
            staged.unlink(missing_ok=True)
            self.skip("zzz", f"{asset} download failed")
        self.install_binary("zzz", staged, record)

    def install_fd_or_rg(self, prog: str) -> None:
        owner, project = {"fd": ("sharkdp", "fd"), "rg": ("BurntSushi", "ripgrep")}[prog]
        if (self.os_name, self.arch) == ("linux", "x86_64") or (self.os_name, self.arch) == ("linux", "aarch64"):
            artifact_target = f"{self.arch}-unknown-linux-musl"
        elif (self.os_name, self.arch) in (("darwin", "x86_64"), ("darwin", "aarch64")):
            artifact_target = f"{self.arch}-apple-darwin"
        else:
            self.skip(prog, f"no upstream release for {self.os_name}/{self.arch}")
        latest_url = self.effective_url(f"https://github.com/{owner}/{project}/releases/latest")
        tag_match = re.search(r"/releases/tag/([^/]+)$", latest_url)
        tag = tag_match.group(1) if tag_match else ""
        if not tag:
            self.unchecked(prog, "no upstream release found")
            return
        asset = f"{project}-{tag}-{artifact_target}"
        url = f"https://github.com/{owner}/{project}/releases/download/{tag}/{asset}.tar.gz"
        record = self.asset_id(url)
        if not record:
            self.unchecked(prog, f"{asset}.tar.gz is not available in {tag}")
            return
        if self.is_current(prog, record):
            self.current(f"{prog} is current ({tag})")
            return
        self.fetch_msg(f"Downloading {asset}.tar.gz ...")
        with tempfile.NamedTemporaryFile(delete=False) as stream:
            archive_path = Path(stream.name)
        if not self.download(url, archive_path):
            archive_path.unlink(missing_ok=True)
            self.skip(prog, f"{asset}.tar.gz is not available in {tag}")
        staged = self.stage_file(self.dest, f".{prog}.")
        member = self.tar_member(archive_path, f"{asset}/{prog}")
        archive_path.unlink(missing_ok=True)
        if member is None:
            staged.unlink(missing_ok=True)
            self.skip(prog, f"{asset}.tar.gz does not contain {prog}")
        staged.write_bytes(member)
        self.install_binary(prog, staged, record)

    def install_mold(self) -> None:
        if (self.os_name, self.arch) not in (("linux", "x86_64"), ("linux", "aarch64")):
            self.skip("mold", "only x86_64 and aarch64 Linux are published")
        tag = ""
        for entry in _ENTRY.findall(self.fetch_text("https://github.com/joshuarli/mold/releases.atom")):
            tag_match = _TAG_LINK.search(entry)
            if tag_match and tag_match.group(1).startswith("mold-musl-"):
                tag = tag_match.group(1)
                break
        if not tag:
            self.unchecked("mold", "no release found")
            return
        version = tag.removeprefix("mold-musl-").rsplit("-", 1)[0]
        asset = f"mold-{version}-{self.arch}-linux-musl"
        url = f"https://github.com/joshuarli/mold/releases/download/{tag}/{asset}.tar.gz"
        record = self.asset_id(url)
        if not record:
            self.unchecked("mold", f"{asset}.tar.gz is not available in {tag}")
            return
        ld_mold = self.dest / "ld.mold"
        if self.is_current("mold", record) and ld_mold.is_symlink() \
                and os.readlink(ld_mold) == "mold":
            self.own_file(ld_mold)
            self.current(f"mold is current ({tag})")
            return
        self.fetch_msg(f"Downloading {asset}.tar.gz ...")
        with tempfile.NamedTemporaryFile(delete=False) as stream:
            archive_path = Path(stream.name)
        if not self.download(url, archive_path):
            archive_path.unlink(missing_ok=True)
            self.skip("mold", f"{asset}.tar.gz is not available in {tag}")
        staged = self.stage_file(self.dest, ".mold.")
        member = self.tar_member(archive_path, f"{asset}/bin/mold")
        archive_path.unlink(missing_ok=True)
        if member is None:
            staged.unlink(missing_ok=True)
            self.skip("mold", f"{asset}.tar.gz does not contain bin/mold")
        staged.write_bytes(member)
        self.install_binary("mold", staged, record)
        if ld_mold.is_symlink() or ld_mold.exists():
            ld_mold.unlink()
        ld_mold.symlink_to("mold")
        self.own_file(ld_mold)

    def install_jaq(self) -> None:
        if (self.os_name, self.arch) == ("linux", "x86_64"):
            target = "x86_64-unknown-linux-musl"
        elif (self.os_name, self.arch) == ("linux", "aarch64"):
            self.skip("jaq", "no musl release for aarch64; install jq instead")
        elif self.os_name == "linux":
            target = f"{self.arch}-unknown-linux-gnu"
        else:
            target = f"{self.arch}-apple-darwin"
        self.install_direct("jaq", f"https://github.com/01mf02/jaq/releases/latest/download/jaq-{target}")

    def install_uv(self) -> None:
        if (self.os_name, self.arch) in (("darwin", "x86_64"), ("darwin", "aarch64")):
            target = f"{self.arch}-apple-darwin"
        elif (self.os_name, self.arch) in (("linux", "x86_64"), ("linux", "aarch64")):
            target = f"{self.arch}-unknown-linux-musl"
        else:
            self.skip("uv", f"no upstream release for {self.os_name}/{self.arch}")
        tag = self.latest_tag("https://github.com/astral-sh/uv/releases.atom")
        if not tag:
            self.unchecked("uv", "no release found")
            return
        asset = f"uv-{target}"
        url = f"https://github.com/astral-sh/uv/releases/download/{tag}/{asset}.tar.gz"
        record = self.asset_id(url)
        if not record:
            self.unchecked("uv", f"{asset}.tar.gz is not available in {tag}")
            return
        if self.is_current("uv", record) and self.is_current("uvx", record):
            self.current(f"uv is current ({tag})")
            return
        self.fetch_msg(f"Downloading {asset}.tar.gz ...")
        with tempfile.NamedTemporaryFile(delete=False) as stream:
            archive_path = Path(stream.name)
        if not self.download(url, archive_path):
            archive_path.unlink(missing_ok=True)
            self.skip("uv", "download failed")
        sums_path = Path(tempfile.mkstemp()[1])
        if not self.download(url + ".sha256", sums_path):
            archive_path.unlink(missing_ok=True)
            sums_path.unlink(missing_ok=True)
            self.skip("uv", "checksum download failed")
        expected = self.sums_for(sums_path.read_text(), f"{asset}.tar.gz")
        sums_path.unlink(missing_ok=True)
        if len(expected) != 64 or self.sha256_file(archive_path) != expected:
            archive_path.unlink(missing_ok=True)
            self.skip("uv", "checksum mismatch")
        for command in ("uv", "uvx"):
            staged = self.stage_file(self.dest, f".{command}.")
            member = self.tar_member(archive_path, f"{asset}/{command}")
            if member is None:
                archive_path.unlink(missing_ok=True)
                staged.unlink(missing_ok=True)
                self.skip("uv", f"{asset}.tar.gz does not contain {command}")
            staged.write_bytes(member)
            self.install_binary(command, staged, record)
        archive_path.unlink(missing_ok=True)

    def install_fx(self) -> None:
        platforms = {("darwin", "aarch64"): "macos-aarch64", ("darwin", "x86_64"): "macos-x86_64",
                     ("linux", "aarch64"): "linux-aarch64", ("linux", "x86_64"): "linux-x86_64"}
        if (self.os_name, self.arch) not in platforms:
            self.skip("fx", f"no upstream binary for {self.os_name}/{self.arch}")
        fx_platform = platforms[(self.os_name, self.arch)]
        fx = self.dest / "fx"
        if fx.exists() or fx.is_symlink():
            if fx.is_symlink() or not fx.is_file() or not (self.state / "fx").is_file():
                self.skip("fx", f"{fx} already exists outside dl management")
        tag = self.latest_tag("https://github.com/vercel-labs/fx/releases.atom")
        if not tag:
            self.unchecked("fx", "no release found")
            return
        asset = f"fx-{fx_platform}.tar.gz"
        base = f"https://github.com/vercel-labs/fx/releases/download/{tag}"
        sums_path = Path(tempfile.mkstemp()[1])
        if not self.download(f"{base}/{asset}.sha256", sums_path):
            sums_path.unlink(missing_ok=True)
            self.unchecked("fx", f"{asset}.sha256 is unavailable")
            return
        expected = sums_path.read_text().split()[0] if sums_path.read_text().split() else ""
        sums_path.unlink(missing_ok=True)
        if len(expected) != 64 or re.search(r"[^0-9a-fA-F]", expected):
            self.unchecked("fx", f"{asset}.sha256 is invalid")
            return
        record = f"{tag}:{expected}"
        if self.is_current("fx", record):
            self.current(f"fx is current ({tag})")
            return
        self.fetch_msg(f"Downloading fx {tag} ({fx_platform}) ...")
        with tempfile.NamedTemporaryFile(delete=False) as stream:
            archive_path = Path(stream.name)
        if not self.download(f"{base}/{asset}", archive_path):
            archive_path.unlink(missing_ok=True)
            self.skip("fx", f"{asset} download failed")
        if self.sha256_file(archive_path) != expected:
            archive_path.unlink(missing_ok=True)
            self.skip("fx", f"{asset} checksum mismatch")
        names = self.tar_names(archive_path)
        if names is None or names.count("fx") != 1:
            archive_path.unlink(missing_ok=True)
            self.skip("fx", f"{asset} does not contain exactly one fx binary")
        staged = self.stage_file(self.dest, ".fx.")
        member = self.tar_member(archive_path, "fx")
        archive_path.unlink(missing_ok=True)
        if not member:
            staged.unlink(missing_ok=True)
            self.skip("fx", f"{asset} could not extract fx")
        staged.write_bytes(member)
        if self.os_name == "darwin" and self.run(["codesign", "--verify", "--strict", str(staged)]).returncode:
            staged.unlink(missing_ok=True)
            self.skip("fx", f"{asset} signature verification failed")
        staged.chmod(staged.stat().st_mode | 0o111)
        os.replace(staged, fx)
        self.own_file(fx)
        self.write_state("fx", record)
        self.changed = True
        self.ok(f"Installed {self.dest}/fx ({tag})")

    def install_grok(self) -> None:
        if self.installed("grok") and not self.legacy_binary("grok"):
            if (self.dest / "grok").is_file() and not (self.dest / "grok").is_symlink() \
                    and (self.state / "grok").is_file() and not self.which("file"):
                self.warn("Warning: file is required to identify the existing Grok launcher; keeping it")
            self.current("grok is installed")
            return
        platforms = {("darwin", "x86_64"): "macos-x86_64", ("darwin", "aarch64"): "macos-aarch64",
                     ("linux", "x86_64"): "linux-x86_64", ("linux", "aarch64"): "linux-aarch64"}
        if (self.os_name, self.arch) not in platforms:
            self.skip("grok", f"no upstream binary for {self.os_name}/{self.arch}")
        platform_name = platforms[(self.os_name, self.arch)]
        version = ""
        for line in self.fetch_text("https://x.ai/cli/stable").splitlines():
            if re.match(r"^\d+\.\d+\.\d+$", line.strip()):
                version = line.strip()
        if not version:
            self.unchecked("grok", "no stable release found")
            return
        url = f"https://x.ai/cli/grok-{version}-{platform_name}"
        record = self.asset_id(url)
        if not record:
            self.unchecked("grok", f"{url} is unreachable")
            return
        bin_dir = self.grok_home / "bin"
        downloads = self.grok_home / "downloads"
        binary = downloads / f"grok-{platform_name}"
        if not self.legacy_binary("grok") and self.is_current("grok", record):
            self.own_file(bin_dir / "grok")
            target = os.readlink(bin_dir / "grok") if (bin_dir / "grok").is_symlink() else ""
            self.own_grok_target(target)
            self.current(f"grok is current ({version})")
            return
        if binary.exists() or binary.is_symlink():
            self.skip("grok", f"{binary} already exists")
        if (bin_dir / "grok").exists() or (bin_dir / "grok").is_symlink():
            self.skip("grok", f"{bin_dir}/grok already exists")
        self.own_missing_dirs(bin_dir)
        self.own_missing_dirs(downloads)
        bin_dir.mkdir(parents=True, exist_ok=True)
        downloads.mkdir(parents=True, exist_ok=True)
        staged = self.stage_file(downloads, ".grok.")
        if not self.download(url, staged):
            staged.unlink(missing_ok=True)
            self.skip("grok", "download failed")
        if self.os_name == "darwin":
            self.run(["xattr", "-d", "com.apple.quarantine", str(staged)])
            self.run(["codesign", "-fs", "-", str(staged)], check=True)
        staged.chmod(staged.stat().st_mode | 0o111)
        os.replace(staged, binary)
        self.own_file(binary)
        self.link_symlink(bin_dir / "grok", f"../downloads/grok-{platform_name}")
        self.link_symlink(self.dest / "grok", str(bin_dir / "grok"))
        self.write_state("grok", record)
        self.changed = True
        self.ok(f"Installed {self.dest}/grok")

    def own_grok_target(self, target: str) -> None:
        if target in ("../downloads/grok-macos-x86_64", "../downloads/grok-macos-aarch64",
                      "../downloads/grok-linux-x86_64", "../downloads/grok-linux-aarch64"):
            self.own_file(self.grok_home / "downloads" / Path(target).name)

    def _install_python_build(self, tool: str, root: Path, triples: dict[tuple[str, str], str],
                              repo: str, inner: str, links: list[tuple[str, str]],
                              *, exclude_prefix: str = "", run_staged: bool = False,
                              pin: tuple[str, str, dict[str, tuple[str, str]]] | None = None) -> None:
        if (self.os_name, self.arch) not in triples:
            self.skip(tool, f"no {tool} release for {self.os_name}/{self.arch}")
        triple = triples[(self.os_name, self.arch)]
        expected = ""
        if pin is not None:
            tag, repo, pinned = pin
            pinned_asset = pinned.get(triple)
            if not pinned_asset or len(pinned_asset[1]) != 64:
                self.unchecked(tool, f"pinned python-build release has no {triple} artifact")
                return
            asset_name, expected = pinned_asset
            asset_url = f"https://github.com/{repo}/releases/download/{tag}/" + asset_name.replace("+", "%2B")
            record = expected
            sums_url = ""
        else:
            if not self.jaq_available():
                self.install_jaq()
                if not self.jaq_available():
                    self.unchecked(tool, f"jaq is required to find the {tool} release")
                    return
            tag = self.latest_tag(f"https://github.com/{repo}/releases.atom", exclude_prefix=exclude_prefix)
            if not tag:
                self.unchecked(tool, "no release found")
                return
            release = self.fetch_json(f"https://api.github.com/repos/{repo}/releases/tags/{tag}")
            assets = release.get("assets", [])
            asset_url = ""
            sums_url = ""
            for entry in assets if isinstance(assets, list) else []:
                if not isinstance(entry, dict):
                    continue
                name = str(entry.get("name", ""))
                if name.endswith(f"-{triple}-install_only_stripped.tar.gz"):
                    asset_url = str(entry.get("browser_download_url", ""))
                if name == "SHA256SUMS":
                    sums_url = str(entry.get("browser_download_url", ""))
            if not asset_url or not sums_url:
                self.unchecked(tool, f"{tag} has no {triple} release asset")
                return
            record = self.asset_id(asset_url)
            if not record:
                self.unchecked(tool, "release asset is unreachable")
                return
        if self.is_current(tool, record):
            self.current(f"{tool} is current ({tag})")
            return
        release_dir = root / tag
        if release_dir.exists() or release_dir.is_symlink():
            existing = release_dir / inner
            smoke = ([str(existing), "-c", "import sqlite3, ssl"] if tool == "python3"
                     else [str(existing), "--version"])
            if existing.is_file() and os.access(existing, os.X_OK) \
                    and self.run(smoke, capture=True).returncode == 0:
                for link_name, inner_name in links:
                    self.link_symlink(self.dest / link_name, str(release_dir / inner_name))
                self.write_state(tool, record)
                self.changed = True
                self.ok(f"Installed {self.dest}/{tool}")
                return
            self.skip(tool, f"{release_dir} already exists")
        self.fetch_msg(f"Downloading {tool} {tag} ({triple}) ...")
        with tempfile.NamedTemporaryFile(delete=False) as stream:
            archive_path = Path(stream.name)
        if not self.download(asset_url, archive_path):
            archive_path.unlink(missing_ok=True)
            self.skip(tool, "download failed")
        if pin is None:
            sums_path = Path(tempfile.mkstemp()[1])
            if not self.download(sums_url, sums_path):
                archive_path.unlink(missing_ok=True)
                sums_path.unlink(missing_ok=True)
                self.skip(tool, "SHA256SUMS download failed")
            asset_name = Path(asset_url).name.replace("%2B", "+").replace("%2b", "+")
            expected = self.sums_for(sums_path.read_text(), asset_name)
            sums_path.unlink(missing_ok=True)
        if len(expected) != 64 or self.sha256_file(archive_path) != expected:
            archive_path.unlink(missing_ok=True)
            self.skip(tool, "checksum mismatch")
        names = self.tar_names(archive_path)
        if names is None or self.archive_paths_bad(names):
            archive_path.unlink(missing_ok=True)
            self.skip(tool, "archive contains an invalid path")
        self.own_missing_dirs(root)
        root.mkdir(parents=True, exist_ok=True)
        staged_bundle = self.stage_dir(root, f".{tool}.")
        if not self.extract_tar(archive_path, staged_bundle):
            archive_path.unlink(missing_ok=True)
            self.skip(tool, "archive could not be extracted")
        archive_path.unlink(missing_ok=True)
        inner_path = staged_bundle / inner
        if not inner_path.is_file() or not os.access(inner_path, os.X_OK):
            self.skip(tool, f"archive is missing {inner}")
        if run_staged and self.run([str(inner_path), "--version"], capture=True).returncode:
            self.skip(tool, "staged node binary does not run")
        if tool == "python3" and pin is not None and self.run(
                [str(inner_path), "-c", "import sqlite3, ssl"], capture=True).returncode:
            self.skip(tool, "sqlite3/ssl imports failed in staged python")
        os.replace(staged_bundle, release_dir)
        self.own_dir(release_dir)
        for link_name, inner_name in links:
            self.link_symlink(self.dest / link_name, str(release_dir / inner_name))
        self.write_state(tool, record)
        self.changed = True
        self.ok(f"Installed {self.dest}/{tool}")
        if tool == "python3" and pin is None and self.run([str(self.dest / "python3"), "-c", "import sqlite3, ssl"],
                                         capture=True).returncode:
            self.warn(f"Python is installed but sqlite3/ssl imports failed; install libgcc or inspect {release_dir}")
            raise SkipInstall(tool, "sqlite3/ssl imports failed")

    def install_python3(self) -> None:
        self._install_python_build(
            "python3", self.python_build_root,
            {("darwin", "aarch64"): "aarch64-apple-darwin",
             ("linux", "x86_64"): "x86_64-unknown-linux-musl",
             ("linux", "aarch64"): "aarch64-unknown-linux-musl"},
            "laputa-systems/python-build", "python/bin/python3.15",
            [("python3", "python/bin/python3.15"), ("python3.15", "python/bin/python3.15")],
            pin=python_build_pin())

    def install_nodebuild(self) -> None:
        self._install_python_build(
            "node-build", self.node_build_root,
            {("darwin", "aarch64"): "aarch64-apple-darwin",
             ("linux", "x86_64"): "x86_64-unknown-linux-musl"},
            "laputa-systems/node-build", "node/bin/node",
            [("node-build", "node/bin/node")], run_staged=True)

    def jaq_runs(self, argv: list[str]) -> bool:
        return self.run(argv + ["--version"], capture=True).returncode == 0

    def jaq_available(self) -> bool:
        for candidate in (["jaq"], [str(self.dest / "jaq")], ["jq"]):
            if self.which(candidate[0]) and self.jaq_runs(candidate):
                return True
        return False

    def run_jaq(self, argv: list[str]) -> subprocess.CompletedProcess[str] | None:
        for candidate in (["jaq"], [str(self.dest / "jaq")], ["jq"]):
            if self.which(candidate[0]) and self.jaq_runs(candidate):
                return self.run(candidate + argv, capture=True)
        return None

    def _npm_tool(self, tool: str, root: Path, package: str, bin_name: str, *,
                  extra: tuple[str, ...] = (), fetch_msg: str = "", no_release: str = "") -> None:
        if not self.which("npm"):
            self.unchecked(tool, "npm is required")
            return
        if not self.node_meets_minimum():
            self.unchecked(tool, f"Node.js {NODE_MINIMUM} or newer is required")
            return
        version = self.npm_view(f"{package}@latest")
        if not self.valid_version(version):
            self.unchecked(tool, no_release or "no npm release found")
            return
        launcher = self.dest / bin_name
        if launcher.exists() or launcher.is_symlink():
            actual = os.readlink(launcher) if launcher.is_symlink() else ""
            if actual != str(root / "bin" / bin_name) or not (self.state / tool).is_file():
                self.skip(tool, f"{launcher} already exists outside dl management")
        if root.exists() or root.is_symlink():
            if root.is_symlink() or not root.is_dir() or not (self.state / tool).is_file():
                self.skip(tool, f"{root} already exists without dl install records")
        if self._state_text(tool) == version and (root / "bin" / bin_name).is_file() \
                and os.access(root / "bin" / bin_name, os.X_OK) \
                and launcher.is_symlink() and os.readlink(launcher) == str(root / "bin" / bin_name):
            self.own_dir(root)
            self.own_file(launcher)
            self.own_file(self.state / tool)
            self.current(f"{tool} is current ({version})")
            return
        self.own_missing_dirs(root.parent)
        root.parent.mkdir(parents=True, exist_ok=True)
        prefix = root
        staged = None
        if not root.is_dir():
            staged = self.stage_dir(root.parent, f"{root.name}.")
            prefix = staged
        self.fetch_msg(fetch_msg or f"Installing {tool} ({version}) ...")
        if not self.npm_install(prefix, f"{package}@{version}", *extra):
            if staged is not None:
                shutil.rmtree(staged, ignore_errors=True)
            self.skip(tool, "npm install failed")
        binary = prefix / "bin" / bin_name
        if not binary.is_file() or not os.access(binary, os.X_OK):
            if staged is not None:
                shutil.rmtree(staged, ignore_errors=True)
            self.skip(tool, f"npm did not install {binary}")
        if staged is not None:
            if root.exists() or root.is_symlink():
                shutil.rmtree(staged, ignore_errors=True)
                self.skip(tool, f"{root} appeared during install")
            os.replace(staged, root)
        self.own_dir(root)
        self.link_symlink(launcher, str(root / "bin" / bin_name))
        self.write_state(tool, version)
        if tool == "cmd":
            self.ok(f"Installed {self.dest}/cmd")
        elif tool == "cf":
            self.ok(f"Installed {self.dest}/cf ({version})")
        elif tool == "agent-browser":
            self.ok(f"Installed {self.dest}/agent-browser ({version})")
        elif tool == "pi":
            self.ok(f"Installed {self.dest}/pi")
        else:
            self.ok(f"Installed {self.dest}/{bin_name} ({version})")
        self.changed = True

    def install_cmd(self) -> None:
        self._npm_tool("cmd", self.cmd_root, "command-code", "cmd",
                       fetch_msg="Installing Command Code ...")

    def install_pnpm(self) -> None:
        extra_root = self.pnpm_root
        if not self.which("npm"):
            self.unchecked("pnpm", "npm is required")
            return
        if not self.node_meets_minimum():
            self.unchecked("pnpm", f"Node.js {NODE_MINIMUM} or newer is required")
            return
        version = self.npm_view("pnpm@latest")
        if not self.valid_version(version):
            self.unchecked("pnpm", "could not resolve the latest pnpm version")
            return
        launcher = self.dest / "pnpm"
        if self._state_text("pnpm") == version and (extra_root / "bin/pnpm").is_file() \
                and os.access(extra_root / "bin/pnpm", os.X_OK) \
                and launcher.is_symlink() and os.readlink(launcher) == str(extra_root / "bin/pnpm"):
            self.own_dir(extra_root)
            self.own_file(launcher)
            self.own_file(self.state / "pnpm")
            self.current(f"pnpm is current ({version})")
            return
        if extra_root.is_symlink() or (extra_root.exists() and not extra_root.is_dir()):
            extra_root.unlink()
        if launcher.is_dir() and not launcher.is_symlink():
            shutil.rmtree(launcher)
        self.own_missing_dirs(extra_root.parent)
        extra_root.parent.mkdir(parents=True, exist_ok=True)
        prefix = extra_root
        staged = None
        if not extra_root.is_dir():
            staged = self.stage_dir(extra_root.parent, f"{extra_root.name}.")
            prefix = staged
        self.fetch_msg(f"Installing pnpm ({version}) ...")
        if not self.npm_install(prefix, f"pnpm@{version}", "--allow-scripts=pnpm"):
            if staged is not None:
                shutil.rmtree(staged, ignore_errors=True)
            self.skip("pnpm", "npm install failed")
        binary = prefix / "bin/pnpm"
        if not binary.is_file() or not os.access(binary, os.X_OK):
            if staged is not None:
                shutil.rmtree(staged, ignore_errors=True)
            self.skip("pnpm", f"npm did not install {binary}")
        if staged is not None:
            if extra_root.exists() or extra_root.is_symlink():
                shutil.rmtree(staged, ignore_errors=True)
                self.skip("pnpm", f"{extra_root} appeared during install")
            os.replace(staged, extra_root)
        self.own_dir(extra_root)
        self.link_symlink(launcher, str(extra_root / "bin/pnpm"))
        self.write_state("pnpm", version)
        self.changed = True
        self.ok(f"Installed {self.dest}/pnpm ({version})")

    def install_cf(self) -> None:
        self._npm_tool("cf", self.cf_root, "cf", "cf", extra=("--ignore-scripts",),
                       fetch_msg="Installing Cloudflare cf ...", no_release="could not resolve the latest cf version")

    def install_agent_browser(self) -> None:
        self._npm_tool("agent-browser", self.agent_browser_root, "agent-browser", "agent-browser",
                       extra=("--ignore-scripts",), fetch_msg="Installing agent-browser ...",
                       no_release="could not resolve the latest agent-browser version")

    def install_pi(self) -> None:
        self._npm_tool("pi", self.pi_root, "@earendil-works/pi-coding-agent", "pi",
                       extra=("--ignore-scripts",), fetch_msg="Installing Pi ...")

    def repair_dsh_tui_patch(self) -> bool:
        patch_path = self.dsh_root / "lib/node_modules/@deepseek-harness-tui/dsh-tui/cordis.patch.yml"
        if not patch_path.is_file() or patch_path.is_symlink():
            self.skip("dsh", "dsh-tui patch is missing or is a symlink")
        directory_fd = os.open(patch_path.parent, os.O_RDONLY | os.O_DIRECTORY)
        temporary_name = None
        try:
            patch_fd = os.open(patch_path.name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=directory_fd)
            patch_info = os.fstat(patch_fd)
            import stat as stat_module
            if not stat_module.S_ISREG(patch_info.st_mode):
                raise ValueError("patch is not a regular file")
            with os.fdopen(patch_fd, "rb") as patch:
                contents = patch.read()
            if b"tool-ralph" not in contents:
                return True
            stale_row = b"- id: tool-ralph\n  disabled: true\n"
            if contents.count(stale_row) != 1:
                raise ValueError("unexpected tool-ralph row")
            temporary_name = f".{patch_path.name}.{os.getpid()}.tmp"
            temporary_fd = os.open(temporary_name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                                   patch_info.st_mode & 0o777, dir_fd=directory_fd)
            with os.fdopen(temporary_fd, "wb") as replacement:
                replacement.write(contents.replace(stale_row, b"", 1))
                replacement.flush()
                os.fchmod(replacement.fileno(), patch_info.st_mode & 0o777)
                os.fsync(replacement.fileno())
            os.replace(temporary_name, patch_path.name, src_dir_fd=directory_fd, dst_dir_fd=directory_fd)
            temporary_name = None
        except (OSError, ValueError):
            if temporary_name is not None:
                try:
                    os.unlink(temporary_name, dir_fd=directory_fd)
                except FileNotFoundError:
                    pass
            self.skip("dsh", "cannot repair the dsh-tui compatibility patch")
        finally:
            os.close(directory_fd)
        self.changed = True
        self.ok("Removed dsh-tui's stale tool-ralph patch row")
        return True

    def remove_legacy_dsh(self) -> bool:
        legacy_root = self.home / ".local"
        legacy_package = legacy_root / "lib/node_modules/@deepseek-ai/dsh"
        legacy_bin = legacy_root / "bin/dsh"
        if not legacy_package.is_dir():
            return True
        if legacy_bin.is_symlink():
            target = os.readlink(legacy_bin)
            if target not in ("../lib/node_modules/@deepseek-ai/dsh/lib/bin.js",
                              str(legacy_package / "lib/bin.js")):
                self.current(f"Keeping existing dsh launcher at {legacy_bin}; leaving the previous npm package installed")
                return True
        elif legacy_bin.exists():
            self.current(f"Keeping existing dsh launcher at {legacy_bin}; leaving the previous npm package installed")
            return True
        if self.run(["npm", "uninstall", "--global", "--prefix", str(legacy_root),
                     "@deepseek-ai/dsh"]).returncode:
            self.skip("dsh", "could not remove the previous global dsh installation")
        return True

    def install_dsh(self) -> None:
        if not self.which("npm"):
            self.unchecked("dsh", "npm is required")
            return
        if not self.node_meets_minimum():
            self.unchecked("dsh", f"Node.js {NODE_MINIMUM} or newer is required")
            return
        version = self.npm_view("@deepseek-ai/dsh@next")
        if not self.valid_version(version):
            self.unchecked("dsh", "no npm release found")
            return
        tui_version = self.npm_view("@deepseek-harness-tui/dsh-tui")
        if not self.valid_version(tui_version):
            self.unchecked("dsh", "no dsh-tui release found")
            return
        if not self.which("pnpm"):
            self.skip("dsh", "pnpm is required by dsh-tui")
        if self._state_text("dsh") == version and self._state_text("dsh-tui") == tui_version \
                and (self.dsh_root / "bin/dsh").is_file() and (self.dsh_root / "bin/dsh-tui").is_file():
            self.repair_dsh_tui_patch()
            self.remove_legacy_dsh()
            self.own_dir(self.dsh_root)
            self.own_file(self.state / "dsh")
            self.own_file(self.state / "dsh-tui")
            self.current(f"dsh and dsh-tui are current ({version}, {tui_version})")
            return
        if self.dsh_root.exists() or self.dsh_root.is_symlink():
            if not (self.state / "dsh").is_file() or not (self.state / "dsh-tui").is_file():
                self.skip("dsh", f"{self.dsh_root} already exists without dl install records")
        else:
            self.own_missing_dirs(self.dsh_root.parent)
            self.own_dir(self.dsh_root)
        self.fetch_msg(f"Installing dsh ({version}) and dsh-tui ({tui_version}) ...")
        result = self.run(["npm", "install", "--global", "--prefix", str(self.dsh_root),
                           f"@deepseek-ai/dsh@{version}", f"@deepseek-harness-tui/dsh-tui@{tui_version}"])
        if result.returncode:
            self.skip("dsh", "npm install failed")
        if not (self.dsh_root / "bin/dsh").is_file() or not (self.dsh_root / "bin/dsh-tui").is_file():
            self.skip("dsh", "npm packages did not install the dsh and dsh-tui commands")
        self.repair_dsh_tui_patch()
        self.remove_legacy_dsh()
        self.write_state("dsh", version)
        self.write_state("dsh-tui", tui_version)
        self.changed = True
        self.ok(f"Installed dsh and dsh-tui under {self.dsh_root}")

    def install_nodejs(self) -> None:
        targets = {
            ("darwin", "aarch64"): ("node-v" + NODEJS_VERSION + "-darwin-arm64.tar.xz",
                                   "https://nodejs.org/dist/v" + NODEJS_VERSION + "/node-v" + NODEJS_VERSION + "-darwin-arm64.tar.xz",
                                   "18830bf448fe187c650dc28c98aa8c968ed1d40b6dd032c081e70a384a1bf660",
                                   "darwin-arm64"),
        }
        if (self.os_name, self.arch) == ("darwin", "aarch64"):
            asset, url, sha256, target = targets[("darwin", "aarch64")]
        elif self.os_name == "linux" and self.arch in ("x86_64", "aarch64"):
            glibc = self.run(["getconf", "GNU_LIBC_VERSION"], capture=True).returncode == 0
            if glibc:
                target = "linux-x64" if self.arch == "x86_64" else "linux-arm64"
                sha256 = "6170b2d474e1c626f43cff3adc118df9fe3b573258a4fc3d850c8dbc6b079bbd" \
                    if self.arch == "x86_64" else "42aa04922591ee5d4dbc7740d452621acf28508239daa512f5ee8c47ee224fdb"
                url = f"https://nodejs.org/dist/v{NODEJS_VERSION}/node-v{NODEJS_VERSION}-{target}.tar.xz"
            elif self.arch == "x86_64":
                target = "linux-x64-musl"
                sha256 = "4fd7c15fdc930ea48cf144bb302ce30a76c81920e36473d087720d0810efe1cd"
                url = f"https://nodejs.org/dist/v{NODEJS_VERSION}/node-v{NODEJS_VERSION}-{target}.tar.xz"
            else:
                target = "linux-arm64-musl"
                sha256 = "87d822005776f222f2964c93df055f926d80595a63442b891d3aafe1f0a1dc67"
                url = f"https://unofficial-builds.nodejs.org/download/release/v{NODEJS_VERSION}/node-v{NODEJS_VERSION}-{target}.tar.xz"
            asset = f"node-v{NODEJS_VERSION}-{target}.tar.xz"
        else:
            self.skip("nodejs", f"no Node.js {NODEJS_VERSION} build for {self.os_name}/{self.arch}")
        if self.nodejs_root.is_symlink():
            self.skip("nodejs", f"{self.nodejs_root} is a symlink")
        managed = False
        previous_release = ""
        current_target = os.readlink(self.nodejs_root / "current") if (self.nodejs_root / "current").is_symlink() else ""
        if current_target:
            if not current_target.startswith(str(self.nodejs_root) + os.sep):
                self.skip("nodejs", f"{self.nodejs_root}/current points outside its install directory")
            previous_release = Path(current_target).name
            if not re.match(rf"^{re.escape(NODEJS_VERSION)}-npm\d+\.\d+\.\d+([.-][A-Za-z0-9.-]+)?-{re.escape(target)}$",
                            previous_release):
                self.skip("nodejs", "invalid install record")
            previous_dir = self.nodejs_root / previous_release
            if previous_dir.is_symlink() or not previous_dir.is_dir():
                self.skip("nodejs", f"{self.nodejs_root}/current target is missing")
            managed = True
        elif self.nodejs_root.exists() or self.nodejs_root.is_symlink():
            if self.nodejs_root.is_symlink() or not self.nodejs_root.is_dir() or any(self.nodejs_root.iterdir()):
                self.skip("nodejs", f"{self.nodejs_root} already exists outside dl management")
        for command in ("node", "npm", "npx"):
            launcher = self.dest / command
            if launcher.exists() or launcher.is_symlink():
                actual = os.readlink(launcher) if launcher.is_symlink() else ""
                if not managed or actual != str(self.nodejs_root / "current/bin" / command):
                    self.skip("nodejs", f"{launcher} already exists outside dl management")
        npm_latest = ""
        if managed:
            current_bin = str(self.nodejs_root / "current/bin")
            npm_latest = self.run([str(self.nodejs_root / "current/bin/npm"), "view", "npm@latest", "version"],
                                  capture=True, extra_env={"PATH": current_bin + os.pathsep + self._path}).stdout.strip()
            if not self.valid_version(npm_latest):
                self.unchecked("nodejs", "could not resolve the latest npm version")
                return
            installed_npm = self.run([str(self.nodejs_root / "current/bin/npm"), "--version"], capture=True).stdout.strip()
            installed_node = self.run([str(self.nodejs_root / "current/bin/node"), "-p", "process.versions.node"], capture=True).stdout.strip()
            if installed_npm == npm_latest and installed_node == NODEJS_VERSION:
                self.own_file(self.nodejs_root / "current")
                self.own_dir(self.nodejs_root / previous_release)
                for command in ("node", "npm", "npx"):
                    launcher = self.dest / command
                    if not launcher.exists() and not launcher.is_symlink():
                        self.link_symlink(launcher, str(self.nodejs_root / "current/bin" / command))
                    self.own_file(launcher)
                self.current(f"nodejs is current ({NODEJS_VERSION}, npm {npm_latest})")
                return
        elif self.which("npm"):
            candidate = self.npm_view("npm@latest")
            npm_latest = candidate if self.valid_version(candidate) else ""
        self.own_missing_dirs(self.nodejs_root)
        self.nodejs_root.mkdir(parents=True, exist_ok=True)
        staged_bundle = self.stage_dir(self.nodejs_root, ".nodejs.")
        if managed:
            try:
                shutil.copytree(self.nodejs_root / "current", staged_bundle, dirs_exist_ok=True)
            except OSError:
                self.skip("nodejs", "could not stage the existing Node.js installation")
        else:
            self.fetch_msg(f"Downloading Node.js {NODEJS_VERSION} ({target}) ...")
            with tempfile.NamedTemporaryFile(delete=False) as stream:
                archive_path = Path(stream.name)
            if not self.download(url, archive_path):
                archive_path.unlink(missing_ok=True)
                self.skip("nodejs", f"{asset} download failed")
            if self.sha256_file(archive_path) != sha256:
                archive_path.unlink(missing_ok=True)
                self.skip("nodejs", f"{asset} checksum mismatch")
            names = self.tar_names(archive_path)
            if names is None or self.archive_paths_bad(names):
                archive_path.unlink(missing_ok=True)
                self.skip("nodejs", f"{asset} contains an invalid path")
            if not self.extract_tar(archive_path, staged_bundle, strip=1):
                archive_path.unlink(missing_ok=True)
                self.skip("nodejs", f"{asset} could not be extracted")
            archive_path.unlink(missing_ok=True)
        if not (staged_bundle / "bin/node").is_file() or not (staged_bundle / "bin/npm").is_file():
            self.skip("nodejs", "Node.js archive is missing node or npm")
        if not npm_latest:
            npm_latest = self.run([str(staged_bundle / "bin/npm"), "view", "npm@latest", "version"],
                                  capture=True, extra_env={"PATH": str(staged_bundle / "bin") + os.pathsep + self._path}).stdout.strip()
        if not self.valid_version(npm_latest):
            self.skip("nodejs", "could not resolve the latest npm version")
        self.fetch_msg(f"Installing npm {npm_latest} ...")
        npm_result = self.run([str(staged_bundle / "bin/npm"), "install", "--global", "--prefix", str(staged_bundle),
                               f"npm@{npm_latest}"], extra_env={"PATH": str(staged_bundle / "bin") + os.pathsep + self._path})
        if npm_result.returncode:
            self.skip("nodejs", f"npm {npm_latest} install failed")
        staged_node = self.run([str(staged_bundle / "bin/node"), "-p", "process.versions.node"], capture=True).stdout.strip()
        staged_npm = self.run([str(staged_bundle / "bin/npm"), "--version"], capture=True,
                              extra_env={"PATH": str(staged_bundle / "bin") + os.pathsep + self._path}).stdout.strip()
        if staged_node != NODEJS_VERSION or staged_npm != npm_latest:
            self.skip("nodejs", "staged Node.js or npm version does not match the requested version")
        release_name = f"{NODEJS_VERSION}-npm{npm_latest}-{target}"
        release_dir = self.nodejs_root / release_name
        if release_dir.exists() or release_dir.is_symlink():
            release_node = self.run([str(release_dir / "bin/node"), "-p", "process.versions.node"], capture=True).stdout.strip() \
                if (release_dir / "bin/node").is_file() else ""
            release_npm = self.run([str(release_dir / "bin/npm"), "--version"], capture=True).stdout.strip() \
                if (release_dir / "bin/npm").is_file() else ""
            if release_dir.is_symlink() or not release_dir.is_dir() or release_node != NODEJS_VERSION or release_npm != npm_latest:
                self.skip("nodejs", f"{release_dir} already exists without a matching Node.js install")
            shutil.rmtree(staged_bundle)
        else:
            os.replace(staged_bundle, release_dir)
        self.own_dir(release_dir)
        if not self.switch_symlink(release_dir, self.nodejs_root / "current"):
            self.skip("nodejs", f"could not switch {self.nodejs_root}/current")
        self.own_file(self.nodejs_root / "current")
        for command in ("node", "npm", "npx"):
            self.link_symlink(self.dest / command, str(self.nodejs_root / "current/bin" / command))
        if previous_release and previous_release != release_name:
            previous_dir = self.nodejs_root / previous_release
            shutil.rmtree(previous_dir, ignore_errors=True)
            self.removed.add(previous_dir)
        self.changed = True
        self.ok(f"Installed {self.dest}/node ({NODEJS_VERSION}, npm {npm_latest})")

    def install_antigravity(self) -> None:
        if self.keep_installed("agy"):
            return
        self.fetch_msg("Installing Antigravity CLI ...")
        with tempfile.NamedTemporaryFile(delete=False) as stream:
            script = Path(stream.name)
        if not self.download("https://antigravity.google/cli/install.sh", script):
            script.unlink(missing_ok=True)
            self.skip("antigravity", "official installer is unavailable")
        agy_home = Path(tempfile.mkdtemp())
        result = self.run(["bash", str(script), "--dir", str(self.dest)], extra_env={"HOME": str(agy_home)})
        shutil.rmtree(agy_home, ignore_errors=True)
        script.unlink(missing_ok=True)
        if result.returncode:
            self.skip("antigravity", "official installer failed")
        if not self.installed("agy"):
            self.skip("antigravity", f"official installer did not install {self.dest}/agy")
        if self.run([str(self.dest / "agy"), "install", "--dir", str(self.dest),
                     "--skip-aliases", "--skip-path"]).returncode:
            self.skip("antigravity", "official setup failed")
        self.changed = True
        self.ok(f"Installed Antigravity CLI ({self.dest}/agy)")
        self.own_file(self.dest / "agy")

    def install_muse(self) -> None:
        if self.installed("muse") and not self.legacy_binary("muse"):
            if (self.dest / "muse").is_file() and not (self.dest / "muse").is_symlink() \
                    and (self.state / "muse").is_file() and not self.which("file"):
                self.warn("Warning: file is required to identify the existing Muse launcher; keeping it")
            self.current("muse is installed")
            return
        self.fetch_msg("Installing Muse Code launcher ...")
        with tempfile.NamedTemporaryFile(delete=False) as stream:
            script = Path(stream.name)
        if not self.download(MUSE_LAUNCHER_URL, script):
            script.unlink(missing_ok=True)
            self.skip("muse", "official installer is unavailable")
        result = self.run(["bash", str(script)],
                          extra_env={"MUSE_INSTALL_DIR": str(self.dest), "MUSE_NO_MODIFY_PATH": "1"})
        script.unlink(missing_ok=True)
        if result.returncode:
            self.skip("muse", "official installer failed")
        if not self.installed("muse"):
            self.skip("muse", f"official installer did not install {self.dest}/muse")
        (self.state / "muse").unlink(missing_ok=True)
        self.changed = True
        self.ok(f"Installed Muse Code launcher ({self.dest}/muse)")
        self.own_file(self.dest / "muse")

    def claude_legacy(self) -> bool:
        if not (self.state / "claude").is_file():
            return False
        launcher = self.dest / "claude"
        if launcher.is_file() and not launcher.is_symlink():
            return self.legacy_binary("claude")
        if not launcher.is_symlink():
            return False
        target = os.readlink(launcher)
        return target.startswith(str(self.claude_versions) + os.sep) and (launcher.exists() or os.access(launcher, os.X_OK))

    def install_claude(self) -> None:
        if self.installed("claude") and not self.claude_legacy():
            if (self.dest / "claude").is_file() and not (self.dest / "claude").is_symlink() \
                    and (self.state / "claude").is_file() and not self.which("file"):
                self.warn("Warning: file is required to identify the existing Claude launcher; keeping it")
            self.current("claude is installed")
            return
        self.fetch_msg("Installing Claude Code with the native installer ...")
        with tempfile.NamedTemporaryFile(delete=False) as stream:
            script = Path(stream.name)
        if not self.download("https://claude.ai/install.sh", script):
            script.unlink(missing_ok=True)
            self.skip("claude", "official installer is unavailable")
        output_path = Path(tempfile.mkstemp(prefix="dl.claude.", dir=self.env.get("TMPDIR") or "/tmp")[1])
        with output_path.open("wb") as output:
            result = subprocess.run(["bash", str(script), "latest"], env={**self.env, "PATH": str(self.dest) + os.pathsep + self._path},
                                    stdout=output, stderr=subprocess.STDOUT)
        script.unlink(missing_ok=True)
        if result.returncode:
            print(output_path.read_text(), file=sys.stderr, end="")
            output_path.unlink(missing_ok=True)
            self.skip("claude", "official installer failed")
        output_path.unlink(missing_ok=True)
        if not self.installed("claude"):
            self.skip("claude", f"official installer did not install {self.dest}/claude")
        (self.state / "claude").unlink(missing_ok=True)
        self.changed = True
        self.ok(f"Installed Claude Code ({self.dest}/claude)")
        self.own_file(self.dest / "claude")
        launcher = self.dest / "claude"
        target = os.readlink(launcher) if launcher.is_symlink() else ""
        if target and not os.path.isabs(target):
            target = str(self.dest / target)
        if target and "/../" not in f"/{target}/":
            if target.startswith(str(self.home / ".claude") + os.sep) or target.startswith(str(self.claude_versions) + os.sep):
                self.own_file(Path(target))

    def codex_legacy(self) -> bool:
        launcher = self.dest / "codex"
        if not launcher.is_symlink() or not (self.state / "codex").is_file():
            return False
        return os.readlink(launcher) == str(self.codex_legacy_root / "current/bin/codex") and launcher.exists()

    def own_codex_release_target(self, target: str) -> bool:
        prefix = str(self.codex_home / "packages/standalone/releases/")
        if not target.startswith(prefix) or not target.endswith("/bin/codex"):
            return False
        name = target[len(prefix):-len("/bin/codex")]
        if not name or "/" in name or name in (".", ".."):
            return False
        self.own_dir(Path(prefix) / name)
        return True

    def install_codex(self) -> None:
        if self.installed("codex") and not self.codex_legacy():
            self.current("codex is installed")
            return
        if not self.jaq_available():
            self.install_jaq()
            if not self.jaq_available():
                return
        targets = {("darwin", "x86_64"): "x86_64-apple-darwin", ("darwin", "aarch64"): "aarch64-apple-darwin",
                   ("linux", "x86_64"): "x86_64-unknown-linux-musl", ("linux", "aarch64"): "aarch64-unknown-linux-musl"}
        if (self.os_name, self.arch) not in targets:
            self.skip("codex", f"no upstream binary for {self.os_name}/{self.arch}")
        target = targets[(self.os_name, self.arch)]
        release = self.fetch_json("https://releases.openai.com/codex/channels/latest")
        tag = str(release.get("tag_name", ""))
        if not tag.startswith("rust-v") or not self.valid_version(tag.removeprefix("rust-v")):
            self.unchecked("codex", "no release found")
            return
        version = tag.removeprefix("rust-v")
        asset = f"codex-package-{target}.tar.gz"
        asset_entry = {}
        assets = release.get("assets", [])
        for entry in assets if isinstance(assets, list) else []:
            if isinstance(entry, dict) and entry.get("name") == asset:
                asset_entry = entry
        url = str(asset_entry.get("browser_download_url", ""))
        digest = str(asset_entry.get("digest", "")).removeprefix("sha256:")
        if len(digest) != 64 or re.search(r"[^0-9a-f]", digest) or not url.startswith(
                ("https://releases.openai.com/codex/releases/", "https://github.com/openai/codex/releases/download/")):
            self.unchecked("codex", f"{asset} is missing a SHA-256 digest")
            return
        codex_root = self.codex_home / "packages/standalone"
        if (self.dest / "codex").is_dir() and not (self.dest / "codex").is_symlink():
            self.skip("codex", f"{self.dest}/codex is a directory")
        releases = codex_root / "releases"
        if releases.is_symlink() or (releases.exists() and not releases.is_dir()):
            self.skip("codex", f"{releases} is not a directory")
        record = self.asset_id(url)
        if not record:
            self.unchecked("codex", f"{asset} is unavailable")
            return
        if not self.codex_legacy() and self.is_current("codex", record):
            target_path = os.readlink(self.dest / "codex") if (self.dest / "codex").is_symlink() else ""
            if self.own_codex_release_target(target_path):
                mode_host = self.dest / "codex-code-mode-host"
                mode_target = os.readlink(mode_host) if mode_host.is_symlink() else ""
                release = target_path.removesuffix("/bin/codex")
                if mode_target == f"{release}/bin/codex-code-mode-host":
                    self.own_file(mode_host)
            self.current(f"codex is current ({version})")
            return
        release_dir = releases / f"{version}-{target}"
        if release_dir.exists() or release_dir.is_symlink():
            self.skip("codex", f"{release_dir} already exists")
        self.own_missing_dirs(releases)
        releases.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(delete=False) as stream:
            archive_path = Path(stream.name)
        if not self.download(url, archive_path):
            archive_path.unlink(missing_ok=True)
            self.skip("codex", f"{asset} download failed")
        if self.sha256_file(archive_path) != digest:
            archive_path.unlink(missing_ok=True)
            self.skip("codex", f"{asset} checksum mismatch")
        names = self.tar_names(archive_path)
        if names is None or self.archive_paths_bad(names):
            archive_path.unlink(missing_ok=True)
            self.skip("codex", f"{asset} contains an invalid path")
        staged = self.stage_dir(releases, ".codex.")
        if not self.extract_tar(archive_path, staged):
            archive_path.unlink(missing_ok=True)
            self.skip("codex", f"{asset} could not be extracted")
        archive_path.unlink(missing_ok=True)
        if not (staged / "codex-package.json").is_file() or not (staged / "bin/codex").is_file() \
                or not (staged / "bin/codex-code-mode-host").is_file() or not (staged / "codex-path/rg").is_file():
            self.skip("codex", f"{asset} is missing required package files")
        os.replace(staged, release_dir)
        self.own_dir(release_dir)
        self.link_symlink(self.dest / "codex", str(release_dir / "bin/codex"))
        if self.os_name == "darwin":
            self.link_symlink(self.dest / "codex-code-mode-host", str(release_dir / "bin/codex-code-mode-host"))
        self.write_state("codex", record)
        self.changed = True
        self.ok(f"Installed {self.dest}/codex")

    def _own_release_target(self, home: Path, commands: list[str], target: str, *, in_bin: bool) -> bool:
        prefix = f"{home}/releases/"
        if not target.startswith(prefix):
            return False
        rest = target[len(prefix):]
        if "/" not in rest:
            return False
        name, remainder = rest.split("/", 1)
        if name in ("", ".", ".."):
            return False
        if in_bin:
            if not remainder.startswith("bin/"):
                return False
            command = remainder[4:]
        else:
            command = remainder
        if command not in commands:
            return False
        self.own_dir(home / "releases" / name)
        return True

    def _own_current_target(self, home: Path, commands: list[str], target: str, *, in_bin: bool) -> bool:
        prefix = f"{home}/current/bin/" if in_bin else f"{home}/current/"
        if not target.startswith(prefix):
            return False
        command = target[len(prefix):]
        if command not in commands:
            return False
        current = home / "current"
        if not current.is_symlink():
            return False
        pointed = os.readlink(current)
        pointed_target = f"{pointed}/bin/{command}" if in_bin else f"{pointed}/{command}"
        if not self._own_release_target(home, commands, pointed_target, in_bin=in_bin):
            return False
        return Path(pointed).is_dir()

    def _ensure_bundle_link(self, tool: str, home: Path, commands: list[str], *, in_bin: bool,
                            command: str) -> None:
        link = self.dest / command
        want = str(home / ("current/bin" if in_bin else "current") / command)
        if link.is_symlink():
            have = os.readlink(link)
            if have != want:
                if not (self._own_release_target(home, commands, have, in_bin=in_bin)
                        or self._own_current_target(home, commands, have, in_bin=in_bin)):
                    self.skip(tool, f"{link} is not a dl-managed symlink")
        elif link.exists():
            self.skip(tool, f"{link} is not a dl-managed symlink")
        self.link_symlink(link, want)

    def _zip_bundle(self, tool: str, home: Path, commands: list[str], state_name: str, *,
                    in_bin: bool, asset: str, url: str, sums_url: str, release_dir: Path,
                    validate, ok_message: str, install_message: str, on_current=None) -> None:
        for command in commands:
            existing = self.dest / command
            if existing.exists() or existing.is_symlink():
                target = os.readlink(existing) if existing.is_symlink() else ""
                if not (self._own_release_target(home, commands, target, in_bin=in_bin)
                        or self._own_current_target(home, commands, target, in_bin=in_bin)):
                    self.skip(tool, f"{existing} is not a dl-managed symlink")
        releases = home / "releases"
        if releases.is_symlink() or (releases.exists() and not releases.is_dir()):
            self.skip(tool, f"{releases} is not a directory")
        current = home / "current"
        if current.exists() and not current.is_symlink():
            self.skip(tool, f"{current} is not a dl-managed symlink")
        record = self.asset_id(url)
        if not record:
            self.unchecked(tool, f"{asset} is unavailable")
            return
        if self.is_current(state_name, record) and current.is_symlink():
            pointed = os.readlink(current)
            current_ok = Path(pointed).is_dir()
            for command in commands:
                have = os.readlink(self.dest / command) if (self.dest / command).is_symlink() else ""
                want = str(home / ("current/bin" if in_bin else "current") / command)
                if have != want:
                    current_ok = False
                else:
                    self.own_file(self.dest / command)
            first = f"{pointed}/bin/{commands[0]}" if in_bin else f"{pointed}/{commands[0]}"
            if current_ok and self._own_release_target(home, commands, first, in_bin=in_bin) and Path(pointed).is_dir():
                if on_current is not None:
                    on_current()
                self.current(ok_message)
                return
        if release_dir.exists() or release_dir.is_symlink():
            if current.is_symlink() and os.readlink(current) == str(release_dir) and self.is_current(state_name, record):
                for command in commands:
                    self._ensure_bundle_link(tool, home, commands, in_bin=in_bin, command=command)
                if on_current is not None:
                    on_current()
                self.current(ok_message)
                return
            self.skip(tool, f"{release_dir} already exists")
        self.own_missing_dirs(releases)
        releases.mkdir(parents=True, exist_ok=True)
        self.fetch_msg(f"Downloading {asset} ...")
        with tempfile.NamedTemporaryFile(delete=False) as stream:
            archive_path = Path(stream.name)
        if not self.download(url, archive_path):
            archive_path.unlink(missing_ok=True)
            self.skip(tool, f"{asset} download failed")
        sums_path = Path(tempfile.mkstemp()[1])
        if not self.download(sums_url, sums_path):
            archive_path.unlink(missing_ok=True)
            sums_path.unlink(missing_ok=True)
            self.skip(tool, "SHA256SUMS download failed")
        expected = self.sums_for(sums_path.read_text(), asset)
        sums_path.unlink(missing_ok=True)
        if len(expected) != 64 or self.sha256_file(archive_path) != expected:
            archive_path.unlink(missing_ok=True)
            self.skip(tool, f"{asset} checksum mismatch")
        names = self.zip_names(archive_path)
        if names is None or self.archive_paths_bad(names):
            archive_path.unlink(missing_ok=True)
            self.skip(tool, f"{asset} contains an invalid path")
        staged = self.stage_dir(releases, f".{tool}.")
        if not self.extract_zip(archive_path, staged):
            archive_path.unlink(missing_ok=True)
            shutil.rmtree(staged, ignore_errors=True)
            self.skip(tool, f"{asset} could not be extracted")
        archive_path.unlink(missing_ok=True)
        if not validate(staged):
            shutil.rmtree(staged, ignore_errors=True)
            self.skip(tool, f"{asset} is missing the {tool} bundle")
        os.replace(staged, release_dir)
        self.own_dir(release_dir)
        if not self.switch_symlink(release_dir, current):
            self.skip(tool, f"could not switch {current}")
        self.own_file(current)
        for command in commands:
            self._ensure_bundle_link(tool, home, commands, in_bin=in_bin, command=command)
        if on_current is not None:
            on_current()
        self.write_state(state_name, record)
        self.changed = True
        self.ok(install_message)

    def ensure_git_templates(self) -> bool:
        templates = self.dest.parent / "share/git-core/templates"
        exclude = templates / "info/exclude"
        template = "# git ls-files --others --exclude-from=.git/info/exclude\n# Lines that start with '#' are comments."
        if exclude.is_symlink() or (exclude.exists() and not exclude.is_file()):
            self.skip("git", f"{exclude} is not a regular file")
        if not exclude.exists():
            self.own_missing_dirs(templates / "info")
            (templates / "info").mkdir(parents=True, exist_ok=True)
            exclude.write_text(template + "\n")
        if exclude.read_text().rstrip("\n") == template:
            self.own_file(exclude)
        return True

    def install_git(self) -> None:
        if not self.which("zipinfo"):
            self.skip("git", "zipinfo is required to validate the archive")
        triples = {("darwin", "aarch64"): "aarch64-apple-darwin",
                   ("linux", "x86_64"): "x86_64-unknown-linux-musl",
                   ("linux", "aarch64"): "aarch64-unknown-linux-musl"}
        if (self.os_name, self.arch) not in triples:
            self.skip("git", f"no git-build release for {self.os_name}/{self.arch}")
        triple = triples[(self.os_name, self.arch)]
        tag = self.latest_tag("https://github.com/laputa-systems/git-build/releases.atom")
        if not tag:
            self.unchecked("git", "no release found")
            return
        asset = f"git-{triple}.zip"
        base = f"https://github.com/laputa-systems/git-build/releases/download/{tag}"
        def validate(staged: Path) -> bool:
            if not (staged / "git").is_file() or not os.access(staged / "git", os.X_OK):
                return False
            if not (staged / "git-shell").is_file() or not os.access(staged / "git-shell", os.X_OK):
                return False
            for helper in ("git-upload-archive", "git-upload-pack", "git-receive-pack"):
                link = staged / helper
                if not link.is_symlink() or os.readlink(link) != "git":
                    return False
            return True
        self._zip_bundle("git", self.git_home, GIT_COMMANDS, "git", in_bin=False,
                         asset=asset, url=f"{base}/{asset}", sums_url=f"{base}/SHA256SUMS",
                         release_dir=self.git_home / "releases" / f"{tag}-{triple}",
                         validate=validate, ok_message=f"git is current ({tag})",
                         install_message=f"Installed {self.dest}/git",
                         on_current=self.ensure_git_templates)

    def install_ssh(self) -> None:
        if not self.which("zipinfo"):
            self.skip("ssh", "zipinfo is required to validate the archive")
        triples = {("darwin", "aarch64"): "aarch64-apple-darwin",
                   ("linux", "x86_64"): "x86_64-unknown-linux-musl",
                   ("linux", "aarch64"): "aarch64-unknown-linux-musl"}
        if (self.os_name, self.arch) not in triples:
            self.skip("ssh", f"no ssh-build release for {self.os_name}/{self.arch}")
        triple = triples[(self.os_name, self.arch)]
        tag = self.latest_tag("https://github.com/laputa-systems/ssh-build/releases.atom")
        if not tag:
            self.unchecked("ssh", "no release found")
            return
        asset = f"ssh-{triple}.zip"
        base = f"https://github.com/laputa-systems/ssh-build/releases/download/{tag}"
        def validate(staged: Path) -> bool:
            return all((staged / command).is_file() and os.access(staged / command, os.X_OK)
                       for command in SSH_COMMANDS)
        self._zip_bundle("ssh", self.ssh_home, SSH_COMMANDS, "ssh", in_bin=False,
                         asset=asset, url=f"{base}/{asset}", sums_url=f"{base}/SHA256SUMS",
                         release_dir=self.ssh_home / "releases" / f"{tag}-{triple}",
                         validate=validate, ok_message=f"ssh is current ({tag})",
                         install_message=f"Installed {self.dest}/ssh")

    def install_oxish(self) -> None:
        triples = {("darwin", "aarch64"): "aarch64-apple-darwin",
                   ("linux", "x86_64"): "x86_64-unknown-linux-musl",
                   ("linux", "aarch64"): "aarch64-unknown-linux-musl"}
        if (self.os_name, self.arch) not in triples:
            self.skip("oxish", f"no ssh-build release for {self.os_name}/{self.arch}")
        triple = triples[(self.os_name, self.arch)]
        tag = self.latest_tag("https://github.com/laputa-systems/ssh-build/releases.atom")
        if not tag:
            self.unchecked("oxish", "no release found")
            return
        asset = f"oxish-{triple}.zip"
        base = f"https://github.com/laputa-systems/ssh-build/releases/download/{tag}"
        def validate(staged: Path) -> bool:
            return all((staged / "bin" / command).is_file() and os.access(staged / "bin" / command, os.X_OK)
                       for command in OXISH_COMMANDS)
        self._zip_bundle("oxish", self.oxish_home, OXISH_COMMANDS, "oxish-server", in_bin=True,
                         asset=asset, url=f"{base}/{asset}", sums_url=f"{base}/SHA256SUMS",
                         release_dir=self.oxish_home / "releases" / f"{tag}-{triple}",
                         validate=validate, ok_message=f"oxish is current ({tag})",
                         install_message=f"Installed {self.dest}/oxish-server")

    def ffmpeg_pair_runs(self, release: Path) -> bool:
        for command in FFMPEG_COMMANDS:
            binary = release / "bin" / command
            if binary.is_symlink() or not binary.is_file() or not os.access(binary, os.X_OK):
                return False
            if self.run([str(binary), "-version"], capture=True).returncode:
                return False
        return True

    def install_ffmpeg(self) -> None:
        triples = {("darwin", "aarch64"): "aarch64-apple-darwin",
                   ("linux", "x86_64"): "x86_64-unknown-linux-musl",
                   ("linux", "aarch64"): "aarch64-unknown-linux-musl"}
        if (self.os_name, self.arch) not in triples:
            self.skip("ffmpeg", f"no ffmpeg-build release for {self.os_name}/{self.arch}")
        triple = triples[(self.os_name, self.arch)]
        tag = self.latest_date_tag(f"https://github.com/{FFMPEG_REPO}/releases.atom")
        if not tag:
            self.unchecked("ffmpeg", "no release found")
            return
        home = self.ffmpeg_home
        for command in FFMPEG_COMMANDS:
            existing = self.dest / command
            if existing.exists() or existing.is_symlink():
                target = os.readlink(existing) if existing.is_symlink() else ""
                if not (self._own_release_target(home, FFMPEG_COMMANDS, target, in_bin=True)
                        or self._own_current_target(home, FFMPEG_COMMANDS, target, in_bin=True)
                        or target == str(home / "current/bin" / command)):
                    self.skip("ffmpeg", f"{existing} is not a dl-managed symlink")
        releases = home / "releases"
        if releases.is_symlink() or (releases.exists() and not releases.is_dir()):
            self.skip("ffmpeg", f"{releases} is not a directory")
        current = home / "current"
        if current.exists() and not current.is_symlink():
            self.skip("ffmpeg", f"{current} is not a dl-managed symlink")
        release_base = f"https://github.com/{FFMPEG_REPO}/releases/download/{tag}"
        sums_path = Path(tempfile.mkstemp()[1])
        if not self.download(f"{release_base}/SHA256SUMS", sums_path):
            sums_path.unlink(missing_ok=True)
            self.unchecked("ffmpeg", f"SHA256SUMS is unavailable in {tag}")
            return
        suffix = f"-{triple}-tools.tar.gz"
        listed = []
        for line in sums_path.read_text().splitlines():
            fields = line.split()
            if len(fields) == 2 and len(fields[0]) == 64 and fields[1].startswith("ffmpeg-") \
                    and fields[1].endswith(suffix):
                listed.append((fields[0], fields[1]))
        sums_path.unlink(missing_ok=True)
        if len(listed) != 1:
            self.unchecked("ffmpeg", f"the {triple} tools archive is not listed in {tag}")
            return
        expected, asset = listed[0]
        if not re.match(rf"^ffmpeg-.*\+{re.escape(tag)}-{re.escape(triple)}-tools\.tar\.gz$", asset) \
                or re.search(r"[^A-Za-z0-9._+\-]", asset):
            self.unchecked("ffmpeg", f"the {triple} tools archive is not listed in {tag}")
            return
        url = f"{release_base}/{asset.replace('+', '%2B')}"
        record_id = self.asset_id(url)
        if not record_id:
            self.unchecked("ffmpeg", f"{asset} is unavailable")
            return
        record = f"{tag}:{record_id}"
        release_dir = releases / f"{tag}-{triple}"
        if self.is_current("ffmpeg", record) and current.is_symlink() \
                and os.readlink(current) == str(release_dir) and release_dir.is_dir() \
                and self.ffmpeg_pair_runs(release_dir):
            current_ok = True
            for command in FFMPEG_COMMANDS:
                have = os.readlink(self.dest / command) if (self.dest / command).is_symlink() else ""
                if have != str(home / "current/bin" / command) or not (self.dest / command).exists():
                    current_ok = False
                else:
                    self.own_file(self.dest / command)
            if current_ok and self._own_release_target(home, FFMPEG_COMMANDS, str(release_dir / "bin/ffmpeg"), in_bin=True):
                self.current(f"ffmpeg is current ({tag})")
                return
        replacing = False
        if release_dir.exists() or release_dir.is_symlink():
            if release_dir.is_symlink() or not release_dir.is_dir():
                self.skip("ffmpeg", f"{release_dir} is not a release directory")
            if self._state_text("ffmpeg") == record and self.ffmpeg_pair_runs(release_dir):
                if (os.readlink(current) if current.is_symlink() else "") != str(release_dir) \
                        and not self.switch_symlink(release_dir, current):
                    self.skip("ffmpeg", f"could not switch {current}")
                for command in FFMPEG_COMMANDS:
                    self._ensure_bundle_link("ffmpeg", home, FFMPEG_COMMANDS, in_bin=True, command=command)
                self.own_dir(release_dir)
                self.own_file(current)
                self.own_file(self.state / "ffmpeg")
                self.changed = True
                self.ok(f"Repaired {self.dest}/ffmpeg and {self.dest}/ffprobe")
                return
            replacing = True
        self.own_missing_dirs(releases)
        releases.mkdir(parents=True, exist_ok=True)
        self.fetch_msg(f"Downloading {asset} ...")
        with tempfile.NamedTemporaryFile(delete=False) as stream:
            archive_path = Path(stream.name)
        if not self.download(url, archive_path):
            archive_path.unlink(missing_ok=True)
            self.skip("ffmpeg", f"{asset} download failed")
        if self.sha256_file(archive_path) != expected:
            archive_path.unlink(missing_ok=True)
            self.skip("ffmpeg", f"{asset} checksum mismatch")
        members = self.tar_members(archive_path)
        if members is None or any(not (member.isreg() or member.isdir()) for member in members):
            archive_path.unlink(missing_ok=True)
            self.skip("ffmpeg", f"{asset} contains an unsupported member type")
        top = asset.removesuffix(".tar.gz")
        names = [member.name for member in members]
        if self.archive_paths_bad(names) or any(
                name not in (top, top + "/") and not name.startswith(top + "/") for name in names):
            archive_path.unlink(missing_ok=True)
            self.skip("ffmpeg", f"{asset} contains an invalid path")
        staged = self.stage_dir(releases, ".ffmpeg.")
        if not self.extract_tar(archive_path, staged, strip=1):
            archive_path.unlink(missing_ok=True)
            self.skip("ffmpeg", f"{asset} could not be extracted")
        archive_path.unlink(missing_ok=True)
        if not self.ffmpeg_pair_runs(staged):
            self.skip("ffmpeg", f"{asset} does not contain a working ffmpeg and ffprobe")
        old_release = None
        if replacing:
            old_release = releases / f".ffmpeg-old.{os.getpid()}"
            shutil.rmtree(old_release, ignore_errors=True)
            try:
                os.replace(release_dir, old_release)
            except OSError:
                self.skip("ffmpeg", f"could not replace {release_dir}")
        try:
            os.replace(staged, release_dir)
        except OSError:
            if old_release is not None:
                os.replace(old_release, release_dir)
            self.skip("ffmpeg", f"could not install {release_dir}")
        self.own_dir(release_dir)
        if not self.switch_symlink(release_dir, current):
            shutil.rmtree(release_dir, ignore_errors=True)
            if old_release is not None:
                os.replace(old_release, release_dir)
            self.skip("ffmpeg", f"could not switch {current}")
        if old_release is not None:
            shutil.rmtree(old_release, ignore_errors=True)
        self.own_file(current)
        self.write_state("ffmpeg", record)
        for command in FFMPEG_COMMANDS:
            self._ensure_bundle_link("ffmpeg", home, FFMPEG_COMMANDS, in_bin=True, command=command)
        self.changed = True
        self.ok(f"Installed {self.dest}/ffmpeg and {self.dest}/ffprobe")

    def write_opencode2_shim(self, target: Path) -> None:
        staged = self.stage_file(target.parent, ".opencode2-shim.")
        staged.write_text('#!/bin/sh\nexec "${HOME}/.opencode/bin/opencode" "$@"\n')
        staged.chmod(0o755)
        os.replace(staged, target)
        self.own_file(target)

    def opencode2_managed(self) -> bool:
        launcher = self.dest / "opencode2"
        if launcher.is_symlink():
            return os.readlink(launcher) == str(self.opencode2_home / "bin/opencode2")
        if not launcher.is_file() or not os.access(launcher, os.X_OK):
            return False
        try:
            return launcher.read_text().rstrip("\n") == '#!/bin/sh\nexec "${HOME}/.opencode/bin/opencode" "$@"'
        except OSError:
            return False

    def opencode2_legacy(self) -> bool:
        launcher = self.dest / "opencode2"
        return launcher.is_file() and not launcher.is_symlink() \
            and (self.state / "opencode2").is_file() and self.legacy_binary("opencode2")

    def install_opencode2(self) -> None:
        if self.installed("opencode2") and not self.opencode2_legacy() and not self.opencode2_managed():
            if (self.dest / "opencode2").is_file() and not (self.dest / "opencode2").is_symlink() \
                    and (self.state / "opencode2").is_file() and not self.which("file"):
                self.warn("Warning: file is required to identify the existing OpenCode 2 launcher; keeping it")
            self.current("opencode2 is installed")
            return
        assets = {("darwin", "x86_64"): "opencode-darwin-x64.zip", ("darwin", "aarch64"): "opencode-darwin-arm64.zip",
                  ("linux", "x86_64"): "opencode-linux-x64.tar.gz", ("linux", "aarch64"): "opencode-linux-arm64.tar.gz"}
        if (self.os_name, self.arch) not in assets:
            self.skip("opencode2", f"no upstream binary for {self.os_name}/{self.arch}")
        asset = assets[(self.os_name, self.arch)]
        ldd_result = self.run(["ldd", "--version"], capture=True) if self.which("ldd") else None
        if self.os_name == "linux" and (Path("/etc/alpine-release").exists()
                or (ldd_result is not None and "musl" in (ldd_result.stdout + ldd_result.stderr).lower())):
            asset = asset.removesuffix(".tar.gz") + "-musl.tar.gz"
        url = f"https://opencode.ai/update/api/latest/cli/opencode/{asset}"
        record = self.asset_id(url)
        if not record:
            self.unchecked("opencode2", f"{asset} is unavailable")
            return
        bin_dir = self.opencode2_home / "bin"
        if not self.opencode2_legacy() and self.is_current("opencode2", record):
            self.write_opencode2_shim(bin_dir / "opencode2")
            self.write_opencode2_shim(self.dest / "opencode2")
            self.own_file(bin_dir / "opencode")
            self.current("opencode2 is current")
            return
        binary = bin_dir / "opencode"
        if binary.exists() or binary.is_symlink():
            if not self.opencode2_managed() or not (self.state / "opencode2").is_file():
                self.skip("opencode2", f"{binary} already exists")
        self.own_missing_dirs(bin_dir)
        bin_dir.mkdir(parents=True, exist_ok=True)
        self.fetch_msg("Downloading opencode2 ...")
        with tempfile.NamedTemporaryFile(delete=False) as stream:
            archive_path = Path(stream.name)
        if not self.download(url, archive_path):
            archive_path.unlink(missing_ok=True)
            self.skip("opencode2", "download failed")
        staged = self.stage_file(bin_dir, ".opencode2.")
        if asset.endswith(".zip"):
            member = self.zip_member(archive_path, "opencode")
        else:
            member = self.tar_member(archive_path, "opencode")
        archive_path.unlink(missing_ok=True)
        if not member:
            staged.unlink(missing_ok=True)
            self.skip("opencode2", f"{asset} is missing the opencode binary")
        staged.write_bytes(member)
        if self.os_name == "darwin":
            self.run(["xattr", "-d", "com.apple.quarantine", str(staged)])
            self.run(["codesign", "-fs", "-", str(staged)], check=True)
        staged.chmod(staged.stat().st_mode | 0o111)
        os.replace(staged, binary)
        self.own_file(binary)
        self.write_opencode2_shim(bin_dir / "opencode2")
        self.write_opencode2_shim(self.dest / "opencode2")
        self.write_state("opencode2", record)
        self.changed = True
        self.ok(f"Installed {self.dest}/opencode2")

    def install_player(self) -> None:
        assets = {("darwin", "aarch64"): "Player-aarch64-apple-darwin.zip",
                  ("linux", "x86_64"): "player-x86_64-linux-musl.tar.gz"}
        if (self.os_name, self.arch) not in assets:
            self.skip("player", f"no Player release for {self.os_name}/{self.arch}")
        asset_name = assets[(self.os_name, self.arch)]
        tag = self.latest_tag(f"https://github.com/{PLAYER_REPO}/releases.atom")
        if not tag:
            self.unchecked("player", "no release found")
            return
        base = f"https://github.com/{PLAYER_REPO}/releases/download/{tag}"
        url = f"{base}/{asset_name}"
        record_id = self.asset_id(url)
        if not record_id:
            self.unchecked("player", f"{asset_name} is unavailable")
            return
        record = f"{tag}:{record_id}"
        launcher = self.dest / "player"
        launcher_target = os.readlink(launcher) if launcher.is_symlink() else ""
        if self.os_name == "darwin":
            if self._state_text("player") == record and self.player_app.is_dir() \
                    and not self.player_app.is_symlink() and (self.player_exec).is_file() \
                    and os.access(self.player_exec, os.X_OK):
                if launcher_target != str(self.player_exec):
                    self.link_symlink(launcher, str(self.player_exec))
                    self.changed = True
                self.own_dir(self.player_app)
                self.own_file(launcher)
                self.own_file(self.state / "player")
                self.current(f"player is current ({tag})")
                return
            if self.player_app.is_symlink() or (self.player_app.exists() and not (self.state / "player").is_file()):
                self.skip("player", f"existing {self.player_app} is not managed by dl")
            if (launcher.exists() or launcher.is_symlink()) and launcher_target != str(self.player_exec):
                self.skip("player", f"existing {launcher} is not managed by dl")
        else:
            if self._state_text("player") == record and launcher.is_file() and not launcher.is_symlink() \
                    and os.access(launcher, os.X_OK):
                self.own_file(launcher)
                self.own_file(self.state / "player")
                self.current(f"player is current ({tag})")
                return
            if (launcher.exists() or launcher.is_symlink()) and not (self.state / "player").is_file():
                self.skip("player", f"existing {launcher} is not managed by dl")
        self.fetch_msg(f"Downloading {asset_name} ...")
        with tempfile.NamedTemporaryFile(delete=False) as stream:
            archive_path = Path(stream.name)
        if not self.download(url, archive_path):
            archive_path.unlink(missing_ok=True)
            self.skip("player", f"{asset_name} download failed")
        sums_path = Path(tempfile.mkstemp()[1])
        if not self.download(f"{base}/SHA256SUMS", sums_path):
            archive_path.unlink(missing_ok=True)
            sums_path.unlink(missing_ok=True)
            self.skip("player", "SHA256SUMS download failed")
        expected = self.sums_for(sums_path.read_text(), asset_name)
        sums_path.unlink(missing_ok=True)
        if len(expected) != 64 or self.sha256_file(archive_path) != expected:
            archive_path.unlink(missing_ok=True)
            self.skip("player", f"{asset_name} checksum mismatch")
        if self.os_name == "darwin":
            self.own_missing_dirs(self.player_apps)
            self.player_apps.mkdir(parents=True, exist_ok=True)
            staged = self.stage_dir(self.player_apps, ".player.")
            if not self.extract_zip(archive_path, staged):
                archive_path.unlink(missing_ok=True)
                self.skip("player", "release archive is invalid")
            archive_path.unlink(missing_ok=True)
            if not (staged / "Player.app/Contents/MacOS/player").is_file():
                self.skip("player", "release archive is invalid")
            if self.run(["codesign", "--verify", "--deep", "--strict", str(staged / "Player.app")]).returncode:
                self.skip("player", "signature verification failed")
            self.run(["xattr", "-dr", "com.apple.quarantine", str(staged / "Player.app")])
            previous = None
            if self.player_app.is_dir():
                previous = Path(tempfile.mkdtemp(prefix=".player-previous.", dir=self.player_apps))
                previous.rmdir()
                try:
                    os.replace(self.player_app, previous)
                except OSError:
                    self.skip("player", "cannot move previous application")
            try:
                os.replace(staged / "Player.app", self.player_app)
            except OSError:
                if previous is not None:
                    os.replace(previous, self.player_app)
                self.skip("player", "cannot install application")
            shutil.rmtree(staged, ignore_errors=True)
            if previous is not None:
                shutil.rmtree(previous, ignore_errors=True)
            if launcher_target != str(self.player_exec):
                self.link_symlink(launcher, str(self.player_exec))
            self.own_dir(self.player_app)
            self.own_file(launcher)
            self.write_state("player", record)
            self.changed = True
            self.ok(f"Installed {self.player_app} ({tag})")
            return
        names = self.tar_names(archive_path)
        if names is None or names.count("player") != 1:
            archive_path.unlink(missing_ok=True)
            self.skip("player", f"{asset_name} does not contain exactly one player binary")
        staged = self.stage_file(self.dest, ".player.")
        member = self.tar_member(archive_path, "player")
        archive_path.unlink(missing_ok=True)
        if not member:
            staged.unlink(missing_ok=True)
            self.skip("player", f"{asset_name} could not extract player")
        staged.write_bytes(member)
        self.install_binary("player", staged, record)

    def install_ghostty_custom(self) -> None:
        if self.os_name != "darwin":
            self.skip("ghostty-custom", "macOS only")
        if self.arch != "aarch64":
            self.skip("ghostty-custom", "only aarch64 prereleases are published")
        tag = self.latest_tag("https://github.com/joshuarli/ghostty/releases.atom", prefix="release-")
        if not tag:
            self.unchecked("ghostty-custom", "no prerelease found")
            return
        base = f"https://github.com/joshuarli/ghostty/releases/download/{tag}"
        url = f"{base}/{GHOSTTY_CUSTOM_ASSET}"
        record = self.asset_id(url)
        if not record:
            self.unchecked("ghostty-custom", f"{GHOSTTY_CUSTOM_ASSET} is not available in {tag}")
            return
        installed_id = self._state_text("ghostty-custom")
        launcher = self.dest / "ghostty-custom"
        launcher_target = os.readlink(launcher) if launcher.is_symlink() else ""
        if self.ghostty_app.is_dir() and not self.ghostty_app.is_symlink() and installed_id == record \
                and self.ghostty_exec.is_file() and os.access(self.ghostty_exec, os.X_OK) \
                and launcher_target == str(self.ghostty_exec):
            self.own_dir(self.ghostty_app)
            self.own_file(launcher)
            self.own_file(self.state / "ghostty-custom")
            self.current(f"ghostty-custom is current ({tag})")
            return
        if self.ghostty_app.is_symlink() or (self.ghostty_app.exists() and not installed_id):
            self.skip("ghostty-custom", f"existing {self.ghostty_app} is not managed by dl")
        if (launcher.exists() or launcher.is_symlink()) and launcher_target != str(self.ghostty_exec):
            self.skip("ghostty-custom", f"existing {launcher} is not managed by dl")
        self.fetch_msg(f"Downloading {GHOSTTY_CUSTOM_ASSET} ({tag}) ...")
        tmpdir = Path(self.env.get("TMPDIR") or "/tmp")
        archive_path = Path(tempfile.mkstemp(prefix="ghostty-custom.", suffix=".dmg", dir=tmpdir)[1])
        if not self.download(url, archive_path):
            archive_path.unlink(missing_ok=True)
            self.skip("ghostty-custom", "download failed")
        sums_path = Path(tempfile.mkstemp()[1])
        if not self.download(f"{base}/SHA256SUMS", sums_path):
            archive_path.unlink(missing_ok=True)
            sums_path.unlink(missing_ok=True)
            self.skip("ghostty-custom", "SHA256SUMS download failed")
        expected = self.sums_for(sums_path.read_text(), GHOSTTY_CUSTOM_ASSET)
        sums_path.unlink(missing_ok=True)
        if len(expected) != 64 or self.sha256_file(archive_path) != expected:
            archive_path.unlink(missing_ok=True)
            self.skip("ghostty-custom", "checksum mismatch")
        self.own_missing_dirs(self.ghostty_apps)
        self.ghostty_apps.mkdir(parents=True, exist_ok=True)
        staged = self.stage_dir(self.ghostty_apps, ".ghostty-custom.")
        mountpoint = Path(tempfile.mkdtemp(prefix="ghostty-custom-mnt.", dir=tmpdir))
        try:
            if self.run(["hdiutil", "attach", "-nobrowse", "-mountpoint", str(mountpoint), str(archive_path)], capture=True).returncode:
                self.skip("ghostty-custom", "release image is invalid")
            if self.run(["ditto", str(mountpoint / "Ghostty Custom.app"), str(staged / "Ghostty Custom.app")]).returncode \
                    or not (staged / "Ghostty Custom.app/Contents/MacOS/ghostty").is_file():
                self.skip("ghostty-custom", "release archive is invalid")
        finally:
            self.run(["hdiutil", "detach", str(mountpoint)])
            shutil.rmtree(mountpoint, ignore_errors=True)
        archive_path.unlink(missing_ok=True)
        bundle_id = self.run(["plutil", "-extract", "CFBundleIdentifier", "raw", "-o", "-",
                              str(staged / "Ghostty Custom.app/Contents/Info.plist")], capture=True).stdout.strip()
        if bundle_id != GHOSTTY_CUSTOM_BUNDLE_ID:
            self.skip("ghostty-custom", f"bundle id {bundle_id or 'unknown'} does not match {GHOSTTY_CUSTOM_BUNDLE_ID}")
        previous = None
        if self.ghostty_app.is_dir():
            previous = Path(tempfile.mkdtemp(prefix=".ghostty-custom-previous.", dir=self.ghostty_apps))
            previous.rmdir()
            try:
                os.replace(self.ghostty_app, previous)
            except OSError:
                self.skip("ghostty-custom", "cannot move previous application")
        try:
            os.replace(staged / "Ghostty Custom.app", self.ghostty_app)
        except OSError:
            if previous is not None:
                os.replace(previous, self.ghostty_app)
            self.skip("ghostty-custom", "cannot install application")
        shutil.rmtree(staged, ignore_errors=True)
        if previous is not None:
            shutil.rmtree(previous, ignore_errors=True)
        if launcher_target != str(self.ghostty_exec):
            self.link_symlink(launcher, str(self.ghostty_exec))
        self.own_dir(self.ghostty_app)
        self.own_file(launcher)
        self.write_state("ghostty-custom", record)
        self.changed = True
        self.ok(f"Installed {self.ghostty_app} ({tag})")

    def install_mactop_app(self) -> None:
        app = Path("/Applications/mactop.app")
        self.fetch_msg(f"Installing {app} ...")
        staged = self.stage_dir(app.parent, ".mactop.")
        (staged / "Contents/MacOS").mkdir(parents=True)
        shutil.copy2(self.dest / "mactop", staged / "Contents/MacOS/mactop")
        (staged / "Contents/Info.plist").write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
            '<plist version="1.0">\n<dict>\n'
            '\t<key>CFBundleName</key><string>mactop</string>\n'
            '\t<key>CFBundleDisplayName</key><string>mactop</string>\n'
            '\t<key>CFBundleIdentifier</key><string>com.mactop</string>\n'
            '\t<key>CFBundleExecutable</key><string>mactop</string>\n'
            '\t<key>CFBundlePackageType</key><string>APPL</string>\n'
            '\t<key>CFBundleVersion</key><string>0.1.0</string>\n'
            '\t<key>CFBundleShortVersionString</key><string>0.1.0</string>\n'
            '\t<key>LSUIElement</key><true/>\n'
            '\t<key>NSHighResolutionCapable</key><true/>\n'
            '\t<key>NSSupportsAutomaticGraphicsSwitching</key><true/>\n'
            '</dict>\n</plist>\n')
        self.run(["codesign", "--force", "--sign", "-", str(staged)], check=True)
        self.run(["xattr", "-dr", "com.apple.quarantine", str(staged)])
        shutil.rmtree(app, ignore_errors=True)
        os.replace(staged, app)
        self.ok(f"Installed {app}")
        self.own_dir(app)
        agent = self.home / "Library/LaunchAgents/com.mactop.plist"
        self.own_missing_dirs(agent.parent)
        agent.parent.mkdir(parents=True, exist_ok=True)
        agent.write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"\n'
            '  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
            '<plist version="1.0">\n<dict>\n'
            '  <key>Label</key><string>com.mactop</string>\n'
            '  <key>ProgramArguments</key><array>\n'
            f'    <string>{self.dest}/mactop</string>\n'
            '  </array>\n  <key>RunAtLoad</key><true/>\n</dict>\n</plist>\n')
        self.own_file(agent)
        uid = str(os.getuid())
        self.run(["launchctl", "bootout", f"gui/{uid}", str(agent)])
        self.run(["launchctl", "bootstrap", f"gui/{uid}", str(agent)], check=True)
        self.run(["launchctl", "kickstart", "-k", f"gui/{uid}/com.mactop"], check=True)
        self.ok(f"Loaded {agent}")

    def install(self, tool: str) -> None:
        handlers = {
            "fd": lambda: self.install_fd_or_rg("fd"), "rg": lambda: self.install_fd_or_rg("rg"),
            "grok": self.install_grok, "fx": self.install_fx, "dsh": self.install_dsh,
            "cmd": self.install_cmd, "pnpm": self.install_pnpm, "cf": self.install_cf,
            "agent-browser": self.install_agent_browser, "pi": self.install_pi,
            "antigravity": self.install_antigravity, "agy": self.install_antigravity,
            "muse": self.install_muse, "claude": self.install_claude, "codex": self.install_codex,
            "opencode2": self.install_opencode2,
            "ghostty": self.install_ghostty_custom, "ghostty-custom": self.install_ghostty_custom,
            "play": self.install_player, "player": self.install_player,
            "jaq": self.install_jaq, "mold": self.install_mold, "nodejs": self.install_nodejs,
            "python3": self.install_python3, "uv": self.install_uv, "node-build": self.install_nodebuild,
            "git": self.install_git, "ffmpeg": self.install_ffmpeg, "ssh": self.install_ssh,
            "oxish": self.install_oxish, "zzz": self.install_zzz,
        }
        if tool in handlers:
            handlers[tool]()
        else:
            self.install_release(tool)
            if tool == "mactop" and self.os_name == "darwin" and (self.dest / "mactop").exists() \
                    and (self.changed or not Path("/Applications/mactop.app").is_dir()):
                self.install_mactop_app()

    def record_managed_binary(self, prog: str) -> None:
        if (self.state / prog).is_file():
            self.own_file(self.state / prog)
            if self.installed(prog):
                self.own_file(self.dest / prog)

    def record_managed_installs(self) -> None:
        for prog in ("fd", "rg", "jaq", "fastermod", "tm", "ish", "stuff", "e", "fz", "fdu", "fs",
                     "srv", "mactop", "vault", "gh", "bylaws", "mold", "cf", "player", "soulseek-rs",
                     "zzz", "uv", "uvx", "rage", "shellcheck"):
            self.record_managed_binary(prog)
        if self.installed("rage") and (self.dest / "rage-keygen").is_symlink():
            self.own_file(self.dest / "rage-keygen")
        if (self.state / "cf").is_file() and (self.state / "cf").stat().st_size > 0 and self.cf_root.is_dir():
            self.own_dir(self.cf_root)
        nodejs_current = self.nodejs_root / "current"
        if nodejs_current.is_symlink():
            target = os.readlink(nodejs_current)
            if target.startswith(str(self.nodejs_root) + os.sep):
                release = Path(target).name
                if re.match(rf"^{re.escape(NODEJS_VERSION)}-npm\d+\.\d+\.\d+([.-][A-Za-z0-9.-]+)?-"
                            r"(darwin-arm64|linux-x64|linux-arm64|linux-x64-musl|linux-arm64-musl)$", release):
                    release_dir = self.nodejs_root / release
                    if release_dir.is_dir():
                        self.own_dir(self.nodejs_root)
                        self.own_file(nodejs_current)
                        for command in ("node", "npm", "npx"):
                            if (self.dest / command).is_symlink() and os.readlink(self.dest / command) == str(self.nodejs_root / "current/bin" / command):
                                self.own_file(self.dest / command)
        if (self.state / "mold").is_file() and (self.state / "mold").stat().st_size > 0 \
                and (self.dest / "ld.mold").is_symlink() and os.readlink(self.dest / "ld.mold") == "mold":
            self.own_file(self.dest / "ld.mold")
        if (self.state / "python3").is_file() and (self.state / "python3").stat().st_size > 0:
            target = os.readlink(self.dest / "python3") if (self.dest / "python3").is_symlink() else ""
            if target.startswith(str(self.python_build_root) + os.sep) and target.endswith("/python/bin/python3.15"):
                own_dir = Path(target.removesuffix("/python/bin/python3.15"))
                if own_dir.is_dir():
                    self.own_dir(own_dir)
                    self.own_file(self.dest / "python3")
                    self.own_file(self.state / "python3")
                    if (self.dest / "python3.15").is_symlink() and os.readlink(self.dest / "python3.15") == target:
                        self.own_file(self.dest / "python3.15")
        if (self.state / "node-build").is_file() and (self.state / "node-build").stat().st_size > 0:
            target = os.readlink(self.dest / "node-build") if (self.dest / "node-build").is_symlink() else ""
            if target.startswith(str(self.node_build_root) + os.sep) and target.endswith("/node/bin/node"):
                own_dir = Path(target.removesuffix("/node/bin/node"))
                if own_dir.is_dir():
                    self.own_dir(own_dir)
                    self.own_file(self.dest / "node-build")
                    self.own_file(self.state / "node-build")
        if (self.state / "claude").is_file() and (self.state / "claude").stat().st_size > 0:
            target = os.readlink(self.dest / "claude") if (self.dest / "claude").is_symlink() else ""
            if "/../" not in f"/{target}/":
                if target.startswith(str(self.home / ".claude") + os.sep) or target.startswith(str(self.claude_versions) + os.sep):
                    self.own_file(Path(target))
        self.record_managed_binary("fx")
        self.record_managed_binary("grok")
        if (self.state / "grok").is_file() and (self.state / "grok").stat().st_size > 0 \
                and (self.dest / "grok").is_symlink() and os.readlink(self.dest / "grok") == str(self.grok_home / "bin/grok"):
            self.own_file(self.grok_home / "bin/grok")
            target = os.readlink(self.grok_home / "bin/grok") if (self.grok_home / "bin/grok").is_symlink() else ""
            self.own_grok_target(target)
        self.record_managed_binary("codex")
        if (self.state / "codex").is_file() and (self.state / "codex").stat().st_size > 0:
            target = os.readlink(self.dest / "codex") if (self.dest / "codex").is_symlink() else ""
            if self.own_codex_release_target(target):
                mode_host = self.dest / "codex-code-mode-host"
                mode_target = os.readlink(mode_host) if mode_host.is_symlink() else ""
                if mode_target == f"{target.removesuffix('/bin/codex')}/bin/codex-code-mode-host":
                    self.own_file(mode_host)
        for tool, root, binary in (("cmd", self.cmd_root, "cmd"), ("pnpm", self.pnpm_root, "pnpm"),
                                   ("pi", self.pi_root, "pi"),
                                   ("agent-browser", self.agent_browser_root, "agent-browser")):
            if (self.state / tool).is_file() and (self.state / tool).stat().st_size > 0:
                self.own_file(self.state / tool)
                if root.is_dir() and not root.is_symlink() and (root / "bin" / binary).is_file() \
                        and os.access(root / "bin" / binary, os.X_OK) \
                        and (self.dest / binary).is_symlink() and os.readlink(self.dest / binary) == str(root / "bin" / binary):
                    self.own_dir(root)
                    self.own_file(self.dest / binary)
        self.record_managed_binary("opencode2")
        if (self.state / "opencode2").is_file() and (self.state / "opencode2").stat().st_size > 0 and self.opencode2_managed():
            self.own_file(self.opencode2_home / "bin/opencode2")
            self.own_file(self.opencode2_home / "bin/opencode")
        for prog in ("dsh", "dsh-tui"):
            if (self.state / prog).is_file():
                self.own_file(self.state / prog)
        if ((self.state / "dsh").is_file() and (self.state / "dsh").stat().st_size > 0) or \
                ((self.state / "dsh-tui").is_file() and (self.state / "dsh-tui").stat().st_size > 0):
            if self.dsh_root.is_dir():
                self.own_dir(self.dsh_root)
        if (self.state / "ghostty-custom").is_file() and (self.state / "ghostty-custom").stat().st_size > 0:
            self.own_file(self.state / "ghostty-custom")
            if self.ghostty_app.is_dir() and not self.ghostty_app.is_symlink():
                self.own_dir(self.ghostty_app)
            if (self.dest / "ghostty-custom").is_symlink() and os.readlink(self.dest / "ghostty-custom") == str(self.ghostty_exec):
                self.own_file(self.dest / "ghostty-custom")
        if (self.state / "mactop").is_file() and (self.state / "mactop").stat().st_size > 0:
            if Path("/Applications/mactop.app").is_dir():
                self.own_dir(Path("/Applications/mactop.app"))
            agent = self.home / "Library/LaunchAgents/com.mactop.plist"
            if agent.is_file():
                self.own_file(agent)
        if (self.state / "ffmpeg").is_file() and (self.state / "ffmpeg").stat().st_size > 0:
            target = os.readlink(self.ffmpeg_home / "current") if (self.ffmpeg_home / "current").is_symlink() else ""
            if self._own_release_target(self.ffmpeg_home, FFMPEG_COMMANDS, f"{target}/bin/ffmpeg", in_bin=True) and Path(target).is_dir():
                self.own_file(self.state / "ffmpeg")
                self.own_file(self.ffmpeg_home / "current")
                for command in FFMPEG_COMMANDS:
                    if (self.dest / command).is_symlink() and os.readlink(self.dest / command) == str(self.ffmpeg_home / "current/bin" / command):
                        self.own_file(self.dest / command)
        if (self.state / "player").is_file() and (self.state / "player").stat().st_size > 0 \
                and self.os_name == "darwin" and self.player_app.is_dir() and not self.player_app.is_symlink():
            self.own_dir(self.player_app)

    def report_unowned_launcher(self, prog: str) -> None:
        launcher = self.dest / prog
        if self.installed(prog) and ("F", launcher) not in set(self.claims):
            self.warn(f"Leaving untracked launcher: {launcher}")
            if launcher.is_symlink():
                target = os.readlink(launcher)
                if target:
                    self.warn(f"Its target is also untracked: {target}")


def default_tools(os_name: str, arch: str, profile: str, server_tools: Path | None = None) -> list[str]:
    tools = ["fd", "rg"]
    if not (os_name == "linux" and arch == "aarch64"):
        tools.append("jaq")
    tools += "codex claude opencode2 pi fastermod tm ish stuff e fz fdu fs srv git python3 uv cf agent-browser rage".split()
    if (os_name, arch) in (("darwin", "aarch64"), ("linux", "x86_64"), ("linux", "aarch64")):
        tools += ["ffmpeg", "nodejs", "pnpm", "cmd", "syncthing", "shuck"]
    if (os_name, arch) in (("linux", "x86_64"), ("linux", "aarch64")):
        tools.append("zzz")
    if os_name == "darwin":
        tools += ["mactop", "vault", "ghostty-custom"]
    tools.append("gh")
    if (os_name, arch) == ("linux", "x86_64"):
        tools += ["mold", "player"]
    elif (os_name, arch) == ("linux", "aarch64"):
        tools.append("mold")
    if profile == "server":
        if server_tools is None or not server_tools.is_file():
            raise InstallError(f"server tool profile is missing: {server_tools}")
        allowed = set(server_tools.read_text().split())
        tools = [tool for tool in tools if tool in allowed]
    return tools


def _profile(env: dict[str, str]) -> str:
    profile = env.get("DL_PROFILE", "")
    if not profile:
        mode = Path("/etc/home/install-mode")
        if mode.is_file():
            profile = mode.read_text().strip()
    return profile if profile in ("server", "desktop") else ""


def main(argv: list[str]) -> int:
    import os as os_module
    home = Path(os_module.environ.get("HOME", str(Path.home())))
    installer = Installer(home, env=dict(os_module.environ))
    if argv == ["--list"]:
        repo_root = Path(__file__).resolve().parents[2]
        for tool in default_tools(installer.os_name, installer.arch, _profile(installer.env),
                                  repo_root / "host/alpine/tools-server.txt"):
            print(tool)
        return 0
    if installer.env.get("DL_RECORD_OWNED") == "true":
        if not installer.env.get("DL_OWNED_FILE"):
            print("✗ DL_OWNED_FILE is required to record installed paths", file=sys.stderr)
            return 1
        installer.record_managed_installs()
        for prog in ("agy", "muse", "claude"):
            installer.report_unowned_launcher(prog)
        claims_path = installer.env.get("SYNC_OWNED_CLAIMS")
        owned_path = installer.env["DL_OWNED_FILE"]
        seen = set()
        try:
            seen = {line for line in Path(owned_path).read_text().splitlines() if line}
        except OSError:
            pass
        with Path(owned_path).open("a") as stream:
            for kind, path in installer.claims:
                line = f"{kind}\t{path}"
                if line not in seen:
                    stream.write(line + "\n")
                    seen.add(line)
        return 0
    if not argv:
        argv = default_tools(installer.os_name, installer.arch, _profile(installer.env),
                             Path(__file__).resolve().parents[2] / "host/alpine/tools-server.txt")
    if len(argv) > 1:
        failed = False
        for tool in argv:
            single = Installer(home, os_name=installer.os_name, arch=installer.arch, env=dict(os_module.environ))
            try:
                single.install(tool)
            except InstallError as exc:
                print(f"✗ {exc}", file=sys.stderr)
                failed = True
        return 1 if failed else 0
    tool = argv[0]
    try:
        installer.install(tool)
    except InstallError as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return 1
    claims_path = installer.env.get("SYNC_OWNED_CLAIMS")
    if claims_path:
        Path(claims_path).write_text("".join(f"{kind}\t{path}\n" for kind, path in installer.claims)
                                     + "".join(f"!\t{path}\n" for path in sorted(installer.removed)))
    owned_path = installer.env.get("DL_OWNED_FILE")
    if owned_path:
        seen = set()
        try:
            seen = {line for line in Path(owned_path).read_text().splitlines() if line}
        except OSError:
            pass
        with Path(owned_path).open("a") as stream:
            for kind, path in installer.claims:
                line = f"{kind}\t{path}"
                if line not in seen:
                    stream.write(line + "\n")
                    seen.add(line)
    changed_path = installer.env.get("SYNC_INSTALL_CHANGED_FILE")
    if changed_path and installer.changed:
        Path(changed_path).write_text("changed\n")
    print("✓ Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))


"""Install the pinned pi-build release closure and bind the Pi bridge to its selection."""
from __future__ import annotations

from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import tarfile
import tempfile
from uuid import uuid4
from typing import TypeGuard, TypedDict
import urllib.error
import urllib.parse
import urllib.request

import pi_offline

HEX = re.compile(r"[0-9a-f]{64}")
TRIPLES = {"darwin-arm64": "aarch64-apple-darwin", "linux-x64": "x86_64-unknown-linux-musl",
           "linux-arm64": "aarch64-unknown-linux-musl"}
VERSION = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+")
RECEIPT = ".usr-pi-release.json"
PIN = Path(__file__).resolve().parents[2] / "tools/pi/runtime.pin.json"


class Artifact(TypedDict):
    archive: str
    sha256: str
    bytes: int


class Pin(TypedDict):
    schema: int
    release_url: str
    builder_revision: str
    profile: str
    version: str
    provenance_sha256: str
    targets: dict[str, Artifact]


def _is_pin(value: object) -> TypeGuard[Pin]:
    if not isinstance(value, dict):
        return False
    targets = value.get("targets")
    return (type(value.get("schema")) is int
            and all(isinstance(value.get(key), str) for key in (
                "release_url", "builder_revision", "profile", "version", "provenance_sha256"))
            and isinstance(targets, dict)
            and all(isinstance(target, str) and isinstance(entry, dict)
                    and isinstance(entry.get("archive"), str) and isinstance(entry.get("sha256"), str)
                    and type(entry.get("bytes")) is int
                    for target, entry in targets.items()))


def load_pin(path: Path = PIN) -> Pin:
    try:
        pin: object = json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        raise pi_offline.OfflinePiError(f"cannot read Pi release pin {path}: {exc}") from exc
    if not _is_pin(pin):
        raise pi_offline.OfflinePiError(f"invalid Pi release pin: {path}")
    return pin


def archive_name(pin: Pin, target: str) -> str:
    return f"pi-{pin['profile']}-{pin['version']}-{TRIPLES[target]}.tar.xz"


def pin_entry(pin: Pin, target: str) -> Artifact:
    try:
        entry = pin["targets"][target]
        url = urllib.parse.urlsplit(pin["release_url"])
        if (pin["schema"] != 1 or target not in TRIPLES
                or pin["profile"] not in {"full", "headless-usr"}
                or not VERSION.fullmatch(pin["version"])
                or not re.fullmatch(r"[0-9a-f]{40}", pin["builder_revision"])
                or not HEX.fullmatch(pin["provenance_sha256"])
                or url.scheme not in {"https", "http"} or not url.netloc
                or url.query or url.fragment or url.username or url.password
                or (url.scheme == "http" and url.hostname not in {"127.0.0.1", "localhost", "::1"})
                or entry["archive"] != archive_name(pin, target)
                or not HEX.fullmatch(entry["sha256"])
                or type(entry["bytes"]) is not int or entry["bytes"] <= 0):
            raise ValueError("invalid identity")
    except (KeyError, TypeError, ValueError) as exc:
        raise pi_offline.OfflinePiError(f"invalid Pi release pin: {exc}") from exc
    return entry


def sync_directory(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def sync_tree(root: Path) -> None:
    for path in root.rglob("*"):
        if not path.is_symlink() and path.is_file():
            with path.open("rb") as stream:
                os.fsync(stream.fileno())
    directories = [path for path in root.rglob("*") if path.is_dir() and not path.is_symlink()]
    for path in sorted(directories, key=lambda path: len(path.parts), reverse=True):
        sync_directory(path)
    sync_directory(root)


def fetch(url: str, path: Path, limit: int) -> None:
    try:
        response = urllib.request.urlopen(url, timeout=30)
    except urllib.error.HTTPError as error:
        error.close()
        raise
    with response, path.open("xb") as stream:
        count = 0
        while block := response.read(min(1 << 20, limit + 1)):
            count += len(block)
            if count > limit:
                raise pi_offline.OfflinePiError("Pi release asset exceeds pinned size")
            stream.write(block)
        stream.flush()
        os.fsync(stream.fileno())


def verified(file: Path, sha256: str, size: int) -> bool:
    return (not file.is_symlink() and file.is_file() and file.stat().st_size == size
            and pi_offline.digest(file) == sha256)


def acquire(pin: Pin, target: str, cache: Path) -> Path:
    entry = pin_entry(pin, target)
    if cache.is_symlink():
        raise pi_offline.OfflinePiError("refusing symlinked Pi cache")
    cache.mkdir(parents=True, exist_ok=True)
    archive = cache / (entry["sha256"] + ".tar.xz")
    if verified(archive, entry["sha256"], entry["bytes"]):
        return archive
    with tempfile.TemporaryDirectory(prefix=".download-", dir=cache) as temp:
        stage = Path(temp)
        base = pin["release_url"].rstrip("/") + "/"
        provenance = stage / "provenance.json"
        fetch(base + "provenance.json", provenance, 8 << 20)
        if pi_offline.digest(provenance) != pin["provenance_sha256"]:
            raise pi_offline.OfflinePiError("Pi provenance digest mismatch")
        data = json.loads(provenance.read_text())
        expected = {"target": TRIPLES[target], "profile": pin["profile"], **entry}
        if (data.get("schema") != 1 or data.get("builder_revision") != pin["builder_revision"]
                or data.get("version") != pin["version"]
                or data.get("targets", {}).get(TRIPLES[target]) != expected):
            raise pi_offline.OfflinePiError("Pi provenance identity mismatch")
        sums = stage / "SHA256SUMS"
        fetch(base + "SHA256SUMS", sums, 1 << 20)
        matches = [line.split() for line in sums.read_text().splitlines()
                   if len(line.split()) == 2 and line.split()[1] == entry["archive"]]
        if matches != [[entry["sha256"], entry["archive"]]]:
            raise pi_offline.OfflinePiError("Pi release SHA256SUMS disagrees with pin")
        candidate = stage / "archive.tar.xz"
        fetch(base + entry["archive"], candidate, entry["bytes"])
        if not verified(candidate, entry["sha256"], entry["bytes"]):
            raise pi_offline.OfflinePiError("Pi release archive hash or size mismatch")
        os.replace(candidate, archive)
        sync_directory(cache)
    return archive


def safe_members(archive: tarfile.TarFile) -> list[tarfile.TarInfo]:
    members = archive.getmembers()
    names: dict[str, tarfile.TarInfo] = {}
    for member in members:
        path = PurePosixPath(member.name)
        if (path.is_absolute() or ".." in path.parts or not path.parts
                or member.name.rstrip("/") != path.as_posix()
                or path.parts[0] != "node_modules" or member.name in names
                or not (member.isdir() or member.isfile() or member.issym())):
            raise pi_offline.OfflinePiError(f"unsafe Pi release archive member: {member.name}")
        member.mode &= 0o777
        names[member.name.rstrip("/")] = member
    for name, member in names.items():
        if any(str(parent) in names and not names[str(parent)].isdir()
               for parent in PurePosixPath(name).parents):
            raise pi_offline.OfflinePiError(f"Pi archive traverses a link: {name}")
        if member.issym():
            import posixpath
            destination = posixpath.normpath(posixpath.join(posixpath.dirname(name), member.linkname))
            resolved = names.get(destination)
            if member.linkname.startswith("/") or resolved is None or not resolved.isfile():
                raise pi_offline.OfflinePiError(f"unsafe or chained Pi archive link: {name}")
    return members


def inventory(root: Path) -> dict[str, dict[str, str | int]]:
    result: dict[str, dict[str, str | int]] = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if relative == RECEIPT:
            continue
        if path.is_symlink():
            result[relative] = {"link": os.readlink(path)}
        elif path.is_file():
            result[relative] = {"sha256": pi_offline.digest(path), "mode": path.stat().st_mode & 0o777}
    return result


@contextmanager
def writer(prefix: Path):
    prefix.parent.mkdir(parents=True, exist_ok=True)
    with (prefix.parent / (prefix.name + ".install.lock")).open("a+b") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield


def generation(path: Path, pin: Pin, target: str) -> bool:
    try:
        if path.is_symlink() or not path.is_dir():
            return False
        receipt = json.loads((path / RECEIPT).read_text())
        return bool(receipt["pin"] == pin and receipt["target"] == target and receipt["files"] == inventory(path))
    except (OSError, ValueError, KeyError):
        return False


def select(prefix: Path, entry: Artifact) -> None:
    link = prefix / (".current-" + uuid4().hex)
    try:
        link.symlink_to("releases/" + entry["sha256"])
        os.replace(link, prefix / "current")
        sync_directory(prefix)
        sync_directory(prefix.parent)
    finally:
        link.unlink(missing_ok=True)


def current(prefix: Path, pin: Pin, target: str) -> Path | None:
    entry = pin_entry(pin, target)
    path = prefix / "releases" / entry["sha256"]
    try:
        if (prefix.is_symlink() or not (prefix / "current").is_symlink()
                or os.readlink(prefix / "current") != "releases/" + entry["sha256"]
                or path.is_symlink()):
            return None
        if generation(path, pin, target):
            return path
    except (OSError, ValueError, KeyError):
        pass
    return None


def install(prefix: Path, pin: Pin, target: str, cache: Path) -> Path:
    entry = pin_entry(pin, target)
    with writer(prefix):
        if (prefix / "releases").is_symlink() or (prefix / ".usr-pi-releases").is_symlink():
            raise pi_offline.OfflinePiError("refusing foreign symlink in Pi release prefix")
        installed = current(prefix, pin, target)
        if installed:
            return installed
        if prefix.is_symlink() or (prefix.exists() and not (prefix / ".usr-pi-releases").is_file()):
            raise pi_offline.OfflinePiError(f"refusing foreign Pi release prefix: {prefix}")
        pointer = prefix / "current"
        if pointer.exists() and not pointer.is_symlink():
            raise pi_offline.OfflinePiError("refusing foreign Pi selection")
        destination = prefix / "releases" / entry["sha256"]
        if generation(destination, pin, target):
            select(prefix, entry)
            return destination
        archive = acquire(pin, target, cache)
        prefix.mkdir(exist_ok=True)
        (prefix / ".usr-pi-releases").touch()
        releases = prefix / "releases"
        releases.mkdir(exist_ok=True)
        if releases.is_symlink():
            raise pi_offline.OfflinePiError("refusing symlinked Pi releases directory")
        destination = releases / entry["sha256"]
        with tempfile.TemporaryDirectory(prefix=".stage-", dir=releases) as temporary:
            stage = Path(temporary) / "runtime"
            stage.mkdir()
            with tarfile.open(archive, "r:xz") as stream:
                members = safe_members(stream)
                if hasattr(tarfile, "data_filter"):
                    stream.extractall(stage, members, filter="data")
                else:
                    stream.extractall(stage, members)
            if not pi_offline.version_matches(stage, pin["profile"]):
                raise pi_offline.OfflinePiError("Pi release missing required runtime packages")
            (stage / "bin").mkdir()
            launcher = stage / "bin/pi"
            launcher.write_text(pi_offline.wrapper(destination, pin["profile"]))
            launcher.chmod(0o755)
            (stage / RECEIPT).write_text(json.dumps({"pin": pin, "target": target, "files": inventory(stage)}, sort_keys=True))
            if destination.exists() or destination.is_symlink():
                raise pi_offline.OfflinePiError("existing Pi release is modified; preserve and inspect before retry")
            sync_tree(stage)
            os.replace(stage, destination)
            sync_directory(releases)
        select(prefix, entry)
        return destination


def selected(prefix: Path, pin: Pin, target: str) -> bool:
    """Cheap check that the selection names the pinned generation and its receipt."""
    entry = pin_entry(pin, target)
    try:
        if prefix.is_symlink() or os.readlink(prefix / "current") != "releases/" + entry["sha256"]:
            return False
        generation_dir = prefix / "releases" / entry["sha256"]
        receipt = json.loads((generation_dir / RECEIPT).read_text())
        return not generation_dir.is_symlink() and receipt["pin"] == pin and receipt["target"] == target
    except (OSError, ValueError, KeyError, TypeError):
        return False


def bridge_target(prefix: Path) -> str:
    return str(prefix / "current/node_modules")


def _installed_pin(prefix: Path) -> Pin | None:
    """Read the pin from the selected receipt, independently of the installer override."""
    try:
        if prefix.is_symlink() or (prefix / "releases").is_symlink():
            return None
        pointer = os.readlink(prefix / "current")
        if not re.fullmatch(r"releases/[0-9a-f]{64}", pointer):
            return None
        root = prefix / pointer
        receipt = root / RECEIPT
        if root.is_symlink() or receipt.is_symlink():
            return None
        data: object = json.loads(receipt.read_text())
        if not isinstance(data, dict):
            return None
        pin = data.get("pin")
        if not _is_pin(pin):
            return None
        target = pi_offline.platform_key()
        entry = pin_entry(pin, target)
        return pin if data.get("target") == target and pointer == "releases/" + entry["sha256"] else None
    except (OSError, ValueError, KeyError, TypeError):
        return None


def bridge_current(project: Path, prefix: Path, pin: Pin | None = None) -> bool:
    link = project / "node_modules"
    try:
        valid = selected(prefix, pin, pi_offline.platform_key()) if pin is not None else _installed_pin(prefix) is not None
        return (valid
                and link.is_symlink() and os.readlink(link) == bridge_target(prefix))
    except OSError:
        return False


def _package_version(root: Path, name: str) -> str | None:
    file = root / name / "package.json"
    return json.loads(file.read_text())["version"] if file.exists() else None


def _replaceable_bridge(link: Path, legacy: Path) -> bool:
    if link.is_symlink():
        return os.readlink(link) == str(legacy / "node_modules") and pi_offline.is_legacy_runtime(legacy)
    if not link.exists():
        return True
    try:
        required = ("@earendil-works/pi-coding-agent", "pi-subagents")
        return (not (link / ".pnpm").exists()
                and all(_package_version(link, name) == pi_offline.PACKAGES[name] for name in required)
                and _package_version(link, "pi-muse-subscription") in (None, pi_offline.PACKAGES["pi-muse-subscription"]))
    except (OSError, KeyError, ValueError, TypeError):
        return False


def link_bridge(project: Path, prefix: Path, legacy: Path, pin: Pin | None = None) -> bool:
    """Point the bridge at the selected closure; adopt only usr's own earlier layouts."""
    valid = selected(prefix, pin, pi_offline.platform_key()) if pin is not None else _installed_pin(prefix) is not None
    if not valid:
        raise pi_offline.OfflinePiError("Pi runtime is not installed; run sh sync tools pi")
    link = project / "node_modules"
    if link.is_symlink() and os.readlink(link) == bridge_target(prefix):
        return False
    if not _replaceable_bridge(link, legacy):
        kind = "symlink" if link.is_symlink() else "dependencies"
        raise pi_offline.OfflinePiError(f"refusing unmanaged bridge {kind}: {link}")
    project.mkdir(parents=True, exist_ok=True)
    temporary = project / (".node_modules.release-" + uuid4().hex)
    temporary.symlink_to(bridge_target(prefix), target_is_directory=True)
    backup = None
    try:
        if link.exists() and not link.is_symlink():
            backup = project / (".node_modules.previous-" + uuid4().hex)
            os.replace(link, backup)
        try:
            os.replace(temporary, link)
        except OSError:
            if backup is not None:
                os.replace(backup, link)
                backup = None
            raise
        if backup is not None:
            shutil.rmtree(backup)
        return True
    finally:
        temporary.unlink(missing_ok=True)

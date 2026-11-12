"""Install usr's prebuilt Pi dependency closure; no npm, fetches, or pi package reconciliation.

The only network/npm activity is in the explicitly invoked pi-update/build-runtime.sh.
Normal sync installs a pinned tarball already committed inside usr.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import platform
import posixpath
import re
import shutil
import shlex
import stat
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[2]
ARCHIVES = ROOT / "vendor/pi/runtime"
STAMP = ".usr-pi-runtime.json"
PACKAGES = {
    "@earendil-works/pi-coding-agent": "1.5.0",
    "pi-subagents": "0.87.0",
    "pi-muse-subscription": "0.1.0",
    "@dataforxyz/agent-intercom-pi": "0.10.0",
    "@dataforxyz/agent-intercom-core": "0.1.0",
}
HEX = re.compile(r"[0-9a-f]{64}")


class OfflinePiError(ValueError):
    pass


def platform_key() -> str:
    system = platform.system().lower()
    machine = platform.machine().lower()
    arch = {"x86_64": "x64", "amd64": "x64", "aarch64": "arm64",
            "arm64": "arm64"}.get(machine)
    if system not in ("linux", "darwin") or arch is None:
        raise OfflinePiError(f"no prebuilt Pi runtime for {system}/{machine}")
    return f"{system}-{arch}"


def manifest() -> tuple[dict, Path]:
    file = ARCHIVES / "artifacts.json"
    try:
        data = json.loads(file.read_text())
        entry = data["artifacts"][platform_key()]
        sha = entry["sha256"]
        name = entry["path"]
        if data["schema"] != 1 or data["pi_version"] != "1.5.0" or not HEX.fullmatch(sha):
            raise ValueError("invalid artifact manifest")
        if name != platform_key() + ".tar.gz" or not isinstance(entry["bytes"], int):
            raise ValueError("invalid archive path or size")
    except (OSError, KeyError, TypeError, ValueError) as exc:
        raise OfflinePiError(f"Pi offline runtime artifact unavailable: {exc}") from exc
    return entry, ARCHIVES / name


def digest(file: Path) -> str:
    h = hashlib.sha256()
    with file.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def verify_archive() -> tuple[dict, Path]:
    entry, file = manifest()
    if not file.is_file() or file.is_symlink() or file.stat().st_size != entry["bytes"]:
        raise OfflinePiError(f"missing or malformed Pi archive: {file}")
    if digest(file) != entry["sha256"]:
        raise OfflinePiError(f"Pi archive digest mismatch: {file}")
    return entry, file


def runtime_dir(home: Path, environ: dict[str, str] | None = None) -> Path:
    env = os.environ if environ is None else environ
    base = Path(env.get("XDG_DATA_HOME") or home / ".local/share")
    if not base.is_absolute():
        raise OfflinePiError("XDG_DATA_HOME must be absolute")
    return base / "pi"


def version_matches(root: Path) -> bool:
    try:
        for name, version in PACKAGES.items():
            actual = json.loads((root / "node_modules" / name / "package.json").read_text())["version"]
            if actual != version:
                return False
        return (root / "node_modules/@earendil-works/pi-coding-agent/dist/bundle/cli.js").is_file()
    except (OSError, KeyError, ValueError, TypeError):
        return False


def current(root: Path) -> bool:
    try:
        entry, _ = manifest()
        record = json.loads((root / STAMP).read_text())
        return (not root.is_symlink() and root.is_dir()
                and record == {"schema": 1, "sha256": entry["sha256"],
                               "platform": platform_key(), "pi_version": "1.5.0"}
                and version_matches(root)
                and not (root / "bin/pi").is_symlink()
                and os.access(root / "bin/pi", os.X_OK)
                and (root / "bin/pi").read_text() == wrapper(root))
    except (OSError, KeyError, ValueError, TypeError):
        return False


def validate_members(members: list[tarfile.TarInfo]) -> None:
    for m in members:
        name = m.name
        parts = name.split("/")
        if (name.startswith("/") or not parts or parts[0] != "node_modules"
                or any(part in ("..", "") for part in parts if part)
                or not (m.isfile() or m.isdir() or m.issym() or m.islnk())):
            raise OfflinePiError(f"unsafe Pi archive member: {name}")
        if m.issym() or m.islnk():
            destination = (posixpath.join(posixpath.dirname(name), m.linkname)
                           if m.issym() else m.linkname)
            normalized = posixpath.normpath(destination)
            if not normalized.startswith("node_modules/") or m.linkname.startswith("/"):
                raise OfflinePiError(f"Pi archive link escapes node_modules: {name}")


def wrapper(root: Path) -> str:
    sdk = root / "node_modules/@earendil-works/pi-coding-agent/dist/bundle/cli.js"
    subagent = root / "node_modules/pi-subagents/index.ts"
    intercom = root / "node_modules/@dataforxyz/agent-intercom-pi/index.ts"
    return ("#!/bin/sh\n"
            "# Bundled in usr; never install or update npm dependencies at runtime.\n"
            "set -eu\n"
            # PI_OFFLINE blocks any project-configured npm/git package auto-installs,
            # and prevents Pi's automatic model catalog/version update requests.
            "export PI_OFFLINE=1 PI_SKIP_VERSION_CHECK=1\n"
            f"exec node {shlex.quote(str(sdk))} "
            f"--extension {shlex.quote(str(subagent))} "
            f"--extension {shlex.quote(str(intercom))} \"$@\"\n")


def install(root: Path) -> bool:
    """Atomic offline install; refuse unmanaged prefixes. The caller owns the prefix."""
    if current(root):
        return False
    entry, file = verify_archive()
    if root.is_symlink() or (root.exists() and not root.is_dir()):
        raise OfflinePiError(f"refusing foreign Pi prefix: {root}")
    root.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".pi-offline-", dir=root.parent))
    backup = None
    try:
        with tarfile.open(file, "r:gz") as archive:
            members = archive.getmembers()
            validate_members(members)
            # tarfile's strict filter was introduced after the oldest Python
            # accepted by sync. validate_members() checks every path/type/link
            # first; retain compatibility with the supported Python 3.9+ bootstrap.
            if hasattr(tarfile, "data_filter"):
                archive.extractall(stage, filter="data")
            else:
                archive.extractall(stage)
        if not version_matches(stage):
            raise OfflinePiError("Pi archive missing pinned CLI, SDK or extensions")
        (stage / "bin").mkdir()
        cli = stage / "bin/pi"
        cli.write_text(wrapper(root))
        cli.chmod(0o755)
        (stage / STAMP).write_text(json.dumps({
            "schema": 1, "sha256": entry["sha256"],
            "platform": platform_key(), "pi_version": "1.5.0"
        }, sort_keys=True) + "\n")
        if root.exists():
            backup = Path(tempfile.mkdtemp(prefix=".pi-previous-", dir=root.parent))
            backup.rmdir()
            os.replace(root, backup)
        try:
            os.replace(stage, root)
        except OSError:
            if backup is not None:
                os.replace(backup, root)
                backup = None
            raise
        if backup is not None:
            shutil.rmtree(backup)
        return True
    finally:
        if stage.exists():
            shutil.rmtree(stage)
        if backup is not None and backup.exists():
            # Never silently discard a failed rollback's original prefix.
            raise OfflinePiError(f"old Pi prefix preserved at {backup}")


def bridge_current(project: Path, root: Path) -> bool:
    link = project / "node_modules"
    try:
        return current(root) and link.is_symlink() and link.resolve(strict=True) == (root / "node_modules").resolve(strict=True)
    except OSError:
        return False


def link_bridge(project: Path, root: Path) -> bool:
    if not current(root):
        raise OfflinePiError("Pi runtime is not installed; run sh sync tools pi")
    if bridge_current(project, root):
        return False
    link = project / "node_modules"
    if link.is_symlink():
        raise OfflinePiError(f"refusing foreign bridge dependency symlink: {link}")
    if link.exists():
        # Previous Claude/OpenCode bridge installs had two packages; Pi also
        # installed Muse. Adopt only the exact known closure, never pnpm/foreign dirs.
        try:
            legacy = not (link / ".pnpm").exists() and all(
                json.loads((link / name / "package.json").read_text())["version"] == PACKAGES[name]
                for name in ("@earendil-works/pi-coding-agent", "pi-subagents"))
            muse = link / "pi-muse-subscription/package.json"
            if muse.exists():
                legacy = legacy and json.loads(muse.read_text())["version"] == PACKAGES["pi-muse-subscription"]
        except (OSError, KeyError, ValueError, TypeError):
            legacy = False
        if not legacy:
            raise OfflinePiError(f"refusing unmanaged bridge dependencies: {link}")
    project.mkdir(parents=True, exist_ok=True)
    tmp = project / (".node_modules.offline-" + next(tempfile._get_candidate_names()))
    tmp.symlink_to(root / "node_modules", target_is_directory=True)
    backup = None
    try:
        if link.exists():
            backup = project / (".node_modules.previous-" + next(tempfile._get_candidate_names()))
            os.replace(link, backup)
        try:
            os.replace(tmp, link)
        except OSError:
            if backup is not None:
                os.replace(backup, link)
                backup = None
            raise
        if backup is not None:
            shutil.rmtree(backup)
        return True
    finally:
        tmp.unlink(missing_ok=True)


def configure_intercom(home: Path, root: Path) -> bool:
    """Choose a local TS loader, never npx; preserve explicitly configured user behavior."""
    directory = home / ".pi/agent/intercom"
    file = directory / "config.json"
    if directory.is_symlink() or file.is_symlink():
        raise OfflinePiError(f"refusing symlinked intercom configuration: {file}")
    loader = root / "node_modules/tsx/dist/loader.mjs"
    if not loader.is_file():
        raise OfflinePiError(f"missing self-contained TS loader: {loader}")
    if file.exists():
        try:
            data = json.loads(file.read_text())
        except (OSError, ValueError) as exc:
            raise OfflinePiError(f"invalid intercom config: {file}") from exc
        if not isinstance(data, dict):
            raise OfflinePiError("intercom config must be an object")
    else:
        data = {}
    desired = dict(data)
    # Any existing explicit non-npm broker remains under the user's control.
    if not desired.get("brokerCommand") or desired.get("brokerCommand") in ("npx", "npm"):
        desired["brokerCommand"] = "node"
        desired["brokerArgs"] = ["--import", str(loader)]
    elif desired.get("brokerCommand") == "node" and desired.get("brokerArgs", []) == ["--no-install", "tsx"]:
        desired["brokerArgs"] = ["--import", str(loader)]
    desired.setdefault("inboundTrigger", "never")
    desired.setdefault("confirmSend", True)
    if desired == data:
        return False
    directory.mkdir(parents=True, exist_ok=True)
    old = file.read_bytes() if file.exists() else None
    fd, temp = tempfile.mkstemp(prefix=".config.", dir=directory)
    try:
        os.fchmod(fd, stat.S_IMODE(file.stat().st_mode) if file.exists() else 0o600)
        with os.fdopen(fd, "w", encoding="utf8") as out:
            json.dump(desired, out, indent=2)
            out.write("\n")
            out.flush()
            os.fsync(out.fileno())
        if old is not None and file.read_bytes() != old:
            raise OfflinePiError("concurrent intercom config change; retry sync")
        os.replace(temp, file)
    finally:
        if os.path.lexists(temp):
            os.unlink(temp)
    return True

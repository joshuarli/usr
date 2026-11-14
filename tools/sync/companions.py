#!/usr/bin/env python3
"""Install and register usr's pinned intercom companions; never touch harness credentials.

The Claude, Codex and OpenCode intercom adapters ship as separate archives in
the pinned pi-build release alongside the Pi runtime. This tool installs them
into ~/.local/share/agent-intercom, creates the PATH shims their command-line
tools need, and registers the MCP server with Claude Code and the plugins with
OpenCode, all with owned-entry semantics: entries that do not point into our
install prefix are never adopted, overwritten or removed. OpenCode merges
plugin arrays from opencode.json and opencode.jsonc, so OpenCode registration
goes in a sync-managed opencode.jsonc and the tracked, symlinked opencode.json
is never read or written through. Codex registers through the tracked
~/.codex/config.toml entry, which needs no machine state.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import sys
import tarfile
import tempfile
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pi_offline  # noqa: E402
import pi_release  # noqa: E402

COMPANIONS = pi_release.COMPANIONS
CLAUDE_MCP_NAME = "claude-intercom"
RECEIPT = ".usr-companion.json"
OPENCODE_SCHEMA = "https://opencode.ai/config.json"


def die(message):
    raise ValueError(message)


def _base(env: dict[str, str], variable: str, default: Path) -> Path:
    base = Path(env.get(variable) or default)
    if not base.is_absolute():
        die(f"{variable} must be absolute")
    return base


def home_of(env: dict[str, str]) -> Path:
    home = Path(env["HOME"])
    if not home.is_absolute():
        die("HOME must be absolute")
    return home


def prefix(env: dict[str, str]) -> Path:
    return _base(env, "XDG_DATA_HOME", home_of(env) / ".local/share") / "agent-intercom"


def bin_dir(env: dict[str, str]) -> Path:
    return home_of(env) / ".local/bin"


def claude_config(env: dict[str, str]) -> Path:
    return home_of(env) / ".claude.json"


def opencode_config(env: dict[str, str]) -> Path:
    base = _base(env, "XDG_CONFIG_HOME", home_of(env) / ".config") / "opencode"
    return base / "opencode.jsonc"


def managed_binary(name: str, env: dict[str, str]) -> str | None:
    path = home_of(env) / ".local/share/nodejs/current/bin" / name
    if path.is_file() and os.access(path, os.X_OK):
        return str(path)
    return shutil.which(name)


def managed_file(name: str, env: dict[str, str]) -> str:
    node = managed_binary(name, env)
    if not node:
        die(f"{name} is missing; install the managed Node.js first")
    return node


def payload_for(pin: dict, name: str, files: dict[str, dict[str, str | int]]) -> dict:
    entry = pin["companions"][name]
    return {
        "pin": {"builder_revision": pin["builder_revision"], "version": pin["version"],
                "source_sha": entry["source_sha"]},
        "companion": name,
        "archive": entry["archive"],
        "sha256": entry["sha256"],
        "files": files,
    }


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


def install_status(destination: Path, pin: dict, name: str) -> str:
    if destination.is_symlink() or not destination.is_dir():
        return "foreign" if destination.exists() or destination.is_symlink() else "absent"
    try:
        current = json.loads((destination / RECEIPT).read_text())
    except (OSError, ValueError):
        return "foreign"
    wanted = payload_for(pin, name, current.get("files", {}))
    if (current.get("pin") != wanted["pin"] or current.get("archive") != wanted["archive"]
            or current.get("sha256") != wanted["sha256"]):
        return "stale"
    return "current" if current.get("files") == inventory(destination) else "modified"


def safe_members(archive: tarfile.TarFile) -> list[tarfile.TarInfo]:
    members = archive.getmembers()
    names: dict[str, tarfile.TarInfo] = {}
    for member in members:
        path = PurePosixPath(member.name)
        if (path.is_absolute() or ".." in path.parts or not path.parts
                or member.name.rstrip("/") != path.as_posix()
                or (path.parts[0] != "package" and len(path.parts) > 1)
                or member.name in names
                or not (member.isdir() or member.isfile())):
            raise pi_offline.OfflinePiError(f"unsafe companion archive member: {member.name}")
        member.mode &= 0o777
        names[member.name.rstrip("/")] = member
    for member in names.values():
        parent = str(PurePosixPath(member.name).parent)
        while parent and parent != ".":
            ancestor = names.get(parent)
            if ancestor is not None and not ancestor.isdir():
                raise pi_offline.OfflinePiError(f"companion archive entry under non-directory: {member.name}")
            parent = str(PurePosixPath(parent).parent)
    return members


def _download_verified(pin: dict, cache: Path, name: str) -> Path:
    entry = pin["companions"][name]
    target = cache / (entry["sha256"] + ".tgz")
    if not pi_release.verified(target, entry["sha256"], entry["bytes"]):
        with tempfile.TemporaryDirectory(prefix=".download-", dir=cache) as temp:
            stage = Path(temp) / "companion.tgz"
            pi_release.fetch(pin["release_url"].rstrip("/") + "/" + entry["archive"], stage, entry["bytes"])
            if not pi_release.verified(stage, entry["sha256"], entry["bytes"]):
                die(f"companion archive hash or size mismatch: {name}")
            os.replace(stage, target)
            pi_release.sync_directory(cache)
    return target


def acquire(pin: dict, cache: Path) -> dict[str, Path]:
    if cache.is_symlink():
        die("refusing symlinked companion cache")
    cache.mkdir(parents=True, exist_ok=True)
    entries = pi_release.companions(pin)
    base = pin["release_url"].rstrip("/") + "/"
    cache_key = hashlib.sha256(pin["provenance_sha256"].encode()).hexdigest()
    provenance = cache / f"companions-{cache_key}.json"
    if not (provenance.is_file() and not provenance.is_symlink()
            and pi_offline.digest(provenance) == pin["provenance_sha256"]):
        candidate = provenance.with_name(provenance.name + ".candidate")
        candidate.unlink(missing_ok=True)
        pi_release.fetch(base + "provenance.json", candidate, 8 << 20)
        if pi_offline.digest(candidate) != pin["provenance_sha256"]:
            candidate.unlink(missing_ok=True)
            die("companion provenance digest mismatch")
        os.replace(candidate, provenance)
    data = json.loads(provenance.read_text())
    companions = data.get("companions")
    if not isinstance(companions, dict) or set(companions) != set(COMPANIONS):
        die("release provenance does not describe the pinned companions")
    for name, entry in entries.items():
        record = companions[name]
        wanted = {"archive": entry["archive"], "bytes": entry["bytes"], "sha256": entry["sha256"],
                  "source_sha": entry["source_sha"], "version": entry["version"]}
        if record != wanted:
            die(f"release provenance disagrees with pinned companion {name}")
    want_lines = sorted(f"{entries[name]['sha256']}  {entries[name]['archive']}" for name in COMPANIONS)
    sums = cache / f"companions-{cache_key}.SHA256SUMS"
    cached_ok = False
    if sums.is_file() and not sums.is_symlink():
        lines = [line for line in sums.read_text().splitlines() if line.strip()]
        cached_ok = all(line in lines for line in want_lines)
    if not cached_ok:
        candidate = sums.with_name(sums.name + ".candidate")
        candidate.unlink(missing_ok=True)
        pi_release.fetch(base + "SHA256SUMS", candidate, 1 << 20)
        lines = [line for line in candidate.read_text().splitlines() if line.strip()]
        if not all(line in lines for line in want_lines):
            candidate.unlink(missing_ok=True)
            die("release SHA256SUMS disagrees with the pinned companions")
        os.replace(candidate, sums)
    return {name: _download_verified(pin, cache, name) for name in COMPANIONS}


def _swap_in_place(root: Path, stage: Path) -> None:
    backup = root.parent / (f".{root.name}.old-" + uuid4().hex)
    if root.exists() or root.is_symlink():
        os.replace(root, backup)
    try:
        os.replace(stage, root)
    except BaseException:
        if backup.exists():
            os.replace(backup, root)
        raise
    if backup.exists():
        shutil.rmtree(backup)


def _extract(archive: Path, stage: Path) -> dict:
    with tarfile.open(archive, "r:gz") as stream:
        members = safe_members(stream)
        for member in members:
            parts = PurePosixPath(member.name).parts[1:]
            if not parts:
                continue
            target = stage / Path(*parts)
            if member.isdir():
                target.mkdir(exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with stream.extractfile(member) as handle:
                target.write_bytes(handle.read() if handle is not None else b"")
            target.chmod(0o755 if member.mode & 0o111 else 0o644)
    manifest_path = stage / "package.json"
    if not manifest_path.is_file():
        die("companion archive is missing package.json")
    return json.loads(manifest_path.read_text())


def install_companion(pin: dict, cache: Path, destination: Path, name: str) -> bool:
    entry = pin["companions"][name]
    destination.parent.mkdir(parents=True, exist_ok=True)
    status = install_status(destination, pin, name)
    if status == "current":
        return False
    if status == "modified":
        die(f"companion {name} installation is modified; preserve it and inspect before retrying")
    if status == "foreign":
        die(f"refusing foreign companion install root: {destination}")
    archive = acquire(pin, cache)[name]
    with tempfile.TemporaryDirectory(prefix=f".{name}-", dir=destination.parent) as temporary:
        stage = Path(temporary) / name
        stage.mkdir()
        try:
            manifest = _extract(archive, stage)
        except tarfile.TarError as exc:
            die(f"companion archive is not a valid tar.gz: {name}: {exc}")
        if manifest.get("name") != f"@dataforxyz/{name}" or manifest.get("version") != entry["version"]:
            die(f"companion archive identity mismatch: {name}")
        bins = manifest.get("bin") or {}
        if isinstance(bins, str):
            bins = {manifest["name"].split("/")[-1]: bins}
        for relative in bins.values():
            bin_path = stage / relative
            if not bin_path.is_file():
                die(f"companion archive is missing its bin entry {relative}: {name}")
            bin_path.chmod(0o755)
        payload = payload_for(pin, name, inventory(stage))
        (stage / RECEIPT).write_text(json.dumps(payload, sort_keys=True) + "\n")
        destination.parent.mkdir(parents=True, exist_ok=True)
        _swap_in_place(destination, stage)
        pi_release.sync_tree(destination)
        pi_release.sync_directory(destination.parent)
    return True


def shim_body(target: Path) -> str:
    return f'#!/bin/sh\nset -eu\nexec node "{target}" "$@"\n'


def bins_of(destination: Path) -> dict[str, str]:
    try:
        manifest = json.loads((destination / "package.json").read_text())
    except (OSError, ValueError):
        return {}
    bins = manifest.get("bin") or {}
    if isinstance(bins, str):
        bins = {manifest["name"].split("/")[-1]: bins}
    return bins if isinstance(bins, dict) else {}


def install_shims(destination: Path, name: str, env: dict[str, str]) -> None:
    directory = bin_dir(env)
    for bin_name, relative in sorted(bins_of(destination).items()):
        launcher = directory / bin_name
        target = destination / relative
        body = shim_body(target)
        if launcher.is_symlink():
            if os.readlink(launcher) == str(target):
                continue
            die(f"{launcher} already exists and is not ours; leaving it unchanged")
        if launcher.exists():
            try:
                existing = launcher.read_text(encoding="utf8", errors="ignore")
            except OSError:
                existing = None
            if existing != body:
                die(f"{launcher} already exists and is not ours; leaving it unchanged")
            continue
        directory.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=f".{bin_name}.", dir=directory)
        try:
            with os.fdopen(fd, "w", encoding="utf8") as out:
                out.write(body)
            os.chmod(temporary, 0o755)
            os.replace(temporary, launcher)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)


def remove_shims(destination: Path, env: dict[str, str]) -> None:
    for bin_name, relative in bins_of(destination).items():
        launcher = bin_dir(env) / bin_name
        target = destination / relative
        body = shim_body(target)
        if launcher.is_symlink() and os.readlink(launcher) == str(target):
            launcher.unlink()
        elif launcher.exists() and not launcher.is_symlink():
            try:
                if launcher.read_text(encoding="utf8", errors="ignore") == body:
                    launcher.unlink()
            except OSError:
                pass


def _read_json(file: Path):
    if file.is_symlink():
        die(f"refusing symlinked configuration: {file}")
    if not file.exists():
        return {}, None
    original = file.read_bytes()
    try:
        value = json.loads(original)
    except (UnicodeError, ValueError) as exc:
        die(f"cannot parse {file}: {exc}")
    if not isinstance(value, dict):
        die(f"{file} must contain an object")
    return value, original


def _write_json(file: Path, data: dict, original: bytes | None) -> None:
    file.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode()
    if original == payload:
        return
    if original is not None and file.read_bytes() != original:
        die(f"{file} changed concurrently; retry sync")
    mode = stat.S_IMODE(file.stat().st_mode) if original is not None and file.exists() else 0o600
    fd, temporary = tempfile.mkstemp(prefix=".intercom.json.", dir=file.parent)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "wb") as output:
            output.write(payload)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, file)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def claude_entry(destination: Path, env: dict[str, str]) -> dict:
    return {"command": managed_file("node", env), "args": [str(destination / "dist" / "claude-server.mjs")]}


def claude_ours(entry: object, destination: Path) -> bool:
    if not isinstance(entry, dict):
        return False
    if not set(entry).issubset({"command", "args"}):
        return False
    command = entry.get("command")
    args = entry.get("args")
    return (isinstance(command, str) and Path(command).name == "node"
            and isinstance(args, list) and len(args) == 1 and isinstance(args[0], str)
            and args[0] == str(destination / "dist" / "claude-server.mjs"))


def sync_claude(destination: Path, action: str, env: dict[str, str]) -> str:
    file = claude_config(env)
    data, original = _read_json(file)
    servers = data.get("mcpServers", {})
    if not isinstance(servers, dict):
        die(f"{file} mcpServers must be an object")
    current = servers.get(CLAUDE_MCP_NAME)
    ours = claude_ours(current, destination)
    if current is not None and not ours:
        if action == "remove":
            return "kept-foreign"
        if action in ("check", "verify-absent"):
            die(f"{file} registers a foreign {CLAUDE_MCP_NAME} MCP server; leaving it unchanged")
        die(f"{file} already names a different {CLAUDE_MCP_NAME} MCP server; leaving it unchanged")
    if action == "check":
        if current != claude_entry(destination, env):
            die(f"{CLAUDE_MCP_NAME} MCP registration is missing or outdated")
        return "current"
    if action in ("remove", "verify-absent"):
        if ours and action == "remove":
            del servers[CLAUDE_MCP_NAME]
            if not servers:
                data.pop("mcpServers", None)
            _write_json(file, data, original)
            return "removed"
        if action == "verify-absent" and ours:
            die(f"{file} still registers {CLAUDE_MCP_NAME}")
        return "absent"
    desired = claude_entry(destination, env)
    if current == desired:
        return "current"
    servers = data.setdefault("mcpServers", {})
    servers[CLAUDE_MCP_NAME] = desired
    _write_json(file, data, original)
    return "registered"


def opencode_entries(env: dict[str, str]) -> str:
    return str(prefix(env) / "agent-intercom-opencode" / "dist" / "plugin.mjs")


def opencode_ours(item: str, env: dict[str, str]) -> bool:
    root = str(prefix(env) / "agent-intercom-opencode") + "/dist/"
    return item.startswith(root) and item.endswith("plugin.mjs")


def sync_opencode(action: str, env: dict[str, str]) -> str:
    target = opencode_config(env)
    entry = opencode_entries(env)
    data, original = _read_json(target)
    if original is None and action == "install":
        data = {"$schema": OPENCODE_SCHEMA}
        values = []
    else:
        values = data.get("plugins", [])
    if not isinstance(values, list) or not all(isinstance(item, str) for item in values):
        die(f"{target} plugins must be a list of paths")
    if action == "check":
        if entry not in values:
            die(f"{target} plugin registration is missing or outdated")
        return "current"
    if action in ("remove", "verify-absent"):
        residue = [item for item in values if opencode_ours(item, env)]
        if action == "verify-absent":
            if residue:
                die(f"{target} still registers the intercom companion plugin")
            return "current"
        kept = [item for item in values if not opencode_ours(item, env)]
        if len(kept) == len(values):
            return "absent"
        if kept:
            data["plugins"] = kept
        else:
            data.pop("plugins", None)
        if data == {"$schema": OPENCODE_SCHEMA}:
            if original is not None and target.read_bytes() != original:
                die(f"{target} changed concurrently; retry sync")
            target.unlink()
        else:
            _write_json(target, data, original)
        return "removed"
    if entry not in values:
        data["plugins"] = values + [entry]
        _write_json(target, data, original)
        return "registered"
    return "current"


def load_pin_for_sync() -> dict:
    pin = pi_release.load_pin()
    pi_release.companions(pin)
    return pin


def command_install(env: dict) -> int:
    pin = load_pin_for_sync()
    root = prefix(env)
    root.mkdir(parents=True, exist_ok=True)
    cache = pi_offline.cache_dir(home_of(env), env)
    for name in COMPANIONS:
        install_companion(pin, cache, root / name, name)
    for name in COMPANIONS:
        install_shims(root / name, name, env)
    sync_claude(root / "agent-intercom-claude", "install", env)
    sync_opencode("install", env)
    return 0


def command_check(env: dict) -> int:
    pin = load_pin_for_sync()
    root = prefix(env)
    for name in COMPANIONS:
        destination = root / name
        status = install_status(destination, pin, name)
        if status != "current":
            die(f"companion {name} installation is {status}")
    sync_claude(root / "agent-intercom-claude", "check", env)
    sync_opencode("check", env)
    return 0


def command_plan(env: dict) -> int:
    pin = load_pin_for_sync()
    root = prefix(env)
    for name in COMPANIONS:
        status = install_status(root / name, pin, name)
        if status in ("absent", "stale"):
            print(f"companions: install {name} {pin['companions'][name]['version']}")
    print("companions: ensure shims, Claude MCP entry and OpenCode plugin registration")
    return 0


def command_remove(env: dict) -> int:
    root = prefix(env)
    result = sync_claude(root / "agent-intercom-claude", "remove", env)
    if result == "kept-foreign":
        print("companions: keeping foreign Claude intercom MCP entry")
    sync_opencode("remove", env)
    for name in COMPANIONS:
        destination = root / name
        if destination.is_symlink():
            die(f"refusing to remove symlinked companion root: {destination}")
        if not destination.exists():
            continue
        remove_shims(destination, env)
        shutil.rmtree(destination)
    return 0


def command_verify_absent(env: dict) -> int:
    root = prefix(env)
    sync_claude(root / "agent-intercom-claude", "verify-absent", env)
    sync_opencode("verify-absent", env)
    return 0


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: companions.py {plan|check|install|remove|verify-absent}", file=sys.stderr)
        return 2
    action = sys.argv[1]
    env = dict(os.environ)
    commands = {
        "plan": command_plan,
        "check": command_check,
        "install": command_install,
        "remove": command_remove,
        "verify-absent": command_verify_absent,
    }
    try:
        handler = commands[action]
    except KeyError:
        print("usage: companions.py {plan|check|install|remove|verify-absent}", file=sys.stderr)
        return 2
    try:
        return handler(env)
    except (OSError, ValueError, KeyError, tarfile.TarError, json.JSONDecodeError) as exc:
        print(f"sync: companions: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

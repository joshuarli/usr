#!/usr/bin/env python3
"""Manage usr's Claude MCP bridge as part of sync; never touch Claude credentials."""
import json
import hashlib
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile

NAME = "pi-subagent-bridge"
LEGACY_NAME = "usr-opencode-worker"
ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / "tools" / "pi-subagent-bridge"
SERVER = PROJECT / "src" / "server.ts"
HOME = Path(os.environ["HOME"])
CONFIG = HOME / ".claude.json"
OWNER = Path(os.environ.get("XDG_STATE_HOME", str(HOME / ".local/state"))) / "sync/claude-mcp-owner.json"


def die(message):
    raise ValueError(message)


def dependency_version():
    package = json.loads((PROJECT / "package.json").read_text())
    version = package["dependencies"]["@earendil-works/pi-coding-agent"]
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        die("Pi SDK must be pinned to an exact version")
    return version


def dependency_current():
    path = PROJECT / "node_modules" / "@earendil-works" / "pi-coding-agent" / "package.json"
    try:
        return json.loads(path.read_text())["version"] == dependency_version()
    except (OSError, KeyError, ValueError, TypeError):
        return False


def managed_binary(name):
    path = HOME / ".local" / "share" / "nodejs" / "current" / "bin" / name
    if path.is_file() and os.access(path, os.X_OK):
        return str(path)
    return shutil.which(name)


def expected_entry(node):
    return {
        "type": "stdio",
        "command": node,
        "args": ["--experimental-strip-types", str(SERVER)],
    }


def entry_fingerprint(entry):
    payload = json.dumps(entry, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def load_owner():
    if OWNER.is_symlink():
        die(f"refusing symlinked MCP ownership record: {OWNER}")
    if not OWNER.exists():
        return None
    value = json.loads(OWNER.read_text())
    if not isinstance(value, dict) or value.get("schema") != 1 or not re.fullmatch(
        r"[0-9a-f]{64}", str(value.get("fingerprint", ""))
    ):
        die(f"invalid MCP ownership record: {OWNER}")
    return value["fingerprint"]


def save_owner(entry):
    OWNER.parent.mkdir(parents=True, exist_ok=True)
    if OWNER.is_symlink():
        die(f"refusing symlinked MCP ownership record: {OWNER}")
    payload = (json.dumps({"schema": 1, "fingerprint": entry_fingerprint(entry)}, sort_keys=True) + "\n").encode()
    fd, temporary = tempfile.mkstemp(prefix=".claude-mcp-owner.", dir=OWNER.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as output:
            output.write(payload)
        os.replace(temporary, OWNER)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def owned_entry(entry):
    if not isinstance(entry, dict) or entry.get("type", "stdio") != "stdio":
        return False
    command = entry.get("command")
    if not isinstance(command, str) or Path(command).name != "node":
        return False
    args = entry.get("args")
    if not isinstance(args, list) or len(args) != 2 or args[0] != "--experimental-strip-types":
        return False
    server = args[1]
    if not isinstance(server, str) or not Path(server).is_absolute() or not (
        server.endswith("/tools/pi-subagent-bridge/src/server.ts")
        or server.endswith("/tools/opencode-worker/src/server.ts")
    ):
        return False
    if entry.get("env") or not set(entry).issubset({"type", "command", "args", "env"}):
        return False
    old_default = HOME / "usr/tools/pi-subagent-bridge/src/server.ts"
    legacy_default = HOME / "usr/tools/opencode-worker/src/server.ts"
    return (server == str(SERVER) or server == str(old_default) or server == str(legacy_default) or
            load_owner() == entry_fingerprint(entry))

def configuration():
    if CONFIG.is_symlink():
        die(f"refusing symlinked Claude configuration: {CONFIG}")
    if not CONFIG.exists():
        return {}, None
    original = CONFIG.read_bytes()
    try:
        value = json.loads(original)
    except (UnicodeError, ValueError) as exc:
        die(f"cannot parse {CONFIG}: {exc}")
    if not isinstance(value, dict):
        die("Claude configuration must be an object")
    servers = value.get("mcpServers", {})
    if not isinstance(servers, dict):
        die("Claude mcpServers must be an object")
    return value, original


def install_dependency():
    if dependency_current():
        return
    if (PROJECT / "node_modules").is_symlink():
        die("refusing to modify symlinked node_modules")
    node, npm = managed_binary("node"), managed_binary("npm")
    if not node or not npm:
        die("Node.js and npm are required; run sync to install them")
    try:
        version = subprocess.check_output([node, "--version"], text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        die("cannot execute Node.js")
    match = re.fullmatch(r"v(\d+)\.(\d+)\.(\d+)", version)
    if not match or int(match.group(1)) < 26:
        die(f"Node.js 26+ required for bridge; found {version}")
    env = os.environ.copy()
    env["PATH"] = str(Path(node).parent) + os.pathsep + env.get("PATH", "")
    subprocess.run(
        [npm, "install", "--prefix", str(PROJECT), "--ignore-scripts",
         "--no-package-lock", "--no-audit", "--no-fund"],
        env=env, check=True,
    )
    if not dependency_current():
        die(f"npm did not install pinned @earendil-works/pi-coding-agent {dependency_version()}")


def update_configuration(data, original):
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode()
    if original == payload:
        return
    if original is not None and CONFIG.read_bytes() != original:
        die("Claude configuration changed concurrently; retry sync")
    mode = stat.S_IMODE(CONFIG.stat().st_mode) if original is not None else 0o600
    fd, temporary = tempfile.mkstemp(prefix=".claude.json.", dir=CONFIG.parent)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "wb") as output:
            output.write(payload)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, CONFIG)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def run(action):
    data, original = configuration()
    servers = data.get("mcpServers", {})
    previous = servers.get(NAME)
    legacy = servers.get(LEGACY_NAME)
    node = managed_binary("node")
    desired = expected_entry(node or "node")
    if previous is not None and not owned_entry(previous):
        die(f"{NAME} already names a different MCP server; leaving it unchanged")
    if legacy is not None and not owned_entry(legacy):
        die(f"{LEGACY_NAME} is not an owned bridge; leaving it unchanged")

    if action == "plan":
        if legacy is not None:
            print(f"MCP: migrate owned {LEGACY_NAME} to {NAME}")
        if not dependency_current():
            print(f"NPM: install pinned @earendil-works/pi-coding-agent {dependency_version()}")
        if previous != desired or legacy is not None:
            print(f"MCP: register {NAME} with Claude user scope")
        elif load_owner() != entry_fingerprint(desired):
            print(f"MCP: record ownership of {NAME}")
        return

    if action == "check":
        if legacy is not None:
            die(f"legacy {LEGACY_NAME} registration is still active")
        if not dependency_current():
            die("Pi SDK worker dependency is not installed")
        if previous != desired or load_owner() != entry_fingerprint(desired):
            die(f"{NAME} MCP registration is missing, unowned, or outdated")
        print(f"ok: {NAME} MCP and dependency current")
        return

    if action == "remove":
        if legacy is not None:
            del servers[LEGACY_NAME]
        if previous is not None:
            del servers[NAME]
        if previous is not None or legacy is not None:
            update_configuration(data, original)
            print(f"sync: unregistered {NAME}")
        OWNER.unlink(missing_ok=True)
        return

    if action != "install":
        die("usage: claude-worker.py {plan|check|install|remove}")
    install_dependency()
    node = managed_binary("node")
    if not node:
        die("Node.js is missing")
    desired = expected_entry(node)
    if previous != desired:
        servers = data.setdefault("mcpServers", {})
        servers.pop(LEGACY_NAME, None)
        servers[NAME] = desired
        update_configuration(data, original)
        print(f"sync: registered {NAME} for Claude Code")
    save_owner(desired)


if __name__ == "__main__":
    try:
        if len(sys.argv) != 2:
            die("usage: claude-worker.py {plan|check|install|remove}")
        run(sys.argv[1])
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"sync: Claude worker bridge: {exc}", file=sys.stderr)
        sys.exit(1)

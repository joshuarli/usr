#!/usr/bin/env python3
"""Manage usr's Claude MCP bridge as part of sync; never touch Claude credentials."""
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile

NAME = "usr-opencode-worker"
ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / "tools" / "opencode-worker"
SERVER = PROJECT / "src" / "server.ts"
HOME = Path(os.environ["HOME"])
CONFIG = HOME / ".claude.json"


def die(message):
    raise ValueError(message)


def dependency_version():
    package = json.loads((PROJECT / "package.json").read_text())
    version = package["dependencies"]["@opencode/client"]
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        die("OpenCode client must be pinned to an exact version")
    return version


def dependency_current():
    path = PROJECT / "node_modules" / "@opencode" / "client" / "package.json"
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


def owned_entry(entry):
    if not isinstance(entry, dict) or entry.get("type", "stdio") != "stdio":
        return False
    command = entry.get("command")
    if not isinstance(command, str) or Path(command).name != "node":
        return False
    if entry.get("args") != ["--experimental-strip-types", str(SERVER)]:
        return False
    return not entry.get("env") and set(entry).issubset({"type", "command", "args", "env"})


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
        die(f"npm did not install pinned @opencode/client {dependency_version()}")


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
    node = managed_binary("node")
    desired = expected_entry(node or "node")
    if previous is not None and not owned_entry(previous):
        die(f"{NAME} already names a different MCP server; leaving it unchanged")

    if action == "plan":
        if not dependency_current():
            print(f"NPM: install pinned @opencode/client {dependency_version()}")
        if previous != desired:
            print(f"MCP: register {NAME} with Claude user scope")
        return

    if action == "check":
        if not dependency_current():
            die("OpenCode worker dependency is not installed")
        if previous != desired:
            die(f"{NAME} MCP registration is missing or outdated")
        print(f"ok: {NAME} MCP and dependency current")
        return

    if action == "remove":
        if previous is None:
            return
        del servers[NAME]
        update_configuration(data, original)
        print(f"sync: unregistered {NAME}")
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
        servers[NAME] = desired
        update_configuration(data, original)
        print(f"sync: registered {NAME} for Claude Code")


if __name__ == "__main__":
    try:
        if len(sys.argv) != 2:
            die("usage: claude-worker.py {plan|check|install|remove}")
        run(sys.argv[1])
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"sync: Claude worker bridge: {exc}", file=sys.stderr)
        sys.exit(1)

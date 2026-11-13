#!/usr/bin/env python3
"""Remove usr's owned OpenCode MCP bridge entry; never touch OpenCode credentials."""
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
CONFIG = Path(os.environ.get("XDG_CONFIG_HOME", str(HOME / ".config"))) / "opencode/opencode.json"
OWNER = Path(os.environ.get("XDG_STATE_HOME", str(HOME / ".local/state"))) / "sync/opencode-mcp-owner.json"


def die(message):
    raise ValueError(message)


def service_is_running(opencode):
    result = subprocess.run(
        [opencode, "service", "status"], capture_output=True, text=True, timeout=60,
    )
    if result.returncode != 0:
        die("cannot check OpenCode service status: " + (result.stderr.strip() or "command failed"))
    return result.stdout.strip().lower() != "stopped"


def restart_opencode_service():
    if os.environ.get("OPENCODE"):
        print("sync: OpenCode registration changed; not restarting the service from inside an OpenCode session; run `opencode service restart`")
        return
    opencode = shutil.which("opencode")
    if opencode is None:
        return
    if not service_is_running(opencode):
        print("sync: OpenCode service not running; MCP registration takes effect when opencode next starts")
        return
    result = subprocess.run(
        [opencode, "service", "restart"], capture_output=True, text=True, timeout=120,
    )
    if result.returncode != 0:
        die("OpenCode service restart failed: " + (result.stderr.strip() or "command failed")
            + "; run `opencode service restart` manually")
    print("sync: restarted opencode service to pick up the new MCP registration")


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


def owned_entry(entry):
    if not isinstance(entry, dict) or entry.get("type", "local") != "local":
        return False
    if not set(entry).issubset({"type", "command", "codemode"}):
        return False
    if entry.get("codemode") not in (None, False):
        return False
    if entry.get("command") == ["pi-subagent-bridge", "mcp"]:
        return True
    command = entry.get("command")
    if not isinstance(command, list) or len(command) != 3 or Path(command[0]).name != "node":
        return False
    if command[1] != "--experimental-strip-types":
        return False
    server = command[2]
    if not isinstance(server, str) or not Path(server).is_absolute() or not (
        server.endswith("/tools/pi-subagent-bridge/src/server.ts")
        or server.endswith("/tools/opencode-worker/src/server.ts")
    ):
        return False
    if entry.get("codemode") not in (None, False):
        return False
    username = HOME.name
    home_roots = {HOME, Path("/Users") / username, Path("/home") / username}
    known_servers = {str(root / "usr/tools/pi-subagent-bridge/src/server.ts") for root in home_roots}
    known_servers.update(str(root / "usr/tools/opencode-worker/src/server.ts") for root in home_roots)
    return server == str(SERVER) or server in known_servers or load_owner() == entry_fingerprint(entry)


def servers_in(data):
    mcp = data.get("mcp", {})
    if not isinstance(mcp, dict):
        die("OpenCode mcp must be an object")
    servers = mcp.get("servers", {})
    if not isinstance(servers, dict):
        die("OpenCode mcp.servers must be an object")
    return mcp, servers


def configuration():
    target = CONFIG.resolve()
    if not target.exists():
        return {}, None
    original = target.read_bytes()
    try:
        value = json.loads(original)
    except (UnicodeError, ValueError) as exc:
        die(f"cannot parse {target}: {exc}")
    if not isinstance(value, dict):
        die("OpenCode configuration must be an object")
    servers_in(value)
    return value, original


def pending_owned(servers):
    return {name for name in (NAME, LEGACY_NAME)
            if name in servers and owned_entry(servers[name])}


def update_configuration(data, original):
    target = CONFIG.resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode()
    if original == payload:
        return
    if original is not None and target.read_bytes() != original:
        die("OpenCode configuration changed concurrently; retry sync")
    mode = stat.S_IMODE(target.stat().st_mode) if original is not None else 0o600
    fd, temporary = tempfile.mkstemp(prefix=".opencode.json.", dir=target.parent)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "wb") as output:
            output.write(payload)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def run_remove():
    data, original = configuration()
    _, servers = servers_in(data)
    names = pending_owned(servers)
    for name in names:
        del servers[name]
    if not servers and isinstance(data.get("mcp"), dict):
        del data["mcp"]["servers"]
        if not data["mcp"]:
            del data["mcp"]
    if names:
        update_configuration(data, original)
        print(f"sync: unregistered {', '.join(sorted(names))}")
        restart_opencode_service()
    OWNER.unlink(missing_ok=True)


def run_verify_absent():
    data, _ = configuration()
    _, servers = servers_in(data)
    if pending_owned(servers):
        die(f"{NAME} MCP registration is still present")
    print(f"ok: {NAME} not registered with OpenCode")


def main():
    if len(sys.argv) != 2:
        die("usage: opencode-worker.py {remove|verify-absent}")
    action = sys.argv[1]
    if action == "remove":
        run_remove()
    elif action == "verify-absent":
        run_verify_absent()
    else:
        die("usage: opencode-worker.py {remove|verify-absent}")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"sync: OpenCode worker bridge: {exc}", file=sys.stderr)
        sys.exit(1)

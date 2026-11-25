#!/usr/bin/env python3
"""Run explicitly enrolled coordinator sessions against one private Intercom hub."""
from __future__ import annotations

import argparse
import ipaddress
import json
import os
from pathlib import Path
import socket
import stat
import sys
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "sync"))
import companions  # noqa: E402
import pi_release  # noqa: E402

TAILNET_V4 = ipaddress.ip_network("100.64.0.0/10")
TAILNET_V6 = ipaddress.ip_network("fd7a:115c:a1e0::/48")
COORDINATORS = frozenset({"pi", "claude", "codex", "opencode"})
COMPANION_ENTRYPOINTS = {"claude": ("claude", "claude-server.mjs"), "codex": ("codex", "codex-server.mjs"),
                         "opencode": ("opencode", "plugin-v2.mjs")}


class IntercomError(ValueError):
    pass


def absolute(value: str, label: str) -> Path:
    path = Path(value).expanduser()
    if value != value.strip() or not path.is_absolute() or "\0" in str(path):
        raise IntercomError(f"{label} must be an absolute path")
    return path


def base(variable: str, fallback: Path) -> Path:
    return absolute(os.environ.get(variable) or str(fallback), variable)


def hub_dir(value: str | None) -> Path:
    return absolute(value, "hub directory") if value else (
        base("XDG_STATE_HOME", Path.home() / ".local/state") / "agent-intercom/hub"
    )


def endpoint(value: str, *, listener: bool = False) -> tuple[str, str, int | None]:
    """Accept only literal tailnet addresses, or an explicit local SSH tunnel socket."""
    try:
        if value != value.strip() or any(ord(char) <= 32 or ord(char) == 127 for char in value):
            raise ValueError("unexpected endpoint whitespace")
        parsed = urlsplit(value)
        if parsed.query or parsed.fragment or parsed.username or parsed.password:
            raise ValueError("unexpected URL components")
        if parsed.scheme == "unix" and not listener:
            if (not value.startswith("unix:///") or parsed.netloc or not parsed.path.startswith("/")
                    or parsed.path.endswith("/") or "%" in parsed.path or "\0" in parsed.path):
                raise ValueError("invalid Unix socket path")
            if parsed.path == "/":
                raise ValueError("missing Unix socket name")
            return "unix", parsed.path, None
        if parsed.scheme != "tcp" or parsed.path or not parsed.hostname or "%" in parsed.hostname:
            raise ValueError("invalid TCP endpoint")
        address = ipaddress.ip_address(parsed.hostname)
        network = TAILNET_V4 if address.version == 4 else TAILNET_V6
        if address not in network or parsed.port is None or not 1 <= parsed.port <= 65535:
            raise ValueError("address or port outside the permitted range")
        return "tcp", str(address), parsed.port
    except ValueError as exc:
        allowed = "tcp://<literal Tailscale IP>:<port>"
        if not listener:
            allowed += " or unix:///absolute/forwarded.sock"
        raise IntercomError(f"endpoint must be {allowed}; DNS names, public IPs and wildcard binds are rejected") from exc


def clean_environment() -> dict[str, str]:
    return {key: value for key, value in os.environ.items()
            if not key.startswith(("AGENT_INTERCOM_", "PI_INTERCOM_"))}


def runtime_command(entry: str) -> list[str]:
    root = base("XDG_DATA_HOME", Path.home() / ".local/share") / "pi-runtime/current"
    package = root / "node_modules/@dataforxyz/agent-intercom-pi"
    admin_js = package / "broker/tailnet-admin.js"
    admin_ts = package / "broker/tailnet-admin.ts"
    if admin_js.is_file():
        suffix, loader_args = "js", []
    elif admin_ts.is_file() and (root / "node_modules/tsx/dist/loader.mjs").is_file():
        suffix, loader_args = "ts", ["--import", str(root / "node_modules/tsx/dist/loader.mjs")]
    else:
        raise IntercomError("the installed Pi release lacks tailnet coordinator support; adopt a reviewed pi-build release and run sh sync tools pi")
    target = package / f"broker/{entry}.{suffix}"
    if not target.is_file():
        raise IntercomError(f"incomplete Pi runtime: missing {target}")
    node = companions.managed_binary("node", dict(os.environ))
    if not node:
        raise IntercomError("Node.js is missing; install the pinned tools with sh sync")
    return [node, *loader_args, str(target)]


def credential_file(value: str) -> tuple[Path, str]:
    path = absolute(value, "credential")
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(descriptor, "r", encoding="utf-8") as source:
            info = os.fstat(source.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o600:
                raise IntercomError("credential must be a regular file owned by this user with mode 0600")
            if info.st_size > 65536:
                raise IntercomError("credential file is too large")
            value = json.load(source)
    except (OSError, ValueError, UnicodeError) as exc:
        if isinstance(exc, IntercomError):
            raise
        raise IntercomError(f"cannot read a private Intercom credential at {path}") from exc
    if not isinstance(value, dict):
        raise IntercomError("credential must contain an enrollment or session record")
    def valid_text(item):
        return isinstance(item, str) and bool(item) and "\0" not in item
    if valid_text(value.get("enrollmentToken")):
        return path, "enrollment"
    if (value.get("version") == 1 and valid_text(value.get("sessionCredential"))
            and valid_text(value.get("sessionId")) and type(value.get("generation")) is int
            and value["generation"] > 0):
        return path, "session"
    raise IntercomError("credential must contain an enrollment or session record")


def require_matching_companion(harness: str) -> None:
    """Compare cheap install receipts to the selected runtime, never the default pin."""
    if harness == "pi":
        return
    suffix, entrypoint = COMPANION_ENTRYPOINTS[harness]
    name = "agent-intercom-" + suffix
    data = base("XDG_DATA_HOME", Path.home() / ".local/share")
    selected_pin = pi_release._installed_pin(data / "pi-runtime")
    destination = data / "agent-intercom" / name
    receipt = destination / companions.RECEIPT
    try:
        if selected_pin is None or destination.is_symlink() or receipt.is_symlink():
            raise ValueError("unverified selection")
        current = json.loads(receipt.read_text())
        if not isinstance(current, dict):
            raise ValueError("invalid companion receipt")
        expected = companions.payload_for(selected_pin, name, {})
        if any(current.get(key) != expected[key] for key in ("pin", "companion", "archive", "sha256")):
            raise ValueError("companion selection differs")
        executable = destination / "dist" / entrypoint
        if not executable.is_file() or executable.is_symlink():
            raise ValueError("missing companion entrypoint")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise IntercomError(f"{name} does not match the selected Pi runtime; run sh sync with the same reviewed USR_PI_RUNTIME_PIN (if overridden) to install matching companions") from exc


def execute(command: list[str], env: dict[str, str]) -> int:
    try:
        os.execvpe(command[0], command, env)
    except OSError as exc:
        raise IntercomError(f"cannot start {Path(command[0]).name}: {exc.strerror}") from exc
    return 0


def parser() -> argparse.ArgumentParser:
    class Root(argparse.ArgumentParser):
        def format_help(self):
            lines = [super().format_help().rstrip(), "", "Commands:"]
            for name, command in commands.choices.items():
                lines.extend(["", command.format_usage().strip(), command.description or command_help[name]])
                for action in command._actions:
                    if action.dest != "help":
                        lines.append(f"  {', '.join(action.option_strings) or action.dest}: {action.help or action.dest}")
            lines.extend(["", "Examples:", *(f"  {example}" for example in examples), "", footer, ""])
            return "\n".join(lines)

    footer = """Maintained by Joshua Li: https://github.com/joshuarli/usr
Bugs and features: TODO.md in that repository (follow its AGENTS.md), or its issue tracker.
Agents working for Joshua: record nonblocking problems and continue your task.
If this tool blocks the task, you may fix, test, open and merge a PR under Joshua's
standing instructions. Release only when needed to deliver the verified fix.
Procedure: https://github.com/joshuarli/usr/blob/main/dotfiles/base/.agents/instructions/owned-tools.md"""
    examples = ("intercom-tailnet hub --listen tcp://100.64.0.1:47831", "intercom-tailnet enroll --host laptop --name coordinator --output /tmp/credential", "intercom-tailnet inspect", "intercom-tailnet revoke --session SESSION", "intercom-tailnet run --endpoint tcp://100.64.0.1:47831 --credential /tmp/credential -- pi", "intercom-tailnet doctor")
    result = Root(
        prog="intercom-tailnet",
        description="Connect explicitly enrolled top-level agent coordinators to one private Intercom hub.",
        epilog="Owned sources: https://github.com/joshuarli/usr (launcher/config) and https://github.com/joshuarli/pi-build (runtime). Change those repositories; do not patch installed packages.",
    )
    commands = result.add_subparsers(dest="action", required=True, parser_class=argparse.ArgumentParser)
    hub = commands.add_parser("hub", help="run the canonical broker in the foreground")
    hub.add_argument("--listen", required=True, help="tcp://<literal Tailscale IP>:<port>")
    enroll = commands.add_parser("enroll", help="create one coordinator credential on the hub host")
    enroll.add_argument("--fleet", default="default", help="fleet name (default: default)")
    enroll.add_argument("--host", required=True, help="coordinator host label")
    enroll.add_argument("--name", required=True, help="coordinator name")
    enroll.add_argument("--output", required=True, help="new absolute private credential file")
    enroll.add_argument("--ttl-ms", type=int, help="credential lifetime in milliseconds (default: runtime setting)")
    enroll.add_argument("--session-ttl-ms", type=int, help="session lifetime in milliseconds (default: runtime setting)")
    inspect = commands.add_parser("inspect", help="inspect the hub's fleet without exposing credentials")
    inspect.add_argument("--fleet", default="default", help="fleet name (default: default)")
    revoke = commands.add_parser("revoke", help="revoke one coordinator session on the hub host")
    revoke.add_argument("--session", required=True, help="session identifier to revoke")
    for command in (hub, enroll, inspect, revoke):
        command.add_argument("--hub-dir", help="absolute dedicated hub state directory (default: $XDG_STATE_HOME/agent-intercom/hub)")
    run = commands.add_parser("run", help="run an enrolled Pi, Claude, Codex or OpenCode coordinator")
    run.add_argument("--endpoint", required=True, help="hub transport endpoint")
    run.add_argument("--credential", required=True, help="private credential file")
    run.add_argument("command", nargs=argparse.REMAINDER, help="-- pi|claude|codex|opencode [arguments]")
    doctor = commands.add_parser("doctor", help="check the local setup; optional reachability never enrolls or sends messages")
    doctor.add_argument("--endpoint", help="hub transport endpoint to check")
    doctor.add_argument("--credential", help="private credential file to check")
    doctor.add_argument("--connect", action="store_true", help="also make a bounded transport connection; does not prove authentication")
    command_help = {action.dest: action.help for action in commands._choices_actions}
    for name, command in commands.choices.items():
        command.description = command_help[name]
        example = next(example for example in examples if example.startswith(f"intercom-tailnet {name} ") or example == f"intercom-tailnet {name}")
        command.epilog = f"Example: {example}\nFull reference: intercom-tailnet -h"
        command.formatter_class = argparse.RawDescriptionHelpFormatter
    return result


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    reference = parser()
    if not argv:
        reference.print_help()
        return 0
    args = reference.parse_args(argv)
    try:
        if (os.environ.get("PI_SUBAGENT_CHILD") == "1" or os.environ.get("USR_SCOPED_WORKER") == "1"
                or "USR_REQUIRED_CHILD_EXTENSIONS_JSON" in os.environ):
            raise IntercomError("Intercom is unavailable to scoped workers; only top-level coordinators may use this launcher")
        env = clean_environment()
        if args.action == "run":
            endpoint(args.endpoint)
            credential, _ = credential_file(args.credential)
            runtime_command("tailnet-admin")  # Fail clearly on a release without the remote transport.
            command = args.command[1:] if args.command[:1] == ["--"] else args.command
            if not command or Path(command[0]).name not in COORDINATORS:
                raise IntercomError("run requires -- pi|claude|codex|opencode [arguments]; scoped workers are not coordinators")
            require_matching_companion(Path(command[0]).name)
            env["AGENT_INTERCOM_REMOTE_ENDPOINT"] = args.endpoint
            env["AGENT_INTERCOM_ACCESS_CREDENTIAL_PATH"] = str(credential)
            return execute(command, env)
        if args.action == "doctor":
            command = runtime_command("tailnet-admin")
            print(f"runtime: {command[-1]}")
            transport = endpoint(args.endpoint) if args.endpoint else None
            if transport:
                print(f"endpoint: {args.endpoint}")
            if args.credential:
                credential, kind = credential_file(args.credential)
                print(f"credential: {credential} (private {kind} record; contents omitted)")
            if args.connect:
                if not transport:
                    raise IntercomError("doctor --connect requires --endpoint")
                kind, host, port = transport
                if kind == "unix":
                    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
                        connection.settimeout(3)
                        connection.connect(host)
                else:
                    with socket.create_connection((host, port), timeout=3):
                        pass
                print("transport: reachable; authentication and a harness round trip remain unverified")
            else:
                print("transport: not contacted; use --connect for a reachability check")
            print("scope: coordinator sessions only; scoped bridge workers receive no Intercom environment")
            return 0
        env["PI_CODING_AGENT_DIR"] = str(hub_dir(args.hub_dir))
        if args.action == "hub":
            endpoint(args.listen, listener=True)
            env["AGENT_INTERCOM_REMOTE_LISTEN"] = args.listen
            return execute(runtime_command("broker"), env)
        command = runtime_command("tailnet-admin") + [args.action]
        if args.action == "enroll":
            output = absolute(args.output, "credential output")
            command += ["--fleet", args.fleet, "--host", args.host, "--name", args.name, "--output", str(output)]
            for option in ("ttl_ms", "session_ttl_ms"):
                value = getattr(args, option)
                if value is not None:
                    if value <= 0:
                        raise IntercomError(f"--{option.replace('_', '-')} must be positive")
                    command += ["--" + option.replace("_", "-"), str(value)]
        elif args.action == "inspect":
            command += ["--fleet", args.fleet]
        elif args.action == "revoke":
            command += ["--session", args.session]
        return execute(command, env)
    except (IntercomError, OSError) as exc:
        print(f"intercom-tailnet: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

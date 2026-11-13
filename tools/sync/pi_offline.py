"""Shared rules for usr's prebuilt Pi closure: no npm, npx, or pi package reconciliation.

pi_release installs the closure from the pinned pi-build release; this module
owns its locations, launcher, package identity and intercom configuration.
"""
from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Mapping
from pathlib import Path
import platform
import shlex
import stat
import tempfile

LEGACY_STAMP = ".usr-pi-runtime.json"
PACKAGES = {
    "@earendil-works/pi-coding-agent": "1.5.0",
    "pi-subagents": "0.87.0",
    "pi-muse-subscription": "0.1.0",
    "@dataforxyz/agent-intercom-pi": "0.10.0",
    "@dataforxyz/agent-intercom-core": "0.1.0",
}


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


def digest(file: Path) -> str:
    h = hashlib.sha256()
    with file.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _base(env: Mapping[str, str], variable: str, default: Path) -> Path:
    base = Path(env.get(variable) or default)
    if not base.is_absolute():
        raise OfflinePiError(f"{variable} must be absolute")
    return base


def runtime_dir(home: Path, environ: dict[str, str] | None = None) -> Path:
    env = os.environ if environ is None else environ
    return _base(env, "XDG_DATA_HOME", home / ".local/share") / "pi-runtime"


def legacy_dir(home: Path, environ: dict[str, str] | None = None) -> Path:
    env = os.environ if environ is None else environ
    return _base(env, "XDG_DATA_HOME", home / ".local/share") / "pi"


def is_legacy_runtime(root: Path) -> bool:
    return (not root.is_symlink() and root.is_dir() and (root / LEGACY_STAMP).is_file()
            and (root / "bin/pi").is_file() and not (root / "bin/pi").is_symlink())


def cache_dir(home: Path, environ: dict[str, str] | None = None) -> Path:
    env = os.environ if environ is None else environ
    return _base(env, "XDG_CACHE_HOME", home / ".cache") / "usr/pi-releases"


def version_matches(root: Path, profile: str = "full") -> bool:
    if profile not in {"full", "headless-usr"}:
        return False
    try:
        for name, version in PACKAGES.items():
            actual = json.loads((root / "node_modules" / name / "package.json").read_text())["version"]
            if actual != version:
                return False
        if profile == "headless-usr":
            for name, entry in (("pi-subagents", "index.js"),
                                ("@dataforxyz/agent-intercom-pi", "index.js"),
                                ("@dataforxyz/agent-intercom-pi", "broker/broker.js"),
                                ("pi-muse-subscription", "src/index.js")):
                if not (root / "node_modules" / name / entry).is_file():
                    return False
        return (root / "node_modules/@earendil-works/pi-coding-agent/dist/bundle/cli.js").is_file()
    except (OSError, KeyError, ValueError, TypeError):
        return False


def wrapper(root: Path, profile: str = "full") -> str:
    suffix = {"full": "ts", "headless-usr": "js"}[profile]
    sdk = root / "node_modules/@earendil-works/pi-coding-agent/dist/bundle/cli.js"
    subagent = root / f"node_modules/pi-subagents/index.{suffix}"
    intercom = root / f"node_modules/@dataforxyz/agent-intercom-pi/index.{suffix}"
    return ("#!/bin/sh\n"
            "# Bundled in usr; never install or update npm dependencies at runtime.\n"
            "set -eu\n"
            # PI_OFFLINE blocks any project-configured npm/git package auto-installs,
            # and prevents Pi's automatic model catalog/version update requests.
            "export PI_OFFLINE=1 PI_SKIP_VERSION_CHECK=1\n"
            'case "${1:-}" in\n'
            '  install|update) echo "usr-managed Pi: use /pi-update to change packages" >&2; exit 64;;\n'
            'esac\n'
            f"exec node {shlex.quote(str(sdk))} "
            f"--extension {shlex.quote(str(subagent))} "
            f"--extension {shlex.quote(str(intercom))} \"$@\"\n")


def configure_intercom(home: Path, root: Path, profile: str = "full") -> bool:
    """Select the profile's local broker runtime and preserve custom commands."""
    directory = home / ".pi/agent/intercom"
    file = directory / "config.json"
    if directory.is_symlink() or file.is_symlink():
        raise OfflinePiError(f"refusing symlinked intercom configuration: {file}")
    loader = root / "node_modules/tsx/dist/loader.mjs"
    if profile == "full":
        if not loader.is_file():
            raise OfflinePiError(f"missing self-contained TS loader: {loader}")
        broker_args = ["--import", str(loader)]
    elif profile == "headless-usr":
        broker = root / "node_modules/@dataforxyz/agent-intercom-pi/broker/broker.js"
        if not broker.is_file():
            raise OfflinePiError(f"missing compiled intercom broker: {broker}")
        broker_args = []
    else:
        raise OfflinePiError(f"unsupported Pi runtime profile: {profile}")
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
    managed = (not desired.get("brokerCommand") or desired.get("brokerCommand") in ("npx", "npm")
               or (desired.get("brokerCommand") == "node" and (
                   desired.get("brokerArgs") in (
                       ["--no-install", "tsx"], ["--import", str(loader)],
                       ["--import", str(legacy_dir(home) / "node_modules/tsx/dist/loader.mjs")])
                   or (desired.get("usrBrokerProfile") == "headless-usr" and desired.get("brokerArgs") == []))))
    if managed:
        desired["brokerCommand"] = "node"
        desired["brokerArgs"] = broker_args
        desired["usrBrokerProfile"] = profile
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

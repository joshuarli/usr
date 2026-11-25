"""Advisory login detection for the harness CLIs sync installs.

Each probe answers one question for one harness: is this machine signed in?
Probes are read-only, run in parallel, skip harnesses that are not installed,
never echo account data or credential material, and never fail the sync run.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from dag import Probe
from report import TaskLine

RunProbe = Callable[[Path, dict[str, str]], Probe]


@dataclass(frozen=True)
class Harness:
    name: str
    binary: str
    probe: RunProbe


def _read_json(path: Path):
    try:
        if path.stat().st_size > 1_000_000:
            return None
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        return None


def _run(home: Path, env: dict[str, str], binary: Path, *args: str, timeout: float = 6.0):
    child = env.copy()
    child["HOME"] = str(home)
    try:
        return subprocess.run([str(binary), *args], env=child, text=True,
                              capture_output=True, stdin=subprocess.DEVNULL,
                              timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None


def _output(result: subprocess.CompletedProcess[str] | None) -> str:
    if result is None:
        return ""
    return (result.stdout + "\n" + result.stderr).lower()


def _signed_out(result, out: str, hint: str) -> Probe:
    if result is None:
        return Probe(False, f"could not check — {hint}")
    if result.returncode == 0:
        return Probe(True, "signed in")
    if "not logged in" in out:
        return Probe(False, f"not signed in — {hint}")
    return Probe(False, f"could not check — {hint}")


def _codex(home: Path, env: dict[str, str]) -> Probe:
    binary = home / ".local/bin/codex"
    result = _run(home, env, binary, "login", "status")
    out = _output(result)
    return _signed_out(result, out, "codex login")


def _claude(home: Path, env: dict[str, str]) -> Probe:
    binary = home / ".local/bin/claude"
    result = _run(home, env, binary, "auth", "status")
    if result is not None:
        try:
            data = json.loads(result.stdout)
        except ValueError:
            data = None
        if isinstance(data, dict) and isinstance(data.get("loggedIn"), bool):
            if data["loggedIn"]:
                return Probe(True, "signed in")
            return Probe(False, "not signed in — claude auth login")
    if result is not None and result.returncode == 0:
        return Probe(True, "signed in")
    return Probe(False, "could not check — claude auth status")


def _devin(home: Path, env: dict[str, str]) -> Probe:
    data_home = Path(env.get("XDG_DATA_HOME") or home / ".local/share")
    if not data_home.is_absolute():
        data_home = home / ".local/share"
    if (data_home / "devin/credentials.toml").is_file():
        return Probe(True, "signed in")
    return Probe(False, "not signed in — devin auth login")


def _cmd(home: Path, env: dict[str, str]) -> Probe:
    data = _read_json(home / ".commandcode" / "auth.json")
    if isinstance(data, dict) and isinstance(data.get("apiKey"), str) and data["apiKey"].strip():
        return Probe(True, "signed in")
    return Probe(False, "not signed in — cmd login")


def _pi(home: Path, env: dict[str, str]) -> Probe:
    agent = Path(env.get("PI_CODING_AGENT_DIR") or home / ".pi" / "agent")
    if not agent.is_absolute():
        agent = home / ".pi" / "agent"
    data = _read_json(agent / "auth.json")
    if isinstance(data, dict) and data:
        return Probe(True, "signed in")
    return Probe(False, "not configured — run `sh sync` to seed Pi from the opencode login")


def _muse(home: Path, env: dict[str, str]) -> Probe:
    if env.get("META_API_KEY", "").strip():
        return Probe(True, "signed in")
    config_home = Path(env.get("XDG_CONFIG_HOME") or home / ".config")
    data_home = Path(env.get("XDG_DATA_HOME") or home / ".local/share")
    for base in (config_home, data_home):
        if not base.is_absolute():
            continue
        data = _read_json(base / "muse" / "auth.json")
        if isinstance(data, dict):
            providers = data.get("providers")
            if isinstance(providers, (dict, list)) and providers:
                return Probe(True, "signed in")
    return Probe(False, "not signed in — muse login")


def _opencode(home: Path, env: dict[str, str]) -> Probe:
    binary = home / ".local/bin/opencode"
    result = _run(home, env, binary, "auth", "list")
    out = _output(result)
    if result is None:
        return Probe(False, "could not check — opencode auth list")
    if "no authenticated integrations" in out:
        return Probe(False, "no credentials — opencode auth login")
    if "stored" in out:
        return Probe(True, "signed in")
    return Probe(False, "could not check — opencode auth list")


def _agy(home: Path, env: dict[str, str]) -> Probe:
    binary = home / ".local/bin/agy"
    result = _run(home, env, binary, "models", timeout=8.0)
    out = _output(result)
    if result is not None and result.returncode == 0:
        return Probe(True, "signed in")
    if result is not None and "sign in" in out:
        return Probe(False, "not signed in — run `agy` to sign in")
    return Probe(False, "could not check — agy models")


def _fx(home: Path, env: dict[str, str]) -> Probe:
    binary = home / ".local/bin/fx"
    result = _run(home, env, binary, "status", "--json")
    if result is not None:
        try:
            data = json.loads(result.stdout)
        except ValueError:
            data = None
        if isinstance(data, dict):
            auth = data.get("auth")
            if isinstance(auth, str) and auth.strip() and auth.lower() != "missing":
                return Probe(True, f"signed in ({auth.strip()})")
            return Probe(False, "not signed in — fx login")
    return Probe(False, "could not check — fx status --json")


def _dsh(home: Path, env: dict[str, str]) -> Probe:
    if env.get("DEEPSEEK_API_KEY", "").strip():
        return Probe(True, "signed in")
    vault = shutil.which("vault", path=env.get("PATH"))
    if vault is None and (home / ".local/bin/vault").exists():
        vault = str(home / ".local/bin/vault")
    if vault is None:
        return Probe(False, "no DEEPSEEK_API_KEY — export one or install vault")
    result = _run(home, env, Path(vault), "ls", timeout=3.0)
    if result is None:
        return Probe(False, "could not check — vault ls (store may be locked)")
    if "deepseek_api_key" in (result.stdout or "").lower():
        return Probe(True, "signed in")
    return Probe(False, "no DEEPSEEK_API_KEY in vault — vault set DEEPSEEK_API_KEY")


HARNESSES: tuple[Harness, ...] = tuple(sorted((
    Harness("agy", "agy", _agy),
    Harness("claude", "claude", _claude),
    Harness("cmd", "cmd", _cmd),
    Harness("codex", "codex", _codex),
    Harness("devin", "devin", _devin),
    Harness("dsh", "dsh", _dsh),
    Harness("fx", "fx", _fx),
    Harness("pi", "pi", _pi),
    Harness("muse", "muse", _muse),
    Harness("opencode", "opencode", _opencode),
), key=lambda harness: harness.name))


def _installed(home: Path, binary: str) -> bool:
    return os.access(home / ".local/bin" / binary, os.X_OK)


def login_lines(home: Path, env: dict[str, str]) -> list[TaskLine]:
    pending = [harness for harness in HARNESSES if _installed(home, harness.binary)]
    if not pending:
        return []
    lines: list[TaskLine] = []
    with ThreadPoolExecutor(max_workers=len(pending)) as pool:
        results = list(pool.map(lambda harness: harness.probe(home, env), pending))
    for harness, probe in zip(pending, results):
        state = "current" if probe.current else "login"
        lines.append(TaskLine(f"auth:{harness.name}", state, probe.detail))
    return lines

"""Seed Pi's OpenCode Go credential from the opencode login.

The key is a runtime command, not a copied token: Pi runs
`opencode auth export opencode` when it needs the credential, so sync never
sees, stores or refreshes access tokens. Existing entries are preserved; an
unreadable or non-object auth file is a conflict and is never rewritten.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dag import Probe

PROVIDER = "opencode-go"
ENTRY = {
    "type": "api_key",
    "key": "!opencode auth export opencode | jaq -r '.[] | select(.active) | .value.access'",
}
MAX_AUTH_BYTES = 1_000_000


def auth_path(home: Path, env: dict[str, str]) -> Path:
    agent = Path(env.get("PI_CODING_AGENT_DIR") or home / ".pi" / "agent")
    if not agent.is_absolute():
        agent = home / ".pi" / "agent"
    return agent / "auth.json"


def _load(path: Path) -> dict[str, object]:
    size = path.stat().st_size
    if size > MAX_AUTH_BYTES:
        raise ValueError("file too large to be a Pi credential file")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("expected a JSON object")
    return dict(data)


def status(home: Path, env: dict[str, str]) -> Probe:
    path = auth_path(home, env)
    if path.is_symlink():
        return Probe(False, "refusing to manage a symlinked Pi credential file", True)
    if not path.exists():
        return Probe(False, "Pi credential file missing the opencode-go provider")
    try:
        data = _load(path)
    except (OSError, UnicodeError, ValueError) as exc:
        return Probe(False, f"unreadable Pi credential file: {exc}", True)
    if PROVIDER in data:
        return Probe(True, "opencode-go provider configured")
    return Probe(False, "Pi credential file missing the opencode-go provider")


def apply(home: Path, env: dict[str, str]) -> None:
    path = auth_path(home, env)
    agent = path.parent
    if path.is_symlink():
        raise RuntimeError(f"refusing to manage a symlinked Pi credential file: {path}")
    data: dict[str, object] = {}
    if path.exists():
        try:
            data = _load(path)
        except (OSError, UnicodeError, ValueError) as exc:
            raise RuntimeError(f"refusing to rewrite unreadable Pi credential file: {exc}") from exc
        if PROVIDER in data:
            return
    agent.mkdir(parents=True, exist_ok=True)
    merged = {**data, PROVIDER: ENTRY}
    payload = (json.dumps(merged, indent=2) + "\n").encode()
    fd, temporary = tempfile.mkstemp(prefix=".auth.json.", dir=agent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as output:
            output.write(payload)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)

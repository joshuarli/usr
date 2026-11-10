#!/usr/bin/env python3
from __future__ import annotations

from enum import Enum
import json
from pathlib import Path
import sys


class Harness(Enum):
    CLAUDE = "claude"
    CODEX = "codex"


class Profile(Enum):
    NORMAL = ".codex/AGENTS.md"
    LEAN = ".agents/instructions/lean.md"


INPUT_LIMIT = 1048576
CONTRACT_LIMIT = 32768


def select_profile(harness: Harness, payload: dict[str, object]) -> Profile | None:
    event = payload.get("hook_event_name")
    if event != "SessionStart" and not (harness is Harness.CODEX and event == "SubagentStart"):
        return None
    model = payload.get("model")
    if (harness is Harness.CLAUDE and model == "claude-opus-5-5") or (
        harness is Harness.CODEX and model == "gpt-6.1-sol"
    ):
        return Profile.LEAN
    return Profile.NORMAL


def read_contract(profile: Profile) -> str:
    source = Path(__file__).resolve().parents[2] / profile.value
    with source.open("rb") as stream:
        raw = stream.read(CONTRACT_LIMIT + 1)
    if len(raw) > CONTRACT_LIMIT:
        raise ValueError("oversized contract")
    text = raw.decode("utf-8")
    if not text.strip():
        raise ValueError("empty contract")
    return text


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: agent-instructions.py claude|codex", file=sys.stderr)
        return 2
    try:
        harness = Harness(sys.argv[1])
    except ValueError:
        print("usage: agent-instructions.py claude|codex", file=sys.stderr)
        return 2
    try:
        raw = sys.stdin.buffer.read(INPUT_LIMIT + 1)
        if len(raw) > INPUT_LIMIT:
            raise ValueError("oversized input")
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError("expected object")
    except (OSError, ValueError, RecursionError):
        print("agent-instructions: invalid hook input", file=sys.stderr)
        return 1
    profile = select_profile(harness, payload)
    if profile is None:
        return 0
    try:
        contract = read_contract(profile)
    except (OSError, ValueError):
        print("agent-instructions: cannot read selected contract", file=sys.stderr)
        return 1
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": payload["hook_event_name"],
        "additionalContext": contract,
    }}))
    return 0


if __name__ == "__main__":
    sys.exit(main())

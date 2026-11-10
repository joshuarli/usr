#!/usr/bin/env python3
from __future__ import annotations

from enum import Enum
import json
from pathlib import Path
import sys


class Harness(Enum):
    CLAUDE = "claude"
    CODEX = "codex"


class Overlay(Enum):
    OPUS = ".claude/model-overlays/opus-5-5.md"
    SOL = ".codex/model-overlays/gpt-6.1-sol.md"
    BASELINE = "baseline"


OPUS_MODEL = "claude-opus-5-5"
SOL_MODEL = "gpt-6.1-sol"
INPUT_LIMIT = 1048576
OVERLAY_LIMIT = 4096


def select_overlay(harness: Harness, payload: dict[str, object]) -> Overlay | None:
    event = payload.get("hook_event_name")
    if harness is Harness.CLAUDE:
        if event == "SessionStart":
            model = payload.get("model")
        elif event == "PostModelSwitch":
            model = payload.get("to_model")
        else:
            return None
        return Overlay.OPUS if model == OPUS_MODEL else Overlay.BASELINE
    if harness is Harness.CODEX and event in ("SessionStart", "UserPromptSubmit", "SubagentStart"):
        return Overlay.SOL if payload.get("model") == SOL_MODEL else Overlay.BASELINE
    return None


def read_overlay(overlay: Overlay) -> str:
    if overlay is Overlay.BASELINE:
        return (
            "usr model overlay selection: baseline. Earlier usr model overlays are inactive. "
            "Follow the shared working contract and current task."
        )
    source = Path(__file__).resolve().parents[2] / overlay.value
    with source.open("rb") as stream:
        raw = stream.read(OVERLAY_LIMIT + 1)
    if len(raw) > OVERLAY_LIMIT:
        raise ValueError("oversized overlay")
    text = raw.decode("utf-8")
    if not text.strip():
        raise ValueError("empty overlay")
    return text


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: agent-model-overlay.py claude|codex", file=sys.stderr)
        return 2
    try:
        harness = Harness(sys.argv[1])
    except ValueError:
        print("usage: agent-model-overlay.py claude|codex", file=sys.stderr)
        return 2
    try:
        raw = sys.stdin.buffer.read(INPUT_LIMIT + 1)
        if len(raw) > INPUT_LIMIT:
            raise ValueError("oversized input")
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError("expected object")
    except (OSError, ValueError, RecursionError):
        print("agent-model-overlay: invalid hook input", file=sys.stderr)
        return 1
    overlay = select_overlay(harness, payload)
    if overlay is None:
        return 0
    try:
        context = read_overlay(overlay)
    except (OSError, ValueError):
        print("agent-model-overlay: cannot read selected overlay", file=sys.stderr)
        return 1
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": payload["hook_event_name"],
        "additionalContext": context,
    }}))
    return 0


if __name__ == "__main__":
    sys.exit(main())

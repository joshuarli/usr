#!/usr/bin/env python3
"""Measure skill use and approval stalls from local Claude and Codex sessions.

usage.py loads [--days N] [--json]   per-skill sessions that loaded or invoked each skill
usage.py stalls [--days N] [--json]  approval nudges and stops after run-until-done authority

Counts are per session. Claude subagent transcripts (subdirectories) and Codex
child sessions (cwd under .work/) are excluded, and Codex's skill listing is
ignored: only tool calls that read a SKILL.md count as a load.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from collections import Counter
from collections.abc import Iterator
from dataclasses import asdict, dataclass, field
from typing import Any
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SKILL_ROOTS = (REPO / "dotfiles/base/.agents/skills", REPO / ".agents/skills")
SKILL_READ = re.compile(r"skills/([a-z0-9-]+)/SKILL\.md")
SLASH = re.compile(r"<command-name>/([a-z0-9:-]+)</command-name>")
DOLLAR = re.compile(r"(?:^|\s)\$([a-z0-9-]+)\b")
AUTHORITY = re.compile(r"(?i)\b(?:don'?t|do not|never) stop\b|\bkeep going until\b|\buntil (?:the )?(?:campaign|it|everything) is (?:done|complete)|\bi'?m going to sleep\b|\byou have (?:full )?(?:autonomy|decision power)\b|\bbe unattended\b")
NUDGE = re.compile(r"(?i)^\s*(?:continue|keep going|go(?: on| ahead)?|proceed|yes|yep|do it|carry on|all approved,? proceed|please (?:continue|don'?t stop)(?: lol)?|don'?t stop)\b[\s.!]*$")


@dataclass
class Session:
    harness: str
    path: Path
    loads: set[str] = field(default_factory=set)
    invoked: set[str] = field(default_factory=set)
    turns: list[tuple[str, str]] = field(default_factory=list)


def skill_modes() -> dict[str, str]:
    modes = {}
    for root in SKILL_ROOTS:
        for skill in sorted(root.glob("*/SKILL.md")):
            front = skill.read_text().split("\n---", 1)[0]
            modes[skill.parent.name] = "explicit" if "\ndisable-model-invocation: true" in front else "auto"
    return modes


def recent(paths: Iterator[Path], cutoff: float) -> Iterator[Path]:
    for path in paths:
        try:
            if path.stat().st_mtime >= cutoff: yield path
        except OSError:
            continue


def records(path: Path) -> Iterator[dict[str, Any]]:
    with path.open(errors="replace") as handle:
        for line in handle:
            try: record = json.loads(line)
            except json.JSONDecodeError: continue
            if isinstance(record, dict): yield record


def text_of(content: object) -> str:
    if isinstance(content, str): return content
    if isinstance(content, list): return "\n".join(str(c.get("text", "")) for c in content if isinstance(c, dict) and c.get("type") in ("text", "input_text", "output_text"))
    return ""


def claude_sessions(home: Path, cutoff: float) -> Iterator[Session]:
    for path in recent((home / ".claude/projects").glob("*/*.jsonl"), cutoff):
        session = Session("claude", path)
        for record in records(path):
            message = record.get("message") or {}
            content = message.get("content")
            if record.get("type") == "assistant" and isinstance(content, list):
                for c in content:
                    if isinstance(c, dict) and c.get("type") == "tool_use" and c.get("name") == "Skill":
                        session.loads.add(str((c.get("input") or {}).get("skill", "")))
                if text := text_of(content).strip(): session.turns.append(("assistant", text))
            elif record.get("type") == "user" and record.get("toolUseResult") is None:
                text = text_of(content)
                session.invoked |= set(SLASH.findall(text))
                if text and not record.get("isMeta") and (not text.startswith("<") or "<command-name>/yea" in text): session.turns.append(("user", text))
        yield session


def codex_sessions(home: Path, cutoff: float) -> Iterator[Session]:
    for path in recent((home / ".codex/sessions").glob("**/*.jsonl"), cutoff):
        session = Session("codex", path); child = False
        for record in records(path):
            payload = record.get("payload") or {}
            if record.get("type") == "session_meta" and "/.work/" in str(payload.get("cwd", "")): child = True; break
            kind = payload.get("type")
            if kind in ("function_call", "custom_tool_call", "local_shell_call"):
                session.loads |= set(SKILL_READ.findall(json.dumps(payload)))
            elif kind == "message":
                text = text_of(payload.get("content"))
                if payload.get("role") == "user" and text and not text.lstrip().startswith("<") and "AGENTS.md" not in text[:300]:
                    session.invoked |= set(DOLLAR.findall(text)); session.turns.append(("user", text))
                elif payload.get("role") == "assistant" and text.strip():
                    session.turns.append(("assistant", text))
        if not child: yield session


def sessions(home: Path, days: float) -> list[Session]:
    cutoff = time.time() - days * 86400
    return [*claude_sessions(home, cutoff), *codex_sessions(home, cutoff)]


def loads_report(all_sessions: list[Session], modes: dict[str, str]) -> dict[str, Any]:
    counts = {h: Counter() for h in ("claude", "codex")}
    totals = Counter(s.harness for s in all_sessions)
    for s in all_sessions:
        for skill in (s.loads | s.invoked) & modes.keys(): counts[s.harness][skill] += 1
    rows: list[dict[str, Any]] = [{"skill": k, "mode": m, "claude": counts["claude"][k], "codex": counts["codex"][k]} for k, m in modes.items()]
    rows.sort(key=lambda r: (r["mode"], -(r["claude"] + r["codex"]), r["skill"]))
    return {"sessions": dict(totals), "skills": rows}


@dataclass(frozen=True)
class Stall:
    path: str
    harness: str
    stop: str
    reply: str


def stalls(session: Session) -> tuple[bool, list[Stall], int]:
    """Return whether authority was granted, the stops after it, and approval nudges."""
    granted = False; found: list[Stall] = []; nudges = 0; last = ""
    for role, text in session.turns:
        if role == "assistant": last = text; continue
        is_nudge = "<command-name>/yea" in text or bool(NUDGE.match(text))
        nudges += is_nudge
        if granted and last and (is_nudge or AUTHORITY.search(text)):
            found.append(Stall(str(session.path), session.harness, " ".join(last.split())[-400:], " ".join(text.split())[:80]))
        granted = granted or bool(AUTHORITY.search(text))
    return granted, found, nudges


def stalls_report(all_sessions: list[Session]) -> dict[str, Any]:
    granted = nudged = 0; stops: list[Stall] = []; per = Counter()
    for s in all_sessions:
        g, found, n = stalls(s)
        granted += g; stops += found; nudged += n > 0; per[s.harness] += 1
    restopped = {s.path for s in stops}
    return {"sessions": dict(per), "sessions_with_nudge": nudged, "authority_granted": granted, "restopped_after_authority": len(restopped), "stops": [asdict(s) for s in stops]}


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="usage.py", description=__doc__.split("\n\n")[0])
    parser.add_argument("command", choices=("loads", "stalls"))
    parser.add_argument("--days", type=float, default=14)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    found = sessions(Path(os.environ.get("HOME", "~")).expanduser(), args.days)
    report = loads_report(found, skill_modes()) if args.command == "loads" else stalls_report(found)
    if args.json: print(json.dumps(report, indent=2)); return 0
    print("sessions:", " ".join(f"{h}={n}" for h, n in sorted(report["sessions"].items())))
    if args.command == "loads":
        for r in report["skills"]: print(f"{r['mode']:8} {r['claude']:4} {r['codex']:4}  {r['skill']}")
    else:
        print(f"with an approval nudge: {report['sessions_with_nudge']}; granted run-until-done: {report['authority_granted']}; stopped again after it: {report['restopped_after_authority']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

#!/usr/bin/env python3
"""Measure skill use, tool use, and approval stalls from local Claude and Codex sessions.

usage.py loads [--days N] [--json]          per-skill sessions that loaded or invoked each skill
usage.py stalls [--days N] [--json]         approval nudges and stops after run-until-done authority
usage.py tools NAME... [--days N] [--json]  CLI invocations and flags per named tool

Counts are per session. Claude subagent transcripts (subdirectories) and Codex
child sessions (cwd under .work/) are excluded, and Codex's skill listing is
ignored: only tool calls that read a SKILL.md count as a load. Tool counts read
only command strings from tool calls, so contract text and repo-name mentions
do not count as invocations.
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
    commands: list[str] = field(default_factory=list)


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
                    if not isinstance(c, dict) or c.get("type") != "tool_use": continue
                    if c.get("name") == "Skill":
                        session.loads.add(str((c.get("input") or {}).get("skill", "")))
                    tool_input = c.get("input")
                    command = tool_input.get("command") if isinstance(tool_input, dict) else None
                    if isinstance(command, str): session.commands.append(command)
                if text := text_of(content).strip(): session.turns.append(("assistant", text))
            elif record.get("type") == "user" and record.get("toolUseResult") is None:
                text = text_of(content)
                session.invoked |= set(SLASH.findall(text))
                if text and not record.get("isMeta") and (not text.startswith("<") or "<command-name>/yea" in text): session.turns.append(("user", text))
        yield session


def command_strings(payload: dict[str, Any]) -> list[str]:
    """Pull shell commands out of the command-shaped Codex tool-call payloads."""
    found: list[str] = []
    arguments = payload.get("arguments")
    if isinstance(arguments, str):
        try: arguments = json.loads(arguments)
        except json.JSONDecodeError: arguments = None
    if isinstance(arguments, dict):
        for key in ("cmd", "command"):
            value = arguments.get(key)
            if isinstance(value, str): found.append(value)
            elif isinstance(value, list): found.extend(x for x in value if isinstance(x, str))
    raw = payload.get("input")
    if isinstance(raw, str):
        found.extend(m.group(1) for m in re.finditer(r'\bcmd\s*:\s*"((?:[^"\\]|\\.)*)"', raw))
    return found


def codex_sessions(home: Path, cutoff: float, include_children: bool = False) -> Iterator[Session]:
    for path in recent((home / ".codex/sessions").glob("**/*.jsonl"), cutoff):
        session = Session("codex", path); child = False
        for record in records(path):
            payload = record.get("payload") or {}
            if record.get("type") == "session_meta" and "/.work/" in str(payload.get("cwd", "")): child = True; continue
            kind = payload.get("type")
            if kind in ("function_call", "custom_tool_call", "local_shell_call"):
                session.loads |= set(SKILL_READ.findall(json.dumps(payload)))
                session.commands.extend(command_strings(payload))
            elif kind == "message":
                text = text_of(payload.get("content"))
                if payload.get("role") == "user" and text and not text.lstrip().startswith("<") and "AGENTS.md" not in text[:300]:
                    session.invoked |= set(DOLLAR.findall(text)); session.turns.append(("user", text))
                elif payload.get("role") == "assistant" and text.strip():
                    session.turns.append(("assistant", text))
        if not child or include_children: yield session


def sessions(home: Path, days: float, include_children: bool = False) -> list[Session]:
    cutoff = time.time() - days * 86400
    return [*claude_sessions(home, cutoff), *codex_sessions(home, cutoff, include_children)]


def loads_report(all_sessions: list[Session], modes: dict[str, str]) -> dict[str, Any]:
    counts = {h: Counter() for h in ("claude", "codex")}
    totals = Counter(s.harness for s in all_sessions)
    for s in all_sessions:
        for skill in (s.loads | s.invoked) & modes.keys(): counts[s.harness][skill] += 1
    rows: list[dict[str, Any]] = [{"skill": k, "mode": m, "claude": counts["claude"][k], "codex": counts["codex"][k]} for k, m in modes.items()]
    rows.sort(key=lambda r: (r["mode"], -(r["claude"] + r["codex"]), r["skill"]))
    return {"sessions": dict(totals), "skills": rows}


def invocations(command: str, name: str) -> list[str]:
    """Segments of a shell command whose executable is exactly NAME."""
    segments: list[str] = []
    for part in re.split(r"[;&|\n]|\$\(", command):
        tokens = part.strip().split()
        while tokens and re.match(r"^[A-Za-z_]\w*=", tokens[0]): tokens.pop(0)
        if tokens and tokens[0] == name: segments.append(part.strip())
    return segments


def flags_of(segments: list[str]) -> Counter[str]:
    flags: Counter[str] = Counter()
    for segment in segments:
        for token in segment.split()[1:]:
            if token.startswith("-") and token not in ("-", "--"): flags[token.split("=", 1)[0]] += 1
    return flags


def tools_report(all_sessions: list[Session], names: list[str]) -> dict[str, Any]:
    totals = Counter(s.harness for s in all_sessions)
    rows: list[dict[str, Any]] = []
    for name in names:
        per = Counter(); seen: set[Path] = set(); flags: Counter[str] = Counter()
        for session in all_sessions:
            segments = [seg for command in session.commands for seg in invocations(command, name)]
            if segments:
                per[session.harness] += len(segments)
                seen.add(session.path)
                flags.update(flags_of(segments))
        rows.append({"tool": name, "claude": per["claude"], "codex": per["codex"],
                     "calls": sum(per.values()), "sessions": len(seen), "flags": dict(flags.most_common())})
    rows.sort(key=lambda row: -row["calls"])
    return {"sessions": dict(totals), "tools": rows}


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
    parser.add_argument("command", choices=("loads", "stalls", "tools"))
    parser.add_argument("names", nargs="*")
    parser.add_argument("--days", type=float, default=14)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "tools" and not args.names: parser.error("tools needs at least one tool name")
    found = sessions(Path(os.environ.get("HOME", "~")).expanduser(), args.days, args.command == "tools")
    if args.command == "loads": report = loads_report(found, skill_modes())
    elif args.command == "stalls": report = stalls_report(found)
    else: report = tools_report(found, args.names)
    if args.json: print(json.dumps(report, indent=2)); return 0
    print("sessions:", " ".join(f"{h}={n}" for h, n in sorted(report["sessions"].items())))
    if args.command == "loads":
        for r in report["skills"]: print(f"{r['mode']:8} {r['claude']:4} {r['codex']:4}  {r['skill']}")
    elif args.command == "stalls":
        print(f"with an approval nudge: {report['sessions_with_nudge']}; granted run-until-done: {report['authority_granted']}; stopped again after it: {report['restopped_after_authority']}")
    else:
        print(f"{'tool':14} {'claude':>6} {'codex':>6} {'calls':>6} {'sessions':>8}  flags")
        for r in report["tools"]:
            flags = " ".join(f"{k}={v}" for k, v in r["flags"].items())
            print(f"{r['tool']:14} {r['claude']:6} {r['codex']:6} {r['calls']:6} {r['sessions']:8}  {flags}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

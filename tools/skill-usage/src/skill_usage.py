#!/usr/bin/env python3
"""Count how each skill is listed and loaded across real Claude, Codex, Muse, Grok, and Pi sessions (read-only)."""
import argparse
import collections
import contextlib
import io
import json
import os
import re
import sys
import tempfile
import time
import unittest
from pathlib import Path
from typing import Any
from urllib.parse import unquote

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "agent-memory" / "src"))
from agent_memory.transcripts import default_roots, is_source_name, normalize
from agent_memory.types import Harness

REPORT_HARNESSES: tuple[Harness, ...] = ("claude", "codex", "muse", "grok", "pi")
LISTING = re.compile(r"^- ([a-z0-9][a-z0-9-]*):", re.M)
SKILL_PATH = re.compile(r"/skills/([a-z0-9][a-z0-9-]*)/SKILL\.md")
READ = SKILL_PATH
SLASH = re.compile(r"<command-name>/([^<]+)</command-name>")
PI_SKILL_BLOCK = re.compile(r"\A<skill name=\"([^\"]+)\" location=\"[^\"]+\">\n.*?\n</skill>(?:\n\n(.+))?\Z", re.S)
GROK_SLASH = re.compile(r"^\s*/([a-z0-9][a-z0-9:_-]*)(?:\s|$)")


def normalized_text(obj, harness: Harness):
    return "\n".join(record["text"] for record in normalize(obj, harness) if record["text"])


def bare(name):
    return name.rsplit(":", 1)[-1]


def clip(text):
    return " ".join(text.split())[:160]


class Usage:
    def __init__(self, want_show):
        self.want_show = want_show
        self.listed = collections.defaultdict(set)
        self.loaded = collections.defaultdict(set)
        self.loads = collections.defaultdict(list)
        self.sessions = collections.defaultdict(set)

    def load(self, skill, harness, session, when, project, how, prompt):
        skill = bare(skill)
        self.loaded[skill].add((harness, session))
        if self.want_show:
            self.loads[skill].append((when, harness, project, how, clip(prompt)))


def scan_claude(root, since, use):
    for path in sorted(Path(root).rglob("*.jsonl")):
        if path.stat().st_mtime < since:
            continue
        prompt = ""
        with open(path, errors="replace") as fh:
            for line in fh:
                listing = '"skill_listing"' in line
                tool = '"Skill"' in line and '"skill"' in line
                slash = "<command-name>/" in line
                user = use.want_show and '"user"' in line
                if not (listing or tool or slash or user):
                    continue
                try:
                    obj = json.loads(line)
                except ValueError:
                    continue
                session = obj.get("sessionId") or path.stem
                use.sessions["claude"].add(session)
                when = str(obj.get("timestamp", ""))[:10]
                project = os.path.basename(obj.get("cwd", "") or "")
                if listing:
                    for name in obj.get("attachment", {}).get("names", []) or []:
                        use.listed[bare(name)].add(("claude", session))
                message = obj.get("message", {}) if isinstance(obj.get("message"), dict) else {}
                content = message.get("content", [])
                if obj.get("type") == "user":
                    text = normalized_text(obj, "claude")
                    match = SLASH.search(text)
                    if match:
                        use.load(match.group(1), "claude", session, when, project, "slash", prompt)
                    elif text and not (isinstance(content, list) and any(b.get("type") == "tool_result" for b in content if isinstance(b, dict))):
                        prompt = text
                if tool and isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "tool_use" and block.get("name") == "Skill":
                            use.load(block.get("input", {}).get("skill", ""), "claude", session, when, project, "tool", prompt)


def scan_codex(root, since, use):
    for path in sorted(Path(root).rglob("rollout-*.jsonl")):
        if path.stat().st_mtime < since:
            continue
        session, project, prompt = path.stem, "", ""
        with open(path, errors="replace") as fh:
            for line in fh:
                meta = '"session_meta"' in line
                listing = "Available skills" in line
                read = "SKILL.md" in line and not listing
                user = use.want_show and '"user"' in line
                if not (meta or listing or read or user):
                    continue
                try:
                    obj = json.loads(line)
                except ValueError:
                    continue
                payload = obj.get("payload", {}) if isinstance(obj.get("payload"), dict) else {}
                when = str(obj.get("timestamp", ""))[:10]
                if obj.get("type") == "session_meta":
                    session = payload.get("parent_thread_id") or payload.get("id") or session
                    project = os.path.basename(payload.get("cwd", "") or "")
                    use.sessions["codex"].add(session)
                elif payload.get("type") == "message" and payload.get("role") == "developer" and listing:
                    section = normalized_text(obj, "codex")
                    for name in LISTING.findall(section[section.find("Available skills"):]):
                        use.listed[name].add(("codex", session))
                elif payload.get("type") == "message" and payload.get("role") == "user":
                    text = normalized_text(obj, "codex")
                    if text and not text.lstrip().startswith("<") and "AGENTS.md instructions" not in text:
                        prompt = text
                elif payload.get("type") in ("function_call", "custom_tool_call") and read:
                    blob = json.dumps(payload.get("arguments", payload.get("input", "")))
                    for name in set(READ.findall(blob)):
                        use.load(name, "codex", session, when, project, "read", prompt)


def muse_date(timestamp):
    if not isinstance(timestamp, (int, float)):
        return ""
    return time.strftime("%Y-%m-%d", time.gmtime(timestamp / 1_000_000))


def scan_muse(root, since, use):
    for path in sorted(Path(root).rglob("session.jsonl")):
        if path.stat().st_mtime < since:
            continue
        session, project, prompt = path.parent.name, "", ""
        use.sessions["muse"].add(session)
        with open(path, errors="replace") as fh:
            for line in fh:
                if '"payload"' not in line and '"payload_type"' not in line:
                    continue
                try:
                    obj = json.loads(line)
                except ValueError:
                    continue
                payload = obj.get("payload", {})
                if not isinstance(payload, dict):
                    continue
                if payload.get("kind") == "metadata":
                    record = payload.get("record", {})
                    if isinstance(record, dict):
                        workspace = record.get("workspace_root", "")
                        if workspace:
                            project = os.path.basename(workspace.rstrip("/"))
                event = payload.get("event", {})
                if not isinstance(event, dict):
                    continue
                when = muse_date(obj.get("recorded_at"))
                kind = event.get("kind")
                if kind == "model_request_configured":
                    for message in event.get("run_context_messages", []):
                        if not isinstance(message, dict):
                            continue
                        text = message.get("text", "")
                        if not isinstance(text, str):
                            continue
                        for name in set(SKILL_PATH.findall(text)):
                            use.listed[bare(name)].add(("muse", session))
                elif kind == "model_user_messages":
                    prompt = normalized_text(obj, "muse")
                elif kind == "skill_read_observed":
                    name = bare(str(event.get("skill_id", "")))
                    if name:
                        use.load(name, "muse", session, when, project, event.get("evidence_kind", "read"), prompt)


def scan_grok(root, since, use, known_skills):
    for path in sorted(Path(root).rglob("chat_history.jsonl")):
        if path.stat().st_mtime < since:
            continue
        session = path.parent.name
        project = os.path.basename(unquote(path.parent.parent.name).rstrip("/"))
        session_date = time.strftime("%Y-%m-%d", time.gmtime(path.stat().st_mtime))
        prompt = ""
        use.sessions["grok"].add(session)
        with open(path, errors="replace") as fh:
            for line in fh:
                if '"user"' not in line and '"tool_calls"' not in line and '"SKILL.md"' not in line:
                    continue
                try:
                    obj = json.loads(line)
                except ValueError:
                    continue
                when = str(obj.get("timestamp", ""))[:10] or session_date
                if obj.get("type") == "user":
                    text = normalized_text(obj, "grok")
                    command = GROK_SLASH.match(text)
                    if command:
                        name = bare(command.group(1))
                        if name in known_skills:
                            use.load(name, "grok", session, when, project, "slash", prompt)
                    elif text:
                        prompt = text
                for tool in obj.get("tool_calls", []) or []:
                    if not isinstance(tool, dict):
                        continue
                    name = tool.get("name", "")
                    arguments = tool.get("arguments", "")
                    if isinstance(arguments, str):
                        try:
                            arguments = json.loads(arguments)
                        except ValueError:
                            pass
                    if name == "read_skill" and isinstance(arguments, dict):
                        skill = bare(str(arguments.get("name", "")))
                        if skill:
                            use.load(skill, "grok", session, when, project, "read", prompt)
                    elif name == "read_file":
                        blob = json.dumps(arguments)
                        for skill in set(SKILL_PATH.findall(blob)):
                            use.load(skill, "grok", session, when, project, "read", prompt)


def scan_pi(root, since, use):
    for path in sorted(Path(root).rglob("*.jsonl")):
        if not is_source_name("pi", path.name) or path.stat().st_mtime < since:
            continue
        session, project, prompt = path.stem, "", ""
        with open(path, errors="replace") as fh:
            for line in fh:
                header = line.startswith('{"type":"session"')
                listing = '"role":"system"' in line and "SKILL.md" in line
                slash = '"role":"user"' in line and "<skill name=" in line
                read = '"toolCall"' in line and "SKILL.md" in line
                user = use.want_show and '"role":"user"' in line
                if not (header or listing or slash or read or user):
                    continue
                try:
                    obj = json.loads(line)
                except ValueError:
                    continue
                if obj.get("type") == "session":
                    session = obj.get("id") or session
                    project = os.path.basename(str(obj.get("cwd") or "").rstrip("/"))
                    use.sessions["pi"].add(session)
                    continue
                message = obj.get("message") if isinstance(obj.get("message"), dict) else {}
                when = str(obj.get("timestamp", ""))[:10]
                role = message.get("role")
                if role == "system":
                    sections = message.get("sections")
                    listing_text = str(sections.get("skills", "")) if isinstance(sections, dict) else ""
                    for name in SKILL_PATH.findall(listing_text):
                        use.listed[bare(name)].add(("pi", session))
                elif role == "user":
                    text = normalized_text(obj, "pi")
                    block = PI_SKILL_BLOCK.match(text)
                    if block:
                        use.load(block.group(1), "pi", session, when, project, "slash", block.group(2) or prompt)
                    elif text:
                        prompt = text
                elif role == "assistant" and read:
                    for part in message.get("content") or []:
                        if isinstance(part, dict) and part.get("type") == "toolCall" and part.get("name") == "read":
                            for name in set(SKILL_PATH.findall(json.dumps(part.get("arguments", {})))):
                                use.load(name, "pi", session, when, project, "read", prompt)


def kinds(skills):
    out = {}
    for skill in sorted(Path(skills).glob("*/SKILL.md")):
        head = skill.read_text(errors="replace").split("---")[1] if skill.read_text(errors="replace").startswith("---") else ""
        out[skill.parent.name] = "explicit" if re.search(r"^disable-model-invocation:\s*true", head, re.M) else "auto"
    return out


def report(use, skill_kinds, args):
    names = sorted(set(skill_kinds) | (set(use.listed) if args.all else set(use.listed) & set(use.loaded)))
    rows: list[dict[str, Any]] = []
    for name in names:
        row: dict[str, Any] = {"skill": name, "kind": skill_kinds.get(name, "other")}
        for harness in REPORT_HARNESSES:
            row[f"listed_{harness}"] = None if harness == "grok" else sum(1 for h, _ in use.listed[name] if h == harness)
            row[f"loaded_{harness}"] = sum(1 for h, _ in use.loaded[name] if h == harness)
        row["last_loaded"] = max((w for w, *_ in use.loads[name]), default="")
        rows.append(row)
    rows.sort(key=lambda r: (-sum(r[f"loaded_{harness}"] for harness in REPORT_HARNESSES), r["skill"]))
    totals = {harness: len(use.sessions[harness]) for harness in REPORT_HARNESSES}
    if args.json:
        print(json.dumps({"days": args.days, "sessions": totals, "skills": rows}))
        return
    print("window %s days; sessions: %s" % (args.days, ", ".join(f"{harness} {totals[harness]}" for harness in REPORT_HARNESSES)))
    print(f"{'skill':46} {'kind':8} {'listed c/x/m/g/p':>17} {'loaded c/x/m/g/p':>17}")
    for r in rows:
        listed = ["—" if r[f"listed_{harness}"] is None else str(r[f"listed_{harness}"]) for harness in REPORT_HARNESSES]
        loaded = [str(r[f"loaded_{harness}"]) for harness in REPORT_HARNESSES]
        print(f"{r['skill']:46} {r['kind']:8} {'/'.join(listed):>17} {'/'.join(loaded):>17}")
    never = [r["skill"] for r in rows if r["kind"] == "auto" and sum(r[f"loaded_{harness}"] for harness in REPORT_HARNESSES) == 0]
    print("auto-triggered and never loaded: " + (", ".join(never) or "none"))


def run(args):
    since = time.time() - args.days * 86400
    use = Usage(bool(args.show))
    if os.path.isdir(args.claude):
        scan_claude(args.claude, since, use)
    if os.path.isdir(args.codex):
        scan_codex(args.codex, since, use)
    if os.path.isdir(args.muse):
        scan_muse(args.muse, since, use)
    if os.path.isdir(args.grok):
        scan_grok(args.grok, since, use, set(kinds(args.skills)))
    if os.path.isdir(args.pi):
        scan_pi(args.pi, since, use)
    if args.show:
        for when, harness, project, how, prompt in sorted(use.loads.get(args.show, [])):
            print(f"{when}\t{harness}\t{project}\t{how}\t{prompt}")
        return 0
    report(use, kinds(args.skills), args)
    return 0


class SelfTest(unittest.TestCase):
    def fixture(self, root):
        claude, codex, skills = Path(root, "claude"), Path(root, "codex"), Path(root, "skills")
        for name, flag in (("a", ""), ("b", "disable-model-invocation: true\n"), ("c", "")):
            (skills / name).mkdir(parents=True)
            (skills / name / "SKILL.md").write_text(f"---\nname: {name}\n{flag}---\n")
        claude.mkdir()
        lines = [
            {"type": "attachment", "sessionId": "s1", "attachment": {"type": "skill_listing", "names": ["a", "c"]}},
            {"type": "user", "sessionId": "s1", "timestamp": "2026-10-13T00:00:00Z", "cwd": "/x/proj", "message": {"role": "user", "content": "tidy the comments"}},
            {"type": "assistant", "sessionId": "s1", "timestamp": "2026-10-13T00:00:01Z", "cwd": "/x/proj", "message": {"role": "assistant", "content": [{"type": "tool_use", "name": "Skill", "input": {"skill": "a"}}]}},
            {"type": "user", "sessionId": "s1", "timestamp": "2026-10-13T00:00:02Z", "cwd": "/x/proj", "message": {"role": "user", "content": "<command-name>/b</command-name>"}},
        ]
        (claude / "s1.jsonl").write_text("\n".join(json.dumps(x) for x in lines) + "\n")
        codex.mkdir()
        rollout = [
            {"type": "session_meta", "payload": {"id": "x1", "cwd": "/x/other"}},
            {"type": "response_item", "payload": {"type": "message", "role": "developer", "content": [{"type": "input_text", "text": "Available skills\n- a: does a\n- c: does c\n"}]}},
            {"type": "response_item", "timestamp": "2026-10-13T01:00:00Z", "payload": {"type": "function_call", "arguments": json.dumps({"cmd": "cat /h/.agents/skills/a/SKILL.md"})}},
        ]
        (codex / "rollout-2026-10-13T01-x1.jsonl").write_text("\n".join(json.dumps(x) for x in rollout) + "\n")
        return claude, codex, skills

    def test_counts_listings_and_loads_per_harness(self):
        with tempfile.TemporaryDirectory() as root:
            claude, codex, skills = self.fixture(root)
            use = Usage(False)
            scan_claude(claude, 0, use)
            scan_codex(codex, 0, use)
            self.assertEqual({k: len(v) for k, v in use.sessions.items()}, {"claude": 1, "codex": 1})
            self.assertEqual({(h, s) for h, s in use.loaded["a"]}, {("claude", "s1"), ("codex", "x1")})
            self.assertEqual(use.loaded["b"], {("claude", "s1")})
            self.assertEqual(use.loaded["c"], set())
            self.assertEqual(use.listed["c"], {("claude", "s1"), ("codex", "x1")})
            self.assertEqual(kinds(skills), {"a": "auto", "b": "explicit", "c": "auto"})

    def test_show_pairs_a_load_with_the_preceding_prompt(self):
        with tempfile.TemporaryDirectory() as root:
            claude, _, _ = self.fixture(root)
            use = Usage(True)
            scan_claude(claude, 0, use)
            self.assertEqual(use.loads["a"], [("2026-10-13", "claude", "proj", "tool", "tidy the comments")])

    def test_muse_counts_context_listings_and_skill_reads(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root, "2026", "10", "14", "m1", "session.jsonl")
            path.parent.mkdir(parents=True)
            records = [
                {"payload": {"kind": "metadata", "record": {"workspace_root": "/x/project"}}},
                {
                    "recorded_at": 1792018406398112,
                    "stream": {"id": "m1"},
                    "payload": {
                        "event": {
                            "kind": "model_request_configured",
                            "run_context_messages": [
                                {"role": "developer", "text": "/x/.agents/skills/a/SKILL.md\n/x/.agents/skills/c/SKILL.md"}
                            ],
                        }
                    },
                },
                {"recorded_at": 1792018406398112, "payload": {"event": {"kind": "model_user_messages", "messages": ["fix the parser"]}}},
                {
                    "recorded_at": 1792018406398112,
                    "payload": {
                        "event": {
                            "kind": "skill_read_observed",
                            "skill_id": "bundled:a",
                            "evidence_kind": "read_skill_tool",
                        }
                    },
                },
            ]
            path.write_text("\n".join(json.dumps(record) for record in records) + "\n")
            use = Usage(True)
            scan_muse(root, 0, use)
            self.assertEqual(use.sessions["muse"], {"m1"})
            self.assertEqual(use.listed["a"], {("muse", "m1")})
            self.assertEqual(use.listed["c"], {("muse", "m1")})
            self.assertEqual(use.loaded["a"], {("muse", "m1")})
            self.assertEqual(use.loads["a"], [("2026-10-14", "muse", "project", "read_skill_tool", "fix the parser")])

    def test_grok_counts_file_reads_and_explicit_slash_loads(self):
        with tempfile.TemporaryDirectory() as root:
            grok = Path(root, "grok")
            history = grok / "%2Fx%2Fproject" / "g1" / "chat_history.jsonl"
            history.parent.mkdir(parents=True)
            records = [
                {"type": "user", "timestamp": "2026-10-13T00:00:00Z", "content": [{"type": "text", "text": "check this code"}]},
                {
                    "type": "assistant",
                    "timestamp": "2026-10-13T00:00:01Z",
                    "tool_calls": [
                        {"name": "read_file", "arguments": json.dumps({"path": "/home/user/.agents/skills/a/SKILL.md"})}
                    ],
                },
                {"type": "user", "timestamp": "2026-10-13T00:00:02Z", "content": [{"type": "text", "text": "/b explain the rule"}]},
            ]
            history.write_text("\n".join(json.dumps(record) for record in records) + "\n")
            use = Usage(True)
            scan_grok(grok, 0, use, {"a", "b"})
            self.assertEqual(use.sessions["grok"], {"g1"})
            self.assertEqual(use.loaded["a"], {("grok", "g1")})
            self.assertEqual(use.loaded["b"], {("grok", "g1")})
            self.assertEqual(use.loads["a"], [("2026-10-13", "grok", "project", "read", "check this code")])
            self.assertEqual(use.loads["b"], [("2026-10-13", "grok", "project", "slash", "check this code")])

    def test_pi_counts_listings_slash_blocks_and_skill_file_reads(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root, "--x-project--", "2026-10-14T00-00-00-000Z_p1.jsonl")
            path.parent.mkdir(parents=True)
            skills = "<available_skills>\n<skill>\n<location>/h/.agents/skills/a/SKILL.md</location>\n</skill>\n<skill>\n<location>/h/.agents/skills/c/SKILL.md</location>\n</skill>\n</available_skills>"
            block = '<skill name="b" location="/h/.agents/skills/b/SKILL.md">\nReferences are relative to /h.\n\nbody\n</skill>\n\nexplain the rule'
            records = [
                {"type": "session", "version": 3, "id": "p1", "timestamp": "2026-10-14T00:00:00.000Z", "cwd": "/x/project"},
                {"type": "message", "id": "s", "parentId": None, "timestamp": "2026-10-14T00:00:01.000Z", "message": {"role": "system", "content": "", "sections": {"skills": skills}}},
                {"type": "message", "id": "u", "parentId": "s", "timestamp": "2026-10-14T00:00:02.000Z", "message": {"role": "user", "content": "fix the parser"}},
                {"type": "message", "id": "a", "parentId": "u", "timestamp": "2026-10-14T00:00:03.000Z", "message": {"role": "assistant", "content": [
                    {"type": "toolCall", "id": "t1", "name": "read", "arguments": {"path": "/h/.agents/skills/a/SKILL.md"}}]}},
                {"type": "message", "id": "u2", "parentId": "a", "timestamp": "2026-10-14T00:00:04.000Z", "message": {"role": "user", "content": block}},
            ]
            path.write_text("\n".join(json.dumps(record, separators=(",", ":")) for record in records) + "\n")
            Path(root, "--x-project--", "events.jsonl").write_text('{"type":"session","id":"not-a-session"}\n')
            use = Usage(True)
            scan_pi(root, 0, use)
            self.assertEqual(use.sessions["pi"], {"p1"})
            self.assertEqual(use.listed["a"], {("pi", "p1")})
            self.assertEqual(use.listed["c"], {("pi", "p1")})
            self.assertEqual(use.loaded["a"], {("pi", "p1")})
            self.assertEqual(use.loaded["b"], {("pi", "p1")})
            self.assertEqual(use.loads["a"], [("2026-10-14", "pi", "project", "read", "fix the parser")])
            self.assertEqual(use.loads["b"], [("2026-10-14", "pi", "project", "slash", "explain the rule")])

    def test_grok_listing_count_is_unknown_without_saved_catalog(self):
        with tempfile.TemporaryDirectory() as root:
            _, _, skills = self.fixture(root)
            use = Usage(False)
            args = argparse.Namespace(all=False, days=60, json=True)
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                report(use, kinds(skills), args)
            result = json.loads(output.getvalue())
            self.assertIsNone(result["skills"][0]["listed_grok"])
            self.assertEqual(result["sessions"], {"claude": 0, "codex": 0, "muse": 0, "grok": 0, "pi": 0})


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="skill-usage",
        description=__doc__,
        epilog="Examples:\n"
        "  skill-usage\n"
        "  skill-usage --days 7\n"
        "  skill-usage --show do\n"
        "  skill-usage --json\n"
        "  skill-usage selftest\n"
        "\n"
        "Reads session transcripts through the agent-memory adapters; it never\n"
        "writes. Full context: tools/agent-memory/README.md.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("command", nargs="?", choices=("report", "selftest"), default="report", help="report (default) or embedded selftest")
    parser.add_argument("--days", type=int, default=60, help="only sessions touched in the last N days (default %(default)s)")
    parser.add_argument("--skills", default=os.path.expanduser("~/.agents/skills"), help="shared skills directory (default %(default)s)")
    roots = default_roots()
    parser.add_argument("--claude", default=str(roots["claude"][0]), help="Claude transcript root")
    parser.add_argument("--codex", default=str(roots["codex"][0]), help="Codex transcript root")
    parser.add_argument("--muse", default=str(roots["muse"][0]), help="Muse transcript root")
    parser.add_argument("--grok", default=str(roots["grok"][0]), help="Grok transcript root")
    parser.add_argument("--pi", default=str(roots["pi"][0]), help="Pi session root")
    parser.add_argument("--show", metavar="SKILL", help="list each load of SKILL with the prompt before it")
    parser.add_argument("--all", action="store_true", help="also list skills that are not in --skills and never loaded")
    parser.add_argument("--json", action="store_true", help="emit the report as JSON")
    args = parser.parse_args(argv)
    if args.command == "selftest":
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(SelfTest)
        return 0 if unittest.TextTestRunner(verbosity=1).run(suite).wasSuccessful() else 1
    return run(args)


if __name__ == "__main__":
    sys.exit(main())

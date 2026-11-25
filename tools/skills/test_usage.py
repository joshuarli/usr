#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

Record = dict[str, Any]

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools/skills/usage.py"


def jsonl(path: Path, *records: Record) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in records))


def user(text: str) -> Record:
    return {"type": "user", "message": {"role": "user", "content": text}}


def assistant(text: str = "", skill: str | None = None) -> Record:
    content: list[Record] = [{"type": "text", "text": text}] if text else []
    if skill: content.append({"type": "tool_use", "name": "Skill", "input": {"skill": skill}})
    return {"type": "assistant", "message": {"role": "assistant", "content": content}}


def codex(cwd: str, *items: Record) -> list[Record]:
    return [{"type": "session_meta", "payload": {"cwd": cwd}}, *({"type": "response_item", "payload": i} for i in items)]


def codex_user(text: str) -> Record:
    return {"type": "message", "role": "user", "content": [{"type": "input_text", "text": text}]}


def bash(command: str) -> Record:
    return {"type": "tool_use", "name": "Bash", "input": {"command": command}}


class UsageTest(unittest.TestCase):
    def setUp(self) -> None:
        scratch = ROOT / ".work/tmp"; scratch.mkdir(parents=True, exist_ok=True)
        self.home = Path(tempfile.mkdtemp(dir=scratch, prefix="usage-"))
        listing = codex_user("<skills_instructions> skills/do/SKILL.md skills/review/SKILL.md </skills_instructions>")
        rename = "fastermod -S old new notes.md --apply; sed -i '' 's/a/b/' one.md; for d in fastermod sed; do echo $d; done"
        mixed = assistant("Plan ready.", skill="do")
        mixed["message"]["content"].append(bash(rename))
        jsonl(self.home / ".claude/projects/p/a.jsonl",
              user("Fix it. I'm going to sleep, don't stop until it is done."),
              mixed,
              assistant("**Needs you:** whether I should keep going."),
              user("<command-message>yea</command-message>\n<command-name>/yea</command-name>"),
              assistant("Done."))
        jsonl(self.home / ".claude/projects/p/a/subagents/agent-1.jsonl", assistant(skill="do"), user("<command-name>/yea</command-name>"))
        jsonl(self.home / ".claude/projects/p/b.jsonl", user("What does this do?"), assistant("It parses."), user("continue"))
        jsonl(self.home / ".codex/sessions/2026/11/16/rollout-1.jsonl", *codex("/r", listing, codex_user("$sleep then fix"),
              {"type": "function_call", "name": "exec", "arguments": json.dumps({"cmd": "cat ~/.agents/skills/review/SKILL.md"})},
              {"type": "custom_tool_call", "name": "exec", "input": 'const r=await tools.exec_command({cmd:"fastermod --literal \'a\' \'b\' t.py --apply",workdir:"/r"})'},
              {"type": "function_call", "name": "exec", "arguments": json.dumps({"cmd": "sed -i '' 's/c/d/' t.txt"})}))
        jsonl(self.home / ".codex/sessions/2026/11/16/rollout-2.jsonl", *codex("/r/.work/wt/lane", listing,
              {"type": "function_call", "name": "exec", "arguments": json.dumps({"cmd": "cat skills/do/SKILL.md"})},
              {"type": "function_call", "name": "exec", "arguments": json.dumps({"cmd": "fastermod -S old new child.md --apply"})}))

    def tearDown(self) -> None:
        shutil.rmtree(self.home)

    def run_tool(self, command: str) -> Record:
        result = subprocess.run([sys.executable, "-I", str(TOOL), command, "--json"], env={**os.environ, "HOME": str(self.home)}, capture_output=True, text=True, check=True)
        return json.loads(result.stdout)

    def test_loads_count_parent_sessions_and_ignore_codex_listing(self) -> None:
        report = self.run_tool("loads")
        self.assertEqual(report["sessions"], {"claude": 2, "codex": 1})
        rows = {r["skill"]: r for r in report["skills"]}
        self.assertEqual((rows["do"]["claude"], rows["do"]["codex"]), (1, 0))
        self.assertEqual((rows["review"]["claude"], rows["review"]["codex"]), (0, 1))
        self.assertEqual((rows["yea"]["claude"], rows["yea"]["mode"]), (1, "explicit"))
        self.assertEqual(rows["sleep"]["codex"], 1)

    def test_stalls_report_stops_after_granted_authority(self) -> None:
        report = self.run_tool("stalls")
        self.assertEqual((report["authority_granted"], report["restopped_after_authority"], report["sessions_with_nudge"]), (1, 1, 2))
        [stop] = report["stops"]
        self.assertIn("whether I should keep going", stop["stop"])
        self.assertTrue(stop["path"].endswith("a.jsonl"))

    def test_tools_counts_invocations_ignores_mentions_and_collects_flags(self) -> None:
        result = subprocess.run([sys.executable, "-I", str(TOOL), "tools", "fastermod", "sed", "--json"],
                                env={**os.environ, "HOME": str(self.home)}, capture_output=True, text=True, check=True)
        report = json.loads(result.stdout)
        rows = {r["tool"]: r for r in report["tools"]}
        self.assertEqual((rows["fastermod"]["claude"], rows["fastermod"]["codex"]), (1, 2))
        self.assertEqual((rows["sed"]["claude"], rows["sed"]["codex"]), (1, 1))
        self.assertEqual(rows["fastermod"]["calls"], 3)
        self.assertEqual(rows["fastermod"]["sessions"], 3)
        self.assertEqual(rows["fastermod"]["flags"], {"-S": 2, "--apply": 3, "--literal": 1})
        self.assertEqual(self.run_tool("loads")["sessions"], {"claude": 2, "codex": 1})


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CLI = ROOT / "dotfiles/base/.local/bin/standards"
STANDARDS = ROOT / "dotfiles/base/.agents/standards"
FIXTURE_STANDARDS = ("cli-interrupt", "github-actions", "shell")
sys.path.insert(0, str(Path(__file__).resolve().parent))
import standards  # noqa: E402

VALID = '''+++
name = "{name}"
summary = "s"
{triggers}
[examples]
match = {match}
skip = {skip}
+++
# T

## Code

- rule
'''


def run(*args: str, cwd: Path, directory: Path = STANDARDS) -> subprocess.CompletedProcess[str]:
    return subprocess.run((sys.executable, "-I", str(CLI), "--dir", str(directory), *args), cwd=cwd, capture_output=True, text=True)


def selected(result: subprocess.CompletedProcess[str]) -> dict[str, list[dict[str, Any]]]:
    assert result.returncode == 0, result.stderr
    return {item["name"]: item["reasons"] for item in json.loads(result.stdout)}


def scratch() -> tempfile.TemporaryDirectory[str]:
    base = ROOT / ".work/tmp"
    base.mkdir(parents=True, exist_ok=True)
    return tempfile.TemporaryDirectory(dir=base)


class Repo:
    def __init__(self, root: Path):
        self.root = root
        root.mkdir(exist_ok=True)
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "user.name", "Test")

    def git(self, *args: str) -> None:
        subprocess.run(("git", *args), cwd=self.root, check=True, capture_output=True)

    def write(self, name: str, text: str) -> None:
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def commit(self) -> None:
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "c")


class PathPatternTests(unittest.TestCase):
    def test_gitignore_semantics(self):
        cases = [
            ("*.sh", "a/b/x.sh", True), ("*.sh", "x.shx", False),
            ("/build.sh", "build.sh", True), ("/build.sh", "a/build.sh", False),
            ("docs/*.md", "docs/a.md", True), ("docs/*.md", "docs/x/a.md", False), ("docs/*.md", "a/docs/a.md", False),
            ("**/src/main.rs", "src/main.rs", True), ("**/src/main.rs", "a/b/src/main.rs", True),
            ("bin/", "x/bin/tool", True), ("bin/", "bin", False),
            ("/.github/workflows/**", ".github/workflows/a/b.yml", True), ("/.github/workflows/**", "s/.github/workflows/a.yml", False),
            ("a/**/b", "a/b", True), ("a/**/b", "a/x/y/b", True),
            ("[!a]x", "bx", True), ("[!a]x", "ax", False), ("?.py", "a.py", True), ("?.py", "ab.py", False),
            ("Makefile", "deep/pkg/Makefile", True), ("\\*.md", "*.md", True), ("\\*.md", "a.md", False),
        ]
        for pattern, path, expected in cases:
            with self.subTest(pattern=pattern, path=path):
                self.assertEqual(expected, standards.paths_match([standards.compile_path(pattern)], path)[0])

    def test_last_matching_pattern_wins(self):
        patterns = [standards.compile_path(p) for p in ("*", "!*.md", "keep.md")]
        self.assertEqual((False, "!*.md"), standards.paths_match(patterns, "docs/a.md"))
        self.assertEqual((True, "keep.md"), standards.paths_match(patterns, "docs/keep.md"))
        self.assertEqual((True, "*"), standards.paths_match(patterns, "src/a.py"))


class SelectTests(unittest.TestCase):
    def setUp(self):
        self.tmp = scratch()
        self.standards = Path(self.tmp.name) / "standards"
        self.standards.mkdir()
        for name in FIXTURE_STANDARDS:
            shutil.copy(STANDARDS / f"{name}.md", self.standards)
        self.repo = Repo(Path(self.tmp.name) / "repo")
        self.repo.write("README.md", "hello\n")
        self.repo.write("tool", "#!/bin/sh\nset -eu\necho one\n")
        self.repo.write("app.py", "def f():\n    return 1\n")
        self.repo.commit()

    def tearDown(self):
        self.tmp.cleanup()

    def select(self, *args: str) -> dict[str, list[dict[str, Any]]]:
        return selected(self.cli("select", "--json", *args))

    def cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        return run(*args, cwd=self.repo.root, directory=self.standards)

    def test_clean_tree_and_prose_edits_select_nothing(self):
        self.assertEqual({}, self.select())
        self.repo.write("README.md", "hello there\n")
        self.assertEqual({}, self.select())

    def test_edit_below_an_unchanged_shebang_selects_shell(self):
        self.repo.write("tool", "#!/bin/sh\nset -eu\necho two\n")
        result = self.select()
        self.assertEqual(["shell"], list(result))
        self.assertEqual([("tool", ["shebang"])], [(r["file"], [c["kind"] for c in r["conditions"]]) for r in result["shell"]])

    def test_only_added_lines_trigger_content_rules(self):
        self.repo.write("app.py", "import argparse\ndef f():\n    return 1\n")
        self.repo.commit()
        self.repo.write("app.py", "def f():\n    return 1\n")
        self.assertEqual({}, self.select())
        self.repo.write("app.py", "import signal\nsignal.signal(signal.SIGINT, h)\n")
        self.assertEqual(["cli-interrupt"], list(self.select()))

    def test_trigger_conditions_combine(self):
        self.repo.write("README.md", "Press Ctrl-C to send SIGINT.\n")
        self.assertEqual({}, self.select())

    def test_quoted_paths_and_plus_prefixed_content_keep_their_added_lines(self):
        for name in ("a b.py", "é.py"):
            self.repo.write(name, "x\n")
        self.repo.commit()
        self.repo.write("a b.py", "x\nimport argparse\n")
        self.assertEqual(["a b.py"], [r["file"] for r in self.select()["cli-interrupt"]])
        self.repo.write("a b.py", "x\n")
        self.repo.write("é.py", "x\n++ import argparse\n")
        self.assertEqual(["é.py"], [r["file"] for r in self.select()["cli-interrupt"]])

    def test_untracked_files_select_by_path(self):
        self.repo.write(".github/workflows/ci.yml", "on: push\n")
        self.repo.write("pkg/Makefile", "all:\n\ttrue\n")
        self.assertEqual({"github-actions", "shell"}, set(self.select()))

    def test_deleted_files_select_nothing(self):
        self.repo.write("build.sh", "#!/bin/sh\n")
        self.repo.commit()
        (self.repo.root / "build.sh").unlink()
        self.assertEqual({}, self.select())

    def test_base_includes_committed_changes(self):
        self.repo.write("build.sh", "#!/bin/sh\n")
        self.repo.commit()
        self.assertEqual({}, self.select())
        self.assertEqual(["shell"], list(self.select("--base", "HEAD~1")))

    def test_tree_matches_every_file_in_full(self):
        self.repo.write("cli.py", "import argparse\n")
        self.repo.commit()
        self.assertEqual({}, self.select())
        tree = self.select("--tree")
        self.assertEqual({"cli-interrupt", "shell"}, set(tree))
        self.repo.write("more.sh", "#!/bin/sh\n")
        self.assertEqual([1, 1], [len(reasons) for reasons in self.select("--tree").values()])
        self.assertEqual(2, self.cli("select", "--tree", "tool").returncode)

    def test_explicit_files_match_whole_content(self):
        self.assertEqual(["shell"], list(self.select("tool")))
        self.assertEqual({}, self.select("README.md"))
        missing = self.cli("select", "nope")
        self.assertEqual(2, missing.returncode)
        self.assertIn("nope: not a file", missing.stderr)

    def test_text_output_names_standard_file_and_reason(self):
        self.repo.write("tool", "#!/bin/sh\necho changed\n")
        result = self.cli("select")
        self.assertEqual(0, result.returncode, result.stderr)
        name, path, reason = result.stdout.rstrip("\n").split("\t")
        self.assertEqual(("shell", str(self.standards / "shell.md")), (name, path))
        self.assertTrue(reason.startswith("tool: trigger 2: shebang "), reason)

    def test_explain_shows_each_trigger_verdict(self):
        self.repo.write("notes.md", "SIGINT\n")
        result = self.cli("explain", "notes.md")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("  cli-interrupt trigger 2: misses (paths no match, content \\bSIG(INT|TERM)\\b)\n", result.stdout)
        self.assertIn("  shell trigger 1: misses (paths no match)\n", result.stdout)


class HookTests(unittest.TestCase):
    def setUp(self):
        self.tmp = scratch()
        root = Path(self.tmp.name)
        self.standards = root / "standards"
        self.standards.mkdir()
        for name in FIXTURE_STANDARDS:
            shutil.copy(STANDARDS / f"{name}.md", self.standards)
        self.repo = Repo(root / "repo")
        self.repo.write("tool.sh", "#!/bin/sh\n")
        self.repo.write("README.md", "hi\n")
        self.env = {**os.environ, "XDG_CACHE_HOME": str(root / "cache")}

    def tearDown(self):
        self.tmp.cleanup()

    def hook(self, event: object) -> subprocess.CompletedProcess[str]:
        data = event if isinstance(event, str) else json.dumps(event)
        return subprocess.run((sys.executable, "-I", str(CLI), "--dir", str(self.standards), "hook"),
                              input=data, capture_output=True, text=True, env=self.env)

    def event(self, session: str, tool_input: object) -> dict[str, object]:
        return {"hook_event_name": "PostToolUse", "session_id": session, "cwd": str(self.repo.root),
                "tool_name": "Edit", "tool_input": tool_input}

    def context(self, result: subprocess.CompletedProcess[str]) -> str:
        self.assertEqual(0, result.returncode, result.stderr)
        if not result.stdout:
            return ""
        context = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
        assert isinstance(context, str)
        return context

    def test_announces_each_standard_once_per_session(self):
        first = self.context(self.hook(self.event("s1", {"file_path": str(self.repo.root / "tool.sh")})))
        self.assertIn("`shell`", first)
        self.assertIn("for tool.sh", first)
        self.assertEqual("", self.context(self.hook(self.event("s1", {"file_path": "tool.sh"}))))
        self.assertIn("`shell`", self.context(self.hook(self.event("s2", {"file_path": "tool.sh"}))))

    def test_reads_apply_patch_file_headers(self):
        patch = "*** Begin Patch\n*** Update File: tool.sh\n@@\n-a\n+b\n*** End Patch\n"
        self.assertIn("`shell`", self.context(self.hook(self.event("s3", {"command": patch}))))

    def test_untriggered_missing_and_invalid_input_stay_silent(self):
        for event in (self.event("s4", {"file_path": "README.md"}), self.event("s4", {"file_path": "missing.sh"}),
                      "not json", {"hook_event_name": "Stop", "session_id": "s4"}, self.event("", {"file_path": "tool.sh"})):
            with self.subTest(event=event):
                self.assertEqual("", self.context(self.hook(event)))


class HelpTests(unittest.TestCase):
    def test_bare_invocation_prints_the_complete_help(self):
        bare = subprocess.run((sys.executable, "-I", str(CLI)), capture_output=True, text=True)
        full = subprocess.run((sys.executable, "-I", str(CLI), "-h"), capture_output=True, text=True)
        self.assertEqual((0, 0), (bare.returncode, full.returncode))
        self.assertEqual(full.stdout, bare.stdout)
        for name in standards.EXAMPLES:
            self.assertIn(f"\nstandards {name} [-h]", full.stdout)
        self.assertTrue(full.stdout.rstrip().endswith(standards.OWNED_FOOTER))
        self.assertEqual(1, full.stdout.count("Maintained by Joshua Li: https://github.com/joshuarli/usr"))

    def test_every_example_parses(self):
        cli = standards.parser()
        for name, examples in standards.EXAMPLES.items():
            for example in examples:
                with self.subTest(example=example):
                    argv = example.split("<")[0].split()[1:]
                    self.assertEqual(name, cli.parse_args(argv).command)


class InterruptTests(unittest.TestCase):
    def test_interrupt_dies_by_sigint_after_notice(self):
        with scratch() as tmp:
            script = Path(tmp) / "interrupt.py"
            script.write_text(
                "import sys\n"
                f"sys.path.insert(0, {str(Path(standards.__file__).parent)!r})\n"
                "import standards\n"
                "def interrupted(directory):\n"
                "    raise KeyboardInterrupt\n"
                "standards.load = interrupted\n"
                "sys.exit(standards.main(['list']))\n")
            result = subprocess.run((sys.executable, "-I", str(script)), capture_output=True, text=True)
        self.assertEqual(-signal.SIGINT, result.returncode, result.stderr)
        self.assertEqual("standards: interrupted\n", result.stderr)
        self.assertEqual("", result.stdout)


class CheckTests(unittest.TestCase):
    def setUp(self):
        self.tmp = scratch()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def check(self, name: str, text: str) -> subprocess.CompletedProcess[str]:
        for old in self.dir.glob("*.md"):
            old.unlink()
        (self.dir / f"{name}.md").write_text(text)
        return run("check", cwd=self.dir, directory=self.dir)

    def standard(self, name: str = "t", triggers: str = '[[trigger]]\npaths = ["*.x"]\n', match: str = '["a.x"]', skip: str = '["a.y"]') -> str:
        return VALID.format(name=name, triggers=triggers, match=match, skip=skip)

    def test_repository_standards_and_examples_are_valid(self):
        result = run("check", cwd=ROOT)
        self.assertEqual(0, result.returncode, result.stderr)

    def test_valid_fixture_passes(self):
        result = self.check("t", self.standard())
        self.assertEqual(0, result.returncode, result.stderr)

    def test_invalid_standards_fail_closed(self):
        cases = {
            "yaml frontmatter": ("t", "---\nname: t\n---\n", "missing +++ TOML frontmatter"),
            "bad toml": ("t", "+++\nname = \n+++\n", "invalid TOML"),
            "name mismatch": ("t", self.standard(name="other"), "name must equal"),
            "unknown key": ("t", self.standard(triggers='[[trigger]]\nglob = ["x"]\n'), "unknown keys"),
            "no triggers": ("t", self.standard(triggers=""), "at least one [[trigger]]"),
            "empty trigger": ("t", self.standard(triggers="[[trigger]]\n"), "needs at least one of"),
            "only negations": ("t", self.standard(triggers='[[trigger]]\npaths = ["!*.md"]\n'), "positive pattern"),
            "bad regex": ("t", self.standard(triggers="[[trigger]]\ncontent = ['(']\n"), "invalid trigger 1 content regex"),
            "no examples": ("t", self.standard(match="[]"), "non-empty match list"),
            "no code section": ("t", self.standard().replace("## Code", "## Rules"), "'## Code' section"),
            "example should match": ("t", self.standard(match='["a.y"]'), "example 'a.y' should match but did not match"),
            "example should skip": ("t", self.standard(skip='["b.x"]'), "example 'b.x' should skip but matched"),
        }
        for label, (name, text, message) in cases.items():
            with self.subTest(label):
                result = self.check(name, text)
                self.assertEqual(1, result.returncode, label)
                self.assertIn(message, result.stderr)

    def test_select_with_invalid_standard_is_an_operational_error(self):
        (self.dir / "x.md").write_text("# no frontmatter\n")
        result = run("select", "--json", str(self.dir / "x.md"), cwd=self.dir, directory=self.dir)
        self.assertEqual(2, result.returncode)
        self.assertEqual("", result.stdout)


if __name__ == "__main__":
    unittest.main()

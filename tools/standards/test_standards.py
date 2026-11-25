#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CLI = ROOT / "dotfiles/base/.local/bin/standards"
STANDARDS = ROOT / "dotfiles/base/.agents/standards"


def run(*args: str, cwd: Path, directory: Path = STANDARDS) -> subprocess.CompletedProcess[str]:
    return subprocess.run((sys.executable, "-I", str(CLI), "--dir", str(directory), *args), cwd=cwd, capture_output=True, text=True)


def selected(result: subprocess.CompletedProcess[str]) -> dict[str, list[dict[str, str]]]:
    assert result.returncode == 0, result.stderr
    return {item["name"]: item["reasons"] for item in json.loads(result.stdout)}


class Repo:
    def __init__(self, root: Path):
        self.root = root
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "user.name", "Test")

    def git(self, *args: str) -> None:
        subprocess.run(("git", *args), cwd=self.root, check=True, capture_output=True)

    def write(self, name: str, text: str) -> None:
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def commit(self, message: str = "c") -> None:
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)


class SelectTests(unittest.TestCase):
    def setUp(self):
        base = ROOT / ".work/tmp"
        base.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=base)
        self.repo = Repo(Path(self.tmp.name))
        self.repo.write("README.md", "hello\n")
        self.repo.write("tool", "#!/bin/sh\nset -eu\necho one\n")
        self.repo.write("app.py", "def f():\n    return 1\n")
        self.repo.commit()

    def tearDown(self):
        self.tmp.cleanup()

    def select(self, *args: str) -> dict[str, list[dict[str, str]]]:
        return selected(run("select", "--json", *args, cwd=self.repo.root))

    def test_clean_tree_and_prose_edits_select_nothing(self):
        self.assertEqual({}, self.select())
        self.repo.write("README.md", "hello there\n")
        self.assertEqual({}, self.select())

    def test_edit_below_an_unchanged_shebang_selects_shell(self):
        self.repo.write("tool", "#!/bin/sh\nset -eu\necho two\n")
        result = self.select()
        self.assertEqual(["shell"], list(result))
        self.assertEqual([("tool", "shebang")], [(r["file"], r["trigger"]) for r in result["shell"]])

    def test_only_added_lines_trigger_content_rules(self):
        self.repo.write("app.py", "import argparse\ndef f():\n    return 1\n")
        self.repo.commit()
        self.repo.write("app.py", "def f():\n    return 1\n")
        self.assertEqual({}, self.select())
        self.repo.write("app.py", "import signal\nsignal.signal(signal.SIGINT, h)\n")
        self.assertEqual(["cli-interrupt"], list(self.select()))

    def test_untracked_and_nested_paths_select_by_glob(self):
        self.repo.write("svc/.github/workflows/ci.yml", "on: push\n")
        self.repo.write("pkg/Makefile", "all:\n\ttrue\n")
        result = self.select()
        self.assertEqual({"github-actions", "shell"}, set(result))
        self.assertEqual("path", result["shell"][0]["trigger"])

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

    def test_explicit_files_match_whole_content(self):
        self.assertEqual(["shell"], list(self.select("tool")))
        self.assertEqual({}, self.select("README.md"))
        missing = run("select", "nope", cwd=self.repo.root)
        self.assertEqual(2, missing.returncode)
        self.assertIn("nope: not a file", missing.stderr)

    def test_text_output_names_standard_file_and_reason(self):
        self.repo.write("tool", "#!/bin/sh\necho changed\n")
        result = run("select", cwd=self.repo.root)
        self.assertEqual(0, result.returncode, result.stderr)
        name, path, reason = result.stdout.rstrip("\n").split("\t")
        self.assertEqual(("shell", str(STANDARDS / "shell.md")), (name, path))
        self.assertTrue(reason.startswith("tool: shebang "), reason)


class CheckTests(unittest.TestCase):
    def setUp(self):
        base = ROOT / ".work/tmp"
        base.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=base)
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def check(self, name: str, text: str) -> subprocess.CompletedProcess[str]:
        (self.dir / f"{name}.md").write_text(text)
        return run("check", cwd=self.dir, directory=self.dir)

    def test_repository_standards_are_valid(self):
        result = run("check", cwd=ROOT)
        self.assertEqual(0, result.returncode, result.stderr)

    def test_invalid_standards_fail_closed(self):
        cases = {
            "missing frontmatter": ("a", "# A\n", "missing frontmatter"),
            "name mismatch": ("b", "---\nname: other\nsummary: s\npaths:\n  - x\n---\n", "name must equal"),
            "unknown key": ("c", "---\nname: c\nsummary: s\nglob: x\n---\n", "expected one of"),
            "no triggers": ("d", "---\nname: d\nsummary: s\n---\n", "needs at least one"),
            "bad regex": ("e", "---\nname: e\nsummary: s\ncontent:\n  - '('\n---\n", "invalid content regex"),
            "inline list": ("f", "---\nname: f\nsummary: s\npaths: x\n---\n", "must be a list"),
        }
        for label, (name, text, message) in cases.items():
            with self.subTest(label):
                for old in self.dir.glob("*.md"):
                    old.unlink()
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

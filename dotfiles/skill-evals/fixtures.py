#!/usr/bin/env python3
import argparse
import shutil
import subprocess
import tempfile
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
SCRATCH_CHECK = REPO / "dotfiles" / "scratch-check.sh"
SKILL_TREE = REPO / "dotfiles" / "base" / ".agents" / "skills"
CASES = (
    "trivial",
    "bug",
    "read-only",
    "unreproduced",
    "feature",
    "ticket",
    "rfc",
    "campaign-authorized",
    "campaign-no-commit",
    "campaign-new",
    "deferred-performance",
    "unavailable-check",
    "verify",
)


def write(root: Path, name: str, content: str) -> None:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def prepare(case: str) -> Path:
    if case not in CASES:
        raise SystemExit(f"unknown fixture {case!r}; choose one of {', '.join(CASES)}")
    subprocess.run(["sh", str(SCRATCH_CHECK), str(REPO)], check=True)
    work = REPO / ".work" / "tmp"
    workspace = Path(tempfile.mkdtemp(prefix=f"do-eval-{case}-", dir=work))
    subprocess.run(["git", "init", "-q", str(workspace)], check=True)
    git(workspace, "config", "user.name", "Fixture Evaluator")
    git(workspace, "config", "user.email", "fixture@example.invalid")
    git(workspace, "config", "core.filemode", "true")
    git(workspace, "config", "core.symlinks", "true")
    git(workspace, "config", "core.excludesFile", "/dev/null")
    write(workspace, "AGENTS.md", "# Evaluation fixture\n\nUse Python's standard library. Keep this fixture offline. Run Python checks with `-B -I` to avoid bytecode artifacts. Do not publish. Follow any task-specific authority in the campaign file. Use Conventional Commit subjects for commits.\n")
    write(workspace, "README.md", "# Evaluation fixture\n\nA disposable repository for /do workflow checks.\n")
    write(workspace, ".git/info/exclude", ".work/\n")
    (workspace / ".agents").mkdir()
    shutil.copytree(SKILL_TREE, workspace / ".agents" / "skills", symlinks=False)

    if case == "trivial":
        write(workspace, "notes.txt", "Existing note.\n")
    elif case == "bug":
        write(workspace, "src/notifier.py", "class Notifier:\n    def __init__(self):\n        self.listeners = []\n\n    def connect(self, listener):\n        self.listeners.append(listener)\n\n    def reconnect(self, listener):\n        self.listeners.append(listener)\n\n    def notify(self, value):\n        for listener in self.listeners:\n            listener(value)\n")
        write(workspace, "tests/test_notifier.py", "import sys\nimport unittest\nfrom pathlib import Path\n\nsys.path.insert(0, str(Path(__file__).resolve().parents[1]))\nfrom src.notifier import Notifier\n\n\nclass NotifierTests(unittest.TestCase):\n    def test_reconnect_does_not_duplicate_notification(self):\n        received = []\n        notifier = Notifier()\n        notifier.connect(received.append)\n        notifier.reconnect(received.append)\n        notifier.notify('connected')\n        self.assertEqual(['connected'], received)\n\n\nif __name__ == '__main__':\n    unittest.main()\n")
    elif case == "read-only":
        write(workspace, "src/startup.py", "import json\n\n\ndef read_settings(path):\n    return json.loads(path.read_text(encoding='utf-8'))\n\n\ndef start(path):\n    display_settings = read_settings(path)\n    runtime_settings = read_settings(path)\n    return {'display': display_settings, 'runtime': runtime_settings}\n")
        write(workspace, "settings.json", '{"mode": "fixture"}\n')
    elif case == "unreproduced":
        write(workspace, "src/notifier.py", "class Notifier:\n    def __init__(self):\n        self.listeners = []\n\n    def connect(self, listener):\n        if listener not in self.listeners:\n            self.listeners.append(listener)\n\n    def reconnect(self, listener):\n        self.connect(listener)\n\n    def notify(self, value):\n        for listener in self.listeners:\n            listener(value)\n")
        write(workspace, "tests/test_notifier.py", "import sys\nimport unittest\nfrom pathlib import Path\n\nsys.path.insert(0, str(Path(__file__).resolve().parents[1]))\nfrom src.notifier import Notifier\n\n\nclass NotifierTests(unittest.TestCase):\n    def test_reconnect_does_not_duplicate_notification(self):\n        received = []\n        notifier = Notifier()\n        notifier.connect(received.append)\n        notifier.reconnect(received.append)\n        notifier.notify('connected')\n        self.assertEqual(['connected'], received)\n\n\nif __name__ == '__main__':\n    unittest.main()\n")
    elif case == "feature":
        write(workspace, "cli.py", "import argparse\n\n\ndef main():\n    parser = argparse.ArgumentParser()\n    parser.add_argument('values', nargs='+', type=int)\n    args = parser.parse_args()\n    print(f'total: {sum(args.values)}')\n\n\nif __name__ == '__main__':\n    main()\n")
        write(workspace, "tests/test_cli.py", "import subprocess\nimport sys\nimport unittest\nfrom pathlib import Path\n\n\nclass CliTests(unittest.TestCase):\n    def test_text_output(self):\n        root = Path(__file__).resolve().parents[1]\n        result = subprocess.run([sys.executable, '-I', str(root / 'cli.py'), '2', '3'], capture_output=True, text=True, check=True)\n        self.assertEqual('total: 5\\n', result.stdout)\n\n\nif __name__ == '__main__':\n    unittest.main()\n")
        write(workspace, ".agents/skills/verify-fixture/SKILL.md", "---\nname: verify-fixture\ndescription: Verify the fixture's Python CLI through its command line.\ndisable-model-invocation: true\n---\n\nRun python3 -B -I cli.py 2 3 and expect total: 5 from the fixture root.\n")
    elif case == "ticket":
        write(workspace, "TODO.md", "Prefix: USR\nNext: 3\n\n### USR-11 · P2 · Prevent duplicate reconnect delivery\n\n- **Area:** Tests\n- **Where:** src/notifier.py\n- **Problem:** reconnect registers an existing listener twice.\n- **Recommendation:** avoid duplicate registration.\n- **Fix with:** root-cause\n- **Effort:** S (hours)\n\n### USR-12 · P3 · Add JSON totals\n\n- **Area:** Build\n- **Where:** cli.py\n- **Problem:** the CLI has no JSON output.\n- **Recommendation:** add an opt-in JSON mode.\n- **Fix with:** none\n- **Effort:** S (hours)\n")
        write(workspace, "src/notifier.py", "class Notifier:\n    def __init__(self):\n        self.listeners = []\n\n    def connect(self, listener):\n        self.listeners.append(listener)\n\n    def reconnect(self, listener):\n        self.listeners.append(listener)\n\n    def notify(self, value):\n        for listener in self.listeners:\n            listener(value)\n")
        write(workspace, "tests/test_notifier.py", "import sys\nimport unittest\nfrom pathlib import Path\n\nsys.path.insert(0, str(Path(__file__).resolve().parents[1]))\nfrom src.notifier import Notifier\n\n\nclass NotifierTests(unittest.TestCase):\n    def test_reconnect_does_not_duplicate_listener(self):\n        received = []\n        notifier = Notifier()\n        notifier.connect(received.append)\n        notifier.reconnect(received.append)\n        notifier.notify('connected')\n        self.assertEqual(['connected'], received)\n\n\nif __name__ == '__main__':\n    unittest.main()\n")
    elif case == "rfc":
        write(workspace, "docs/rfc/SEARCH.md", "# USR-20: Search migration\n\nStatus: draft\n\n## Summary\n\nReplace the current search backend.\n\n## Open questions\n\n- Which backend should own ranking?\n")
        write(workspace, "src/search.py", "def search(query):\n    return []\n")
    elif case in ("campaign-authorized", "campaign-no-commit"):
        authority = (
            "One local commit is authorized after all acceptance checks pass. Do not push.\n"
            if case == "campaign-authorized"
            else "Do not commit or push. Complete the work in the working tree.\n"
        )
        write(workspace, "AGENTS.md", f"# Evaluation fixture\n\nUse Python's standard library. Keep this fixture offline. Run Python checks with `-B -I` to avoid bytecode artifacts. {authority}")
        write(workspace, "docs/CAMPAIGN-SAMPLE.md", f"# Sample campaign\n\nStatus: ready\n\n## Acceptance\n\n- Implement `is_positive(value: int) -> bool`, returning true exactly when `value > 0`.\n- `python3 -B -I -m unittest discover -s tests` passes tests for 1, 0, and -1.\n\n## Authority\n\n{authority}")
        write(workspace, "src/value.py", "def is_positive(value: int) -> bool:\n    raise NotImplementedError\n")
        write(workspace, "tests/test_value.py", "import sys\nimport unittest\nfrom pathlib import Path\n\nsys.path.insert(0, str(Path(__file__).resolve().parents[1]))\nfrom src.value import is_positive\n\n\nclass ValueTests(unittest.TestCase):\n    def test_positive_values(self):\n        self.assertTrue(is_positive(1))\n\n    def test_zero_is_not_positive(self):\n        self.assertFalse(is_positive(0))\n\n    def test_negative_values_are_not_positive(self):\n        self.assertFalse(is_positive(-1))\n\n\nif __name__ == '__main__':\n    unittest.main()\n")
    elif case == "campaign-new":
        write(workspace, "README.md", """# Manifest importer

`python3 -B -I import_manifest.py FILE` reads UTF-8 JSON Lines, one object per line. Each object has exactly a nonblank string `name` and a nonnegative integer `count`; booleans are invalid. It prints compact JSON with `records` and summed `total` fields.

Two records `{"name":"alpha","count":2}` and `{"name":"beta","count":3}` print `{"records":2,"total":5}` followed by a newline. An empty file prints `{"records":0,"total":0}`.

Malformed JSON, invalid schema, and invalid UTF-8 exit 2, write exactly `error: invalid manifest` to stderr, and write nothing to stdout.
""")
        write(workspace, "src/manifest.py", "def summarize(lines):\n    raise NotImplementedError\n")
        write(workspace, "import_manifest.py", "import sys\nfrom pathlib import Path\n\nfrom src.manifest import summarize\n\n\ndef main():\n    result = summarize(Path(sys.argv[1]).read_text(encoding='utf-8').splitlines())\n    print(result)\n\n\nif __name__ == '__main__':\n    main()\n")
        write(workspace, "tests/data/two-records.jsonl", '{"name":"alpha","count":2}\n{"name":"beta","count":3}\n')
        write(workspace, "tests/data/empty.jsonl", "")
        write(workspace, "tests/data/invalid-json.jsonl", "{\n")
        write(workspace, "tests/data/invalid-schema.jsonl", '{"name":" ","count":1}\n')
        write(workspace, "tests/data/negative-count.jsonl", '{"name":"alpha","count":-1}\n')
        write(workspace, "tests/data/boolean-count.jsonl", '{"name":"alpha","count":true}\n')
        invalid_utf8 = workspace / "tests" / "data" / "invalid-utf8.jsonl"
        invalid_utf8.write_bytes(b"\xff")
        write(workspace, "tests/test_manifest.py", """import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.manifest import summarize


class ManifestTests(unittest.TestCase):
    def test_summarizes_records(self):
        lines = ['{\"name\":\"alpha\",\"count\":2}', '{\"name\":\"beta\",\"count\":3}']
        self.assertEqual({'records': 2, 'total': 5}, summarize(lines))

    def test_empty_input(self):
        self.assertEqual({'records': 0, 'total': 0}, summarize([]))

    def test_invalid_records_raise_value_error(self):
        invalid = (
            ['{'],
            ['{\"name\":\" \",\"count\":1}'],
            ['{\"name\":\"alpha\",\"count\":true}'],
            ['{\"name\":\"alpha\",\"count\":-1}'],
            ['{\"name\":\"alpha\",\"count\":1,\"extra\":2}'],
        )
        for lines in invalid:
            with self.subTest(lines=lines), self.assertRaises(ValueError):
                summarize(lines)

    def run_cli(self, filename):
        root = Path(__file__).resolve().parents[1]
        manifest = root / 'tests' / 'data' / filename
        return subprocess.run([sys.executable, '-B', '-I', str(root / 'import_manifest.py'), str(manifest)], capture_output=True, text=True, check=False)

    def test_cli_outputs_compact_json(self):
        result = self.run_cli('two-records.jsonl')
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual('{\"records\":2,\"total\":5}\\n', result.stdout)

    def test_cli_outputs_zeroes_for_empty_input(self):
        result = self.run_cli('empty.jsonl')
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual('{\"records\":0,\"total\":0}\\n', result.stdout)

    def test_cli_rejects_invalid_documents(self):
        invalid = ('invalid-json.jsonl', 'invalid-schema.jsonl', 'negative-count.jsonl', 'boolean-count.jsonl', 'invalid-utf8.jsonl')
        for filename in invalid:
            with self.subTest(filename=filename):
                result = self.run_cli(filename)
                self.assertEqual(2, result.returncode)
                self.assertEqual('', result.stdout)
                self.assertEqual('error: invalid manifest\\n', result.stderr)


if __name__ == '__main__':
    unittest.main()
""")
    elif case == "deferred-performance":
        write(workspace, "src/parser.py", "import json\n\n\ndef summarize(lines):\n    amounts = []\n    for line in lines:\n        amounts.append(json.loads(line)['amount'])\n    return {'count': len(amounts), 'total': sum(amounts)}\n")
        write(workspace, "input.jsonl", '{"amount":2}\n{"amount":3}\n{"amount":5}\n')
        write(workspace, "tests/test_parser.py", "import sys\nimport unittest\nfrom pathlib import Path\n\nsys.path.insert(0, str(Path(__file__).resolve().parents[1]))\nfrom src.parser import summarize\n\n\nclass ParserTests(unittest.TestCase):\n    def test_useful_output(self):\n        lines = ['{\"amount\":2}', '{\"amount\":3}', '{\"amount\":5}']\n        self.assertEqual({'count': 3, 'total': 10}, summarize(lines))\n\n\nif __name__ == '__main__':\n    unittest.main()\n")
        write(workspace, "tools/perf-gate-ready", "#!/bin/sh\nprintf '%s\\n' busy\nexit 75\n")
        (workspace / "tools" / "perf-gate-ready").chmod(0o755)
    elif case == "unavailable-check":
        write(workspace, "src/labels.py", "def format_label(value):\n    return value.strip().upper()\n")
        write(workspace, "tests/test_labels.py", "import sys\nimport unittest\nfrom pathlib import Path\n\nsys.path.insert(0, str(Path(__file__).resolve().parents[1]))\nfrom src.labels import format_label\n\n\nclass LabelTests(unittest.TestCase):\n    def test_formats_label(self):\n        self.assertEqual('ALPHA', format_label(' alpha '))\n\n\nif __name__ == '__main__':\n    unittest.main()\n")
        write(workspace, "tools/required_check.py", "import sys\n\nprint('required check unavailable', file=sys.stderr)\nraise SystemExit(86)\n")
        write(workspace, "HANDOFF.md", "# Worker handoff\n\nThe implementation in `src/labels.py` is complete and its unit test passed. The required acceptance command `python3 -B -I tools/required_check.py` remains open. The parent must run it and retain the exact command, exit status, and output. If unavailable, report `partial`; do not claim `done`.\n")
    elif case == "verify":
        write(workspace, "tools/slugify.py", "import re\nimport sys\n\n\ndef main():\n    if len(sys.argv) != 2 or not sys.argv[1].strip():\n        print('usage: slugify.py TEXT', file=sys.stderr)\n        return 2\n    slug = re.sub(r'[^a-z0-9]+', '-', sys.argv[1].strip().lower()).strip('-')\n    if not slug:\n        print('error: text has no slug characters', file=sys.stderr)\n        return 2\n    print(slug)\n    return 0\n\n\nif __name__ == '__main__':\n    raise SystemExit(main())\n")

    git(workspace, "add", "--all")
    git(workspace, "commit", "-m", "test(fixtures): seed evaluation repository")
    return workspace


def git(root: Path, *args: str) -> str:
    result = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=False)
    if result.returncode:
        raise RuntimeError(f"git {' '.join(args)} failed ({result.returncode}): {result.stderr.strip()}")
    return result.stdout


def score_unchanged(workspace: Path, baseline_head: str) -> None:
    head = git(workspace, "rev-parse", "--verify", "HEAD")
    if head.strip() != baseline_head.strip():
        raise RuntimeError(f"fixture HEAD changed: expected {baseline_head.strip()}, got {head.strip()}")
    expected_config = {
        "core.excludesFile": "/dev/null",
        "core.filemode": "true",
        "core.symlinks": "true",
        "user.email": "fixture@example.invalid",
        "user.name": "Fixture Evaluator",
    }
    for name, expected in expected_config.items():
        actual = git(workspace, "config", "--local", "--get-all", name).splitlines()
        if actual != [expected]:
            raise RuntimeError(f"fixture Git setting changed: {name}: {actual!r}")
    exclude = Path(git(workspace, "rev-parse", "--git-path", "info/exclude").strip())
    if not exclude.is_absolute():
        exclude = workspace / exclude
    if exclude.is_symlink() or not exclude.is_file() or exclude.read_text(encoding="utf-8") != ".work/\n":
        raise RuntimeError("fixture .git/info/exclude changed")
    status = git(workspace, "status", "--porcelain=v1", "--untracked-files=all", "--ignored=matching")
    if status:
        raise RuntimeError(f"fixture working tree changed:\n{status.rstrip()}")
    remotes = git(workspace, "remote", "-v")
    if remotes:
        raise RuntimeError(f"fixture has unexpected remotes:\n{remotes.rstrip()}")


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="action", required=True)
    prepare_parser = subparsers.add_parser("prepare")
    prepare_parser.add_argument("case", choices=CASES)
    score_parser = subparsers.add_parser("score-unchanged")
    score_parser.add_argument("fixture", type=Path)
    score_parser.add_argument("baseline_head")
    args = parser.parse_args()
    if args.action == "prepare":
        print(prepare(args.case))
    else:
        try:
            score_unchanged(args.fixture, args.baseline_head)
        except RuntimeError as error:
            raise SystemExit(str(error)) from error


if __name__ == "__main__":
    main()

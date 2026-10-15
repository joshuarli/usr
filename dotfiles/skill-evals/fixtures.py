#!/usr/bin/env python3
import argparse
import subprocess
import tempfile
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
CASES = ("trivial", "bug", "read-only", "feature", "ticket", "rfc", "campaign", "verify")


def write(root: Path, name: str, content: str) -> None:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def prepare(case: str) -> Path:
    if case not in CASES:
        raise SystemExit(f"unknown fixture {case!r}; choose one of {', '.join(CASES)}")
    if subprocess.run(["git", "-C", str(REPO), "check-ignore", "-q", ".work"]).returncode:
        raise SystemExit(".work must be ignored through .git/info/exclude")
    work = REPO / ".work" / "tmp"
    work.mkdir(parents=True, exist_ok=True)
    workspace = Path(tempfile.mkdtemp(prefix=f"do-eval-{case}-", dir=work))
    subprocess.run(["git", "init", "-q", str(workspace)], check=True)
    write(workspace, "AGENTS.md", "# Evaluation fixture\n\nUse Python's standard library. Keep this fixture offline. Do not commit or publish.\n")
    write(workspace, "README.md", "# Evaluation fixture\n\nA disposable repository for /do workflow checks.\n")

    if case == "trivial":
        write(workspace, "notes.txt", "Existing note.\n")
    elif case == "bug":
        write(workspace, "src/notifier.py", "class Notifier:\n    def __init__(self):\n        self.listeners = []\n\n    def connect(self, listener):\n        self.listeners.append(listener)\n\n    def reconnect(self, listener):\n        self.listeners.append(listener)\n\n    def notify(self, value):\n        for listener in self.listeners:\n            listener(value)\n")
        write(workspace, "tests/test_notifier.py", "import sys\nimport unittest\nfrom pathlib import Path\n\nsys.path.insert(0, str(Path(__file__).resolve().parents[1]))\nfrom src.notifier import Notifier\n\n\nclass NotifierTests(unittest.TestCase):\n    def test_reconnect_does_not_duplicate_notification(self):\n        received = []\n        notifier = Notifier()\n        notifier.connect(received.append)\n        notifier.reconnect(received.append)\n        notifier.notify('connected')\n        self.assertEqual(['connected'], received)\n\n\nif __name__ == '__main__':\n    unittest.main()\n")
    elif case == "read-only":
        write(workspace, "src/startup.py", "import json\n\n\ndef read_settings(path):\n    return json.loads(path.read_text(encoding='utf-8'))\n\n\ndef start(path):\n    display_settings = read_settings(path)\n    runtime_settings = read_settings(path)\n    return {'display': display_settings, 'runtime': runtime_settings}\n")
        write(workspace, "settings.json", '{"mode": "fixture"}\n')
    elif case == "feature":
        write(workspace, "cli.py", "import argparse\n\n\ndef main():\n    parser = argparse.ArgumentParser()\n    parser.add_argument('values', nargs='+', type=int)\n    args = parser.parse_args()\n    print(f'total: {sum(args.values)}')\n\n\nif __name__ == '__main__':\n    main()\n")
        write(workspace, "tests/test_cli.py", "import subprocess\nimport sys\nimport unittest\nfrom pathlib import Path\n\n\nclass CliTests(unittest.TestCase):\n    def test_text_output(self):\n        root = Path(__file__).resolve().parents[1]\n        result = subprocess.run([sys.executable, '-I', str(root / 'cli.py'), '2', '3'], capture_output=True, text=True, check=True)\n        self.assertEqual('total: 5\\n', result.stdout)\n\n\nif __name__ == '__main__':\n    unittest.main()\n")
        write(workspace, ".agents/skills/verify-fixture/SKILL.md", "---\nname: verify-fixture\ndescription: Verify the fixture's Python CLI through its command line.\ndisable-model-invocation: true\n---\n\nRun python3 -I cli.py 2 3 and expect total: 5 from the fixture root.\n")
    elif case == "ticket":
        write(workspace, "TODO.md", "Prefix: USR\nNext: 3\n\n### USR-11 · P2 · Prevent duplicate reconnect delivery\n\n- **Area:** Tests\n- **Where:** src/notifier.py\n- **Problem:** reconnect registers an existing listener twice.\n- **Recommendation:** avoid duplicate registration.\n- **Fix with:** root-cause\n- **Effort:** S (hours)\n\n### USR-12 · P3 · Add JSON totals\n\n- **Area:** Build\n- **Where:** cli.py\n- **Problem:** the CLI has no JSON output.\n- **Recommendation:** add an opt-in JSON mode.\n- **Fix with:** none\n- **Effort:** S (hours)\n")
        write(workspace, "src/notifier.py", "class Notifier:\n    def __init__(self):\n        self.listeners = []\n\n    def connect(self, listener):\n        self.listeners.append(listener)\n\n    def reconnect(self, listener):\n        self.listeners.append(listener)\n\n    def notify(self, value):\n        for listener in self.listeners:\n            listener(value)\n")
        write(workspace, "tests/test_notifier.py", "import sys\nimport unittest\nfrom pathlib import Path\n\nsys.path.insert(0, str(Path(__file__).resolve().parents[1]))\nfrom src.notifier import Notifier\n\n\nclass NotifierTests(unittest.TestCase):\n    def test_reconnect_does_not_duplicate_listener(self):\n        received = []\n        notifier = Notifier()\n        notifier.connect(received.append)\n        notifier.reconnect(received.append)\n        notifier.notify('connected')\n        self.assertEqual(['connected'], received)\n\n\nif __name__ == '__main__':\n    unittest.main()\n")
    elif case == "rfc":
        write(workspace, "docs/rfc/SEARCH.md", "# USR-20: Search migration\n\nStatus: draft\n\n## Summary\n\nReplace the current search backend.\n\n## Open questions\n\n- Which backend should own ranking?\n")
        write(workspace, "src/search.py", "def search(query):\n    return []\n")
    elif case == "campaign":
        write(workspace, "docs/CAMPAIGN-SAMPLE.md", "# Sample campaign\n\nStatus: ready\n\n## Acceptance\n\n- Add one tested helper.\n- Do not commit or push.\n")
        write(workspace, "src/value.py", "def value():\n    return 1\n")
    elif case == "verify":
        (workspace / ".agents" / "skills").mkdir(parents=True)
        with (workspace / ".git" / "info" / "exclude").open("a", encoding="utf-8") as exclude:
            exclude.write(".work/\n")
        write(workspace, "tools/slugify.py", "import re\nimport sys\n\n\ndef main():\n    if len(sys.argv) != 2 or not sys.argv[1].strip():\n        print('usage: slugify.py TEXT', file=sys.stderr)\n        return 2\n    slug = re.sub(r'[^a-z0-9]+', '-', sys.argv[1].strip().lower()).strip('-')\n    if not slug:\n        print('error: text has no slug characters', file=sys.stderr)\n        return 2\n    print(slug)\n    return 0\n\n\nif __name__ == '__main__':\n    raise SystemExit(main())\n")

    return workspace


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare",))
    parser.add_argument("case", choices=CASES)
    args = parser.parse_args()
    print(prepare(args.case))


if __name__ == "__main__":
    main()

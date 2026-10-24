#!/usr/bin/env python3
"""Offline Pi installer/profile checks; all writes stay in .work/."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "dotfiles/base/.pi/agent"
MODEL = "google/gemini-3.8-flash"
TIERS = {"scout": "low", "mechanic": "medium", "worker": "high", "expert": "high", "god": "high"}


class PiTests(unittest.TestCase):
    def setUp(self):
        work = ROOT / ".work"
        work.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="pi-test-", dir=work)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.home = self.root / "home"
        self.home.mkdir()
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.env = {
            "HOME": str(self.home), "PATH": f"{self.bin}:/usr/bin:/bin",
            "TMPDIR": str(self.root), "DL_OWNED_FILE": str(self.root / "owned"),
            "MOCK_LOG": str(self.root / "npm.log"), "MOCK_VERSION": "1.4.0",
        }
        self.script("node", '#!/bin/sh\nprintf "%s\\n" "${MOCK_NODE_VERSION:-26.12.0}"\nexit "${MOCK_NODE_STATUS:-0}"\n')
        self.script("npm", f"#!{sys.executable}\n" + '''import json, os, pathlib, sys
args = sys.argv[1:]
with open(os.environ["MOCK_LOG"], "a") as log:
    log.write(json.dumps(args) + "\\n")
if args == ["view", "@earendil-works/pi-coding-agent@latest", "version"]:
    print(os.environ["MOCK_VERSION"])
elif args[:4] == ["install", "--global", "--ignore-scripts", "--prefix"]:
    if os.environ.get("MOCK_FAIL") == "1":
        sys.exit(1)
    assert args[5] == "@earendil-works/pi-coding-agent@" + os.environ["MOCK_VERSION"]
    if os.environ.get("MOCK_NO_BIN") != "1":
        binary = pathlib.Path(args[4]) / "bin/pi"
        binary.parent.mkdir(parents=True, exist_ok=True)
        binary.write_text("#!/bin/sh\\nprintf '%s\\\\n' " + os.environ["MOCK_VERSION"] + "\\n")
        binary.chmod(0o755)
else:
    raise SystemExit("unexpected npm arguments: " + repr(args))
''')

    def script(self, name, text):
        path = self.bin / name
        path.write_text(text)
        path.chmod(0o755)

    def dl(self, ok=True, *args):
        result = subprocess.run(
            ["/bin/sh", str(ROOT / "dl"), *(args or ("pi",))],
            cwd=ROOT, env=self.env, text=True, capture_output=True, timeout=20,
        )
        self.assertEqual(result.returncode == 0, ok, result.stdout + result.stderr)
        return result

    def install_calls(self):
        path = self.root / "npm.log"
        return [json.loads(line) for line in path.read_text().splitlines() if json.loads(line)[0] == "install"]

    def test_install_idempotence_upgrade_and_credentials(self):
        auth = self.home / ".pi/agent/auth.json"
        auth.parent.mkdir(parents=True)
        auth.write_text("private sentinel")
        self.dl()
        launcher = self.home / ".local/bin/pi"
        self.assertTrue(launcher.is_symlink())
        self.assertTrue(os.access(launcher, os.X_OK))
        self.dl()
        self.assertEqual(len(self.install_calls()), 1)
        self.env["MOCK_VERSION"] = "1.4.1"
        self.dl()
        self.assertEqual(len(self.install_calls()), 2)
        self.assertEqual((self.home / ".local/state/dl/pi").read_text(), "1.4.1\n")
        self.assertEqual(auth.read_text(), "private sentinel")
        self.assertNotIn(".pi/agent", (self.root / "owned").read_text())

    def test_failed_fresh_install_is_not_recorded(self):
        self.env["MOCK_FAIL"] = "1"
        self.dl(False)
        self.assertFalse((self.home / ".local/state/dl/pi").exists())
        self.assertFalse((self.home / ".local/share/pi").exists())
        self.assertEqual(list((self.home / ".local/share").glob("pi.*")), [])

    def test_missing_binary_is_failure(self):
        self.env["MOCK_NO_BIN"] = "1"
        self.dl(False)
        self.assertFalse((self.home / ".local/bin/pi").exists())

    def test_unmanaged_launcher_is_preserved(self):
        launcher = self.home / ".local/bin/pi"
        launcher.parent.mkdir(parents=True)
        launcher.write_text("do not replace")
        self.dl(False)
        self.assertEqual(launcher.read_text(), "do not replace")
        self.assertEqual(self.install_calls(), [])

    def test_unmanaged_prefix_is_preserved(self):
        prefix = self.home / ".local/share/pi"
        prefix.mkdir(parents=True)
        (prefix / "sentinel").touch()
        self.dl(False)
        self.assertTrue((prefix / "sentinel").exists())
        self.assertEqual(self.install_calls(), [])

    def test_symlinked_prefix_is_rejected(self):
        prefix = self.home / ".local/share/pi"
        prefix.parent.mkdir(parents=True)
        prefix.symlink_to(self.root, target_is_directory=True)
        self.dl(False)
        self.assertEqual(self.install_calls(), [])

    def test_invalid_version_and_old_node(self):
        self.env["MOCK_VERSION"] = "not-a-version"
        self.dl(False)
        self.assertEqual(self.install_calls(), [])
        self.env["MOCK_NODE_VERSION"] = "26.11.0"
        result = self.dl(False)
        self.assertIn("26.12.0", result.stderr)

    def test_xdg_paths_and_ownership_recovery(self):
        self.env["XDG_DATA_HOME"] = str(self.home / "data with spaces")
        self.env["XDG_STATE_HOME"] = str(self.home / "state with spaces")
        self.dl()
        launcher = self.home / ".local/bin/pi"
        self.assertEqual(os.readlink(launcher), str(self.home / "data with spaces/pi/bin/pi"))
        (self.root / "owned").unlink()
        self.env["DL_RECORD_OWNED"] = "true"
        self.dl()
        owned = (self.root / "owned").read_text()
        self.assertIn(f"D\t{self.home}/data with spaces/pi\n", owned)
        self.assertIn(f"F\t{launcher}\n", owned)
        self.assertNotIn(".pi/agent", owned)
        self.assertEqual(len(self.install_calls()), 1)

    def test_profile_and_orchestration_agree(self):
        settings = json.loads((PROFILE / "settings.json").read_text())
        self.assertEqual(settings["defaultProvider"] + "/" + settings["defaultModel"], MODEL)
        self.assertEqual(settings["enabledModels"], [MODEL])
        self.assertEqual(settings["packages"], ["npm:pi-subagents@0.82.0"])
        self.assertEqual(settings["skills"], ["~/.agents/skills"])
        subagents = settings["subagents"]
        self.assertEqual(subagents["defaultModel"], MODEL)
        self.assertEqual(subagents["maxThinking"], "high")
        self.assertEqual(subagents["modelScope"], {"enforce": True, "strict": True, "allow": [MODEL]})
        self.assertEqual(os.readlink(PROFILE / "AGENTS.md"), "../../.codex/AGENTS.md")
        self.assertFalse((PROFILE / ".sym-dir").exists())
        routing = (ROOT / "dotfiles/base/.agents/skills/orchestrate/SKILL.md").read_text()
        for name, thinking in TIERS.items():
            agent = (PROFILE / "agents" / f"{name}.md").read_text()
            fields = dict(line.split(": ", 1) for line in agent.split("---", 2)[1].strip().splitlines())
            self.assertEqual(fields["model"], MODEL)
            self.assertEqual(fields["thinking"], thinking)
            self.assertNotIn("subagent", fields["tools"])
            if name == "scout":
                self.assertEqual(fields["tools"], "read, grep, find, ls")
            self.assertIn(f"`{MODEL}`, `{name}`, `{thinking}`", routing)
        default_line = next(line for line in (ROOT / "dl").read_text().splitlines() if line.startswith("    set -- fd rg"))
        self.assertIn("pi", default_line.split())


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""Exercise installed harness shims without real clients, accounts, or network."""

import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SHIMS = ROOT / "dotfiles/base/.local/lib/harness-shims"
NAMES = ("codex", "claude", "cmd", "copilot")
POLICY_ENV = ("CLAUDE_CODE_ENABLE_CFC", "CMD_DISABLE_NOTICES", "COMMANDCODE_SKIP_UPDATES", "DO_NOT_TRACK")
FAKE = """import json, os, sys
from pathlib import Path
record = {"argv": sys.argv[1:], "pid": os.getpid(), "stdin": sys.stdin.read(),
          "env": {key: os.environ.get(key) for key in json.loads(os.environ["HARNESS_TEST_ENV_KEYS"])}}
Path(os.environ["HARNESS_TEST_CAPTURE"]).write_text(json.dumps(record))
sys.stdout.write("upstream stdout\\n")
sys.stderr.write("upstream stderr\\n")
sys.exit(int(os.environ.get("HARNESS_TEST_STATUS", "0")))
"""


class HarnessLeanTests(unittest.TestCase):
    def setUp(self):
        scratch = ROOT / ".work/tmp"
        scratch.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=scratch, prefix="harness lean-")
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.bin = self.home / ".local/bin"
        self.shims = self.home / ".local/lib/harness-shims"
        self.bin.mkdir(parents=True)
        self.shims.mkdir(parents=True)
        self.capture = self.home / "capture.json"
        fake = self.home / "fake.py"
        fake.write_text(FAKE)
        for name in NAMES:
            (self.shims / name).symlink_to(SHIMS / name)
            upstream = self.bin / name
            upstream.write_text(f'#!/bin/sh\nexec {shlex.quote(sys.executable)} -I -S {shlex.quote(str(fake))} "$@"\n')
            upstream.chmod(0o755)
        # A repeated shim PATH entry must not recurse, and no host client is reachable.
        self.env = {
            "HOME": str(self.home),
            "PATH": os.pathsep.join(map(str, (self.shims, self.shims, self.bin))),
            "HARNESS_TEST_CAPTURE": str(self.capture),
            "HARNESS_TEST_ENV_KEYS": json.dumps((*POLICY_ENV, "HARNESS_TEST_KEEP")),
            "HARNESS_TEST_KEEP": "ordinary inherited value",
            **dict.fromkeys(POLICY_ENV, "inherited"),
        }

    def invoke(self, name: str, args: tuple[str, ...], status: int = 0):
        self.capture.unlink(missing_ok=True)
        with subprocess.Popen(
            [name, *args], env={**self.env, "HARNESS_TEST_STATUS": str(status)},
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        ) as process:
            try:
                stdout, stderr = process.communicate("input unchanged\n", timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate()
                raise
        self.assertEqual((process.returncode, stdout, stderr), (status, "upstream stdout\n", "upstream stderr\n"))
        record = json.loads(self.capture.read_text())
        self.assertEqual(record["pid"], process.pid, "shim must exec, not supervise the client")
        self.assertEqual(record["stdin"], "input unchanged\n")
        self.assertEqual(record["env"]["HARNESS_TEST_KEEP"], "ordinary inherited value")
        return record

    def test_arguments_and_stdio_survive_symlinked_launch(self):
        args = ("two words", "", "line\nbreak", "'quoted'", "$(not executed)", "*", "--", "--remote")
        for name in NAMES:
            with self.subTest(name=name):
                record = self.invoke(name, args, status=23)
                if name == "codex":
                    expected = ("--no-daemon", *args)
                elif name == "copilot":
                    expected = ("--no-auto-update", "--disable-client-telemetry", "--sync-session=off", *args)
                else:
                    expected = args
                self.assertEqual(record["argv"], list(expected))

    def test_shared_shell_selects_shims_before_managed_binaries(self):
        config = ROOT / "dotfiles/base/.config/sh/config.sh"
        result = subprocess.run(
            ["/bin/sh", "-c", '. "$1"; . "$1"; for name in codex claude cmd copilot; do command -v "$name"; done', "sh", str(config)],
            env={**self.env, "PATH": str(self.bin) + ":/usr/bin:/bin"},
            capture_output=True, text=True, check=True, timeout=5,
        )
        self.assertEqual(result.stdout.splitlines(), [str(self.shims / name) for name in NAMES])

    def test_codex_local_modes_get_one_no_daemon_flag(self):
        for args in (
            (), ("resume", "session id"), ("fork", "--last"),
            ("exec", "--json", "prompt with spaces"), ("app-server",),
            ("--help",), ("login",), ("mcp", "list"),
        ):
            with self.subTest(args=args):
                self.assertEqual(self.invoke("codex", args)["argv"], ["--no-daemon", *args])

    def test_codex_explicit_no_daemon_is_not_duplicated(self):
        for args in (("--no-daemon",), ("resume", "--no-daemon", "--last"),
                     ("--no-daemon", "--", "--no-daemon")):
            with self.subTest(args=args):
                self.assertEqual(self.invoke("codex", args)["argv"], list(args))

    def test_codex_explicit_remote_is_preserved(self):
        for args in (
            ("--remote", "ssh://example", "prompt"),
            ("resume", "--remote=ssh://example", "--last"),
            ("--remote", "ssh://example", "--", "--no-daemon"),
            ("--no-daemon", "--remote=ssh://example"),
        ):
            with self.subTest(args=args):
                self.assertEqual(self.invoke("codex", args)["argv"], list(args))

    def test_codex_option_boundary_and_similar_text_are_not_options(self):
        for args in (
            ("--", "--no-daemon"), ("--", "--remote", "ssh://example"),
            ("--", "--remote=ssh://example"), ("explain --remote and --no-daemon",),
            ("--remote-like",),
        ):
            with self.subTest(args=args):
                self.assertEqual(self.invoke("codex", args)["argv"], ["--no-daemon", *args])

    def test_claude_environment_only_leaves_all_arguments_intact(self):
        for args in ((), ("--chrome",), ("auth", "login"), ("update",), ("mcp", "list"),
                     ("-p", "--output-format", "stream-json", "prompt")):
            with self.subTest(args=args):
                record = self.invoke("claude", args)
                self.assertEqual(record["argv"], list(args))
                self.assertEqual(record["env"]["CLAUDE_CODE_ENABLE_CFC"], "0")
                for key in POLICY_ENV[1:]:
                    self.assertEqual(record["env"][key], "inherited")

    def test_cmd_environment_only_leaves_all_arguments_intact(self):
        for args in ((), ("--help",), ("login",), ("mcp", "list"), ("-p", "prompt")):
            with self.subTest(args=args):
                record = self.invoke("cmd", args)
                self.assertEqual(record["argv"], list(args))
                self.assertEqual(record["env"]["CLAUDE_CODE_ENABLE_CFC"], "inherited")
                for key in POLICY_ENV[1:]:
                    self.assertEqual(record["env"][key], "1")

    def test_missing_upstream_fails_without_path_fallback(self):
        for name in NAMES:
            with self.subTest(name=name):
                (self.bin / name).unlink()
                result = subprocess.run([name, "--help"], env=self.env, capture_output=True, text=True, timeout=5)
                self.assertEqual(result.returncode, 127)
                self.assertEqual(result.stdout, "")
                self.assertIn(str(self.bin / name), result.stderr)


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""Exercise installed harness shims without real clients, accounts, or network."""

import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SHIMS = ROOT / "dotfiles/base/.local/lib/harness-shims"
NAMES = ("codex", "claude", "cmd", "copilot", "pi", "opencode", "devin", "agy", "fx", "muse", "dsh")
HARNESS_IDS = ("claude", "codex", "command-code", "pi", "opencode", "opencode-go", "devin", "antigravity", "copilot", "fx", "muse", "deepseek")
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
        self.repo = self.home / "usr"
        helper = self.repo / "dotfiles/base/.local/bin/harness-enabled"
        helper.parent.mkdir(parents=True)
        shutil.copy2(ROOT / "dotfiles/base/.local/bin/harness-enabled", helper)
        reader = self.repo / "tools/sync/harnesses.py"
        reader.parent.mkdir(parents=True)
        shutil.copy2(ROOT / "tools/sync/harnesses.py", reader)
        self.switches = dict.fromkeys(HARNESS_IDS, True)
        self.config = self.repo / "harnesses.json"
        self.config.write_text(json.dumps(self.switches))
        self.pi_settings = self.home / ".pi/agent/settings.json"
        self.pi_settings.parent.mkdir(parents=True)
        self.pi_settings.write_text(json.dumps({"defaultProvider": "opencode-go", "defaultModel": "fixture"}))
        (self.bin / "harness-enabled").symlink_to(helper)
        (self.bin / "python3").symlink_to(sys.executable)
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
            ["/bin/sh", "-c", '. "$1"; . "$1"; shift; for name; do command -v "$name"; done', "sh", str(config), *NAMES],
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

    def test_each_disabled_harness_stops_before_the_client_and_can_be_restored(self):
        aliases = {"cmd": "command-code", "agy": "antigravity", "dsh": "deepseek"}
        for name in NAMES:
            with self.subTest(name=name):
                self.capture.unlink(missing_ok=True)
                key = aliases.get(name, name)
                self.switches[key] = False
                self.config.write_text(json.dumps(self.switches))
                result = subprocess.run([name, "prompt"], env=self.env, capture_output=True, text=True, timeout=5)
                self.assertEqual(result.returncode, 1)
                self.assertIn("is disabled", result.stderr)
                self.assertFalse(self.capture.exists(), "disabled client was launched")
                self.switches[key] = True
                self.config.write_text(json.dumps(self.switches))
                self.invoke(name, ("prompt",))

    def test_missing_or_malformed_switchboard_fails_closed(self):
        for data in (None, "{", '{"cmd": true}', json.dumps({**self.switches, "pi": "true"})):
            with self.subTest(data=data):
                if data is None:
                    self.config.unlink()
                else:
                    self.config.write_text(data)
                result = subprocess.run(["cmd", "prompt"], env=self.env, capture_output=True, text=True, timeout=5)
                self.assertEqual(result.returncode, 2)
                self.assertFalse(self.capture.exists())

    def test_disabled_native_opencode_preserves_only_enabled_pi_go_auth_exports(self):
        self.switches["opencode"] = False
        self.config.write_text(json.dumps(self.switches))
        for args in (("auth", "export"), ("auth", "export", "opencode")):
            self.assertEqual(self.invoke("opencode", args)["argv"], list(args))
        for args in (("auth", "export", "other"), ("auth", "export", "opencode", "--extra"),
                     ("auth", "login"), ("auth", "export", ""), ("prompt",)):
            self.capture.unlink(missing_ok=True)
            result = subprocess.run(["opencode", *args], env=self.env, capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 1, str(args))
            self.assertFalse(self.capture.exists())
        for provider in ("pi", "opencode-go"):
            self.switches[provider] = False
            self.config.write_text(json.dumps(self.switches))
            for args in (("auth", "export"), ("auth", "export", "opencode")):
                result = subprocess.run(["opencode", *args], env=self.env, capture_output=True, text=True, timeout=5)
                self.assertEqual(result.returncode, 1)
                self.assertFalse(self.capture.exists())
            self.switches[provider] = True

    def test_pi_disabled_default_stops_before_native_start_and_accepts_explicit_enabled_provider(self):
        self.switches["opencode-go"] = False
        self.config.write_text(json.dumps(self.switches))
        for args in ((), ("prompt",), ("--model", "fixture"), ("--", "--provider", "devin", "--model", "fixture"),
                     ("--system-prompt", "--provider", "devin", "--model", "fixture")):
            result = subprocess.run(["pi", *args], env=self.env, capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 1, str(args))
            self.assertIn("default provider 'opencode-go' is disabled", result.stderr)
            self.assertIn("--provider with --model", result.stderr)
            self.assertFalse(self.capture.exists())
        for args in (("--provider", "devin", "--model", "fixture", "prompt"),
                     ("--model", "devin/fixture:high", "prompt"),
                     ("--provider", "opencode-go", "--provider", "devin", "--model", "fixture"),
                     ("--help",), ("--version",), ("--list-models",), ("auth", "login")):
            self.assertEqual(self.invoke("pi", args)["argv"], list(args))

    def test_pi_disabled_explicit_provider_and_extension_bypass_are_refused(self):
        self.switches["devin"] = False
        self.config.write_text(json.dumps(self.switches))
        for args in (("--provider", "devin", "--model", "fixture"),
                     ("--model", "devin/fixture:high"),
                     ("--provider", "opencode-go", "--provider", "DEVIN", "--model", "fixture"),
                     ("--provider", "opencode-go", "--model", "devin/fixture"),
                     ("--no-extensions",), ("-ne", "--model", "opencode-go/fixture")):
            result = subprocess.run(["pi", *args], env=self.env, capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 1, str(args))
            self.assertFalse(self.capture.exists())
        self.assertEqual(self.invoke("pi", ("prompt",))["argv"], ["prompt"])

    def test_pi_reads_current_settings_without_an_environment_enable_override(self):
        self.switches["devin"] = False
        self.config.write_text(json.dumps(self.switches))
        self.pi_settings.write_text(json.dumps({"defaultProvider": "devin", "defaultModel": "fixture"}))
        result = subprocess.run(["pi", "prompt"], env={**self.env, "USR_ENABLE_DEVIN": "1"},
                                capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 1)
        self.assertFalse(self.capture.exists())
        self.switches["devin"] = True
        self.config.write_text(json.dumps(self.switches))
        self.assertEqual(self.invoke("pi", ("prompt",))["argv"], ["prompt"])

    def test_switch_helper_bare_and_harness_help_share_full_config_independent_help(self):
        self.config.unlink()
        outputs = []
        for args in ((), ("-h",), ("--help",), ("cmd", "-h"), ("pi", "--help"), ("--auth-export", "-h")):
            result = subprocess.run(["harness-enabled", *args], env=self.env, capture_output=True, text=True, timeout=5)
            self.assertEqual((result.returncode, result.stderr), (0, ""), str(args))
            outputs.append(result.stdout)
        self.assertTrue(all(output == outputs[0] for output in outputs))
        for detail in ("--auth-export", "--launch", "--version", "cmd = command-code", "agy = antigravity", "dsh = deepseek",
                       "Exit status:", "Examples:", "HOME", "PI_CODING_AGENT_DIR", "harnesses.json", ".pi/settings.json"):
            self.assertIn(detail, outputs[0])
        result = subprocess.run(["harness-enabled", "--version"], env=self.env, capture_output=True, text=True, timeout=5)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "harness-enabled 1.0\n", ""))

    def test_switch_helper_parser_rejects_usage_errors_and_preserves_launch_help(self):
        for args in (("missing",), ("--auth-export",), ("cmd", "--launch"), ("pi", "--auth-export"),
                     ("opencode", "--auth-export", "extra"), ("pi", "--la"), ("pi", "--bad", "--launch", "--")):
            result = subprocess.run(["harness-enabled", *args], env=self.env, capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 2, str(args))
            self.assertIn("usage: harness-enabled", result.stderr)
        self.switches["pi"] = False
        self.config.write_text(json.dumps(self.switches))
        for flag in ("--help", "-h", "--version"):
            result = subprocess.run(["harness-enabled", "pi", "--launch", flag], env=self.env,
                                    capture_output=True, text=True, timeout=5)
            self.assertEqual((result.returncode, result.stdout), (1, ""), flag)
            self.assertIn("pi is disabled", result.stderr)

    def test_switch_helper_aliases_keep_guard_and_configuration_exit_statuses(self):
        for alias, canonical in (("cmd", "command-code"), ("agy", "antigravity"), ("dsh", "deepseek")):
            self.switches[canonical] = False
            self.config.write_text(json.dumps(self.switches))
            for name in (alias, canonical):
                result = subprocess.run(["harness-enabled", name], env=self.env, capture_output=True, text=True, timeout=5)
                self.assertEqual(result.returncode, 1, name)
                self.assertIn(f"enable {canonical!r}", result.stderr)
        for data in (None, "not JSON"):
            if data is None:
                self.config.unlink()
            else:
                self.config.write_text(data)
            result = subprocess.run(["harness-enabled", "pi", "--launch", "--help"], env=self.env,
                                    capture_output=True, text=True, timeout=5)
            self.assertEqual((result.returncode, result.stdout), (2, ""))
        self.assertFalse(self.capture.exists(), "helper checks must never launch a client")


if __name__ == "__main__":
    unittest.main()

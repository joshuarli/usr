#!/usr/bin/env python3
"""Disk-pressure threshold, event delivery and shared-notice safety tests."""
from __future__ import annotations

import concurrent.futures
import importlib.machinery
import importlib.util
import io
import json
import multiprocessing
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import tomllib
from types import SimpleNamespace
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "dotfiles/base/.local/bin/agent-disk-pressure"
loader = importlib.machinery.SourceFileLoader("disk_pressure", str(TOOL))
spec = importlib.util.spec_from_loader(loader.name, loader)
assert spec and spec.loader
pressure = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = pressure
spec.loader.exec_module(pressure)


def notify_process(directory: str) -> str | None:
    with patch.object(pressure, "state_directory", return_value=Path(directory)), \
         patch.object(pressure, "sample_disk", return_value=pressure.Sample("/", 9, 100)), \
         patch.dict(os.environ, {"USR_SCOPED_WORKER": ""}):
        return pressure.notification()


class DiskPressureTests(unittest.TestCase):
    def setUp(self):
        scratch = ROOT / ".work/tmp"
        scratch.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=scratch, prefix="pressure-")
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name) / "state"
        self.enterContext(patch.object(pressure, "state_directory", return_value=self.directory))
        self.enterContext(patch.dict(os.environ, {"USR_SCOPED_WORKER": ""}))

    def notify(self, available: int, total: int = 100, now: float = 10000) -> str | None:
        with patch.object(pressure, "sample_disk", return_value=pressure.Sample("/", available, total)), \
             patch.object(pressure.time, "time", return_value=now):
            return pressure.notification()

    def event(self, payload: object) -> str:
        stream = SimpleNamespace(buffer=io.BytesIO(json.dumps(payload).encode()))
        output = io.StringIO()
        with patch.object(sys, "stdin", stream), patch.object(sys, "stdout", output):
            self.assertEqual(pressure.hook(), 0)
        return output.getvalue()

    def test_exact_threshold_and_no_state_or_external_commands_when_healthy(self):
        with patch.object(subprocess, "run", side_effect=AssertionError("no subprocess")), \
             patch.object(pressure, "locked", side_effect=AssertionError("no lock needed")):
            for available, total in ((10, 100), (11, 100), (100, 100), (10001, 100000)):
                self.assertIsNone(self.notify(available, total))
                self.assertFalse(self.directory.exists())
        self.assertIsNotNone(self.notify(9999, 100000))

    def test_available_not_root_reserved_blocks_and_writable_macos_boot_volume(self):
        info = SimpleNamespace(f_bavail=9, f_bfree=50, f_blocks=100, f_frsize=4096, f_bsize=4096)
        for platform, path in (("darwin", "/System/Volumes/Data"), ("linux", "/")):
            with patch.object(pressure.sys, "platform", platform), patch.object(pressure.os, "statvfs", return_value=info) as read:
                sample = pressure.sample_disk()
                read.assert_called_once_with(path)
                self.assertTrue(sample.low)
                self.assertEqual(sample.available, 9 * 4096)
        with patch.object(pressure.os, "statvfs", return_value=SimpleNamespace(**(vars(info) | {"f_blocks": 0}))):
            with self.assertRaises(ValueError):
                pressure.sample_disk()

    def test_cross_session_cooldown_recovery_and_clock_rollback(self):
        self.assertIsNotNone(self.notify(9, now=10000))
        self.assertIsNone(self.notify(8, now=10001))
        self.assertIsNone(self.notify(1, now=11799))
        self.assertIsNotNone(self.notify(1, now=11800))
        self.assertIsNone(self.notify(10, now=11801))
        self.assertFalse((self.directory / "notice.json").exists())
        self.assertTrue((self.directory / "notice.lock").exists())
        self.assertIsNotNone(self.notify(9, now=11802))
        self.assertIsNotNone(self.notify(9, now=100))

    def test_fresh_sample_under_lock_prevents_stale_low_notice(self):
        with patch.object(pressure, "sample_disk", side_effect=[pressure.Sample("/", 9, 100), pressure.Sample("/", 10, 100)]):
            self.assertIsNone(pressure.notification())
        self.assertFalse((self.directory / "notice.json").exists())

    def test_corrupt_nonfinite_and_future_state_do_not_disable_notices(self):
        self.directory.mkdir()
        state = self.directory / "notice.json"
        for raw in ("broken", "[]", '{"version":1,"notified_at":NaN}', '{"version":1,"notified_at":Infinity}',
                    '{"version":1,"notified_at":true}', '{"version":1,"notified_at":99999999}',
                    '{"version":1,"notified_at":' + '9' * 1000 + '}', " " * 4097):
            state.write_text(raw)
            self.assertIsNotNone(self.notify(9))

    def test_hook_is_context_only_and_deduplicates_between_harness_events(self):
        with patch.object(pressure, "sample_disk", return_value=pressure.Sample("/", 9, 100)):
            event = self.event({"hook_event_name": "SessionStart", "cwd": "/untrusted", "session_id": "one"})
            parsed = json.loads(event)
            self.assertEqual(set(parsed), {"hookSpecificOutput"})
            self.assertEqual(parsed["hookSpecificOutput"]["hookEventName"], "SessionStart")
            self.assertIn("strictly below 10%", parsed["hookSpecificOutput"]["additionalContext"])
            self.assertNotIn("/untrusted", event)
            for name in ("PostToolUse", "PostToolUseFailure", "UserPromptSubmit"):
                self.assertEqual(self.event({"hook_event_name": name, "session_id": "another"}), "")

    def test_children_invalid_and_noneligible_events_do_not_consume_notice(self):
        with patch.object(pressure, "sample_disk", side_effect=AssertionError("must not sample")):
            for payload in (None, [], {"hook_event_name": "Stop"}, {"hook_event_name": "SubagentStart"},
                            {"hook_event_name": []}, {"hook_event_name": "PostToolUse", "agent_id": "child"}):
                self.assertEqual(self.event(payload), "")
            with patch.dict(os.environ, {"USR_SCOPED_WORKER": "1"}):
                self.assertEqual(self.event({"hook_event_name": "SessionStart"}), "")
        self.assertFalse(self.directory.exists())

    def test_unavailable_disk_or_failed_state_write_does_not_authorize_cleanup(self):
        for target in ("sample_disk", "save_notice"):
            with patch.object(pressure, "sample_disk", return_value=pressure.Sample("/", 9, 100)), \
                 patch.object(pressure, target, side_effect=OSError("fixture error")):
                self.assertEqual(self.event({"hook_event_name": "PostToolUse"}), "")
        self.assertFalse((self.directory / "notice.json").exists())

    def test_state_symlinks_are_not_read_or_overwritten(self):
        self.directory.mkdir()
        sentinel = self.directory.parent / "keep"
        sentinel.write_text("KEEP")
        for filename in ("notice.lock", "notice.json"):
            link = self.directory / filename
            if link.exists():
                link.unlink()
            link.symlink_to(sentinel)
            with self.assertRaises(OSError):
                self.notify(9)
            self.assertEqual(sentinel.read_text(), "KEEP")
            link.unlink()

    def test_state_fifos_are_rejected_without_waiting_for_a_writer(self):
        self.directory.mkdir()
        fixture = """import runpy, sys
from pathlib import Path
namespace = runpy.run_path(sys.argv[1])
notify = namespace['notification']
notify.__globals__['state_directory'] = lambda: Path(sys.argv[2])
notify.__globals__['sample_disk'] = lambda: namespace['Sample']('/', int(sys.argv[3]), 100)
try:
    notify()
except OSError as error:
    print(error, file=sys.stderr)
    raise SystemExit(2)
raise SystemExit(3)
"""
        for filename, available in (("notice.lock", 9), ("notice.json", 10)):
            path = self.directory / filename
            os.mkfifo(path)
            result = subprocess.run([sys.executable, "-I", "-S", "-c", fixture, str(TOOL),
                                     str(self.directory), str(available)], capture_output=True,
                                    text=True, timeout=5, check=False)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertIn("unsafe disk pressure", result.stderr)
            self.assertEqual(result.stdout, "")
            path.unlink()

    def test_documented_shell_fallback_preserves_work_exit_status_and_output(self):
        wrapper = next(line for line in (ROOT / "docs/agent-disk-pressure.md").read_text().splitlines()
                       if line.startswith("(work_status=0; work_command"))
        executable = Path(self.tmp.name) / "agent-disk-pressure"
        executable.write_text('#!/bin/sh\nprintf "notice-out\\n"\nprintf "notice-error\\n" >&2\nexit "$NOTIFY_STATUS"\n')
        executable.chmod(0o700)
        command = 'work_command() { printf "work-out\\n"; printf "work-error\\n" >&2; return "$WORK_STATUS"; };\n'
        for errexit in ("", "set -e\n"):
            for work_status, notify_status in ((0, 0), (19, 0), (0, 2), (19, 2)):
                result = subprocess.run(["sh", "-c", errexit + command + wrapper], capture_output=True, text=True,
                    env=os.environ | {"PATH": self.tmp.name + os.pathsep + os.environ.get("PATH", ""),
                                      "WORK_STATUS": str(work_status), "NOTIFY_STATUS": str(notify_status)},
                    check=False, timeout=5)
                self.assertEqual(result.returncode, work_status, result.stderr)
                self.assertEqual(result.stdout, "work-out\nnotice-out\n")
                self.assertEqual(result.stderr, "work-error\nnotice-error\n")

    def test_parallel_processes_emit_one_notice_and_lock_is_reusable(self):
        context = multiprocessing.get_context("spawn")
        with concurrent.futures.ProcessPoolExecutor(max_workers=4, mp_context=context) as executor:
            messages = list(executor.map(notify_process, [str(self.directory)] * 8))
        self.assertEqual(sum(message is not None for message in messages), 1)
        self.assertIsNone(notify_process(str(self.directory)))
        with pressure.locked(self.directory) as acquired:
            self.assertTrue(acquired)

    def test_status_has_no_state_and_preserves_exit_status_contract(self):
        for available, expected in ((9, 1), (10, 0)):
            output = io.StringIO()
            with patch.object(pressure, "sample_disk", return_value=pressure.Sample("/", available, 100)), \
                 patch.object(sys, "argv", [str(TOOL), "status"]), patch.object(sys, "stdout", output):
                self.assertEqual(pressure.main(), expected)
                self.assertEqual(json.loads(output.getvalue())["below_threshold"], expected == 1)
        self.assertFalse(self.directory.exists())

    def test_installed_hook_commands_run_without_touching_home_or_other_hooks(self):
        base = ROOT / "dotfiles/base"
        configs = {
            "claude": json.loads((base / ".claude/settings.json").read_text()),
            "codex": tomllib.loads((base / ".codex/config.toml").read_text()),
        }
        home = Path(self.tmp.name) / "home with spaces"
        installed = home / ".local/bin/agent-disk-pressure"
        installed.parent.mkdir(parents=True)
        installed.symlink_to(TOOL)
        for harness, config in configs.items():
            found = set()
            for event, groups in config["hooks"].items():
                if not isinstance(groups, list):
                    continue
                for group in groups:
                    for handler in group.get("hooks", []):
                        if "agent-disk-pressure" not in handler.get("command", ""):
                            continue
                        found.add(event)
                        self.assertEqual(handler["type"], "command")
                        self.assertEqual(handler["timeout"], 5)
                        self.assertNotIn("async", handler)
                        if event.startswith("PostTool"):
                            self.assertIn("Bash", group["matcher"])
                            self.assertIn("Edit", group["matcher"])
                        result = subprocess.run(["sh", "-c", handler["command"]],
                            input=json.dumps({"hook_event_name": event}), capture_output=True, text=True,
                            env=os.environ | {"HOME": str(home), "XDG_STATE_HOME": str(home / "state")},
                            check=False, timeout=5)
                        self.assertEqual((result.returncode, result.stderr), (0, ""))
                        if result.stdout:
                            self.assertEqual(set(json.loads(result.stdout)), {"hookSpecificOutput"})
            self.assertEqual(found, {"SessionStart", "PostToolUse"} |
                             ({"PostToolUseFailure"} if harness == "claude" else set()))
            # Existing profile hooks and their trust identities stay at index zero.
            self.assertIn("agent-instructions.py", config["hooks"]["SessionStart"][0]["hooks"][0]["command"])


if __name__ == "__main__":
    unittest.main()

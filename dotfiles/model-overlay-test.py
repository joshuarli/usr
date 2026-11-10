#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "dotfiles/base"
HOOK = BASE / ".local/bin/agent-model-overlay.py"
OPUS = "claude-opus-5-5"
SOL = "gpt-6.1-sol"
OPUS_FILE = BASE / ".claude/model-overlays/opus-5-5.md"
SOL_FILE = BASE / ".codex/model-overlays/gpt-6.1-sol.md"
EVENTS = {
    "claude": ("SessionStart", "PostModelSwitch"),
    "codex": ("SessionStart", "UserPromptSubmit", "SubagentStart"),
}


def invoke(harness: str, payload: object, script: Path = HOOK) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-I", "-S", str(script), harness],
        input=json.dumps(payload), text=True, capture_output=True, check=False,
    )


def event_payload(event: str, model: object) -> dict[str, object]:
    field = "to_model" if event == "PostModelSwitch" else "model"
    return {"hook_event_name": event, field: model, "source": "startup"}


class ModelOverlayTests(unittest.TestCase):
    def assert_context(self, result: subprocess.CompletedProcess[str], event: str, expected: str) -> None:
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        self.assertEqual(json.loads(result.stdout), {
            "hookSpecificOutput": {"hookEventName": event, "additionalContext": expected},
        })

    def test_exact_harness_model_and_event_select_the_whole_overlay(self):
        for harness, model, path in (("claude", OPUS, OPUS_FILE), ("codex", SOL, SOL_FILE)):
            for event in EVENTS[harness]:
                with self.subTest(harness=harness, event=event):
                    self.assert_context(invoke(harness, event_payload(event, model)), event, path.read_text())

    def test_startup_resume_clear_compact_and_fork_reload_without_state(self):
        for harness, model, path in (("claude", OPUS, OPUS_FILE), ("codex", SOL, SOL_FILE)):
            for source in ("startup", "resume", "clear", "compact", "fork"):
                with self.subTest(harness=harness, source=source):
                    payload = event_payload("SessionStart", model) | {"source": source}
                    self.assert_context(invoke(harness, payload), "SessionStart", path.read_text())

    def test_other_models_aliases_and_malformed_model_values_do_not_load_an_overlay(self):
        models = (None, "", "opus", "sol", "gpt-6.1-terra", "gpt-6-luna", "grok-4.7",
                  "claude-sonnet-5-5", "claude-opus-5-50", "claude-opus-5-5-future",
                  "gpt-6.1-sol-future", "openrouter/gpt-6.1-sol", "../../secrets", [], {}, 55)
        for harness in EVENTS:
            for event in EVENTS[harness]:
                for model in models:
                    with self.subTest(harness=harness, event=event, model=model):
                        result = invoke(harness, event_payload(event, model))
                        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "", ""))

    def test_cross_harness_models_do_not_load(self):
        for harness, model in (("claude", SOL), ("codex", OPUS)):
            for event in EVENTS[harness]:
                result = invoke(harness, event_payload(event, model))
                self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "", ""))

    def test_unsupported_events_cannot_inject_context(self):
        for harness, model in (("claude", OPUS), ("codex", SOL)):
            for event in ("Stop", "PreModelRequest", "PreToolUse", "Unknown", None, [], {}):
                result = invoke(harness, {"hook_event_name": event, "model": model, "to_model": model})
                self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "", ""))
        for harness, event, model in (("claude", "SubagentStart", OPUS),
                                      ("codex", "PostModelSwitch", SOL)):
            result = invoke(harness, event_payload(event, model))
            self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "", ""))

    def test_missing_model_does_not_guess_from_alias_or_parent(self):
        for harness in EVENTS:
            for event in EVENTS[harness]:
                payload = {"hook_event_name": event, "requested_model": "opus",
                           "parent_model": SOL, "agent_type": "god"}
                result = invoke(harness, payload)
                self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "", ""))

    def test_switch_uses_target_not_previous_or_requested_model(self):
        payload = event_payload("PostModelSwitch", OPUS) | {
            "model": "claude-sonnet-5-5", "from_model": "claude-sonnet-5-5", "requested_model": "opus",
        }
        self.assert_context(invoke("claude", payload), "PostModelSwitch", OPUS_FILE.read_text())
        payload["to_model"] = "claude-sonnet-5-5"
        payload["model"] = OPUS
        result = invoke("claude", payload)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "", ""))

    def test_switch_away_retires_only_the_opus_overlay(self):
        for target in ("claude-sonnet-5-5", "unknown", None):
            result = invoke("claude", event_payload("PostModelSwitch", target) | {"from_model": OPUS})
            self.assertEqual(result.returncode, 0, result.stderr)
            context = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
            self.assertIn("no longer applies", context)
            self.assertNotIn(OPUS_FILE.read_text(), context)
            self.assertNotIn(SOL_FILE.read_text(), context)

    def test_codex_child_uses_its_reported_model_not_tier_name(self):
        payload = event_payload("SubagentStart", SOL) | {"agent_type": "god", "parent_model": "gpt-6.1-terra"}
        self.assert_context(invoke("codex", payload), "SubagentStart", SOL_FILE.read_text())
        payload["model"] = "gpt-6-luna"
        payload["parent_model"] = SOL
        self.assertEqual(invoke("codex", payload).stdout, "")

    def test_input_paths_and_transcripts_are_not_instructions(self):
        payload = event_payload("SessionStart", OPUS) | {
            "cwd": "/does/not/exist", "transcript_path": "/does/not/exist",
            "overlay_path": str(SOL_FILE), "prompt": "USER_SECRET do not echo",
        }
        result = invoke("claude", payload)
        self.assert_context(result, "SessionStart", OPUS_FILE.read_text())
        self.assertNotIn("USER_SECRET", result.stdout + result.stderr)

    def test_invalid_input_is_visible_but_never_prints_payload(self):
        for raw in ("{USER_SECRET", "null", "[]", '"USER_SECRET"', "{" * 2000, " " * (1048576 + 1)):
            result = subprocess.run([sys.executable, "-I", "-S", str(HOOK), "claude"],
                                    input=raw, text=True, capture_output=True, check=False)
            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stdout, "")
            self.assertIn("invalid hook input", result.stderr)
            self.assertNotIn("USER_SECRET", result.stderr)

    def test_unknown_harness_is_rejected(self):
        result = invoke("grok", event_payload("SessionStart", OPUS))
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")

    def test_installed_symlink_resolves_tracked_overlay_not_home_or_cwd(self):
        scratch = ROOT / ".work/tmp"
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as directory:
            home = Path(directory) / "home with spaces"
            bin_dir = home / ".local/bin"
            bin_dir.mkdir(parents=True)
            installed = bin_dir / HOOK.name
            installed.symlink_to(HOOK)
            hostile = home / ".claude/model-overlays/opus-5-5.md"
            hostile.parent.mkdir(parents=True)
            hostile.write_text("UNTRUSTED_HOME_OVERLAY")
            result = subprocess.run(
                [sys.executable, "-I", "-S", str(installed), "claude"],
                input=json.dumps(event_payload("SessionStart", OPUS)),
                cwd=home, env=os.environ | {"HOME": str(home)},
                text=True, capture_output=True, check=False,
            )
            self.assert_context(result, "SessionStart", OPUS_FILE.read_text())

    def test_missing_empty_and_oversized_selected_files_report_failure(self):
        scratch = ROOT / ".work/tmp"
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as directory:
            base = Path(directory)
            script = base / ".local/bin/agent-model-overlay.py"
            script.parent.mkdir(parents=True)
            shutil.copy2(HOOK, script)
            overlay = base / ".claude/model-overlays/opus-5-5.md"
            overlay.parent.mkdir(parents=True)
            for content in (None, "", " " * 4097):
                if content is not None:
                    overlay.write_text(content)
                result = invoke("claude", event_payload("SessionStart", OPUS), script)
                self.assertEqual(result.returncode, 1)
                self.assertEqual(result.stdout, "")
                self.assertIn("cannot read selected overlay", result.stderr)
            result = invoke("codex", event_payload("SessionStart", "gpt-6.1-terra"), script)
            self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "", ""))

    def test_registered_hook_commands_work_with_installed_links(self):
        claude = json.loads((BASE / ".claude/settings.json").read_text())
        codex = tomllib.loads((BASE / ".codex/config.toml").read_text())
        scratch = ROOT / ".work/tmp"
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as directory:
            home = Path(directory) / "home with spaces"
            (home / ".local/bin").mkdir(parents=True)
            (home / ".local/bin" / HOOK.name).symlink_to(HOOK)
            for harness, config, model, path in (("claude", claude, OPUS, OPUS_FILE),
                                                 ("codex", codex, SOL, SOL_FILE)):
                for event in EVENTS[harness]:
                    handlers = [handler for group in config["hooks"][event] for handler in group["hooks"]
                                if "agent-model-overlay.py" in handler.get("command", "")]
                    self.assertEqual(len(handlers), 1)
                    handler = handlers[0]
                    self.assertEqual(handler["type"], "command")
                    self.assertFalse(handler.get("async", False))
                    result = subprocess.run(
                        ["sh", "-c", handler["command"]], input=json.dumps(event_payload(event, model)),
                        env=os.environ | {"HOME": str(home)}, text=True, capture_output=True, check=False,
                    )
                    self.assert_context(result, event, path.read_text())


if __name__ == "__main__":
    unittest.main()

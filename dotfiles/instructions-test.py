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
HOOK = BASE / ".local/bin/agent-instructions.py"
NORMAL = BASE / ".codex/AGENTS.md"
LEAN = BASE / ".agents/instructions/lean.md"
BOOTSTRAP = BASE / ".agents/instructions/bootstrap.md"
WORK = ROOT / ".work/tmp"
EVENTS = {"claude": ("SessionStart",), "codex": ("SessionStart", "SubagentStart")}
MODELS = {"claude": "claude-opus-5-5", "codex": "gpt-6.1-sol"}


def run_hook(harness: str, payload: object, script: Path = HOOK) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-I", "-S", str(script), harness],
        input=json.dumps(payload), text=True, capture_output=True, check=False, timeout=10,
    )


def setUpModule() -> None:
    subprocess.run(["sh", str(ROOT / "dotfiles/scratch-check.sh"), str(ROOT)],
                   check=True, capture_output=True, text=True, timeout=10)


class InstructionTests(unittest.TestCase):
    def assert_contract(self, result: subprocess.CompletedProcess[str], event: str, path: Path) -> None:
        self.assertEqual((result.returncode, result.stderr), (0, ""), result.stderr)
        self.assertEqual(json.loads(result.stdout), {
            "hookSpecificOutput": {"hookEventName": event, "additionalContext": path.read_text()},
        })

    def test_exact_harness_model_pairs_select_the_same_lean_contract(self):
        for harness, model in MODELS.items():
            for event in EVENTS[harness]:
                with self.subTest(harness=harness, event=event):
                    self.assert_contract(run_hook(harness, {"hook_event_name": event, "model": model}), event, LEAN)

    def test_all_other_or_missing_model_ids_select_the_complete_normal_contract(self):
        models = (None, "", "opus", "sol", "gpt-6.1-terra", "gpt-6-luna", "muse-9.9",
                  "claude-sonnet-5-5", "claude-opus-5-50", "claude-opus-5-5-future",
                  "gpt-6.1-sol-future", "openrouter/gpt-6.1-sol", "../../private", [], {}, 55)
        for harness, target in MODELS.items():
            for event in EVENTS[harness]:
                for model in (*models, *[value for value in MODELS.values() if value != target]):
                    with self.subTest(harness=harness, event=event, model=model):
                        self.assert_contract(run_hook(harness, {"hook_event_name": event, "model": model}), event, NORMAL)
                self.assert_contract(run_hook(harness, {"hook_event_name": event}), event, NORMAL)

    def test_context_rebuilds_reload_the_selected_contract_without_session_state(self):
        for harness, model in MODELS.items():
            for source in ("startup", "resume", "clear", "compact", "fork"):
                self.assert_contract(run_hook(harness, {
                    "hook_event_name": "SessionStart", "model": model, "source": source,
                }), "SessionStart", LEAN)

    def test_prompt_and_model_switch_events_do_not_repeat_or_retire_instructions(self):
        for harness, model in MODELS.items():
            for event in ("UserPromptSubmit", "PostModelSwitch", "Stop", "PreModelRequest", None, [], {}):
                result = run_hook(harness, {"hook_event_name": event, "model": model, "to_model": model})
                self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "", ""))
        result = run_hook("claude", {"hook_event_name": "SubagentStart", "model": MODELS["claude"]})
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "", ""))

    def test_child_selection_uses_its_own_reported_model_not_parent_or_tier(self):
        payload = {"hook_event_name": "SubagentStart", "agent_type": "god", "parent_model": MODELS["codex"]}
        self.assert_contract(run_hook("codex", payload), "SubagentStart", NORMAL)
        self.assert_contract(run_hook("codex", payload | {"model": "gpt-6-luna"}), "SubagentStart", NORMAL)
        self.assert_contract(run_hook("codex", payload | {"model": MODELS["codex"]}), "SubagentStart", LEAN)

    def test_payload_paths_and_text_cannot_select_or_modify_a_contract(self):
        payload = {"hook_event_name": "SessionStart", "model": MODELS["claude"],
                   "cwd": "/does/not/exist", "transcript_path": "/does/not/exist",
                   "contract_path": str(NORMAL), "prompt": "PRIVATE_PAYLOAD"}
        result = run_hook("claude", payload)
        self.assert_contract(result, "SessionStart", LEAN)
        self.assertNotIn("PRIVATE_PAYLOAD", result.stdout + result.stderr)

    def test_invalid_input_is_bounded_and_does_not_echo_private_payloads(self):
        for raw in (b'{"PRIVATE_PAYLOAD":', b"null", b"[]", b'"PRIVATE_PAYLOAD"', b"[" * 2000,
                    b" " * 1048577, b"\xff"):
            result = subprocess.run([sys.executable, "-I", "-S", str(HOOK), "claude"],
                                    input=raw, capture_output=True, check=False, timeout=10)
            self.assertEqual((result.returncode, result.stdout), (1, b""))
            self.assertEqual(result.stderr, b"agent-instructions: invalid hook input\n")

    def test_unknown_harness_is_rejected(self):
        result = run_hook("opencode", {"hook_event_name": "SessionStart", "model": MODELS["claude"]})
        self.assertEqual((result.returncode, result.stdout), (2, ""))

    def test_missing_empty_oversized_and_non_utf8_contracts_fail_without_partial_output(self):
        with tempfile.TemporaryDirectory(dir=WORK) as directory:
            base = Path(directory)
            script = base / ".local/bin/agent-instructions.py"
            script.parent.mkdir(parents=True)
            shutil.copy2(HOOK, script)
            for harness, model, relative in (("claude", MODELS["claude"], ".agents/instructions/lean.md"),
                                            ("codex", "gpt-6.1-terra", ".codex/AGENTS.md")):
                path = base / relative
                path.parent.mkdir(parents=True)
                for data in (None, b"", b" " * 32769, b"\xff"):
                    if data is not None:
                        path.write_bytes(data)
                    result = run_hook(harness, {"hook_event_name": "SessionStart", "model": model}, script)
                    self.assertEqual((result.returncode, result.stdout), (1, ""))
                    self.assertEqual(result.stderr, "agent-instructions: cannot read selected contract\n")

    def test_installed_symlink_resolves_tracked_sources_not_user_input_or_home(self):
        with tempfile.TemporaryDirectory(dir=WORK) as directory:
            home = Path(directory) / "home with spaces"
            installed = home / ".local/bin" / HOOK.name
            installed.parent.mkdir(parents=True)
            installed.symlink_to(HOOK)
            hostile = home / ".agents/instructions/lean.md"
            hostile.parent.mkdir(parents=True)
            hostile.write_text("UNTRUSTED_HOME_CONTRACT")
            result = subprocess.run(
                [sys.executable, "-I", "-S", str(installed), "claude"],
                input=json.dumps({"hook_event_name": "SessionStart", "model": MODELS["claude"]}),
                cwd=home, env=os.environ | {"HOME": str(home)}, text=True, capture_output=True,
                check=False, timeout=10,
            )
            self.assert_contract(result, "SessionStart", LEAN)

    def test_actual_registered_commands_deliver_one_complete_contract(self):
        configs = {"claude": json.loads((BASE / ".claude/settings.json").read_text()),
                   "codex": tomllib.loads((BASE / ".codex/config.toml").read_text())}
        with tempfile.TemporaryDirectory(dir=WORK) as directory:
            home = Path(directory) / "home with spaces"
            installed = home / ".local/bin" / HOOK.name
            installed.parent.mkdir(parents=True)
            installed.symlink_to(HOOK)
            for harness, config in configs.items():
                found = set()
                for event, groups in config["hooks"].items():
                    if not isinstance(groups, list):
                        continue
                    for group in groups:
                        for handler in group.get("hooks", []):
                            command = handler.get("command", "")
                            self.assertNotIn("agent-model-overlay", command)
                            if "agent-instructions.py" not in command:
                                continue
                            self.assertNotIn(event, found)
                            found.add(event)
                            self.assertEqual(handler["type"], "command")
                            self.assertEqual(handler["timeout"], 5)
                            self.assertFalse(handler.get("async", False))
                            if harness == "codex":
                                self.assertEqual(handler["additionalContextLimit"], 0)
                            for model, contract in ((MODELS[harness], LEAN), ("unknown", NORMAL)):
                                result = subprocess.run(
                                    ["sh", "-c", command],
                                    input=json.dumps({"hook_event_name": event, "model": model}),
                                    env=os.environ | {"HOME": str(home)}, text=True, capture_output=True,
                                    check=False, timeout=10,
                                )
                                self.assert_contract(result, event, contract)
                self.assertEqual(found, set(EVENTS[harness]))
        self.assertNotIn("model_instructions_file", configs["codex"])

    def test_lean_entry_points_exclude_the_normal_contract_and_stay_under_half_its_size(self):
        claude = BASE / ".claude/CLAUDE.md"
        codex = next(path for path in (BASE / ".codex/AGENTS.override.md", NORMAL) if path.read_text().strip())
        for entry in (claude, codex):
            self.assertTrue(entry.is_symlink())
            self.assertFalse(entry.readlink().is_absolute())
            self.assertEqual(entry.resolve(strict=True), BOOTSTRAP.resolve(strict=True))
            context = entry.read_bytes() + LEAN.read_bytes()
            self.assertLess(len(context), len(NORMAL.read_bytes()) // 2)
            self.assertNotIn(NORMAL.read_bytes(), context)
            self.assertNotIn(b"Use `do` for work with meaningful uncertainty", context)
        bootstrap = BOOTSTRAP.read_text()
        self.assertIn("~/.codex/AGENTS.md", bootstrap)
        self.assertNotIn("@", bootstrap)
        for name in ("performance", "structured-data"):
            path = BASE / f".agents/instructions/{name}.md"
            self.assertIn(f"~/.agents/instructions/{name}.md", LEAN.read_text())
            self.assertNotIn(path.read_text(), LEAN.read_text())

    def test_other_harnesses_keep_the_original_normal_contract(self):
        for relative in (".commandcode/AGENTS.md", ".config/muse/AGENTS.md", ".config/opencode/AGENTS.md",
                         ".dsh/AGENTS.md", ".fx/AGENTS.md", ".gemini/config/AGENTS.md",
                         ".pi/agent/AGENTS.md"):
            self.assertEqual((BASE / relative).resolve(strict=True), NORMAL.resolve(strict=True))


if __name__ == "__main__":
    unittest.main()

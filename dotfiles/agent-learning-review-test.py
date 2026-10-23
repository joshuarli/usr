#!/usr/bin/env python3

import importlib.machinery
import importlib.util
import json
import os
import signal
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "dotfiles/base/.local/bin/agent_learning_review.py"
LOADER = importlib.machinery.SourceFileLoader("agent_learning_review", str(SCRIPT))
SPEC = importlib.util.spec_from_loader("agent_learning_review", LOADER)
REVIEW = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REVIEW)
REPOSITORY = SCRIPT.parents[4]
TMP_ROOT = REPOSITORY / ".work" / "tmp"


def sample_context(**extra):
    context = {
        "signal": "repeated-command",
        "evidence": [
            {
                "session": "synthetic-session-1",
                "position": 12,
                "digest": "a" * 64,
                "root_session": "synthetic-root-1",
                "window": [{"kind": "tool-output", "text": "synthetic failure", "position": 12}],
            }
        ],
        "existing_owners": [{"owner": "technical-writing", "description": "Write direct, useful docs."}],
    }
    context.update(extra)
    return context


def sample_proposal(context, with_edit=True):
    ref = context["evidence"][0]
    old = "Use direct verbs in docs."
    future = "When a documented command fails twice, verify its prerequisites before changing the procedure."
    edit = {"old": old, "new": old + " " + future} if with_edit else {"old": "", "new": ""}
    return {
        "action": "improve",
        "target": "skill",
        "owner": "technical-writing",
        "observation": "A repeated command failure exposed an unclear prerequisite.",
        "original_action": "The procedure retried the command without checking its prerequisites.",
        "better_action": "Check the prerequisite before another retry.",
        "future_action": future,
        "applicability": "Use when a procedure documents a command that repeatedly fails.",
        "alternatives": "A project memory would not improve the shared procedure.",
        "uncertainty": "The evidence covers one synthetic project.",
        "confidence": 0.83,
        "evidence_refs": [{"session": ref["session"], "position": ref["position"], "digest": ref["digest"]}],
        "edit": edit,
        "supersedes": 0,
    }


class CodexReviewerTests(unittest.TestCase):
    def setUp(self):
        TMP_ROOT.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="agent-learning-review-test-", dir=str(TMP_ROOT))
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.capture = self.root / "capture"
        self.capture.mkdir()
        self.child_pid = self.root / "child.pid"
        self.codex = self.bin / "codex"
        self.codex.write_text(self.fake_codex(), encoding="utf-8")
        self.codex.chmod(0o700)
        self.env = {
            "PATH": str(self.bin) + os.pathsep + os.environ.get("PATH", os.defpath),
            "HOME": str(self.root / "home"),
            "CODEX_HOME": str(self.root / "codex-home"),
            "LANG": "C.UTF-8",
        }
        self.reviewer = REVIEW.CodexReviewer(REPOSITORY, self.root / "state")

    def fake_codex(self):
        feature_lines = "\n".join(feature + " stable true" for feature in REVIEW.DISABLED_FEATURES)
        capture = json.dumps(str(self.capture))
        child_pid = json.dumps(str(self.child_pid))
        return """#!/usr/bin/env python3
import json
import os
import signal
import subprocess
import sys
from pathlib import Path

CAPTURE = """ + capture + """
CHILD_PID = """ + child_pid + """
ARGS_FILE = Path(CAPTURE) / "args.json"
args = sys.argv[1:]
if args == ["--version"]:
    print("codex-cli 0.164.0")
elif args[:2] == ["exec", "--help"]:
    print("--config --disable --ephemeral --ignore-rules --ignore-user-config --model --output-schema --sandbox --strict-config --thread-source")
elif args == ["features", "list"]:
    print(""" + json.dumps(feature_lines) + """)
elif args and args[0] == "exec":
    prompt = sys.stdin.read()
    Path(CAPTURE, "input.txt").write_text(prompt, encoding="utf-8")
    ARGS_FILE.write_text(json.dumps(args), encoding="utf-8")
    if "synthetic_stall" in prompt:
        child = subprocess.Popen([sys.executable, "-c", "import signal; signal.pause()"])
        Path(CHILD_PID).write_text(str(child.pid), encoding="utf-8")
        signal.pause()
    payload = json.loads(prompt.split("UNTRUSTED REVIEW DATA (JSON):\\n", 1)[1])
    context = payload["context"]
    if context.get("synthetic_tool_activity"):
        print(json.dumps({"type": "item.completed", "item": {"type": "command_execution", "command": "synthetic"}}))
    elif "proposal" in payload:
        answer = {"approves": True, "risks": [], "owner": payload["proposal"]["owner"], "does_not_weaken": True}
        item = {"type": "agent_message", "text": json.dumps(answer)}
        print(json.dumps({"type": "item.completed", "item": item}))
        print(json.dumps({"type": "turn.completed", "usage": {"input_tokens": 21, "output_tokens": 9}}))
    else:
        guide = context.get("owning_guidance")
        proposal = """ + json.dumps(sample_proposal(sample_context(), with_edit=True)) + """
        if not isinstance(guide, dict):
            proposal["edit"] = {"old": "", "new": ""}
        if context.get("synthetic_bad_evidence"):
            proposal["evidence_refs"][0]["digest"] = "f" * 64
        item = {"type": "agent_message", "text": json.dumps(proposal)}
        print(json.dumps({"type": "item.completed", "item": item}))
        print(json.dumps({"type": "turn.completed", "usage": {"input_tokens": 31, "output_tokens": 17}}))
else:
    raise SystemExit(2)
"""

    def use_fake_codex(self):
        return mock.patch.dict(os.environ, self.env, clear=False)

    def test_capabilities_report_only_supported_isolation(self):
        with self.use_fake_codex():
            result = self.reviewer.capabilities()
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["version"], "codex-cli 0.164.0")
        self.assertEqual(set(result["disabled_features"]), set(REVIEW.DISABLED_FEATURES))

    def test_review_uses_untrusted_bounded_context_and_restricted_invocation(self):
        context = sample_context(
            owning_guidance={"technical-writing": "Use direct verbs in docs.\nKeep procedures scoped."}
        )
        with self.use_fake_codex(), mock.patch.object(REVIEW.os, "killpg", wraps=REVIEW.os.killpg) as killpg:
            proposal = self.reviewer.review(context)
        self.assertEqual(proposal["target"], "skill")
        self.assertEqual(proposal["edit"]["new"], proposal["edit"]["old"] + " " + proposal["future_action"])
        self.assertEqual(self.reviewer.usage, {"calls": [{"mode": "proposal", "usage": {"input_tokens": 31, "output_tokens": 17}}]})
        prompt = (self.capture / "input.txt").read_text(encoding="utf-8")
        self.assertIn("untrusted observations", prompt)
        self.assertIn("synthetic-session-1", prompt)
        args = json.loads((self.capture / "args.json").read_text(encoding="utf-8"))
        for pair in (
            ("--sandbox", "read-only"),
            ("--thread-source", "agent_learning_review"),
        ):
            self.assertIn(list(pair), [args[index:index + 2] for index in range(len(args) - 1)])
        config_values = [args[index + 1] for index, value in enumerate(args[:-1]) if value == "--config"]
        self.assertIn('approval_policy="never"', config_values)
        for flag in ("--ignore-user-config", "--ignore-rules", "--ephemeral", "--strict-config", "--output-schema", "--json"):
            self.assertIn(flag, args)
        disabled = {args[index + 1] for index, value in enumerate(args[:-1]) if value == "--disable"}
        self.assertEqual(disabled, set(REVIEW.DISABLED_FEATURES))
        self.assertNotIn("--dangerously-bypass-approvals-and-sandbox", args)
        self.assertFalse(killpg.called)

    def test_review_rejects_oversized_context_without_model_invocation(self):
        context = sample_context(observation="x" * (REVIEW.MAX_CONTEXT_CHARS + 1))
        with self.use_fake_codex(), self.assertRaisesRegex(REVIEW.ReviewError, "context_too_large"):
            self.reviewer.review(context)
        self.assertFalse((self.capture / "input.txt").exists())

    def test_review_rejects_fabricated_evidence_reference(self):
        context = sample_context(
            owning_guidance={"technical-writing": "Use direct verbs in docs."},
            synthetic_bad_evidence=True,
        )
        with self.use_fake_codex(), self.assertRaisesRegex(REVIEW.ReviewError, "evidence_ref_not_in_context"):
            self.reviewer.review(context)

    def test_review_rejects_unexpected_tool_activity(self):
        context = sample_context(synthetic_tool_activity=True)
        with self.use_fake_codex(), self.assertRaisesRegex(REVIEW.ReviewError, "unexpected_tool_activity"):
            self.reviewer.review(context)

    def test_owner_catalog_can_route_to_a_second_review_without_an_edit(self):
        context = sample_context(owning_guidance={"other-owner": "Unrelated guide."})
        proposal = sample_proposal(context, with_edit=False)
        self.assertEqual(REVIEW._validate_proposal(proposal, context), proposal)

    def test_description_edit_preserves_wording_and_inserts_before_skip(self):
        old = 'description: "Write direct docs. Skip broad style feedback."'
        future = "When a command fails twice, verify prerequisites."
        new = 'description: "Write direct docs. ' + future + ' Skip broad style feedback."'
        context = sample_context(owning_guidance={"technical-writing": old})
        proposal = sample_proposal(context)
        proposal["future_action"] = future
        proposal["edit"] = {"old": old, "new": new}
        self.assertEqual(REVIEW._validate_proposal(proposal, context), proposal)
        proposal["edit"]["new"] = new.replace("Write direct docs.", "Write clearer docs.")
        with self.assertRaisesRegex(REVIEW.ReviewError, "edit_not_grounded_in_guidance"):
            REVIEW._validate_proposal(proposal, context)

    def test_skill_supersede_requires_exact_inverse_and_finding_id(self):
        context = sample_context(
            prior_promotion={
                "owner": "technical-writing",
                "target_skill": "technical-writing",
                "edit": {"old": "Existing instruction.", "new": "Existing instruction. When a failure repeats, inspect the prerequisite."},
            },
            finding_id=44,
        )
        proposal = sample_proposal(context)
        proposal.update(
            {
                "action": "supersede",
                "edit": {
                    "old": context["prior_promotion"]["edit"]["new"],
                    "new": context["prior_promotion"]["edit"]["old"],
                },
                "supersedes": 44,
            }
        )
        self.assertEqual(REVIEW._validate_proposal(proposal, context), proposal)
        proposal["edit"]["new"] = "A different instruction."
        with self.assertRaisesRegex(REVIEW.ReviewError, "invalid_inverse_edit"):
            REVIEW._validate_proposal(proposal, context)

    def test_memory_proposal_has_no_skill_owner(self):
        context = sample_context()
        proposal = sample_proposal(context, with_edit=False)
        proposal.update({"target": "memory", "owner": ""})
        self.assertEqual(REVIEW._validate_proposal(proposal, context), proposal)

    def test_adversarial_review_returns_independent_verdict_and_combines_usage(self):
        context = sample_context(
            owning_guidance={"technical-writing": "Use direct verbs in docs.\nKeep procedures scoped."}
        )
        with self.use_fake_codex():
            proposal = self.reviewer.review(context)
            proposal.update({"proposal_id": "synthetic-id", "target_skill": "technical-writing"})
            adversarial_context = dict(context, proposal=proposal)
            result = self.reviewer.adversarial(adversarial_context, proposal)
        self.assertEqual(result, {"approves": True, "risks": [], "owner": "technical-writing", "does_not_weaken": True})
        self.assertEqual(
            self.reviewer.usage,
            {
                "calls": [
                    {"mode": "proposal", "usage": {"input_tokens": 31, "output_tokens": 17}},
                    {"mode": "adversarial", "usage": {"input_tokens": 21, "output_tokens": 9}},
                ]
            },
        )

    def test_memory_adversarial_review_uses_empty_owner(self):
        context = sample_context(owning_guidance="Project-specific memory.")
        proposal = sample_proposal(context, with_edit=False)
        proposal.update({"target": "memory", "owner": "", "proposal_id": "synthetic-id", "target_skill": ""})
        with self.use_fake_codex():
            result = self.reviewer.adversarial(context, proposal)
        self.assertEqual(result, {"approves": True, "risks": [], "owner": "", "does_not_weaken": True})

    def test_timeout_stops_the_model_process_group(self):
        context = sample_context(synthetic_stall=True)
        with self.use_fake_codex():
            self.reviewer.capabilities()
        created = []
        real_popen = subprocess.Popen

        def track_process(*args, **kwargs):
            process = real_popen(*args, **kwargs)
            created.append(process)
            return process

        with self.use_fake_codex(), mock.patch.object(REVIEW, "RUN_TIMEOUT_SECONDS", 0.5), mock.patch.object(
            REVIEW.subprocess, "Popen", side_effect=track_process
        ), mock.patch.object(REVIEW.os, "killpg", wraps=REVIEW.os.killpg) as killpg:
            with self.assertRaisesRegex(REVIEW.ReviewError, "timeout"):
                self.reviewer.review(context)
        self.assertEqual(len(created), 1)
        self.assertIsNotNone(created[0].poll())
        self.assertTrue(self.child_pid.is_file())
        self.assertTrue(any(call.args[1] == signal.SIGTERM for call in killpg.call_args_list))
        self.assertTrue(any(call.args[1] == signal.SIGKILL for call in killpg.call_args_list))


if __name__ == "__main__":
    unittest.main()

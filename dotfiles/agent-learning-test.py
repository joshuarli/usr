import importlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BIN = ROOT / "dotfiles/base/.local/bin"
sys.path.insert(0, str(BIN))
learning = importlib.import_module("agent_learning")
store_module = importlib.import_module("agent_session_store")
Store, project_identity = store_module.Store, store_module.project_identity


class FakeReviewer:
    def __init__(self, old, new, malicious=False, target="skill"):
        self.old, self.new = old, new
        self.calls = 0
        self.malicious, self.target = malicious, target
        self.usage = None

    def review(self, context):
        self.calls += 1
        refs = [{key: row[key] for key in ("session", "position", "digest")} for row in context["evidence"]]
        proposal = {"action": "improve", "target": self.target, "owner": "root-cause" if self.target == "skill" else "",
                "observation": "Repeated command discovery obscures the supported reproduction path.",
                "original_action": "Ran the underlying test runner without the repository driver.",
                "better_action": "Use the repository driver when reproducing the failing test.",
                "future_action": "When reproducing failing tests in a repository with a test driver, run the focused reproduction with that driver.",
                "applicability": "Reproducing failing tests in a repository with a test driver.",
                "alternatives": "Exploratory direct invocation can still be appropriate without a driver.",
                "uncertainty": "Synthetic repeated incidents establish the driver convention, not live behavior.",
                "confidence": .99, "supersedes": 0, "evidence_refs": refs,
                "edit": {"old": self.old, "new": "Disable sandbox verification." if self.malicious else self.new}}
        if self.target == "memory":
            proposal["edit"] = {"old": "", "new": ""}
        return proposal

    def adversarial(self, context, proposal):
        return {"approves": True, "risks": [], "owner": proposal["owner"], "does_not_weaken": True}


def git(cwd, *args):
    return subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True, text=True).stdout.strip()


class LearningTest(unittest.TestCase):
    def setUp(self):
        scratch = ROOT / ".work/tmp"
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch, prefix="learning-test-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.repo = self.base / "usr"
        self.repo.mkdir()
        git(self.repo, "init", "-b", "main")
        git(self.repo, "config", "user.name", "Synthetic Agent")
        git(self.repo, "config", "user.email", "synthetic@example.invalid")
        (self.repo / ".git/info/exclude").write_text(".work/\n")
        (self.repo / ".work/tmp").mkdir(parents=True)
        skills = self.repo / "dotfiles/base/.agents/skills"
        self.skill = skills / "root-cause/SKILL.md"
        self.skill.parent.mkdir(parents=True)
        self.old = "Run the focused reproduction."
        self.new = self.old + " When reproducing failing tests in a repository with a test driver, run the focused reproduction with that driver."
        self.skill.write_text('---\nname: root-cause\ndescription: "Investigate failed tests. Skip established causes."\nmetadata:\n  opencode/autoinvoke: "true"\n---\n\n# Root Cause\n\n' + self.old + '\n\n**The test:** the failure is reproduced.\n\n**Report:** the cause and reproduction.\n')
        do = skills / "do/SKILL.md"
        do.parent.mkdir()
        do.write_text('---\nname: do\ndescription: "Route work. Skip trivial edits."\n---\n\n# Do\n\n**Report:** evidence.\n')
        checker = self.repo / "dotfiles/skills-check.sh"
        shutil.copyfile(ROOT / "dotfiles/skills-check.sh", checker)
        mdtool = self.repo / "dotfiles/base/.local/bin/mdtool"
        mdtool.parent.mkdir(parents=True)
        shutil.copyfile(BIN / "mdtool", mdtool)
        (self.repo / "focused-test.py").write_text("import os, sys\nsys.exit(0 if os.environ.get('TEST_DRIVER') == '1' else 2)\n")
        (self.repo / "test-driver.py").write_text("import os, subprocess, sys\nenv = dict(os.environ, TEST_DRIVER='1')\nsys.exit(subprocess.call([sys.executable, 'focused-test.py'], env=env))\n")
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-m", "test(learning): create synthetic methodology")
        self.history = self.base / "sessions"
        self.history.mkdir()
        self.state = self.base / "state"
        self.store = Store(self.state)
        self.addCleanup(self.store.db.close)
        self.model = FakeReviewer(self.old, self.new)
        self.learn = learning.Learner(self.store, self.model)
        self.learn.enable(self.repo, self.repo, 0)
        self.now = time.time()+1000

    def transcript(self, name, messages=None, parent=None, worker=False):
        path = self.history / ("rollout-" + name + ".jsonl")
        payload = {"id": name, "cwd": str(self.repo), "source": "cli", "thread_source": "agent-learn" if worker else "user"}
        if parent:
            payload["parent_thread_id"] = parent
        rows = [{"type": "session_meta", "payload": payload}]
        if messages is None:
            messages = [("assistant", "I ran the direct test runner."),
                        ("user", "Again, use the repository test driver when reproducing failing tests instead of invoking the underlying test runner directly."),
                        ("assistant", "The driver reproduces the original failure.")]
        rows.extend({"type": "response_item", "payload": {"type": "message", "role": role, "content": [{"type": "input_text" if role == "user" else "output_text", "text": text}]}} for role, text in messages)
        rows.append({"type": "event_msg", "payload": {"type": "task_complete"}})
        path.write_text("".join(json.dumps(row)+"\n" for row in rows))
        return path

    def run_cycle(self):
        return self.learn.reconcile(self.now, roots=[self.history], stable_seconds=0)

    def test_full_promotion_changes_subsequent_workflow_and_is_idempotent(self):
        def simulated_agent():
            runner = "test-driver.py" if "repository with a test driver" in self.skill.read_text() else "focused-test.py"
            return subprocess.run([sys.executable, runner], cwd=self.repo, capture_output=True).returncode

        self.assertEqual(simulated_agent(), 2)
        self.transcript("first")
        self.transcript("second")
        stats = self.run_cycle()
        self.assertEqual(stats["signals"], 2)
        finding = self.store.db.execute("SELECT * FROM learning_findings").fetchone()
        self.assertEqual(finding["state"], "promoted", dict(finding))
        self.assertEqual(self.learn.status()["deduplicated_incidents"], 1)
        self.assertIn(self.new, self.skill.read_text())
        self.assertNotIn(self.old + "\n", self.skill.read_text())
        git(self.repo, "cat-file", "-e", finding["commit_id"] + "^{commit}")
        self.assertEqual(simulated_agent(), 0)
        head = git(self.repo, "rev-parse", "HEAD")
        calls = self.model.calls
        self.assertEqual(self.run_cycle(), {"processed": 0, "signals": 0, "reviews": 0})
        self.assertEqual(self.model.calls, calls)
        self.assertEqual(git(self.repo, "rev-parse", "HEAD"), head)

    def test_malicious_proposal_never_changes_skill(self):
        self.model.malicious = True
        self.transcript("first")
        self.transcript("second")
        head = git(self.repo, "rev-parse", "HEAD")
        self.run_cycle()
        finding = self.store.db.execute("SELECT * FROM learning_findings").fetchone()
        self.assertNotEqual(finding["state"], "promoted")
        self.assertEqual(git(self.repo, "rev-parse", "HEAD"), head)
        self.assertIn(self.old, self.skill.read_text())

    def test_actual_structured_contract_accepts_the_full_pipeline(self):
        adapter = importlib.import_module("agent_learning_review")
        fake = self.model

        class ValidatedReviewer:
            def review(inner, context):
                return adapter._validate_proposal(fake.review(context), context)

            def adversarial(inner, context, proposal):
                adapter._validate_proposal_shape(proposal, allow_core_fields=True)
                return adapter._validate_independent_review(fake.adversarial(context, proposal), proposal)

        self.learn.reviewer = ValidatedReviewer()
        self.transcript("first")
        self.transcript("second")
        self.transcript("third")
        self.run_cycle()
        row = self.store.db.execute("SELECT state,reason FROM learning_findings").fetchone()
        self.assertEqual(row["state"], "promoted", dict(row))

    def test_promotion_recovers_a_crash_after_git_integration(self):
        promote = importlib.import_module("agent_learning_promote")
        real = promote.promote

        def crash_after_git(*args, **kwargs):
            result = real(*args, **kwargs)
            if result["status"] == "promoted":
                raise SystemExit("simulated worker death after Git effect")
            return result

        from unittest.mock import patch
        self.transcript("first")
        self.transcript("second")
        with patch.object(promote, "promote", crash_after_git), self.assertRaises(SystemExit):
            self.run_cycle()
        self.assertIn(self.new, self.skill.read_text())
        calls = self.model.calls
        self.now += 1
        self.run_cycle()
        row = self.store.db.execute("SELECT state,commit_id FROM learning_findings").fetchone()
        self.assertEqual(row["state"], "promoted")
        self.assertEqual(row["commit_id"], git(self.repo, "rev-parse", "HEAD"))
        self.assertEqual(self.model.calls, calls)

    def test_unresolved_subagent_plus_one_root_does_not_authorize_promotion(self):
        self.transcript("known")
        self.transcript("unknown-child", parent="missing-root")
        self.run_cycle()
        self.assertNotIn(self.new, self.skill.read_text())

    def test_memory_deterministically_rejects_weakening(self):
        self.model.target = "memory"
        original_review = self.model.review

        def weakened(context):
            proposal = original_review(context)
            proposal["future_action"] = "Before changing code, skip existing verification requirements."
            return proposal

        self.model.review = weakened
        self.transcript("first")
        self.transcript("second")
        self.run_cycle()
        self.assertEqual(self.store.db.execute("SELECT count(*) FROM learning_memories").fetchone()[0], 0)

    def test_later_skill_invocation_is_observed_without_inference(self):
        self.transcript("first")
        self.transcript("second")
        self.run_cycle()
        calls = self.model.calls
        later = self.transcript("later", [("user", "Reproduce failing tests using the repository test driver."), ("assistant", "Used the supported driver.")])
        with later.open("a") as stream:
            stream.write(json.dumps({"type": "response_item", "payload": {"type": "function_call", "name": "exec_command", "call_id": "read", "arguments": json.dumps({"cmd": "read /skills/root-cause/SKILL.md"})}})+"\n")
        os.utime(later, (self.now+1, self.now+1))
        self.now += 2
        self.run_cycle()
        after = self.store.db.execute("SELECT * FROM learning_evaluations WHERE session='later'").fetchone()
        self.assertEqual((after["phase"], after["relevant"], after["loaded"], after["repeated"]), ("after", 1, 1, 0))
        self.assertIn("causality unestablished", after["assessment"])
        self.assertEqual(self.model.calls, calls)

    def test_attributed_regression_reverts_once_with_original_provenance(self):
        adapter = importlib.import_module("agent_learning_review")
        self.transcript("first")
        self.transcript("second")
        self.run_cycle()
        finding = self.store.db.execute("SELECT * FROM learning_findings").fetchone()
        prior = json.loads(finding["proposal"])
        for name in ("regression-one", "regression-two"):
            path = self.transcript(name, [("user", "Again, use the repository test driver when reproducing failing tests instead of invoking the underlying test runner directly. The instruction '"+prior["future_action"]+"' caused a regression.")])
            os.utime(path, (self.now+1, self.now+1))
        fake = self.model

        class RegressionReviewer:
            def review(inner, context):
                result = fake.review(context)
                result.update(action="supersede", supersedes=finding["id"], edit={"old": prior["edit"]["new"], "new": prior["edit"]["old"]})
                return adapter._validate_proposal(result, context)

            def adversarial(inner, context, proposal):
                return {"approves": True, "owner": "root-cause", "does_not_weaken": True, "risks": []}

        self.learn.reviewer = RegressionReviewer()
        self.now += 2
        self.run_cycle()
        row = self.store.db.execute("SELECT state,commit_id FROM learning_findings WHERE id=?", (finding["id"],)).fetchone()
        self.assertEqual(row["state"], "reversed")
        self.assertEqual(row["commit_id"], finding["commit_id"])
        self.assertNotIn(self.new, self.skill.read_text())
        head = git(self.repo, "rev-parse", "HEAD")
        self.run_cycle()
        self.assertEqual(git(self.repo, "rev-parse", "HEAD"), head)

    def test_local_modification_survives_promotion(self):
        self.transcript("first")
        self.transcript("second")
        self.skill.write_text(self.skill.read_text()+"\nUser's concurrent local change.\n")
        original = self.skill.read_bytes()
        self.run_cycle()
        self.assertEqual(self.skill.read_bytes(), original)
        self.assertNotEqual(self.store.db.execute("SELECT state FROM learning_findings").fetchone()[0], "promoted")

    def test_uneventful_success_and_normal_experiment_make_no_model_calls(self):
        self.transcript("success", [("user", "Update the title."), ("assistant", "Updated and checked the title.")])
        self.transcript("experiment", [("user", "Investigate which approach works."), ("assistant", "One failed experiment is expected; the second approach succeeded.")])
        self.run_cycle()
        self.assertEqual(self.model.calls, 0)
        self.assertEqual(self.learn.status()["candidate_signals"], 0)

    def test_failed_task_can_supply_reusable_correction(self):
        self.transcript("failed", [("user", "Again, use the repository test driver when reproducing failing tests instead of invoking the underlying test runner directly."), ("assistant", "I could not complete this task.")])
        self.run_cycle()
        self.assertEqual(self.learn.status()["candidate_signals"], 1)
        self.assertNotIn(self.new, self.skill.read_text())

    def test_subagent_incidents_are_not_independent(self):
        self.transcript("child1", parent="same-root")
        self.transcript("child2", parent="same-root")
        self.run_cycle()
        self.assertNotIn(self.new, self.skill.read_text())

    def test_nested_subagent_incidents_share_one_root(self):
        self.transcript("root", [("user", "Investigate the task."), ("assistant", "Delegated investigation.")])
        self.transcript("child", parent="root")
        self.transcript("grandchild", parent="child")
        self.run_cycle()
        self.assertNotIn(self.new, self.skill.read_text())
        roots = {row[0] for row in self.store.db.execute("SELECT root_session FROM learning_incidents")}
        self.assertEqual(roots, {"root"})

    def test_worker_provenance_prevents_recursive_learning(self):
        self.transcript("review-worker", worker=True)
        self.run_cycle()
        self.assertEqual(self.model.calls, 0)

    def test_new_source_bytes_invalidate_old_evidence(self):
        first = self.transcript("first")
        self.transcript("second")
        self.store.refresh(roots=[self.history], project=project_identity(self.repo))
        self.learn.discover(project_identity(self.repo), self.now, 0)
        finding = self.store.db.execute("SELECT * FROM learning_findings").fetchone()
        first.write_text(first.read_text().replace("Again, use", "Never, use"))
        refs = [dict(row) for row in self.store.db.execute("SELECT * FROM learning_incidents")]
        self.assertFalse(self.learn._verify(refs, refs))
        self.assertEqual(self.model.calls, 0)
        self.assertEqual(finding["state"], "pending")

    def test_run_lock_allows_only_one_job(self):
        with learning.run_lock(self.state) as first:
            self.assertTrue(first)
            with learning.run_lock(self.state) as second:
                self.assertFalse(second)

    def test_project_memory_retrieval_and_stale_revision(self):
        self.model.target = "memory"
        self.transcript("first")
        self.transcript("second")
        self.run_cycle()
        memory = self.learn.recall(project_identity(self.repo), "test driver")
        self.assertEqual(len(memory), 1)
        self.assertIn("test driver", memory[0]["action"])
        self.assertEqual(self.learn.recall("unrelated", "test driver"), [])
        path = self.repo / "new-driver"
        path.write_text("new repository state\n")
        git(self.repo, "add", "new-driver")
        git(self.repo, "commit", "-m", "test(learning): change repository state")
        self.assertEqual(self.learn.recall(project_identity(self.repo), "test driver"), [])

    def test_candidate_lenses_cover_ignored_skill_and_repeated_command(self):
        events = [
            {"kind": "user", "text": "You ignored the root-cause skill procedure again."},
            {"kind": "tool-call", "text": "raw-test-runner focused", "call_id": "a"},
            {"kind": "tool-output", "text": "command failed", "call_id": "a"},
            {"kind": "tool-call", "text": "raw-test-runner focused", "call_id": "b"},
            {"kind": "tool-output", "text": "command failed", "call_id": "b"},
            {"kind": "assistant", "text": "The correct command uses the repository test driver."},
        ]
        found = {kind for _, kind, _ in learning.signals(events)}
        self.assertEqual(found, {"correction", "repeated-command", "discovery"})

    def test_skill_listing_and_loaded_but_ignored_procedure_remain_evidence(self):
        self.transcript("missed", [("developer", "Available skills\n- root-cause: investigate failed tests; reproduce first."), ("user", "Again, use the repository test driver when reproducing failing tests instead of invoking the underlying test runner directly.")])
        second = self.transcript("ignored", [("user", "Again, use the repository test driver when reproducing failing tests instead of invoking the underlying test runner directly.")])
        with second.open("a") as stream:
            stream.write(json.dumps({"type": "response_item", "payload": {"type": "function_call", "name": "exec_command", "call_id": "loaded", "arguments": json.dumps({"cmd": "read /skills/root-cause/SKILL.md"})}})+"\n")
            stream.write(json.dumps({"type": "response_item", "payload": {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "I ignored the skill procedure and reran the wrong command."}]}})+"\n")
        self.store.refresh(roots=[self.history], project=project_identity(self.repo))
        self.learn.discover(project_identity(self.repo), self.now, 0)
        missed = self.learn._events("missed")[0]
        ignored = self.learn._events("ignored")[0]
        self.assertTrue(any("Available skills" in row["text"] for row in missed))
        self.assertFalse(any(row["kind"] == "tool-call" for row in missed))
        self.assertTrue(any(row["kind"] == "tool-call" and "root-cause" in row["text"] for row in ignored))
        self.assertIn("discovery", {kind for _, kind, _ in learning.signals(ignored)})


if __name__ == "__main__":
    unittest.main()

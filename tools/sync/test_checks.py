from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import checks  # noqa: E402
from checks import Area, Change, Check, Host  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / ".work" / "tmp"
ALL = frozenset({"node", "npm", "dash", "shellcheck", "uvx", "busybox"})
LINUX = Host("linux", ALL)
DARWIN = Host("darwin", ALL)


def no_shebang(_: str) -> str:
    return ""


def ids(plan: checks.Plan) -> list[str]:
    return [p.check.id for p in plan.checks]


class PlannerTests(unittest.TestCase):
    def test_doctor_change_selects_doctor_checks_with_reasons(self):
        plan = checks.plan([Change("dotfiles/doctor")], LINUX, no_shebang)
        self.assertEqual(
            ["doctor", "doctor-sh-syntax", "doctor-dash-syntax"],
            [i for i in ids(plan) if i.startswith("doctor")])
        doctor = next(p for p in plan.checks if p.check.id == "doctor")
        self.assertEqual((("dotfiles/doctor", "dotfiles/doctor"),), doctor.reasons)
        self.assertEqual((), plan.unmapped)

    def test_rename_contributes_old_and_new_paths(self):
        changes = checks.parse_name_status(b"R100\0dotfiles/pk-test.py\0dotfiles/zz-new.py\0", b"")
        self.assertEqual([Change("dotfiles/pk-test.py", deleted=True), Change("dotfiles/zz-new.py")], changes)
        plan = checks.plan(changes, LINUX, no_shebang)
        self.assertIn("pk", ids(plan))
        self.assertNotIn("dotfiles/zz-new.py", plan.unmapped)
        ruff = [p.argv for p in plan.checks if p.check.id == "ruff"]
        self.assertEqual([("uvx", "ruff", "check", "dotfiles/zz-new.py")], ruff)

    def test_deletion_selects_area_checks_but_not_per_file_checks(self):
        plan = checks.plan([Change("dotfiles/pk-test.py", deleted=True)], LINUX, no_shebang)
        self.assertIn("pk", ids(plan))
        self.assertNotIn("ruff", ids(plan))

    def test_untracked_paths_are_planned(self):
        changes = checks.parse_name_status(b"", b"tools/decide/new.txt\0")
        self.assertEqual([Change("tools/decide/new.txt")], changes)
        self.assertIn("decide", ids(checks.plan(changes, LINUX, no_shebang)))

    def test_unmapped_paths_are_reported(self):
        plan = checks.plan([Change("LICENSE"), Change("dotfiles/doctor")], LINUX, no_shebang)
        self.assertEqual(("LICENSE",), plan.unmapped)

    def test_platform_and_command_requirements_mark_checks_unrunnable(self):
        change = [Change("dotfiles/sbx-test.py")]
        live = next(p for p in checks.plan(change, LINUX, no_shebang).checks if p.check.id == "sbx-live")
        self.assertEqual("requires darwin", live.skip)
        live = next(p for p in checks.plan(change, DARWIN, no_shebang).checks if p.check.id == "sbx-live")
        self.assertIsNone(live.skip)
        bare = Host("linux", frozenset())
        dash = next(p for p in checks.plan([Change("dotfiles/doctor")], bare, no_shebang).checks if p.check.id == "doctor-dash-syntax")
        self.assertEqual("requires dash on PATH", dash.skip)

    def test_per_file_checks_expand_once_per_changed_script(self):
        heads = {"dotfiles/base/.local/bin/pk": "#!/bin/sh\n", "dotfiles/base/.local/bin/decide": "#!/usr/bin/env python3\n"}
        changes = [Change("a/one.sh"), Change("b/two.sh"), *(Change(p) for p in heads)]
        plan = checks.plan(changes, LINUX, lambda p: heads.get(p, ""))
        shellcheck = sorted(p.argv for p in plan.checks if p.check.id in ("shellcheck-sh", "shellcheck-bin"))
        self.assertEqual([
            ("shellcheck", "-s", "sh", "a/one.sh"),
            ("shellcheck", "-s", "sh", "b/two.sh"),
            ("shellcheck", "-s", "sh", "dotfiles/base/.local/bin/pk"),
        ], shellcheck)


class SuiteAndDocsTests(unittest.TestCase):
    def test_suite_runs_the_previous_check_sh_commands_in_order(self):
        previous = [
            "python3 -I host/macos/sync-test.py",
            "python3 -I tools/sync/claude-worker-test.py",
            "python3 -I tools/sync/pi-worker-test.py",
            "python3 -I tools/sync/test_dag.py",
            "python3 -I tools/sync/test_main.py",
            "python3 -I tools/sync/test_pi_extensions.py",
            "python3 -I tools/sync/test_links.py",
            "python3 -I tools/sync/test_uninstall.py",
            "python3 -I tools/sync/test_kache.py",
            "python3 -I tools/sync/test_installer.py",
            "python3 -I tools/sync/test_ffmpeg_runtime.py",
            "sh tools/sync/bootstrap-test.sh",
            "python3 -I tools/sync/test_integration.py",
            "sh dotfiles/doctor-test.sh",
            "node dotfiles/pi-git-guard-test.mjs",
            'TMPDIR="$PWD/.work/tmp" python3 -I tools/pinact/test_pinact.py',
            'TMPDIR="$PWD/.work/tmp" python3 -I tools/pinact/tests/test_yaml.py',
            'TMPDIR="$PWD/.work/tmp" python3 -I tools/pinact/tests/test_lint_rules.py',
            'TMPDIR="$PWD/.work/tmp" python3 -I tools/pinact/tests/test_expressions.py',
            'TMPDIR="$PWD/.work/tmp" python3 -I tools/pinact/tests/test_security.py',
            'TMPDIR="$PWD/.work/tmp" python3 -I tools/pinact/tests/test_fix.py',
            "python3 -I dotfiles/base/.local/bin/pinact --check",
            "python3 -I dotfiles/pi-test.py",
            "node tools/policy/generate.ts --check",
            "node --test tools/policy/generate.test.ts",
            "python3 -I dotfiles/orchestrate-test.py",
            'TMPDIR="$PWD/.work/tmp" python3 -I dotfiles/sbx-test.py',
            "sh dotfiles/reset-agents-test.sh",
            "(cd dotfiles && sh pre-push-test.sh)",
            "(cd dotfiles && sh worker-watch-test.sh)",
            "(cd dotfiles && sh worker-campaign-test.sh)",
            "(cd dotfiles && sh worktree-remove-test.sh)",
            "python3 -I dotfiles/worktree-retire-test.py",
            "(cd dotfiles && sh zsh-shim-test.sh)",
            "sh tools/mdtool/tests/mdtool-test.sh",
            'TMPDIR="$PWD/.work/tmp" python3 -I tools/decide/tests/test_decide.py',
            "node tools/skills/skills.ts check",
            "node tools/skills/skills.ts check --root .agents/skills",
            "python3 -I dotfiles/skills-campaign-test.py",
        ]
        rendered = [checks.render_argv(checks.BY_ID[i], checks.BY_ID[i].argv) for i in checks.SUITE]
        self.assertEqual(previous, rendered)

    def test_registry_ids_are_unique_and_suite_entries_exist(self):
        self.assertEqual(len(checks.REGISTRY), len(checks.BY_ID))
        self.assertFalse([i for i in checks.SUITE if checks.BY_ID[i].per_file])

    def test_docs_render_is_deterministic_and_check_detects_drift(self):
        WORK.mkdir(parents=True, exist_ok=True)
        root = Path(tempfile.mkdtemp(dir=WORK, prefix="checks-docs-"))
        try:
            doc = root / checks.DOC
            doc.parent.mkdir(parents=True)
            doc.write_text("intro\n\n<!-- checks:begin -->\nstale\n<!-- checks:end -->\n\noutro\n")
            self.assertEqual(1, checks.docs(root, check_only=True))
            self.assertIn("stale", doc.read_text())
            self.assertEqual(0, checks.docs(root, check_only=False))
            first = doc.read_text()
            self.assertTrue(first.startswith("intro\n") and first.endswith("\noutro\n"))
            self.assertEqual(0, checks.docs(root, check_only=True))
            self.assertEqual(first, checks.render_doc(first))
        finally:
            shutil.rmtree(root)

    def test_docs_reject_missing_or_duplicate_markers(self):
        with self.assertRaises(ValueError):
            checks.render_doc("no markers")
        with self.assertRaises(ValueError):
            checks.render_doc("<!-- checks:begin --><!-- checks:end --><!-- checks:begin --><!-- checks:end -->")

    def test_repository_docs_are_current(self):
        self.assertEqual(0, checks.docs(ROOT, check_only=True))


class RunnerTests(unittest.TestCase):
    def setUp(self):
        WORK.mkdir(parents=True, exist_ok=True)
        self.root = Path(tempfile.mkdtemp(dir=WORK, prefix="checks-run-"))
        for args in (["init", "-q"], ["config", "user.email", "t@example.invalid"], ["config", "user.name", "t"]):
            subprocess.run(["git", *args], cwd=self.root, check=True)
        (self.root / "a.txt").write_text("one\n")
        subprocess.run(["git", "add", "a.txt"], cwd=self.root, check=True)
        subprocess.run(["git", "commit", "-qm", "init"], cwd=self.root, check=True)

    def tearDown(self):
        shutil.rmtree(self.root)

    def test_results_record_exit_code_head_and_tree_fingerprint(self):
        area = Area("fake")
        ok = Check("ok", (area,), ("true",), ("a.txt",))
        bad = Check("bad", (area,), ("sh", "-c", "echo boom; exit 3"), ("a.txt",))
        first = checks.execute(self.root, ok, ok.argv)
        failed = checks.execute(self.root, bad, bad.argv)
        self.assertEqual(0, first["exit_code"])
        self.assertEqual(3, failed["exit_code"])
        self.assertEqual("boom\n", failed["output_tail"])
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=self.root, check=True, capture_output=True, text=True).stdout.strip()
        self.assertEqual(head, first["head"])
        self.assertEqual(first["tree_fingerprint"], failed["tree_fingerprint"])
        (self.root / "a.txt").write_text("two\n")
        self.assertNotEqual(first["tree_fingerprint"], checks.execute(self.root, ok, ok.argv)["tree_fingerprint"])
        self.assertNotIn("passed", first)

    def test_changed_reads_staged_unstaged_untracked_and_base_commits(self):
        (self.root / "b.txt").write_text("b\n")
        subprocess.run(["git", "add", "b.txt"], cwd=self.root, check=True)
        subprocess.run(["git", "commit", "-qm", "b"], cwd=self.root, check=True)
        (self.root / "a.txt").write_text("changed\n")
        (self.root / "c.txt").write_text("staged\n")
        subprocess.run(["git", "add", "c.txt"], cwd=self.root, check=True)
        (self.root / "d.txt").write_text("untracked\n")
        subprocess.run(["git", "mv", "b.txt", "e.txt"], cwd=self.root, check=True)
        working = sorted(checks.changed(self.root, None), key=lambda c: c.path)
        self.assertEqual([
            Change("a.txt"), Change("b.txt", deleted=True), Change("c.txt"), Change("d.txt"), Change("e.txt"),
        ], working)
        since = {c.path for c in checks.changed(self.root, "HEAD~1")}
        self.assertEqual({"a.txt", "c.txt", "d.txt", "e.txt"}, since)

    def test_plan_json_shape(self):
        out = json.loads(json.dumps(checks.plan_json(checks.plan([Change("dotfiles/doctor"), Change("LICENSE")], LINUX, no_shebang))))
        self.assertEqual(["LICENSE"], out["unmapped"])
        doctor = next(c for c in out["checks"] if c["id"] == "doctor")
        self.assertEqual({"id", "argv", "cwd", "why", "runnable", "skip_reason"}, set(doctor))


if __name__ == "__main__":
    unittest.main()

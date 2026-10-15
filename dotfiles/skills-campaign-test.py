#!/usr/bin/env python3
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORK_TMP = ROOT / ".work" / "tmp"
CHECKER = ROOT / "dotfiles" / "skills-check.sh"
MDTOOL = ROOT / "dotfiles" / "base" / ".local" / "bin" / "mdtool"
FIXTURE_TOOL = ROOT / "dotfiles" / "skill-evals" / "fixtures.py"
VERIFY_SKILL = ROOT / ".agents" / "skills" / "verify-usr"
VERIFY_HELPER = VERIFY_SKILL / "scripts" / "sym-journey.sh"
EXPLICIT_SKILL = "---\nname: sample\ndescription: Test explicit invocation.\ndisable-model-invocation: true\nmetadata:\n  opencode/slash: \"true\"\n  opencode/autoinvoke: \"false\"\n---\n\n**The test:** the sample is explicit.\n\n**Reply:** the sample passed.\n"
CODEX_POLICY = "policy:\n  allow_implicit_invocation: false\n"
OPENCODE_POLICY = '  opencode/slash: "true"\n  opencode/autoinvoke: "false"\n'


def run(*command: str, cwd: Path = ROOT, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True, check=False)


def setUpModule() -> None:
    if run("git", "check-ignore", "-q", ".work").returncode:
        raise RuntimeError(".work must be ignored through .git/info/exclude")
    WORK_TMP.mkdir(parents=True, exist_ok=True)


def skill_errors(skill_dir: Path) -> list[str]:
    content = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
    referenced = re.findall(r"\bscripts/([A-Za-z0-9_.-]+)", content)
    return [
        f"missing or non-executable helper: scripts/{name}"
        for name in referenced
        if not (skill_dir / "scripts" / name).is_file()
        or not os.access(skill_dir / "scripts" / name, os.X_OK)
    ]


def install_fixture_skill(root: Path) -> Path:
    skill = root / "sample"
    (skill / "agents").mkdir(parents=True)
    (skill / "SKILL.md").write_text(EXPLICIT_SKILL, encoding="utf-8")
    (skill / "agents" / "openai.yaml").write_text(CODEX_POLICY, encoding="utf-8")
    return skill


class SkillCampaignTests(unittest.TestCase):
    def test_new_skills_keep_host_specific_explicit_only_metadata(self):
        skills = (
            ROOT / "dotfiles" / "base" / ".agents" / "skills" / "do",
            ROOT / "dotfiles" / "base" / ".agents" / "skills" / "create-verification-skill",
            VERIFY_SKILL,
        )
        for skill in skills:
            content = (skill / "SKILL.md").read_text(encoding="utf-8")
            self.assertIn("disable-model-invocation: true", content)
            self.assertIn('opencode/slash: "true"', content)
            self.assertIn('opencode/autoinvoke: "false"', content)

    def test_known_global_and_local_skill_trees_pass(self):
        for skills in (
            ROOT / "dotfiles" / "base" / ".agents" / "skills",
            ROOT / ".agents" / "skills",
        ):
            result = run("sh", str(CHECKER), str(skills))
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_skill_checker_rejects_name_drift_and_missing_invocation_flag(self):
        work = Path(tempfile.mkdtemp(prefix="skills-check-", dir=WORK_TMP))
        try:
            skills = work / "skills"
            skill = install_fixture_skill(skills)
            valid = run("sh", str(CHECKER), str(skills))
            self.assertEqual(0, valid.returncode, valid.stdout + valid.stderr)
            drifted = skills / "renamed"
            skill.rename(drifted)
            invalid_name = run("sh", str(CHECKER), str(skills))
            self.assertNotEqual(0, invalid_name.returncode)
            drifted.rename(skill)
            policy = skill / "agents" / "openai.yaml"
            policy.write_text("policy:\n  allow_implicit_invocation: true\n", encoding="utf-8")
            invalid_policy = run("sh", str(CHECKER), str(skills))
            self.assertNotEqual(0, invalid_policy.returncode)
        finally:
            shutil.rmtree(work)

    def test_skill_checker_rejects_missing_explicit_skill_metadata(self):
        work = Path(tempfile.mkdtemp(prefix="skills-policy-", dir=WORK_TMP))
        try:
            skills = work / "skills"
            skill = install_fixture_skill(skills)
            skill_file = skill / "SKILL.md"
            skill_file.write_text(EXPLICIT_SKILL.replace("disable-model-invocation: true\n", ""), encoding="utf-8")
            result = run("sh", str(CHECKER), str(skills))
            self.assertNotEqual(0, result.returncode)
        finally:
            shutil.rmtree(work)

    def test_skill_checker_follows_source_links_in_installed_layout(self):
        work = Path(tempfile.mkdtemp(prefix="skills-layout-", dir=WORK_TMP))
        try:
            skills = work / ".agents" / "skills"
            skills.mkdir(parents=True)
            for name in ("do", "create-verification-skill"):
                target = ROOT / "dotfiles" / "base" / ".agents" / "skills" / name
                (skills / name).symlink_to(target, target_is_directory=True)
            result = run("sh", str(CHECKER), str(skills))
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        finally:
            shutil.rmtree(work)

    def test_markdown_link_oracle_accepts_good_fixture_and_rejects_bad_fixture(self):
        work = Path(tempfile.mkdtemp(prefix="mdtool-links-", dir=WORK_TMP))
        try:
            subprocess.run(["git", "init", "-q", str(work)], check=True)
            skill_dir = work / ".agents" / "skills" / "do"
            skill_dir.mkdir(parents=True)
            (skill_dir / "references").mkdir()
            (skill_dir / "references" / "playbooks.md").write_text("# Playbooks\n", encoding="utf-8")
            skill_file = skill_dir / "SKILL.md"
            skill_file.write_text("[playbooks](references/playbooks.md)\n", encoding="utf-8")
            good = run(sys.executable, "-I", str(MDTOOL), "links", "--root", str(work), "--untracked", ".agents/skills/do/SKILL.md")
            self.assertEqual(0, good.returncode, good.stdout + good.stderr)
            skill_file.write_text("[playbooks](references/missing.md)\n", encoding="utf-8")
            bad = run(sys.executable, "-I", str(MDTOOL), "links", "--root", str(work), "--untracked", ".agents/skills/do/SKILL.md")
            self.assertEqual(1, bad.returncode, bad.stdout + bad.stderr)
            self.assertIn("L001", bad.stdout)
        finally:
            shutil.rmtree(work)

    def test_verification_skill_names_an_existing_executable_helper(self):
        self.assertEqual([], skill_errors(VERIFY_SKILL))
        work = Path(tempfile.mkdtemp(prefix="skills-helper-", dir=WORK_TMP))
        try:
            skill = work / "verify-usr"
            (skill / "scripts").mkdir(parents=True)
            (skill / "SKILL.md").write_text((VERIFY_SKILL / "SKILL.md").read_text(encoding="utf-8"), encoding="utf-8")
            self.assertEqual(["missing or non-executable helper: scripts/sym-journey.sh"], skill_errors(skill))
        finally:
            shutil.rmtree(work)

    def test_usr_journey_cleans_fixtures_and_keeps_noncolliding_evidence(self):
        work = WORK_TMP
        before = {path for path in work.glob("verify-usr.*") if path.is_dir()}
        artifacts = []
        for _ in range(2):
            result = run(str(VERIFY_HELPER))
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            match = re.search(r"^evidence: (.+)$", result.stdout, re.MULTILINE)
            self.assertIsNotNone(match, result.stdout)
            evidence = Path(match.group(1))
            self.assertTrue(evidence.is_file())
            content = evidence.read_text(encoding="utf-8")
            self.assertIn("observed: link target and contents match the fixture", content)
            self.assertIn("observed: repeat run produced no changes or output", content)
            self.assertIn("observed: sym reported the conflict and preserved both destination and source", content)
            artifacts.append(evidence)
        fake_bin = Path(tempfile.mkdtemp(prefix="verify-usr-failure-", dir=work))
        try:
            fake_git = fake_bin / "git"
            fake_git.write_text(f"#!/bin/sh\ncase \"$*\" in\n  *check-ignore*|*rev-parse*) exec {shutil.which('git')} \"$@\" ;;\nesac\nexit 97\n", encoding="utf-8")
            fake_git.chmod(0o755)
            env = os.environ.copy()
            env["PATH"] = f"{fake_bin}:/usr/bin:/bin"
            failed = run(str(VERIFY_HELPER), env=env)
            self.assertEqual(1, failed.returncode, failed.stdout + failed.stderr)
            match = re.search(r"^evidence: (.+)$", failed.stdout, re.MULTILINE)
            self.assertIsNotNone(match, failed.stdout)
            failure_evidence = Path(match.group(1))
            self.assertIn("FAIL: cannot initialize isolated fixture", failure_evidence.read_text(encoding="utf-8"))
        finally:
            shutil.rmtree(fake_bin)
        after = {path for path in work.glob("verify-usr.*") if path.is_dir()}
        self.assertEqual(before, after)
        self.assertNotEqual(artifacts[0], artifacts[1])
        self.assertTrue(all(path.is_file() for path in artifacts))
        self.assertTrue(failure_evidence.is_file())

    def test_usr_journey_rejects_symlinked_scratch_directories(self):
        for scratch_path in (".work", ".work/tmp"):
            with self.subTest(scratch_path=scratch_path):
                work = Path(tempfile.mkdtemp(prefix="verify-usr-symlink-", dir=WORK_TMP))
                try:
                    repo = work / "repo"
                    helper = repo / ".agents" / "skills" / "verify-usr" / "scripts" / "sym-journey.sh"
                    helper.parent.mkdir(parents=True)
                    helper.write_text(VERIFY_HELPER.read_text(encoding="utf-8"), encoding="utf-8")
                    helper.chmod(0o755)
                    subprocess.run(["git", "init", "-q", str(repo)], check=True)
                    exclude = repo / ".git" / "info" / "exclude"
                    exclude.write_text(".work/\n", encoding="utf-8")
                    outside = work / "outside"
                    outside.mkdir()
                    scratch = repo / ".work"
                    if scratch_path == ".work":
                        scratch.symlink_to(outside, target_is_directory=True)
                    else:
                        scratch.mkdir()
                        (scratch / "tmp").symlink_to(outside, target_is_directory=True)
                    result = run(str(helper))
                    self.assertNotEqual(0, result.returncode)
                    self.assertIn("must not be symlinks", result.stderr)
                    self.assertEqual([], list(outside.iterdir()))
                finally:
                    shutil.rmtree(work)

    def test_usr_journey_requires_the_git_info_exclude_rule(self):
        work = Path(tempfile.mkdtemp(prefix="verify-usr-ignore-source-", dir=WORK_TMP))
        try:
            repo = work / "repo"
            helper = repo / ".agents" / "skills" / "verify-usr" / "scripts" / "sym-journey.sh"
            helper.parent.mkdir(parents=True)
            helper.write_text(VERIFY_HELPER.read_text(encoding="utf-8"), encoding="utf-8")
            helper.chmod(0o755)
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            (repo / ".gitignore").write_text(".work/\n", encoding="utf-8")
            result = run(str(helper))
            self.assertNotEqual(0, result.returncode)
            self.assertIn("must be ignored through .git/info/exclude", result.stderr)
            self.assertFalse((repo / ".work").exists())
        finally:
            shutil.rmtree(work)

    def test_usr_journey_retains_evidence_when_interrupted_before_observation(self):
        work = Path(tempfile.mkdtemp(prefix="verify-usr-interrupt-", dir=WORK_TMP))
        try:
            repo = work / "repo"
            helper = repo / ".agents" / "skills" / "verify-usr" / "scripts" / "sym-journey.sh"
            helper.parent.mkdir(parents=True)
            script = VERIFY_HELPER.read_text(encoding="utf-8")
            signal_trap = "trap 'exit 130' 1 2 3 15\n"
            self.assertIn(signal_trap, script)
            helper.write_text(script.replace(signal_trap, signal_trap + 'kill -TERM "$$"\n', 1), encoding="utf-8")
            helper.chmod(0o755)
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            exclude = repo / ".git" / "info" / "exclude"
            exclude.write_text(".work/\n", encoding="utf-8")
            interrupted = run(str(helper))
            self.assertEqual(130, interrupted.returncode, interrupted.stdout + interrupted.stderr)
            match = re.search(r"^evidence: (.+)$", interrupted.stdout, re.MULTILINE)
            self.assertIsNotNone(match, interrupted.stdout)
            evidence = Path(match.group(1))
            self.assertEqual("journey exited before its first observation\n", evidence.read_text(encoding="utf-8"))
            self.assertEqual([], [path for path in (repo / ".work" / "tmp").glob("verify-usr.*") if path.is_dir()])
        finally:
            shutil.rmtree(work)

    def test_fixture_setup_creates_offline_git_repository_with_observable_failure(self):
        result = run(sys.executable, "-I", str(FIXTURE_TOOL), "prepare", "bug")
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        workspace = Path(result.stdout.strip())
        try:
            self.assertTrue(workspace.is_relative_to(ROOT / ".work" / "tmp"))
            self.assertEqual("", run("git", "remote", "-v", cwd=workspace).stdout)
            self.assertEqual("", run("git", "log", "--oneline", "-1", cwd=workspace).stdout)
            failure = run(sys.executable, "-I", "tests/test_notifier.py", cwd=workspace)
            self.assertNotEqual(0, failure.returncode)
            self.assertIn("test_reconnect_does_not_duplicate_notification", failure.stderr + failure.stdout)
        finally:
            shutil.rmtree(workspace)

        ticket_result = run(sys.executable, "-I", str(FIXTURE_TOOL), "prepare", "ticket")
        self.assertEqual(0, ticket_result.returncode, ticket_result.stdout + ticket_result.stderr)
        ticket_workspace = Path(ticket_result.stdout.strip())
        try:
            self.assertEqual("", run("git", "remote", "-v", cwd=ticket_workspace).stdout)
            failure = run(sys.executable, "-I", "tests/test_notifier.py", cwd=ticket_workspace)
            self.assertNotEqual(0, failure.returncode)
            self.assertIn("test_reconnect_does_not_duplicate_listener", failure.stderr + failure.stdout)
        finally:
            shutil.rmtree(ticket_workspace)

    def test_verification_fixture_distinguishes_success_from_negative_input(self):
        result = run(sys.executable, "-I", str(FIXTURE_TOOL), "prepare", "verify")
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        workspace = Path(result.stdout.strip())
        try:
            self.assertTrue((workspace / ".agents" / "skills").is_dir())
            self.assertEqual(0, run("git", "check-ignore", "-q", ".work/tmp/marker", cwd=workspace).returncode)
            good = run(sys.executable, "-I", "tools/slugify.py", "Hello, World", cwd=workspace)
            self.assertEqual(0, good.returncode)
            self.assertEqual("hello-world\n", good.stdout)
            bad = run(sys.executable, "-I", "tools/slugify.py", "", cwd=workspace)
            self.assertEqual(2, bad.returncode)
            self.assertIn("usage: slugify.py TEXT", bad.stderr)
        finally:
            shutil.rmtree(workspace)


if __name__ == "__main__":
    unittest.main()

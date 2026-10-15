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
SCRATCH_CHECK = ROOT / "dotfiles" / "scratch-check.sh"
EXPLICIT_SKILL = "---\nname: sample\ndescription: Test explicit invocation.\ndisable-model-invocation: true\nmetadata:\n  opencode/slash: \"true\"\n  opencode/autoinvoke: \"false\"\n---\n\n**The test:** the sample is explicit.\n\n**Reply:** the sample passed.\n"
CODEX_POLICY = "policy:\n  allow_implicit_invocation: false\n"
OPENCODE_POLICY = '  opencode/slash: "true"\n  opencode/autoinvoke: "false"\n'


def run(*command: str, cwd: Path = ROOT, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True, check=False)


def setUpModule() -> None:
    result = run("sh", str(SCRATCH_CHECK), str(ROOT))
    if result.returncode:
        raise RuntimeError(result.stdout + result.stderr)


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


def install_journey(repo: Path) -> Path:
    helper = repo / ".agents" / "skills" / "verify-usr" / "scripts" / "sym-journey.sh"
    helper.parent.mkdir(parents=True)
    shutil.copy2(VERIFY_HELPER, helper)
    scratch_check = repo / "dotfiles" / "scratch-check.sh"
    scratch_check.parent.mkdir(parents=True)
    shutil.copy2(SCRATCH_CHECK, scratch_check)
    scratch_check.chmod(0o755)
    return helper


def git_init(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", str(repo)], check=True)


def scoring_repo(parent: Path) -> tuple[Path, str]:
    repo = parent / "repo"
    git_init(repo)
    for name, value in (("user.name", "Fixture Evaluator"), ("user.email", "fixture@example.invalid"), ("core.filemode", "true"), ("core.symlinks", "true"), ("core.excludesFile", "/dev/null")):
        subprocess.run(["git", "-C", str(repo), "config", name, value], check=True)
    (repo / ".git" / "info" / "exclude").write_text(".work/\n", encoding="utf-8")
    source = repo / "src" / "startup.py"
    source.parent.mkdir()
    source.write_text("start = True\n", encoding="utf-8")
    target_a = repo / "target-a"
    target_b = repo / "target-b"
    target_a.write_text("a\n", encoding="utf-8")
    target_b.write_text("b\n", encoding="utf-8")
    (repo / "link").symlink_to("target-a")
    subprocess.run(["git", "-C", str(repo), "add", "--all"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-m", "test(fixtures): seed scoring repository"], check=True, capture_output=True, text=True)
    baseline = subprocess.run(["git", "-C", str(repo), "rev-parse", "--verify", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()
    return repo, baseline


def score_fixture(repo: Path, baseline: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return run(sys.executable, "-I", str(FIXTURE_TOOL), "score-unchanged", str(repo), baseline, env=env)


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

    def test_do_reference_graph_resolves_in_source_and_installed_layouts(self):
        source_skills = ROOT / "dotfiles" / "base" / ".agents" / "skills"
        names = ("do", "campaign-plan", "campaign-preflight", "orchestrate", "create-verification-skill")
        source_args = tuple(f"dotfiles/base/.agents/skills/{name}" for name in names)
        source = run(sys.executable, str(MDTOOL), "links", "--root", str(ROOT), "--untracked", *source_args)
        self.assertEqual(0, source.returncode, source.stdout + source.stderr)

        work = Path(tempfile.mkdtemp(prefix="do-links-layout-", dir=WORK_TMP))
        try:
            repo = work / "installed"
            git_init(repo)
            installed_skills = repo / ".agents" / "skills"
            shutil.copytree(source_skills, installed_skills, symlinks=False)
            installed_args = tuple(f".agents/skills/{name}" for name in names)
            installed = run(sys.executable, str(MDTOOL), "links", "--root", str(repo), "--untracked", *installed_args)
            self.assertEqual(0, installed.returncode, installed.stdout + installed.stderr)
            (installed_skills / "campaign-plan" / "SKILL.md").unlink()
            broken_args = tuple(path for path in installed_args if not path.endswith("/campaign-plan"))
            broken = run(sys.executable, str(MDTOOL), "links", "--root", str(repo), "--untracked", *broken_args)
            self.assertEqual(1, broken.returncode, broken.stdout + broken.stderr)
            self.assertIn("L001", broken.stdout)
        finally:
            shutil.rmtree(work)

    def test_scratch_check_creates_fresh_work_after_validating_info_exclude(self):
        work = Path(tempfile.mkdtemp(prefix="scratch-check-fresh-", dir=WORK_TMP))
        try:
            repo = work / "repo"
            git_init(repo)
            (repo / ".git" / "info" / "exclude").write_text(".work/\n", encoding="utf-8")
            result = run("sh", str(SCRATCH_CHECK), str(repo))
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            self.assertTrue((repo / ".work" / "tmp").is_dir())
            self.assertEqual(0, run("git", "check-ignore", "-q", ".work/tmp/verify-marker", cwd=repo).returncode)
        finally:
            shutil.rmtree(work)

    def test_scratch_check_rejects_a_gitignore_only_rule_before_writing(self):
        work = Path(tempfile.mkdtemp(prefix="scratch-check-ignore-source-", dir=WORK_TMP))
        try:
            repo = work / "repo"
            git_init(repo)
            (repo / ".gitignore").write_text(".work/\n", encoding="utf-8")
            result = run("sh", str(SCRATCH_CHECK), str(repo))
            self.assertNotEqual(0, result.returncode)
            self.assertIn("must be ignored through .git/info/exclude", result.stderr)
            self.assertFalse((repo / ".work").exists())
        finally:
            shutil.rmtree(work)

    def test_scratch_check_rejects_both_symlinked_scratch_paths(self):
        for scratch_path in (".work", ".work/tmp"):
            with self.subTest(scratch_path=scratch_path):
                work = Path(tempfile.mkdtemp(prefix="scratch-check-symlink-", dir=WORK_TMP))
                try:
                    repo = work / "repo"
                    git_init(repo)
                    (repo / ".git" / "info" / "exclude").write_text(".work/\n", encoding="utf-8")
                    outside = work / "outside"
                    outside.mkdir()
                    scratch = repo / ".work"
                    if scratch_path == ".work":
                        scratch.symlink_to(outside, target_is_directory=True)
                    else:
                        scratch.mkdir()
                        (scratch / "tmp").symlink_to(outside, target_is_directory=True)
                    result = run("sh", str(SCRATCH_CHECK), str(repo))
                    self.assertNotEqual(0, result.returncode)
                    self.assertIn("must not be symlinks", result.stderr)
                    self.assertEqual([], list(outside.iterdir()))
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
                    helper = install_journey(repo)
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
            helper = install_journey(repo)
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
            helper = install_journey(repo)
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
            self.assertEqual("1\n", run("git", "rev-list", "--count", "HEAD", cwd=workspace).stdout)
            baseline = run("git", "rev-parse", "--verify", "HEAD", cwd=workspace).stdout.strip()
            self.assertEqual(0, score_fixture(workspace, baseline).returncode)
            failure = run(sys.executable, "-B", "-I", "tests/test_notifier.py", cwd=workspace)
            self.assertNotEqual(0, failure.returncode)
            self.assertIn("test_reconnect_does_not_duplicate_notification", failure.stderr + failure.stdout)
        finally:
            shutil.rmtree(workspace)

        ticket_result = run(sys.executable, "-I", str(FIXTURE_TOOL), "prepare", "ticket")
        self.assertEqual(0, ticket_result.returncode, ticket_result.stdout + ticket_result.stderr)
        ticket_workspace = Path(ticket_result.stdout.strip())
        try:
            self.assertEqual("", run("git", "remote", "-v", cwd=ticket_workspace).stdout)
            self.assertEqual("1\n", run("git", "rev-list", "--count", "HEAD", cwd=ticket_workspace).stdout)
            failure = run(sys.executable, "-B", "-I", "tests/test_notifier.py", cwd=ticket_workspace)
            self.assertNotEqual(0, failure.returncode)
            self.assertIn("test_reconnect_does_not_duplicate_listener", failure.stderr + failure.stdout)
        finally:
            shutil.rmtree(ticket_workspace)

    def test_unchanged_score_accepts_only_the_exact_seed_state(self):
        work = Path(tempfile.mkdtemp(prefix="fixture-score-clean-", dir=WORK_TMP))
        try:
            repo, baseline = scoring_repo(work)
            clean = score_fixture(repo, baseline)
            self.assertEqual(0, clean.returncode, clean.stdout + clean.stderr)
        finally:
            shutil.rmtree(work)

    def test_unchanged_score_rejects_every_filesystem_and_history_mutation(self):
        def overwrite(repo: Path) -> None:
            (repo / "src" / "startup.py").write_text("start = False\n", encoding="utf-8")

        def delete(repo: Path) -> None:
            (repo / "src" / "startup.py").unlink()

        def add(repo: Path) -> None:
            (repo / "new-file.txt").write_text("unauthorized\n", encoding="utf-8")

        def change_mode(repo: Path) -> None:
            (repo / "src" / "startup.py").chmod(0o755)

        def change_symlink(repo: Path) -> None:
            (repo / "link").unlink()
            (repo / "link").symlink_to("target-b")

        def add_ignored_file(repo: Path) -> None:
            exclude = repo / ".git" / "info" / "exclude"
            with exclude.open("a", encoding="utf-8") as handle:
                handle.write("hidden.txt\n")
            (repo / "hidden.txt").write_text("still unauthorized\n", encoding="utf-8")

        def worker_commit(repo: Path) -> None:
            subprocess.run(["git", "-C", str(repo), "commit", "--allow-empty", "-m", "test(fixtures): empty worker commit"], check=True, capture_output=True, text=True)

        def add_remote(repo: Path) -> None:
            subprocess.run(["git", "-C", str(repo), "remote", "add", "origin", "https://example.invalid/fixture.git"], check=True)

        def change_git_config(repo: Path) -> None:
            subprocess.run(["git", "-C", str(repo), "config", "--local", "--add", "core.filemode", "false"], check=True)
            subprocess.run(["git", "-C", str(repo), "config", "--local", "--add", "core.filemode", "true"], check=True)

        mutations = (overwrite, delete, add, change_mode, change_symlink, add_ignored_file, change_git_config, worker_commit, add_remote)
        for mutation in mutations:
            with self.subTest(mutation=mutation.__name__):
                work = Path(tempfile.mkdtemp(prefix="fixture-score-mutation-", dir=WORK_TMP))
                try:
                    repo, baseline = scoring_repo(work)
                    mutation(repo)
                    scored = score_fixture(repo, baseline)
                    self.assertNotEqual(0, scored.returncode, scored.stdout + scored.stderr)
                finally:
                    shutil.rmtree(work)

    def test_unchanged_score_fails_when_git_command_fails(self):
        work = Path(tempfile.mkdtemp(prefix="fixture-score-command-failure-", dir=WORK_TMP))
        try:
            repo, baseline = scoring_repo(work)
            fake_bin = work / "bin"
            fake_bin.mkdir()
            fake_git = fake_bin / "git"
            fake_git.write_text("#!/bin/sh\nexit 97\n", encoding="utf-8")
            fake_git.chmod(0o755)
            env = os.environ.copy()
            env["PATH"] = str(fake_bin)
            scored = score_fixture(repo, baseline, env=env)
            self.assertNotEqual(0, scored.returncode)
            self.assertIn("failed (97)", scored.stderr)
        finally:
            shutil.rmtree(work)

    def test_scenario_fixtures_construct_their_advertised_facts(self):
        unreproduced = run(sys.executable, "-I", str(FIXTURE_TOOL), "prepare", "unreproduced")
        self.assertEqual(0, unreproduced.returncode, unreproduced.stdout + unreproduced.stderr)
        unreproduced_repo = Path(unreproduced.stdout.strip())
        try:
            baseline = run("git", "rev-parse", "--verify", "HEAD", cwd=unreproduced_repo).stdout.strip()
            self.assertEqual(0, run(sys.executable, "-B", "-I", "-m", "unittest", "discover", "-s", "tests", cwd=unreproduced_repo).returncode)
            self.assertEqual(0, score_fixture(unreproduced_repo, baseline).returncode)
        finally:
            shutil.rmtree(unreproduced_repo)

        for case, allowed in (("campaign-authorized", True), ("campaign-no-commit", False)):
            with self.subTest(case=case):
                prepared = run(sys.executable, "-I", str(FIXTURE_TOOL), "prepare", case)
                self.assertEqual(0, prepared.returncode, prepared.stdout + prepared.stderr)
                repo = Path(prepared.stdout.strip())
                try:
                    authority = (repo / "AGENTS.md").read_text(encoding="utf-8") + (repo / "docs" / "CAMPAIGN-SAMPLE.md").read_text(encoding="utf-8")
                    self.assertEqual(allowed, "One local commit is authorized" in authority)
                    tests = (repo / "tests" / "test_value.py").read_text(encoding="utf-8")
                    for value in ("is_positive(1)", "is_positive(0)", "is_positive(-1)"):
                        self.assertIn(value, tests)
                    baseline = run("git", "rev-parse", "--verify", "HEAD", cwd=repo).stdout.strip()
                    self.assertEqual(0, score_fixture(repo, baseline).returncode)
                finally:
                    shutil.rmtree(repo)

        campaign_new = run(sys.executable, "-I", str(FIXTURE_TOOL), "prepare", "campaign-new")
        self.assertEqual(0, campaign_new.returncode, campaign_new.stdout + campaign_new.stderr)
        campaign_repo = Path(campaign_new.stdout.strip())
        try:
            tests = (campaign_repo / "tests" / "test_manifest.py").read_text(encoding="utf-8")
            for required in ("{'records': 2, 'total': 5}", "{'records': 0, 'total': 0}", "test_cli_rejects_invalid_documents", "self.assertEqual(2, result.returncode)"):
                self.assertIn(required, tests)
            baseline = run("git", "rev-parse", "--verify", "HEAD", cwd=campaign_repo).stdout.strip()
            self.assertEqual(0, score_fixture(campaign_repo, baseline).returncode)
        finally:
            shutil.rmtree(campaign_repo)

        performance = run(sys.executable, "-I", str(FIXTURE_TOOL), "prepare", "deferred-performance")
        self.assertEqual(0, performance.returncode, performance.stdout + performance.stderr)
        performance_repo = Path(performance.stdout.strip())
        try:
            ready = run("sh", "tools/perf-gate-ready", cwd=performance_repo)
            self.assertEqual(75, ready.returncode)
            self.assertEqual("busy\n", ready.stdout)
            self.assertEqual(0, run(sys.executable, "-B", "-I", "-m", "unittest", "discover", "-s", "tests", cwd=performance_repo).returncode)
        finally:
            shutil.rmtree(performance_repo)

        unavailable = run(sys.executable, "-I", str(FIXTURE_TOOL), "prepare", "unavailable-check")
        self.assertEqual(0, unavailable.returncode, unavailable.stdout + unavailable.stderr)
        unavailable_repo = Path(unavailable.stdout.strip())
        try:
            required = run(sys.executable, "-B", "-I", "tools/required_check.py", cwd=unavailable_repo)
            self.assertEqual(86, required.returncode)
            self.assertEqual("required check unavailable\n", required.stderr)
            self.assertEqual("", required.stdout)
            self.assertIn("partial", (unavailable_repo / "HANDOFF.md").read_text(encoding="utf-8"))
        finally:
            shutil.rmtree(unavailable_repo)

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

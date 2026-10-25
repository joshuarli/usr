"""Offline integration tests for the bundled pinact executable."""

from __future__ import annotations

import contextlib
import importlib.machinery
import importlib.util
import io
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from pathlib import Path

PINACT = Path(__file__).resolve().parents[2] / "dotfiles/base/.local/bin/pinact"
MIGRATE = PINACT.parents[3] / "migrate-pinact.sh"
LOADER = importlib.machinery.SourceFileLoader("bundled_pinact", str(PINACT))
SPEC = importlib.util.spec_from_loader(LOADER.name, LOADER)
assert SPEC is not None
PINACT_MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = PINACT_MODULE
LOADER.exec_module(PINACT_MODULE)


def git(*args: str, cwd: Path, env: dict[str, str] | None = None) -> str:
    return subprocess.check_output(["git", *args], cwd=cwd, env=env, text=True).strip()


class PinactTests(unittest.TestCase):
    def test_requires_python_311(self) -> None:
        stderr = io.StringIO()
        with patch.object(sys, "version_info", (3, 10)):
            with contextlib.redirect_stderr(stderr):
                result = PINACT_MODULE.main(["--help"])
        self.assertEqual(result, 2)
        self.assertIn("Python 3.11 or newer", stderr.getvalue())

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.remotes = self.root / "remotes" / "actions"
        self.remotes.mkdir(parents=True)
        self.bare = self.remotes / "checkout.git"
        self.bare.mkdir()
        git("init", "--bare", "-q", cwd=self.bare)
        self.upstream = self.root / "upstream"
        self.upstream.mkdir()
        git("init", "-q", "-b", "main", cwd=self.upstream)
        git("config", "user.name", "Test", cwd=self.upstream)
        git("config", "user.email", "test@example.invalid", cwd=self.upstream)
        (self.upstream / "README").write_text("one\n")
        git("add", "README", cwd=self.upstream)
        git("commit", "-qm", "one", cwd=self.upstream)
        self.first = git("rev-parse", "HEAD", cwd=self.upstream)
        git("tag", "v1", cwd=self.upstream)
        git("tag", "-a", "v2", "-m", "annotated", cwd=self.upstream)
        self.tag_object = git("rev-parse", "v2", cwd=self.upstream)
        git("remote", "add", "origin", str(self.bare), cwd=self.upstream)
        git("push", "-q", "origin", "main", "--tags", cwd=self.upstream)
        config = self.root / "gitconfig"
        config.write_text(f'[url "file://{self.root}/remotes/"]\n\tinsteadOf = https://github.com/\n')
        self.env = {**os.environ, "GIT_CONFIG_GLOBAL": str(config), "GIT_CONFIG_NOSYSTEM": "1"}
        self.workspace = self.root / "workspace"
        self.workspace.mkdir()
        git("init", "-q", cwd=self.workspace, env=self.env)

    def workflow(self, content: str, name: str = "test.yml") -> Path:
        file = self.workspace / ".github" / "workflows" / name
        file.parent.mkdir(parents=True, exist_ok=True)
        with file.open("w", encoding="utf-8", newline="") as f:
            f.write(content)
        return file

    def run_pinact(self, *args: str, env: dict[str, str] | None = None) -> SimpleNamespace:
        stdout, stderr = io.StringIO(), io.StringIO()
        old_cwd = Path.cwd()
        try:
            os.chdir(self.workspace)
            with patch.dict(os.environ, env or self.env, clear=True):
                with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                    try:
                        status = PINACT_MODULE.main(list(args))
                    except SystemExit as exc:
                        status = int(exc.code)
        finally:
            os.chdir(old_cwd)
        return SimpleNamespace(returncode=status, stdout=stdout.getvalue(), stderr=stderr.getvalue())

    def test_tag_peeling_comments_crlf_quotes_and_idempotence(self) -> None:
        self.assertNotEqual(self.first, self.tag_object)
        source = (
            'jobs:\r\n'
            '  test:\r\n'
            '    steps:\r\n'
            '      - uses: "actions/checkout@v2"  # zizmor: ignore[example]\r\n'
            "      - 'uses': 'actions/checkout/subdirectory@v1' # v1\r\n"
            '      - uses: ./local\r\n'
            '      - uses: docker://alpine:3\r\n'
            '      - run: |\r\n'
            '          uses: actions/checkout@unresolvable\r\n'
        )
        path = self.workflow(source)
        os.chmod(path, 0o640)
        result = self.run_pinact("run")
        self.assertEqual(result.returncode, 0, result.stderr)
        with path.open(encoding="utf-8", newline="") as f:
            updated = f.read()
        self.assertIn(f'"actions/checkout@{self.first}"  # zizmor: ignore[example] [pin:v2]\r\n', updated)
        self.assertIn(f"'actions/checkout/subdirectory@{self.first}' # v1\r\n", updated)
        self.assertIn("uses: actions/checkout@unresolvable\r\n", updated)
        self.assertIn("- uses: docker://alpine:3\r\n", updated)
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o640)
        self.assertEqual(self.run_pinact("--check").returncode, 0)
        self.assertEqual(self.run_pinact().returncode, 0)
        with path.open(encoding="utf-8", newline="") as f:
            self.assertEqual(f.read(), updated)

    def test_offline_check_and_invalid_inputs(self) -> None:
        path = self.workflow('  - uses: actions/checkout@v1 # test\n')
        # No git access at all: with filenames supplied, check is still offline.
        fake = self.root / "bin"
        fake.mkdir()
        script = fake / "git"
        script.write_text("#!/bin/sh\nexit 98\n")
        script.chmod(0o755)
        result = self.run_pinact("--check", str(path), env={**self.env, "PATH": f"{fake}:{os.environ['PATH']}"})
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("checkout@v1", result.stderr)
        self.assertEqual(path.read_text(), '  - uses: actions/checkout@v1 # test\n')
        self.assertEqual(self.run_pinact("--check", "--refresh", str(path)).returncode, 2)

    def test_branch_guard_and_opt_in(self) -> None:
        path = self.workflow('uses: actions/checkout@main\n')
        result = self.run_pinact()
        self.assertEqual(result.returncode, 2)
        self.assertIn("--allow-branches", result.stderr)
        self.assertEqual(path.read_text(), 'uses: actions/checkout@main\n')
        result = self.run_pinact("--allow-branches")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(path.read_text(), f'uses: actions/checkout@{self.first} # main\n')

    def test_missing_and_ambiguous_refs(self) -> None:
        path = self.workflow('uses: actions/checkout@unknown\n')
        self.assertIn("ref not found", self.run_pinact().stderr)
        self.assertEqual(path.read_text(), 'uses: actions/checkout@unknown\n')
        git("branch", "v1", cwd=self.upstream)
        git("push", "-q", "origin", "refs/heads/v1:refs/heads/v1", cwd=self.upstream)
        path.write_text('uses: actions/checkout@v1\n')
        result = self.run_pinact("--allow-branches")
        self.assertEqual(result.returncode, 2)
        self.assertIn("ambiguous", result.stderr)
        self.assertEqual(path.read_text(), 'uses: actions/checkout@v1\n')

    def test_refresh_moves_only_explicit_versions(self) -> None:
        path = self.workflow('uses: actions/checkout@v2\n')
        self.assertEqual(self.run_pinact().returncode, 0)
        self.assertIn(self.first, path.read_text())
        (self.upstream / "README").write_text("two\n")
        git("add", "README", cwd=self.upstream)
        git("commit", "-qm", "two", cwd=self.upstream)
        second = git("rev-parse", "HEAD", cwd=self.upstream)
        git("tag", "-fa", "v2", "-m", "new annotated", cwd=self.upstream)
        git("push", "-q", "-f", "origin", "v2", cwd=self.upstream)
        self.assertEqual(self.run_pinact().returncode, 0)
        self.assertIn(self.first, path.read_text())
        result = self.run_pinact("--refresh")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(path.read_text(), f'uses: actions/checkout@{second} # v2\n')

    def test_all_resolved_before_any_writes(self) -> None:
        first = self.workflow('uses: actions/checkout@v1\n', "a.yml")
        second = self.workflow('uses: actions/checkout@does-not-exist\n', "b.yml")
        result = self.run_pinact()
        self.assertEqual(result.returncode, 2)
        self.assertEqual(first.read_text(), 'uses: actions/checkout@v1\n')
        self.assertEqual(second.read_text(), 'uses: actions/checkout@does-not-exist\n')

    def test_pin_refuses_to_modify_invalid_yaml(self) -> None:
        source = "steps:\n  - uses: actions/checkout@v2\n  - {broken:\n"
        path = self.workflow(source)

        result = self.run_pinact()

        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(path.read_text(), source)

    def test_scan_rejects_unsupported_flow_and_invalid_refs(self) -> None:
        for value in (
            'steps: [{uses: actions/checkout@v1}]\n',
            'uses: >-\n  actions/checkout@v1\n',
            'uses: actions/checkout@x..y\n',
            'uses: actions/checkout@v1@v2\n',
            'uses: actions/../checkout@v1\n',
            'uses: ${{ inputs.action }}\n',
        ):
            with self.subTest(value=value):
                path = self.workflow(value)
                result = self.run_pinact("--check")
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertEqual(path.read_text(), value)

    def test_non_action_input_and_block_scalar_are_not_pinned(self) -> None:
        path = self.workflow(
            'steps:\n'
            '  - uses: actions/checkout@v1\n'
            '    with:\n'
            '      uses: other/tool@v9\n'
            '    env:\n'
            '      uses: some/text@latest\n'
            '  - run: |\n'
            '      uses: impossible/tool@v99\n'
        )
        result = self.run_pinact()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(f'uses: actions/checkout@{self.first} # v1', path.read_text())
        self.assertIn('      uses: other/tool@v9', path.read_text())
        self.assertIn('      uses: some/text@latest', path.read_text())
        self.assertIn('      uses: impossible/tool@v99', path.read_text())

    def test_migration_requires_dl_ownership_and_cleans_state(self) -> None:
        home = self.root / "home"
        binary = home / ".local" / "bin" / "pinact"
        marker = home / ".local" / "state" / "dl" / "pinact"
        ledger = home / ".local" / "state" / "make" / "dl-owned"
        for file in (binary, marker, ledger):
            file.parent.mkdir(parents=True, exist_ok=True)
        binary.write_text("legacy executable")
        marker.write_text("etag")
        env = {**self.env, "HOME": str(home), "XDG_STATE_HOME": str(home / ".local" / "state")}

        def migrate() -> subprocess.CompletedProcess[str]:
            return subprocess.run(["sh", str(MIGRATE), str(home), str(ledger)],
                                  text=True, capture_output=True, env=env)

        result = migrate()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not recorded", result.stderr)
        self.assertTrue(binary.exists())
        self.assertTrue(marker.exists())
        ledger.write_text(f"F\t{binary}\n")
        result = migrate()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(binary.exists())
        self.assertFalse(marker.exists())
        self.assertEqual(migrate().returncode, 0)

    def test_git_discovery_includes_local_action_files(self) -> None:
        workflow = self.workflow('uses: actions/checkout@v1\n')
        action = self.workspace / "support" / "subdir" / "action.yaml"
        action.parent.mkdir(parents=True)
        action.write_text('runs:\n  using: composite\n  steps:\n    - uses: actions/checkout@v2\n')
        irrelevant = self.workspace / "support" / "readme.yml"
        irrelevant.write_text('uses: actions/checkout@v1\n')
        result = self.run_pinact("--check")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("action.yaml", result.stderr)
        self.assertIn("test.yml", result.stderr)
        self.assertNotIn("readme.yml", result.stderr)
        self.assertEqual(self.run_pinact().returncode, 0)
        self.assertIn(self.first, workflow.read_text())
        self.assertIn(self.first, action.read_text())
        self.assertEqual(irrelevant.read_text(), 'uses: actions/checkout@v1\n')

    def test_rejects_symlinks(self) -> None:
        path = self.workflow('uses: actions/checkout@v1\n', "actual.yml")
        link = path.parent / "link.yml"
        link.symlink_to(path)
        result = self.run_pinact(str(link))
        self.assertEqual(result.returncode, 2)
        self.assertIn("symlink", result.stderr)
        self.assertEqual(path.read_text(), 'uses: actions/checkout@v1\n')


if __name__ == "__main__":
    unittest.main()

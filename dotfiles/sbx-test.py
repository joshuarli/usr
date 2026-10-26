#!/usr/bin/env python3
"""Structural and optional real-kernel checks for sbx."""

import argparse
import importlib.machinery
import importlib.util
import io
import os
import platform
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).parent / "base/.local/bin/sbx"
LOADER = importlib.machinery.SourceFileLoader("sbx", str(SCRIPT))
SPEC = importlib.util.spec_from_loader("sbx", LOADER)
SBX = importlib.util.module_from_spec(SPEC)
sys.modules["sbx"] = SBX
SPEC.loader.exec_module(SBX)


class LocalFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="sbx-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.home = self.root / "home"
        self.home.mkdir()
        self.project = self.home / "d/project"
        self.project.mkdir(parents=True)
        self.ro = self.root / "reference"
        self.rw = self.root / "other"
        self.ro.mkdir()
        self.rw.mkdir()

    def plan(self, *args, backend="Linux"):
        return SBX.parse(list(args), backend=backend, home=self.home, cwd=self.project)

    def make_sources(self):
        base = self.home / "usr/dotfiles/base"
        skill = base / ".agents/skills/review"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("skill", encoding="utf-8")
        codex = base / ".codex"
        codex.mkdir(parents=True)
        (codex / "AGENTS.md").write_text("instructions", encoding="utf-8")
        claude = base / ".claude/agents"
        claude.mkdir(parents=True)
        (claude / "worker.md").write_text("worker", encoding="utf-8")
        return base


class PolicyTests(LocalFixture):
    def test_default_and_explicit_directory_grants(self):
        plan = self.plan("--ro", str(self.ro), "--rw", str(self.rw), "--", "echo", "ok")
        self.assertEqual(plan.command, ("echo", "ok"))
        self.assertEqual([(p.path, p.writable) for p in plan.grants], [
            (self.project, True), (self.ro, False), (self.rw, True)])

    def test_default_shell_per_platform(self):
        self.assertEqual(self.plan().command, ("/bin/sh",))
        self.assertEqual(self.plan(backend="Darwin").command, ("/bin/zsh",))

    def test_default_online_offline_explicit(self):
        self.assertFalse(self.plan().offline)
        self.assertTrue(self.plan("--offline").offline)

    def test_command_flag_not_interpreted_as_wrapper_option(self):
        self.assertFalse(self.plan("--", "printf", "--explain").explain)
        self.assertTrue(self.plan("--explain", "--", "printf", "hi").explain)

    def test_root_home_and_ancestor_rejected(self):
        for location in (self.home, self.root, Path("/")):
            with self.subTest(path=location), self.assertRaisesRegex(SBX.SandboxError, "host home"):
                SBX.parse([], backend="Linux", home=self.home, cwd=location)
            with self.subTest(extra=location), self.assertRaisesRegex(SBX.SandboxError, "host home"):
                self.plan("--ro", str(location))

    def test_overlap_rejected_regardless_of_order(self):
        sub = self.project / "sub"
        sub.mkdir()
        for args in (("--ro", str(sub)), ("--rw", str(self.home / "d")),
                     ("--ro", str(self.ro), "--rw", str(self.ro))):
            with self.subTest(args=args), self.assertRaisesRegex(SBX.SandboxError, "overlapping"):
                self.plan(*args)

    def test_symlink_alias_overlap_rejected(self):
        link = self.root / "alias"
        link.symlink_to(self.project, target_is_directory=True)
        with self.assertRaisesRegex(SBX.SandboxError, "overlapping"):
            self.plan("--ro", str(link))

    def test_explicit_symlink_grant_canonicalizes(self):
        link = self.root / "alias"
        link.symlink_to(self.ro, target_is_directory=True)
        self.assertEqual(self.plan("--ro", str(link)).grants[1].path, self.ro)

    def test_nonexistent_or_file_grant_rejected(self):
        regular = self.root / "file"
        regular.write_text("x", encoding="utf-8")
        for p in (regular, self.root / "missing"):
            with self.subTest(p=p), self.assertRaises(SBX.SandboxError):
                self.plan("--rw", str(p))

    def test_control_characters_in_grants_rejected(self):
        p = self.root / "evil\npath"
        p.mkdir()
        with self.assertRaisesRegex(SBX.SandboxError, "control character"):
            self.plan("--rw", str(p))

    def test_skills_absent_without_repo(self):
        self.assertIsNone(self.plan().sources)

    def test_skills_are_resolved_from_tracked_repo(self):
        base = self.make_sources()
        s = self.plan().sources
        self.assertEqual(s.skills, base / ".agents/skills")
        self.assertEqual(s.instructions, base / ".codex/AGENTS.md")
        self.assertEqual(s.claude_agents, base / ".claude/agents")
        self.assertIsNone(s.grok_agents)
        self.assertIsNone(self.plan("--no-skills").sources)

    def test_broken_or_external_skill_source_rejected(self):
        base = self.make_sources()
        (base / ".codex/AGENTS.md").unlink()
        (base / ".codex/AGENTS.md").symlink_to(self.ro / "secret")
        (self.ro / "secret").write_text("nope", encoding="utf-8")
        with self.assertRaisesRegex(SBX.SandboxError, "outside usr"):
            self.plan()

    def test_sanitized_environment(self):
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "secret", "SSH_AUTH_SOCK": "/bad", "PYTHONPATH": "/evil", "TERM": "xterm"}):
            env = SBX.environment(self.home, "Linux")
        self.assertEqual(env["HOME"], str(self.home))
        self.assertEqual(env["TERM"], "xterm")
        for secret_name in ("ANTHROPIC_API_KEY", "SSH_AUTH_SOCK", "PYTHONPATH", "GITHUB_TOKEN", "DYLD_INSERT_LIBRARIES"):
            self.assertNotIn(secret_name, env)

    def test_missing_bwrap_fails_closed(self):
        with mock.patch.object(SBX.shutil, "which", return_value=None):
            with self.assertRaisesRegex(SBX.SandboxError, "required"):
                SBX.linux_command(self.plan())
        with mock.patch.object(SBX, "parse", return_value=self.plan()), \
             mock.patch.object(SBX.shutil, "which", return_value=None), \
             mock.patch.object(SBX.subprocess, "call") as call:
            self.assertEqual(SBX.main([]), 1)
        call.assert_not_called()

    def test_linux_no_home_bind_and_private_namespaces(self):
        with mock.patch.object(SBX.shutil, "which", return_value="/usr/bin/bwrap"):
            argv = SBX.linux_command(self.plan("--ro", str(self.ro), "--offline"))
        self.assertEqual(argv[0], "/usr/bin/bwrap")
        for flag in ("--unshare-all", "--die-with-parent", "--new-session", "--clearenv", "--proc", "--dev", "--tmpfs", "--chdir"):
            self.assertIn(flag, argv)
        self.assertNotIn("--share-net", argv)
        bindings = [(argv[i], argv[i+1], argv[i+2]) for i in range(len(argv) - 2)
                    if argv[i] in ("--bind", "--ro-bind")]
        self.assertIn(("--bind", str(self.project), str(self.project)), bindings)
        self.assertIn(("--ro-bind", str(self.ro), str(self.ro)), bindings)
        self.assertFalse(any(source == str(self.home) for _, source, _ in bindings))
        self.assertIn(["--dir", str(self.home)], [argv[i:i+2] for i in range(len(argv)-1)])

    def test_linux_online_is_explicit_shared_network(self):
        with mock.patch.object(SBX.shutil, "which", return_value="/usr/bin/bwrap"):
            argv = SBX.linux_command(self.plan())
        self.assertIn("--share-net", argv)

    def test_linux_rejects_symlinked_git_root(self):
        (self.project / ".git").symlink_to(self.ro, target_is_directory=True)
        with mock.patch.object(SBX.shutil, "which", return_value="/usr/bin/bwrap"):
            with self.assertRaisesRegex(SBX.SandboxError, "symlinked .git"):
                SBX.linux_command(self.plan())

    def test_linux_git_root_protected(self):
        git = self.project / ".git"
        git.mkdir()
        with mock.patch.object(SBX.shutil, "which", return_value="/usr/bin/bwrap"):
            argv = SBX.linux_command(self.plan())
        self.assertIn(["--ro-bind", str(git), str(git)], [argv[i:i+3] for i in range(len(argv)-2)])

    def test_linux_prevents_alias_setup_inside_host_bind(self):
        self.make_sources()
        collision = self.home / ".config/opencode"
        collision.mkdir(parents=True)
        with mock.patch.object(SBX.shutil, "which", return_value="/usr/bin/bwrap"):
            with self.assertRaisesRegex(SBX.SandboxError, "conflicts with private home adapter"):
                SBX.linux_command(SBX.parse([], backend="Linux", home=self.home, cwd=collision))
            with self.assertRaisesRegex(SBX.SandboxError, "conflicts with private home adapter"):
                SBX.linux_command(self.plan("--ro", str(self.home / ".config")))
            self.assertIn("--bind", SBX.linux_command(SBX.parse(["--no-skills"], backend="Linux", home=self.home, cwd=collision)))

    def test_linux_skills_bound_ro_and_aliases(self):
        self.make_sources()
        with mock.patch.object(SBX.shutil, "which", return_value="/usr/bin/bwrap"):
            argv = SBX.linux_command(self.plan())
        sources = SBX.skill_bindings(self.plan().sources, self.home)
        for source, target in sources:
            self.assertIn(["--ro-bind", str(source), str(target)], [argv[i:i+3] for i in range(len(argv)-2)])
        self.assertIn(["--symlink", "../.agents/skills", str(self.home / ".claude/skills")],
                      [argv[i:i+3] for i in range(len(argv)-2)])

    def test_mac_denies_default_and_limits_keychain_ipc(self):
        profile = SBX.macos_profile(self.plan(backend="Darwin"), self.root)
        self.assertIn("(deny default)", profile)
        self.assertIn(SBX.sbpl_path(self.project), profile)
        self.assertNotIn('com.apple.SecurityServer', profile)
        self.assertNotIn('com.apple.securityd.xpc', profile)
        self.assertNotIn('appleevent-send', profile)
        self.assertNotIn('lsopen', profile)
        self.assertNotIn('global-name-prefix', profile)
        self.assertIn('(allow network*)', profile)
        offline = SBX.macos_profile(self.plan("--offline", backend="Darwin"), self.root)
        self.assertNotIn("(allow network*)", offline)

    def test_mac_writes_only_grants_and_scratch(self):
        profile = SBX.macos_profile(self.plan("--ro", str(self.ro), "--rw", str(self.rw), backend="Darwin"), self.root)
        writable = [line for line in profile.splitlines() if line.startswith("(allow file-write*")]
        self.assertTrue(any(SBX.sbpl_path(self.project) in line and SBX.sbpl_path(self.rw) in line for line in writable))
        self.assertFalse(any(SBX.sbpl_path(self.ro) in line for line in writable))

    def test_mac_symlinks_outside_are_not_whitelisted(self):
        private = self.root / "private"
        private.mkdir()
        (self.project / "outside").symlink_to(private, target_is_directory=True)
        profile = SBX.macos_profile(self.plan(backend="Darwin"), self.root / "scratch")
        self.assertIn(SBX.sbpl_path(self.project), profile)
        self.assertNotIn(SBX.sbpl_path(private), profile)

    def test_mac_escapes_paths_as_literals_not_regex(self):
        funky = self.root / 'my [odd] "name"'
        funky.mkdir()
        profile = SBX.macos_profile(self.plan("--ro", str(funky), backend="Darwin"), self.root)
        self.assertIn(SBX.sbpl_path(funky), profile)
        self.assertNotIn(f'(regex "{funky}")', profile)

    def test_mac_git_protection(self):
        git = self.project / ".git"
        git.mkdir()
        profile = SBX.macos_profile(self.plan(backend="Darwin"), self.root)
        self.assertIn(f"(deny file-write* {SBX.sbpl_path(git)})", profile)

    def test_private_home_symlinks_reach_tracked_sources(self):
        self.make_sources()
        with tempfile.TemporaryDirectory(prefix="sbx-home-test-") as name:
            scratch = Path(name)
            SBX.prepare_private_home(self.plan(backend="Darwin"), scratch)
            home = scratch / "home"
            self.assertEqual((home / ".claude/skills/review/SKILL.md").read_text(), "skill")
            self.assertEqual((home / ".config/muse/AGENTS.md").read_text(), "instructions")
            self.assertEqual((home / ".claude/agents/worker.md").read_text(), "worker")

    def test_explain_does_not_execute(self):
        plan = self.plan("--explain", "--", "echo", "hello")
        with mock.patch.object(SBX, "parse", return_value=plan), \
             mock.patch.object(SBX.shutil, "which", return_value="/usr/bin/bwrap"), \
             mock.patch.object(SBX.subprocess, "call") as call, redirect_stdout(io.StringIO()) as out:
            self.assertEqual(SBX.main(["--explain"]), 0)
        self.assertIn("project (rw):", out.getvalue())
        self.assertIn("network: unrestricted", out.getvalue())
        call.assert_not_called()


class LiveTests(LocalFixture):
    def run_sandbox(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), *args], cwd=self.project,
                              text=True, capture_output=True, check=False)

    def test_live_read_write_and_symlink(self):
        (self.project / "ok").write_text("open", encoding="utf-8")
        (self.ro / "readable").write_text("read", encoding="utf-8")
        secret = self.root / "private"
        secret.write_text("secret", encoding="utf-8")
        (self.project / "escape").symlink_to(secret)
        code = (
            "from pathlib import Path; "
            "p=Path.cwd(); "
            "assert (p/'ok').read_text()=='open'; "
            "(p/'write').write_text('allowed'); "
            f"assert Path({str(self.ro)!r}, 'readable').read_text()=='read'; "
            f"assert not Path({str(secret)!r}).exists(); "
            "assert not (p/'escape').exists(); "
            f"assert not Path({str(self.ro)!r}, 'no').write_text('x')"
        )
        # The final expression is expected to raise an OS error on a read-only mount.
        result = self.run_sandbox("--ro", str(self.ro), "--offline", "--", "/usr/bin/python3", "-c", code)
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((self.project / "write").read_text(), "allowed")
        self.assertFalse((self.ro / "no").exists())
        self.assertEqual(secret.read_text(), "secret")

    def test_live_private_path_and_offline_network(self):
        secret = self.root / "host-secret"
        secret.write_text("private", encoding="utf-8")
        code = (
            "import pathlib,socket; "
            f"assert not pathlib.Path({str(secret)!r}).exists(); "
            "s=socket.socket(); "
            "s.settimeout(0.5); "
            "s.connect(('127.0.0.1', 9))"
        )
        result = self.run_sandbox("--offline", "--", "/usr/bin/python3", "-c", code)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Network is unreachable" if platform.system() == "Linux" else "Operation not permitted", result.stderr)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", help="run the host-kernel integration tests")
    args = parser.parse_args()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(PolicyTests)
    if args.live:
        suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(LiveTests))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return not result.wasSuccessful()


if __name__ == "__main__":
    sys.exit(main())

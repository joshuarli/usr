#!/usr/bin/env python3

import argparse
import importlib.machinery
import importlib.util
import io
import os
import shlex
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).with_name("agent-vm")
LOADER = importlib.machinery.SourceFileLoader("agent_vm", str(SCRIPT))
SPEC = importlib.util.spec_from_loader("agent_vm", LOADER)
AGENT_VM = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = AGENT_VM
SPEC.loader.exec_module(AGENT_VM)


class AgentVmTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.home = self.root / "Users" / "tester"
        self.home.mkdir(parents=True)
        self.project = self.home / "d" / "project"
        self.project.mkdir(parents=True)
        self.other = self.home / "d" / "shared library"
        self.other.mkdir(parents=True)
        self.reference = self.home / "d" / "data"
        self.reference.mkdir(parents=True)
        self.config = self.home / "usr" / "dotfiles" / "base"
        for relative in (".agents/skills", ".codex", ".claude/agents", ".grok/agents"):
            (self.config / relative).mkdir(parents=True)
        (self.config / ".codex/AGENTS.md").write_text("global instructions")
        self.env = {"HOME": str(self.home), "PWD": str(self.project)}

    def command(self, *args, cwd=None, env=None, interactive=False):
        parsed = AGENT_VM.arguments().parse_args(args)
        return AGENT_VM.command_for(parsed, str(cwd or self.project), env or self.env, interactive)

    def volumes(self, command):
        return [command[index + 1] for index, arg in enumerate(command[:-1]) if arg == "-v"]

    def test_default_mounts_only_cwd_rw_and_explicit_agent_resources_ro(self):
        command = self.command()
        volumes = self.volumes(command)
        self.assertEqual(volumes[0], f"{self.project}:{self.project}")
        self.assertEqual(
            volumes[1:],
            [
                f"{self.config / '.agents/skills'}:/opt/agent-vm/skills:ro",
                f"{self.config / '.codex'}:/opt/agent-vm/codex:ro",
                f"{self.config / '.claude/agents'}:/opt/agent-vm/claude-agents:ro",
                f"{self.config / '.grok/agents'}:/opt/agent-vm/grok-agents:ro",
            ],
        )
        self.assertEqual(command[:5], ["smolvm", "machine", "run", "--image", "node:24-bookworm"])
        self.assertIn("--block-private", command)
        self.assertIn("--net", command)
        self.assertEqual(command[command.index("--workdir") + 1], str(self.project))
        self.assertIn(f"HOME={self.home}", command)
        self.assertIn("IS_SANDBOX=1", command)
        self.assertEqual(command[-1], "/bin/bash")
        self.assertNotIn("--ssh-agent", command)
        self.assertNotIn("--secret-env", command)
        self.assertNotIn("--mount-socket", command)

    def test_guest_skill_aliases_and_global_instruction_adapters(self):
        boot = self.command()[-3]
        for path in (
            "$HOME/.agents/skills",
            "$HOME/.claude/skills",
            "$HOME/.gemini/antigravity-cli/skills",
            "$HOME/.codex/AGENTS.md",
            "$HOME/.claude/CLAUDE.md",
            "$HOME/.grok/AGENTS.md",
            "$HOME/.config/opencode/AGENTS.md",
            "$HOME/.config/muse/AGENTS.md",
            "$HOME/.gemini/config/AGENTS.md",
            "$HOME/.dsh/AGENTS.md",
            "$HOME/.claude/agents",
            "$HOME/.grok/agents",
        ):
            self.assertIn(path, boot)
        self.assertIn('exec "$@"', boot)

    def test_guest_bootstrap_installs_discovery_paths_without_host_home(self):
        guest_home = self.root / "guest-home"
        guest_home.mkdir()
        resources = self.root / "resources"
        resources.mkdir()
        for src, dest in (
            (".agents/skills", "skills"),
            (".codex", "codex"),
            (".claude/agents", "claude-agents"),
            (".grok/agents", "grok-agents"),
        ):
            (resources / dest).symlink_to(self.config / src, target_is_directory=True)
        boot = AGENT_VM.GUEST_BOOTSTRAP.replace("/opt/agent-vm", str(resources))
        env = {
            "HOME": str(guest_home),
            "AGENT_VM_CWD": str(self.project),
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        }
        result = subprocess.run(
            ["/bin/sh", "-c", boot, "agent-vm", "/bin/sh", "-c", "exit 31"],
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 31, result.stderr)
        for path in (
            ".agents/skills",
            ".claude/skills",
            ".gemini/antigravity-cli/skills",
        ):
            self.assertTrue((guest_home / path).is_dir())
        for path in (
            ".codex/AGENTS.md",
            ".claude/CLAUDE.md",
            ".grok/AGENTS.md",
            ".config/opencode/AGENTS.md",
            ".config/muse/AGENTS.md",
            ".gemini/config/AGENTS.md",
            ".dsh/AGENTS.md",
        ):
            self.assertEqual((guest_home / path).read_text(), "global instructions")
        self.assertTrue((guest_home / ".claude/agents").is_dir())
        self.assertTrue((guest_home / ".grok/agents").is_dir())
        self.assertFalse((guest_home / ".ssh").exists())

    def test_readonly_extra_and_rw_extra_are_mirrored(self):
        command = self.command("--ro", str(self.reference), "--rw", str(self.other), "--", "git", "status", "--porcelain")
        volumes = self.volumes(command)
        self.assertIn(f"{self.reference}:{self.reference}:ro", volumes)
        self.assertIn(f"{self.other}:{self.other}", volumes)
        self.assertEqual(command[-3:], ["git", "status", "--porcelain"])

    def test_relative_mounts_resolve_against_host_cwd(self):
        command = self.command("--ro", "../data")
        self.assertIn(f"{self.reference}:{self.reference}:ro", self.volumes(command))

    def test_directory_alias_keeps_logical_guest_path_but_canonical_host_source(self):
        alias = self.home / "d" / "alias"
        alias.symlink_to(self.project, target_is_directory=True)
        env = {**self.env, "PWD": str(alias)}
        command = self.command(env=env)
        self.assertEqual(self.volumes(command)[0], f"{self.project}:{alias}")
        self.assertEqual(command[command.index("--workdir") + 1], str(alias))

    def test_symlink_outside_project_does_not_add_a_mount(self):
        hidden = self.home / ".ssh"
        hidden.mkdir()
        (hidden / "key").write_text("fake key")
        (self.project / "key-link").symlink_to(hidden / "key")
        (self.project / "relative-link").symlink_to("../../.ssh/key")
        command = self.command()
        self.assertNotIn(str(hidden), "\n".join(self.volumes(command)))

    def test_conflicting_mounts_fail_instead_of_exposing_parent_alias(self):
        subdir = self.project / "packages"
        subdir.mkdir()
        for args in (
            ("--ro", str(subdir)),
            ("--rw", str(self.project)),
            ("--ro", str(self.other), "--rw", str(self.other)),
        ):
            with self.subTest(args=args), self.assertRaisesRegex(AGENT_VM.UsageError, "overlapping mounts"):
                self.command(*args)

    def test_overlapping_host_aliases_fail_even_when_guest_destinations_differ(self):
        alias = self.home / "d" / "alias"
        alias.symlink_to(self.project, target_is_directory=True)
        with self.assertRaisesRegex(AGENT_VM.UsageError, "overlapping mounts"):
            self.command("--ro", str(alias))

    def test_home_and_private_directories_cannot_be_mounted(self):
        hidden = self.home / ".ssh"
        hidden.mkdir()
        for path in (self.home, self.home.parent, hidden):
            with self.subTest(path=path), self.assertRaises(AGENT_VM.UsageError):
                self.command("--ro", str(path))
        with self.assertRaisesRegex(AGENT_VM.UsageError, "sensitive home directory"):
            self.command(cwd=hidden, env={**self.env, "PWD": str(hidden)})

    def test_sensitive_alias_rejected_after_realpath(self):
        private = self.home / ".ssh"
        private.mkdir()
        alias = self.home / "d" / "safe-name"
        alias.symlink_to(private, target_is_directory=True)
        with self.assertRaises(AGENT_VM.UsageError):
            self.command("--rw", str(alias))

    def test_sibling_named_like_private_dir_is_not_rejected(self):
        directory = self.home / ".ssh-backup-name"
        directory.mkdir()
        self.assertIn(f"{directory}:{directory}:ro", self.volumes(self.command("--ro", str(directory))))

    def test_readonly_file_and_colon_mount_rejected(self):
        file = self.project / "file"
        file.touch()
        with self.assertRaisesRegex(AGENT_VM.UsageError, "not a directory"):
            self.command("--ro", str(file))
        path = self.home / "d" / "weird:dir"
        path.mkdir()
        with self.assertRaisesRegex(AGENT_VM.UsageError, "cannot contain"):
            self.command("--rw", str(path))

    def test_offline_excludes_network_and_rejects_network_grants(self):
        command = self.command("--offline", "--no-config")
        self.assertNotIn("--net", command)
        self.assertNotIn("--block-private", command)
        for args in (
            ("--allow-host", "api.anthropic.com"),
            ("--allow-host-pattern", "api.anthropic.com"),
            ("--credential", "key=API_KEY@api.anthropic.com"),
        ):
            with self.subTest(args=args), self.assertRaises(AGENT_VM.UsageError):
                self.command("--offline", *args)

    def test_explicit_egress_allowlist_and_credential_are_forwarded(self):
        credential = "anthropic=ANTHROPIC_API_KEY@api.anthropic.com"
        command = self.command("--allow-host-pattern", "api.anthropic.com", "--credential", credential)
        self.assertIn(credential, command)
        self.assertIn("--allow-host-pattern", command)
        self.assertNotIn("--secret-env", command)

    def test_no_config_avoids_accessing_usr(self):
        command = self.command("--usr", str(self.home / "missing"), "--no-config", "--", "/bin/true")
        self.assertEqual(self.volumes(command), [f"{self.project}:{self.project}"])
        self.assertEqual(command[-1], "/bin/true")
        self.assertNotIn("/opt/agent-vm/skills", " ".join(command))

    def test_missing_skills_fail_closed(self):
        (self.config / ".codex/AGENTS.md").unlink()
        with self.assertRaisesRegex(AGENT_VM.UsageError, "missing global instructions"):
            self.command()

    def test_terminal_flag_only_for_interactive_terminals(self):
        self.assertIn("-it", self.command(interactive=True))
        self.assertNotIn("-it", self.command(interactive=False))

    def test_dry_run_does_not_launch_smolvm(self):
        with mock.patch.object(AGENT_VM.os, "getcwd", return_value=str(self.project)):
            with mock.patch.dict(AGENT_VM.os.environ, self.env, clear=True):
                with mock.patch.object(AGENT_VM.subprocess, "call") as call:
                    output = io.StringIO()
                    with redirect_stdout(output):
                        status = AGENT_VM.main(["--dry-run", "--no-config"])
        self.assertEqual(status, 0)
        call.assert_not_called()
        self.assertIn(str(self.project), output.getvalue())

    def test_exit_code_passes_through(self):
        with mock.patch.object(AGENT_VM.os, "getcwd", return_value=str(self.project)):
            with mock.patch.dict(AGENT_VM.os.environ, self.env, clear=True):
                with mock.patch.object(AGENT_VM.shutil, "which", return_value="/bin/smolvm"):
                    with mock.patch.object(AGENT_VM.subprocess, "call", return_value=41) as call:
                        self.assertEqual(AGENT_VM.main(["--no-config", "--", "false"]), 41)
        call.assert_called_once()


@unittest.skipUnless(sys.platform == "darwin", "live smolvm test requires macOS")
class LiveMacosVmTest(unittest.TestCase):
    def test_rw_and_symlink_containment(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            project = root / "project"
            project.mkdir()
            hidden = root / "hidden"
            hidden.mkdir()
            (hidden / "secret").write_text("not for guest")
            (project / "escape-absolute").symlink_to(hidden / "secret")
            (project / "escape-relative").symlink_to("../hidden/secret")
            guest_script = """
set -eu
test "$(pwd -P)" = "$AGENT_VM_EXPECTED"
if cat escape-absolute >/dev/null 2>&1; then exit 20; fi
if cat escape-relative >/dev/null 2>&1; then exit 21; fi
printf 'vm edited this' > created-by-vm
"""
            env = os.environ.copy()
            guest_script = guest_script.replace('"$AGENT_VM_EXPECTED"', shlex.quote(os.path.realpath(project)))
            result = subprocess.run(
                [str(SCRIPT), "--no-config", "--offline", "--image", "alpine", "--", "/bin/sh", "-c", guest_script],
                cwd=project,
                env=env,
                check=False,
            )
            self.assertEqual(result.returncode, 0)
            self.assertEqual((project / "created-by-vm").read_text(), "vm edited this")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", help="also run a real smolvm guest on macOS")
    options = parser.parse_args()
    suite = unittest.TestLoader().loadTestsFromTestCase(AgentVmTests)
    if options.live:
        suite.addTests(unittest.TestLoader().loadTestsFromTestCase(LiveMacosVmTest))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(not result.wasSuccessful())

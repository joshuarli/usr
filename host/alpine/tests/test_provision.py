"""Provisioner graph shape, managed-file ownership, key checks and the check-before-change guarantee."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import provision  # noqa: E402
import tuning  # noqa: E402
from dag import Graph, Probe, Task  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
SCRATCH = ROOT / ".work" / "tmp"


def scratch() -> Path:
    SCRATCH.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(dir=SCRATCH, prefix="alpine-provision-"))


def context(mode: str, arch: str = "x86_64") -> provision.Context:
    cpu = tuning.Cpu(arch, frozenset({"constant_tsc", "nonstop_tsc"}) if arch == "x86_64" else frozenset(), False)
    return provision.Context(mode, provision.User("josh", 1000, 1000, Path("/home/josh")), arch, cpu, "")


class GraphShape(unittest.TestCase):
    def names(self, mode: str, arch: str = "x86_64") -> list[str]:
        return [task.name for task in provision.graph(context(mode, arch)).order()]

    def before(self, order: list[str], first: str, then: str) -> None:
        self.assertLess(order.index(first), order.index(then), f"{first} must run before {then}")

    def test_server_graph_has_no_desktop_tasks(self) -> None:
        names = self.names("server")
        for task in ("packages", "sysctl", "boot-config", "cpu-policy", "kernel-modules", "tools", "tailscale"):
            self.assertIn(task, names)
        for task in ("desktop-packages", "dwl", "ghostty", "seat", "bridge"):
            self.assertNotIn(task, names)

    def test_desktop_graph_layers_on_server(self) -> None:
        self.assertLess(set(self.names("server")), set(self.names("desktop")))

    def test_dependency_order(self) -> None:
        order = self.names("desktop")
        self.before(order, "apk-index", "packages")
        self.before(order, "packages", "clang-config")
        self.before(order, "packages", "boot-config")
        self.before(order, "kernel-modules", "sysctl")
        self.before(order, "install-mode", "dotfiles")
        self.before(order, "dotfiles", "tools")
        self.before(order, "rustup", "tools")
        self.before(order, "tools", "login-hook")
        self.before(order, "dwl", "seat")
        self.assertEqual(order[-1], "tailscale")

    def test_microcode_ships_for_both_x86_vendors(self) -> None:
        specs = provision.packages(context("server"))
        self.assertIn("amd-ucode", specs)
        self.assertIn("intel-ucode", specs)
        self.assertNotIn("amd-ucode", provision.packages(context("server", "aarch64")))

    def test_failed_probe_command_is_a_failed_check(self) -> None:
        def broken() -> Probe:
            raise RuntimeError("su exited 1")

        task = provision.guarded(Task("t", (), broken, lambda: None, broken))
        self.assertEqual(task.probe(), Probe(False, "RuntimeError: su exited 1"))
        self.assertEqual(task.verify(), Probe(False, "RuntimeError: su exited 1"))


class CheckBeforeChange(unittest.TestCase):
    def test_any_conflict_stops_before_the_first_apply(self) -> None:
        applied: list[str] = []
        tasks = [
            Task("first", (), lambda: Probe(False, "pending"), lambda: applied.append("first"), lambda: Probe(True)),
            Task("later", ("first",), lambda: Probe(False, "foreign file", conflict=True),
                 lambda: applied.append("later"), lambda: Probe(True)),
        ]
        with mock.patch.object(provision, "preflight", return_value=context("server")), \
                mock.patch.object(provision, "graph", return_value=Graph(tasks)), \
                mock.patch("sys.stdout"), mock.patch("sys.stderr"):
            self.assertEqual(provision.apply("server", "josh", False), 1)
        self.assertEqual(applied, [])

    def test_clean_plan_applies_in_dependency_order(self) -> None:
        applied: list[str] = []
        state = {"first": False, "later": False}

        def task(name: str, needs: tuple[str, ...]) -> Task:
            return Task(name, needs, lambda: Probe(state[name]), lambda: (applied.append(name), state.update({name: True})) and None,
                        lambda: Probe(state[name]))

        with mock.patch.object(provision, "preflight", return_value=context("server", "aarch64")), \
                mock.patch.object(provision, "graph", return_value=Graph([task("later", ("first",)), task("first", ())])), \
                mock.patch.object(provision, "reboot_needed", return_value=""), \
                mock.patch("sys.stdout"):
            self.assertEqual(provision.apply("server", "josh", False), 0)
        self.assertEqual(applied, ["first", "later"])


class ManagedFiles(unittest.TestCase):
    def setUp(self) -> None:
        self.dir = scratch()
        self.addCleanup(shutil.rmtree, self.dir)

    def test_missing_file_is_pending(self) -> None:
        managed = provision.Managed(self.dir / "absent", 0o644, rendered=b"x\n")
        self.assertEqual(managed.probe(), Probe(False, f"{self.dir / 'absent'} is missing"))

    def test_foreign_content_is_a_conflict(self) -> None:
        target = self.dir / "home-session.sh"
        target.write_text("echo unmanaged\n")
        result = provision.Managed(target, 0o644, source=provision.HERE / "config/profile.sh").probe()
        self.assertTrue(result.conflict)
        self.assertIn("was not installed by home", result.detail)

    def test_older_committed_version_is_an_update(self) -> None:
        source = provision.HERE / "config/profile.sh"
        revs = subprocess.run(["git", "-C", str(ROOT), "log", "--format=%H", "--", str(source.relative_to(ROOT))],
                              capture_output=True, text=True, check=True).stdout.split()
        older = next((subprocess.run(["git", "-C", str(ROOT), "show", f"{rev}:{source.relative_to(ROOT)}"],
                                     capture_output=True, check=True).stdout for rev in revs[1:]), None)
        if older is None or older == source.read_bytes():
            self.skipTest("config/profile.sh has no distinct older version")
        target = self.dir / "home-session.sh"
        target.write_bytes(older)
        result = provision.Managed(target, 0o644, source=source).probe()
        self.assertFalse(result.conflict)
        self.assertFalse(result.current)
        self.assertIn("older version", result.detail)

    def test_matching_content_needs_root_ownership(self) -> None:
        target = self.dir / "conf"
        target.write_bytes(b"x\n")
        target.chmod(0o644)
        result = provision.Managed(target, 0o644, rendered=b"x\n").probe()
        self.assertEqual(result.current, os.geteuid() == 0)
        self.assertFalse(result.conflict)

    def test_symlink_is_a_conflict(self) -> None:
        target = self.dir / "link"
        target.symlink_to(self.dir / "elsewhere")
        self.assertTrue(provision.Managed(target, 0o644, rendered=b"x\n").probe().conflict)


class ToolLaunchers(unittest.TestCase):
    """Every launcher of every default server tool must exist; a missing one reselects exactly its tool."""

    def setUp(self) -> None:
        self.dir = scratch()
        self.addCleanup(shutil.rmtree, self.dir)
        self.home = self.dir / "home"
        (self.home / ".local/bin").mkdir(parents=True)
        user = provision.User("fixture", os.getuid(), os.getgid(), self.home)
        self.ctx = provision.Context("server", user, "x86_64", context("server").cpu, "")
        env = {**os.environ, "HOME": str(self.home), "XDG_STATE_HOME": str(self.dir / "state")}

        def as_user(_user: provision.User, script: str, *, check: bool = True) -> subprocess.CompletedProcess[str]:
            return subprocess.run(["/bin/sh", "-c", script], env=env, cwd=self.home, text=True, capture_output=True, check=check)

        patcher = mock.patch.object(provision, "as_user", as_user)
        patcher.start()
        self.addCleanup(patcher.stop)
        tools = as_user(user, provision.sync_cmd(self.ctx, "list", profile=True)).stdout.split()
        out = as_user(user, f"python3 -I '{ROOT}/tools/sync/main.py' launchers {' '.join(tools)}").stdout
        self.launchers = {line.split()[0]: line.split()[1:] for line in out.splitlines() if line.strip()}
        self.launchers.pop("agy", None)
        for names in self.launchers.values():
            for name in names:
                path = self.home / ".local/bin" / name
                if name == "python3":
                    path.symlink_to(sys.executable)
                    continue
                path.write_text("#!/bin/sh\nexit 0\n")
                path.chmod(0o755)

    def test_unusable_sync_is_an_error_not_an_empty_profile(self) -> None:
        (self.home / ".local/bin/python3").unlink()
        (self.home / ".local/bin/python3").write_text("#!/bin/sh\nexit 0\n")
        (self.home / ".local/bin/python3").chmod(0o755)
        with self.assertRaisesRegex(RuntimeError, "printed no tools"):
            provision.missing_tools(self.ctx)

    def test_complete_profile_needs_nothing(self) -> None:
        self.assertIn("shuck", self.launchers)
        self.assertEqual(provision.missing_tools(self.ctx), [])

    def test_each_missing_launcher_selects_its_tool(self) -> None:
        for tool, names in self.launchers.items():
            for name in names:
                with self.subTest(tool=tool, launcher=name):
                    path = self.home / ".local/bin" / name
                    path.rename(self.dir / "removed")
                    try:
                        self.assertEqual(provision.missing_tools(self.ctx), [tool])
                    finally:
                        (self.dir / "removed").rename(path)


@unittest.skipUnless(shutil.which("ssh-keygen"), "ssh-keygen is required")
class GithubKeyMatch(unittest.TestCase):
    def setUp(self) -> None:
        self.dir = scratch()
        self.addCleanup(shutil.rmtree, self.dir)

    def keygen(self, name: str, kind: str = "ed25519", passphrase: str = "", comment: str = "original") -> Path:
        path = self.dir / name
        subprocess.run(["ssh-keygen", "-q", "-t", kind, "-N", passphrase, "-f", str(path), "-C", comment],
                       stdin=subprocess.DEVNULL, check=True)
        return path

    def pub(self, name: str, text: str) -> Path:
        path = self.dir / name
        path.write_text(text)
        return path

    def test_comments_are_ignored(self) -> None:
        key = self.keygen("github")
        material = " ".join(Path(f"{key}.pub").read_text().split()[:2])
        self.assertTrue(provision.public_key_matches(key, Path(f"{key}.pub")))
        self.assertTrue(provision.public_key_matches(key, self.pub("bare.pub", material + "\n")))
        self.assertTrue(provision.public_key_matches(key, self.pub("other.pub", material + " a different comment\n")))
        bare = self.keygen("nocomment", comment="")
        self.assertTrue(provision.public_key_matches(bare, Path(f"{bare}.pub")))

    def test_mismatches_are_refused(self) -> None:
        key = self.keygen("github")
        other = self.keygen("other")
        kind, material = Path(f"{key}.pub").read_text().split()[:2]
        flipped = material[:-1] + ("B" if material[-1] == "A" else "A")
        rsa = self.keygen("rsa", "rsa")
        encrypted = self.keygen("encrypted", passphrase="secret")
        self.assertFalse(provision.public_key_matches(key, Path(f"{other}.pub")))
        self.assertFalse(provision.public_key_matches(key, self.pub("tampered.pub", f"{kind} {flipped}\n")))
        self.assertFalse(provision.public_key_matches(rsa, Path(f"{key}.pub")))
        self.assertFalse(provision.public_key_matches(encrypted, Path(f"{encrypted}.pub")))
        self.assertFalse(provision.public_key_matches(key, self.pub("garbage.pub", "not a public key\n")))
        self.assertFalse(provision.public_key_matches(key, self.pub("empty.pub", "")))


if __name__ == "__main__":
    unittest.main()

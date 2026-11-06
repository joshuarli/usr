"""Exercise the public shell facade with disposable homes and fake leaf installers."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parent
sys.path.insert(0, str(SOURCE))
SYNC = SOURCE.parents[1] / "sync"


class SyncIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for relative in ("tools/sync", "dotfiles/base", "dotfiles/linux", "bin", "home"):
            (self.root / relative).mkdir(parents=True, exist_ok=True)
        for name in ("dag.py", "main.py", "uninstall.py", "ownership.py", "links.py", "link_plan.py", "link_apply.py", "link_recovery.py"):
            shutil.copy2(SOURCE / name, self.root / "tools/sync" / name)
        shutil.copy2(SYNC, self.root / "sync")
        self._script("bin/uname", '#!/bin/sh\nprintf "Linux\\n"\n')
        self._script("dotfiles/migrate-pinact.sh", "#!/bin/sh\nexit 0\n")
        self._script("tools/sync/install.sh", '''#!/bin/sh
if [ "$1" = --list ]; then printf 'nodejs\\ncmd\\n'; exit 0; fi
if [ "$1" = lease-tool ]; then
  mkdir -p "$HOME/.local/bin" "$(dirname "$DL_OWNED_FILE")"
  printf 'F\\t%s\\n' "$HOME/.local/bin/lease-tool" >> "$DL_OWNED_FILE"
  touch "$HOME/installer-ready"
  while [ ! -f "$HOME/installer-release" ]; do sleep 0.02; done
  printf '#!/bin/sh\\nexit 0\\n' > "$HOME/.local/bin/lease-tool"
  chmod +x "$HOME/.local/bin/lease-tool"
  printf 'F\\t%s\\n' "$HOME/.local/bin/lease-tool" >> "$SYNC_OWNED_CLAIMS"
  printf changed > "$SYNC_INSTALL_CHANGED_FILE"
  exit 0
fi
printf '%s\\n' "$1" >> "$HOME/installed"
mkdir -p "$HOME/.local/bin"
case "$1" in nodejs) set -- node npm ;; esac
for name in "$@"; do printf '#!/bin/sh\\nexit 0\\n' > "$HOME/.local/bin/$name"; chmod +x "$HOME/.local/bin/$name"; done
''')
        self.env = dict(os.environ, HOME=str(self.root / "home"),
                        PATH=str(self.root / "bin") + os.pathsep + os.environ.get("PATH", ""),
                        DL_PROFILE="server", TARGET=str(self.root / "home"))

    def _script(self, path: str, content: str) -> None:
        file = self.root / path
        file.write_text(content)
        file.chmod(0o755)

    def run_sync(self, *args: str, success: bool = True):
        result = subprocess.run(["sh", str(self.root / "sync"), *args], env=self.env,
                                text=True, capture_output=True, timeout=20)
        self.assertEqual(result.returncode == 0, success, result.stdout + result.stderr)
        return result

    def test_named_command_installs_only_dependency_closure(self):
        self.run_sync("tools", "cmd")
        self.assertEqual((self.root / "home/installed").read_text().splitlines(), ["nodejs", "cmd"])
        self.run_sync("tools", "cmd")
        self.assertEqual((self.root / "home/installed").read_text().splitlines(),
                         ["nodejs", "cmd", "nodejs", "cmd"])

    def test_links_plan_and_apply_without_sym_shell(self):
        source = self.root / "dotfiles/base/.config/app.conf"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text("hello")
        plan = self.run_sync("plan").stdout
        self.assertIn("LINK:", plan)
        self.assertFalse((self.root / "home/.config/app.conf").exists())
        self.run_sync("links")
        link = self.root / "home/.config/app.conf"
        self.assertTrue(link.is_symlink())
        self.assertEqual(link.read_text(), "hello")
        self.run_sync("links")
        self.assertIn("CURRENT", self.run_sync("plan").stdout)

    def test_links_foreign_file_blocks_entire_apply(self):
        self.root.joinpath("dotfiles/base/first").write_text("first")
        self.root.joinpath("dotfiles/base/second").write_text("second")
        self.root.joinpath("home/second").write_text("custom")
        self.run_sync("links", success=False)
        self.assertEqual(self.root.joinpath("home/second").read_text(), "custom")
        self.assertFalse(self.root.joinpath("home/first").exists())

    def test_link_and_tool_sync_share_one_interprocess_ownership_lease(self):
        from ownership import records, read_manifest
        source = self.root / "dotfiles/base/.profile"
        source.write_text("source")
        tool = subprocess.Popen(["sh", str(self.root / "sync"), "tools", "lease-tool"], env=self.env,
                                text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        ready = self.root / "home/installer-ready"
        released = self.root / "home/installer-release"
        link = None
        try:
            for _ in range(150):
                if ready.exists(): break
                self.assertIsNone(tool.poll(), "installer exited before readiness")
                time.sleep(0.02)
            self.assertTrue(ready.exists(), "installer did not reach locked state")
            link = subprocess.Popen(["sh", str(self.root / "sync"), "links"], env=self.env,
                                    text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            time.sleep(0.12)
            self.assertIsNone(link.poll(), "link sync must block on tool's ownership lease")
            self.assertFalse((self.root / "home/.profile").exists())
        finally:
            released.touch()
            tool_out, tool_err = tool.communicate(timeout=12)
            self.assertEqual(tool.returncode, 0, tool_out + tool_err)
            if link is not None:
                link_out, link_err = link.communicate(timeout=12)
                self.assertEqual(link.returncode, 0, link_out + link_err)
        ownership = self.root / "home/.local/state/sync/dl-owned"
        found = records(ownership)
        self.assertIn(("F", self.root / "home/.local/bin/lease-tool"), found)
        self.assertIn(("F", self.root / "home/.profile"), found)
        proofs = read_manifest(ownership)
        self.assertIn(str(self.root / "home/.profile"), proofs)
        self.assertIn(str(self.root / "home/.local/bin/lease-tool"), proofs)

    def test_symlinked_ownership_lease_is_refused(self):
        self.root.joinpath("dotfiles/base/.profile").write_text("source")
        state = self.root / "home/.local/state/sync"
        state.mkdir(parents=True)
        outside = self.root / "foreign-lock"
        outside.write_text("keep")
        (state / "dl-owned.lock").symlink_to(outside)
        result = self.run_sync("links", success=False)
        self.assertIn("failed", result.stdout.lower())
        self.assertEqual(outside.read_text(), "keep")
        self.assertFalse((self.root / "home/.profile").exists())

    def test_plan_does_not_change_home(self):
        self.assertIn("nodejs", self.run_sync("list").stdout)
        plan = self.run_sync("plan").stdout
        self.assertIn("APPLY    tool:nodejs", plan)
        self.assertIn("APPLY    tool:cmd", plan)
        self.assertFalse((self.root / "home/installed").exists())


if __name__ == "__main__":
    unittest.main()

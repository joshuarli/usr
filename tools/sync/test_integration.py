"""Exercise the public shell facade with disposable homes and fake leaf installers."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parent
SYNC = SOURCE.parents[1] / "sync"


class SyncIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for relative in ("tools/sync", "dotfiles/base", "dotfiles/linux", "bin", "home"):
            (self.root / relative).mkdir(parents=True, exist_ok=True)
        for name in ("dag.py", "main.py", "uninstall.py"):
            shutil.copy2(SOURCE / name, self.root / "tools/sync" / name)
        shutil.copy2(SYNC, self.root / "sync")
        self._script("bin/uname", '#!/bin/sh\nprintf "Linux\\n"\n')
        self._script("dotfiles/sym", "#!/bin/sh\nexit 0\n")
        self._script("dotfiles/migrate-pinact.sh", "#!/bin/sh\nexit 0\n")
        self._script("tools/sync/install.sh", '''#!/bin/sh
if [ "$1" = --list ]; then printf 'nodejs\\ncmd\\n'; exit 0; fi
printf '%s\\n' "$1" >> "$HOME/installed"
mkdir -p "$HOME/.local/bin"
case "$1" in nodejs) set -- node npm ;; esac
for name in "$@"; do printf '#!/bin/sh\\nexit 0\\n' > "$HOME/.local/bin/$name"; chmod +x "$HOME/.local/bin/$name"; done
''')
        self.env = dict(os.environ, HOME=str(self.root / "home"),
                        PATH=str(self.root / "bin") + os.pathsep + os.environ.get("PATH", ""),
                        DL_PROFILE="server")

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

    def test_plan_does_not_change_home(self):
        self.assertIn("nodejs", self.run_sync("list").stdout)
        plan = self.run_sync("plan").stdout
        self.assertIn("APPLY    tool:nodejs", plan)
        self.assertIn("APPLY    tool:cmd", plan)
        self.assertFalse((self.root / "home/installed").exists())


if __name__ == "__main__":
    unittest.main()

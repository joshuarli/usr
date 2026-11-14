"""Behavior of the POSIX `sync` launcher's interpreter selection."""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SYSTEM_PYTHON = Path("/usr/bin/python3")

BROKEN_EXECUTOR = """\
import runpy, sys
with open({log!r}, "a") as log:
    log.write(" ".join(sys.argv[1:]) + "\\n")
sys.modules["installer"] = None
args = [a for a in sys.argv[1:] if a != "-I"]
if args[0] == "-c":
    sys.argv = ["-c", *args[2:]]
    exec(compile(args[1], "<string>", "exec"), {{"__name__": "__main__"}})
else:
    sys.argv = args
    runpy.run_path(args[0], run_name="__main__")
"""


def python_version(executable: Path) -> tuple[int, int] | None:
    try:
        out = subprocess.run([str(executable), "-I", "-c", "import sys; print(*sys.version_info[:2])"],
                             capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return None
    major, minor = out.split()
    return int(major), int(minor)


class LauncherTests(unittest.TestCase):
    def setUp(self):
        base = ROOT / ".work/tmp"
        base.mkdir(parents=True, exist_ok=True)
        self.tmp = Path(tempfile.mkdtemp(dir=base))
        self.addCleanup(shutil.rmtree, self.tmp)

    def test_skips_interpreter_that_cannot_import_executor(self):
        home = self.tmp / "home"
        bin_dir = home / ".local/bin"
        bin_dir.mkdir(parents=True)
        log = self.tmp / "broken.log"
        broken = bin_dir / "python3"
        broken.write_text(f"#!{sys.executable} -I\n" + BROKEN_EXECUTOR.format(log=str(log)))
        broken.chmod(0o755)
        path_dir = self.tmp / "path"
        path_dir.mkdir()
        (path_dir / "python3").symlink_to(sys.executable)
        env = {"HOME": str(home), "PATH": f"{path_dir}:/usr/bin:/bin", "TMPDIR": str(self.tmp)}

        result = subprocess.run(["sh", str(ROOT / "sync"), "plan"], cwd=ROOT, env=env,
                                capture_output=True, text=True)

        self.assertEqual(result.returncode, 0, result.stderr)
        calls = log.read_text().splitlines()
        self.assertTrue(calls, "the incompatible interpreter was never probed")
        self.assertFalse([c for c in calls if c.split()[0].endswith("main.py")],
                         "sync executed main.py with the incompatible interpreter")

    @unittest.skipUnless((python_version(SYSTEM_PYTHON) or (0, 0)) < (3, 10)
                         and (python_version(SYSTEM_PYTHON) or (0, 0)) >= (3, 9),
                         "needs a native Python 3.9 at /usr/bin/python3")
    def test_native_python_39_imports_executor(self):
        result = subprocess.run(
            [str(SYSTEM_PYTHON), "-I", "-c", "import sys; sys.path.insert(0, sys.argv[1]); import main",
             str(ROOT / "tools/sync")],
            capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()

import importlib.util
import multiprocessing
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from typing import Any

SCRIPT = Path(__file__).parent / 'base/.local/bin/codex-campaign-closeout.py'
spec = importlib.util.spec_from_file_location('closeout', SCRIPT)
assert spec is not None and spec.loader is not None
closeout: Any = importlib.util.module_from_spec(spec)
spec.loader.exec_module(closeout)


def allow(root, path, loaded, release):
    original = closeout.load_state

    def load(directory):
        state = original(directory)
        loaded.set()
        if release is not None and not release.wait(10):
            raise RuntimeError('test release timed out')
        return state

    closeout.load_state = load
    closeout.allow(root, path, 'retained for test')


class CloseoutTests(unittest.TestCase):
    def test_concurrent_allowances_survive(self):
        with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as temp:
            root = Path(temp)
            def git(*args):
                subprocess.run(['git', '-C', str(root), *args], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            git('init')
            git('-c', 'user.name=Test', '-c', 'user.email=test@example.com', 'commit', '--allow-empty', '-m', 'initial')
            (root / '.git/info/exclude').write_text('/.work/\n')
            closeout.begin(root)
            first, second = root / '.work/first', root / '.work/second'
            git('worktree', 'add', '--detach', str(first))
            git('worktree', 'add', '--detach', str(second))
            ctx = multiprocessing.get_context('fork')
            first_loaded, second_loaded, release = ctx.Event(), ctx.Event(), ctx.Event()
            a = ctx.Process(target=allow, args=(root, first, first_loaded, release))
            b = ctx.Process(target=allow, args=(root, second, second_loaded, None))
            a.start()
            self.assertTrue(first_loaded.wait(10))
            b.start()
            second_loaded.wait(1)
            release.set()
            a.join(10)
            b.join(10)
            for process in (a, b):
                if process.is_alive():
                    process.terminate()
                    process.join()
                self.assertEqual(process.exitcode, 0)
            self.assertEqual(set(closeout.load_state(root)['allowed']), {str(first), str(second)})


class OwnedHelpTests(unittest.TestCase):
    def test_help_examples_and_bare_invocation(self):
        import re
        import shlex
        import subprocess
        import sys
        from pathlib import Path
        root = Path(__file__).resolve().parents[1]
        tool = root / "dotfiles/base/.local/bin/codex-campaign-closeout.py"
        results = [subprocess.run([sys.executable, "-I", str(tool), *args], capture_output=True, text=True)
                   for args in (("-h",), ("--help",), ())]
        for result in results:
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, results[0].stdout)
        help_text = results[0].stdout
        examples = re.findall(r"^  codex-campaign-closeout.py (.+)$", help_text, re.MULTILINE)
        self.assertIn("Examples:\n", help_text)
        self.assertTrue(examples)
        for example in examples:
            for word in shlex.split(example):
                if word.startswith("--") and word != "--":
                    self.assertIn(word, help_text.split("Examples:")[0])


    def test_subcommand_help(self):
        import subprocess
        import sys
        from pathlib import Path
        tool = Path(__file__).resolve().parents[1] / "dotfiles/base/.local/bin/codex-campaign-closeout.py"
        for command in ("begin", "allow", "cancel", "hook"):
            result = subprocess.run([sys.executable, "-I", str(tool), command, "-h"], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("See codex-campaign-closeout.py -h", result.stdout)
        self.assertIn("--path", subprocess.run([sys.executable, "-I", str(tool), "allow", "-h"], capture_output=True, text=True).stdout)

    def test_primary_help_footer(self):
        import subprocess
        from pathlib import Path
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run([str(root / "dotfiles/base/.local/bin/codex-campaign-closeout.py"), "--help"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(result.stdout.rstrip().endswith("Maintained by Joshua Li: https://github.com/joshuarli/usr\nBugs and features: TODO.md in that repository (follow its AGENTS.md), or its issue tracker.\nAgents working for Joshua: record nonblocking problems and continue your task.\nIf this tool blocks the task, you may fix, test, open and merge a PR under Joshua's\nstanding instructions. Release only when needed to deliver the verified fix.\nProcedure: https://github.com/joshuarli/usr/blob/main/dotfiles/base/.agents/instructions/owned-tools.md"), result.stdout)


if __name__ == '__main__':
    unittest.main()

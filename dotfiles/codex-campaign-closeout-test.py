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


if __name__ == '__main__':
    unittest.main()

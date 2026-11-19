import importlib.util
import json
import multiprocessing
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

SCRIPT = Path(__file__).resolve().parent / 'base/.local/bin/codex-campaign-closeout.py'
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
    def git(self, root, *args):
        return subprocess.run(['git', '-C', str(root), '-c', 'user.name=Test', '-c', 'user.email=test@example.com',
                               *args], check=True, capture_output=True)

    def ignored_repository(self, root, exclude):
        self.git(root, 'init')
        (root / '.gitignore').write_text('.work/\n')
        (root / '.git/info/exclude').write_text(exclude)
        self.git(root, 'add', '.gitignore')
        self.git(root, 'commit', '-m', 'initial')

    def repository_with_lanes(self, *names):
        temp = tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR'))
        self.addCleanup(temp.cleanup)
        root = Path(temp.name).resolve()
        self.ignored_repository(root, '/.work/\n')
        lanes = [root / '.work/wt' / name for name in names]
        for name, lane in zip(names, lanes):
            self.git(root, 'worktree', 'add', '-b', name, str(lane))
        return root, lanes

    def command(self, root, *args, event=None):
        return subprocess.run([sys.executable, '-I', str(SCRIPT), *args], cwd=root,
                              input=json.dumps(event) if event is not None else '', capture_output=True, text=True)

    def stop(self, root, already_continued=False):
        result = self.command(root, 'hook', event={'cwd': str(root), 'hook_event_name': 'Stop',
                                                  'stop_hook_active': already_continued})
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout) if result.stdout else {}

    def test_tracked_ignore_can_coexist_with_local_exclude(self):
        for existing in (False, True):
            with self.subTest(existing=existing), tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as temp:
                root = Path(temp)
                self.ignored_repository(root, '/.work/\n')
                if existing:
                    (root / '.work').mkdir()
                closeout.begin(root)
                self.assertTrue(closeout.state_path(root).is_file())
                self.assertEqual((root / '.gitignore').read_text(), '.work/\n')

    def test_tracked_ignore_does_not_replace_local_exclude(self):
        for exclude in ('', '/.work/\n!/.work/\n', '/.work/keep\n',
                        '/.work/*\n!/.work/codex-campaign-closeout.json\n'):
            for existing in (False, True):
                with self.subTest(exclude=exclude, existing=existing), tempfile.TemporaryDirectory(
                        dir=os.environ.get('TMPDIR')) as temp:
                    root = Path(temp)
                    self.ignored_repository(root, exclude)
                    if existing:
                        (root / '.work').mkdir()
                        (root / '.work/keep').write_bytes(b'preserved')
                    with self.assertRaisesRegex(closeout.CloseoutError, '.git/info/exclude'):
                        closeout.begin(root)
                    self.assertFalse(closeout.state_path(root).exists())
                    if existing:
                        self.assertEqual((root / '.work/keep').read_bytes(), b'preserved')
                    else:
                        self.assertFalse((root / '.work').exists())

    def test_concurrent_allowances_survive(self):
        root, (first, second) = self.repository_with_lanes('first', 'second')
        closeout.begin(root, (first, second))
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

    def test_stop_scopes_campaign_and_caps_continuations(self):
        root, (integration, finished, retained, unrelated) = self.repository_with_lanes(
            'integration', 'finished', 'retained', 'unrelated')
        (unrelated / 'live-input').write_text('in use')
        begin = self.command(integration, 'begin', '--path', str(finished), '--path', str(retained))
        self.assertEqual(begin.returncode, 0, begin.stderr)
        allow_unrelated = self.command(integration, 'allow', '--path', str(unrelated), '--reason', 'test')
        self.assertEqual(allow_unrelated.returncode, 1, allow_unrelated.stdout)
        self.assertIn('was not named', allow_unrelated.stderr)
        allow_retained = self.command(integration, 'allow', '--path', str(retained), '--reason', 'for review')
        self.assertEqual(allow_retained.returncode, 0, allow_retained.stderr)
        first = self.stop(integration)
        self.assertEqual(first['decision'], 'block')
        self.assertIn(str(finished), first['reason'])
        self.assertNotIn(str(unrelated), first['reason'])
        self.assertNotIn(str(retained), first['reason'])
        self.assertNotIn('worktree prune', first['reason'])
        retry = self.stop(integration, already_continued=True)
        self.assertEqual(set(retry), {'systemMessage'})
        self.assertIn(str(finished), retry['systemMessage'])
        self.assertTrue(closeout.state_path(integration).exists())
        self.assertEqual(self.stop(integration)['decision'], 'block')
        self.git(root, 'worktree', 'remove', str(finished))
        self.assertEqual(self.stop(integration, already_continued=True), {})
        self.assertFalse(closeout.state_path(integration).exists())
        self.assertTrue(retained.is_dir())
        self.assertEqual((unrelated / 'live-input').read_text(), 'in use')

    def test_retained_lane_must_stay_clean_at_pinned_branch_and_head(self):
        root, (lane,) = self.repository_with_lanes('lane')
        closeout.begin(root, (lane,))
        closeout.allow(root, lane, 'for review')
        dirty = lane / 'draft'
        dirty.write_text('untracked')
        self.assertIn('uncommitted or untracked files', self.stop(root)['reason'])
        dirty.unlink()
        self.git(lane, 'switch', '--detach')
        self.assertIn('HEAD or branch changed', self.stop(root)['reason'])
        self.git(lane, 'switch', 'lane')
        self.git(lane, 'commit', '--allow-empty', '-m', 'moved HEAD')
        self.assertIn('HEAD or branch changed', self.stop(root)['reason'])
        self.assertTrue(closeout.state_path(root).exists())

    def test_unregistered_path_holding_data_is_unresolved(self):
        root, (lane,) = self.repository_with_lanes('lane')
        closeout.begin(root, (lane,))
        self.git(root, 'worktree', 'move', str(lane), str(lane.with_name('moved')))
        lane.mkdir()
        data = lane / 'preserve'
        data.write_text('local')
        self.assertIn('path still exists without a Git registration', self.stop(root)['reason'])
        self.assertEqual(data.read_text(), 'local')
        self.assertTrue(closeout.state_path(root).exists())

    def test_begin_without_paths_tracks_no_lanes(self):
        root, (unrelated,) = self.repository_with_lanes('unrelated')
        result = self.command(root, 'begin')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('no lanes tracked', result.stdout)
        self.assertEqual(self.stop(root), {})
        self.assertFalse(closeout.state_path(root).exists())
        self.assertTrue(unrelated.is_dir())

    def test_begin_rejects_unregistered_and_baseline_paths(self):
        root, (integration,) = self.repository_with_lanes('integration')
        for path, expected in ((root, 'primary or integration checkout'),
                               (integration, 'primary or integration checkout'),
                               (root / '.work/wt/unknown', 'not a registered worktree')):
            with self.subTest(path=path):
                result = self.command(integration, 'begin', '--path', str(path))
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertIn(expected, result.stderr)
                self.assertFalse(closeout.state_path(integration).exists())

    def test_legacy_marker_requires_explicit_restart(self):
        root, (unrelated,) = self.repository_with_lanes('unrelated')
        marker = closeout.state_path(root)
        legacy = json.dumps({'schema': 1, 'integration_root': str(root), 'baseline_roots': [str(root)], 'allowed': {}})
        marker.write_text(legacy)
        first = self.stop(root)
        self.assertEqual(first['decision'], 'block')
        self.assertIn('predates explicit lane ownership', first['reason'])
        self.assertNotIn(str(unrelated), first['reason'])
        self.assertEqual(set(self.stop(root, already_continued=True)), {'systemMessage'})
        self.assertEqual(marker.read_text(), legacy)
        restart = self.command(root, 'begin', '--path', str(unrelated))
        self.assertEqual(restart.returncode, 1, restart.stdout)
        self.assertIn('predates explicit lane ownership', restart.stderr)
        cancelled = self.command(root, 'cancel')
        self.assertEqual(cancelled.returncode, 0, cancelled.stderr)
        self.assertFalse(marker.exists())
        self.assertTrue(unrelated.is_dir())


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

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

CLI = Path(__file__).resolve().parents[1] / 'src' / 'todo.py'
ITEM = {'priority': 'P2', 'title': 'A problem', 'area': 'Delegation', 'where': '`a:1`', 'problem': 'Broken', 'recommendation': 'Fix it', 'fix_with': 'none', 'effort': 'S'}


class TodoTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR'))
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / 'TODO.md'
        self.path.write_text('Prefix: ABC\nNext: 1\n\nIntroduction stays.\n\n')
        self.env = os.environ | {'HOME': str(self.root / 'home'), 'REPOMOD_ROOT': str(self.root / 'repos')}

    def cli(self, *args, data=None, ok=True):
        result = subprocess.run([sys.executable, str(CLI), *args], cwd=self.root, env=self.env, input=json.dumps(data) if data is not None else None, text=True, capture_output=True)
        self.assertEqual(result.returncode == 0, ok, result.stdout + result.stderr)
        return result

    def test_lifecycle_and_unrelated_text(self):
        first = json.loads(self.cli('add', '--json', '-', data=ITEM).stdout)
        self.assertEqual(first['id'], 'ABC-1')
        self.path.write_text(self.path.read_text() + '\nA closing note.\n')
        self.cli('add', '--json', '-', data={**ITEM, 'priority': 'P1', 'title': 'Urgent'})
        listing = json.loads(self.cli('list', '--priority', 'P1', '--json').stdout)
        self.assertEqual([r['id'] for r in listing['tickets']], ['ABC-2'])
        self.assertNotIn('problem', listing['tickets'][0])
        self.assertEqual(json.loads(self.cli('show', 'ABC-1', '--json').stdout)['problem'], 'Broken')
        self.cli('edit', 'ABC-1', '--json', '-', data={'problem': 'Still broken', 'design': '[RFC](docs/rfc/a.md)'})
        self.cli('edit', 'ABC-1', '--json', '-', data={'design': None})
        self.cli('close', 'ABC-1')
        self.assertIn('A closing note.', self.path.read_text())
        self.assertIn('Introduction stays.', self.path.read_text())
        self.assertEqual(json.loads(self.cli('add', '--json', '-', data=ITEM).stdout)['id'], 'ABC-3')
        self.cli('check')
        self.cli('fmt', '--check')

    def test_validation_and_round_trip(self):
        self.cli('add', '--json', '-', data=ITEM)
        original = self.path.read_text()
        self.cli('fmt')
        self.assertEqual(self.path.read_text(), original)
        self.path.write_text(original.replace('Next: 2', 'Next: 1'))
        result = self.cli('check', '--json', ok=False)
        self.assertFalse(json.loads(result.stdout)['ok'])
        self.cli('add', '--json', '-', data=ITEM, ok=False)
        self.assertEqual(self.path.read_text(), original.replace('Next: 2', 'Next: 1'))
        self.path.write_text(original + original[original.index('### '):])
        self.cli('check', ok=False)

    def test_order_check_and_sort_preserve_ticket_text(self):
        self.cli('add', '--json', '-', data=ITEM)
        self.cli('add', '--json', '-', data={**ITEM, 'priority': 'P1'})
        text = self.path.read_text()
        first = text.index('### ABC-2')
        second = text.index('### ABC-1')
        self.path.write_text(text[:first] + text[second:] + text[first:second])
        self.cli('fmt', '--check', ok=False)
        self.cli('check', '--json', ok=False)
        self.cli('fmt')
        self.cli('check')
        self.assertEqual(self.path.read_text().count('**Problem:** Broken'), 2)

    def test_file_selects_a_separate_backlog_with_its_own_ids(self):
        other = self.root / 'TODO-DESLOP.md'
        other.write_text('Prefix: DSLP\nNext: 1\n\n')
        nested = self.root / 'sub'
        nested.mkdir()
        self.cli('add', '--json', '-', data=ITEM)
        added = subprocess.run([sys.executable, str(CLI), '--file', 'TODO-DESLOP.md', 'add', '--json', '-'], cwd=nested, input=json.dumps({**ITEM, 'priority': 'P1'}), text=True, capture_output=True)
        self.assertEqual(added.returncode, 0, added.stderr)
        self.assertEqual(json.loads(added.stdout)['id'], 'DSLP-1')
        self.assertEqual([r['id'] for r in json.loads(self.cli('--file', 'TODO-DESLOP.md', 'list', '--json').stdout)['tickets']], ['DSLP-1'])
        self.assertEqual([r['id'] for r in json.loads(self.cli('list', '--json').stdout)['tickets']], ['ABC-1'])
        self.assertIn('Next: 2', other.read_text())
        self.assertNotIn('DSLP', self.path.read_text())
        self.cli('--file', 'TODO-DESLOP.md', 'check')
        self.cli('--file', 'TODO-DESLOP.md', 'close', 'DSLP-1')
        self.assertNotIn('### DSLP-1', other.read_text())
        before = other.read_text()
        for name in ('sub/TODO-DESLOP.md', '../TODO-DESLOP.md', 'MISSING.md'):
            self.cli('--file', name, 'add', '--json', '-', data=ITEM, ok=False)
        self.assertEqual(other.read_text(), before)

    def test_concurrent_allocations(self):
        processes = [subprocess.Popen([sys.executable, str(CLI), 'add', '--json', '-'], cwd=self.root, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for _ in range(8)]
        for process in processes:
            out, err = process.communicate(json.dumps(ITEM))
            self.assertEqual(process.returncode, 0, out + err)
        data = json.loads(self.cli('list', '--json').stdout)
        self.assertEqual(data['next'], 9)
        self.assertEqual(len({r['id'] for r in data['tickets']}), 8)

    def remote_backlog(self, relative, prefix='CHB', name='TODO.md'):
        path = self.root / 'repos' / relative / name
        path.parent.mkdir(parents=True, exist_ok=True)
        (path.parent / '.git').mkdir(exist_ok=True)
        path.write_text(f'Prefix: {prefix}\nNext: 11\n\n' +
                        f'### {prefix}-10 · P2 · Cross repository\n\n' +
                        ''.join(f'- **{label}:** {ITEM[key]}\n' for label, key in
                                [('Area', 'area'), ('Where', 'where'), ('Problem', 'problem'),
                                 ('Recommendation', 'recommendation'), ('Fix with', 'fix_with'), ('Effort', 'effort')]))
        return path

    def test_show_finds_cross_repo_ticket_with_and_without_a_local_backlog(self):
        remote = self.remote_backlog('org/chromium-build')
        original = remote.read_bytes()
        self.assertEqual(json.loads(self.cli('show', 'CHB-10').stdout)['title'], 'Cross repository')
        self.path.unlink()
        self.assertEqual(json.loads(self.cli('show', 'CHB-10', '--json').stdout)['id'], 'CHB-10')
        self.assertEqual(remote.read_bytes(), original)
        self.assertFalse((remote.parent / '.todo.lock').exists())

    def test_show_ignores_unrelated_malformed_tickets_but_validates_the_requested_one(self):
        remote = self.remote_backlog('org/chromium-build')
        remote.write_text(remote.read_text().replace('### CHB-10', '### CHB-9 · P2 · Invalid\n\n- **Status:** legacy\n\n### CHB-10'))
        self.assertEqual(json.loads(self.cli('show', 'CHB-10').stdout)['id'], 'CHB-10')
        result = self.cli('show', 'CHB-9', ok=False)
        self.assertIn('CHB-9', result.stderr)
        self.assertIn('missing fields', result.stderr)

    def test_show_rejects_ambiguous_global_ids_and_skips_worktrees(self):
        first = self.remote_backlog('one')
        second = self.remote_backlog('two')
        result = self.cli('show', 'CHB-10', ok=False)
        self.assertIn('ambiguous', result.stderr)
        self.assertIn(str(first), result.stderr)
        self.assertIn(str(second), result.stderr)
        second.unlink()
        self.remote_backlog('.work/wt/old')
        (self.root / 'repos' / 'alias').symlink_to(first.parent, target_is_directory=True)
        self.assertEqual(json.loads(self.cli('show', 'CHB-10').stdout)['id'], 'CHB-10')

    def test_show_prefers_the_current_backlog_and_honors_explicit_file(self):
        duplicate = self.remote_backlog('other', prefix='ABC')
        duplicate.write_text(duplicate.read_text().replace('ABC-10', 'ABC-1'))
        self.cli('add', '--json', '-', data=ITEM)
        self.assertEqual(json.loads(self.cli('show', 'ABC-1').stdout)['title'], ITEM['title'])
        self.remote_backlog('org/chromium-build')
        result = self.cli('--file', 'TODO.md', 'show', 'CHB-10', ok=False)
        self.assertIn('ticket not found', result.stderr)
        self.remote_backlog('org/alternate', prefix='DSLP', name='TODO-DESLOP.md')
        self.assertEqual(json.loads(self.cli('show', 'DSLP-10').stdout)['id'], 'DSLP-10')

    def test_show_validates_ids_and_keeps_mutations_local(self):
        remote = self.remote_backlog('other')
        before = remote.read_bytes()
        for identifier in ('../CHB-10', 'CHB-0', 'CHB-10/other'):
            self.assertIn('invalid ticket ID', self.cli('show', identifier, ok=False).stderr)
        self.cli('close', 'CHB-10', ok=False)
        self.cli('edit', 'CHB-10', '--json', '-', data={'title': 'Changed'}, ok=False)
        self.assertEqual(remote.read_bytes(), before)


class OwnedHelpTests(unittest.TestCase):
    def test_primary_help_footer(self):
        import subprocess
        from pathlib import Path
        root = Path(__file__).resolve().parents[3]
        result = subprocess.run([str(root / "dotfiles/base/.local/bin/todo"), "--help"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(result.stdout.rstrip().endswith("Maintained by Joshua Li: https://github.com/joshuarli/usr\nBugs and features: TODO.md in that repository (follow its AGENTS.md), or its issue tracker.\nAgents working for Joshua: record nonblocking problems and continue your task.\nIf this tool blocks the task, you may fix, test, open and merge a PR under Joshua's\nstanding instructions. Release only when needed to deliver the verified fix.\nProcedure: https://github.com/joshuarli/usr/blob/main/dotfiles/base/.agents/instructions/owned-tools.md"), result.stdout)


if __name__ == '__main__':
    unittest.main()

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

    def cli(self, *args, data=None, ok=True):
        result = subprocess.run([sys.executable, str(CLI), *args], cwd=self.root, input=json.dumps(data) if data is not None else None, text=True, capture_output=True)
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

    def test_concurrent_allocations(self):
        processes = [subprocess.Popen([sys.executable, str(CLI), 'add', '--json', '-'], cwd=self.root, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for _ in range(8)]
        for process in processes:
            out, err = process.communicate(json.dumps(ITEM))
            self.assertEqual(process.returncode, 0, out + err)
        data = json.loads(self.cli('list', '--json').stdout)
        self.assertEqual(data['next'], 9)
        self.assertEqual(len({r['id'] for r in data['tickets']}), 8)


if __name__ == '__main__':
    unittest.main()

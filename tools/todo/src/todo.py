#!/usr/bin/env python3
import argparse
import fcntl
import json
import os
import re
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path

HEADER = re.compile(r'\APrefix: ([A-Z]{3,4})\nNext: ([1-9][0-9]*)\n')
TICKET = re.compile(r'^### ([A-Z]{3,4}-[1-9][0-9]*) · (P[1-4]) · (.+)\n', re.M)
FIELD = re.compile(r'^- \*\*(Area|Where|Problem|Recommendation|Fix with|Effort|Design):\*\* (.+)\n', re.M)
NAMES = {'Area': 'area', 'Where': 'where', 'Problem': 'problem', 'Recommendation': 'recommendation', 'Fix with': 'fix_with', 'Effort': 'effort', 'Design': 'design'}
REQUIRED = set(NAMES.values()) - {'design'}


def locate(name):
    if not name or Path(name).name != name or name in ('.', '..'):
        raise ValueError(f'{name}: --file takes a file name, not a path')
    for directory in (Path.cwd(), *Path.cwd().parents):
        path = directory / name
        if path.is_file():
            return path
    raise ValueError(f'{name} not found in this directory or its parents')


def show_record(path, identifier):
    text = path.read_text(encoding='utf-8')
    matches = [match for match in TICKET.finditer(text) if match.group(1) == identifier]
    if not matches:
        return None
    if len(matches) > 1:
        raise ValueError(f'{path}: {identifier}: duplicate ID')
    header = HEADER.match(text)
    if header is None:
        raise ValueError(f'{path}: expected Prefix and Next header')
    start = matches[0].start()
    following = re.search(r'^### ', text[matches[0].end():], re.M)
    end = matches[0].end() + following.start() if following else len(text)
    try:
        _, _, _, records = parse(header.group() + '\n' + text[start:end])
    except ValueError as error:
        raise ValueError(f'{path}: {error}') from error
    return {key: value for key, value in records[0].items() if not key.startswith('_')}


def workspace_backlogs():
    root = Path(os.environ.get('REPOMOD_ROOT', str(Path.home() / 'repos'))).expanduser()
    if not root.is_absolute():
        raise ValueError('REPOMOD_ROOT must be an absolute directory')
    repositories = {Path(__file__).resolve().parents[3]}
    pending = [root] if root.exists() else []
    visited = set()
    while pending:
        directory = pending.pop().resolve()
        if directory in visited:
            continue
        visited.add(directory)
        if (directory / '.git').exists():
            repositories.add(directory)
            continue
        for child in sorted(directory.iterdir()):
            if child.name.startswith('.') or not child.is_dir():
                continue
            if not child.is_symlink() or (child / '.git').exists():
                pending.append(child)
    return sorted({path.resolve() for repo in repositories for path in repo.glob('TODO*.md') if path.is_file()})


def show_ticket(identifier, filename):
    if re.fullmatch(r'[A-Z]{3,4}-[1-9][0-9]*', identifier) is None:
        raise ValueError(f'{identifier}: invalid ticket ID')
    if filename is not None:
        path = locate(filename)
        record = show_record(path, identifier)
    else:
        path = next((directory / 'TODO.md' for directory in (Path.cwd(), *Path.cwd().parents)
                     if (directory / 'TODO.md').is_file()), None)
        record = show_record(path, identifier) if path is not None else None
        if record is None:
            matches = [(path, found) for path in workspace_backlogs()
                       if (found := show_record(path, identifier)) is not None]
            if len(matches) > 1:
                raise ValueError(f'{identifier}: ambiguous ticket ID: ' + ', '.join(str(path) for path, _ in matches))
            path, record = matches[0] if matches else (None, None)
    if record is None or path is None:
        raise ValueError(f'{identifier}: ticket not found')
    result = subprocess.run(['git', '-C', str(path.parent), 'rev-parse', '--show-toplevel'],
                            capture_output=True, text=True)
    root = Path(result.stdout.strip()).resolve() if result.returncode == 0 else path.parent.resolve()
    print(json.dumps({'repository_root': str(root), **record}, indent=2))


def parse(text):
    header = HEADER.match(text)
    if not header:
        raise ValueError('expected Prefix and Next header')
    prefix, next_number = header.group(1), int(header.group(2))
    matches = list(TICKET.finditer(text))
    records = []
    seen = set()
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        body = text[match.end():end]
        fields = list(FIELD.finditer(body))
        values = {}
        for field in fields:
            key = NAMES[field.group(1)]
            if key in values:
                raise ValueError(f'{match.group(1)}: duplicate {key}')
            values[key] = field.group(2)
        identifier, priority, title = match.groups()
        if identifier in seen or not identifier.startswith(prefix + '-'):
            raise ValueError(f'{identifier}: duplicate ID or wrong prefix')
        seen.add(identifier)
        if int(identifier.split('-')[1]) >= next_number:
            raise ValueError(f'{identifier}: Next must exceed all ticket IDs')
        if not REQUIRED <= values.keys() or values.get('effort') not in ('S', 'M', 'L'):
            raise ValueError(f'{identifier}: missing fields or invalid effort')
        field_end = match.end() + fields[-1].end()
        raw = text[match.start():field_end]
        gaps = text[field_end:end]
        expected = '\n' + ''.join(f'- **{field.group(1)}:** {field.group(2)}\n' for field in fields)
        if text[match.end():field_end] != expected:
            raise ValueError(f'{identifier}: malformed ticket fields')
        records.append({'id': identifier, 'priority': priority, 'title': title, **values, '_raw': raw, '_gap': gaps})
    if re.search(r'^### ', text[header.end():matches[0].start() if matches else len(text)], re.M):
        raise ValueError('malformed ticket heading')
    for record in records:
        if re.search(r'^### ', record['_gap'], re.M):
            raise ValueError('malformed ticket heading')
    return prefix, next_number, text[:matches[0].start()] if matches else text, records


def key(record):
    return record['priority'], int(record['id'].split('-')[1])


def render(record):
    return (f"### {record['id']} · {record['priority']} · {record['title']}\n\n" +
            ''.join(f'- **{label}:** {record[name]}\n' for label, name in NAMES.items() if name in record))


def validate_input(data, partial=False):
    if not isinstance(data, dict):
        raise ValueError('input must be a JSON object')
    allowed = REQUIRED | {'design', 'title', 'priority'}
    if set(data) - allowed or (not partial and not (REQUIRED | {'title', 'priority'}) <= data.keys()):
        raise ValueError('unknown or missing fields')
    for name, value in data.items():
        if name == 'design' and value is None and partial:
            continue
        if not isinstance(value, str) or not value.strip() or '\n' in value or '\r' in value:
            raise ValueError(f'{name}: expected a nonempty single-line string')
    if 'priority' in data and data['priority'] not in ('P1', 'P2', 'P3', 'P4'):
        raise ValueError('invalid priority')
    if 'effort' in data and data['effort'] not in ('S', 'M', 'L'):
        raise ValueError('invalid effort')


def ordered(records):
    return records == sorted(records, key=key)


def assemble(head, records):
    return head + ''.join(r['_raw'] + r['_gap'] for r in records)


def sort_records(records):
    gaps = [r['_gap'] for r in records]
    result = sorted(records, key=key)
    for record, gap in zip(result, gaps):
        record['_gap'] = gap
    return result


@contextmanager
def lock(path):
    result = subprocess.run(['git', '-C', str(path.parent), 'rev-parse', '--git-path', 'todo.lock'], capture_output=True, text=True)
    lock_path = Path(result.stdout.strip()) if result.returncode == 0 else path.parent / '.todo.lock'
    if not lock_path.is_absolute():
        lock_path = path.parent / lock_path
    with lock_path.open('a') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        yield


def write(path, text):
    mode = path.stat().st_mode
    name = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, delete=False) as handle:
            name = handle.name
            os.fchmod(handle.fileno(), mode & 0o7777)
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
    finally:
        if name and os.path.exists(name):
            os.unlink(name)


def run(args, path):
    text = path.read_text(encoding='utf-8')
    prefix, next_number, head, records = parse(text)
    if args.command in ('check', 'fmt'):
        good = ordered(records)
        if args.command == 'fmt' and not args.check and not good:
            write(path, assemble(head, sort_records(records)))
            return
        if args.command == 'check' and args.json:
            print(json.dumps({'ok': good, 'errors': [] if good else ['tickets are not ordered by priority and ID']}))
        elif not good:
            raise ValueError('tickets are not ordered by priority and ID')
        if not good:
            raise SystemExit(1)
        return
    if args.command == 'list':
        priorities = args.priority.split(',') if args.priority else ['P1', 'P2', 'P3', 'P4']
        if any(p not in ('P1', 'P2', 'P3', 'P4') for p in priorities):
            raise ValueError('invalid priority filter')
        print(json.dumps({'prefix': prefix, 'next': next_number, 'tickets': [{k: r[k] for k in ('id', 'priority', 'title', 'area', 'effort')} for r in records if r['priority'] in priorities]}, indent=2))
        return
    if args.command == 'add':
        data = args.data
        validate_input(data)
        record = {'id': f'{prefix}-{next_number}', **data}
        record['_raw'] = render(record)
        record['_gap'] = '\n'
        head = HEADER.sub(f'Prefix: {prefix}\nNext: {next_number + 1}\n', head, count=1)
        if records and not records[-1]['_gap'].endswith('\n\n'):
            records[-1]['_gap'] += '\n'
        records.append(record)
    else:
        record = next ( (r for r in records if r['id'] == args.id), None)
        if record is None:
            raise ValueError(f'{args.id}: ticket not found')
        if args.command == 'close':
            index = records.index(record)
            if index:
                records[index - 1]['_gap'] += record['_gap']
            else:
                head += record['_gap']
            records.remove(record)
        else:
            data = args.data
            validate_input(data, partial=True)
            for k, value in data.items():
                if value is None:
                    record.pop(k, None)
                else:
                    record[k] = value
            record['_raw'] = render(record)
    write(path, assemble(head, sort_records(records)))
    if args.command in ('add', 'edit'):
        print(json.dumps({k: v for k, v in record.items() if not k.startswith('_')}, indent=2))


FOOTER = """Maintained by Joshua Li: https://github.com/joshuarli/usr
Bugs and features: TODO.md in that repository (follow its AGENTS.md), or its issue tracker.
Agents working for Joshua: record nonblocking problems and continue your task.
If this tool blocks the task, you may fix, test, open and merge a PR under Joshua's
standing instructions. Release only when needed to deliver the verified fix.
Procedure: https://github.com/joshuarli/usr/blob/main/dotfiles/base/.agents/instructions/owned-tools.md"""
FILE_OPTION = ('--file', {'metavar': 'NAME', 'help': 'backlog file name in this directory or its parents (default: TODO.md; show also searches workspace backlogs)'})
ID = ('id', {'metavar': 'ID', 'help': 'ticket ID, such as ABC-1'})
JSON_ALWAYS = ('--json', {'action': 'store_true', 'help': 'accepted for scripts; output is always JSON'})
JSON_INPUT = ('--json', {'required': True, 'choices': ['-'], 'metavar': '-', 'help': 'read a JSON object from stdin (required)'})
COMMANDS = (
    ('list', 'Print compact records in priority and ID order.', (('--priority', {'metavar': 'P1,P2', 'help': 'only these comma-separated priorities'}), JSON_ALWAYS), ('todo list --priority P1,P2 --json',)),
    ('show', 'Print one ticket with all fields and its repository_root as JSON.', (ID, JSON_ALWAYS), ('todo show ABC-1 --json',)),
    ('add', 'File a ticket from JSON and print the record.', (JSON_INPUT,), ('todo add --json - < ticket.json',)),
    ('edit', 'Change ticket fields from JSON and print the record.', (ID, JSON_INPUT), ('todo edit ABC-1 --json - < changes.json',)),
    ('close', 'Remove a ticket.', (ID,), ('todo close ABC-1',)),
    ('check', 'Validate records, IDs, Next, and ordering.', (('--json', {'action': 'store_true', 'help': 'print {"ok", "errors"} JSON instead of failing with a message'}),), ('todo check --json',)),
    ('fmt', 'Order tickets by priority and ID.', (('--check', {'action': 'store_true', 'help': 'exit 1 instead of writing when tickets are out of order'}),), ('todo fmt --check',)),
)


class Parser(argparse.ArgumentParser):
    def error(self, message):
        self.exit(2, f'{self.format_usage()}{self.prog}: error: {message}\nRun `todo -h` for the full reference.\n')


def _arguments(arguments):
    rows = []
    for name, options in arguments:
        label = name if name.startswith('-') else options['metavar']
        if name.startswith('-') and options.get('action') != 'store_true':
            label = f"{name} {options['metavar']}"
        rows.append(f'    {label:<18} {options["help"]}')
    return rows


def _usage(parser):
    return parser.format_usage().removeprefix('usage: ').replace(' [-h]', '').strip()


def build_parser():
    commands = {}

    class Root(Parser):
        def format_help(self):
            lines = [f'usage: {_usage(self)}', '', 'Manage a Markdown TODO backlog.', '', 'Common options, given before COMMAND:', *_arguments([FILE_OPTION]), f"    {'-h, --help':<18} print this reference", '', 'Commands:']
            for name, description, arguments, examples in COMMANDS:
                lines += ['', f'  {_usage(commands[name])}', f'    {description}', *_arguments(arguments), *(f'    Example: {example}' for example in examples)]
            return '\n'.join([*lines, '', FOOTER, ''])

    parser = Root(prog='todo', description='Manage a Markdown TODO backlog.')
    parser.add_argument(FILE_OPTION[0], **FILE_OPTION[1])
    sub = parser.add_subparsers(dest='command', required=True, metavar='COMMAND', parser_class=Parser)
    for name, description, arguments, examples in COMMANDS:
        command = sub.add_parser(name, description=description, epilog='\n'.join([*(f'example: {example}' for example in examples), 'Common option --file NAME goes before the command. Full reference and maintainer: todo -h']), formatter_class=argparse.RawDescriptionHelpFormatter)
        for argument, options in arguments:
            command.add_argument(argument, **options)
        commands[name] = command
    return parser


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    parser = build_parser()
    if not argv:
        parser.print_help()
        return 0
    args = parser.parse_args(argv)
    try:
        if args.command == 'show':
            show_ticket(args.id, args.file)
            return 0
        if args.command in ('add', 'edit'):
            args.data = json.load(sys.stdin)
        path = locate(args.file or 'TODO.md')
        if args.command in ('add', 'edit', 'close') or (args.command == 'fmt' and not args.check):
            with lock(path):
                run(args, path)
        else:
            run(args, path)
    except (ValueError, OSError, json.JSONDecodeError) as error:
        if args.command == 'check' and args.json:
            print(json.dumps({'ok': False, 'errors': [str(error)]}))
        else:
            print(f'todo: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())

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


def locate():
    for directory in (Path.cwd(), *Path.cwd().parents):
        path = directory / 'TODO.md'
        if path.is_file():
            return path
    raise ValueError('TODO.md not found in this directory or its parents')


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
        if args.command == 'show':
            print(json.dumps({k: v for k, v in record.items() if not k.startswith('_')}, indent=2))
            return
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


def main():
    parser = argparse.ArgumentParser(description='Manage a Markdown TODO backlog')
    sub = parser.add_subparsers(dest='command', required=True)
    listing = sub.add_parser('list')
    listing.add_argument('--priority')
    listing.add_argument('--json', action='store_true')
    show = sub.add_parser('show')
    show.add_argument('id')
    show.add_argument('--json', action='store_true')
    for name in ('add', 'edit'):
        command = sub.add_parser(name)
        if name == 'edit':
            command.add_argument('id')
        command.add_argument('--json', required=True, choices=['-'])
    close = sub.add_parser('close')
    close.add_argument('id')
    check = sub.add_parser('check')
    check.add_argument('--json', action='store_true')
    fmt = sub.add_parser('fmt')
    fmt.add_argument('--check', action='store_true')
    args = parser.parse_args()
    try:
        if args.command in ('add', 'edit'):
            args.data = json.load(sys.stdin)
        path = locate()
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

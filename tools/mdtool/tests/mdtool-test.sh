#!/bin/sh

set -u
repo=$(CDPATH='' cd -- "$(dirname -- "$0")/../../.." && pwd) || exit 1
tool="$repo/dotfiles/base/.local/bin/mdtool"
nfailed=0
mkdir -p "$repo/.work/tmp" || exit 1
TMPDIR="$repo/.work/tmp"
export TMPDIR

expect_status() {
	name=$1 wanted=$2
	shift 2
	"$@" >/dev/null 2>&1
	got=$?
	if [ "$got" -eq "$wanted" ]; then
		printf 'ok: %s\n' "$name"
	else
		printf 'FAIL: %s (wanted %s, got %s)\n' "$name" "$wanted" "$got"
		nfailed=$((nfailed + 1))
	fi
}

help_output=$(python3 -I "$tool" --help)
case "$help_output" in
  *"Examples:"*"  mdtool "*) ;;
  *) printf 'FAIL: examples in help\n'; nfailed=$((nfailed + 1)) ;;
esac
expected_footer="Maintained by Joshua Li: https://github.com/joshuarli/usr
Bugs and features: TODO.md in that repository (follow its AGENTS.md), or its issue tracker.
Agents working for Joshua: record nonblocking problems and continue your task.
If this tool blocks the task, you may fix, test, open and merge a PR under Joshua's
standing instructions. Release only when needed to deliver the verified fix.
Procedure: https://github.com/joshuarli/usr/blob/main/dotfiles/base/.agents/instructions/owned-tools.md"
case "$help_output" in
  *"$expected_footer") ;;
  *) printf 'FAIL: primary help footer\n'; nfailed=$((nfailed + 1)) ;;
esac

python3 -I - "$repo/tools/mdtool/src/mdtool.py" <<'PYTEST' || nfailed=$((nfailed + 1))
import importlib.util
import shlex
import sys
spec = importlib.util.spec_from_file_location("mdtool", sys.argv[1])
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
help_text = module.build_parser().format_help()
reference, examples = help_text.split("\nExamples:\n", 1)
for line in examples.splitlines():
    if line == "  mdtool" or line.startswith("  mdtool "):
        words = shlex.split(line)
        module.build_parser().parse_intermixed_args(words[1:])
        for word in words:
            if word.startswith("--"):
                assert word.split("=", 1)[0] in reference, word
PYTEST

for command in links anchors refs consumers pointers dups router check commands selftest; do
    command_help=$(python3 -I "$tool" "$command" -h) || nfailed=$((nfailed + 1))
    case "$command_help" in
      *"Full reference: mdtool -h"*) ;;
      *) printf 'FAIL: %s help reference\n' "$command"; nfailed=$((nfailed + 1)) ;;
    esac
done

printf '\n1: embedded behavior tests\n'
python3 -I "$tool" selftest || nfailed=$((nfailed + 1))

printf '\n2: command inventory\n'
expected='links
anchors
refs
consumers
pointers
dups
router
check'
got=$(python3 -I "$tool" commands)
case "$got" in *"Maintained by Joshua Li:"*) nfailed=$((nfailed + 1));; esac
if [ "$got" = "$expected" ]; then printf 'ok: exact command set\n'; else printf 'FAIL: command set differs\n'; nfailed=$((nfailed + 1)); fi

printf '\n3: invalid invocations\n'
expect_status 'anchors requires a path' 2 python3 -I "$tool" anchors
expect_status 'unknown ignore code is rejected' 2 python3 -I "$tool" links --ignore ZZZ
expect_status 'unsupported command is rejected' 2 python3 -I "$tool" not-a-command

printf '\ntesting finished.\n'
[ "$nfailed" -eq 0 ]

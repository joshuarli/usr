#!/bin/sh

set -u
repo=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd) || exit 1
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
if [ "$got" = "$expected" ]; then printf 'ok: exact command set\n'; else printf 'FAIL: command set differs\n'; nfailed=$((nfailed + 1)); fi

printf '\n3: invalid invocations\n'
expect_status 'anchors requires a path' 2 python3 -I "$tool" anchors
expect_status 'unknown ignore code is rejected' 2 python3 -I "$tool" links --ignore ZZZ
expect_status 'unsupported command is rejected' 2 python3 -I "$tool" not-a-command

printf '\ntesting finished.\n'
[ "$nfailed" -eq 0 ]

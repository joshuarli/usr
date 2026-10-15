#!/bin/sh

set -u
script_dir=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd) || exit 1
repo=$(CDPATH='' cd -- "$script_dir/../../../.." && pwd) || exit 1
scratch_root="$repo/.work"
scratch_tmp="$scratch_root/tmp"
if [ -L "$scratch_root" ] || [ -L "$scratch_tmp" ]; then
	printf '%s\n' '.work and .work/tmp must not be symlinks' >&2
	exit 1
fi
git -C "$repo" check-ignore -q .work || { printf '%s\n' '.work must be ignored by .git/info/exclude' >&2; exit 1; }
mkdir -p "$scratch_tmp" || exit 1
if [ ! -d "$scratch_root" ] || [ -L "$scratch_root" ] || [ ! -d "$scratch_tmp" ] || [ -L "$scratch_tmp" ]; then
	printf '%s\n' '.work and .work/tmp must be real directories' >&2
	exit 1
fi
run_dir=$(mktemp -d "$scratch_tmp/verify-usr.XXXXXX") || exit 1
run_name=${run_dir##*/}
evidence="$scratch_tmp/$run_name.log"
fixture="$run_dir/repo"
cleanup() {
	status=$?
	trap - 0
	if ! rm -rf "$run_dir"; then
		printf 'failed to clean fixture: %s\n' "$run_dir" >&2
		status=1
	fi
	printf 'evidence: %s\n' "$evidence"
	exit "$status"
}
trap cleanup 0
trap 'exit 130' 1 2 3 15

record() {
	printf '%s\n' "$*" | tee -a "$evidence"
}

fail() {
	record "FAIL: $*"
	exit 1
}

mkdir -p "$fixture/dotfiles/tool/.config" "$fixture/home" || fail 'cannot prepare scratch fixture'
printf 'fixture setting\n' > "$fixture/dotfiles/tool/.config/app.conf" || fail 'cannot write source fixture'
git init -q "$fixture" || fail 'cannot initialize isolated fixture repository'
git -C "$fixture" add dotfiles/tool/.config/app.conf || fail 'cannot register source fixture'
record 'success journey: create link'
	if (cd "$fixture" && TMPDIR="$scratch_tmp" sh "$repo/dotfiles/sym" -t home dotfiles/tool) > "$run_dir/link.out" 2>&1; then
	cat "$run_dir/link.out" | tee -a "$evidence"
else
	cat "$run_dir/link.out" | tee -a "$evidence"
	fail 'sym rejected a clean scratch target'
fi
link="$fixture/home/.config/app.conf"
[ -L "$link" ] || fail 'sym did not create the expected link'
[ "$(readlink "$link")" = '../../dotfiles/tool/.config/app.conf' ] || fail 'sym created an unexpected link target'
[ "$(cat "$link")" = 'fixture setting' ] || fail 'the link does not expose the source contents'
record 'observed: link target and contents match the fixture'

record 'success journey: repeat the same operation'
if (cd "$fixture" && TMPDIR="$scratch_tmp" sh "$repo/dotfiles/sym" -t home dotfiles/tool) > "$run_dir/repeat.out" 2>&1; then
	[ ! -s "$run_dir/repeat.out" ] || fail 'the repeat run was not a no-op'
else
	fail 'sym rejected an idempotent repeat'
fi
record 'observed: repeat run produced no changes or output'

record 'negative journey: preserve a conflicting destination'
printf 'new fixture setting\n' > "$fixture/dotfiles/tool/.config/blocked.conf" || fail 'cannot add conflict source'
git -C "$fixture" add dotfiles/tool/.config/blocked.conf || fail 'cannot register conflict source'
printf 'owner data\n' > "$fixture/home/.config/blocked.conf" || fail 'cannot create conflict destination'
status=0
(cd "$fixture" && TMPDIR="$scratch_tmp" sh "$repo/dotfiles/sym" -t home dotfiles/tool) > "$run_dir/conflict.out" 2>&1 || status=$?
cat "$run_dir/conflict.out" | tee -a "$evidence"
[ "$status" -ne 0 ] || fail 'sym accepted a conflicting destination'
if grep -q 'CONFLICT: home/.config/blocked.conf already exists' "$run_dir/conflict.out"; then
	:
else
	fail 'sym did not report the destination conflict'
fi
[ -f "$fixture/home/.config/blocked.conf" ] || fail 'the conflicting destination was replaced'
[ "$(cat "$fixture/home/.config/blocked.conf")" = 'owner data' ] || fail 'the conflicting destination contents changed'
[ -L "$link" ] && [ "$(cat "$link")" = 'fixture setting' ] || fail 'the existing valid link changed'
[ -f "$fixture/dotfiles/tool/.config/blocked.conf" ] || fail 'the source fixture was removed'
record 'observed: sym reported the conflict and preserved both destination and source'

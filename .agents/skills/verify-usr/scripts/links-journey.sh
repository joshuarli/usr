#!/bin/sh
# Scratch-only journey for the Python sync link reconciler.
set -u
script_dir=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd) || exit 1
repo=$(cd "$script_dir/../../../.." && pwd) || exit 1
scratch_tmp="$repo/.work/tmp"
"$repo/dotfiles/scratch-check.sh" "$repo" || exit $?
run_dir=$(mktemp -d "$scratch_tmp/verify-usr.XXXXXX") || exit 1
run_name=${run_dir##*/}
evidence="$scratch_tmp/$run_name.log"
fixture="$run_dir/repo"
cleanup() {
    status=$?
    trap '' 1 2 3 15
    trap - 0
    if [ -L "$evidence" ]; then
        printf 'evidence path is a symlink: %s\n' "$evidence" >&2
        status=1
    elif [ ! -f "$evidence" ]; then
        if ! printf '%s\n' 'journey exited before its first observation' > "$evidence"; then
            printf 'failed to retain evidence: %s\n' "$evidence" >&2
            status=1
        fi
    fi
    if ! rm -rf "$run_dir"; then
        printf 'failed to clean fixture: %s\n' "$run_dir" >&2
        status=1
    fi
    if [ -f "$evidence" ] && [ ! -L "$evidence" ]; then
        printf 'evidence: %s\n' "$evidence"
    else
        printf 'evidence was not retained: %s\n' "$evidence" >&2
        status=1
    fi
    exit "$status"
}
trap cleanup 0
trap 'exit 130' 1 2 3 15

record() { printf '%s\n' "$*" | tee -a "$evidence"; }
fail() { record "FAIL: $*"; exit 1; }

# The fixture is independent of the usr checkout; only the Python linker
# modules are imported from usr. No writes reach HOME.
python_links() {
    action=$1
    python3 -I - "$repo/tools/sync" "$fixture" "$action" <<'PY'
from pathlib import Path
import sys
sys.path.insert(0, sys.argv[1])
from links import discover
from link_plan import plan_links
from link_apply import apply
root = Path(sys.argv[2])
mode = sys.argv[3]
plan = plan_links(discover(root, root / "home", "linux"), root / "owned")
for line in plan.lines():
    print(line)
if plan.conflicts:
    sys.exit(1)
if mode == "apply":
    apply(plan, root / "owned")
PY
}

mkdir -p "$fixture/dotfiles/base/.config" "$fixture/home" || fail 'cannot prepare scratch fixture'
printf 'fixture setting\n' > "$fixture/dotfiles/base/.config/app.conf" || fail 'cannot write source fixture'
git init -q "$fixture" || fail 'cannot initialize isolated fixture'
git -C "$fixture" add dotfiles/base/.config/app.conf || fail 'cannot register source fixture'
record 'success journey: create link'
if python_links apply > "$run_dir/link.out" 2>&1; then
    cat "$run_dir/link.out" | tee -a "$evidence"
else
    cat "$run_dir/link.out" | tee -a "$evidence"
    fail 'Python link planner rejected a clean scratch target'
fi
link="$fixture/home/.config/app.conf"
[ -L "$link" ] || fail 'planner did not create the expected link'
[ "$(readlink "$link")" = '../../dotfiles/base/.config/app.conf' ] || fail 'planner created an unexpected target'
[ "$(cat "$link")" = 'fixture setting' ] || fail 'the link does not expose the source contents'
record 'observed: link target and contents match the fixture'

record 'success journey: repeat the same operation'
if python_links apply > "$run_dir/repeat.out" 2>&1; then
    [ ! -s "$run_dir/repeat.out" ] || fail 'the repeat run was not a no-op'
else
    fail 'Python linker rejected an idempotent repeat'
fi
record 'observed: repeat run produced no changes or output'

record 'negative journey: preserve a conflicting destination'
printf 'new fixture setting\n' > "$fixture/dotfiles/base/.config/blocked.conf" || fail 'cannot add conflict source'
git -C "$fixture" add dotfiles/base/.config/blocked.conf || fail 'cannot register conflict source'
printf 'owner data\n' > "$fixture/home/.config/blocked.conf" || fail 'cannot create conflict destination'
status=0
python_links apply > "$run_dir/conflict.out" 2>&1 || status=$?
cat "$run_dir/conflict.out" | tee -a "$evidence"
[ "$status" -ne 0 ] || fail 'Python linker accepted a conflicting destination'
grep -q 'CONFLICT: .*home/.config/blocked.conf already exists' "$run_dir/conflict.out" || fail 'linker did not report the destination conflict'
[ "$(cat "$fixture/home/.config/blocked.conf")" = 'owner data' ] || fail 'the conflicting destination changed'
[ -L "$link" ] && [ "$(cat "$link")" = 'fixture setting' ] || fail 'the existing valid link changed'
[ -f "$fixture/dotfiles/base/.config/blocked.conf" ] || fail 'the source fixture was removed'
record 'observed: Python linker reported the conflict and preserved both destination and source'

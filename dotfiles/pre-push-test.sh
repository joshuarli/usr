#!/bin/sh
# Tests for the global pre-push hook: it refuses without a terminal and otherwise defers to the repository's own hook.

hook="${PWD}/base/.config/git/hooks/pre-push"
nfailed=0

# expect <wanted exit> <description> <run with a terminal: yes|no> <repository hook exit code, or none>
expect () {
    repo=$(mktemp -d "${PWD}/../.work/tmp/pre-push.XXXXXX") || exit 1
    git -C "$repo" init -q
    if [ "$4" != none ]; then
        printf '#!/bin/sh\nexit %s\n' "$4" > "$repo/.git/hooks/pre-push"
        chmod +x "$repo/.git/hooks/pre-push"
    fi
    if [ "$3" = yes ]; then
        got=$(cd "$repo" && python3 -I -c 'import os, pty, sys; sys.exit(os.waitstatus_to_exitcode(pty.spawn(sys.argv[1:])))' sh "$hook" origin url </dev/null >/dev/null 2>&1; echo $?)
    else
        got=$(cd "$repo" && sh "$hook" origin url </dev/null >/dev/null 2>&1; echo $?)
    fi
    rm -rf "$repo"
    if [ "$got" = "$1" ]; then
        printf 'ok: %s\n' "$2"
    else
        printf 'FAIL: %s (wanted %s, got %s)\n' "$2" "$1" "$got"
        nfailed=$((nfailed + 1))
    fi
}

mkdir -p "${PWD}/../.work/tmp"
expect 1 'a push without a terminal is refused' no none
expect 1 'the repository hook cannot override the refusal' no 0
expect 0 'a terminal push with no repository hook is allowed' yes none
expect 0 'a terminal push defers to a passing repository hook' yes 0
expect 3 'a terminal push defers to a failing repository hook' yes 3

echo "testing finished."
[ "$nfailed" -eq 0 ]

#!/bin/sh
# Tests for worktree-remove: a clean worktree is removed, and one holding uncommitted work is refused and kept.

hook="${PWD}/base/.local/bin/worktree-remove"
nfailed=0

mkdir -p "${PWD}/../.work/tmp"
scratch=$(mktemp -d "${PWD}/../.work/tmp/worktree-remove.XXXXXX") || exit 1
trap 'rm -rf "$scratch"' 0
repo="$scratch/repo"
git init -q "$repo"
git -C "$repo" -c user.name=t -c user.email=t@t commit -q --allow-empty -m init
printf 'tracked\n' > "$repo/tracked"
git -C "$repo" add tracked
git -C "$repo" -c user.name=t -c user.email=t@t commit -q -m tracked

# expect <wanted exit> <description> <name> <command run inside the worktree before removal>
expect () {
    path="$repo/.work/wt/$3"
    git -C "$repo" worktree add -q -b "worktree-$3" "$path"
    (cd "$path" && eval "$4")
    got=$(printf '{"worktree_path":"%s"}' "$path" | sh "$hook" >/dev/null 2>&1; echo $?)
    if [ "$1" = 0 ] && [ -e "$path" ]; then got="$got-but-left-in-place"; fi
    if [ "$1" != 0 ] && [ ! -e "$path" ]; then got="$got-but-deleted"; fi
    if [ "$got" = "$1" ]; then
        printf 'ok: %s\n' "$2"
    else
        printf 'FAIL: %s (wanted %s, got %s)\n' "$2" "$1" "$got"
        nfailed=$((nfailed + 1))
    fi
}

expect 0 'a clean worktree is removed' clean ':'
expect 1 'an untracked file keeps the worktree' untracked 'printf x > scratch.txt'
expect 1 'a modified tracked file keeps the worktree' modified 'printf y >> tracked'
expect 1 'a staged new file keeps the worktree' staged 'printf z > new.txt && git add new.txt'

echo "testing finished."
[ "$nfailed" -eq 0 ]

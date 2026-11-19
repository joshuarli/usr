#!/bin/sh
# Exercise the Claude hook against disposable linked worktrees.

repo_root=$(CDPATH='' cd "$(dirname "$0")/.." && pwd -P)
hook="$repo_root/dotfiles/base/.local/bin/worktree-remove"
nfailed=0

mkdir -p "$repo_root/.work/tmp"
scratch=$(mktemp -d "$repo_root/.work/tmp/worktree-remove.XXXXXX") || exit 1
trap 'rm -rf "$scratch"' 0
export HOME="$scratch" XDG_CONFIG_HOME="$scratch" TMPDIR="$scratch"
help=$(sh "$hook" -h) || exit 1
printf '%s\n' "$help" | grep -qx 'Examples:' || exit 1
printf '%s\n' "$help" | grep -q '^  worktree-remove ' || exit 1
printf '%s\n' "$help" | grep -q -- '--help' || exit 1
repo="$scratch/repo"
git init -q "$repo"
git -C "$repo" -c user.name=t -c user.email=t@t commit -q --allow-empty -m init
printf 'tracked\n' > "$repo/tracked"
git -C "$repo" add tracked
git -C "$repo" -c user.name=t -c user.email=t@t commit -q -m tracked
printf '%s\n' 'valuable-*' >> "$repo/.git/info/exclude"

# expect <wanted exit> <description> <name> <command run inside the worktree before removal>
expect () {
    path="$repo/.work/wt/$3"
    git -C "$repo" worktree add -q -b "worktree-$3" "$path" || exit 1
    (cd "$path" && eval "$4") || exit 1
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
if git -C "$repo" show-ref --verify --quiet refs/heads/worktree-clean; then
    printf '%s\n' 'FAIL: the merged hook branch was kept'
    nfailed=$((nfailed + 1))
fi
expect 0 'a clean unmerged checkout is removed' attached 'git -c user.name=t -c user.email=t@t commit -q --allow-empty -m unique'
if ! git -C "$repo" show-ref --verify --quiet refs/heads/worktree-attached; then
    printf '%s\n' 'FAIL: the unmerged hook branch was deleted'
    nfailed=$((nfailed + 1))
fi
expect 0 'a clean checkout merged into its upstream is removed' upstream '
    git -c user.name=t -c user.email=t@t commit -q --allow-empty -m upstream-only &&
    git branch upstream-target && git branch -q --set-upstream-to=upstream-target'
if git -C "$repo" show-ref --verify --quiet refs/heads/worktree-upstream; then
    printf '%s\n' 'FAIL: the hook branch merged into its upstream was kept'
    nfailed=$((nfailed + 1))
fi
expect 1 'a unique detached HEAD keeps the worktree' detached 'git checkout -q --detach && git -c user.name=t -c user.email=t@t commit -q --allow-empty -m detached-only'
expect 0 'a retained detached HEAD can be removed' detached-retained 'git checkout -q --detach'
expect 1 'an untracked file keeps the worktree' untracked 'printf x > scratch.txt'
expect 1 'a modified tracked file keeps the worktree' modified 'printf y >> tracked'
expect 1 'a staged new file keeps the worktree' staged 'printf z > new.txt && git add new.txt'
expect 1 'a locked checkout is kept' locked 'git worktree lock "$path"'
expect 1 'an unknown bridge lease keeps the worktree' leased '
    digest=$(python3 -I -c "import hashlib, os, sys; print(hashlib.sha256(os.fsencode(sys.argv[1])).hexdigest())" "$path") &&
    mkdir -p "$repo/.work/worker-bridge/.active-worktree-$digest"'

ignored="$repo/.work/wt/ignored"
git -C "$repo" worktree add -q -b worktree-ignored "$ignored"
printf valuable > "$ignored/valuable-state"
got=$(printf '{"worktree_path":"%s"}' "$ignored" | sh "$hook" 2>"$scratch/ignored.err" >/dev/null; echo $?)
if [ "$got" = 1 ] && [ -f "$ignored/valuable-state" ] && case "$(cat "$scratch/ignored.err")" in *"ignored files"*) true;; *) false;; esac; then
    printf '%s\n' 'ok: ignored files are kept with a diagnostic'
else
    printf '%s\n' "FAIL: ignored file preservation (exit $got)"
    nfailed=$((nfailed + 1))
fi

echo "testing finished."
[ "$nfailed" -eq 0 ]

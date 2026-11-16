#!/bin/sh
set -eu

root=$(CDPATH='' cd "$(dirname "$0")/.." && pwd -P)
mkdir -p "$root/.work/tmp"
scratch=$(mktemp -d "$root/.work/tmp/owned-help.XXXXXX")
trap 'rm -rf "$scratch"' 0
mkdir "$scratch/bin" "$scratch/home" "$scratch/tmp"
ln -s /bin/cat "$scratch/bin/cat"

for script in \
    dotfiles/base/.local/bin/docker-killall \
    dotfiles/base/.local/bin/pk \
    dotfiles/base/.local/bin/memtop \
    dotfiles/base/.local/bin/ecount \
    dotfiles/base/.local/bin/gr \
    dotfiles/base/.local/bin/git-bench \
    dotfiles/base/.local/bin/git-branch-consolidation \
    dotfiles/base/.local/bin/git-tune \
    dotfiles/base/.local/bin/gh-cancel-pr-runs \
    dotfiles/base/.local/bin/ghostty-fda-check \
    dotfiles/base/.local/bin/perf-gate-ready \
    dotfiles/base/.local/bin/reset-agent-home \
    dotfiles/base/.local/bin/reset-agents \
    dotfiles/base/.local/bin/setup-git-client.sh \
    dotfiles/base/.local/bin/setup-kache \
    dotfiles/base/.local/bin/worktree-create \
    dotfiles/base/.local/bin/worktree-remove \
    dotfiles/linux/.local/bin/setup-mold
do
    for option in -h --help; do
        output=$(HOME="$scratch/home" TMPDIR="$scratch/tmp" PATH="$scratch/bin" /bin/sh "$root/$script" "$option" </dev/null)
        printf '%s\n' "$output" | grep -Fx 'Maintained by Joshua Li: https://github.com/joshuarli/usr' >/dev/null || {
            printf 'FAIL: %s %s\n' "$script" "$option" >&2
            exit 1
        }
        printf 'ok: %s %s\n' "$script" "$option"
    done
done

#!/bin/sh
set -eu

repo=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
sh "$repo/sync" list | grep -qx rg
mkdir -p "$repo/.work/tmp"
fixture=$(mktemp -d "$repo/.work/tmp/doctor-test.XXXXXX")
trap 'rm -rf "$fixture"' EXIT
trap 'exit 130' HUP INT TERM

mkdir -p "$fixture/dotfiles/base/.config" "$fixture/dotfiles/base/.codex" \
    "$fixture/dotfiles/base/.agents/skills/example" "$fixture/dotfiles/linux/.config" \
    "$fixture/dotfiles" "$fixture/home/.local/bin" "$fixture/tmp" "$fixture/mock" "$fixture/tools/sync"
cp "$repo/sync" "$fixture/sync"
cp "$repo/dotfiles/sym" "$fixture/dotfiles/sym"
cp "$repo/dotfiles/doctor" "$fixture/dotfiles/doctor"
printf '#!/bin/sh\nexit 0\n' > "$fixture/dotfiles/migrate-pinact.sh"
# shellcheck disable=SC2016
printf '#!/bin/sh\n[ "${1:-}" = --list ] || exit 2\nprintf "testtool\\n"\n' > "$fixture/tools/sync/install.sh"
printf '#!/bin/sh\nprintf "Linux\\n"\n' > "$fixture/mock/uname"
printf '#!/bin/sh\nexit 0\n' > "$fixture/home/.local/bin/testtool"
printf 'configured\n' > "$fixture/dotfiles/base/.config/example.conf"
printf 'instructions\n' > "$fixture/dotfiles/base/.codex/AGENTS.md"
printf 'skills\n' > "$fixture/dotfiles/base/.agents/skills/example/SKILL.md"
printf 'linux\n' > "$fixture/dotfiles/linux/.config/linux.conf"
printf '#!/usr/bin/env python3\nimport sys\n' > "$fixture/tools/sync/claude-worker.py"
chmod +x "$fixture/tools/sync/install.sh" "$fixture/mock/uname" "$fixture/home/.local/bin/testtool"
git -C "$fixture" init -q
git -C "$fixture" add dotfiles/base dotfiles/linux

export HOME="$fixture/home" TARGET="$fixture/home" XDG_STATE_HOME="$fixture/state" TMPDIR="$fixture/tmp"
PATH="$fixture/mock:$PATH"; export PATH

sh "$fixture/sync" links > "$fixture/link-output"
sh "$fixture/sync" doctor > "$fixture/healthy"
grep -q 'ok: doctor passed' "$fixture/healthy"
[ -L "$HOME/.config/example.conf" ]

rm "$HOME/.config/example.conf"
if sh "$fixture/sync" doctor > "$fixture/missing"; then
    echo 'doctor failed to detect missing link' >&2; exit 1
fi
grep -q '^LINK:' "$fixture/missing"
[ ! -e "$HOME/.config/example.conf" ]

printf 'foreign\n' > "$HOME/.config/example.conf"
if sh "$fixture/sync" doctor > "$fixture/conflict"; then
    echo 'doctor failed to detect conflict' >&2; exit 1
fi
grep -q '^CONFLICT:' "$fixture/conflict"
[ "$(cat "$HOME/.config/example.conf")" = foreign ]

rm "$HOME/.config/example.conf"
sh "$fixture/sync" links > "$fixture/relink-output"
rm "$HOME/.local/bin/testtool"
if sh "$fixture/sync" doctor > "$fixture/missing-tool"; then
    echo 'doctor failed to detect missing default tool' >&2; exit 1
fi
grep -q 'missing: testtool' "$fixture/missing-tool"

printf '#!/bin/sh\nexit 0\n' > "$HOME/.local/bin/testtool"
chmod +x "$HOME/.local/bin/testtool"
rm "$HOME/.codex/AGENTS.md"
if sh "$fixture/sync" doctor > "$fixture/missing-agent"; then
    echo 'doctor failed to detect missing agent instructions' >&2; exit 1
fi
grep -q 'canonical agent instructions are unavailable' "$fixture/missing-agent"

sh "$fixture/sync" links > "$fixture/relink-agents"
# shellcheck disable=SC2016
printf '#!/bin/sh\n[ "${1:-}" = --list ] || exit 2\nprintf "ffmpeg\\n"\n' > "$fixture/tools/sync/install.sh"
printf '#!/bin/sh\nexit 0\n' > "$HOME/.local/bin/ffmpeg"
chmod +x "$HOME/.local/bin/ffmpeg"
if sh "$fixture/sync" doctor > "$fixture/half-pair"; then
    echo 'doctor accepted ffmpeg without ffprobe' >&2; exit 1
fi
grep -q 'missing: ffmpeg (~/.local/bin/ffprobe)' "$fixture/half-pair"
if grep -q 'missing: ffmpeg (~/.local/bin/ffmpeg)' "$fixture/half-pair"; then
    echo 'doctor reported the present ffmpeg launcher' >&2; exit 1
fi
printf '#!/bin/sh\nexit 0\n' > "$HOME/.local/bin/ffprobe"
chmod +x "$HOME/.local/bin/ffprobe"
sh "$fixture/sync" doctor > "$fixture/full-pair"
grep -q 'ok: doctor passed' "$fixture/full-pair"

printf 'doctor: fixture checks passed\n'

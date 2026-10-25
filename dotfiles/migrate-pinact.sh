#!/bin/sh
# Retire only the old dl-owned binary before sym links the bundled pinact.
set -eu

[ "$1" = "$HOME" ] || exit 0
old="$HOME/.local/bin/pinact"
marker="${XDG_STATE_HOME:-$HOME/.local/state}/dl/pinact"
owned=$2
[ -f "$marker" ] || exit 0

# A missing binary or an existing symlink needs only stale state cleanup.
if [ ! -e "$old" ] || [ -L "$old" ]; then
    rm -f "$marker"
    exit 0
fi

if [ ! -f "$old" ] || [ ! -f "$owned" ] || ! awk -F '\t' -v path="$old" \
    '$1 == "F" && $2 == path { found = 1 } END { exit !found }' "$owned"; then
    printf 'pinact migration: %s is not recorded as dl-owned; refusing to replace it\n' "$old" >&2
    exit 1
fi
rm "$old" "$marker"

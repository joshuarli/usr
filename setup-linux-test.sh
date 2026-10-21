#!/bin/sh
set -eu

root=$(cd "$(dirname "$0")" && pwd)
os_id=$(awk -F= '$1 == "ID" { gsub(/^"/, "", $2); gsub(/"$/, "", $2); print $2; exit }' /etc/os-release 2>/dev/null || :)
if [ "$(uname -s)" != Linux ] || [ "$os_id" != alpine ]; then
    printf 'setup-linux-test: skipped outside Alpine Linux\n'
    exit 0
fi

find_apk_source=$(sed -n '/^find_apk() {$/,/^}$/p' "$root/setup-linux")
[ -n "$find_apk_source" ] || { printf 'setup-linux: find_apk is missing\n' >&2; exit 1; }
eval "$find_apk_source"

expected=
for candidate in /sbin/apk /usr/sbin/apk /usr/bin/apk /bin/apk; do
    if [ -x "$candidate" ]; then
        expected=$candidate
        break
    fi
done
[ -n "$expected" ] || { printf 'setup-linux: apk is unavailable\n' >&2; exit 1; }

# shellcheck disable=SC2123
PATH=/nonexistent
export PATH
actual=$(find_apk)
[ "$actual" = "$expected" ] || {
    printf 'setup-linux: expected %s with restricted PATH, got %s\n' "$expected" "$actual" >&2
    exit 1
}

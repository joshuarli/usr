#!/bin/sh
set -eu

root=$(cd "$(dirname "$0")" && pwd)

path_line=$(awk '/^PATH=/ { print; exit }' "$root/setup-linux")
[ -n "$path_line" ] || { printf 'setup-linux: PATH is not set\n' >&2; exit 1; }
case $path_line in
    *'$'*) printf 'setup-linux: PATH must be hermetic, got: %s\n' "$path_line" >&2; exit 1 ;;
esac

os_id=$(awk -F= '$1 == "ID" { gsub(/^"/, "", $2); gsub(/"$/, "", $2); print $2; exit }' /etc/os-release 2>/dev/null || :)
if [ "$(uname -s)" != Linux ] || [ "$os_id" != alpine ]; then
    printf 'setup-linux-test: skipped apk resolution outside Alpine Linux\n'
    exit 0
fi

expected=
for candidate in /usr/local/sbin/apk /usr/local/bin/apk /usr/sbin/apk /usr/bin/apk /sbin/apk /bin/apk; do
    if [ -x "$candidate" ]; then
        expected=$candidate
        break
    fi
done
[ -n "$expected" ] || { printf 'setup-linux: apk is unavailable\n' >&2; exit 1; }

# shellcheck disable=SC2123
PATH=/nonexistent
export PATH
eval "$path_line"
actual=$(command -v apk)
[ "$actual" = "$expected" ] || {
    printf 'setup-linux: expected %s with restricted PATH, got %s\n' "$expected" "${actual:-nothing}" >&2
    exit 1
}

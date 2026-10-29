#!/bin/sh
set -eu

root=$(cd "$(dirname "$0")" && pwd)

os_id=
if [ -r /etc/os-release ]; then
    os_id=$(awk -F= '$1 == "ID" { gsub(/^"/, "", $2); gsub(/"$/, "", $2); print $2; exit }' /etc/os-release)
fi
if [ "$(uname -s)" = Linux ] && [ "$os_id" = alpine ]; then
    printf 'setup-test: skipped on Alpine Linux (the bootstrap would provision)\n'
    exit 0
fi

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT HUP INT TERM
status=0
output=$(HOME="$tmp" sh "$root/setup.sh" 2>&1) || status=$?
[ "$status" -ne 0 ] || { printf 'setup-test: expected setup.sh to refuse, got success\n' >&2; exit 1; }
case $output in
*Alpine*) ;;
*)
    printf 'setup-test: expected an Alpine-only refusal, got: %s\n' "$output" >&2
    exit 1
    ;;
esac
[ ! -e "$tmp/usr" ] || { printf 'setup-test: refused run created %s\n' "$tmp/usr" >&2; exit 1; }
printf 'setup-test: ok\n'

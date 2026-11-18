#!/bin/sh
set -eu
cd "$(dirname "$0")"
[ -x /usr/bin/python3 ] || { echo 'verify: python3 is missing; run install.sh first' >&2; exit 1; }
exec /usr/bin/python3 -I -B provision.py verify "$@"

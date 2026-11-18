#!/bin/sh
# Bootstrap: provision.py needs Alpine's python3, so install it before handing off.
set -eu
cd "$(dirname "$0")"
die() { printf 'home: %s\n' "$*" >&2; exit 1; }
[ "$(id -u)" -eq 0 ] || die 'run as root, for example: doas sh usr/host/alpine/install.sh'
grep -qsx 'ID=alpine' /etc/os-release || die 'this provisioner supports only Alpine Linux'
command -v git >/dev/null || die 'git is required: apk add git'
if [ ! -x /usr/bin/python3 ]; then
	apk add --quiet python3 || die 'could not install python3; check networking and /etc/apk/repositories'
fi
exec /usr/bin/python3 -I -B provision.py apply

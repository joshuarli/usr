#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
version=0.9
sha=5d0b70dfe3e47a0df3015353f3184b6d18625de4de980b4abdd0c0d8a6190cfd
build_id=$(cat build/dwl.sh config/dwl.h config/dwl-relative-tags.patch | sha256sum | cut -c1-12)
build_version=$version-home.$build_id
target=/usr/local/bin/dwl

case ${1:-} in
	--version) printf 'dwl %s\n' "$build_version"; exit 0 ;;
	'') ;;
	*) echo "usage: $0 [--version]" >&2; exit 2 ;;
esac

if [ -x "$target" ] && [ "$("$target" -v 2>&1)" = "dwl $build_version" ]; then
	echo "home: $target is current ($build_version)"
	exit 0
fi

apk add --quiet --virtual .home-dwl-build make pkgconf patch unzip wayland-dev wayland-protocols \
	libinput-dev libxkbcommon-dev wlroots0.20-dev
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"; apk del --quiet .home-dwl-build' EXIT HUP INT TERM
wget -q -O "$tmp/dwl.zip" "https://mirror.17166969.xyz/current/dwl-0.9.zip"
printf '%s  %s\n' "$sha" "$tmp/dwl.zip" | sha256sum -c -s - || {
	echo "home: dwl $version source does not match the pinned SHA-256" >&2
	exit 1
}
unzip -q -d "$tmp/dwl" "$tmp/dwl.zip"
patch -s -p1 -d "$tmp/dwl" < config/dwl-relative-tags.patch
cp config/dwl.h "$tmp/dwl/config.h"
make -s -C "$tmp/dwl" CC=clang CFLAGS='-O2 -std=gnu23' VERSION="$build_version"
install -o root -g root -m 0755 "$tmp/dwl/dwl" "$target"
echo "home: installed $target ($build_version)"

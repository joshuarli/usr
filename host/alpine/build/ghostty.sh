#!/bin/sh
set -eu
cd "$(dirname "$0")/.."

arch=$(apk --print-arch)
case $arch in
	x86_64 | aarch64) ;;
	*) echo "home: architecture $arch is not supported" >&2; exit 1 ;;
esac
asset=ghostty-custom-$arch-linux-musl.tar.gz
target=/usr/local/bin/ghostty-custom
tagdir=/usr/local/share/home
tagfile=$tagdir/ghostty-custom.tag
repo=https://github.com/joshuarli/ghostty

latest_tag() {
	curl -fsSL "$repo/releases.atom" | awk '
		/<entry>/ { in_entry = 1; updated = ""; tag = "" }
		in_entry && /<updated>/ {
			updated = $0
			sub(/^.*<updated>/, "", updated)
			sub(/<.*/, "", updated)
		}
		in_entry && /<link[^>]*releases\/tag\// {
			tag = $0
			sub(/^.*releases\/tag\//, "", tag)
			sub(/".*/, "", tag)
			if (index(tag, "release-") != 1) tag = ""
		}
		/\/entry>/ {
			if (updated > newest_updated && tag != "") {
				newest_updated = updated
				newest_tag = tag
			}
			in_entry = 0
		}
		END { print newest_tag }
	'
}

case ${1:-} in
	--version)
		latest=$(latest_tag)
		[ -n "$latest" ] || { echo "home: no ghostty release found" >&2; exit 1; }
		printf '%s\n' "$latest"
		exit 0
		;;
	'') ;;
	*) echo "usage: $0 [--version]" >&2; exit 2 ;;
esac

tag=$(latest_tag)
[ -n "$tag" ] || { echo "home: no ghostty release found" >&2; exit 1; }

if [ -f "$tagfile" ] && [ "$(cat "$tagfile")" = "$tag" ] &&
	[ -x "$target" ] && [ -f "$target" ] && [ ! -L "$target" ] &&
	[ -f /usr/share/terminfo/x/xterm-ghostty ]; then
	if ldd "$target" 2>&1 | grep -q "not found"; then
		echo "home: $target has unresolved libraries" >&2
		exit 1
	elif "$target" --version >/dev/null 2>&1 &&
		"$target" +show-config >/dev/null 2>&1; then
		echo "home: $target is current ($tag)"
		exit 0
	fi
fi

sums=$(mktemp)
trap 'rm -f "$sums"' EXIT HUP INT TERM
curl -fsSL "$repo/releases/download/$tag/SHA256SUMS" -o "$sums" || {
	echo "home: SHA256SUMS download failed for $tag" >&2
	exit 1
}
sha=$(grep -F "  $asset" "$sums" | awk '{ print $1 }')
rm -f "$sums"
trap - EXIT HUP INT TERM
[ "${#sha}" -eq 64 ] || {
	echo "home: $asset is not available in $tag" >&2
	exit 1
}

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"; apk del --quiet .home-ghostty-build 2>/dev/null || :' EXIT HUP INT TERM
curl -fsSL "$repo/releases/download/$tag/$asset" -o "$tmp/ghostty.tgz" || {
	echo "home: $asset download failed" >&2
	exit 1
}
printf '%s  %s\n' "$sha" "$tmp/ghostty.tgz" | sha256sum -c -s - || {
	echo "home: $asset does not match SHA256SUMS" >&2
	exit 1
}
contents=$(tar -tzf "$tmp/ghostty.tgz") || {
	echo "home: $asset could not be listed" >&2
	exit 1
}
if [ "$(printf '%s\n' "$contents" | wc -l)" -ne 1 ] ||
	printf '%s\n' "$contents" | grep -Eq '(^/|(^|/)\.\.(/|$))'; then
	echo "home: $asset does not contain a single top-level binary" >&2
	exit 1
fi
tar -xzf "$tmp/ghostty.tgz" -C "$tmp"
[ -f "$tmp/ghostty" ] && [ ! -L "$tmp/ghostty" ] || {
	echo "home: $asset is missing the ghostty binary" >&2
	exit 1
}

apk add --quiet --virtual .home-ghostty-build ncurses
install -o root -g root -m 0755 "$tmp/ghostty" "$target"
echo "home: installed $target ($tag)"

mkdir -p "$tagdir"
printf '%s\n' "$tag" > "$tagfile.tmp"
install -o root -g root -m 0644 "$tagfile.tmp" "$tagfile"
rm -f "$tagfile.tmp"

"$target" +show-terminfo 2>/dev/null | tic -x -o /usr/share/terminfo - || {
	echo "home: ghostty terminfo install failed" >&2
	exit 1
}

ldd "$target" 2>&1 | grep -q "not found" && {
	echo "home: $target has unresolved libraries" >&2
	exit 1
}
"$target" --version >/dev/null 2>&1 || {
	echo "home: $target --version failed" >&2
	exit 1
}
"$target" +show-config >/dev/null 2>&1 || {
	echo "home: $target +show-config failed" >&2
	exit 1
}
[ -f /usr/share/terminfo/x/xterm-ghostty ] || {
	echo "home: ghostty terminfo is missing after install" >&2
	exit 1
}

#!/bin/sh
set -eu
cd "$(dirname "$0")/.."

repo=https://github.com/laputa-systems/chromium-build
tagdir=/usr/local/share/home
tagfile=$tagdir/helium.tag
libroot=/usr/local/lib/helium
target=/usr/local/bin/helium

fail() { printf 'home: %s\n' "$*" >&2; exit 1; }
say() { printf 'home: %s\n' "$*"; }

arch=$(apk --print-arch)
case $arch in
	x86_64) ;;
	*)
		say "helium is not available for $arch; skipping"
		exit 0
		;;
esac

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
			if (index(tag, "helium-") != 1) tag = ""
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
		tag=$(latest_tag)
		[ -n "$tag" ] || fail 'no helium release found'
		printf '%s\n' "$tag"
		exit 0
		;;
	'') ;;
	*) fail "usage: $0 [--version]" ;;
esac

if [ ! -f /usr/lib/libva.so.2 ] || [ ! -f /usr/lib/dri/i965_drv_video.so ]; then
	apk add --quiet libva libva-intel-driver ||
		fail 'could not install the Intel VA-API runtime'
fi

tag=$(latest_tag)
[ -n "$tag" ] || fail 'no helium release found'
version=${tag#helium-}
asset=helium-${version}-linux-x86_64-musl.tar.xz
root=${asset%.tar.xz}

current_release=$(readlink "$libroot/current" 2>/dev/null || :)
if [ -f "$tagfile" ] && [ "$(cat "$tagfile")" = "$tag" ] &&
	[ -L "$libroot/current" ] && [ -d "$current_release" ] &&
	[ -L "$target" ] && [ "$(readlink "$target")" = "$libroot/current/helium-wrapper" ]; then
	if ! LD_LIBRARY_PATH="$current_release/lib" ldd "$current_release/helium" 2>&1 | grep -q 'not found' &&
		{ [ -z "${USER_NAME:-}" ] || su -s /bin/sh "$USER_NAME" -c "$target --version" >/dev/null 2>&1; } &&
		{ [ -n "${USER_NAME:-}" ] || "$target" --version >/dev/null 2>&1; }; then
		say "helium is current ($tag)"
		exit 0
	fi
fi

if [ -e "$target" ] && [ ! -L "$target" ]; then
	fail "$target exists and is not a home-managed symlink"
fi
if [ -L "$target" ] && [ "$(readlink "$target")" != "$libroot/current/helium-wrapper" ]; then
	fail "$target points outside the home helium install"
fi
if [ -e "$libroot/current" ] && [ ! -L "$libroot/current" ]; then
	fail "$libroot/current exists and is not a home-managed symlink"
fi

mkdir -p "$libroot"
work=$(mktemp -d)
tmpdir=
cleanup() {
	rm -rf "$work"
	[ -z "$tmpdir" ] || rm -rf "$tmpdir"
	apk del --quiet .home-helium-build 2>/dev/null || :
}
trap cleanup EXIT HUP INT TERM

apk add --quiet --virtual .home-helium-build xz

say "downloading helium $version"
curl -fsSL "$repo/releases/download/$tag/$asset" -o "$work/$asset" || fail "$asset download failed"
curl -fsSL "$repo/releases/download/$tag/$asset.sha256" -o "$work/$asset.sha256" || fail "$asset.sha256 download failed"
curl -fsSL "$repo/releases/download/$tag/$asset.acceptance.json" -o "$work/$asset.acceptance.json" ||
	fail "$asset.acceptance.json download failed"

expected=$(awk 'NR == 1 { print $1 }' "$work/$asset.sha256")
actual=$(sha256sum "$work/$asset" | awk '{ print $1 }')
[ "${#expected}" -eq 64 ] && [ "$expected" = "$actual" ] || fail "$asset checksum mismatch"

jq -e --arg asset "$asset" --arg sha "$expected" '
	.schema == 1 and .status == "complete" and .product == "helium" and
	.archive == $asset and .archive_sha256 == $sha and
	(.checks | type == "object" and length > 0 and all(.[]; . == true))
' "$work/$asset.acceptance.json" >/dev/null || fail "$asset acceptance sidecar is invalid"

tar -tJf "$work/$asset" >"$work/contents" || fail "$asset could not be listed"
awk '
	BEGIN { bad = 0 }
	/^\// { bad = 1 }
	{
		count = split($0, path, "/")
		for (component = 1; component <= count; component++) {
			if (path[component] == "..") bad = 1
		}
	}
	END { exit bad }
' "$work/contents" || fail "$asset contains an unsafe path"
[ "$(awk -F/ 'NF { print $1 }' "$work/contents" | sort -u)" = "$root" ] ||
	fail "$asset does not contain a single top-level directory"

release=$libroot/$version
if [ ! -d "$release" ]; then
	tmpdir=$(mktemp -d "$libroot/.helium.XXXXXX")
	tar -xJf "$work/$asset" -C "$tmpdir" || fail "$asset could not be extracted"
	[ -d "$tmpdir/$root" ] || fail "$asset is missing $root"
	mv "$tmpdir/$root" "$release" || fail "could not install $release"
	rm -rf "$tmpdir"
	tmpdir=
fi

[ -f "$release/package-manifest.json" ] || fail "$release has no package manifest"
jq -e --arg version "$version" '
	.schema == 1 and .status == "complete" and .product == "helium" and
	.product_version == $version and .architecture == "amd64" and
	.launcher == "helium-wrapper" and .executable == "helium" and
	(.files | type == "array" and length > 0)
' "$release/package-manifest.json" >/dev/null || fail "$release package manifest is invalid"
jq -r '.files[].path' "$release/package-manifest.json" |
	awk '
		BEGIN { bad = 0 }
		/^\// { bad = 1 }
		{
			count = split($0, path, "/")
			for (component = 1; component <= count; component++) {
				if (path[component] == "..") bad = 1
			}
		}
		END { exit bad }
	' || fail "$release package manifest contains an unsafe path"
jq -r '.files[] | "\(.sha256)  \(.path)"' "$release/package-manifest.json" >"$work/sums"
(cd "$release" && sha256sum -c "$work/sums" >/dev/null) || fail "$release file digests do not match"

[ -x "$release/helium" ] || fail "$release/helium is not executable"
[ -x "$release/helium-wrapper" ] || fail "$release/helium-wrapper is not executable"
chmod 4755 "$release/chrome_sandbox" || fail "$release/chrome_sandbox is missing"

ln -sfn "$release" "$libroot/current" || fail "could not switch $libroot/current"
mkdir -p "$(dirname "$target")"
ln -sfn "$libroot/current/helium-wrapper" "$target" || fail "could not link $target"

mkdir -p "$tagdir"
printf '%s\n' "$tag" >"$tagfile.tmp"
install -o root -g root -m 0644 "$tagfile.tmp" "$tagfile"
rm -f "$tagfile.tmp"

if LD_LIBRARY_PATH="$release/lib" ldd "$release/helium" 2>&1 | grep -q 'not found'; then
	fail "$release has unresolved libraries"
fi
if [ -n "${USER_NAME:-}" ]; then
	su -s /bin/sh "$USER_NAME" -c "$target --version" >/dev/null 2>&1 ||
		fail "$target --version failed for $USER_NAME"
else
	"$target" --version >/dev/null 2>&1 || fail "$target --version failed"
fi
say "installed $target ($tag)"

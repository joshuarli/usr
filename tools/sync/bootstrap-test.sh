#!/bin/sh
set -eu
root=$(CDPATH='' cd -- "$(dirname -- "$0")/../.." && pwd)
tmp=${TMPDIR:-$root/.work/tmp}
mkdir -p "$tmp"
work=$(mktemp -d "$tmp/bootstrap-test.XXXXXX")
unset XDG_DATA_HOME XDG_CONFIG_HOME XDG_CACHE_HOME XDG_STATE_HOME
trap 'rm -rf "$work"' 0
fail() { printf 'bootstrap-test: %s\n' "$*" >&2; exit 1; }

case "$(uname -s):$(uname -m | sed 's/arm64/aarch64/')" in
    Darwin:aarch64) triple=aarch64-apple-darwin ;;
    Linux:x86_64) triple=x86_64-unknown-linux-musl ;;
    Linux:aarch64) triple=aarch64-unknown-linux-musl ;;
    *) printf 'bootstrap-test: skipped on %s/%s\n' "$(uname -s)" "$(uname -m)"; exit 0 ;;
esac

stub=$work/bin
payload=$work/payload.tar.xz
tag=release-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
asset="cpython-3.15.1-${triple}.tar.xz"
python3 - "$payload" <<'PY'
import io, sys, tarfile
script = b"#!/bin/sh\nif [ \"$1\" = -c ]; then exit 0; fi\nprintf 'Python 3.15.1\\n'\n"
with tarfile.open(sys.argv[1], mode="w:xz") as archive:
    info = tarfile.TarInfo("python/bin/python3.15")
    info.size = len(script)
    info.mode = 0o755
    archive.addfile(info, io.BytesIO(script))
PY
digest=$(sha256sum "$payload")
digest=${digest%% *}
fake_atom=$work/releases.atom
cat > "$fake_atom" <<EOF
<?xml version="1.0"?><feed><entry><link href="https://github.com/laputa-systems/python-build/releases/tag/${tag}"/><updated>2026-11-14T00:00:00Z</updated></entry></feed>
EOF
fake_sums=$work/SHA256SUMS
printf '%s  %s\n' "$digest" "$asset" > "$fake_sums"

mkdir -p "$stub"
cat > "$stub/curl" <<'EOS'
#!/bin/sh
out=
prev=
url=
for arg in "$@"; do
    if [ "$prev" = "-o" ]; then out=$arg; fi
    case $arg in -o) ;; -*) ;; *) url=$arg ;; esac
    prev=$arg
done
[ -n "$out" ] || out=/dev/stdout
case "$url" in
    */releases.atom) cat "$FAKE_ATOM" > "$out" ;;
    */SHA256SUMS) cat "$FAKE_SUMS" > "$out" ;;
    */cpython-*.tar.xz)
        if [ "${FAKE_CURL_CORRUPT:-}" = 1 ]; then printf 'corrupt' > "$out"; exit 0; fi
        cat "$FAKE_PAYLOAD" > "$out" ;;
    *) exit 1 ;;
esac
EOS
chmod +x "$stub/curl"

setup() {
    home=$work/home-$1
    mkdir -p "$home" "$stub"
    cp "$root/tools/sync/bootstrap.sh" "$work/bootstrap.sh"
    printf '%s' "$home"
}
run_bootstrap() {
    HOME=$1 FAKE_ATOM=$fake_atom FAKE_SUMS=$fake_sums FAKE_PAYLOAD=$2 PATH="$stub:$PATH" sh "$work/bootstrap.sh" python3
}

home=$(setup install)
run_bootstrap "$home" "$payload" >/dev/null
[ -L "$home/.local/bin/python3" ] || fail "python3 launcher was not installed"
[ "$(cat "$home/.local/state/dl/python3")" = "$digest" ] || fail "state does not record the asset digest"
"$home/.local/bin/python3" -c 'import sqlite3, ssl' || fail "installed python3 does not run its smoke import"
run_bootstrap "$home" "$payload" > "$work/second.log"
grep -q "is current" "$work/second.log" || fail "second run was not idempotent: $(cat "$work/second.log")"

home=$(setup mismatch)
mkdir -p "$home/.local/bin"
printf 'keep' > "$home/.local/bin/python3"
if FAKE_CURL_CORRUPT=1 HOME=$home FAKE_ATOM=$fake_atom FAKE_SUMS=$fake_sums FAKE_PAYLOAD=$payload PATH="$stub:$PATH" sh "$work/bootstrap.sh" python3 >"$work/mismatch.log" 2>&1; then
    fail "checksum mismatch was not rejected"
fi
[ "$(cat "$home/.local/bin/python3")" = "keep" ] || fail "checksum mismatch replaced an existing python3"

home=$(setup resume)
mkdir -p "$home/.local/share/python-build/$tag"
tar -xJf "$payload" -C "$home/.local/share/python-build/$tag"
chmod +x "$home/.local/share/python-build/$tag/python/bin/python3.15"
run_bootstrap "$home" "$payload" >/dev/null
[ -L "$home/.local/bin/python3" ] || fail "interrupted install was not resumed"

python3 - "$work/evil.tar.xz" <<'PY'
import io, sys, tarfile
with tarfile.open(sys.argv[1], mode="w:xz") as archive:
    info = tarfile.TarInfo("../evil")
    info.size = 1
    archive.addfile(info, io.BytesIO(b"x"))
PY
fake_sums_evil=$work/SHA256SUMS.evil
printf '%s  %s\n' "$(sha256sum "$work/evil.tar.xz" | awk '{print $1}')" "cpython-3.15.1-${triple}.tar.xz" > "$fake_sums_evil"
home=$(setup evil)
if HOME=$home FAKE_ATOM=$fake_atom FAKE_SUMS=$fake_sums_evil FAKE_PAYLOAD=$work/evil.tar.xz PATH="$stub:$PATH" sh "$work/bootstrap.sh" python3 >"$work/evil.log" 2>&1; then
    fail "archive with an unsafe path was not rejected"
fi
[ ! -e "$home/.local/bin/python3" ] || fail "unsafe archive installed a python3 launcher"

# A managed python3 that crashes (as a build for a newer macOS does on its first
# subprocess) must not be chosen; sync falls back to a working python3.
crash_home=$work/crash-home
mkdir -p "$crash_home/.local/bin" "$work/good-bin"
cat > "$crash_home/.local/bin/python3" <<'EOS'
#!/bin/sh
[ "${1:-}" = --version ] && exec python3-real --version
kill -SEGV $$
EOS
chmod 755 "$crash_home/.local/bin/python3"
real=$(command -v python3)
ln -s "$real" "$work/good-bin/python3-real"
ln -s "$real" "$work/good-bin/python3"
if ! HOME=$crash_home DL_OWNED_FILE=$crash_home/owned PATH="$work/good-bin:/usr/bin:/bin" \
        sh "$root/sync" layers >"$work/crash.log" 2>&1; then
    fail "sync did not run main.py on the fallback python3: $(cat "$work/crash.log")"
fi

printf 'bootstrap-test: ok\n'

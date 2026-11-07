#!/bin/sh
set -eu
root=$(CDPATH='' cd -- "$(dirname -- "$0")/../.." && pwd)
tmp=${TMPDIR:-$root/.work/tmp}
mkdir -p "$tmp"
work=$(mktemp -d "$tmp/bootstrap-test.XXXXXX")
trap 'rm -rf "$work"' 0
fail() { printf 'bootstrap-test: %s\n' "$*" >&2; exit 1; }

case "$(uname -s):$(uname -m | sed 's/arm64/aarch64/')" in
    Darwin:aarch64) triple=aarch64-apple-darwin ;;
    Linux:x86_64) triple=x86_64-unknown-linux-musl ;;
    Linux:aarch64) triple=aarch64-unknown-linux-musl ;;
    *) printf 'bootstrap-test: skipped on %s/%s\n' "$(uname -s)" "$(uname -m)"; exit 0 ;;
esac

stub=$work/bin
payload=$work/payload.tar.gz
python3 - "$payload" <<'PY'
import io, sys, tarfile
script = b"#!/bin/sh\nif [ \"$1\" = -c ]; then exit 0; fi\nprintf 'Python 3.15.1\\n'\n"
with tarfile.open(sys.argv[1], mode="w:gz") as archive:
    info = tarfile.TarInfo("python/bin/python3.15")
    info.size = len(script)
    info.mode = 0o755
    archive.addfile(info, io.BytesIO(script))
PY

mkdir -p "$stub"
cat > "$stub/curl" <<'EOS'
#!/bin/sh
out=
for arg in "$@"; do case $arg in -o) ;; -*) ;; *) out=$arg ;; esac; done
# last non-flag argument is the URL; the -o value is before it in our calls
prev=
url=
for arg in "$@"; do
    if [ "$prev" = "-o" ]; then out=$arg; fi
    case $arg in -o) ;; -*) ;; *) url=$arg ;; esac
    prev=$arg
done
[ -n "$out" ] || exit 1
if [ "${FAKE_CURL_CORRUPT:-}" = 1 ]; then printf 'corrupt' > "$out"; exit 0; fi
cat "$FAKE_PAYLOAD" > "$out"
EOS
chmod +x "$stub/curl"

setup() {
    home=$work/home-$1
    if command -v sha256sum >/dev/null 2>&1; then case_digest=$(sha256sum "$2" | awk '{print $1}'); else case_digest=$(shasum -a 256 "$2" | awk '{print $1}'); fi
    mkdir -p "$home" "$stub"
    cp "$root/tools/sync/bootstrap.sh" "$work/bootstrap.sh"
    printf '20261107 laputa-systems/python-build\n%s cpython-3.15.1+20261107-%s-install_only_stripped.tar.gz %s\n' \
        "$triple" "$triple" "$case_digest" > "$work/python-build.pin"
    printf '%s' "$home"
}
run_bootstrap() {
    HOME=$1 FAKE_PAYLOAD=$2 PATH="$stub:$PATH" sh "$work/bootstrap.sh" python3
}

home=$(setup install "$payload")
if command -v sha256sum >/dev/null 2>&1; then digest=$(sha256sum "$payload" | awk '{print $1}'); else digest=$(shasum -a 256 "$payload" | awk '{print $1}'); fi
run_bootstrap "$home" "$payload" >/dev/null
[ -L "$home/.local/bin/python3" ] || fail "python3 launcher was not installed"
[ "$(cat "$home/.local/state/dl/python3")" = "$digest" ] || fail "state does not record the pinned digest"
"$home/.local/bin/python3" -c 'import sqlite3, ssl' || fail "installed python3 does not run its smoke import"
run_bootstrap "$home" "$payload" > "$work/second.log"
grep -q "is current" "$work/second.log" || fail "second run was not idempotent: $(cat "$work/second.log")"

home=$(setup mismatch "$payload")
mkdir -p "$home/.local/bin"
printf 'keep' > "$home/.local/bin/python3"
if FAKE_CURL_CORRUPT=1 HOME=$home FAKE_PAYLOAD=$payload PATH="$stub:$PATH" sh "$work/bootstrap.sh" python3 >"$work/mismatch.log" 2>&1; then
    fail "checksum mismatch was not rejected"
fi
[ "$(cat "$home/.local/bin/python3")" = "keep" ] || fail "checksum mismatch replaced an existing python3"

home=$(setup resume "$payload")
mkdir -p "$home/.local/share/python-build/20261107"
tar -xzf "$payload" -C "$home/.local/share/python-build/20261107"
chmod +x "$home/.local/share/python-build/20261107/python/bin/python3.15"
run_bootstrap "$home" "$payload" >/dev/null
[ -L "$home/.local/bin/python3" ] || fail "interrupted install was not resumed"

python3 - "$work/evil.tar.gz" <<'PY'
import io, sys, tarfile
with tarfile.open(sys.argv[1], mode="w:gz") as archive:
    info = tarfile.TarInfo("../evil")
    info.size = 1
    archive.addfile(info, io.BytesIO(b"x"))
PY
home=$(setup evil "$work/evil.tar.gz")
if run_bootstrap "$home" "$work/evil.tar.gz" >"$work/evil.log" 2>&1; then
    fail "archive with an unsafe path was not rejected"
fi
[ ! -e "$home/.local/bin/python3" ] || fail "unsafe archive installed a python3 launcher"

printf 'bootstrap-test: ok\n'

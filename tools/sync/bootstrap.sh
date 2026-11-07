#!/bin/sh
# Pre-Python bootstrap: installs only jaq and the managed python3, for use on
# machines where no Python interpreter exists yet. Everything else is
# installed by tools/sync/installer.py under tools/sync/main.py.
set -eu

ARCH=$(uname -m | sed 's/arm64/aarch64/')
OS=$(uname -s)
case "$OS" in
    Darwin|Linux) ;;
    *) printf '✗ Unsupported OS: %s\n' "$OS" >&2; exit 1 ;;
esac

DEST="${HOME}/.local/bin"
PYTHON_BUILD_ROOT="${XDG_DATA_HOME:-${HOME}/.local/share}/python-build"
STATE="${XDG_STATE_HOME:-${HOME}/.local/state}/dl"
DL_OWNED_FILE=${DL_OWNED_FILE:-}
failed=false
tmpzip=
tmpbin=
tmpoutput=
tmpbundle=

DL_COLOR=${DL_COLOR:-auto}
if [ "$DL_COLOR" = auto ]; then
    if [ -n "${NO_COLOR:-}" ]; then DL_COLOR=0
    elif [ -t 1 ]; then DL_COLOR=1
    else DL_COLOR=0
    fi
fi
case "$DL_COLOR" in 1|true|yes|always) DL_COLOR=1 ;; *) DL_COLOR=0 ;; esac
if [ "$DL_COLOR" = 1 ]; then
    _dl_reset=$(printf '\033[0m'); _dl_dim=$(printf '\033[2m')
    _dl_red=$(printf '\033[31m'); _dl_green=$(printf '\033[32m')
    _dl_yellow=$(printf '\033[33m'); _dl_blue=$(printf '\033[34m')
else
    _dl_reset=; _dl_dim=; _dl_red=; _dl_green=; _dl_yellow=; _dl_blue=
fi
_dl_ok() { printf '%s✓ %s%s\n' "$_dl_green" "$1" "$_dl_reset"; }
_dl_current() { printf '%s· %s%s\n' "$_dl_dim" "$1" "$_dl_reset"; }
_dl_fetch() { printf '%s↓ %s%s\n' "$_dl_blue" "$1" "$_dl_reset"; }
_dl_warn() { printf '%s! %s%s\n' "$_dl_yellow" "$1" "$_dl_reset" >&2; }
_dl_fail() { printf '%s✗ %s%s\n' "$_dl_red" "$1" "$_dl_reset" >&2; }
skip() { _dl_fail "Skipping $1: $2"; failed=true; }
unchecked() {
    if [ -x "${DEST}/$1" ]; then
        _dl_warn "Warning: keeping installed $1 ($2; will retry next run)"
    else
        skip "$1" "$2"
    fi
}

own_file() {
    if [ -n "$DL_OWNED_FILE" ] && { [ ! -f "$DL_OWNED_FILE" ] \
        || ! awk -F '\t' -v path="$1" '$1 == "F" && $2 == path { found = 1 } END { exit !found }' "$DL_OWNED_FILE"; }; then
        printf 'F\t%s\n' "$1" >> "$DL_OWNED_FILE"
    fi
}
own_dir() {
    if [ -n "$DL_OWNED_FILE" ] && { [ ! -f "$DL_OWNED_FILE" ] \
        || ! awk -F '\t' -v path="$1" '$1 == "D" && $2 == path { found = 1 } END { exit !found }' "$DL_OWNED_FILE"; }; then
        printf 'D\t%s\n' "$1" >> "$DL_OWNED_FILE"
    fi
}
own_empty_dir() {
    if [ -n "$DL_OWNED_FILE" ] && { [ ! -f "$DL_OWNED_FILE" ] \
        || ! awk -F '\t' -v path="$1" '$1 == "E" && $2 == path { found = 1 } END { exit !found }' "$DL_OWNED_FILE"; }; then
        printf 'E\t%s\n' "$1" >> "$DL_OWNED_FILE"
    fi
}
own_missing_dirs() {
    [ ! -d "$1" ] || return 0
    own_empty_dir "$1"
    missing_parent=${1%/*}
    [ -n "$missing_parent" ] || missing_parent=/
    [ "$missing_parent" = "$1" ] || own_missing_dirs "$missing_parent"
}

own_missing_dirs "$DEST"
mkdir -p "$DEST"
own_missing_dirs "$STATE"
mkdir -p "$STATE"

cleanup_temporary_files() {
    [ -z "$tmpzip" ] || rm -f "$tmpzip" || _dl_warn "Warning: could not remove $tmpzip"
    [ -z "$tmpbin" ] || rm -f "$tmpbin" || _dl_warn "Warning: could not remove $tmpbin"
    [ -z "$tmpoutput" ] || rm -f "$tmpoutput" || _dl_warn "Warning: could not remove $tmpoutput"
    [ -z "$tmpbundle" ] || rm -rf "$tmpbundle" || _dl_warn "Warning: could not remove $tmpbundle"
    return 0
}
trap 'cleanup_temporary_files' 0
trap 'cleanup_temporary_files; exit 129' HUP
trap 'cleanup_temporary_files; exit 130' INT
trap 'cleanup_temporary_files; exit 143' TERM

# A one-byte ranged GET, because release URLs redirect to signed storage URLs that reject HEAD.
asset_id() {
    curl -fsSL -r 0-0 -D - -o /dev/null "$1" 2>/dev/null \
        | tr -d '\r' | sed -n 's/^[Ee][Tt][Aa][Gg]: *//p' | tail -n 1
}

is_current() {
    if [ -x "${DEST}/$1" ] && [ "$(cat "${STATE}/$1" 2>/dev/null)" = "$2" ]; then
        own_file "${DEST}/$1"
        own_file "${STATE}/$1"
        return 0
    fi
    return 1
}

installed() {
    [ -x "${DEST}/$1" ] && [ ! -d "${DEST}/$1" ]
}

sha256_file() {
    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum "$1" | awk '{print $1}'
    else
        shasum -a 256 "$1" | awk '{print $1}'
    fi
}

install_binary() {
    if [ "$OS" = Darwin ]; then
        xattr -d com.apple.quarantine "$2" 2>/dev/null || true
        codesign -fs - "$2"
    fi
    chmod +x "$2"
    mv "$2" "${DEST}/$1"
    own_file "${DEST}/$1"
    printf '%s\n' "$3" > "${STATE}/$1"
    own_file "${STATE}/$1"
    _dl_ok "Installed ${DEST}/$1"
}

install_direct() {
    id=$(asset_id "$2")
    if [ -z "$id" ]; then
        unchecked "$1" "$2 is unreachable"
        return
    fi
    if is_current "$1" "$id"; then
        _dl_current "$1 is current"
        return
    fi
    _dl_fetch "Downloading $1 ..."
    tmpbin=$(mktemp "${DEST}/.$1.XXXXXX")
    if ! curl -fsSL -o "$tmpbin" "$2"; then
        rm -f "$tmpbin"
        tmpbin=
        skip "$1" "download failed"
        return
    fi
    install_binary "$1" "$tmpbin" "$id"
    tmpbin=
}

install_jaq() {
    case "${OS}:${ARCH}" in
        Linux:x86_64) jaq_target=x86_64-unknown-linux-musl ;;
        Linux:aarch64) skip jaq "no musl release for aarch64; install jq instead"; return ;;
        Linux:*) jaq_target="${ARCH}-unknown-linux-gnu" ;;
        *) jaq_target="${ARCH}-apple-darwin" ;;
    esac
    install_direct jaq \
        "https://github.com/01mf02/jaq/releases/latest/download/jaq-${jaq_target}"
}

jaq_runs() {
    "$1" --version >/dev/null 2>&1
}

jaq_available() {
    if command -v jaq >/dev/null 2>&1 && jaq_runs jaq; then return 0; fi
    if [ -x "${DEST}/jaq" ] && jaq_runs "${DEST}/jaq"; then return 0; fi
    command -v jq >/dev/null 2>&1 && jq --version >/dev/null 2>&1
}

run_jaq() {
    if command -v jaq >/dev/null 2>&1 && jaq_runs jaq; then
        jaq "$@"
    elif [ -x "${DEST}/jaq" ] && jaq_runs "${DEST}/jaq"; then
        "${DEST}/jaq" "$@"
    elif command -v jq >/dev/null 2>&1 && jq --version >/dev/null 2>&1; then
        jq "$@"
    else
        return 127
    fi
}

install_python3() {
    case "$OS:$ARCH" in
        Darwin:aarch64) triple=aarch64-apple-darwin ;;
        Linux:x86_64) triple=x86_64-unknown-linux-musl ;;
        Linux:aarch64) triple=aarch64-unknown-linux-musl ;;
        *) skip python3 "no python-build release for ${OS}/${ARCH}"; return ;;
    esac
    if ! jaq_available; then
        install_jaq
        if ! jaq_available; then
            unchecked python3 "jaq is required to find the python-build release"
            return
        fi
    fi
    tag=$(curl -fsSL "https://github.com/joshuarli/python-build/releases.atom" \
        | awk '
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
                if (tag ~ /^research-/) tag = ""
            }
            /<\/entry>/ {
                if (updated > newest_updated && tag != "") {
                    newest_updated = updated
                    newest_tag = tag
                }
                in_entry = 0
            }
            END { print newest_tag }
        ') || tag=
    if [ -z "$tag" ]; then
        unchecked python3 "no release found"
        return
    fi
    release_json=$(curl -fsSL "https://api.github.com/repos/joshuarli/python-build/releases/tags/${tag}") || release_json=
    asset_url=$(printf '%s\n' "$release_json" \
        | run_jaq -r --arg triple "$triple" \
            '[.assets[] | select(.name | endswith("-\($triple)-install_only_stripped.tar.gz"))][0].browser_download_url // empty' 2>/dev/null) || asset_url=
    sums_url=$(printf '%s\n' "$release_json" \
        | run_jaq -r '[.assets[] | select(.name == "SHA256SUMS")][0].browser_download_url // empty' 2>/dev/null) || sums_url=
    if [ -z "$asset_url" ] || [ -z "$sums_url" ]; then
        unchecked python3 "${tag} has no ${triple} release asset"
        return
    fi
    id=$(asset_id "$asset_url")
    if [ -z "$id" ]; then
        unchecked python3 "release asset is unreachable"
        return
    fi
    if is_current python3 "$id"; then
        _dl_current "python3 is current (${tag})"
        return
    fi
    release_dir="${PYTHON_BUILD_ROOT}/${tag}"
    if [ -e "$release_dir" ] || [ -L "$release_dir" ]; then
        skip python3 "$release_dir already exists"
        return
    fi
    _dl_fetch "Downloading python-build ${tag} (${triple}) ..."
    tmpzip=$(mktemp)
    if ! curl -fsSL -o "$tmpzip" "$asset_url"; then
        rm -f "$tmpzip"
        tmpzip=
        skip python3 "download failed"
        return
    fi
    tmpoutput=$(mktemp)
    if ! curl -fsSL -o "$tmpoutput" "$sums_url"; then
        rm -f "$tmpzip" "$tmpoutput"
        tmpzip=
        tmpoutput=
        skip python3 "SHA256SUMS download failed"
        return
    fi
    asset_name=${asset_url##*/}
    asset_name=$(printf '%s\n' "$asset_name" | sed 's/%2B/+/g; s/%2b/+/g')
    expected_sha256=$(grep -F "  ${asset_name}" "$tmpoutput" | awk '{print $1}')
    rm -f "$tmpoutput"
    tmpoutput=
    if [ "${#expected_sha256}" -ne 64 ] || [ "$(sha256_file "$tmpzip")" != "$expected_sha256" ]; then
        rm -f "$tmpzip"
        tmpzip=
        skip python3 "checksum mismatch"
        return
    fi
    if ! tar -tzf "$tmpzip" | awk '
        BEGIN { bad = 0 }
        /^\// { bad = 1 }
        {
            count = split($0, path, "/")
            for (component = 1; component <= count; component++) {
                if (path[component] == "..") bad = 1
            }
        }
        END { exit bad }
    '; then
        rm -f "$tmpzip"
        tmpzip=
        skip python3 "archive contains an invalid path"
        return
    fi
    own_missing_dirs "$PYTHON_BUILD_ROOT"
    mkdir -p "$PYTHON_BUILD_ROOT"
    tmpbundle=$(mktemp -d "${PYTHON_BUILD_ROOT}/.python3.XXXXXX")
    if ! tar -xzf "$tmpzip" -C "$tmpbundle"; then
        rm -f "$tmpzip"
        tmpzip=
        skip python3 "archive could not be extracted"
        return
    fi
    rm -f "$tmpzip"
    tmpzip=
    if [ ! -x "${tmpbundle}/python/bin/python3.15" ]; then
        skip python3 "archive is missing python/bin/python3.15"
        return
    fi
    mv "$tmpbundle" "$release_dir"
    tmpbundle=
    own_dir "$release_dir"
    tmpbinlink=$(mktemp "${DEST}/.python3.XXXXXX")
    rm -f "$tmpbinlink"
    ln -s "${release_dir}/python/bin/python3.15" "$tmpbinlink"
    mv -f "$tmpbinlink" "${DEST}/python3"
    own_file "${DEST}/python3"
    tmpbinlink=$(mktemp "${DEST}/.python3.15.XXXXXX")
    rm -f "$tmpbinlink"
    ln -s "${release_dir}/python/bin/python3.15" "$tmpbinlink"
    mv -f "$tmpbinlink" "${DEST}/python3.15"
    own_file "${DEST}/python3.15"
    printf '%s\n' "$id" > "${STATE}/python3"
    own_file "${STATE}/python3"
    _dl_ok "Installed ${DEST}/python3"
    if ! "${DEST}/python3" -c 'import sqlite3, ssl' >/dev/null 2>&1; then
        _dl_warn "Python is installed but sqlite3/ssl imports failed; install libgcc or inspect ${release_dir}"
        failed=true
    fi
}

if ! command -v curl >/dev/null 2>&1; then
    _dl_fail 'curl is required to download tools'
    exit 1
fi

for prog in "$@"; do
    case "$prog" in
        jaq) install_jaq ;;
        python3) install_python3 ;;
        *) _dl_fail "bootstrap.sh only installs jaq and python3, not $prog"; failed=true ;;
    esac
done

if $failed; then exit 1; fi
_dl_ok "Done."

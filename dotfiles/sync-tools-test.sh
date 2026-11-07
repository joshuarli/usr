#!/bin/sh
set -eu

script_dir=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
repo_root=$(CDPATH='' cd -- "$script_dir/.." && pwd)
work_root="$repo_root/.work/tmp"
mkdir -p "$work_root"
test_root=$(mktemp -d "$work_root/sync-tools.XXXXXX")
trap 'rm -rf "$test_root"' 0
trap 'exit 1' HUP INT TERM
mock_bin="$test_root/bin"
home="$test_root/home"
mkdir -p "$mock_bin" "$home" "$test_root/tmp"

# Test the private leaf tool installer with mocks first on PATH. Three macOS /bin/sh startup quirks
# make a plain VAR=value prefix unreliable here: entries prepended to PATH
# are silently dropped (bypassing mocks for npm/node), login-time
# XDG_DATA_HOME is restored (bypassing per-scenario data dirs), and
# assignments preceding a function call persist exported into later
# scenarios (CMD_TEST_VERSION, DL_RECORD_OWNED, ...). PATH and the XDG
# variables are therefore rebuilt at runtime inside the child, and the known
# test-control variables are scrubbed afterwards so every scenario starts
# clean; each scenario sets what it needs on its own run_tools call.
unset XDG_DATA_HOME XDG_STATE_HOME
run_tools() {
    _run_tools_path=$1
    _run_tools_root=$2
    shift 2
    sh -c 'PATH=$1; export PATH; XDG_DATA_HOME=$2; export XDG_DATA_HOME; XDG_STATE_HOME=$3; export XDG_STATE_HOME; DL_PROFILE=${DL_PROFILE:-desktop}; export DL_PROFILE; _dl_root=$4; shift 4; exec /bin/sh "$_dl_root/tools/sync/install.sh" "$@"' \
        run_tools "$_run_tools_path" "${XDG_DATA_HOME-}" "${XDG_STATE_HOME-}" "$_run_tools_root" "$@"
    _run_tools_status=$?
    unset CMD_TEST_VERSION CMD_TEST_NODE_VERSION CMD_INSTALL_FAIL \
        CLAUDE_INSTALL_FAIL DL_TEST_OS DL_TEST_ARCH DL_JAQ_MOCK FX_TAR FX_TEST_SHA \
        CODEX_TAR OPENCODE_TAR OPENCODE_ETAG \
        UV_TEST_BAD_SHA UV_TEST_ETAG \
        GIT_ZIP GIT_SUMS GIT_ZIP_SHA256 GIT_UNZIP_LIST_FAIL GIT_UNZIP_EXTRACT_FAIL GIT_FEED_OLD \
        SSH_ZIP SSH_SUMS SSH_UNZIP_LIST_FAIL SSH_UNZIP_EXTRACT_FAIL SSH_FEED_OLD OXISH_ZIP OXISH_SUMS OXISH_UNZIP_EXTRACT_FAIL \
        DL_RECORD_OWNED DL_OWNED_FILE NPM_LOG DL_PROFILE \
        XDG_DATA_HOME XDG_STATE_HOME CODEX_HOME \
        GHOSTTY_APPLICATIONS_DIR GHOSTTY_TEST_EXTRACT_FAIL \
        GHOSTTY_TEST_BAD_SIGNATURE GHOSTTY_TEST_VERSION \
        GHOSTTY_CUSTOM_TEST_BAD_SUMS GHOSTTY_CUSTOM_TEST_BUNDLE_ID \
        PLAYER_APPLICATIONS_DIR PLAYER_TEST_BAD_SUMS FFMPEG_ROOT
    return $_run_tools_status
}

# Shared across cases: each case runs in a subshell, so anything read by a
# later case is defined here once. Per-case homes stay local to their case.
cmd_log="$test_root/cmd-npm.log"
dsh_home="$test_root/dsh-home"
dsh_data="$dsh_home/data"
dsh_state="$dsh_home/state"
npm_log="$test_root/npm.log"

case_n=0
nfailed=0
failed_cases=""
begin_case() {
    case_n=$((case_n + 1))
    _case_label=$1
    printf 'case %d: %s\n' "$case_n" "$_case_label"
    set +e
}
end_case() {
    _case_status=$?
    set -e
    if [ "$_case_status" -ne 0 ]; then
        printf 'FAIL case %d: %s\n' "$case_n" "$_case_label" >&2
        nfailed=$((nfailed + 1))
        failed_cases="${failed_cases:+$failed_cases }$case_n"
    fi
}

cat > "$mock_bin/curl" <<'EOF'
#!/bin/sh
set -eu

url=
output=
headers=
while [ "$#" -gt 0 ]; do
    case "$1" in
        -o) output=$2; shift 2 ;;
        -D) headers=$2; shift 2 ;;
        -*) shift ;;
        *) url=$1; shift ;;
    esac
done

case "$url" in
    https://claude.ai/install.sh)
        [ -n "$output" ] || exit 1
        cat > "$output" <<'INSTALLER'
#!/bin/sh
case ":$PATH:" in *":$HOME/.local/bin:"*) ;; *) exit 8 ;; esac
printf '%s\n' 'native installer output'
if [ "${CLAUDE_INSTALLER_FAIL:-false}" = true ]; then
    printf '%s\n' 'native installer failure'
    exit 7
fi
mkdir -p "$HOME/.claude/native" "$HOME/.local/bin"
printf '%s\n' '#!/bin/sh' 'exit 0' > "$HOME/.claude/native/claude"
chmod +x "$HOME/.claude/native/claude"
ln -s "$HOME/.claude/native/claude" "$HOME/.local/bin/.claude.XXXXXX"
mv -f "$HOME/.local/bin/.claude.XXXXXX" "$HOME/.local/bin/claude"
INSTALLER
        ;;
    https://antigravity.google/cli/install.sh)
        [ -n "$output" ] || exit 1
        cat > "$output" <<'INSTALLER'
#!/bin/sh
[ "$#" -eq 2 ] && [ "$1" = --dir ] && [ -n "${2:-}" ] || exit 1
mkdir -p "$2"
cat > "$2/agy" <<'AGY'
#!/bin/sh
if [ "${1:-}" = install ]; then
    [ "$2" = --dir ] && [ -n "${3:-}" ] \
        && [ "$4" = --skip-aliases ] && [ "$5" = --skip-path ] || exit 1
    exit 0
fi
exit 0
AGY
chmod +x "$2/agy"
printf '%s\n' '# Added by Antigravity CLI installer' >> "$HOME/.bashrc"
INSTALLER
        ;;
    https://dev.meta.ai/install.sh)
        [ -n "$output" ] || exit 1
        cat > "$output" <<'INSTALLER'
#!/bin/bash
[ "${MUSE_INSTALL_DIR:-}" = "$HOME/.local/bin" ] || exit 1
[ "${MUSE_NO_MODIFY_PATH:-}" = 1 ] || exit 1
printf '%s\n' '#!/bin/sh' 'exit 0' > "$MUSE_INSTALL_DIR/muse"
chmod +x "$MUSE_INSTALL_DIR/muse"
INSTALLER
        ;;
    https://github.com/vercel-labs/fx/releases.atom)
        cat <<'FEED'
<feed>
<entry>
<updated>2026-10-30T10:00:00Z</updated>
<link rel="alternate" type="text/html" href="https://github.com/vercel-labs/fx/releases/tag/v0.0.16"/>
</entry>
</feed>
FEED
        ;;
    https://github.com/vercel-labs/fx/releases/download/v0.0.16/fx-linux-x86_64.tar.gz.sha256)
        [ -n "$output" ] || exit 1
        printf '%s  %s\n' 'f0fb822c7be546c80bcc89d50521bc1454435e0c6f586e8420c4e2b84fa80599' 'fx-linux-x86_64.tar.gz' > "$output"
        ;;
    https://github.com/vercel-labs/fx/releases/download/v0.0.16/fx-linux-x86_64.tar.gz)
        [ -n "$output" ] || exit 1
        cp "$FX_TAR" "$output"
        ;;
    https://x.ai/cli/stable)
        printf '%s\n' '1.2.3'
        ;;
    https://github.com/01mf02/jaq/releases/latest/download/jaq-*)
        if [ "$headers" = - ]; then
            printf '%s\n' 'ETag: jaq-test-etag'
        elif [ -n "$output" ]; then
            cp "$DL_JAQ_MOCK" "$output"
        else
            exit 1
        fi
        ;;
    https://releases.openai.com/codex/channels/latest)
        printf '%s\n' '{}'
        ;;
    https://releases.openai.com/codex/releases/codex-test.tar.gz)
        if [ "$headers" = - ]; then
            printf '%s\n' 'ETag: codex-test-etag'
        elif [ -n "$output" ]; then
            cp "$CODEX_TAR" "$output"
        else
            exit 1
        fi
        ;;
    https://x.ai/cli/grok-1.2.3-linux-x86_64)
        if [ "$headers" = - ]; then
            printf '%s\n' 'ETag: grok-test-etag'
        elif [ -n "$output" ]; then
            printf '%s\n' 'grok-test-binary' > "$output"
        else
            exit 1
        fi
        ;;
    https://opencode.ai/update/api/latest/cli/opencode/opencode-linux-x64.tar.gz)
        if [ "$headers" = - ]; then
            printf '%s\n' "ETag: ${OPENCODE_ETAG:-opencode-test-etag}"
        elif [ -n "$output" ]; then
            cp "$OPENCODE_TAR" "$output"
        else
            exit 1
        fi
        ;;
    https://api.meta.ai/muse-code/channels/muse-stable)
        printf '%s\n' '{"version":"1.4.9-R6297.1","manifest_url":"https://lookaside.facebook.com/lookaside/muse/download/?channel=muse&version=1.4.9-R6297.1&file=manifest.json"}'
        ;;
    'https://lookaside.facebook.com/lookaside/muse/download/?channel=muse&version=1.4.9-R6297.1&file=manifest.json')
        printf '%s\n' '{"version":"1.4.9-R6297.1","artifacts":{"x86_linux":{"checksum":"23036067f74d814ea3059686c1f0596ffe619e29fd38a8caa71c3c446a1eeba9","url":"https://lookaside.facebook.com/lookaside/muse/download/?channel=muse&version=1.4.9-R6297.1&file=x86_linux"},"aarch64_linux":{"checksum":"23036067f74d814ea3059686c1f0596ffe619e29fd38a8caa71c3c446a1eeba9","url":"https://lookaside.facebook.com/lookaside/muse/download/?channel=muse&version=1.4.9-R6297.1&file=aarch64_linux"},"x86_macos":{"checksum":"23036067f74d814ea3059686c1f0596ffe619e29fd38a8caa71c3c446a1eeba9","url":"https://lookaside.facebook.com/lookaside/muse/download/?channel=muse&version=1.4.9-R6297.1&file=x86_macos"},"aarch64_macos":{"checksum":"23036067f74d814ea3059686c1f0596ffe619e29fd38a8caa71c3c446a1eeba9","url":"https://lookaside.facebook.com/lookaside/muse/download/?channel=muse&version=1.4.9-R6297.1&file=aarch64_macos"}}}'
        ;;
    https://lookaside.facebook.com/lookaside/muse/download/*)
        if [ "$headers" = - ]; then
            printf '%s\n' 'ETag: muse-test-etag'
        elif [ -n "$output" ]; then
            printf '%s' 'muse-test-binary' > "$output"
        else
            exit 1
        fi
        ;;
    https://github.com/joshuarli/gh/releases.atom)
        cat <<'FEED'
<feed>
<entry>
<updated>2026-10-18T17:51:43Z</updated>
<link rel="alternate" type="text/html" href="https://github.com/joshuarli/gh/releases/tag/release-cce000de204a5ded499612a3fd2b8b3261fde078"/>
</entry>
<entry>
<updated>2026-10-19T21:56:41Z</updated>
<link rel="alternate" type="text/html" href="https://github.com/joshuarli/gh/releases/tag/release-9be88d806c91cbce8920e188f90fb6df34b45ba9"/>
</entry>
</feed>
FEED
        ;;
    https://github.com/joshuarli/gh/releases/download/release-9be88d806c91cbce8920e188f90fb6df34b45ba9/gh-aarch64-apple-darwin.zip)
        [ "$headers" = - ] || exit 1
        printf '%s\n' 'ETag: gh-test-etag'
        ;;
    https://github.com/joshuarli/syncthing/releases.atom)
        cat <<'FEED'
<feed>
<entry>
<updated>2026-10-24T10:00:00Z</updated>
<link rel="alternate" type="text/html" href="https://github.com/joshuarli/syncthing/releases/tag/release-aaa000aaa000aaa000aaa000aaa000aaa000aaa0001"/>
</entry>
<entry>
<updated>2026-10-25T10:00:00Z</updated>
<link rel="alternate" type="text/html" href="https://github.com/joshuarli/syncthing/releases/tag/release-bbb000bbb000bbb000bbb000bbb000bbb000bbb0002"/>
</entry>
</feed>
FEED
        ;;
    https://github.com/joshuarli/syncthing/releases/download/release-bbb000bbb000bbb000bbb000bbb000bbb000bbb0002/syncthing-aarch64-apple-darwin.zip)
        if [ "$headers" = - ]; then
            printf '%s\n' 'ETag: syncthing-test-etag'
        elif [ -n "$output" ]; then
            printf '%s' 'syncthing-test-zip' > "$output"
        else
            exit 1
        fi
        ;;
    https://github.com/joshuarli/soulseek-rs/releases.atom)
        cat <<'FEED'
<feed>
<entry>
<updated>2026-11-03T10:00:00Z</updated>
<link rel="alternate" type="text/html" href="https://github.com/joshuarli/soulseek-rs/releases/tag/release-sss000sss000sss000sss000sss000sss000sss0001"/>
</entry>
</feed>
FEED
        ;;
    https://github.com/joshuarli/soulseek-rs/releases/download/release-sss000sss000sss000sss000sss000sss000sss0001/soulseek-rs-aarch64-apple-darwin.zip)
        if [ "$headers" = - ]; then
            printf '%s\n' 'ETag: soulseek-rs-test-etag'
        elif [ -n "$output" ]; then
            printf '%s' 'soulseek-rs-test-zip' > "$output"
        else
            exit 1
        fi
        ;;
    https://github.com/joshuarli/soulseek-rs/releases/download/release-sss000sss000sss000sss000sss000sss000sss0001/soulseek-rs-x86_64-unknown-linux-musl-static.zip)
        if [ "$headers" = - ]; then
            printf '%s\n' 'ETag: soulseek-rs-static-test-etag'
        elif [ -n "$output" ]; then
            printf '%s' 'soulseek-rs-static-test-zip' > "$output"
        else
            exit 1
        fi
        ;;
    https://github.com/laputa-systems/fz/releases.atom)
        cat <<'FEED'
<feed>
<entry>
<updated>2026-10-30T10:00:00Z</updated>
<link rel="alternate" type="text/html" href="https://github.com/laputa-systems/fz/releases/tag/release-cccccccccccccccccccccccccccccccccccccccc"/>
</entry>
</feed>
FEED
        ;;
    https://github.com/laputa-systems/fz/releases/download/release-cccccccccccccccccccccccccccccccccccccccc/fz-x86_64-unknown-linux-musl-static.zip)
        if [ "$headers" = - ]; then
            printf '%s\n' 'ETag: fz-static-test-etag'
        elif [ -n "$output" ]; then
            printf '%s' 'fz-static-test-binary' > "$output"
        else
            exit 1
        fi
        ;;
    https://github.com/joshuarli/shck/releases.atom)
        cat <<'FEED'
<feed>
<entry>
<updated>2026-11-05T10:00:00Z</updated>
<link rel="alternate" type="text/html" href="https://github.com/joshuarli/shck/releases/tag/release-shuck-test-1"/>
</entry>
</feed>
FEED
        ;;
    https://github.com/joshuarli/shck/releases/download/release-shuck-test-1/shuck-aarch64-apple-darwin.zip)
        if [ "$headers" = - ]; then
            printf '%s\n' 'ETag: shuck-test-etag'
        elif [ -n "$output" ]; then
            printf '%s' 'shuck-test-zip' > "$output"
        else
            exit 1
        fi
        ;;
    https://github.com/joshuarli/shck/releases/download/release-shuck-test-1/shuck-x86_64-unknown-linux-musl-static.zip)
        if [ "$headers" = - ]; then
            printf '%s\n' 'ETag: shuck-static-test-etag'
        elif [ -n "$output" ]; then
            printf '%s' 'shuck-static-test-zip' > "$output"
        else
            exit 1
        fi
        ;;
    https://github.com/laputa-systems/zzz/releases.atom)
        cat <<'FEED'
<feed>
<entry>
<updated>2026-10-25T22:22:20Z</updated>
<link rel="alternate" type="text/html" href="https://github.com/laputa-systems/zzz/releases/tag/release-37544a545a89ce94721cba6a953fb18f26123ab3"/>
</entry>
</feed>
FEED
        ;;
    https://github.com/laputa-systems/zzz/releases/download/release-37544a545a89ce94721cba6a953fb18f26123ab3/zzz-linux-musl-static-*)
        if [ "$headers" = - ]; then
            printf '%s\n' 'ETag: zzz-test-etag'
        elif [ -n "$output" ]; then
            cp "$ZZZ_BIN" "$output"
        else
            exit 1
        fi
        ;;
    https://github.com/astral-sh/uv/releases.atom)
        cat <<'FEED'
<feed>
<entry>
<updated>2026-11-02T18:26:00Z</updated>
<link rel="alternate" type="text/html" href="https://github.com/astral-sh/uv/releases/tag/0.13.7"/>
</entry>
</feed>
FEED
        ;;
    https://github.com/astral-sh/uv/releases/download/0.13.7/uv-x86_64-unknown-linux-musl.tar.gz)
        if [ "$headers" = - ]; then
            printf '%s\n' "ETag: ${UV_TEST_ETAG:-uv-test-etag}"
        elif [ -n "$output" ]; then
            cp "$UV_TAR" "$output"
        else
            exit 1
        fi
        ;;
    https://github.com/astral-sh/uv/releases/download/0.13.7/uv-x86_64-unknown-linux-musl.tar.gz.sha256)
        [ -n "$output" ] || exit 1
        if [ "${UV_TEST_BAD_SHA:-false}" = true ]; then
            printf '%s  %s\n' '0000000000000000000000000000000000000000000000000000000000000000' 'uv-x86_64-unknown-linux-musl.tar.gz' > "$output"
        else
            printf '%s  %s\n' "$UV_TAR_SHA256" 'uv-x86_64-unknown-linux-musl.tar.gz' > "$output"
        fi
        ;;
    https://github.com/joshuarli/ghostty/releases.atom)
        cat <<'FEED'
<feed>
<entry>
<updated>2026-10-29T10:00:00Z</updated>
<link rel="alternate" type="text/html" href="https://github.com/joshuarli/ghostty/releases/tag/v1.4.1-custom.1"/>
</entry>
<entry>
<updated>2026-10-30T10:00:00Z</updated>
<link rel="alternate" type="text/html" href="https://github.com/joshuarli/ghostty/releases/tag/release-aaa000aaa000aaa000aaa000aaa000aaa000aaa0001"/>
</entry>
<entry>
<updated>2026-10-30T11:00:00Z</updated>
<link rel="alternate" type="text/html" href="https://github.com/joshuarli/ghostty/releases/tag/release-bbb000bbb000bbb000bbb000bbb000bbb000bbb0002"/>
</entry>
</feed>
FEED
        ;;
    https://github.com/joshuarli/ghostty/releases/download/release-bbb000bbb000bbb000bbb000bbb000bbb000bbb0002/Ghostty-Custom-aarch64-apple-darwin.dmg)
        if [ "$headers" = - ]; then
            printf '%s\n' 'ETag: ghostty-custom-test-etag'
        elif [ -n "$output" ]; then
            printf '%s\n' 'ghostty-custom-test-zip' > "$output"
        else
            exit 1
        fi
        ;;
    https://github.com/joshuarli/ghostty/releases/download/release-bbb000bbb000bbb000bbb000bbb000bbb000bbb0002/SHA256SUMS)
        [ -n "$output" ] || exit 1
        if [ "${GHOSTTY_CUSTOM_TEST_BAD_SUMS:-false}" = true ]; then
            printf '%s\n' '0000000000000000000000000000000000000000000000000000000000000000  Ghostty-Custom-aarch64-apple-darwin.dmg' > "$output"
        else
            printf '%s\n' '8da6066dfe57453cb8e98d9e5fa376252d60aa001e0b71ec33af5828c463ce21  Ghostty-Custom-aarch64-apple-darwin.dmg' > "$output"
        fi
        ;;
    https://github.com/joshuarli/play/releases.atom)
        cat <<'FEED'
<feed>
<entry>
<updated>2026-11-01T10:00:00Z</updated>
<link rel="alternate" type="text/html" href="https://github.com/joshuarli/play/releases/tag/v0.41.0"/>
</entry>
</feed>
FEED
        ;;
    https://github.com/joshuarli/play/releases/download/v0.41.0/SHA256SUMS)
        [ -n "$output" ] || exit 1
        if [ "${PLAYER_TEST_BAD_SUMS:-false}" = true ]; then
            printf '%s  %s\n' '0000000000000000000000000000000000000000000000000000000000000000' Player-aarch64-apple-darwin.zip > "$output"
            printf '%s  %s\n' '0000000000000000000000000000000000000000000000000000000000000000' player-x86_64-linux-musl.tar.gz >> "$output"
        else
            printf '%s  %s\n' "$PLAYER_ZIP_SHA256" Player-aarch64-apple-darwin.zip > "$output"
            printf '%s  %s\n' "$PLAYER_TAR_SHA256" player-x86_64-linux-musl.tar.gz >> "$output"
        fi
        ;;
    https://github.com/joshuarli/play/releases/download/v0.41.0/Player-aarch64-apple-darwin.zip)
        if [ "$headers" = - ]; then
            printf '%s\n' 'ETag: player-test-etag'
        elif [ -n "$output" ]; then
            printf '%s' 'player-test-zip' > "$output"
        else
            exit 1
        fi
        ;;
    https://github.com/joshuarli/play/releases/download/v0.41.0/player-x86_64-linux-musl.tar.gz)
        if [ "$headers" = - ]; then
            printf '%s\n' 'ETag: player-test-etag'
        elif [ -n "$output" ]; then
            cp "$PLAYER_TAR" "$output"
        else
            exit 1
        fi
        ;;
    https://github.com/laputa-systems/git-build/releases.atom)
        if [ "${GIT_FEED_OLD:-false}" = true ]; then
            cat <<'FEED'
<feed>
<entry>
<updated>2026-10-26T10:00:00Z</updated>
<link rel="alternate" type="text/html" href="https://github.com/laputa-systems/git-build/releases/tag/release-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"/>
</entry>
</feed>
FEED
        else
            cat <<'FEED'
<feed>
<entry>
<updated>2026-10-26T10:00:00Z</updated>
<link rel="alternate" type="text/html" href="https://github.com/laputa-systems/git-build/releases/tag/release-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"/>
</entry>
<entry>
<updated>2026-10-27T10:00:00Z</updated>
<link rel="alternate" type="text/html" href="https://github.com/laputa-systems/git-build/releases/tag/release-bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"/>
</entry>
</feed>
FEED
        fi
        ;;
    https://github.com/laputa-systems/git-build/releases/download/release-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/git-x86_64-unknown-linux-musl.zip)
        if [ "$headers" = - ]; then
            printf '%s\n' 'ETag: git-test-etag-a'
        elif [ -n "$output" ]; then
            cp "$GIT_ZIP" "$output"
        else
            exit 1
        fi
        ;;
    https://github.com/laputa-systems/git-build/releases/download/release-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/SHA256SUMS)
        [ -n "$output" ] || exit 1
        cp "$GIT_SUMS" "$output"
        ;;
    https://github.com/laputa-systems/git-build/releases/download/release-bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb/git-x86_64-unknown-linux-musl.zip)
        if [ "$headers" = - ]; then
            printf '%s\n' 'ETag: git-test-etag'
        elif [ -n "$output" ]; then
            cp "$GIT_ZIP" "$output"
        else
            exit 1
        fi
        ;;
    https://github.com/laputa-systems/git-build/releases/download/release-bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb/SHA256SUMS)
        [ -n "$output" ] || exit 1
        cp "$GIT_SUMS" "$output"
        ;;
    https://github.com/laputa-systems/ssh-build/releases.atom)
        if [ "${SSH_FEED_OLD:-false}" = true ]; then
            cat <<'FEED'
<feed>
<entry>
<updated>2026-10-26T10:00:00Z</updated>
<link rel="alternate" type="text/html" href="https://github.com/laputa-systems/ssh-build/releases/tag/release-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"/>
</entry>
</feed>
FEED
        else
            cat <<'FEED'
<feed>
<entry>
<updated>2026-10-26T10:00:00Z</updated>
<link rel="alternate" type="text/html" href="https://github.com/laputa-systems/ssh-build/releases/tag/release-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"/>
</entry>
<entry>
<updated>2026-10-27T10:00:00Z</updated>
<link rel="alternate" type="text/html" href="https://github.com/laputa-systems/ssh-build/releases/tag/release-bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"/>
</entry>
</feed>
FEED
        fi
        ;;
    https://github.com/laputa-systems/ssh-build/releases/download/release-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/ssh-x86_64-unknown-linux-musl.zip)
        if [ "$headers" = - ]; then
            printf '%s\n' 'ETag: ssh-test-etag-a'
        elif [ -n "$output" ]; then
            cp "$SSH_ZIP" "$output"
        else
            exit 1
        fi
        ;;
    https://github.com/laputa-systems/ssh-build/releases/download/release-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/SHA256SUMS)
        [ -n "$output" ] || exit 1
        cp "${OXISH_SUMS:-$SSH_SUMS}" "$output"
        ;;
    https://github.com/laputa-systems/ssh-build/releases/download/release-bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb/ssh-x86_64-unknown-linux-musl.zip)
        if [ "$headers" = - ]; then
            printf '%s\n' 'ETag: ssh-test-etag'
        elif [ -n "$output" ]; then
            cp "$SSH_ZIP" "$output"
        else
            exit 1
        fi
        ;;
    https://github.com/laputa-systems/ssh-build/releases/download/release-bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb/SHA256SUMS)
        [ -n "$output" ] || exit 1
        cp "${OXISH_SUMS:-$SSH_SUMS}" "$output"
        ;;
    https://github.com/laputa-systems/ssh-build/releases/download/release-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/oxish-x86_64-unknown-linux-musl.zip)
        if [ "$headers" = - ]; then
            printf '%s\n' 'ETag: oxish-test-etag-a'
        elif [ -n "$output" ]; then
            cp "$OXISH_ZIP" "$output"
        else
            exit 1
        fi
        ;;
    https://github.com/laputa-systems/ssh-build/releases/download/release-bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb/oxish-x86_64-unknown-linux-musl.zip)
        if [ "$headers" = - ]; then
            printf '%s\n' 'ETag: oxish-test-etag'
        elif [ -n "$output" ]; then
            cp "$OXISH_ZIP" "$output"
        else
            exit 1
        fi
        ;;
    https://github.com/laputa-systems/ffmpeg-build/releases.atom)
        [ -f "$FFMPEG_ROOT/feed.atom" ] || exit 22
        cat "$FFMPEG_ROOT/feed.atom"
        ;;
    https://github.com/laputa-systems/ffmpeg-build/releases/download/*)
        ffmpeg_path=${url#https://github.com/laputa-systems/ffmpeg-build/releases/download/}
        case "$ffmpeg_path" in *+*) exit 22 ;; esac
        ffmpeg_path=$(printf '%s' "$ffmpeg_path" | sed 's/%2B/+/g')
        ffmpeg_file="$FFMPEG_ROOT/$ffmpeg_path"
        [ -f "$ffmpeg_file" ] || exit 22
        if [ "$headers" = - ]; then
            printf 'ETag: ffmpeg-etag-%s\n' "$(cksum < "$ffmpeg_file" | awk '{print $1}')"
        elif [ -n "$output" ]; then
            cp "$ffmpeg_file" "$output"
        else
            exit 1
        fi
        ;;
    *) exit 1 ;;
esac
EOF
chmod +x "$mock_bin/curl"

cat > "$mock_bin/jaq" <<'EOF'
#!/bin/sh
if [ "${1:-}" = --version ]; then
    printf '%s\n' 'jaq 2.0.0'
    exit 0
fi
for query do :; done
case "$query" in
    '.tag_name // empty') printf '%s\n' 'rust-v1.2.3' ;;
    *'select(.name == $asset)'*) printf '%s\n' '{"browser_download_url":"https://releases.openai.com/codex/releases/codex-test.tar.gz","digest":"sha256:'"$CODEX_SHA256"'"}' ;;
    '.browser_download_url // empty') printf '%s\n' 'https://releases.openai.com/codex/releases/codex-test.tar.gz' ;;
    '.digest // empty') printf '%s\n' "sha256:$CODEX_SHA256" ;;
    '.version // empty') printf '%s\n' '1.4.9-R6297.1' ;;
    '.manifest_url // empty') printf '%s\n' 'https://lookaside.facebook.com/lookaside/muse/download/?channel=muse&version=1.4.9-R6297.1&file=manifest.json' ;;
    *'.platforms['*) printf '%s\n' 'c4156c243860ddee43e9c200f5b3d672b447d928df5273a3c954bb15b0f8dcad' ;;
    *'.artifacts['*'.checksum'*) printf '%s\n' '23036067f74d814ea3059686c1f0596ffe619e29fd38a8caa71c3c446a1eeba9' ;;
    *'.artifacts['*'.url'*) printf '%s\n' 'https://lookaside.facebook.com/lookaside/muse/download/?channel=muse&version=1.4.9-R6297.1&file=x86_linux' ;;
    *) exit 1 ;;
esac
EOF
chmod +x "$mock_bin/jaq"
printf '%s\n' '#!/bin/sh' 'exit 1' > "$mock_bin/jq"
chmod +x "$mock_bin/jq"
printf '%s\n' '#!/bin/sh' 'exit 0' > "$mock_bin/codesign"
printf '%s\n' '#!/bin/sh' 'exit 0' > "$mock_bin/xattr"
chmod +x "$mock_bin/codesign" "$mock_bin/xattr"
cat > "$mock_bin/unzip" <<'EOF'
#!/bin/sh
set -eu
mode=
zipfile=
inner=
dest=
while [ "$#" -gt 0 ]; do
    case "$1" in
        -p) mode=print; shift ;;
        -q) shift ;;
        -d) dest=$2; shift 2 ;;
        -*) shift ;;
        *) if [ -z "$zipfile" ]; then zipfile=$1; else inner=$1; fi; shift ;;
    esac
done
case "$mode" in
    print)
        case "$inner" in
            syncthing-aarch64-apple-darwin) printf '%s' 'syncthing-test-binary' ;;
            fz-x86_64-unknown-linux-musl-static) printf '%s' 'fz-static-test-binary' ;;
            soulseek-rs-aarch64-apple-darwin) printf '%s' 'soulseek-rs-test-binary' ;;
            soulseek-rs-x86_64-unknown-linux-musl-static) printf '%s' 'soulseek-rs-static-test-binary' ;;
            shuck-aarch64-apple-darwin) printf '%s' 'shuck-test-binary' ;;
            shuck-x86_64-unknown-linux-musl-static) printf '%s' 'shuck-static-test-binary' ;;
            *) exit 1 ;;
        esac
        ;;
    *)
        [ -n "$dest" ] || exit 1
        if [ "$(cat "$zipfile")" = oxish-test-zip ]; then
            [ "${OXISH_UNZIP_EXTRACT_FAIL:-false}" != true ] || exit 1
            mkdir -p "$dest/bin"
            for oxish_command in oxish-server oxish-session; do
                printf '%s\n' '#!/bin/sh' 'exit 0' > "$dest/bin/$oxish_command"
                chmod +x "$dest/bin/$oxish_command"
            done
            exit 0
        fi
        if [ "$(cat "$zipfile")" = ssh-test-zip ]; then
            [ "${SSH_UNZIP_EXTRACT_FAIL:-false}" != true ] || exit 1
            for ssh_command in ssh ssh-keygen ssh-agent ssh-add sftp scp; do
                printf '%s\n' '#!/bin/sh' 'exit 0' > "$dest/$ssh_command"
                chmod +x "$dest/$ssh_command"
            done
            exit 0
        fi
        [ "${GIT_UNZIP_EXTRACT_FAIL:-false}" != true ] || exit 1
        for git_command in git git-shell; do
            printf '%s\n' '#!/bin/sh' 'exit 0' > "$dest/$git_command"
            chmod +x "$dest/$git_command"
        done
        for git_helper in git-upload-archive git-upload-pack git-receive-pack; do
            ln -s git "$dest/$git_helper"
        done
        ;;
esac
EOF
chmod +x "$mock_bin/unzip"
cat > "$mock_bin/zipinfo" <<'EOF'
#!/bin/sh
[ "$1" = -1 ] && [ -n "${2:-}" ] || exit 1
if [ "$(cat "$2")" = oxish-test-zip ]; then
    printf '%s\n' bin/oxish-server bin/oxish-session provenance.json
elif [ "$(cat "$2")" = ssh-test-zip ]; then
    if [ "${SSH_UNZIP_LIST_FAIL:-false}" = true ]; then
        printf '%s\n' '../evil' 'ssh'
    else
        printf '%s\n' ssh ssh-keygen ssh-agent ssh-add sftp scp
    fi
elif [ "${GIT_UNZIP_LIST_FAIL:-false}" = true ]; then
    printf '%s\n' '../evil' 'git'
else
    printf '%s\n' git git-shell git-upload-archive git-upload-pack git-receive-pack
fi
EOF
chmod +x "$mock_bin/zipinfo"

cat > "$mock_bin/ditto" <<'EOF'
#!/bin/sh
set -eu
[ "${GHOSTTY_TEST_EXTRACT_FAIL:-false}" != true ] || exit 1
if [ "$1" = -x ] && [ "$2" = -k ]; then
    [ -f "$3" ] || exit 1
    dest=$4
    case "$(cat "$3")" in
        player-test-zip)
            mkdir -p "$dest/Player.app/Contents/MacOS"
            printf '%s\n' '#!/bin/sh' 'exit 0' > "$dest/Player.app/Contents/MacOS/player"
            chmod +x "$dest/Player.app/Contents/MacOS/player"
            printf '%s\n' 'mock plist' > "$dest/Player.app/Contents/Info.plist"
            exit 0
            ;;
    esac
    mkdir -p "$dest/Ghostty.app/Contents/MacOS"
    printf '%s\n' '#!/bin/sh' 'exit 0' > "$dest/Ghostty.app/Contents/MacOS/ghostty"
    chmod +x "$dest/Ghostty.app/Contents/MacOS/ghostty"
    printf '%s\n' 'mock plist' > "$dest/Ghostty.app/Contents/Info.plist"
    mkdir -p "$dest/Ghostty Custom.app/Contents/MacOS"
    printf '%s\n' '#!/bin/sh' 'exit 0' > "$dest/Ghostty Custom.app/Contents/MacOS/ghostty"
    chmod +x "$dest/Ghostty Custom.app/Contents/MacOS/ghostty"
    printf '%s\n' 'mock plist' > "$dest/Ghostty Custom.app/Contents/Info.plist"
else
    case "$1" in *"/Ghostty Custom.app") ;; *) exit 1 ;; esac
    [ -d "$1" ] || exit 1
    dest=$2
    mkdir -p "$dest/Contents/MacOS"
    printf '%s\n' '#!/bin/sh' 'exit 0' > "$dest/Contents/MacOS/ghostty"
    chmod +x "$dest/Contents/MacOS/ghostty"
    printf '%s\n' 'mock plist' > "$dest/Contents/Info.plist"
fi
EOF
cat > "$mock_bin/hdiutil" <<'EOF'
#!/bin/sh
set -eu
case "${1:-}" in
    attach)
        mnt=
        dmg=
        expect_mnt=false
        for arg in "$@"; do
            if [ "$expect_mnt" = true ]; then
                mnt=$arg
                expect_mnt=false
            elif [ "$arg" = -mountpoint ]; then
                expect_mnt=true
            elif [ "$arg" != attach ] && [ "${arg#-}" = "$arg" ]; then
                dmg=$arg
            fi
        done
        [ -n "$mnt" ] && [ -f "$dmg" ] || exit 1
        [ "${GHOSTTY_TEST_EXTRACT_FAIL:-false}" != true ] || exit 1
        mkdir -p "$mnt/Ghostty Custom.app/Contents/MacOS"
        printf '%s\n' '#!/bin/sh' 'exit 0' > "$mnt/Ghostty Custom.app/Contents/MacOS/ghostty"
        chmod +x "$mnt/Ghostty Custom.app/Contents/MacOS/ghostty"
        printf '%s\n' 'mock plist' > "$mnt/Ghostty Custom.app/Contents/Info.plist"
        ;;
    detach)
        [ -d "${2:-}" ] || exit 1
        [ "${GHOSTTY_TEST_EXTRACT_FAIL:-false}" != true ] || exit 1
        ;;
    *) exit 1 ;;
esac
EOF
cat > "$mock_bin/spctl" <<'EOF'
#!/bin/sh
[ "${GHOSTTY_TEST_BAD_SIGNATURE:-false}" != true ]
EOF
cat > "$mock_bin/plutil" <<'EOF'
#!/bin/sh
case "$*" in
    *CFBundleIdentifier*) printf '%s\n' "${GHOSTTY_CUSTOM_TEST_BUNDLE_ID:-com.joshuarli.ghostty-custom}" ;;
    *) printf '%s\n' "${GHOSTTY_TEST_VERSION:-1.4.0}" ;;
esac
EOF
chmod +x "$mock_bin/ditto" "$mock_bin/hdiutil" "$mock_bin/spctl" "$mock_bin/plutil"

mkdir -p "$test_root/opencode-package"
cat > "$test_root/opencode-package/opencode" <<'EOF'
#!/bin/sh
[ "$1" = --version ] && printf '%s\n' 'opencode 2.0.1'
EOF
chmod +x "$test_root/opencode-package/opencode"
tar -czf "$test_root/opencode.tar.gz" -C "$test_root/opencode-package" opencode
mkdir -p "$test_root/opencode-package-v2"
cat > "$test_root/opencode-package-v2/opencode" <<'EOF'
#!/bin/sh
[ "$1" = --version ] && printf '%s\n' 'opencode 2.0.2'
EOF
chmod +x "$test_root/opencode-package-v2/opencode"
tar -czf "$test_root/opencode-v2.tar.gz" -C "$test_root/opencode-package-v2" opencode

mkdir -p "$test_root/fx-package" "$test_root/fx-sha-bin"
cat > "$test_root/fx-package/fx" <<'EOF'
#!/bin/sh
[ "${1:-}" = --version ] && printf '%s\n' 'fx-test 0.0.16'
EOF
chmod +x "$test_root/fx-package/fx"
tar -czf "$test_root/fx.tar.gz" -C "$test_root/fx-package" fx
cat > "$test_root/fx-sha-bin/sha256sum" <<'EOF'
#!/bin/sh
case "${FX_TEST_SHA:-}" in
    valid) printf '%s  %s\n' 'f0fb822c7be546c80bcc89d50521bc1454435e0c6f586e8420c4e2b84fa80599' "$1" ;;
    bad) printf '%s  %s\n' '0000000000000000000000000000000000000000000000000000000000000000' "$1" ;;
    *) exit 1 ;;
esac
EOF
chmod +x "$test_root/fx-sha-bin/sha256sum"

mkdir -p "$test_root/codex-package/bin" "$test_root/codex-package/codex-path"
printf '%s\n' '{}' > "$test_root/codex-package/codex-package.json"
for codex_command in codex codex-code-mode-host; do
    printf '%s\n' '#!/bin/sh' 'exit 0' > "$test_root/codex-package/bin/$codex_command"
    chmod +x "$test_root/codex-package/bin/$codex_command"
done
printf '%s\n' '#!/bin/sh' 'exit 0' > "$test_root/codex-package/codex-path/rg"
chmod +x "$test_root/codex-package/codex-path/rg"
tar -czf "$test_root/codex.tar.gz" -C "$test_root/codex-package" .

if command -v sha256sum >/dev/null 2>&1; then
    CODEX_SHA256=$(sha256sum "$test_root/codex.tar.gz" | awk '{print $1}')
else
    CODEX_SHA256=$(shasum -a 256 "$test_root/codex.tar.gz" | awk '{print $1}')
fi

printf '%s' 'player-test-zip' > "$test_root/player.zip"
if command -v sha256sum >/dev/null 2>&1; then
    PLAYER_ZIP_SHA256=$(sha256sum "$test_root/player.zip" | awk '{print $1}')
else
    PLAYER_ZIP_SHA256=$(shasum -a 256 "$test_root/player.zip" | awk '{print $1}')
fi
mkdir -p "$test_root/player-package"
printf '%s\n' '#!/bin/sh' 'printf player-test' > "$test_root/player-package/player"
chmod +x "$test_root/player-package/player"
tar -czf "$test_root/player.tar.gz" -C "$test_root/player-package" player
if command -v sha256sum >/dev/null 2>&1; then
    PLAYER_TAR_SHA256=$(sha256sum "$test_root/player.tar.gz" | awk '{print $1}')
else
    PLAYER_TAR_SHA256=$(shasum -a 256 "$test_root/player.tar.gz" | awk '{print $1}')
fi
PLAYER_TAR="$test_root/player.tar.gz"
export PLAYER_TAR PLAYER_ZIP_SHA256 PLAYER_TAR_SHA256

mkdir -p "$test_root/zzz-package"
printf '%s' 'zzz-test-binary' > "$test_root/zzz-package/zzz"
chmod +x "$test_root/zzz-package/zzz"
ZZZ_BIN="$test_root/zzz-package/zzz"
export ZZZ_BIN

git_tag=release-bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
git_triple=x86_64-unknown-linux-musl
git_asset="git-${git_triple}.zip"
printf '%s' 'git-test-zip' > "$test_root/git.zip"
if command -v sha256sum >/dev/null 2>&1; then
    GIT_ZIP_SHA256=$(sha256sum "$test_root/git.zip" | awk '{print $1}')
else
    GIT_ZIP_SHA256=$(shasum -a 256 "$test_root/git.zip" | awk '{print $1}')
fi
printf '%s  %s\n' "$GIT_ZIP_SHA256" "$git_asset" > "$test_root/git.SHA256SUMS"

ssh_tag=release-bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
ssh_old_tag=release-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
ssh_asset="ssh-${git_triple}.zip"
printf '%s' 'ssh-test-zip' > "$test_root/ssh.zip"
if command -v sha256sum >/dev/null 2>&1; then
    SSH_ZIP_SHA256=$(sha256sum "$test_root/ssh.zip" | awk '{print $1}')
else
    SSH_ZIP_SHA256=$(shasum -a 256 "$test_root/ssh.zip" | awk '{print $1}')
fi
printf '%s  %s\n' "$SSH_ZIP_SHA256" "$ssh_asset" > "$test_root/ssh.SHA256SUMS"
printf '%s  %s\n' '0000000000000000000000000000000000000000000000000000000000000000' "$ssh_asset" > "$test_root/ssh-bad.SHA256SUMS"

oxish_asset="oxish-${git_triple}.zip"
printf '%s' 'oxish-test-zip' > "$test_root/oxish.zip"
if command -v sha256sum >/dev/null 2>&1; then
    OXISH_ZIP_SHA256=$(sha256sum "$test_root/oxish.zip" | awk '{print $1}')
else
    OXISH_ZIP_SHA256=$(shasum -a 256 "$test_root/oxish.zip" | awk '{print $1}')
fi
printf '%s  %s\n' "$OXISH_ZIP_SHA256" "$oxish_asset" > "$test_root/oxish.SHA256SUMS"
printf '%s  %s\n' '0000000000000000000000000000000000000000000000000000000000000000' "$oxish_asset" > "$test_root/oxish-bad.SHA256SUMS"

test_sha256() {
    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum "$1" | awk '{print $1}'
    else
        shasum -a 256 "$1" | awk '{print $1}'
    fi
}

mkdir -p "$test_root/uv-package/uv-x86_64-unknown-linux-musl"
printf '%s' 'uv-test-0.13.7' > "$test_root/uv-package/uv-x86_64-unknown-linux-musl/uv"
printf '%s' 'uvx-test-0.13.7' > "$test_root/uv-package/uv-x86_64-unknown-linux-musl/uvx"
chmod +x "$test_root/uv-package/uv-x86_64-unknown-linux-musl/uv" \
    "$test_root/uv-package/uv-x86_64-unknown-linux-musl/uvx"
tar -czf "$test_root/uv.tar.gz" -C "$test_root/uv-package" uv-x86_64-unknown-linux-musl
UV_TAR="$test_root/uv.tar.gz"
UV_TAR_SHA256=$(test_sha256 "$UV_TAR")
export UV_TAR UV_TAR_SHA256

ff_triples="aarch64-apple-darwin x86_64-unknown-linux-musl aarch64-unknown-linux-musl"
ff_zero_sha=0000000000000000000000000000000000000000000000000000000000000000

ff_write_sums() {
    : > "$1/SHA256SUMS"
    for _ff_archive in "$1"/ffmpeg-*.tar.gz; do
        printf '%s  %s\n' "$(test_sha256 "$_ff_archive")" "${_ff_archive##*/}" >> "$1/SHA256SUMS"
    done
    printf '%s  release.json\n' "$ff_zero_sha" >> "$1/SHA256SUMS"
}

ff_write_release() {
    _ff_root=$1
    _ff_tag=$2
    _ff_probe_exit=${3:-0}
    _ff_top=${4:-}
    _ff_extra=${5:-}
    mkdir -p "$_ff_root/$_ff_tag"
    for _ff_triple in $ff_triples; do
        _ff_name="ffmpeg-9.0.2+${_ff_tag}-${_ff_triple}-tools"
        _ff_dir=${_ff_top:-$_ff_name}
        _ff_stage="$test_root/ff-stage/$_ff_root/$_ff_tag"
        rm -rf "${_ff_stage:?}"
        mkdir -p "$_ff_stage/$_ff_dir/bin" "$_ff_stage/$_ff_dir/share/ffmpeg-build"
        printf '%s\n' '#!/bin/sh' "printf 'ffmpeg ${_ff_tag} ${_ff_triple}\\n'" > "$_ff_stage/$_ff_dir/bin/ffmpeg"
        printf '%s\n' '#!/bin/sh' "printf 'ffprobe ${_ff_tag} ${_ff_triple}\\n'" "exit ${_ff_probe_exit}" > "$_ff_stage/$_ff_dir/bin/ffprobe"
        chmod +x "$_ff_stage/$_ff_dir/bin/ffmpeg" "$_ff_stage/$_ff_dir/bin/ffprobe"
        printf '{}\n' > "$_ff_stage/$_ff_dir/share/ffmpeg-build/manifest.json"
        case "$_ff_extra" in
            symlink) ln -s ffmpeg "$_ff_stage/$_ff_dir/bin/extra" ;;
            hardlink) ln "$_ff_stage/$_ff_dir/bin/ffmpeg" "$_ff_stage/$_ff_dir/bin/extra" ;;
        esac
        tar -czf "$_ff_root/$_ff_tag/$_ff_name.tar.gz" -C "$_ff_stage" "$_ff_dir"
    done
    ff_write_sums "$_ff_root/$_ff_tag"
}

ff_write_feed() {
    _ff_feed=$1
    shift
    {
        printf '<feed>\n'
        for _ff_entry in "$@"; do
            printf '<entry>\n<updated>2026-11-04T10:00:00Z</updated>\n'
            printf '<link rel="alternate" type="text/html" href="https://github.com/laputa-systems/ffmpeg-build/releases/tag/%s"/>\n</entry>\n' "$_ff_entry"
        done
        printf '</feed>\n'
    } > "$_ff_feed/feed.atom"
}

ff_tag_old=20261103
ff_tag=20261104-r10
ff_root_a="$test_root/ff-root-a"
ff_write_release "$ff_root_a" "$ff_tag_old"
ff_write_feed "$ff_root_a" "$ff_tag_old"

ff_root_b="$test_root/ff-root-b"
ff_write_release "$ff_root_b" "$ff_tag_old"
ff_write_release "$ff_root_b" "$ff_tag"
ff_write_feed "$ff_root_b" "$ff_tag_old" 20261105-rc1 20261104-r2 "$ff_tag" 20261104

ff_root_bad="$test_root/ff-root-bad"
cp -R "$ff_root_b" "$ff_root_bad"
sed "s/^[0-9a-f]\{64\}/$ff_zero_sha/" "$ff_root_b/$ff_tag/SHA256SUMS" > "$ff_root_bad/$ff_tag/SHA256SUMS"

ff_root_garbage="$test_root/ff-root-garbage"
cp -R "$ff_root_b" "$ff_root_garbage"
for _ff_archive in "$ff_root_garbage/$ff_tag"/ffmpeg-*.tar.gz; do
    printf 'not an archive\n' > "$_ff_archive"
done
ff_write_sums "$ff_root_garbage/$ff_tag"

ff_root_smoke="$test_root/ff-root-smoke"
cp -R "$ff_root_a" "$ff_root_smoke"
ff_write_release "$ff_root_smoke" "$ff_tag" 1
ff_write_feed "$ff_root_smoke" "$ff_tag_old" "$ff_tag"

ff_root_top="$test_root/ff-root-top"
cp -R "$ff_root_a" "$ff_root_top"
ff_write_release "$ff_root_top" "$ff_tag" 0 unexpected-top
ff_write_feed "$ff_root_top" "$ff_tag_old" "$ff_tag"

ff_root_symlink="$test_root/ff-root-symlink"
cp -R "$ff_root_a" "$ff_root_symlink"
ff_write_release "$ff_root_symlink" "$ff_tag" 0 "" symlink
ff_write_feed "$ff_root_symlink" "$ff_tag_old" "$ff_tag"

ff_root_hardlink="$test_root/ff-root-hardlink"
cp -R "$ff_root_a" "$ff_root_hardlink"
ff_write_release "$ff_root_hardlink" "$ff_tag" 0 "" hardlink
ff_write_feed "$ff_root_hardlink" "$ff_tag_old" "$ff_tag"

ff_root_unlisted="$test_root/ff-root-unlisted"
cp -R "$ff_root_b" "$ff_root_unlisted"
sed '/aarch64-apple-darwin/d' "$ff_root_b/$ff_tag/SHA256SUMS" > "$ff_root_unlisted/$ff_tag/SHA256SUMS"

ff_root_absent="$test_root/ff-root-absent"
cp -R "$ff_root_b" "$ff_root_absent"
rm -f "$ff_root_absent/$ff_tag"/ffmpeg-*.tar.gz

ff_root_nosums="$test_root/ff-root-nosums"
cp -R "$ff_root_b" "$ff_root_nosums"
rm -f "$ff_root_nosums/$ff_tag/SHA256SUMS"

cat > "$mock_bin/file" <<'EOF'
#!/bin/sh
case "$(cat "$2")" in
    *'custom launcher'*) printf '%s\n' 'POSIX shell script' ;;
    *) printf '%s\n' 'ELF 64-bit LSB pie executable' ;;
esac
EOF
chmod +x "$mock_bin/file"

cat > "$mock_bin/npm" <<'EOF'
#!/bin/sh
set -eu
case "$1" in
    view)
        case "$2" in
            @deepseek-ai/dsh@next) printf '%s\n' '0.2.1-rc.2' ;;
            @deepseek-harness-tui/dsh-tui) printf '%s\n' '0.16.0' ;;
            command-code@latest) printf '%s\n' "${CMD_TEST_VERSION:-1.87.3}" ;;
            pnpm@latest) printf '%s\n' '12.16.1' ;;
            *) exit 1 ;;
        esac
        ;;
    install)
        prefix=
        for arg do
            case "$arg" in
                --prefix) next_is_prefix=true ;;
                *)
                    if [ "${next_is_prefix:-false}" = true ]; then
                        prefix=$arg
                        next_is_prefix=false
                    fi
                    ;;
            esac
        done
        [ -n "$prefix" ] || exit 1
        case " $* " in
            *" command-code@${CMD_TEST_VERSION:-1.87.3} "*)
                if [ "${CMD_INSTALL_FAIL:-false}" = true ]; then
                    mkdir -p "$prefix/lib/node_modules/command-code"
                    exit 17
                fi
                mkdir -p "$prefix/bin" "$prefix/lib/node_modules/command-code"
                printf '%s\n' '#!/bin/sh' 'exit 0' > "$prefix/bin/cmd"
                chmod +x "$prefix/bin/cmd"
                printf '%s\n' "install $*" >> "$NPM_LOG"
                exit 0
                ;;
            *" pnpm@12.16.1 "*)
                if [ -e "$prefix/bin/pn" ] && [ ! -L "$prefix/bin/pn" ]; then
                    printf '%s\n' 'npm error EEXIST: file already exists' >&2
                    exit 1
                fi
                mkdir -p "$prefix/bin" "$prefix/lib/node_modules/pnpm"
                printf '%s\n' '#!/bin/sh' 'exit 0' > "$prefix/bin/pnpm"
                chmod +x "$prefix/bin/pnpm"
                printf '%s\n' "install $*" >> "$NPM_LOG"
                exit 0
                ;;
        esac
        mkdir -p "$prefix/bin"
        mkdir -p "$prefix/lib/node_modules/@deepseek-harness-tui/dsh-tui"
        printf '%s\n' '#!/bin/sh' 'exit 0' > "$prefix/bin/dsh"
        printf '%s\n' '#!/bin/sh' 'exit 0' > "$prefix/bin/dsh-tui"
        printf '%s\n' '- id: tool-ralph' '  disabled: true' > \
            "$prefix/lib/node_modules/@deepseek-harness-tui/dsh-tui/cordis.patch.yml"
        chmod +x "$prefix/bin/dsh" "$prefix/bin/dsh-tui"
        printf '%s\n' "install $*" >> "$NPM_LOG"
        ;;
    uninstall)
        [ "$2" = --global ] && [ "$3" = --prefix ] && [ "$5" = @deepseek-ai/dsh ] || exit 1
        rm -rf "$4/lib/node_modules/@deepseek-ai/dsh"
        rm -f "$4/bin/dsh"
        printf '%s\n' "uninstall $*" >> "$NPM_LOG"
        ;;
    *) exit 1 ;;
esac
EOF
chmod +x "$mock_bin/npm"

cat > "$mock_bin/pnpm" <<'EOF'
#!/bin/sh
exit 0
EOF
chmod +x "$mock_bin/pnpm"

cat > "$mock_bin/node" <<'EOF'
#!/bin/sh
[ "$1" = -p ] || exit 1
printf '%s\n' "${CMD_TEST_NODE_VERSION:-26.12.0}"
EOF
chmod +x "$mock_bin/node"

begin_case "cmd install, current check, upgrade, and owned-file tracking"
( set -e
cmd_home="$test_root/cmd-home"
if output=$(HOME="$cmd_home" TMPDIR="$test_root/tmp" NPM_LOG="$cmd_log" \
    run_tools "$mock_bin:$PATH" "$repo_root" cmd 2>&1); then
    :
else
    printf '%s\n' "$output" >&2
    exit 1
fi
[ "$(readlink "$cmd_home/.local/bin/cmd")" = "$cmd_home/.local/share/command-code/bin/cmd" ]
[ -x "$cmd_home/.local/share/command-code/bin/cmd" ]
[ "$(cat "$cmd_home/.local/state/dl/cmd")" = 1.87.3 ]
case "$output" in
    *"Installed $cmd_home/.local/bin/cmd"*) ;;
    *) printf '%s\n' "$output" >&2; exit 1 ;;
esac
if output=$(HOME="$cmd_home" TMPDIR="$test_root/tmp" NPM_LOG="$cmd_log" \
    run_tools "$mock_bin:$PATH" "$repo_root" cmd 2>&1); then
    :
else
    printf '%s\n' "$output" >&2
    exit 1
fi
case "$output" in
    *'cmd is current (1.87.3)'*) ;;
    *) printf '%s\n' "$output" >&2; exit 1 ;;
esac
[ "$(wc -l < "$cmd_log")" -eq 1 ]
if output=$(HOME="$cmd_home" TMPDIR="$test_root/tmp" NPM_LOG="$cmd_log" \
    CMD_TEST_VERSION=1.87.4 run_tools "$mock_bin:$PATH" "$repo_root" cmd 2>&1); then
    :
else
    printf '%s\n' "$output" >&2
    exit 1
fi
[ "$(cat "$cmd_home/.local/state/dl/cmd")" = 1.87.4 ]
[ "$(wc -l < "$cmd_log")" -eq 2 ]

cmd_owned_file="$cmd_home/.local/state/sync/dl-owned"
mkdir -p "$(dirname "$cmd_owned_file")"
HOME="$cmd_home" DL_RECORD_OWNED=true DL_OWNED_FILE="$cmd_owned_file" \
    TMPDIR="$test_root/tmp" run_tools "$mock_bin:$PATH" "$repo_root"
for owned_path in "$cmd_home/.local/bin/cmd" "$cmd_home/.local/state/dl/cmd"; do
    awk -F '\t' -v path="$owned_path" \
        '$1 == "F" && $2 == path { found = 1 } END { exit !found }' "$cmd_owned_file"
done
awk -F '\t' -v path="$cmd_home/.local/share/command-code" \
    '$1 == "D" && $2 == path { found = 1 } END { exit !found }' "$cmd_owned_file"
)
end_case

begin_case "cmd rejects unmanaged launcher"
( set -e
cmd_collision_home="$test_root/cmd-collision-home"
mkdir -p "$cmd_collision_home/.local/bin"
printf '%s\n' sentinel > "$cmd_collision_home/.local/bin/cmd"
if HOME="$cmd_collision_home" TMPDIR="$test_root/tmp" NPM_LOG="$cmd_log" \
    run_tools "$mock_bin:$PATH" "$repo_root" cmd >/dev/null 2>&1; then
    printf 'cmd overwrote an unmanaged launcher\n' >&2
    exit 1
fi
[ "$(cat "$cmd_collision_home/.local/bin/cmd")" = sentinel ]
)
end_case

begin_case "cmd rejects unmanaged npm prefix"
( set -e
cmd_prefix_home="$test_root/cmd-prefix-home"
mkdir -p "$cmd_prefix_home/.local/share/command-code"
if HOME="$cmd_prefix_home" TMPDIR="$test_root/tmp" NPM_LOG="$cmd_log" \
    run_tools "$mock_bin:$PATH" "$repo_root" cmd >/dev/null 2>&1; then
    printf 'cmd overwrote an unmanaged npm prefix\n' >&2
    exit 1
fi
[ ! -e "$cmd_prefix_home/.local/bin/cmd" ]
)
end_case

begin_case "cmd requires supported node"
( set -e
cmd_old_node_home="$test_root/cmd-old-node-home"
if HOME="$cmd_old_node_home" TMPDIR="$test_root/tmp" NPM_LOG="$cmd_log" \
    CMD_TEST_NODE_VERSION=26.11.0 run_tools "$mock_bin:$PATH" "$repo_root" cmd >/dev/null 2>&1; then
    printf 'cmd accepted an unsupported Node.js version\n' >&2
    exit 1
fi
[ ! -e "$cmd_old_node_home/.local/bin/cmd" ]
)
end_case


begin_case "cmd cleans up after failed install and recovers"
( set -e
cmd_failure_home="$test_root/cmd-failure-home"
if HOME="$cmd_failure_home" TMPDIR="$test_root/tmp" NPM_LOG="$cmd_log" \
    CMD_INSTALL_FAIL=true run_tools "$mock_bin:$PATH" "$repo_root" cmd >/dev/null 2>&1; then
    printf 'cmd ignored a failed npm install\n' >&2
    exit 1
fi
[ ! -e "$cmd_failure_home/.local/bin/cmd" ]
[ ! -e "$cmd_failure_home/.local/state/dl/cmd" ]
[ ! -e "$cmd_failure_home/.local/share/command-code" ]
if find "$cmd_failure_home/.local/share" -name 'command-code.*' | grep -q .; then
    printf 'cmd kept an incomplete npm installation\n' >&2
    exit 1
fi
if output=$(HOME="$cmd_failure_home" TMPDIR="$test_root/tmp" NPM_LOG="$cmd_log" \
    run_tools "$mock_bin:$PATH" "$repo_root" cmd 2>&1); then
    :
else
    printf '%s\n' "$output" >&2
    exit 1
fi
[ -x "$cmd_failure_home/.local/share/command-code/bin/cmd" ]
)
end_case

begin_case "sync tools prefers managed node over PATH node"
( set -e
managed_node_home="$test_root/managed-node-home"
mkdir -p "$managed_node_home/.local/share/nodejs/26.12.1/bin"
cat > "$managed_node_home/.local/share/nodejs/26.12.1/bin/node" <<'EOF'
#!/bin/sh
printf '%s\n' '26.12.1'
EOF
chmod +x "$managed_node_home/.local/share/nodejs/26.12.1/bin/node"
ln -s 26.12.1 "$managed_node_home/.local/share/nodejs/current"
stale_node_dir="$test_root/stale-node-bin"
mkdir -p "$stale_node_dir"
cat > "$stale_node_dir/node" <<'EOF'
#!/bin/sh
printf '%s\n' '26.11.0'
EOF
chmod +x "$stale_node_dir/node"
if output=$(HOME="$managed_node_home" TMPDIR="$test_root/tmp" NPM_LOG="$npm_log" \
    run_tools "$stale_node_dir:$mock_bin:/usr/bin:/bin" "$repo_root" cmd 2>&1); then
    :
else
    printf '%s\n' "$output" >&2
    exit 1
fi
case "$output" in
    *"Installed $managed_node_home/.local/bin/cmd"*) ;;
    *) printf '%s\n' "$output" >&2; exit 1 ;;
esac
)
end_case

begin_case "pnpm installs under its own prefix, is idempotent, and is recorded"
( set -e
pnpm_home="$test_root/pnpm-home"
pnpm_log="$test_root/pnpm-npm.log"
for run in 1 2; do
    if output=$(HOME="$pnpm_home" TMPDIR="$test_root/tmp" NPM_LOG="$pnpm_log" \
        run_tools "$mock_bin:$PATH" "$repo_root" pnpm 2>&1); then
        :
    else
        printf '%s\n' "$output" >&2
        exit 1
    fi
    if [ "$run" = 2 ]; then
        case "$output" in
            *'pnpm is current (12.16.1)'*) ;;
            *) printf '%s\n' "$output" >&2; exit 1 ;;
        esac
    fi
done
[ "$(readlink "$pnpm_home/.local/bin/pnpm")" = "$pnpm_home/.local/share/pnpm-npm/bin/pnpm" ]
[ "$(cat "$pnpm_home/.local/state/dl/pnpm")" = 12.16.1 ]
[ "$(wc -l < "$pnpm_log")" -eq 1 ]
pnpm_owned="$pnpm_home/.local/state/sync/dl-owned"
mkdir -p "$(dirname "$pnpm_owned")"
HOME="$pnpm_home" DL_RECORD_OWNED=true DL_OWNED_FILE="$pnpm_owned" \
    TMPDIR="$test_root/tmp" run_tools "$mock_bin:$PATH" "$repo_root"
for pnpm_path in "$pnpm_home/.local/bin/pnpm" "$pnpm_home/.local/state/dl/pnpm"; do
    awk -F '\t' -v path="$pnpm_path" \
        '$1 == "F" && $2 == path { found = 1 } END { exit !found }' "$pnpm_owned"
done
awk -F '\t' -v path="$pnpm_home/.local/share/pnpm-npm" \
    '$1 == "D" && $2 == path { found = 1 } END { exit !found }' "$pnpm_owned"
)
end_case

begin_case "pnpm installs beside a polluted pnpm home without touching it"
( set -e
pnpm_polluted_home="$test_root/pnpm-polluted-home"
mkdir -p "$pnpm_polluted_home/.local/share/pnpm/bin" \
    "$pnpm_polluted_home/.local/share/pnpm/store" \
    "$pnpm_polluted_home/.local/share/pnpm/global"
printf '%s\n' '#!/bin/sh' 'exec pnpm "$@"' > "$pnpm_polluted_home/.local/share/pnpm/bin/pn"
printf '%s\n' '#!/bin/sh' 'exec pnpm dlx "$@"' > "$pnpm_polluted_home/.local/share/pnpm/bin/pnpx"
chmod +x "$pnpm_polluted_home/.local/share/pnpm/bin/pn" "$pnpm_polluted_home/.local/share/pnpm/bin/pnpx"
printf '%s\n' keep > "$pnpm_polluted_home/.local/share/pnpm/store/keep"
if output=$(HOME="$pnpm_polluted_home" TMPDIR="$test_root/tmp" NPM_LOG="$test_root/pnpm-polluted.log" \
    run_tools "$mock_bin:$PATH" "$repo_root" pnpm 2>&1); then
    :
else
    printf '%s\n' "$output" >&2
    exit 1
fi
[ "$(readlink "$pnpm_polluted_home/.local/bin/pnpm")" = "$pnpm_polluted_home/.local/share/pnpm-npm/bin/pnpm" ]
[ -x "$pnpm_polluted_home/.local/share/pnpm-npm/bin/pnpm" ]
[ "$(cat "$pnpm_polluted_home/.local/share/pnpm/bin/pn")" = '#!/bin/sh
exec pnpm "$@"' ]
[ "$(cat "$pnpm_polluted_home/.local/share/pnpm/store/keep")" = keep ]
)
end_case

begin_case "default targets include required tools and exclude optional agents"
( set -e
default_targets=$(sed -n '/^if \[ \$# -eq 0 \]; then/,/^fi$/p' "$repo_root/tools/sync/install.sh")
case "$default_targets" in
    *'set -- '*grok*|*'set -- '*fx*)
        printf 'optional agents appeared in sync defaults\n' >&2
        exit 1 ;;
esac
case "$default_targets" in
    *' agy '*) printf 'agy is in the default dl targets\n' >&2; exit 1 ;;
esac
case "$default_targets" in
    *'nodejs pnpm cmd'*) ;;
    *) printf 'Command Code fallback is missing from sync defaults\n' >&2; exit 1 ;;
esac
case "$default_targets" in
    *' git '*) ;;
    *) printf 'git is missing from the default dl targets\n' >&2; exit 1 ;;
esac
case "$default_targets" in
    *'set -- "$@" gh'*) ;;
    *) printf 'gh is missing from the default dl targets\n' >&2; exit 1 ;;
esac
case "$default_targets" in
    *'set -- "$@" mold'*) ;;
    *) printf 'mold is missing from the default dl targets\n' >&2; exit 1 ;;
esac
case "$default_targets" in
    *' uv '*) ;;
    *) printf 'uv is missing from the default dl targets\n' >&2; exit 1 ;;
esac
case "$default_targets" in
    *'set -- "$@" shuck'*) ;;
    *) printf 'shuck is missing from the default dl targets\n' >&2; exit 1 ;;
esac
)
end_case

begin_case "parallel wave defaults to the CPU count and honors SYNC_JOBS"
( set -e
grep -q 'sysctl -n hw.ncpu' "$repo_root/tools/sync/install.sh"
grep -q 'getconf _NPROCESSORS_ONLN' "$repo_root/tools/sync/install.sh"
grep -q 'wave_jobs=$(_dl_jobs)' "$repo_root/tools/sync/install.sh"
grep -q 'if \[ "$wave_jobs" -lt "$max_workers" \]' "$repo_root/tools/sync/install.sh"
)
end_case

begin_case "npm installers are dispatched in the npm wave"
( set -e
npm_installers=$(awk '
    /^install_[a-z_]+\(\) \{/ { fn = $1; sub(/\(\)/, "", fn); body = ""; active = 1 }
    active { body = body $0 "\n" }
    active && /^}$/ { if (body ~ /command -v npm/) print fn; active = 0 }
' "$repo_root/tools/sync/install.sh")
[ -n "$npm_installers" ]
npm_wave=$(sed -n 's/^[[:space:]]*//; s/)[[:space:]]*npm_tools=.*//p' "$repo_root/tools/sync/install.sh")
for fn in $npm_installers; do
    [ "$fn" = install_nodejs ] && continue
    tool=${fn#install_}
    tool=$(printf '%s\n' "$tool" | tr '_' '-')
    case "|$npm_wave|" in
        *"|$tool|"*) ;;
        *) printf '%s requires npm but is not in the npm wave (%s)\n' "$tool" "$npm_wave" >&2; exit 1 ;;
    esac
done
)
end_case

begin_case "dsh rejects existing root without dl install records"
( set -e
unowned_dsh_home="$test_root/unowned-dsh-home"
unowned_dsh_root="$unowned_dsh_home/data/dsh"
unowned_dsh_log="$test_root/unowned-dsh-npm.log"
mkdir -p "$unowned_dsh_root"
if output=$(HOME="$unowned_dsh_home" XDG_DATA_HOME="$unowned_dsh_home/data" \
    XDG_STATE_HOME="$unowned_dsh_home/state" TMPDIR="$test_root/tmp" \
    NPM_LOG="$unowned_dsh_log" run_tools "$mock_bin:$PATH" "$repo_root" dsh 2>&1); then
    printf '%s\n' 'dsh install accepted an existing package root without dl install records' >&2
    exit 1
fi
case "$output" in
    *"Skipping dsh: $unowned_dsh_root already exists without dl install records"*) ;;
    *) printf '%s\n' "$output" >&2; exit 1 ;;
esac
if [ -f "$unowned_dsh_log" ]; then
    printf '%s\n' 'dsh install changed an existing package root without dl install records' >&2
    exit 1
fi
[ -d "$unowned_dsh_root" ]
)
end_case

begin_case "dsh install removes legacy npm package and repairs TUI patch"
( set -e
mkdir -p "$dsh_home/.local/bin" "$dsh_home/.local/lib/node_modules/@deepseek-ai/dsh"
ln -s ../lib/node_modules/@deepseek-ai/dsh/lib/bin.js "$dsh_home/.local/bin/dsh"
if output=$(HOME="$dsh_home" XDG_DATA_HOME="$dsh_data" XDG_STATE_HOME="$dsh_state" \
    TMPDIR="$test_root/tmp" NPM_LOG="$npm_log" run_tools "$mock_bin:$PATH" "$repo_root" dsh 2>&1); then
    :
else
    printf '%s\n' "$output" >&2
    exit 1
fi
[ -x "$dsh_data/dsh/bin/dsh" ]
[ -x "$dsh_data/dsh/bin/dsh-tui" ]
[ ! -L "$dsh_data/dsh/lib/node_modules/@deepseek-harness-tui/dsh-tui/cordis.patch.yml" ]
if grep -Fq 'tool-ralph' "$dsh_data/dsh/lib/node_modules/@deepseek-harness-tui/dsh-tui/cordis.patch.yml"; then
    printf '%s\n' 'dsh did not remove the incompatible TUI patch row' >&2
    exit 1
fi
[ ! -e "$dsh_home/.local/bin/dsh" ]
[ ! -d "$dsh_home/.local/lib/node_modules/@deepseek-ai/dsh" ]
case "$output" in
    *"Installed dsh and dsh-tui under $dsh_data/dsh"*) ;;
    *) printf '%s\n' "$output" >&2; exit 1 ;;
esac
)
end_case
begin_case "dsh requires supported node"
( set -e
old_node_dsh_home="$test_root/old-node-dsh-home"
if HOME="$old_node_dsh_home" XDG_DATA_HOME="$old_node_dsh_home/data" \
    XDG_STATE_HOME="$old_node_dsh_home/state" TMPDIR="$test_root/tmp" \
    CMD_TEST_NODE_VERSION=25.9.9 run_tools "$mock_bin:$PATH" "$repo_root" dsh >/dev/null 2>&1; then
    printf '%s\n' 'dsh accepted an unsupported Node.js version' >&2
    exit 1
fi
[ ! -e "$old_node_dsh_home/data/dsh" ]
case "$(cat "$npm_log")" in
    *'@deepseek-ai/dsh@0.2.1-rc.2 @deepseek-harness-tui/dsh-tui@0.16.0'*) ;;
    *) cat "$npm_log" >&2; exit 1 ;;
esac
)
end_case

begin_case "dsh keeps repo-managed launcher during legacy cleanup"
( set -e
managed_dsh_home="$test_root/managed-dsh-home"
managed_dsh_data="$managed_dsh_home/data"
managed_dsh_state="$managed_dsh_home/state"
managed_dsh_log="$test_root/managed-dsh-npm.log"
mkdir -p "$managed_dsh_home/.local/bin" "$managed_dsh_home/.local/lib/node_modules/@deepseek-ai/dsh"
ln -s "$repo_root/dotfiles/base/.local/bin/dsh" "$managed_dsh_home/.local/bin/dsh"
if output=$(HOME="$managed_dsh_home" XDG_DATA_HOME="$managed_dsh_data" \
    XDG_STATE_HOME="$managed_dsh_state" TMPDIR="$test_root/tmp" NPM_LOG="$managed_dsh_log" \
    run_tools "$mock_bin:$PATH" "$repo_root" dsh 2>&1); then
    :
else
    printf '%s\n' "$output" >&2
    exit 1
fi
[ "$(readlink "$managed_dsh_home/.local/bin/dsh")" = "$repo_root/dotfiles/base/.local/bin/dsh" ]
[ -d "$managed_dsh_home/.local/lib/node_modules/@deepseek-ai/dsh" ]
if grep -Fq 'uninstall ' "$managed_dsh_log"; then
    printf '%s\n' 'dsh removed a repo-managed launcher while cleaning up the old npm package' >&2
    exit 1
fi
case "$output" in
    *"Keeping existing dsh launcher at $managed_dsh_home/.local/bin/dsh"*) ;;
    *) printf '%s\n' "$output" >&2; exit 1 ;;
esac
)
end_case

begin_case "dsh current check and TUI patch integrity"
( set -e
if output=$(HOME="$dsh_home" XDG_DATA_HOME="$dsh_data" XDG_STATE_HOME="$dsh_state" \
    TMPDIR="$test_root/tmp" NPM_LOG="$npm_log" run_tools "$mock_bin:$PATH" "$repo_root" dsh 2>&1); then
    :
else
    printf '%s\n' "$output" >&2
    exit 1
fi
case "$output" in
    *'dsh and dsh-tui are current (0.2.1-rc.2, 0.16.0)'*) ;;
    *) printf '%s\n' "$output" >&2; exit 1 ;;
esac
printf '%s\n' '- id: tool-ralph' '  disabled: true' \
    > "$dsh_data/dsh/lib/node_modules/@deepseek-harness-tui/dsh-tui/cordis.patch.yml"
if output=$(HOME="$dsh_home" XDG_DATA_HOME="$dsh_data" XDG_STATE_HOME="$dsh_state" \
    TMPDIR="$test_root/tmp" NPM_LOG="$npm_log" run_tools "$mock_bin:$PATH" "$repo_root" dsh 2>&1); then
    :
else
    printf '%s\n' "$output" >&2
    exit 1
fi
if grep -Fq 'tool-ralph' "$dsh_data/dsh/lib/node_modules/@deepseek-harness-tui/dsh-tui/cordis.patch.yml"; then
    printf '%s\n' 'dsh did not repair the TUI patch on the current fast path' >&2
    exit 1
fi
printf '%s\n' sentinel > "$test_root/external-patch.yml"
rm "$dsh_data/dsh/lib/node_modules/@deepseek-harness-tui/dsh-tui/cordis.patch.yml"
ln -s "$test_root/external-patch.yml" \
    "$dsh_data/dsh/lib/node_modules/@deepseek-harness-tui/dsh-tui/cordis.patch.yml"
if output=$(HOME="$dsh_home" XDG_DATA_HOME="$dsh_data" XDG_STATE_HOME="$dsh_state" \
    TMPDIR="$test_root/tmp" NPM_LOG="$npm_log" run_tools "$mock_bin:$PATH" "$repo_root" dsh 2>&1); then
    printf '%s\n' 'dsh followed a symlinked TUI patch' >&2
    exit 1
fi
[ "$(cat "$test_root/external-patch.yml")" = sentinel ]
rm "$dsh_data/dsh/lib/node_modules/@deepseek-harness-tui/dsh-tui/cordis.patch.yml"
printf '%s\n' '- id: tool-ralph' '  disabled: false' \
    > "$dsh_data/dsh/lib/node_modules/@deepseek-harness-tui/dsh-tui/cordis.patch.yml"
if output=$(HOME="$dsh_home" XDG_DATA_HOME="$dsh_data" XDG_STATE_HOME="$dsh_state" \
    TMPDIR="$test_root/tmp" NPM_LOG="$npm_log" run_tools "$mock_bin:$PATH" "$repo_root" dsh 2>&1); then
    printf '%s\n' 'dsh accepted a changed TUI compatibility row' >&2
    exit 1
fi
case "$(cat "$dsh_data/dsh/lib/node_modules/@deepseek-harness-tui/dsh-tui/cordis.patch.yml")" in
    *'disabled: false'*) ;;
    *) printf '%s\n' 'dsh changed the unexpected TUI patch row' >&2; exit 1 ;;
esac
)
end_case

begin_case "muse installs official launcher"
( set -e
if output=$(HOME="$home" XDG_DATA_HOME="$home/.local/share" XDG_STATE_HOME="$home/.local/state" \
    TMPDIR="$test_root/tmp" run_tools "$mock_bin:$PATH" "$repo_root" muse 2>&1); then
    :
else
    printf '%s\n' "$output" >&2
    exit 1
fi

case "$output" in
    *"Installed Muse Code launcher ($home/.local/bin/muse)"*) ;;
    *) printf '%s\n' "$output" >&2; exit 1 ;;
esac
case "$(cat "$home/.local/bin/muse")" in
    *'#!/bin/sh'*) ;;
    *) printf '%s\n' 'Muse did not install the official launcher' >&2; exit 1 ;;
esac
)
end_case

begin_case "antigravity install and idempotence"
( set -e
antigravity_home="$test_root/antigravity-home"
if output=$(HOME="$antigravity_home" XDG_STATE_HOME="$antigravity_home/.local/state" \
    TMPDIR="$test_root/tmp" run_tools "$mock_bin:$PATH" "$repo_root" antigravity 2>&1); then
    :
else
    printf '%s\n' "$output" >&2
    exit 1
fi
[ -x "$antigravity_home/.local/bin/agy" ]
[ ! -e "$antigravity_home/.bashrc" ]
case "$output" in
    *"Installed Antigravity CLI ($antigravity_home/.local/bin/agy)"*) ;;
    *) printf '%s\n' "$output" >&2; exit 1 ;;
esac
if output=$(HOME="$antigravity_home" XDG_STATE_HOME="$antigravity_home/.local/state" \
    TMPDIR="$test_root/tmp" run_tools "$mock_bin:$PATH" "$repo_root" antigravity 2>&1); then
    :
else
    printf '%s\n' "$output" >&2
    exit 1
fi
case "$output" in
    *'agy is installed'*) ;;
    *) printf '%s\n' "$output" >&2; exit 1 ;;
esac
)
end_case

begin_case "jaq ownership recorded exactly once"
( set -e
ownership_home="$test_root/ownership-home"
ownership_file="$ownership_home/.local/state/sync/dl-owned"
mkdir -p "$(dirname "$ownership_file")"
if output=$(HOME="$ownership_home" XDG_STATE_HOME="$ownership_home/.local/state" \
    DL_OWNED_FILE="$ownership_file" DL_JAQ_MOCK="$mock_bin/jaq" \
    TMPDIR="$test_root/tmp" run_tools "$mock_bin:$PATH" "$repo_root" jaq 2>&1); then
    :
else
    printf '%s\n' "$output" >&2
    exit 1
fi
if output=$(HOME="$ownership_home" XDG_STATE_HOME="$ownership_home/.local/state" \
    DL_OWNED_FILE="$ownership_file" DL_JAQ_MOCK="$mock_bin/jaq" \
    TMPDIR="$test_root/tmp" run_tools "$mock_bin:$PATH" "$repo_root" jaq 2>&1); then
    :
else
    printf '%s\n' "$output" >&2
    exit 1
fi
awk -F '\t' -v path="$ownership_home/.local/bin/jaq" \
    '$1 == "F" && $2 == path { count++ } END { exit count != 1 }' "$ownership_file"
awk -F '\t' -v path="$ownership_home/.local/state/dl/jaq" \
    '$1 == "F" && $2 == path { count++ } END { exit count != 1 }' "$ownership_file"
awk -F '\t' -v path="$ownership_home/.local/bin" \
    '$1 == "E" && $2 == path { count++ } END { exit count != 1 }' "$ownership_file"
awk -F '\t' -v path="$ownership_home/.local/state/dl" \
    '$1 == "E" && $2 == path { count++ } END { exit count != 1 }' "$ownership_file"
)
end_case

begin_case "reconcile records managed installs"
( set -e
reconcile_home="$test_root/reconcile-home"
reconcile_file="$reconcile_home/.local/state/sync/dl-owned"
mkdir -p "$reconcile_home/.local/bin" "$reconcile_home/.local/state/dl" \
    "$(dirname "$reconcile_file")"
printf '%s\n' 'managed jaq' > "$reconcile_home/.local/bin/jaq"
chmod +x "$reconcile_home/.local/bin/jaq"
printf '%s\n' 'jaq-test-etag' > "$reconcile_home/.local/state/dl/jaq"
HOME="$reconcile_home" XDG_STATE_HOME="$reconcile_home/.local/state" \
    DL_OWNED_FILE="$reconcile_file" DL_RECORD_OWNED=true \
    TMPDIR="$test_root/tmp" run_tools "$mock_bin:$PATH" "$repo_root"
awk -F '\t' -v path="$reconcile_home/.local/bin/jaq" \
    '$1 == "F" && $2 == path { count++ } END { exit count != 1 }' "$reconcile_file"
awk -F '\t' -v path="$reconcile_home/.local/state/dl/jaq" \
    '$1 == "F" && $2 == path { count++ } END { exit count != 1 }' "$reconcile_file"
)
end_case

begin_case "unmanaged launcher is not recorded for removal"
( set -e
unmanaged_home="$test_root/unmanaged-home"
unmanaged_file="$unmanaged_home/.local/state/sync/dl-owned"
mkdir -p "$unmanaged_home/.local/bin" "$(dirname "$unmanaged_file")"
printf '%s\n' '#!/bin/sh' 'exit 0' > "$unmanaged_home/.local/bin/jaq"
chmod +x "$unmanaged_home/.local/bin/jaq"
HOME="$unmanaged_home" XDG_STATE_HOME="$unmanaged_home/.local/state" \
    DL_OWNED_FILE="$unmanaged_file" DL_RECORD_OWNED=true \
    TMPDIR="$test_root/tmp" run_tools "$mock_bin:$PATH" "$repo_root"
if awk -F '\t' -v path="$unmanaged_home/.local/bin/jaq" \
    '$1 == "F" && $2 == path { found = 1 } END { exit !found }' "$unmanaged_file"; then
    printf '%s\n' 'launcher without dl install state was recorded for removal' >&2
    exit 1
fi
[ -x "$unmanaged_home/.local/bin/jaq" ]
)
end_case

begin_case "untracked launcher is reported"
( set -e
untracked_home="$test_root/untracked-home"
mkdir -p "$untracked_home/.local/bin" "$untracked_home/.local/state/dl" \
    "$untracked_home/.local/state/sync"
printf '%s\n' '#!/bin/sh' 'exit 0' > "$untracked_home/.local/bin/agy"
chmod +x "$untracked_home/.local/bin/agy"
if output=$(HOME="$untracked_home" XDG_STATE_HOME="$untracked_home/.local/state" \
    DL_OWNED_FILE="$untracked_home/.local/state/sync/dl-owned" DL_RECORD_OWNED=true \
    TMPDIR="$test_root/tmp" run_tools "$mock_bin:$PATH" "$repo_root" 2>&1); then
    :
else
    printf '%s\n' "$output" >&2
    exit 1
fi
case "$output" in
    *"Leaving untracked launcher: $untracked_home/.local/bin/agy"*) ;;
    *) printf '%s\n' "$output" >&2; exit 1 ;;
esac
[ -x "$untracked_home/.local/bin/agy" ]
)
end_case

begin_case "unsafe codex target is not recorded for removal"
( set -e
unsafe_target_home="$test_root/unsafe-target-home"
unsafe_target_rogue="$unsafe_target_home/.codex/packages/rogue/bin"
unsafe_target_owned="$unsafe_target_home/.local/state/sync/dl-owned"
mkdir -p "$unsafe_target_rogue" "$unsafe_target_home/.local/bin" \
    "$unsafe_target_home/.local/state/dl" "$(dirname "$unsafe_target_owned")"
printf '%s\n' '#!/bin/sh' 'exit 0' > "$unsafe_target_rogue/codex"
printf '%s\n' '#!/bin/sh' 'exit 0' > "$unsafe_target_rogue/codex-code-mode-host"
chmod +x "$unsafe_target_rogue/codex" "$unsafe_target_rogue/codex-code-mode-host"
printf '%s\n' 'codex-test-etag' > "$unsafe_target_home/.local/state/dl/codex"
ln -s "$unsafe_target_home/.codex/packages/standalone/releases/../../rogue/bin/codex" \
    "$unsafe_target_home/.local/bin/codex"
ln -s "$unsafe_target_home/.codex/packages/standalone/releases/../../rogue/bin/codex-code-mode-host" \
    "$unsafe_target_home/.local/bin/codex-code-mode-host"
HOME="$unsafe_target_home" XDG_STATE_HOME="$unsafe_target_home/.local/state" \
    DL_OWNED_FILE="$unsafe_target_owned" DL_RECORD_OWNED=true \
    TMPDIR="$test_root/tmp" run_tools "$mock_bin:$PATH" "$repo_root"
if awk -F '\t' -v path="$unsafe_target_home/.codex/packages/rogue" \
    '$1 == "D" && $2 == path { found = 1 } END { exit !found }' "$unsafe_target_owned"; then
    printf '%s\n' 'unsafe Codex release target was recorded for recursive removal' >&2
    exit 1
fi
if awk -F '\t' -v path="$unsafe_target_home/.local/bin/codex-code-mode-host" \
    '$1 == "F" && $2 == path { found = 1 } END { exit !found }' "$unsafe_target_owned"; then
    printf '%s\n' 'unsafe Codex companion launcher was recorded for removal' >&2
    exit 1
fi
[ -x "$unsafe_target_rogue/codex" ]
[ -x "$unsafe_target_rogue/codex-code-mode-host" ]
)
end_case

cat > "$mock_bin/uname" <<'EOF'
#!/bin/sh
case "$1" in
    -s) printf '%s\n' "${DL_TEST_OS:-Linux}" ;;
    -m) printf '%s\n' "${DL_TEST_ARCH:-x86_64}" ;;
    *) exit 1 ;;
esac
EOF
chmod +x "$mock_bin/uname"

begin_case "player is a default target on x86-64 Linux only"
( set -e
targets=$(HOME="$test_root/player-default-home" DL_TEST_OS=Linux DL_TEST_ARCH=x86_64 \
    TMPDIR="$test_root/tmp" run_tools "$mock_bin:$PATH" "$repo_root" --list)
printf '%s\n' "$targets" | grep -qx player
targets=$(HOME="$test_root/player-default-home" DL_TEST_OS=Linux DL_TEST_ARCH=aarch64 \
    TMPDIR="$test_root/tmp" run_tools "$mock_bin:$PATH" "$repo_root" --list)
if printf '%s\n' "$targets" | grep -qx player; then
    printf '%s\n' 'player is a default target on aarch64' >&2
    exit 1
fi
)
end_case

begin_case "server profile keeps only the minimal tools"
( set -e
DL_PROFILE=server
export DL_PROFILE
targets=$(HOME="$test_root/server-profile-home" DL_TEST_OS=Linux DL_TEST_ARCH=x86_64 \
    TMPDIR="$test_root/tmp" run_tools "$mock_bin:$PATH" "$repo_root" --list)
for expected in fd rg jaq fastermod tm ish stuff e fz fdu fs srv git python3 uv gh zzz shuck; do
    printf '%s\n' "$targets" | grep -qx "$expected" || {
        printf 'server profile is missing %s\n' "$expected" >&2
        exit 1
    }
done
for excluded in codex claude opencode2 pi agent-browser cf ffmpeg nodejs syncthing mold player; do
    if printf '%s\n' "$targets" | grep -qx "$excluded"; then
        printf 'server profile includes %s\n' "$excluded" >&2
        exit 1
    fi
done
)
end_case

begin_case "ghostty-custom installs latest prerelease, is idempotent, and records ownership"
( set -e
custom_home="$test_root/ghostty-custom-home"
apps="$custom_home/Applications"
owned="$custom_home/.local/state/sync/dl-owned"
mkdir -p "$(dirname "$owned")"
if output=$(HOME="$custom_home" GHOSTTY_APPLICATIONS_DIR="$apps" \
    DL_TEST_OS=Darwin DL_TEST_ARCH=arm64 DL_OWNED_FILE="$owned" \
    TMPDIR="$test_root/tmp" run_tools "$mock_bin:$PATH" "$repo_root" ghostty-custom 2>&1); then
    :
else
    printf '%s\n' "$output" >&2
    exit 1
fi
[ -x "$apps/Ghostty Custom.app/Contents/MacOS/ghostty" ]
[ "$(readlink "$custom_home/.local/bin/ghostty-custom")" \
    = "$apps/Ghostty Custom.app/Contents/MacOS/ghostty" ]
[ "$(cat "$custom_home/.local/state/dl/ghostty-custom")" = ghostty-custom-test-etag ]
case "$output" in *"Installed $apps/Ghostty Custom.app (release-bbb000bbb000bbb000bbb000bbb000bbb000bbb0002)"*) ;; *) exit 1 ;; esac

if output=$(HOME="$custom_home" GHOSTTY_APPLICATIONS_DIR="$apps" \
    DL_TEST_OS=Darwin DL_TEST_ARCH=arm64 DL_OWNED_FILE="$owned" \
    TMPDIR="$test_root/tmp" run_tools "$mock_bin:$PATH" "$repo_root" ghostty-custom 2>&1); then
    :
else
    printf '%s\n' "$output" >&2
    exit 1
fi
case "$output" in *'ghostty-custom is current (release-bbb000bbb000bbb000bbb000bbb000bbb000bbb0002)'*) ;; *) exit 1 ;; esac
HOME="$custom_home" GHOSTTY_APPLICATIONS_DIR="$apps" \
    DL_RECORD_OWNED=true DL_OWNED_FILE="$owned" \
    TMPDIR="$test_root/tmp" run_tools "$mock_bin:$PATH" "$repo_root"
awk -F '\t' -v path="$apps/Ghostty Custom.app" \
    '$1 == "D" && $2 == path { found = 1 } END { exit !found }' "$owned"
for f in "$custom_home/.local/bin/ghostty-custom" "$custom_home/.local/state/dl/ghostty-custom"; do
    awk -F '\t' -v path="$f" \
        '$1 == "F" && $2 == path { found = 1 } END { exit !found }' "$owned"
done
)
end_case

begin_case "ghostty-custom refuses existing unmanaged app and launcher"
( set -e
collision_home="$test_root/ghostty-custom-collision"
apps="$collision_home/Applications"
mkdir -p "$apps/Ghostty Custom.app" "$collision_home/.local/bin"
printf '%s\n' "unmanaged" > "$apps/Ghostty Custom.app/keep"
printf '%s\n' '#!/bin/sh' 'exit 0' > "$collision_home/.local/bin/ghostty-custom"
chmod +x "$collision_home/.local/bin/ghostty-custom"
if HOME="$collision_home" GHOSTTY_APPLICATIONS_DIR="$apps" \
    DL_TEST_OS=Darwin DL_TEST_ARCH=arm64 TMPDIR="$test_root/tmp" \
    run_tools "$mock_bin:$PATH" "$repo_root" ghostty-custom; then exit 1; fi
[ "$(cat "$apps/Ghostty Custom.app/keep")" = unmanaged ]
[ -f "$collision_home/.local/bin/ghostty-custom" ]
[ ! -e "$collision_home/.local/state/dl/ghostty-custom" ]
)
end_case

begin_case "ghostty-custom rejects checksum mismatch, bundle id drift, and extract failure"
( set -e
for fault in sums bundle extract; do
    broken_home="$test_root/ghostty-custom-broken-$fault"
    apps="$broken_home/Applications"
    case "$fault" in
        sums) GHOSTTY_CUSTOM_TEST_BAD_SUMS=true ;;
        bundle) GHOSTTY_CUSTOM_TEST_BUNDLE_ID=com.example.wrong ;;
        extract) GHOSTTY_TEST_EXTRACT_FAIL=true ;;
    esac
    export GHOSTTY_CUSTOM_TEST_BAD_SUMS GHOSTTY_CUSTOM_TEST_BUNDLE_ID GHOSTTY_TEST_EXTRACT_FAIL
    if HOME="$broken_home" GHOSTTY_APPLICATIONS_DIR="$apps" \
        DL_TEST_OS=Darwin DL_TEST_ARCH=arm64 TMPDIR="$test_root/tmp" \
        run_tools "$mock_bin:$PATH" "$repo_root" ghostty-custom; then exit 1; fi
    [ ! -e "$apps/Ghostty Custom.app" ]
    [ ! -e "$broken_home/.local/bin/ghostty-custom" ]
    [ ! -e "$broken_home/.local/state/dl/ghostty-custom" ]
    unset GHOSTTY_CUSTOM_TEST_BAD_SUMS GHOSTTY_CUSTOM_TEST_BUNDLE_ID GHOSTTY_TEST_EXTRACT_FAIL
done
)
end_case

begin_case "gh is current"
( set -e
gh_home="$test_root/gh-home"
mkdir -p "$gh_home/.local/bin" "$gh_home/.local/state/dl"
printf '%s\n' 'gh test binary' > "$gh_home/.local/bin/gh"
chmod +x "$gh_home/.local/bin/gh"
printf '%s\n' 'gh-test-etag' > "$gh_home/.local/state/dl/gh"
if output=$(HOME="$gh_home" XDG_STATE_HOME="$gh_home/.local/state" \
    DL_TEST_OS=Darwin DL_TEST_ARCH=arm64 TMPDIR="$test_root/tmp" \
    run_tools "$mock_bin:$PATH" "$repo_root" gh 2>&1); then
    :
else
    printf '%s\n' "$output" >&2
    exit 1
fi
case "$output" in
    *'gh is current (release-9be88d806c91cbce8920e188f90fb6df34b45ba9)'*) ;;
    *) printf '%s\n' "$output" >&2; exit 1 ;;
esac
)
end_case

begin_case "syncthing install and current check"
( set -e
st_home="$test_root/syncthing-home"
mkdir -p "$st_home/.local/bin" "$st_home/.local/state/dl"
if output=$(HOME="$st_home" XDG_STATE_HOME="$st_home/.local/state" \
    DL_TEST_OS=Darwin DL_TEST_ARCH=arm64 TMPDIR="$test_root/tmp" \
    run_tools "$mock_bin:$PATH" "$repo_root" syncthing 2>&1); then
    :
else
    printf '%s\n' "$output" >&2
    exit 1
fi
case "$output" in
    *'Installed '"$st_home"'/.local/bin/syncthing'*) ;;
    *) printf '%s\n' "$output" >&2; exit 1 ;;
esac
[ "$(cat "$st_home/.local/bin/syncthing")" = 'syncthing-test-binary' ]
[ "$(cat "$st_home/.local/state/dl/syncthing")" = 'syncthing-test-etag' ]
if output=$(HOME="$st_home" XDG_STATE_HOME="$st_home/.local/state" \
    DL_TEST_OS=Darwin DL_TEST_ARCH=arm64 TMPDIR="$test_root/tmp" \
    run_tools "$mock_bin:$PATH" "$repo_root" syncthing 2>&1); then
    :
else
    printf '%s\n' "$output" >&2
    exit 1
fi
case "$output" in
    *'syncthing is current (release-bbb000bbb000bbb000bbb000bbb000bbb000bbb0002)'*) ;;
    *) printf '%s\n' "$output" >&2; exit 1 ;;
esac
)
end_case

begin_case "soulseek-rs install, current check, and musl-static asset"
( set -e
ss_home="$test_root/soulseek-rs-home"
mkdir -p "$ss_home/.local/bin" "$ss_home/.local/state/dl"
if output=$(HOME="$ss_home" XDG_STATE_HOME="$ss_home/.local/state" \
    DL_TEST_OS=Darwin DL_TEST_ARCH=arm64 TMPDIR="$test_root/tmp" \
    run_tools "$mock_bin:$PATH" "$repo_root" soulseek-rs 2>&1); then
    :
else
    printf '%s\n' "$output" >&2
    exit 1
fi
case "$output" in
    *'Installed '"$ss_home"'/.local/bin/soulseek-rs'*) ;;
    *) printf '%s\n' "$output" >&2; exit 1 ;;
esac
[ "$(cat "$ss_home/.local/bin/soulseek-rs")" = 'soulseek-rs-test-binary' ]
[ "$(cat "$ss_home/.local/state/dl/soulseek-rs")" = 'soulseek-rs-test-etag' ]
if output=$(HOME="$ss_home" XDG_STATE_HOME="$ss_home/.local/state" \
    DL_TEST_OS=Darwin DL_TEST_ARCH=arm64 TMPDIR="$test_root/tmp" \
    run_tools "$mock_bin:$PATH" "$repo_root" soulseek-rs 2>&1); then
    :
else
    printf '%s\n' "$output" >&2
    exit 1
fi
case "$output" in
    *'soulseek-rs is current (release-sss000sss000sss000sss000sss000sss000sss0001)'*) ;;
    *) printf '%s\n' "$output" >&2; exit 1 ;;
esac
ss_linux_home="$test_root/soulseek-rs-linux-home"
mkdir -p "$ss_linux_home/.local/bin" "$ss_linux_home/.local/state/dl"
if output=$(HOME="$ss_linux_home" XDG_STATE_HOME="$ss_linux_home/.local/state" \
    TMPDIR="$test_root/tmp" DL_TEST_OS=Linux DL_TEST_ARCH=x86_64 \
    run_tools "$mock_bin:/usr/bin:/bin" "$repo_root" soulseek-rs 2>&1); then
    :
else
    printf '%s\n' "$output" >&2
    exit 1
fi
case "$output" in
    *'Installed '"$ss_linux_home"'/.local/bin/soulseek-rs'*) ;;
    *) printf '%s\n' "$output" >&2; exit 1 ;;
esac
[ "$(cat "$ss_linux_home/.local/bin/soulseek-rs")" = 'soulseek-rs-static-test-binary' ]
[ "$(cat "$ss_linux_home/.local/state/dl/soulseek-rs")" = 'soulseek-rs-static-test-etag' ]
)
end_case

begin_case "fx installs latest release, stays current, and records ownership"
( set -e
fx_home="$test_root/fx-home"
fx_path="$fx_home/.local/bin/fx"
fx_state="$fx_home/.local/state/dl/fx"
fx_path_env="$test_root/fx-sha-bin:$mock_bin:$PATH"
if output=$(HOME="$fx_home" XDG_STATE_HOME="$fx_home/.local/state" \
    TMPDIR="$test_root/tmp" FX_TAR="$test_root/fx.tar.gz" FX_TEST_SHA=valid \
    run_tools "$fx_path_env" "$repo_root" fx 2>&1); then
    :
else
    printf '%s\n' "$output" >&2
    exit 1
fi
[ -x "$fx_path" ]
[ "$("$fx_path" --version)" = 'fx-test 0.0.16' ]
[ "$(cat "$fx_state")" = 'v0.0.16:f0fb822c7be546c80bcc89d50521bc1454435e0c6f586e8420c4e2b84fa80599' ]
if output=$(HOME="$fx_home" XDG_STATE_HOME="$fx_home/.local/state" \
    TMPDIR="$test_root/tmp" FX_TAR="$test_root/fx.tar.gz" FX_TEST_SHA=bad \
    run_tools "$fx_path_env" "$repo_root" fx 2>&1); then
    :
else
    printf '%s\n' "$output" >&2
    exit 1
fi
case "$output" in *'fx is current (v0.0.16)'*) ;; *) printf '%s\n' "$output" >&2; exit 1 ;; esac
)
end_case

begin_case "fx rejects archive checksum mismatch"
( set -e
fx_home="$test_root/fx-bad-home"
if output=$(HOME="$fx_home" XDG_STATE_HOME="$fx_home/.local/state" \
    TMPDIR="$test_root/tmp" FX_TAR="$test_root/fx.tar.gz" FX_TEST_SHA=bad \
    run_tools "$test_root/fx-sha-bin:$mock_bin:$PATH" "$repo_root" fx 2>&1); then
    printf '%s\n' "$output" >&2
    exit 1
fi
case "$output" in *'checksum mismatch'*) ;; *) printf '%s\n' "$output" >&2; exit 1 ;; esac
[ ! -e "$fx_home/.local/bin/fx" ]
[ ! -e "$fx_home/.local/state/dl/fx" ]
)
end_case

begin_case "fx preserves unmanaged binary"
( set -e
fx_home="$test_root/fx-unmanaged-home"
mkdir -p "$fx_home/.local/bin"
printf '%s\n' '#!/bin/sh' 'echo unmanaged' > "$fx_home/.local/bin/fx"
chmod +x "$fx_home/.local/bin/fx"
if output=$(HOME="$fx_home" XDG_STATE_HOME="$fx_home/.local/state" \
    TMPDIR="$test_root/tmp" FX_TAR="$test_root/fx.tar.gz" FX_TEST_SHA=valid \
    run_tools "$test_root/fx-sha-bin:$mock_bin:$PATH" "$repo_root" fx 2>&1); then
    printf '%s\n' "$output" >&2
    exit 1
fi
case "$output" in *'outside dl management'*) ;; *) printf '%s\n' "$output" >&2; exit 1 ;; esac
[ "$("$fx_home/.local/bin/fx")" = unmanaged ]
[ ! -e "$fx_home/.local/state/dl/fx" ]
)
end_case

begin_case "grok install"
( set -e
grok_home="$test_root/grok-home"
if output=$(HOME="$grok_home" XDG_STATE_HOME="$grok_home/.local/state" \
    TMPDIR="$test_root/tmp" run_tools "$mock_bin:$PATH" "$repo_root" grok 2>&1); then
    :
else
    printf '%s\n' "$output" >&2
    exit 1
fi
[ "$(readlink "$grok_home/.local/bin/grok")" = "$grok_home/.grok/bin/grok" ]
[ "$(readlink "$grok_home/.grok/bin/grok")" = ../downloads/grok-linux-x86_64 ]
[ "$(cat "$grok_home/.grok/downloads/grok-linux-x86_64")" = grok-test-binary ]
)
end_case

begin_case "grok collision preserves native install"
( set -e
grok_collision_home="$test_root/grok-collision-home"
mkdir -p "$grok_collision_home/.local/bin" "$grok_collision_home/.local/state/dl" \
    "$grok_collision_home/.grok/bin" "$grok_collision_home/.grok/downloads"
printf '%s\n' 'legacy grok binary' > "$grok_collision_home/.local/bin/grok"
printf '%s\n' 'native grok binary' > "$grok_collision_home/.grok/downloads/grok-linux-x86_64"
chmod +x "$grok_collision_home/.local/bin/grok" "$grok_collision_home/.grok/downloads/grok-linux-x86_64"
ln -s ../downloads/grok-linux-x86_64 "$grok_collision_home/.grok/bin/grok"
printf '%s\n' 'old-grok-test-etag' > "$grok_collision_home/.local/state/dl/grok"
if output=$(HOME="$grok_collision_home" XDG_STATE_HOME="$grok_collision_home/.local/state" \
    TMPDIR="$test_root/tmp" run_tools "$mock_bin:$PATH" "$repo_root" grok 2>&1); then
    printf '%s\n' 'Grok migration replaced an existing native install' >&2
    exit 1
fi
[ "$(cat "$grok_collision_home/.local/bin/grok")" = 'legacy grok binary' ]
[ "$(cat "$grok_collision_home/.grok/downloads/grok-linux-x86_64")" = 'native grok binary' ]
)
end_case

begin_case "grok legacy migration"
( set -e
legacy_grok_home="$test_root/legacy-grok-home"
mkdir -p "$legacy_grok_home/.local/bin" "$legacy_grok_home/.local/state/dl"
printf '%s\n' 'legacy grok binary' > "$legacy_grok_home/.local/bin/grok"
chmod +x "$legacy_grok_home/.local/bin/grok"
printf '%s\n' 'old-grok-test-etag' > "$legacy_grok_home/.local/state/dl/grok"
if output=$(HOME="$legacy_grok_home" XDG_STATE_HOME="$legacy_grok_home/.local/state" \
    TMPDIR="$test_root/tmp" run_tools "$mock_bin:$PATH" "$repo_root" grok 2>&1); then
    :
else
    printf '%s\n' "$output" >&2
    exit 1
fi
[ "$(readlink "$legacy_grok_home/.local/bin/grok")" = "$legacy_grok_home/.grok/bin/grok" ]
)
end_case

begin_case "muse legacy migration"
( set -e
muse_legacy_home="$test_root/legacy-muse-home"
mkdir -p "$muse_legacy_home/.local/bin" "$muse_legacy_home/.local/state/dl"
printf '%s\n' 'legacy muse binary' > "$muse_legacy_home/.local/bin/muse"
chmod +x "$muse_legacy_home/.local/bin/muse"
printf '%s\n' 'old-muse-test-etag' > "$muse_legacy_home/.local/state/dl/muse"
if output=$(HOME="$muse_legacy_home" XDG_STATE_HOME="$muse_legacy_home/.local/state" \
    TMPDIR="$test_root/tmp" run_tools "$mock_bin:$PATH" "$repo_root" muse 2>&1); then
    :
else
    printf '%s\n' "$output" >&2
    exit 1
fi
case "$(cat "$muse_legacy_home/.local/bin/muse")" in
    *'#!/bin/sh'*) ;;
    *) printf '%s\n' 'Muse legacy install was not migrated to the official launcher' >&2; exit 1 ;;
esac
)
end_case

begin_case "opencode install, shim repair, and managed update"
( set -e
opencode_home="$test_root/opencode-home"
if output=$(HOME="$opencode_home" XDG_STATE_HOME="$opencode_home/.local/state" \
    TMPDIR="$test_root/tmp" OPENCODE_TAR="$test_root/opencode.tar.gz" run_tools "$mock_bin:$PATH" "$repo_root" opencode2 2>&1); then
    :
else
    printf '%s\n' "$output" >&2
    exit 1
fi
[ -x "$opencode_home/.opencode/bin/opencode" ]
[ ! -L "$opencode_home/.local/bin/opencode2" ]
[ -x "$opencode_home/.local/bin/opencode2" ]
[ "$(HOME="$opencode_home" "$opencode_home/.local/bin/opencode2" --version)" = 'opencode 2.0.1' ]
cat > "$opencode_home/.opencode/bin/opencode2" <<'EOF'
#!/bin/sh
exec "$HOME/.local/bin/opencode" "$@"
EOF
chmod +x "$opencode_home/.opencode/bin/opencode2"
if output=$(HOME="$opencode_home" XDG_STATE_HOME="$opencode_home/.local/state" \
    TMPDIR="$test_root/tmp" OPENCODE_TAR="$test_root/opencode.tar.gz" run_tools "$mock_bin:$PATH" "$repo_root" opencode2 2>&1); then
    :
else
    printf '%s\n' "$output" >&2
    exit 1
fi
[ "$(HOME="$opencode_home" "$opencode_home/.local/bin/opencode2" --version)" = 'opencode 2.0.1' ]
if output=$(HOME="$opencode_home" XDG_STATE_HOME="$opencode_home/.local/state" \
    TMPDIR="$test_root/tmp" OPENCODE_TAR="$test_root/opencode-v2.tar.gz" OPENCODE_ETAG=opencode-test-etag-2 \
    run_tools "$mock_bin:$PATH" "$repo_root" opencode2 2>&1); then
    :
else
    printf '%s\n' "$output" >&2
    exit 1
fi
case "$output" in
    *'already exists'*) printf '%s\n' 'managed OpenCode 2 update was skipped' >&2; exit 1 ;;
esac
[ "$(HOME="$opencode_home" "$opencode_home/.local/bin/opencode2" --version)" = 'opencode 2.0.2' ]
[ "$(cat "$opencode_home/.local/state/dl/opencode2")" = opencode-test-etag-2 ]
cat > "$opencode_home/.opencode/bin/opencode2" <<'EOF'
#!/bin/sh
exec "$(dirname "$0")/opencode" "$@"
EOF
chmod +x "$opencode_home/.opencode/bin/opencode2"
[ "$(HOME="$opencode_home" "$opencode_home/.local/bin/opencode2" --version)" = 'opencode 2.0.2' ]
if output=$(HOME="$opencode_home" XDG_STATE_HOME="$opencode_home/.local/state" \
    TMPDIR="$test_root/tmp" OPENCODE_TAR="$test_root/opencode-v2.tar.gz" OPENCODE_ETAG=opencode-test-etag-2 \
    run_tools "$mock_bin:$PATH" "$repo_root" opencode2 2>&1); then
    :
else
    printf '%s\n' "$output" >&2
    exit 1
fi
[ ! -L "$opencode_home/.local/bin/opencode2" ]
[ "$(HOME="$opencode_home" "$opencode_home/.local/bin/opencode2" --version)" = 'opencode 2.0.2' ]
rm -f "$opencode_home/.local/bin/opencode2"
ln -s "$opencode_home/.opencode/bin/opencode2" "$opencode_home/.local/bin/opencode2"
if output=$(HOME="$opencode_home" XDG_STATE_HOME="$opencode_home/.local/state" \
    TMPDIR="$test_root/tmp" OPENCODE_TAR="$test_root/opencode-v2.tar.gz" OPENCODE_ETAG=opencode-test-etag-2 \
    run_tools "$mock_bin:$PATH" "$repo_root" opencode2 2>&1); then
    :
else
    printf '%s\n' "$output" >&2
    exit 1
fi
[ ! -L "$opencode_home/.local/bin/opencode2" ]
[ "$(HOME="$opencode_home" "$opencode_home/.local/bin/opencode2" --version)" = 'opencode 2.0.2' ]
)
end_case

begin_case "opencode collision preserves native install"
( set -e
opencode_collision_home="$test_root/opencode-collision-home"
mkdir -p "$opencode_collision_home/.local/bin" "$opencode_collision_home/.local/state/dl" \
    "$opencode_collision_home/.opencode/bin"
printf '%s\n' 'legacy opencode binary' > "$opencode_collision_home/.local/bin/opencode2"
printf '%s\n' 'native opencode binary' > "$opencode_collision_home/.opencode/bin/opencode"
chmod +x "$opencode_collision_home/.local/bin/opencode2" "$opencode_collision_home/.opencode/bin/opencode"
printf '%s\n' 'old-opencode-test-etag' > "$opencode_collision_home/.local/state/dl/opencode2"
if output=$(HOME="$opencode_collision_home" XDG_STATE_HOME="$opencode_collision_home/.local/state" \
    TMPDIR="$test_root/tmp" OPENCODE_TAR="$test_root/opencode.tar.gz" run_tools "$mock_bin:$PATH" "$repo_root" opencode2 2>&1); then
    printf '%s\n' 'OpenCode 2 migration replaced an existing native install' >&2
    exit 1
fi
[ "$(cat "$opencode_collision_home/.local/bin/opencode2")" = 'legacy opencode binary' ]
[ "$(cat "$opencode_collision_home/.opencode/bin/opencode")" = 'native opencode binary' ]
)
end_case

begin_case "claude install and idempotence"
( set -e
claude_home="$test_root/claude-home"
claude_data="$claude_home/share"
claude_state="$claude_home/state"
if output=$(HOME="$claude_home" XDG_DATA_HOME="$claude_data" XDG_STATE_HOME="$claude_state" \
    TMPDIR="$test_root/tmp" run_tools "$mock_bin:$PATH" "$repo_root" claude 2>&1); then
    :
else
    printf '%s\n' "$output" >&2
    exit 1
fi
claude_version="$claude_home/.claude/native/claude"
[ -L "$claude_home/.local/bin/claude" ]
[ "$(readlink "$claude_home/.local/bin/claude")" = "$claude_version" ]
[ -x "$claude_version" ]
case "$output" in
    *"Installed Claude Code ($claude_home/.local/bin/claude)"*) ;;
    *) printf '%s\n' "$output" >&2; exit 1 ;;
esac
case "$output" in
    *'native installer output'*) printf '%s\n' "$output" >&2; exit 1 ;;
esac
if output=$(HOME="$claude_home" XDG_DATA_HOME="$claude_data" XDG_STATE_HOME="$claude_state" \
    TMPDIR="$test_root/tmp" run_tools "$mock_bin:$PATH" "$repo_root" claude 2>&1); then
    :
else
    printf '%s\n' "$output" >&2
    exit 1
fi
case "$output" in
    *'claude is installed'*) ;;
    *) printf '%s\n' "$output" >&2; exit 1 ;;
esac
)
end_case

begin_case "claude installer failure passthrough"
( set -e
claude_failure_home="$test_root/claude-failure-home"
if output=$(HOME="$claude_failure_home" XDG_STATE_HOME="$claude_failure_home/.local/state" \
    TMPDIR="$test_root/tmp" CLAUDE_INSTALLER_FAIL=true \
    run_tools "$mock_bin:$PATH" "$repo_root" claude 2>&1); then
    printf '%s\n' 'Claude installer failure was ignored' >&2
    exit 1
fi
case "$output" in
    *'native installer failure'*) ;;
    *) printf '%s\n' "$output" >&2; exit 1 ;;
esac
)
end_case

begin_case "claude old versioned migration"
( set -e
old_claude_home="$test_root/old-claude-home"
old_claude_data="$old_claude_home/share"
mkdir -p "$old_claude_home/.local/bin" "$old_claude_home/.local/state/dl" \
    "$old_claude_data/claude/versions"
printf '%s\n' 'legacy versioned Claude binary' > "$old_claude_data/claude/versions/2.1.299"
chmod +x "$old_claude_data/claude/versions/2.1.299"
ln -s "$old_claude_data/claude/versions/2.1.299" "$old_claude_home/.local/bin/claude"
printf '%s\n' 'old-claude-test-etag' > "$old_claude_home/.local/state/dl/claude"
if output=$(HOME="$old_claude_home" XDG_DATA_HOME="$old_claude_data" \
    XDG_STATE_HOME="$old_claude_home/.local/state" TMPDIR="$test_root/tmp" \
    run_tools "$mock_bin:$PATH" "$repo_root" claude 2>&1); then
    :
else
    printf '%s\n' "$output" >&2
    exit 1
fi
[ "$(readlink "$old_claude_home/.local/bin/claude")" = "$old_claude_home/.claude/native/claude" ]
)
end_case

begin_case "claude legacy migration"
( set -e
legacy_home="$test_root/legacy-home"
mkdir -p "$legacy_home/.local/bin" "$legacy_home/.local/state/dl"
printf '%s' 'legacy Claude binary' > "$legacy_home/.local/bin/claude"
chmod +x "$legacy_home/.local/bin/claude"
printf '%s\n' 'old-claude-test-etag' > "$legacy_home/.local/state/dl/claude"
if output=$(HOME="$legacy_home" XDG_DATA_HOME="$legacy_home/.local/share" \
    XDG_STATE_HOME="$legacy_home/.local/state" TMPDIR="$test_root/tmp" run_tools "$mock_bin:$PATH" "$repo_root" claude 2>&1); then
    :
else
    printf '%s\n' "$output" >&2
    exit 1
fi
legacy_version="$legacy_home/.claude/native/claude"
[ -L "$legacy_home/.local/bin/claude" ]
[ "$(readlink "$legacy_home/.local/bin/claude")" = "$legacy_version" ]
)
end_case

begin_case "claude custom launcher kept"
( set -e
custom_home="$test_root/custom-home"
mkdir -p "$custom_home/.local/bin" "$custom_home/.local/state/dl"
printf '%s\n' 'custom launcher' > "$custom_home/.local/bin/claude"
chmod +x "$custom_home/.local/bin/claude"
printf '%s\n' 'old-claude-test-etag' > "$custom_home/.local/state/dl/claude"
if output=$(HOME="$custom_home" XDG_DATA_HOME="$custom_home/.local/share" \
    XDG_STATE_HOME="$custom_home/.local/state" TMPDIR="$test_root/tmp" run_tools "$mock_bin:$PATH" "$repo_root" claude 2>&1); then
    :
else
    printf '%s\n' "$output" >&2
    exit 1
fi
[ "$(cat "$custom_home/.local/bin/claude")" = 'custom launcher' ]
)
end_case

begin_case "claude missing file warning"
( set -e
missing_file_home="$test_root/missing-file-home"
missing_file_bin="$test_root/missing-file-bin"
mkdir -p "$missing_file_home/.local/bin" "$missing_file_home/.local/state/dl" "$missing_file_bin"
printf '%s' 'legacy Claude binary' > "$missing_file_home/.local/bin/claude"
chmod +x "$missing_file_home/.local/bin/claude"
printf '%s\n' 'old-claude-test-etag' > "$missing_file_home/.local/state/dl/claude"
ln -s "$mock_bin/curl" "$missing_file_bin/curl"
ln -s "$mock_bin/uname" "$missing_file_bin/uname"
ln -s "$(command -v mkdir)" "$missing_file_bin/mkdir"
ln -s "$(command -v sed)" "$missing_file_bin/sed"
if output=$(HOME="$missing_file_home" XDG_DATA_HOME="$missing_file_home/.local/share" \
    XDG_STATE_HOME="$missing_file_home/.local/state" TMPDIR="$test_root/tmp" \
    run_tools "$missing_file_bin" "$repo_root" claude 2>&1); then
    :
else
    printf '%s\n' "$output" >&2
    exit 1
fi
case "$output" in
    *'file is required to identify the existing Claude launcher'*) ;;
    *) printf '%s\n' "$output" >&2; exit 1 ;;
esac
[ "$(cat "$missing_file_home/.local/bin/claude")" = 'legacy Claude binary' ]
)
end_case

begin_case "codex multi-tool run with hidden jaq"
( set -e
codex_home="$test_root/codex-home"
mv "$mock_bin/jaq" "$mock_bin/jaq.hidden"
if output=$(HOME="$codex_home" XDG_STATE_HOME="$codex_home/.local/state" \
    TMPDIR="$test_root/tmp" CODEX_SHA256="$CODEX_SHA256" CODEX_TAR="$test_root/codex.tar.gz" \
    DL_TEST_OS=Linux DL_TEST_ARCH=x86_64 DL_JAQ_MOCK="$mock_bin/jaq.hidden" \
    run_tools "$mock_bin:/usr/bin:/bin" "$repo_root" jaq codex muse 2>&1); then
    :
else
    printf '%s\n' "$output" >&2
    exit 1
fi
[ -x "$codex_home/.local/bin/jaq" ]
[ -L "$codex_home/.local/bin/codex" ]
[ -x "$codex_home/.local/bin/muse" ]
)
end_case

begin_case "codex uses jq when jaq is unavailable"
( set -e
jq_home="$test_root/codex-jq-home"
jq_bin="$test_root/jq-bin"
mkdir -p "$jq_bin"
cp "$mock_bin/jaq.hidden" "$jq_bin/jq"
chmod +x "$jq_bin/jq"
if output=$(HOME="$jq_home" XDG_STATE_HOME="$jq_home/.local/state" \
    TMPDIR="$test_root/tmp" CODEX_SHA256="$CODEX_SHA256" CODEX_TAR="$test_root/codex.tar.gz" \
    DL_TEST_OS=Linux DL_TEST_ARCH=x86_64 \
    run_tools "$jq_bin:$mock_bin:/usr/bin:/bin" "$repo_root" codex 2>&1); then
    :
else
    printf '%s\n' "$output" >&2
    exit 1
fi
[ -L "$jq_home/.local/bin/codex" ]
[ ! -e "$jq_home/.local/bin/jaq" ]
)
end_case

begin_case "release falls back to a musl-static asset"
( set -e
fz_home="$test_root/fz-home"
if output=$(HOME="$fz_home" XDG_STATE_HOME="$fz_home/.local/state" \
    TMPDIR="$test_root/tmp" DL_TEST_OS=Linux DL_TEST_ARCH=x86_64 \
    run_tools "$mock_bin:/usr/bin:/bin" "$repo_root" fz 2>&1); then
    :
else
    printf '%s\n' "$output" >&2
    exit 1
fi
case "$output" in
    *'Installed '"$fz_home"'/.local/bin/fz'*) ;;
    *) printf '%s\n' "$output" >&2; exit 1 ;;
esac
[ "$(cat "$fz_home/.local/bin/fz")" = 'fz-static-test-binary' ]
[ "$(cat "$fz_home/.local/state/dl/fz")" = 'fz-static-test-etag' ]
)
end_case

begin_case "shuck installs the release as shellcheck and stays current"
( set -e
shuck_home="$test_root/shuck-home"
if output=$(HOME="$shuck_home" XDG_STATE_HOME="$shuck_home/.local/state" \
    TMPDIR="$test_root/tmp" DL_TEST_OS=Darwin DL_TEST_ARCH=arm64 \
    run_tools "$mock_bin:/usr/bin:/bin" "$repo_root" shuck 2>&1); then
    :
else
    printf '%s\n' "$output" >&2
    exit 1
fi
case "$output" in
    *'Installed '"$shuck_home"'/.local/bin/shellcheck'*) ;;
    *) printf '%s\n' "$output" >&2; exit 1 ;;
esac
[ "$(cat "$shuck_home/.local/bin/shellcheck")" = 'shuck-test-binary' ]
[ "$(cat "$shuck_home/.local/state/dl/shellcheck")" = 'shuck-test-etag' ]
[ ! -e "$shuck_home/.local/bin/shuck" ]
if output=$(HOME="$shuck_home" XDG_STATE_HOME="$shuck_home/.local/state" \
    TMPDIR="$test_root/tmp" DL_TEST_OS=Darwin DL_TEST_ARCH=arm64 \
    run_tools "$mock_bin:/usr/bin:/bin" "$repo_root" shuck 2>&1); then
    :
else
    printf '%s\n' "$output" >&2
    exit 1
fi
case "$output" in
    *'shellcheck is current (release-shuck-test-1)'*) ;;
    *) printf '%s\n' "$output" >&2; exit 1 ;;
esac
shuck_linux_home="$test_root/shuck-linux-home"
if output=$(HOME="$shuck_linux_home" XDG_STATE_HOME="$shuck_linux_home/.local/state" \
    TMPDIR="$test_root/tmp" DL_TEST_OS=Linux DL_TEST_ARCH=x86_64 \
    run_tools "$mock_bin:/usr/bin:/bin" "$repo_root" shuck 2>&1); then
    :
else
    printf '%s\n' "$output" >&2
    exit 1
fi
[ "$(cat "$shuck_linux_home/.local/bin/shellcheck")" = 'shuck-static-test-binary' ]
[ "$(cat "$shuck_linux_home/.local/state/dl/shellcheck")" = 'shuck-static-test-etag' ]
)
end_case

begin_case "zzz installs the linux musl static release and stays current"
( set -e
    zzz_home="$test_root/zzz-home"
    if output=$(HOME="$zzz_home" XDG_STATE_HOME="$zzz_home/.local/state" \
        TMPDIR="$test_root/tmp" DL_TEST_OS=Linux DL_TEST_ARCH=x86_64 \
        run_tools "$mock_bin:/usr/bin:/bin" "$repo_root" zzz 2>&1); then
        :
    else
        printf '%s\n' "$output" >&2; exit 1
    fi
    case "$output" in
        *"Installed $zzz_home/.local/bin/zzz"*) ;;
        *) printf '%s\n' "$output" >&2; exit 1 ;;
    esac
    [ "$(cat "$zzz_home/.local/bin/zzz")" = 'zzz-test-binary' ]
    [ "$(cat "$zzz_home/.local/state/dl/zzz")" = 'zzz-test-etag' ]
    if output=$(HOME="$zzz_home" XDG_STATE_HOME="$zzz_home/.local/state" \
        TMPDIR="$test_root/tmp" DL_TEST_OS=Linux DL_TEST_ARCH=x86_64 \
        run_tools "$mock_bin:/usr/bin:/bin" "$repo_root" zzz 2>&1); then
        :
    else
        printf '%s\n' "$output" >&2; exit 1
    fi
    case "$output" in
        *'zzz is current (release-37544a545a89ce94721cba6a953fb18f26123ab3)'*) ;;
        *) printf '%s\n' "$output" >&2; exit 1 ;;
    esac
)
end_case

begin_case "zzz is a default target on Linux only"
( set -e
    zzz_list_home="$test_root/zzz-list-home"
    zzz_list=$(HOME="$zzz_list_home" DL_TEST_OS=Linux DL_TEST_ARCH=x86_64 \
        TMPDIR="$test_root/tmp" run_tools "$mock_bin:$PATH" "$repo_root" --list)
    printf '%s\n' "$zzz_list" | grep -qx zzz
    zzz_list=$(HOME="$zzz_list_home" DL_TEST_OS=Linux DL_TEST_ARCH=aarch64 \
        TMPDIR="$test_root/tmp" run_tools "$mock_bin:$PATH" "$repo_root" --list)
    printf '%s\n' "$zzz_list" | grep -qx zzz
    zzz_list=$(HOME="$zzz_list_home" DL_TEST_OS=Darwin DL_TEST_ARCH=arm64 \
        TMPDIR="$test_root/tmp" run_tools "$mock_bin:$PATH" "$repo_root" --list)
    if printf '%s\n' "$zzz_list" | grep -qx zzz; then
        printf 'zzz is a default target on macOS\n' >&2; exit 1
    fi
)
end_case

begin_case "zzz skips unsupported platforms"
( set -e
    zzz_darwin_home="$test_root/zzz-darwin-home"
    if HOME="$zzz_darwin_home" XDG_STATE_HOME="$zzz_darwin_home/.local/state" \
        TMPDIR="$test_root/tmp" DL_TEST_OS=Darwin DL_TEST_ARCH=arm64 \
        run_tools "$mock_bin:/usr/bin:/bin" "$repo_root" zzz >/dev/null 2>&1; then
        printf 'zzz installed on an unsupported platform\n' >&2; exit 1
    fi
    [ ! -e "$zzz_darwin_home/.local/bin/zzz" ]
    [ ! -e "$zzz_darwin_home/.local/state/dl/zzz" ]
)
end_case

begin_case "uv installs both launchers, stays current, and records ownership"
( set -e
    uv_home="$test_root/uv-home"
    if output=$(HOME="$uv_home" XDG_STATE_HOME="$uv_home/.local/state" \
        TMPDIR="$test_root/tmp" DL_TEST_OS=Linux DL_TEST_ARCH=x86_64 \
        run_tools "$mock_bin:/usr/bin:/bin" "$repo_root" uv 2>&1); then
        :
    else
        printf '%s\n' "$output" >&2; exit 1
    fi
    [ "$(cat "$uv_home/.local/bin/uv")" = 'uv-test-0.13.7' ]
    [ "$(cat "$uv_home/.local/bin/uvx")" = 'uvx-test-0.13.7' ]
    [ "$(cat "$uv_home/.local/state/dl/uv")" = 'uv-test-etag' ]
    [ "$(cat "$uv_home/.local/state/dl/uvx")" = 'uv-test-etag' ]
    if output=$(HOME="$uv_home" XDG_STATE_HOME="$uv_home/.local/state" \
        TMPDIR="$test_root/tmp" DL_TEST_OS=Linux DL_TEST_ARCH=x86_64 \
        run_tools "$mock_bin:/usr/bin:/bin" "$repo_root" uv 2>&1); then
        :
    else
        printf '%s\n' "$output" >&2; exit 1
    fi
    case "$output" in
        *'uv is current (0.13.7)'*) ;;
        *) printf '%s\n' "$output" >&2; exit 1 ;;
    esac
    uv_owned="$uv_home/.local/state/sync/dl-owned"
    mkdir -p "$(dirname "$uv_owned")"
    HOME="$uv_home" XDG_STATE_HOME="$uv_home/.local/state" DL_RECORD_OWNED=true \
        DL_OWNED_FILE="$uv_owned" TMPDIR="$test_root/tmp" \
        run_tools "$mock_bin:$PATH" "$repo_root"
    for uv_path in "$uv_home/.local/bin/uv" "$uv_home/.local/bin/uvx" \
        "$uv_home/.local/state/dl/uv" "$uv_home/.local/state/dl/uvx"; do
        awk -F '\t' -v path="$uv_path" \
            '$1 == "F" && $2 == path { found = 1 } END { exit !found }' "$uv_owned"
    done
)
end_case

begin_case "uv rejects a checksum mismatch and preserves the prior install"
( set -e
    uv_home="$test_root/uv-bad-home"
    if output=$(HOME="$uv_home" XDG_STATE_HOME="$uv_home/.local/state" \
        TMPDIR="$test_root/tmp" DL_TEST_OS=Linux DL_TEST_ARCH=x86_64 \
        run_tools "$mock_bin:/usr/bin:/bin" "$repo_root" uv 2>&1); then
        :
    else
        printf '%s\n' "$output" >&2; exit 1
    fi
    if output=$(HOME="$uv_home" XDG_STATE_HOME="$uv_home/.local/state" \
        TMPDIR="$test_root/tmp" DL_TEST_OS=Linux DL_TEST_ARCH=x86_64 \
        UV_TEST_BAD_SHA=true UV_TEST_ETAG=uv-test-etag-2 \
        run_tools "$mock_bin:/usr/bin:/bin" "$repo_root" uv 2>&1); then
        printf 'uv accepted a bad checksum\n' >&2; exit 1
    fi
    case "$output" in
        *'checksum mismatch'*) ;;
        *) printf '%s\n' "$output" >&2; exit 1 ;;
    esac
    [ "$(cat "$uv_home/.local/bin/uv")" = 'uv-test-0.13.7' ]
    [ "$(cat "$uv_home/.local/bin/uvx")" = 'uvx-test-0.13.7' ]
    [ "$(cat "$uv_home/.local/state/dl/uv")" = 'uv-test-etag' ]
    [ "$(cat "$uv_home/.local/state/dl/uvx")" = 'uv-test-etag' ]
)
end_case

begin_case "git install, current check, and bundle layout"
( set -e
git_home="$test_root/git-home"
if output=$(HOME="$git_home" XDG_STATE_HOME="$git_home/.local/state" \
    TMPDIR="$test_root/tmp" GIT_ZIP="$test_root/git.zip" GIT_SUMS="$test_root/git.SHA256SUMS" \
    run_tools "$mock_bin:$PATH" "$repo_root" git 2>&1); then
    :
else
    printf '%s\n' "$output" >&2
    exit 1
fi
case "$output" in
    *'Installed '"$git_home"'/.local/bin/git'*) ;;
    *) printf '%s\n' "$output" >&2; exit 1 ;;
esac
git_release="$git_home/.local/share/git/releases/${git_tag}-${git_triple}"
git_current="$git_home/.local/share/git/current"
[ -x "$git_release/git" ]
[ -x "$git_release/git-shell" ]
[ "$(readlink "$git_current")" = "$git_release" ]
[ "$(readlink "$git_home/.local/bin/git")" = "$git_current/git" ]
[ "$(readlink "$git_home/.local/bin/git-shell")" = "$git_current/git-shell" ]
for git_helper in git-upload-archive git-upload-pack git-receive-pack; do
    [ "$(readlink "$git_home/.local/bin/$git_helper")" = "$git_current/$git_helper" ]
    [ "$(readlink "$git_release/$git_helper")" = git ]
done
[ "$(cat "$git_home/.local/state/dl/git")" = 'git-test-etag' ]
git_exclude="$git_home/.local/share/git-core/templates/info/exclude"
[ -f "$git_exclude" ] && [ ! -L "$git_exclude" ]
grep -q 'exclude-from=.git/info/exclude' "$git_exclude"
rm -r "$git_home/.local/share/git-core"
if output=$(HOME="$git_home" XDG_STATE_HOME="$git_home/.local/state" \
    TMPDIR="$test_root/tmp" GIT_ZIP="$test_root/git.zip" GIT_SUMS="$test_root/git.SHA256SUMS" \
    run_tools "$mock_bin:$PATH" "$repo_root" git 2>&1); then
    :
else
    printf '%s\n' "$output" >&2
    exit 1
fi
case "$output" in
    *'git is current ('"$git_tag"')'*) ;;
    *) printf '%s\n' "$output" >&2; exit 1 ;;
esac
[ -f "$git_exclude" ]
)
end_case

begin_case "git checksum mismatch preserves prior install"
( set -e
git_bad_home="$test_root/git-bad-home"
git_old_tag=release-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
if output=$(HOME="$git_bad_home" XDG_STATE_HOME="$git_bad_home/.local/state" \
    TMPDIR="$test_root/tmp" GIT_ZIP="$test_root/git.zip" GIT_SUMS="$test_root/git.SHA256SUMS" \
    GIT_FEED_OLD=true run_tools "$mock_bin:$PATH" "$repo_root" git 2>&1); then
    :
else
    printf '%s\n' "$output" >&2
    exit 1
fi
git_bad_release="$git_bad_home/.local/share/git/releases/${git_old_tag}-${git_triple}"
git_bad_current="$git_bad_home/.local/share/git/current"
[ "$(readlink "$git_bad_current")" = "$git_bad_release" ]
[ "$(readlink "$git_bad_home/.local/bin/git")" = "$git_bad_current/git" ]
printf '%s  %s\n' '0000000000000000000000000000000000000000000000000000000000000000' "$git_asset" > "$test_root/git-bad.SHA256SUMS"
if output=$(HOME="$git_bad_home" XDG_STATE_HOME="$git_bad_home/.local/state" \
    TMPDIR="$test_root/tmp" GIT_ZIP="$test_root/git.zip" GIT_SUMS="$test_root/git-bad.SHA256SUMS" \
    run_tools "$mock_bin:$PATH" "$repo_root" git 2>&1); then
    printf '%s\n' "$output" >&2
    exit 1
fi
case "$output" in
    *'checksum mismatch'*) ;;
    *) printf '%s\n' "$output" >&2; exit 1 ;;
esac
[ "$(readlink "$git_bad_home/.local/bin/git")" = "$git_bad_current/git" ]
[ "$(readlink "$git_bad_home/.local/bin/git-shell")" = "$git_bad_current/git-shell" ]
for git_helper in git-upload-archive git-upload-pack git-receive-pack; do
    [ "$(readlink "$git_bad_home/.local/bin/$git_helper")" = "$git_bad_current/$git_helper" ]
done
[ "$(readlink "$git_bad_home/.local/share/git/current")" = "$git_bad_release" ]
[ "$(cat "$git_bad_home/.local/state/dl/git")" = 'git-test-etag-a' ]
[ "$(find "$git_bad_home/.local/share/git/releases" -mindepth 1 -maxdepth 1 | wc -l)" -eq 1 ]
)
end_case

begin_case "git update installs the new bundle"
( set -e
git_update_home="$test_root/git-update-home"
git_old_tag=release-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
if output=$(HOME="$git_update_home" XDG_STATE_HOME="$git_update_home/.local/state" \
    TMPDIR="$test_root/tmp" GIT_ZIP="$test_root/git.zip" GIT_SUMS="$test_root/git.SHA256SUMS" \
    GIT_FEED_OLD=true run_tools "$mock_bin:$PATH" "$repo_root" git 2>&1); then
    :
else
    printf '%s\n' "$output" >&2
    exit 1
fi
if output=$(HOME="$git_update_home" XDG_STATE_HOME="$git_update_home/.local/state" \
    TMPDIR="$test_root/tmp" GIT_ZIP="$test_root/git.zip" GIT_SUMS="$test_root/git.SHA256SUMS" \
    run_tools "$mock_bin:$PATH" "$repo_root" git 2>&1); then
    :
else
    printf '%s\n' "$output" >&2
    exit 1
fi
case "$output" in
    *'Installed '"$git_update_home"'/.local/bin/git'*) ;;
    *) printf '%s\n' "$output" >&2; exit 1 ;;
esac
git_new_release="$git_update_home/.local/share/git/releases/${git_tag}-${git_triple}"
git_old_release="$git_update_home/.local/share/git/releases/${git_old_tag}-${git_triple}"
git_update_current="$git_update_home/.local/share/git/current"
[ "$(readlink "$git_update_home/.local/bin/git")" = "$git_update_current/git" ]
[ "$(readlink "$git_update_home/.local/bin/git-shell")" = "$git_update_current/git-shell" ]
for git_helper in git-upload-archive git-upload-pack git-receive-pack; do
    [ "$(readlink "$git_update_home/.local/bin/$git_helper")" = "$git_update_current/$git_helper" ]
done
[ "$(readlink "$git_update_current")" = "$git_new_release" ]
[ "$(cat "$git_update_home/.local/state/dl/git")" = 'git-test-etag' ]
[ -x "$git_old_release/git" ]
if output=$(HOME="$git_update_home" XDG_STATE_HOME="$git_update_home/.local/state" \
    TMPDIR="$test_root/tmp" GIT_ZIP="$test_root/git.zip" GIT_SUMS="$test_root/git.SHA256SUMS" \
    run_tools "$mock_bin:$PATH" "$repo_root" git 2>&1); then
    :
else
    printf '%s\n' "$output" >&2
    exit 1
fi
case "$output" in
    *'git is current ('"$git_tag"')'*) ;;
    *) printf '%s\n' "$output" >&2; exit 1 ;;
esac
)
end_case

begin_case "git traversal archive is rejected with no partial state"
( set -e
git_evil_home="$test_root/git-evil-home"
if output=$(HOME="$git_evil_home" XDG_STATE_HOME="$git_evil_home/.local/state" \
    TMPDIR="$test_root/tmp" GIT_ZIP="$test_root/git.zip" GIT_SUMS="$test_root/git.SHA256SUMS" \
    GIT_UNZIP_LIST_FAIL=true run_tools "$mock_bin:$PATH" "$repo_root" git 2>&1); then
    printf '%s\n' "$output" >&2
    exit 1
fi
case "$output" in
    *'contains an invalid path'*) ;;
    *) printf '%s\n' "$output" >&2; exit 1 ;;
esac
[ ! -e "$git_evil_home/.local/bin/git" ]
[ ! -e "$git_evil_home/.local/state/dl/git" ]
[ ! -e "$git_evil_home/.local/share/git/releases/${git_tag}-${git_triple}" ]
)
end_case

begin_case "ssh install, current check, update, and bundle layout"
( set -e
ssh_home="$test_root/ssh-home"
ssh_env() {
    HOME="$ssh_home" XDG_STATE_HOME="$ssh_home/.local/state" TMPDIR="$test_root/tmp" \
        SSH_ZIP="$test_root/ssh.zip" SSH_SUMS="${ssh_sums:-$test_root/ssh.SHA256SUMS}" \
        SSH_FEED_OLD="${ssh_feed_old:-false}" run_tools "$mock_bin:$PATH" "$repo_root" ssh 2>&1
}
ssh_feed_old=true
output=$(ssh_env) || { printf '%s\n' "$output" >&2; exit 1; }
ssh_current="$ssh_home/.local/share/ssh/current"
[ "$(readlink "$ssh_current")" = "$ssh_home/.local/share/ssh/releases/${ssh_old_tag}-${git_triple}" ]
ssh_feed_old=false
output=$(ssh_env) || { printf '%s\n' "$output" >&2; exit 1; }
case "$output" in
    *'Installed '"$ssh_home"'/.local/bin/ssh'*) ;;
    *) printf '%s\n' "$output" >&2; exit 1 ;;
esac
ssh_release="$ssh_home/.local/share/ssh/releases/${ssh_tag}-${git_triple}"
[ "$(readlink "$ssh_current")" = "$ssh_release" ]
[ -x "$ssh_home/.local/share/ssh/releases/${ssh_old_tag}-${git_triple}/ssh" ]
for ssh_command in ssh ssh-keygen ssh-agent ssh-add sftp scp; do
    [ -x "$ssh_release/$ssh_command" ]
    [ "$(readlink "$ssh_home/.local/bin/$ssh_command")" = "$ssh_current/$ssh_command" ]
done
[ "$(cat "$ssh_home/.local/state/dl/ssh")" = 'ssh-test-etag' ]
output=$(ssh_env) || { printf '%s\n' "$output" >&2; exit 1; }
case "$output" in
    *'ssh is current ('"$ssh_tag"')'*) ;;
    *) printf '%s\n' "$output" >&2; exit 1 ;;
esac
)
end_case

begin_case "ssh failures preserve the prior install"
( set -e
ssh_bad_home="$test_root/ssh-bad-home"
ssh_bad_env() {
    HOME="$ssh_bad_home" XDG_STATE_HOME="$ssh_bad_home/.local/state" TMPDIR="$test_root/tmp" \
        SSH_ZIP="$test_root/ssh.zip" SSH_SUMS="${ssh_bad_sums:-$test_root/ssh.SHA256SUMS}" \
        SSH_FEED_OLD="${ssh_bad_feed_old:-false}" run_tools "$mock_bin:$PATH" "$repo_root" ssh 2>&1
}
ssh_bad_feed_old=true
output=$(ssh_bad_env) || { printf '%s\n' "$output" >&2; exit 1; }
ssh_bad_feed_old=false
ssh_bad_release="$ssh_bad_home/.local/share/ssh/releases/${ssh_old_tag}-${git_triple}"
ssh_bad_current="$ssh_bad_home/.local/share/ssh/current"
ssh_bad_sums="$test_root/ssh-bad.SHA256SUMS"
if output=$(ssh_bad_env); then
    printf '%s\n' "$output" >&2
    exit 1
fi
case "$output" in
    *'checksum mismatch'*) ;;
    *) printf '%s\n' "$output" >&2; exit 1 ;;
esac
ssh_bad_sums=
if output=$(HOME="$ssh_bad_home" XDG_STATE_HOME="$ssh_bad_home/.local/state" TMPDIR="$test_root/tmp" \
    SSH_ZIP="$test_root/ssh.zip" SSH_SUMS="$test_root/ssh.SHA256SUMS" \
    SSH_UNZIP_LIST_FAIL=true run_tools "$mock_bin:$PATH" "$repo_root" ssh 2>&1); then
    printf '%s\n' "$output" >&2
    exit 1
fi
case "$output" in
    *'contains an invalid path'*) ;;
    *) printf '%s\n' "$output" >&2; exit 1 ;;
esac
if output=$(HOME="$ssh_bad_home" XDG_STATE_HOME="$ssh_bad_home/.local/state" TMPDIR="$test_root/tmp" \
    SSH_ZIP="$test_root/ssh.zip" SSH_SUMS="$test_root/ssh.SHA256SUMS" \
    SSH_UNZIP_EXTRACT_FAIL=true run_tools "$mock_bin:$PATH" "$repo_root" ssh 2>&1); then
    printf '%s\n' "$output" >&2
    exit 1
fi
[ "$(readlink "$ssh_bad_current")" = "$ssh_bad_release" ]
for ssh_command in ssh ssh-keygen ssh-agent ssh-add sftp scp; do
    [ "$(readlink "$ssh_bad_home/.local/bin/$ssh_command")" = "$ssh_bad_current/$ssh_command" ]
done
[ "$(cat "$ssh_bad_home/.local/state/dl/ssh")" = 'ssh-test-etag-a' ]
[ "$(find "$ssh_bad_home/.local/share/ssh/releases" -mindepth 1 -maxdepth 1 | wc -l)" -eq 1 ]
)
end_case

begin_case "ssh refuses to replace an unmanaged launcher and stays out of the default set"
( set -e
ssh_own_home="$test_root/ssh-own-home"
mkdir -p "$ssh_own_home/.local/bin"
printf '%s\n' '#!/bin/sh' 'exit 0' > "$ssh_own_home/.local/bin/ssh"
chmod +x "$ssh_own_home/.local/bin/ssh"
if output=$(HOME="$ssh_own_home" XDG_STATE_HOME="$ssh_own_home/.local/state" TMPDIR="$test_root/tmp" \
    SSH_ZIP="$test_root/ssh.zip" SSH_SUMS="$test_root/ssh.SHA256SUMS" \
    run_tools "$mock_bin:$PATH" "$repo_root" ssh 2>&1); then
    printf '%s\n' "$output" >&2
    exit 1
fi
case "$output" in
    *'is not a dl-managed symlink'*) ;;
    *) printf '%s\n' "$output" >&2; exit 1 ;;
esac
[ ! -L "$ssh_own_home/.local/bin/ssh" ]
[ ! -e "$ssh_own_home/.local/share/ssh/current" ]
default_targets=$(sed -n '/^if \[ \$# -eq 0 \]; then/,/^fi$/p' "$repo_root/tools/sync/install.sh")
case "$default_targets" in
    *' ssh '*) printf 'ssh appeared in the default dl targets\n' >&2; exit 1 ;;
esac
)
end_case

begin_case "oxish installs opt-in, updates atomically, and failures keep the prior install"
( set -e
oxish_home="$test_root/oxish-home"
oxish_run() {
    HOME="$oxish_home" XDG_STATE_HOME="$oxish_home/.local/state" TMPDIR="$test_root/tmp" \
        OXISH_ZIP="$test_root/oxish.zip" OXISH_SUMS="${oxish_sums:-$test_root/oxish.SHA256SUMS}" \
        SSH_FEED_OLD="${oxish_feed_old:-false}" OXISH_UNZIP_EXTRACT_FAIL="${oxish_extract_fail:-false}" \
        run_tools "$mock_bin:$PATH" "$repo_root" oxish 2>&1
}
oxish_feed_old=true
output=$(oxish_run) || { printf '%s\n' "$output" >&2; exit 1; }
oxish_current="$oxish_home/.local/share/oxish/current"
oxish_old="$oxish_home/.local/share/oxish/releases/${ssh_old_tag}-${git_triple}"
[ "$(readlink "$oxish_current")" = "$oxish_old" ]
oxish_feed_old=false
oxish_sums="$test_root/oxish-bad.SHA256SUMS"
if output=$(oxish_run); then printf '%s\n' "$output" >&2; exit 1; fi
case "$output" in *'checksum mismatch'*) ;; *) printf '%s\n' "$output" >&2; exit 1 ;; esac
oxish_sums=
oxish_extract_fail=true
if output=$(oxish_run); then printf '%s\n' "$output" >&2; exit 1; fi
oxish_extract_fail=false
[ "$(readlink "$oxish_current")" = "$oxish_old" ]
for oxish_command in oxish-server oxish-session; do
    [ "$(readlink "$oxish_home/.local/bin/$oxish_command")" = "$oxish_current/bin/$oxish_command" ]
done
[ "$(cat "$oxish_home/.local/state/dl/oxish-server")" = 'oxish-test-etag-a' ]
[ "$(find "$oxish_home/.local/share/oxish/releases" -mindepth 1 -maxdepth 1 | wc -l)" -eq 1 ]
output=$(oxish_run) || { printf '%s\n' "$output" >&2; exit 1; }
case "$output" in *'Installed '"$oxish_home"'/.local/bin/oxish-server'*) ;; *) printf '%s\n' "$output" >&2; exit 1 ;; esac
oxish_new="$oxish_home/.local/share/oxish/releases/${ssh_tag}-${git_triple}"
[ "$(readlink "$oxish_current")" = "$oxish_new" ]
[ -x "$oxish_old/bin/oxish-server" ]
[ -x "$oxish_new/bin/oxish-session" ]
output=$(oxish_run) || { printf '%s\n' "$output" >&2; exit 1; }
case "$output" in *'oxish is current ('"$ssh_tag"')'*) ;; *) printf '%s\n' "$output" >&2; exit 1 ;; esac
default_targets=$(sed -n '/^if \[ \$# -eq 0 \]; then/,/^fi$/p' "$repo_root/tools/sync/install.sh")
case "$default_targets" in
    *' oxish '*|*' ssh '*) printf 'ssh or oxish appeared in the default dl targets\n' >&2; exit 1 ;;
esac
)
end_case

begin_case "git extract failure leaves no partial state"
( set -e
git_extract_home="$test_root/git-extract-home"
if output=$(HOME="$git_extract_home" XDG_STATE_HOME="$git_extract_home/.local/state" \
    TMPDIR="$test_root/tmp" GIT_ZIP="$test_root/git.zip" GIT_SUMS="$test_root/git.SHA256SUMS" \
    GIT_UNZIP_EXTRACT_FAIL=true run_tools "$mock_bin:$PATH" "$repo_root" git 2>&1); then
    printf '%s\n' "$output" >&2
    exit 1
fi
case "$output" in
    *'could not be extracted'*) ;;
    *) printf '%s\n' "$output" >&2; exit 1 ;;
esac
[ ! -e "$git_extract_home/.local/bin/git" ]
[ ! -e "$git_extract_home/.local/state/dl/git" ]
[ ! -e "$git_extract_home/.local/share/git/releases/${git_tag}-${git_triple}" ]
)
end_case

begin_case "git unmanaged launcher is preserved"
( set -e
git_rogue_home="$test_root/git-rogue-home"
mkdir -p "$git_rogue_home/.local/bin" "$git_rogue_home/.local/state/dl"
printf '%s\n' '#!/bin/sh' 'exit 0' > "$git_rogue_home/.local/bin/git"
chmod +x "$git_rogue_home/.local/bin/git"
if output=$(HOME="$git_rogue_home" XDG_STATE_HOME="$git_rogue_home/.local/state" \
    TMPDIR="$test_root/tmp" GIT_ZIP="$test_root/git.zip" GIT_SUMS="$test_root/git.SHA256SUMS" \
    run_tools "$mock_bin:$PATH" "$repo_root" git 2>&1); then
    printf '%s\n' "$output" >&2
    exit 1
fi
case "$output" in
    *'is not a dl-managed symlink'*) ;;
    *) printf '%s\n' "$output" >&2; exit 1 ;;
esac
[ ! -L "$git_rogue_home/.local/bin/git" ]
[ "$(cat "$git_rogue_home/.local/bin/git")" = '#!/bin/sh
exit 0' ]
[ ! -e "$git_rogue_home/.local/state/dl/git" ]
)
end_case

begin_case "git unmanaged symlink is preserved"
( set -e
git_symlink_home="$test_root/git-symlink-home"
mkdir -p "$git_symlink_home/.local/bin" "$git_symlink_home/.local/state/dl"
printf '%s\n' '#!/bin/sh' 'exit 0' > "$test_root/git-symlink-rogue"
chmod +x "$test_root/git-symlink-rogue"
ln -s "$test_root/git-symlink-rogue" "$git_symlink_home/.local/bin/git"
if output=$(HOME="$git_symlink_home" XDG_STATE_HOME="$git_symlink_home/.local/state" \
    TMPDIR="$test_root/tmp" GIT_ZIP="$test_root/git.zip" GIT_SUMS="$test_root/git.SHA256SUMS" \
    run_tools "$mock_bin:$PATH" "$repo_root" git 2>&1); then
    printf '%s\n' "$output" >&2
    exit 1
fi
case "$output" in
    *'is not a dl-managed symlink'*) ;;
    *) printf '%s\n' "$output" >&2; exit 1 ;;
esac
[ "$(readlink "$git_symlink_home/.local/bin/git")" = "$test_root/git-symlink-rogue" ]
[ ! -e "$git_symlink_home/.local/state/dl/git" ]
[ ! -e "$git_symlink_home/.local/share/git/releases" ]
)
end_case

begin_case "git drifted launcher is repaired"
( set -e
git_drift_home="$test_root/git-drift-home"
if output=$(HOME="$git_drift_home" XDG_STATE_HOME="$git_drift_home/.local/state" \
    TMPDIR="$test_root/tmp" GIT_ZIP="$test_root/git.zip" GIT_SUMS="$test_root/git.SHA256SUMS" \
    run_tools "$mock_bin:$PATH" "$repo_root" git 2>&1); then
    :
else
    printf '%s\n' "$output" >&2
    exit 1
fi
git_drift_release="$git_drift_home/.local/share/git/releases/${git_tag}-${git_triple}"
git_drift_current="$git_drift_home/.local/share/git/current"
ln -sfn "$git_drift_release/git" "$git_drift_home/.local/bin/git-shell"
if output=$(HOME="$git_drift_home" XDG_STATE_HOME="$git_drift_home/.local/state" \
    TMPDIR="$test_root/tmp" GIT_ZIP="$test_root/git.zip" GIT_SUMS="$test_root/git.SHA256SUMS" \
    run_tools "$mock_bin:$PATH" "$repo_root" git 2>&1); then
    :
else
    printf '%s\n' "$output" >&2
    exit 1
fi
case "$output" in
    *'git is current ('"$git_tag"')'*) ;;
    *) printf '%s\n' "$output" >&2; exit 1 ;;
esac
case "$output" in
    *'missing ]'*) printf '%s\n' "$output" >&2; exit 1 ;;
esac
[ "$(readlink "$git_drift_home/.local/bin/git-shell")" = "$git_drift_current/git-shell" ]
[ "$(readlink "$git_drift_current")" = "$git_drift_release" ]
)
end_case

begin_case "player macOS install and current check"
( set -e
player_home="$test_root/player-home"
player_apps="$player_home/Applications"
if output=$(HOME="$player_home" PLAYER_APPLICATIONS_DIR="$player_apps" \
    DL_TEST_OS=Darwin DL_TEST_ARCH=arm64 TMPDIR="$test_root/tmp" \
    run_tools "$mock_bin:$PATH" "$repo_root" player 2>&1); then
    :
else
    printf '%s\n' "$output" >&2
    exit 1
fi
[ -x "$player_apps/Player.app/Contents/MacOS/player" ]
[ "$(readlink "$player_home/.local/bin/player")" \
    = "$player_apps/Player.app/Contents/MacOS/player" ]
[ "$(cat "$player_home/.local/state/dl/player")" = v0.41.0:player-test-etag ]
case "$output" in
    *"Installed $player_apps/Player.app (v0.41.0)"*) ;;
    *) printf '%s\n' "$output" >&2; exit 1 ;;
esac
if output=$(HOME="$player_home" PLAYER_APPLICATIONS_DIR="$player_apps" \
    DL_TEST_OS=Darwin DL_TEST_ARCH=arm64 TMPDIR="$test_root/tmp" \
    run_tools "$mock_bin:$PATH" "$repo_root" player 2>&1); then
    :
else
    printf '%s\n' "$output" >&2
    exit 1
fi
case "$output" in
    *'player is current (v0.41.0)'*) ;;
    *) printf '%s\n' "$output" >&2; exit 1 ;;
esac
)
end_case

begin_case "player macOS refuses an unmanaged app or launcher"
( set -e
player_home="$test_root/player-collision-home"
player_apps="$player_home/Applications"
mkdir -p "$player_apps/Player.app" "$player_home/.local/bin"
printf '%s\n' sentinel > "$player_apps/Player.app/keep"
printf '%s\n' '#!/bin/sh' 'exit 0' > "$player_home/.local/bin/player"
chmod +x "$player_home/.local/bin/player"
if HOME="$player_home" PLAYER_APPLICATIONS_DIR="$player_apps" \
    DL_TEST_OS=Darwin DL_TEST_ARCH=arm64 TMPDIR="$test_root/tmp" \
    run_tools "$mock_bin:$PATH" "$repo_root" player >/dev/null 2>&1; then
    printf '%s\n' 'player replaced an unmanaged install' >&2
    exit 1
fi
[ "$(cat "$player_apps/Player.app/keep")" = sentinel ]
[ -f "$player_home/.local/bin/player" ]
[ ! -L "$player_home/.local/bin/player" ]
[ ! -e "$player_home/.local/state/dl/player" ]
)
end_case

begin_case "player rejects a checksum mismatch"
( set -e
player_home="$test_root/player-bad-home"
player_apps="$player_home/Applications"
if HOME="$player_home" PLAYER_APPLICATIONS_DIR="$player_apps" \
    PLAYER_TEST_BAD_SUMS=true DL_TEST_OS=Darwin DL_TEST_ARCH=arm64 \
    TMPDIR="$test_root/tmp" \
    run_tools "$mock_bin:$PATH" "$repo_root" player >/dev/null 2>&1; then
    printf '%s\n' 'player accepted a checksum mismatch' >&2
    exit 1
fi
[ ! -e "$player_apps/Player.app" ]
[ ! -e "$player_home/.local/bin/player" ]
[ ! -e "$player_home/.local/state/dl/player" ]
)
end_case

begin_case "player records ownership"
( set -e
player_home="$test_root/player-own-home"
player_apps="$player_home/Applications"
if HOME="$player_home" PLAYER_APPLICATIONS_DIR="$player_apps" \
    DL_TEST_OS=Darwin DL_TEST_ARCH=arm64 TMPDIR="$test_root/tmp" \
    run_tools "$mock_bin:$PATH" "$repo_root" player >/dev/null 2>&1; then
    :
else
    exit 1
fi
owned="$player_home/.local/state/sync/dl-owned"
mkdir -p "$(dirname "$owned")"
HOME="$player_home" PLAYER_APPLICATIONS_DIR="$player_apps" \
    DL_RECORD_OWNED=true DL_OWNED_FILE="$owned" \
    DL_TEST_OS=Darwin DL_TEST_ARCH=arm64 TMPDIR="$test_root/tmp" \
    run_tools "$mock_bin:$PATH" "$repo_root" player
awk -F '\t' -v path="$player_apps/Player.app" \
    '$1 == "D" && $2 == path { found = 1 } END { exit !found }' "$owned"
for owned_file in "$player_home/.local/bin/player" \
    "$player_home/.local/state/dl/player"; do
    awk -F '\t' -v path="$owned_file" \
        '$1 == "F" && $2 == path { found = 1 } END { exit !found }' "$owned"
done
)
end_case

begin_case "player Linux install and current check"
( set -e
player_home="$test_root/player-linux-home"
if output=$(HOME="$player_home" DL_TEST_OS=Linux DL_TEST_ARCH=x86_64 \
    TMPDIR="$test_root/tmp" \
    run_tools "$mock_bin:$PATH" "$repo_root" player 2>&1); then
    :
else
    printf '%s\n' "$output" >&2
    exit 1
fi
[ -x "$player_home/.local/bin/player" ]
[ "$(HOME="$player_home" "$player_home/.local/bin/player")" = player-test ]
[ "$(cat "$player_home/.local/state/dl/player")" = v0.41.0:player-test-etag ]
case "$output" in
    *"Installed $player_home/.local/bin/player"*) ;;
    *) printf '%s\n' "$output" >&2; exit 1 ;;
esac
if output=$(HOME="$player_home" DL_TEST_OS=Linux DL_TEST_ARCH=x86_64 \
    TMPDIR="$test_root/tmp" \
    run_tools "$mock_bin:$PATH" "$repo_root" player 2>&1); then
    :
else
    printf '%s\n' "$output" >&2
    exit 1
fi
case "$output" in
    *'player is current (v0.41.0)'*) ;;
    *) printf '%s\n' "$output" >&2; exit 1 ;;
esac
)
end_case

begin_case "player skips an unsupported platform"
( set -e
player_home="$test_root/player-arch-home"
if HOME="$player_home" DL_TEST_OS=Linux DL_TEST_ARCH=aarch64 \
    TMPDIR="$test_root/tmp" \
    run_tools "$mock_bin:$PATH" "$repo_root" player >/dev/null 2>&1; then
    printf '%s\n' 'player installed on an unsupported platform' >&2
    exit 1
fi
[ ! -e "$player_home/.local/bin/player" ]
[ ! -e "$player_home/.local/state/dl/player" ]
)
end_case

cat > "$mock_bin/mv" <<'EOF'
#!/bin/sh
if [ -n "${DL_TEST_MV_FAIL-}" ]; then
    case "$*" in
        *"$DL_TEST_MV_FAIL"*) exit 1 ;;
    esac
fi
case "$1" in
    -fh|-fT)
        shift
        if [ "$(/usr/bin/uname -s)" = Darwin ]; then
            set -- -fh "$@"
        else
            set -- -fT "$@"
        fi
        ;;
esac
exec /bin/mv "$@"
EOF
chmod +x "$mock_bin/mv"

ff_run() {
    _ff_home=$1
    _ff_with=$2
    _ff_os=$3
    _ff_arch=$4
    shift 4
    HOME="$_ff_home" XDG_STATE_HOME="$_ff_home/.local/state" TMPDIR="$test_root/tmp" \
        FFMPEG_ROOT="$_ff_with" DL_TEST_OS="$_ff_os" DL_TEST_ARCH="$_ff_arch" \
        run_tools "$mock_bin:$PATH" "$repo_root" "$@" 2>&1
}

ff_ok() {
    if ff_out=$(ff_run "$@"); then return 0; fi
    printf '%s\n' "$ff_out" >&2
    return 1
}

ff_fails() {
    if ff_out=$(ff_run "$@"); then
        printf '%s\n' "$ff_out" >&2
        return 1
    fi
    return 0
}

ff_said() {
    case "$ff_out" in
        *"$1"*) return 0 ;;
    esac
    printf 'missing %s in:\n%s\n' "$1" "$ff_out" >&2
    return 1
}

ff_owns() {
    awk -F '\t' -v kind="$2" -v path="$3" \
        '$1 == kind && $2 == path { found = 1 } END { exit !found }' "$1"
}

ff_installed_as() {
    [ "$("$1/.local/bin/ffmpeg" -version)" = "ffmpeg $2 $3" ]
    [ "$("$1/.local/bin/ffprobe" -version)" = "ffprobe $2 $3" ]
    [ "$(readlink "$1/.local/bin/ffmpeg")" = "$1/.local/share/ffmpeg/current/bin/ffmpeg" ]
    [ "$(readlink "$1/.local/bin/ffprobe")" = "$1/.local/share/ffmpeg/current/bin/ffprobe" ]
    [ "$(readlink "$1/.local/share/ffmpeg/current")" = "$1/.local/share/ffmpeg/releases/$2-$3" ]
}

begin_case "ffmpeg maps each supported target to its musl or darwin tools archive"
( set -e
for ff_case in Darwin:aarch64:aarch64-apple-darwin Linux:x86_64:x86_64-unknown-linux-musl Linux:aarch64:aarch64-unknown-linux-musl; do
    ff_case_os=${ff_case%%:*}
    ff_case_rest=${ff_case#*:}
    ff_case_arch=${ff_case_rest%%:*}
    ff_case_triple=${ff_case_rest#*:}
    ff_map_home="$test_root/ff-map-$ff_case_arch-$ff_case_os"
    ff_ok "$ff_map_home" "$ff_root_b" "$ff_case_os" "$ff_case_arch" ffmpeg
    ff_installed_as "$ff_map_home" "$ff_tag" "$ff_case_triple"
done
for ff_case in Darwin:x86_64 Linux:armv7l Linux:riscv64; do
    ff_bad_home="$test_root/ff-unsupported-${ff_case%%:*}-${ff_case#*:}"
    ff_fails "$ff_bad_home" "$ff_root_b" "${ff_case%%:*}" "${ff_case#*:}" ffmpeg
    ff_said 'no ffmpeg-build release'
    [ ! -e "$ff_bad_home/.local/bin/ffmpeg" ]
    [ ! -e "$ff_bad_home/.local/bin/ffprobe" ]
    [ ! -e "$ff_bad_home/.local/state/dl/ffmpeg" ]
    [ ! -e "$ff_bad_home/.local/share/ffmpeg" ]
done
)
end_case

begin_case "ffmpeg installs both commands from the newest release and repeats as current"
( set -e
ff_home="$test_root/ff-install-home"
ff_owned="$ff_home/.local/state/sync/dl-owned"
mkdir -p "$(dirname "$ff_owned")"
DL_OWNED_FILE="$ff_owned" ff_ok "$ff_home" "$ff_root_b" Linux x86_64 ffmpeg
ff_said "Installed $ff_home/.local/bin/ffmpeg and $ff_home/.local/bin/ffprobe"
ff_installed_as "$ff_home" "$ff_tag" x86_64-unknown-linux-musl
ff_release="$ff_home/.local/share/ffmpeg/releases/${ff_tag}-x86_64-unknown-linux-musl"
[ -f "$ff_release/share/ffmpeg-build/manifest.json" ]
[ ! -e "$ff_home/.local/share/ffmpeg/releases/20261105-rc1-x86_64-unknown-linux-musl" ]
case "$(cat "$ff_home/.local/state/dl/ffmpeg")" in
    "$ff_tag":ffmpeg-etag-*) ;;
    *) printf 'bad state record\n' >&2; exit 1 ;;
esac
ff_owns "$ff_owned" D "$ff_release"
ff_owns "$ff_owned" F "$ff_home/.local/share/ffmpeg/current"
ff_owns "$ff_owned" F "$ff_home/.local/bin/ffmpeg"
ff_owns "$ff_owned" F "$ff_home/.local/bin/ffprobe"
ff_owns "$ff_owned" F "$ff_home/.local/state/dl/ffmpeg"
DL_OWNED_FILE="$ff_owned" ff_ok "$ff_home" "$ff_root_b" Linux x86_64 ffmpeg
ff_said "ffmpeg is current ($ff_tag)"
ff_installed_as "$ff_home" "$ff_tag" x86_64-unknown-linux-musl
[ "$(printf '%s\n' "$ff_home"/.local/share/ffmpeg/releases/* | wc -l)" -eq 1 ]
)
end_case

begin_case "ffmpeg upgrade promotes the new pair and keeps the previous release"
( set -e
ff_home="$test_root/ff-upgrade-home"
ff_ok "$ff_home" "$ff_root_a" Darwin aarch64 ffmpeg
ff_installed_as "$ff_home" "$ff_tag_old" aarch64-apple-darwin
ff_ok "$ff_home" "$ff_root_b" Darwin aarch64 ffmpeg
ff_said Installed
ff_installed_as "$ff_home" "$ff_tag" aarch64-apple-darwin
[ -x "$ff_home/.local/share/ffmpeg/releases/${ff_tag_old}-aarch64-apple-darwin/bin/ffprobe" ]
case "$(cat "$ff_home/.local/state/dl/ffmpeg")" in
    "$ff_tag":*) ;;
    *) printf 'state not updated\n' >&2; exit 1 ;;
esac
)
end_case

begin_case "ffmpeg repairs a missing launcher of the pair"
( set -e
ff_home="$test_root/ff-repair-home"
ff_ok "$ff_home" "$ff_root_b" Linux aarch64 ffmpeg
rm "$ff_home/.local/bin/ffprobe"
ff_ok "$ff_home" "$ff_root_b" Linux aarch64 ffmpeg
ff_said Repaired
ff_installed_as "$ff_home" "$ff_tag" aarch64-unknown-linux-musl
rm "$ff_home/.local/bin/ffmpeg"
ff_ok "$ff_home" "$ff_root_b" Linux aarch64 ffmpeg
ff_installed_as "$ff_home" "$ff_tag" aarch64-unknown-linux-musl
ff_ok "$ff_home" "$ff_root_b" Linux aarch64 ffmpeg
ff_said "ffmpeg is current ($ff_tag)"
)
end_case

begin_case "ffmpeg failures keep the previous working pair"
( set -e
ff_home="$test_root/ff-preserve-home"
ff_ok "$ff_home" "$ff_root_a" Linux x86_64 ffmpeg
ff_state=$(cat "$ff_home/.local/state/dl/ffmpeg")
for ff_variant in "$ff_root_bad|checksum mismatch" "$ff_root_garbage|could not be extracted" "$ff_root_smoke|working ffmpeg and ffprobe" "$ff_root_top|invalid path"; do
    ff_fails "$ff_home" "${ff_variant%%|*}" Linux x86_64 ffmpeg
    ff_said "${ff_variant#*|}"
    ff_installed_as "$ff_home" "$ff_tag_old" x86_64-unknown-linux-musl
    [ "$(cat "$ff_home/.local/state/dl/ffmpeg")" = "$ff_state" ]
    [ "$(printf '%s\n' "$ff_home"/.local/share/ffmpeg/releases/* | wc -l)" -eq 1 ]
done
ff_fresh="$test_root/ff-preserve-fresh-home"
ff_fails "$ff_fresh" "$ff_root_bad" Linux x86_64 ffmpeg
[ ! -e "$ff_fresh/.local/bin/ffmpeg" ]
[ ! -e "$ff_fresh/.local/bin/ffprobe" ]
[ ! -e "$ff_fresh/.local/share/ffmpeg/current" ]
[ ! -e "$ff_fresh/.local/state/dl/ffmpeg" ]
)
end_case

begin_case "ffmpeg leaves unmanaged launchers and release files alone"
( set -e
ff_home="$test_root/ff-unmanaged-home"
mkdir -p "$ff_home/.local/bin"
printf 'mine\n' > "$ff_home/.local/bin/ffprobe"
chmod +x "$ff_home/.local/bin/ffprobe"
ff_fails "$ff_home" "$ff_root_b" Linux x86_64 ffmpeg
ff_said 'is not a dl-managed symlink'
[ "$(cat "$ff_home/.local/bin/ffprobe")" = mine ]
[ ! -e "$ff_home/.local/bin/ffmpeg" ]
[ ! -e "$ff_home/.local/share/ffmpeg/current" ]
[ ! -e "$ff_home/.local/state/dl/ffmpeg" ]
ff_other="$test_root/ff-unmanaged-other-home"
mkdir -p "$ff_other/.local/bin" "$ff_other/bin"
printf 'brew\n' > "$ff_other/bin/ffmpeg"
ln -s "$ff_other/bin/ffmpeg" "$ff_other/.local/bin/ffmpeg"
ff_fails "$ff_other" "$ff_root_b" Darwin aarch64 ffmpeg
[ "$(readlink "$ff_other/.local/bin/ffmpeg")" = "$ff_other/bin/ffmpeg" ]
[ ! -e "$ff_other/.local/bin/ffprobe" ]
ff_keep="$test_root/ff-unmanaged-keep-home"
ff_ok "$ff_keep" "$ff_root_a" Linux x86_64 ffmpeg
mkdir -p "$ff_keep/.local/share/ffmpeg/releases/mine"
printf 'mine\n' > "$ff_keep/.local/share/ffmpeg/releases/mine/note"
printf 'mine\n' > "$ff_keep/.local/share/ffmpeg/note"
ff_ok "$ff_keep" "$ff_root_b" Linux x86_64 ffmpeg
[ "$(cat "$ff_keep/.local/share/ffmpeg/releases/mine/note")" = mine ]
[ "$(cat "$ff_keep/.local/share/ffmpeg/note")" = mine ]
ff_installed_as "$ff_keep" "$ff_tag" x86_64-unknown-linux-musl
ff_clash="$test_root/ff-unmanaged-current-home"
mkdir -p "$ff_clash/.local/share/ffmpeg/current"
printf 'mine\n' > "$ff_clash/.local/share/ffmpeg/current/note"
ff_fails "$ff_clash" "$ff_root_b" Linux x86_64 ffmpeg
[ "$(cat "$ff_clash/.local/share/ffmpeg/current/note")" = mine ]
[ ! -e "$ff_clash/.local/bin/ffmpeg" ]
)
end_case

begin_case "ffmpeg ownership is recorded for both launchers, the release, and current"
( set -e
ff_home="$test_root/ff-record-home"
ff_owned="$ff_home/.local/state/sync/dl-owned"
ff_ok "$ff_home" "$ff_root_b" Linux x86_64 ffmpeg
mkdir -p "$(dirname "$ff_owned")"
DL_RECORD_OWNED=true DL_OWNED_FILE="$ff_owned" ff_ok "$ff_home" "$ff_root_b" Linux x86_64
ff_owns "$ff_owned" D "$ff_home/.local/share/ffmpeg/releases/${ff_tag}-x86_64-unknown-linux-musl"
ff_owns "$ff_owned" F "$ff_home/.local/share/ffmpeg/current"
ff_owns "$ff_owned" F "$ff_home/.local/bin/ffmpeg"
ff_owns "$ff_owned" F "$ff_home/.local/bin/ffprobe"
ff_owns "$ff_owned" F "$ff_home/.local/state/dl/ffmpeg"
)
end_case

begin_case "ffmpeg is a default tool on the three supported targets only, as one pair entry"
( set -e
for ff_case in Darwin:aarch64 Linux:x86_64 Linux:aarch64; do
    ff_list=$(HOME="$test_root/ff-list-home" DL_TEST_OS="${ff_case%%:*}" DL_TEST_ARCH="${ff_case#*:}" \
        TMPDIR="$test_root/tmp" run_tools "$mock_bin:$PATH" "$repo_root" --list)
    [ "$(printf '%s\n' "$ff_list" | grep -cx ffmpeg)" -eq 1 ]
    if printf '%s\n' "$ff_list" | grep -qx ffprobe; then exit 1; fi
done
ff_list=$(HOME="$test_root/ff-list-home" DL_TEST_OS=Darwin DL_TEST_ARCH=x86_64 \
    TMPDIR="$test_root/tmp" run_tools "$mock_bin:$PATH" "$repo_root" --list)
if printf '%s\n' "$ff_list" | grep -qx ffmpeg; then exit 1; fi
)
end_case

begin_case "ffmpeg discovery chooses the newest valid tag and ignores prerelease-looking tags"
( set -e
ff_home="$test_root/ff-discovery-home"
ff_ok "$ff_home" "$ff_root_b" Linux x86_64 ffmpeg
ff_installed_as "$ff_home" 20261104-r10 x86_64-unknown-linux-musl
ff_only="$test_root/ff-root-only-prerelease"
mkdir -p "$ff_only"
ff_write_feed "$ff_only" 20261105-rc1 v1 latest
ff_fresh="$test_root/ff-discovery-none-home"
ff_fails "$ff_fresh" "$ff_only" Linux x86_64 ffmpeg
ff_said 'no release found'
[ ! -e "$ff_fresh/.local/bin/ffmpeg" ]
)
end_case

begin_case "ffmpeg missing assets fail a fresh install and keep an existing pair"
( set -e
for ff_variant_root in "$ff_root_unlisted" "$ff_root_absent" "$ff_root_nosums"; do
    ff_variant=${ff_variant_root##*-}
    ff_fresh="$test_root/ff-missing-$ff_variant-home"
    ff_fails "$ff_fresh" "$ff_variant_root" Darwin aarch64 ffmpeg
    [ ! -e "$ff_fresh/.local/bin/ffmpeg" ]
    [ ! -e "$ff_fresh/.local/bin/ffprobe" ]
    [ ! -e "$ff_fresh/.local/state/dl/ffmpeg" ]
    ff_kept="$test_root/ff-missing-$ff_variant-kept-home"
    ff_ok "$ff_kept" "$ff_root_a" Darwin aarch64 ffmpeg
    ff_ok "$ff_kept" "$ff_variant_root" Darwin aarch64 ffmpeg
    ff_said 'keeping installed ffmpeg'
    ff_installed_as "$ff_kept" "$ff_tag_old" aarch64-apple-darwin
done
)
end_case

begin_case "ffmpeg rejects archives with link members and keeps the previous pair"
( set -e
ff_home="$test_root/ff-links-home"
ff_ok "$ff_home" "$ff_root_a" Linux x86_64 ffmpeg
ff_state=$(cat "$ff_home/.local/state/dl/ffmpeg")
for ff_root in "$ff_root_symlink" "$ff_root_hardlink"; do
    ff_fails "$ff_home" "$ff_root" Linux x86_64 ffmpeg
    ff_said "unsupported member type"
    ff_installed_as "$ff_home" "$ff_tag_old" x86_64-unknown-linux-musl
    [ "$(cat "$ff_home/.local/state/dl/ffmpeg")" = "$ff_state" ]
    [ "$(printf '%s\n' "$ff_home"/.local/share/ffmpeg/releases/* | wc -l)" -eq 1 ]
    [ -z "$(fd -H --max-depth 1 '^\.ffmpeg\.' "$ff_home/.local/share/ffmpeg/releases")" ]
done
)
end_case

begin_case "ffmpeg switches current atomically and keeps the previous current when the switch fails"
( set -e
ff_home="$test_root/ff-switch-home"
ff_ok "$ff_home" "$ff_root_a" Linux x86_64 ffmpeg
ff_state=$(cat "$ff_home/.local/state/dl/ffmpeg")
(
    DL_TEST_MV_FAIL="/ffmpeg/current"
    export DL_TEST_MV_FAIL
    ff_fails "$ff_home" "$ff_root_b" Linux x86_64 ffmpeg
    ff_said "could not switch"
)
ff_installed_as "$ff_home" "$ff_tag_old" x86_64-unknown-linux-musl
[ "$(cat "$ff_home/.local/state/dl/ffmpeg")" = "$ff_state" ]
[ "$(printf '%s\n' "$ff_home"/.local/share/ffmpeg/releases/* | wc -l)" -eq 1 ]
[ -z "$(fd -H --max-depth 1 '^\.' "$ff_home/.local/share/ffmpeg")" ]
ff_ok "$ff_home" "$ff_root_b" Linux x86_64 ffmpeg
ff_installed_as "$ff_home" "$ff_tag" x86_64-unknown-linux-musl
[ -z "$(fd -H --max-depth 1 '^\.' "$ff_home/.local/share/ffmpeg")" ]
)
end_case

begin_case "ffmpeg reinstalls when current is missing behind managed launchers"
( set -e
ff_home="$test_root/ff-nocurrent-home"
ff_ok "$ff_home" "$ff_root_b" Linux x86_64 ffmpeg
rm "$ff_home/.local/share/ffmpeg/current"
ff_ok "$ff_home" "$ff_root_b" Linux x86_64 ffmpeg
ff_installed_as "$ff_home" "$ff_tag" x86_64-unknown-linux-musl
)
end_case

begin_case "ffmpeg replaces a damaged release directory only after the new one passes"
( set -e
ff_home="$test_root/ff-damaged-home"
ff_release="$ff_home/.local/share/ffmpeg/releases/${ff_tag}-x86_64-unknown-linux-musl"
ff_ok "$ff_home" "$ff_root_b" Linux x86_64 ffmpeg
ff_state=$(cat "$ff_home/.local/state/dl/ffmpeg")
printf 'broken\n' > "$ff_release/bin/ffprobe"
printf 'sentinel\n' > "$ff_release/sentinel"
ff_fails "$ff_home" "$ff_root_smoke" Linux x86_64 ffmpeg
ff_said "working ffmpeg and ffprobe"
[ "$(cat "$ff_release/sentinel")" = sentinel ]
[ "$(cat "$ff_home/.local/state/dl/ffmpeg")" = "$ff_state" ]
ff_ok "$ff_home" "$ff_root_b" Linux x86_64 ffmpeg
ff_installed_as "$ff_home" "$ff_tag" x86_64-unknown-linux-musl
[ ! -e "$ff_release/sentinel" ]
[ "$(printf '%s\n' "$ff_home"/.local/share/ffmpeg/releases/* | wc -l)" -eq 1 ]
[ -z "$(fd -H --max-depth 1 '^\.' "$ff_home/.local/share/ffmpeg/releases")" ]
printf '%s\n' "${ff_tag}:ffmpeg-etag-0" > "$ff_home/.local/state/dl/ffmpeg"
printf 'sentinel\n' > "$ff_release/sentinel"
ff_ok "$ff_home" "$ff_root_b" Linux x86_64 ffmpeg
[ "$(cat "$ff_home/.local/state/dl/ffmpeg")" = "$ff_state" ]
[ ! -e "$ff_release/sentinel" ]
ff_installed_as "$ff_home" "$ff_tag" x86_64-unknown-linux-musl
)
end_case

begin_case "sync tools ffmpeg installs the pair through dl"
( set -e
ff_home="$test_root/ff-sync-home"
mkdir -p "$ff_home"
sh -c 'PATH=$1; export PATH; XDG_DATA_HOME=; export XDG_DATA_HOME; XDG_STATE_HOME=$2; export XDG_STATE_HOME; HOME=$3; export HOME; TMPDIR=$4; export TMPDIR; FFMPEG_ROOT=$5; export FFMPEG_ROOT; DL_TEST_OS=Linux; export DL_TEST_OS; DL_TEST_ARCH=x86_64; export DL_TEST_ARCH; DL_OWNED_FILE=$3/.local/state/sync/dl-owned; export DL_OWNED_FILE; exec /bin/sh "$6/sync" tools ffmpeg' \
    sync_ffmpeg "$mock_bin:$PATH" "$ff_home/.local/state" "$ff_home" "$test_root/tmp" "$ff_root_b" "$repo_root" >/dev/null
ff_installed_as "$ff_home" "$ff_tag" x86_64-unknown-linux-musl
ff_owns "$ff_home/.local/state/sync/dl-owned" F "$ff_home/.local/bin/ffprobe"
)
end_case

if [ "$nfailed" -gt 0 ]; then
    printf 'FAIL: %d of %d cases failed (cases:%s)\n' "$nfailed" "$case_n" "$failed_cases" >&2
    exit 1
fi
printf 'all %d cases passed\n' "$case_n"

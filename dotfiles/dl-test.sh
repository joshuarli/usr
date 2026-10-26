#!/bin/sh
set -eu

script_dir=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
repo_root=$(CDPATH='' cd -- "$script_dir/.." && pwd)
work_root="$repo_root/.work/tmp"
mkdir -p "$work_root"
test_root=$(mktemp -d "$work_root/dl.XXXXXX")
trap 'rm -rf "$test_root"' 0
trap 'exit 1' HUP INT TERM
mock_bin="$test_root/bin"
home="$test_root/home"
mkdir -p "$mock_bin" "$home" "$test_root/tmp"

# Run dl with the mocks first on PATH. Three macOS /bin/sh startup quirks
# make a plain VAR=value prefix unreliable here: entries prepended to PATH
# are silently dropped (bypassing mocks for npm/node), login-time
# XDG_DATA_HOME is restored (bypassing per-scenario data dirs), and
# assignments preceding a function call persist exported into later
# scenarios (CMD_TEST_VERSION, DL_RECORD_OWNED, ...). PATH and the XDG
# variables are therefore rebuilt at runtime inside the child, and the known
# test-control variables are scrubbed afterwards so every scenario starts
# clean; each scenario sets what it needs on its own run_dl call.
unset XDG_DATA_HOME XDG_STATE_HOME
run_dl() {
    _run_dl_path=$1
    _run_dl_root=$2
    shift 2
    sh -c 'PATH=$1; export PATH; XDG_DATA_HOME=$2; export XDG_DATA_HOME; XDG_STATE_HOME=$3; export XDG_STATE_HOME; _dl_root=$4; shift 4; exec /bin/sh "$_dl_root/dl" "$@"' \
        run_dl "$_run_dl_path" "${XDG_DATA_HOME-}" "${XDG_STATE_HOME-}" "$_run_dl_root" "$@"
    _run_dl_status=$?
    unset CMD_TEST_VERSION CMD_TEST_NODE_VERSION CMD_INSTALL_FAIL \
        CLAUDE_INSTALL_FAIL DL_TEST_OS DL_TEST_ARCH DL_JAQ_MOCK \
        CODEX_TAR OPENCODE_TAR OPENCODE_ETAG \
        DL_RECORD_OWNED DL_OWNED_FILE NPM_LOG \
        XDG_DATA_HOME XDG_STATE_HOME CODEX_HOME
    return $_run_dl_status
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
    https://github.com/joshuarli/sandbox-runtime/releases.atom)
        cat <<'FEED'
<feed>
<entry>
<updated>2026-10-24T02:00:00Z</updated>
<link rel="alternate" type="text/html" href="https://github.com/joshuarli/sandbox-runtime/releases/tag/bun-1.4.4-static-musl"/>
</entry>
<entry>
<updated>2026-10-24T00:00:00Z</updated>
<link rel="alternate" type="text/html" href="https://github.com/joshuarli/sandbox-runtime/releases/tag/release-0123456789abcdef0123456789abcdef01234567"/>
</entry>
</feed>
FEED
        ;;
    https://github.com/joshuarli/sandbox-runtime/releases/download/release-0123456789abcdef0123456789abcdef01234567/srt-x86_64-unknown-linux-musl.zip)
        [ "$headers" = - ] || exit 1
        printf '%s\n' 'ETag: srt-test-etag'
        ;;
    *) exit 1 ;;
esac
EOF
chmod +x "$mock_bin/curl"

cat > "$mock_bin/jaq" <<'EOF'
#!/bin/sh
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
printf '%s\n' '#!/bin/sh' 'exit 0' > "$mock_bin/codesign"
printf '%s\n' '#!/bin/sh' 'exit 0' > "$mock_bin/xattr"
chmod +x "$mock_bin/codesign" "$mock_bin/xattr"

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
        if [ "${5:-}" = "command-code@${CMD_TEST_VERSION:-1.87.3}" ]; then
            if [ "${CMD_INSTALL_FAIL:-false}" = true ]; then
                mkdir -p "$prefix/lib/node_modules/command-code"
                exit 17
            fi
            mkdir -p "$prefix/bin" "$prefix/lib/node_modules/command-code"
            printf '%s\n' '#!/bin/sh' 'exit 0' > "$prefix/bin/cmd"
            chmod +x "$prefix/bin/cmd"
            printf '%s\n' "install $*" >> "$NPM_LOG"
            exit 0
        fi
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
    run_dl "$mock_bin:$PATH" "$repo_root" cmd 2>&1); then
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
    run_dl "$mock_bin:$PATH" "$repo_root" cmd 2>&1); then
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
    CMD_TEST_VERSION=1.87.4 run_dl "$mock_bin:$PATH" "$repo_root" cmd 2>&1); then
    :
else
    printf '%s\n' "$output" >&2
    exit 1
fi
[ "$(cat "$cmd_home/.local/state/dl/cmd")" = 1.87.4 ]
[ "$(wc -l < "$cmd_log")" -eq 2 ]

cmd_owned_file="$cmd_home/.local/state/make/dl-owned"
mkdir -p "$(dirname "$cmd_owned_file")"
HOME="$cmd_home" DL_RECORD_OWNED=true DL_OWNED_FILE="$cmd_owned_file" \
    TMPDIR="$test_root/tmp" run_dl "$mock_bin:$PATH" "$repo_root"
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
    run_dl "$mock_bin:$PATH" "$repo_root" cmd >/dev/null 2>&1; then
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
    run_dl "$mock_bin:$PATH" "$repo_root" cmd >/dev/null 2>&1; then
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
    CMD_TEST_NODE_VERSION=26.11.0 run_dl "$mock_bin:$PATH" "$repo_root" cmd >/dev/null 2>&1; then
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
    CMD_INSTALL_FAIL=true run_dl "$mock_bin:$PATH" "$repo_root" cmd >/dev/null 2>&1; then
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
    run_dl "$mock_bin:$PATH" "$repo_root" cmd 2>&1); then
    :
else
    printf '%s\n' "$output" >&2
    exit 1
fi
[ -x "$cmd_failure_home/.local/share/command-code/bin/cmd" ]
)
end_case

begin_case "default targets exclude optional agents"
( set -e
default_targets=$(sed -n '/^if \[ \$# -eq 0 \]; then/,/^fi$/p' "$repo_root/dl")
case "$default_targets" in
    *'set -- '*grok*|*'set -- '*cmd*)
        printf 'optional coding agents appeared in the default dl targets\n' >&2
        exit 1 ;;
esac
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
    NPM_LOG="$unowned_dsh_log" run_dl "$mock_bin:$PATH" "$repo_root" dsh 2>&1); then
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
    TMPDIR="$test_root/tmp" NPM_LOG="$npm_log" run_dl "$mock_bin:$PATH" "$repo_root" dsh 2>&1); then
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
    CMD_TEST_NODE_VERSION=25.9.9 run_dl "$mock_bin:$PATH" "$repo_root" dsh >/dev/null 2>&1; then
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
    run_dl "$mock_bin:$PATH" "$repo_root" dsh 2>&1); then
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
    TMPDIR="$test_root/tmp" NPM_LOG="$npm_log" run_dl "$mock_bin:$PATH" "$repo_root" dsh 2>&1); then
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
    TMPDIR="$test_root/tmp" NPM_LOG="$npm_log" run_dl "$mock_bin:$PATH" "$repo_root" dsh 2>&1); then
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
    TMPDIR="$test_root/tmp" NPM_LOG="$npm_log" run_dl "$mock_bin:$PATH" "$repo_root" dsh 2>&1); then
    printf '%s\n' 'dsh followed a symlinked TUI patch' >&2
    exit 1
fi
[ "$(cat "$test_root/external-patch.yml")" = sentinel ]
rm "$dsh_data/dsh/lib/node_modules/@deepseek-harness-tui/dsh-tui/cordis.patch.yml"
printf '%s\n' '- id: tool-ralph' '  disabled: false' \
    > "$dsh_data/dsh/lib/node_modules/@deepseek-harness-tui/dsh-tui/cordis.patch.yml"
if output=$(HOME="$dsh_home" XDG_DATA_HOME="$dsh_data" XDG_STATE_HOME="$dsh_state" \
    TMPDIR="$test_root/tmp" NPM_LOG="$npm_log" run_dl "$mock_bin:$PATH" "$repo_root" dsh 2>&1); then
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
    TMPDIR="$test_root/tmp" run_dl "$mock_bin:$PATH" "$repo_root" muse 2>&1); then
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
    TMPDIR="$test_root/tmp" run_dl "$mock_bin:$PATH" "$repo_root" antigravity 2>&1); then
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
    TMPDIR="$test_root/tmp" run_dl "$mock_bin:$PATH" "$repo_root" antigravity 2>&1); then
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
ownership_file="$ownership_home/.local/state/make/dl-owned"
mkdir -p "$(dirname "$ownership_file")"
if output=$(HOME="$ownership_home" XDG_STATE_HOME="$ownership_home/.local/state" \
    DL_OWNED_FILE="$ownership_file" DL_JAQ_MOCK="$mock_bin/jaq" \
    TMPDIR="$test_root/tmp" run_dl "$mock_bin:$PATH" "$repo_root" jaq 2>&1); then
    :
else
    printf '%s\n' "$output" >&2
    exit 1
fi
if output=$(HOME="$ownership_home" XDG_STATE_HOME="$ownership_home/.local/state" \
    DL_OWNED_FILE="$ownership_file" DL_JAQ_MOCK="$mock_bin/jaq" \
    TMPDIR="$test_root/tmp" run_dl "$mock_bin:$PATH" "$repo_root" jaq 2>&1); then
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
reconcile_file="$reconcile_home/.local/state/make/dl-owned"
mkdir -p "$reconcile_home/.local/bin" "$reconcile_home/.local/state/dl" \
    "$(dirname "$reconcile_file")"
printf '%s\n' 'managed jaq' > "$reconcile_home/.local/bin/jaq"
chmod +x "$reconcile_home/.local/bin/jaq"
printf '%s\n' 'jaq-test-etag' > "$reconcile_home/.local/state/dl/jaq"
HOME="$reconcile_home" XDG_STATE_HOME="$reconcile_home/.local/state" \
    DL_OWNED_FILE="$reconcile_file" DL_RECORD_OWNED=true \
    TMPDIR="$test_root/tmp" run_dl "$mock_bin:$PATH" "$repo_root"
awk -F '\t' -v path="$reconcile_home/.local/bin/jaq" \
    '$1 == "F" && $2 == path { count++ } END { exit count != 1 }' "$reconcile_file"
awk -F '\t' -v path="$reconcile_home/.local/state/dl/jaq" \
    '$1 == "F" && $2 == path { count++ } END { exit count != 1 }' "$reconcile_file"
)
end_case

begin_case "unmanaged launcher is not recorded for removal"
( set -e
unmanaged_home="$test_root/unmanaged-home"
unmanaged_file="$unmanaged_home/.local/state/make/dl-owned"
mkdir -p "$unmanaged_home/.local/bin" "$(dirname "$unmanaged_file")"
printf '%s\n' '#!/bin/sh' 'exit 0' > "$unmanaged_home/.local/bin/jaq"
chmod +x "$unmanaged_home/.local/bin/jaq"
HOME="$unmanaged_home" XDG_STATE_HOME="$unmanaged_home/.local/state" \
    DL_OWNED_FILE="$unmanaged_file" DL_RECORD_OWNED=true \
    TMPDIR="$test_root/tmp" run_dl "$mock_bin:$PATH" "$repo_root"
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
    "$untracked_home/.local/state/make"
printf '%s\n' '#!/bin/sh' 'exit 0' > "$untracked_home/.local/bin/agy"
chmod +x "$untracked_home/.local/bin/agy"
if output=$(HOME="$untracked_home" XDG_STATE_HOME="$untracked_home/.local/state" \
    DL_OWNED_FILE="$untracked_home/.local/state/make/dl-owned" DL_RECORD_OWNED=true \
    TMPDIR="$test_root/tmp" run_dl "$mock_bin:$PATH" "$repo_root" 2>&1); then
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
unsafe_target_owned="$unsafe_target_home/.local/state/make/dl-owned"
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
    TMPDIR="$test_root/tmp" run_dl "$mock_bin:$PATH" "$repo_root"
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

begin_case "gh is current"
( set -e
gh_home="$test_root/gh-home"
mkdir -p "$gh_home/.local/bin" "$gh_home/.local/state/dl"
printf '%s\n' 'gh test binary' > "$gh_home/.local/bin/gh"
chmod +x "$gh_home/.local/bin/gh"
printf '%s\n' 'gh-test-etag' > "$gh_home/.local/state/dl/gh"
if output=$(HOME="$gh_home" XDG_STATE_HOME="$gh_home/.local/state" \
    DL_TEST_OS=Darwin DL_TEST_ARCH=arm64 TMPDIR="$test_root/tmp" \
    run_dl "$mock_bin:$PATH" "$repo_root" gh 2>&1); then
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

begin_case "sandbox is current"
( set -e
sandbox_home="$test_root/sandbox-home"
mkdir -p "$sandbox_home/.local/bin" "$sandbox_home/.local/state/dl"
printf '%s\n' 'sandbox test binary' > "$sandbox_home/.local/bin/sandbox"
chmod +x "$sandbox_home/.local/bin/sandbox"
printf '%s\n' 'srt-test-etag' > "$sandbox_home/.local/state/dl/sandbox"
if output=$(HOME="$sandbox_home" XDG_STATE_HOME="$sandbox_home/.local/state" \
    DL_TEST_OS=Linux DL_TEST_ARCH=x86_64 TMPDIR="$test_root/tmp" \
    run_dl "$mock_bin:$PATH" "$repo_root" sandbox 2>&1); then
    :
else
    printf '%s\n' "$output" >&2
    exit 1
fi
case "$output" in
    *'sandbox is current (release-0123456789abcdef0123456789abcdef01234567)'*) ;;
    *) printf '%s\n' "$output" >&2; exit 1 ;;
esac
)
end_case

begin_case "grok install"
( set -e
grok_home="$test_root/grok-home"
if output=$(HOME="$grok_home" XDG_STATE_HOME="$grok_home/.local/state" \
    TMPDIR="$test_root/tmp" run_dl "$mock_bin:$PATH" "$repo_root" grok 2>&1); then
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
    TMPDIR="$test_root/tmp" run_dl "$mock_bin:$PATH" "$repo_root" grok 2>&1); then
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
    TMPDIR="$test_root/tmp" run_dl "$mock_bin:$PATH" "$repo_root" grok 2>&1); then
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
    TMPDIR="$test_root/tmp" run_dl "$mock_bin:$PATH" "$repo_root" muse 2>&1); then
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
    TMPDIR="$test_root/tmp" OPENCODE_TAR="$test_root/opencode.tar.gz" run_dl "$mock_bin:$PATH" "$repo_root" opencode2 2>&1); then
    :
else
    printf '%s\n' "$output" >&2
    exit 1
fi
[ -x "$opencode_home/.opencode/bin/opencode" ]
[ "$(readlink "$opencode_home/.local/bin/opencode2")" = "$opencode_home/.opencode/bin/opencode2" ]
[ "$(HOME="$opencode_home" "$opencode_home/.local/bin/opencode2" --version)" = 'opencode 2.0.1' ]
cat > "$opencode_home/.opencode/bin/opencode2" <<'EOF'
#!/bin/sh
exec "$HOME/.local/bin/opencode" "$@"
EOF
chmod +x "$opencode_home/.opencode/bin/opencode2"
if output=$(HOME="$opencode_home" XDG_STATE_HOME="$opencode_home/.local/state" \
    TMPDIR="$test_root/tmp" OPENCODE_TAR="$test_root/opencode.tar.gz" run_dl "$mock_bin:$PATH" "$repo_root" opencode2 2>&1); then
    :
else
    printf '%s\n' "$output" >&2
    exit 1
fi
[ "$(HOME="$opencode_home" "$opencode_home/.local/bin/opencode2" --version)" = 'opencode 2.0.1' ]
if output=$(HOME="$opencode_home" XDG_STATE_HOME="$opencode_home/.local/state" \
    TMPDIR="$test_root/tmp" OPENCODE_TAR="$test_root/opencode-v2.tar.gz" OPENCODE_ETAG=opencode-test-etag-2 \
    run_dl "$mock_bin:$PATH" "$repo_root" opencode2 2>&1); then
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
    TMPDIR="$test_root/tmp" OPENCODE_TAR="$test_root/opencode.tar.gz" run_dl "$mock_bin:$PATH" "$repo_root" opencode2 2>&1); then
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
    TMPDIR="$test_root/tmp" run_dl "$mock_bin:$PATH" "$repo_root" claude 2>&1); then
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
    TMPDIR="$test_root/tmp" run_dl "$mock_bin:$PATH" "$repo_root" claude 2>&1); then
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
    run_dl "$mock_bin:$PATH" "$repo_root" claude 2>&1); then
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
    run_dl "$mock_bin:$PATH" "$repo_root" claude 2>&1); then
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
    XDG_STATE_HOME="$legacy_home/.local/state" TMPDIR="$test_root/tmp" run_dl "$mock_bin:$PATH" "$repo_root" claude 2>&1); then
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
    XDG_STATE_HOME="$custom_home/.local/state" TMPDIR="$test_root/tmp" run_dl "$mock_bin:$PATH" "$repo_root" claude 2>&1); then
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
ln -s "$mock_bin/uname" "$missing_file_bin/uname"
ln -s "$(command -v mkdir)" "$missing_file_bin/mkdir"
ln -s "$(command -v sed)" "$missing_file_bin/sed"
if output=$(HOME="$missing_file_home" XDG_DATA_HOME="$missing_file_home/.local/share" \
    XDG_STATE_HOME="$missing_file_home/.local/state" TMPDIR="$test_root/tmp" \
    run_dl "$missing_file_bin" "$repo_root" claude 2>&1); then
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
    run_dl "$mock_bin:/usr/bin:/bin" "$repo_root" jaq codex muse 2>&1); then
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

if [ "$nfailed" -gt 0 ]; then
    printf 'FAIL: %d of %d cases failed (cases:%s)\n' "$nfailed" "$case_n" "$failed_cases" >&2
    exit 1
fi
printf 'all %d cases passed\n' "$case_n"

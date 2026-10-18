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
[ "$1" = --dir ] && [ "$2" = "$HOME/.local/bin" ] || exit 1
mkdir -p "$HOME/.local/bin"
printf '%s\n' '#!/bin/sh' 'exit 0' > "$HOME/.local/bin/agy"
chmod +x "$HOME/.local/bin/agy"
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
            printf '%s\n' 'ETag: opencode-test-etag'
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
    *) exit 1 ;;
esac
EOF
chmod +x "$mock_bin/curl"

cat > "$mock_bin/jaq" <<'EOF'
#!/bin/sh
for query do :; done
case "$query" in
    '.version // empty') printf '%s\n' '1.4.9-R6297.1' ;;
    '.manifest_url // empty') printf '%s\n' 'https://lookaside.facebook.com/lookaside/muse/download/?channel=muse&version=1.4.9-R6297.1&file=manifest.json' ;;
    *'.platforms['*) printf '%s\n' 'c4156c243860ddee43e9c200f5b3d672b447d928df5273a3c954bb15b0f8dcad' ;;
    *'.artifacts['*'.checksum'*) printf '%s\n' '23036067f74d814ea3059686c1f0596ffe619e29fd38a8caa71c3c446a1eeba9' ;;
    *'.artifacts['*'.url'*) printf '%s\n' 'https://lookaside.facebook.com/lookaside/muse/download/?channel=muse&version=1.4.9-R6297.1&file=x86_linux' ;;
    *) exit 1 ;;
esac
EOF
chmod +x "$mock_bin/jaq"

mkdir -p "$test_root/opencode-package"
cat > "$test_root/opencode-package/opencode" <<'EOF'
#!/bin/sh
[ "$1" = --version ] && printf '%s\n' 'opencode 2.0.1'
EOF
chmod +x "$test_root/opencode-package/opencode"
tar -czf "$test_root/opencode.tar.gz" -C "$test_root/opencode-package" opencode

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

dsh_home="$test_root/dsh-home"
dsh_data="$dsh_home/data"
dsh_state="$dsh_home/state"
npm_log="$test_root/npm.log"
mkdir -p "$dsh_home/.local/bin" "$dsh_home/.local/lib/node_modules/@deepseek-ai/dsh"
ln -s ../lib/node_modules/@deepseek-ai/dsh/lib/bin.js "$dsh_home/.local/bin/dsh"
if output=$(HOME="$dsh_home" XDG_DATA_HOME="$dsh_data" XDG_STATE_HOME="$dsh_state" \
    TMPDIR="$test_root/tmp" NPM_LOG="$npm_log" PATH="$mock_bin:$PATH" \
    sh "$repo_root/dl" dsh 2>&1); then
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
case "$(cat "$npm_log")" in
    *'@deepseek-ai/dsh@0.2.1-rc.2 @deepseek-harness-tui/dsh-tui@0.16.0'*) ;;
    *) cat "$npm_log" >&2; exit 1 ;;
esac

managed_dsh_home="$test_root/managed-dsh-home"
managed_dsh_data="$managed_dsh_home/data"
managed_dsh_state="$managed_dsh_home/state"
managed_dsh_log="$test_root/managed-dsh-npm.log"
mkdir -p "$managed_dsh_home/.local/bin" "$managed_dsh_home/.local/lib/node_modules/@deepseek-ai/dsh"
ln -s "$repo_root/dotfiles/base/.local/bin/dsh" "$managed_dsh_home/.local/bin/dsh"
if output=$(HOME="$managed_dsh_home" XDG_DATA_HOME="$managed_dsh_data" \
    XDG_STATE_HOME="$managed_dsh_state" TMPDIR="$test_root/tmp" NPM_LOG="$managed_dsh_log" \
    PATH="$mock_bin:$PATH" sh "$repo_root/dl" dsh 2>&1); then
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

if output=$(HOME="$dsh_home" XDG_DATA_HOME="$dsh_data" XDG_STATE_HOME="$dsh_state" \
    TMPDIR="$test_root/tmp" NPM_LOG="$npm_log" PATH="$mock_bin:$PATH" \
    sh "$repo_root/dl" dsh 2>&1); then
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
    TMPDIR="$test_root/tmp" NPM_LOG="$npm_log" PATH="$mock_bin:$PATH" \
    sh "$repo_root/dl" dsh 2>&1); then
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
    TMPDIR="$test_root/tmp" NPM_LOG="$npm_log" PATH="$mock_bin:$PATH" \
    sh "$repo_root/dl" dsh 2>&1); then
    printf '%s\n' 'dsh followed a symlinked TUI patch' >&2
    exit 1
fi
[ "$(cat "$test_root/external-patch.yml")" = sentinel ]
rm "$dsh_data/dsh/lib/node_modules/@deepseek-harness-tui/dsh-tui/cordis.patch.yml"
printf '%s\n' '- id: tool-ralph' '  disabled: false' \
    > "$dsh_data/dsh/lib/node_modules/@deepseek-harness-tui/dsh-tui/cordis.patch.yml"
if output=$(HOME="$dsh_home" XDG_DATA_HOME="$dsh_data" XDG_STATE_HOME="$dsh_state" \
    TMPDIR="$test_root/tmp" NPM_LOG="$npm_log" PATH="$mock_bin:$PATH" \
    sh "$repo_root/dl" dsh 2>&1); then
    printf '%s\n' 'dsh accepted a changed TUI compatibility row' >&2
    exit 1
fi
case "$(cat "$dsh_data/dsh/lib/node_modules/@deepseek-harness-tui/dsh-tui/cordis.patch.yml")" in
    *'disabled: false'*) ;;
    *) printf '%s\n' 'dsh changed the unexpected TUI patch row' >&2; exit 1 ;;
esac

if output=$(HOME="$home" XDG_DATA_HOME="$home/.local/share" XDG_STATE_HOME="$home/.local/state" \
    TMPDIR="$test_root/tmp" PATH="$mock_bin:$PATH" sh "$repo_root/dl" muse 2>&1); then
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

antigravity_home="$test_root/antigravity-home"
if output=$(HOME="$antigravity_home" XDG_STATE_HOME="$antigravity_home/.local/state" \
    TMPDIR="$test_root/tmp" PATH="$mock_bin:$PATH" sh "$repo_root/dl" antigravity 2>&1); then
    :
else
    printf '%s\n' "$output" >&2
    exit 1
fi
[ -x "$antigravity_home/.local/bin/agy" ]
case "$output" in
    *"Installed Antigravity CLI ($antigravity_home/.local/bin/agy)"*) ;;
    *) printf '%s\n' "$output" >&2; exit 1 ;;
esac
if output=$(HOME="$antigravity_home" XDG_STATE_HOME="$antigravity_home/.local/state" \
    TMPDIR="$test_root/tmp" PATH="$mock_bin:$PATH" sh "$repo_root/dl" antigravity 2>&1); then
    :
else
    printf '%s\n' "$output" >&2
    exit 1
fi
case "$output" in
    *'agy is installed'*) ;;
    *) printf '%s\n' "$output" >&2; exit 1 ;;
esac

cat > "$mock_bin/uname" <<'EOF'
#!/bin/sh
case "$1" in
    -s) printf '%s\n' Linux ;;
    -m) printf '%s\n' x86_64 ;;
    *) exit 1 ;;
esac
EOF
chmod +x "$mock_bin/uname"

grok_home="$test_root/grok-home"
if output=$(HOME="$grok_home" XDG_STATE_HOME="$grok_home/.local/state" \
    TMPDIR="$test_root/tmp" PATH="$mock_bin:$PATH" sh "$repo_root/dl" grok 2>&1); then
    :
else
    printf '%s\n' "$output" >&2
    exit 1
fi
[ "$(readlink "$grok_home/.local/bin/grok")" = "$grok_home/.grok/bin/grok" ]
[ "$(readlink "$grok_home/.grok/bin/grok")" = ../downloads/grok-linux-x86_64 ]
[ "$(cat "$grok_home/.grok/downloads/grok-linux-x86_64")" = grok-test-binary ]

grok_collision_home="$test_root/grok-collision-home"
mkdir -p "$grok_collision_home/.local/bin" "$grok_collision_home/.local/state/dl" \
    "$grok_collision_home/.grok/bin" "$grok_collision_home/.grok/downloads"
printf '%s\n' 'legacy grok binary' > "$grok_collision_home/.local/bin/grok"
printf '%s\n' 'native grok binary' > "$grok_collision_home/.grok/downloads/grok-linux-x86_64"
chmod +x "$grok_collision_home/.local/bin/grok" "$grok_collision_home/.grok/downloads/grok-linux-x86_64"
ln -s ../downloads/grok-linux-x86_64 "$grok_collision_home/.grok/bin/grok"
printf '%s\n' 'old-grok-test-etag' > "$grok_collision_home/.local/state/dl/grok"
if output=$(HOME="$grok_collision_home" XDG_STATE_HOME="$grok_collision_home/.local/state" \
    TMPDIR="$test_root/tmp" PATH="$mock_bin:$PATH" sh "$repo_root/dl" grok 2>&1); then
    printf '%s\n' 'Grok migration replaced an existing native install' >&2
    exit 1
fi
[ "$(cat "$grok_collision_home/.local/bin/grok")" = 'legacy grok binary' ]
[ "$(cat "$grok_collision_home/.grok/downloads/grok-linux-x86_64")" = 'native grok binary' ]

legacy_grok_home="$test_root/legacy-grok-home"
mkdir -p "$legacy_grok_home/.local/bin" "$legacy_grok_home/.local/state/dl"
printf '%s\n' 'legacy grok binary' > "$legacy_grok_home/.local/bin/grok"
chmod +x "$legacy_grok_home/.local/bin/grok"
printf '%s\n' 'old-grok-test-etag' > "$legacy_grok_home/.local/state/dl/grok"
if output=$(HOME="$legacy_grok_home" XDG_STATE_HOME="$legacy_grok_home/.local/state" \
    TMPDIR="$test_root/tmp" PATH="$mock_bin:$PATH" sh "$repo_root/dl" grok 2>&1); then
    :
else
    printf '%s\n' "$output" >&2
    exit 1
fi
[ "$(readlink "$legacy_grok_home/.local/bin/grok")" = "$legacy_grok_home/.grok/bin/grok" ]

muse_legacy_home="$test_root/legacy-muse-home"
mkdir -p "$muse_legacy_home/.local/bin" "$muse_legacy_home/.local/state/dl"
printf '%s\n' 'legacy muse binary' > "$muse_legacy_home/.local/bin/muse"
chmod +x "$muse_legacy_home/.local/bin/muse"
printf '%s\n' 'old-muse-test-etag' > "$muse_legacy_home/.local/state/dl/muse"
if output=$(HOME="$muse_legacy_home" XDG_STATE_HOME="$muse_legacy_home/.local/state" \
    TMPDIR="$test_root/tmp" PATH="$mock_bin:$PATH" sh "$repo_root/dl" muse 2>&1); then
    :
else
    printf '%s\n' "$output" >&2
    exit 1
fi
case "$(cat "$muse_legacy_home/.local/bin/muse")" in
    *'#!/bin/sh'*) ;;
    *) printf '%s\n' 'Muse legacy install was not migrated to the official launcher' >&2; exit 1 ;;
esac

opencode_home="$test_root/opencode-home"
if output=$(HOME="$opencode_home" XDG_STATE_HOME="$opencode_home/.local/state" \
    TMPDIR="$test_root/tmp" OPENCODE_TAR="$test_root/opencode.tar.gz" PATH="$mock_bin:$PATH" \
    sh "$repo_root/dl" opencode2 2>&1); then
    :
else
    printf '%s\n' "$output" >&2
    exit 1
fi
[ -x "$opencode_home/.opencode/bin/opencode" ]
[ "$(readlink "$opencode_home/.local/bin/opencode2")" = "$opencode_home/.opencode/bin/opencode2" ]
[ "$(HOME="$opencode_home" "$opencode_home/.local/bin/opencode2" --version)" = 'opencode 2.0.1' ]

opencode_collision_home="$test_root/opencode-collision-home"
mkdir -p "$opencode_collision_home/.local/bin" "$opencode_collision_home/.local/state/dl" \
    "$opencode_collision_home/.opencode/bin"
printf '%s\n' 'legacy opencode binary' > "$opencode_collision_home/.local/bin/opencode2"
printf '%s\n' 'native opencode binary' > "$opencode_collision_home/.opencode/bin/opencode"
chmod +x "$opencode_collision_home/.local/bin/opencode2" "$opencode_collision_home/.opencode/bin/opencode"
printf '%s\n' 'old-opencode-test-etag' > "$opencode_collision_home/.local/state/dl/opencode2"
if output=$(HOME="$opencode_collision_home" XDG_STATE_HOME="$opencode_collision_home/.local/state" \
    TMPDIR="$test_root/tmp" OPENCODE_TAR="$test_root/opencode.tar.gz" PATH="$mock_bin:$PATH" \
    sh "$repo_root/dl" opencode2 2>&1); then
    printf '%s\n' 'OpenCode 2 migration replaced an existing native install' >&2
    exit 1
fi
[ "$(cat "$opencode_collision_home/.local/bin/opencode2")" = 'legacy opencode binary' ]
[ "$(cat "$opencode_collision_home/.opencode/bin/opencode")" = 'native opencode binary' ]

claude_home="$test_root/claude-home"
claude_data="$claude_home/share"
claude_state="$claude_home/state"
if output=$(HOME="$claude_home" XDG_DATA_HOME="$claude_data" XDG_STATE_HOME="$claude_state" \
    TMPDIR="$test_root/tmp" PATH="$mock_bin:$PATH" sh "$repo_root/dl" claude 2>&1); then
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
if output=$(HOME="$claude_home" XDG_DATA_HOME="$claude_data" XDG_STATE_HOME="$claude_state" \
    TMPDIR="$test_root/tmp" PATH="$mock_bin:$PATH" sh "$repo_root/dl" claude 2>&1); then
    :
else
    printf '%s\n' "$output" >&2
    exit 1
fi
case "$output" in
    *'claude is installed'*) ;;
    *) printf '%s\n' "$output" >&2; exit 1 ;;
esac

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
    PATH="$mock_bin:$PATH" sh "$repo_root/dl" claude 2>&1); then
    :
else
    printf '%s\n' "$output" >&2
    exit 1
fi
[ "$(readlink "$old_claude_home/.local/bin/claude")" = "$old_claude_home/.claude/native/claude" ]

legacy_home="$test_root/legacy-home"
mkdir -p "$legacy_home/.local/bin" "$legacy_home/.local/state/dl"
printf '%s' 'legacy Claude binary' > "$legacy_home/.local/bin/claude"
chmod +x "$legacy_home/.local/bin/claude"
printf '%s\n' 'old-claude-test-etag' > "$legacy_home/.local/state/dl/claude"
if output=$(HOME="$legacy_home" XDG_DATA_HOME="$legacy_home/.local/share" \
    XDG_STATE_HOME="$legacy_home/.local/state" TMPDIR="$test_root/tmp" PATH="$mock_bin:$PATH" \
    sh "$repo_root/dl" claude 2>&1); then
    :
else
    printf '%s\n' "$output" >&2
    exit 1
fi
legacy_version="$legacy_home/.claude/native/claude"
[ -L "$legacy_home/.local/bin/claude" ]
[ "$(readlink "$legacy_home/.local/bin/claude")" = "$legacy_version" ]

custom_home="$test_root/custom-home"
mkdir -p "$custom_home/.local/bin" "$custom_home/.local/state/dl"
printf '%s\n' 'custom launcher' > "$custom_home/.local/bin/claude"
chmod +x "$custom_home/.local/bin/claude"
printf '%s\n' 'old-claude-test-etag' > "$custom_home/.local/state/dl/claude"
if output=$(HOME="$custom_home" XDG_DATA_HOME="$custom_home/.local/share" \
    XDG_STATE_HOME="$custom_home/.local/state" TMPDIR="$test_root/tmp" PATH="$mock_bin:$PATH" \
    sh "$repo_root/dl" claude 2>&1); then
    :
else
    printf '%s\n' "$output" >&2
    exit 1
fi
[ "$(cat "$custom_home/.local/bin/claude")" = 'custom launcher' ]

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
    PATH="$missing_file_bin" /bin/sh "$repo_root/dl" claude 2>&1); then
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

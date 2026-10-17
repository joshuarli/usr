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
    https://downloads.claude.ai/claude-code-releases/latest)
        printf '%s\n' '2.1.300'
        ;;
    https://downloads.claude.ai/claude-code-releases/2.1.300/manifest.json)
        printf '%s\n' '{"platforms":{"linux-x64":{"checksum":"c4156c243860ddee43e9c200f5b3d672b447d928df5273a3c954bb15b0f8dcad"}}}'
        ;;
    https://downloads.claude.ai/claude-code-releases/2.1.300/linux-x64/claude)
        if [ "$headers" = - ]; then
            printf '%s\n' 'ETag: claude-test-etag'
        elif [ -n "$output" ]; then
            printf '%s' 'claude-test-binary' > "$output"
        else
            exit 1
        fi
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

cat > "$mock_bin/file" <<'EOF'
#!/bin/sh
case "$(cat "$2")" in
    *'custom launcher'*) printf '%s\n' 'POSIX shell script' ;;
    *) printf '%s\n' 'ELF 64-bit LSB pie executable' ;;
esac
EOF
chmod +x "$mock_bin/file"

if output=$(HOME="$home" XDG_DATA_HOME="$home/.local/share" XDG_STATE_HOME="$home/.local/state" \
    TMPDIR="$test_root/tmp" PATH="$mock_bin:$PATH" sh "$repo_root/dl" muse 2>&1); then
    :
else
    printf '%s\n' "$output" >&2
    exit 1
fi

case "$output" in
    *"Installed $home/.local/bin/muse"*) ;;
    *) printf '%s\n' "$output" >&2; exit 1 ;;
esac
[ "$(cat "$home/.local/bin/muse")" = muse-test-binary ]

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
claude_version="$claude_data/claude/versions/2.1.300"
[ -L "$claude_home/.local/bin/claude" ]
[ "$(readlink "$claude_home/.local/bin/claude")" = "$claude_version" ]
[ -x "$claude_version" ]
[ "$(cat "$claude_version")" = claude-test-binary ]
case "$output" in
    *"Installed $claude_home/.local/bin/claude"*) ;;
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
legacy_version="$legacy_home/.local/share/claude/versions/2.1.300"
[ -L "$legacy_home/.local/bin/claude" ]
[ "$(readlink "$legacy_home/.local/bin/claude")" = "$legacy_version" ]
[ "$(cat "$legacy_version")" = claude-test-binary ]

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

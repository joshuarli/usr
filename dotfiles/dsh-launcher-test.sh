#!/bin/sh
set -eu
unset DEEPSEEK_API_KEY

script_dir=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
repo_root=$(CDPATH='' cd -- "$script_dir/.." && pwd)
work_root="$repo_root/.work/tmp"
mkdir -p "$work_root"
test_root=$(mktemp -d "$work_root/dsh-launcher.XXXXXX")
trap 'rm -rf "$test_root"' 0
trap 'exit 1' HUP INT TERM

home="$test_root/home"
data="$home/data"
capture="$test_root/args"
bin="$data/dsh/bin"
mock_bin="$test_root/bin"
launcher="$home/.local/bin/dsh"
vault_capture="$test_root/vault"
mkdir -p "$bin" "$mock_bin" "$(dirname "$launcher")"
ln -s "$repo_root/dotfiles/base/.local/bin/dsh" "$launcher"

cat > "$mock_bin/vault" <<'EOF'
#!/bin/sh
printf '%s\n' "$@" > "$DSH_VAULT_CAPTURE"
[ "$1" = DEEPSEEK_API_KEY ] || exit 64
[ "$2" = -- ] || exit 64
shift 2
exec "$@"
EOF

cat > "$bin/dsh" <<'EOF'
#!/bin/sh
printf '%s\n' core > "$DSH_COMMAND_CAPTURE"
printf '%s\n' "$@" > "$DSH_CAPTURE"
printf '%s\n' "${DEEPSEEK_API_KEY:-}" > "$DSH_KEY_CAPTURE"
EOF
cat > "$bin/dsh-tui" <<'EOF'
#!/bin/sh
printf '%s\n' tui > "$DSH_COMMAND_CAPTURE"
printf '%s\n' "$@" > "$DSH_CAPTURE"
printf '%s\n' "${DEEPSEEK_API_KEY:-}" > "$DSH_KEY_CAPTURE"
[ -z "${DSH_PATH_CAPTURE:-}" ] || printf '%s\n' "$PATH" > "$DSH_PATH_CAPTURE"
EOF
chmod +x "$bin/dsh" "$bin/dsh-tui" "$mock_bin/vault"
PATH="$mock_bin:$PATH"
DSH_VAULT_CAPTURE="$vault_capture"
export PATH DSH_VAULT_CAPTURE

if output=$(HOME="$home" XDG_DATA_HOME="$data" DSH_CAPTURE="$capture" \
    DSH_COMMAND_CAPTURE="$test_root/command" \
    DSH_KEY_CAPTURE="$test_root/key" \
    DSH_PATH_CAPTURE="$test_root/path" \
    sh "$launcher" 2>&1); then
    :
else
    printf '%s\n' "$output" >&2
    exit 1
fi
[ "$(cat "$test_root/command")" = tui ]
[ "$(sed -n '1p' "$vault_capture")" = DEEPSEEK_API_KEY ]
[ "$(sed -n '2p' "$vault_capture")" = -- ]
[ "$(sed -n '1p' "$capture")" = --patch ]
[ "$(sed -n '2p' "$capture")" = "$repo_root/dotfiles/base/.local/bin/../../.config/dsh/tui.patch.yml" ]
[ "$(sed -n '1p' "$test_root/path" | cut -d: -f1)" = "$bin" ]

if output=$(HOME="$home" XDG_DATA_HOME="$data" DSH_CAPTURE="$capture" \
    DSH_COMMAND_CAPTURE="$test_root/command" \
    DSH_KEY_CAPTURE="$test_root/key" \
    sh "$launcher" web --dump-config 2>&1); then
    :
else
    printf '%s\n' "$output" >&2
    exit 1
fi
[ "$(cat "$test_root/command")" = core ]
[ "$(sed -n '1p' "$vault_capture")" = DEEPSEEK_API_KEY ]
[ "$(sed -n '2p' "$vault_capture")" = -- ]
[ "$(sed -n '1p' "$capture")" = --profile ]
[ "$(sed -n '2p' "$capture")" = web ]
[ "$(sed -n '3p' "$capture")" = --patch ]
[ "$(sed -n '4p' "$capture")" = "$repo_root/dotfiles/base/.local/bin/../../.config/dsh/tui.patch.yml" ]
[ "$(sed -n '5p' "$capture")" = --dump-config ]

if output=$(HOME="$home" XDG_DATA_HOME="$data" DSH_CAPTURE="$capture" \
    DSH_COMMAND_CAPTURE="$test_root/command" \
    DSH_KEY_CAPTURE="$test_root/key" \
    sh "$launcher" --profile web --dump-config 2>&1); then
    :
else
    printf '%s\n' "$output" >&2
    exit 1
fi
[ "$(cat "$test_root/command")" = core ]
[ "$(sed -n '1p' "$vault_capture")" = DEEPSEEK_API_KEY ]
[ "$(sed -n '2p' "$vault_capture")" = -- ]
[ "$(sed -n '1p' "$capture")" = --profile ]
[ "$(sed -n '2p' "$capture")" = web ]
[ "$(sed -n '3p' "$capture")" = --patch ]
[ "$(sed -n '5p' "$capture")" = --dump-config ]

rm -f "$vault_capture"
if output=$(HOME="$home" XDG_DATA_HOME="$data" DSH_CAPTURE="$capture" \
    DSH_COMMAND_CAPTURE="$test_root/command" \
    DSH_KEY_CAPTURE="$test_root/key" \
    sh "$launcher" plugin --profile web add example 2>&1); then
    :
else
    printf '%s\n' "$output" >&2
    exit 1
fi
[ "$(cat "$test_root/command")" = core ]
[ ! -e "$vault_capture" ]
[ "$(sed -n '1p' "$capture")" = plugin ]

if output=$(HOME="$home" XDG_DATA_HOME="$data" DSH_CAPTURE="$capture" \
    DSH_COMMAND_CAPTURE="$test_root/command" \
    DSH_KEY_CAPTURE="$test_root/key" \
    sh "$launcher" tui --resume session-1 2>&1); then
    :
else
    printf '%s\n' "$output" >&2
    exit 1
fi
[ "$(cat "$test_root/command")" = tui ]
[ "$(sed -n '1p' "$vault_capture")" = DEEPSEEK_API_KEY ]
[ "$(sed -n '2p' "$vault_capture")" = -- ]
[ "$(sed -n '1p' "$capture")" = --patch ]
[ "$(sed -n '3p' "$capture")" = --resume ]
[ "$(sed -n '4p' "$capture")" = session-1 ]

if output=$(HOME="$home" XDG_DATA_HOME="$data" DSH_CAPTURE="$capture" \
    DSH_COMMAND_CAPTURE="$test_root/command" \
    DSH_KEY_CAPTURE="$test_root/key" \
    sh "$launcher" --profile tui --resume session-2 2>&1); then
    :
else
    printf '%s\n' "$output" >&2
    exit 1
fi
[ "$(cat "$test_root/command")" = tui ]
[ "$(sed -n '1p' "$vault_capture")" = DEEPSEEK_API_KEY ]
[ "$(sed -n '2p' "$vault_capture")" = -- ]
[ "$(sed -n '1p' "$capture")" = --patch ]
[ "$(sed -n '3p' "$capture")" = --resume ]
[ "$(sed -n '4p' "$capture")" = session-2 ]

rm -f "$vault_capture"
if output=$(env PATH="$bin:/usr/bin:/bin" HOME="$home" XDG_DATA_HOME="$data" \
    DSH_CAPTURE="$capture" DSH_COMMAND_CAPTURE="$test_root/command" \
    DSH_KEY_CAPTURE="$test_root/key" DEEPSEEK_API_KEY=fixture-key \
    sh "$launcher" web --dump-config 2>&1); then
    :
else
    printf '%s\n' "$output" >&2
    exit 1
fi
[ "$(cat "$test_root/command")" = core ]
[ "$(cat "$test_root/key")" = fixture-key ]
[ ! -e "$vault_capture" ]

rm -f "$test_root/command"
if output=$(env PATH="$bin:/usr/bin:/bin" HOME="$home" XDG_DATA_HOME="$data" \
    DSH_CAPTURE="$capture" DSH_COMMAND_CAPTURE="$test_root/command" \
    DSH_KEY_CAPTURE="$test_root/key" sh "$launcher" web 2>&1); then
    printf '%s\n' 'dsh unexpectedly started without a key source' >&2
    exit 1
fi
printf '%s\n' "$output" | grep -Fqx 'dsh: set DEEPSEEK_API_KEY or install vault with that entry'
[ ! -e "$test_root/command" ]

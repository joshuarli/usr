#!/bin/sh
set -eu

repo=$(CDPATH='' cd "$(dirname "$0")/.." && pwd -P)
reset_agents=$repo/dotfiles/base/.local/bin/reset-agents
mkdir -p "$repo/.work/tmp"
scratch=$(mktemp -d "$repo/.work/tmp/reset-agents-test.XXXXXX")
home="$scratch/home with spaces"
mkdir -p "$home"
trap 'rm -rf "$scratch"' 0
trap 'exit 1' HUP INT TERM

present() {
    if [ ! -e "$1" ] && [ ! -L "$1" ]; then
        printf 'FAIL: expected %s to remain\n' "$1" >&2
        exit 1
    fi
}

absent() {
    if [ -e "$1" ] || [ -L "$1" ]; then
        printf 'FAIL: expected %s to be removed\n' "$1" >&2
        exit 1
    fi
}

reset_agent() {
    HOME=$home \
        XDG_CONFIG_HOME=$home/.config \
        XDG_DATA_HOME=$home/.local/share \
        XDG_CACHE_HOME=$home/.cache \
        "$reset_agents" "$@"
}

mkdir -p "$home/.claude"
: > "$home/.claude/settings.json"
: > "$home/.claude/.credentials.json"
: > "$home/.claude/history.jsonl"
reset_agent claude
present "$home/.claude/settings.json"
present "$home/.claude/.credentials.json"
absent "$home/.claude/history.jsonl"

mkdir -p "$home/.grok/sessions"
: > "$home/.grok/config.toml"
: > "$home/.grok/auth.json"
: > "$home/.grok/mcp_credentials.json"
: > "$home/.grok/sessions/history.jsonl"
reset_agent grok
present "$home/.grok/config.toml"
present "$home/.grok/auth.json"
present "$home/.grok/mcp_credentials.json"
absent "$home/.grok/sessions"

mkdir -p "$home/.config/muse" "$home/.local/share/muse/sessions"
: > "$home/.config/muse/settings.json"
: > "$home/.config/muse/auth.json"
: > "$home/.config/muse/trust.json"
: > "$home/.local/share/muse/session-index.db"
reset_agent muse
present "$home/.config/muse/settings.json"
present "$home/.config/muse/auth.json"
absent "$home/.config/muse/trust.json"
absent "$home/.local/share/muse/session-index.db"

custom_config="$home/custom,config"
custom_data="$home/custom data"
mkdir -p "$custom_config/muse" "$custom_data/muse"
: > "$custom_config/muse/settings.json"
: > "$custom_config/muse/auth.json"
: > "$custom_data/muse/session-index.db"
HOME=$home XDG_CONFIG_HOME=$custom_config XDG_DATA_HOME=$custom_data "$reset_agents" muse
present "$custom_config/muse/auth.json"
absent "$custom_config/muse/settings.json"
absent "$custom_data/muse/session-index.db"

mkdir -p "$home/.config/opencode/plugins" "$home/.local/share/opencode" "$home/.cache/opencode/bin"
: > "$home/.config/opencode/opencode.json"
: > "$home/.config/opencode/tui.json"
: > "$home/.config/opencode/cli.json"
: > "$home/.config/opencode/plugins/notification.js"
: > "$home/.config/opencode/plugins/untracked.js"
: > "$home/.local/share/opencode/auth.json"
: > "$home/.local/share/opencode/opencode.db"
: > "$home/.cache/opencode/bin/tool"
reset_agent opencode
present "$home/.config/opencode/opencode.json"
present "$home/.config/opencode/cli.json"
present "$home/.config/opencode/plugins/notification.js"
present "$home/.local/share/opencode/auth.json"
absent "$home/.config/opencode/tui.json"
absent "$home/.config/opencode/plugins/untracked.js"
absent "$home/.local/share/opencode/opencode.db"
absent "$home/.cache/opencode/bin"

custom_cache=$home/custom-cache
mkdir -p "$custom_cache/opencode/bin"
: > "$custom_cache/opencode/bin/tool"
HOME=$home XDG_CACHE_HOME=$custom_cache "$reset_agents" opencode
absent "$custom_cache/opencode/bin"

outside=$scratch/outside
symlink_home=$scratch/symlink-home
mkdir -p "$outside" "$symlink_home"
: > "$outside/state"
ln -s "$outside" "$symlink_home/.grok"
if HOME=$symlink_home "$reset_agents" grok >/dev/null 2>&1; then
    printf 'FAIL: a harness home symlink was accepted\n' >&2
    exit 1
fi
present "$outside/state"

physical_home=$scratch/physical-home
linked_home=$scratch/linked-home
mkdir -p "$physical_home/.grok"
: > "$physical_home/.grok/runtime.json"
ln -s "$physical_home" "$linked_home"
HOME=$linked_home "$reset_agents" grok
absent "$physical_home/.grok/runtime.json"

physical_xdg_home=$scratch/physical-xdg-home
linked_xdg_home=$scratch/linked-xdg-home
mkdir -p "$physical_xdg_home/custom-config/muse" "$physical_xdg_home/custom-data/muse"
: > "$physical_xdg_home/custom-config/muse/auth.json"
: > "$physical_xdg_home/custom-data/muse/session-index.db"
ln -s "$physical_xdg_home" "$linked_xdg_home"
HOME=$linked_xdg_home \
    XDG_CONFIG_HOME=$physical_xdg_home/custom-config \
    XDG_DATA_HOME=$physical_xdg_home/custom-data \
    "$reset_agents" muse
present "$physical_xdg_home/custom-config/muse/auth.json"
absent "$physical_xdg_home/custom-data/muse/session-index.db"

preflight_home=$scratch/preflight-home
mkdir -p "$preflight_home/.config/muse" "$outside/share/muse"
: > "$preflight_home/.config/muse/runtime.json"
ln -s "$outside" "$preflight_home/.local"
if HOME=$preflight_home "$reset_agents" muse >/dev/null 2>&1; then
    printf 'FAIL: a parent symlink was accepted\n' >&2
    exit 1
fi
present "$preflight_home/.config/muse/runtime.json"

if usage=$(reset_agent invalid 2>&1); then
    printf 'FAIL: an unknown agent was accepted\n' >&2
    exit 1
fi
case $usage in
    *'agents: claude codex grok muse opencode'*) ;;
    *) printf 'FAIL: usage did not list each agent once\n' >&2; exit 1 ;;
esac

dispatch_bin=$scratch/dispatch-bin
mkdir -p "$dispatch_bin"
cp "$reset_agents" "$dispatch_bin/reset-agents"
chmod +x "$dispatch_bin/reset-agents"
cat > "$dispatch_bin/reset-agent-home" <<'EOF'
#!/bin/sh
printf '%s\n' "$@" > "$RESET_CAPTURE"
EOF
chmod +x "$dispatch_bin/reset-agent-home"
HOME=$home \
    XDG_CONFIG_HOME=$home/.config \
    XDG_DATA_HOME=$home/.local/share \
    XDG_CACHE_HOME=$home/.cache \
    RESET_CAPTURE=$scratch/targets \
    "$dispatch_bin/reset-agents"
printf '%s\n' \
    "$home/.claude" \
    "$home/.codex" \
    "$home/.grok" \
    "$home/.config/muse" \
    "$home/.local/share/muse" \
    "$home/.config/opencode" \
    "$home/.local/share/opencode" \
    "$home/.cache/opencode" > "$scratch/expected-targets"
if ! cmp -s "$scratch/expected-targets" "$scratch/targets"; then
    printf 'FAIL: default dispatch did not select every harness target\n' >&2
    exit 1
fi

printf 'reset-agents smoke checks passed\n'

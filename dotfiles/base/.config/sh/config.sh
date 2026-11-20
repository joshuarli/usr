# Nested shells source this file too; prepending only missing directories
# keeps a caller's PATH order (such as a pinned toolchain first) intact.
_usr_path_prepend() {
    for _usr_dir in "$@"; do
        case ":$PATH:" in
            *":$_usr_dir:"*) ;;
            *) PATH="$_usr_dir:$PATH" ;;
        esac
    done
    unset _usr_dir
}
# Harness shims call the sync-managed binaries in .local/bin directly.
_usr_path_prepend /opt/homebrew/bin /Applications/OrbStack.app/Contents/MacOS/xbin "$HOME/.cache/.bun/bin" "$HOME/go/bin" "$HOME/.cargo/bin" /opt/homebrew/opt/rustup/bin "$HOME/.local/bin" "$HOME/.local/lib/harness-shims" "$HOME/.local/share/sentry-devenv/bin" /opt/homebrew/share/google-cloud-sdk/bin
unset -f _usr_path_prepend
export PATH
export EDITOR="$HOME/.local/bin/e"
export PAGER="less"
export LS_COLORS="su=00:sg=00:ca=00:or=40;31;01:"
export XDG_CONFIG_HOME="$HOME/.config"
export XDG_CACHE_HOME="$HOME/.cache"
export XDG_DATA_HOME="$HOME/.local/share"
if [ "${TERM-}" = network ]; then
    TERM=xterm-256color
    export TERM
fi
export HOMEBREW_NO_AUTO_UPDATE="1"
export HOMEBREW_NO_INSTALLED_DEPENDENTS_CHECK="1"
export HOMEBREW_NO_INSTALL_CLEANUP="1"
export HOMEBREW_NO_ANALYTICS="1"
export CARGO_NET_GIT_FETCH_WITH_CLI="true"
export CLAUDE_CODE_MAX_WEB_SEARCHES_PER_SESSION="9001"
export OPENCODE_DISABLE_FFF="1"
export CLAUDE_CODE_SHELL="$HOME/.local/bin/bash"

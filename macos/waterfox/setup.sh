#!/bin/dash
set -eu

info() { printf '\033[1;32m==> \033[0m%s\n' "$*"; }
warn() { printf '\033[1;33mwarn:\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31merr:\033[0m %s\n' "$*" >&2; exit 1; }

FIREFOX_DIR="$HOME/Library/Application Support/Waterfox"
PROFILES_INI="$FIREFOX_DIR/profiles.ini"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

[ -f "$PROFILES_INI" ] || die "profiles.ini not found — is Firefox installed?"

# ── Detect default profile ─────────────────────────────────────────────────────
# Firefox 67+: [Install*] section has the authoritative default
DEFAULT_PATH=$(awk '
    /^\[Install/ { in_install=1; next }
    /^\[/        { in_install=0 }
    in_install && /^Default=/ { sub(/^Default=/, ""); print; exit }
' "$PROFILES_INI")

# Fallback: [Profile*] section with Default=1
if [ -z "$DEFAULT_PATH" ]; then
    DEFAULT_PATH=$(awk '
        /^\[Profile/ { in_p=1; path=""; rel=1; def=0; next }
        /^\[/        { if (in_p && def) { print path; exit } in_p=0 }
        in_p && /^Path=/       { sub(/^Path=/, ""); path=$0 }
        in_p && /^IsRelative=/ { sub(/^IsRelative=/, ""); rel=$0 }
        in_p && /^Default=1/   { def=1 }
        END { if (in_p && def) print path }
    ' "$PROFILES_INI")
fi

[ -z "$DEFAULT_PATH" ] && die "Could not detect default Firefox profile"

case "$DEFAULT_PATH" in
    /*) PROFILE_DIR="$DEFAULT_PATH" ;;
    *)  PROFILE_DIR="$FIREFOX_DIR/$DEFAULT_PATH" ;;
esac

[ -d "$PROFILE_DIR" ] || die "Profile directory does not exist: $PROFILE_DIR"
info "Profile: $PROFILE_DIR"

# ── Warn if Firefox is running ─────────────────────────────────────────────────
if pgrep -xq "firefox" 2>/dev/null || pgrep -xq "Firefox" 2>/dev/null; then
    warn "Firefox is running — changes take effect after restart"
fi

# ── Back up existing user.js if present ───────────────────────────────────────
USER_JS="$PROFILE_DIR/user.js"
if [ -f "$USER_JS" ]; then
    BACKUP="${USER_JS}.bak.$(date +%Y%m%d-%H%M%S)"
    cp "$USER_JS" "$BACKUP"
    info "Backed up existing user.js → $BACKUP"
fi

# ── Write user.js ──────────────────────────────────────────────────────────────
# Firefox reads user.js on every startup and applies these prefs over prefs.js.
info "Writing $USER_JS"
{
    printf '// Managed by setup.sh — written %s\n' "$(date '+%Y-%m-%d %H:%M:%S')"
    printf '// Re-run the script to update. Do not edit manually.\n\n'
    cat "$SCRIPT_DIR/user.js"
} > "$USER_JS"

# ── Install extensions ─────────────────────────────────────────────────────
install_ext() {
    _ext_name="$1" _ext_id="$2"
    mkdir -p "$PROFILE_DIR/extensions"
    (cd "$SCRIPT_DIR/$_ext_name" && zip -r -q -FS "$PROFILE_DIR/extensions/$_ext_id.xpi" .)
    info "Installed extension: $_ext_name"
}

install_ext "host-redirects" "host-redirects@local"

install_ext "allow-right-click" "{278b0ae0-da9d-4cc6-be81-5aa7f3202672}"

# ── Clean up extension caches ──────────────────────────────────────────────
# addonStartup.json.lz4 caches extension state; stale entries cause silent failures.
rm -f "$PROFILE_DIR/addonStartup.json.lz4"
# Empty staged dirs confuse Firefox into treating them as pending installs.
find "$PROFILE_DIR/extensions/staged" -mindepth 1 -maxdepth 1 -type d -empty -exec rm -rf {} + 2>/dev/null || true

info "Done. Restart Firefox to apply changes."

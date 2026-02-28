#!/usr/bin/env bash
set -euo pipefail

info() { printf '\e[1;32m==> \e[0m%s\n' "$*"; }
warn() { printf '\e[1;33mwarn:\e[0m %s\n' "$*"; }
die()  { printf '\e[1;31merr:\e[0m %s\n' "$*" >&2; exit 1; }

FIREFOX_DIR="$HOME/Library/Application Support/Waterfox"
PROFILES_INI="$FIREFOX_DIR/profiles.ini"

[[ -f "$PROFILES_INI" ]] || die "profiles.ini not found — is Firefox installed?"

# ── Detect default profile ─────────────────────────────────────────────────────
# Firefox 67+: [Install*] section has the authoritative default
DEFAULT_PATH=$(awk '
    /^\[Install/ { in_install=1; next }
    /^\[/        { in_install=0 }
    in_install && /^Default=/ { sub(/^Default=/, ""); print; exit }
' "$PROFILES_INI")

# Fallback: [Profile*] section with Default=1
if [[ -z "$DEFAULT_PATH" ]]; then
    DEFAULT_PATH=$(awk '
        /^\[Profile/ { in_p=1; path=""; rel=1; def=0; next }
        /^\[/        { if (in_p && def) { print path; exit } in_p=0 }
        in_p && /^Path=/       { sub(/^Path=/, ""); path=$0 }
        in_p && /^IsRelative=/ { sub(/^IsRelative=/, ""); rel=$0 }
        in_p && /^Default=1/   { def=1 }
        END { if (in_p && def) print path }
    ' "$PROFILES_INI")
fi

[[ -z "$DEFAULT_PATH" ]] && die "Could not detect default Firefox profile"

if [[ "$DEFAULT_PATH" = /* ]]; then
    PROFILE_DIR="$DEFAULT_PATH"
else
    PROFILE_DIR="$FIREFOX_DIR/$DEFAULT_PATH"
fi

[[ -d "$PROFILE_DIR" ]] || die "Profile directory does not exist: $PROFILE_DIR"
info "Profile: $PROFILE_DIR"

# ── Warn if Firefox is running ─────────────────────────────────────────────────
if pgrep -xq "firefox" 2>/dev/null || pgrep -xq "Firefox" 2>/dev/null; then
    warn "Firefox is running — changes take effect after restart"
fi

# ── Back up existing user.js if present ───────────────────────────────────────
USER_JS="$PROFILE_DIR/user.js"
if [[ -f "$USER_JS" ]]; then
    BACKUP="${USER_JS}.bak.$(date +%Y%m%d-%H%M%S)"
    cp "$USER_JS" "$BACKUP"
    info "Backed up existing user.js → $BACKUP"
fi

# ── Write user.js ──────────────────────────────────────────────────────────────
# Firefox reads user.js on every startup and applies these prefs over prefs.js.
# This file is the source of truth — re-run the script to update.
info "Writing $USER_JS"

{
printf '// Managed by firefox-setup.sh — written %s\n' "$(date '+%Y-%m-%d %H:%M:%S')"
printf '// Re-run the script to update. Do not edit manually.\n'
cat << 'PREFS'

// ── DNS ───────────────────────────────────────────────────────────────────────
// Disable DoH entirely — queries go through the local Unbound resolver instead
user_pref("network.trr.mode", 5);

// ── Network ───────────────────────────────────────────────────────────────────
user_pref("network.http.max-connections", 900);
user_pref("network.http.max-persistent-connections-per-server", 10);
user_pref("network.http.speculative-parallel-limit", 32);  // speculative pre-connects
user_pref("network.prefetch-next", true);                  // <link rel="prefetch">
user_pref("network.dns.disablePrefetch", false);           // DNS prefetch on hover
user_pref("network.dns.max_high_priority_threads", 8);
user_pref("network.dns.echconfig.enabled", true);          // Encrypted Client Hello; Reduces TLS handshake metadata leakage and can slightly improve connection time to supporting servers.
user_pref("network.http.http3.enabled", true);             // QUIC / HTTP3

// ── Cache ─────────────────────────────────────────────────────────────────────
user_pref("browser.cache.memory.enable", true);
user_pref("browser.cache.memory.capacity", 1048576); // 1 GB
user_pref("browser.cache.disk.capacity", 4000000);

// ── Rendering ─────────────────────────────────────────────────────────────────
user_pref("gfx.webrender.all", true);                      // GPU compositing

// ── Enhanced Tracking Protection ─────────────────────────────────────────────
// Redundant with uBlock Origin — uBO's lists are a superset. Disabling avoids
// processing every request twice.
user_pref("privacy.trackingprotection.enabled", false);
user_pref("privacy.trackingprotection.pbmode.enabled", false);
user_pref("privacy.trackingprotection.socialtracking.enabled", false);
user_pref("privacy.trackingprotection.cryptomining.enabled", false);
user_pref("privacy.trackingprotection.fingerprinting.enabled", false);

// ── Rendering / perceived load speed ─────────────────────────────────────────
user_pref("nglayout.initialpaint.delay", 0);               // paint immediately, don't wait 250ms
user_pref("content.notify.interval", 100000);              // flush layout to screen more frequently (default 120000µs)

// ── Request handling ──────────────────────────────────────────────────────────
user_pref("network.http.pacing.requests.enabled", false);  // disable request throttling on fast connections
user_pref("network.ssl_tokens_cache_capacity", 32768);     // TLS session cache (default 2048) — fewer full handshakes

// ── Disk I/O ──────────────────────────────────────────────────────────────────
user_pref("browser.sessionstore.interval", 60000);         // save session every 60s not 15s

// ── Autoplay ──────────────────────────────────────────────────────────────────
user_pref("media.autoplay.default", 5);                    // block all autoplay (saves CPU on media-heavy sites)

// ── Background services ───────────────────────────────────────────────────────
user_pref("app.normandy.enabled", false);                  // remote experiment system
user_pref("app.shield.optoutstudies.enabled", false);      // Firefox studies
user_pref("extensions.pocket.enabled", false);             // Pocket integration

// ── Safe Browsing ─────────────────────────────────────────────────────────────
// Uses a local blocklist, not real-time URL checks. uBO covers this.
user_pref("browser.safebrowsing.malware.enabled", false);
user_pref("browser.safebrowsing.phishing.enabled", false);

// ── Sponsored new tab content ─────────────────────────────────────────────────
user_pref("browser.newtabpage.activity-stream.showSponsored", false);
user_pref("browser.newtabpage.activity-stream.showSponsoredTopSites", false);

// ── Notifications / background push ───────────────────────────────────────────
user_pref("dom.serviceWorkers.enabled", true);             // keep: needed for SW caching
user_pref("dom.webnotifications.enabled", false);          // no push notifications
user_pref("dom.push.enabled", false);                      // no background push API
PREFS
} > "$USER_JS"

info "Done. Restart Firefox to apply changes."

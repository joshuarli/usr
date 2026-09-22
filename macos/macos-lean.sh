#!/bin/dash
# ============================================================================
# macos-lean.sh — Make macOS lean (27 Golden Gate)
# ============================================================================
#
# Canonical script. Legacy versioned scripts have been retired.
#
# Design: validate-then-act. Every launchd label is checked against a live
# index of labels installed on THIS Mac (built at startup from the plist
# files' Label keys, cached per OS build). Unknown labels are reported as
# STALE and skipped, never silently no-op'd. Run --audit after any OS upgrade
# to surface renamed/added services before applying. Apply converges: existing
# disabled jobs and matching preferences are left alone.
#
# macOS 27 (Golden Gate) verification: live-audited on 27.0 build 26A428.
# Every non-optional managed label below exists on that build. The 27 additions
# were read from their plists' ProgramArguments/MachServices before being
# categorized; see the Golden Gate audit record in macos-lean.md.
# pmset, mdutil, tmutil, defaults, networksetup, and log command syntax remains
# valid; tmutil disablelocal stays removed (dead since Tahoe).
#
# Disables ~170 unnecessary services via launchctl disable (persists across
# reboots) and launchctl bootout (immediate effect). Organized by category.
#
# DISABLED:
#   - Siri, Dictation, "Hey Siri", all assistant/speech services
#   - Apple Intelligence, on-device ML, generative AI, Private Cloud Compute,
#     call intelligence, cipher ML, intelligence tasks
#   - Golden Gate additions: Siri App Intents, Image Playground, Visual
#     Intelligence, CloudTelemetry, and SQLite maintenance-log telemetry
#   - Spotlight indexing (mdutil + all workers/scanners/knowledge agents)
#   - Telemetry: analytics, diagnostics, biome, ad tracking, A/B trials,
#     sysmond, tailspind, ecosystem analytics, USB-C telemetry,
#     web privacy, OS analytics, installer diagnostics
#   - Apple apps: Music, News, Weather, Sports, Shazam, Voice Memos,
#     TV/video subscriptions, Game Center, Wallet/Pay, Reminders, Maps,
#     Home/HomeKit, Tips, Stickers
#   - iMessage, FaceTime, phone call relay
#   - Continuity: Handoff, Sidecar, Universal Clipboard (NOT AirDrop/AirPlay)
#   - Family Sharing, parental controls, Screen Time
#   - Screen sharing (giving and receiving)
#   - Photos: ML analysis, Photo Stream, iCloud Photos sync
#   - Location: routine tracking, Find My, geo services
#   - iCloud: mail agent, Photos sync (Drive + Keychain preserved)
#   - Mail: maild, mail extensions, iCloud mail agent
#   - Safari: history, bookmarks sync, notifications, web inspector
#   - App Store: storefront, commerce, StoreKit, update notifications
#   - Focus/DND: donotdisturbd
#   - Accessibility: motion tracking, hearing, voice banking
#   - Misc: Time Machine, translation, avatars/Memoji,
#     content caching, accessory firmware updates, app placeholders,
#     settings sync, Continuity Camera, Thread/smart home, DND/Focus,
#     recent items, NFC
#   - Crash reporting: ReportCrash, crash dialogs suppressed
#   - Wireless/network diagnostics: symptomsd, spindump
#   - Performance: window/scroll animations, Dock bounce, transparency,
#     Mission Control animation speed, window resize delay, screensaver
#   - App state: window state not saved on quit, new docs default to local
#   - Power management (battery): Power Nap, TCP keepalive, proximity wake,
#     Wake on LAN, TTY keepawake, aggressive standby (10 min),
#     hibernatemode 0 (no sleepimage), display sleep 2 min, system sleep 10 min,
#     auto power-off after 30 min standby
#   - Network: IPv6 off on all non-VPN interfaces, mDNS multicast ads off,
#     captive network detection off
#   - Logging: unified log system disabled
#
# PRESERVED:
#   - QuickLook (spacebar preview, thumbnails)
#   - Touch ID (biometrickitd)
#   - AirDrop & AirPlay (sharingd, rapportd, AirPlayUIAgent, AirPlayXPCHelper)
#   - Core networking: WiFi, Bluetooth, DNS, mDNS, Tailscale
#   - Audio: coreaudiod, media keys (rcd), system sounds
#   - Display: WindowServer, Dock, Finder, WindowManager
#   - Security: Gatekeeper, XProtect, keychain (local), sandboxd, SIP
#   - Notifications (notificationcenterui, usernoted)
#   - Clipboard (pboard)
#   - Text input (IMK, keyboard services, spell check)
#   - Disk management, APFS, file systems
#   - Login/auth: loginwindow, SecurityAgent, opendirectoryd
#   - iCloud Drive (bird, cloudd, FileProvider, nsurlsessiond)
#   - iCloud Keychain / Apple Passwords (swcd, accountsd, akd, autofill)
#   - Calendar.app (calaccessd)
#   - Photos.app local library (photolibraryd)
#   - Notes.app (synapse content linking, back-links)
#   - Camera & video calls (videoconference.camera, CMIO extensions)
#   - AirPods (Bluetooth LE audio, cloud pairing)
#   - Kandji MDM agent and CrowdStrike Falcon when installed
#
# AUDITED AND DELIBERATELY KEPT (see --audit; do not "fix" by disabling):
#   - BackgroundTaskManagement (agent + daemon): Login Items infrastructure
#     and background-task consent prompts; 27's Background App Activity UI
#     sits on top of it. Disabling breaks login items.
#   - sysdiagnose agent/helper: on-demand manual diagnostic collection.
#     Keep — you want this when something breaks (logging is already off).
#   - Golden Gate candidates: BackgroundTaskManagement is Login Items
#     infrastructure; sysdiagnose remains on-demand diagnostics. Both stay
#     preserved. The remaining candidates were added to the disable lists only
#     after their plist programs established their Siri, AI, or telemetry role.
#
# Usage:
#   ./macos-lean.sh              # Apply changes (requires sudo)
#   ./macos-lean.sh --dry-run    # Preview changes only (stale labels flagged)
#   ./macos-lean.sh --audit      # Validate labels vs live OS, no sudo, no changes
#   ./macos-lean.sh --revert     # Re-enable everything
#
# Always run --audit first after an OS upgrade, then --dry-run, then apply.
# Apply snapshots pre-change state to ~/.local/state/macos-lean/.
#
# SIP note: bootout is blocked by SIP (error 150). This script uses
#           launchctl disable (persists across reboots) + kill (immediate
#           effect) instead. The disabled flag prevents MachService/XPC
#           respawns even with SIP on.
#
# 27 note: disables live in /private/var/db/com.apple.xpc.launchd/disabled*.plist
#          and may reset on major upgrades — re-run --audit + apply after
#          upgrading. Policy items (Siri, Apple Intelligence, analytics) are
#          better enforced via MDM restriction profiles, which survive upgrades;
#          launchctl covers what profiles can't express.
#
# Nuclear revert:
#   sudo rm /private/var/db/com.apple.xpc.launchd/disabled.501.plist
#   sudo rm /private/var/db/com.apple.xpc.launchd/disabled.plist
#   sudo mdutil -a -i on && reboot
#
# Verify: launchctl print-disabled gui/$(id -u)
#         sudo launchctl print-disabled system
# ============================================================================

set -u

DRY_RUN=false
REVERT=false
AUDIT=false

print_usage() {
  echo "Usage: $0 [--dry-run] [--audit] [--revert]"
  echo "  (no flags)  apply changes (requires sudo)"
  echo "  --dry-run   preview; stale labels flagged, no changes"
  echo "  --audit     validate labels vs live OS; no sudo, no changes"
  echo "  --revert    re-enable everything this script manages"
}

while [ $# -gt 0 ]; do
  case $1 in
    --dry-run) DRY_RUN=true; shift ;;
    --audit) AUDIT=true; shift ;;
    --revert)  REVERT=true; shift ;;
    -h|--help) print_usage; exit 0 ;;
    *) print_usage; exit 1 ;;
  esac
done

if $AUDIT && { $DRY_RUN || $REVERT; }; then
  echo "Error: --audit is mutually exclusive with --dry-run/--revert"
  exit 1
fi

UID_NUM=$(id -u)
MACOS_VERSION=$(sw_vers -productVersion 2>/dev/null || echo "unknown")
# Fixed collation: sort/comm/grep must agree, otherwise comm reports false
# uniques (this bit the first version of --audit).
export LC_ALL=C
OS_MAJOR=$(printf '%s' "$MACOS_VERSION" | cut -d. -f1)
case "$OS_MAJOR" in
  15) OS_NAME="Sequoia" ;;
  26) OS_NAME="Tahoe" ;;
  27) OS_NAME="Golden Gate" ;;
  *) OS_NAME="unvalidated (lists verified on 15/26; 27 by --audit)" ;;
esac

if $AUDIT; then
  echo "macOS Lean — AUDIT (${OS_NAME} ${MACOS_VERSION}, no changes, no sudo)"
elif $REVERT; then
  echo "macOS Lean — REVERT mode (${OS_NAME} ${MACOS_VERSION})"
elif $DRY_RUN || $AUDIT; then
  echo "macOS Lean — DRY RUN (${OS_NAME} ${MACOS_VERSION}, no changes)"
else
  echo "macOS Lean — ${OS_NAME} ${MACOS_VERSION}"
fi
echo "User UID: ${UID_NUM}"
echo ""

# --- Temp state (label index, audit records) ---
_REAL_LABELS=$(mktemp /tmp/macos-lean-labels.XXXXXX)
_AUDIT_TARGETS=$(mktemp /tmp/macos-lean-targets.XXXXXX)
_AUDIT_PRESERVE=$(mktemp /tmp/macos-lean-preserve.XXXXXX)
_DISABLED_USER=$(mktemp /tmp/macos-lean-disabled-user.XXXXXX)
_DISABLED_SYSTEM=$(mktemp /tmp/macos-lean-disabled-system.XXXXXX)
trap 'rm -f "$_REAL_LABELS" "$_AUDIT_TARGETS" "$_AUDIT_PRESERVE" "$_DISABLED_USER" "$_DISABLED_SYSTEM"' EXIT

N_APPLIED=0
N_SKIPPED=0
N_UNCHANGED=0

# --- Live label index (cached per OS build; plutil per-file is slow) ---
BUILD_VER=$(sw_vers -buildVersion 2>/dev/null || echo "unknown")
_INDEX_CACHE="/tmp/macos-lean-index-${BUILD_VER}.txt"
build_label_index() {
  if [ -f "$_INDEX_CACHE" ]; then
    cp "$_INDEX_CACHE" "$_REAL_LABELS"
    return
  fi
  for f in /System/Library/LaunchAgents/*.plist /System/Library/LaunchDaemons/*.plist \
           /Library/LaunchAgents/*.plist /Library/LaunchDaemons/*.plist; do
    [ -f "$f" ] || continue
    plutil -extract Label raw "$f" 2>/dev/null
  done | LC_ALL=C sort -u > "$_REAL_LABELS"
  cp "$_REAL_LABELS" "$_INDEX_CACHE" 2>/dev/null || true
}
build_label_index

is_known_label() { grep -Fxq "$1" "$_REAL_LABELS" 2>/dev/null; }

# --- Pre-change snapshot (apply/revert only) ---
snapshot_state() {
  if $DRY_RUN || $AUDIT; then return; fi
  SNAPDIR="${HOME}/.local/state/macos-lean"
  mkdir -p "$SNAPDIR" 2>/dev/null || return
  SNAP="${SNAPDIR}/snapshot-$(date +%Y%m%d-%H%M%S)"
  {
    echo "# macOS ${MACOS_VERSION} $(date)"
    echo "## launchctl print-disabled gui/${UID_NUM}"
    launchctl print-disabled "gui/${UID_NUM}" 2>/dev/null || true
    echo "## sudo launchctl print-disabled system"
    sudo launchctl print-disabled system 2>/dev/null || true
  } > "$SNAP" 2>/dev/null
  echo "Snapshot: ${SNAP}"
  echo ""
}

# Cache disabled state before applying anything. A repeated apply must leave
# already-disabled jobs alone, including their running processes.
load_disabled_state() {
  if $DRY_RUN || $AUDIT || $REVERT; then return; fi
  if ! launchctl print-disabled "gui/${UID_NUM}" > "$_DISABLED_USER" 2>/dev/null; then
    echo "Error: unable to read disabled user services"
    exit 1
  fi
  if ! sudo launchctl print-disabled system > "$_DISABLED_SYSTEM" 2>/dev/null; then
    echo "Error: unable to read disabled system services"
    exit 1
  fi
}

# --- Audit report (macos-lean.md workflow, built in) ---
audit_report() {
  LC_ALL=C sort -u "$_AUDIT_TARGETS" -o "$_AUDIT_TARGETS"
  LC_ALL=C sort -u "$_AUDIT_PRESERVE" -o "$_AUDIT_PRESERVE"
  _AUDIT_ALL=$(mktemp /tmp/macos-lean-all.XXXXXX)
  cat "$_AUDIT_TARGETS" "$_AUDIT_PRESERVE" | LC_ALL=C sort -u > "$_AUDIT_ALL"
  echo ""
  echo "=== Audit: stale disable targets (in script, NOT on this OS) ==="
  comm -23 "$_AUDIT_TARGETS" "$_REAL_LABELS" | sed 's/^/  STALE  /'
  echo ""
  echo "=== Audit: stale preserve checks (in script, NOT on this OS) ==="
  comm -23 "$_AUDIT_PRESERVE" "$_REAL_LABELS" | sed 's/^/  STALE  /'
  echo ""
  echo "=== Audit: candidate new services (on OS, not in script) ==="
  comm -23 "$_REAL_LABELS" "$_AUDIT_ALL" \
    | grep -i -E 'intellig|siri|analytic|telemetry|biome|trial|diagnos|genmoji|playground|writing.tool|backgroundtask|background.task' \
    | sed 's/^/  NEW?   /'
  echo ""
  echo "Review NEW? lines before disabling: check the plist's ProgramArguments"
  echo "— names lie (e.g. avconferenced.plist hosts videoconference.camera)."
  rm -f "$_AUDIT_ALL"
}

# --- Sudo keepalive (apply/revert only) ---
if ! $DRY_RUN && ! $AUDIT; then
  sudo -v || { echo "Error: sudo required"; exit 1; }
  while true; do sudo -n true; sleep 50; kill -0 "$$" || exit; done 2>/dev/null &
  SUDO_PID=$!
  trap 'kill $SUDO_PID 2>/dev/null; rm -f "$_REAL_LABELS" "$_AUDIT_TARGETS" "$_AUDIT_PRESERVE" "$_DISABLED_USER" "$_DISABLED_SYSTEM"' EXIT
fi

# --- Helpers ---

is_disabled() {
  _disabled_label=$1
  _disabled_state=$2
  grep -Fq "\"${_disabled_label}\" => disabled" "$_disabled_state" 2>/dev/null || \
    grep -Fq "\"${_disabled_label}\" => true" "$_disabled_state" 2>/dev/null
}

is_user_disabled() { is_disabled "$1" "$_DISABLED_USER"; }
is_system_disabled() { is_disabled "$1" "$_DISABLED_SYSTEM"; }

mark_disabled() {
  printf '\t"%s" => disabled\n' "$1" >> "$2"
}

# Write a preference only when it differs. This keeps repeated applies from
# rewriting plist files or restarting consumers of an unchanged preference.
DEFAULT_CHANGED=false
ensure_default() {
  DEFAULT_CHANGED=false
  _default_domain=$1
  _default_key=$2
  _default_expected=$3
  _default_type=$4
  _default_value=$5
  _default_current=$(defaults read "$_default_domain" "$_default_key" 2>/dev/null || true)
  [ "$_default_current" = "$_default_expected" ] && return
  if defaults write "$_default_domain" "$_default_key" "$_default_type" "$_default_value"; then
    DEFAULT_CHANGED=true
  else
    echo "FAIL defaults ${_default_domain} ${_default_key}"
    return 1
  fi
}

SYSTEM_DEFAULT_CHANGED=false
ensure_system_default() {
  SYSTEM_DEFAULT_CHANGED=false
  _system_default_domain=$1
  _system_default_key=$2
  _system_default_expected=$3
  _system_default_type=$4
  _system_default_value=$5
  _system_default_current=$(sudo defaults read "$_system_default_domain" "$_system_default_key" 2>/dev/null || true)
  [ "$_system_default_current" = "$_system_default_expected" ] && return
  if sudo defaults write "$_system_default_domain" "$_system_default_key" "$_system_default_type" "$_system_default_value"; then
    SYSTEM_DEFAULT_CHANGED=true
  else
    echo "FAIL defaults ${_system_default_domain} ${_system_default_key}"
    return 1
  fi
}

disable_user() {
  label=$1
  if $AUDIT; then
    printf '%s\n' "$label" >> "$_AUDIT_TARGETS"
    if is_known_label "$label"; then
      echo "  ${label}"
    else
      echo "  STALE ${label}"
    fi
  elif $DRY_RUN || $AUDIT; then
    if is_known_label "$label"; then
      echo "  ${label}"
    else
      echo "  STALE ${label} (not on ${OS_NAME} ${MACOS_VERSION} — would skip)"
    fi
  elif $REVERT; then
    # Attempt even stale labels: clears orphaned disabled.plist entries
    # left by older OS releases.
    launchctl enable "gui/${UID_NUM}/${label}" 2>/dev/null
    echo "  + ${label}"
    N_APPLIED=$((N_APPLIED + 1))
  else
    if ! is_known_label "$label"; then
      echo "  STALE ${label} (skipped)"
      N_SKIPPED=$((N_SKIPPED + 1))
      return
    fi
    if is_user_disabled "$label"; then
      echo "  = ${label} (already disabled)"
      N_UNCHANGED=$((N_UNCHANGED + 1))
      return
    fi
    if launchctl disable "gui/${UID_NUM}/${label}" 2>/dev/null; then
      N_APPLIED=$((N_APPLIED + 1))
      mark_disabled "$label" "$_DISABLED_USER"
    else
      echo "  FAIL ${label} (disable rejected)"
      N_SKIPPED=$((N_SKIPPED + 1))
      return
    fi
    # bootout is blocked by SIP; kill the process directly instead.
    # The disabled flag prevents MachService/LaunchEvent respawns.
    pid=$(launchctl print "gui/${UID_NUM}/${label}" 2>/dev/null | sed -n 's/.*pid = \([0-9]*\).*/\1/p')
    if [ -n "$pid" ]; then
      kill "$pid" 2>/dev/null || true
    fi
    echo "  - ${label}"
  fi
}

SYSTEM_LABELS=""

disable_system() {
  label=$1
  if $AUDIT; then
    printf '%s\n' "$label" >> "$_AUDIT_TARGETS"
    if is_known_label "$label"; then
      echo "  ${label}"
    else
      echo "  STALE ${label}"
    fi
  elif $DRY_RUN || $AUDIT; then
    if is_known_label "$label"; then
      echo "  ${label}"
    else
      echo "  STALE ${label} (not on ${OS_NAME} ${MACOS_VERSION} — would skip)"
    fi
  elif $REVERT; then
    SYSTEM_LABELS="${SYSTEM_LABELS} ${label}"
    echo "  + ${label}"
  else
    if ! is_known_label "$label"; then
      echo "  STALE ${label} (skipped)"
      N_SKIPPED=$((N_SKIPPED + 1))
      return
    fi
    if is_system_disabled "$label"; then
      echo "  = ${label} (already disabled)"
      N_UNCHANGED=$((N_UNCHANGED + 1))
      return
    fi
    SYSTEM_LABELS="${SYSTEM_LABELS} ${label}"
    echo "  - ${label}"
  fi
}

# Called once after all disable_system calls to apply in a single sudo.
flush_system() {
  if $AUDIT; then SYSTEM_LABELS=""; return; fi
  [ -z "$SYSTEM_LABELS" ] && return
  if $REVERT; then
    for label in $SYSTEM_LABELS; do
      sudo launchctl enable "system/${label}" 2>/dev/null
      N_APPLIED=$((N_APPLIED + 1))
    done
  else
    for label in $SYSTEM_LABELS; do
      if sudo launchctl disable "system/${label}" 2>/dev/null; then
        N_APPLIED=$((N_APPLIED + 1))
        mark_disabled "$label" "$_DISABLED_SYSTEM"
      else
        echo "  FAIL ${label} (disable rejected)"
        N_SKIPPED=$((N_SKIPPED + 1))
      fi
    done
    # Kill any that are still running
    for label in $SYSTEM_LABELS; do
      short=$(echo "$label" | sed 's/.*\.//')
      pid=$(pgrep -x "$short" 2>/dev/null | head -1)
      if [ -n "$pid" ]; then
        sudo kill -9 "$pid" 2>/dev/null || true
      fi
    done
  fi
  SYSTEM_LABELS=""
}

section() { echo ""; echo "=== $1 ==="; }

VERIFY_FAIL=0

ensure_user() {
  label=$1
  desc=$2
  if $AUDIT; then
    printf '%s\n' "$label" >> "$_AUDIT_PRESERVE"
    if is_known_label "$label"; then
      echo "  --  ${desc} (${label})"
    else
      echo "  STALE  ${desc} (${label}) — preserve check can never pass"
    fi
    return
  fi
  if $DRY_RUN || $AUDIT; then
    echo "  --  ${desc} (${label})"
    return
  fi
  # force-enable in case it was accidentally disabled
  if ! $REVERT; then
    launchctl enable "gui/${UID_NUM}/${label}" 2>/dev/null
  fi
  if launchctl print "gui/${UID_NUM}/${label}" >/dev/null 2>&1; then
    echo "  OK  ${desc}"
  else
    echo "  FAIL ${desc} — not loaded (${label})"
    VERIFY_FAIL=$((VERIFY_FAIL + 1))
  fi
}

# Endpoint-security software is optional. Only audit or verify it when its
# launchd plist is installed; an absent third-party product is not a stale
# macOS label and must not make the audit fail.
ensure_optional_user() {
  label=$1
  desc=$2
  if ! is_known_label "$label"; then
    echo "  --  ${desc} not installed (${label})"
    return
  fi
  ensure_user "$label" "$desc"
}

ensure_system() {
  label=$1
  desc=$2
  if $AUDIT; then
    printf '%s\n' "$label" >> "$_AUDIT_PRESERVE"
    if is_known_label "$label"; then
      echo "  --  ${desc} (${label})"
    else
      echo "  STALE  ${desc} (${label}) — preserve check can never pass"
    fi
    return
  fi
  if $DRY_RUN || $AUDIT; then
    echo "  --  ${desc} (${label})"
    return
  fi
  if ! $REVERT; then
    sudo launchctl enable "system/${label}" 2>/dev/null
  fi
  if sudo launchctl print "system/${label}" >/dev/null 2>&1; then
    echo "  OK  ${desc}"
  else
    echo "  FAIL ${desc} — not loaded (${label})"
    VERIFY_FAIL=$((VERIFY_FAIL + 1))
  fi
}

# ============================================================================
# USER AGENTS
# ============================================================================

snapshot_state
load_disabled_state

section "Siri & Assistant"
# Golden Gate 27: SiriAppIntentsRuntime's siriappintentsd serves Siri app
# intents, so it belongs with the existing Siri disable set.
for s in \
  com.apple.assistant_service \
  com.apple.assistant_cdmd \
  com.apple.assistantd \
  com.apple.Siri.agent \
  com.apple.siriknowledged \
  com.apple.siriactionsd \
  com.apple.sirittsd \
  com.apple.SiriTTSTrainingAgent \
  com.apple.siriinferenced \
  com.apple.corespeechd \
  com.apple.DictationIM \
  com.apple.speech.speechdatainstallerd \
  com.apple.parsec-fbf \
  com.apple.parsecd \
  com.apple.suggestd \
  com.apple.proactived \
  com.apple.proactiveeventtrackerd \
  com.apple.ContextStoreAgent \
  com.apple.duetexpertd \
  com.apple.siriappintentsd \
; do disable_user "$s"; done

section "Apple Intelligence & ML"
# Golden Gate 27: imageplaygroundd (SuggestedImage.framework) and
# visualintelligenced (VisualIntelligenceServices.framework) are generative
# image and visual-intelligence agents, including background maintenance work.
for s in \
  com.apple.intelligenceplatformd \
  com.apple.intelligenceflowd \
  com.apple.intelligencecontextd \
  com.apple.intelligencetasksd \
  com.apple.intelligentroutingd \
  com.apple.knowledgeconstructiond \
  com.apple.generativeexperiencesd \
  com.apple.privatecloudcomputed \
  com.apple.textunderstandingd \
  com.apple.ciphermld \
  com.apple.milod \
  com.apple.mlhostd \
  com.apple.mlruntimed \
  com.apple.ModelCatalogAgent \
  com.apple.imageplaygroundd \
  com.apple.visualintelligenced \
; do disable_user "$s"; done

section "Telemetry & Analytics"
for s in \
  com.apple.ap.adprivacyd \
  com.apple.ap.promotedcontentd \
  com.apple.BiomeAgent \
  com.apple.biomesyncd \
  com.apple.UsageTrackingAgent \
  com.apple.triald \
  com.apple.inputanalyticsd \
  com.apple.dprivacyd \
  com.apple.diagnostics_agent \
  com.apple.diagnosticspushd \
  com.apple.DiagnosticsReporter \
  com.apple.feedbackd \
  com.apple.betaenrollmentagent \
  com.apple.appleseed.seedusaged \
  com.apple.appleseed.seedusaged.postinstall \
  com.apple.amsengagementd \
  com.apple.analyticsagent \
  com.apple.geoanalyticsd \
  com.apple.metrickitd \
  com.apple.diagnosticextensionsd \
  com.apple.backgroundassets.user \
  com.apple.spindump_agent \
  com.apple.webprivacyd \
  com.apple.ecosystemagent \
; do disable_user "$s"; done

section "Apple Apps (Music, News, Weather, Games, Maps, etc.)"
for s in \
  com.apple.AMPArtworkAgent \
  com.apple.AMPDeviceDiscoveryAgent \
  com.apple.AMPLibraryAgent \
  com.apple.AMPDevicesAgent \
  com.apple.AMPSystemPlayerAgent \
  com.apple.amp.mediasharingd \
  com.apple.itunescloudd \
  com.apple.newsd \
  com.apple.financed \
  com.apple.tipsd \
  com.apple.weatherd \
  com.apple.sportsd \
  com.apple.shazamd \
  com.apple.voicememod \
  com.apple.watchlistd \
  com.apple.videosubscriptionsd \
  com.apple.gamed \
  com.apple.GameController.gamecontrolleragentd \
  com.apple.GamePolicyAgent \
  com.apple.gamesaved \
  com.apple.replayd \
  com.apple.remindd \
  com.apple.passd \
  com.apple.Maps.mapspushd \
  com.apple.maps.destinationd \
  com.apple.Maps.mapssyncd \
  com.apple.homed \
  com.apple.homeenergyd \
  com.apple.homeeventsd \
  com.apple.followupd \
  com.apple.sociallayerd \
  com.apple.StatusKitAgent \
  com.apple.studentd \
  com.apple.stickersd \
  com.apple.navd \
  com.apple.amsondevicestoraged \
  com.apple.amsaccountsd \
  com.apple.avatarsd \
  com.apple.mobiletimerd \
  com.apple.appplaceholdersyncd \
; do disable_user "$s"; done

section "iMessage, FaceTime & Phone"
for s in \
  com.apple.imagent \
  com.apple.imautomatichistorydeletionagent \
  com.apple.imcore.imtransferagent \
  com.apple.CallHistoryPluginHelper \
  com.apple.CallHistorySyncHelper \
  com.apple.callhistoryd \
  com.apple.callintelligenced \
  com.apple.telephonyutilities.callservicesd \
  com.apple.facetimemessagestored \
  com.apple.CommCenter \
; do disable_user "$s"; done

section "Continuity (keeping sharingd/rapportd for AirDrop & AirPlay)"
for s in \
  com.apple.ensemble \
  com.apple.sidecar-relay \
  com.apple.sidecar-display-agent \
  com.apple.coreservices.useractivityd \
  com.apple.cmio.ContinuityCaptureAgent \
; do disable_user "$s"; done

section "Family & Parental Controls"
for s in \
  com.apple.familycircled \
  com.apple.familycontrols.useragent \
  com.apple.FamilyControlsAgent \
  com.apple.familynotificationd \
  com.apple.ScreenTimeAgent \
  com.apple.askpermissiond \
  com.apple.AskPermissionUI \
; do disable_user "$s"; done

section "Screen Sharing"
for s in \
  com.apple.screensharing.agent \
  com.apple.screensharing.menuextra \
  com.apple.screensharing.MessagesAgent \
; do disable_user "$s"; done

section "Photos & Media Analysis"
for s in \
  com.apple.photoanalysisd \
  com.apple.mediaanalysisd \
  com.apple.mediastream.mstreamd \
  com.apple.cloudphotod \
; do disable_user "$s"; done

section "Location Tracking & Find My"
for s in \
  com.apple.routined \
  com.apple.geodMachServiceBridge \
  com.apple.knowledge-agent \
  com.apple.icloud.searchpartyuseragent \
  com.apple.findmy.findmylocateagent \
  com.apple.findmymacmessenger \
  com.apple.icloud.findmydeviced.findmydevice-user-agent \
; do disable_user "$s"; done

section "Spotlight & Indexing"
for s in \
  com.apple.Spotlight \
  com.apple.corespotlightd \
  com.apple.corespotlightservice \
  com.apple.spotlightknowledged \
  com.apple.spotlightknowledged.importer \
  com.apple.spotlightknowledged.updater \
  com.apple.managedcorespotlightd \
  com.apple.metadata.mdbulkimport \
  com.apple.metadata.mdwrite \
  com.apple.metadata.mdflagwriter \
  com.apple.mdworker.shared \
  com.apple.mdworker.single.arm64 \
  com.apple.mdworker.single.x86_64 \
  com.apple.mdworker.sizing \
  com.apple.mdworker.mail \
; do disable_user "$s"; done

section "Mail (not using)"
for s in \
  com.apple.email.maild \
  com.apple.MENotificationService \
  com.apple.icloudmailagent \
; do disable_user "$s"; done

section "Safari (browser only — keeping PasswordBreachAgent for Passwords.app)"
for s in \
  com.apple.SafariBookmarksSyncAgent \
  com.apple.SafariNotificationAgent \
  com.apple.SafariLaunchAgent \
  com.apple.Safari.History \
  com.apple.SafariHistoryServiceAgent \
  com.apple.webinspectord \
; do disable_user "$s"; done

section "App Store"
for s in \
  com.apple.appstoreagent \
  com.apple.appstorecomponentsd \
  com.apple.commerce \
  com.apple.storeaccountd \
  com.apple.storedownloadd \
  com.apple.storekitagent \
  com.apple.storelegacy \
  com.apple.storeassetd \
  com.apple.storeuid \
  com.apple.SoftwareUpdateNotificationManager \
; do disable_user "$s"; done

section "Focus & Misc"
for s in \
  com.apple.donotdisturbd \
  com.apple.accessibility.MotionTrackingAgent \
  com.apple.accessibility.heard \
  com.apple.voicebankingd \
  com.apple.dataaccess.dataaccessd \
  com.apple.progressd \
  com.apple.TMHelperAgent \
  com.apple.translationd \
  com.apple.peopled \
  com.apple.contacts.donation-agent \
  com.apple.ThreadCommissionerService \
  com.apple.AssetCacheLocatorService \
  com.apple.MobileAccessoryUpdater.fudHelperAgent \
  com.apple.syncdefaultsd \
  com.apple.recentsd \
  com.apple.ReportCrash \
; do disable_user "$s"; done

# ============================================================================
# SYSTEM DAEMONS (may need SIP disabled for full persistence)
# ============================================================================

section "System — Siri"
disable_system com.apple.corespeechd_system

section "System — Analytics"
# Golden Gate 27: CloudTelemetry.framework submits/maintains telemetry, and
# dbtelemetryd collects SQLite logs daily while on external power.
for s in \
  com.apple.analyticsd \
  com.apple.audioanalyticsd \
  com.apple.diagnosticd \
  com.apple.diagnosticservicesd \
  com.apple.dprivacyd \
  com.apple.ecosystemanalyticsd \
  com.apple.ecosystemd \
  com.apple.osanalytics.osanalyticshelper \
  com.apple.usbctelemetryd \
  com.apple.InstallerDiagnostics.installerdiagd \
  com.apple.InstallerDiagnostics.installerdiagwatcher \
  com.apple.wifianalyticsd \
  com.apple.triald.system \
  com.apple.sysmond \
  com.apple.tailspind \
  com.apple.cloudtelemetryd \
  com.apple.libsqlite3.dbtelemetryd \
; do disable_system "$s"; done

section "System — App Store"
for s in \
  com.apple.appstored \
  com.apple.storereceiptinstaller \
; do disable_system "$s"; done

section "System — Unused Services"
for s in \
  com.apple.backupd \
  com.apple.backupd-helper \
  com.apple.biomed \
  com.apple.coreduetd \
  com.apple.diagnosticextensions.osx.timemachine.helper \
  com.apple.familycontrols \
  com.apple.ftp-proxy \
  com.apple.GameController.gamecontrollerd \
  com.apple.gamepolicyd \
  com.apple.netbiosd \
  com.apple.screensharing \
  com.apple.dhcp6d \
; do disable_system "$s"; done

section "System — Wireless & Network Diagnostics"
for s in \
  com.apple.symptomsd \
  com.apple.symptomsd-diag \
  com.apple.spindump \
  com.apple.nfcd \
; do disable_system "$s"; done

section "System — Find My"
for s in \
  com.apple.findmymacd \
  com.apple.findmy.findmybeaconingd \
  com.apple.findmymacmessenger \
  com.apple.icloud.findmydeviced \
  com.apple.icloud.searchpartyd \
; do disable_system "$s"; done

section "System — Spotlight Indexing"
for s in \
  com.apple.diagnosticextensions.osx.spotlight.helper \
  com.apple.metadata.mds.index \
  com.apple.metadata.mds.scan \
  com.apple.metadata.mds.spindump \
; do disable_system "$s"; done

flush_system

# ============================================================================
# SPOTLIGHT — mdutil
# ============================================================================

section "Spotlight Indexing (mdutil)"
if $DRY_RUN || $AUDIT; then
  echo "  would run: sudo mdutil -a -i off"
elif $REVERT; then
  sudo mdutil -a -i on 2>/dev/null
  echo "  Spotlight indexing re-enabled"
else
  # mdutil -E erases and rebuilds indexes, creating work on every apply.
  # Disabling indexing is the desired steady state and is repeat-safe.
  sudo mdutil -a -i off 2>/dev/null
  echo "  Indexing disabled"
fi

section "Time Machine"
if $DRY_RUN || $AUDIT; then
  echo "  would disable Time Machine"
elif $REVERT; then
  sudo tmutil enable 2>/dev/null || true
  echo "  Time Machine re-enabled"
else
  # Belt-and-suspenders alongside backupd/backupd-helper being disabled.
  sudo tmutil disable 2>/dev/null || true
  echo "  Time Machine disabled"
fi

# ============================================================================
# DEFAULTS — preference-level disabling
# ============================================================================

section "System Preferences"
if $DRY_RUN || $AUDIT; then
  echo "  would disable Siri (assistant, menu bar, voice trigger)"
  echo "  would disable Spotlight suggestions"
elif $REVERT; then
  defaults delete com.apple.assistant.support 'Assistant Enabled' 2>/dev/null || true
  defaults delete com.apple.Siri StatusMenuVisible 2>/dev/null || true
  defaults delete com.apple.Siri UserHasDeclinedEnable 2>/dev/null || true
  defaults delete com.apple.Siri VoiceTriggerUserEnabled 2>/dev/null || true
  defaults delete com.apple.lookup.shared LookupSuggestionsDisabled 2>/dev/null || true
  echo "  Preferences restored to defaults"
else
  ensure_default com.apple.assistant.support 'Assistant Enabled' 0 -bool false || exit 1
  ensure_default com.apple.Siri StatusMenuVisible 0 -bool false || exit 1
  ensure_default com.apple.Siri UserHasDeclinedEnable 1 -bool true || exit 1
  ensure_default com.apple.Siri VoiceTriggerUserEnabled 0 -bool false || exit 1
  ensure_default com.apple.lookup.shared LookupSuggestionsDisabled 1 -bool true || exit 1
  echo "  Siri fully disabled (assistant, menu bar, voice trigger)"
  echo "  Spotlight suggestions disabled"
fi

section "App Store Preferences"
if $DRY_RUN || $AUDIT; then
  echo "  would disable App Store auto-check, auto-download, auto-update"
elif $REVERT; then
  defaults delete com.apple.commerce AutoUpdate 2>/dev/null || true
  defaults delete com.apple.commerce AutoUpdateRestartRequired 2>/dev/null || true
  defaults delete com.apple.SoftwareUpdate AutomaticCheckEnabled 2>/dev/null || true
  defaults delete com.apple.SoftwareUpdate AutomaticDownload 2>/dev/null || true
  echo "  App Store preferences restored to defaults"
else
  # Disable App Store auto-update
  ensure_default com.apple.commerce AutoUpdate 0 -bool false || exit 1
  ensure_default com.apple.commerce AutoUpdateRestartRequired 0 -bool false || exit 1
  # Disable automatic update checks and downloads
  ensure_default com.apple.SoftwareUpdate AutomaticCheckEnabled 0 -bool false || exit 1
  ensure_default com.apple.SoftwareUpdate AutomaticDownload 0 -bool false || exit 1
  echo "  App Store auto-check, auto-download, auto-update disabled"
fi

section "CrashReporter Preferences"
if $DRY_RUN || $AUDIT; then
  echo "  would suppress crash dialogs"
elif $REVERT; then
  defaults delete com.apple.CrashReporter DialogType 2>/dev/null || true
  echo "  CrashReporter preferences restored to defaults"
else
  # Suppress crash dialog pop-ups; crashes still logged to ~/Library/Logs/DiagnosticReports
  ensure_default com.apple.CrashReporter DialogType none -string none || exit 1
  echo "  Crash dialogs suppressed"
fi

section "App Quit & Screensaver Preferences"
if $DRY_RUN || $AUDIT; then
  echo "  would disable window state save on quit"
  echo "  would disable screensaver (direct to display sleep)"
  echo "  would default new document save location to local (not iCloud)"
elif $REVERT; then
  defaults delete NSGlobalDomain NSQuitAlwaysKeepsWindows 2>/dev/null || true
  defaults delete com.apple.screensaver idleTime 2>/dev/null || true
  defaults delete NSGlobalDomain NSDocumentSaveNewDocumentsToCloud 2>/dev/null || true
  echo "  App quit and screensaver preferences restored to defaults"
else
  # Don't write window/document state to disk on every app quit
  ensure_default NSGlobalDomain NSQuitAlwaysKeepsWindows 0 -bool false || exit 1
  # Disable screensaver — go straight to display sleep, no GPU spinning
  ensure_default com.apple.screensaver idleTime 0 -int 0 || exit 1
  # New documents default to local disk, not iCloud (iCloud Drive sync unaffected)
  ensure_default NSGlobalDomain NSDocumentSaveNewDocumentsToCloud 0 -bool false || exit 1
  echo "  Window state on quit disabled, screensaver disabled, new docs default to local"
fi

# ============================================================================
# PERFORMANCE DEFAULTS — reduce animations and visual overhead
# ============================================================================

section "Performance Defaults"
if $DRY_RUN || $AUDIT; then
  echo "  would disable window open/close animations"
  echo "  would set window resize time to 0.001s"
  echo "  would disable Dock launch bounce animation"
  echo "  would set Dock autohide delay to 0s, animation to 0.1s"
  echo "  would set Mission Control animation to 0.1s"
  echo "  would disable scroll animations"
  echo "  would enable reduce transparency"
  echo "  would enable reduce motion"
elif $REVERT; then
  defaults delete NSGlobalDomain NSAutomaticWindowAnimationsEnabled 2>/dev/null || true
  defaults delete NSGlobalDomain NSWindowResizeTime 2>/dev/null || true
  defaults delete com.apple.dock launchanim 2>/dev/null || true
  defaults delete com.apple.dock autohide-delay 2>/dev/null || true
  defaults delete com.apple.dock autohide-time-modifier 2>/dev/null || true
  defaults delete com.apple.dock expose-animation-duration 2>/dev/null || true
  defaults delete NSGlobalDomain NSScrollAnimationEnabled 2>/dev/null || true
  defaults delete com.apple.universalaccess reduceTransparency 2>/dev/null || true
  defaults delete com.apple.universalaccess reduceMotion 2>/dev/null || true
  killall Dock 2>/dev/null || true
  echo "  Performance defaults restored (Dock restarted)"
else
  PERFORMANCE_CHANGED=false
  # Disable window open/close animations
  ensure_default NSGlobalDomain NSAutomaticWindowAnimationsEnabled 0 -bool false || exit 1
  if $DEFAULT_CHANGED; then PERFORMANCE_CHANGED=true; fi
  # Near-instant window resize
  ensure_default NSGlobalDomain NSWindowResizeTime 0.001 -float 0.001 || exit 1
  if $DEFAULT_CHANGED; then PERFORMANCE_CHANGED=true; fi
  # Disable Dock launch bounce
  ensure_default com.apple.dock launchanim 0 -bool false || exit 1
  if $DEFAULT_CHANGED; then PERFORMANCE_CHANGED=true; fi
  # Instant Dock autohide (no delay, fast animation)
  ensure_default com.apple.dock autohide-delay 0 -float 0 || exit 1
  if $DEFAULT_CHANGED; then PERFORMANCE_CHANGED=true; fi
  ensure_default com.apple.dock autohide-time-modifier 0.1 -float 0.1 || exit 1
  if $DEFAULT_CHANGED; then PERFORMANCE_CHANGED=true; fi
  # Fast Mission Control animation
  ensure_default com.apple.dock expose-animation-duration 0.1 -float 0.1 || exit 1
  if $DEFAULT_CHANGED; then PERFORMANCE_CHANGED=true; fi
  # Disable scroll view animations
  ensure_default NSGlobalDomain NSScrollAnimationEnabled 0 -bool false || exit 1
  if $DEFAULT_CHANGED; then PERFORMANCE_CHANGED=true; fi
  # Reduce transparency (less compositing work for WindowServer)
  ensure_default com.apple.universalaccess reduceTransparency 1 -bool true || exit 1
  if $DEFAULT_CHANGED; then PERFORMANCE_CHANGED=true; fi
  # Reduce motion (system-wide animation reduction)
  ensure_default com.apple.universalaccess reduceMotion 1 -bool true || exit 1
  if $DEFAULT_CHANGED; then PERFORMANCE_CHANGED=true; fi
  # Restart Dock to pick up changes
  if $PERFORMANCE_CHANGED; then
    killall Dock 2>/dev/null || true
    echo "  Animations disabled, transparency reduced (Dock restarted)"
  else
    echo "  Performance defaults already set"
  fi
fi

# ============================================================================
# POWER MANAGEMENT — pmset (battery profile)
# ============================================================================

section "Power Management (pmset — battery)"
if $DRY_RUN || $AUDIT; then
  echo "  would disable Power Nap on battery"
  echo "  would disable TCP keepalive during sleep"
  echo "  would disable proximity wake (iPhone/Watch)"
  echo "  would disable Wake on LAN"
  echo "  would disable TTY keepawake"
  echo "  would set standby delay to 600s (default: up to 86400s)"
  echo "  would set hibernatemode 0 on battery (no sleepimage writes)"
  echo "  would set hibernatemode 3 on AC (safe sleep preserved)"
  echo "  would delete existing sleepimage to reclaim disk space"
  echo "  would set display sleep to 2 min on battery"
  echo "  would set system sleep to 10 min on battery"
  echo "  would enable auto power-off after 30 min standby"
elif $REVERT; then
  sudo pmset -b powernap 1
  sudo pmset -b tcpkeepalive 1
  sudo pmset -b proximitywake 1
  sudo pmset -b womp 1
  sudo pmset -b ttyskeepawake 1
  sudo pmset -b standbydelayhigh 86400
  sudo pmset -b standbydelaylow 10800
  sudo pmset -b highstandbythreshold 50
  sudo pmset -b hibernatemode 3
  sudo pmset -c hibernatemode 3
  sudo pmset -b displaysleep 5
  sudo pmset -b sleep 10
  sudo pmset -b autopoweroff 1
  sudo pmset -b autopoweroffdelay 28800
  echo "  pmset battery defaults restored"
else
  # Power Nap: no background iCloud/mail fetch during sleep (syncs fine when awake)
  sudo pmset -b powernap 0
  # TCP keepalive: eliminates dark wakes every ~2h to maintain TCP connections
  sudo pmset -b tcpkeepalive 0
  # Proximity wake: prevents iPhone/Watch from waking the Mac
  sudo pmset -b proximitywake 0
  # Wake on LAN
  sudo pmset -b womp 0
  # TTY keepawake: open SSH/terminal connections won't prevent sleep
  sudo pmset -b ttyskeepawake 0
  # Aggressive standby: enter deep hibernate after 10 min sleep (default: up to 24h)
  sudo pmset -b standbydelayhigh 600
  sudo pmset -b standbydelaylow 600
  sudo pmset -b highstandbythreshold 50
  # hibernatemode 0 on battery: skip writing RAM to disk on sleep (saves RAM-sized SSD
  # writes per sleep cycle). Risk: unsaved work lost if battery fully exhausts during sleep.
  # hibernatemode 3 on AC: keep safe sleep when plugged in (writes are free there).
  sudo pmset -b hibernatemode 0
  sudo pmset -c hibernatemode 3
  # Remove existing sleepimage — no longer needed on battery, reclaims RAM-sized disk space
  sudo rm -f /private/var/vm/sleepimage
  # Sleep timers: display off at 2 min, system sleep at 10 min on battery
  sudo pmset -b displaysleep 2
  sudo pmset -b sleep 10
  # Auto power-off: fully cut power after 30 min of standby (saves more than standby alone)
  sudo pmset -b autopoweroff 1
  sudo pmset -b autopoweroffdelay 1800
  echo "  Power Nap, TCP keepalive, proximity wake, WoL, TTY keepawake disabled"
  echo "  Standby: 600s / auto power-off: 1800s"
  echo "  hibernatemode 0 (battery) / 3 (AC), sleepimage removed"
  echo "  Display sleep: 2 min, system sleep: 10 min"
fi

# ============================================================================
# NETWORK — IPv6
# ============================================================================

section "IPv6 (all interfaces except VPN/Tailscale)"
# Enumerates all network services, skips VPN/Tailscale, applies to the rest
_ipv6_each() {
  cmd=$1
  networksetup -listallnetworkservices 2>/dev/null | tail -n +2 | while IFS= read -r svc; do
    svc="${svc#\* }"  # strip leading asterisk from disabled services
    case "$svc" in
      *[Tt]ailscale*|*VPN*|*[Vv]pn*|*utun*) echo "  skip $svc" ;;
      *) sudo networksetup "$cmd" "$svc" 2>/dev/null && echo "  $svc" ;;
    esac
  done
}
if $DRY_RUN || $AUDIT; then
  echo "  would disable IPv6 on all non-VPN interfaces:"
  networksetup -listallnetworkservices 2>/dev/null | tail -n +2 | while IFS= read -r svc; do
    svc="${svc#\* }"
    case "$svc" in
      *[Tt]ailscale*|*VPN*|*[Vv]pn*|*utun*) echo "    skip: $svc" ;;
      *) echo "    off:  $svc" ;;
    esac
  done
elif $REVERT; then
  _ipv6_each -setv6automatic
  echo "  IPv6 restored to automatic on all interfaces"
else
  _ipv6_each -setv6off
  echo "  IPv6 disabled on all non-VPN interfaces"
fi

# ============================================================================
# NETWORK — mDNS & Captive Portal
# ============================================================================

section "mDNS Multicast Advertisements"
if $DRY_RUN || $AUDIT; then
  echo "  would stop Mac advertising its own services via mDNS"
elif $REVERT; then
  sudo defaults delete /Library/Preferences/com.apple.mDNSResponder.plist NoMulticastAdvertisements 2>/dev/null || true
  sudo killall mDNSResponder 2>/dev/null || true
  echo "  mDNS multicast advertisements restored"
else
  # Stops Mac broadcasting its own services (AFP, SMB, AirPlay receiver, etc.)
  # Mac can still discover other devices. Note: breaks this Mac as an AirPlay receiver target.
  ensure_system_default /Library/Preferences/com.apple.mDNSResponder.plist NoMulticastAdvertisements 1 -bool YES || exit 1
  if $SYSTEM_DEFAULT_CHANGED; then
    sudo killall mDNSResponder 2>/dev/null || true
    echo "  mDNS multicast advertisements disabled (mDNSResponder restarted)"
  else
    echo "  mDNS multicast advertisements already disabled"
  fi
fi

section "Captive Network Detection"
if $DRY_RUN || $AUDIT; then
  echo "  would disable captive portal HTTP probing"
elif $REVERT; then
  sudo defaults delete /Library/Preferences/SystemConfiguration/com.apple.captive.control Active 2>/dev/null || true
  echo "  Captive network detection restored"
else
  # Stops background HTTP probes to detect hotel/airport captive portals
  # Side effect: no auto-popup on captive networks — open browser manually to trigger login
  ensure_system_default /Library/Preferences/SystemConfiguration/com.apple.captive.control Active 0 -bool false || exit 1
  if $SYSTEM_DEFAULT_CHANGED; then
    echo "  Captive network detection disabled"
  else
    echo "  Captive network detection already disabled"
  fi
fi

# ============================================================================
# LOGGING — Unified log system
# ============================================================================

section "Unified Logging"
if $DRY_RUN || $AUDIT; then
  echo "  would disable unified log system (no Console.app data, no log show)"
elif $REVERT; then
  sudo log config --mode "level:default"
  echo "  Unified logging restored to default"
else
  # Shuts down the log subsystem entirely — eliminates constant SSD writes to /var/db/diagnostics
  # Trade-off: Console.app goes dark, 'log show' returns nothing, crash diagnosis is harder
  sudo log config --mode "level:off"
  echo "  Unified logging disabled"
fi

# ============================================================================
# VERIFY — Ensure preserved services are enabled and loaded
# ============================================================================

section "Verify: QuickLook"
ensure_user com.apple.quicklook "QuickLook"
ensure_user com.apple.quicklook.ui.helper "QuickLook UI helper"
ensure_user com.apple.quicklook.ThumbnailsAgent "QuickLook thumbnails"

section "Verify: AirDrop & AirPlay"
ensure_user com.apple.sharingd "AirDrop/sharing daemon"
ensure_user com.apple.AirPlayUIAgent "AirPlay UI"
ensure_user com.apple.rapportd "Device discovery (rapportd)"
ensure_user com.apple.RapportUIAgent "Device discovery UI"
ensure_user com.apple.bluetoothuserd "Bluetooth user agent"
ensure_system com.apple.AirPlayXPCHelper "AirPlay XPC helper"
ensure_system com.apple.bluetoothd "Bluetooth daemon"
ensure_system com.apple.rapportd "Device discovery daemon"

section "Verify: iCloud Drive"
ensure_user com.apple.bird "iCloud Drive sync (bird)"
ensure_user com.apple.cloudd "iCloud core daemon"
ensure_user com.apple.nsurlsessiond "Network transfers"
ensure_user com.apple.FileProvider "File Provider framework"
ensure_user com.apple.iCloudNotificationAgent "iCloud push notifications"
ensure_user com.apple.protectedcloudstorage.protectedcloudkeysyncing "Cloud encryption keys"
ensure_system com.apple.cloudd "iCloud system daemon"
ensure_system com.apple.nsurlsessiond "Network transfers (system)"

section "Verify: Apple Passwords"
# NOTE: no com.apple.Passwords.MenuBarExtra here — it is a LoginItem, not a
# launchd job, so a launchctl preserve-check could never pass. Its companion
# PasswordBreachAgent below IS a real agent and is verified instead.
ensure_user com.apple.AuthenticationServicesCore.AuthenticationServicesAgent "Authentication services"
ensure_user com.apple.LocalAuthentication.UIAgent "Local auth UI (Touch ID prompts)"
ensure_user com.apple.swcd "Shared Web Credentials"
ensure_user com.apple.AutoFillPanel "AutoFill panel"
ensure_user com.apple.accountsd "Account management"
ensure_user com.apple.akd "Auth Kit (Apple ID)"
ensure_user com.apple.security.cloudkeychainproxy3 "iCloud Keychain sync"
ensure_user com.apple.Safari.PasswordBreachAgent "Password breach monitoring"

section "Verify: Notes"
ensure_user com.apple.synapse.contentlinkingd "Notes content linking"

section "Verify: Camera & Video Calls"
ensure_user com.apple.videoconference.camera "Video conferencing camera"
ensure_user com.apple.cmio.LaunchCMIOUserExtensionsAgent "Camera extensions"
ensure_user com.apple.ptpcamerad "Camera daemon"

section "Verify: AirPods & Bluetooth Audio"
ensure_user com.apple.BTServer.cloudpairing "BT cloud pairing (cross-device AirPods)"
ensure_system com.apple.bluetoothd "Bluetooth daemon"

section "Verify: Touch ID"
ensure_system com.apple.biometrickitd "Touch ID"

section "Verify: Core UI"
ensure_user com.apple.Dock.agent "Dock"
ensure_user com.apple.Finder "Finder"
ensure_user com.apple.WindowManager.agent "Window Manager"
ensure_user com.apple.SystemUIServer.agent "System UI Server"
ensure_user com.apple.controlcenter "Control Center"
ensure_system com.apple.WindowServer "WindowServer"

section "Verify: Input & Clipboard"
ensure_user com.apple.pboard "Clipboard (pasteboard)"
ensure_user com.apple.imklaunchagent "Input method framework"
ensure_user com.apple.keyboardservicesd "Keyboard services"
ensure_user com.apple.TextInputMenuAgent "Text input menu"

section "Verify: Notifications"
ensure_user com.apple.notificationcenterui.agent "Notification Center"
ensure_user com.apple.usernoted "User notifications"
ensure_user com.apple.usernotificationsd "Notification delivery"

section "Verify: Audio"
ensure_system com.apple.audio.coreaudiod "Core Audio"

section "Verify: Networking"
ensure_system com.apple.mDNSResponder.reloaded "DNS/Bonjour"
ensure_system com.apple.configd "Network configuration"
ensure_system com.apple.airportd "WiFi"

section "Verify: Security & Auth"
ensure_system com.apple.securityd "Security daemon"
ensure_system com.apple.opendirectoryd "Directory services"
ensure_system com.apple.sandboxd "App sandbox"

section "Verify: Disk & Filesystem"
ensure_system com.apple.diskarbitrationd "Disk Arbitration"
ensure_system com.apple.apfsd "APFS filesystem"

section "Verify: Calendar"
ensure_user com.apple.calaccessd "Calendar access"

section "Verify: Photos"
ensure_user com.apple.photolibraryd "Photos library"

section "Verify: MDM & Endpoint Security"
ensure_optional_user io.kandji.Kandji "Kandji MDM"
ensure_optional_user com.crowdstrike.falcon.UserAgent "CrowdStrike Falcon"

section "Verify: Spell Check & Language"
ensure_user com.apple.applespell "Spell checking"
ensure_user com.apple.naturallanguaged "Natural language processing"

# ============================================================================
# SUMMARY
# ============================================================================

echo ""
echo "============================================"
if $AUDIT; then
  audit_report
  echo "Audit complete. No changes made."
  echo "Next: ./${0##*/} --dry-run, then apply."
elif $DRY_RUN || $AUDIT; then
  echo "Dry run complete. No changes made."
  echo "Any STALE lines above would be skipped on ${OS_NAME} ${MACOS_VERSION}."
  echo "Run without --dry-run to apply."
elif $REVERT; then
  echo "Re-enabled ${N_APPLIED} service(s). Reboot required."
else
  echo "Changed: ${N_APPLIED} disabled, ${N_UNCHANGED} already disabled, ${N_SKIPPED} skipped (stale/rejected)."
  if [ "$VERIFY_FAIL" -gt 0 ]; then
    echo "WARNING: ${VERIFY_FAIL} preserved service(s) not loaded."
    echo "Review FAIL lines above. May need reboot or"
    echo "manual investigation."
  else
    echo "All preserved services verified OK."
  fi
  echo ""
  if [ "$OS_MAJOR" -ge 27 ] 2>/dev/null; then
    echo "27 reminders: check Settings > General > Login Items & Extensions >"
    echo "Background App Activity (new per-app kill switch), and re-run --audit"
    echo "after every OS update — disabled.plist may reset."
  else
    echo "After upgrading macOS: re-run --audit, then --dry-run, then apply."
    echo "(Major upgrades may reset disabled.plist and rename labels.)"
  fi
  echo ""
  echo "Reboot to finalize."
  echo ""
  echo "Inspect disabled services:"
  echo "  launchctl print-disabled gui/${UID_NUM}"
  echo "  sudo launchctl print-disabled system"
  echo ""
  echo "Note: Cmd+Space (Spotlight) is now dead."
  echo "Set up Raycast/Alfred if you haven't already."
fi
echo "============================================"

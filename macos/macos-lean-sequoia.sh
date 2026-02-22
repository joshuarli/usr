#!/bin/bash
# ============================================================================
# macos-lean-sequoia.sh — Make macOS 15.7 (Sequoia) lean
# ============================================================================
#
# Disables ~160 unnecessary services via launchctl disable (persists across
# reboots) and launchctl bootout (immediate effect). Organized by category.
#
# DISABLED:
#   - Siri, Dictation, "Hey Siri", all assistant/speech services
#   - Apple Intelligence, on-device ML, generative AI, Private Cloud Compute
#   - Spotlight indexing (mdutil + all workers/scanners/knowledge agents)
#   - Telemetry: analytics, diagnostics, biome, ad tracking, A/B trials
#   - Apple apps: Music, News, Weather, Sports, Shazam, Voice Memos,
#     TV/video subscriptions, Game Center, Wallet/Pay, Reminders, Maps,
#     Home/HomeKit, Tips, Books, Stickers
#   - iMessage, FaceTime, phone call relay, CommCenter
#   - Continuity: Handoff, Sidecar, Universal Clipboard (NOT AirDrop)
#   - Family Sharing, parental controls, Screen Time
#   - Screen sharing (giving and receiving)
#   - Photos: ML analysis, Photo Stream, iCloud Photos sync
#   - Location: routine tracking, Find My, geo services
#   - iCloud: Keychain sync, mail agent, protected cloud storage
#   - Time Machine, translation, MDM enrollment follow-ups
#
# PRESERVED:
#   - QuickLook (spacebar preview, thumbnails)
#   - Touch ID (biometrickitd)
#   - AirDrop (sharingd kept running)
#   - Core networking: WiFi, Bluetooth, DNS, mDNS, Tailscale
#   - Audio: coreaudiod, media keys (rcd), system sounds
#   - Display: WindowServer, Dock, Finder, WindowManager
#   - Security: Gatekeeper, XProtect, keychain (local), sandboxd, SIP
#   - Notifications (notificationcenterui, usernoted)
#   - Clipboard (pboard)
#   - Text input (IMK, keyboard services, spell check)
#   - Disk management, APFS, file systems
#   - Login/auth: loginwindow, SecurityAgent, opendirectoryd
#   - App Store (downloads, updates)
#   - Kandji MDM agent, CrowdStrike Falcon
#
# Usage:
#   ./macos-lean-sequoia.sh              # Apply changes (requires sudo)
#   ./macos-lean-sequoia.sh --dry-run    # Preview changes only
#   ./macos-lean-sequoia.sh --revert     # Re-enable everything
#
# SIP note: User agents persist with SIP on. Some system daemons may
#           re-enable themselves unless SIP is disabled.
#
# Nuclear revert:
#   sudo rm /private/var/db/com.apple.xpc.launchd/disabled.501.plist
#   sudo rm /private/var/db/com.apple.xpc.launchd/disabled.plist
#   sudo mdutil -a -i on && reboot
#
# Verify: launchctl print-disabled gui/$(id -u)
#         sudo launchctl print-disabled system
# ============================================================================

set -uo pipefail

DRY_RUN=false
REVERT=false

while [[ $# -gt 0 ]]; do
  case $1 in
    --dry-run) DRY_RUN=true; shift ;;
    --revert)  REVERT=true; shift ;;
    -h|--help) sed -n '2,29p' "$0"; exit 0 ;;
    *) echo "Usage: $0 [--dry-run] [--revert]"; exit 1 ;;
  esac
done

UID_NUM=$(id -u)

if $REVERT; then
  echo "macOS Lean — REVERT mode (re-enabling services)"
elif $DRY_RUN; then
  echo "macOS Lean — DRY RUN (no changes)"
else
  echo "macOS Lean — Sequoia 15.7"
fi
echo "User UID: ${UID_NUM}"
echo ""

# --- Sudo keepalive (unless dry-run) ---
if ! $DRY_RUN; then
  sudo -v || { echo "Error: sudo required"; exit 1; }
  while true; do sudo -n true; sleep 50; kill -0 "$$" || exit; done 2>/dev/null &
  SUDO_PID=$!
  trap 'kill $SUDO_PID 2>/dev/null' EXIT
fi

# --- Helpers ---

disable_user() {
  local label=$1
  if $DRY_RUN; then
    echo "  ${label}"
  elif $REVERT; then
    launchctl enable "gui/${UID_NUM}/${label}" 2>/dev/null
    echo "  + ${label}"
  else
    launchctl disable "gui/${UID_NUM}/${label}" 2>/dev/null
    launchctl bootout "gui/${UID_NUM}/${label}" 2>/dev/null || true
    echo "  - ${label}"
  fi
}

disable_system() {
  local label=$1
  if $DRY_RUN; then
    echo "  ${label}"
  elif $REVERT; then
    sudo launchctl enable "system/${label}" 2>/dev/null
    echo "  + ${label}"
  else
    sudo launchctl disable "system/${label}" 2>/dev/null
    sudo launchctl bootout "system/${label}" 2>/dev/null || true
    echo "  - ${label}"
  fi
}

section() { echo ""; echo "=== $1 ==="; }

# ============================================================================
# USER AGENTS
# ============================================================================

section "Siri & Assistant"
for s in \
  com.apple.assistant_service \
  com.apple.assistant_cdmd \
  com.apple.assistantd \
  com.apple.Siri.agent \
  com.apple.siriknowledged \
  com.apple.siriactionsd \
  com.apple.sirittsd \
  com.apple.SiriTTSTrainingAgent \
  com.apple.siri-distributed-evaluation \
  com.apple.siriinferenced \
  com.apple.corespeechd \
  com.apple.DictationIM \
  com.apple.speech.speechdatainstallerd \
  com.apple.parsec-fbf \
  com.apple.parsecd \
  com.apple.suggestd \
  com.apple.proactived \
  com.apple.proactiveeventtrackerd \
; do disable_user "$s"; done

section "Apple Intelligence & ML"
for s in \
  com.apple.intelligenceplatformd \
  com.apple.intelligenceflowd \
  com.apple.intelligencecontextd \
  com.apple.intelligentroutingd \
  com.apple.knowledgeconstructiond \
  com.apple.generativeexperiencesd \
  com.apple.privatecloudcomputed \
  com.apple.textunderstandingd \
  com.apple.synapse.contentlinkingd \
  com.apple.milod \
  com.apple.mlhostd \
  com.apple.mlruntimed \
  com.apple.ModelCatalogAgent \
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
  com.apple.amsengagementd \
  com.apple.analyticsagent \
  com.apple.geoanalyticsd \
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
  com.apple.replayd \
  com.apple.remindd \
  com.apple.passd \
  com.apple.Maps.mapspushd \
  com.apple.maps.destinationd \
  com.apple.Maps.mapssyncd \
  com.apple.homed \
  com.apple.homeenergyd \
  com.apple.followupd \
  com.apple.sociallayerd \
  com.apple.StatusKitAgent \
  com.apple.macos.studentd \
  com.apple.stickersd \
  com.apple.navd \
; do disable_user "$s"; done

section "iMessage, FaceTime & Phone"
for s in \
  com.apple.imagent \
  com.apple.imautomatichistorydeletionagent \
  com.apple.imcore.imtransferagent \
  com.apple.imtransferservices.IMTransferAgent \
  com.apple.CallHistoryPluginHelper \
  com.apple.CallHistorySyncHelper \
  com.apple.telephonyutilities.callservicesd \
  com.apple.avconferenced \
  com.apple.CommCenter \
  com.apple.CommCenter-osx \
; do disable_user "$s"; done

section "Continuity (keeping sharingd for AirDrop)"
for s in \
  com.apple.ensemble \
  com.apple.rapportd-user \
  com.apple.RapportUIAgent \
  com.apple.sidecar-hid-relay \
  com.apple.sidecar-relay \
  com.apple.sidecar-display-agent \
  com.apple.coreservices.useractivityd \
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
  com.apple.spotlight.ImportAgent \
  com.apple.metadata.mdwrite \
  com.apple.metadata.mdflagwriter \
  com.apple.mdworker.shared \
  com.apple.mdworker.single.arm64 \
  com.apple.mdworker.single.x86_64 \
  com.apple.mdworker.sizing \
  com.apple.mdworker.mail \
; do disable_user "$s"; done

section "Other"
for s in \
  com.apple.accessibility.MotionTrackingAgent \
  com.apple.dataaccess.dataaccessd \
  com.apple.progressd \
  com.apple.protectedcloudstorage.protectedcloudkeysyncing \
  com.apple.security.cloudkeychainproxy3 \
  com.apple.TMHelperAgent \
  com.apple.translationd \
  com.apple.icloudmailagent \
; do disable_user "$s"; done

# ============================================================================
# SYSTEM DAEMONS (may need SIP disabled for full persistence)
# ============================================================================

section "System — Siri"
for s in \
  com.apple.corespeechd.system \
; do disable_system "$s"; done

section "System — Analytics"
for s in \
  com.apple.analyticsd \
  com.apple.wifianalyticsd \
  com.apple.triald.system \
; do disable_system "$s"; done

section "System — Unused Services"
for s in \
  com.apple.backupd \
  com.apple.backupd-helper \
  com.apple.biomed \
  com.apple.coreduetd \
  com.apple.familycontrols \
  com.apple.ftp-proxy \
  com.apple.GameController.gamecontrollerd \
  com.apple.gamepolicyd \
  com.apple.netbiosd \
  com.apple.rapportd \
  com.apple.screensharing \
  com.apple.dhcp6d \
; do disable_system "$s"; done

section "System — Find My"
for s in \
  com.apple.findmymac \
  com.apple.findmymacmessenger \
  com.apple.icloud.findmydeviced \
  com.apple.icloud.searchpartyd \
; do disable_system "$s"; done

section "System — Spotlight Indexing"
for s in \
  com.apple.metadata.mds.index \
  com.apple.metadata.mds.scan \
  com.apple.metadata.mds.spindump \
; do disable_system "$s"; done

# ============================================================================
# SPOTLIGHT — mdutil
# ============================================================================

section "Spotlight Indexing (mdutil)"
if $DRY_RUN; then
  echo "  would run: sudo mdutil -a -i off"
  echo "  would run: sudo mdutil -aE"
elif $REVERT; then
  sudo mdutil -a -i on 2>/dev/null
  echo "  Spotlight indexing re-enabled"
else
  sudo mdutil -a -i off 2>/dev/null
  sudo mdutil -aE 2>/dev/null
  echo "  Indexing disabled, indexes deleted"
fi

# ============================================================================
# DEFAULTS — preference-level disabling
# ============================================================================

section "System Preferences"
if $DRY_RUN; then
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
  defaults write com.apple.assistant.support 'Assistant Enabled' -bool false
  defaults write com.apple.Siri StatusMenuVisible -bool false
  defaults write com.apple.Siri UserHasDeclinedEnable -bool true
  defaults write com.apple.Siri VoiceTriggerUserEnabled -bool false
  defaults write com.apple.lookup.shared LookupSuggestionsDisabled -bool true
  echo "  Siri fully disabled (assistant, menu bar, voice trigger)"
  echo "  Spotlight suggestions disabled"
fi

# ============================================================================
# SUMMARY
# ============================================================================

echo ""
echo "============================================"
if $DRY_RUN; then
  echo "Dry run complete. No changes made."
  echo "Run without --dry-run to apply."
elif $REVERT; then
  echo "All services re-enabled. Reboot required."
else
  echo "Done. Reboot to finalize."
  echo ""
  echo "Verify:"
  echo "  launchctl print-disabled gui/${UID_NUM}"
  echo "  sudo launchctl print-disabled system"
  echo ""
  echo "Note: Cmd+Space (Spotlight) is now dead."
  echo "Set up Raycast/Alfred if you haven't already."
fi
echo "============================================"

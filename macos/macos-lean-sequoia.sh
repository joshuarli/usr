#!/bin/dash
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
#   - Telemetry: analytics, diagnostics, biome, ad tracking, A/B trials,
#     sysmond, tailspind
#   - Apple apps: Music, News, Weather, Sports, Shazam, Voice Memos,
#     TV/video subscriptions, Game Center, Wallet/Pay, Reminders, Maps,
#     Home/HomeKit, Tips, Stickers, Podcasts, Health
#   - iMessage, FaceTime, phone call relay, CommCenter
#   - Continuity: Handoff, Sidecar, Universal Clipboard (NOT AirDrop/AirPlay)
#   - Family Sharing, parental controls, Screen Time
#   - Screen sharing (giving and receiving)
#   - Photos: ML analysis, Photo Stream, iCloud Photos sync
#   - Location: routine tracking, Find My, geo services
#   - iCloud: mail agent, Photos sync (Drive + Keychain preserved)
#   - Mail: maild, mail extensions, iCloud mail agent
#   - Safari: history, bookmarks sync, notifications, web inspector,
#     cloud history push
#   - App Store: storefront, commerce, StoreKit, update notifications
#   - Focus/DND: donotdisturbd
#   - Accessibility: motion tracking, hearing, voice banking
#   - Misc: Time Machine + APFS local snapshots, translation, avatars/Memoji,
#     content caching, accessory firmware updates, app placeholders,
#     settings sync, Continuity Camera, Thread/smart home, DND/Focus,
#     recent items, NFC
#   - Crash reporting: ReportCrash, ReportPanic, crash dialogs suppressed
#   - Wireless/network diagnostics: awdd, symptomsd, spindump
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
#   - AirPort base station support
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

set -u

DRY_RUN=false
REVERT=false

while [ $# -gt 0 ]; do
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
  label=$1
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
  label=$1
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

VERIFY_FAIL=0

ensure_user() {
  label=$1
  desc=$2
  if $DRY_RUN; then
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

ensure_system() {
  label=$1
  desc=$2
  if $DRY_RUN; then
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
  com.apple.ContextStoreAgent \
  com.apple.duetexpertd \
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
  com.apple.metrickitd \
  com.apple.diagnosticextensionsd \
  com.apple.backgroundassets.user \
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
  com.apple.studentd \
  com.apple.stickersd \
  com.apple.navd \
  com.apple.amsondevicestoraged \
  com.apple.amsaccountsd \
  com.apple.avatarsd \
  com.apple.mobiletimerd \
  com.apple.appplaceholdersyncd \
  com.apple.podcastsd \
  com.apple.healthd \
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

section "Continuity (keeping sharingd/rapportd for AirDrop & AirPlay)"
for s in \
  com.apple.ensemble \
  com.apple.sidecar-hid-relay \
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
  com.apple.spotlight.ImportAgent \
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
  com.apple.webinspectord \
  com.apple.SafariCloudHistoryPushAgent \
; do disable_user "$s"; done

section "App Store"
for s in \
  com.apple.appstoreagent \
  com.apple.appstorecomponentsd \
  com.apple.commerce \
  com.apple.storekitagent \
  com.apple.storeassetd \
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
  com.apple.ReportPanic \
; do disable_user "$s"; done

# ============================================================================
# SYSTEM DAEMONS (may need SIP disabled for full persistence)
# ============================================================================

section "System — Siri"
disable_system com.apple.corespeechd.system

section "System — Analytics"
for s in \
  com.apple.analyticsd \
  com.apple.wifianalyticsd \
  com.apple.triald.system \
  com.apple.sysmond \
  com.apple.tailspind \
; do disable_system "$s"; done

section "System — App Store"
disable_system com.apple.appstored

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
  com.apple.screensharing \
  com.apple.dhcp6d \
; do disable_system "$s"; done

section "System — Wireless & Network Diagnostics"
for s in \
  com.apple.awdd \
  com.apple.symptomsd \
  com.apple.spindump \
  com.apple.nfcd \
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

section "Time Machine & Local Snapshots"
if $DRY_RUN; then
  echo "  would disable Time Machine"
  echo "  would disable APFS local snapshot creation"
elif $REVERT; then
  sudo tmutil enable 2>/dev/null || true
  sudo tmutil enablelocal 2>/dev/null || true
  echo "  Time Machine and local snapshots re-enabled"
else
  # Belt-and-suspenders alongside backupd/backupd-helper being disabled
  sudo tmutil disable 2>/dev/null || true
  # Stop APFS from creating local Time Machine snapshots (significant write traffic)
  sudo tmutil disablelocal 2>/dev/null || true
  echo "  Time Machine disabled, APFS local snapshots disabled"
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

section "App Store Preferences"
if $DRY_RUN; then
  echo "  would disable App Store auto-check, auto-download, auto-update"
elif $REVERT; then
  defaults delete com.apple.commerce AutoUpdate 2>/dev/null || true
  defaults delete com.apple.commerce AutoUpdateRestartRequired 2>/dev/null || true
  defaults delete com.apple.SoftwareUpdate AutomaticCheckEnabled 2>/dev/null || true
  defaults delete com.apple.SoftwareUpdate AutomaticDownload 2>/dev/null || true
  echo "  App Store preferences restored to defaults"
else
  # Disable App Store auto-update
  defaults write com.apple.commerce AutoUpdate -bool false
  defaults write com.apple.commerce AutoUpdateRestartRequired -bool false
  # Disable automatic update checks and downloads
  defaults write com.apple.SoftwareUpdate AutomaticCheckEnabled -bool false
  defaults write com.apple.SoftwareUpdate AutomaticDownload -bool false
  echo "  App Store auto-check, auto-download, auto-update disabled"
fi

section "CrashReporter Preferences"
if $DRY_RUN; then
  echo "  would suppress crash dialogs"
elif $REVERT; then
  defaults delete com.apple.CrashReporter DialogType 2>/dev/null || true
  echo "  CrashReporter preferences restored to defaults"
else
  # Suppress crash dialog pop-ups; crashes still logged to ~/Library/Logs/DiagnosticReports
  defaults write com.apple.CrashReporter DialogType none
  echo "  Crash dialogs suppressed"
fi

section "App Quit & Screensaver Preferences"
if $DRY_RUN; then
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
  defaults write NSGlobalDomain NSQuitAlwaysKeepsWindows -bool false
  # Disable screensaver — go straight to display sleep, no GPU spinning
  defaults write com.apple.screensaver idleTime -int 0
  # New documents default to local disk, not iCloud (iCloud Drive sync unaffected)
  defaults write NSGlobalDomain NSDocumentSaveNewDocumentsToCloud -bool false
  echo "  Window state on quit disabled, screensaver disabled, new docs default to local"
fi

# ============================================================================
# PERFORMANCE DEFAULTS — reduce animations and visual overhead
# ============================================================================

section "Performance Defaults"
if $DRY_RUN; then
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
  # Disable window open/close animations
  defaults write NSGlobalDomain NSAutomaticWindowAnimationsEnabled -bool false
  # Near-instant window resize
  defaults write NSGlobalDomain NSWindowResizeTime -float 0.001
  # Disable Dock launch bounce
  defaults write com.apple.dock launchanim -bool false
  # Instant Dock autohide (no delay, fast animation)
  defaults write com.apple.dock autohide-delay -float 0
  defaults write com.apple.dock autohide-time-modifier -float 0.1
  # Fast Mission Control animation
  defaults write com.apple.dock expose-animation-duration -float 0.1
  # Disable scroll view animations
  defaults write NSGlobalDomain NSScrollAnimationEnabled -bool false
  # Reduce transparency (less compositing work for WindowServer)
  defaults write com.apple.universalaccess reduceTransparency -bool true
  # Reduce motion (system-wide animation reduction)
  defaults write com.apple.universalaccess reduceMotion -bool true
  # Restart Dock to pick up changes
  killall Dock 2>/dev/null || true
  echo "  Animations disabled, transparency reduced (Dock restarted)"
fi

# ============================================================================
# POWER MANAGEMENT — pmset (battery profile)
# ============================================================================

section "Power Management (pmset — battery)"
if $DRY_RUN; then
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
if $DRY_RUN; then
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
if $DRY_RUN; then
  echo "  would stop Mac advertising its own services via mDNS"
elif $REVERT; then
  sudo defaults delete /Library/Preferences/com.apple.mDNSResponder.plist NoMulticastAdvertisements 2>/dev/null || true
  sudo killall mDNSResponder 2>/dev/null || true
  echo "  mDNS multicast advertisements restored"
else
  # Stops Mac broadcasting its own services (AFP, SMB, AirPlay receiver, etc.)
  # Mac can still discover other devices. Note: breaks this Mac as an AirPlay receiver target.
  sudo defaults write /Library/Preferences/com.apple.mDNSResponder.plist NoMulticastAdvertisements -bool YES
  sudo killall mDNSResponder 2>/dev/null || true
  echo "  mDNS multicast advertisements disabled (mDNSResponder restarted)"
fi

section "Captive Network Detection"
if $DRY_RUN; then
  echo "  would disable captive portal HTTP probing"
elif $REVERT; then
  sudo defaults delete /Library/Preferences/SystemConfiguration/com.apple.captive.control Active 2>/dev/null || true
  echo "  Captive network detection restored"
else
  # Stops background HTTP probes to detect hotel/airport captive portals
  # Side effect: no auto-popup on captive networks — open browser manually to trigger login
  sudo defaults write /Library/Preferences/SystemConfiguration/com.apple.captive.control Active -bool false
  echo "  Captive network detection disabled"
fi

# ============================================================================
# LOGGING — Unified log system
# ============================================================================

section "Unified Logging"
if $DRY_RUN; then
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
ensure_user com.apple.Passwords.MenuBarExtra "Passwords menu bar"
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
ensure_system com.apple.mDNSResponder "DNS/Bonjour"
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

section "Verify: AirPort"
ensure_user com.apple.AirPortBaseStationAgent "AirPort base station"

section "Verify: MDM & Endpoint Security"
ensure_user io.kandji.Kandji "Kandji MDM"
ensure_user com.crowdstrike.falcon.UserAgent "CrowdStrike Falcon"

section "Verify: Spell Check & Language"
ensure_user com.apple.applespell "Spell checking"
ensure_user com.apple.naturallanguaged "Natural language processing"

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
  if [ "$VERIFY_FAIL" -gt 0 ]; then
    echo "WARNING: ${VERIFY_FAIL} preserved service(s) not loaded."
    echo "Review FAIL lines above. May need reboot or"
    echo "manual investigation."
  else
    echo "All preserved services verified OK."
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

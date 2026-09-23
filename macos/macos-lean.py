#!/usr/bin/env python3
"""macos-lean.py — Make macOS lean (27 Golden Gate).

Stdlib only. Disables ~230 unnecessary services via ``launchctl disable``
(persists across reboots) plus process kill for immediate effect (bootout
is blocked by SIP; the disabled flag still prevents respawn), then
converges preferences, power, network, and logging settings. The full
managed lists live below in ``DISABLE_SECTIONS``, ``PRESERVE_SECTIONS``,
``USER_DEFAULTS``, ``PERFORMANCE_DEFAULTS``, and ``PMSET_*``.

Usage:
    ./macos-lean.py              # apply changes (requires sudo)
    ./macos-lean.py --dry-run    # preview; stale labels flagged, no changes
    ./macos-lean.py --audit      # validate labels vs live OS; no sudo, no changes
    ./macos-lean.py --revert     # re-enable everything managed

Always run --audit first after an OS upgrade, then --dry-run, then apply.
Apply snapshots pre-change state to ~/.local/state/macos-lean/.

Design: validate-then-act. Every label is checked against a live index of
labels installed on THIS Mac (``Label`` keys read with plistlib, cached
per OS build). Unknown labels print STALE and are skipped, never silently
no-op'd. Apply converges: already-disabled jobs and matching preferences
are left alone. --dry-run output contains every managed label, so the
label-extraction workflow below (rg over --dry-run) keeps working.

Disabled (categories): Siri/dictation, Apple Intelligence + on-device ML,
Spotlight indexing, telemetry/analytics/biome/trials, Apple apps (Music,
News, Weather, Sports, Shazam, Voice Memos, TV, Games, Wallet, Reminders,
Maps, Home, Tips, Stickers), iMessage/FaceTime/phone relay, Continuity
except AirDrop/AirPlay, Family/Screen Time, screen sharing, Photos ML +
iCloud Photos sync, location/Find My, iCloud mail agent, Mail, Safari
sync/notifications, App Store commerce, Focus/DND, misc accessibility,
Time Machine, translation, avatars, content caching, Thread, NFC, crash
dialogs, network/wireless diagnostics, animations/transparency, window
state on quit, Power Nap/TCP-keepalive/proximity-wake/WoL, IPv6 (non-VPN),
mDNS ads, captive probing, unified logging.

Preserved: QuickLook, Touch ID, AirDrop/AirPlay, core networking/audio/
display, Gatekeeper/XProtect/keychain, notifications, clipboard, text
input, disks, login/auth, iCloud Drive + Keychain/Passwords, Calendar,
local Photos library, Notes linking, camera/video calls, AirPods,
Kandji/CrowdStrike when installed.

Verify: ``launchctl print-disabled gui/$(id -u)``,
``sudo launchctl print-disabled system``.
Nuclear revert: delete
/private/var/db/com.apple.xpc.launchd/disabled{,.501}.plist, then
``sudo mdutil -a -i on`` and reboot. Major upgrades may reset
disabled.plist — re-run --audit + apply afterwards. Siri / Apple
Intelligence / analytics policy is better enforced via MDM restriction
profiles, which survive upgrades; launchctl covers what profiles can't.

Maintaining across macOS versions
---------------------------------
Apple changes three things independently between releases: plist
*filename*, the *Label* key inside it (what launchctl uses), and service
*existence*. Filenames and labels matched on Sequoia but diverged on
Tahoe — never assume the filename is the label; always read the Label:

| Plist filename              | Actual Label                          |
| ---                         | ---                                   |
| corespeechd.system.plist    | com.apple.corespeechd_system          |
| findmymac.plist             | com.apple.findmymacd                  |
| mDNSResponder.plist         | com.apple.mDNSResponder.reloaded      |
| CommCenter-osx.plist        | com.apple.CommCenter                  |
| Maps.pushdaemon.plist       | com.apple.Maps.mapspushd              |
| imtransferagent.plist       | com.apple.imcore.imtransferagent      |
| MENotificationAgent.plist   | com.apple.MENotificationService       |
| macos.studentd.plist        | com.apple.studentd                    |
| sidecar-hid-relay.plist     | com.apple.sidecar-display-agent       |
| avconferenced.plist         | com.apple.videoconference.camera (!)  |

The last row is dangerous: avconferenced.plist hosts the *camera*, while
the real FaceTime service is facetimemessagestored. Before disabling any
new label, read the plist's ProgramArguments/MachServices — names lie.

Audit workflow (--audit runs the checks built in; these are the manual
equivalents and the post-upgrade procedure):

1. ``./macos-lean.py --audit`` — review STALE and NEW? lines.
2. ``./macos-lean.py --dry-run | rg -o '(com|io)\\.[A-Za-z0-9._-]+' | sort -u``
   gives the effective managed-label list for manual diffing against a
   live index (``plutil -extract Label raw`` over /System and /Library
   LaunchAgents/Daemons).
3. For each NEW? label, read ProgramArguments before touching it.
4. ``./macos-lean.py --dry-run``, then apply, then reboot.
5. Test ``tmutil``/``pmset``/``networksetup``/``defaults``/``log`` verbs per
   release (e.g. ``tmutil disablelocal`` died in Tahoe).
6. Manual items no script can cover: Settings > General > Login Items &
   Extensions > Background App Activity (new in 27).

Traps: ``launchctl print-disabled`` shows stale entries from past
disables — it proves nothing about valid labels. Finding a plist by
filename confirms existence, not correctness. BackgroundTaskManagement
(agent + daemon) is Login Items infrastructure — disabling breaks login
items, and 27's Background App Activity UI sits on top of it. sysdiagnose
(agent/helper) is on-demand manual diagnostics — keep it; you want it
when things break. (Historical: the first --audit mixed an LC_ALL=C sort
with a locale-aware comm and reported bogus STALE lines. Python's
codepoint sort makes that class of bug impossible.)

macOS 27 (Golden Gate) live audit
---------------------------------
Audited --audit on 27.0 build 26A428 (Apple silicon): no stale disable
targets. Renames/removals: both sysdiagnose plists share the label
``com.apple.sysdiagnose`` (index labels, not filenames);
``com.apple.AirPortBaseStationAgent`` is gone (only ``airportd`` remains;
no replacement preserve check exists).

Candidate dispositions (plist program + launchd domain confirmed via
``launchctl print`` before categorizing):

| Label | Program / domain | Disposition |
| --- | --- | --- |
| backgroundtaskmanagement.agent | BackgroundTaskManagementAgent, gui | Preserve (Login Items) |
| backgroundtaskmanagementd | backgroundtaskmanagementd -daemon, system | Preserve (Login Items) |
| cloudtelemetryd | CloudTelemetry.framework, system | Disable (system) |
| imageplaygroundd | SuggestedImage.framework, gui | Disable (user) |
| libsqlite3.dbtelemetryd | /usr/libexec/dbtelemetryd, system | Disable (system) |
| siriappintentsd | SiriAppIntentsRuntime.framework, gui | Disable (user) |
| sysdiagnose / _agent / _helper | sysdiagnosed / sysdiagnose_helper | Preserve (on-demand diagnostics) |
| visualintelligenced | VisualIntelligenceServices.framework, gui | Disable (user) |

Interface notes (27): pmset/mdutil/tmutil/networksetup/defaults verbs
used here all verified; ``log config --mode level:off|default`` via
/usr/bin/log (the zsh ``log`` builtin is unrelated); Kandji/CrowdStrike
are optional (absent = not installed, never STALE); the 27 unified-log
archive format change is irrelevant (live logging only, never archives).

Requires macOS (launchctl, defaults, pmset, mdutil, tmutil, networksetup).
Only the standard library is used.
"""

from __future__ import annotations

import argparse
import datetime
import os
import plistlib
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
from dataclasses import dataclass, field
from pathlib import Path


# ---------------------------------------------------------------------------
# Managed label lists (audited per the docstring; keep in label order).
# ---------------------------------------------------------------------------

# (section title, domain, labels) — domain is "user" (gui/UID) or "system".
DISABLE_SECTIONS: list[tuple[str, str, list[str]]] = [
    ("Siri & Assistant", "user", [
        "com.apple.assistant_service",
        "com.apple.assistant_cdmd",
        "com.apple.assistantd",
        "com.apple.Siri.agent",
        "com.apple.siriknowledged",
        "com.apple.siriactionsd",
        "com.apple.sirittsd",
        "com.apple.SiriTTSTrainingAgent",
        "com.apple.siriinferenced",
        "com.apple.corespeechd",
        "com.apple.DictationIM",
        "com.apple.speech.speechdatainstallerd",
        "com.apple.parsec-fbf",
        "com.apple.parsecd",
        "com.apple.suggestd",
        "com.apple.proactived",
        "com.apple.proactiveeventtrackerd",
        "com.apple.ContextStoreAgent",
        "com.apple.duetexpertd",
        "com.apple.siriappintentsd",
    ]),
    ("Apple Intelligence & ML", "user", [
        "com.apple.intelligenceplatformd",
        "com.apple.intelligenceflowd",
        "com.apple.intelligencecontextd",
        "com.apple.intelligencetasksd",
        "com.apple.intelligentroutingd",
        "com.apple.knowledgeconstructiond",
        "com.apple.generativeexperiencesd",
        "com.apple.privatecloudcomputed",
        "com.apple.textunderstandingd",
        "com.apple.ciphermld",
        "com.apple.milod",
        "com.apple.mlhostd",
        "com.apple.mlruntimed",
        "com.apple.ModelCatalogAgent",
        "com.apple.imageplaygroundd",
        "com.apple.visualintelligenced",
    ]),
    ("Telemetry & Analytics", "user", [
        "com.apple.ap.adprivacyd",
        "com.apple.ap.promotedcontentd",
        "com.apple.BiomeAgent",
        "com.apple.biomesyncd",
        "com.apple.UsageTrackingAgent",
        "com.apple.triald",
        "com.apple.inputanalyticsd",
        "com.apple.dprivacyd",
        "com.apple.diagnostics_agent",
        "com.apple.diagnosticspushd",
        "com.apple.DiagnosticsReporter",
        "com.apple.feedbackd",
        "com.apple.betaenrollmentagent",
        "com.apple.appleseed.seedusaged",
        "com.apple.appleseed.seedusaged.postinstall",
        "com.apple.amsengagementd",
        "com.apple.analyticsagent",
        "com.apple.geoanalyticsd",
        "com.apple.metrickitd",
        "com.apple.diagnosticextensionsd",
        "com.apple.backgroundassets.user",
        "com.apple.spindump_agent",
        "com.apple.webprivacyd",
        "com.apple.ecosystemagent",
    ]),
    ("Apple Apps (Music, News, Weather, Games, Maps, etc.)", "user", [
        "com.apple.AMPArtworkAgent",
        "com.apple.AMPDeviceDiscoveryAgent",
        "com.apple.AMPLibraryAgent",
        "com.apple.AMPDevicesAgent",
        "com.apple.AMPSystemPlayerAgent",
        "com.apple.amp.mediasharingd",
        "com.apple.itunescloudd",
        "com.apple.newsd",
        "com.apple.financed",
        "com.apple.tipsd",
        "com.apple.weatherd",
        "com.apple.sportsd",
        "com.apple.shazamd",
        "com.apple.voicememod",
        "com.apple.watchlistd",
        "com.apple.videosubscriptionsd",
        "com.apple.gamed",
        "com.apple.GameController.gamecontrolleragentd",
        "com.apple.GamePolicyAgent",
        "com.apple.gamesaved",
        "com.apple.replayd",
        "com.apple.remindd",
        "com.apple.passd",
        "com.apple.Maps.mapspushd",
        "com.apple.maps.destinationd",
        "com.apple.Maps.mapssyncd",
        "com.apple.homed",
        "com.apple.homeenergyd",
        "com.apple.homeeventsd",
        "com.apple.followupd",
        "com.apple.sociallayerd",
        "com.apple.StatusKitAgent",
        "com.apple.studentd",
        "com.apple.stickersd",
        "com.apple.navd",
        "com.apple.amsondevicestoraged",
        "com.apple.amsaccountsd",
        "com.apple.avatarsd",
        "com.apple.mobiletimerd",
        "com.apple.appplaceholdersyncd",
    ]),
    ("iMessage, FaceTime & Phone", "user", [
        "com.apple.imagent",
        "com.apple.imautomatichistorydeletionagent",
        "com.apple.imcore.imtransferagent",
        "com.apple.CallHistoryPluginHelper",
        "com.apple.CallHistorySyncHelper",
        "com.apple.callhistoryd",
        "com.apple.callintelligenced",
        "com.apple.telephonyutilities.callservicesd",
        "com.apple.facetimemessagestored",
        "com.apple.CommCenter",
    ]),
    ("Continuity (keeping sharingd/rapportd for AirDrop & AirPlay)", "user", [
        "com.apple.ensemble",
        "com.apple.sidecar-relay",
        "com.apple.sidecar-display-agent",
        "com.apple.coreservices.useractivityd",
        "com.apple.cmio.ContinuityCaptureAgent",
    ]),
    ("Family & Parental Controls", "user", [
        "com.apple.familycircled",
        "com.apple.familycontrols.useragent",
        "com.apple.FamilyControlsAgent",
        "com.apple.familynotificationd",
        "com.apple.ScreenTimeAgent",
        "com.apple.askpermissiond",
        "com.apple.AskPermissionUI",
    ]),
    ("Screen Sharing", "user", [
        "com.apple.screensharing.agent",
        "com.apple.screensharing.menuextra",
        "com.apple.screensharing.MessagesAgent",
    ]),
    ("Photos & Media Analysis", "user", [
        "com.apple.photoanalysisd",
        "com.apple.mediaanalysisd",
        "com.apple.mediastream.mstreamd",
        "com.apple.cloudphotod",
    ]),
    ("Location Tracking & Find My", "user", [
        "com.apple.routined",
        "com.apple.geodMachServiceBridge",
        "com.apple.knowledge-agent",
        "com.apple.icloud.searchpartyuseragent",
        "com.apple.findmy.findmylocateagent",
        "com.apple.findmymacmessenger",
        "com.apple.icloud.findmydeviced.findmydevice-user-agent",
    ]),
    ("Spotlight & Indexing", "user", [
        "com.apple.Spotlight",
        "com.apple.corespotlightd",
        "com.apple.corespotlightservice",
        "com.apple.spotlightknowledged",
        "com.apple.spotlightknowledged.importer",
        "com.apple.spotlightknowledged.updater",
        "com.apple.managedcorespotlightd",
        "com.apple.metadata.mdbulkimport",
        "com.apple.metadata.mdwrite",
        "com.apple.metadata.mdflagwriter",
        "com.apple.mdworker.shared",
        "com.apple.mdworker.single.arm64",
        "com.apple.mdworker.single.x86_64",
        "com.apple.mdworker.sizing",
        "com.apple.mdworker.mail",
    ]),
    ("Mail (not using)", "user", [
        "com.apple.email.maild",
        "com.apple.MENotificationService",
        "com.apple.icloudmailagent",
    ]),
    ("Safari (browser only — keeping PasswordBreachAgent for Passwords.app)", "user", [
        "com.apple.SafariBookmarksSyncAgent",
        "com.apple.SafariNotificationAgent",
        "com.apple.SafariLaunchAgent",
        "com.apple.Safari.History",
        "com.apple.SafariHistoryServiceAgent",
        "com.apple.webinspectord",
    ]),
    ("App Store", "user", [
        "com.apple.appstoreagent",
        "com.apple.appstorecomponentsd",
        "com.apple.commerce",
        "com.apple.storeaccountd",
        "com.apple.storedownloadd",
        "com.apple.storekitagent",
        "com.apple.storelegacy",
        "com.apple.storeassetd",
        "com.apple.storeuid",
        "com.apple.SoftwareUpdateNotificationManager",
    ]),
    ("Focus & Misc", "user", [
        "com.apple.donotdisturbd",
        "com.apple.accessibility.MotionTrackingAgent",
        "com.apple.accessibility.heard",
        "com.apple.voicebankingd",
        "com.apple.dataaccess.dataaccessd",
        "com.apple.progressd",
        "com.apple.TMHelperAgent",
        "com.apple.translationd",
        "com.apple.peopled",
        "com.apple.contacts.donation-agent",
        "com.apple.ThreadCommissionerService",
        "com.apple.AssetCacheLocatorService",
        "com.apple.MobileAccessoryUpdater.fudHelperAgent",
        "com.apple.syncdefaultsd",
        "com.apple.recentsd",
        "com.apple.ReportCrash",
    ]),
    ("System — Siri", "system", [
        "com.apple.corespeechd_system",
    ]),
    ("System — Analytics", "system", [
        "com.apple.analyticsd",
        "com.apple.audioanalyticsd",
        "com.apple.diagnosticd",
        "com.apple.diagnosticservicesd",
        "com.apple.dprivacyd",
        "com.apple.ecosystemanalyticsd",
        "com.apple.ecosystemd",
        "com.apple.osanalytics.osanalyticshelper",
        "com.apple.usbctelemetryd",
        "com.apple.InstallerDiagnostics.installerdiagd",
        "com.apple.InstallerDiagnostics.installerdiagwatcher",
        "com.apple.wifianalyticsd",
        "com.apple.triald.system",
        "com.apple.sysmond",
        "com.apple.tailspind",
        "com.apple.cloudtelemetryd",
        "com.apple.libsqlite3.dbtelemetryd",
    ]),
    ("System — App Store", "system", [
        "com.apple.appstored",
        "com.apple.storereceiptinstaller",
    ]),
    ("System — Unused Services", "system", [
        "com.apple.backupd",
        "com.apple.backupd-helper",
        "com.apple.biomed",
        "com.apple.coreduetd",
        "com.apple.diagnosticextensions.osx.timemachine.helper",
        "com.apple.familycontrols",
        "com.apple.ftp-proxy",
        "com.apple.GameController.gamecontrollerd",
        "com.apple.gamepolicyd",
        "com.apple.netbiosd",
        "com.apple.screensharing",
        "com.apple.dhcp6d",
    ]),
    ("System — Wireless & Network Diagnostics", "system", [
        "com.apple.symptomsd",
        "com.apple.symptomsd-diag",
        "com.apple.spindump",
        "com.apple.nfcd",
    ]),
    ("System — Find My", "system", [
        "com.apple.findmymacd",
        "com.apple.findmy.findmybeaconingd",
        "com.apple.findmymacmessenger",
        "com.apple.icloud.findmydeviced",
        "com.apple.icloud.searchpartyd",
    ]),
    ("System — Spotlight Indexing", "system", [
        "com.apple.diagnosticextensions.osx.spotlight.helper",
        "com.apple.metadata.mds.index",
        "com.apple.metadata.mds.scan",
        "com.apple.metadata.mds.spindump",
    ]),
]


@dataclass(frozen=True)
class PreserveCheck:
    """A service that must stay enabled. `optional` = third-party product
    that may not be installed (absent is "not installed", never STALE)."""

    label: str
    desc: str
    domain: str  # "user" or "system"
    optional: bool = False


# (section title, checks) — order defines verify output order.
PRESERVE_SECTIONS: list[tuple[str, list[PreserveCheck]]] = [
    ("Verify: QuickLook", [
        PreserveCheck("com.apple.quicklook", "QuickLook", "user"),
        PreserveCheck("com.apple.quicklook.ui.helper", "QuickLook UI helper", "user"),
        PreserveCheck("com.apple.quicklook.ThumbnailsAgent", "QuickLook thumbnails", "user"),
    ]),
    ("Verify: AirDrop & AirPlay", [
        PreserveCheck("com.apple.sharingd", "AirDrop/sharing daemon", "user"),
        PreserveCheck("com.apple.AirPlayUIAgent", "AirPlay UI", "user"),
        PreserveCheck("com.apple.rapportd", "Device discovery (rapportd)", "user"),
        PreserveCheck("com.apple.RapportUIAgent", "Device discovery UI", "user"),
        PreserveCheck("com.apple.bluetoothuserd", "Bluetooth user agent", "user"),
        PreserveCheck("com.apple.AirPlayXPCHelper", "AirPlay XPC helper", "system"),
        PreserveCheck("com.apple.bluetoothd", "Bluetooth daemon", "system"),
        PreserveCheck("com.apple.rapportd", "Device discovery daemon", "system"),
    ]),
    ("Verify: iCloud Drive", [
        PreserveCheck("com.apple.bird", "iCloud Drive sync (bird)", "user"),
        PreserveCheck("com.apple.cloudd", "iCloud core daemon", "user"),
        PreserveCheck("com.apple.nsurlsessiond", "Network transfers", "user"),
        PreserveCheck("com.apple.FileProvider", "File Provider framework", "user"),
        PreserveCheck("com.apple.iCloudNotificationAgent", "iCloud push notifications", "user"),
        PreserveCheck("com.apple.protectedcloudstorage.protectedcloudkeysyncing",
                      "Cloud encryption keys", "user"),
        PreserveCheck("com.apple.cloudd", "iCloud system daemon", "system"),
        PreserveCheck("com.apple.nsurlsessiond", "Network transfers (system)", "system"),
    ]),
    ("Verify: Apple Passwords", [
        PreserveCheck("com.apple.AuthenticationServicesCore.AuthenticationServicesAgent",
                      "Authentication services", "user"),
        PreserveCheck("com.apple.LocalAuthentication.UIAgent",
                      "Local auth UI (Touch ID prompts)", "user"),
        PreserveCheck("com.apple.swcd", "Shared Web Credentials", "user"),
        PreserveCheck("com.apple.AutoFillPanel", "AutoFill panel", "user"),
        PreserveCheck("com.apple.accountsd", "Account management", "user"),
        PreserveCheck("com.apple.akd", "Auth Kit (Apple ID)", "user"),
        PreserveCheck("com.apple.security.cloudkeychainproxy3", "iCloud Keychain sync", "user"),
        PreserveCheck("com.apple.Safari.PasswordBreachAgent",
                      "Password breach monitoring", "user"),
    ]),
    ("Verify: Notes", [
        PreserveCheck("com.apple.synapse.contentlinkingd", "Notes content linking", "user"),
    ]),
    ("Verify: Camera & Video Calls", [
        PreserveCheck("com.apple.videoconference.camera", "Video conferencing camera", "user"),
        PreserveCheck("com.apple.cmio.LaunchCMIOUserExtensionsAgent", "Camera extensions", "user"),
        PreserveCheck("com.apple.ptpcamerad", "Camera daemon", "user"),
    ]),
    ("Verify: AirPods & Bluetooth Audio", [
        PreserveCheck("com.apple.BTServer.cloudpairing",
                      "BT cloud pairing (cross-device AirPods)", "user"),
        PreserveCheck("com.apple.bluetoothd", "Bluetooth daemon", "system"),
    ]),
    ("Verify: Touch ID", [
        PreserveCheck("com.apple.biometrickitd", "Touch ID", "system"),
    ]),
    ("Verify: Core UI", [
        PreserveCheck("com.apple.Dock.agent", "Dock", "user"),
        PreserveCheck("com.apple.Finder", "Finder", "user"),
        PreserveCheck("com.apple.WindowManager.agent", "Window Manager", "user"),
        PreserveCheck("com.apple.SystemUIServer.agent", "System UI Server", "user"),
        PreserveCheck("com.apple.controlcenter", "Control Center", "user"),
        PreserveCheck("com.apple.WindowServer", "WindowServer", "system"),
    ]),
    ("Verify: Input & Clipboard", [
        PreserveCheck("com.apple.pboard", "Clipboard (pasteboard)", "user"),
        PreserveCheck("com.apple.imklaunchagent", "Input method framework", "user"),
        PreserveCheck("com.apple.keyboardservicesd", "Keyboard services", "user"),
        PreserveCheck("com.apple.TextInputMenuAgent", "Text input menu", "user"),
    ]),
    ("Verify: Notifications", [
        PreserveCheck("com.apple.notificationcenterui.agent", "Notification Center", "user"),
        PreserveCheck("com.apple.usernoted", "User notifications", "user"),
        PreserveCheck("com.apple.usernotificationsd", "Notification delivery", "user"),
    ]),
    ("Verify: Audio", [
        PreserveCheck("com.apple.audio.coreaudiod", "Core Audio", "system"),
    ]),
    ("Verify: Networking", [
        PreserveCheck("com.apple.mDNSResponder.reloaded", "DNS/Bonjour", "system"),
        PreserveCheck("com.apple.configd", "Network configuration", "system"),
        PreserveCheck("com.apple.airportd", "WiFi", "system"),
    ]),
    ("Verify: Security & Auth", [
        PreserveCheck("com.apple.securityd", "Security daemon", "system"),
        PreserveCheck("com.apple.opendirectoryd", "Directory services", "system"),
        PreserveCheck("com.apple.sandboxd", "App sandbox", "system"),
    ]),
    ("Verify: Disk & Filesystem", [
        PreserveCheck("com.apple.diskarbitrationd", "Disk Arbitration", "system"),
        PreserveCheck("com.apple.apfsd", "APFS filesystem", "system"),
    ]),
    ("Verify: Calendar", [
        PreserveCheck("com.apple.calaccessd", "Calendar access", "user"),
    ]),
    ("Verify: Photos", [
        PreserveCheck("com.apple.photolibraryd", "Photos library", "user"),
    ]),
    ("Verify: MDM & Endpoint Security", [
        PreserveCheck("io.kandji.Kandji", "Kandji MDM", "user", optional=True),
        PreserveCheck("com.crowdstrike.falcon.UserAgent", "CrowdStrike Falcon",
                      "user", optional=True),
    ]),
    ("Verify: Spell Check & Language", [
        PreserveCheck("com.apple.applespell", "Spell checking", "user"),
        PreserveCheck("com.apple.naturallanguaged", "Natural language processing", "user"),
    ]),
]


@dataclass(frozen=True)
class DefaultSpec:
    """A `defaults write domain key type value` managed by this script.
    `expected` is the `defaults read` output string meaning "already set"."""

    domain: str
    key: str
    expected: str
    type_flag: str
    value: str
    system: bool = False  # True → run under sudo


USER_DEFAULTS: dict[str, list[DefaultSpec]] = {
    "System Preferences": [
        DefaultSpec("com.apple.assistant.support", "Assistant Enabled", "0", "-bool", "false"),
        DefaultSpec("com.apple.Siri", "StatusMenuVisible", "0", "-bool", "false"),
        DefaultSpec("com.apple.Siri", "UserHasDeclinedEnable", "1", "-bool", "true"),
        DefaultSpec("com.apple.Siri", "VoiceTriggerUserEnabled", "0", "-bool", "false"),
        DefaultSpec("com.apple.lookup.shared", "LookupSuggestionsDisabled", "1", "-bool", "true"),
    ],
    "App Store Preferences": [
        DefaultSpec("com.apple.commerce", "AutoUpdate", "0", "-bool", "false"),
        DefaultSpec("com.apple.commerce", "AutoUpdateRestartRequired", "0", "-bool", "false"),
        DefaultSpec("com.apple.SoftwareUpdate", "AutomaticCheckEnabled", "0", "-bool", "false"),
        DefaultSpec("com.apple.SoftwareUpdate", "AutomaticDownload", "0", "-bool", "false"),
    ],
    "CrashReporter Preferences": [
        DefaultSpec("com.apple.CrashReporter", "DialogType", "none", "-string", "none"),
    ],
    "App Quit & Screensaver Preferences": [
        DefaultSpec("NSGlobalDomain", "NSQuitAlwaysKeepsWindows", "0", "-bool", "false"),
        DefaultSpec("com.apple.screensaver", "idleTime", "0", "-int", "0"),
        DefaultSpec("NSGlobalDomain", "NSDocumentSaveNewDocumentsToCloud",
                    "0", "-bool", "false"),
    ],
}

PERFORMANCE_DEFAULTS: list[DefaultSpec] = [
    DefaultSpec("NSGlobalDomain", "NSAutomaticWindowAnimationsEnabled", "0", "-bool", "false"),
    DefaultSpec("NSGlobalDomain", "NSWindowResizeTime", "0.001", "-float", "0.001"),
    DefaultSpec("com.apple.dock", "launchanim", "0", "-bool", "false"),
    DefaultSpec("com.apple.dock", "autohide-delay", "0", "-float", "0"),
    DefaultSpec("com.apple.dock", "autohide-time-modifier", "0.1", "-float", "0.1"),
    DefaultSpec("com.apple.dock", "expose-animation-duration", "0.1", "-float", "0.1"),
    DefaultSpec("NSGlobalDomain", "NSScrollAnimationEnabled", "0", "-bool", "false"),
    DefaultSpec("com.apple.universalaccess", "reduceTransparency", "1", "-bool", "true"),
    DefaultSpec("com.apple.universalaccess", "reduceMotion", "1", "-bool", "true"),
]

MDNS_DEFAULT = DefaultSpec("/Library/Preferences/com.apple.mDNSResponder.plist",
                            "NoMulticastAdvertisements", "1", "-bool", "YES", system=True)
CAPTIVE_DEFAULT = DefaultSpec(
    "/Library/Preferences/SystemConfiguration/com.apple.captive.control",
    "Active", "0", "-bool", "false", system=True)

# (pmset scope, key, value) for `sudo pmset <scope> <key> <value>`.
PMSET_APPLY: list[tuple[str, str, str]] = [
    ("-b", "powernap", "0"),
    ("-b", "tcpkeepalive", "0"),
    ("-b", "proximitywake", "0"),
    ("-b", "womp", "0"),
    ("-b", "ttyskeepawake", "0"),
    ("-b", "standbydelayhigh", "600"),
    ("-b", "standbydelaylow", "600"),
    ("-b", "highstandbythreshold", "50"),
    ("-b", "hibernatemode", "0"),
    ("-c", "hibernatemode", "3"),
    ("-b", "displaysleep", "2"),
    ("-b", "sleep", "10"),
    ("-b", "autopoweroff", "1"),
    ("-b", "autopoweroffdelay", "1800"),
]
PMSET_REVERT: list[tuple[str, str, str]] = [
    ("-b", "powernap", "1"),
    ("-b", "tcpkeepalive", "1"),
    ("-b", "proximitywake", "1"),
    ("-b", "womp", "1"),
    ("-b", "ttyskeepawake", "1"),
    ("-b", "standbydelayhigh", "86400"),
    ("-b", "standbydelaylow", "10800"),
    ("-b", "highstandbythreshold", "50"),
    ("-b", "hibernatemode", "3"),
    ("-c", "hibernatemode", "3"),
    ("-b", "displaysleep", "5"),
    ("-b", "sleep", "10"),
    ("-b", "autopoweroff", "1"),
    ("-b", "autopoweroffdelay", "28800"),
]

LAUNCHD_DIRS = (
    "/System/Library/LaunchAgents",
    "/System/Library/LaunchDaemons",
    "/Library/LaunchAgents",
    "/Library/LaunchDaemons",
)

DISABLED_RE = re.compile(r'"([^"]+)"\s*=>\s*(disabled|true)\b')
PID_RE = re.compile(r"pid\s*=\s*(\d+)")
# Case pattern: *[Tt]ailscale*|*VPN*|*[Vv]pn*|*utun* (case-sensitive as shown).
VPN_SKIP_RE = re.compile(r"[Tt]ailscale|VPN|[Vv]pn|utun")
AUDIT_CANDIDATE_RE = re.compile(
    r"intellig|siri|analytic|telemetry|biome|trial|diagnos|genmoji|playground"
    r"|writing\.tool|backgroundtask|background\.task", re.IGNORECASE)


def os_name_for_major(major: str) -> str:
    return {
        "15": "Sequoia",
        "26": "Tahoe",
        "27": "Golden Gate",
    }.get(major, "unvalidated (lists verified on 15/26; 27 by --audit)")


def short_service_name(label: str) -> str:
    """Last dotted component, mirroring `sed 's/.*\\.//'`."""
    return label.rsplit(".", 1)[-1]


def is_vpn_service(name: str) -> bool:
    return VPN_SKIP_RE.search(name) is not None


def parse_disabled_output(text: str) -> set[str]:
    """Parse `launchctl print-disabled` into disabled labels."""
    return {m.group(1) for m in DISABLED_RE.finditer(text or "")}


def strip_networkservice(raw: str) -> str:
    """Strip the "* " prefix networksetup uses for disabled services."""
    return raw[2:] if raw.startswith("* ") else raw


def audit_findings(real: set[str], targets: set[str],
                   preserve: set[str]) -> tuple[list[str], list[str], list[str]]:
    """Pure audit computation: (stale targets, stale preserve, NEW? candidates)."""
    stale_targets = sorted(targets - real)
    stale_preserve = sorted(preserve - real)
    candidates = sorted(
        label for label in real - targets - preserve
        if AUDIT_CANDIDATE_RE.search(label))
    return stale_targets, stale_preserve, candidates


# ---------------------------------------------------------------------------
# Runtime state
# ---------------------------------------------------------------------------

@dataclass
class State:
    mode: str  # "apply", "dry-run", "audit", or "revert"
    uid: int
    macos_version: str
    os_name: str
    os_major: str
    real_labels: set[str] = field(default_factory=set)
    audit_targets: set[str] = field(default_factory=set)
    audit_preserve: set[str] = field(default_factory=set)
    disabled_user: set[str] = field(default_factory=set)
    disabled_system: set[str] = field(default_factory=set)
    pending_system: list[str] = field(default_factory=list)
    n_applied: int = 0
    n_skipped: int = 0
    n_unchanged: int = 0
    verify_fail: int = 0

    @property
    def dry_run(self) -> bool:
        return self.mode == "dry-run"

    @property
    def audit(self) -> bool:
        return self.mode == "audit"

    @property
    def revert(self) -> bool:
        return self.mode == "revert"

    @property
    def mutating(self) -> bool:
        return self.mode in ("apply", "revert")


def run(argv: list[str], *, sudo: bool = False,
        check: bool = False) -> subprocess.CompletedProcess[str]:
    """Run a command without a shell. Never raises on failure by default."""
    if sudo:
        argv = ["sudo", *argv]
    try:
        return subprocess.run(argv, capture_output=True, text=True, check=check)
    except FileNotFoundError as exc:
        return subprocess.CompletedProcess(argv, 127, "", str(exc))


def section(title: str) -> None:
    print()
    print(f"=== {title} ===")


# ---------------------------------------------------------------------------
# Live label index (plistlib, cached per OS build)
# ---------------------------------------------------------------------------

def read_plist_label(path: Path) -> str | None:
    try:
        with path.open("rb") as fh:
            plist = plistlib.load(fh)
    except Exception:
        return None
    label = plist.get("Label") if isinstance(plist, dict) else None
    return label if isinstance(label, str) and label else None


def build_label_index(build_ver: str) -> set[str]:
    cache = Path(f"/tmp/macos-lean-index-{build_ver}.txt")
    if cache.is_file():
        try:
            return {line.strip() for line in cache.read_text().splitlines() if line.strip()}
        except OSError:
            pass
    labels: set[str] = set()
    for dirname in LAUNCHD_DIRS:
        try:
            entries = sorted(Path(dirname).glob("*.plist"))
        except OSError:
            continue
        for plist_path in entries:
            label = read_plist_label(plist_path)
            if label is None:
                # Fall back to plutil for plists plistlib cannot parse.
                proc = run(["plutil", "-extract", "Label", "raw", str(plist_path)])
                candidate = proc.stdout.strip()
                if proc.returncode == 0 and candidate:
                    label = candidate
            if label:
                labels.add(label)
    if labels:
        try:
            with tempfile.NamedTemporaryFile("w", dir="/tmp", delete=False) as tmp:
                tmp.write("".join(f"{label}\n" for label in sorted(labels)))
                tmp_path = tmp.name
            os.replace(tmp_path, cache)
        except OSError:
            pass
    return labels


# ---------------------------------------------------------------------------
# Snapshot + disabled-state cache + sudo keepalive
# ---------------------------------------------------------------------------

def snapshot_state(state: State) -> None:
    if not state.mutating:
        return
    snapdir = Path.home() / ".local" / "state" / "macos-lean"
    try:
        snapdir.mkdir(parents=True, exist_ok=True)
    except OSError:
        return
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    snap = snapdir / f"snapshot-{stamp}"
    user = run(["launchctl", "print-disabled", f"gui/{state.uid}"])
    system = run(["launchctl", "print-disabled", "system"], sudo=True)
    try:
        with snap.open("w") as fh:
            fh.write(f"# macOS {state.macos_version} {datetime.datetime.now()}\n")
            fh.write(f"## launchctl print-disabled gui/{state.uid}\n")
            fh.write(user.stdout)
            fh.write("## sudo launchctl print-disabled system\n")
            fh.write(system.stdout)
    except OSError:
        return
    print(f"Snapshot: {snap}")
    print()


def load_disabled_state(state: State) -> None:
    if state.mode != "apply":
        return
    user = run(["launchctl", "print-disabled", f"gui/{state.uid}"])
    if user.returncode != 0:
        print("Error: unable to read disabled user services")
        sys.exit(1)
    system = run(["launchctl", "print-disabled", "system"], sudo=True)
    if system.returncode != 0:
        print("Error: unable to read disabled system services")
        sys.exit(1)
    state.disabled_user = parse_disabled_output(user.stdout)
    state.disabled_system = parse_disabled_output(system.stdout)


class SudoKeepalive:
    """Refresh the sudo timestamp until stopped (apply/revert only)."""

    def __init__(self) -> None:
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True)

    def start(self) -> None:
        proc = run(["sudo", "-v"])
        if proc.returncode != 0:
            print("Error: sudo required")
            sys.exit(1)
        self._thread.start()

    def _loop(self) -> None:
        while not self._stop.wait(50):
            run(["sudo", "-n", "true"])

    def stop(self) -> None:
        self._stop.set()


# ---------------------------------------------------------------------------
# launchctl disable/enable + verify
# ---------------------------------------------------------------------------

def disable_user(state: State, label: str) -> None:
    if state.audit:
        state.audit_targets.add(label)
        print(f"  {label}" if label in state.real_labels else f"  STALE {label}")
    elif state.dry_run:
        if label in state.real_labels:
            print(f"  {label}")
        else:
            print(f"  STALE {label} (not on {state.os_name} "
                  f"{state.macos_version} — would skip)")
    elif state.revert:
        # Attempt even stale labels: clears orphaned disabled.plist entries
        # left by older OS releases.
        run(["launchctl", "enable", f"gui/{state.uid}/{label}"])
        print(f"  + {label}")
        state.n_applied += 1
    else:
        if label not in state.real_labels:
            print(f"  STALE {label} (skipped)")
            state.n_skipped += 1
            return
        if label in state.disabled_user:
            print(f"  = {label} (already disabled)")
            state.n_unchanged += 1
            return
        proc = run(["launchctl", "disable", f"gui/{state.uid}/{label}"])
        if proc.returncode != 0:
            print(f"  FAIL {label} (disable rejected)")
            state.n_skipped += 1
            return
        state.n_applied += 1
        state.disabled_user.add(label)
        # bootout is blocked by SIP; kill the process directly instead.
        # The disabled flag prevents MachService/LaunchEvent respawns.
        info = run(["launchctl", "print", f"gui/{state.uid}/{label}"])
        match = PID_RE.search(info.stdout)
        if match:
            try:
                os.kill(int(match.group(1)), signal.SIGTERM)
            except (OSError, ValueError):
                pass
        print(f"  - {label}")


def disable_system(state: State, label: str) -> None:
    if state.audit:
        state.audit_targets.add(label)
        print(f"  {label}" if label in state.real_labels else f"  STALE {label}")
    elif state.dry_run:
        if label in state.real_labels:
            print(f"  {label}")
        else:
            print(f"  STALE {label} (not on {state.os_name} "
                  f"{state.macos_version} — would skip)")
    elif state.revert:
        state.pending_system.append(label)
        print(f"  + {label}")
    else:
        if label not in state.real_labels:
            print(f"  STALE {label} (skipped)")
            state.n_skipped += 1
            return
        if label in state.disabled_system:
            print(f"  = {label} (already disabled)")
            state.n_unchanged += 1
            return
        state.pending_system.append(label)
        print(f"  - {label}")


def flush_system(state: State) -> None:
    if state.audit:
        state.pending_system.clear()
        return
    if not state.pending_system:
        return
    labels = state.pending_system
    state.pending_system = []
    if state.revert:
        for label in labels:
            run(["launchctl", "enable", f"system/{label}"], sudo=True)
            state.n_applied += 1
        return
    for label in labels:
        proc = run(["launchctl", "disable", f"system/{label}"], sudo=True)
        if proc.returncode != 0:
            print(f"  FAIL {label} (disable rejected)")
            state.n_skipped += 1
        else:
            state.n_applied += 1
            state.disabled_system.add(label)
    # Kill any that are still running.
    for label in labels:
        proc = run(["pgrep", "-x", short_service_name(label)])
        pids = proc.stdout.split()
        if pids:
            run(["kill", "-9", pids[0]], sudo=True)


def ensure_service(state: State, check: PreserveCheck) -> None:
    if check.optional and check.label not in state.real_labels:
        print(f"  --  {check.desc} not installed ({check.label})")
        return
    if state.audit:
        state.audit_preserve.add(check.label)
        if check.label in state.real_labels:
            print(f"  --  {check.desc} ({check.label})")
        else:
            print(f"  STALE  {check.desc} ({check.label}) — preserve check can never pass")
        return
    if state.dry_run:
        print(f"  --  {check.desc} ({check.label})")
        return
    if check.domain == "user":
        target = f"gui/{state.uid}/{check.label}"
        if not state.revert:
            # Force-enable in case it was accidentally disabled.
            run(["launchctl", "enable", target])
        ok = run(["launchctl", "print", target]).returncode == 0
    else:
        target = f"system/{check.label}"
        if not state.revert:
            run(["launchctl", "enable", target], sudo=True)
        ok = run(["launchctl", "print", target], sudo=True).returncode == 0
    if ok:
        print(f"  OK  {check.desc}")
    else:
        print(f"  FAIL {check.desc} — not loaded ({check.label})")
        state.verify_fail += 1


# ---------------------------------------------------------------------------
# defaults helpers (convergent: write only when the value differs)
# ---------------------------------------------------------------------------

def defaults_read(spec: DefaultSpec) -> str | None:
    proc = run(["defaults", "read", spec.domain, spec.key], sudo=spec.system)
    if proc.returncode != 0:
        return None
    return proc.stdout.strip()


def ensure_default(spec: DefaultSpec) -> bool:
    """Write the preference only when it differs. Returns True if changed.

    Exits(1) on write failure, mirroring `ensure_default ... || exit 1`.
    """
    if defaults_read(spec) == spec.expected:
        return False
    proc = run(["defaults", "write", spec.domain, spec.key,
                spec.type_flag, spec.value], sudo=spec.system)
    if proc.returncode != 0:
        print(f"FAIL defaults {spec.domain} {spec.key}")
        sys.exit(1)
    return True


def defaults_delete(domain: str, key: str, *, sudo: bool = False) -> None:
    run(["defaults", "delete", domain, key], sudo=sudo)


# ---------------------------------------------------------------------------
# Sections: Spotlight/Time Machine, defaults, power, network, logging
# ---------------------------------------------------------------------------

def apply_spotlight_tmutil(state: State) -> None:
    section("Spotlight Indexing (mdutil)")
    if state.dry_run or state.audit:
        print("  would run: sudo mdutil -a -i off")
    elif state.revert:
        run(["mdutil", "-a", "-i", "on"], sudo=True)
        print("  Spotlight indexing re-enabled")
    else:
        # mdutil -E erases and rebuilds indexes, creating work on every
        # apply. Disabling indexing is the desired steady state.
        run(["mdutil", "-a", "-i", "off"], sudo=True)
        print("  Indexing disabled")

    section("Time Machine")
    if state.dry_run or state.audit:
        print("  would disable Time Machine")
    elif state.revert:
        run(["tmutil", "enable"], sudo=True)
        print("  Time Machine re-enabled")
    else:
        # Belt-and-suspenders alongside backupd/backupd-helper being disabled.
        run(["tmutil", "disable"], sudo=True)
        print("  Time Machine disabled")


USER_DEFAULTS_PREVIEW = {
    "System Preferences": [
        "  would disable Siri (assistant, menu bar, voice trigger)",
        "  would disable Spotlight suggestions",
    ],
    "App Store Preferences": [
        "  would disable App Store auto-check, auto-download, auto-update",
    ],
    "CrashReporter Preferences": [
        "  would suppress crash dialogs",
    ],
    "App Quit & Screensaver Preferences": [
        "  would disable window state save on quit",
        "  would disable screensaver (direct to display sleep)",
        "  would default new document save location to local (not iCloud)",
    ],
}

USER_DEFAULTS_REVERT = {
    "System Preferences": [
        ("com.apple.assistant.support", "Assistant Enabled"),
        ("com.apple.Siri", "StatusMenuVisible"),
        ("com.apple.Siri", "UserHasDeclinedEnable"),
        ("com.apple.Siri", "VoiceTriggerUserEnabled"),
        ("com.apple.lookup.shared", "LookupSuggestionsDisabled"),
    ],
    "App Store Preferences": [
        ("com.apple.commerce", "AutoUpdate"),
        ("com.apple.commerce", "AutoUpdateRestartRequired"),
        ("com.apple.SoftwareUpdate", "AutomaticCheckEnabled"),
        ("com.apple.SoftwareUpdate", "AutomaticDownload"),
    ],
    "CrashReporter Preferences": [
        ("com.apple.CrashReporter", "DialogType"),
    ],
    "App Quit & Screensaver Preferences": [
        ("NSGlobalDomain", "NSQuitAlwaysKeepsWindows"),
        ("com.apple.screensaver", "idleTime"),
        ("NSGlobalDomain", "NSDocumentSaveNewDocumentsToCloud"),
    ],
}

USER_DEFAULTS_DONE = {
    "System Preferences": [
        "  Siri fully disabled (assistant, menu bar, voice trigger)",
        "  Spotlight suggestions disabled",
    ],
    "App Store Preferences": [
        "  App Store auto-check, auto-download, auto-update disabled",
    ],
    "CrashReporter Preferences": [
        "  Crash dialogs suppressed",
    ],
    "App Quit & Screensaver Preferences": [
        "  Window state on quit disabled, screensaver disabled, new docs default to local",
    ],
}

USER_DEFAULTS_RESTORED = {
    "System Preferences": "  Preferences restored to defaults",
    "App Store Preferences": "  App Store preferences restored to defaults",
    "CrashReporter Preferences": "  CrashReporter preferences restored to defaults",
    "App Quit & Screensaver Preferences":
        "  App quit and screensaver preferences restored to defaults",
}


def apply_user_defaults(state: State) -> None:
    for title, specs in USER_DEFAULTS.items():
        section(title)
        if state.dry_run or state.audit:
            print("\n".join(USER_DEFAULTS_PREVIEW[title]))
        elif state.revert:
            for domain, key in USER_DEFAULTS_REVERT[title]:
                defaults_delete(domain, key)
            print(USER_DEFAULTS_RESTORED[title])
        else:
            # Don't write window/document state to disk on every app quit, etc.
            for spec in specs:
                ensure_default(spec)
            print("\n".join(USER_DEFAULTS_DONE[title]))


def apply_performance_defaults(state: State) -> None:
    section("Performance Defaults")
    if state.dry_run or state.audit:
        print("  would disable window open/close animations")
        print("  would set window resize time to 0.001s")
        print("  would disable Dock launch bounce animation")
        print("  would set Dock autohide delay to 0s, animation to 0.1s")
        print("  would set Mission Control animation to 0.1s")
        print("  would disable scroll animations")
        print("  would enable reduce transparency")
        print("  would enable reduce motion")
    elif state.revert:
        for spec in PERFORMANCE_DEFAULTS:
            defaults_delete(spec.domain, spec.key)
        run(["killall", "Dock"])
        print("  Performance defaults restored (Dock restarted)")
    else:
        changed = any(ensure_default(spec) for spec in PERFORMANCE_DEFAULTS)
        if changed:
            run(["killall", "Dock"])
            print("  Animations disabled, transparency reduced (Dock restarted)")
        else:
            print("  Performance defaults already set")


def apply_pmset(state: State) -> None:
    section("Power Management (pmset — battery)")
    if state.dry_run or state.audit:
        print("  would disable Power Nap on battery")
        print("  would disable TCP keepalive during sleep")
        print("  would disable proximity wake (iPhone/Watch)")
        print("  would disable Wake on LAN")
        print("  would disable TTY keepawake")
        print("  would set standby delay to 600s (default: up to 86400s)")
        print("  would set hibernatemode 0 on battery (no sleepimage writes)")
        print("  would set hibernatemode 3 on AC (safe sleep preserved)")
        print("  would delete existing sleepimage to reclaim disk space")
        print("  would set display sleep to 2 min on battery")
        print("  would set system sleep to 10 min on battery")
        print("  would enable auto power-off after 30 min standby")
    elif state.revert:
        for scope, key, value in PMSET_REVERT:
            run(["pmset", scope, key, value], sudo=True)
        print("  pmset battery defaults restored")
    else:
        for scope, key, value in PMSET_APPLY:
            proc = run(["pmset", scope, key, value], sudo=True)
            if proc.returncode != 0:
                print(f"  FAIL pmset {scope} {key} {value}")
        # Remove existing sleepimage — no longer needed on battery, reclaims
        # RAM-sized disk space. hibernatemode 0/3 split documented above.
        run(["rm", "-f", "/private/var/vm/sleepimage"], sudo=True)
        print("  Power Nap, TCP keepalive, proximity wake, WoL, TTY keepawake disabled")
        print("  Standby: 600s / auto power-off: 1800s")
        print("  hibernatemode 0 (battery) / 3 (AC), sleepimage removed")
        print("  Display sleep: 2 min, system sleep: 10 min")


def list_network_services() -> list[str]:
    proc = run(["networksetup", "-listallnetworkservices"])
    if proc.returncode != 0:
        return []
    services: list[str] = []
    for line in proc.stdout.splitlines()[1:]:  # skip header line
        name = strip_networkservice(line).strip()
        if name:
            services.append(name)
    return services


def apply_ipv6(state: State) -> None:
    section("IPv6 (all interfaces except VPN/Tailscale)")
    services = list_network_services()
    if state.dry_run or state.audit:
        print("  would disable IPv6 on all non-VPN interfaces:")
        for svc in services:
            if is_vpn_service(svc):
                print(f"    skip: {svc}")
            else:
                print(f"    off:  {svc}")
    elif state.revert:
        for svc in services:
            if is_vpn_service(svc):
                print(f"  skip {svc}")
            elif run(["networksetup", "-setv6automatic", svc], sudo=True).returncode == 0:
                print(f"  {svc}")
            else:
                print(f"  FAIL {svc}")
        print("  IPv6 restored to automatic on all interfaces")
    else:
        for svc in services:
            if is_vpn_service(svc):
                print(f"  skip {svc}")
            elif run(["networksetup", "-setv6off", svc], sudo=True).returncode == 0:
                print(f"  {svc}")
            else:
                print(f"  FAIL {svc}")
        print("  IPv6 disabled on all non-VPN interfaces")


def apply_mdns_captive(state: State) -> None:
    section("mDNS Multicast Advertisements")
    if state.dry_run or state.audit:
        print("  would stop Mac advertising its own services via mDNS")
    elif state.revert:
        defaults_delete("/Library/Preferences/com.apple.mDNSResponder.plist",
                        "NoMulticastAdvertisements", sudo=True)
        run(["killall", "mDNSResponder"], sudo=True)
        print("  mDNS multicast advertisements restored")
    else:
        # Stops Mac broadcasting its own services. Mac can still discover
        # others. Note: breaks this Mac as an AirPlay receiver target.
        if ensure_default(MDNS_DEFAULT):
            run(["killall", "mDNSResponder"], sudo=True)
            print("  mDNS multicast advertisements disabled (mDNSResponder restarted)")
        else:
            print("  mDNS multicast advertisements already disabled")

    section("Captive Network Detection")
    if state.dry_run or state.audit:
        print("  would disable captive portal HTTP probing")
    elif state.revert:
        defaults_delete("/Library/Preferences/SystemConfiguration/com.apple.captive.control",
                        "Active", sudo=True)
        print("  Captive network detection restored")
    else:
        # Stops background HTTP probes for hotel/airport captive portals.
        # Side effect: no auto-popup — open a browser manually to log in.
        if ensure_default(CAPTIVE_DEFAULT):
            print("  Captive network detection disabled")
        else:
            print("  Captive network detection already disabled")


def log_command() -> list[str]:
    if Path("/usr/bin/log").exists():
        return ["/usr/bin/log"]
    return ["log"]


def apply_logging(state: State) -> None:
    section("Unified Logging")
    if state.dry_run or state.audit:
        print("  would disable unified log system (no Console.app data, no log show)")
    elif state.revert:
        run([*log_command(), "config", "--mode", "level:default"], sudo=True)
        print("  Unified logging restored to default")
    else:
        # Shuts down the log subsystem — eliminates constant SSD writes to
        # /var/db/diagnostics. Trade-off: Console.app goes dark, `log show`
        # returns nothing, crash diagnosis is harder.
        run([*log_command(), "config", "--mode", "level:off"], sudo=True)
        print("  Unified logging disabled")


# ---------------------------------------------------------------------------
# Audit report + summary
# ---------------------------------------------------------------------------

def audit_report(state: State) -> None:
    stale_targets, stale_preserve, candidates = audit_findings(
        state.real_labels, state.audit_targets, state.audit_preserve)
    print()
    print("=== Audit: stale disable targets (in script, NOT on this OS) ===")
    for label in stale_targets:
        print(f"  STALE  {label}")
    print()
    print("=== Audit: stale preserve checks (in script, NOT on this OS) ===")
    for label in stale_preserve:
        print(f"  STALE  {label}")
    print()
    print("=== Audit: candidate new services (on OS, not in script) ===")
    for label in candidates:
        print(f"  NEW?   {label}")
    print()
    print("Review NEW? lines before disabling: check the plist's ProgramArguments")
    print("— names lie (e.g. avconferenced.plist hosts videoconference.camera).")


def print_summary(state: State, prog: str) -> None:
    print()
    print("============================================")
    if state.audit:
        audit_report(state)
        print("Audit complete. No changes made.")
        print(f"Next: ./{prog} --dry-run, then apply.")
    elif state.dry_run:
        print("Dry run complete. No changes made.")
        print(f"Any STALE lines above would be skipped on {state.os_name} "
              f"{state.macos_version}.")
        print("Run without --dry-run to apply.")
    elif state.revert:
        print(f"Re-enabled {state.n_applied} service(s). Reboot required.")
    else:
        print(f"Changed: {state.n_applied} disabled, {state.n_unchanged} "
              f"already disabled, {state.n_skipped} skipped (stale/rejected).")
        if state.verify_fail > 0:
            print(f"WARNING: {state.verify_fail} preserved service(s) not loaded.")
            print("Review FAIL lines above. May need reboot or")
            print("manual investigation.")
        else:
            print("All preserved services verified OK.")
        print()
        try:
            major = int(state.os_major)
        except ValueError:
            major = 0
        if major >= 27:
            print("27 reminders: check Settings > General > Login Items & Extensions >")
            print("Background App Activity (new per-app kill switch), and re-run --audit")
            print("after every OS update — disabled.plist may reset.")
        else:
            print("After upgrading macOS: re-run --audit, then --dry-run, then apply.")
            print("(Major upgrades may reset disabled.plist and rename labels.)")
        print()
        print("Reboot to finalize.")
        print()
        print("Inspect disabled services:")
        print(f"  launchctl print-disabled gui/{state.uid}")
        print("  sudo launchctl print-disabled system")
        print()
        print("Note: Cmd+Space (Spotlight) is now dead.")
        print("Set up Raycast/Alfred if you haven't already.")
    print("============================================")


# ---------------------------------------------------------------------------
# CLI + main
# ---------------------------------------------------------------------------

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="macos-lean.py",
        description="Make macOS lean: disable unnecessary services, converge preferences.",
        epilog="Always run --audit first after an OS upgrade, then --dry-run, then apply.",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--dry-run", action="store_true",
                       help="preview; stale labels flagged, no changes")
    group.add_argument("--audit", action="store_true",
                       help="validate labels vs live OS; no sudo, no changes")
    group.add_argument("--revert", action="store_true",
                       help="re-enable everything this script manages")
    return parser.parse_args(argv)


def sw_vers(key: str) -> str:
    proc = run(["sw_vers", f"-{key}"])
    return proc.stdout.strip() if proc.returncode == 0 else "unknown"


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    mode = "audit" if args.audit else "revert" if args.revert else \
        "dry-run" if args.dry_run else "apply"

    uid = os.getuid()
    macos_version = sw_vers("productVersion")
    major = macos_version.split(".")[0] if macos_version != "unknown" else "unknown"
    os_name = os_name_for_major(major)

    if mode == "audit":
        print(f"macOS Lean — AUDIT ({os_name} {macos_version}, no changes, no sudo)")
    elif mode == "revert":
        print(f"macOS Lean — REVERT mode ({os_name} {macos_version})")
    elif mode == "dry-run":
        print(f"macOS Lean — DRY RUN ({os_name} {macos_version}, no changes)")
    else:
        print(f"macOS Lean — {os_name} {macos_version}")
    print(f"User UID: {uid}")
    print()

    state = State(mode=mode, uid=uid, macos_version=macos_version,
                  os_name=os_name, os_major=major)
    state.real_labels = build_label_index(sw_vers("buildVersion"))

    keepalive: SudoKeepalive | None = None
    if state.mutating:
        keepalive = SudoKeepalive()
        keepalive.start()
    try:
        snapshot_state(state)
        load_disabled_state(state)

        for title, domain, labels in DISABLE_SECTIONS:
            section(title)
            for label in labels:
                if domain == "user":
                    disable_user(state, label)
                else:
                    disable_system(state, label)

        # One flush batches every system label: prints happen at disable
        # time, sudo + kills happen here.
        flush_system(state)

        apply_spotlight_tmutil(state)
        apply_user_defaults(state)
        apply_performance_defaults(state)
        apply_pmset(state)
        apply_ipv6(state)
        apply_mdns_captive(state)
        apply_logging(state)

        for title, checks in PRESERVE_SECTIONS:
            section(title)
            for check in checks:
                ensure_service(state, check)

        print_summary(state, Path(sys.argv[0]).name)
    finally:
        if keepalive is not None:
            keepalive.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())

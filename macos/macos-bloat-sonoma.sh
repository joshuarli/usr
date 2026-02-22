#!/bin/zsh

# https://gist.githubusercontent.com/b0gdanw/812997a189f72f3953e0a1bb237f783d/raw/8fd81b4674ccca893c61094361586a01d872a546/Disable-Sonoma-Bloatware.sh

# hmm disable doesn't seem to do anything and unload -w is deprecated / fails on sonoma

# Disabling SIP is required for bootout ("csrutil disable" from Terminal in Recovery)
# Modifications are written in /private/var/db/com.apple.xpc.launchd/ disabled.plist, disabled.501.plist
# To revert, delete /private/var/db/com.apple.xpc.launchd/ disabled.plist and disabled.501.plist and reboot; sudo rm -r /private/var/db/com.apple.xpc.launchd/*

# launchctl reboot userspace

# icloud and photos
# com.apple.bird
# 'com.apple.icloud.fmfd' \
# 'com.apple.nsurlsessiond' \
# 'com.apple.photolibraryd' \
# 'com.apple.cloudd' \
# 'com.apple.cloudpaird' \
# 'com.apple.cloudphotod' \
# 'com.apple.CloudSettingsSyncAgent' \
# 'com.apple.iCloudNotificationAgent' \
# 'com.apple.iCloudUserNotifications' \

# 'com.apple.homed' \
# 'com.apple.calaccessd' \

# launchctl dumpstate

# user
# launchctl print gui/501
TODISABLE=()

TODISABLE+=('com.apple.accessibility.MotionTrackingAgent' \
'com.apple.AMPArtworkAgent' \
'com.apple.AMPDeviceDiscoveryAgent' \
'com.apple.AMPLibraryAgent' \
'com.apple.ap.adprivacyd' \
'com.apple.ap.promotedcontentd' \
'com.apple.assistant_service' \
'com.apple.assistantd' \
'com.apple.avconferenced' \
'com.apple.BiomeAgent' \
'com.apple.biomesyncd' \
'com.apple.CallHistoryPluginHelper' \
'com.apple.CommCenter-osx' \
'com.apple.CoreLocationAgent' \
'com.apple.dataaccess.dataaccessd' \
'com.apple.ensemble' \
'com.apple.familycircled' \
'com.apple.familycontrols.useragent' \
'com.apple.familynotificationd' \
'com.apple.financed' \
'com.apple.followupd' \
'com.apple.gamed' \
'com.apple.geodMachServiceBridge' \
'com.apple.icloud.searchpartyuseragent' \
'com.apple.imagent' \
'com.apple.imautomatichistorydeletionagent' \
'com.apple.imtransferagent' \
'com.apple.intelligenceplatformd' \
'com.apple.itunescloudd' \
'com.apple.knowledge-agent' \
'com.apple.ManagedClientAgent.enrollagent' \
'com.apple.Maps.pushdaemon' \
'com.apple.networkserviceproxy' \
'com.apple.networkserviceproxy-osx' \
'com.apple.mediaanalysisd' \
'com.apple.mediastream.mstreamd' \
'com.apple.newsd' \
'com.apple.parsec-fbf' \
'com.apple.parsecd' \
'com.apple.passd' \
'com.apple.photoanalysisd' \
'com.apple.progressd' \
'com.apple.protectedcloudstorage.protectedcloudkeysyncing' \
'com.apple.quicklook' \
'com.apple.quicklook.ui.helper' \
'com.apple.quicklook.ThumbnailsAgent' \
'com.apple.rapportd-user' \
'com.apple.remindd' \
'com.apple.routined' \
'com.apple.screensharing.agent' \
'com.apple.screensharing.menuextra' \
'com.apple.screensharing.MessagesAgent' \
'com.apple.ScreenTimeAgent' \
'com.apple.security.cloudkeychainproxy3' \
'com.apple.sharingd' \
'com.apple.sidecar-hid-relay' \
'com.apple.sidecar-relay' \
'com.apple.Siri.agent' \
'com.apple.macos.studentd' \
'com.apple.siriknowledged' \
'com.apple.suggestd' \
'com.apple.tipsd' \
'com.apple.telephonyutilities.callservicesd' \
'com.apple.TMHelperAgent' \
'com.apple.triald' \
'com.apple.universalaccessd' \
'com.apple.UsageTrackingAgent' \
'com.apple.videosubscriptionsd' \
'com.apple.weatherd')

for agent in "${TODISABLE[@]}"
do
    echo "gui/501/${agent}"
	launchctl bootout "gui/501/${agent}"
	# launchctl disable "gui/501/${agent}"
done


# system
# launchctl print system
TODISABLE=()

TODISABLE+=('com.apple.analyticsd' \
'com.apple.backupd' \
'com.apple.backupd-helper' \
'com.apple.biomed' \
'com.apple.biometrickitd' \
'com.apple.corespotlightd' \
'com.apple.coreduetd' \
'com.apple.dhcp6d' \
'com.apple.familycontrols' \
'com.apple.findmymac' \
'com.apple.findmymacmessenger' \
'com.apple.ftp-proxy' \
'com.apple.GameController.gamecontrollerd' \
'com.apple.icloud.findmydeviced' \
'com.apple.icloud.searchpartyd' \
'com.apple.locationd' \
'com.apple.ManagedClient.cloudconfigurationd' \
'com.apple.netbiosd' \
'com.apple.rapportd' \
'com.apple.screensharing' \
'com.apple.siriinferenced' \
'com.apple.softwareupdated' \
'com.apple.triald.system' \
'com.apple.wifianalyticsd')

for daemon in "${TODISABLE[@]}"
do
    echo "system/${daemon}"
	sudo launchctl bootout "system/${daemon}"
	# sudo launchctl disable "system/${daemon}"
done

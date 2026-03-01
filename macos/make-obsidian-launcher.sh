#!/bin/dash

# 1. Compile the AppleScript launcher app into ~/Applications/Obsidian.app
# 2. Swap in Obsidian's real icon
# 3. Restart the Dock to refresh the icon cache

set -e

APP=~/Applications/Obsidian.app

mkdir -p ~/Applications

cat > /tmp/obsidian_launcher.applescript << 'APPLESCRIPT'
do shell script "open -a Obsidian --args --enable-gpu-rasterization --enable-zero-copy --ignore-gpu-blocklist --disable-field-trials --disable-background-timer-throttling --disable-renderer-backgrounding --disable-backgrounding-occluded-windows --disable-background-networking --disable-features=MediaRouter,AutofillServerCommunication,TranslateUI --disable-ipc-flooding-protection --no-pings --js-flags=--max-old-space-size=4096"
APPLESCRIPT

osacompile -o "$APP" /tmp/obsidian_launcher.applescript
rm /tmp/obsidian_launcher.applescript

# Replace the generic script icon with Obsidian's icon
cp /Applications/Obsidian.app/Contents/Resources/icon.icns \
   "$APP/Contents/Resources/applet.icns"

# Refresh icon cache
touch "$APP"
killall Dock

echo "Done. Obsidian launcher created at $APP"
echo "You can add it to your Dock or launch it from Spotlight."

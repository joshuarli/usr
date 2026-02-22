#!/bin/bash
# ============================================================================
# macos-lean-report.sh — System leanness report
# ============================================================================
#
# Shows Apple system process counts, memory usage, and top consumers
# to gauge how lean the system is (especially after a fresh boot).
#
# Usage:
#   ./macos-lean-report.sh
# ============================================================================

set -uo pipefail

UID_NUM=$(id -u)
UPTIME=$(uptime | sed 's/.*up //' | sed 's/,.*//')

# --- Sudo (required for system daemon stats) ---
sudo -v || { echo "Error: sudo required"; exit 1; }
while true; do sudo -n true; sleep 50; kill -0 "$$" || exit; done 2>/dev/null &
SUDO_PID=$!
trap 'kill $SUDO_PID 2>/dev/null' EXIT

# --- Memory via vm_stat ---
PAGE_SIZE=$(pagesize)

vm_page() {
  local label=$1
  local val
  val=$(vm_stat | grep "^${label}" | awk -F: '{print $2}' | tr -d '. ')
  echo "${val:-0}"
}

to_mb() { echo $(( ($1 * PAGE_SIZE) / 1048576 )); }

FREE=$(to_mb "$(vm_page 'Pages free')")
ACTIVE=$(to_mb "$(vm_page 'Pages active')")
INACTIVE=$(to_mb "$(vm_page 'Pages inactive')")
SPECULATIVE=$(to_mb "$(vm_page 'Pages speculative')")
WIRED=$(to_mb "$(vm_page 'Pages wired down')")
COMPRESSED=$(to_mb "$(vm_page 'Pages occupied by compressor')")
PURGEABLE=$(to_mb "$(vm_page 'Pages purgeable')")

PHYS_MB=$(( $(sysctl -n hw.memsize) / 1048576 ))
USED_MB=$(( ACTIVE + WIRED + COMPRESSED ))
SWAP_USED=$(sysctl -n vm.swapusage | grep -oE 'used = [0-9.]+M' | grep -oE '[0-9.]+' | head -1)
SWAP_USED=${SWAP_USED:-0}

# --- Apple system process count (exclude third-party, user, kernel) ---
APPLE_SYS=0
APPLE_APPS=0

while IFS= read -r comm; do
  case "$comm" in
    /System/Library/*|/usr/libexec/*|/usr/sbin/*|/usr/bin/*|/sbin/*|/bin/*)
      ((APPLE_SYS++)) ;;
    /Library/Apple/*)
      ((APPLE_SYS++)) ;;
    /Applications/System\ *|/System/Applications/*)
      ((APPLE_APPS++)) ;;
  esac
done < <(ps axo comm=)

APPLE_TOTAL=$(( APPLE_SYS + APPLE_APPS ))

# --- Loaded launch services ---
USER_AGENTS_LOADED=$(launchctl print gui/"$UID_NUM" 2>/dev/null | grep -cE '^\s+(0x|[0-9]+)\s' || true)
USER_AGENTS_LOADED=${USER_AGENTS_LOADED:-0}
USER_AGENTS_TOTAL=$(ls /System/Library/LaunchAgents/*.plist 2>/dev/null | wc -l | xargs)
SYS_DAEMONS_TOTAL=$(ls /System/Library/LaunchDaemons/*.plist 2>/dev/null | wc -l | xargs)
DISABLED_USER=$(launchctl print-disabled gui/"$UID_NUM" 2>/dev/null | grep -c '".*" => true' || true)
DISABLED_USER=${DISABLED_USER:-0}
SYS_DAEMONS_LOADED=$(sudo launchctl print system 2>/dev/null | grep -cE '^\s+(0x|[0-9]+)\s' || true)
SYS_DAEMONS_LOADED=${SYS_DAEMONS_LOADED:-0}
DISABLED_SYSTEM=$(sudo launchctl print-disabled system 2>/dev/null | grep -c '".*" => true' || true)
DISABLED_SYSTEM=${DISABLED_SYSTEM:-0}

# --- Running with PID (actually consuming resources) ---
AGENTS_WITH_PID=0
while read -r svc; do
  pid=$(launchctl print "gui/${UID_NUM}/${svc}" 2>/dev/null | grep 'pid = ' | awk '{print $3}')
  if [[ -n "$pid" && "$pid" != "0" ]]; then
    ((AGENTS_WITH_PID++))
  fi
done < <(launchctl print gui/"$UID_NUM" 2>/dev/null | grep -E '^\s+(0x|[0-9]+)\s' | awk '{print $NF}' | grep -v '^\s*$')

# ============================================================================
# Report
# ============================================================================

pct() { echo $(( ($1 * 100) / $2 )); }

echo "============================================"
echo "  macOS Lean Report"
echo "  $(sw_vers -productName) $(sw_vers -productVersion) ($(sw_vers -buildVersion))"
echo "  Uptime: ${UPTIME}"
echo "============================================"
echo ""

# --- Top Apple system processes by memory ---
echo "TOP 20 APPLE SYSTEM BY MEMORY"
printf "  %-8s %s\n" "MEM(MB)" "PROCESS"
ps axo rss=,comm= -m | while read -r rss comm; do
  case "$comm" in
    /System/Library/*|/usr/libexec/*|/Library/Apple/*|/System/Applications/*|/Applications/System\ *)
      mb=$(( rss / 1024 ))
      [[ $mb -gt 0 ]] && printf "  %-8s %s\n" "${mb}" "$(basename "$comm")"
      ;;
  esac
done | head -20
echo ""

# --- Top Apple system processes by CPU ---
echo "TOP 10 APPLE SYSTEM BY CPU (snapshot)"
printf "  %-6s %-8s %s\n" "%CPU" "MEM(MB)" "PROCESS"
ps axo %cpu=,rss=,comm= -r | while read -r cpu rss comm; do
  [[ "$cpu" == "0.0" ]] && continue
  case "$comm" in
    /System/Library/*|/usr/libexec/*|/Library/Apple/*|/System/Applications/*|/Applications/System\ *)
      mb=$(( rss / 1024 ))
      printf "  %-6s %-8s %s\n" "${cpu}%" "${mb}" "$(basename "$comm")"
      ;;
  esac
done | head -10
echo ""

# --- Summary ---
echo "MEMORY (${PHYS_MB} MB physical)"
echo "  Used:        ${USED_MB} MB ($(pct $USED_MB $PHYS_MB)%)"
echo "    Active:    ${ACTIVE} MB"
echo "    Wired:     ${WIRED} MB"
echo "    Compressed: ${COMPRESSED} MB"
echo "  Free:        ${FREE} MB"
echo "  Inactive:    ${INACTIVE} MB (reclaimable)"
echo "  Purgeable:   ${PURGEABLE} MB (reclaimable)"
echo "  Speculative: ${SPECULATIVE} MB"
echo "  Swap used:   ${SWAP_USED} MB"
echo ""

echo "APPLE PROCESSES (${APPLE_TOTAL} total)"
echo "  System:  ${APPLE_SYS}"
echo "  Apps:    ${APPLE_APPS}"
echo ""

echo "LAUNCH SERVICES"
echo "  User agents:    ${USER_AGENTS_LOADED} loaded / ${USER_AGENTS_TOTAL} available (${DISABLED_USER} disabled)"
echo "  System daemons: ${SYS_DAEMONS_LOADED} loaded / ${SYS_DAEMONS_TOTAL} available (${DISABLED_SYSTEM} disabled)"
echo "  Agents with PID: ${AGENTS_WITH_PID} (actually running)"
echo ""

echo "============================================"
echo "  Tip: Run after a fresh reboot for the"
echo "  most accurate leanness measurement."
echo "============================================"

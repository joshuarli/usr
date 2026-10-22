#!/bin/sh
# Tests for perf-gate-ready: the gate decides on load per core, and status mode reports load with memory, swap and disk.
# The Linux paths read a stand-in /proc.

script="${PWD}/base/.local/bin/perf-gate-ready"
nfailed=0

mkdir -p "${PWD}/../.work/tmp"
scratch=$(mktemp -d "${PWD}/../.work/tmp/perf-gate-ready.XXXXXX") || exit 1
trap 'rm -rf "$scratch"' 0

# proc <name> <MemAvailable kB> <SwapFree kB>: a 32 GiB host with 8 GiB of swap
proc () {
    mkdir -p "$scratch/$1"
    printf '3.21 2.00 1.00 1/100 1\n' > "$scratch/$1/loadavg"
    printf 'MemTotal:       33554432 kB\nMemAvailable:   %s kB\nSwapTotal:       8388608 kB\nSwapFree:        %s kB\n' "$2" "$3" > "$scratch/$1/meminfo"
}

# expect <wanted exit> <description> <proc dir name> <wanted text in output or ''> [VAR=value ...]
expect () {
    wanted=$1; what=$2; dir=$3; text=$4; shift 4
    out=$(env PERF_GATE_PROC="$scratch/$dir" "$@" sh "$script" -s "$scratch" 2>&1)
    got=$?
    case "$out" in *"$text"*) found=yes ;; *) found=no ;; esac
    if [ "$got" = "$wanted" ] && [ "$found" = yes ]; then
        printf 'ok: %s\n' "$what"
    else
        printf 'FAIL: %s (wanted exit %s with "%s", got exit %s: %s)\n' "$what" "$wanted" "$text" "$got" "$out"
        nfailed=$((nfailed + 1))
    fi
}

proc roomy 16777216 8388608
proc lowmem 1048576 8388608
proc swapping 16777216 1048576

expect 0 'plenty of memory and swap is roomy' roomy 'perf-gate-ready: ok' PERF_GATE_MIN_DISK_GIB=0
expect 0 'the line reports free memory in GiB' roomy 'mem_free=50% (16.0 of 32.0 GiB)' PERF_GATE_MIN_DISK_GIB=0
expect 0 'lanes follow free memory over the lane size' roomy 'lanes_by_memory=4' PERF_GATE_MIN_DISK_GIB=0 PERF_GATE_LANE_GIB=4
expect 0 'load is reported per core and never decides the verdict' roomy 'load=3.21' PERF_GATE_MIN_DISK_GIB=0
expect 75 'low free memory is constrained' lowmem 'memory 3% free' PERF_GATE_MIN_DISK_GIB=0
expect 75 'heavy swap use is constrained' swapping 'swap 88% used' PERF_GATE_MIN_DISK_GIB=0
expect 75 'low free disk is constrained' roomy 'disk' PERF_GATE_MIN_DISK_GIB=100000000
expect 0 'a lowered memory threshold accepts the same host' lowmem 'perf-gate-ready: ok' PERF_GATE_MIN_DISK_GIB=0 PERF_GATE_MIN_MEM_PCT=1

mkdir -p "$scratch/empty"
printf '0.5 0.5 0.5 1/1 1\n' > "$scratch/empty/loadavg"
expect 1 'a stand-in without meminfo is an error' empty 'no meminfo'

# gate <wanted exit> <description> <proc dir name> [VAR=value ...]: gate mode, one check
gate () {
    wanted=$1; what=$2; dir=$3; shift 3
    out=$(env PERF_GATE_PROC="$scratch/$dir" "$@" sh "$script" -1 2>&1)
    got=$?
    if [ "$got" = "$wanted" ]; then
        printf 'ok: %s\n' "$what"
    else
        printf 'FAIL: %s (wanted exit %s, got exit %s: %s)\n' "$what" "$wanted" "$got" "$out"
        nfailed=$((nfailed + 1))
    fi
}

gate 0 'a load under the per-core limit is quiet' roomy PERF_GATE_MAX_LOAD=100
gate 75 'a load over the per-core limit is busy' roomy PERF_GATE_MAX_LOAD=0.0001
gate 0 'memory pressure does not make the gate busy' lowmem PERF_GATE_MAX_LOAD=100

ps_bin="$scratch/ps-bin"
mkdir -p "$ps_bin"
cat > "$ps_bin/ps" <<'EOF'
#!/bin/sh
cat <<'PROCESS_LIST'
0 1 0 1 0.0 0.0 128 4000 2-00:00:00 Ss /sbin/launchd
501 40 1 40 0.0 0.0 512 8000 01:00:00 S /usr/bin/manager --mode worker
501 41 40 41 150.0 0.1 4096 16000 00:10:00 R /Applications/Virtualization.app/Contents/MacOS/com.apple.Virtualization --vm guest
501 42 41 42 2.0 0.1 1024 8000 00:01:00 S /usr/bin/child --serve
501 43 40 43 0.0 0.1 1024 8000 00:01:00 S /usr/bin/sibling
PROCESS_LIST
EOF
cat > "$ps_bin/launchctl" <<'EOF'
#!/bin/sh
cat <<'LAUNCHD_INFO'
resource coalition = {
	ID = 1
	name = application.example.vmhost
	bundle ID = com.example.vmhost
}
LAUNCHD_INFO
EOF
chmod +x "$ps_bin/ps"
chmod +x "$ps_bin/launchctl"
tree_out=$(env PERF_GATE_PROC="$scratch/roomy" PERF_GATE_MAX_LOAD=100 PATH="$ps_bin:$PATH" sh "$script" -1 2>&1)
tree_status=$?
tree_found=yes
for expected in \
    'perf-gate-ready: hot process tree (>= 100% CPU)' \
    'pid=1 ppid=0' \
    'pid=40 ppid=1' \
    'pid=41 ppid=40' \
    'pid=42 ppid=41' \
    'command=/Applications/Virtualization.app/Contents/MacOS/com.apple.Virtualization --vm guest' \
    'perf-gate-ready: app bundle attribution pid=41 bundle_id=com.example.vmhost'
do
    if ! printf '%s\n' "$tree_out" | grep -F "$expected" >/dev/null; then
        tree_found=no
    fi
done
if printf '%s\n' "$tree_out" | grep -F 'pid=43' >/dev/null; then sibling_found=yes; else sibling_found=no; fi
if [ "$tree_status" = 0 ] && [ "$tree_found" = yes ] && [ "$sibling_found" = no ]; then
    printf 'ok: a hot process reports its full tree and macOS owner attribution\n'
else
    printf 'FAIL: hot process tree (wanted exit 0 with ancestors, descendants, full command and owner attribution, without siblings; got exit %s: %s)\n' "$tree_status" "$tree_out"
    nfailed=$((nfailed + 1))
fi

echo "testing finished."
[ "$nfailed" -eq 0 ]

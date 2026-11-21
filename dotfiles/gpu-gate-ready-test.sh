#!/bin/sh
# Tests for gpu-gate-ready: GPU time from other Metal clients, device utilization, memory pressure,
# swap and compressor activity each make the gate contended; ignored pids and invalid settings.
# Stand-in ioreg, vm_stat, sysctl and uname read counters from files the test rewrites per sample.

root=$(CDPATH='' cd -P "$(dirname "$0")/.." && pwd -P)
script="$root/dotfiles/base/.local/bin/gpu-gate-ready"
nfailed=0

mkdir -p "$root/.work/tmp"
scratch=$(mktemp -d "$root/.work/tmp/gpu-gate-ready.XXXXXX") || exit 1
trap 'rm -rf "$scratch"' 0
bin="$scratch/bin"
mkdir -p "$bin"

# Each stub counts its calls; the second call of a check reads the "after" state.
cat > "$bin/ioreg" <<'STUB'
#!/bin/sh
case "$*" in
    *AGXDeviceUserClient*) n=$(cat "$GG/clients.n" 2>/dev/null || echo 0); n=$((n + 1)); echo $n > "$GG/clients.n"
        [ "$n" -ge 2 ] && cat "$GG/clients.after" || cat "$GG/clients.before" ;;
    *IOAccelerator*) printf '  "PerformanceStatistics" = {"Device Utilization %%"=%s,"Renderer Utilization %%"=0}\n' "$(cat "$GG/util")" ;;
esac
STUB
cat > "$bin/vm_stat" <<'STUB'
#!/bin/sh
n=$(cat "$GG/vm.n" 2>/dev/null || echo 0); n=$((n + 1)); echo $n > "$GG/vm.n"
if [ "$n" -ge 2 ]; then set -- $(cat "$GG/vm.after"); else set -- $(cat "$GG/vm.before"); fi
printf 'Mach Virtual Memory Statistics:\nDecompressions:  %s.\nCompressions:  %s.\nSwapins:  %s.\nSwapouts:  %s.\n' "$4" "$3" "$1" "$2"
STUB
# shellcheck disable=SC2016 # the stub expands $GG when it runs, not here
printf '#!/bin/sh\ncat "$GG/pressure"\n' > "$bin/sysctl"
printf '#!/bin/sh\necho Darwin\n' > "$bin/uname"
chmod +x "$bin"/*

client () { printf '    {\n      "AppUsage" = ({"API"="Metal","accumulatedGPUTime"=%s})\n      "IOUserClientCreator" = "pid %s, %s"\n    }\n' "$3" "$1" "$2"; }

# state <GPU ns before> <GPU ns after> <util %> <pressure> <vm before> <vm after>
state () {
    rm -f "$scratch/clients.n" "$scratch/vm.n"
    { client 100 WindowServer 5000000000; client 200 renderer "$1"; } > "$scratch/clients.before"
    { client 100 WindowServer 5000000000; client 200 renderer "$2"; } > "$scratch/clients.after"
    echo "$3" > "$scratch/util"; echo "$4" > "$scratch/pressure"
    echo "$5" > "$scratch/vm.before"; echo "$6" > "$scratch/vm.after"
}

# expect <wanted exit> <description> <wanted text or ''> [VAR=value ...]
expect () {
    wanted=$1; what=$2; text=$3; shift 3
    out=$(env PATH="$bin:/usr/bin:/bin" GG="$scratch" GPU_GATE_WAIT=0 "$@" sh "$script" -1 2>&1)
    got=$?
    case "$out" in *"$text"*) found=yes ;; *) found=no ;; esac
    if [ "$got" = "$wanted" ] && [ "$found" = yes ]; then
        printf 'ok: %s\n' "$what"
    else
        printf 'FAIL: %s (wanted exit %s with "%s", got exit %s: %s)\n' "$what" "$wanted" "$text" "$got" "$out"
        nfailed=$((nfailed + 1))
    fi
}

quiet_vm='10 10 1000 1000'
state 0 0 0 1 "$quiet_vm" "$quiet_vm"
expect 0 'an idle GPU with normal memory is quiet' ''
state 0 500000000 0 1 "$quiet_vm" "$quiet_vm"
expect 75 'another process using half the GPU window is contended' 'other processes used 50.0% GPU time'
state 0 500000000 0 1 "$quiet_vm" "$quiet_vm"
expect 75 'the GPU user is named' 'renderer pid=200 50.0%'
state 0 500000000 0 1 "$quiet_vm" "$quiet_vm"
expect 0 'an ignored pid does not count' '' GPU_GATE_IGNORE_PIDS=200
state 0 0 40 1 "$quiet_vm" "$quiet_vm"
expect 75 'high device utilization is contended' 'device utilization 40%'
state 0 0 40 1 "$quiet_vm" "$quiet_vm"
expect 0 'a post-run check with ignored pids is not decided by utilization' '' GPU_GATE_IGNORE_PIDS=300
state 0 0 0 2 "$quiet_vm" "$quiet_vm"
expect 75 'memory pressure warn is contended' 'memory pressure level 2'
state 0 0 0 1 "$quiet_vm" '300 10 1000 1000'
expect 75 'swap activity is contended' 'swapping 290 pages/s'
state 0 0 0 1 "$quiet_vm" '10 10 9000 1000'
expect 75 'heavy compressor activity is contended' 'compressor 8000 pages/s'
state 0 0 0 1 "$quiet_vm" "$quiet_vm"
expect 2 'a non-numeric setting is refused' 'GPU_GATE_MAX_GPU_PCT must be a nonnegative number' GPU_GATE_MAX_GPU_PCT=lots
expect 2 'a non-pid ignore list is refused' 'GPU_GATE_IGNORE_PIDS must be pids' GPU_GATE_IGNORE_PIDS=self

out=$(env PATH="$bin:/usr/bin:/bin" GG="$scratch" sh "$script" --help 2>&1)
case "$out" in *'usage: gpu-gate-ready'*Examples:*) printf 'ok: help\n' ;; *) printf 'FAIL: help (%s)\n' "$out"; nfailed=$((nfailed + 1)) ;; esac

state 0 500000000 0 1 "$quiet_vm" "$quiet_vm"
out=$(env PATH="$bin:/usr/bin:/bin" GG="$scratch" sh "$script" -s 2>&1)
case "$?:$out" in 0:*'gpu_other=50.0%'*'renderer pid=200'*) printf 'ok: status reports figures and users\n' ;; *) printf 'FAIL: status (%s)\n' "$out"; nfailed=$((nfailed + 1)) ;; esac

[ "$nfailed" = 0 ] || { printf '%s failed\n' "$nfailed"; exit 1; }
printf 'all passed\n'

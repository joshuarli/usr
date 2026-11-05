#!/bin/sh
# Exercising file-backed mock sysfs: no actual machine settings are changed.
set -eu
cd "$(dirname "$0")/.."
program=$PWD/dotfiles/linux/.local/bin/power-policy
work=$(mktemp -d)
trap 'rm -rf "$work"' 0
trap 'exit 1' 1 2 3 15
export POWER_POLICY_SYSFS_ROOT=$work/sys
sys=$POWER_POLICY_SYSFS_ROOT

fail() { printf 'power-policy test: %s\n' "$*" >&2; exit 1; }
expect() {
    value=$(cat "$1")
    [ "$value" = "$2" ] || fail "expected $1=$2, got $value"
}
reset() {
    rm -rf "$sys"
    mkdir -p "$sys/devices/system/cpu/cpufreq"
}
policy() {
    path=$sys/devices/system/cpu/cpufreq/policy0
    mkdir -p "$path"
    printf '%s\n' "$1" > "$path/scaling_driver"
    printf '%s\n' "$2" > "$path/scaling_governor"
    printf '%s\n' "$3" > "$path/scaling_available_governors"
}
epp() {
    printf '%s\n' "$1" > "$path/energy_performance_preference"
    printf '%s\n' "$2" > "$path/energy_performance_available_preferences"
}
ac_supply() {
    supply=$sys/class/power_supply/AC
    mkdir -p "$supply"
    printf 'Mains\n' > "$supply/type"
    printf '%s\n' "$1" > "$supply/online"
}
battery() {
    supply=$sys/class/power_supply/BAT0
    mkdir -p "$supply"
    printf 'Battery\n' > "$supply/type"
    printf '1\n' > "$supply/present"
    printf '%s\n' "$1" > "$supply/status"
}

# 1. Status read-only; no-CPU no-op is visibly unsupported.
reset
"$program" status > "$work/out"
grep -qx 'source=ac' "$work/out" || fail 'AC-only default'
grep -qx 'cpufreq=unavailable' "$work/out" || fail 'empty status'
if "$program" ac > /dev/null 2>&1; then fail 'no-controls apply succeeded'; fi

# 2. Intel N100 with active intel_pstate/HWP: EPP and turbo, no fixed CPU cap.
reset
policy intel_pstate performance 'performance powersave'
epp performance 'performance balance_performance balance_power power'
mkdir -p "$sys/devices/system/cpu/intel_pstate"
printf '1\n' > "$sys/devices/system/cpu/intel_pstate/no_turbo"
"$program" diff ac > "$work/out"
expect "$path/scaling_governor" performance
expect "$path/energy_performance_preference" performance
grep -q 'scaling_governor: performance -> powersave' "$work/out" || fail 'missing Intel governor diff'
"$program" apply ac > /dev/null
expect "$path/scaling_governor" powersave
expect "$path/energy_performance_preference" balance_performance
expect "$sys/devices/system/cpu/intel_pstate/no_turbo" 1
"$program" diff ac > "$work/out"
[ "$(wc -l < "$work/out")" -eq 1 ] || fail 'not idempotent'

# 3. AC change for an N100 laptop; explicit performance reenables turbo.
ac_supply 0
battery Discharging
"$program" auto > /dev/null
expect "$path/energy_performance_preference" balance_power
"$program" status > "$work/out"
grep -qx 'source=battery' "$work/out" || fail 'source detection'
ac_supply 1
"$program" auto > /dev/null
expect "$path/energy_performance_preference" balance_performance
"$program" performance > /dev/null
expect "$path/energy_performance_preference" performance
expect "$path/scaling_governor" powersave
expect "$sys/devices/system/cpu/intel_pstate/no_turbo" 0

# 4. Intel N100 running passive intel_cpufreq: use scheduler governor.
reset
policy intel_cpufreq powersave 'powersave performance schedutil ondemand'
"$program" battery > /dev/null
expect "$path/scaling_governor" schedutil
"$program" performance > /dev/null
expect "$path/scaling_governor" performance
"$program" ac > /dev/null
expect "$path/scaling_governor" schedutil

# 5. Ryzen 2400GE (no CPPC/amd-pstate): acpi-cpufreq never pins to min.
reset
policy acpi-cpufreq powersave 'performance powersave schedutil ondemand'
printf '0\n' > "$sys/devices/system/cpu/cpufreq/boost"
"$program" battery > /dev/null
expect "$path/scaling_governor" schedutil
expect "$sys/devices/system/cpu/cpufreq/boost" 0
"$program" performance > /dev/null
expect "$path/scaling_governor" performance
expect "$sys/devices/system/cpu/cpufreq/boost" 1
"$program" ac > /dev/null
expect "$path/scaling_governor" schedutil

# 6. Legacy CPUFreq fallback: ondemand if schedutil unavailable.
reset
policy acpi-cpufreq powersave 'performance powersave ondemand'
"$program" battery > /dev/null
expect "$path/scaling_governor" ondemand

# 7. Peripheral battery must not count as the system battery.
reset
policy intel_pstate powersave 'performance powersave'
epp balance_power 'performance balance_performance balance_power'
mkdir -p "$sys/class/power_supply/mouse"
printf 'Battery\n' > "$sys/class/power_supply/mouse/type"
printf 'Device\n' > "$sys/class/power_supply/mouse/scope"
printf 'Discharging\n' > "$sys/class/power_supply/mouse/status"
"$program" auto > /dev/null
expect "$path/energy_performance_preference" balance_performance

# 8. AMD active EPP: kernel-managed dynamic AUTO and explicit performance.
reset
policy amd-pstate-epp performance 'performance powersave'
epp balance_performance 'performance balance_performance balance_power power dynamic'
printf '0\n' > "$sys/devices/system/cpu/cpufreq/boost"
"$program" auto > /dev/null
expect "$path/scaling_governor" powersave
expect "$path/energy_performance_preference" dynamic
"$program" performance > /dev/null
expect "$path/energy_performance_preference" performance
expect "$sys/devices/system/cpu/cpufreq/boost" 1

# 9. Multi-policy Threadripper EPP: both tune, all are idempotent.
policy2=$sys/devices/system/cpu/cpufreq/policy2
mkdir -p "$policy2"
printf 'amd-pstate-epp\n' > "$policy2/scaling_driver"
printf 'powersave\n' > "$policy2/scaling_governor"
printf 'performance powersave\n' > "$policy2/scaling_available_governors"
printf 'balance_power\n' > "$policy2/energy_performance_preference"
printf 'performance balance_performance balance_power\n' > "$policy2/energy_performance_available_preferences"
"$program" performance > /dev/null
expect "$path/energy_performance_preference" performance
expect "$policy2/energy_performance_preference" performance
"$program" diff performance > "$work/out"
[ "$(wc -l < "$work/out")" -eq 1 ] || fail 'multi policy not idempotent'

# 10. Legacy Intel without EPP: EPB 0/6/12 and intel_pstate governors.
reset
policy intel_pstate performance 'performance powersave'
cpu=$sys/devices/system/cpu/cpu0
mkdir -p "$cpu/power"
printf '0\n' > "$cpu/power/energy_perf_bias"
"$program" battery > /dev/null
expect "$path/scaling_governor" powersave
expect "$cpu/power/energy_perf_bias" 12
"$program" ac > /dev/null
expect "$cpu/power/energy_perf_bias" 6
"$program" performance > /dev/null
expect "$path/scaling_governor" performance
expect "$cpu/power/energy_perf_bias" 0

# 11. Unknown drivers and generic governors without safe options untouched.
reset
policy foocpufreq powersave 'performance powersave schedutil'
if "$program" battery > /dev/null 2>&1; then fail 'unknown driver changed'; fi
expect "$path/scaling_governor" powersave
policy acpi-cpufreq powersave 'performance powersave'
if "$program" battery > /dev/null 2>&1; then fail 'pinned min generic CPU'; fi
expect "$path/scaling_governor" powersave

# 12. Older AMD dynamic EPP is already kernel-managed, never fight it.
reset
policy amd-pstate-epp powersave 'performance powersave'
epp balance_power 'performance balance_performance balance_power'
mkdir -p "$sys/devices/system/cpu/amd_pstate"
printf 'enabled\n' > "$sys/devices/system/cpu/amd_pstate/dynamic_epp"
"$program" auto > /dev/null
expect "$path/energy_performance_preference" balance_power
if "$program" performance > "$work/out" 2>&1; then fail 'overrode dynamic EPP'; fi
grep -q 'dynamic_epp owns EPP' "$work/out" || fail 'missing old AMD dynamic EPP warning'

# 13. Commands and test-root validation.
if "$program" nonsense > /dev/null 2>&1; then fail 'unknown command'; fi
if "$program" apply battery extra > /dev/null 2>&1; then fail 'extra arguments'; fi
if POWER_POLICY_SYSFS_ROOT=/ "$program" status > /dev/null 2>&1; then fail 'accepted / root'; fi
if POWER_POLICY_SYSFS_ROOT=relative "$program" status > /dev/null 2>&1; then fail 'relative root'; fi

printf 'power-policy: 13 test groups passed\n'

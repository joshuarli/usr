#!/bin/sh
# Fixtures for tsc-opts.sh: GRUB and extlinux option lines that need, already keep
# or conflict with tsc=nowatchdog, and the rewrite that adds it.
set -eu
cd "$(dirname "$0")/.."
helper=$PWD/tsc-opts.sh
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT HUP INT TERM
fail=0
grub=GRUB_CMDLINE_LINUX_DEFAULT
ext=default_kernel_opts

check() { # NAME EXPECTED KEY CONTENT
	printf '%s\n' "$4" > "$tmp/conf"
	if sh "$helper" check "$tmp/conf" "$3" >/dev/null 2>&1; then rc=0; else rc=$?; fi
	if [ "$rc" -eq "$2" ]; then
		printf 'ok: %s\n' "$1"
	else
		printf 'FAIL: %s (expected exit %s, got %s)\n' "$1" "$2" "$rc" >&2
		fail=1
	fi
}

apply() { # NAME KEY CONTENT EXPECTED
	printf '%s\n' "$3" > "$tmp/conf"
	got=$(sh "$helper" apply "$tmp/conf" "$2")
	if [ "$got" = "$4" ]; then
		printf '%s\n' "$got" > "$tmp/applied"
		if sh "$helper" check "$tmp/applied" "$2" >/dev/null 2>&1; then
			printf 'ok: %s\n' "$1"
			return
		fi
		printf 'FAIL: %s (rewrite does not pass check)\n' "$1" >&2
	else
		printf 'FAIL: %s\n  expected: %s\n  got:      %s\n' "$1" "$4" "$got" >&2
	fi
	fail=1
}

lisa='GRUB_TIMEOUT=2
GRUB_CMDLINE_LINUX_DEFAULT="modules=sd-mod,usb-storage,ext4,nvme quiet rootfstype=ext4"
GRUB_DISABLE_RECOVERY=true'

check 'grub line without tsc needs it' 1 "$grub" "$lisa"
check 'extlinux line without tsc needs it' 1 "$ext" 'default_kernel_opts="quiet rootfstype=ext4"'
check 'empty options need it' 1 "$ext" 'default_kernel_opts=""'
check 'tsc=nowatchdog keeps TSC' 0 "$grub" 'GRUB_CMDLINE_LINUX_DEFAULT="quiet tsc=nowatchdog"'
check 'tsc=reliable keeps TSC' 0 "$grub" 'GRUB_CMDLINE_LINUX_DEFAULT="tsc=reliable quiet"'
check 'combined tsc flags keep TSC' 0 "$grub" 'GRUB_CMDLINE_LINUX_DEFAULT="tsc=nowatchdog,recalibrate"'
check 'clocksource=tsc with nowatchdog keeps TSC' 0 "$grub" 'GRUB_CMDLINE_LINUX_DEFAULT="clocksource=tsc tsc=nowatchdog"'
check 'commented line is not the setting' 2 "$grub" '#GRUB_CMDLINE_LINUX_DEFAULT="quiet"'
check 'similar key is not the setting' 2 "$grub" 'GRUB_CMDLINE_LINUX="quiet"'
check 'missing key is refused' 2 "$grub" 'GRUB_TIMEOUT=2'
check 'repeated key is refused' 2 "$grub" 'GRUB_CMDLINE_LINUX_DEFAULT="quiet"
GRUB_CMDLINE_LINUX_DEFAULT="splash"'
check 'single-quoted value is refused' 2 "$grub" "GRUB_CMDLINE_LINUX_DEFAULT='quiet'"
check 'other tsc flag is refused' 2 "$grub" 'GRUB_CMDLINE_LINUX_DEFAULT="tsc=unstable"'
check 'other clocksource is refused' 2 "$grub" 'GRUB_CMDLINE_LINUX_DEFAULT="clocksource=hpet"'
check 'notsc is refused' 2 "$grub" 'GRUB_CMDLINE_LINUX_DEFAULT="notsc"'

apply 'grub options gain tsc=nowatchdog, other lines kept' "$grub" "$lisa" 'GRUB_TIMEOUT=2
GRUB_CMDLINE_LINUX_DEFAULT="modules=sd-mod,usb-storage,ext4,nvme quiet rootfstype=ext4 tsc=nowatchdog"
GRUB_DISABLE_RECOVERY=true'
apply 'empty options become tsc=nowatchdog' "$ext" 'default_kernel_opts=""' 'default_kernel_opts="tsc=nowatchdog"'
apply 'kept options are printed unchanged' "$grub" 'GRUB_CMDLINE_LINUX_DEFAULT="quiet tsc=reliable"' 'GRUB_CMDLINE_LINUX_DEFAULT="quiet tsc=reliable"'

exit "$fail"

#!/bin/sh
# Keep the kernel on the TSC clocksource through one KEY="..." option line in a
# bootloader defaults file (GRUB_CMDLINE_LINUX_DEFAULT in /etc/default/grub or
# default_kernel_opts in /etc/update-extlinux.conf).
#   check FILE KEY  exit 0 when the options already keep TSC (tsc=nowatchdog or
#                   tsc=reliable), 1 when tsc=nowatchdog must be added, 2 when the
#                   line is missing, repeated, not double-quoted or selects another clock.
#   apply FILE KEY  print FILE with tsc=nowatchdog appended to the KEY options.
set -eu
[ $# -eq 3 ] || { echo 'usage: tsc-opts.sh check|apply FILE KEY' >&2; exit 2; }
case $1 in check | apply) ;; *) echo 'usage: tsc-opts.sh check|apply FILE KEY' >&2; exit 2 ;; esac
[ -r "$2" ] || { echo "tsc-opts: cannot read $2" >&2; exit 2; }

awk -v op="$1" -v key="$3" -v file="$2" '
	function bad(msg) { print "tsc-opts: " file ": " msg > "/dev/stderr"; exit 2 }
	{ lines[NR] = $0 }
	index($0, key "=") == 1 {
		count++
		at = NR
		value = substr($0, length(key) + 2)
	}
	END {
		if (count == 0) bad(key " is not set")
		if (count > 1) bad(key " is set more than once")
		if (value !~ /^"[^"]*"$/) bad(key " must be a double-quoted string")
		opts = substr(value, 2, length(value) - 2)
		n = split(opts, words, /[ \t]+/)
		keeps = 0
		for (i = 1; i <= n; i++) {
			w = words[i]
			if (w == "notsc") bad("notsc disables the TSC")
			if (w ~ /^clocksource=/ && w != "clocksource=tsc") bad(w " selects another clocksource")
			if (w ~ /^tsc=/) {
				m = split(substr(w, 5), flags, ",")
				for (j = 1; j <= m; j++) if (flags[j] == "nowatchdog" || flags[j] == "reliable") keeps = 1
				if (!keeps) bad(w " is set without nowatchdog or reliable; merge nowatchdog into it")
			}
		}
		if (op == "check") exit keeps ? 0 : 1
		if (!keeps) lines[at] = key "=\"" (opts ~ /^[ \t]*$/ ? "" : opts " ") "tsc=nowatchdog\""
		for (i = 1; i <= NR; i++) print lines[i]
	}
' "$2"

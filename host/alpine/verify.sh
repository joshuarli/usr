#!/bin/sh
set -u
cd "$(dirname "$0")" || exit 1
usr_root=$(cd ../.. && pwd)

mode=${1:-$(cat /etc/home/install-mode 2>/dev/null || printf desktop)}
case $mode in server | desktop) ;; *) echo "usage: $0 [server|desktop]" >&2; exit 2 ;; esac

failures=0
fail() { printf 'FAIL: %s\n' "$*"; failures=$((failures + 1)); }
pass() { printf 'ok: %s\n' "$*"; }
check() { label=$1; shift; if "$@" >/dev/null 2>&1; then pass "$label"; else fail "$label"; fi; }

in_runlevel() { rc-update show "$2" | awk -v s="$1" '$1 == s { found = 1 } END { exit !found }'; }
managed() { cmp -s "$1" "$2" && [ "$(stat -c %u:%g:%a "$2")" = "0:0:$3" ]; }
no_match() { ! grep -Eqs "$@"; }
no_extra_nopass() {
	cat /etc/doas.conf /etc/doas.d/*.conf 2>/dev/null |
		awk -v user="$user" '
			{ sub(/#.*/, "") }
			/nopass/ &&
				$0 != "permit nopass " user " as root" &&
				index($0, "tailscale as root cmd /usr/sbin/resolvconf") == 0 { found = 1 }
			END { exit found }
		'
}
install_profile_matches() {
	[ "$(cat /etc/home/install-mode 2>/dev/null)" = "$mode" ]
}
github_key_matches_user() {
	[ "$(stat -c %u:%g:%a "$home/.ssh" 2>/dev/null)" = "$uid:$gid:700" ] || return 1
	[ "$(stat -c %u:%g:%a "$github_key" 2>/dev/null)" = "$uid:$gid:600" ] || return 1
	[ "$(stat -c %u:%g:%a "$github_pub" 2>/dev/null)" = "$uid:$gid:644" ] || return 1
	ssh-keygen -y -P '' -f "$github_key" 2>/dev/null | cmp -s - "$github_pub" || return 1
	ssh-keygen -lf "$github_pub" 2>/dev/null | grep -q '(ED25519)$'
}
doas_policy_matches_user() {
	[ "$(stat -c %u:%g:%a /etc/doas.d/30-home-nopass.conf 2>/dev/null)" = '0:0:644' ] || return 1
	cmp -s /etc/doas.d/30-home-nopass.conf - <<EOF
permit nopass $user as root
EOF
}
major_at_least() { [ "$("$2" --version 2>/dev/null | grep -Eo '[0-9]+\.[0-9]+\.[0-9]+' | head -n 1 | cut -d. -f1)" -ge "$1" ] 2>/dev/null; }

[ "$(id -u)" -eq 0 ] || { echo 'verify: run as root' >&2; exit 1; }
user=${USER_NAME:-josh}
uid=$(id -u "$user") || { echo "verify: no user $user" >&2; exit 1; }
gid=$(id -g "$user") || { echo "verify: no group for $user" >&2; exit 1; }
home=$(getent passwd "$user" | cut -d: -f6)
github_key=$home/.ssh/github
github_pub=$github_key.pub

check 'curl installed' command -v curl
check 'bash installed' command -v bash
check 'jq installed' command -v jq
check 'unzip installed' command -v unzip
check 'zipinfo installed' command -v zipinfo
check 'ssh installed' command -v ssh
check 'uv installed' command -v uv
for tool in clang ld.lld llc; do check "$tool is version 23 or newer" major_at_least 23 "$tool"; done
clang_dir=/etc/clang$(clang -dumpversion | cut -d. -f1)
check 'clang defaults match config/clang.cfg, root 0644' managed config/clang.cfg "$clang_dir/clang.cfg" 644
check 'clang++ defaults match config/clang.cfg, root 0644' managed config/clang.cfg "$clang_dir/clang++.cfg" 644
# shellcheck disable=SC2016
check 'clang builds and runs C with lld and compiler-rt' sh -c 't=$(mktemp) && printf "int main(void){return 0;}\n" | clang -x c - -o "$t" && "$t"; s=$?; rm -f "$t"; exit $s'
# shellcheck disable=SC2016
check 'clang++ builds and runs C++' sh -c 't=$(mktemp) && printf "#include <cstdio>\nint main(){std::puts(\"\");}\n" | clang++ -x c++ - -o "$t" && "$t" >/dev/null; s=$?; rm -f "$t"; exit $s'
check "$user has a password" sh -c "awk -F: '\$1 == \"$user\" { exit !(\$2 ~ /^\\$/) }' /etc/shadow"
check 'no getty autologin' no_match -- '--autologin|[[:space:]]-a[[:space:]]' /etc/inittab
check 'passwordless doas policy matches provisioned user' doas_policy_matches_user
check 'no other passwordless doas rules' no_extra_nopass
check 'passwordless doas works for user' su -s /bin/sh "$user" -c 'doas -n true'
check 'unencrypted Ed25519 GitHub key matches user and modes' github_key_matches_user
check "install profile is $mode" install_profile_matches
default_tools=$(DL_PROFILE="$mode" sh "$usr_root/dl" --list) || fail 'cannot read the default dl tool list'
for tool in $default_tools; do
	[ "$tool" = agy ] && continue
	case $tool in nodejs) launchers=node ;; ffmpeg) launchers='ffmpeg ffprobe' ;; *) launchers=$tool ;; esac
	for launcher in $launchers; do
		check "$launcher installed for $user" test -x "$home/.local/bin/$launcher"
	done
done
case " $default_tools " in
	*" ffmpeg "*)
		for launcher in ffmpeg ffprobe; do
			check "$launcher reports version" su -s /bin/sh "$user" -c "$home/.local/bin/$launcher -version"
		done
		;;
esac
case " $default_tools " in
	*" nodejs "*)
		check 'node runs' su -s /bin/sh "$user" -c "$home/.local/bin/node --version"
		check 'npm runs' su -s /bin/sh "$user" -c "PATH='$home/.local/bin':\$PATH '$home/.local/bin/npm' --version"
		;;
esac
check 'python3 imports sqlite3 and ssl' su -s /bin/sh "$user" -c "$home/.local/bin/python3 -c 'import sqlite3, ssl'"
check 'sudo not installed' sh -c '! apk info -e sudo'
check "usr dotfiles linked" sh -c "su -s /bin/sh '$user' -c \"cd ~ && sh '$usr_root/sync' plan\" | awk '/^(LINK|CONFLICT|PRUNE)/ { found = 1 } END { exit found }'"
check 'tailscale installed' command -v tailscale
check 'tailscale enabled' in_runlevel tailscale default
check 'tailscale started' rc-service tailscale status
check 'tun loads at boot' grep -qx tun /etc/modules
check 'kernel modules service enabled at boot' in_runlevel modules boot
check 'tun device available' test -c /dev/net/tun
state=$(tailscale status --json 2>/dev/null | jq -r '.BackendState // "Unknown"')
# shellcheck disable=SC2016
case $state in
	Running)
		check 'tailscale node is online' sh -c 'tailscale status --json | jq -e ".Self.Online == true" >/dev/null'
		check 'tailscale SSH enabled' sh -c '[ "$(tailscale get ssh)" = true ]'
		;;
	NeedsLogin) printf 'note: tailscale is logged out; run: doas tailscale up --ssh\n' ;;
	*) fail "tailscaled is in state $state" ;;
esac
check 'Docker CLI installed' command -v docker
check 'Docker engine installed' command -v dockerd
check 'Docker enabled' in_runlevel docker default
check 'Docker started' rc-service docker status
check "$user in docker group" sh -c "id -Gn '$user' | tr ' ' '\\n' | grep -qx docker"
check 'Docker CLI connects to engine as user' su -s /bin/sh "$user" -c 'docker info --format "{{.ServerVersion}}"'
check 'interactive login hook matches config/profile.sh, root 0644' managed config/profile.sh /etc/profile.d/home-session.sh 644

if [ "$mode" = desktop ]; then
	check 'volume helper matches config/volume, root 0755' managed config/volume /usr/local/bin/volume 755
	check 'amixer installed' command -v amixer
	check 'home-session matches config/home-session, root 0755' managed config/home-session /usr/local/bin/home-session 755
	check 'home-runtime service matches services/home-runtime, root 0755' managed services/home-runtime /etc/init.d/home-runtime 755
	check "home-runtime configured for $user" grep -qx "home_user=\"$user\"" /etc/conf.d/home-runtime
	check 'dwl build matches build/dwl.sh, config/dwl.h, and config/dwl-relative-tags.patch' test "$(/usr/local/bin/dwl -v 2>&1)" = "$(sh build/dwl.sh --version)"
	check 'dwl shared libraries resolve' sh -c '! ldd /usr/local/bin/dwl 2>&1 | grep -q "not found"'
	check 'dwl build dependencies removed' sh -c '! apk info -e .home-dwl-build'
	check 'ghostty-custom release tracked' sh -c 'grep -qx "release-[0-9a-f][0-9a-f]*" /usr/local/share/home/ghostty-custom.tag'
	# shellcheck disable=SC2016
	check 'ghostty-custom installed, root 0755' sh -c '[ -f /usr/local/bin/ghostty-custom ] && [ ! -L /usr/local/bin/ghostty-custom ] && [ -x /usr/local/bin/ghostty-custom ] && [ "$(stat -c %u:%g:%a /usr/local/bin/ghostty-custom)" = 0:0:755 ]'
	check 'ghostty-custom shared libraries resolve' sh -c '! ldd /usr/local/bin/ghostty-custom 2>&1 | grep -q "not found"'
	check 'ghostty-custom reports version' sh -c '/usr/local/bin/ghostty-custom --version >/dev/null'
	check 'ghostty-custom shows config' sh -c '/usr/local/bin/ghostty-custom +show-config >/dev/null'
	check 'ghostty terminfo installed' test -f /usr/share/terminfo/x/xterm-ghostty
	check 'ghostty build dependencies removed' sh -c '! apk info -e .home-ghostty-build'
	if [ "$(apk --print-arch)" = x86_64 ]; then
		check 'helium tag recorded' grep -Eqx 'helium-[0-9].*' /usr/local/share/home/helium.tag
		check 'helium launcher installed' test -x /usr/local/bin/helium
		# shellcheck disable=SC2016
		check 'helium launcher points at the current release' sh -c '[ -L /usr/local/bin/helium ] && [ "$(readlink /usr/local/bin/helium)" = /usr/local/lib/helium/current/helium-wrapper ]'
		check 'helium shared libraries resolve' sh -c '! LD_LIBRARY_PATH=/usr/local/lib/helium/current/lib ldd /usr/local/lib/helium/current/helium 2>&1 | grep -q "not found"'
		check 'helium reports version' su -s /bin/sh "$user" -c '/usr/local/bin/helium --version'
		check 'VA-API Intel driver installed' test -f /usr/lib/dri/i965_drv_video.so
		if [ -e /dev/dri/renderD128 ]; then
			check 'VA-API H.264 decode available to user' su -s /bin/sh "$user" -c 'vainfo 2>/dev/null | grep -q VAProfileH264'
		fi
	fi
	check 'foot not installed' sh -c '! apk info -e foot && ! apk info -e foot-extra-terminfo'
	for cmd in ghostty-custom bemenu-run grim slurp wl-copy; do check "$cmd installed" command -v "$cmd"; done
	check 'Hack font installed' sh -c 'fc-list | grep -q Hack'
	check 'player shared libraries resolve' sh -c "! ldd '$home/.local/bin/player' 2>&1 | grep -q 'not found'"
	check 'player reports version' su -s /bin/sh "$user" -c "$home/.local/bin/player --version"
	check 'Vulkan ICD installed' sh -c 'ls /usr/share/vulkan/icd.d/*.json >/dev/null 2>&1'
	check 'linux-lts not installed' sh -c '! apk info -e linux-lts'
	check 'running linux-stable' sh -c 'uname -r | grep -q -- -stable$'

	check 'udev manages devices' in_runlevel udev sysinit
	check 'mdev disabled' sh -c '! rc-update show sysinit | grep -qw mdev'
	for service in seatd home-runtime; do
		check "$service enabled" in_runlevel "$service" default
		check "$service started" rc-service "$service" status
	done
	check "$user in seat" sh -c "id -Gn '$user' | tr ' ' '\n' | grep -qx seat"
	check "/run/user/$uid private to $user" test "$(stat -c %U:%a "/run/user/$uid" 2>/dev/null)" = "$user:700"
fi

if [ "$failures" -ne 0 ]; then
	echo "verify: $failures check(s) failed"
	exit 1
fi
if [ "$mode" = desktop ]; then
	echo 'verify: all checks passed (graphical session and hardware not exercised)'
else
	echo 'verify: all server checks passed'
fi

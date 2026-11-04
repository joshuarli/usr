#!/bin/sh
set -eu
cd "$(dirname "$0")"

usr_root=$(cd ../.. && pwd)
usr_url=https://github.com/joshuarli/usr
doas_policy=/etc/doas.d/30-home-nopass.conf
conf=
doas_tmp=

die() { printf 'home: %s\n' "$*" >&2; exit 1; }
say() { printf 'home: %s\n' "$*"; }

cleanup() {
	[ -z "$conf" ] || rm -f "$conf" || say "could not remove temporary file $conf"
	[ -z "$doas_tmp" ] || rm -f "$doas_tmp" || say "could not remove temporary file $doas_tmp"
}

trap cleanup EXIT
trap 'exit 1' HUP INT TERM

as_user() { su -s /bin/sh "$user" -c "cd ~ && $1"; }

matches_committed() {
	git -c safe.directory="$PWD" -c safe.directory="$usr_root" log --follow --format=%H --name-only -- "$1" | awk NF |
		while read -r rev && read -r path; do
			git -c safe.directory="$PWD" -c safe.directory="$usr_root" show "$rev:$path" 2>/dev/null | cmp -s - "$2" && exit 0
		done
}

check_managed() {
	[ -e "$2" ] || return 0
	[ -f "$2" ] && [ ! -L "$2" ] || die "$2 exists and is not a regular file; move it aside"
	cmp -s "$1" "$2" || matches_committed "$1" "$2" ||
		die "$2 exists and was not installed by home; move it aside or merge it into $1"
}

install_managed() {
	if cmp -s "$1" "$2" 2>/dev/null; then
		[ "$(stat -c %u:%g:%a "$2")" = "0:0:${3#0}" ] || { chown root:root "$2"; chmod "$3" "$2"; }
	else
		install -o root -g root -m "$3" "$1" "$2"
		say "installed $2"
	fi
}

clang_major() { clang -dumpversion | cut -d. -f1; }

check_doas_policy() {
	[ -d /etc/doas.d ] && [ ! -L /etc/doas.d ] || die '/etc/doas.d is missing or is not a regular directory; run setup-user -a'
	[ -e "$doas_policy" ] || [ -L "$doas_policy" ] || return 0
	[ -f "$doas_policy" ] && [ ! -L "$doas_policy" ] || die "$doas_policy exists and is not a regular file; move it aside"
	if ! cmp -s "$doas_policy" - <<EOF
permit nopass $user as root
EOF
	then
		die "$doas_policy contains a different rule; move it aside or update it for $user"
	fi
}

install_doas_policy() {
	if [ -e "$doas_policy" ]; then
		[ "$(stat -c %u:%g:%a "$doas_policy")" = '0:0:644' ] || {
			chown root:root "$doas_policy"
			chmod 0644 "$doas_policy"
		}
		return
	fi
	doas_tmp=$(mktemp /etc/doas.d/.home-nopass.XXXXXX)
	printf 'permit nopass %s as root\n' "$user" >"$doas_tmp"
	chown root:root "$doas_tmp"
	chmod 0644 "$doas_tmp"
	if ! ln "$doas_tmp" "$doas_policy" 2>/dev/null; then
		check_doas_policy
		[ -e "$doas_policy" ] || die "could not install $doas_policy"
	fi
	rm -f "$doas_tmp"
	doas_tmp=
	say "enabled passwordless doas for $user"
}

setup_tailscale() {
	grep -qx tun /etc/modules 2>/dev/null || printf 'tun\n' >>/etc/modules
	rc-update show boot | awk '$1 == "modules" { found = 1 } END { exit !found }' || rc-update add modules boot

	rc-update show default | awk '$1 == "tailscale" { found = 1 } END { exit !found }' || rc-update add tailscale default
	if [ ! -c /dev/net/tun ]; then
		modprobe tun || die 'could not load tun for the running kernel; reboot after a kernel upgrade, otherwise check kernel support and device access'
	fi
	[ -c /dev/net/tun ] || die 'the tun module did not create /dev/net/tun; check kernel support and device access'

	rc-service --ifstopped tailscale start

	i=0
	while [ ! -S /run/tailscale/tailscaled.sock ] && [ "$i" -lt 20 ]; do
		sleep 1
		i=$((i + 1))
	done
	[ -S /run/tailscale/tailscaled.sock ] ||
		die 'tailscaled did not create /run/tailscale/tailscaled.sock; see /var/log/tailscaled.log'

	i=0
	while :; do
		state=$(tailscale status --json 2>/dev/null | jq -r '.BackendState // empty')
		case $state in Running | NeedsLogin) break ;; esac
		[ "$i" -lt 20 ] || die "tailscaled is in state ${state:-unknown}; see /var/log/tailscaled.log"
		sleep 1
		i=$((i + 1))
	done

	case $state in
		Running)
			tailscale set --ssh >/dev/null || die 'could not enable Tailscale SSH'
			;;
		NeedsLogin)
			if [ -n "${TS_AUTHKEY:-}" ]; then
				tailscale up --ssh --auth-key="$TS_AUTHKEY" --timeout=60s >/dev/null ||
					die 'tailscale up failed; check TS_AUTHKEY and the tailnet policy'
			elif [ -t 2 ]; then
				printf 'home: logging in to Tailscale; open the URL below\n' >&2
				if tailscale up --ssh --timeout=120s; then
					printf 'home: logged in to Tailscale with SSH enabled\n' >&2
				else
					printf 'home: tailscale login did not finish; run: doas tailscale up --ssh\n' >&2
				fi
			else
				say 'tailscale is logged out; run: doas tailscale up --ssh'
			fi
			;;
	esac
}

setup_docker() {
	getent group docker >/dev/null 2>&1 || addgroup -S docker
	id -Gn "$user" | tr ' ' '\n' | grep -qx docker || {
		addgroup "$user" docker
		say "added $user to docker (root-equivalent access); log out and back in to use Docker"
	}
	rc-update show default | awk '$1 == "docker" { found = 1 } END { exit !found }' || rc-update add docker default
	rc-service --ifstopped docker start
}

mode=${INSTALL_MODE:-}
if [ -z "$mode" ]; then
	[ -r /dev/tty ] || die 'no terminal for the install type prompt; set INSTALL_MODE=server or INSTALL_MODE=desktop'
	while :; do
		printf 'home: install type, server or desktop: ' >/dev/tty
		IFS= read -r answer </dev/tty || die 'no install type chosen; set INSTALL_MODE=server or INSTALL_MODE=desktop'
		case $answer in
			server | s) mode=server; break ;;
			desktop | d) mode=desktop; break ;;
			*) printf 'home: answer server or desktop\n' >/dev/tty ;;
		esac
	done
fi
case $mode in server | desktop) ;; *) die "INSTALL_MODE must be server or desktop, not $mode" ;; esac
say "installing $mode"

[ "$(id -u)" -eq 0 ] || die 'run as root, for example: doas sh usr/host/alpine/install.sh'
# shellcheck disable=SC1091
[ -r /etc/os-release ] && . /etc/os-release
[ "${ID:-}" = alpine ] || die 'this provisioner supports only Alpine Linux'
case ${VERSION_ID:-} in
	*_alpha* | *_git*) ;;
	*) die "Alpine ${VERSION_ID:-unknown} is a stable release; this provisioner targets edge (see README)" ;;
esac
arch=$(apk --print-arch)
case $arch in x86_64 | aarch64) ;; *) die "architecture $arch is not supported" ;; esac
rootfs=$(awk '$2 == "/" { t = $3 } END { print t }' /proc/mounts)
case $rootfs in tmpfs | ramfs | '') die "root filesystem is $rootfs; install Alpine to disk (sys mode) first" ;; esac
command -v git >/dev/null || die 'git is required: apk add git'
[ "$(git -c safe.directory="$PWD" -c safe.directory="$usr_root" rev-parse --is-shallow-repository)" = false ] ||
	die 'this checkout is shallow; home recognizes its installed files from full history: git fetch --unshallow'

user=${USER_NAME:-josh}
[ "$user" != root ] || die 'USER_NAME must be a regular user, not root'
entry=$(getent passwd "$user") || die "user $user does not exist; create it with setup-user or adduser"
uid=$(printf '%s\n' "$entry" | cut -d: -f3)
home=$(printf '%s\n' "$entry" | cut -d: -f6)
[ "$uid" -ge 1000 ] || die "user $user has uid $uid; a regular login (uid >= 1000) is required"
[ -d "$home" ] && [ "$(stat -c %u "$home")" = "$uid" ] || die "home directory $home of $user is missing or not owned by $user"
hash=$(awk -F: -v u="$user" '$1 == u { print $2 }' /etc/shadow)
case $hash in '$'*) ;; *) die "user $user has no usable password; set one with: passwd $user" ;; esac

[ -s /etc/apk/repositories ] || die '/etc/apk/repositories is empty; run setup-apkrepos'
repos=$(sed -e 's/#.*//' -e '/^[[:space:]]*$/d' /etc/apk/repositories)
printf '%s\n' "$repos" | grep -Eqv '/edge/(main|community)/*$' &&
	die "only edge main and community repositories are supported; remove the others from /etc/apk/repositories"
printf '%s\n' "$repos" | grep -q '/edge/community/*$' ||
	die 'enable the edge community repository in /etc/apk/repositories'
check_doas_policy

for script in install.sh verify.sh build/dwl.sh build/ghostty.sh build/helium.sh config/volume config/home-session config/profile.sh services/home-runtime; do
	sh -n "$script" || die "$script has a syntax error"
done

[ -f "$usr_root/sync" ] && [ -f "$usr_root/dotfiles/sym" ] && [ -f "$usr_root/dl" ] ||
	die "$usr_root is not the usr checkout; clone $usr_url and run usr/host/alpine/install.sh from it"
origin=$(as_user "git -C '$usr_root' remote get-url origin" 2>/dev/null) ||
	die "$usr_root is not a git checkout"
case $origin in
	"$usr_url" | "$usr_url.git" | git@github.com:joshuarli/usr | git@github.com:joshuarli/usr.git) ;;
	*) die "$usr_root is a checkout of $origin, not $usr_url" ;;
esac

if command -v clang >/dev/null; then
	check_managed config/clang.cfg "/etc/clang$(clang_major)/clang.cfg"
	check_managed config/clang.cfg "/etc/clang$(clang_major)/clang++.cfg"
fi

as_user "sh '$usr_root/sync' plan >/dev/null" ||
	die "dotfile links conflict with existing files; run sh $usr_root/sync plan as $user and resolve each CONFLICT"
check_managed config/profile.sh /etc/profile.d/home-session.sh

if [ "$mode" = desktop ]; then
	! apk info -e linux-lts >/dev/null 2>&1 ||
		die 'linux-lts is installed; this desktop runs linux-stable: apk add linux-stable && apk del linux-lts, then reboot'

	! awk -F: '$1 == "tty0" && $3 == "respawn"' /etc/inittab | grep -q . ||
		die 'a getty on tty0 shares the tty1 console with the desktop login; comment out the tty0 line in /etc/inittab and run: kill -HUP 1'

	conf=$(mktemp)
	printf 'home_user="%s"\n' "$user" > "$conf"
	check_managed config/volume /usr/local/bin/volume
	check_managed config/home-session /usr/local/bin/home-session
	check_managed services/home-runtime /etc/init.d/home-runtime
	if [ -e /etc/conf.d/home-runtime ] && ! cmp -s "$conf" /etc/conf.d/home-runtime; then
		die "/etc/conf.d/home-runtime configures a different user or was not written by home; remove it to provision $user"
	fi
	if [ -e /usr/local/bin/dwl ]; then
		case $(/usr/local/bin/dwl -v 2>&1) in
			'dwl '*-home.*) ;;
			*) die '/usr/local/bin/dwl was not built by home; move it aside' ;;
		esac
	fi
	if [ -e /usr/local/bin/ghostty-custom ]; then
		[ -f /usr/local/bin/ghostty-custom ] && [ ! -L /usr/local/bin/ghostty-custom ] ||
			die '/usr/local/bin/ghostty-custom exists and is not a regular file; move it aside'
		[ -f /usr/local/share/home/ghostty-custom.tag ] ||
			die '/usr/local/bin/ghostty-custom was not installed by home; move it aside'
	fi
	if [ -e /usr/local/bin/helium ]; then
		[ -L /usr/local/bin/helium ] &&
			[ "$(readlink /usr/local/bin/helium)" = /usr/local/lib/helium/current/helium-wrapper ] ||
			die '/usr/local/bin/helium exists and is not a home-managed symlink; move it aside'
	fi
	if [ -e /usr/local/lib/helium/current ] && [ ! -L /usr/local/lib/helium/current ]; then
		die '/usr/local/lib/helium/current exists and is not a home-managed symlink; move it aside'
	fi
fi

say 'checking network and repositories'
apk update --quiet || die 'apk update failed; check networking and /etc/apk/repositories'

packages=$(sed -e 's/#.*//' -e '/^[[:space:]]*$/d' packages.txt)
[ ! -f "packages-$arch.txt" ] || packages="$packages $(sed -e 's/#.*//' -e '/^[[:space:]]*$/d' "packages-$arch.txt")"
# shellcheck disable=SC2086
apk add --quiet $packages
install_doas_policy
setup_docker

[ "$(clang_major)" -ge 23 ] || die "clang $(clang -dumpversion) is older than 23; check the edge repositories"
install_managed config/clang.cfg "/etc/clang$(clang_major)/clang.cfg" 0644
install_managed config/clang.cfg "/etc/clang$(clang_major)/clang++.cfg" 0644

as_user "sh '$usr_root/sync' links >/dev/null" || die "linking dotfiles from $usr_root failed"
default_tools=$(as_user "sh '$usr_root/dl' --list") || die "reading the default tool list from $usr_root failed"
missing_tools=
for tool in $default_tools; do
	[ "$tool" = agy ] && continue
	case $tool in
		nodejs) [ -x "$home/.local/bin/node" ] && [ -x "$home/.local/bin/npm" ] ;;
		ffmpeg) [ -x "$home/.local/bin/ffmpeg" ] && [ -x "$home/.local/bin/ffprobe" ] ;;
		*) [ -x "$home/.local/bin/$tool" ] ;;
	esac || missing_tools="$missing_tools $tool"
done
if [ -n "$missing_tools" ]; then
	# shellcheck disable=SC2086
	as_user "sh '$usr_root/sync' tools$missing_tools" >/dev/null || die "installing$missing_tools from $usr_root failed"
fi
install_managed config/profile.sh /etc/profile.d/home-session.sh 0644

if [ "$mode" = desktop ]; then
	desktop_packages=$(sed -e 's/#.*//' -e '/^[[:space:]]*$/d' packages-desktop.txt)
	# shellcheck disable=SC2086
	apk add --quiet $desktop_packages
	if apk info -e foot >/dev/null 2>&1; then
		apk del --quiet foot || die 'could not remove foot'
		say 'removed foot'
	fi
	if apk info -e foot-extra-terminfo >/dev/null 2>&1; then
		apk del --quiet foot-extra-terminfo || die 'could not remove foot-extra-terminfo'
		say 'removed foot-extra-terminfo'
	fi

	rc-update show sysinit | awk '$1 == "udev" { found = 1 } END { exit !found }' || setup-devd udev

	sh build/dwl.sh
	sh build/ghostty.sh
	USER_NAME="$user" sh build/helium.sh
	install_managed config/volume /usr/local/bin/volume 0755
	install_managed config/home-session /usr/local/bin/home-session 0755
	install_managed services/home-runtime /etc/init.d/home-runtime 0755
	install_managed "$conf" /etc/conf.d/home-runtime 0644

	id -Gn "$user" | tr ' ' '\n' | grep -qx seat || { addgroup "$user" seat; say "added $user to seat"; }
	for service in seatd home-runtime; do
		rc-update show default | awk -v s="$service" '$1 == s { found = 1 } END { exit !found }' || rc-update add "$service" default
		rc-service --ifstopped "$service" start
	done
fi

setup_tailscale

case $mode in
server) say "provisioned server for $user. Run: doas sh usr/host/alpine/verify.sh server" ;;
desktop) say "provisioned desktop. Log out, then log in as $user on tty1. Run: doas sh usr/host/alpine/verify.sh" ;;
esac

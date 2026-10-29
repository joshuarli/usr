#!/bin/sh
set -eu
cd "$(dirname "$0")"

usr_root=$(cd ../.. && pwd)
usr_url=https://github.com/joshuarli/usr

die() { printf 'home: %s\n' "$*" >&2; exit 1; }
say() { printf 'home: %s\n' "$*"; }

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

[ "$(id -u)" -eq 0 ] || die 'run as root, for example: doas sh usr/host/alpine/install.sh'
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
! apk info -e linux-lts >/dev/null 2>&1 ||
	die 'linux-lts is installed; this desktop runs linux-stable: apk add linux-stable && apk del linux-lts, then reboot'

user=${USER_NAME:-josh}
[ "$user" != root ] || die 'USER_NAME must be a regular user, not root'
entry=$(getent passwd "$user") || die "user $user does not exist; create it with setup-user or adduser"
uid=$(printf '%s\n' "$entry" | cut -d: -f3)
home=$(printf '%s\n' "$entry" | cut -d: -f6)
[ "$uid" -ge 1000 ] || die "user $user has uid $uid; a regular login (uid >= 1000) is required"
[ -d "$home" ] && [ "$(stat -c %u "$home")" = "$uid" ] || die "home directory $home of $user is missing or not owned by $user"
hash=$(awk -F: -v u="$user" '$1 == u { print $2 }' /etc/shadow)
case $hash in '$'*) ;; *) die "user $user has no usable password; set one with: passwd $user" ;; esac

! awk -F: '$1 == "tty0" && $3 == "respawn"' /etc/inittab | grep -q . ||
	die 'a getty on tty0 shares the tty1 console with the desktop login; comment out the tty0 line in /etc/inittab and run: kill -HUP 1'

[ -s /etc/apk/repositories ] || die '/etc/apk/repositories is empty; run setup-apkrepos'
repos=$(sed -e 's/#.*//' -e '/^[[:space:]]*$/d' /etc/apk/repositories)
printf '%s\n' "$repos" | grep -Eqv '/edge/(main|community)/*$' &&
	die "only edge main and community repositories are supported; remove the others from /etc/apk/repositories"
printf '%s\n' "$repos" | grep -q '/edge/community/*$' ||
	die 'enable the edge community repository in /etc/apk/repositories'

for script in install.sh verify.sh build/dwl.sh config/home-session config/profile.sh services/home-runtime; do
	sh -n "$script" || die "$script has a syntax error"
done

conf=$(mktemp)
trap 'rm -f "$conf"' EXIT HUP INT TERM
printf 'home_user="%s"\n' "$user" > "$conf"
check_managed config/home-session /usr/local/bin/home-session
check_managed services/home-runtime /etc/init.d/home-runtime
check_managed config/profile.sh /etc/profile.d/home-session.sh
clang_major() { clang -dumpversion | cut -d. -f1; }
if command -v clang >/dev/null; then
	check_managed config/clang.cfg "/etc/clang$(clang_major)/clang.cfg"
	check_managed config/clang.cfg "/etc/clang$(clang_major)/clang++.cfg"
fi
if [ -e /etc/conf.d/home-runtime ] && ! cmp -s "$conf" /etc/conf.d/home-runtime; then
	die "/etc/conf.d/home-runtime configures a different user or was not written by home; remove it to provision $user"
fi
if [ -e /usr/local/bin/dwl ]; then
	case $(/usr/local/bin/dwl -v 2>&1) in
		'dwl '*-home.*) ;;
		*) die '/usr/local/bin/dwl was not built by home; move it aside' ;;
	esac
fi
[ -f "$usr_root/sync" ] && [ -f "$usr_root/dotfiles/sym" ] && [ -f "$usr_root/dl" ] ||
	die "$usr_root is not the usr checkout; clone $usr_url and run usr/host/alpine/install.sh from it"
origin=$(as_user "git -C '$usr_root' remote get-url origin" 2>/dev/null) ||
	die "$usr_root is not a git checkout"
case $origin in
	"$usr_url" | "$usr_url.git" | git@github.com:joshuarli/usr | git@github.com:joshuarli/usr.git) ;;
	*) die "$usr_root is a checkout of $origin, not $usr_url" ;;
esac

say 'checking network and repositories'
apk update --quiet || die 'apk update failed; check networking and /etc/apk/repositories'

as_user "sh '$usr_root/sync' plan >/dev/null" ||
	die "dotfile links conflict with existing files; run sh $usr_root/sync plan as $user and resolve each CONFLICT"

packages=$(sed -e 's/#.*//' -e '/^[[:space:]]*$/d' packages.txt)
[ ! -f "packages-$arch.txt" ] || packages="$packages $(sed -e 's/#.*//' -e '/^[[:space:]]*$/d' "packages-$arch.txt")"
# shellcheck disable=SC2086
apk add --quiet $packages

rc-update show sysinit | awk '$1 == "udev" { found = 1 } END { exit !found }' || setup-devd udev

[ "$(clang_major)" -ge 23 ] || die "clang $(clang -dumpversion) is older than 23; check the edge repositories"
install_managed config/clang.cfg "/etc/clang$(clang_major)/clang.cfg" 0644
install_managed config/clang.cfg "/etc/clang$(clang_major)/clang++.cfg" 0644
sh build/dwl.sh
install_managed config/home-session /usr/local/bin/home-session 0755
install_managed services/home-runtime /etc/init.d/home-runtime 0755
install_managed "$conf" /etc/conf.d/home-runtime 0644
install_managed config/profile.sh /etc/profile.d/home-session.sh 0644

id -Gn "$user" | tr ' ' '\n' | grep -qx seat || { addgroup "$user" seat; say "added $user to seat"; }
for service in seatd home-runtime; do
	rc-update show default | awk -v s="$service" '$1 == s { found = 1 } END { exit !found }' || rc-update add "$service" default
	rc-service --ifstopped "$service" start
done

as_user "sh '$usr_root/sync' links >/dev/null" || die "linking dotfiles from $usr_root failed"
[ -x "$home/.local/bin/ish" ] || as_user "sh '$usr_root/sync' tools ish >/dev/null" || die "installing ish from $usr_root failed"

say "provisioned. Log out, then log in as $user on tty1. Run: doas sh usr/host/alpine/verify.sh"

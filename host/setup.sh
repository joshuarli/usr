#!/bin/sh
set -eu

usr_url=https://github.com/joshuarli/usr

die() { printf 'setup: %s\n' "$*" >&2; exit 1; }
say() { printf 'setup: %s\n' "$*"; }

PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
export PATH

os=$(uname -s)
os_id=unknown
if [ -r /etc/os-release ]; then
    os_id=$(awk -F= '$1 == "ID" { gsub(/^"/, "", $2); gsub(/"$/, "", $2); print $2; exit }' /etc/os-release)
fi
[ -n "$os_id" ] || os_id=unknown

case $os in
Linux) ;;
*) die "unsupported OS $os; this bootstrap supports only Alpine Linux" ;;
esac

as_root() {
    if [ "$(id -u)" -eq 0 ]; then
        "$@"
    elif command -v doas >/dev/null 2>&1; then
        doas "$@"
    elif command -v sudo >/dev/null 2>&1; then
        sudo "$@"
    else
        die 'run as root or install doas or sudo'
    fi
}

setup_alpine() {
    command -v git >/dev/null 2>&1 || {
        say 'installing git'
        as_root apk add --interactive=no git
    }

    if [ -f ./host/alpine/install.sh ] && [ -f ./sync ]; then
        dest=$PWD
        say "using checkout at $dest"
    else
        [ -n "${HOME:-}" ] || die 'HOME is not set; run from the usr checkout or set HOME'
        if [ -f "$HOME/usr/host/alpine/install.sh" ]; then
            dest=$HOME/usr
            say "using existing checkout at $dest"
        elif [ -e "$HOME/usr" ]; then
            die "$HOME/usr exists but is not a usr checkout; move it aside"
        else
            say "cloning $usr_url to $HOME/usr"
            git clone "$usr_url" "$HOME/usr"
            dest=$HOME/usr
        fi
    fi

    say 'provisioning the Alpine desktop'
    if [ -n "${USER_NAME:-}" ]; then
        as_root env "USER_NAME=$USER_NAME" sh "$dest/host/alpine/install.sh" </dev/null
    else
        as_root sh "$dest/host/alpine/install.sh" </dev/null
    fi
}

case $os_id in
alpine) setup_alpine ;;
*) die "unsupported distribution $os_id; this bootstrap supports only Alpine Linux" ;;
esac

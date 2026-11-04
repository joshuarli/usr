#!/bin/sh
set -eu

usr_url=https://github.com/joshuarli/usr

die() { printf 'setup: %s\n' "$*" >&2; exit 1; }
say() { printf 'setup: %s\n' "$*"; }

PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
export PATH

os=$(uname -s)
os_id=unknown
os_version=
if [ -r /etc/os-release ]; then
    os_id=$(awk -F= '$1 == "ID" { gsub(/^"/, "", $2); gsub(/"$/, "", $2); print $2; exit }' /etc/os-release)
    os_version=$(awk -F= '$1 == "VERSION_ID" { gsub(/^"/, "", $2); gsub(/"$/, "", $2); print $2; exit }' /etc/os-release)
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

as_setup_user() {
    if [ "$(id -u)" -eq "$setup_uid" ]; then
        sh -c "$1"
    else
        su -l -s /bin/sh "$setup_user" -c "$1"
    fi
}

setup_github_ssh_key() {
    setup_user=${USER_NAME:-josh}
    setup_entry=$(getent passwd "$setup_user") || die "no such user: $setup_user"
    setup_uid=$(printf '%s\n' "$setup_entry" | cut -d: -f3)
    setup_home=$(printf '%s\n' "$setup_entry" | cut -d: -f6)
    github_key=$setup_home/.ssh/github.pub
    [ -x "$setup_home/.local/bin/gh" ] || die 'gh is not installed for the setup user'
    [ -f "$github_key" ] && [ ! -L "$github_key" ] || die "missing public key: $github_key"
    [ "$(stat -c %u "$github_key")" = "$setup_uid" ] || die "$github_key is not owned by $setup_user"

    if [ "$(id -u)" -ne 0 ] && [ "$(id -u)" -ne "$setup_uid" ]; then
        say "GitHub login and key upload must run as $setup_user; run setup.sh from that account"
        return 0
    fi

    if auth_status=$(as_setup_user '~/.local/bin/gh auth status --hostname github.com 2>&1'); then
        :
    else
        if [ ! -r /dev/tty ] || [ ! -t 2 ]; then
            say 'GitHub is not authenticated. Run: gh auth login --hostname github.com --git-protocol https --web --skip-ssh-key --scopes admin:public_key'
            say 'then rerun setup.sh'
            return 0
        fi
        say 'log in to GitHub and approve public-key access'
        as_setup_user '~/.local/bin/gh auth login --hostname github.com --git-protocol https --web --skip-ssh-key --scopes admin:public_key' </dev/tty ||
            die 'GitHub login failed'
        auth_status=$(as_setup_user '~/.local/bin/gh auth status --hostname github.com 2>&1') ||
            die 'GitHub login did not complete'
    fi

    case $auth_status in
        *admin:public_key*) ;;
        *)
            if [ ! -r /dev/tty ] || [ ! -t 2 ]; then
                say 'GitHub login needs admin:public_key. Run: gh auth refresh --hostname github.com --scopes admin:public_key'
                say 'then rerun setup.sh'
                return 0
            fi
            say 'refresh GitHub access to allow SSH-key upload'
            as_setup_user '~/.local/bin/gh auth refresh --hostname github.com --scopes admin:public_key' </dev/tty ||
                die 'could not grant GitHub public-key access'
            auth_status=$(as_setup_user '~/.local/bin/gh auth status --hostname github.com 2>&1') ||
                die 'GitHub authentication is unavailable'
            case $auth_status in
                *admin:public_key*) ;;
                *) die 'GitHub login lacks admin:public_key access' ;;
            esac
            ;;
    esac

    as_setup_user '~/.local/bin/gh ssh-key add ~/.ssh/github.pub --title "$(hostname) Alpine" --type authentication' ||
        die 'could not upload the GitHub SSH key'
    say 'GitHub SSH key is registered'
}

bootstrap_git() {
    GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1 git "$@"
}

converted=false

ensure_edge() {
    case ${os_version:-} in
        *_alpha* | *_git*) return 0 ;;
    esac
    [ -n "${os_version:-}" ] || die 'cannot read VERSION_ID from /etc/os-release'
    say "converting Alpine $os_version to edge; this upgrades every package"
    as_root sh -ec '
        printf "%s\n" \
            https://dl-cdn.alpinelinux.org/alpine/edge/main \
            https://dl-cdn.alpinelinux.org/alpine/edge/community \
            >/etc/apk/repositories
        apk update --quiet
        apk upgrade --available --interactive=no
        if apk info -e linux-lts >/dev/null 2>&1; then
            apk add --interactive=no linux-stable
            apk del --interactive=no linux-lts
        fi
    '
    converted=true
    say 'converted to edge'
}

setup_alpine() {
    ensure_edge
    if [ "$converted" = true ]; then
        say 'reboot into Alpine edge, then rerun setup.sh to provision'
        return 0
    fi

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
            bootstrap_git clone "$usr_url" "$HOME/usr"
            dest=$HOME/usr
        fi
    fi
    bootstrap_git -C "$dest" pull --ff-only || die "could not update $dest; pull it by hand"

    say 'provisioning Alpine'
    if [ -z "${TS_AUTHKEY:-}" ] && [ -t 2 ]; then
        say 'if Tailscale needs authorization, open the device URL printed during provisioning'
    fi
    as_root env "USER_NAME=${USER_NAME:-}" "INSTALL_MODE=${INSTALL_MODE:-}" "TS_AUTHKEY=${TS_AUTHKEY:-}" \
        sh "$dest/host/alpine/install.sh" </dev/null
    setup_github_ssh_key
    [ "$converted" = false ] || say 'reboot to finish the edge upgrade'
}

case $os_id in
alpine) setup_alpine ;;
*) die "unsupported distribution $os_id; this bootstrap supports only Alpine Linux" ;;
esac

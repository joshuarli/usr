#!/bin/sh
set -eu

usage() {
    cat <<'EOF'
Usage: setup-git-client.sh [--host HOST] [--user USER] [--repo NAME]
                           [--remote NAME] [--push]

Run inside an existing local Git repository. Create ~/d/NAME.git on the SSH
server if needed, then add NAME as a local Git remote. The repo name defaults
to the local repository directory name. --push also pushes the current branch.
EOF
}

fail() {
    printf 'Error: %s\n' "$*" >&2
    exit 1
}

host=threadripper
user=josh
repo_name=
remote_name=origin
push_now=no

while [ "$#" -gt 0 ]; do
    case "$1" in
        --host)
            [ "$#" -ge 2 ] || fail "--host requires a value"
            host=$2
            shift 2
            ;;
        --user)
            [ "$#" -ge 2 ] || fail "--user requires a value"
            user=$2
            shift 2
            ;;
        --repo)
            [ "$#" -ge 2 ] || fail "--repo requires a value"
            repo_name=$2
            shift 2
            ;;
        --remote)
            [ "$#" -ge 2 ] || fail "--remote requires a value"
            remote_name=$2
            shift 2
            ;;
        --push)
            push_now=yes
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            usage >&2
            fail "unknown argument: $1"
            ;;
    esac
done

case "$host" in
    ''|-*) fail "invalid SSH host: $host" ;;
esac
case "$user" in
    ''|-*|*[!A-Za-z0-9._-]*) fail "invalid SSH user: $user" ;;
esac
case "$remote_name" in
    .|..|''|-*|*[!A-Za-z0-9._-]*) fail "invalid Git remote name: $remote_name" ;;
esac

repo_root=$(git rev-parse --show-toplevel 2>/dev/null) || fail "run inside a Git repository"
if [ -z "$repo_name" ]; then
    repo_name=$(basename "$repo_root")
fi
case "$repo_name" in
    .|..|*[!A-Za-z0-9._-]*|'') fail "invalid repository name: $repo_name" ;;
esac

destination=$user@$host
remote_url=$destination:d/$repo_name.git
cd "$repo_root"
if git remote | grep -Fqx -- "$remote_name"; then
    configured_urls=$(git remote get-url --all "$remote_name")
    configured_push_urls=$(git remote get-url --push --all "$remote_name")
    [ "$configured_urls" = "$remote_url" ] && [ "$configured_push_urls" = "$remote_url" ] ||
        fail "remote '$remote_name' already has a different fetch or push URL; choose another --remote name or update it manually"
else
    remote_missing=yes
fi

ssh "$destination" "sh -s -- '$repo_name'" <<'REMOTE'
set -eu
repo_name=$1
[ -n "$HOME" ] || {
    printf 'Error: remote account has no home directory\n' >&2
    exit 1
}
repo_path=$HOME/d/$repo_name.git
mkdir -p "$HOME/d"
if [ -L "$repo_path" ]; then
    printf 'Error: remote repository path must not be a symbolic link: %s\n' "$repo_path" >&2
    exit 1
fi
if [ -e "$repo_path" ]; then
    [ "$(git -C "$repo_path" rev-parse --is-bare-repository 2>/dev/null || true)" = true ] || {
        printf 'Error: remote path exists but is not a bare repository: %s\n' "$repo_path" >&2
        exit 1
    }
else
    git init --bare "$repo_path"
fi
REMOTE

if [ "${remote_missing:-no}" = yes ]; then
    git remote add "$remote_name" "$remote_url"
fi

printf 'Remote %s is ready: %s\n' "$remote_name" "$remote_url"
if [ "$push_now" = yes ]; then
    git push -u "$remote_name" HEAD
else
    printf 'To publish the current branch, run: git push -u %s HEAD\n' "$remote_name"
fi

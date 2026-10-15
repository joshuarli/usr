#!/bin/sh

set -u
script_dir=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd -P) || exit 1
default_root=$(CDPATH='' cd -- "$script_dir/.." && pwd -P) || exit 1
requested_root=$(CDPATH='' cd -- "${1:-$default_root}" && pwd -P) || {
	printf '%s\n' 'repository root does not exist' >&2
	exit 1
}
git_root=$(git -C "$requested_root" rev-parse --show-toplevel) || {
	printf '%s\n' 'cannot find the Git repository root' >&2
	exit 1
}
physical_git_root=$(CDPATH='' cd -- "$git_root" && pwd -P) || exit 1
if [ "$physical_git_root" != "$requested_root" ]; then
	printf '%s\n' 'scratch check must run at the Git repository root' >&2
	exit 1
fi

scratch_root="$physical_git_root/.work"
scratch_tmp="$scratch_root/tmp"
if [ -L "$scratch_root" ] || [ -L "$scratch_tmp" ]; then
	printf '%s\n' '.work and .work/tmp must not be symlinks' >&2
	exit 1
fi

git -C "$physical_git_root" check-ignore -q -- .work/tmp/verify-marker || {
	printf '%s\n' '.work must be ignored by .git/info/exclude' >&2
	exit 1
}
exclude_path=$(git -C "$physical_git_root" rev-parse --git-path info/exclude) || exit 1
ignore_rule=$(git -C "$physical_git_root" check-ignore -v -- .work/tmp/verify-marker) || {
	printf '%s\n' '.work must be ignored by .git/info/exclude' >&2
	exit 1
}
case "$ignore_rule" in
	"$exclude_path":*|"$physical_git_root/$exclude_path":*) ;;
	*)
		printf '%s\n' '.work must be ignored through .git/info/exclude' >&2
		exit 1
		;;
esac

mkdir -p "$scratch_tmp" || {
	printf '%s\n' 'cannot create .work/tmp' >&2
	exit 1
}
if [ ! -d "$scratch_root" ] || [ -L "$scratch_root" ] || [ ! -d "$scratch_tmp" ] || [ -L "$scratch_tmp" ]; then
	printf '%s\n' '.work and .work/tmp must be real directories' >&2
	exit 1
fi

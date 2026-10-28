#!/bin/sh
set -eu

cmd=${1:-}
case $cmd in
plan | links | tools) ;;
*) printf 'usage: usr-sync.sh plan|links|tools [TOOL...]\n' >&2; exit 1 ;;
esac
shift

usr_root=$(cd "$(dirname "$0")/.." && pwd)
os=$(uname -s | tr '[:upper:]' '[:lower:]')
target=${TARGET:-$HOME}
tmpdir=${TMPDIR:-$usr_root/.work/tmp}
owned=${DL_OWNED_FILE:-${XDG_STATE_HOME:-$HOME/.local/state}/make/dl-owned}

dup=$(for layer in dotfiles/base "dotfiles/$os"; do
	git -C "$usr_root" ls-files -- "$layer" | sed "s|^$layer/||"
done | sort | uniq -d)
[ -z "$dup" ] || { printf 'in more than one layer:\n%s\n' "$dup" >&2; exit 1; }

mkdir -p "$tmpdir"

case $cmd in
plan)
	planned=$tmpdir/plan-prunes.$$
	: > "$planned"
	trap 'rm -f "$planned"' EXIT HUP INT TERM
	status=0
	for layer in dotfiles/base "dotfiles/$os"; do
		output=$(SYM_OWNED_FILE="$owned" SYM_PLANNED_PRUNES="$planned" sh "$usr_root/dotfiles/sym" --dry-run -t "$target" "$usr_root/$layer" 2>&1) || status=$?
		printf '%s\n' "$output"
		case $output in *CONFLICT:*) status=1 ;; esac
	done
	exit "$status"
	;;
links)
	mkdir -p "$(dirname "$owned")"
	sh "$usr_root/dotfiles/migrate-pinact.sh" "$target" "$owned"
	for layer in dotfiles/base "dotfiles/$os"; do
		TMPDIR="$tmpdir" SYM_OWNED_FILE="$owned" sh "$usr_root/dotfiles/sym" -v -t "$target" "$usr_root/$layer"
	done
	;;
tools)
	mkdir -p "$(dirname "$owned")"
	TMPDIR="$tmpdir" DL_OWNED_FILE="$owned" sh "$usr_root/dl" "$@"
	;;
esac

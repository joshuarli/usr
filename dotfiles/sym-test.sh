#!/bin/sh

set -e
die () { >&2 printf %s\\n "$1"; exit 1; }

tmp="$(mktemp -d)" || die 'mktemp failed'
trap 'rm -rf "$tmp"' 0 1 2 3 15

sym="${PWD}/sym"

# setup for all tests
cd "$tmp"
mkdir -p home expected-home dotfiles/bash dotfiles/mpv/.config/mpv
touch dotfiles/bash/.bashrc
touch dotfiles/mpv/.config/mpv/mpv.conf
mkdir -p tree/agent
touch tree/agent/.sym-dir tree/agent/keep.txt
printf 'generated.log\n' > tree/agent/.gitignore
touch tree/agent/generated.log
git init -q .
git add tree/agent/.sym-dir tree/agent/.gitignore tree/agent/keep.txt

nfailed=0
echo "running tests."

assert_output() {
	printf '%s\n' "$1" > expected-log
	diff log expected-log || nfailed=$((nfailed + 1))
}

printf '\n1: dry-run, no conflicts, link bash\n'
$sym -t home --dry-run dotfiles/bash > log 2>&1
expected="dry-run; the following operations are what would have been executed.
LINK: home/.bashrc -> ../dotfiles/bash/.bashrc"
echo "  assertion 1: expected output"; assert_output "$expected"


printf '\n2: dry-run, conflict with bash\n'
touch home/.bashrc
$sym -t home --dry-run dotfiles/bash > log 2>&1
expected="CONFLICT: home/.bashrc already exists. sym cannot create symlinks if there is an existing file.
dry-run; the following operations are what would have been executed."
echo "  assertion 1: expected output"; assert_output "$expected"
rm -r home; mkdir home


printf '\n3: nonexistent target directory\n'
$sym -t home/foo dotfiles/bash > log 2>&1 || true
expected="target directory home/foo is not a directory or does not exist"
echo "  assertion 1: expected output"; assert_output "$expected"


printf '\n4: no conflicts, link all\n'
cd expected-home
mkdir -p .config/mpv
ln -s ../dotfiles/bash/.bashrc .
cd .config/mpv
ln -s ../../../dotfiles/mpv/.config/mpv/mpv.conf .
cd ../../..
$sym -t home -v dotfiles/bash > log 2>&1
$sym -t home -v dotfiles/mpv >> log 2>&1
expected="LINK: home/.bashrc -> ../dotfiles/bash/.bashrc
MKDIRS: home/.config/mpv
LINK: home/.config/mpv/mpv.conf -> ../../../dotfiles/mpv/.config/mpv/mpv.conf"
echo "  assertion 1: expected output"; assert_output "$expected"
echo "  assertion 2: expected result"; diff -r --no-dereference home expected-home || nfailed=$((nfailed + 1))
rm -r home; mkdir home
rm -r expected-home; mkdir expected-home


printf '\n5: conflict with mpv (link should be noop)\n'
mkdir -p home/.config/mpv expected-home/.config/mpv
touch home/.config/mpv/mpv.conf expected-home/.config/mpv/mpv.conf
$sym -t home dotfiles/mpv > log 2>&1 || true
expected="CONFLICT: home/.config/mpv/mpv.conf already exists. sym cannot create symlinks if there is an existing file.
sym will not start until all conflicts are resolved."
echo "  assertion 1: expected output"; assert_output "$expected"
echo "  assertion 2: expected result"; diff -r --no-dereference home expected-home || nfailed=$((nfailed + 1))
rm -r home; mkdir home
rm -r expected-home; mkdir expected-home


printf '\n6: dry-run, unlink all\n'
$sym -t home dotfiles/bash > /dev/null
$sym -t home dotfiles/mpv > /dev/null
$sym -t home --delete --dry-run dotfiles/bash > log 2>&1
$sym -t home --delete --dry-run dotfiles/mpv >> log 2>&1
expected="dry-run; the following operations are what would have been executed.
UNLINK: home/.bashrc
dry-run; the following operations are what would have been executed.
UNLINK: home/.config/mpv/mpv.conf"
echo "  assertion 1: expected output"; assert_output "$expected"
rm -r home; mkdir home


printf '\n7: dry-run, unlink mpv, absolute symlink to same path (resolves correctly, not a conflict)\n'
$sym -t home dotfiles/mpv > /dev/null
mpv_abs="$(cd dotfiles/mpv && pwd)/.config/mpv/mpv.conf"
ln -sf "$mpv_abs" home/.config/mpv/mpv.conf
$sym -t home --delete --dry-run dotfiles/mpv > log 2>&1
expected="dry-run; the following operations are what would have been executed.
UNLINK: home/.config/mpv/mpv.conf"
echo "  assertion 1: expected output"; assert_output "$expected"
rm -r home; mkdir home


printf '\n8: unlink only mpv\n'
$sym -t home dotfiles/bash > /dev/null
$sym -t home dotfiles/mpv > /dev/null
cd expected-home
ln -s ../dotfiles/bash/.bashrc .
cd ..
$sym -t home -v -d dotfiles/mpv > log 2>&1
expected="UNLINK: home/.config/mpv/mpv.conf
RMDIR: home/.config/mpv
RMDIR: home/.config"
echo "  assertion 1: expected output"; assert_output "$expected"
echo "  assertion 2: expected result"; diff -r --no-dereference home expected-home || nfailed=$((nfailed + 1))
rm -r home; mkdir home
rm -r expected-home; mkdir expected-home


printf '\n9: try to unlink bash, but conflict; bash is not owned by sym (relative symlink)\n'
touch foo
cd home
ln -s ../foo .bashrc
cd ../expected-home
ln -s ../foo .bashrc
cd ..
$sym -t home -v -d dotfiles/bash > log 2>&1 || true
expected="CONFLICT: home/.bashrc does not point to the expected destination, so refusing to remove.
sym will not start until all conflicts are resolved."
echo "  assertion 1: expected output"; assert_output "$expected"
echo "  assertion 2: expected result"; diff -r --no-dereference home expected-home || nfailed=$((nfailed + 1))
rm -r home; mkdir home
rm -r expected-home; mkdir expected-home


printf '\n10: try to unlink all, but conflict; a non-symlink file exists\n'
mkdir -p home/.config/mpv expected-home/.config/mpv
echo foobar > home/.config/mpv/mpv.conf
echo foobar > expected-home/.config/mpv/mpv.conf
$sym -t home -v dotfiles/mpv > log 2>&1 || true
expected="CONFLICT: home/.config/mpv/mpv.conf already exists. sym cannot create symlinks if there is an existing file.
sym will not start until all conflicts are resolved."
echo "  assertion 1: expected output"; assert_output "$expected"
echo "  assertion 2: expected result"; diff -r --no-dereference home expected-home || nfailed=$((nfailed + 1))
rm -r home; mkdir home
rm -r expected-home; mkdir expected-home


printf '\n11: whole-directory link respects Git ignores and is idempotent\n'
$sym -t home -v tree > log 2>&1
expected="LINK: home/agent -> ../tree/agent"
echo "  assertion 1: expected output"; assert_output "$expected"
echo "  assertion 2: expected symlink target"
[ -L home/agent ] && [ "$(readlink home/agent)" = '../tree/agent' ] || nfailed=$((nfailed + 1))
echo "  assertion 3: ignored file is not individually linked"
[ "$(find home -type l | wc -l | tr -d ' ')" -eq 1 ] || nfailed=$((nfailed + 1))
$sym -t home -v tree > log 2>&1
echo "  assertion 4: second run is a no-op"
[ ! -s log ] || nfailed=$((nfailed + 1))
rm -r home; mkdir home


printf '\ntesting finished.\n'
[ "$nfailed" -gt 0 ] && die "failed ${nfailed} assertions"

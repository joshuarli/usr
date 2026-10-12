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


printf '\n12: --copy overwrites an existing file, including an identical copy\n'
mkdir -p dotfiles/copytest
echo v1 > dotfiles/copytest/app.conf
echo local-edit > home/app.conf
src_abs="$(cd dotfiles/copytest && pwd)/app.conf"
$sym -t home -v --copy '*/app.conf' dotfiles/copytest > log 2>&1
expected="COPY: home/app.conf <- $src_abs"
echo "  assertion 1: expected output"; assert_output "$expected"
echo "  assertion 2: content was replaced with the source copy"
cmp -s home/app.conf dotfiles/copytest/app.conf || nfailed=$((nfailed + 1))
echo "  assertion 3: result is a regular file, not a symlink"
[ -f home/app.conf ] && [ ! -L home/app.conf ] || nfailed=$((nfailed + 1))
$sym -t home -v --copy '*/app.conf' dotfiles/copytest > log 2>&1
expected="COPY: home/app.conf <- $src_abs"
echo "  assertion 4: second run forcefully copies the identical file"; assert_output "$expected"


printf '\n13: --copy in delete mode refuses non-identical files, removes identical ones\n'
echo modified > home/app.conf
$sym -t home -v -d --copy '*/app.conf' dotfiles/copytest > log 2>&1 || true
expected="CONFLICT: home/app.conf is not an identical copy of $src_abs, so refusing to remove.
sym will not start until all conflicts are resolved."
echo "  assertion 1: expected output"; assert_output "$expected"
echo "  assertion 2: modified file survived"
[ "$(cat home/app.conf)" = modified ] || nfailed=$((nfailed + 1))
cp dotfiles/copytest/app.conf home/app.conf
$sym -t home -v -d --copy '*/app.conf' dotfiles/copytest > log 2>&1
expected="UNLINK: home/app.conf
RMDIR: home"
echo "  assertion 3: expected output for identical copy"; assert_output "$expected"
[ ! -e home/app.conf ] || nfailed=$((nfailed + 1))
rm dotfiles/copytest/app.conf


printf '\n14: --copy replaces an existing directory\n'
echo v1 > dotfiles/copytest/app.conf
mkdir -p home/app.conf
echo local-edit > home/app.conf/old
src_abs="$(cd dotfiles/copytest && pwd)/app.conf"
$sym -t home -v --copy '*/app.conf' dotfiles/copytest > log 2>&1
expected="COPY: home/app.conf <- $src_abs"
echo "  assertion 1: expected output"; assert_output "$expected"
echo "  assertion 2: directory was replaced with the source copy"
[ -f home/app.conf ] && [ ! -e home/app.conf/old ] && cmp -s home/app.conf dotfiles/copytest/app.conf || nfailed=$((nfailed + 1))
rm dotfiles/copytest/app.conf
rm -r home; mkdir home


printf '\n15: .agents/skills is synced: source files are pushed, target-only files are pulled, reruns are no-ops\n'
skills=dotfiles/synctest/.agents/skills
mkdir -p $skills/alpha
echo alpha > $skills/alpha/SKILL.md
$sym -t home -v dotfiles/synctest > log 2>&1
expected="MKDIRS: home/.agents/skills/alpha
PUSH: home/.agents/skills/alpha/SKILL.md <- $skills/alpha/SKILL.md"
echo "  assertion 1: new source file is pushed as a regular file"; assert_output "$expected"
[ -f home/.agents/skills/alpha/SKILL.md ] && [ ! -L home/.agents/skills/alpha/SKILL.md ] || nfailed=$((nfailed + 1))
echo beta > home/.agents/skills/beta.md
$sym -t home -v dotfiles/synctest > log 2>&1
expected="PULL: $skills/beta.md <- home/.agents/skills/beta.md"
echo "  assertion 2: new target-only file is pulled into the source"; assert_output "$expected"
cmp -s $skills/beta.md home/.agents/skills/beta.md || nfailed=$((nfailed + 1))
$sym -t home -v dotfiles/synctest > log 2>&1
echo "  assertion 3: second run is a no-op"
[ ! -s log ] || nfailed=$((nfailed + 1))


printf '\n16: a one-sided edit flows toward the other side; --dry-run changes nothing\n'
m=home/.agents/skills/.sym-synced
s=$skills/alpha/SKILL.md
t=home/.agents/skills/alpha/SKILL.md
touch -t 202001010000 $m
touch -t 201912310000 $s $t
echo edited-at-target > $t
$sym -t home --dry-run dotfiles/synctest > log 2>&1
expected="dry-run; the following operations are what would have been executed.
PULL: $s <- $t"
echo "  assertion 1: dry-run reports the pull"; assert_output "$expected"
echo "  assertion 2: dry-run leaves source and marker untouched"
[ "$(cat $s)" = alpha ] && [ ! $m -nt $t ] || nfailed=$((nfailed + 1))
$sym -t home -v dotfiles/synctest > log 2>&1
expected="PULL: $s <- $t"
echo "  assertion 3: target edit is pulled into the source"; assert_output "$expected"
[ "$(cat $s)" = edited-at-target ] || nfailed=$((nfailed + 1))
touch -t 202001010000 $m
touch -t 201912310000 $s $t
echo edited-at-source > $s
$sym -t home -v dotfiles/synctest > log 2>&1
expected="PUSH: $t <- $s"
echo "  assertion 4: source edit is pushed to the target"; assert_output "$expected"
[ "$(cat $t)" = edited-at-source ] || nfailed=$((nfailed + 1))


printf '\n17: edits on both sides, or no recorded sync, are a conflict that changes nothing\n'
touch -t 202001010000 $m
echo both-source > $s
echo both-target > $t
$sym -t home -v dotfiles/synctest > log 2>&1 || true
expected="CONFLICT: $t and $s differ and sync cannot tell which side is newer (both changed since the last sync, or none is recorded).
sym will not start until all conflicts are resolved."
echo "  assertion 1: both-changed conflict"; assert_output "$expected"
echo "  assertion 2: neither side was modified"
[ "$(cat $s)" = both-source ] && [ "$(cat $t)" = both-target ] || nfailed=$((nfailed + 1))
rm $m
$sym -t home -v dotfiles/synctest > log 2>&1 || true
echo "  assertion 3: differing files with no recorded sync are also a conflict"; assert_output "$expected"
cp $s $t
$sym -t home -v dotfiles/synctest > log 2>&1
echo "  assertion 4: resolving by hand lets sync proceed and records the marker"
[ ! -s log ] && [ -f $m ] || nfailed=$((nfailed + 1))


printf '\n18: --sync DIR adds a synced directory; a source without the directory is left alone\n'
mkdir -p dotfiles/synctest/.config/synced
echo a > dotfiles/synctest/.config/synced/a.txt
$sym -t home -v --sync .config/synced dotfiles/synctest > log 2>&1
expected="MKDIRS: home/.config/synced
PUSH: home/.config/synced/a.txt <- dotfiles/synctest/.config/synced/a.txt"
echo "  assertion 1: extra directory is synced"; assert_output "$expected"
mkdir -p home/.agents/skills/ghost
echo ghost > home/.agents/skills/ghost/SKILL.md
$sym -t home -v dotfiles/bash > log 2>&1
echo "  assertion 2: target-only skills are not pulled into a source with no .agents/skills"
! grep -q PULL log && [ ! -e dotfiles/bash/.agents ] || nfailed=$((nfailed + 1))
rm -r home/.agents/skills/ghost


printf '\n19: --delete removes identical synced copies and the marker, and refuses modified ones\n'
echo modified > home/.config/synced/a.txt
$sym -t home -v -d --sync .config/synced dotfiles/synctest > log 2>&1 || true
expected="CONFLICT: home/.config/synced/a.txt is not an identical copy of dotfiles/synctest/.config/synced/a.txt, so refusing to remove.
sym will not start until all conflicts are resolved."
echo "  assertion 1: modified copy is a conflict"; assert_output "$expected"
echo "  assertion 2: nothing was removed"
[ -f home/.config/synced/a.txt ] && [ -f $m ] || nfailed=$((nfailed + 1))
cp dotfiles/synctest/.config/synced/a.txt home/.config/synced/a.txt
$sym -t home -v -d --sync .config/synced dotfiles/synctest > log 2>&1
echo "  assertion 3: identical copies and markers are removed; the source is untouched"
[ ! -e home/.config/synced ] && [ ! -e $m ] && [ -f $s ] && [ -f dotfiles/synctest/.config/synced/a.txt ] || nfailed=$((nfailed + 1))
rm -rf home; mkdir home


printf '\n20: a symlink with the link text sym would write is already correct, even if it resolves into the target tree\n'
mkdir -p dotfiles/linktest/.a dotfiles/linktest/.b/real home/.a home/.b/real
echo f > dotfiles/linktest/.b/real/f
ln -s ../.b/real dotfiles/linktest/.a/link
echo g > home/.b/real/g
ln -s ../.b/real home/.a/link
$sym -t home -v dotfiles/linktest > log 2>&1
expected="LINK: home/.b/real/f -> ../../../dotfiles/linktest/.b/real/f"
echo "  assertion 1: matching link text is not a conflict"; assert_output "$expected"
rm home/.a/link; ln -s ../elsewhere home/.a/link
$sym -t home -v dotfiles/linktest > log 2>&1 || true
expected="CONFLICT: home/.a/link already exists. sym cannot create symlinks if there is an existing file.
sym will not start until all conflicts are resolved."
echo "  assertion 2: different link text is still a conflict"; assert_output "$expected"
rm home/.a/link; ln -s ../.b/real home/.a/link
$sym -t home -v -d dotfiles/linktest > log 2>&1
expected="UNLINK: home/.a/link
RMDIR: home/.a
UNLINK: home/.b/real/f"
echo "  assertion 3: delete mode removes the matching link and leaves unrelated files"; assert_output "$expected"
[ -f home/.b/real/g ] || nfailed=$((nfailed + 1))
rm -rf home; mkdir home


printf '\n21: .claude/agents is synced by default, as real files\n'
mkdir -p dotfiles/agenttest/.claude/agents
echo scout > dotfiles/agenttest/.claude/agents/scout.md
$sym -t home -v dotfiles/agenttest > log 2>&1
expected="MKDIRS: home/.claude/agents
PUSH: home/.claude/agents/scout.md <- dotfiles/agenttest/.claude/agents/scout.md"
echo "  assertion 1: source agent definition is pushed"; assert_output "$expected"
echo "  assertion 2: result is a regular file, not a symlink"
[ -f home/.claude/agents/scout.md ] && [ ! -L home/.claude/agents/scout.md ] || nfailed=$((nfailed + 1))
rm -rf home; mkdir home


printf '\n22: --force makes the source win: overwrites differing and non-regular targets, pulls nothing, leaves extras\n'
fs=dotfiles/forcetest/.agents/skills
mkdir -p $fs home/.agents/skills/b.md
echo src > $fs/a.md
echo src-b > $fs/b.md
echo tgt-edit > home/.agents/skills/a.md
echo inside > home/.agents/skills/b.md/inner
echo keep > home/.agents/skills/extra.md
$sym -t home -v dotfiles/forcetest > log 2>&1 || true
echo "  assertion 1: without --force the differing file is a conflict"
grep -q '^CONFLICT: home/.agents/skills/a.md' log || nfailed=$((nfailed + 1))
$sym -t home -v --force dotfiles/forcetest > log 2>&1
expected="DISCARD: home/.agents/skills/b.md/inner (inside a directory replaced by a file)
EXTRA: home/.agents/skills/extra.md
OVERWRITE: home/.agents/skills/a.md <- $fs/a.md (target changed since the last sync)
REPLACE: home/.agents/skills/b.md <- $fs/b.md"
echo "  assertion 2: differing file overwritten, non-regular target replaced and its contents named, extra reported"; assert_output "$expected"
echo "  assertion 3: targets now match the source and are regular files"
cmp -s $fs/a.md home/.agents/skills/a.md && [ -f home/.agents/skills/b.md ] && [ ! -L home/.agents/skills/b.md ] && cmp -s $fs/b.md home/.agents/skills/b.md || nfailed=$((nfailed + 1))
echo "  assertion 4: the target-only file survives and is not pulled into the source"
[ "$(cat home/.agents/skills/extra.md)" = keep ] && [ ! -e $fs/extra.md ] || nfailed=$((nfailed + 1))
rm -rf home; mkdir home


printf '\n23: --delete refuses a target sync root that resolves to its source, and the source survives\n'
ss=dotfiles/rootlink/.agents/skills
mkdir -p $ss/foo home/.agents
echo x > $ss/foo/SKILL.md
ln -s "$(pwd)/$ss" home/.agents/skills
rc=0; $sym -t home -d dotfiles/rootlink > log 2>&1 || rc=$?
echo "  assertion 1: refuses with a nonzero status"
[ "$rc" -ne 0 ] && grep -q 'resolves to its source' log || nfailed=$((nfailed + 1))
echo "  assertion 2: the source file survives"
[ -f $ss/foo/SKILL.md ] || nfailed=$((nfailed + 1))
rm -rf home; mkdir home


printf '\n24: a symlinked directory inside a synced directory is a conflict, never written through\n'
mkdir -p dotfiles/linkdir/.agents/skills/ext outside/data home/.agents/skills
echo f > dotfiles/linkdir/.agents/skills/ext/data
echo important > outside/data/db
ln -s "$(pwd)/outside" home/.agents/skills/ext
for flag in '' --force; do
	rc=0; $sym -t home $flag dotfiles/linkdir > log 2>&1 || rc=$?
	echo "  assertion: conflict and nothing written through the link (${flag:-no flag})"
	[ "$rc" -ne 0 ] && grep -q 'CONFLICT: .*ext/data.*symlink' log && [ "$(cat outside/data/db)" = important ] || nfailed=$((nfailed + 1))
done
rm -rf home outside; mkdir home


printf '\n25: a failed copy exits nonzero and does not advance the sync marker\n'
fk=dotfiles/failtest/.agents/skills
mkdir -p $fk home/.agents/skills
echo new > $fk/a.md
echo old > home/.agents/skills/a.md
chmod 444 home/.agents/skills/a.md
touch -t 202001010000 home/.agents/skills/.sym-synced
touch -t 202101010000 reference-time
rc=0; $sym -t home --force dotfiles/failtest > log 2>&1 || rc=$?
echo "  assertion 1: nonzero exit"
[ "$rc" -ne 0 ] || nfailed=$((nfailed + 1))
echo "  assertion 2: the marker was not advanced"
[ ! home/.agents/skills/.sym-synced -nt reference-time ] || nfailed=$((nfailed + 1))
chmod 644 home/.agents/skills/a.md
rm -rf home reference-time; mkdir home


printf '\n26: a target edit in the same second as the marker still counts as changed\n'
tt=dotfiles/tietest/.agents/skills
mkdir -p $tt home/.agents/skills
echo src > $tt/a.md
echo tgt > home/.agents/skills/a.md
touch -t 202001010000 home/.agents/skills/.sym-synced
touch -r home/.agents/skills/.sym-synced home/.agents/skills/a.md
touch -t 202101010000 $tt/a.md
rc=0; $sym -t home -v dotfiles/tietest > log 2>&1 || rc=$?
expected="CONFLICT: home/.agents/skills/a.md and $tt/a.md differ and sync cannot tell which side is newer (both changed since the last sync, or none is recorded).
sym will not start until all conflicts are resolved."
echo "  assertion 1: tie with the marker is a conflict, not a silent overwrite"; assert_output "$expected"
echo "  assertion 2: the target edit survives"
[ "$(cat home/.agents/skills/a.md)" = tgt ] || nfailed=$((nfailed + 1))
rm -rf home; mkdir home


printf '\n27: --force names an overwrite of a target changed since the last sync, even without -v\n'
ow=dotfiles/owtest/.agents/skills
mkdir -p $ow home/.agents/skills
echo src > $ow/a.md
echo src > $ow/b.md
echo edited > home/.agents/skills/a.md
echo old > home/.agents/skills/b.md
touch -t 202001010000 home/.agents/skills/.sym-synced
touch -t 201912310000 home/.agents/skills/b.md
$sym -t home --force dotfiles/owtest > log 2>&1
expected="OVERWRITE: home/.agents/skills/a.md <- $ow/a.md (target changed since the last sync)"
echo "  assertion 1: only the edited file is named; the untouched one is silent"; assert_output "$expected"
echo "  assertion 2: both targets now match the source"
cmp -s $ow/a.md home/.agents/skills/a.md && cmp -s $ow/b.md home/.agents/skills/b.md || nfailed=$((nfailed + 1))
rm -rf home; mkdir home


printf '\n28: --sync rejects paths that are not plain relative directories\n'
for bad in . ./x a//b .. ../x x/..; do
	rc=0; $sym -t home --sync "$bad" dotfiles/bash > log 2>&1 || rc=$?
	echo "  assertion: rejects '$bad'"
	[ "$rc" -ne 0 ] && grep -q 'must be a relative path' log || nfailed=$((nfailed + 1))
done
rc=0; $sym -t home --dry-run --sync foo..bar dotfiles/bash > log 2>&1 || rc=$?
echo "  assertion: accepts a name that merely contains two dots"
[ "$rc" -eq 0 ] || nfailed=$((nfailed + 1))
rm -rf home; mkdir home


printf '\n29: a symlink in a source sync dir is a conflict; a target-only symlink is left alone\n'
sl=dotfiles/symtest/.agents/skills
mkdir -p $sl home/.agents/skills shared
echo s > shared/ref.md
ln -s ../../../../shared/ref.md $sl/ref.md
rc=0; $sym -t home dotfiles/symtest > log 2>&1 || rc=$?
echo "  assertion 1: a source symlink is a conflict, not silently dropped"
[ "$rc" -ne 0 ] && grep -q '^CONFLICT: .*ref.md' log || nfailed=$((nfailed + 1))
rm $sl/ref.md
echo a > $sl/a.md
ln -s "$(pwd)/shared" home/.agents/skills/ext
$sym -t home -v dotfiles/symtest > log 2>&1
expected="PUSH: home/.agents/skills/a.md <- $sl/a.md"
echo "  assertion 2: a target-only symlink is neither a conflict nor touched"; assert_output "$expected"
[ -L home/.agents/skills/ext ] && [ -f shared/ref.md ] || nfailed=$((nfailed + 1))
rm -rf home shared; mkdir home


printf '\n30: --force names the target-only files discarded with a replaced directory\n'
dc=dotfiles/discardtest/.agents/skills
mkdir -p $dc home/.agents/skills/notes
echo n > $dc/notes
echo mine > home/.agents/skills/notes/mine.md
$sym -t home -v --force dotfiles/discardtest > log 2>&1
expected="DISCARD: home/.agents/skills/notes/mine.md (inside a directory replaced by a file)
REPLACE: home/.agents/skills/notes <- $dc/notes"
echo "  assertion 1: the discarded file is named"; assert_output "$expected"
rm -rf home; mkdir home


printf '\n31: an existing symlink with the right text but a dangling target is still a conflict\n'
mkdir -p dotfiles/dangle/.a home/.a
ln -s ../x/y dotfiles/dangle/.a/link
ln -s ../x/y home/.a/link
rc=0; $sym -t home dotfiles/dangle > log 2>&1 || rc=$?
expected="CONFLICT: home/.a/link already exists. sym cannot create symlinks if there is an existing file.
sym will not start until all conflicts are resolved."
echo "  assertion 1: dangling same-text link is rejected"; assert_output "$expected"
rm -rf home; mkdir home


printf '\ntesting finished.\n'
if [ "$nfailed" -gt 0 ]; then die "failed ${nfailed} assertions"; fi

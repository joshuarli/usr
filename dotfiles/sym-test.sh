#!/bin/sh

set -e
die () { >&2 printf %s\\n "$1"; exit 1; }

script_dir=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
repo_root=$(CDPATH='' cd -- "$script_dir/.." && pwd)
work_root="$repo_root/.work/tmp"
mkdir -p "$work_root"
tmp="$(mktemp -d "$work_root/sym.XXXXXX")" || die 'mktemp failed'
trap 'rm -rf "$tmp"' 0
trap 'exit 130' 1 2 3 15

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


printf '\n12: a symlink with the link text sym would write is already correct, even if it resolves into the target tree\n'
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


printf '\n13: an existing symlink with the right text but a dangling target is still a conflict\n'
mkdir -p dotfiles/dangle/.a home/.a
ln -s ../x/y dotfiles/dangle/.a/link
ln -s ../x/y home/.a/link
rc=0; $sym -t home dotfiles/dangle > log 2>&1 || rc=$?
expected="CONFLICT: home/.a/link already exists. sym cannot create symlinks if there is an existing file.
sym will not start until all conflicts are resolved."
echo "  assertion 1: dangling same-text link is rejected"; assert_output "$expected"
rm -rf home; mkdir home



printf '\n14: a target directory that links into the source is a conflict in both modes, and the source survives\n'
mkdir -p dotfiles/viaparent/.tool/agent home/.tool
echo cfg > dotfiles/viaparent/.tool/agent/settings.json
ln -s ../x dotfiles/viaparent/.tool/agent/AGENTS.md
ln -s "$(pwd)/dotfiles/viaparent/.tool/agent" home/.tool/agent
for flag in "" -d; do
	rc=0; $sym -t home $flag dotfiles/viaparent > log 2>&1 || rc=$?
	echo "  assertion: mode '$flag' refuses"
	[ "$rc" -ne 0 ] && grep -q 'passes through a symlinked directory' log || nfailed=$((nfailed + 1))
done
echo "  assertion: the source files survive"
[ -f dotfiles/viaparent/.tool/agent/settings.json ] && [ -L dotfiles/viaparent/.tool/agent/AGENTS.md ] || nfailed=$((nfailed + 1))
rm -rf home; mkdir home


printf '\n15: delete mode never removes directories above the target\n'
mkdir -p dotfiles/rmtest/.a outer/keep/home
echo x > dotfiles/rmtest/.a/f
$sym -t outer/keep/home dotfiles/rmtest > /dev/null
$sym -t outer/keep/home -d dotfiles/rmtest > /dev/null
echo "  assertion 1: the target directory survives"
[ -d outer/keep/home ] || nfailed=$((nfailed + 1))
rm -rf outer


printf '\n16: ignored files are not linked, and names with non-ASCII characters are linked correctly\n'
mkdir -p dotfiles/gi/.cfg
echo a > dotfiles/gi/.cfg/keep
echo b > dotfiles/gi/.cfg/skip.log
echo c > "dotfiles/gi/.cfg/café"
printf 'skip.log\n' > dotfiles/gi/.gitignore
$sym -t home dotfiles/gi > log 2>&1
echo "  assertion 1: an ignored file outside a whole-directory link is skipped"
[ -L home/.cfg/keep ] && [ ! -e home/.cfg/skip.log ] || nfailed=$((nfailed + 1))
echo "  assertion 2: the non-ASCII name is linked under its real name"
[ -e "home/.cfg/café" ] || nfailed=$((nfailed + 1))
rm -rf home; mkdir home


printf '\n17: a source outside Git works, and honors .sym-dir\n'
ng="$(mktemp -d "$work_root/sym-nongit.XXXXXX")"
mkdir -p "$ng/src/.a" "$ng/src/d" "$ng/home"
echo x > "$ng/src/.a/f"; touch "$ng/src/d/.sym-dir"; echo y > "$ng/src/d/g"
mkdir -p "$ng/no-git"
cat > "$ng/no-git/git" <<'EOF'
#!/bin/sh
exit 1
EOF
chmod +x "$ng/no-git/git"
(cd "$ng" && PATH="$ng/no-git:$PATH" $sym -t home src > /dev/null 2>&1)
echo "  assertion 1: file link and directory link are both made"
[ -L "$ng/home/.a/f" ] && [ -L "$ng/home/d" ] && [ "$(find "$ng/home" -type l | wc -l | tr -d ' ')" -eq 2 ] || nfailed=$((nfailed + 1))
rm -rf "$ng"


printf '\n18: a .sym-dir nested in another one is skipped\n'
mkdir -p dotfiles/nest/.a/inner
touch dotfiles/nest/.a/.sym-dir dotfiles/nest/.a/inner/.sym-dir
echo x > dotfiles/nest/.a/inner/f
$sym -t home -v dotfiles/nest > log 2>&1
expected="SKIP (nested in another symlink-dir): dotfiles/nest/.a/inner
LINK: home/.a -> ../dotfiles/nest/.a"
echo "  assertion 1: only the outer directory is linked"; assert_output "$expected"


printf '\n19: delete mode removes a matching directory link and refuses a foreign one\n'
$sym -t home -v -d dotfiles/nest > log 2>&1
expected="SKIP (nested in another symlink-dir): dotfiles/nest/.a/inner
UNLINK: home/.a"
echo "  assertion 1: the matching link is removed"; assert_output "$expected"
mkdir -p home; ln -s ../elsewhere home/.a
rc=0; $sym -t home -d dotfiles/nest > log 2>&1 || rc=$?
echo "  assertion 2: a link that points elsewhere is refused"
[ "$rc" -ne 0 ] && grep -q 'does not point to the expected destination' log && [ -L home/.a ] || nfailed=$((nfailed + 1))
rm -rf home; mkdir home


printf '\n20: a target reached through a symlink gets links that resolve\n'
mkdir -p real/tg dotfiles/viasym/.f
echo x > dotfiles/viasym/.f/g
ln -s real/tg tglink
$sym -t tglink dotfiles/viasym > /dev/null
echo "  assertion 1: the link resolves"
[ -e tglink/.f/g ] || nfailed=$((nfailed + 1))
rm -rf real tglink


printf '\n21: a dangling link is valid when its target is a planned whole-directory link\n'
mkdir -p dotfiles/planned/.agents/skills dotfiles/planned/.claude home/.claude
touch dotfiles/planned/.agents/skills/.sym-dir
echo x > dotfiles/planned/.agents/skills/keep
ln -s ../.agents/skills dotfiles/planned/.claude/skills
ln -s ../.agents/skills home/.claude/skills
$sym -t home dotfiles/planned > log 2>&1
echo "  assertion 1: the existing link resolves after the planned target is linked"
[ -e home/.claude/skills/keep ] && [ -L home/.agents/skills ] || nfailed=$((nfailed + 1))
rm -rf home


printf '\n22: newline-split paths cannot escape the target in either mode\n'
newline=$(printf 'x\ny')
escaped_source="escape/prefixx${newline}yfoo/../../outside-source"
escaped_target=escape/target
escaped_destination=escape/outside-source/payload
mkdir -p "escape/prefixx${newline}yfoo" "$escaped_target" outside-source
printf '%s\n' payload > outside-source/payload
mkdir -p no-git
cat > no-git/git <<'EOF'
#!/bin/sh
exit 1
EOF
chmod +x no-git/git
rc=0
PATH="$(pwd)/no-git:$PATH" "$sym" -t "$escaped_target" "$escaped_source" > log 2>&1 || rc=$?
echo "  assertion 1: linking rejects newline-split traversal fragments"
[ "$rc" -ne 0 ] && grep -Fq 'is not a safe source path' log && [ ! -L "$escaped_destination" ] || nfailed=$((nfailed + 1))
if [ -L "$escaped_destination" ]; then rm "$escaped_destination"; fi
mkdir -p "$escaped_target/yyfoo" escape/outside-source
ln -s "$(pwd)/outside-source/payload" "$escaped_destination"
rc=0
PATH="$(pwd)/no-git:$PATH" "$sym" -t "$escaped_target" -d "$escaped_source" > log 2>&1 || rc=$?
echo "  assertion 2: delete mode rejects fragments and preserves a link outside the target"
[ "$rc" -ne 0 ] && grep -Fq 'is not a safe source path' log && [ -L "$escaped_destination" ] || nfailed=$((nfailed + 1))
escaped_directory_name="outside-marker-$$"
escaped_directory_source="escape-dir/prefixx${newline}yfoo/../../${escaped_directory_name}"
escaped_directory_target=escape-dir/target
escaped_directory_destination="escape-dir/${escaped_directory_name}"
mkdir -p "escape-dir/prefixx${newline}yfoo" "$escaped_directory_target" "$escaped_directory_name"
touch "$escaped_directory_name/.sym-dir"
rc=0
PATH="$(pwd)/no-git:$PATH" "$sym" -t "$escaped_directory_target" "$escaped_directory_source" > log 2>&1 || rc=$?
echo "  assertion 3: newline-split .sym-dir paths cannot escape the target"
[ "$rc" -ne 0 ] && grep -Fq 'is not a safe source path' log && [ ! -L "$escaped_directory_destination" ] || nfailed=$((nfailed + 1))


printf '\ntesting finished.\n'
if [ "$nfailed" -gt 0 ]; then die "failed ${nfailed} assertions"; fi

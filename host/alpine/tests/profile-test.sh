#!/bin/sh
set -eu
root=$(CDPATH='' cd -P -- "$(dirname -- "$0")/.." && pwd)
scratch=$root/.work/tmp/profile-test-$$
home=$scratch/home
stubs=$scratch/stubs
umask 077
mkdir -p "$home/.local/bin" "$stubs"
cleanup() {
	rm -rf "$scratch"
}
trap cleanup 0 HUP INT TERM

cat > "$stubs/tty" <<'EOF'
#!/bin/sh
printf '%s\n' /dev/tty2
EOF
cat > "$home/.local/bin/ish-path-probe" <<'EOF'
#!/bin/sh
exit 0
EOF
cat > "$home/.local/bin/ish" <<'EOF'
#!/bin/sh
command -v ish-path-probe >/dev/null
EOF
chmod 0755 "$stubs/tty" "$home/.local/bin/ish-path-probe" "$home/.local/bin/ish"
if ! HOME=$home PATH=$stubs /bin/sh -ic '. "$1"' profile "$root/config/profile.sh" >/dev/null 2>&1; then
	printf '%s\n' 'profile-test: interactive ish cannot find user-local tools' >&2
	exit 1
fi

#!/bin/sh
set -eu
root=$(CDPATH='' cd -P -- "$(dirname -- "$0")/.." && pwd)
usr_root=$(CDPATH='' cd -P -- "$root/../.." && pwd)
scratch=$usr_root/.work/tmp/profile-test-$$
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
if ! HOME=$home PATH=$stubs /bin/sh -ic ". \"\$1\"" profile "$root/config/profile.sh" >/dev/null 2>&1; then
	printf '%s\n' 'profile-test: interactive ish cannot find user-local tools' >&2
	exit 1
fi

printf "#!/bin/sh\ncase \$1 in -m) echo x86_64 ;; *) echo Linux ;; esac\n" > "$stubs/uname"
chmod 0755 "$stubs/uname"
PATH="$stubs:$PATH"; export PATH
mkdir -p "$usr_root/.work/tmp"
default_tools=$(DL_PROFILE=server sh "$usr_root/sync" list)
printf '%s\n' "$default_tools" | grep -qx shuck
[ "$(python3 -I "$usr_root/tools/sync/main.py" launchers shuck lz gluon nodejs ffmpeg)" = "$(printf 'shuck shellcheck\nlz less\ngluon meson ninja gluon-build\nnodejs node npm\nffmpeg ffmpeg ffprobe')" ]
default_tools="$default_tools lz gluon nodejs ffmpeg"
user=fixture
export usr_root home default_tools user
awk '/^tool_launchers=/ {copy=1} /^if \[ -n "\$missing_tools" \]/ {copy=0} copy {print}' "$root/install.sh" > "$scratch/install-loop"
awk '/^tool_launchers=/ {copy=1} /^case " \$default_tools " in$/ {copy=0} copy {print}' "$root/verify.sh" > "$scratch/verify-loop"
for tool in $default_tools; do
	[ "$tool" = agy ] && continue
	launchers=$(python3 -I "$usr_root/tools/sync/main.py" launchers "$tool" | cut -d' ' -f2-)
	for launcher in $launchers; do
		printf '#!/bin/sh\nexit 0\n' > "$home/.local/bin/$launcher"
		chmod 0755 "$home/.local/bin/$launcher"
	done
done
[ ! -e "$home/.local/bin/shuck" ]
check_loops() {
	sh -c 'die() { exit 1; }; as_user() { sh -c "$1"; }; . "$1"; printf "%s\n" "$missing_tools"' sh "$scratch/install-loop" > "$scratch/install-result"
	sh -c 'failures=0; check() { shift; "$@" || failures=$((failures + 1)); }; fail() { failures=$((failures + 1)); }; . "$1"; exit "$failures"' sh "$scratch/verify-loop"
}
check_loops
[ ! -s "$scratch/install-result" ] || [ "$(cat "$scratch/install-result")" = '' ]
for tool in $default_tools; do
	[ "$tool" = agy ] && continue
	launchers=$(python3 -I "$usr_root/tools/sync/main.py" launchers "$tool" | cut -d' ' -f2-)
	for launcher in $launchers; do
		mv "$home/.local/bin/$launcher" "$scratch/removed"
		if default_tools="$tool" check_loops; then
			printf 'profile-test: missing %s accepted\n' "$launcher" >&2; exit 1
		fi
		case " $(cat "$scratch/install-result") " in
			*" $tool "*) ;;
			*) printf 'profile-test: %s did not select %s\n' "$launcher" "$tool" >&2; exit 1 ;;
		esac
		mv "$scratch/removed" "$home/.local/bin/$launcher"
	done
done
printf 'profile-test: launcher mappings passed\n'

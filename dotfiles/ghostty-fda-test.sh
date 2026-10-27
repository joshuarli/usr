#!/bin/sh
# Tests for ghostty-fda-check: granted, missing, unknown, and absent-app
# verdicts, the settings pane opening, and its --no-open opt-outs.

script="${PWD}/base/.local/bin/ghostty-fda-check"
nfailed=0

mkdir -p "${PWD}/../.work/tmp"
scratch=$(mktemp -d "${PWD}/../.work/tmp/ghostty-fda.XXXXXX") || exit 1
trap 'rm -rf "$scratch"' 0
trap 'exit 1' HUP INT TERM

mock_bin="$scratch/bin"
fixture_home="$scratch/home"
empty_home="$scratch/empty-home"
apps="$scratch/Applications"
open_capture="$scratch/opened"
mkdir -p "$mock_bin" "$fixture_home" "$empty_home" "$apps/Ghostty.app/Contents"
printf '%s\n' 'mock plist' > "$apps/Ghostty.app/Contents/Info.plist"
: > "$open_capture"

cat > "$mock_bin/plutil" <<'EOF'
#!/bin/sh
printf '%s\n' "${GHOSTTY_FDA_TEST_BUNDLE-com.mitchellh.ghostty}"
EOF
cat > "$mock_bin/open" <<'EOF'
#!/bin/sh
printf '%s\n' "$@" >> "$GHOSTTY_FDA_TEST_OPEN_CAPTURE"
EOF
chmod +x "$mock_bin/plutil" "$mock_bin/open"

granted="$scratch/granted.txt"
denied="$scratch/denied.txt"
printf 'probe\n' > "$granted"
printf 'probe\n' > "$denied"
chmod 000 "$denied"

extra_args=
# check <want exit> <label> <want text> <want open: yes|no> [VAR=value ...]
check() {
    want_exit=$1; label=$2; want_text=$3; want_open=$4; shift 4
    : > "$open_capture"
    # shellcheck disable=SC2086
    out=$(env PATH="$mock_bin:/usr/bin:/bin" GHOSTTY_APPLICATIONS_DIR="$apps" \
        HOME="$fixture_home" GHOSTTY_FDA_TEST_OPEN_CAPTURE="$open_capture" \
        "$@" sh "$script" $extra_args 2>&1)
    got=$?
    case "$out" in *"$want_text"*) found=yes ;; *) found=no ;; esac
    if [ "$want_open" = yes ]; then
        if grep -Fq 'Privacy_AllFiles' "$open_capture"; then opened=yes; else opened=no; fi
    elif [ -s "$open_capture" ]; then
        opened=no
    else
        opened=yes
    fi
    if [ "$got" = "$want_exit" ] && [ "$found" = yes ] && [ "$opened" = yes ]; then
        printf 'ok: %s\n' "$label"
    else
        printf 'FAIL: %s (wanted exit %s with "%s" and open=%s, got exit %s open-capture-bytes=%s: %s)\n' \
            "$label" "$want_exit" "$want_text" "$want_open" "$got" "$(wc -c < "$open_capture")" "$out"
        nfailed=$((nfailed + 1))
    fi
}

if [ -d /Applications/Ghostty.app ]; then
    printf 'skip: a real /Applications/Ghostty.app shadows the missing-app case\n'
else
    check 2 'a missing app reports the install hint' 'not installed' no \
        GHOSTTY_APPLICATIONS_DIR="$scratch/nowhere" HOME="$empty_home"
fi

check 0 'a readable probe means granted' 'granted' no \
    TERM_PROGRAM=ghostty GHOSTTY_FDA_PROBE="$granted"

if [ "$(id -u)" -eq 0 ]; then
    printf 'skip: unreadable-probe cases need a non-root user\n'
else
    check 1 'an unreadable probe means missing and opens settings' 'missing' yes \
        TERM_PROGRAM=ghostty GHOSTTY_FDA_PROBE="$denied"
    check 1 'outside Ghostty the verdict warns about the terminal' 'not ghostty' yes \
        TERM_PROGRAM= GHOSTTY_FDA_PROBE="$denied"
    extra_args='--no-open'
    check 1 '--no-open suppresses the settings pane' 'missing' no \
        TERM_PROGRAM=ghostty GHOSTTY_FDA_PROBE="$denied"
    extra_args=
    check 1 'GHOSTTY_FDA_NO_OPEN=1 suppresses the settings pane' 'missing' no \
        TERM_PROGRAM=ghostty GHOSTTY_FDA_PROBE="$denied" GHOSTTY_FDA_NO_OPEN=1
fi

check 3 'absent probes are unknown and open settings' 'could not confirm' yes \
    TERM_PROGRAM=ghostty HOME="$empty_home"

check 0 'an empty plutil result falls back to the Ghostty bundle id' 'com.mitchellh.ghostty' no \
    TERM_PROGRAM=ghostty GHOSTTY_FDA_PROBE="$granted" GHOSTTY_FDA_TEST_BUNDLE=

extra_args='--help'
check 0 '--help prints usage' 'usage: ghostty-fda-check' no \
    TERM_PROGRAM=ghostty
extra_args=

echo 'testing finished.'
[ "$nfailed" -eq 0 ]

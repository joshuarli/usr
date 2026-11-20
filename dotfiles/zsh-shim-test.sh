#!/bin/sh
# Tests for the zsh and bash shims: they exec the real shell with unchanged arguments, refuse to run a command when no shell exists, and keep the caller's PATH order.

shim="${PWD}/darwin/.local/bin/zsh"
nfailed=0

mkdir -p "${PWD}/../.work/tmp"
scratch=$(mktemp -d "${PWD}/../.work/tmp/zsh-shim.XXXXXX") || exit 1
trap 'rm -rf "$scratch"' 0
mkdir -p "$scratch/config/sh" "$scratch/empty" "$scratch/withzsh"
: > "$scratch/config/sh/config.sh"
cat > "$scratch/withzsh/zsh" <<'EOF'
#!/bin/sh
printf 'real-zsh'
printf ' [%s]' "$@"
EOF
chmod +x "$scratch/withzsh/zsh"

# expect <description> <wanted exit> <wanted stdout> <PATH dir> <shim args...>
expect () {
    description=$1 wanted_status=$2 wanted_out=$3 dir=$4
    shift 4
    out=$(XDG_CONFIG_HOME="$scratch/config" PATH="$dir" "$shim" "$@" 2>/dev/null)
    status=$?
    if [ "$status" = "$wanted_status" ] && [ "$out" = "$wanted_out" ]; then
        printf 'ok: %s\n' "$description"
    else
        printf 'FAIL: %s (wanted %s %s, got %s %s)\n' "$description" "$wanted_status" "$wanted_out" "$status" "$out"
        nfailed=$((nfailed + 1))
    fi
}

expect 'a real zsh receives the arguments unchanged' 0 'real-zsh [-c] [-l] [echo hi]' "$scratch/withzsh" -c -l 'echo hi'
expect 'a command is refused when no zsh exists' 127 '' "$scratch/empty" -c 'echo ran'
expect 'a login command is refused when no zsh exists' 127 '' "$scratch/empty" -lc 'echo ran'

# The shared config must not move user directories ahead of a caller's PATH.
mkdir -p "$scratch/home/.local/bin" "$scratch/first"
for name in zsh bash; do
    printf '#!/bin/sh\nprintf %%s "${PATH%%%%:*}"\n' > "$scratch/first/$name"
    chmod +x "$scratch/first/$name"
done
managed=$(HOME="$scratch/home" PATH=/usr/bin:/bin sh -c '. "$1"; printf %s "$PATH"' sh "${PWD}/base/.config/sh/config.sh")
for shell in "${PWD}/darwin/.local/bin/zsh" "${PWD}/base/.local/bin/bash"; do
    out=$(HOME="$scratch/home" XDG_CONFIG_HOME="${PWD}/base/.config" PATH="$scratch/first:$managed" "$shell" -c : 2>/dev/null)
    if [ "$out" = "$scratch/first" ]; then
        printf 'ok: %s keeps the caller PATH order\n' "${shell##*/}"
    else
        printf 'FAIL: %s moved %s ahead of the caller PATH\n' "${shell##*/}" "$out"
        nfailed=$((nfailed + 1))
    fi
done

# The shared config must replace TERM values that have no terminfo entry.
expect_term () {
    description=$1 given=$2 wanted=$3
    out=$(HOME="$scratch/home" TERM="$given" sh -c '. "$1"; printf %s "${TERM-}"' sh "${PWD}/base/.config/sh/config.sh")
    if [ "$out" = "$wanted" ]; then
        printf 'ok: %s\n' "$description"
    else
        printf 'FAIL: %s (wanted %s, got %s)\n' "$description" "$wanted" "$out"
        nfailed=$((nfailed + 1))
    fi
}

expect_term 'network is replaced with a usable terminal' network xterm-256color
expect_term 'a valid terminal is left alone' xterm-256color xterm-256color

echo "testing finished."
[ "$nfailed" -eq 0 ]

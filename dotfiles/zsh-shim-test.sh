#!/bin/sh
# Tests for the zsh shim: it execs the real zsh with unchanged arguments, and refuses to run a command when no zsh exists.

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

echo "testing finished."
[ "$nfailed" -eq 0 ]

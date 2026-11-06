#!/bin/sh

bin="${PWD}/base/.local/bin"
root=$(CDPATH='' cd -- "${PWD}/.." && pwd)
nfailed=0

mkdir -p "$root/.work/tmp"
scratch=$(mktemp -d "$root/.work/tmp/agent-memory-launchers.XXXXXX") || exit 1
trap 'rm -rf "$scratch"' 0
venv="$scratch/venv with space"
mkdir -p "$venv/bin" "$scratch/cwd" "$scratch/links" "$scratch/home"
for command in agent-learn agent-sessions agent-sessions-serve python; do
    cat > "$venv/bin/$command" <<EOF
#!/bin/sh
printf '%s' "$command"
printf ' [%s]' "\$@"
printf ' cwd=%s stdin=%s' "\$(pwd)" "\$(cat)"
exit \${FAKE_STATUS:-0}
EOF
    chmod +x "$venv/bin/$command"
done
ln -s "$bin/skill-usage" "$scratch/links/skill-usage"

pass () { printf 'ok: %s\n' "$1"; }
fail () { printf 'FAIL: %s (%s)\n' "$1" "$2"; nfailed=$((nfailed + 1)); }

expect () {
    description=$1 wanted_status=$2 wanted_out=$3 launcher=$4
    shift 4
    out=$(cd "$scratch/cwd" && printf "input" | env -i HOME="$scratch/home" PATH=/usr/bin:/bin AGENT_MEMORY_VENV="$venv" FAKE_STATUS="$wanted_status" "$launcher" "$@" 2>/dev/null)
    status=$?
    if [ "$status" = "$wanted_status" ] && [ "$out" = "$wanted_out" ]; then pass "$description"; else fail "$description" "wanted $wanted_status $wanted_out, got $status $out"; fi
}

for command in agent-learn agent-sessions agent-sessions-serve; do
    expect "$command passes arguments, cwd, and stdin unchanged" 0 "$command [recall] [two words] [] cwd=$scratch/cwd stdin=input" "$bin/$command" recall 'two words' ''
    expect "$command keeps the exit status" 3 "$command [status] cwd=$scratch/cwd stdin=input" "$bin/$command" status
    err=$(env -i HOME="$scratch/home" PATH=/usr/bin:/bin "$bin/$command" status 2>&1 >/dev/null)
    status=$?
    case "$status:$err" in
        "127:$command: $scratch/home/d/agent-memory/.venv/bin/$command is not installed;"*) pass "$command names the missing default environment" ;;
        *) fail "$command names the missing default environment" "$status $err" ;;
    esac
done
expect 'skill-usage runs its script isolated with the environment python through a symlink' 0 "python [-I] [$root/tools/skill-usage/src/skill_usage.py] [--days] [7] cwd=$scratch/cwd stdin=input" "$scratch/links/skill-usage" --days 7
err=$(env -i HOME="$scratch/home" PATH=/usr/bin:/bin AGENT_MEMORY_VENV="$scratch/missing" "$bin/skill-usage" selftest 2>&1 >/dev/null)
case "$?:$err" in
    "127:skill-usage: $scratch/missing/bin/python is not installed;"*) pass 'skill-usage names a missing environment' ;;
    *) fail 'skill-usage names a missing environment' "$err" ;;
esac

if command -v plutil >/dev/null 2>&1; then
    for template in "$PWD"/launchd/com.josh.agent-*.plist.in; do
        name=$(basename "$template" .in)
        sed -e "s|@@HOME@@|$scratch/home|g" -e "s|@@STATE_DIR@@|$scratch/state|g" -e 's|@@REMOTE@@|cloudflare|g' "$template" > "$scratch/$name"
        if plutil -lint "$scratch/$name" >/dev/null; then pass "$name renders to a valid plist"; else fail "$name renders to a valid plist" lint; fi
    done
fi

echo "testing finished."
[ "$nfailed" -eq 0 ]

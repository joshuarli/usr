#!/bin/sh
# Tests for worker-campaign: sessions are discovered from bridge records under
# each root, terminal evidence matches worker-watch, and acks persist.

campaign="${PWD}/base/.local/bin/worker-campaign"
nfailed=0

mkdir -p "${PWD}/../.work/tmp"
scratch=$(mktemp -d "${PWD}/../.work/tmp/worker-campaign.XXXXXX") || exit 1
scratch=$(CDPATH='' cd -- "$scratch" && pwd -P) || exit 1
home="$scratch/home"
mkdir -p "$home"
XDG_STATE_HOME="$home/state"
export XDG_STATE_HOME
trap 'kill "$alive" ${worker:+"$worker"} ${waiter:+"$waiter"} 2>/dev/null; rm -rf "$scratch"' 0

# expect <wanted exit> <description> <text the output must contain> [campaign args...]
expect () {
    wanted=$1
    description=$2
    needle=$3
    shift 3
    out=$(sh "$campaign" "$@" 2>&1)
    got=$?
    case $out in *"$needle"*) ;; *) got="$got-without-$needle" ;; esac
    if [ "$got" = "$wanted" ]; then
        printf 'ok: %s\n' "$description"
    else
        printf 'FAIL: %s (wanted %s, got %s): %s\n' "$description" "$wanted" "$got" "$out"
        nfailed=$((nfailed + 1))
    fi
}

# require <description> <text the last output must contain>
require () {
    case $out in
        *"$2"*) printf 'ok: %s\n' "$1" ;;
        *) printf 'FAIL: %s: %s\n' "$1" "$out"; nfailed=$((nfailed + 1)) ;;
    esac
}

# forbid <description> <text the last output must NOT contain>
forbid () {
    case $out in
        *"$2"*) printf 'FAIL: %s: %s\n' "$1" "$out"; nfailed=$((nfailed + 1)) ;;
        *) printf 'ok: %s\n' "$1" ;;
    esac
}

# session <root> <id> <pid or empty> <backend> <title> [continuations] [steers]
session () {
    root=$1
    bridge="$root/.work/worker-bridge"
    mkdir -p "$bridge"
    budgets=
    if [ -n "${6:-}" ]; then budgets="$budgets,\"continuations\":$6"; fi
    if [ -n "${7:-}" ]; then budgets="$budgets,\"steers\":$7"; fi
    if [ -n "$3" ]; then
        printf '{"id":"%s","title":"%s","cwd":"%s","backend":"%s","command_run":{"pid":%s,"output":"%s/%s.ndjson","errors":"%s/%s.stderr"},"attempts":1%s}\n' \
            "$2" "$5" "$root" "$4" "$3" "$bridge" "$2" "$bridge" "$2" "$budgets" > "$bridge/$2.json"
    else
        printf '{"id":"%s","title":"%s","cwd":"%s","backend":"%s","attempts":1%s}\n' \
            "$2" "$5" "$root" "$4" "$budgets" > "$bridge/$2.json"
    fi
}

# log <root> <id> <lines>
log () {
    printf '%s\n' "$3" > "$1/.work/worker-bridge/$2.ndjson"
}

repo_a="$scratch/repo-a"
repo_b="$scratch/repo-b"
mkdir -p "$repo_a/.work/worker-bridge" "$repo_b/.work/worker-bridge"

sleep 600 &
alive=$!
sh -c 'exit 0' &
gone=$!
wait "$gone"

prefix=usrw_01234567-89ab-cdef-0123-456789abcdef

session "$repo_a" "${prefix}01" "$alive" command-code "Alpha lane"
log "$repo_a" "${prefix}01" '{"type":"result","subtype":"success","result":"first done"}'
session "$repo_a" "${prefix}02" "$alive" command-code "Beta lane"
log "$repo_a" "${prefix}02" '{"type":"result","subtype":"error","result":"compile failed"}'
session "$repo_a" "${prefix}03" "$alive" command-code "Gamma lane"
log "$repo_a" "${prefix}03" '{"type":"result","subtype":"max_turns","result":"ran out of turns"}'
session "$repo_a" "${prefix}04" "$gone" command-code "Delta lane"
log "$repo_a" "${prefix}04" '{"type":"event","event":{"type":"tool_queued","toolName":"shell_command","input":{"description":"Download kernel"}}}'
session "$repo_a" "${prefix}05" "$alive" command-code "Epsilon running"
log "$repo_a" "${prefix}05" '{"type":"event","event":{"type":"tool_queued","toolName":"shell_command","input":{"description":"Still working"}}}'
session "$repo_b" "${prefix}06" "$alive" command-code "Zeta other repo"
log "$repo_b" "${prefix}06" '{"type":"result","subtype":"success","result":"second repo done"}'

expect 0 "wait discovers sessions under both roots" "${prefix}01 succeeded $repo_a Alpha lane" wait "$repo_a" "$repo_b"
require "wait reports the failed lane" "${prefix}02 failed $repo_a Beta lane"
require "wait reports the turn_limit lane" "${prefix}03 turn_limit $repo_a Gamma lane"
require "wait reports a gone Command Code process as interrupted" "${prefix}04 interrupted $repo_a Delta lane"
require "wait discovers the other repo root" "${prefix}06 succeeded $repo_b Zeta other repo"
forbid "wait leaves a running session out" "${prefix}05"

if out=$(cd "$scratch" && sh "$campaign" wait repo-a 2>&1); then ok=0; else ok=1; fi
case $out in *"${prefix}01 succeeded $repo_a Alpha lane"*) ;; *) ok=1 ;; esac
if [ "$ok" = 0 ]; then
    printf 'ok: a relative root resolves to the absolute worktree\n'
else
    printf 'FAIL: a relative root: %s\n' "$out"
    nfailed=$((nfailed + 1))
fi

session "$repo_a" "${prefix}07" "$alive" command-code "Budgeted lane" 1 2
log "$repo_a" "${prefix}07" '{"type":"result","subtype":"success","result":"budgeted done"}'
expect 0 "list shows state, age and worktree" "${prefix}07 succeeded " list "$repo_a"
require "list includes the continuation and steer budgets" " $repo_a continuations=1 steers=2"

expect 0 "ack accepts ids" "" ack "${prefix}01" "${prefix}02"
expect 0 "ack is idempotent" "" ack "${prefix}01" "${prefix}02"
if [ "$(sort "$XDG_STATE_HOME/worker-campaign/acked" 2>&1)" = "${prefix}01
${prefix}02" ]; then
    printf 'ok: ack persisted one id per line under XDG_STATE_HOME\n'
else
    printf 'FAIL: ack file contents: %s\n' "$(cat "$XDG_STATE_HOME/worker-campaign/acked" 2>&1)"
    nfailed=$((nfailed + 1))
fi
expect 0 "an acknowledged session is never reported again" "${prefix}03 turn_limit" wait "$repo_a"
forbid "an acknowledged failed session stays silent" "${prefix}02 failed"

session "$repo_a" "${prefix}08" "$alive" command-code "Only running"
log "$repo_a" "${prefix}08" '{"type":"event","event":{"type":"tool_queued","toolName":"shell_command","input":{"description":"Waiting"}}}'
tmp_repo="$scratch/repo-timeout"
mkdir -p "$tmp_repo/.work/worker-bridge"
session "$tmp_repo" "${prefix}09" "$alive" command-code "Still running"
log "$tmp_repo" "${prefix}09" '{"type":"event","event":{"type":"tool_queued","toolName":"shell_command","input":{"description":"Waiting"}}}'
expect 2 "a timeout exits 2 with a tick" "tick: 1 running" wait --timeout 1s "$tmp_repo"
lines=$(printf '%s\n' "$out" | wc -l | tr -d ' ')
if [ "$lines" = 1 ]; then
    printf 'ok: the timeout prints a single tick line\n'
else
    printf 'FAIL: timeout printed %s lines: %s\n' "$lines" "$out"
    nfailed=$((nfailed + 1))
fi

pi_repo="$scratch/repo-pi"
pi_id=ses_0123456789abcdef0123456789abcdef
mkdir -p "$pi_repo/.work/worker-bridge"
printf '{"id":"%s10","backend":"pi","pi_id":"%s","title":"Pi lane","cwd":"%s","attempts":1}\n' \
    "$prefix" "$pi_id" "$pi_repo" > "$pi_repo/.work/worker-bridge/${prefix}10.json"
printf '{"id":"%s","cwd":"%s","run":{"pid":%s,"output":"%s/pi.result.json","errors":"%s/pi.stderr"}}\n' \
    "$pi_id" "$pi_repo" "$alive" "$pi_repo/.work/worker-bridge" "$pi_repo/.work/worker-bridge" \
    > "$pi_repo/.work/worker-bridge/$pi_id.pi.json"
printf '{"state":"succeeded","text":"SDK proof"}\n' > "$pi_repo/.work/worker-bridge/pi.result.json"
expect 0 "a Pi SDK terminal result is reported" "${prefix}10 succeeded $pi_repo Pi lane" wait "$pi_repo"

live_repo="$scratch/repo-live"
mkdir -p "$live_repo/.work/worker-bridge"
sleep 600 &
worker=$!
session "$live_repo" "${prefix}11" "$worker" command-code "Live lane"
log "$live_repo" "${prefix}11" '{"type":"event","event":{"type":"tool_queued","toolName":"shell_command","input":{"description":"Working"}}}'
sh "$campaign" wait "$live_repo" > "$scratch/live.out" 2>&1 &
waiter=$!
sleep 1
if kill -0 "$waiter" 2>/dev/null && [ ! -s "$scratch/live.out" ]; then
    printf 'ok: wait keeps blocking while the session runs\n'
else
    printf 'FAIL: wait did not block on a running session: %s\n' "$(cat "$scratch/live.out" 2>&1)"
    nfailed=$((nfailed + 1))
fi
log "$live_repo" "${prefix}11" '{"type":"result","subtype":"success","result":"finished"}'
if wait "$waiter"; then
    got=0
else
    got=$?
fi
sleep 1
out=$(cat "$scratch/live.out")
require "wait returns once the session terminates" "${prefix}11 succeeded $live_repo Live lane"
if [ "$got" = 0 ]; then
    printf 'ok: the unblocked wait exited 0\n'
else
    printf 'FAIL: the unblocked wait exit: %s\n' "$got"
    nfailed=$((nfailed + 1))
fi
kill "$worker" 2>/dev/null
worker=

WORKER_CAMPAIGN_ROOTS="$repo_b:$repo_a"
export WORKER_CAMPAIGN_ROOTS
expect 0 "WORKER_CAMPAIGN_ROOTS supplies the roots" "${prefix}06 succeeded $repo_b" wait
unset WORKER_CAMPAIGN_ROOTS

empty_repo="$scratch/repo-empty"
mkdir -p "$empty_repo"
expect 2 "an empty campaign still honours the timeout" "tick: 0 running" wait --timeout 1s "$empty_repo"

[ "$nfailed" -eq 0 ]

#!/bin/sh
# Tests for worker-watch: each way a bridge session can end maps to its own exit status.

watch="${PWD}/base/.local/bin/worker-watch"
nfailed=0

mkdir -p "${PWD}/../.work/tmp"
scratch=$(mktemp -d "${PWD}/../.work/tmp/worker-watch.XXXXXX") || exit 1
trap 'rm -rf "$scratch"' 0
bridge="$scratch/.work/worker-bridge"
mkdir -p "$bridge"

# session <id> <pid or empty> <log lines>
session () {
    if [ -n "$2" ]; then
        printf '{"id":"%s","command_run":{"pid":%s,"output":"%s/%s.ndjson"}}' "$1" "$2" "$bridge" "$1" > "$bridge/$1.json"
    else
        printf '{"id":"%s"}' "$1" > "$bridge/$1.json"
    fi
    printf '%s\n' "$3" > "$bridge/$1.ndjson"
}

# expect <wanted exit> <description> <id> <idle minutes> <text the output must contain>
expect () {
    out=$(sh "$watch" "$scratch" "$3" "$4" 2>&1)
    got=$?
    case $out in *"$5"*) ;; *) got="$got-without-$5" ;; esac
    if [ "$got" = "$1" ]; then
        printf 'ok: %s\n' "$2"
    else
        printf 'FAIL: %s (wanted %s, got %s): %s\n' "$2" "$1" "$got" "$out"
        nfailed=$((nfailed + 1))
    fi
}

queued='{"type":"event","event":{"type":"tool_queued","toolName":"shell_command","input":{"description":"Download kernel"}}}'
sleep 600 &
alive=$!
trap 'kill "$alive" 2>/dev/null; rm -rf "$scratch"' 0
sh -c 'exit 0' &
gone=$!
wait "$gone"

session 'done' "$alive" "$queued
{\"type\":\"result\",\"subtype\":\"success\",\"result\":\"report written\"}"
expect 0 "a final result record ends the wait" 'done' 10 "report written"

session crashed "$gone" "$queued"
expect 3 "an executor gone without a result is reported" crashed 10 "Download kernel"

session quiet "$alive" "$queued"
expect 2 "a quiet log reports the last queued tool" quiet 0 "shell_command: Download kernel"

session remote "" ""
expect 4 "a missing backend is refused" remote 10 "no known terminal-output backend"

# state <wanted exit> <description> <id> <state word>
state () {
    out=$(sh "$watch" --state "$scratch" "$3" 2>&1)
    got=$?
    case $out in *"$4"*) ;; *) got="$got-without-$4" ;; esac
    if [ "$got" = "$1" ]; then
        printf 'ok: %s\n' "$2"
    else
        printf 'FAIL: %s (wanted %s, got %s): %s\n' "$2" "$1" "$got" "$out"
        nfailed=$((nfailed + 1))
    fi
}

state 0 "--state names a finished run without blocking" 'done' succeeded
state 0 "--state names a gone executor" crashed interrupted
state 0 "--state names a live executor" quiet running
state 0 "--state names a backend it cannot follow" remote unknown

pi_id=ses_0123456789abcdef0123456789abcdef
printf '{"backend":"pi","pi_id":"%s"}\n' "$pi_id" > "$bridge/pi-done.json"
printf '{"id":"%s","cwd":"%s","run":{"pid":%s,"output":"%s/pi-result.json","errors":"%s/pi-err"}}\n' "$pi_id" "$scratch" "$alive" "$bridge" "$bridge" > "$bridge/$pi_id.pi.json"
printf '{"state":"succeeded","text":"SDK proof"}\n' > "$bridge/pi-result.json"
expect 0 "Pi SDK terminal result is observed" pi-done 10 "SDK proof"
printf '{"backend":"codex","command_run":{"pid":%s,"output":"%s/codex.ndjson"}}\n' "$alive" "$bridge" > "$bridge/codex.json"
printf '{"type":"thread.started","thread_id":"thread"}\n{"type":"item.completed","item":{"type":"agent_message","text":"Codex proof"}}\n{"type":"turn.completed"}\n' > "$bridge/codex.ndjson"
state 0 "Codex receipt does not precede process termination" codex running
printf '{"backend":"codex","command_run":{"pid":%s,"output":"%s/codex.ndjson"}}\n' "$gone" "$bridge" > "$bridge/codex.json"
state 0 "Codex completed turn is observed after termination" codex succeeded
expect 0 "Codex proof is displayed" codex 10 "Codex proof"

# The executor is stable; its admitted model is data, including after a policy update.
printf '{"schema_version":1,"backend":"antigravity","antigravity_pin":{"model":"fixture-model","effort":"xhigh"},"command_run":{"pid":%s,"output":"%s/agy.ndjson"}}\n' "$alive" "$bridge" > "$bridge/agy.json"
printf '{"event":"init","conversation_id":"conversation","init":{"model":"fixture-model"}}\n{"event":"result","result":{"status":"SUCCESS","response":"Antigravity proof"}}\n' > "$bridge/agy.ndjson"
state 0 "Antigravity receipt does not precede process termination" agy running
printf '{"schema_version":1,"backend":"antigravity","antigravity_pin":{"model":"fixture-model","effort":"xhigh"},"command_run":{"pid":%s,"output":"%s/agy.ndjson"}}\n' "$gone" "$bridge" > "$bridge/agy.json"
state 0 "Antigravity success uses the admitted model pin" agy succeeded
expect 0 "Antigravity proof is displayed" agy 10 "Antigravity proof"
printf '{"event":"init","init":{"model":"wrong-model"}}\n{"event":"result","result":{"status":"SUCCESS"}}\n' > "$bridge/agy.ndjson"
state 0 "Antigravity cannot succeed with a mismatched model" agy failed
printf '{"event":"result","result":{"status":"SUCCESS"}}\n' > "$bridge/agy.ndjson"
state 0 "Antigravity cannot succeed without an init model" agy failed
printf '{"event":"init","init":{"model":"fixture-model"}}\n{"event":"result","result":{"status":"ERROR","error":"quota exhausted"}}\n' > "$bridge/agy.ndjson"
state 0 "Antigravity provider failure remains failed" agy failed
expect 0 "Antigravity error is displayed" agy 10 "quota exhausted"
printf '{"event":"init","init":{"model":"fixture-model"}}\n' > "$bridge/agy.ndjson"
state 0 "Antigravity without a terminal receipt is interrupted" agy interrupted
printf '{"backend":"antigravity","command_run":{"pid":%s,"output":"%s/agy.ndjson"}}\n' "$gone" "$bridge" > "$bridge/agy-unpinned.json"
state 0 "Antigravity without an admitted pin is unknown" agy-unpinned unknown
printf '{"backend":"antigravity-transition","command_run":{"pid":%s,"output":"%s/agy.ndjson"}}\n' "$gone" "$bridge" > "$bridge/agy-transition.json"
state 0 "Antigravity interrupted admission stays unknown" agy-transition unknown
printf '{"backend":"hydrogen","command_run":{"pid":%s,"output":"%s/legacy.ndjson"}}\n' "$gone" "$bridge" > "$bridge/agy-legacy.json"
printf '{"event":"init","init":{"model":"gemini-4-hydrogen-xhigh"}}\n{"event":"result","result":{"status":"SUCCESS","response":"Legacy proof"}}\n' > "$bridge/legacy.ndjson"
state 0 "legacy Hydrogen records retain their historical pin" agy-legacy succeeded
printf '{"backend":"hydrogen","antigravity_pin":{"model":"different-model","effort":"xhigh"},"command_run":{"pid":%s,"output":"%s/legacy.ndjson"}}\n' "$gone" "$bridge" > "$bridge/agy-ambiguous.json"
state 0 "legacy Hydrogen cannot adopt a newly attached pin" agy-ambiguous unknown
printf '{"schema_version":2,"backend":"antigravity","antigravity_pin":{"model":"gemini-4-hydrogen-xhigh","effort":"xhigh"},"command_run":{"pid":%s,"output":"%s/legacy.ndjson"}}\n' "$gone" "$bridge" > "$bridge/agy-future.json"
state 0 "a future session schema is not interpreted as successful" agy-future unknown
printf '{"event":"init","init":{"model":"wrong-model"}}\n{"event":"result","result":{"status":"SUCCESS"}}\n' > "$bridge/legacy.ndjson"
state 0 "legacy Hydrogen does not adopt a different model" agy-legacy failed
[ "$nfailed" -eq 0 ]

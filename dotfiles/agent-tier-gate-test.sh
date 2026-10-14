#!/bin/sh
# Tests for agent-tier-gate: exit 0 allows a spawn, exit 2 is the only status that blocks one.

gate="${PWD}/base/.local/bin/agent-tier-gate"
nfailed=0

# expect <wanted exit> <description> <input> [PATH override]
expect () {
    if [ -n "${4+x}" ]; then
        got=$(printf '%s' "$3" | PATH="$4" /bin/sh "$gate" >/dev/null 2>&1; echo $?)
    else
        got=$(printf '%s' "$3" | /bin/sh "$gate" >/dev/null 2>&1; echo $?)
    fi
    if [ "$got" = "$1" ]; then
        printf 'ok: %s\n' "$2"
    else
        printf 'FAIL: %s (wanted %s, got %s)\n' "$2" "$1" "$got"
        nfailed=$((nfailed + 1))
    fi
}

expect 0 'main conversation spawns any tier' '{"tool_input":{"subagent_type":"god"}}'
expect 2 'main conversation cannot spawn a built-in type' '{"tool_input":{"subagent_type":"general-purpose"}}'
expect 2 'a spawn without a type is refused' '{"agent_type":"worker","tool_input":{}}'
expect 0 'mechanic spawns scout' '{"agent_type":"mechanic","tool_input":{"subagent_type":"scout"}}'
expect 2 'mechanic cannot spawn god' '{"agent_type":"mechanic","tool_input":{"subagent_type":"god"}}'
expect 2 'a tier cannot spawn its own tier' '{"agent_type":"worker","tool_input":{"subagent_type":"worker"}}'
expect 0 'god spawns expert' '{"agent_type":"god","tool_input":{"subagent_type":"expert"}}'
expect 2 'scout spawns nothing' '{"agent_type":"scout","tool_input":{"subagent_type":"scout"}}'
expect 2 'a non-tier caller is refused' '{"agent_type":"fork","tool_input":{"subagent_type":"scout"}}'
expect 2 'unparseable input is refused' 'not json'
expect 2 'empty input is refused' ''
empty=$(mktemp -d) || exit 1
trap 'rm -rf "$empty"' 0
expect 2 'a missing JSON tool is refused' '{"tool_input":{"subagent_type":"scout"}}' "$empty"
expect 0 'grok main conversation spawns any tier' '{"toolInput":{"subagent_type":"god"}}'
expect 2 'grok main conversation cannot spawn a built-in type' '{"toolInput":{"subagent_type":"general-purpose"}}'
expect 0 'grok mechanic spawns scout' '{"subagentType":"mechanic","toolInput":{"subagent_type":"scout"}}'
expect 2 'grok mechanic cannot spawn worker' '{"subagentType":"mechanic","toolInput":{"subagent_type":"worker"}}'
expect 2 'grok camelCase target is still ranked' '{"subagentType":"worker","toolInput":{"subagentType":"worker"}}'

echo "testing finished."
[ "$nfailed" -eq 0 ]

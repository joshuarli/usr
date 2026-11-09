#!/bin/sh
# Native delegation is restricted to Claude's root god tier.
gate="$PWD/base/.local/bin/agent-tier-gate"
failed=0
expect () {
    got=$(printf '%s' "$3" | /bin/sh "$gate" >/dev/null 2>&1; echo $?)
    if [ "$got" = "$1" ]; then printf 'ok: %s\n' "$2"
    else printf 'FAIL: %s: expected %s got %s\n' "$2" "$1" "$got"; failed=$((failed+1)); fi
}
expect 0 'Claude root god' '{"tool_input":{"subagent_type":"god"}}'
expect 2 'Claude root worker blocked' '{"tool_input":{"subagent_type":"worker"}}'
expect 2 'Claude root scout blocked' '{"tool_input":{"subagent_type":"scout"}}'
expect 2 'Claude general-purpose blocked' '{"tool_input":{"subagent_type":"general-purpose"}}'
expect 2 'Claude nested god blocked' '{"agent_type":"expert","tool_input":{"subagent_type":"god"}}'
expect 2 'Claude nested ordinary blocked' '{"agent_type":"god","tool_input":{"subagent_type":"scout"}}'
expect 2 'Grok god blocked' '{"toolInput":{"subagent_type":"god"}}'
expect 2 'Grok worker blocked' '{"toolInput":{"subagent_type":"worker"}}'
expect 2 'Grok camelCase blocked' '{"toolInput":{"subagentType":"mechanic"}}'
expect 2 'missing harness denied' '{"tool_input_other":{"subagent_type":"god"}}'
expect 2 'invalid JSON denied' 'not json'
expect 2 'empty input denied' ''
empty=$(mktemp -d) || exit 1
trap 'rm -rf "$empty"' 0
result=$(printf '%s' '{"tool_input":{"subagent_type":"god"}}' | PATH="$empty" /bin/sh "$gate" >/dev/null 2>&1; echo $?)
[ "$result" = 2 ] || { printf 'FAIL: missing JSON tool was allowed\n'; failed=$((failed+1)); }
[ "$failed" -eq 0 ]

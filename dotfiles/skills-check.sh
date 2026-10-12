#!/bin/sh
# Checks the skills tree for drift between harness-specific copies of one fact:
# a skill that Claude must not auto-invoke (disable-model-invocation: true in
# SKILL.md) must also tell Codex (allow_implicit_invocation: false in
# agents/openai.yaml), and no other skill may carry that Codex policy.
# Also checks that each skill's frontmatter name matches its directory.
set -u
skills="${1:-base/.agents/skills}"
bad=0
for d in "$skills"/*/; do
    n=$(basename "$d"); f="$d/SKILL.md"
    [ "$(sed -n 's/^name: //p' "$f" | head -1)" = "$n" ] || { echo "name does not match directory: $n"; bad=1; }
    grep -q '^description:' "$f" || { echo "missing description: $n"; bad=1; }
    explicit=false; codex_off=false
    grep -q '^disable-model-invocation: true' "$f" && explicit=true
    grep -q 'allow_implicit_invocation: false' "$d/agents/openai.yaml" 2>/dev/null && codex_off=true
    [ "$explicit" = "$codex_off" ] || { echo "Claude and Codex invocation policy differ: $n (explicit=$explicit, codex_off=$codex_off)"; bad=1; }
done
exit $bad

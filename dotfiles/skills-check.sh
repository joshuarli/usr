#!/bin/sh
# Checks the skills tree for drift and shape.
# Failures (exit 1):
#   - frontmatter name does not match the directory, or description is missing;
#   - a skill Claude must not auto-invoke (disable-model-invocation: true in SKILL.md)
#     does not also tell Codex (allow_implicit_invocation: false in agents/openai.yaml),
#     or the reverse;
#   - an auto-triggered skill's description has no "Skip" clause, so it would fire on
#     every task;
#   - a router table whose second column is Skill names a skill that does not exist.
# Warnings (exit 0): a skill over 60 lines, or one with no closing **Reply:**.
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
    if [ "$explicit" = false ] && ! sed -n 's/^description: //p' "$f" | grep -q 'Skip'; then
        echo "auto-triggered skill has no Skip clause in its description: $n"; bad=1
    fi
    # Backticked names in the Skill column of a router table.
    refs=$(awk -F'|' '/^\|[^|]*\| *Skill *\|/ {t=1; next} t && /^\| *-/ {next} t && /^\|/ {print $3; next} {t=0}' "$f" \
        | grep -o '`[^`]*`' | tr -d '`')
    for r in $refs; do
        [ -f "$skills/$r/SKILL.md" ] || { echo "$n names a skill that does not exist: $r"; bad=1; }
    done
    [ "$(wc -l < "$f")" -le 60 ] || echo "warning: $n is over 60 lines"
    grep -q '^\*\*Reply:\*\*\|^## \(Hand back\|Report\|Handoff\)' "$f" || echo "warning: $n has no closing **Reply:**"
done
exit $bad

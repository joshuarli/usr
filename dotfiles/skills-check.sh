#!/bin/sh
# Checks the skills tree for drift and shape.
# Failures (exit 1):
#   - frontmatter name does not match the directory, or description is missing;
#   - the Claude and Codex implicit-invocation settings disagree;
#   - an auto-triggered skill's description has no "Skip" clause, so it would fire on
#     every task;
#   - a literal mdtool reference names a command the checked-in tool does not expose;
#   - a router table whose second column is Skill names a skill that does not exist.
# Warnings (exit 0): a skill over 60 lines, or one with no closing **Reply:**.
set -u
skills="${1:-base/.agents/skills}"
script_dir=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd) || exit 1
repo_root=$(CDPATH='' cd -- "$script_dir/.." && pwd) || exit 1
command_list=$(python3 -I "$repo_root/dotfiles/base/.local/bin/mdtool" commands) || {
    echo "cannot read mdtool command list" >&2
    exit 1
}
valid_commands=$(printf '%s\n' "$command_list" | tr '\n' ' ')
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
    # shellcheck disable=SC2016  # backticks are literal here
    refs=$(awk -F'|' '/^\|[^|]*\| *Skill *\|/ {t=1; next} t && /^\| *-/ {next} t && /^\|/ {print $3; next} {t=0}' "$f" \
        | grep -o '`[^`]*`' | tr -d '`')
    for r in $refs; do
        [ -f "$skills/$r/SKILL.md" ] || { echo "$n names a skill that does not exist: $r"; bad=1; }
    done
    # Skill references are literal command names so they can be checked without installing mdtool.
    # shellcheck disable=SC2016
    commands=$(grep -Eo '`mdtool [a-z][a-z-]*' "$f" | sed 's/^`mdtool //')
    for c in $commands; do
        case " $valid_commands " in
            *" $c "*) ;;
            *) echo "$n references unknown mdtool command: $c"; bad=1 ;;
        esac
    done
    [ "$(wc -l < "$f")" -le 60 ] || echo "warning: $n is over 60 lines"
    grep -q '^\*\*Reply:\*\*\|^## \(Hand back\|Report\|Handoff\)' "$f" || echo "warning: $n has no closing **Reply:**"
done
exit $bad

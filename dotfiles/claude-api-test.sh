#!/bin/sh

set -eu

root=$(CDPATH='' cd -P "$(dirname "$0")/.." && pwd -P)
TMPDIR="$root/.work/tmp"
export TMPDIR
mkdir -p "$TMPDIR"
work=$(mktemp -d "$TMPDIR/claude-api-test.XXXXXX")
trap 'rm -rf "$work"' 0 HUP INT TERM

bin="$work/bin"
repo="$work/repo"
launcher="$root/dotfiles/base/.local/bin/claude-api"
args="$work/args"
calls="$work/calls"
expected="$work/expected"
output="$work/output"
error="$work/error"
mkdir -p "$bin" "$repo"
git -C "$repo" init -q

cat >"$bin/vault" <<'EOF'
#!/bin/sh
case ${1-} in
ls) printf '%s\n' ANTHROPIC_API_KEY ;;
ANTHROPIC_API_KEY)
	[ "${2-}" = -- ] || exit 64
	shift 2
	exec "$@"
	;;
*) exit 64 ;;
esac
EOF

cat >"$bin/claude" <<'EOF'
#!/bin/sh
printf '%s\n' "$@" >"$CLAUDE_API_ARGS"
printf '%s\n' called >>"$CLAUDE_API_CALLS"
printf '%s\n' '{"type":"result","subtype":"success","is_error":false,"result":"completed","num_turns":1,"duration_ms":0,"total_cost_usd":0}'
EOF

cat >"$bin/editor" <<'EOF'
#!/bin/sh
for last in "$@"; do :; done
printf '%s\n' "$last" >"$EDITOR_FILE"
printf '%s\n' "$EDITOR_PROMPT" >"$last"
EOF

chmod +x "$bin/vault" "$bin/claude" "$bin/editor"

run() {
	(
		cd "$repo"
		umask 022
		PATH="$bin:$PATH" CLAUDE_API_ARGS="$args" CLAUDE_API_CALLS="$calls" "$launcher" "$@"
	) >"$output" 2>"$error"
}

fail() {
	printf '%s\n' "claude-api test: $1" >&2
	exit 1
}

if run --help; then
	:
else
	fail "help returned an error"
fi
[ ! -s "$error" ] || fail "help wrote to stderr"
grep -q 'only the first /skill-name' "$output" || fail "help omitted the print-mode caveat"
grep -q 'later /skill-name tokens' "$output" || fail "help omitted how later skill tokens are handled"
# shellcheck disable=SC2016 # $EDITOR is literal help text
grep -Fq 'opens $EDITOR' "$output" || fail "help omitted editor composition"

: >"$calls"
mkdir -p "$repo/.work/logs"
chmod 777 "$repo/.work/logs"
run --budget 7 --model test-model Review the cache /skill1 /skill2
log=$(sed -n 's/^raw log: //p' "$error")
python3 -c 'import os, sys; assert os.stat(sys.argv[1]).st_mode & 0o777 == 0o700; assert os.stat(sys.argv[2]).st_mode & 0o777 == 0o600' "$repo/.work/logs" "$log" || fail "log paths were not private"
cat >"$expected" <<'EOF'
-p
Review the cache /skill1 /skill2
--max-budget-usd
7
--dangerously-skip-permissions
--model
test-model
--effort
high
--output-format
stream-json
--verbose
EOF
cmp -s "$expected" "$args" || fail "prompt and options were not forwarded"
[ "$(grep -c '^called$' "$calls")" -eq 1 ] || fail "launcher made an unexpected number of Claude calls"

run -- '/skill1 /skill2 inspect src/'
cat >"$expected" <<'EOF'
-p
/skill1 /skill2 inspect src/
--max-budget-usd
100
--dangerously-skip-permissions
--model
claude-sonnet-5-5
--effort
high
--output-format
stream-json
--verbose
EOF
cmp -s "$expected" "$args" || fail "default budget or prompt was wrong"
[ "$(grep -c '^called$' "$calls")" -eq 2 ] || fail "skill preflight called Claude separately"

EDITOR="$bin/editor --wait"
editor_file="$work/editor-file"
EDITOR_FILE="$editor_file"
EDITOR_PROMPT='Review the cache from the editor
and check /skill1'
export EDITOR EDITOR_FILE EDITOR_PROMPT
: >"$calls"
run
[ "$(grep -c '^called$' "$calls")" -eq 1 ] || fail "editor prompt did not reach Claude"
prompt_file=$(cat "$editor_file")
[ ! -e "$prompt_file" ] || fail "editor temp file was left behind"
cat >"$expected" <<'EOF'
-p
Review the cache from the editor
and check /skill1
--max-budget-usd
100
--dangerously-skip-permissions
--model
claude-sonnet-5-5
--effort
high
--output-format
stream-json
--verbose
EOF
cmp -s "$expected" "$args" || fail "editor prompt and options were not forwarded"

EDITOR_PROMPT=''
if run; then
	fail "accepted an empty editor buffer"
else
	[ "$?" -eq 2 ] || fail "empty editor buffer returned the wrong status"
fi
grep -q 'no prompt entered' "$error" || fail "empty editor buffer was not reported"
[ "$(grep -c '^called$' "$calls")" -eq 1 ] || fail "empty editor buffer started Claude"

EDITOR=''
if run; then
	fail "accepted a missing EDITOR"
else
	[ "$?" -eq 2 ] || fail "missing EDITOR returned the wrong status"
fi
grep -q 'EDITOR is not set' "$error" || fail "missing EDITOR was not reported"
[ "$(grep -c '^called$' "$calls")" -eq 1 ] || fail "missing EDITOR started Claude"

if run ""; then
	fail "accepted an empty string as a prompt"
else
	[ "$?" -eq 2 ] || fail "empty string prompt returned the wrong status"
fi

# The historical price table remains accurate for audit, but no Fable launch is permitted.
grep -q 'startswith("claude-fable-5-2").*{i: 8,  o: 40, r: 0.2}' "$launcher" || fail "missing Fable 5.2 historical pricing"
for banned in fable fable-5-2 claude-fable-5-1 claude-fable-5-2 anthropic/claude-fable-5-2; do
  if run --model "$banned" test; then
    fail "accepted banned Fable model $banned"
  else
    [ "$?" -eq 2 ] || fail "Fable ban returned wrong status"
  fi
  grep -q 'prohibited Fable model' "$error" || fail "Fable rejection was not explicit"
done
[ "$(grep -c '^called$' "$calls")" -eq 1 ] || fail "Fable rejection launched Claude"
if run --prompt example; then
	fail "accepted the removed --prompt option"
else
	[ "$?" -eq 2 ] || fail "removed --prompt option returned the wrong status"
fi
[ "$(grep -c '^called$' "$calls")" -eq 1 ] || fail "invalid prompt started Claude"

printf '%s\n' 'claude-api tests passed'

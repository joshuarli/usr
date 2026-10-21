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

cat >"$bin/notify-sound" <<'EOF'
#!/bin/sh
exit 0
EOF

chmod +x "$bin/vault" "$bin/claude" "$bin/notify-sound"

run() {
	(
		cd "$repo"
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

: >"$calls"
run --budget 7 --model test-model Review the cache /skill1 /skill2
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

if run; then
	fail "accepted an empty prompt"
else
	[ "$?" -eq 2 ] || fail "empty prompt returned the wrong status"
fi
grep -q '^usage: claude-api ' "$error" || fail "empty prompt did not print usage"

if run ""; then
	fail "accepted an empty string as a prompt"
else
	[ "$?" -eq 2 ] || fail "empty string prompt returned the wrong status"
fi

if run --prompt example; then
	fail "accepted the removed --prompt option"
else
	[ "$?" -eq 2 ] || fail "removed --prompt option returned the wrong status"
fi
[ "$(grep -c '^called$' "$calls")" -eq 2 ] || fail "invalid prompt started Claude"

printf '%s\n' 'claude-api tests passed'

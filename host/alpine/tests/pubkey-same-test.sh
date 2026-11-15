#!/bin/sh
# Focused fixtures for pubkey-same.sh: same key material with different or absent
# comments must match; encrypted keys, mismatched material and garbage input must not.
# Fixture files are only ever read, never rewritten.
set -eu
cd "$(dirname "$0")/.."
helper=$PWD/pubkey-same.sh
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT HUP INT TERM
fail=0
run() { # NAME EXPECTED KEY PUB
	if "$helper" "$3" "$4" >/dev/null 2>&1; then
		rc=0
	else
		rc=$?
	fi
	if [ "$rc" -eq "$2" ]; then
		printf 'ok: %s\n' "$1"
	else
		printf 'FAIL: %s (expected exit %s, got %s)\n' "$1" "$2" "$rc" >&2
		fail=1
	fi
}

key="$tmp/github"
ssh-keygen -q -t ed25519 -N '' -f "$key" -C 'original comment' </dev/null
same=0
other=1

run 'matching pair as generated' "$same" "$key" "$key.pub"
checksum=$(cksum "$key" | awk '{print $1}')

commentless="$tmp/commentless.pub"
awk '{print $1 " " $2}' "$key.pub" > "$commentless"
run 'public key without comment' "$same" "$key" "$commentless"

different="$tmp/different-comment.pub"
awk '{print $1 " " $2 " a different comment"}' "$key.pub" > "$different"
run 'public key with different comment' "$same" "$key" "$different"

[ "$(cksum "$key" | awk '{print $1}')" = "$checksum" ] || { echo "FAIL: fixture key was modified" >&2; fail=1; }

nocomment_key="$tmp/nocomment"
ssh-keygen -q -t ed25519 -N '' -f "$nocomment_key" -C '' </dev/null
run 'private key without comment and commentless pub' "$same" "$nocomment_key" "$nocomment_key.pub"

mismatch="$tmp/mismatch"
ssh-keygen -q -t ed25519 -N '' -f "$mismatch" -C 'original comment' </dev/null
run 'different key material' "$other" "$key" "$mismatch.pub"

tampered="$tmp/tampered.pub"
awk '{ s = $2; sub(/.$/, (substr(s, length(s)) == "A" ? "B" : "A"), s); print $1 " " s }' "$key.pub" > "$tampered"
run 'same type with corrupted key material' "$other" "$key" "$tampered"

rsa_key="$tmp/rsa"
ssh-keygen -q -t rsa -N '' -f "$rsa_key" -C 'original comment' </dev/null
run 'different key type' "$other" "$rsa_key" "$key.pub"

encrypted="$tmp/encrypted"
ssh-keygen -q -t ed25519 -N 'secret' -f "$encrypted" -C 'original comment' </dev/null
run 'encrypted private key rejected' "$other" "$encrypted" "$encrypted.pub"

garbage="$tmp/garbage.pub"
printf 'not a public key\n' > "$garbage"
run 'unparseable public key rejected' "$other" "$key" "$garbage"

empty="$tmp/empty.pub"
: > "$empty"
run 'empty public key rejected' "$other" "$key" "$empty"

exit "$fail"

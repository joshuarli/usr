#!/bin/sh
# Exit 0 when PRIVATE is an unencrypted public key matching PUB in key type and encoded
# key material; the optional comment on either file is ignored. Exit 1 on any mismatch,
# unreadable key, missing ssh-keygen input or an encrypted private key.
set -eu
[ $# -eq 2 ] || { echo 'usage: pubkey-same.sh PRIVATE PUB' >&2; exit 2; }
command -v ssh-keygen >/dev/null || { echo 'ssh-keygen is required to check the key pair; install openssh-keygen' >&2; exit 2; }
derived=$(ssh-keygen -y -P '' -f "$1" 2>/dev/null | awk 'NF >= 2 { print $1 " " $2; exit }') || exit 1
material=$(awk 'NF >= 2 { print $1 " " $2; exit }' "$2")
[ -n "$derived" ] && [ -n "$material" ] && [ "$derived" = "$material" ]

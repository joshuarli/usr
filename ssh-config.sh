#!/bin/sh
# Append a Host * block to ~/.ssh/config if not already present.
# Idempotent — safe to run multiple times.

set -eu

config="${HOME}/.ssh/config"

mkdir -p "${HOME}/.ssh/sockets"
chmod 700 "${HOME}/.ssh"
touch "$config"

grep -q '^Host \*' "$config" && exit 0

cat >> "$config" << 'EOF'

Host *
  ControlMaster auto
  ControlPath ~/.ssh/sockets/%r@%h-%p
  ControlPersist yes
  AddKeysToAgent yes
  IdentitiesOnly yes
  ConnectTimeout 5
  ServerAliveInterval 60
  ServerAliveCountMax 3
  PreferredAuthentications publickey
EOF

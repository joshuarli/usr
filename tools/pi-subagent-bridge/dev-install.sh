#!/bin/sh
set -eu

here=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)

if [ -e "$here/node_modules" ] && [ ! -L "$here/node_modules" ]; then
  echo "refusing to install dev tooling: $here/node_modules is not the usual runtime symlink" >&2
  exit 1
fi

deps=$(cd "$here" && node -e 'const p = require("./package.json"); const all = { ...p.dependencies, ...p.devDependencies }; process.stdout.write(Object.entries(all).map(([name, version]) => `${name}@${version}`).join(" "))')
# shellcheck disable=SC2086
npm install --global --prefix "$here/.dev" --no-audit --no-fund $deps

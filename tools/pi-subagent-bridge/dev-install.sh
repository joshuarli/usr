#!/bin/sh
set -eu

here=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)

if [ -e "$here/node_modules" ] && [ ! -L "$here/node_modules" ]; then
  echo "refusing to install dev tooling: $here/node_modules is not the usual runtime symlink" >&2
  exit 1
fi

case ${1-} in
  ""|--core) ;;
  *) echo "usage: dev-install.sh [--core]" >&2; exit 1 ;;
esac

if [ ! -e "$here/node_modules" ] && [ ! -L "$here/node_modules" ]; then
  runtime="${XDG_DATA_HOME:-$HOME/.local/share}/pi-runtime/current/node_modules"
  if [ ! -d "$runtime" ]; then
    echo "Pi runtime not found at $runtime; run sh sync first" >&2
    exit 1
  fi
  ln -s "$runtime" "$here/node_modules"
fi

deps=$(cd "$here" && node - "$@" <<'JS'
const p = require("./package.json");
const all = process.argv[2] === "--core" ? p.devDependencies : { ...p.optionalDependencies, ...p.devDependencies };
process.stdout.write(Object.entries(all).map(([name, version]) => `${name}@${version}`).join(" "));
JS
)
# shellcheck disable=SC2086
npm install --global --prefix "$here/.dev" --no-audit --no-fund $deps

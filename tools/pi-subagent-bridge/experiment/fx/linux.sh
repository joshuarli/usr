#!/bin/sh
# Run the real-binary FX ACP qualification inside an Alpine (musl) container.
# usage: linux.sh arm64|amd64
# arm64 is native on an ARM64 host; amd64 there runs under the container runtime's emulation.
set -eu

arch=${1-}
case $arch in
  arm64) node_target=linux-arm64-musl ;;
  amd64) node_target=linux-x64-musl ;;
  *) echo "usage: linux.sh arm64|amd64" >&2; exit 2 ;;
esac

here=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
repo=$(CDPATH='' cd -- "$here/../../../.." && pwd)
pins=$(python3 -I - "$repo/tools/sync/installer.py" "$node_target" <<'PY'
import ast, sys
values = {}
for node in ast.parse(open(sys.argv[1]).read()).body:
    if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name) and node.targets[0].id in ("NODEJS_VERSION", "MIRROR_BASE", "NODE_MIRROR_SHA256"):
        values[node.targets[0].id] = ast.literal_eval(node.value)
print(values["NODEJS_VERSION"], values["MIRROR_BASE"], values["NODE_MIRROR_SHA256"][sys.argv[2]])
PY
)
set -- $pins
node_version=$1 mirror=$2 node_sha=$3

docker run --rm --platform "linux/$arch" \
  -e NODE_ASSET="node-v$node_version-$node_target.tar.xz" -e NODE_URL="$mirror/node-v$node_version-$node_target.tar.xz" -e NODE_SHA="$node_sha" \
  -v "$repo:/usr-repo" -w /usr-repo/tools/pi-subagent-bridge alpine:3.22 sh -euc '
    apk add --no-cache git python3 bash xz curl ca-certificates libgcc libstdc++ libatomic >/dev/null
    mkdir -p /opt/node && cd /opt/node
    curl -fsSL -o "$NODE_ASSET" "$NODE_URL"
    echo "$NODE_SHA  $NODE_ASSET" | sha256sum -c - >/dev/null
    tar -xJf "$NODE_ASSET"
    export PATH="/opt/node/bin:$PATH"
    git config --global --add safe.directory "*"
    git config --global user.name fixture; git config --global user.email fixture@example.com
    cd /usr-repo/tools/pi-subagent-bridge
    uname -m; node --version; ldd --version 2>&1 | head -1 || true
    node experiment/fx/spike.mjs --setup
    node experiment/fx/spike.mjs --local-acp
  '

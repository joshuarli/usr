#!/usr/bin/env bash
# Explicit maintainer-only build: npm is permitted HERE, never in sh sync.
set -euo pipefail
root=$(CDPATH='' cd -- "$(dirname -- "$0")/../.." && pwd)
cd "$root"
python3 -I tools/pi/vendor.py check
node --version
npm --version
scratch=$(mktemp -d)
trap 'rm -rf "$scratch"' EXIT
mkdir -p "$scratch/packages" "$scratch/tars" "$scratch/runtime"
for name in pi-subagents agent-intercom-pi agent-intercom-core pi-muse-subscription; do
    cp -R "vendor/pi/$name" "$scratch/packages/$name"
done

# The intercom core publishes compiled .js/.d.ts; build it from the pinned source.
(cd "$scratch/packages/agent-intercom-core"
 npm install --ignore-scripts --no-audit --no-fund --no-package-lock
 ./node_modules/.bin/tsc -p tsconfig.build.json
 test -f dist/index.js
)
# Do not package the build-only TypeScript compiler into the production archive.
rm -rf "$scratch/packages/agent-intercom-core/node_modules"

# Upstream Pi adapter pins the core to a Git URL. Replace only in the throwaway
# npm packaging copy; the snapshot in vendor/pi stays byte-for-byte upstream.
node - "$scratch/packages/agent-intercom-pi/package.json" <<'NODE'
const fs = require("node:fs");
const file = process.argv[2];
const data = JSON.parse(fs.readFileSync(file, "utf8"));
data.dependencies["@dataforxyz/agent-intercom-core"] = "0.1.0";
fs.writeFileSync(file, JSON.stringify(data, null, 2) + "\n");
NODE

pack() {
    local name="$1" target="$2" output
    output=$(cd "$scratch/packages/$name" &&
        npm pack --silent --ignore-scripts --pack-destination "$scratch/tars" .)
    test -n "$output" && test -f "$scratch/tars/$output"
    mv "$scratch/tars/$output" "$scratch/tars/$target.tgz"
}
pack agent-intercom-core core
pack agent-intercom-pi intercom
pack pi-subagents subagents
pack pi-muse-subscription muse

node - "$scratch/runtime/package.json" "$scratch/tars" <<'NODE'
const fs = require("node:fs");
const [file, tars] = process.argv.slice(2);
fs.writeFileSync(file, JSON.stringify({
  name: "usr-pi-offline-runtime", private: true, version: "1.5.0", type: "module",
  description: "Prebuilt production dependency closure. Never npm install during sync.",
  dependencies: {
    "@earendil-works/pi-coding-agent": "1.5.0",
    "@earendil-works/pi-ai": "1.5.0",
    "@earendil-works/pi-tui": "1.5.0",
    "@earendil-works/pi-agent-core": "1.5.0",
    "@dataforxyz/agent-intercom-core": "file:" + tars + "/core.tgz",
    "@dataforxyz/agent-intercom-pi": "file:" + tars + "/intercom.tgz",
    "pi-subagents": "file:" + tars + "/subagents.tgz",
    "pi-muse-subscription": "file:" + tars + "/muse.tgz",
    "tsx": "4.20.6",
    "typebox": "1.3.27",
    "yaml": "2.8.3"
  }
}, null, 2) + "\n");
NODE

npm install --prefix "$scratch/runtime" --omit=dev --ignore-scripts \
    --no-audit --no-fund --no-package-lock --install-strategy=hoisted
for pkg in @earendil-works/pi-coding-agent pi-subagents pi-muse-subscription \
           @dataforxyz/agent-intercom-pi @dataforxyz/agent-intercom-core; do
    test -f "$scratch/runtime/node_modules/$pkg/package.json" || {
        echo "Missing packaged dependency: $pkg" >&2; exit 1;
    }
done
test -f "$scratch/runtime/node_modules/@earendil-works/pi-coding-agent/dist/bundle/cli.js"
test -f "$scratch/runtime/node_modules/@dataforxyz/agent-intercom-core/dist/index.js"

# Exit immediately if the package or SDK is incomplete, before creating an artifact.
(
 cd "$scratch/runtime"
 node --input-type=module -e '
   import { createRequire } from "node:module";
   const req = createRequire(import.meta.url);
   for (const x of ["@earendil-works/pi-coding-agent",
                    "pi-subagents",
                    "pi-subagents/required-child-extensions",
                    "pi-muse-subscription/src/index.ts",
                    "@dataforxyz/agent-intercom-pi/index.ts"]) {
     console.log(x + " -> " + req.resolve(x));
   }'
 node node_modules/@earendil-works/pi-coding-agent/dist/bundle/cli.js --version
)

os=$(uname -s | tr '[:upper:]' '[:lower:]')
arch=$(uname -m)
case "$arch" in x86_64|amd64) arch=x64;; aarch64|arm64) arch=arm64;; *) echo "Unsupported architecture: $arch" >&2; exit 1;; esac
case "$os" in linux|darwin) :;; *) echo "Unsupported OS: $os" >&2; exit 1;; esac
platform="$os-$arch"
archive="$root/vendor/pi/runtime/$platform.tar.gz"
mkdir -p "$(dirname "$archive")"
tar -C "$scratch/runtime" -czf "$archive" node_modules
sha=$(sha256sum "$archive" | awk '{print $1}')
size=$(wc -c < "$archive" | tr -d ' ')
node - "$root/vendor/pi/runtime/artifacts.json" "$platform" "$sha" "$size" <<'NODE'
const fs = require("node:fs");
const [file, platform, sha256, size] = process.argv.slice(2);
const current = fs.existsSync(file) ? JSON.parse(fs.readFileSync(file,"utf8")) :
    {schema:1, pi_version:"1.5.0", node_minimum:"26.0.0", artifacts:{}};
current.artifacts[platform] = {path:platform+".tar.gz",sha256,bytes:Number(size)};
fs.writeFileSync(file, JSON.stringify(current, null, 2) + "\n");
NODE
echo "BUILT $platform $size bytes sha256=$sha"

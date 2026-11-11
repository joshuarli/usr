# Vendored Pi runtime

The Pi coding agent, its SDK, `pi-subagents`, the Muse subscription adapter, and the Pi intercom adapter are available from **committed, self-contained runtime archives**. Normal Pi setup never invokes npm, npx, `pi install`, `pi update`, or the package registry. The `pi-subagent-bridge` uses that same dependency closure, not a separately installed SDK.

## Offline installation

`sh sync tools pi` installs the matching checked-in `runtime/<platform>.tar.gz` beneath `${XDG_DATA_HOME:-$HOME/.local/share}/pi`. The installer verifies the archive byte count and SHA-256 from [runtime/artifacts.json](runtime/artifacts.json), rejects unsafe tar members, validates package versions, stages the tree, and atomically switches the managed Pi prefix. It creates `~/.local/bin/pi` and loads the vendored subagent and intercom extensions by their absolute local paths.

`sh sync bridge` (or desktop `sh sync`) connects the bridge's `node_modules` to the same installed closure. `sh sync plan` and `sh sync doctor` remain read-only. The tracked Pi settings declare `packages: []` and sync rejects nonempty package arrays: neither Pi startup nor sync is allowed to reconcile online extension sources. The installer preserves credentials and refuses foreign/unmanaged paths.

| Archive | Platform |
| --- | --- |
| `runtime/darwin-arm64.tar.gz` | macOS Apple Silicon |
| `runtime/linux-x64.tar.gz` | Linux x86-64, including musl |
| `runtime/linux-arm64.tar.gz` | Linux ARM64 |

Node.js 26.12+ is required. The Node.js installation is a separate sync tool, and **other unrelated sync tools** (Command Code, npm, etc.) may still use npm or the network. The guarantee here is that the **Pi CLI, SDK, bridge dependencies and Pi intercom setup** use no npm fetch, even with an empty npm cache and registry disabled.

## Provenance

[upstreams.json](upstreams.json) records each upstream source repository and full commit SHA; the file inventory records the actual upstream Git **blob SHA** for every imported source file. These exact source snapshots are retained:

| Source | License | Runtime role |
| --- | --- | --- |
| `pi-subagents` | MIT | Native delegation extension and RPC |
| `agent-intercom-pi` | AGPL-3.0-or-later | Interactive Pi intercom adapter |
| `agent-intercom-core` | AGPL-3.0-or-later | Intercom broker protocol and policy |
| `pi-muse-subscription` | MIT | Muse SDK subscription provider |

The Pi 1.5.0 CLI/SDK package is bundled as an exact-version dependency closure; its source repository/tag/SHA are listed in `upstreams.json` under `tracked_only`. The runtime artifacts are checksum-pinned in `runtime/artifacts.json`. The upstream intercom AGPL notices remain in their directories. Review these obligations before redistributing a derived combined application.

## Updating (explicit only)

Use the manual `/pi-update` skill: validate source provenance, inspect upstream releases, advance all compatible SHAs, update the CLI/SDK package pins, then run `bash tools/pi/build-runtime.sh` on the supported platform builders. The script may use npm **during explicit build/update only**, from a temporary workspace; it packs vendor source snapshots and the complete installed dependency closure into a new archive. Commit the archives plus their SHA-256 manifest **together**. Do not replace ordinary sync with a package-manager fallback. `python3 -I tools/pi/vendor.py check` verifies all upstream blob hashes offline, and `python3 -I tools/pi/test_offline.py` exercises an actual archive with npm unavailable.

## Intercom scope and limits

Interactive Pi loads the local intercom adapter. Its local broker is configured with the bundled `tsx` loader rather than `npx`, `inboundTrigger: "never"` by default, and `confirmSend: true`. No separate fleet/orchestrator package is imported. The scoped `pi-subagent-bridge` SDK workers deliberately load only their required subagent/Muse extensions and do **not** inherit unrestricted intercom tools. Independent Claude/Codex/OpenCode intercom adapters are **not** part of these Pi archives; cross-harness messaging requires separately enabled compatible adapters and is not implied by this Pi-only runtime.

Worker admission, worktree lease, scope, model, nested tier and proof remain exclusively owned by `pi-subagent-bridge`.

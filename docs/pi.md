# Pi

Every coding harness delegates through the shared `pi-subagent-bridge` MCP tools or CLI shim. Its routing policy prefers Command Code, then the pinned Muse SDK subscription for scout/mechanic/worker, then OpenCode Go through Pi SDK and [`pi-subagents`](https://github.com/nicobailon/pi-subagents). The bridge invokes the versioned delegation RPC directly, without `pi -p` or an LLM-driven subagent decision. It owns cross-harness worktree leases and provider selection; pi-subagents owns native child execution, completion events, and retained-session continuation. See the [bridge reference](../tools/pi-subagent-bridge/README.md#safety-and-durability) for known result-identity and fallback defects.

## Pinned, npm-free Pi runtime

Pi 1.5.0, its SDK, `pi-subagents`, the Muse provider and `agent-intercom-pi` are built with their transitive dependencies by [`pi-build`](https://github.com/joshuarli/pi-build), which owns the upstream source snapshots, patches, locks, provenance and archives. [`tools/pi/runtime.pin.json`](../tools/pi/runtime.pin.json) pins one immutable release: its URL, builder revision, provenance digest, and each target archive's SHA-256 and size. `sh sync tools pi` downloads only that pinned archive, verifies it against the pin, the release `provenance.json` and `SHA256SUMS`, and installs it. The shared `pi-subagent-bridge` links to the **same** installed closure. Supported platforms: macOS ARM64, Linux x64 and Linux ARM64, with Linux archives also checked under musl. Pi setup and bridge registration do not invoke npm, npx, or `pi install/update`; `/pi-update` is the explicit maintainer-only update workflow.

Pi's launcher loads `pi-subagents` and `agent-intercom-pi` from the installed local directory. Intercom's broker uses the bundled TypeScript loader, with automatic model wakeups disabled by default (`inboundTrigger: "never"`). Interactive Pi can communicate with compatible peers; Claude/Codex/OpenCode companion adapters are not installed by this Pi-only runtime. Scoped SDK children intentionally do not inherit intercom capabilities.

The first-party bridge, harness configuration, the consumer pin, installation and registration remain in `usr`. The [Pi build campaign](CAMPAIGN-PI-BUILD.md) tracks the remaining headless-profile work.

**Scope:** unrelated `usr` tools may still install or update themselves with npm. This guarantee is about the Pi executable, SDK, bridge dependencies, and Pi extension setup, not every tool in full `sh sync`.

## Pinned models

The [bridge model table](../tools/pi-subagent-bridge/README.md) owns the exact role/model/effort mapping for all three providers.

Pi's default parent model is `opencode-go/deepseek-v4.1-flash` at high. Its global `subagents.modelScope` allows only the pinned OpenCode Go DeepSeek model, the pinned free Zen model, and the pinned Muse SDK model. **The `opencode/inkling-2-small-free` pin is the sole permitted Zen exception** (free tier; declared in `~/.pi/agent/models.json`, scout `low`, mechanic `high`). All other `opencode/*` Zen models, metered endpoints, and custom providers are forbidden even when advertised by a model catalog. No Pi `god` role exists. Claude Code and Codex alone may invoke their existing native `god` models. The SDK bridge independently enforces the role pins and the effective model, effort, and tool allowlists, so Pi settings or a project override cannot silently select another model for bridge workers.

## Install

Run `sh sync plan`, `sh sync`, and `sh sync doctor` from the `usr` checkout. The default tool set includes Pi, Node.js and Command Code. The bridge's pinned Pi SDK and pi-subagents dependencies are symlinked from the SHA-256-verified local Pi runtime into `tools/pi-subagent-bridge`, and its MCP entry is registered for Claude, Pi and OpenCode; Codex uses its tracked MCP entry. Sync migrates recognized legacy `usr-opencode-worker` registrations without disturbing unrelated MCP connections.

Pi authenticates only to OpenCode Go using the existing OpenCode login. In the **untracked and private** `~/.pi/agent/auth.json`:

```json
{
  "opencode-go": {
    "type": "api_key",
    "key": "!opencode2 auth export opencode | jaq -r '.[] | select(.active) | .value.access'"
  }
}
```

Pi resolves the credential command at runtime; OpenCode's OAuth session may need refreshing with `opencode2`. The tracked custom Zen model catalog declares exactly `opencode/inkling-2-small-free` (free) in `~/.pi/agent/models.json`; the Pi SDK authenticates it as the `opencode` provider with the same OpenCode OAuth credential exported as `OPENCODE_API_KEY`. Muse Ember remains only in the Command Code lane; nothing on the Pi path pins it. Command Code uses a separate interactive `cmd login` and runs first. No credentials are committed.

`sh sync` does **not** run `pi install`, `pi update`, or npm for Pi. The tracked package list is empty and a nonempty Pi package list is treated as a sync conflict; the CLI explicitly loads its locally vendored extensions. `sh sync plan` and `sh sync doctor` inspect local postconditions without writing. The bridge uses the single installed Pi runtime, and the tracked user profiles in `~/.pi/agent/agents/` enforce the same tier contract for interactive Pi.

## Worker runtime

Each assignment gets a clean linked worktree under `.work/wt/` and an explicit scope (base HEAD, writable paths, acceptance proof, bounded attempts, stop conditions). On a Pi route, a dedicated SDK host loads the pinned pi-subagents extension and, for Muse, its provider, then calls `subagents:rpc:v1:request` (`spawn`, async) with the exact tier/model/task. Corrections reopen the same durable SDK host session and use native `resume` with the previous run ID. Native worktree allocation is disabled because the external parent already owns the worktree.

The [bridge contract](../tools/pi-subagent-bridge/README.md#safety-and-durability) defines permissible pre-edit fallback and its current limitations (USR-39, USR-41, USR-45). A fallback notice or worker success record is insufficient evidence by itself. The parent independently checks proof, changed paths, HEAD, and the diff; task failures and uncertain admissions do not authorize another provider start.

This is a Git write-scope check, not an OS sandbox. Ignored paths and host-side effects require additional containment such as `sbx` or a VM.

## Coordinating a campaign

Sessions are recorded per repository under `.work/worker-bridge/`, so a parent does not need a hand-maintained lane table. `worker-watch` follows one session and exits on its terminal evidence. `worker-campaign` discovers every `usrw_*.json` under one or more repository roots and blocks until any unacknowledged session becomes terminal:

```
worker-campaign wait [--timeout DURATION] [ROOT...]
worker-campaign ack ID...
worker-campaign list [ROOT...]
```

`wait` exits 0 and prints one `<id> <state> <cwd> <title>` line per newly terminal session (`succeeded`, `failed`, `turn_limit`, `interrupted`), or exits 2 with a one-line `tick: N running` summary after `--timeout` (for example `30m`). Roots may instead be given colon-separated in `$WORKER_CAMPAIGN_ROOTS`. `ack` records IDs under `${XDG_STATE_HOME:-$HOME/.local/state}/worker-campaign/acked`; it is idempotent. `list` prints state, age, worktree, and continuation/steer budgets.

These commands use the shell `worker-watch --state ROOT ID` as a notification aid. It checks PID existence without the bridge's process-start identity check and maps a dead Pi host without a result to `interrupted`; `worker_status` retains an uncertain Pi state and lease. Check bridge status and the actual proof before reusing a worktree. Watcher output does not release a lease.

## One-level native Pi nesting

The tracked native Pi profiles (scout, mechanic, worker, expert, and the Muse-only `muse-worker`) expose `subagent` and declare ordered descendant allowlists. A required child extension registers the capability ceiling from the typed [`tier-policy.ts`](../tools/pi-subagent-bridge/src/tier-policy.ts) graph in each first-level child and its descendants. The SDK checks parsed YAML profile parity and the exact modelScope before a new root launch. Nested/async children inherit that ceiling and `maxSubagentDepth = 2`; second-level agents cannot delegate again. A permitted nested launch uses `subagent({ agent: "mechanic", task: "...", options: { agentScope: "user" } })`; all other nested options are rejected.

Scout → scout; mechanic → scout/mechanic; worker → scout/mechanic/worker; expert → scout/mechanic/worker/expert. No God. A nested call cannot select a model, override tools/provider, create a new worktree, change cwd or use workflow-script launch modes: a code-installed tool-call guard rejects those paths, alongside the upstream `allowedAgents` and depth admission checks. Nested children remain in the assigned worktree; the outer parent must check the combined diff and acceptance proof. This is *not* an OS sandbox against arbitrary shell commands.

**Command Code is still the primary backend and currently remains a leaf.** This change enables nesting in the Pi fallback (Muse or OpenCode Go) only, not Command Code's standalone CLI process; do not claim universal bridge nesting without implementing a separate typed, authenticated child-delegation interface.

## CLI entrypoint

The `pi-subagent-bridge` executable in `~/.local/bin` invokes the same SDK bridge when a harness cannot speak MCP:

```
pi-subagent-bridge model-check /absolute/repo/.work/wt/task worker
pi-subagent-bridge start /absolute/repo/.work/wt/task "Fix one bug" worker /path/scope.json /path/brief.txt
pi-subagent-bridge status /absolute/repo/.work/wt/task usrw_SESSION_ID
pi-subagent-bridge resume /absolute/repo/.work/wt/task usrw_SESSION_ID /path/feedback.txt
pi-subagent-bridge cancel /absolute/repo/.work/wt/task usrw_SESSION_ID
```

It also exposes `pi-subagent-bridge mcp` for JSON-RPC. See the [bridge reference](../tools/pi-subagent-bridge/README.md) for schema and live acceptance checks.

## Verification

Run `TMPDIR="$PWD/.work/tmp" python3 -I tools/pi/test_release_install.py` and `TMPDIR="$PWD/.work/tmp" python3 -I tools/pi/test_offline.py`, then the affected [bridge checks](../tools/pi-subagent-bridge/README.md#tests). The runtime suite installs the pinned archive from `.work/cache/pi-releases`, downloading it once from the pinned release when that cache is empty. It skips runtime checks without a supported Node; skips are not SDK or extension proof. Offline fixtures cannot prove live provider compatibility, authentication refresh, quota, or successful account-backed tool execution. Record those separately using the disposable-worktree live gate.

Pi SDK: https://pi.dev/docs/latest/sdk · pi-subagents RPC: https://github.com/nicobailon/pi-subagents/blob/main/docs/extension-api.md

## Muse subscription integration

After `sh sync` and `muse` → `/login`, the bridge uses the pinned Muse SDK model as
the Pi fallback for the worker tier when Command Code is unavailable or fails before
edits: `muse-sdk/muse-spark-1.3` (xhigh). Scout and mechanic run on the pinned free Zen
model `opencode/inkling-2-small-free` (scout `low`, mechanic `high`); expert runs on
`opencode-go/deepseek-v4.1-flash` (max). No environment flag is required and
`USR_PI_MUSE_SUBSCRIPTION` is ignored. Muse-only nested child profiles preserve
type-checked tier limits and the two-level depth cap. The bridge sets
`PI_MUSE_SDK_CONTRIBUTOR=on` for its Muse workers, so Meta may use prompts, code and
outputs for training.
For a disposable real-account verification and Contributor-mode privacy details,
read [the bridge documentation](../tools/pi-subagent-bridge/README.md).

# Pi

Every coding harness except OpenCode delegates through `pi-subagent-bridge`. The bridge invokes the versioned Pi SDK delegation RPC directly, without `pi -p` or an LLM-driven subagent decision. It owns cross-harness worktree leases and provider selection; pi-subagents owns native execution, completion events and retained-session continuation. See the [bridge reference](../tools/pi-subagent-bridge/README.md#safety-and-durability).

<!-- policy:begin routing-summary -->
<!-- Generated from tools/pi-subagent-bridge/src/policy.ts; run make generate. -->
New `expert` assignments use Antigravity CLI `gemini-4-hydrogen-xhigh` (`xhigh`) exclusively, with no fallback. The available tiers are `scout`, `mechanic`, `worker`, `expert`; there is no `god` tier. The model families `gemini-4-argon` and `gemini-4-carbon` are prohibited, including every effort variant. Already-admitted sessions retain their recorded models and routes.
<!-- policy:end routing-summary -->

## Pinned, npm-free Pi runtime

Pi 1.5.0, its SDK, `pi-subagents`, the Muse provider and `agent-intercom-pi` are built with their transitive dependencies by [`pi-build`](https://github.com/joshuarli/pi-build), which owns the upstream source snapshots, patches, locks, provenance and archives. [`tools/pi/runtime.pin.json`](../tools/pi/runtime.pin.json) pins one prerelease of `pi-build` — currently the `headless-usr` `release-headless-usr-<sha>` prerelease: its URL, builder revision, profile, version, provenance digest, and each target archive's name (`pi-<profile>-<version>-<rust triple>.tar.xz`), SHA-256 and size. GitHub's "latest" release flag does not select it. `sh sync tools pi` downloads only that pinned archive, verifies it against the pin, the release `provenance.json` and `SHA256SUMS`, and installs it. The shared `pi-subagent-bridge` links to the **same** installed closure. Supported platforms: macOS ARM64, Linux x64 and Linux ARM64, with Linux archives also checked under musl. Pi setup and bridge registration do not invoke npm, npx, or `pi install/update`; `/pi-update` is the explicit maintainer-only update workflow.

Pi's launcher loads `pi-subagents` and `agent-intercom-pi` from the installed local directory. Intercom's broker launches natively (compiled JavaScript under `headless-usr`, the bundled TypeScript loader under `full`), with automatic model wakeups disabled by default (`inboundTrigger: "never"`). Interactive Pi can communicate with compatible peers; Claude/Codex/OpenCode companion adapters are not installed by this Pi-only runtime. Scoped SDK children intentionally do not inherit intercom capabilities.

The committed pin selects the `headless-usr` profile. To select another reviewed release (for example the `full` profile or a newer headless build), set `USR_PI_RUNTIME_PIN` to the absolute path of its pin file before running `sh sync tools pi`; a reviewed `full` pin can be taken from Git history. A missing selected pin fails installation without falling back. Both profiles share one runtime selection and the same bridge dependency link, and reverting the pin commit rolls back without a download.

The `headless-usr` profile precompiles bundled extensions and the Intercom broker. It omits maps, SDK declarations, `tsx`, esbuild, and AWS/Smithy. Bedrock requests fail with an explicit unsupported-profile error. Docs, examples, images, the interactive CLI, and OpenCode Go's existing protocols remain available. Sync migrates its managed broker arguments in either direction and preserves custom broker commands.

Sync records `usrBrokerProfile` when it manages the broker configuration. This field distinguishes its native JavaScript launch from an explicit custom `node` command with empty arguments. Custom commands and their arguments remain under your control.

**Changes to the Pi installation go through `pi-build`, never local edits.** If the Pi runtime or a bundled extension (pi-subagents, pi-muse-subscription, agent-intercom-pi) needs a change, it is made in [`pi-build`](https://github.com/joshuarli/pi-build) as a snapshot update or local patch, released there, and adopted in `usr` through a reviewed release pin. Do not hand-patch the installed closure under `~/.pi/agent` or the install prefix, drop extra extensions into it, or fork its dependencies locally. Tracked first-party configuration (bridge, profiles, settings) lives in `usr` and is changed there; it never requires touching the runtime.

The first-party bridge, harness configuration, the consumer pin, installation and registration remain in `usr`. The [Pi build campaign](CAMPAIGN-PI-BUILD.md) tracks the remaining headless-profile work.

**Scope:** unrelated `usr` tools may still install or update themselves with npm. This guarantee is about the Pi executable, SDK, bridge dependencies, and Pi extension setup, not every tool in full `sh sync`.

## Pinned models

The generated [bridge model table](../tools/pi-subagent-bridge/README.md) lists exact models, efforts and ordered fallbacks. `make policy` exports the same approved policy as JSON without live account checks.

Pi parent session defaults remain in its tracked settings. The generated subagent fields and native profile frontmatter follow the typed nested policy. The native Pi expert profile belongs to the nested domain and supports already-admitted legacy sessions; it does not authorize new root expert dispatches through Pi. The SDK validates model, effort and tool allowlists independently of project overrides. Contributor Muse routes permit Meta to use prompts, code and outputs for training.

## Why Zen is not a pin

`opencode/inkling-2-small-free` looked like a zero-cost fit for scout and mechanic, and was pinned for them. It cannot work from a headless SDK worker: **every free Zen model answers non-official-client requests with `429 FreeUsageLimitError`, regardless of account, API key, IP, session headers or quota window.** The upstream gateway only serves free capacity to traffic carrying the official OpenCode client's `User-Agent` (`opencode/…`); the `x-opencode-client`, `x-opencode-session` and `x-opencode-version` headers do not unlock it, and non-opencode User-Agents get the 429 from anywhere. Interactive opencode sessions keep working, which masks the gate completely. Verified locally against the live endpoint on 2026-11-12 (see `tools/pi-subagent-bridge/test/hybrid.test.ts` fixtures and the bridge admission logs). opencode has confirmed this is intended: "Free models are meant for use inside OpenCode … for an application integration, use a paid model or Go" ([issue](https://github.com/anomalyco/opencode/issues/43786), [issue](https://github.com/anomalyco/opencode/issues/42074), [issue](https://github.com/anomalyco/opencode/issues/42029), [issue](https://github.com/anomalyco/opencode/issues/58205)). Routing bridge traffic through the official client path would mean spoofing the client's `User-Agent`, an anti-abuse gate the bridge deliberately does not evade; a local `opencode serve` passthrough was rejected as fragile and unsupported. Contributor Spark on OpenCode Go is the subsidized paid lane and is what scout and mechanic pin.

## Install

Run `sh sync plan`, `sh sync`, and `sh sync doctor` from the `usr` checkout. The default tool set includes Pi, Node.js and Command Code. The bridge's pinned Pi SDK and pi-subagents dependencies are symlinked from the SHA-256-verified local Pi runtime into `tools/pi-subagent-bridge`, and its MCP entry is registered for Claude and Pi; Codex uses its tracked MCP entry. OpenCode never registers the bridge (see `orchestrate`); sync removes an owned OpenCode registration. Sync migrates recognized legacy `usr-opencode-worker` registrations on the Claude and Pi paths without disturbing unrelated MCP connections.

Pi authenticates only to OpenCode Go using the existing OpenCode login. In the **untracked and private** `~/.pi/agent/auth.json`:

```json
{
  "opencode-go": {
    "type": "api_key",
    "key": "!opencode2 auth export opencode | jaq -r '.[] | select(.active) | .value.access'"
  }
}
```

Pi resolves the credential command at runtime; OpenCode's OAuth session may need refreshing with `opencode2`. Pi authenticates only to OpenCode Go with that credential (exported as `OPENCODE_API_KEY`); there is no Zen access from the Pi path. Muse Ember remains only in the Command Code lane; nothing on the Pi path pins it. Codex subscription runs first using `codex login` with ChatGPT. Command Code uses a separate interactive `cmd login` and runs second. No credentials are committed.

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

The generated [nesting table](../tools/pi-subagent-bridge/README.md#bounded-native-pi-nesting) lists the permitted descendants, including legacy Pi expert sessions. A nested call cannot select a model, override tools/provider, create a new worktree, change cwd or use workflow-script launch modes: a code-installed tool-call guard rejects those paths, alongside the upstream `allowedAgents` and depth admission checks. Nested children remain in the assigned worktree; the outer parent must check the combined diff and acceptance proof. This is *not* an OS sandbox against arbitrary shell commands.

**Codex is the primary backend. Codex and Command Code remain leaves.** This change enables nesting in the Pi fallback (Muse or OpenCode Go) only, not Command Code's standalone CLI process; do not claim universal bridge nesting without implementing a separate typed, authenticated child-delegation interface.

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

After `sh sync` and `muse` → `/login`, the bridge uses the Muse SDK fallback from the generated routing table when earlier approved routes cannot run before edits. Native Muse child profiles preserve the typed tier limits and depth cap. No environment flag selects the route; `USR_PI_MUSE_SUBSCRIPTION` is ignored. The bridge sets `PI_MUSE_SDK_CONTRIBUTOR=on`, so Meta may use prompts, code and outputs for training.
For a disposable real-account verification and Contributor-mode privacy details,
read [the bridge documentation](../tools/pi-subagent-bridge/README.md).

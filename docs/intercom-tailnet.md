# Intercom across the tailnet

`intercom-tailnet` connects explicitly enrolled **coordinator sessions** in Pi,
Claude Code, Codex and OpenCode to one hub on an always-on tailnet host. The hub
routes messages between enrolled coordinators. Scoped bridge workers, including
native Pi SDK children and their descendants, remain outside Intercom.

The launcher requires a reviewed `pi-build` release containing
`broker/tailnet-admin.js` (or its TypeScript entry in the full profile). It fails
clearly if the installed pin predates that implementation. Installing this
launcher alone does not upgrade the runtime or enable a network listener.

Before starting Claude, Codex or OpenCode, the launcher compares that adapter's
installation receipt with the **selected installed runtime**, including the
builder revision, archive and checksum. An older or missing companion fails
before the harness starts, so it cannot silently ignore the remote settings and
connect locally. `USR_PI_RUNTIME_PIN=/absolute/reviewed-pin.json sh sync` applies
the same reviewed override to both the runtime and its companions. The launcher
checks installed receipts rather than assuming that setting this variable
completed an upgrade. A partial upgrade fails closed.

## One-time hub setup

Choose an always-on Linux machine, a port allowed by your tailnet policy, and its
literal Tailscale address. The examples use `100.100.100.11:47831`; replace that
address with the hub's actual address. Both `100.64.0.0/10` and Tailscale IPv6
addresses in `fd7a:115c:a1e0::/48` are accepted. DNS names, public addresses,
loopback TCP and wildcard binds are rejected.

Install the reviewed runtime and companion pin using the normal
[Pi installation](pi.md#install), then start the hub in the foreground:

```sh
intercom-tailnet hub --listen tcp://100.100.100.11:47831
```

Run that command under your existing host supervisor when ready. The launcher
does not install a system service or change Tailscale, firewall, or SSH settings.
The broker retains its private local Unix socket for local administration.

Hub state is separate from interactive Pi:
`${XDG_STATE_HOME:-$HOME/.local/state}/agent-intercom/hub`. Use the same absolute
`--hub-dir` for `hub`, `enroll`, `inspect` and `revoke` when overriding it. Do not
point a normal interactive Pi session at that directory. This keeps an older
automatically spawned local broker from sharing the coordinator registry.

## Enroll a coordinator

Leave the hub running. In another shell on the hub host, create a distinct
credential for each coordinator session:

```sh
intercom-tailnet enroll --fleet default --host mac --name main \
  --output "$HOME/.config/agent-intercom/mac-main.json"
```

The admin command creates a new private file and refuses to overwrite an existing
one. Transfer it privately to the coordinator host, keep it owned by the user
running that harness with mode `0600`, and remove any unnecessary transfer copy.
Do not put the credential in Git, paste its contents into prompts, or reuse one
coordinator credential for concurrent sessions. The enrollment credential is
replaced in place by the runtime's persisted session credential on first use, so
the file must remain writable. `--ttl-ms` and `--session-ttl-ms` override enrollment
and session lifetimes when needed. The defaults are ten minutes to enroll and
30 days for the resulting session; start the coordinator before enrollment
expires. The broker presents the identity as `HOST/NAME`, such as `mac/main`.

Start the desired top-level harness with the endpoint and credential explicitly:

```sh
intercom-tailnet run --endpoint tcp://100.100.100.11:47831 \
  --credential "$HOME/.config/agent-intercom/mac-main.json" -- pi
```

Use `-- claude`, `-- codex`, `-- opencode`, or `-- opencode2` for another harness;
their existing arguments follow the executable. Each concurrent coordinator
needs its own enrollment. The Codex MCP registration forwards the selected
endpoint and credential path to its Intercom adapter. Claude's local MCP process
and the OpenCode plugin inherit those variables from the wrapped harness.

The wrapper removes inherited Intercom settings before adding the two selected
client settings. It does not export them into your shell, persist them in global
harness configuration, or enable a listener on the coordinator machine. A Mac
with inbound tailnet access disabled can make an outbound connection to the hub.

For an explicitly configured SSH Unix-socket forward, use
`--endpoint unix:///absolute/forwarded.sock`. Forward the hub's **remote gateway**
socket, not its privileged local broker/admin socket. The remote credential is
still required. The launcher does not create or manage the SSH connection.

## Observe and revoke

Check local installation and credential permissions without contacting the hub:

```sh
intercom-tailnet doctor --endpoint tcp://100.100.100.11:47831 \
  --credential "$HOME/.config/agent-intercom/mac-main.json"
```

Add `--connect` to test transport reachability with a three-second timeout. A
successful connection alone does not prove enrollment, authentication, routing,
or a model response. `doctor` never enrolls a session or sends an agent message.

On the hub host, inspect enrollment/session summaries without printing secrets,
or revoke one session. Use the `id` of the intended coordinator returned by
`inspect` in place of `SESSION_ID`:

```sh
intercom-tailnet inspect --fleet default
intercom-tailnet revoke --session SESSION_ID
```

Administration is local to the hub's private Unix socket and admin credential.
Running these commands inside a remotely configured coordinator shell does not
redirect administration to the remote endpoint.

## Coordinator and worker boundaries

The remote listener accepts explicitly enrolled coordinator identities. A
network route through Tailscale does not by itself authorize a session. Use a
fleet to group coordinators that may discover and message each other; the hub
owns enrollment and routing authorization.

The bridge strips all `AGENT_INTERCOM_*` and legacy `PI_INTERCOM_*` variables from
Pi SDK and every CLI worker process, including Codex, Command Code and
Antigravity. It marks those children `USR_SCOPED_WORKER=1`; the launcher refuses
worker-marked callers, including native Pi children. The SDK entry repeats the
scrub before launching nested children. Its extension loader still disables
discovery and includes only the existing scoped subagent/Muse/guard extensions.
It does not load Intercom. This is a runtime capability boundary, not an OS
sandbox against arbitrary code running as the same Unix user.

Existing Pi behavior stays deliberate: `confirmSend: true` requires confirmation
for sends that need it, and `inboundTrigger: "never"` queues incoming messages
without waking the model. Reachability does not promise autonomous chatter or
allow Intercom to bypass worker admission, worktree leases, or parent review.

## Verification before relying on it

Local fixture checks:

```sh
python3 -I tools/intercom-tailnet/test_intercom_tailnet.py
node --experimental-strip-types --test tools/pi-subagent-bridge/test/worker-env.test.ts
```

They prove launcher argument/environment boundaries, endpoint rejection, private
credential checks, old-runtime failures and worker environment isolation. They do
not prove a connection between two physical hosts or a complete real-harness
conversation.

### Two-host qualification

After both hosts run the reviewed runtime, qualify the deployment from the
coordinator host. SSH must reach the hub host without a prompt, and both hosts
need `tmux` and a `usr` checkout at `~/usr`:

```sh
python3 -I tools/intercom-tailnet/qualify.py --hub-ssh josh@lisa \
  --hub-address 100.68.104.43 --hub-label lisa --local-label mac
```

It starts a disposable hub with its own state directory, port (`--port`,
default 47839) and fleets. It does not touch a running hub. It drives
interactive Pi coordinators in `tmux` on both hosts through the Intercom overlay
shortcut and checks:

- the listener binds only the tailnet address;
- discovery and delivery in both directions;
- identity retention across a restart;
- isolation between fleets;
- rejection of a forged enrollment;
- inspect output without secrets;
- revocation, including reconnect with the old credential;
- launcher refusal of scoped workers;
- a bounded error after the hub stops, without starting a local broker.

Each coordinator runs with the tracked Pi settings and Intercom policy but no
`auth.json`. Any model turn, including an automatic wakeup on an incoming
message, would leave a local provider error. The run fails if one appears and
never spends provider budget. Everything it starts is stopped, and its scratch
is removed unless you pass `--keep`.

The qualifier does not cover these:

- Claude, Codex or OpenCode coordinator pairs, which need model turns;
- a scoped Pi bridge worker launched from an enrolled coordinator.

Exercise those separately before relying on them.

Results on 2026-11-14, runtime `pi-build` `f6fc723` (usr `a34fdcc`), with hub
`lisa` (Alpine x86_64) and coordinator `mac` (macOS arm64):

- The qualifier passed all checks on three consecutive runs; the last followed
  tightening the roster check to an exact peer set.
- A manual Pi (`lisa`) and Claude Code (`mac`) pair delivered in both
  directions. Claude saw only its fleet peer. Pi received
  `From: mac/a1 [remote:mac]`, and Claude's `intercom_pending` showed the Pi
  sender with `remotePolicy: remote-fleet` and `trustedLocal: false`.
- Codex and OpenCode pairs and a real scoped bridge worker remain unverified.

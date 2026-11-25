# Model policy projections

[`harnesses.json`](../../harnesses.json) is the single on/off control for every
harness and subscription provider. Flip one boolean, then run `make generate`.
Disabled harnesses disappear from shared instructions, delegation tables and
resume suggestions; their configured pins and authored definitions remain in
source so enabling the same switch restores them. Runtime launch and probe
guards read the switches directly. `opencode-go` controls the headless provider
independently of the native `opencode` harness, while `pi` disables all SDK lanes.
No enabled route means a blocked tier; generation never invents a replacement.

Root admission plans and native exceptions are authored in
[`policy.ts`](../pi-subagent-bridge/src/policy.ts): `ROOT_PLANS` holds one typed
`RootPlan` per admitted bridge tier (`scout`, `mechanic`, `worker`: Codex,
Command Code and an ordered Pi list), and `routesOf` derives the ordered route
list that the JSON export, the tables and the MCP summary share after applying
the harness switches. `expert` has one configured SDK route and no provider
fallback; native parents keep their own expert lanes. Nested Pi pins, tool sets and
descendant ceilings are authored in
[`tier-policy.ts`](../pi-subagent-bridge/src/tier-policy.ts). The first module
composes both domains into one pure `POLICY` value. Runtime code imports these
typed sources; it never imports generated JSON or parses Markdown.

The [bridge safety contract](../pi-subagent-bridge/README.md#safety-and-durability)
owns admitted model snapshots, legacy decoding, request validation and worktree
leases. Policy changes preserve those contracts. Session defaults and
instruction-profile selection remain outside the policy generator's ownership.

From the repository root, with the supported Node runtime:

```
make generate
make check-generated
make policy
make subagent-visualization
```

`generate` renders checked-in policy tables, bounded instruction blocks, native
Pi profile fields, Pi subagent settings, OpenCode tier models, Command Code native agent model/effort pins, and
Antigravity native agent tier selectors, Copilot native pilot agent pins, plus synchronized global instructions.
`policy.generated.json` is the same deterministic export for Python consumers.
`policy` prints that JSON without reading credentials or probing providers.
Live availability belongs to `worker_model_check`.
The installed `pi-subagent-bridge policy` command exposes the same pure export.
`subagent-visualization` renders [`docs/subagents.html`](../../docs/subagents.html),
a self-contained HTML decision graph of the delegation architecture from the
same typed export. Lane hue marks the lane kind (native, bridge primary,
fallback, undefined or opt-in pilot), shade and bar mark model effort, rank
badges mark the fallback order, and tier pills mark the assignment tier.
`check-generated` verifies it stays current.

Edit the policy, run `make generate`, and review the generated diff. Session
defaults, profile descriptions, unrelated harness settings and authored
instructions remain outside generator ownership. Pi expert profiles back the
first-class Pi expert bridge lane.

[`templates/pi-settings.json`](templates/pi-settings.json) is the authored source
for Pi settings. Edit session defaults and per-profile custom settings there;
`dotfiles/base/.pi/agent/settings.json` is its generated effective projection.
The template omits managed model pins, which still come from the typed policy.
Generation omits disabled profiles from `agentOverrides` and `modelScope.agents`,
filters the model allowlist, and filters each profile's `allowedAgents` to
installed enabled children. This keeps the SDK from resolving absent profiles.
Custom settings survive toggling because they remain in the source template.


Named `policy:begin` / `policy:end` blocks are the only Markdown template
mechanism. Their reversible templates live in `generate.ts` and
`harness-context.ts`, outside installed agent context. Native-parent instructions
share one block so disabled harness names do not survive as empty markers;
disabled content is removed, never hidden in comments. Rendering rejects missing, duplicate, nested, malformed and unknown
markers before changing any output. Native profile frontmatter uses the same
markers in YAML comments. Generated documents are ordinary, complete files;
session hooks and installed harnesses never run a renderer.

Every input is read and every result rendered before writing. Unchanged files
are untouched; a second generation is a no-op. Changed outputs are staged beside
their destination and individually renamed. A process crash between renames can
leave a partial generation; `make check-generated` detects it and rerunning
`make generate` repairs it. If an interrupted writer leaves a `.policy-tmp` file,
inspect and remove that staging file after the writer has stopped, then rerun.
Generation does not change the home configuration or
perform installation. It requires neither the Pi SDK nor npm packages.

When a role is removed, the previous JSON export identifies formerly managed
entries only to detect leftovers. Generation refuses to proceed while a retired
native profile or harness entry remains and names the exact removal required.
It never deletes a profile body, custom agent or configuration object based on
that snapshot. Remove the retired entries explicitly and regenerate. Malformed
snapshots fail before any output is changed.

`check-generated` is read-only and reports stale paths. Both `sh sync check` and
the dedicated policy workflow run it. It never consults the policy claim and is
never blocked by one. The focused regression command is:

```
node --test tools/policy/generate.test.ts
node --test tools/policy/claim.test.ts
python3 -I dotfiles/orchestrate-test.py
```

## The shared policy claim

Two sessions once edited the model policy concurrently in different worktrees
of this checkout; the collision surfaced only when a push was rejected, after
both had built and tested, and a seventeen-file rebase followed. The policy
claim exists so the second session learns at the start of policy work, not at
push, that another live session holds the area.

The claim is one JSON record at `<checkout root>/.work/policy-claim/claim.json`,
where the checkout root is the parent of the Git common dir
(`git rev-parse --git-common-dir`), so every worktree of the checkout resolves
to the same file. It sits beside the bridge's shared state under the ignored
`.work/` tree. The record names the owner (the first agent/session identifier
found in the environment — `USR_SESSION_ID`, then the Claude, Pi, Codex,
OpenCode, Devin or generic agent session variables — else `user@host`), the
branch, the worktree path, the session process id and the start time. The pid
is chosen by walking the ancestor chain past transient `sh -c` command shells
and `make` to the long-lived harness or interactive shell. The age bound is
the final guard in both directions: no claim can be taken over within it
whatever the guess, and an abandoned claim is always recoverable after it. Sessions on other machines or in other
clones are out of scope: the file is local to this checkout, and a record
whose host differs cannot have its process verified, so the age bound alone
decides those.

A claim is stale only when its recorded process is gone (or unverifiable
across hosts) **and** its age exceeds twelve hours — never on one signal
alone. A live process keeps its claim indefinitely; a young claim outlives a
racy or mis-recorded pid. Nothing expires silently: every takeover or removal
reports the prior record, the liveness reading and the age comparison. A
corrupt claim file blocks with instructions until it ages past the bound.

Enforcement sits where policy edits become real. Write-mode generation
(`make generate`, `tools/policy/generate.ts`) refuses to run while another
live session holds the claim, naming the holder's branch, owner and start time
plus the commands to inspect or break it; a stale claim is reported and taken
over for the calling worktree. `--check` and `--json` never consult the claim.
The management commands are:

```
make policy-claim     # claim the area before editing model policy
make policy-claims    # show the current claim and its staleness reading
make policy-release   # release this worktree's claim when policy work is done
```

`node tools/policy/claim.ts break` force-removes a claim after coordinating
with its owner; it prints the removed record. Generation without any claim
still proceeds — the claim is an advisory contract between sessions, kept
lightweight so agents and humans actually follow it — but no write-mode
generation ever runs over another live session's claim. Mutations are
serialized by a lock directory with an abandoned-lock bound, so concurrent
claimants cannot silently overwrite each other.

The generator tests prove reproduction, ownership and propagation. They disable
each switch independently, disable every harness together, and restore the
original instructions byte-for-byte after reenabling; repeated generation in
either state is a no-op. One
hand-written list names every remaining policy dimension (Codex and
Command Code pins per lower tier, the Pi fallback list, OpenCode, native
fallback, direct Antigravity models, banned families and each native Pi field);
each entry must change a rendered projection other than the JSON export or be
rejected. Command Code top-level parents use native `usr-*` agents; Command CLI
rows in bridge `rootRoutes` remain leaf fallback executors for other parents. Add a line there when a dimension is added. The native-fallback
reasons, the OpenCode bridge and free-parent rules and the direct-model
availability check have fixed meaning and are stated in the renderer prose, not
exported. Independent
bridge behavior tests establish approved routing and fallback behavior; matching
generated representations alone does not establish policy correctness.

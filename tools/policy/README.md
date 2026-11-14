# Model policy projections

Root admission plans and native exceptions are authored in
[`policy.ts`](../pi-subagent-bridge/src/policy.ts): `ROOT_PLANS` holds one typed
`RootPlan` per tier (an exclusive terminal executor, or Codex, Command Code and
an ordered Pi list), and `routesOf` derives the ordered route list that the JSON
export, the tables and the MCP summary share. Nested Pi pins, tool sets and
descendant ceilings are authored in
[`tier-policy.ts`](../pi-subagent-bridge/src/tier-policy.ts). The first module
composes both domains into one pure `POLICY` value. Runtime code imports these
typed sources; it never imports generated JSON or parses Markdown.

From the repository root, with the supported Node runtime:

```
make generate
make check-generated
make policy
```

`generate` renders checked-in policy tables, bounded instruction blocks, native
Pi profile fields, Pi subagent settings and OpenCode tier model fields.
`policy.generated.json` is the same deterministic export for Python consumers.
`policy` prints that JSON without reading credentials or probing providers.
Live availability belongs to `worker_model_check`.
The installed `pi-subagent-bridge policy` command exposes the same pure export.

Edit the policy, run `make generate`, and review the generated diff. Session
defaults, profile descriptions, unrelated harness settings and authored
instructions remain outside generator ownership. Pi expert profiles preserve
the nested/legacy contract; root expert admission is a separate terminal route.

Named `policy:begin` / `policy:end` blocks are the only Markdown template
mechanism. Rendering rejects missing, duplicate, nested, malformed and unknown
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
the dedicated policy workflow run it. The focused regression command is:

```
node --test tools/policy/generate.test.ts
python3 -I dotfiles/orchestrate-test.py
```

The generator tests prove reproduction, ownership and propagation. One
hand-written list names every remaining policy dimension (expert, Codex and
Command Code pins per lower tier, the Pi fallback list, OpenCode, native
fallback, direct Antigravity models, banned families and each native Pi field);
each entry must change a rendered projection other than the JSON export or be
rejected. Add a line there when a dimension is added. The native-fallback
reasons, the OpenCode bridge and free-parent rules and the direct-model
availability check have fixed meaning and are stated in the renderer prose, not
exported. Independent
bridge behavior tests establish approved routing and fallback behavior; matching
generated representations alone does not establish policy correctness.

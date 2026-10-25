# Pinact architecture

Pinact is one Python launcher with three command paths: legacy SHA pinning, `lint`, and `fix`.
The launcher finds `tools/pinact/src/pinact` relative to itself, so the installed symlink works from
any current directory and under `python3 -I`.

## Input model

`model.py` reads each lint input once and composes it with the vendored pure-Python YAML parser.
The source text, line endings, document nodes, and source marks stay together in `SourceDocument`.
The parser uses `BaseLoader`, so values remain strings and workflow keys such as `on` are not
reinterpreted as booleans. Duplicate keys and syntax errors are retained for diagnostics.

Linting runs structural checks from `workflow.py`, bounded expression analysis from
`expressions.py`, security checks from `security.py`, and action reference checks from
`pinning.py`. Rules share the source document and node tree. Dynamic values that cannot be proved
remain unknown; closed-world validation is limited to enumerated workflow fields.

Catalog parsing and approval live in `catalog.py`. A caller supplies the path explicitly. Lint
does not resolve refs over the network. Pinning commands resolve refs with Git, and `fix` only
does so when `--pin` is explicitly selected without a catalog.

## Fix plan

`fixes.py` creates byte-span edits against the original UTF-8 source. It never serializes a YAML
tree back to text. Each edit carries expected source bytes, a replacement, and its rule. The edit
engine sorts edits, rejects overlaps and mismatched preconditions, and combines the untouched source
spans with replacements.

Before writing, the fixer checks the targeted finding, lints the result, reparses it, and confirms
the same fix is no longer proposed. `--diff` returns the proposed patch without writing. A normal
fix checks the source again and atomically replaces each changed file while preserving its mode.
Unsafe paths, changed inputs, unsupported forms, and invalid catalog policy are rejected.

## Module ownership

| Module | Owns |
| --- | --- |
| `cli.py` | Dispatch to pin, lint, and fix commands |
| `model.py` | YAML source documents, duplicate keys, source positions |
| `workflow.py` | Workflow and action schema, event, job, permission, and matrix checks |
| `expressions.py` | Expression lexing, parsing, interpolation, and bounded context checks |
| `security.py` | Checkout credentials, permissions, dangerous triggers, injection, and exposure checks |
| `pinning.py` | Action reference discovery, Git resolution, and atomic pinning |
| `catalog.py` | Explicit approved-pin catalog parsing and comparisons |
| `fixes.py` | Safe source-span edits, validation, and writes |

PyYAML 6.0.3 is vendored as pure Python with its MIT license and source details in
`src/pinact/_vendor/yaml/`. Pinact does not import installed packages or require runtime package
installation.

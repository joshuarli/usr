# Coding Style

- Prefer the simplest correct solution. No premature abstraction, no unnecessary dependencies.
- Vet every dependency before adding — fewer is always better.
- Never add banner/separator comments (`// ---`, `# ====`, `// ── Section ──`, etc.). No exceptions.
- Never remove useful comments during refactors. Comments that explain *why* something exists, document non-obvious constants, or clarify tricky behavior must be preserved. Update them if the code changes, but don't silently drop them.

# Agent Discoverability

- Agents navigate by filenames and text search. Prefer distinctive,
  domain-specific names over generic names and ambiguous abbreviations.
- Keep related modules, tests, and docs discoverable with matching names; name
  tests after the source or behavior they cover.
- In docs, pair every important concept with the exact grep targets: symbols,
  types, enum variants, module paths, commands, or test names. Prefer “the
  `Parser::parse()` path in `src/parser.rs`, covered by
  `tests/parser.rs::parse_pipeline`” over generic descriptions alone.
- Put important explanations above the definitions they describe. Explain why,
  invariants, platform workarounds, and intentional absences.
- Use precise types, narrow interfaces, and one spelling per concept. Mark
  legacy paths clearly and avoid new references to them.

# Terminology and Trust

- Use established domain terminology. Define a short glossary when related
  concepts could be confused, and distinguish raw input, parsed structure,
  transformed values, runtime state, and output.
- Write documentation in two layers: explain the concept in domain terms, then
  name the concrete code objects that implement or test it. Keep those names
  current when code moves or is renamed.
- Separate dependency capability from product behavior; document the supported
  contract. Treat docs as interface and update stale architecture or behavior.
- Prefer comments that explain why, constraints, ownership, and boundaries.

# Change Workflow

- Before editing, inspect applicable `AGENTS.md` files, worktree status, module
  boundaries, tests, and behavior docs. Use text and filename search for all
  definitions, call sites, tests, and documentation.
- Preserve unrelated user changes. Keep patches focused and fix root causes
  rather than speculative cleanup. During renames, update definitions, callers,
  tests, comments, docs, and old-reference searches together.
- Prefer a small coherent patch over broad reorganization. For behavior changes,
  add the smallest contract test and update user-facing docs.
- Use compiler errors, focused tests, and repository search as feedback loops;
  do not leave known stale references or docs.

# Committing

- Do NOT run pre-commit hooks. User verifies commits independently.
- Never push to a remote. No `git push`, no `--force`. Leave pushing to the user.

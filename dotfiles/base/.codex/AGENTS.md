# Workflow

- Prioritize test-driven development. Avoid trivial unittests.
- Bugfixes must NOT be speculative; author a minimal best-effort isolated reproduction
  in the form of a regression test that fails, then the bugfix must pass it.
  - Test harnesses must be structured to isolate as much state as possible.
- Temporary workarounds that are not root cause fixes are only acceptable if documented
  and absolutely necessary to unblock a higher priority fix. Circle back to remove such
  workarounds once the broader fix is implemented.

# Coding Style

- Prefer distinctive, domain-specific names over generic names and ambiguous abbreviations.
  Code must be easily disambiguated and greppable.
- Keep related modules, tests, and docs discoverable with matching names; name
  tests after the source or behavior they cover.
- Use precise types, narrow interfaces, and one spelling per concept. Mark
  legacy paths clearly and avoid new references to them.
- Never add dependencies. They are only added in consultation with the user.
- Comments that explain *why* something exists, document non-obvious constants,
  or clarify tricky behavior must be preserved. Update them if the code changes, but don't silently drop them.

# Documentation

- Pair every important concept (symbols, types, enum variants, module paths,
  commands, test names) with exact grep targets formatted as `target`.
- Write documentation in two layers: explain the concept in domain terms, then
  name the concrete code objects that implement or test it. Keep those names
  current when code moves or is renamed. Define a short glossary in AGENTS.md
  when related concepts could be confused.

# Committing

- Do NOT run pre-commit hooks. User verifies commits independently.
- Never push to a remote. No `git push`, no `--force`. Leave pushing to the user.

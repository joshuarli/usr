---
name: single-source-of-truth
description: "Apply when the same fact, closed set, default, or limit is defined in more than one place, or when adding a setting whose default or limit other code must also know. Skip a constant used once, locally."
---

# Single Source of Truth

Facts may have many consumers but one owner.

- **Merge facts that must evolve together, not code that looks alike.** A wire model and a domain model are different contracts. Centralize the mapping between them instead.
- **Name the authority** (the type, a declarative schema, a registry, the database schema, an upstream spec) and derive everything else one way. Never circular, and never make generated output the authority when its input exists.
- **A "keep in sync" comment is an alarm.** Remove the synchronization work. Where the copy is irreducible (language boundary, public protocol, docs), name the authoritative side, say why the copy exists, and add a test that fails loudly when they drift.
- **Prefer a readable declaration to metaprogramming.** Do not build a generator to remove three harmless lines.
- **If existing copies disagree, investigate.** Do not silently pick one.
- **Settings are policy with one typed home.** Classify first: runtime setting, application policy, protocol constant, local constant. Protocol constants stay with the format that owns them. A setting has one default. Read raw sources (CLI, env, config files) once at one boundary, resolve precedence there, and pass typed values with units (`Duration`, `NonZero*`). Reject invalid combinations at construction. Do not merge two `30`s because the literals match, do not build a `constants` drawer, and do not add mutable global configuration.

**The test:** add one variant or setting. Exactly one place changes, or a test names the others.

Afterward, search for each retired copy and spelling and classify what remains. Preserve existing defaults and precedence unless asked to change them.

**Reply:** each fact and its new owner, plus intentional duplicates and the drift test that guards each.

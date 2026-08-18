You are improving an existing codebase so coding agents can reliably discover the
definitions, callers, contracts, tests, and documentation relevant to a task using
ordinary filename and text search.

The goal is a codebase whose names, paths, types, boundaries, and explanations make
the shortest useful path from a task description to the right code. Preserve runtime
behavior and public contracts unless this request explicitly changes them.

First inspect the repository before editing:

- Inventory the important domain concepts and their definitions, callers, methods,
  types, file paths, tests, fixtures, documentation, configuration, exports, aliases,
  and legacy implementations.
- Use `rg --files` and focused `rg` searches to see how an agent would actually find
  those concepts. Search both symbol names and likely task vocabulary.
- Identify generic names, inconsistent spellings, monolithic or grab-bag modules,
  implicit contracts, duplicated implementations, and stale paths.
- Run the narrowest useful baseline compiler, type checker, and focused tests before
  changing code. Record failures that predate the work.
- Preserve existing valid behavior, APIs, output, side effects, permissions, and
  state transitions unless an intentional change is part of the request.

## Non-negotiable design

### 1. Treat text search as a navigation boundary

Assume that a coding agent will commonly navigate with commands such as:

```text
rg --files | rg -i 'delivery-history|deliveryHistory|delivery_history'
rg -n 'calculateNotificationRetryBackoff'
```

Design important concepts so a focused search reaches the relevant definition in one
or very few hops. A compiler, language server, repository map, or semantic index may
help, but it must not be the only way to locate or understand the code.

Names and paths are search interfaces. Every important concept should have a stable,
distinctive textual handle that appears at its definition and at meaningful uses.
Prefer a precise domain term over a short name that happens to be locally clear.

Do not optimize for fewer characters, cleverness, or accidental reuse of a familiar
generic word. Optimize for signal: a search should return the definition, its relevant
callers, its tests, and its documentation without a large unrelated haystack.

### 2. Choose one canonical, domain-specific vocabulary

Choose one spelling for each concept and use it consistently in:

- directories and file names
- modules, classes, functions, methods, constants, events, and errors
- parameters, local variables, and type names
- imports, exports, configuration keys, tests, fixtures, examples, and docs

Prefer names such as:

```text
createStripeClient
NotificationDeliveryHistory
calculateNotificationRetryBackoff
OrganizationId
```

over names such as:

```text
create
data
manager
helper
utils
config
result
```

Generic words are acceptable only when the surrounding scope makes the concept truly
unambiguous. Otherwise qualify the name with the domain, operation, resource, or
state it represents. Name methods as carefully as top-level functions: a method call
often has no import or module trail, so its method name may be the agent's only useful
search handle.

Do not use synonyms or arbitrary aliases for one concept, such as `organizations` in
one area and `customers` in another, or `orgId` beside `organizationId`. If an alias is
required for compatibility or an external protocol, keep the canonical internal name,
document the boundary, and mark the alias as legacy where the language supports it.

Do not rename a public concept merely to satisfy a preference. When a rename is
needed, inventory all references first and migrate the vocabulary coherently.

### 3. Make files and module boundaries carry domain meaning

Name directories and files after the concept they own. Keep a related definition,
implementation, and focused tests easy to find together. Prefer boundaries such as:

```text
notifications/
  notification-delivery-history.ts
  notification-retry-backoff.ts
  notification-delivery-history.test.ts
```

over a large module whose ownership is hidden behind names such as `helpers.ts`,
`utils.ts`, `common.ts`, `misc.ts`, or `manager.ts`.

Split a monolith or grab-bag module when a coherent domain boundary makes retrieval,
reasoning, and testing clearer. Keep each resulting module responsible for a
searchable concept or tightly related set of concepts. Do not fragment code to meet
an arbitrary line count, and do not move code without updating every reference.

Avoid relying on package specifiers, barrel files, or wildcard re-exports to convey
ownership. They may remain when they are part of the public API, but important symbols
must still have distinctive names and an obvious definition. Prefer explicit exports
when that makes the source of a concept easier to search.

Name test files after the source concept they cover, for example
`stripe.test.ts` for `stripe.ts` or `delivery_history_test.py` for
`delivery_history.py`. Test names should include the behavior or invariant they
exercise so a search for a requirement reaches the test as well as the implementation.

### 4. Make contracts and state transitions explicit in types

Give functions, methods, public values, and important internal boundaries precise
input and output types. A signature should tell an agent what the code accepts,
returns, mutates, and may reject without requiring a full implementation read.

Avoid `any`, untyped dictionaries, implicit dynamic values, and broad primitive types
when a domain contract is available. Use the strongest suitable representation for
the language:

- distinct or branded types/newtypes for semantically different identifiers
- enums or tagged unions for finite states and state transitions
- explicit result/error types for failure behavior
- units and value objects for quantities that must not be interchanged
- named request, response, configuration, and event types

For example, prefer:

```text
transferOwnership(userId: UserId, organizationId: OrganizationId,
                  projectId: ProjectId) -> TransferOwnershipResult
```

over three interchangeable `string` parameters and an untyped return value. Precise
types should let the compiler catch swapped arguments, invalid states, and unsupported
transitions. They should also provide useful, searchable names when an agent follows a
type-checker error.

Use `unknown` or an equivalent opaque type at an untrusted boundary when appropriate,
then validate and narrow it. Do not spread an escape hatch through the rest of the
codebase merely to avoid defining a contract.

Keep names such as `NotificationDeliveryHistory`, `UserEnrichmentResult`, and
`OrganizationId` specific enough that searching the type name finds its definition and
the places that use the contract. Avoid vague catch-all types named only `Data`,
`Config`, `Result`, or `Context` when a domain name is available.

### 5. Put explanations where a name search lands

Place concise comments immediately above the definition they explain: the function,
method, type, module-level constant, state transition, or other symbol an agent will
reach from a search result.

Explain what the code cannot express by itself, especially:

- why a non-obvious choice is required
- invariants and safety constraints
- ordering, lifecycle, permission, or transaction rules
- compatibility behavior and external protocol quirks
- why a fallback exists and when it is safe

Do not write comments that merely repeat the symbol name or restate obvious syntax.
Keep rationale next to the definition rather than in a distant document that a search
for the symbol is unlikely to open.

Record repository-wide conventions, source locations, naming rules, generated-code
boundaries, and other non-obvious navigation guidance in `AGENTS.md`, `CLAUDE.md`, or
the nearest established conventions file. Keep that guidance current when structure
or terminology changes.

### 6. Make ownership and reverse references discoverable

Before renaming, moving, or splitting a concept, build a complete reference inventory:

- the definition and related overloads or implementations
- direct and indirect callers, including method calls
- imports, exports, re-exports, and package-specifier boundaries
- tests, fixtures, examples, scripts, and generated inputs
- configuration, migrations, docs, and operational references
- deprecated or compatibility paths

Update all references to the canonical spelling. Search for the old spelling after the
change and classify every remaining match; do not assume an import graph or barrel has
revealed every caller. A compatibility bridge must be explicit, temporary or
purposeful, and documented at the boundary.

Keep the definition and its contract visible. Do not hide important behavior behind a
generic dispatcher, anonymous callback, catch-all registry, or indirection whose only
description exists elsewhere. Abstractions are welcome when their names and types
preserve the domain concept they implement.

### 7. Handle legacy paths explicitly

Remove obsolete implementations and aliases when it is safe. If a legacy path must
remain, mark it with the language's deprecation mechanism (such as `@deprecated`), name
the replacement, and explain the removal or compatibility constraint where users and
agents will find it.

Do not let new code, examples, or tests choose a deprecated path. Keep one canonical
implementation; a compatibility wrapper should forward to it rather than create a
second source of truth. Make legacy status visible in names, docs, diagnostics, and
tests where relevant.

### 8. Verify discoverability as an observable contract

After editing, test the codebase the way a search-driven agent would:

1. Search the canonical concept name and confirm that the definition is an obvious
   hit, followed by relevant callers, tests, and docs.
2. Search the old name, synonyms, and generic terms; confirm that remaining matches
   are intentional and documented.
3. Search by likely task vocabulary, not only by implementation symbol. For example:

   ```text
   Where is the notification retry delay calculated?
   Where is delivery history loaded for an organization?
   ```

   The resulting filenames, symbols, comments, and tests should make the answer clear
   without paging through unrelated modules.
4. Check that methods, types, errors, and state names are independently searchable;
   do not verify only top-level functions.
5. Run the nearest compiler or type checker and focused tests, then broaden the checks
   when the change crosses module or public-contract boundaries.

Test observable behavior and invariants, not just the presence of preferred strings.
Add regression coverage for a bug before fixing it when behavior is being corrected.
Do not weaken tests, remove useful type checks, or accept a discoverability change that
silently changes outputs, side effects, permissions, or state transitions.

### 9. Keep the migration coherent

Make the smallest coherent change that improves discoverability for the requested
scope. Do not mix a naming or structure migration with unrelated formatting,
dependency, business-logic, or API changes.

When a public rename, file move, type change, or module split is necessary:

- state the canonical vocabulary and the compatibility policy
- update definitions, callers, tests, docs, configuration, and generated artifacts
- preserve old behavior until the intended migration boundary
- keep a visible deprecation path when removal cannot happen immediately
- update conventions documentation so future code uses the new path

Do not leave a repository in a half-migrated state where both spellings look equally
canonical or where the only explanation of ownership lives in an external tool.

## Explicit anti-patterns

Do not:

- use vague names when a domain-specific name is available
- use multiple spellings or synonyms for one concept
- put unrelated behavior in `utils`, `helpers`, `common`, `misc`, or `manager` buckets
- depend on an IDE, semantic index, import graph, or barrel alone to reveal callers
- hide important ownership behind wildcard exports or anonymous indirection
- leave important contracts implicit in `any`, untyped values, or interchangeable
  primitives
- place the only explanation of a symbol far from its definition
- perform a broad mechanical rename without a reference inventory and compatibility
  plan
- split files solely to satisfy an arbitrary size target
- leave deprecated and canonical implementations with equal status
- change runtime behavior under cover of a discoverability refactor
- skip the baseline or focused compiler and test checks

## Acceptance criteria

The work is complete only when all of the following are true:

- Important concepts have one canonical, specific, domain-oriented spelling.
- Definitions, methods, call sites, types, files, tests, configuration, and docs use
  that spelling consistently.
- A focused `rg` search for an important concept reaches its definition and relevant
  reverse references without a large generic haystack.
- File and module boundaries make domain ownership apparent; no new catch-all module
  hides unrelated concepts.
- Important functions, values, errors, and state transitions have precise,
  searchable contracts and types.
- Semantically different identifiers or units cannot be accidentally interchanged
  where the language can enforce the distinction.
- Test files are named after the source concepts they cover, and test names expose the
  behavior or invariant under review.
- Non-obvious rationale, constraints, and fallbacks are documented immediately above
  the definitions they explain.
- Repository conventions and navigation guidance are recorded in the established
  conventions file and match the resulting structure.
- Legacy paths are removed or visibly deprecated, with a named replacement and no
  duplicate canonical implementation.
- Remaining aliases, old spellings, wildcard exports, and compatibility wrappers are
  intentional, documented, and covered by tests where relevant.
- The nearest compiler or type checker and focused tests pass; broader checks pass
  when the changed boundary requires them.
- Existing behavior, public contracts, output, side effects, permissions, and state
  transitions are preserved unless explicitly changed.
- No unrelated dependencies, formatting churn, or refactors were introduced.

The architectural principle is: **make the words in the source good search terms**.
A greppable codebase gives an agent a short, reliable path from task vocabulary to the
right definition, contract, caller, test, and explanation; precise names and types
make that path useful to humans as well.

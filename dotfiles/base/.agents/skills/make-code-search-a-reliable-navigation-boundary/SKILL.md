---
name: make-code-search-a-reliable-navigation-boundary
description: Rename and restructure code so ordinary filename and text search reaches definitions, callers, tests, and docs in few hops.
disable-model-invocation: true
---

# Make Code Search a Reliable Navigation Boundary

Make names, paths, types, and comments the shortest path from task vocabulary to the right definition, caller, test, and doc, using ordinary filename and text search. A compiler, language server, or index may help, but it must not be the only way to find or understand code.

Apply only where current naming causes needless hops or ambiguity; otherwise report the evidence and change nothing. Preserve behavior, public contracts, persisted formats, output, side effects, and permissions. Discoverability renames, moves, type tightening, module splits, and legacy cleanup are the only intended changes.

## Inspect first

Inventory the important concepts with their definitions, callers, methods, types, paths, tests, fixtures, docs, config, exports, aliases, and legacy implementations. Search the way an agent would, by symbol and by task vocabulary:

```text
rg --files | rg -i 'delivery-history|deliveryHistory|delivery_history'
rg -n 'calculateNotificationRetryBackoff'
```

Note generic names, inconsistent spellings, grab-bag modules, duplicate implementations, and stale paths. Run the narrowest baseline compile and tests, and record preexisting failures.

## Rules

- **A name is a search handle.** Every important concept has a distinctive textual handle at its definition and at meaningful uses: `createStripeClient`, `NotificationDeliveryHistory`, `calculateNotificationRetryBackoff`, `OrganizationId`, not `create`, `data`, `manager`, `helper`, `utils`, `config`, `result`. Method names count, because a call has no import trail and the method name may be the only handle. Qualify a generic word only when its scope does not make it unambiguous. Optimize for signal, not brevity.
- **One spelling per concept** across directories, files, symbols, parameters, imports, exports, config keys, tests, fixtures, and docs. No `organizations` beside `customers`, no `orgId` beside `organizationId`. A compatibility alias keeps the canonical internal name, is documented at the boundary, and is marked legacy.
- **Files and modules carry domain meaning.** Name them for the concept they own and keep definition, implementation, and focused tests together (`notification-delivery-history.ts` beside its `.test.ts`). Split a grab-bag only along a coherent domain boundary, never to hit a line count. Do not let barrel files or wildcard re-exports convey ownership; prefer explicit exports when that makes a source easier to find. Name test files after the source (`stripe.test.ts` for `stripe.ts`, `delivery_history_test.py` for `delivery_history.py`) and test names after the behavior or invariant. Avoid ownership-hiding names like `helpers.ts`, `utils.ts`, `common.ts`, `misc.ts`, `manager.ts`.
- **Types are searchable contracts.** Precise input and output types, branded ids, enums for states, explicit result and error types, named request and response types. Prefer `transferOwnership(userId: UserId, organizationId: OrganizationId, projectId: ProjectId) -> TransferOwnershipResult` to three strings and an untyped return. Use `unknown` only at untrusted boundaries, then narrow. Avoid catch-all `Data`, `Config`, `Result`, `Context`.
- **Explanations sit where a name search lands:** a concise comment above the definition giving the why, invariants, ordering, permission, or transaction rules, compatibility quirks, and why a fallback exists. Never restate the name. Repo-wide conventions (source locations, naming rules, generated-code boundaries) go in `AGENTS.md`, `CLAUDE.md`, or the established conventions file, and stay current.
- **Do not hide behavior behind indirection** (a generic dispatcher, anonymous callback, or catch-all registry) whose only description lives elsewhere.
- **Rust:** `parse`, `new`, `validate`, `run`, `execute`, `context`, `result`, and `value` are fine when the receiver or enclosing module makes the domain unmistakable. Do not mechanically repeat that context in the symbol: when a function is its module's sole entry point, `runner_runtime::main` and `web::run` are clearer than a verb that repeats the module, and a module-owned validator can stay `workflow_validation::validate`. Qualify only when it adds information search would lose (`parse_workflow_source`, `validate_command_spec_tree`, `render_command_help`, `read_leased_job_spec`, `job_expression_context`). Apply the same vocabulary to associated methods, error variants, fixtures, test names, docs, and examples; a precise top-level function does not make up for ambiguous methods or a stale alias elsewhere.
- **Legacy is explicit.** Remove obsolete implementations and aliases when safe. Otherwise mark them deprecated (`@deprecated` or the language's equivalent), name the replacement, state the compatibility or removal constraint, forward to the single canonical implementation, and keep new code, examples, and tests off them.

## Renames

Before renaming, moving, or splitting, inventory every reference: the definition and overloads, direct and indirect callers including method calls, imports, exports, re-exports, tests, fixtures, scripts, generated inputs, config, migrations, docs, and deprecated paths. State the canonical vocabulary and the compatibility policy. Update every reference, then search the old spelling and classify each remaining match. Do not leave a half-migrated tree where both spellings look canonical, and do not mix a rename with formatting, dependency, or logic changes.

A repo-wide request covers source, binaries, exports, feature gates, migrations, config, generated inputs, fixtures, tests, scripts, docs, diagnostics, and parallel implementations that answer the same vocabulary. Renames that cross exports, binaries, persistence names, or wire fields need more than a focused module test.

## Verify

Test as a search-driven agent would:

1. Search the canonical name; the definition is the obvious hit, followed by callers, tests, and docs.
2. Search old names, synonyms, and generic terms; every remaining match is intentional and documented.
3. Search by task vocabulary ("where is the notification retry delay calculated?"); the resulting files, symbols, comments, and tests answer it without paging through unrelated modules.
4. Check that methods, types, errors, and state names are independently searchable, not just top-level functions.
5. Run the compiler or type checker and focused tests, widening when the change crosses public contracts. Test behavior, not preferred strings.

**The test:** a focused `rg` for an important concept returns its definition and reverse references without a large generic haystack.

## Avoid

Vague names, synonyms for one concept, `utils`/`helpers`/`manager` buckets, relying on an IDE or import graph, hidden ownership behind wildcard exports, implicit `any` or untyped contracts, a symbol's only explanation living far away, mechanical renames without an inventory, size-driven splits, behavior changes under cover of a discoverability refactor, and improving one convenient module when the scope is repo-wide.

**Reply:** the vocabulary chosen, renames made, and remaining aliases or old spellings with their status.

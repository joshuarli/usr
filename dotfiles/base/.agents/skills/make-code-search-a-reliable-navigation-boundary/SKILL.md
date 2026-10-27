---
name: make-code-search-a-reliable-navigation-boundary
description: "Apply when asked to make code easier to find by search: rename, retype, or move so filename and text search reach definitions, callers, tests, and docs in few hops. Skip behavior changes."
disable-model-invocation: true
metadata:
  opencode/autoinvoke: "false"
---

# Make Code Search a Reliable Navigation Boundary

Make names, paths, types, and tests the shortest path from task vocabulary to the right definition, caller, test, and doc, using ordinary filename and text search. A compiler, language server, or index may help, but it must not be the only way to find or understand code.

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
- **One spelling per concept** across directories, files, symbols, parameters, imports, exports, config keys, tests, fixtures, and docs. No `organizations` beside `customers`, no `orgId` beside `organizationId`.
- **Files and modules carry domain meaning.** Name them for the concept they own and keep definition, implementation, and focused tests together (`notification-delivery-history.ts` beside its `.test.ts`). Split a grab-bag only along a coherent domain boundary, never to hit a line count. Do not let barrel files or wildcard re-exports convey ownership; prefer explicit exports when that makes a source easier to find. Name test files after the source (`stripe.test.ts` for `stripe.ts`, `delivery_history_test.py` for `delivery_history.py`) and test names after the behavior or invariant. Avoid ownership-hiding names like `helpers.ts`, `utils.ts`, `common.ts`, `misc.ts`, `manager.ts`.
- **Types are searchable contracts.** Precise input and output types, branded ids, enums for states, explicit result and error types, named request and response types. Prefer `transferOwnership(userId: UserId, organizationId: OrganizationId, projectId: ProjectId) -> TransferOwnershipResult` to three strings and an untyped return. Use `unknown` only at untrusted boundaries, then narrow. Avoid catch-all `Data`, `Config`, `Result`, `Context`.
- **The definition explains itself, not a comment.** A name search lands on the definition, so its name, type, and the names of its tests carry the invariant, ordering, permission, or transaction rule, and the legacy marker. When a definition needs a comment to be understood, rename or retype until it does not (`comment-cleanup`). Repo-wide conventions (source locations, naming rules, generated-code boundaries) go in `AGENTS.md`, `CLAUDE.md`, or the established conventions file, and stay current.
- **Do not hide behavior behind indirection** (a generic dispatcher, anonymous callback, or catch-all registry) whose only description lives elsewhere.
- **Rust:** `parse`, `new`, `validate`, `run`, `execute`, `context`, `result`, and `value` are fine when the receiver or enclosing module makes the domain unmistakable. Do not repeat the module in the symbol: a module's sole entry point is `runner_runtime::main` or `web::run`, and a module-owned validator can stay `workflow_validation::validate`. Qualify only when it adds information search would lose (`parse_workflow_source`, `validate_command_spec_tree`, `render_command_help`, `read_leased_job_spec`, `job_expression_context`). Apply the same vocabulary to associated methods, error variants, fixtures, test names, docs, and examples.
- **Legacy is explicit.** Remove obsolete implementations and aliases when safe. Otherwise quarantine them as `dead-code-archaeology` describes: a compatibility alias keeps the canonical internal name and is marked legacy by its name or a deprecation attribute. Report the constraint in the reply.

## Renames

Before renaming, moving, or splitting, inventory every reference: the definition and overloads, direct and indirect callers including method calls, imports, exports, re-exports, tests, fixtures, scripts, generated inputs, config, migrations, docs, and deprecated paths. State the canonical vocabulary and the compatibility policy. Update every reference, then search the old spelling and classify each remaining match. Do not leave a half-migrated tree where both spellings look canonical, and do not mix a rename with formatting, dependency, or logic changes.

A repo-wide request covers source, binaries, exports, feature gates, migrations, config, generated inputs, fixtures, tests, scripts, docs, diagnostics, and parallel implementations that answer the same vocabulary. Renames that cross exports, binaries, persistence names, or wire fields need more than a focused module test.

## Verify

Test as a search-driven agent would:

1. Search the canonical name; the definition is the obvious hit, followed by callers, tests, and docs.
2. Search old names, synonyms, and generic terms; every remaining match is intentional and explained in your reply.
3. Search by task vocabulary ("where is the notification retry delay calculated?"); the resulting files, symbols, and tests answer it without paging through unrelated modules.
4. Check that methods, types, errors, and state names are independently searchable, not just top-level functions.
5. Run the compiler or type checker and focused tests, widening when the change crosses public contracts. Test behavior, not preferred strings.

**The test:** a focused `rg` for an important concept returns its definition and reverse references without a large generic haystack.

**Report:** the vocabulary chosen, renames made, and remaining aliases or old spellings with their status.

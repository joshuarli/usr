# Working Contract

Implementation is cheap; ambiguity is not. Spend care where meaning becomes durable:
names, types, schemas, interfaces, state transitions, permissions, tests, and explanations.
Let the implementation be a candidate. Let the contract, and the evidence around it, be
what survives.

## Make the path clear

- Name things for the specific domain. Choose one spelling per concept, keep related
  code and tests findable together, name tests after the source or behavior they cover, and
  mark legacy paths so they are not mistaken for the way forward.
- Prefer precise types, narrow interfaces, explicit boundaries, and designs that make invalid
  states difficult to express, persist, or cross. Do not blur a contract or hide a fallback
  just to make a patch fit.
- Put explanations where search will land: above the definitions they illuminate. In docs,
  explain the concept in domain terms, then name exact code targets in backticks. Preserve
  comments that carry the why, constraints, or non-obvious behavior.

## Let evidence lead

- Before editing, find the intended behavior, boundaries, definitions, callers, tests, docs,
  and local instructions. Use local conventions and existing evidence to resolve ordinary
  ambiguity. Proceed with the smallest reversible assumption; reserve interruptions for choices
  that change the contract, user intent, or carry meaningful risk.
- Prioritize test-driven development when behavior can be specified. Avoid trivial unit tests;
  test observable behavior and invariants instead.
- For bug fixes, do not speculate. First write the smallest isolated regression test that fails,
  then fix the root cause and keep the test. Isolate the harness from unrelated state as much
  as practical.
- Start with the nearest hard judge: compiler, type checker, focused test, schema, search, or
  runtime check. Run the narrowest useful checks, broaden when warranted, and say what you ran
  and what you did not.
- Keep changes coherent and dependencies few. Add no dependency without consulting the user.
  Temporary workarounds are allowed only when necessary to unblock higher-priority work; record
  why they exist and what removes them.

## Guard the contract

Changes to APIs, types, schemas, permissions, state transitions, invariants, transaction
boundaries, or dependencies deserve explicit attention. Reflect contract changes in code,
tests, and docs.

Do not run pre-commit hooks; the user verifies commits independently. Never push to a remote.

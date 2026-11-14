# Refactor the agent policy system

Implement this task in `joshuarli/usr`. Read `AGENTS.md` and the affected code
before changing it. Use the repository's single-source-of-truth and typed-domain
design principles. Finish the implementation, focused verification, and coherent
commits; a plan alone does not complete the task.

## Why

Commit `23f0997c3d5d12ae73361bb569288fec6f9975a5` changed 15 files to move the
root expert lane to Hydrogen XHigh and remove `god`. Model choices appear in
runtime code, lifecycle names, schemas, profiles, instructions, documentation,
and prose-based tests. Another same-provider model change should require one
authored policy edit and regeneration. Generated diffs may span many files;
manual synchronization must disappear.

Implement the existing USR-52. Keep USR-53's broader skill discovery work,
USR-51's check planner, and USR-54's campaign snapshot separate.

## Policy and types

Extend the existing typed policy nucleus. Give each fact one owner: tier graph,
provider/model pins, effort, tool restrictions, ordered routes, nesting, and
native exceptions. Derive unions, allowlists, schemas, and presentation from
these declarations. Keep distinct root-bridge, native/nested Pi, and
OpenCode-native contexts explicit. Interactive harness defaults retain their
existing owners.

Current behavior is the baseline: new bridge experts use Antigravity's approved
Hydrogen XHigh model with no fallback; `god` is rejected; Argon and Carbon remain
prohibited. Lower tiers retain their ordered approved fallbacks. Native Pi
nesting and OpenCode's native-only exception retain their current constraints.
Audit apparent inconsistencies before deleting an entry or broadening a route.

Use stable executor identities such as `antigravity`, `codex`, `command-code`,
and `pi`. Model choice is data, not a function name or lifecycle discriminator.
Use small discriminated domain types where they remove real invalid states.
Decode external and persisted input from `unknown`; a TypeScript assertion is
not validation. Preserve protocol contracts or document an intentional,
validated correction where the public schema and runtime already disagree.

Resolve and persist the model and effort needed by each admitted session.
Status and continuation use that snapshot, not today's global default. Decode
legacy records explicitly, preserving known pins and refusing ambiguous or
prohibited replay with an actionable diagnostic. A migration never authorizes
a removed tier or provider. Keep worktree ownership, process identity, bounded
retries, and uncertain-admission handling intact.

The policy module must be pure and importable without the Pi SDK, account
credentials, provider CLIs, home configuration, or network access. Expose a
deterministic JSON projection for Python consumers. Live availability remains
the responsibility of `worker_model_check`.

## Deterministic generation

Provide one explicit generation command and one read-only stale-output check.
Prefer a handful of named render functions and generated blocks over a general
template language. If literal substitution or shared prose fragments are useful,
keep their vocabulary explicit and reject unknown references. Do not introduce
expression evaluation, a new configuration language, or a template dependency.

Generate policy tables, concise repeated policy paragraphs, profile frontmatter,
and mechanically related settings from the typed source. Declare every owned
output or region. Reject missing, duplicate, or mismatched markers and invalid
destinations. Validate the complete rendering before writing; preserve authored
surrounding text and unrelated JSON settings. Keep frontmatter first, symlinks
intact, links valid, and unchanged files untouched. Output must have stable
ordering and newlines without timestamps or machine paths.

Commit ordinary self-contained outputs that existing harnesses can read.
Generation happens during development, never during session startup. Preserve
the existing single-contract selector, the normal/lean distinction and lean
size guard, and on-demand references. Keep Python hooks standard-library-only.
Count resolved source paths when inventorying duplication: `skills` and harness
adapters already use symlinks.

Reduce authored policy repetition in the bridge README, orchestration skill,
normal/lean contracts, and setup/Pi/profile docs. Keep useful explanation with
its topic owner. Update ownership guidance to identify the new source and the
regeneration command. Integrate the stale-output check with existing checks and
a cheap automatic CI job, separately from manual host provisioning.

## Verification and completion

Use focused tests that address the migration's actual risks:

- An independent behavior matrix covers exact expert routing, fail-closed
  availability/quota handling, rejected `god`, prohibited models, lower-tier
  fallback, OpenCode's exception, and nesting bounds.
- Boundary cases prove advertised schemas and admission agree; malformed
  persisted state cannot select a different route or lose ownership safeguards.
- Existing sessions retain their admitted pins across a policy change and
  restart. Legacy records have explicit compatibility behavior.
- A test-only model change propagates to runtime policy inspection, generated
  docs, and applicable profiles without editing consumer implementation. A
  current-policy assertion remains independent of the generated source.
- Rendering twice is a no-op; stale checks fail without writing; malformed
  ownership markers leave all outputs untouched; unrelated settings survive.
- Existing instruction selection, profile validation, sync registration, and
  relevant bridge tests still pass. Keep installed-profile validation even
  though tracked profiles are generated.

Run the real type checker and relevant lint/tests. Distinguish successful
fixture proof from unavailable live-account verification. Do not run home sync,
host setup, or paid model jobs as part of this refactor.

Close USR-52 only when its consumers and checks are migrated. Preserve unrelated
backlog items. Report the authoritative files, exact regeneration/check
commands, authored versus generated changes, compatibility decisions, and
verification results. Demonstrate that changing a same-provider model pin no
longer entails a repository-wide manual search-and-replace.

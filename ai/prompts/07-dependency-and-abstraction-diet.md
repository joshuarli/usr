# Dependency and Abstraction Diet

You are improving this codebase so dependencies and abstractions remain only where their real capability, contract, or boundary value justifies their complexity cost.

The goal is to maximize **capability per unit of complexity** while preserving readability, correctness, maintainability, and interoperability.

Scope: direct/transitive dependencies, enabled features, internal abstractions, wrappers, factories, traits/interfaces, and extension points.

Applicability: Apply this prompt only when dependency or abstraction cost is plausibly larger than the real capability, policy, or compatibility value it provides. If the condition is materially absent, report that evidence and make no speculative changes.

Preserve: Existing valid behavior, public contracts, persisted data and formats, output, side effects, permissions, state transitions, and supported-platform semantics unless this request explicitly changes them.

Intentional changes: Only changes explicitly authorized by the invoking request; otherwise none.

If inspection shows that the relevant contract already holds, do not manufacture
changes. Verify it, correct only concrete gaps, and report the evidence.

## First inspect the repository

Before editing:

- inventory direct and transitive dependencies
- identify enabled default/features
- identify duplicated libraries solving overlapping problems
- identify dependencies used for tiny amounts of functionality
- inspect build time, binary/code-size implications where relevant
- inventory traits/interfaces, factories, wrappers, managers, providers, registries, generic layers, callbacks, and forwarding abstractions
- identify abstractions with exactly one implementation
- identify wrappers that add no policy, invariants, translation, or ownership
- run narrow baseline checks before editing

For Rust, inspect `Cargo.toml`, resolved feature graphs, and meaningful crate usage rather than judging dependencies only by count.

- Record failures that predate the work.

## Non-negotiable design

Each numbered requirement defines an invariant or observable behavior, its
authoritative owner or boundary, the shortcut or ambiguous state it prohibits,
and the evidence that proves it. Do not prescribe incidental implementation
structure unless that structure is itself part of the contract.

### 1. Justify dependencies by consumed capability and feature cost

#### Evaluate each dependency by consumed capability


For every suspicious dependency, answer:

- what exact capability do we use?
- how much of the dependency do we use?
- what transitive dependencies/features does it pull in?
- does it affect compile time, binary size, startup, portability, MSRV, licensing, or security surface?
- is the capability difficult or risky to implement correctly ourselves?
- would replacing it create maintenance burden larger than the dependency cost?

Do not remove mature parsing, cryptographic, protocol, compression, Unicode, or other correctness-heavy libraries merely because a local implementation would have fewer lines.

#### Disable gratuitous features


Prefer the minimum dependency feature set that supports actual usage.

Audit default features.

Remove unused features and obsolete optional dependencies.

Do not make feature configuration so granular that it becomes difficult to understand.

### 2. Consolidate overlapping dependencies and replace only truly tiny ones

#### Consolidate overlapping dependencies


If multiple crates/libraries provide substantially the same capability, determine whether one can cover the required surface cleanly.

Examples:

- multiple HTTP clients
- multiple serialization helpers
- multiple CLI parsers
- multiple async runtimes
- multiple regex/glob/path libraries
- multiple error wrappers

Do not force consolidation when platform-specific or semantic differences justify separate choices.

#### Replace tiny dependencies selectively


A dependency may be replaceable when the consumed behavior is:

- small
- stable
- well-specified
- easy to test exhaustively
- not security-sensitive
- not protocol-complex

If replacing it, implement only the behavior the project actually needs and add focused tests.

Do not grow a bespoke mini-framework.

### 3. Keep abstractions only when they express a real boundary or policy

#### Audit abstraction value


For each abstraction, ask what it buys:

- multiple real implementations?
- isolation of an external effect?
- policy?
- invariant enforcement?
- compatibility boundary?
- reusable algorithm?
- ownership/lifecycle clarity?
- simpler callers?

If the answer is merely "future flexibility," consider collapsing it.

#### Collapse forwarding layers


Remove classes/modules/functions that only forward arguments and return values without adding:

- validation
- translation
- policy
- caching
- instrumentation with semantic value
- lifecycle control
- ownership
- compatibility

A direct call is usually clearer than a wrapper whose existence must be rediscovered.

#### Treat single-implementation interfaces skeptically, not dogmatically


A one-implementation trait/interface may still be justified when it isolates:

- filesystem
- clock
- network
- process execution
- persistence
- a stable plugin/API boundary

Otherwise prefer the concrete type until substitution is real.

Do not preserve an interface merely because mocking frameworks prefer it.

### 4. Remove speculative extension points and internal mini-frameworks

#### Remove speculative extension points


Search for:

- generic factories with one product
- registries with one entry
- plugin hooks never used
- callback layers that obscure direct control flow
- generic type parameters always instantiated with one type
- configurable strategies with one supported strategy

Collapse speculative flexibility unless there is an actual compatibility promise or imminent concrete need.

#### Prefer explicit code over tiny internal frameworks


Do not replace a dependency with a homegrown framework.

Do not replace three explicit call sites with a generic abstraction that requires readers to learn a mini-language.

Duplication can be cheaper than the wrong abstraction when the duplicated code does not encode shared evolving knowledge.

### 5. Measure claimed costs while preserving ecosystem compatibility

#### Measure performance-related claims


If dependency or abstraction removal is justified by:

- compile time
- binary size
- runtime speed
- allocation count

measure before and after where practical.

Do not cite hypothetical performance as the reason for churn.

#### Preserve important ecosystem compatibility


Dependencies can provide compatibility value beyond LOC.

Consider:

- standard formats
- upstream behavior
- security updates
- platform quirks
- interoperability
- diagnostics
- long-tail edge cases

Keep a dependency when these benefits dominate its cost.


## Explicit anti-patterns

Do not:

- remove dependencies to optimize a vanity metric
- rewrite security-sensitive or standards-heavy code casually
- build bespoke replacements larger than the dependency usage they replace
- keep wrappers that only forward
- introduce interfaces solely for hypothetical future implementations
- create a generic internal framework to eliminate a little duplication
- measure success only by dependency count or LOC
- collapse genuinely distinct platform/semantic implementations into one awkward abstraction
- make public API changes solely to simplify internals unless explicitly requested


## Verification

After editing:

- inspect the resolved dependency/feature graph
- search for unused abstraction types and compatibility shims
- ensure replacements cover every previously consumed behavior
- run focused and broader tests
- compare build/binary/runtime metrics when those motivated the change
- verify public APIs and observable behavior remain stable


- Distinguish failures that predate the work from regressions introduced by this change.

## Acceptance criteria

The work is complete only when:

- every remaining nontrivial dependency has a clear capability justification
- gratuitous features are disabled
- overlapping dependencies are reduced where sensible
- tiny dependency replacements are simple and exhaustively tested
- forwarding abstractions with no semantic value are removed
- speculative extension points are collapsed
- real effect/compatibility boundaries remain explicit
- no bespoke mini-framework was introduced
- performance claims are measured when relevant
- readability and correctness improve rather than merely dependency/LOC counts
- existing behavior and public contracts are preserved

The architectural principle is: **pay complexity only where it buys a real capability, contract, or boundary.**

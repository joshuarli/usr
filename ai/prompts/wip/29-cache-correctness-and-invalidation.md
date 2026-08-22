# Cache Correctness and Invalidation

You are improving this codebase so caches are clearly derived, bounded, invalidated deliberately, and incapable of silently becoming alternate sources of truth.

The goal is to preserve correctness while making freshness, eviction, and failure semantics explicit.

Scope: in-memory/disk/query/build/HTTP caches, memoization, cache keys, TTLs, invalidation, capacity, negative/stale behavior, and concurrent misses.

Applicability: Apply this prompt only when the repository contains a meaningful cache or memoized derived state. If the condition is materially absent, report that evidence and make no speculative changes.

Preserve: Existing valid behavior, public contracts, persisted data and formats, output, side effects, permissions, state transitions, and supported-platform semantics unless this request explicitly changes them.

Intentional changes: Only changes explicitly authorized by the invoking request; otherwise none.

If inspection shows that the relevant contract already holds, do not manufacture
changes. Verify it, correct only concrete gaps, and report the evidence.

## First inspect the repository

Before editing:

- inventory in-memory caches, disk caches, memoization, HTTP caches, query caches, build caches, singleton memoized values, and "recent result" state
- identify authoritative data behind each cache
- identify keys and key normalization
- identify TTLs
- identify invalidation paths
- identify unbounded caches
- identify cache stampede/concurrent miss behavior
- identify negative caching
- identify fallback-to-stale behavior
- inspect tests around freshness and mutation
- run baseline checks

- Record failures that predate the work.

## Non-negotiable design

Each numbered requirement defines an invariant or observable behavior, its
authoritative owner or boundary, the shortcut or ambiguous state it prohibits,
and the evidence that proves it. Do not prescribe incidental implementation
structure unless that structure is itself part of the contract.

### 1. Name cache authority and define complete keys

#### Name the authority


For every cache, identify the authoritative source.

A cache must never become the only place where durable truth lives unless it is intentionally a datastore rather than a cache.

#### Define key semantics


Keys should include every input that affects the cached result.

Audit for missing dimensions such as:

- user/account
- locale
- permissions
- version
- feature mode
- environment
- normalization

### 2. Define freshness and bound growth

#### Define freshness


Choose intentionally among:

- invalidate-on-write
- TTL
- versioned keys
- explicit refresh
- stale-while-revalidate
- immutable/content-addressed caching

Do not combine multiple freshness schemes accidentally.

#### Bound cache growth


Define:

- capacity
- eviction
- TTL
- memory/disk limits

Unbounded process-lifetime maps are caches whether or not they are called caches.

### 3. Handle concurrent, stale, and negative outcomes deliberately

#### Handle concurrent misses


Prevent expensive duplicate work where needed via:

- request coalescing
- single-flight behavior
- keyed locking

Do not serialize unrelated cache keys globally.

#### Define stale-on-error behavior


Decide whether a stale value may be used when refresh fails.

Make the policy visible and testable.

#### Define negative caching


Caching "not found" or errors can be useful but dangerous.

Specify which negative outcomes are cacheable and for how long.

### 4. Align invalidation with mutation and expose useful cache signals

#### Keep invalidation close to mutation


When authoritative state changes, the code that owns the mutation should make cache consequences obvious.

Avoid distant hidden invalidation hooks.

#### Instrument useful cache behavior


Where operationally relevant, expose:

- hit/miss
- eviction
- refresh failure
- stale serve
- size

Do not instrument trivial local memoization unnecessarily.

### 5. Test the complete freshness contract


Cover:

- hit
- miss
- mutation
- expiration
- concurrent miss
- stale-on-error
- negative cache

as relevant.

### Migration and compatibility policy

Do not create parallel legacy and canonical implementations as part of this work.
If a rename, move, replacement, or contract change becomes necessary, inventory all
references first, keep one canonical path, and retain compatibility only when the
invoking request or an existing external contract requires it.

## Explicit anti-patterns

Do not:

- add a cache without naming authority and invalidation
- use unbounded maps
- omit relevant inputs from keys
- cache errors indiscriminately
- hide stale behavior
- let invalidation depend on unrelated callers
- add cache layers before measuring the underlying cost


## Verification

After editing:

- Run the nearest hard judge for in-memory/disk/query/build/HTTP caches, memoization, cache keys, TTLs, invalidation, capacity, negative/stale behavior, and concurrent misses: the compiler, type checker, schema/build check, or focused tests that can reject an invalid change.
- Test the observable success behavior, failure behavior, edge cases, and invariants established by the numbered requirements.
- Audit authority, key dimensions, freshness, bounds, concurrent misses, stale/negative policy, invalidation ownership, and cache tests; classify every remaining exception rather than assuming it is harmless.
- Broaden checks only when the changed boundary warrants it, and distinguish pre-existing failures from regressions introduced by this work.

## Acceptance criteria

The work is complete only when:

- each cache has a named authoritative source
- cache keys represent all relevant inputs
- freshness/invalidation policy is explicit
- growth is bounded
- concurrent miss behavior is understood
- stale and negative caching are deliberate
- mutation and invalidation ownership align
- cache behavior has focused tests
- caches cannot silently become alternate truth

The architectural principle is: **a cache is derived state with an expiration story, not a faster database you forgot to model.**

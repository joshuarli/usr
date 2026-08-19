# Cache Correctness and Invalidation

You are improving an existing codebase so caches are clearly derived, bounded, invalidated deliberately, and incapable of silently becoming alternate sources of truth.

The goal is not to maximize cache hit rate. The goal is to preserve correctness while making freshness, eviction, and failure semantics explicit.

Preserve externally visible semantics unless stale behavior is itself a defect.

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

## 1. Name the authority

For every cache, identify the authoritative source.

A cache must never become the only place where durable truth lives unless it is intentionally a datastore rather than a cache.

## 2. Define key semantics

Keys should include every input that affects the cached result.

Audit for missing dimensions such as:

- user/account
- locale
- permissions
- version
- feature mode
- environment
- normalization

## 3. Define freshness

Choose intentionally among:

- invalidate-on-write
- TTL
- versioned keys
- explicit refresh
- stale-while-revalidate
- immutable/content-addressed caching

Do not combine multiple freshness schemes accidentally.

## 4. Bound cache growth

Define:

- capacity
- eviction
- TTL
- memory/disk limits

Unbounded process-lifetime maps are caches whether or not they are called caches.

## 5. Handle concurrent misses

Prevent expensive duplicate work where needed via:

- request coalescing
- single-flight behavior
- keyed locking

Do not serialize unrelated cache keys globally.

## 6. Define stale-on-error behavior

Decide whether a stale value may be used when refresh fails.

Make the policy visible and testable.

## 7. Define negative caching

Caching "not found" or errors can be useful but dangerous.

Specify which negative outcomes are cacheable and for how long.

## 8. Keep invalidation close to mutation

When authoritative state changes, the code that owns the mutation should make cache consequences obvious.

Avoid distant hidden invalidation hooks.

## 9. Instrument useful cache behavior

Where operationally relevant, expose:

- hit/miss
- eviction
- refresh failure
- stale serve
- size

Do not instrument trivial local memoization unnecessarily.

## 10. Test freshness semantics

Cover:

- hit
- miss
- mutation
- expiration
- concurrent miss
- stale-on-error
- negative cache

as relevant.

## Explicit anti-patterns

Do not:

- add a cache without naming authority and invalidation
- use unbounded maps
- omit relevant inputs from keys
- cache errors indiscriminately
- hide stale behavior
- let invalidation depend on unrelated callers
- add cache layers before measuring the underlying cost

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

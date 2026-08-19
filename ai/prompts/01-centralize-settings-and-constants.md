# Consolidate Settings, Constants, and Tunable Policy

You are improving an existing codebase so its tunable behavior, fixed constants, defaults, limits, thresholds, timeouts, feature switches, environment-controlled values, and other policy knobs are easy to discover and reason about.

The goal is **not** to dump every literal into one giant constants file. The goal is to make configuration and policy explicit, typed, centralized at the correct ownership boundary, and distinguishable from implementation details.

Preserve runtime behavior and public contracts unless this request explicitly changes them.

## First inspect the repository

Before editing:

- inventory configuration files, environment variables, CLI defaults, build-time values, feature flags, constants, static values, limits, retry parameters, polling intervals, timeouts, buffer sizes, capacities, thresholds, protocol values, path defaults, URLs, user-agent strings, and other tunable behavior
- search for duplicated literals and repeated numeric/string values
- identify values whose meaning is implicit because they appear inline inside implementation code
- identify multiple mechanisms for configuring the same behavior
- identify values that are truly protocol/domain constants and should **not** become runtime settings
- identify constants that belong locally to one module rather than globally
- run the narrowest useful baseline compiler/type-checker and focused tests before changing code

Do not mechanically hoist every literal.

## 1. Establish a clear taxonomy

Classify values before moving them.

### Runtime settings

Values intentionally configurable by the user, deployment, environment, config file, or CLI.

Examples:

- server address
- cache directory
- concurrency
- retry count
- timeout
- log level
- feature toggle

These should flow through a typed runtime settings/configuration model.

### Application policy

Values chosen by the application that may reasonably be tuned by maintainers but are not currently user-configurable.

Examples:

- retry backoff bounds
- batching thresholds
- queue capacities
- debounce intervals
- maximum retained history

Collect these in a clearly named settings/policy module or in domain-specific settings structures.

### Domain/protocol constants

Values fixed by an external protocol, file format, ABI, mathematical definition, wire contract, or hard invariant.

Examples:

- magic bytes
- protocol version tags
- fixed header sizes
- RFC-defined values
- database schema identifiers

Keep these near the domain/protocol implementation that owns them. Do not pretend they are configurable.

### Local implementation constants

Values meaningful only to one small implementation unit.

Keep them local when locality improves understanding. Do not create a global junk drawer.

## 2. Create one obvious settings boundary

Establish one obvious location for application-wide configuration and policy, using the conventions of the language and repository.

Typical shapes:

```text
src/settings.rs
src/settings/
  mod.rs
  runtime.rs
  policy.rs
```

or the equivalent for the project.

Avoid:

```text
constants.rs
globals.rs
misc.rs
common.rs
config_utils.rs
```

unless the repository already has a coherent established convention.

The settings boundary should expose typed structures rather than an unstructured bag of globals.

For example:

```rust
pub struct RuntimeSettings {
    pub cache_dir: PathBuf,
    pub worker_count: NonZeroUsize,
    pub request_timeout: Duration,
}

pub struct RetryPolicy {
    pub max_attempts: NonZeroU32,
    pub initial_backoff: Duration,
    pub max_backoff: Duration,
}
```

Prefer domain-specific nested settings over dozens of unrelated top-level constants.

## 3. Centralize defaults

A setting must have one authoritative default.

Do not maintain the same default separately in:

- CLI declarations
- environment parsing
- config-file parsing
- constructors
- documentation
- tests

Define the default once and have the relevant consumers derive behavior from it.

If documentation cannot be generated from the same source, add tests that detect drift where practical.

## 4. Normalize configuration once

Raw configuration sources should be read at a narrow boundary.

Prefer:

```text
CLI
environment
config file
platform discovery
        ↓
raw inputs
        ↓
parse + validate + resolve precedence
        ↓
typed Settings
        ↓
application
```

Do not let arbitrary modules call environment-variable APIs, parse raw config strings, or independently apply defaults.

Define and document precedence when multiple sources can control the same setting, for example:

```text
CLI > environment > project config > user config > defaults
```

Preserve the project's existing precedence unless intentionally changing it.

## 5. Make units and semantics explicit

Do not expose ambiguous scalar constants such as:

```text
TIMEOUT = 30
LIMIT = 100
SIZE = 4096
```

Prefer typed values or names that make semantics and units obvious:

```text
request_timeout: Duration
max_pending_jobs: NonZeroUsize
read_buffer_capacity_bytes: usize
```

Use `Duration`, path types, byte-size types, enums, newtypes, or validated domain values when available.

Avoid storing parsed values as strings after the configuration boundary.

## 6. Eliminate duplicated magic values

Search for repeated literals that encode one policy.

Examples:

```text
3 retries
30-second timeout
64 KiB chunk size
100-item batch size
"localhost"
```

If multiple occurrences represent the same policy, replace them with the canonical setting or constant.

Do not combine values merely because their literals happen to be equal. Two unrelated `30` values are not necessarily one concept.

## 7. Keep ownership visible

Centralization does not mean one enormous global file.

Application-wide policy belongs in the application settings boundary.

Domain-specific constants should remain with their domain when moving them globally would hide ownership.

Good:

```text
settings::RuntimeSettings
settings::SchedulerPolicy
http::MAX_HEADER_BYTES
archive_format::MAGIC
```

Bad:

```text
constants::MAX
constants::TIMEOUT
constants::VERSION
constants::MAGIC
```

The question is: **where would a maintainer naturally look to change or understand this value?**

## 8. Avoid mutable global configuration

Do not introduce mutable process-wide globals merely to centralize configuration.

Prefer constructing immutable typed settings and passing the relevant subset to components that need them.

Where global initialization is unavoidable, make initialization order and mutation semantics explicit and constrained.

## 9. Validate settings at construction

Reject invalid combinations once, near the configuration boundary.

Examples:

- zero worker count
- minimum greater than maximum
- retry backoff maximum smaller than initial delay
- mutually exclusive modes
- invalid paths or malformed URLs where validation is appropriate

Downstream code should be able to rely on the invariants of the typed settings model instead of repeatedly defending against malformed configuration.

## 10. Make settings discoverable

A search for terms such as:

```text
timeout
retry
concurrency
buffer
batch
cache
limit
interval
```

should lead quickly to the authoritative setting or policy definition.

Document non-obvious policy choices immediately next to the setting definition, especially when a value exists because of an external constraint or measured tradeoff.

## Explicit anti-patterns

Do not:

- move every literal into a giant constants file
- create global mutable configuration
- turn protocol invariants into user settings
- leave duplicate defaults in multiple parsers or constructors
- read environment variables throughout business logic
- store all settings as strings
- use ambiguous unitless numbers
- merge unrelated values because their literals match
- introduce a configuration framework merely for architectural symmetry
- change defaults or precedence accidentally during the cleanup
- create dozens of one-line constants that make code harder to read
- centralize domain-owned constants so aggressively that ownership becomes obscure

## Verification

After editing:

- search for each migrated setting and confirm one authoritative definition
- search for old literal/default copies and classify every remaining match
- verify runtime configuration precedence
- verify invalid settings are rejected at the boundary
- verify domain/protocol constants remain fixed and locally understandable
- run focused tests and the nearest compiler/type checker
- add tests for default values and precedence where those contracts matter

## Acceptance criteria

The work is complete only when:

- runtime settings have one typed configuration boundary
- application policy knobs are obvious and intentionally located
- every configurable value has one authoritative default
- raw environment/config/CLI values are normalized once
- downstream code consumes typed settings rather than reparsing raw sources
- duplicated magic values representing the same policy are removed
- units and semantics are explicit
- protocol/domain constants remain owned by their domains
- mutable global configuration has not been introduced
- invalid configuration is rejected before business logic executes
- settings and policy are easy to locate with ordinary text search
- existing behavior, defaults, precedence, and public contracts are preserved unless explicitly changed

The architectural principle is: **configuration is policy, and policy should have an obvious, typed, authoritative home.**

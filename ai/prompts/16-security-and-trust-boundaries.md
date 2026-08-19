# Security and Trust Boundary Audit

You are improving an existing codebase so trust transitions are explicit and untrusted input cannot silently acquire authority.

The goal is practical boundary hardening, not speculative security theater.

Preserve intended capabilities and compatibility unless fixing a concrete vulnerability.

## First inspect the repository

Inventory trust boundaries involving:

- user input
- filesystem paths
- subprocesses
- environment variables
- network responses
- credentials/secrets
- config files
- archives
- symlinks
- temporary files
- permissions
- deserialization
- database content
- plugin/extensions
- unsafe/native code

Identify where untrusted data becomes trusted.

## 1. Mark trust transitions

For each external input, identify:

- source
- validation
- authority granted
- side effects it can trigger

## 2. Avoid shell reinterpretation

Pass subprocess arguments structurally.

Use a shell only when shell semantics are intentionally required.

## 3. Harden path handling

Consider:

- traversal
- symlinks
- race conditions
- absolute vs relative paths
- root confinement
- replacement semantics
- permissions

Do not assume lexical normalization provides filesystem security.

## 4. Handle secrets deliberately

Avoid secrets in:

- logs
- command lines when avoidable
- error messages
- persisted debug dumps
- world-readable temp files

Keep secret lifetime and scope narrow.

## 5. Validate deserialization boundaries

Treat parsed external data as untrusted even when syntax is valid.

Apply semantic validation before use.

## 6. Make privilege transitions explicit

If code runs with elevated privileges or acts on behalf of another identity, isolate the privileged operations and minimize their surface.

## 7. Secure temporary resources

Use safe creation APIs, restrictive permissions where appropriate, unpredictable names when required, and cleanup.

## 8. Audit unsafe/native boundaries

For unsafe code, FFI, mmap, raw pointers, syscalls:

- document safety preconditions
- keep unsafe blocks narrow
- validate inputs before crossing
- add tests around the safe wrapper

## 9. Avoid denial-of-service footguns

Bound:

- input sizes
- recursion
- queue growth
- decompression expansion
- concurrency
- retries

where external input can control resource consumption.

## Explicit anti-patterns

Do not:

- add generic sanitization everywhere
- assume string escaping solves structural command/path problems
- log secrets for debugging
- trust deserialized data because parsing succeeded
- broaden privileges for convenience
- use unsafe code without documented preconditions
- add arbitrary limits without understanding real workloads

## Acceptance criteria

The work is complete only when:

- trust boundaries are identifiable
- untrusted input is validated before authority is granted
- subprocess execution avoids unintended shell interpretation
- path-sensitive operations define symlink/traversal semantics
- secrets have controlled scope and are not leaked
- unsafe/native boundaries document and enforce preconditions
- externally controlled resource growth is bounded where necessary
- security changes remain proportional and understandable

The architectural principle is: **trust should increase only at explicit, validated boundaries.**

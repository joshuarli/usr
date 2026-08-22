# Security and Trust Boundary Audit

You are improving this codebase so trust transitions are explicit and untrusted input cannot silently acquire authority.

The goal is practical boundary hardening, not speculative security theater.

Scope: trust boundaries involving input, paths, subprocesses, secrets, deserialization, temporary resources, privileges, unsafe/native code, and resource limits.

Applicability: Apply this prompt only when untrusted data can influence authority, resource consumption, filesystem/process behavior, or secret handling. If the condition is materially absent, report that evidence and make no speculative changes.

Preserve: Existing valid behavior, public contracts, persisted data and formats, output, side effects, permissions, state transitions, and supported-platform semantics unless this request explicitly changes them.

Intentional changes: Only changes explicitly authorized by the invoking request; otherwise none.

If inspection shows that the relevant contract already holds, do not manufacture
changes. Verify it, correct only concrete gaps, and report the evidence.

## First inspect the repository

Before editing:

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

- Record failures that predate the work.

## Non-negotiable design

Each numbered requirement defines an invariant or observable behavior, its
authoritative owner or boundary, the shortcut or ambiguous state it prohibits,
and the evidence that proves it. Do not prescribe incidental implementation
structure unless that structure is itself part of the contract.

### 1. Identify trust transitions and preserve structural subprocess safety

#### Mark trust transitions


For each external input, identify:

- source
- validation
- authority granted
- side effects it can trigger

#### Avoid shell reinterpretation


Pass subprocess arguments structurally.

Use a shell only when shell semantics are intentionally required.

### 2. Harden path and secret handling at authority boundaries

#### Harden path handling


Consider:

- traversal
- symlinks
- race conditions
- absolute vs relative paths
- root confinement
- replacement semantics
- permissions

Do not assume lexical normalization provides filesystem security.

#### Handle secrets deliberately


Avoid secrets in:

- logs
- command lines when avoidable
- error messages
- persisted debug dumps
- world-readable temp files

Keep secret lifetime and scope narrow.

### 3. Validate deserialized data and isolate privilege transitions

#### Validate deserialization boundaries


Treat parsed external data as untrusted even when syntax is valid.

Apply semantic validation before use.

#### Make privilege transitions explicit


If code runs with elevated privileges or acts on behalf of another identity, isolate the privileged operations and minimize their surface.

### 4. Secure temporary/native boundaries and bound attacker-controlled resource use

#### Secure temporary resources


Use safe creation APIs, restrictive permissions where appropriate, unpredictable names when required, and cleanup.

#### Audit unsafe/native boundaries


For unsafe code, FFI, mmap, raw pointers, syscalls:

- document safety preconditions
- keep unsafe blocks narrow
- validate inputs before crossing
- add tests around the safe wrapper

#### Avoid denial-of-service footguns


Bound:

- input sizes
- recursion
- queue growth
- decompression expansion
- concurrency
- retries

where external input can control resource consumption.

### Migration and compatibility policy

Do not create parallel legacy and canonical implementations as part of this work.
If a rename, move, replacement, or contract change becomes necessary, inventory all
references first, keep one canonical path, and retain compatibility only when the
invoking request or an existing external contract requires it.

## Explicit anti-patterns

Do not:

- add generic sanitization everywhere
- assume string escaping solves structural command/path problems
- log secrets for debugging
- trust deserialized data because parsing succeeded
- broaden privileges for convenience
- use unsafe code without documented preconditions
- add arbitrary limits without understanding real workloads


## Verification

After editing:

- Run the nearest hard judge for trust boundaries involving input, paths, subprocesses, secrets, deserialization, temporary resources, privileges, unsafe/native code, and resource limits: the compiler, type checker, schema/build check, or focused tests that can reject an invalid change.
- Test the observable success behavior, failure behavior, edge cases, and invariants established by the numbered requirements.
- Audit trust transitions, shell/path handling, secrets, deserialization, privileges, temp resources, unsafe boundaries, and DoS limits; classify every remaining exception rather than assuming it is harmless.
- Broaden checks only when the changed boundary warrants it, and distinguish pre-existing failures from regressions introduced by this work.

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

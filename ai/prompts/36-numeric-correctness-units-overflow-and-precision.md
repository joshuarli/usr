# Numeric Correctness: Units, Overflow, and Precision

You are improving this codebase so numeric calculations have explicit units, ranges, overflow behavior, rounding semantics, and precision appropriate to the domain.

The goal is to prevent subtle bugs caused by unit confusion, integer truncation, floating-point assumptions, unchecked arithmetic, and ambiguous rounding.

Scope: numeric values and calculations involving units, widths/signs, overflow, rounding, money/decimals, floating point, ranges, and thresholds.

Applicability: Apply this prompt only when numeric semantics are material enough that unit, range, precision, overflow, or rounding mistakes could affect correctness. If the condition is materially absent, report that evidence and make no speculative changes.

Preserve: Existing valid behavior, public contracts, persisted data and formats, output, side effects, permissions, state transitions, and supported-platform semantics unless this request explicitly changes them.

Intentional changes: Only changes explicitly authorized by the invoking request; otherwise none.

If inspection shows that the relevant contract already holds, do not manufacture
changes. Verify it, correct only concrete gaps, and report the evidence.

## First inspect the repository

Before editing:

- inventory numeric fields and calculations
- identify money
- identify timestamps/durations
- identify byte counts
- identify percentages/rates
- identify indexes/counts
- identify coordinate/measurement math
- identify integer casts
- identify floating-point equality
- identify division and rounding
- identify multiplication/addition that may overflow
- identify parsing boundaries and serialized numeric ranges
- run baseline tests

- Record failures that predate the work.

## Non-negotiable design

Each numbered requirement defines an invariant or observable behavior, its
authoritative owner or boundary, the shortcut or ambiguous state it prohibits,
and the evidence that proves it. Do not prescribe incidental implementation
structure unless that structure is itself part of the contract.

### 1. Make units, numeric ranges, and overflow semantics explicit

#### Make units explicit


Use domain/unit types where practical.

At minimum, names should distinguish:

```text
timeout_ms
size_bytes
rate_per_second
```

Prefer standard `Duration`/quantity types where available.

#### Audit integer width and sign


Choose types based on valid domain range, not habit.

Be careful with:

- signed/unsigned mixing
- platform-sized integers
- serialization width
- database width
- FFI width

#### Define overflow behavior


For arithmetic that can exceed range, choose deliberately:

- checked
- saturating
- wrapping
- widened intermediate
- explicit error

Do not rely on debug-vs-release differences.

### 2. Define rounding and exact-versus-approximate representation

#### Define rounding


For division/conversion, specify:

- floor
- ceil
- nearest
- ties-to-even
- truncation

Especially for:

- money
- percentages
- durations
- rate limiting
- allocation/sharding

#### Avoid floating point where exact decimal semantics matter


Money and exact decimal quantities may require integer minor units or decimal representations.

Do not replace floating point categorically where approximate real-valued computation is appropriate.

#### Avoid direct float equality when semantics are approximate


Use domain-appropriate tolerances or exact representations.

Do not use arbitrary epsilon without understanding scale.

### 3. Validate domain ranges and account for cumulative numerical error

#### Validate numeric input ranges


Parsing success does not mean domain validity.

Reject negative counts, impossible percentages, zero denominators, and out-of-range values at boundaries.

#### Watch cumulative error


For repeated addition/integration/statistics, consider numerical stability when it materially affects results.

### 4. Test numeric boundaries and thresholds


Cover:

- zero
- one
- min/max
- just below/above thresholds
- overflow edges
- rounding boundaries
- negative values where relevant

### Migration and compatibility policy

Do not create parallel legacy and canonical implementations as part of this work.
If a rename, move, replacement, or contract change becomes necessary, inventory all
references first, keep one canonical path, and retain compatibility only when the
invoking request or an existing external contract requires it.

## Explicit anti-patterns

Do not:

- use bare numbers with ambiguous units
- cast between widths/signs casually
- rely on overflow behavior accidentally
- use float equality blindly
- use arbitrary epsilon constants
- use floating point for exact money without a deliberate model
- hide rounding in integer division


## Verification

After editing:

- Run the nearest hard judge for numeric values and calculations involving units, widths/signs, overflow, rounding, money/decimals, floating point, ranges, and thresholds: the compiler, type checker, schema/build check, or focused tests that can reject an invalid change.
- Test the observable success behavior, failure behavior, edge cases, and invariants established by the numbered requirements.
- Audit units, integer widths/signs, overflow, rounding, exact/approximate representations, range validation, cumulative error, and boundary tests; classify every remaining exception rather than assuming it is harmless.
- Broaden checks only when the changed boundary warrants it, and distinguish pre-existing failures from regressions introduced by this work.

## Acceptance criteria

The work is complete only when:

- important units are explicit
- numeric ranges fit their types
- overflow behavior is deliberate
- rounding policy is defined
- exact-decimal domains use suitable representations
- approximate comparisons use justified tolerances
- boundary validation rejects invalid numeric states
- edge-case tests protect thresholds and limits

The architectural principle is: **numbers are domain values with units and bounds, not interchangeable scalars.**

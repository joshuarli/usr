# Numeric Correctness: Units, Overflow, and Precision

You are improving an existing codebase so numeric calculations have explicit units, ranges, overflow behavior, rounding semantics, and precision appropriate to the domain.

The goal is to prevent subtle bugs caused by unit confusion, integer truncation, floating-point assumptions, unchecked arithmetic, and ambiguous rounding.

Preserve numerical behavior unless correcting a demonstrated defect.

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

## 1. Make units explicit

Use domain/unit types where practical.

At minimum, names should distinguish:

```text
timeout_ms
size_bytes
rate_per_second
```

Prefer standard `Duration`/quantity types where available.

## 2. Audit integer width and sign

Choose types based on valid domain range, not habit.

Be careful with:

- signed/unsigned mixing
- platform-sized integers
- serialization width
- database width
- FFI width

## 3. Define overflow behavior

For arithmetic that can exceed range, choose deliberately:

- checked
- saturating
- wrapping
- widened intermediate
- explicit error

Do not rely on debug-vs-release differences.

## 4. Define rounding

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

## 5. Avoid floating point where exact decimal semantics matter

Money and exact decimal quantities may require integer minor units or decimal representations.

Do not replace floating point categorically where approximate real-valued computation is appropriate.

## 6. Avoid direct float equality when semantics are approximate

Use domain-appropriate tolerances or exact representations.

Do not use arbitrary epsilon without understanding scale.

## 7. Validate numeric input ranges

Parsing success does not mean domain validity.

Reject negative counts, impossible percentages, zero denominators, and out-of-range values at boundaries.

## 8. Watch cumulative error

For repeated addition/integration/statistics, consider numerical stability when it materially affects results.

## 9. Test boundaries

Cover:

- zero
- one
- min/max
- just below/above thresholds
- overflow edges
- rounding boundaries
- negative values where relevant

## Explicit anti-patterns

Do not:

- use bare numbers with ambiguous units
- cast between widths/signs casually
- rely on overflow behavior accidentally
- use float equality blindly
- use arbitrary epsilon constants
- use floating point for exact money without a deliberate model
- hide rounding in integer division

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
